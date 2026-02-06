"""不動産情報ライブラリAPIクライアント"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config.settings import get_settings

logger = structlog.get_logger()


class ReinfoLibClient:
    """国土交通省 不動産情報ライブラリAPIクライアント

    API Documentation: https://www.reinfolib.mlit.go.jp/help/apiManual/
    """

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.reinfolib_api_key
        self.base_url = settings.reinfolib_base_url
        self.kansai_prefectures = settings.kansai_prefectures

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def fetch_transactions(
        self,
        prefecture_code: str,
        year: int,
        quarter: int | None = None,
    ) -> list[dict[str, Any]]:
        """取引価格情報を取得

        Args:
            prefecture_code: 府県コード (25-30 for 関西)
            year: 取引年
            quarter: 四半期 (1-4)、Noneの場合は年間全て

        Returns:
            取引データのリスト
        """
        endpoint = f"{self.base_url}/XIT001"

        params = {
            "year": year,
            "area": prefecture_code,
        }
        if quarter:
            params["quarter"] = quarter

        headers = {}
        if self.api_key:
            headers["Ocp-Apim-Subscription-Key"] = self.api_key

        async with httpx.AsyncClient() as client:
            response = await client.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        transactions = data.get("data", [])
        logger.info(
            "Fetched transactions",
            prefecture=self.kansai_prefectures.get(prefecture_code),
            year=year,
            quarter=quarter,
            count=len(transactions),
        )

        return transactions

    async def fetch_all_kansai_transactions(
        self,
        start_year: int = 2005,
        end_year: int | None = None,
    ) -> list[dict[str, Any]]:
        """関西全府県の取引データを取得

        Args:
            start_year: 開始年
            end_year: 終了年（省略時は現在の年）

        Returns:
            全取引データのリスト
        """
        from datetime import datetime

        if end_year is None:
            end_year = datetime.now().year

        all_transactions = []

        for pref_code in self.kansai_prefectures.keys():
            for year in range(start_year, end_year + 1):
                for quarter in range(1, 5):
                    try:
                        transactions = await self.fetch_transactions(
                            prefecture_code=pref_code,
                            year=year,
                            quarter=quarter,
                        )
                        all_transactions.extend(transactions)
                    except (httpx.HTTPStatusError, Exception) as e:
                        logger.warning(
                            "Failed to fetch transactions",
                            prefecture_code=pref_code,
                            year=year,
                            quarter=quarter,
                            error=str(e),
                        )
                        continue

        logger.info(
            "Completed fetching all transactions",
            total_count=len(all_transactions),
        )

        return all_transactions

    def filter_mansions(
        self, transactions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """マンションデータのみをフィルタリング

        Args:
            transactions: 取引データリスト

        Returns:
            マンションのみの取引データ
        """
        mansion_data = [
            t for t in transactions
            if t.get("Type") and "マンション" in t.get("Type", "")
        ]

        logger.info(
            "Filtered mansion data",
            original_count=len(transactions),
            mansion_count=len(mansion_data),
        )

        return mansion_data

    def save_to_json(
        self,
        data: list[dict[str, Any]],
        filepath: Path,
    ) -> None:
        """データをJSONファイルに保存

        Args:
            data: 保存するデータ
            filepath: 保存先パス
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("Saved data to file", filepath=str(filepath), count=len(data))
