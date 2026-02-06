"""特徴量エンジニアリングモジュール"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config.settings import get_settings


class MansionFeatureEngineer:
    """マンション価格予測用特徴量エンジニアリング"""

    # 数値特徴量
    NUMERIC_FEATURES = [
        "area_sqm",              # 面積（平米）
        "building_age",          # 築年数
        "num_rooms",             # 部屋数
        "time_to_station_min",   # 最寄駅までの時間
        "coverage_ratio",        # 建蔽率
        "floor_area_ratio",      # 容積率
        "city_avg_price_per_sqm",     # 市区町村平均単価
        "station_avg_price_per_sqm",  # 駅周辺平均単価
        "log_passenger_count",   # 乗降客数（対数）
        "total_hazard_risk",     # 総合災害リスクスコア
        "trade_year",            # 取引年
        "quarter",               # 取引四半期
    ]

    # カテゴリカル特徴量
    CATEGORICAL_FEATURES = [
        "structure_type",   # 構造（RC, SRC, S, Wood）
        "has_ldk",          # LDKの有無
        "prefecture_code",  # 府県コード
        "station_rank",     # 駅ランク（large/medium/small）
        "hazard_risk_category",  # 災害リスクカテゴリ（low/medium/high）
    ]

    # ターゲット変数
    TARGET = "trade_price"

    def __init__(self):
        self.preprocessor: ColumnTransformer | None = None
        self.feature_names: list[str] = []

    def create_preprocessor(self) -> ColumnTransformer:
        """前処理パイプラインを作成"""
        numeric_transformer = Pipeline(steps=[
            ("scaler", StandardScaler())
        ])

        categorical_transformer = Pipeline(steps=[
            ("onehot", OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False
            ))
        ])

        self.preprocessor = ColumnTransformer(
            transformers=[
                ("num", numeric_transformer, self.NUMERIC_FEATURES),
                ("cat", categorical_transformer, self.CATEGORICAL_FEATURES)
            ],
            remainder="drop"
        )

        return self.preprocessor

    def create_additional_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """追加の特徴量を作成"""
        df = df.copy()

        # 面積あたりの部屋数（空間効率）
        if "num_rooms" in df.columns and "area_sqm" in df.columns:
            df["rooms_per_area"] = df["num_rooms"] / df["area_sqm"]

        # 築年数の二乗項（非線形効果）
        if "building_age" in df.columns:
            df["building_age_squared"] = df["building_age"] ** 2

        # 駅近フラグ（徒歩5分以内）
        if "time_to_station_min" in df.columns:
            df["is_near_station"] = (df["time_to_station_min"] <= 5).astype(int)

        # 地域プレミアム（駅周辺 - 市区町村平均）
        if "station_avg_price_per_sqm" in df.columns and "city_avg_price_per_sqm" in df.columns:
            df["location_premium"] = (
                df["station_avg_price_per_sqm"] - df["city_avg_price_per_sqm"]
            )

        return df

    def fit_transform(
        self,
        df: pd.DataFrame,
        target_col: str | None = None,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """特徴量の学習と変換

        Args:
            df: 入力データフレーム
            target_col: ターゲット変数のカラム名（学習時のみ）

        Returns:
            変換後の特徴量行列、ターゲット変数（あれば）
        """
        if target_col is None:
            target_col = self.TARGET

        df = self.create_additional_features(df)

        # 欠損値処理
        df = self._handle_missing_values(df)

        X = df[self.NUMERIC_FEATURES + self.CATEGORICAL_FEATURES]

        y = None
        if target_col in df.columns:
            y = df[target_col].values

        if self.preprocessor is None:
            self.create_preprocessor()

        X_transformed = self.preprocessor.fit_transform(X)

        # 特徴量名を保存
        self._save_feature_names()

        return X_transformed, y

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        """特徴量の変換のみ（学習済み前提）"""
        if self.preprocessor is None:
            raise ValueError("Preprocessor not fitted. Call fit_transform first.")

        df = self.create_additional_features(df)
        df = self._handle_missing_values(df)
        X = df[self.NUMERIC_FEATURES + self.CATEGORICAL_FEATURES]

        return self.preprocessor.transform(X)

    def _handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """欠損値を処理"""
        df = df.copy()

        # 数値特徴量の欠損値を中央値で埋める
        for col in self.NUMERIC_FEATURES:
            if col in df.columns and df[col].isna().any():
                df[col] = df[col].fillna(df[col].median())

        # カテゴリカル特徴量の欠損値
        for col in self.CATEGORICAL_FEATURES:
            if col in df.columns and df[col].isna().any():
                df[col] = df[col].fillna("Unknown")

        return df

    def _save_feature_names(self) -> None:
        """特徴量名を保存"""
        cat_features = []
        if hasattr(self.preprocessor, "named_transformers_"):
            onehot = self.preprocessor.named_transformers_["cat"].named_steps["onehot"]
            if hasattr(onehot, "get_feature_names_out"):
                cat_features = list(onehot.get_feature_names_out(self.CATEGORICAL_FEATURES))

        self.feature_names = self.NUMERIC_FEATURES + cat_features


def parse_floor_plan(floor_plan: str) -> tuple[int, int]:
    """間取りから部屋数とLDK有無を抽出

    Args:
        floor_plan: 間取り文字列（例: "3LDK"）

    Returns:
        (部屋数, LDK有無フラグ)
    """
    floor_plan = floor_plan.upper()

    # 部屋数の抽出（R, L, D, K, Sで始まる間取りに対応）
    match = re.search(r"(\d+)[RLDKS]", floor_plan)
    num_rooms = int(match.group(1)) if match else 2

    # LDKの有無
    has_ldk = 1 if "LDK" in floor_plan else 0

    return num_rooms, has_ldk


def get_prefecture_code(address: str) -> int:
    """住所から府県コードを取得

    Args:
        address: 住所文字列

    Returns:
        府県コード（1-6、不明の場合は1）
    """
    # 完全な府県名で検索（「京都」が「東京都」にマッチするのを防ぐ）
    settings = get_settings()
    prefecture_codes = settings.prefecture_local_codes

    for pref, code in prefecture_codes.items():
        if pref in address:
            return code

    return 1  # デフォルト: 大阪


def estimate_location_stats(
    prefecture_code: int,
    station_name: str | None = None,
    municipality: str | None = None,
) -> dict[str, Any]:
    """府県コードと駅名から地域統計を推定

    Args:
        prefecture_code: 府県コード
        station_name: 最寄駅名（オプション）
        municipality: 市区町村名（オプション）

    Returns:
        地域統計の辞書
    """
    from src.data.hazard_data import get_hazard_risk
    from src.data.municipality_data import get_municipality_avg_price
    from src.data.station_data import get_station_features

    # 府県コードから府県名を取得
    settings = get_settings()
    prefecture_name = settings.prefecture_names_by_code.get(prefecture_code)

    # 市区町村別の平均単価を取得（フォールバック付き）
    city_avg = get_municipality_avg_price(municipality, prefecture_name)
    station_avg = int(city_avg * 1.1)  # 駅周辺は1.1倍として概算

    result = {
        "city_avg_price_per_sqm": city_avg,
        "station_avg_price_per_sqm": station_avg,
    }

    # 駅乗降客数の特徴量を追加
    if station_name:
        station_features = get_station_features(station_name)
        result.update(station_features)
    else:
        # デフォルト値（中規模駅相当）
        result["passenger_count"] = 30000
        result["log_passenger_count"] = 4.48  # log10(30000)
        result["station_rank"] = "medium"
        result["is_major_station"] = 0

    # ハザードリスクの特徴量を追加
    hazard_info = get_hazard_risk(municipality or "", prefecture_name)
    result["total_hazard_risk"] = hazard_info["total_hazard_risk"]
    result["hazard_risk_category"] = hazard_info["hazard_risk_category"]

    return result
