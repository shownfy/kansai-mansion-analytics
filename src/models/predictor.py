"""予測処理モジュール"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from src.config.settings import get_settings
from src.data.hazard_data import HAZARD_RISK_SCORES
from src.data.municipality_data import MUNICIPALITY_AVG_PRICES
from src.data.station_data import KANSAI_STATION_PASSENGERS
from src.features.feature_engineering import (
    estimate_location_stats,
    get_prefecture_code,
    parse_floor_plan,
)
from src.models.trainer import MansionPriceModelTrainer

settings = get_settings()

logger = structlog.get_logger()


class MansionPricePredictor:
    """マンション価格予測器"""

    def __init__(self, model_path: Path):
        """初期化

        Args:
            model_path: 学習済みモデルのパス
        """
        self.trainer = MansionPriceModelTrainer.load(model_path)

    def predict(
        self,
        address: str,
        floor_plan: str,
        area_sqm: float,
        prediction_year: int,
        building_age: int | None = None,
        building_year: int | None = None,
        time_to_station_min: int | None = None,
    ) -> dict[str, Any]:
        """マンション価格を予測

        Args:
            address: マンションの住所
            floor_plan: 間取り（例: "3LDK"）
            area_sqm: 面積（平米）
            prediction_year: 予測対象年
            building_age: 築年数（building_yearと排他）
            building_year: 建築年（building_ageと排他）
            time_to_station_min: 最寄駅までの徒歩時間（分）、指定しない場合は自動推定

        Returns:
            予測結果を含む辞書
        """
        logger.info(
            "Predicting mansion price",
            address=address,
            floor_plan=floor_plan,
            area_sqm=area_sqm,
            prediction_year=prediction_year,
        )

        # 築年数の計算（予測年時点）
        if building_age is None and building_year is not None:
            building_age_at_prediction = prediction_year - building_year
        elif building_age is not None:
            building_age_at_prediction = building_age
        else:
            raise ValueError("Either building_age or building_year must be provided")

        # 築年数は0以上
        building_age_at_prediction = max(0, building_age_at_prediction)

        # 住所から地域情報を取得
        prefecture_code = get_prefecture_code(address)

        # 府県コードから府県名を取得
        prefecture_name = settings.prefecture_names_by_code.get(prefecture_code)

        # 住所から最寄駅を推定（簡易的に住所内の駅名を検索）
        nearest_station = self._extract_station_from_address(address)

        # 住所から市区町村を推定
        municipality = self._extract_municipality_from_address(address)

        # 地域統計と乗降客数・ハザードリスクを取得
        location_stats = estimate_location_stats(prefecture_code, nearest_station, municipality)

        # 間取りから部屋数を抽出
        num_rooms, has_ldk = parse_floor_plan(floor_plan)

        # 駅までの時間（指定がなければデフォルト10分）
        station_time = time_to_station_min if time_to_station_min is not None else 10

        # 入力データの作成（予測年の条件で予測）
        input_data = pd.DataFrame([{
            "area_sqm": area_sqm,
            "building_age": building_age_at_prediction,  # 予測年時点の築年数
            "num_rooms": num_rooms,
            "has_ldk": has_ldk,
            "time_to_station_min": station_time,
            "coverage_ratio": 60.0,     # デフォルト値
            "floor_area_ratio": 200.0,  # デフォルト値
            "city_avg_price_per_sqm": location_stats["city_avg_price_per_sqm"],
            "station_avg_price_per_sqm": location_stats["station_avg_price_per_sqm"],
            "log_passenger_count": location_stats["log_passenger_count"],
            "structure_type": "RC",     # デフォルト: RC造
            "prefecture_code": prefecture_code,
            "station_rank": location_stats["station_rank"],
            "total_hazard_risk": location_stats["total_hazard_risk"],
            "hazard_risk_category": location_stats["hazard_risk_category"],
            "trade_year": prediction_year,  # 予測年を使用
            "quarter": 2,  # デフォルト: 第2四半期
        }])

        # 特徴量変換
        X = self.trainer.feature_engineer.transform(input_data)

        # 予測（市場インデックス調整なし - モデルがtrade_yearとbuilding_ageから学習）
        predicted_price = float(self.trainer.model.predict(X)[0])
        predicted_price_per_sqm = predicted_price / area_sqm

        # 信頼区間の推定
        mape = self.trainer.metrics.get("mape", 10.0)
        confidence_interval = self._estimate_confidence_interval(
            predicted_price, mape
        )

        result = {
            "predicted_price": int(predicted_price),
            "predicted_price_per_sqm": int(predicted_price_per_sqm),
            "confidence_interval": {
                "lower": int(confidence_interval[0]),
                "upper": int(confidence_interval[1]),
            },
            "input_summary": {
                "address": address,
                "floor_plan": floor_plan,
                "area_sqm": area_sqm,
                "building_age": building_age_at_prediction,
                "prediction_year": prediction_year,
                "prefecture": prefecture_name,
                "municipality": municipality,
            },
            "model_metrics": self.trainer.metrics,
        }

        logger.info("Prediction completed", predicted_price=result["predicted_price"])

        return result

    def _extract_station_from_address(self, address: str) -> str | None:
        """住所から最寄駅を推定

        Args:
            address: 住所文字列

        Returns:
            推定された駅名（見つからない場合はNone）
        """
        # 住所に含まれる駅名を検索
        for station in KANSAI_STATION_PASSENGERS.keys():
            if station in address:
                return station

        # 地域名から主要駅を推定
        area_to_station = {
            "中央区": "本町",
            "北区": "梅田",
            "天王寺": "天王寺",
            "難波": "なんば",
            "心斎橋": "心斎橋",
            "中京区": "四条",
            "下京区": "京都",
            "東山区": "祇園四条",
            "三宮": "三宮",
            "元町": "元町",
            "西宮": "西宮北口",
            "芦屋": "芦屋",
            "奈良市": "近鉄奈良",
            "大津市": "大津",
            "草津市": "草津",
            "和歌山市": "和歌山",
        }

        for area, station in area_to_station.items():
            if area in address:
                return station

        return None

    def _extract_municipality_from_address(self, address: str) -> str | None:
        """住所から市区町村を推定

        Args:
            address: 住所文字列

        Returns:
            推定された市区町村名（見つからない場合はNone）
        """
        # 市区町村データにある市区町村を検索（優先）
        for municipality in MUNICIPALITY_AVG_PRICES.keys():
            if municipality in address:
                return municipality

        # ハザードデータにある市区町村を検索
        for municipality in HAZARD_RISK_SCORES.keys():
            if municipality in address:
                return municipality

        return None

    def _estimate_confidence_interval(
        self,
        predicted_price: float,
        mape: float,
    ) -> tuple[float, float]:
        """信頼区間を推定

        Args:
            predicted_price: 予測価格
            mape: 平均絶対パーセント誤差

        Returns:
            (下限, 上限)のタプル
        """
        # MAPEの1.5倍を範囲とする
        margin = predicted_price * (mape / 100) * 1.5
        return (predicted_price - margin, predicted_price + margin)
