"""予測モジュールのテスト"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models.predictor import MansionPricePredictor


class TestMansionPricePredictor:
    """MansionPricePredictorのテスト"""

    @pytest.fixture
    def mock_predictor(self):
        """モックを使用したpredictor"""
        with patch.object(MansionPricePredictor, "__init__", lambda x, y: None):
            predictor = MansionPricePredictor(Path("dummy"))
            predictor.trainer = MagicMock()
            predictor.trainer.metrics = {"mape": 10.0}
            return predictor

    def test_extract_station_from_address_三宮(self, mock_predictor):
        """住所から駅名を抽出 - 三宮"""
        station = mock_predictor._extract_station_from_address("兵庫県神戸市中央区三宮町1-1-1")
        assert station == "三宮"

    def test_extract_station_from_address_奈良(self, mock_predictor):
        """住所から駅名を抽出 - 奈良"""
        station = mock_predictor._extract_station_from_address("奈良県奈良市登大路町1-1")
        assert station == "奈良"

    def test_extract_station_from_address_京都(self, mock_predictor):
        """住所から駅名を抽出 - 京都"""
        station = mock_predictor._extract_station_from_address("京都府京都市下京区烏丸通塩小路下ル東塩小路町")
        assert station == "京都"

    def test_extract_station_from_address_地域名から推定(self, mock_predictor):
        """住所から駅名を抽出 - 地域名から推定（芦屋）"""
        station = mock_predictor._extract_station_from_address("兵庫県芦屋市船戸町1-1-1")
        assert station == "芦屋"

    def test_extract_municipality_from_address_大阪市中央区(self, mock_predictor):
        """住所から市区町村を抽出 - 大阪市中央区"""
        municipality = mock_predictor._extract_municipality_from_address("大阪府大阪市中央区本町1-1-1")
        assert municipality == "大阪市中央区"

    def test_extract_municipality_from_address_不明(self, mock_predictor):
        """住所から市区町村を抽出 - 見つからない場合"""
        municipality = mock_predictor._extract_municipality_from_address("福岡県福岡市博多区1-1-1")
        assert municipality is None

    def test_estimate_confidence_interval(self, mock_predictor):
        """信頼区間の推定"""
        lower, upper = mock_predictor._estimate_confidence_interval(
            predicted_price=30000000,
            mape=10.0
        )
        # MAPE 10%の1.5倍 = 15%の範囲
        assert lower == 30000000 - 30000000 * 0.15
        assert upper == 30000000 + 30000000 * 0.15
