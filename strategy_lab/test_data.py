"""Offline tests for historical pagination, exact ranges, and missing-data disclosure."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from strategy_lab import data


def candle(t, step=3_600_000):
    return [t, "10", "12", "9", "11", "7", t + step - 1, "77", 1, "3", "33", "0"]


class DataTests(unittest.TestCase):
    def test_pagination_advances_and_end_is_exclusive(self):
        step = 3_600_000
        calls = []

        def fake_get(market, endpoint, params, weight=1):
            calls.append(params)
            return [candle(0), candle(step)] if len(calls) == 1 else [candle(2 * step), candle(3 * step)]

        with patch.object(data, "_get", side_effect=fake_get):
            result = data._download_klines("futures", "BTCUSDT", "1h", 0, 3 * step, "bars")
        self.assertEqual(result.open_time.tolist(), [0, step, 2 * step])
        self.assertEqual(calls[1]["startTime"], 2 * step)
        self.assertEqual(calls[0]["endTime"], 3 * step - 1)
        self.assertEqual(result.quote_vol.tolist(), [77, 77, 77])

    def test_incremental_cache_fetches_only_missing_edges(self):
        step = 14_400_000
        requests = []

        def fake_download(market, symbol, interval, start, end, kind):
            requests.append((start, end))
            return pd.DataFrame([[t, 10, 12, 9, 11, 7, 77, t + step - 1]
                                 for t in range(start, end, step)], columns=data.BAR_COLUMNS)

        with tempfile.TemporaryDirectory() as tmp, patch.object(data, "DATA_DIR", Path(tmp)), \
                patch.object(data, "_download_klines", side_effect=fake_download):
            data.fetch_bars("spot", "BTCUSDT", "4h", step, 3 * step)
            result = data.fetch_bars("spot", "BTCUSDT", "4h", 0, 4 * step)
            cached = data.load_bars("spot", "BTCUSDT")
        self.assertEqual(requests, [(step, 3 * step), (0, step), (3 * step, 4 * step)])
        self.assertEqual(result.open_time.tolist(), [0, step, 2 * step, 3 * step])
        self.assertEqual(len(cached), 4)

    def test_missing_candle_is_reported_and_not_filled(self):
        step = 3_600_000
        frame = pd.DataFrame([[t, 10, 12, 9, 11, 7, 77, t + step - 1]
                              for t in [0, 2 * step]], columns=data.BAR_COLUMNS)
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, "DATA_DIR", Path(tmp) / "data"):
            path = data._path("futures", "BTCUSDT")
            data._write_csv(frame, path)
            audit = data._audit(frame, path, 0, 3 * step, step)
        self.assertFalse(audit["coverage_ok"])
        self.assertEqual(audit["internal_missing_bars"], 1)
        self.assertEqual(audit["gap_after_timestamps_ms"], [0])
        self.assertEqual(len(frame), 2)

    def test_blank_historical_funding_mark_is_nan(self):
        events = [{"fundingTime": 2, "fundingRate": "0.0001", "markPrice": ""},
                  {"fundingTime": 28_800_002, "fundingRate": "-0.0002", "markPrice": "12.5"}]
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, "DATA_DIR", Path(tmp)), \
                patch.object(data, "_get", side_effect=[events, []]):
            result = data.fetch_funding("BTCUSDT", 0, 57_600_000)
            loaded = data.load_funding("BTCUSDT")
        self.assertTrue(pd.isna(result.markPrice.iloc[0]))
        self.assertEqual(result.fundingTime.tolist(), [2, 28_800_002])
        self.assertEqual(loaded.fundingRate.tolist(), [0.0001, -0.0002])
        self.assertEqual(loaded.markPrice.iloc[1], 12.5)

    def test_rejects_interval_collision(self):
        with self.assertRaises(ValueError):
            data.fetch_bars("spot", "BTCUSDT", "1h", 0, 3_600_000)

    def test_missing_funding_event_fails_coverage(self):
        hour = 3_600_000
        frame = pd.DataFrame([[2, 0.0001, 10.0], [16 * hour + 2, 0.0001, 11.0]],
                             columns=data.FUNDING_COLUMNS)
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, "DATA_DIR", Path(tmp) / "data"):
            path = data._path("futures", "BTCUSDT", "funding")
            data._write_csv(frame, path)
            audit = data._audit(frame, path, 0, 24 * hour)
        self.assertFalse(audit["coverage_ok"])
        self.assertEqual(audit["events_gap_over_9h"], 1)

    def test_download_failure_is_recorded_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, "DATA_DIR", Path(tmp)), \
                patch.object(data, "fetch_bars", side_effect=RuntimeError("simulated missing source")):
            manifest = data.download(0, 14_400_000, ["BTCUSDT"], workers=1)
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["errors"][0]["symbol"], "BTCUSDT")
        self.assertIn("simulated missing source", manifest["errors"][0]["error"])


if __name__ == "__main__":
    unittest.main()
