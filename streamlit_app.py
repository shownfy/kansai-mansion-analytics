"""関西マンションAI - Streamlit App"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.config.settings import get_settings
from src.models.predictor import MansionPricePredictor

settings = get_settings()

# ページ設定
st.set_page_config(
    page_title="関西マンションAI",
    page_icon="image/kansai-mansion-prediction-ai.png",
    layout="centered",
)

# カスタムCSS
st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #1e293b;
        margin-bottom: 2rem;
    }
    .result-card {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        text-align: center;
        margin: 1rem 0;
    }
    .price-value {
        font-size: 2.5rem;
        font-weight: 700;
    }
    .stMetric {
        background-color: #f8fafc;
        padding: 1rem;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_predictor() -> MansionPricePredictor | None:
    """予測モデルをロード（キャッシュ付き）"""
    # まず latest.joblib を試す
    model_path = Path("models/latest.joblib")
    if not model_path.exists():
        # フォールバック: mansion_price_model.pkl
        model_path = Path("models/mansion_price_model.pkl")
    if model_path.exists():
        return MansionPricePredictor(model_path)
    return None


def format_currency(value: int) -> str:
    """通貨フォーマット"""
    return f"¥{value:,}"


def format_currency_man(value: int) -> str:
    """万円単位でフォーマット"""
    return f"{value // 10000:,}万円"


def main():
    # タイトル画像を表示
    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.image("image/kansai-mansion-prediction-ai.png", use_container_width=True)

    # 予測モデルのロード
    predictor = load_predictor()
    if predictor is None:
        st.error("モデルがロードされていません。先にモデルを学習してください。")
        st.code("python scripts/train_model.py", language="bash")
        return

    # 入力フォーム
    with st.form("prediction_form"):
        # 住所
        address = st.text_input(
            "住所",
            placeholder="例: 大阪府大阪市中央区本町1-1-1",
            help="関西地方（大阪、京都、兵庫、奈良、滋賀、和歌山）の住所を入力してください",
        )

        # 2カラムレイアウト
        col1, col2 = st.columns(2)

        with col1:
            floor_plan = st.selectbox(
                "間取り",
                options=["1R", "1K", "1DK", "1LDK", "2DK", "2LDK", "3DK", "3LDK", "4LDK", "5LDK"],
                index=7,  # デフォルト: 3LDK
            )

        with col2:
            area_sqm = st.number_input(
                "面積（m²）",
                min_value=10,
                max_value=500,
                value=70,
                step=1,
            )

        col3, col4 = st.columns(2)

        with col3:
            building_year = st.number_input(
                "建築年",
                min_value=1950,
                max_value=2030,
                value=2010,
            )

        with col4:
            time_to_station = st.number_input(
                "最寄駅まで（分）",
                min_value=1,
                max_value=60,
                value=10,
                help="最寄駅までの徒歩時間を入力してください",
            )

        submitted = st.form_submit_button("価格を予測する", use_container_width=True)

    # 予測実行
    if submitted:
        # バリデーション
        if not address:
            st.error("住所を入力してください")
            return

        if not any(pref in address for pref in settings.kansai_prefecture_names):
            st.error("関西地方（大阪、京都、兵庫、奈良、滋賀、和歌山）の住所を入力してください")
            return

        current_year = datetime.now().year
        max_year = building_year + 50  # 築50年まで

        # 5年刻みの予測年リスト生成（グラフ用）
        start_year = (current_year // 5 + 1) * 5
        prediction_years = list(range(start_year, min(start_year + 51, max_year + 1), 5))

        with st.spinner("予測中..."):
            try:
                # 全ての予測年に対して予測を実行
                predictions = []
                for year in prediction_years:
                    result = predictor.predict(
                        address=address,
                        floor_plan=floor_plan,
                        area_sqm=area_sqm,
                        prediction_year=year,
                        building_year=building_year,
                        time_to_station_min=time_to_station,
                    )
                    predictions.append({"year": year, "data": result})

                if not predictions:
                    st.error("予測に失敗しました")
                    return

                # 結果表示
                st.markdown("---")
                st.subheader("予測結果")

                df = pd.DataFrame([
                    {
                        "year": p["year"],
                        "price": p["data"]["predicted_price"] / 10000,
                    }
                    for p in predictions
                ])

                fig = go.Figure()

                # 予測価格ライン
                fig.add_trace(go.Scatter(
                    x=df["year"],
                    y=df["price"],
                    mode="lines+markers",
                    name="予測価格",
                    line=dict(color="#2563eb", width=2),
                    marker=dict(size=8),
                ))

                fig.update_layout(
                    xaxis_title="予測年",
                    yaxis_title="価格（万円）",
                    hovermode="x unified",
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=0, r=0, t=30, b=0),
                )

                st.plotly_chart(fig, use_container_width=True)

                st.caption("※築50年以降は予測精度が低下するため表示していません")

                # 入力情報サマリー
                st.markdown("#### 入力情報")
                current_building_age = current_year - building_year
                summary_data = {
                    "項目": ["住所", "間取り", "面積", "築年数（現在）", "最寄駅まで"],
                    "値": [
                        address,
                        floor_plan,
                        f"{area_sqm} m²",
                        f"{current_building_age}年",
                        f"{time_to_station}分",
                    ],
                }
                st.table(pd.DataFrame(summary_data).set_index("項目"))

            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"予測処理に失敗しました: {e}")



if __name__ == "__main__":
    main()
