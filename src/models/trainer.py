"""モデル学習モジュール"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import structlog
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import GridSearchCV, train_test_split

from src.features.feature_engineering import MansionFeatureEngineer

logger = structlog.get_logger()


class MansionPriceModelTrainer:
    """マンション価格予測モデルのトレーナー"""

    MODELS: dict[str, type] = {
        "gradient_boosting": GradientBoostingRegressor,
    }

    # ハイパーパラメータグリッド
    PARAM_GRIDS: dict[str, dict[str, list]] = {
        "gradient_boosting": {
            "n_estimators": [100, 200],
            "max_depth": [3, 5, 7],
            "learning_rate": [0.05, 0.1],
        },
    }

    def __init__(
        self,
        model_name: str = "gradient_boosting",
        model_dir: Path | None = None,
    ):
        self.model_name = model_name
        self.model_dir = model_dir or Path("models")
        self.model: Any = None
        self.feature_engineer = MansionFeatureEngineer()
        self.metrics: dict[str, float] = {}
        self.feature_importances: pd.DataFrame | None = None

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "trade_price",
        test_size: float = 0.2,
        tune_hyperparameters: bool = True,
        cv_folds: int = 5,
    ) -> dict[str, float]:
        """モデルを学習

        Args:
            df: 学習データ
            target_col: ターゲット変数のカラム名
            test_size: テストデータの割合
            tune_hyperparameters: ハイパーパラメータチューニングを行うか
            cv_folds: クロスバリデーションの分割数

        Returns:
            評価指標の辞書
        """
        logger.info("Starting model training", model=self.model_name)

        # 特徴量エンジニアリング
        X, y = self.feature_engineer.fit_transform(df, target_col)

        if y is None:
            raise ValueError(f"Target column '{target_col}' not found")

        # データ分割
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        # モデル初期化
        model_class = self.MODELS.get(self.model_name)
        if model_class is None:
            raise ValueError(f"Unknown model: {self.model_name}")

        if tune_hyperparameters and self.model_name in self.PARAM_GRIDS:
            # ハイパーパラメータチューニング
            logger.info("Tuning hyperparameters...")
            base_model = model_class(random_state=42)
            grid_search = GridSearchCV(
                base_model,
                self.PARAM_GRIDS[self.model_name],
                cv=cv_folds,
                scoring="neg_mean_squared_error",
                n_jobs=-1,
                verbose=1,
            )
            grid_search.fit(X_train, y_train)
            self.model = grid_search.best_estimator_
            logger.info("Best parameters", params=grid_search.best_params_)
        else:
            # デフォルトパラメータで学習
            self.model = model_class(random_state=42)
            self.model.fit(X_train, y_train)

        # 評価
        y_pred = self.model.predict(X_test)
        self.metrics = self._calculate_metrics(y_test, y_pred)

        # 特徴量重要度
        self._calculate_feature_importance()

        logger.info("Training completed", metrics=self.metrics)

        return self.metrics

    def _calculate_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> dict[str, float]:
        """評価指標を計算"""
        return {
            "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
            "mae": float(mean_absolute_error(y_true, y_pred)),
            "mape": float(mean_absolute_percentage_error(y_true, y_pred) * 100),
            "r2": float(r2_score(y_true, y_pred)),
        }

    def _calculate_feature_importance(self) -> None:
        """特徴量重要度を計算"""
        if hasattr(self.model, "feature_importances_"):
            importances = self.model.feature_importances_
            self.feature_importances = pd.DataFrame({
                "feature": self.feature_engineer.feature_names,
                "importance": importances,
            }).sort_values("importance", ascending=False)

    def save(self, version: str | None = None) -> Path:
        """モデルを保存

        Args:
            version: バージョン文字列（省略時は日時）

        Returns:
            保存先パス
        """
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.model_dir.mkdir(parents=True, exist_ok=True)

        model_path = self.model_dir / f"{self.model_name}_{version}.joblib"

        # モデルと特徴量エンジニアリングを一緒に保存
        artifact = {
            "model": self.model,
            "feature_engineer": self.feature_engineer,
            "metrics": self.metrics,
            "feature_importances": self.feature_importances,
            "model_name": self.model_name,
            "version": version,
        }

        joblib.dump(artifact, model_path)

        # latest.joblib としても保存
        latest_path = self.model_dir / "latest.joblib"
        joblib.dump(artifact, latest_path)

        logger.info("Model saved", path=str(model_path))

        return model_path

    @classmethod
    def load(cls, model_path: Path) -> "MansionPriceModelTrainer":
        """モデルを読み込み

        Args:
            model_path: モデルファイルパス

        Returns:
            トレーナーインスタンス
        """
        artifact = joblib.load(model_path)

        trainer = cls(model_name=artifact["model_name"])
        trainer.model = artifact["model"]
        trainer.feature_engineer = artifact["feature_engineer"]
        trainer.metrics = artifact["metrics"]
        trainer.feature_importances = artifact["feature_importances"]

        logger.info("Model loaded", path=str(model_path))

        return trainer
