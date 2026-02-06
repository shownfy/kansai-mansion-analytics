#!/usr/bin/env python
"""駅距離エンリッチメントスクリプト

取引データの町名から最寄駅までの距離を計算し、DuckDBに保存する。
データソース:
- Geolonia住所データ: https://geolonia.github.io/japanese-addresses/
- 国土数値情報 鉄道データ: https://nlftp.mlit.go.jp/ksj/
"""
from __future__ import annotations

import time
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from urllib.parse import quote

import duckdb
import httpx
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger()

# 関西6府県のコード
KANSAI_PREFECTURES = {
    "25": "滋賀県",
    "26": "京都府",
    "27": "大阪府",
    "28": "兵庫県",
    "29": "奈良県",
    "30": "和歌山県",
}

# 関西地方の全駅座標データ（国土数値情報ベース + 拡充）
# データソース: https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-v2_3.html
KANSAI_ALL_STATIONS: dict[str, tuple[float, float]] = {
    # ===== 大阪府 =====
    # JR
    "大阪": (34.7024, 135.4959),
    "新大阪": (34.7334, 135.5001),
    "天王寺": (34.6469, 135.5166),
    "京橋": (34.6966, 135.5363),
    "鶴橋": (34.6679, 135.5302),
    "難波": (34.6659, 135.5013),
    "高槻": (34.8512, 135.6175),
    "茨木": (34.8168, 135.5688),
    "吹田": (34.7612, 135.5173),
    "堺市": (34.5507, 135.4837),
    "和泉府中": (34.4835, 135.4287),
    "三国ヶ丘": (34.5556, 135.4893),
    "鳳": (34.5298, 135.4589),
    "熊取": (34.4023, 135.3589),
    "日根野": (34.4010, 135.3275),
    "関西空港": (34.4320, 135.2440),
    "弁天町": (34.6639, 135.4644),
    "西九条": (34.6802, 135.4616),
    "福島": (34.6936, 135.4830),
    "東淀川": (34.7412, 135.5104),
    "平野": (34.6196, 135.5523),
    "久宝寺": (34.6137, 135.5822),
    "八尾": (34.6266, 135.6009),
    # 私鉄・地下鉄
    "梅田": (34.7006, 135.4982),
    "なんば": (34.6659, 135.5013),
    "淀屋橋": (34.6935, 135.5025),
    "本町": (34.6830, 135.5005),
    "心斎橋": (34.6752, 135.5006),
    "天満橋": (34.6915, 135.5150),
    "谷町四丁目": (34.6830, 135.5184),
    "谷町六丁目": (34.6740, 135.5184),
    "谷町九丁目": (34.6620, 135.5184),
    "江坂": (34.7512, 135.4997),
    "千里中央": (34.8094, 135.4952),
    "豊中": (34.7811, 135.4694),
    "茨木市": (34.8168, 135.5688),
    "高槻市": (34.8512, 135.6175),
    "枚方市": (34.8145, 135.6509),
    "寝屋川市": (34.7665, 135.6283),
    "守口市": (34.7379, 135.5621),
    "門真市": (34.7388, 135.5873),
    "東大阪": (34.6796, 135.5606),
    "藤井寺": (34.5746, 135.5984),
    "堺": (34.5735, 135.4829),
    "堺東": (34.5686, 135.4784),
    "中百舌鳥": (34.5449, 135.5015),
    "泉大津": (34.5048, 135.4042),
    "岸和田": (34.4596, 135.3734),
    "泉佐野": (34.4110, 135.3205),
    "天下茶屋": (34.6488, 135.4975),
    "新今宮": (34.6488, 135.5078),
    "住吉大社": (34.6117, 135.4926),
    "住之江公園": (34.6117, 135.4782),
    "コスモスクエア": (34.6349, 135.4145),
    "森ノ宮": (34.6845, 135.5328),
    "長居": (34.6117, 135.5178),
    "あびこ": (34.5961, 135.5106),
    "喜連瓜破": (34.5961, 135.5416),
    "八尾南": (34.5961, 135.5826),
    # ===== 京都府 =====
    "京都": (34.9857, 135.7588),
    "四条": (35.0033, 135.7591),
    "烏丸": (35.0033, 135.7591),
    "河原町": (35.0037, 135.7697),
    "三条": (35.0096, 135.7711),
    "祇園四条": (35.0037, 135.7720),
    "山科": (34.9700, 135.8194),
    "二条": (35.0106, 135.7435),
    "丹波橋": (34.9400, 135.7611),
    "桃山御陵前": (34.9327, 135.7727),
    "宇治": (34.8906, 135.7999),
    "長岡京": (34.9256, 135.6958),
    "向日町": (34.9467, 135.7008),
    "亀岡": (35.0123, 135.5779),
    "福知山": (35.2961, 135.1278),
    "舞鶴": (35.4715, 135.3831),
    "西院": (35.0012, 135.7314),
    "嵐山": (35.0145, 135.6788),
    "北大路": (35.0438, 135.7591),
    "今出川": (35.0300, 135.7591),
    "丸太町": (35.0159, 135.7591),
    "竹田": (34.9553, 135.7591),
    "中書島": (34.9192, 135.7611),
    "東福寺": (34.9772, 135.7718),
    "伏見": (34.9327, 135.7611),
    # ===== 兵庫県 =====
    "三宮": (34.6953, 135.1956),
    "神戸": (34.6799, 135.1780),
    "元町": (34.6878, 135.1853),
    "西宮北口": (34.7440, 135.3614),
    "尼崎": (34.7333, 135.4177),
    "芦屋": (34.7284, 135.3032),
    "西宮": (34.7350, 135.3424),
    "宝塚": (34.7986, 135.3447),
    "川西能勢口": (34.8269, 135.4100),
    "伊丹": (34.7815, 135.4003),
    "明石": (34.6430, 134.9934),
    "加古川": (34.7671, 134.8397),
    "姫路": (34.8269, 134.6906),
    "三田": (34.8893, 135.2234),
    "垂水": (34.6309, 135.0526),
    "須磨": (34.6543, 135.1284),
    "住吉": (34.7186, 135.2529),
    "六甲道": (34.7128, 135.2352),
    "灘": (34.7072, 135.2213),
    "春日野道": (34.7009, 135.2078),
    "新開地": (34.6711, 135.1622),
    "湊川": (34.6724, 135.1543),
    "板宿": (34.6556, 135.1287),
    "塚口": (34.7533, 135.4177),
    "武庫之荘": (34.7533, 135.3877),
    "園田": (34.7533, 135.4477),
    "西明石": (34.6430, 134.9534),
    "魚住": (34.6940, 134.9354),
    "土山": (34.7171, 134.9097),
    "東加古川": (34.7571, 134.8697),
    "御着": (34.7969, 134.7506),
    "網干": (34.8169, 134.6006),
    "新長田": (34.6556, 135.1487),
    "鷹取": (34.6456, 135.1287),
    # ===== 奈良県 =====
    "奈良": (34.6852, 135.8199),
    "近鉄奈良": (34.6818, 135.8196),
    "大和西大寺": (34.7049, 135.7836),
    "学園前": (34.6942, 135.7521),
    "生駒": (34.6897, 135.7015),
    "王寺": (34.5945, 135.7068),
    "天理": (34.5969, 135.8374),
    "桜井": (34.5182, 135.8417),
    "橿原神宮前": (34.4874, 135.7916),
    "大和八木": (34.5093, 135.7926),
    "高田": (34.5153, 135.7387),
    "郡山": (34.6500, 135.7836),
    "西ノ京": (34.6752, 135.7836),
    "新大宮": (34.6918, 135.8096),
    "富雄": (34.6897, 135.7415),
    "東生駒": (34.6897, 135.7215),
    # ===== 滋賀県 =====
    "大津": (35.0015, 135.8596),
    "草津": (35.0139, 135.9570),
    "守山": (35.0584, 135.9943),
    "野洲": (35.0680, 136.0222),
    "近江八幡": (35.1282, 136.0913),
    "彦根": (35.2648, 136.2495),
    "長浜": (35.3815, 136.2705),
    "米原": (35.3140, 136.2893),
    "膳所": (34.9970, 135.8779),
    "石山": (34.9594, 135.9029),
    "瀬田": (34.9598, 135.9261),
    "南草津": (34.9896, 135.9608),
    "栗東": (35.0239, 135.9770),
    "手原": (35.0339, 135.9970),
    "能登川": (35.1782, 136.1613),
    "安土": (35.1482, 136.1313),
    "篠原": (35.0980, 136.0522),
    # ===== 和歌山県 =====
    "和歌山": (34.2329, 135.1908),
    "和歌山市": (34.2274, 135.1658),
    "海南": (34.1562, 135.2038),
    "紀三井寺": (34.1832, 135.1820),
    "田辺": (33.7298, 135.3778),
    "白浜": (33.6767, 135.3537),
    "新宮": (33.7262, 135.9878),
    "橋本": (34.3142, 135.6058),
    "岩出": (34.2519, 135.3014),
    "紀伊": (34.2029, 135.2308),
    "六十谷": (34.2429, 135.2308),
    "紀ノ川": (34.2529, 135.1708),
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2点間の距離をHaversine公式で計算（km）"""
    R = 6371  # 地球の半径(km)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def find_nearest_station(lat: float, lon: float) -> tuple[str, float, int]:
    """指定座標から最寄り駅を検索

    Returns:
        (駅名, 距離km, 徒歩分)
    """
    min_distance = float("inf")
    nearest_station = None

    for station, (slat, slon) in KANSAI_ALL_STATIONS.items():
        distance = haversine_distance(lat, lon, slat, slon)
        if distance < min_distance:
            min_distance = distance
            nearest_station = station

    # 徒歩時間を計算（80m/分、直線距離×1.3係数）
    walking_time = max(1, int(round(min_distance * 1000 * 1.3 / 80)))

    return nearest_station, round(min_distance, 3), walking_time


def get_municipalities_list() -> dict[str, list[str]]:
    """Geoloniaから全市区町村リストを取得"""
    url = "https://geolonia.github.io/japanese-addresses/api/ja.json"
    logger.info("Fetching municipalities list from Geolonia...")

    response = httpx.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def download_city_addresses(prefecture: str, city: str) -> list[dict]:
    """特定の市区町村の住所データをダウンロード

    https://geolonia.github.io/japanese-addresses/api/ja/<prefecture>/<city>.json
    """
    encoded_pref = quote(prefecture, safe="")
    encoded_city = quote(city, safe="")
    url = f"https://geolonia.github.io/japanese-addresses/api/ja/{encoded_pref}/{encoded_city}.json"

    response = httpx.get(url, timeout=60)
    response.raise_for_status()
    return response.json()


def build_address_coordinates(prefectures: list[str]) -> dict[str, tuple[float, float]]:
    """住所→座標のマッピングを構築

    Args:
        prefectures: 対象の府県名リスト（例: ["大阪府", "京都府"]）
    """
    address_coords = {}

    # 全市区町村リストを取得
    all_municipalities = get_municipalities_list()

    for pref_name in prefectures:
        cities = all_municipalities.get(pref_name, [])
        logger.info("Processing prefecture", prefecture=pref_name, cities_count=len(cities))

        city_count = 0
        for city_name in cities:
            try:
                # API制限を考慮して少し待つ
                time.sleep(0.1)

                addresses = download_city_addresses(pref_name, city_name)

                for addr in addresses:
                    town_name = addr.get("town", "")
                    lat = addr.get("lat")
                    lng = addr.get("lng")

                    if lat and lng and town_name:
                        # 町名のバリエーションを作成
                        key = f"{pref_name}|{city_name}|{town_name}"
                        address_coords[key] = (float(lat), float(lng))

                        # 丁目を除いたバージョンも追加
                        base_town = town_name
                        for suffix in ["一丁目", "二丁目", "三丁目", "四丁目", "五丁目",
                                       "六丁目", "七丁目", "八丁目", "九丁目", "十丁目",
                                       "１丁目", "２丁目", "３丁目", "４丁目", "５丁目"]:
                            if town_name.endswith(suffix):
                                base_town = town_name[:-len(suffix)]
                                break
                        if base_town != town_name:
                            base_key = f"{pref_name}|{city_name}|{base_town}"
                            if base_key not in address_coords:
                                address_coords[base_key] = (float(lat), float(lng))

                city_count += 1
                if city_count % 10 == 0:
                    logger.info("Progress", prefecture=pref_name, processed=city_count, total=len(cities))

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning("City not found in Geolonia", city=city_name)
                else:
                    logger.error("HTTP error", city=city_name, status=e.response.status_code)
            except Exception as e:
                logger.error("Failed to fetch city data", city=city_name, error=str(e))
                continue

        pref_count = len([k for k in address_coords if k.startswith(pref_name)])
        logger.info("Loaded address data", prefecture=pref_name, addresses=pref_count)

    return address_coords


def enrich_district_station_distance(db_path: Path) -> None:
    """取引データの町名に最寄駅距離を付与"""
    conn = duckdb.connect(str(db_path))

    # ユニークな住所を取得
    logger.info("Fetching unique addresses from transaction data...")
    unique_addresses = conn.execute("""
        SELECT DISTINCT
            "Prefecture" as prefecture,
            "Municipality" as municipality,
            "DistrictName" as district_name
        FROM transaction_data
        WHERE "Type" LIKE '%マンション%'
          AND "DistrictName" IS NOT NULL
          AND "DistrictName" != ''
    """).fetchall()

    logger.info("Found unique addresses", count=len(unique_addresses))

    # Geolonia住所データをダウンロード
    logger.info("Building address coordinates from Geolonia data...")
    address_coords = build_address_coordinates(list(KANSAI_PREFECTURES.values()))
    logger.info("Total address coordinates loaded", count=len(address_coords))

    # 各住所に対して最寄駅を計算
    results = []
    matched = 0
    unmatched = 0

    for prefecture, municipality, district_name in unique_addresses:
        # 住所キーを構築
        key = f"{prefecture}|{municipality}|{district_name}"

        coords = address_coords.get(key)

        # 見つからない場合は町名の一部でマッチを試みる
        if coords is None:
            # "○○町" -> "○○" で再検索
            for suffix in ["町", "丁", "通", "筋"]:
                if district_name.endswith(suffix) and len(district_name) > 1:
                    alt_key = f"{prefecture}|{municipality}|{district_name[:-1]}"
                    coords = address_coords.get(alt_key)
                    if coords:
                        break

        if coords:
            lat, lon = coords
            station, distance_km, walking_time = find_nearest_station(lat, lon)
            results.append({
                "prefecture": prefecture,
                "municipality": municipality,
                "district_name": district_name,
                "latitude": lat,
                "longitude": lon,
                "nearest_station": station,
                "distance_km": distance_km,
                "time_to_station_min": walking_time,
            })
            matched += 1
        else:
            # 座標が見つからない場合はデフォルト値
            results.append({
                "prefecture": prefecture,
                "municipality": municipality,
                "district_name": district_name,
                "latitude": None,
                "longitude": None,
                "nearest_station": None,
                "distance_km": None,
                "time_to_station_min": 10,  # デフォルト
            })
            unmatched += 1

    logger.info("Address matching complete", matched=matched, unmatched=unmatched, match_rate=f"{matched/(matched+unmatched)*100:.1f}%")

    # 結果をDuckDBに保存
    logger.info("Saving district_station_distance table to DuckDB...")

    # テーブルを作成
    conn.execute("DROP TABLE IF EXISTS district_station_distance")
    conn.execute("""
        CREATE TABLE district_station_distance (
            prefecture VARCHAR,
            municipality VARCHAR,
            district_name VARCHAR,
            latitude DOUBLE,
            longitude DOUBLE,
            nearest_station VARCHAR,
            distance_km DOUBLE,
            time_to_station_min INTEGER,
            PRIMARY KEY (prefecture, municipality, district_name)
        )
    """)

    # データを挿入
    for r in results:
        conn.execute("""
            INSERT INTO district_station_distance VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            r["prefecture"],
            r["municipality"],
            r["district_name"],
            r["latitude"],
            r["longitude"],
            r["nearest_station"],
            r["distance_km"],
            r["time_to_station_min"],
        ])

    conn.commit()

    # 統計を表示
    stats = conn.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(nearest_station) as with_station,
            AVG(time_to_station_min) as avg_time,
            MIN(time_to_station_min) as min_time,
            MAX(time_to_station_min) as max_time
        FROM district_station_distance
    """).fetchone()

    logger.info(
        "District station distance table created",
        total=stats[0],
        with_station=stats[1],
        avg_time=f"{stats[2]:.1f}分",
        min_time=f"{stats[3]}分",
        max_time=f"{stats[4]}分",
    )

    conn.close()


def main():
    """メイン処理"""
    from src.config.settings import get_settings

    settings = get_settings()
    db_path = settings.database_path

    if not db_path.exists():
        logger.error("Database not found", path=str(db_path))
        return

    enrich_district_station_distance(db_path)
    logger.info("Enrichment complete!")


if __name__ == "__main__":
    main()
