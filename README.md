# 関西マンションAI

関西地方（大阪、京都、兵庫、奈良、滋賀、和歌山）のマンション価格を予測するWebアプリケーション。

## 機能

- 住所、間取り、面積、建築年、最寄駅までの時間を入力してマンション価格を予測
- 5年刻みの価格推移グラフ表示（築50年まで）
- 国土交通省 不動産情報ライブラリAPIの実データ（2005年〜現在）を使用

## モデル精度

| 指標 | 値 |
|------|-----|
| MAPE | 69.05%（平均絶対パーセント誤差） |
| R² | 0.86（決定係数） |
| 学習データ件数 | 約283,000件 |

## 技術スタック

| カテゴリ | 技術 |
|----------|------|
| 言語 | Python 3.10+ |
| フロントエンド | Streamlit（キャッシュ機能付き） |
| データパイプライン | dbt + DuckDB（ディメンショナルモデリング） |
| 機械学習 | scikit-learn, Gradient Boosting |
| 設定管理 | pydantic-settings |
| ロギング | structlog |
| データソース | 国土交通省 不動産情報ライブラリAPI |

## ローカルでの実行

### 1. 依存関係のインストール

```bash
# 仮想環境の作成
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# パッケージのインストール
pip install -e .

# 開発用依存関係（テスト実行時）
pip install -e ".[dev]"
```

### 2. 環境変数の設定

```bash
cp .env.example .env
# .env に REINFOLIB_API_KEY を設定
```

### 3. データの取得

```bash
python scripts/fetch_data.py
```

### 4. dbtモデルのビルド

```bash
cd dbt_project
dbt deps
dbt build
cd ..
```

### 5. モデルの学習

```bash
python scripts/train_model.py
```

### 6. Streamlitアプリの起動

```bash
streamlit run streamlit_app.py
```

http://localhost:8501 にアクセスしてアプリケーションを使用できます。

### テストの実行

```bash
python -m pytest tests/ -v
```

## プロジェクト構成

```
kansai-mansion-analytics/
├── streamlit_app.py       # Streamlit アプリ（メイン）
├── requirements.txt       # Streamlit Cloud 用依存関係
├── pyproject.toml         # プロジェクト設定
│
├── src/
│   ├── config/            # 設定管理
│   │   └── settings.py    # 府県コード等の集約設定（pydantic-settings）
│   ├── data/              # データ取得・マスターデータ
│   │   ├── api_client.py         # 不動産情報APIクライアント（非同期）
│   │   ├── station_data.py       # 駅乗降客数データ（110駅）
│   │   ├── municipality_data.py  # 市区町村平均単価データ（123市区町村）
│   │   └── hazard_data.py        # ハザードリスクデータ（63市区町村）
│   ├── features/          # 特徴量エンジニアリング
│   │   └── feature_engineering.py
│   └── models/            # 機械学習モデル
│       ├── trainer.py     # モデル学習
│       └── predictor.py   # 予測処理
│
├── dbt_project/           # dbt プロジェクト
│   └── models/
│       ├── staging/       # ステージング層（クレンジング）
│       ├── dimensions/    # ディメンションテーブル
│       ├── facts/         # ファクトテーブル
│       └── marts/         # マート層（学習データ）
│
├── models/                # 学習済みモデル
├── scripts/               # 実行スクリプト
│   ├── fetch_data.py      # データ取得
│   └── train_model.py     # モデル学習
├── tests/                 # テスト
└── docs/                  # ドキュメント
```

## dbtモデル構造

```
raw (ソース)
└── transaction_data        ← 国土交通省APIレスポンス

staging/
└── stg_transactions        ← クレンジング・型変換（和暦→西暦等）

dimensions/
├── dim_prefecture          ← 府県マスタ
├── dim_municipality        ← 市区町村マスタ（価格統計付き）
├── dim_structure           ← 建物構造マスタ（価格係数付き）
└── dim_floor_plan          ← 間取りマスタ

facts/
└── fct_transactions        ← 取引ファクトテーブル

marts/
└── mart_training_dataset   ← ML学習用データセット
```

## 特徴量

| カテゴリ | 特徴量 | 説明 |
|----------|--------|------|
| 基本属性 | area_sqm | 面積（平米） |
| 基本属性 | building_age | 築年数 |
| 基本属性 | num_rooms | 部屋数 |
| 基本属性 | has_ldk | LDKの有無 |
| 建物 | structure_type | 構造（RC/SRC/S/Wood） |
| 建物 | coverage_ratio | 建蔽率 |
| 建物 | floor_area_ratio | 容積率 |
| 立地 | prefecture_code | 府県コード（1-6） |
| 立地 | time_to_station_min | 最寄駅までの徒歩時間（ユーザー入力） |
| 地域統計 | city_avg_price_per_sqm | 市区町村平均単価 |
| 地域統計 | station_avg_price_per_sqm | 駅周辺平均単価 |
| 駅情報 | log_passenger_count | 乗降客数（対数） |
| 駅情報 | station_rank | 駅規模（large/medium/small） |
| リスク | total_hazard_risk | 総合災害リスクスコア |
| リスク | hazard_risk_category | リスクカテゴリ（low/medium/high） |
| 時系列 | trade_year | 取引年 |
| 時系列 | quarter | 取引四半期（1-4） |

## データソース

- [国土交通省 不動産情報ライブラリ](https://www.reinfolib.mlit.go.jp/)
  - データ期間: 2005年〜現在（約20年分）
  - 対象地域: 関西6府県（大阪、京都、兵庫、奈良、滋賀、和歌山）
  - 対象物件: 中古マンション取引データ

## ライセンス

MIT License
