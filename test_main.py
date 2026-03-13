import json
import math
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from main import (
    compute_annualized_volatily,
    compute_cumulative_returns,
    compute_daily_returns,
    extract_sorted_closes,
    fetch_data,
    save_to_json,
)


# extract_sorted_closes

class TestExtractSortedCloses(unittest.TestCase):

    def test_sorted_chronologically(self):
        raw = {
            "2024-01-03": {"4. close": "105.0"},
            "2024-01-01": {"4. close": "100.0"},
            "2024-01-02": {"4. close": "102.0"},
        }
        result = extract_sorted_closes(raw)
        dates = [d for d, _ in result]
        self.assertEqual(dates, ["2024-01-01", "2024-01-02", "2024-01-03"])

    def test_float_conversion(self):
        raw = {"2024-01-01": {"4. close": "123.45"}}
        result = extract_sorted_closes(raw)
        self.assertIsInstance(result[0][1], float)
        self.assertAlmostEqual(result[0][1], 123.45)

    def test_single_entry(self):
        raw = {"2024-01-01": {"4. close": "50.0"}}
        result = extract_sorted_closes(raw)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], ("2024-01-01", 50.0))


# compute_daily_returns

class TestComputeDailyReturns(unittest.TestCase):

    def setUp(self):
        self.closes = [
            ("2024-01-01", 100.0),
            ("2024-01-02", 110.0),
            ("2024-01-03", 99.0),
        ]

    def test_length_is_n_minus_one(self):
        result = compute_daily_returns(self.closes)
        self.assertEqual(len(result), len(self.closes) - 1)

    def test_positive_return(self):
        # (110 - 100) / 100 = 0.1
        result = compute_daily_returns(self.closes)
        self.assertEqual(result[0][0], "2024-01-02")
        self.assertTrue(math.isclose(result[0][1], 0.1))

    def test_negative_return(self):
        # (99 - 110) / 110 ≈ -0.1
        result = compute_daily_returns(self.closes)
        expected = (99.0 - 110.0) / 110.0
        self.assertEqual(result[1][0], "2024-01-03")
        self.assertTrue(math.isclose(result[1][1], expected))

    def test_first_date_excluded(self):
        result = compute_daily_returns(self.closes)
        dates = [d for d, _ in result]
        self.assertNotIn("2024-01-01", dates)


# compute_cumulative_returns

class TestComputeCumulativeReturns(unittest.TestCase):

    def test_cumulative_sum(self):
        returns = [
            ("2024-01-02", 0.1),
            ("2024-01-03", -0.05),
            ("2024-01-04", 0.02),
        ]
        result = compute_cumulative_returns(returns)
        self.assertTrue(math.isclose(result[0][1], 0.10, rel_tol=1e-5))
        self.assertTrue(math.isclose(result[1][1], 0.05, rel_tol=1e-5))
        self.assertTrue(math.isclose(result[2][1], 0.07, rel_tol=1e-5))

    def test_preserves_dates(self):
        returns = [("2024-01-02", 0.1), ("2024-01-03", 0.2)]
        result = compute_cumulative_returns(returns)
        self.assertEqual(result[0][0], "2024-01-02")
        self.assertEqual(result[1][0], "2024-01-03")

    def test_all_negative_stays_negative(self):
        returns = [("2024-01-02", -0.1), ("2024-01-03", -0.05)]
        result = compute_cumulative_returns(returns)
        self.assertLess(result[-1][1], 0)

    def test_single_return(self):
        returns = [("2024-01-02", 0.07)]
        result = compute_cumulative_returns(returns)
        self.assertTrue(math.isclose(result[0][1], 0.07))


# compute_annualized_volatility

class TestComputeAnnualizedVolatility(unittest.TestCase):

    def _returns(self, values):
        return [(f"2024-01-{i+1:02d}", v) for i, v in enumerate(values)]

    def test_output_length(self):
        # range(window, n+1) → n - window + 1 pontos
        result = compute_annualized_volatily(self._returns([0.01] * 25), window=5)
        self.assertEqual(len(result), 21)

    def test_known_value(self):
        # std([0.01, 0.02, 0.03]) = 0.01  →  0.01 × √252
        result = compute_annualized_volatily(self._returns([0.01, 0.02, 0.03]), window=3)
        expected = round(0.01 * math.sqrt(252), 6)
        self.assertEqual(len(result), 1)
        self.assertTrue(math.isclose(result[0][1], expected, rel_tol=1e-5))

    def test_constant_series_zero_volatility(self):
        # desvio padrão de série constante = 0
        result = compute_annualized_volatily(self._returns([0.01] * 5), window=5)
        self.assertTrue(math.isclose(result[0][1], 0.0, abs_tol=1e-9))

    def test_uses_last_date_of_window(self):
        result = compute_annualized_volatily(self._returns([0.01, 0.02, 0.03]), window=3)
        self.assertEqual(result[0][0], "2024-01-03")

    def test_default_window_21(self):
        result = compute_annualized_volatily(self._returns([0.01] * 25))
        self.assertEqual(len(result), 5)  # 25 - 21 + 1


# save_to_json

class TestSaveToJson(unittest.TestCase):

    def _save_and_read(self, data, key):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name
        try:
            save_to_json(data, filepath, key)
            with open(filepath, encoding="utf-8") as f:
                return json.load(f)
        finally:
            os.unlink(filepath)

    def test_structure_and_values(self):
        data = [("2024-01-01", 0.05), ("2024-01-02", 0.10)]
        records = self._save_and_read(data, "retorno_acumulado")
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["date"], "2024-01-01")
        self.assertAlmostEqual(records[0]["retorno_acumulado"], 0.05)

    def test_custom_value_key(self):
        data = [("2024-01-01", 0.15)]
        records = self._save_and_read(data, "volatilidade_anualizada")
        self.assertIn("volatilidade_anualizada", records[0])
        self.assertNotIn("retorno_acumulado", records[0])

    def test_valid_json_output(self):
        data = [("2024-01-01", 0.01)]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            filepath = f.name
        try:
            save_to_json(data, filepath, "valor")
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            json.loads(content)
        finally:
            os.unlink(filepath)


# fetch_data

class TestFetchData(unittest.TestCase):

    @patch("main.requests.get")
    def test_returns_time_series_dict(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {"2024-01-01": {"4. close": "100.0"}}
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_data()
        self.assertIn("2024-01-01", result)

    @patch("main.requests.get")
    def test_raises_key_error_on_missing_key(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Note": "API rate limit reached"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        with self.assertRaises(KeyError):
            fetch_data()

    @patch("main.requests.get")
    def test_raises_on_request_exception(self, mock_get):
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("timeout")

        with self.assertRaises(req.exceptions.RequestException):
            fetch_data()


if __name__ == "__main__":
    unittest.main(verbosity=2)
