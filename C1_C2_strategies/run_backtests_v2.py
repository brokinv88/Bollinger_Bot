"""Vòng 2 research: C2 MTF (H1 vs level H4), funding vào chi phí, split train/test.

Thay đổi so vòng 1 (một vòng, một chủ đề chính — T05):
- C2 sweep/CHoCH đúng khái niệm: level H4, quét xuyên trên H1.
- Chi phí funding được cộng vào (funding trung bình mỗi cặp).
- C1/C2 được tách train (2023-07→2025-06) / test (2025-07→2026-09).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from . import data as data_mod
from . import engine, indicators as ind, report, strategies

H4_TF = "4h"
H1_TF = "1h"
START_MS = int(pd.Timestamp("2023-07-01", tz="UTC").value // 1_000_000)
SPLIT_MS = int(pd.Timestamp("2025-07-01", tz="UTC").value // 1_000_000)
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


def mean_funding_per8h(symbol: str) -> float:
    s = data_mod.fetch_funding(symbol, START_MS, END_MS)
    if not len(s):
        return 0.0
    return float(s.mean())


def h4_levels_for(h4: pd.DataFrame, lookback: int = 60, k: int = 3) -> pd.DataFrame:
    sw = ind.swing_points(h4, k)
    hi = sw["swing_high"].to_numpy()
    lo = sw["swing_low"].to_numpy()
    n = len(h4)
    out_hi = pd.Series(index=h4.index, dtype=float)
    out_lo = pd.Series(index=h4.index, dtype=float)
    for i in range(n):
        w = slice(max(0, i - lookback), i + 1)
        oh = hi[w]
        ol = lo[w]
        mh = oh[~pd.isna(oh)]
        ml = ol[~pd.isna(ol)]
        out_hi.iloc[i] = mh.max() if len(mh) else float("nan")
        out_lo.iloc[i] = ml.min() if len(ml) else float("nan")
    return pd.DataFrame({"level_high": out_hi, "level_low": out_lo}, index=h4.index)


def run() -> pd.DataFrame:
    rows = []
    all_trades: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        print(f"[v2] {symbol} ...", flush=True)
        h4 = data_mod.fetch_ohlcv(symbol, H4_TF, START_MS, END_MS)
        h1 = data_mod.fetch_ohlcv(symbol, H1_TF, START_MS, END_MS)
        f = mean_funding_per8h(symbol)
        meta = {"funding_per_8h": round(f, 6), "bar_hours": 1.0}

        # C1 (H4, funding-aware)
        sig_c1 = strategies.gen_c1(h4)
        sig_c1["funding_per_8h"] = f
        sig_c1["bar_hours"] = 4.0
        t_c1 = engine.run_backtest(h4, sig_c1, symbol=symbol)

        # C2 MTF: H1 signal vs H4 levels
        lv = h4_levels_for(h4)
        sig_mtf_sweep = strategies.gen_c2_mtf(h1, lv, require_sweep=True)
        sig_mtf_base = strategies.gen_c2_mtf(h1, lv, require_sweep=False)
        for s in (sig_mtf_sweep, sig_mtf_base):
            s["funding_per_8h"] = f
            s["bar_hours"] = 1.0
        t_c2s = engine.run_backtest(h1, sig_mtf_sweep, symbol=symbol)
        t_c2b = engine.run_backtest(h1, sig_mtf_base, symbol=symbol)

        for lbl, t in [("C1_BOS_H4v2", t_c1), ("C2_MTF_SWEEP", t_c2s), ("C2_MTF_BASE", t_c2b)]:
            if not len(t):
                continue
            train = t[t["entry_time"] < pd.Timestamp(SPLIT_MS, unit="ms", tz="UTC")]
            test = t[t["entry_time"] >= pd.Timestamp(SPLIT_MS, unit="ms", tz="UTC")]
            for part, sub in [("ALL", t), ("TRAIN", train), ("TEST", test)]:
                if not len(sub):
                    continue
                m = report._metrics(sub)
                eq = report._equity_path(sub)
                m.update(
                    {
                        "symbol": symbol,
                        "strategy": lbl,
                        "split": part,
                        "funding_p8h": round(f, 6),
                        "bh_return": round(report.bh_return(h4), 4),
                        "max_dd_pct": round(report.max_drawdown_pct(eq), 4),
                        "final_equity": round(eq[-1], 2),
                    }
                )
                rows.append(m)
                all_trades[f"{lbl}_{part}"] = sub

    summary = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    summary.to_csv(OUT / "summary_v2.csv", index=False)
    for k, tdf in all_trades.items():
        tdf.to_csv(OUT / f"trades_v2_{k}.csv", index=False)
    print(summary.sort_values(["strategy", "split"]).to_string())
    return summary


if __name__ == "__main__":
    run()