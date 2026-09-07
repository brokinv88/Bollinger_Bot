"""Fetchers and OHLCV cache for Binance USDT-M futures.

Chi tiết xem spec: Tamly/spec-C1-C2.md. Mục tiêu: chỉ đọc dữ liệu công khai,
không đặt lệnh, không cần API key.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import ccxt
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
DATA_DIR.mkdir(exist_ok=True)

FRAME_S = {"1h": 3600_000, "4h": 14_400_000, "1d": 86_400_000}


def _client() -> ccxt.binance:
    ex = ccxt.binance(
        {
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        }
    )
    ex.load_markets()
    return ex


def fetch_ohlcv(symbol: str, timeframe: str, start_ms: int, end_ms: int | None = None) -> pd.DataFrame:
    """Fetch + cache OHLCV của một cặp futures. Trả về DataFrame có datetime index."""
    cache = DATA_DIR / f"{symbol.replace('/', '_')}-{timeframe}.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        if df.index[-1].value >= (end_ms or int(time.time() * 1000)) - FRAME_S[timeframe] * 2:
            return df
    ex = _client()
    all_rows = []
    since = start_ms
    step = FRAME_S[timeframe] * 1000
    while True:
        rows = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not rows:
            break
        all_rows.extend(rows)
        last = rows[-1][0]
        if end_ms is not None and last >= end_ms:
            break
        since = last + step
        if len(rows) < 1000:
            break
    df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="ts").sort_values("ts")
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts")
    if end_ms is not None:
        df = df.loc[: pd.to_datetime(end_ms, unit="ms", utc=True)]
    df.to_parquet(cache)
    return df


def fetch_funding(symbol: str, start_ms: int, end_ms: int | None = None) -> pd.Series:
    """Funding rate lịch sử (lần/8h) của cặp USD-M futures, cache parquet.

    Trả về Series float, index = thời điểm áp dụng (UTC). Dùng để tính chi phí
    funding trung bình khi cầm lệnh qua nhiều chu kỳ.
    """
    base = symbol.replace("/", "_")
    cache = DATA_DIR / f"{base}-funding.parquet"
    if cache.exists():
        s = pd.read_parquet(cache)["rate"]
        if s.index[-1].value >= (end_ms or int(time.time() * 1000)) - 8 * 3600_000:
            return s
    ex = _client()
    rates = []
    since = start_ms
    while True:
        try:
            rows = ex.fetch_funding_rate_history(symbol, since=since, limit=1000, params={"type": "PERPETUAL"})
        except TypeError:
            rows = ex.fetch_funding_rate_history(symbol, since=since, limit=1000)
        except Exception:  # noqa: BLE001
            rows = ex.fetch_funding_rate_history(symbol, since=since, limit=1000)
        if not rows:
            break
        for r in rows:
            rates.append((r["timestamp"], float(r["fundingRate"])))
        last = rows[-1]["timestamp"]
        if end_ms is not None and last >= end_ms:
            break
        since = last + 8 * 3600_000
        if len(rows) < 1000:
            break
    if not rates:
        return pd.Series(dtype=float)
    ts = [pd.Timestamp(t, unit="ms", tz="UTC") for t, _ in rates]
    vals = [v for _, v in rates]
    s = pd.Series(vals, index=ts, name="rate").sort_index()
    s = s[~s.index.duplicated(keep="last")]
    pd.DataFrame({"rate": s}).to_parquet(cache)
    return s


def get_universe() -> list[str]:
    """Danh mục 10 cặp liquid nhất (USD-M futures) làm bộ kiểm chứng ban đầu."""
    ex = _client()
    tickers = ex.fetch_tickers()
    perp = {
        s: t
        for s, t in tickers.items()
        if s.endswith("/USDT:USDT") and t.get("quoteVolume", 0) is not None
    }
    ranked = sorted(perp.items(), key=lambda kv: kv[1]["quoteVolume"] or 0, reverse=True)
    return [s for s, _ in ranked[:10]]