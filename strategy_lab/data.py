"""Public Binance historical data, without credentials or order endpoints.

All ranges are UTC and end-exclusive. CSV timestamps retain Binance milliseconds.
The frozen universe is intentionally a survivor sample, not a point-in-time top 200.
Run: python -m strategy_lab.data --start 2021-01-01 --end 2026-09-01
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_SYMBOLS = tuple(f"{x}USDT" for x in (
    "BTC", "ETH", "BNB", "XRP", "ADA", "DOGE", "LINK", "LTC", "BCH", "DOT", "UNI", "SOL"
))
SYMBOLS = DEFAULT_SYMBOLS
BAR_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "quote_vol", "close_time"]
FUNDING_COLUMNS = ["fundingTime", "fundingRate", "markPrice"]
INTERVAL_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
BASE_URLS = {"spot": "https://api.binance.com", "futures": "https://fapi.binance.com"}
_LOCAL = threading.local()
_RATE_LOCK = threading.Lock()
_NEXT_REQUEST = {"spot": 0.0, "futures": 0.0, "funding": 0.0}


def utc_ms(value: str) -> int:
    stamp = pd.Timestamp(value)
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return int(stamp.timestamp() * 1000)


def _iso(value: int | None) -> str | None:
    return None if value is None else datetime.fromtimestamp(value / 1000, timezone.utc).isoformat()


def _path(market: str, symbol: str, kind: str = "bars") -> Path:
    if market not in BASE_URLS:
        raise ValueError("market must be spot or futures")
    if symbol not in DEFAULT_SYMBOLS and not (symbol.isalnum() and symbol.endswith("USDT")):
        raise ValueError(f"Invalid public Binance symbol: {symbol!r}")
    suffix = {"bars": "", "mark": "_mark", "funding": "_funding"}[kind]
    return DATA_DIR / market / f"{symbol}{suffix}.csv"


def _pause(bucket: str, weight: float) -> None:
    # Conservatively reserve 1,200 weight/minute; funding <= 1 request/sec.
    spacing = 1.0 if bucket == "funding" else weight / 20.0
    with _RATE_LOCK:
        now = time.monotonic()
        due = max(now, _NEXT_REQUEST[bucket])
        _NEXT_REQUEST[bucket] = due + spacing
    if due > now:
        time.sleep(due - now)


def _get(market: str, endpoint: str, params: dict[str, Any], weight: int = 1) -> list:
    if not hasattr(_LOCAL, "session"):
        _LOCAL.session = requests.Session()
        _LOCAL.session.headers.update({"User-Agent": "strategy-lab-research/1.0"})
    bucket = "funding" if endpoint.endswith("fundingRate") else market
    last_error: Exception | None = None
    for attempt in range(6):
        _pause(bucket, weight)
        try:
            response = _LOCAL.session.get(BASE_URLS[market] + endpoint, params=params, timeout=(10, 45))
            if response.status_code in (418, 429):
                wait = min(float(response.headers.get("Retry-After", 30 * (attempt + 1))), 300)
                print(f"Rate limited {market}: waiting {wait:.0f}s", flush=True)
                time.sleep(wait)
                response.raise_for_status()
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, list):
                raise RuntimeError(f"Unexpected Binance response: {result!r}")
            return result
        except (requests.RequestException, ValueError, RuntimeError) as error:
            last_error = error
            if attempt < 5:
                time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f"Public data request failed: {market} {endpoint} {params}: {last_error}")


def _read(path: Path, funding: bool = False) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Download historical data first: {path}")
    frame = pd.read_csv(path)
    required = FUNDING_COLUMNS if funding else BAR_COLUMNS
    missing = set(required) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    time_cols = ["fundingTime"] if funding else ["open_time", "close_time"]
    for col in required:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    for col in time_cols:
        frame[col] = frame[col].astype("int64")
    return frame[required].sort_values(time_cols[0]).reset_index(drop=True)


def load_bars(market: str, symbol: str) -> pd.DataFrame:
    """Load canonical 4h spot or 1h USD-M contract bars from the local cache."""
    return _read(_path(market, symbol))


def load_mark(symbol: str) -> pd.DataFrame:
    """Actual Binance historical H1 mark-price OHLC (zero volume by design)."""
    return _read(_path("futures", symbol, "mark"))


def load_funding(symbol: str) -> pd.DataFrame:
    """Actual funding events; blank historical markPrice remains NaN, never zero."""
    return _read(_path("futures", symbol, "funding"), funding=True)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".csv.tmp")
    frame.to_csv(tmp, index=False, float_format="%.12g")
    tmp.replace(path)


def _download_klines(market: str, symbol: str, interval: str, start_ms: int, end_ms: int,
                      kind: str) -> pd.DataFrame:
    if interval not in INTERVAL_MS:
        raise ValueError(f"Unsupported interval {interval}")
    if kind == "mark":
        endpoint = "/fapi/v1/markPriceKlines"
    else:
        endpoint = "/api/v3/klines" if market == "spot" else "/fapi/v1/klines"
    limit = 1000 if market == "spot" else 1500
    weight = 2 if market == "spot" else 10
    cursor, rows = start_ms, []
    while cursor < end_ms:
        page = _get(market, endpoint, {
            "symbol": symbol, "interval": interval, "startTime": cursor,
            "endTime": end_ms - 1, "limit": limit,
        }, weight=weight)
        if not page:
            break
        for row in page:
            if start_ms <= int(row[0]) < end_ms and int(row[6]) < end_ms:
                rows.append([row[0], row[1], row[2], row[3], row[4], row[5], row[7], row[6]])
        next_cursor = int(page[-1][0]) + INTERVAL_MS[interval]
        if next_cursor <= cursor:
            raise RuntimeError(f"Pagination did not advance: {market} {symbol} {kind}")
        cursor = next_cursor
    frame = pd.DataFrame(rows, columns=BAR_COLUMNS)
    for col in BAR_COLUMNS:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
    for col in ("open_time", "close_time"):
        frame[col] = frame[col].astype("int64")
    return frame


def fetch_bars(market: str, symbol: str, interval: str, start_ms: int, end_ms: int,
               refresh: bool = False) -> pd.DataFrame:
    """Fetch/cache end-exclusive bars; never manufactures missing candles.

    The canonical cache fixes spot=4h and futures=1h to prevent interval collisions.
    A cache can be incrementally extended; --refresh re-downloads the requested range.
    Internal historical gaps are preserved and disclosed in manifest.json.
    """
    expected = {"spot": "4h", "futures": "1h"}.get(market)
    if interval != expected:
        raise ValueError(f"Canonical {market} cache requires {expected}, received {interval}")
    return _fetch_klines(market, symbol, interval, start_ms, end_ms, refresh, "bars")


def _fetch_klines(market: str, symbol: str, interval: str, start_ms: int, end_ms: int,
                   refresh: bool, kind: str) -> pd.DataFrame:
    if end_ms <= start_ms:
        raise ValueError("end must be after start")
    path = _path(market, symbol, kind)
    old = _read(path) if path.exists() and not refresh else pd.DataFrame(columns=BAR_COLUMNS)
    pieces = [old] if not old.empty else []
    ranges: list[tuple[int, int]] = []
    if old.empty:
        ranges.append((start_ms, end_ms))
    else:
        first, last = int(old.open_time.iloc[0]), int(old.open_time.iloc[-1])
        if start_ms < first:
            ranges.append((start_ms, min(first, end_ms)))
        if end_ms > last + INTERVAL_MS[interval]:
            ranges.append((max(start_ms, last + INTERVAL_MS[interval]), end_ms))
    for range_start, range_end in ranges:
        frame = _download_klines(market, symbol, interval, range_start, range_end, kind)
        if not frame.empty:
            pieces.append(frame)
    if not pieces:
        raise RuntimeError(f"No actual data returned for {market} {symbol} {kind}")
    frame = pd.concat(pieces, ignore_index=True).sort_values("open_time").reset_index(drop=True)
    if frame.open_time.duplicated().any():
        raise RuntimeError(f"Duplicate data returned for {market} {symbol} {kind}; refusing overwrite")
    for col in ("open_time", "close_time"):
        frame[col] = frame[col].astype("int64")
    _write_csv(frame, path)
    return frame[(frame.open_time >= start_ms) & (frame.close_time < end_ms)].reset_index(drop=True)


def fetch_funding(symbol: str, start_ms: int, end_ms: int, refresh: bool = False) -> pd.DataFrame:
    path = _path("futures", symbol, "funding")
    old = _read(path, funding=True) if path.exists() and not refresh else pd.DataFrame(columns=FUNDING_COLUMNS)
    rows: list[dict] = []
    cursor = start_ms
    # Re-request the last event when appending to detect a changed historical record.
    ranges = [(start_ms, end_ms)] if old.empty else []
    if not old.empty:
        if start_ms < int(old.fundingTime.min()):
            ranges.append((start_ms, min(end_ms, int(old.fundingTime.min()))))
        ranges.append((max(start_ms, int(old.fundingTime.max())), end_ms))
    for range_start, range_end in ranges:
        cursor = range_start
        while cursor < range_end:
            page = _get("futures", "/fapi/v1/fundingRate", {
                "symbol": symbol, "startTime": cursor, "endTime": range_end - 1, "limit": 1000,
            })
            if not page:
                break
            rows.extend({col: row.get(col, "") for col in FUNDING_COLUMNS} for row in page
                        if range_start <= int(row["fundingTime"]) < range_end)
            next_cursor = int(page[-1]["fundingTime"]) + 1
            if next_cursor <= cursor:
                raise RuntimeError(f"Funding pagination did not advance for {symbol}")
            cursor = next_cursor
    fresh = pd.DataFrame(rows, columns=FUNDING_COLUMNS)
    for col in FUNDING_COLUMNS:
        fresh[col] = pd.to_numeric(fresh[col].replace("", float("nan")), errors="raise")
    pieces = [part for part in (old, fresh) if not part.empty]
    if not pieces:
        raise RuntimeError(f"No actual funding returned for {symbol}")
    frame = pd.concat(pieces, ignore_index=True).drop_duplicates("fundingTime", keep="last")
    frame = frame.sort_values("fundingTime").reset_index(drop=True)
    frame["fundingTime"] = frame.fundingTime.astype("int64")
    _write_csv(frame, path)
    return frame[(frame.fundingTime >= start_ms) & (frame.fundingTime < end_ms)].reset_index(drop=True)


def _audit(frame: pd.DataFrame, path: Path, start_ms: int, end_ms: int,
           interval_ms: int | None = None) -> dict:
    funding = interval_ms is None
    col = "fundingTime" if funding else "open_time"
    first, last = int(frame[col].min()), int(frame[col].max())
    report: dict[str, Any] = {
        "file": str(path.relative_to(DATA_DIR.parent)), "rows": len(frame),
        "first_timestamp_ms": first, "last_timestamp_ms": last,
        "first_utc": _iso(first), "last_utc": _iso(last),
        "duplicates": int(frame[col].duplicated().sum()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if funding:
        gap_count = int((frame[col].diff() > 9 * 3_600_000).sum())
        missing_rates = int(frame.fundingRate.isna().sum())
        report.update({"missing_event_mark_prices": int(frame.markPrice.isna().sum()),
                       "missing_rates": missing_rates,
                       "events_gap_over_9h": gap_count,
                       "coverage_ok": first < start_ms + 9 * 3_600_000 and last >= end_ms - 9 * 3_600_000
                       and gap_count == 0 and missing_rates == 0 and report["duplicates"] == 0})
    else:
        jumps = frame[col].diff()
        gaps = frame.loc[jumps > interval_ms, col]
        invalid = ((frame.high < frame[["open", "close", "low"]].max(axis=1)) |
                   (frame.low > frame[["open", "close", "high"]].min(axis=1)) |
                   (frame[["open", "high", "low", "close"]] <= 0).any(axis=1) |
                   frame[BAR_COLUMNS].isna().any(axis=1))
        timing_errors = int(((frame.open_time % interval_ms != 0) |
                             (frame.close_time < frame.open_time) |
                             (frame.close_time >= frame.open_time + interval_ms)).sum())
        shortened = frame.loc[frame.close_time < frame.open_time + interval_ms - 1, "open_time"]
        report.update({
            "interval_ms": interval_ms, "expected_rows": (end_ms - start_ms) // interval_ms,
            "missing_rows": max(0, (end_ms - start_ms) // interval_ms - len(frame)),
            "internal_gap_count": int(len(gaps)),
            "internal_missing_bars": int(((jumps[jumps > interval_ms] / interval_ms) - 1).sum()),
            "gap_after_timestamps_ms": [int(frame[col].iloc[i - 1]) for i in gaps.index],
            "invalid_ohlc_rows": int(invalid.sum()),
            "timestamp_alignment_errors": timing_errors,
            "shortened_close_rows": len(shortened),
            "shortened_close_open_times_ms": shortened.astype(int).tolist(),
            "coverage_ok": first == start_ms and last == end_ms - interval_ms and not invalid.any()
            and len(gaps) == 0 and timing_errors == 0 and report["duplicates"] == 0,
        })
    return report


def download(start_ms: int, end_ms: int, symbols: list[str] | tuple[str, ...] = DEFAULT_SYMBOLS,
             workers: int = 3, refresh: bool = False) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "status": "running", "retrieval_started_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start_utc": _iso(start_ms), "requested_end_exclusive_utc": _iso(end_ms),
        "symbols": list(symbols), "universe_policy": "Fixed predeclared present-survivor universe; not historical top-200 membership; excludes delisted failures.",
        "sources": {
            "spot": "https://api.binance.com/api/v3/klines",
            "futures": "https://fapi.binance.com/fapi/v1/klines",
            "mark": "https://fapi.binance.com/fapi/v1/markPriceKlines",
            "funding": "https://fapi.binance.com/fapi/v1/fundingRate",
        },
        "notes": ["Only fully closed candles in UTC; end date exclusive.",
                  "Historical blank event markPrice is retained as NaN. Actual hourly mark OHLC is a separate series.",
                  "Mark-price hourly OHLC does not provide the exact mark price at every funding event.",
                  "Internal missing bars are preserved, never forward-filled or fabricated.",
                  "Official early close times inside otherwise aligned bars are preserved and disclosed, not rewritten. The five affected spot H4 bars in 2021 are warm-up only.",
                  "SHA256 hashes refer to entire cached files; row summaries refer to requested range."],
        "files": {}, "errors": [],
    }

    def save_manifest() -> None:
        tmp = DATA_DIR / "manifest.json.tmp"
        tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        tmp.replace(DATA_DIR / "manifest.json")

    def job(symbol: str) -> dict:
        records = {}
        for market, interval in (("spot", "4h"), ("futures", "1h")):
            frame = fetch_bars(market, symbol, interval, start_ms, end_ms, refresh)
            key = f"{market}/{symbol}"
            records[key] = _audit(frame, _path(market, symbol), start_ms, end_ms, INTERVAL_MS[interval])
            print(f"{key}: {len(frame):,} bars", flush=True)
        mark = _fetch_klines("futures", symbol, "1h", start_ms, end_ms, refresh, "mark")
        records[f"futures/{symbol}_mark"] = _audit(mark, _path("futures", symbol, "mark"), start_ms, end_ms, INTERVAL_MS["1h"])
        funding = fetch_funding(symbol, start_ms, end_ms, refresh)
        records[f"futures/{symbol}_funding"] = _audit(funding, _path("futures", symbol, "funding"), start_ms, end_ms)
        print(f"{symbol}: actual mark bars and {len(funding):,} funding events ready", flush=True)
        return records

    save_manifest()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 3))) as pool:
        pending = {pool.submit(job, symbol): symbol for symbol in symbols}
        for future in as_completed(pending):
            symbol = pending[future]
            try:
                manifest["files"].update(future.result())
            except Exception as error:
                manifest["errors"].append({"symbol": symbol, "error": str(error)})
                print(f"ERROR {symbol}: {error}", flush=True)
            save_manifest()
    manifest["retrieval_finished_utc"] = datetime.now(timezone.utc).isoformat()
    incomplete = [key for key, record in manifest["files"].items() if not record["coverage_ok"]]
    manifest["incomplete_series"] = incomplete
    manifest["status"] = "failed" if manifest["errors"] else ("complete_with_data_gaps" if incomplete else "complete")
    save_manifest()
    return manifest


def verify_cache() -> dict:
    """Re-audit every published series and its original hash without network access."""
    manifest_path = DATA_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    start_ms = utc_ms(manifest["requested_start_utc"])
    end_ms = utc_ms(manifest["requested_end_exclusive_utc"])
    errors = list(manifest["errors"])
    if manifest["status"] != "complete":
        errors.append({"error": f"Manifest status is {manifest['status']}"})
    if len(manifest["files"]) != 4 * len(manifest["symbols"]):
        errors.append({"error": "Manifest does not contain all four series per symbol"})
    for key, previous in manifest["files"].items():
        try:
            path = DATA_DIR.parent / previous["file"]
            interval_ms = previous.get("interval_ms")
            frame = _read(path, funding=interval_ms is None)
            col = "fundingTime" if interval_ms is None else "open_time"
            frame = frame[(frame[col] >= start_ms) & (frame[col] < end_ms)].reset_index(drop=True)
            current = _audit(frame, path, start_ms, end_ms, interval_ms)
            if current["sha256"] != previous["sha256"]:
                errors.append({"series": key, "error": "CSV hash changed since manifest creation"})
            if not current["coverage_ok"]:
                errors.append({"series": key, "error": "Data coverage or integrity failed", "audit": current})
        except Exception as error:
            errors.append({"series": key, "error": str(error)})
    return {"status": "verified" if not errors else "failed", "files": len(manifest["files"]),
            "verified_utc": datetime.now(timezone.utc).isoformat(), "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default="2026-09-01", help="Exclusive UTC end date")
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--verify", action="store_true", help="Verify manifest, coverage and hashes offline; no download")
    args = parser.parse_args()
    if args.verify:
        result = verify_cache()
        print(json.dumps(result, indent=2), flush=True)
        return 0 if result["status"] == "verified" else 1
    start_ms, end_ms = utc_ms(args.start), utc_ms(args.end)
    complete_hour = int(time.time() * 1000) // 3_600_000 * 3_600_000
    if start_ms % INTERVAL_MS["4h"] or end_ms % INTERVAL_MS["4h"]:
        parser.error("Start/end must align with UTC H4 boundaries")
    if end_ms > complete_hour:
        parser.error("End must not include an incomplete/future hour")
    result = download(start_ms, end_ms, args.symbols, args.workers, args.refresh)
    print(json.dumps({"status": result["status"], "files": len(result["files"]),
                      "incomplete_series": result["incomplete_series"], "errors": result["errors"]}, indent=2), flush=True)
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
