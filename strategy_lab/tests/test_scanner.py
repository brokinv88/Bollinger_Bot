"""Decision-relevant checks for the read-only live scanner; no network required."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from strategy_lab.scanner import (
    DEFAULT_ACCOUNT, InsufficientHistory, assign_capacity, closed_bars, live_quantity, load_account,
    pick_universe, reference_size, run_scan, scan_symbol, write_reports,
)


HOUR = 3_600_000
DAY = 24 * HOUR
FILTERS = [
    {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "1000", "stepSize": "0.001"},
    {"filterType": "MARKET_LOT_SIZE", "minQty": "0", "maxQty": "500", "stepSize": "0"},
    {"filterType": "MIN_NOTIONAL", "minNotional": "5"},
    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
]


def candles(interval: int, n: int, next_open: int, include_current: bool = True) -> list:
    end = next_open + interval if include_current else next_open
    return [[t, "100", "103", "98", "101", "20", t + interval - 1, "25000000", 3, "10", "10", "0"]
            for t in range(next_open - n * interval, end, interval)]


def metadata(symbol="BTCUSDT", volume=100_000_000):
    return {"symbol": symbol, "baseAsset": symbol.removesuffix("USDT"), "quoteAsset": "USDT", "marginAsset": "USDT",
            "status": "TRADING", "isSpotTradingAllowed": True, "contractType": "PERPETUAL",
            "quote_volume_24h": volume, "filters": FILTERS}


def account():
    result = json.loads(json.dumps(DEFAULT_ACCOUNT))
    result["state_supplied"] = True
    return result


def signal_row(market="spot", symbol="BTCUSDT", status="SETUP"):
    return {"market": market, "symbol": symbol, "signal": 1, "side": "long", "status": status,
            "close": 100.0, "atr": 1.0, "eligible": True, "daily_liquidity": 100_000_000}


class DataAndUniverseTests(unittest.TestCase):
    def test_incomplete_candle_removed(self):
        next_open = 1_000 * HOUR
        bars = closed_bars(candles(HOUR, 3, next_open), "1h", next_open + 1234)
        self.assertEqual(len(bars), 3)
        self.assertEqual(int(bars.iloc[-1].close_time), next_open - 1)

    def test_new_token_with_only_open_candle_is_insufficient(self):
        next_open=1000*HOUR
        raw=candles(HOUR,0,next_open)
        with self.assertRaises(InsufficientHistory):
            closed_bars(raw,'1h',next_open+1234)

    def test_gaps_and_stale_data_fail_closed(self):
        next_open = 1_000 * HOUR
        raw = candles(HOUR, 3, next_open)
        with self.assertRaisesRegex(ValueError, "Missing"):
            closed_bars([raw[0], raw[2], raw[3]], "1h", next_open + 1234)
        with self.assertRaisesRegex(ValueError, "Stale"):
            closed_bars(raw[:2], "1h", next_open + 1234)

    def test_nan_and_impossible_high_rejected(self):
        next_open = 1_000 * HOUR
        raw = candles(HOUR, 3, next_open)
        raw[1][2] = "99"
        with self.assertRaisesRegex(ValueError, "OHLC"):
            closed_bars(raw, "1h", next_open + 1234)
        raw[1][2] = "nan"
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            closed_bars(raw, "1h", next_open + 1234)

    def test_universe_excludes_stables_wrappers_nonperpetual_and_resolves_ties(self):
        instruments = [metadata("ETHUSDT"), metadata("BTCUSDT"), metadata("USDCUSDT"),
                       metadata("WBETHUSDT"), metadata("BTCUPUSDT"), metadata("XRPUSDT")]
        instruments[-1]["contractType"] = "CURRENT_QUARTER"
        tickers = [{"symbol": m["symbol"], "quoteVolume": "100"} for m in instruments]
        result = pick_universe({"symbols": instruments}, tickers, "futures", 100)
        self.assertEqual([m["symbol"] for m in result], ["BTCUSDT", "ETHUSDT"])


class PositionSizingTests(unittest.TestCase):
    def test_rounds_down_and_never_increases_to_exchange_minimum(self):
        result = live_quantity(0.123456, 100, FILTERS)
        self.assertEqual(result["quantity_text"], "0.123")
        result = live_quantity(0.04, 100, FILTERS)
        self.assertEqual(result["quantity"], 0)
        self.assertEqual(result["size_status"], "BELOW_EXCHANGE_MINIMUM")

    def test_intersection_of_quantity_steps(self):
        filters = [
            {"filterType": "LOT_SIZE", "minQty": "0", "maxQty": "100", "stepSize": "0.002"},
            {"filterType": "MARKET_LOT_SIZE", "minQty": "0", "maxQty": "100", "stepSize": "0.003"},
        ]
        self.assertAlmostEqual(live_quantity(0.02, 100, filters)["quantity"], 0.018)

    def test_fees_slippage_and_caps_stay_within_risk_budget(self):
        for market, budget, cap in [("spot", 20, 750), ("futures", 12.5, 1000)]:
            sized = reference_size(signal_row(market), metadata(), account(), {})
            self.assertGreater(sized["quantity"], 0)
            self.assertLessEqual(sized["estimated_initial_risk_usdt"], budget)
            self.assertLessEqual(sized["reference_notional_usdt"], cap)
            self.assertGreater(sized["estimated_initial_risk_usdt"], sized["quantity"] * 2)

    def test_drawdown_halves_then_freezes(self):
        state = account()
        state["futures_equity"] = 920
        half = reference_size(signal_row("futures"), metadata(), state, {})
        self.assertAlmostEqual(half["risk_budget_usdt"], 920 * 0.0125 * 0.5)
        state["futures_equity"] = 880
        freeze = reference_size(signal_row("futures"), metadata(), state, {})
        self.assertEqual(freeze["quantity"], 0)
        self.assertEqual(freeze["size_status"], "DRAWDOWN_FREEZE")

    def test_capacity_does_not_multiply_full_risk_across_simultaneous_signals(self):
        rows = [signal_row("futures", "BTCUSDT"), signal_row("futures", "ETHUSDT")]
        meta = {(r["market"], r["symbol"]): metadata(r["symbol"]) for r in rows}
        result = assign_capacity(rows, meta, account(), {})
        self.assertTrue(result[0]["capacity_reserved"])
        self.assertFalse(result[1]["capacity_reserved"])
        self.assertLessEqual(sum(r["estimated_initial_risk_usdt"] for r in result), 20)
        self.assertEqual(result[1]["size_status"], "NO_RISK_OR_CAPITAL_CAPACITY")

    def test_expired_signals_do_not_reserve_risk(self):
        rows = [signal_row("futures", "BTCUSDT", "EXPIRED_SIGNAL"), signal_row("futures", "ETHUSDT")]
        meta = {(r["market"], r["symbol"]): metadata(r["symbol"]) for r in rows}
        result = assign_capacity(rows, meta, account(), {})
        self.assertFalse(result[0]["capacity_reserved"])
        self.assertEqual(result[0]["size_status"], "EXPIRED_REFERENCE_DO_NOT_ENTER")
        self.assertEqual(result[1]["risk_budget_usdt"], 12.5)

    def test_manual_narrative_capacity_works_across_sleeves(self):
        state = account()
        state["positions"] = [{"market": "spot", "symbol": "ETHUSDT", "side": "long",
                               "initial_risk_usdt": 37.5, "notional_usdt": 600}]
        result = reference_size(signal_row("futures", "SOLUSDT"), metadata("SOLUSDT"), state,
                                {"ETHUSDT": ["l1"], "SOLUSDT": ["l1"]})
        self.assertEqual(result["quantity"], 0)
        self.assertEqual(result["size_status"], "NO_RISK_OR_CAPITAL_CAPACITY")

    def test_bad_account_does_not_silently_use_default_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "account.json"
            path.write_text('{"futures_equity": 500}')
            with self.assertRaisesRegex(ValueError, "requires"):
                load_account(path)


class EndToEndTests(unittest.TestCase):
    def test_scan_marks_latest_signal_expired_and_no_orders_exist(self):
        now = 1_000 * DAY + 2 * HOUR + 90_000
        class FakeClient:
            def bars(self, market, symbol, interval, limit, asof):
                duration = {"1h": HOUR, "4h": 4 * HOUR, "1d": DAY}[interval]
                next_open = asof // duration * duration
                return closed_bars(candles(duration, limit, next_open), interval, asof)
        featured = pd.DataFrame([{"signal": 1, "eligible": True, "trend": 1, "atr": 2,
                                  "daily_liquidity": 30_000_000}])
        with patch("strategy_lab.scanner.features", return_value=featured):
            row = scan_symbol(FakeClient(), metadata(), "futures", now, None, {})
        self.assertEqual(row["status"], "EXPIRED_SIGNAL")
        self.assertEqual(row["signal"], 1)

    def test_no_htf_trend_is_filtered_out_for_futures(self):
        now = 1_000 * DAY + 2 * HOUR + 90_000
        class FakeClient:
            def bars(self, market, symbol, interval, limit, asof):
                duration = {"1h": HOUR, "4h": 4 * HOUR, "1d": DAY}[interval]
                return closed_bars(candles(duration, limit, asof // duration * duration), interval, asof)
        featured = pd.DataFrame([{"signal": 0, "eligible": True, "trend": 0, "atr": 2}])
        with patch("strategy_lab.scanner.features", return_value=featured):
            row = scan_symbol(FakeClient(), metadata(), "futures", now, None, {})
        self.assertEqual(row["status"], "FILTERED_OUT")

    def test_failed_network_writes_explicit_failure_not_empty_success(self):
        class FakeClient:
            def get(self, *args, **kwargs):
                raise RuntimeError("offline")
        args = argparse.Namespace(account=None, narratives=None, market="both", workers=1, limit=3)
        report = run_scan(args, FakeClient())
        self.assertEqual(report["run_status"], "FAILED")
        self.assertEqual(len(report["errors"]), 2)
        with tempfile.TemporaryDirectory() as folder:
            write_reports(Path(folder), report)
            self.assertIn("FAILED", (Path(folder) / "scan_vi.md").read_text())
            self.assertEqual(json.loads((Path(folder) / "scan.json").read_text())["rows"], [])

    def test_watchlist_suffixes_and_json_have_real_report(self):
        rows = [signal_row("spot", "BTCUSDT", "WATCH"), signal_row("futures", "ETHUSDT", "WATCH")]
        for row in rows:
            row.update(quantity_text="0", size_status="NO_SIGNAL")
        report = {"generated_at_utc": "2026-09-06T12:00:00+00:00", "run_status": "OK",
                  "account": account(), "errors": [], "rows": rows}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_reports(output, report)
            self.assertEqual((output / "tradingview_spot.txt").read_text().strip(), "BINANCE:BTCUSDT")
            self.assertEqual((output / "tradingview_futures.txt").read_text().strip(), "BINANCE:ETHUSDT.P")
            self.assertIn("EXPANDED_UNVALIDATED", (output / "scan_vi.md").read_text())


if __name__ == "__main__":
    unittest.main()
