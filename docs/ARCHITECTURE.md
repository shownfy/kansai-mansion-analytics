# 関西マンションAI - 設計・実装ドキュメント

## 1. システム概要

### 1.1 目的

関西地方（大阪、京都、兵庫、奈良、滋賀、和歌山）のマンション価格を予測するWebアプリケーション。
ユーザーが住所、間取り、面積、建築年、最寄駅までの時間を入力すると、機械学習モデルが将来の価格を予測する。

### 1.2 主要機能

- マンション価格の予測（入力: 住所、間取り、面積、建築年、最寄駅までの時間）
- 5年刻みの価格推移グラフ
- 築50年までの予測制限（精度担保）

### 1.3 モデル精度

| 指標 | 値 |
|------|-----|
| MAPE | 69.05% |
| R² | 0.86 |
| 学習データ件数 | 約283,000件 |

---

## 2. アーキテクチャ

### 2.1 全体構成

```
┌─────────────────────────────────────────────────────────────────┐
│                        クライアント                              │
│                         (ブラウザ)                               │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTPS
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Streamlit Cloud                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                  streamlit_app.py                        │   │
│  │  ┌───────────────────┐  ┌────────────────────────────┐  │   │
│  │  │   入力フォーム     │  │   結果表示 + グラフ        │  │   │
│  │  └───────────────────┘  └────────────────────────────┘  │   │
│  │                           │                              │   │
│  │                           ▼                              │   │
│  │  ┌─────────────────────────────────────────────────┐    │   │
│  │  │   MansionPricePredictor (@st.cache_resource)    │    │   │
│  │  │  ┌───────────────┐  ┌────────────────────────┐  │    │   │
│  │  │  │FeatureEngineer│  │ 学習済みモデル (joblib)│  │    │   │
│  │  │  └───────────────┘  └────────────────────────┘  │    │   │
│  │  │                                                  │    │   │
│  │  │  ┌────────────────────────────────────────────┐ │    │   │
│  │  │  │ マスターデータ (駅/市区町村/ハザード)       │ │    │   │
│  │  │  └────────────────────────────────────────────┘ │    │   │
│  │  └─────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                      │
                      │ 学習時のみ（ローカル）
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     データパイプライン                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 不動産情報API │──▶│   DuckDB    │──▶│    dbt      │          │
│  │    (生データ) │  │  (データ保存) │  │ (データ変換) │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 コンポーネント構成

| コンポーネント | 役割 | 技術 | ファイル |
|----------------|------|------|----------|
| UI | ユーザーインターフェース | Streamlit | streamlit_app.py |
| 予測エンジン | 価格予測ロジック | MansionPricePredictor | predictor.py |
| 特徴量変換 | 入力データの変換 | MansionFeatureEngineer | feature_engineering.py |
| MLモデル | 価格予測 | Gradient Boosting (scikit-learn) | trainer.py |
| データパイプライン | データ変換 | dbt + DuckDB | dbt_project/ |
| 設定管理 | 府県コード等の集約 | Settings (pydantic-settings) | settings.py |

### 2.3 キャッシング戦略

Streamlitアプリでは`@st.cache_resource`デコレータを使用してモデルをキャッシュし、再実行時のパフォーマンスを最適化している。

```python
@st.cache_resource
def load_predictor() -> MansionPricePredictor | None:
    """予測モデルをロード（キャッシュ付き）"""
    model_path = Path("models/mansion_price_model.pkl")
    if model_path.exists():
        return MansionPricePredictor(model_path)
    return None
```

---

## 3. データパイプライン

### 3.1 データソース

**国土交通省 不動産情報ライブラリAPI**

- エンドポイント: `https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001`
- 取得データ: 不動産取引価格情報
- 対象: 関西6府県の中古マンション
- データ期間: **2005年〜現在**（約20年分）
- 取得方式: 非同期（httpx + tenacity によるリトライ機構）

**内部マスターデータ**

| データ | ファイル | 件数 | 内容 |
|--------|----------|------|------|
| 駅乗降客数 | station_data.py | 110駅 | 関西主要駅の乗降客数 |
| 市区町村平均単価 | municipality_data.py | 123市区町村 | 市区町村別の平均㎡単価 |
| ハザードリスク | hazard_data.py | 63市区町村 | 洪水・津波・土砂災害リスクスコア |

### 3.2 dbtモデル設計（ディメンショナルモデリング）

```
┌─────────────────────────────────────────────────────────────────┐
│                      dbt レイヤー構成                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │   raw (ソース)                                           │   │
│  │   └── transaction_data        ← APIレスポンス            │   │
│  └─────────────────────┬───────────────────────────────────┘   │
│                        │                                        │
│                        ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │    staging                                               │   │
│  │    └── stg_transactions   ← クレンジング、型変換          │   │
│  └─────────────────────┬───────────────────────────────────┘   │
│                        │                                        │
│      ┌─────────────────┼─────────────────────┐                 │
│      ▼                 ▼                     ▼                 │
│  ┌────────┐ ┌────────────────┐ ┌────────────────┐             │
│  │  dim_  │ │     dim_       │ │      dim_      │             │
│  │prefec- │ │ municipality   │ │   structure    │             │
│  │ ture   │ │ (価格統計付き)  │ │  / floor_plan  │             │
│  └────┬───┘ └───────┬────────┘ └───────┬────────┘             │
│       │             │                  │                       │
│       └─────────────┼──────────────────┘                       │
│                     ▼                                          │
│            ┌─────────────────┐                                 │
│            │      facts      │                                 │
│            │ fct_transactions│                                 │
│            └────────┬────────┘                                 │
│                     │                                          │
│                     ▼                                          │
│            ┌─────────────────┐                                 │
│            │      marts      │                                 │
│            │ mart_training_  │                                 │
│            │    dataset      │                                 │
│            └─────────────────┘                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 ディメンションテーブル

