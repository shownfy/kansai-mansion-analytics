#!/usr/bin/env python
"""データ取得スクリプト

不動産情報ライブラリAPIからデータを取得します。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import duckdb
import structlog

from src.config.settings import get_settings
from src.data.api_client import ReinfoLibClient

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger()


def load_data_to_duckdb(data: list[dict], db_path: Path) -> None:
    """データをDuckDBに読み込む

    Args:
        data: 取引データのリスト
        db_path: DuckDBファイルパス
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(db_path))

    # 一時的にJSONファイルに保存してから読み込む
    temp_json = db_path.parent / "temp_data.json"
    with open(temp_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    # テーブル作成
    conn.execute("""
        CREATE OR REPLACE TABLE transaction_data AS
        SELECT * FROM read_json_auto(?)
    """, [str(temp_json)])

    count = conn.execute("SELECT COUNT(*) FROM transaction_data").fetchone()[0]
    logger.info("Data loaded to DuckDB", count=count, path=str(db_path))

    # 一時ファイル削除
    temp_json.unlink()
    conn.close()


async def fetch_from_api(
    start_year: int = 2005,
    end_year: int | None = None,
) -> list[dict]:
    """APIからデータを取得

    Args:
        start_year: 開始年
        end_year: 終了年（省略時は現在の年）

    Returns:
        取引データのリスト
    """
    from datetime import datetime

    if end_year is None:
        end_year = datetime.now().year

    client = ReinfoLibClient()
    all_data = await client.fetch_all_kansai_transactions(
        start_year=start_year,
        end_year=end_year,
    )
    return client.filter_mansions(all_data)


def main() -> None:
    """メイン処理"""
    settings = get_settings()
    db_path = settings.database_path

    if not settings.reinfolib_api_key:
        logger.error("API key not set. Set REINFOLIB_API_KEY in .env")
        return

    logger.info("Fetching data from API...")
    data = asyncio.run(fetch_from_api())

    # 生データを保存
    raw_path = Path("data/raw/transactions.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("Raw data saved", path=str(raw_path), count=len(data))

    # DuckDBに読み込み
    load_data_to_duckdb(data, db_path)

    logger.info("Data fetch completed successfully")


if __name__ == "__main__":
    main()
