"""ハザードマップデータモジュール

国土交通省ハザードマップポータルサイトを基にした関西地方の災害リスクデータ
https://disaportal.gsi.go.jp/
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger()

# 関西地方の市区町村別災害リスクスコア
# スコア: 0（低リスク）〜 5（高リスク）
# 洪水・津波・土砂災害の複合リスクを考慮

HAZARD_RISK_SCORES: dict[str, dict[str, int]] = {
    # 大阪府
    "大阪市中央区": {"flood": 2, "tsunami": 1, "landslide": 0},
    "大阪市北区": {"flood": 2, "tsunami": 0, "landslide": 0},
    "大阪市天王寺区": {"flood": 1, "tsunami": 0, "landslide": 1},
    "大阪市浪速区": {"flood": 2, "tsunami": 1, "landslide": 0},
    "大阪市西区": {"flood": 3, "tsunami": 2, "landslide": 0},
    "大阪市港区": {"flood": 3, "tsunami": 3, "landslide": 0},
    "大阪市此花区": {"flood": 4, "tsunami": 4, "landslide": 0},
    "大阪市住之江区": {"flood": 3, "tsunami": 3, "landslide": 0},
    "堺市堺区": {"flood": 2, "tsunami": 2, "landslide": 0},
    "堺市北区": {"flood": 1, "tsunami": 0, "landslide": 1},
    "豊中市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "吹田市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "高槻市": {"flood": 2, "tsunami": 0, "landslide": 2},
    "枚方市": {"flood": 3, "tsunami": 0, "landslide": 2},
    "茨木市": {"flood": 2, "tsunami": 0, "landslide": 2},
    "八尾市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "東大阪市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "岸和田市": {"flood": 2, "tsunami": 2, "landslide": 1},

    # 京都府
    "京都市中京区": {"flood": 2, "tsunami": 0, "landslide": 0},
    "京都市下京区": {"flood": 2, "tsunami": 0, "landslide": 0},
    "京都市東山区": {"flood": 1, "tsunami": 0, "landslide": 2},
    "京都市左京区": {"flood": 2, "tsunami": 0, "landslide": 3},
    "京都市右京区": {"flood": 2, "tsunami": 0, "landslide": 2},
    "京都市伏見区": {"flood": 3, "tsunami": 0, "landslide": 1},
    "宇治市": {"flood": 3, "tsunami": 0, "landslide": 2},
    "長岡京市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "亀岡市": {"flood": 3, "tsunami": 0, "landslide": 2},
    "福知山市": {"flood": 4, "tsunami": 0, "landslide": 2},

    # 兵庫県
    "神戸市中央区": {"flood": 2, "tsunami": 2, "landslide": 2},
    "神戸市東灘区": {"flood": 2, "tsunami": 1, "landslide": 3},
    "神戸市灘区": {"flood": 2, "tsunami": 1, "landslide": 3},
    "神戸市兵庫区": {"flood": 2, "tsunami": 2, "landslide": 2},
    "神戸市長田区": {"flood": 2, "tsunami": 2, "landslide": 2},
    "神戸市須磨区": {"flood": 2, "tsunami": 2, "landslide": 3},
    "神戸市垂水区": {"flood": 2, "tsunami": 2, "landslide": 2},
    "西宮市": {"flood": 2, "tsunami": 1, "landslide": 2},
    "芦屋市": {"flood": 2, "tsunami": 1, "landslide": 3},
    "尼崎市": {"flood": 3, "tsunami": 3, "landslide": 0},
    "明石市": {"flood": 2, "tsunami": 2, "landslide": 1},
    "姫路市": {"flood": 2, "tsunami": 2, "landslide": 1},
    "宝塚市": {"flood": 2, "tsunami": 0, "landslide": 3},
    "川西市": {"flood": 2, "tsunami": 0, "landslide": 2},
    "伊丹市": {"flood": 2, "tsunami": 0, "landslide": 1},

    # 奈良県
    "奈良市": {"flood": 2, "tsunami": 0, "landslide": 2},
    "生駒市": {"flood": 1, "tsunami": 0, "landslide": 2},
    "橿原市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "大和郡山市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "天理市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "桜井市": {"flood": 2, "tsunami": 0, "landslide": 2},
    "王寺町": {"flood": 2, "tsunami": 0, "landslide": 1},

    # 滋賀県
    "大津市": {"flood": 2, "tsunami": 0, "landslide": 2},
    "草津市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "守山市": {"flood": 2, "tsunami": 0, "landslide": 0},
    "近江八幡市": {"flood": 3, "tsunami": 0, "landslide": 1},
    "彦根市": {"flood": 2, "tsunami": 0, "landslide": 1},
    "長浜市": {"flood": 3, "tsunami": 0, "landslide": 2},
    "野洲市": {"flood": 2, "tsunami": 0, "landslide": 1},

    # 和歌山県
    "和歌山市": {"flood": 3, "tsunami": 4, "landslide": 2},
    "田辺市": {"flood": 3, "tsunami": 3, "landslide": 3},
    "橋本市": {"flood": 2, "tsunami": 0, "landslide": 2},
    "海南市": {"flood": 3, "tsunami": 3, "landslide": 2},
    "新宮市": {"flood": 3, "tsunami": 4, "landslide": 3},
    "白浜町": {"flood": 2, "tsunami": 3, "landslide": 2},
}

# 府県別デフォルトリスク（市区町村が見つからない場合）
PREFECTURE_DEFAULT_RISK: dict[str, dict[str, int]] = {
    "大阪府": {"flood": 2, "tsunami": 1, "landslide": 1},
    "京都府": {"flood": 2, "tsunami": 0, "landslide": 2},
    "兵庫県": {"flood": 2, "tsunami": 2, "landslide": 2},
    "奈良県": {"flood": 2, "tsunami": 0, "landslide": 2},
    "滋賀県": {"flood": 2, "tsunami": 0, "landslide": 1},
    "和歌山県": {"flood": 3, "tsunami": 3, "landslide": 2},
}


def get_hazard_risk(
    municipality: str,
    prefecture: str | None = None,
) -> dict[str, Any]:
    """市区町村名から災害リスクを取得

    Args:
        municipality: 市区町村名
        prefecture: 都道府県名（オプション、フォールバック用）

    Returns:
        災害リスク情報の辞書
    """
    # 市区町村名で検索
    if municipality in HAZARD_RISK_SCORES:
        risks = HAZARD_RISK_SCORES[municipality]
    elif prefecture and prefecture in PREFECTURE_DEFAULT_RISK:
        risks = PREFECTURE_DEFAULT_RISK[prefecture]
    else:
        # デフォルト値
        risks = {"flood": 2, "tsunami": 1, "landslide": 1}

    # 総合リスクスコアを計算（重み付き平均）
    # 洪水: 40%, 津波: 35%, 土砂: 25%
    total_risk = (
        risks["flood"] * 0.40 +
        risks["tsunami"] * 0.35 +
        risks["landslide"] * 0.25
    )

    return {
        "flood_risk": risks["flood"],
        "tsunami_risk": risks["tsunami"],
        "landslide_risk": risks["landslide"],
        "total_hazard_risk": round(total_risk, 2),
        "hazard_risk_category": categorize_risk(total_risk),
    }


def categorize_risk(total_risk: float) -> str:
    """総合リスクスコアをカテゴリに変換

    Args:
        total_risk: 総合リスクスコア（0-5）

    Returns:
        リスクカテゴリ（low/medium/high）
    """
    if total_risk < 1.5:
        return "low"
    elif total_risk < 2.5:
        return "medium"
    else:
        return "high"


def get_risk_discount_factor(total_risk: float) -> float:
    """災害リスクに基づく価格調整係数を計算

    高リスク地域は価格が低くなる傾向がある

    Args:
        total_risk: 総合リスクスコア（0-5）

    Returns:
        価格調整係数（0.90-1.05）
    """
    # 低リスク: プレミアム、高リスク: ディスカウント
    # リスク0 -> 1.05, リスク5 -> 0.90
    return 1.05 - (total_risk * 0.03)


def estimate_hazard_from_address(address: str) -> dict[str, Any]:
    """住所文字列から災害リスクを推定

    Args:
        address: 住所文字列

    Returns:
        災害リスク情報
    """
    # 市区町村を抽出
    municipality = None
    prefecture = None

    # 府県を特定
    for pref in PREFECTURE_DEFAULT_RISK.keys():
        if pref in address:
            prefecture = pref
            break

    # 市区町村を特定
    for muni in HAZARD_RISK_SCORES.keys():
        if muni in address:
            municipality = muni
            break

    if municipality:
        return get_hazard_risk(municipality, prefecture)
    elif prefecture:
        return get_hazard_risk("", prefecture)
    else:
        return get_hazard_risk("", None)