| テーブル | 説明 | 主なカラム |
|----------|------|-----------|
| dim_prefecture | 府県マスタ | prefecture_id, prefecture_name, prefecture_code, prefecture_rank |
| dim_municipality | 市区町村マスタ | municipality_id, municipality, avg_price_per_sqm, area_rank |
| dim_structure | 構造マスタ | structure_id, structure_type, price_factor |
| dim_floor_plan | 間取りマスタ | floor_plan_id, floor_plan_name, num_rooms, has_ldk |

### 3.4 ステージング層の処理

stg_transactions では以下の処理を行う:

- マンション物件のフィルタリング（`Type like '%マンション%'`）
- 建築年の正規化（令和/平成/昭和 → 西暦）
- 空文字・NULL値の処理
- 数値型への変換

---

## 4. 機械学習モデル

### 4.1 特徴量

| カテゴリ | 特徴量名 | 説明 | データソース |
|----------|----------|------|-------------|
| 基本 | area_sqm | 面積（平米） | API |
| 基本 | building_age | 築年数 | API（計算） |
| 基本 | num_rooms | 部屋数 | API（パース） |
| 基本 | has_ldk | LDKの有無 | API（パース） |
| 建物 | structure_type | 構造 | API |
| 建物 | coverage_ratio | 建蔽率 | API |
| 建物 | floor_area_ratio | 容積率 | API |
| 立地 | prefecture_code | 府県コード（1-6） | 住所から推定 |
| 立地 | time_to_station_min | 最寄駅徒歩時間 | ユーザー入力 |
| 地域統計 | city_avg_price_per_sqm | 市区町村平均単価 | municipality_data.py |
| 地域統計 | station_avg_price_per_sqm | 駅周辺平均単価 | 推定（市区町村×1.1） |
| 駅情報 | log_passenger_count | 乗降客数（対数） | station_data.py |
| 駅情報 | station_rank | 駅規模 | 乗降客数から判定 |
| リスク | total_hazard_risk | 災害リスクスコア | hazard_data.py |
| リスク | hazard_risk_category | リスクカテゴリ | hazard_data.py |
| 時系列 | trade_year | 取引年 | API |
| 時系列 | quarter | 取引四半期 | API |

### 4.2 特徴量変換

```python
# 数値特徴量 → StandardScaler
NUMERIC_FEATURES = [
    "area_sqm", "building_age", "num_rooms", "time_to_station_min",
    "coverage_ratio", "floor_area_ratio", "city_avg_price_per_sqm",
    "station_avg_price_per_sqm", "log_passenger_count", "total_hazard_risk",
    "trade_year", "quarter"
]

# カテゴリカル特徴量 → OneHotEncoder
CATEGORICAL_FEATURES = [
    "structure_type", "has_ldk", "prefecture_code",
    "station_rank", "hazard_risk_category"
]
```

### 4.3 モデル

**Gradient Boosting Regressor** (scikit-learn)

- GridSearchCVによるハイパーパラメータチューニング
- 5-Fold Cross Validation

### 4.4 特徴量重要度（上位10）

| 特徴量 | 重要度 |
|--------|--------|
| area_sqm | 30.0% |
| building_age | 22.7% |
| trade_year | 15.1% |
| station_avg_price_per_sqm | 11.6% |
| city_avg_price_per_sqm | 9.9% |
| time_to_station_min | 4.3% |
| log_passenger_count | 1.7% |
| floor_area_ratio | 0.8% |
| num_rooms | 0.8% |
| prefecture_code_3 | 0.7% |

### 4.5 予測制限

- **築50年まで**: 50年以降は予測精度が低下するため表示しない

---

## 5. ディレクトリ構造

