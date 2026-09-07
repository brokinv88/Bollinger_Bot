"""Vòng 4 research: lọc "close tạo cấu trúc mới rõ" cho C1 (fresh close window).

Một biến duy nhất — T05: thêm fresh_close_window=16 vào gen_c1 so với baseline.
Giả thuyết ex-ante: nến breakout yếu (tái chạm level cũ, close chưa phải mức mới nhất)
sinh ra nhiễu — nhóm thường thấy nhất ở LTC. Đo trên train/test, mọi cặp.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from . import data as data_mod
from . import engine, report, strategies

H4_TF = "4h"
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
FRESH = 16


def run() -> None:
    all_trades: dict[str, pd.DataFrame] = {}
    for symbol in SYMBOLS:
        print(f"[v4] {symbol} ...", flush=True)
        h4 = data_mod.fetch_ohlcv(symbol, H4_TF, START_MS, END_MS)
        f = float(data_mod.fetch_funding(symbol, START_MS, END_MS).mean() or 0.0)

        s_base = strategies.gen_c1(h4)
        s_fr = strategies.gen_c1(h4, fresh_close_window=FRESH)
        for s in (s_base, s_fr):
            s["funding_per_8h"] = f
            s["bar_hours"] = 4.0
        lbls = ["C1_BASE", "C1_FRESH16"]
        for lbl, sg in zip(lbls, (s_base, s_fr)):
            t = engine.run_backtest(h4, sg, symbol=symbol)
            all_trades[f"{lbl}_{symbol}"] = t
            print(f"   {lbl}: n={len(t)}", flush=True)

    rows = []
    for name, t in all_trades.items():
        if not len(t):
            continue
        lbl, sym = name.rsplit("_", 1)
        tt = t.copy()
        tt["_ts"] = pd.to_datetime(tt["entry_time"], utc=True)
        for part, sub in [
            ("ALL", tt),
            ("TRAIN", tt[tt["_ts"] < pd.Timestamp(SPLIT_MS, unit="ms", tz="UTC")]),
            ("TEST", tt[tt["_ts"] >= pd.Timestamp(SPLIT_MS, unit="ms", tz="UTC")]),
        ]:
            if not len(sub):
                continue
            m = report._metrics(sub)
            m.update(
                {
                    "symbol": sym.split("/")[0],
                    "strategy": lbl,
                    "split": part,
                    "trades": len(sub),
                    "total_r": sub["r"].sum(),
                    "max_dd_pct": round(report.max_drawdown_pct(report._equity_path(sub)), 4),
                }
            )
            rows.append(m)
    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "summary_v4.csv", index=False)
    for name, t in all_trades.items():
        t.to_csv(OUT / f"trades_v4_{name.replace('/', '_')}.csv", index=False)

    for lbl in ["C1_BASE", "C1_FRESH16"]:
        for sp in ["TRAIN", "TEST"]:
            d = summary[(summary.strategy == lbl) & (summary.split == sp)]
            if not len(d):
                continue
            print(
                f"{lbl:12s} {sp:5s} n={d.trades.sum():5d} WR={d.win_rate.mean():.3f} "
                f"PF={d.profit_factor.mean():.3f} expR={d.expectancy_r.mean():+.4f} "
                f"pos_pairs={(d.expectancy_r > 0).mean():.0%}"
            )
    print("\n=== Theo cặp (TEST): BASE vs FRESH16 ===")
    d = summary[summary.split == "TEST"]
    pivot = d.pivot(index="symbol", columns="strategy", values="expectancy_r")
    print(pivot.round(3).to_string())


if __name__ == "__main__":
    run()