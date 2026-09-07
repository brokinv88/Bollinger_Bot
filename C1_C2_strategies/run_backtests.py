"""Chạy backtest C1, C2 trên dữ liệu Binance USD-M futures.

- C1: phá vỡ cấu trúc thuận xu hướng (H4, trend EMA50/200, BOS swing, stop 2×ATR, TP 2R).
- C2: quét thanh khoản tại vùng cũ + CHoCH (H4, sweep rồi đóng lại, stop 2×ATR, TP 2R;
      chạy 2 nhóm: require_sweep=True vs False để tách giá trị thêm của sweep — S05).
Không đặt lệnh; chỉ đọc dữ liệu công khai.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd

from . import data as data_mod
from . import engine, report, strategies

TF = "4h"
START_MS = int(pd.Timestamp("2023-07-01", tz="UTC").value // 1_000_000)
END_MS = int(time.time() * 1000)
OUT = Path(__file__).resolve().parent / "reports"
SYMBOLS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "BNB/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
    "ADA/USDT:USDT",
    "LINK/USDT:USDT",
    "AVAX/USDT:USDT",
    "LTC/USDT:USDT",
]


def generate_trades(symbol: str, df: pd.DataFrame) -> dict:
    sig_c1 = strategies.gen_c1(df)
    sig_c2_sweep = strategies.gen_c2(df, require_sweep=True)
    sig_c2_base = strategies.gen_c2(df, require_sweep=False)

    t_c1 = engine.run_backtest(df, sig_c1, symbol=symbol)
    t_c2_sweep = engine.run_backtest(df, sig_c2_sweep, symbol=symbol)
    t_c2_base = engine.run_backtest(df, sig_c2_base, symbol=symbol)

    return {
        "C1_BOS_H4": t_c1,
        "C2_SWEEP_H4": t_c2_sweep,
        "C2_BASE_H4": t_c2_base,
    }


def run() -> pd.DataFrame:
    source = {}
    for symbol in SYMBOLS:
        print(f"[{TF}] {symbol} ...", flush=True)
        df = data_mod.fetch_ohlcv(symbol, TF, START_MS, END_MS)
        source[symbol] = {"df": df, "trades": generate_trades(symbol, df)}

    summary = report.run_all(source, OUT)
    print(summary.to_string())
    return summary


if __name__ == "__main__":
    run()