```
kansai-mansion-analytics/
├── streamlit_app.py           # Streamlit アプリ（メインエントリ）
├── requirements.txt           # Streamlit Cloud 用依存関係
├── pyproject.toml             # プロジェクト設定
├── .env.example               # 環境変数テンプレート
│
├── data/
│   ├── raw/                   # 生データ（JSON）
│   └── database/              # DuckDBファイル
│       └── mansion.duckdb     # メインDB
│
├── dbt_project/               # dbtプロジェクト
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── models/
│       ├── staging/           # ステージング層
│       │   └── stg_transactions.sql
│       ├── dimensions/        # ディメンションテーブル
│       │   ├── dim_prefecture.sql
│       │   ├── dim_municipality.sql
│       │   ├── dim_structure.sql
│       │   └── dim_floor_plan.sql
│       ├── facts/             # ファクトテーブル
│       │   └── fct_transactions.sql
│       └── marts/             # マート層
│           └── mart_training_dataset.sql
│
├── src/
│   ├── config/
│   │   └── settings.py        # 設定管理（府県コード等の集約）
│   ├── data/
│   │   ├── api_client.py      # 不動産情報APIクライアント（非同期）
│   │   ├── station_data.py    # 駅乗降客数データ（110駅）
│   │   ├── municipality_data.py  # 市区町村平均単価データ（123市区町村）
│   │   └── hazard_data.py     # ハザードマップデータ（63市区町村）
│   ├── features/
│   │   └── feature_engineering.py  # 特徴量エンジニアリング
│   └── models/
│       ├── trainer.py         # モデル学習
│       └── predictor.py       # 予測処理
│
├── models/                    # 学習済みモデル
│   └── mansion_price_model.pkl
│
├── scripts/
│   ├── fetch_data.py          # データ取得
│   └── train_model.py         # モデル学習
│
├── tests/                     # テスト
│   ├── conftest.py
│   ├── test_features/
│   │   └── test_feature_engineering.py
│   └── test_models/
│       └── test_predictor.py
│
└── docs/
    └── ARCHITECTURE.md        # 本ドキュメント
```

---

## 6. 実行方法

### 6.1 ローカル開発

```bash
# 仮想環境の作成・有効化
python -m venv .venv
source .venv/bin/activate

# 依存関係のインストール
pip install -e .

# 開発用依存関係（テスト、Lint）
pip install -e ".[dev]"

# 環境変数の設定
cp .env.example .env
# .env に REINFOLIB_API_KEY を設定

# データ取得
python scripts/fetch_data.py

# dbtモデルのビルド
cd dbt_project && dbt deps && dbt build && cd ..

# モデルの学習
python scripts/train_model.py

# テストの実行
python -m pytest tests/ -v

# Streamlitアプリ起動
streamlit run streamlit_app.py
```

### 6.2 テスト

```bash
# 全テスト実行
python -m pytest tests/ -v

# カバレッジ付き
python -m pytest tests/ --cov=src --cov-report=html
```

---

## 7. 設定管理

### 7.1 府県コードの集約 (settings.py)

府県コードは用途別に3つの形式で管理し、`settings.py`に一元化している。

```python
class Settings(BaseSettings):
    # JISコード（APIレスポンス用、25-30）
    @property
    def kansai_prefectures(self) -> dict[str, str]:
        return {
            "25": "滋賀県", "26": "京都府", "27": "大阪府",
            "28": "兵庫県", "29": "奈良県", "30": "和歌山県",
        }

    # 住所検証用（短縮形）
    @property
    def kansai_prefecture_names(self) -> list[str]:
        return ["大阪", "京都", "兵庫", "奈良", "滋賀", "和歌山"]

    # ML特徴量用（ローカルコード、住所→コード）
    @property
    def prefecture_local_codes(self) -> dict[str, int]:
        return {
            "大阪府": 1, "大阪市": 1, "京都府": 2, "兵庫県": 3,
            "奈良県": 4, "滋賀県": 5, "和歌山県": 6, "和歌山市": 6,
        }

    # ML特徴量用（ローカルコード、コード→府県名）
    @property
    def prefecture_names_by_code(self) -> dict[int, str]:
        return {
            1: "大阪府", 2: "京都府", 3: "兵庫県",
            4: "奈良県", 5: "滋賀県", 6: "和歌山県",
        }
```

---

## 8. 今後の拡張案

### 8.1 データ拡充

- [ ] ハザードマップAPIの実データ連携
- [ ] 駅乗降客数の定期更新
- [ ] 市区町村データのカバー率向上

### 8.2 モデル改善

- [ ] LightGBM/XGBoostの導入
- [ ] 特徴量追加（ブランド、周辺施設等）
- [ ] ハイパーパラメータの最適化

### 8.3 機能追加

- [ ] 類似物件の表示
- [ ] エリア別の相場分析
- [ ] 物件構造（RC/SRC等）のUI入力

### 8.4 インフラ

- [ ] GitHub Actions による CI/CD
- [ ] 定期的なモデル再学習
- [ ] dbtテストの追加（範囲チェック、異常検知）

### 8.5 コード品質

- [ ] 相対パスから絶対パスへの移行
- [ ] エラーハンドリングの強化
- [ ] テストカバレッジの向上
