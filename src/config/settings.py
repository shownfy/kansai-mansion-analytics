"""設定管理"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """アプリケーション設定"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 環境
    environment: str = "development"
    debug: bool = True

    # API設定
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # データベース
    database_path: Path = Path("data/database/mansion.duckdb")

    # モデル
    model_path: Path = Path("models/latest.joblib")

    # 外部API
    reinfolib_api_key: str | None = None
    reinfolib_base_url: str = "https://www.reinfolib.mlit.go.jp/ex-api/external"

    # ロギング
    log_level: str = "INFO"

    # 関西地方の府県コード（JISコード → 府県名）
    @property
    def kansai_prefectures(self) -> dict[str, str]:
        return {
            "25": "滋賀県",
            "26": "京都府",
            "27": "大阪府",
            "28": "兵庫県",
            "29": "奈良県",
            "30": "和歌山県",
        }

    # 関西地方の府県名（短縮形、住所検証用）
    @property
    def kansai_prefecture_names(self) -> list[str]:
        return ["大阪", "京都", "兵庫", "奈良", "滋賀", "和歌山"]

    # 府県ローカルコード（ML特徴量用、1-6）
    @property
    def prefecture_local_codes(self) -> dict[str, int]:
        return {
            "大阪府": 1,
            "大阪市": 1,
            "京都府": 2,
            "兵庫県": 3,
            "奈良県": 4,
            "滋賀県": 5,
            "和歌山県": 6,
            "和歌山市": 6,
        }

    # 府県コードから府県名への逆引き（ML特徴量用、1-6 → 府県名）
    @property
    def prefecture_names_by_code(self) -> dict[int, str]:
        return {
            1: "大阪府",
            2: "京都府",
            3: "兵庫県",
            4: "奈良県",
            5: "滋賀県",
            6: "和歌山県",
        }


@lru_cache
def get_settings() -> Settings:
    """設定のシングルトンインスタンスを取得"""
    return Settings()
