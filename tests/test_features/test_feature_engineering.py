"""特徴量エンジニアリングのテスト"""
from __future__ import annotations

import pytest

from src.features.feature_engineering import (
    get_prefecture_code,
    parse_floor_plan,
    estimate_location_stats,
)


class TestParseFloorPlan:
    """間取りパース関数のテスト"""

    def test_parse_3ldk(self):
        num_rooms, has_ldk = parse_floor_plan("3LDK")
        assert num_rooms == 3
        assert has_ldk == 1

    def test_parse_2dk(self):
        num_rooms, has_ldk = parse_floor_plan("2DK")
        assert num_rooms == 2
        assert has_ldk == 0

    def test_parse_1r(self):
        num_rooms, has_ldk = parse_floor_plan("1R")
        assert num_rooms == 1
        assert has_ldk == 0

    def test_parse_lowercase(self):
        num_rooms, has_ldk = parse_floor_plan("3ldk")
        assert num_rooms == 3
        assert has_ldk == 1


class TestGetPrefectureCode:
    """府県コード取得関数のテスト"""

    def test_osaka(self):
        assert get_prefecture_code("大阪府大阪市") == 1

    def test_kyoto(self):
        assert get_prefecture_code("京都府京都市") == 2

    def test_hyogo(self):
        assert get_prefecture_code("兵庫県神戸市") == 3

    def test_nara(self):
        assert get_prefecture_code("奈良県奈良市") == 4

    def test_shiga(self):
        assert get_prefecture_code("滋賀県大津市") == 5

    def test_wakayama(self):
        assert get_prefecture_code("和歌山県和歌山市") == 6

    def test_unknown(self):
        # 不明な場合はデフォルトで大阪（1）
        assert get_prefecture_code("東京都渋谷区") == 1


class TestEstimateLocationStats:
    """地域統計推定関数のテスト"""

    def test_osaka_stats(self):
        stats = estimate_location_stats(1)
        assert stats["city_avg_price_per_sqm"] == 450000  # 大阪府のデフォルト
        assert stats["station_avg_price_per_sqm"] > stats["city_avg_price_per_sqm"]

    def test_kyoto_stats(self):
        stats = estimate_location_stats(2)
        assert stats["city_avg_price_per_sqm"] == 420000  # 京都府のデフォルト

    def test_unknown_prefecture(self):
        stats = estimate_location_stats(99)
        assert stats["city_avg_price_per_sqm"] == 350000  # デフォルト値
