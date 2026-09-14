"""Research-only screening for additions to the DON55 phase-1 universe.

Uses official Binance USD-M H1 contract bars, H1 mark bars and funding events.
The production universe is never changed by this script.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import BAR_COLUMNS, FUNDING_COLUMNS, _download_klines, _get, utc_ms
from .data import load_bars, load_funding, load_mark
from .existing_engine import Run, simulate
from .existing_signals import STRATEGIES, future_signals


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "don55_expansion"
OUT = ROOT / "reports" / "don55_expansion"
CANDIDATES = (
    "ZECUSDT", "SUIUSDT", "1000PEPEUSDT", "WLDUSDT", "NEARUSDT", "AAVEUSDT",
    "AVAXUSDT", "FILUSDT", "XLMUSDT", "ARBUSDT", "INJUSDT", "APTUSDT",
)
BASELINE = ("ADAUSDT", "BCHUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "DOTUSDT",
            "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "UNIUSDT", "XRPUSDT")
DATA_START = "2023-11-01"
TEST_START = "2024-01-01"
SPLIT = "2025-01-01"
TEST_END = "2026-09-01"


def _atomic_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temp, index=False, float_format="%.12g")
    temp.replace(path)


def _funding(symbol: str, start: int, end: int) -> pd.DataFrame:
    cursor, rows = start, []
    while cursor < end:
        page = _get("futures", "/fapi/v1/fundingRate", {
            "symbol": symbol, "startTime": cursor, "endTime": end - 1, "limit": 1000,
        })
        if not page:
            break
        rows.extend({col: row.get(col, "") for col in FUNDING_COLUMNS} for row in page
                    if start <= int(row["fundingTime"]) < end)
        following = int(page[-1]["fundingTime"]) + 1
        if following <= cursor:
            raise RuntimeError(f"Funding pagination did not advance for {symbol}")
        cursor = following
    frame = pd.DataFrame(rows, columns=FUNDING_COLUMNS)
    if frame.empty:
        raise RuntimeError(f"No funding returned for {symbol}")
    for col in FUNDING_COLUMNS:
        frame[col] = pd.to_numeric(frame[col].replace("", float("nan")), errors="raise")
    frame["fundingTime"] = frame.fundingTime.astype("int64")
    return frame.drop_duplicates("fundingTime", keep="last").sort_values("fundingTime").reset_index(drop=True)


def fetch_symbol(symbol: str, start: int, end: int, refresh: bool) -> dict:
    paths = {kind: DATA / f"{symbol}_{kind}.csv" for kind in ("bars", "mark", "funding")}
    if not refresh and all(path.exists() for path in paths.values()):
        return {"symbol": symbol, "status": "cached"}
    bars = _download_klines("futures", symbol, "1h", start, end, "bars")
    mark = _download_klines("futures", symbol, "1h", start, end, "mark")
    funding = _funding(symbol, start, end)
    _atomic_csv(bars, paths["bars"])
    _atomic_csv(mark, paths["mark"])
    _atomic_csv(funding, paths["funding"])
    return {"symbol": symbol, "status": "downloaded", "bars": len(bars),
            "mark": len(mark), "funding": len(funding)}


def fetch_all(refresh: bool = False) -> None:
    start, end = utc_ms(DATA_START), utc_ms(TEST_END)
    manifest = {"created_utc": datetime.now(timezone.utc).isoformat(), "symbols": list(CANDIDATES),
                "data_start": DATA_START, "test_start": TEST_START, "split": SPLIT,
                "test_end_exclusive": TEST_END, "sources": {
                    "bars": "https://fapi.binance.com/fapi/v1/klines",
                    "mark": "https://fapi.binance.com/fapi/v1/markPriceKlines",
                    "funding": "https://fapi.binance.com/fapi/v1/fundingRate",
                }, "results": [], "errors": []}
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {pool.submit(fetch_symbol, symbol, start, end, refresh): symbol for symbol in CANDIDATES}
        for future in as_completed(pending):
            symbol = pending[future]
            try:
                result = future.result(); manifest["results"].append(result)
                print(symbol, result["status"], flush=True)
            except Exception as error:
                manifest["errors"].append({"symbol": symbol, "error": str(error)})
                print(symbol, "ERROR", error, flush=True)
    for path in sorted(DATA.glob("*.csv")):
        manifest.setdefault("files", {})[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest["status"] = "complete" if not manifest["errors"] else "failed"
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if manifest["errors"]:
        raise RuntimeError(f"Download failed for {len(manifest['errors'])} symbol(s)")


def _read(symbol: str, kind: str) -> pd.DataFrame:
    frame = pd.read_csv(DATA / f"{symbol}_{kind}.csv")
    columns = FUNDING_COLUMNS if kind == "funding" else BAR_COLUMNS
    for col in columns:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    frame["fundingTime" if kind == "funding" else "open_time"] = frame[
        "fundingTime" if kind == "funding" else "open_time"].astype("int64")
    if kind != "funding":
        frame["close_time"] = frame.close_time.astype("int64")
    return frame


def _run_one(symbol: str, start: str, end: str, costs: float = 1.0):
    raw = _read(symbol, "bars"); mark = _read(symbol, "mark"); funding = _read(symbol, "funding")
    signals = {"DON55": {symbol: future_signals(raw, funding, STRATEGIES["DON55"])}}
    return simulate({symbol: raw}, signals, {symbol: funding}, {symbol: mark},
                    Run(("DON55",), start, end, costs=costs))


def _calendar_returns(equity: pd.DataFrame) -> dict[str, float]:
    """Calendar returns from one continuous holdout run, including open PnL."""
    series = equity[["time", "equity"]].copy()
    series["time"] = pd.to_datetime(series["time"], unit="ms", utc=True)
    start_equity = 1000.0
    boundary = float(series.loc[
        series.time <= pd.Timestamp("2026-01-01", tz="UTC"), "equity"
    ].iloc[-1])
    end_equity = float(series.equity.iloc[-1])
    return {
        "year_2025_return_pct": (boundary / start_equity - 1) * 100,
        "year_2026_return_pct": (end_equity / boundary - 1) * 100,
    }


def analyze() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, all_trades = [], []
    for symbol in CANDIDATES:
        record = {"symbol": symbol}
        runs = {}
        try:
            holdout_equity = None
            for label, start, end, costs in (
                ("validation", TEST_START, SPLIT, 1.0),
                ("holdout", SPLIT, TEST_END, 1.0),
                ("stress_holdout", SPLIT, TEST_END, 2.0),
            ):
                trades, equity, meta, _ = _run_one(symbol, start, end, costs)
                runs[label] = meta
                if label == "holdout":
                    holdout_equity = equity
                    trades.to_csv(OUT / f"trades_{symbol}.csv", index=False)
                    equity.to_csv(OUT / f"equity_{symbol}.csv", index=False)
                    if not trades.empty:
                        all_trades.append(trades.assign(candidate=symbol))
            v, h, stress = (runs[k]["metrics"] for k in
                            ("validation", "holdout", "stress_holdout"))
            calendar = _calendar_returns(holdout_equity)
            checks = {
                "validation_profit": v["net_pnl"] > 0,
                "year_2025_profit": calendar["year_2025_return_pct"] > 0,
                "year_2026_profit": calendar["year_2026_return_pct"] > 0,
                "holdout_profit": h["net_pnl"] > 0,
                "holdout_pf_1_15": (h["profit_factor"] or 0) >= 1.15,
                "holdout_trades_20": h["trades"] >= 20,
                "holdout_dd_12": h["max_drawdown_pct"] <= 12,
                "stress_profit": stress["net_pnl"] > 0,
                "no_liquidation_flag": runs["holdout"]["audit"]["liquidation_risk_bars"] == 0,
            }
            record.update({"status": "PASS" if all(checks.values()) else "FAIL",
                           "failed": ",".join(k for k, ok in checks.items() if not ok),
                           "validation_return_pct": v["return_pct"], "validation_pf": v["profit_factor"],
                           "holdout_return_pct": h["return_pct"], "holdout_pf": h["profit_factor"],
                           "holdout_trades": h["trades"], "holdout_win_rate_pct": h["win_rate_pct"],
                           "holdout_mean_r": h["mean_r"], "holdout_max_dd_pct": h["max_drawdown_pct"],
                           **calendar,
                           "stress_return_pct": stress["return_pct"], "checks": checks})
        except Exception as error:
            record.update({"status": "DATA_FAIL", "failed": str(error)})
        rows.append(record)
        print(symbol, record["status"], record.get("failed", ""), flush=True)
    table = pd.DataFrame(rows).sort_values(["status", "holdout_pf"], ascending=[False, False], na_position="last")
    table.to_csv(OUT / "screen.csv", index=False)
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(OUT / "trades_all.csv", index=False)
    selected = [row["symbol"] for row in rows if row["status"] == "PASS"]
    portfolio = {}
    raw = {symbol: load_bars("futures", symbol) for symbol in BASELINE}
    mark = {symbol: load_mark(symbol) for symbol in BASELINE}
    funding = {symbol: load_funding(symbol) for symbol in BASELINE}
    for symbol in selected:
        raw[symbol] = _read(symbol, "bars"); mark[symbol] = _read(symbol, "mark")
        funding[symbol] = _read(symbol, "funding")
    strategy = STRATEGIES["DON55"]
    signals = {"DON55": {symbol: future_signals(raw[symbol], funding[symbol], strategy)
                          for symbol in raw}}
    # Match the phase-1 risk budget: 0.25% per trade, at most three DON55 positions.
    STRATEGIES["DON55"] = replace(strategy, risk=.0025)
    try:
        for label, universe in (("baseline_12", list(BASELINE)),
                                ("expanded", list(BASELINE) + selected)):
            portfolio[label] = {"symbols": universe, "runs": {}}
            holdout_equity = None
            for period, start, end, costs in (
                ("validation", TEST_START, SPLIT, 1.0),
                ("holdout", SPLIT, TEST_END, 1.0),
                ("stress_holdout", SPLIT, TEST_END, 2.0),
            ):
                subset_raw = {symbol: raw[symbol] for symbol in universe}
                subset_funding = {symbol: funding[symbol] for symbol in universe}
                subset_mark = {symbol: mark[symbol] for symbol in universe}
                subset_signals = {"DON55": {symbol: signals["DON55"][symbol] for symbol in universe}}
                trades, equity, meta, _ = simulate(subset_raw, subset_signals, subset_funding,
                                                   subset_mark, Run(("DON55",), start, end, costs=costs))
                portfolio[label]["runs"][period] = meta
                if period == "holdout":
                    holdout_equity = equity
                trades.to_csv(OUT / f"portfolio_trades_{label}_{period}.csv", index=False)
                equity.to_csv(OUT / f"portfolio_equity_{label}_{period}.csv", index=False)
            portfolio[label]["calendar_returns"] = _calendar_returns(holdout_equity)
    finally:
        STRATEGIES["DON55"] = strategy
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "strategy": "DON55 corrected engine",
              "periods": {"warmup_start": DATA_START, "validation": [TEST_START, SPLIT],
                          "holdout": [SPLIT, TEST_END], "stress": "2x fees and slippage on holdout"},
              "gate": {"validation_profit": True, "each_following_year_profit": True,
                       "holdout_profit": True, "holdout_pf": 1.15,
                       "holdout_min_trades": 20, "holdout_max_dd_pct_at_0_75pct_risk": 12,
                       "stress_profit": True, "liquidation_flags": 0},
              "phase1_risk": {"risk_per_trade": .0025, "max_positions": 3,
                              "max_initial_open_risk": .0075},
              "selected": selected, "portfolio_comparison": portfolio, "rows": rows}
    (OUT / "results.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        fetch_all(args.refresh)
    if args.analyze:
        analyze()
    if not args.fetch and not args.analyze:
        parser.error("Use --fetch and/or --analyze")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
