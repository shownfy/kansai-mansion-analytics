#!/usr/bin/env python
"""モデル学習スクリプト

dbtで構築したmart_training_datasetからデータを読み込み、モデルを学習・保存します。
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import structlog

from src.config.settings import get_settings
from src.models.trainer import MansionPriceModelTrainer

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger()


def load_training_data(db_path: Path) -> pd.DataFrame:
    """dbtのmart_training_datasetから学習データを読み込む

    Args:
        db_path: DuckDBファイルパス

    Returns:
        学習データのDataFrame
    """
    conn = duckdb.connect(str(db_path))

    # dbtで構築したmartテーブルから直接読み込み
    query = """
    SELECT
        trade_price,
        area_sqm,
        building_age,
        num_rooms,
        has_ldk,
        time_to_station_min,
        coverage_ratio,
        floor_area_ratio,
        city_avg_price_per_sqm,
        station_avg_price_per_sqm,
        structure_type,
        prefecture_code,
        log_passenger_count,
        station_rank,
        total_hazard_risk,
        hazard_risk_category,
        trade_year,
        quarter
    FROM main_marts.mart_training_dataset
    WHERE trade_price > 0
      AND area_sqm > 0
    """

    df = conn.execute(query).fetchdf()
    conn.close()

    logger.info("Loaded training data from dbt mart", count=len(df))
    return df


def main(model_name: str = "gradient_boosting") -> None:
    """メイン処理

    Args:
        model_name: 使用するモデル名
    """
    settings = get_settings()
    db_path = settings.database_path

    if not db_path.exists():
        logger.error("Database not found. Run fetch_data.py first.", path=str(db_path))
        return

    # データ読み込み
    df = load_training_data(db_path)

    if len(df) < 100:
        logger.warning("Training data is too small", count=len(df))

    # モデル学習
    trainer = MansionPriceModelTrainer(model_name=model_name)
    metrics = trainer.train(
        df,
        target_col="trade_price",
        tune_hyperparameters=True,
    )

    # 結果表示
    print("\n===== Training Results =====")
    print(f"Model: {model_name}")
    print(f"RMSE: {metrics['rmse']:,.0f} 円")
    print(f"MAE: {metrics['mae']:,.0f} 円")
    print(f"MAPE: {metrics['mape']:.2f} %")
    print(f"R²: {metrics['r2']:.4f}")

    if trainer.feature_importances is not None:
        print("\n===== Feature Importances =====")
        print(trainer.feature_importances.head(10).to_string(index=False))

    # モデル保存
    model_path = trainer.save()
    print(f"\nModel saved to: {model_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train mansion price prediction model")
    parser.add_argument(
        "--model",
        type=str,
        default="gradient_boosting",
        choices=["gradient_boosting"],
        help="Model type to train",
    )
    args = parser.parse_args()

    main(model_name=args.model)
