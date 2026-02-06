"""駅乗降客数データモジュール

国土数値情報「駅別乗降客数データ」を基にした関西地方の駅マスターデータ
https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-S12-v3_1.html
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

# 関西地方主要駅の乗降客数データ（1日平均、2022年度ベース）
# データソース: 国土数値情報、各鉄道会社公表データ
KANSAI_STATION_PASSENGERS: dict[str, int] = {
    # 大阪府 - JR
    "大阪": 430000,
    "天王寺": 140000,
    "京橋": 130000,
    "鶴橋": 100000,
    "新大阪": 95000,
    "難波": 90000,
    "三ノ宮": 85000,
    "高槻": 65000,
    "茨木": 55000,
    "吹田": 45000,
    "堺市": 40000,
    "和泉府中": 25000,

    # 大阪府 - 私鉄
    "梅田": 500000,
    "なんば": 320000,
    "天王寺駅": 200000,
    "淀屋橋": 150000,
    "本町": 140000,
    "心斎橋": 130000,
    "新大阪駅": 120000,
    "江坂": 80000,
    "千里中央": 75000,
    "豊中": 60000,
    "吹田駅": 55000,
    "茨木市": 50000,
    "高槻市": 48000,
    "枚方市": 70000,
    "寝屋川市": 45000,
    "守口市": 40000,
    "門真市": 35000,
    "東大阪": 30000,
    "八尾": 28000,
    "藤井寺": 25000,
    "堺": 60000,
    "堺東": 55000,
    "中百舌鳥": 50000,
    "泉大津": 20000,
    "岸和田": 25000,
    "泉佐野": 30000,
    "関西空港": 35000,

    # 京都府
    "京都": 350000,
    "四条": 100000,
    "烏丸": 95000,
    "河原町": 90000,
    "三条": 45000,
    "祇園四条": 40000,
    "山科": 35000,
    "二条": 30000,
    "丹波橋": 35000,
    "桃山御陵前": 20000,
    "宇治": 25000,
    "長岡京": 30000,
    "向日町": 20000,
    "亀岡": 15000,
    "福知山": 10000,
    "舞鶴": 5000,

    # 兵庫県
    "三宮": 250000,
    "神戸": 120000,
    "元町": 80000,
    "西宮北口": 85000,
    "尼崎": 70000,
    "芦屋": 40000,
    "西宮": 50000,
    "宝塚": 45000,
    "川西能勢口": 40000,
    "伊丹": 35000,
    "明石": 55000,
    "加古川": 35000,
    "姫路": 65000,
    "三田": 25000,
    "垂水": 30000,
    "須磨": 20000,
    "住吉": 35000,
    "六甲道": 40000,
    "灘": 25000,
    "春日野道": 15000,
    "新開地": 45000,
    "湊川": 30000,
    "板宿": 25000,

    # 奈良県
    "奈良": 45000,
    "近鉄奈良": 50000,
    "大和西大寺": 55000,
    "学園前": 45000,
    "生駒": 50000,
    "王寺": 30000,
    "天理": 15000,
    "桜井": 12000,
    "橿原神宮前": 20000,
    "大和八木": 25000,
    "高田": 18000,

    # 滋賀県
    "大津": 40000,
    "草津": 45000,
    "守山": 25000,
    "野洲": 18000,
    "近江八幡": 20000,
    "彦根": 18000,
    "長浜": 12000,
    "米原": 15000,
    "膳所": 20000,
    "石山": 25000,
    "瀬田": 22000,
    "南草津": 35000,

    # 和歌山県
    "和歌山": 35000,
    "和歌山市": 25000,
    "海南": 8000,
    "紀三井寺": 5000,
    "田辺": 6000,
    "白浜": 4000,
    "新宮": 3000,
    "橋本": 15000,
    "岩出": 8000,
}

# 駅名の正規化マッピング（表記揺れ対応）
STATION_NAME_ALIASES: dict[str, str] = {
    # JR/私鉄の表記揺れ
    "JR難波": "難波",
    "近鉄難波": "なんば",
    "南海難波": "なんば",
    "大阪難波": "なんば",
    "地下鉄梅田": "梅田",
    "阪急梅田": "梅田",
    "阪神梅田": "梅田",
    "大阪梅田": "梅田",
    "JR三ノ宮": "三宮",
    "阪急三宮": "三宮",
    "阪神三宮": "三宮",
    "神戸三宮": "三宮",
    "JR京都": "京都",
    "近鉄京都": "京都",
    "阪急河原町": "河原町",
    "京阪三条": "三条",
    "近鉄奈良駅": "近鉄奈良",
    "JR奈良": "奈良",
    # 駅の付く/付かないの揺れ
    "大阪駅": "大阪",
    "京都駅": "京都",
    "神戸駅": "神戸",
    "三宮駅": "三宮",
    "梅田駅": "梅田",
    "難波駅": "難波",
    "なんば駅": "なんば",
    "天王寺駅前": "天王寺",
}


def normalize_station_name(station_name: str) -> str:
    """駅名を正規化

    Args:
        station_name: 元の駅名

    Returns:
        正規化された駅名
    """
    # 末尾の「駅」を除去
    normalized = station_name.rstrip("駅")

    # エイリアスがあれば変換
    if normalized in STATION_NAME_ALIASES:
        normalized = STATION_NAME_ALIASES[normalized]

    return normalized


def get_passenger_count(station_name: str) -> int | None:
    """駅名から乗降客数を取得

    Args:
        station_name: 駅名

    Returns:
        1日平均乗降客数（見つからない場合はNone）
    """
    normalized = normalize_station_name(station_name)

    # 完全一致
    if normalized in KANSAI_STATION_PASSENGERS:
        return KANSAI_STATION_PASSENGERS[normalized]

    # 部分一致（駅名が含まれている場合）
    for key, value in KANSAI_STATION_PASSENGERS.items():
        if key in normalized or normalized in key:
            return value

    return None


def get_station_rank(passenger_count: int | None) -> str:
    """乗降客数から駅ランクを判定

    Args:
        passenger_count: 乗降客数

    Returns:
        駅ランク（large/medium/small/unknown）
    """
    if passenger_count is None:
        return "unknown"

    if passenger_count >= 100000:
        return "large"  # 大規模駅（10万人以上）
    elif passenger_count >= 30000:
        return "medium"  # 中規模駅（3万人以上）
    else:
        return "small"  # 小規模駅


def get_station_features(station_name: str) -> dict[str, Any]:
    """駅名から特徴量を取得

    Args:
        station_name: 駅名

    Returns:
        駅関連の特徴量辞書
    """
    passenger_count = get_passenger_count(station_name)
    station_rank = get_station_rank(passenger_count)

    # 乗降客数の対数変換（スケール調整）
    log_passengers = math.log10(passenger_count) if passenger_count else 0

    return {
        "passenger_count": passenger_count or 0,
        "log_passenger_count": log_passengers,
        "station_rank": station_rank,
        "is_major_station": 1 if station_rank == "large" else 0,
    }


def save_station_master_csv(filepath: Path) -> None:
    """駅マスターデータをCSVに保存

    Args:
        filepath: 保存先パス
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["station_name", "passenger_count", "station_rank"])

        for station, count in sorted(
            KANSAI_STATION_PASSENGERS.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            rank = get_station_rank(count)
            writer.writerow([station, count, rank])

    logger.info("Station master saved", path=str(filepath))


def load_station_master_json(filepath: Path) -> dict[str, int]:
    """駅マスターデータをJSONから読み込み

    Args:
        filepath: JSONファイルパス

    Returns:
        駅名→乗降客数の辞書
    """
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)
