"""Vòng 3 research: bộ lọc thời điểm phiên cho C1 (C09/S07).

Một biến duy nhất — T05: thêm điều kiện "giờ phiên" vào C1 so với baseline.
Giả thuyết ex-ante từ SMC/rules: tránh "giờ chết" 4:00–7:00 VN (= 21:00–24:00 UTC,
 tức vào lệnh ở nến H4 mở 20:00 UTC) và thứ Sáu. Không chọn giờ sau khi nhìn dữ liệu
 (chống overfit — T06); chỉ đo xem bộ lọc có giúp trên cả train lẫn test không.
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

DEAD_HOURS = {20}          # nến H4 mở 20:00 UTC chứa 21:00–24:00 = giờ chết 4–7 VN
DEAD_WEEKDAYS = {4}        # thứ Sáu (dayofweek: Mon=0..Sun=6)


def add_time_features(sig: pd.DataFrame) -> pd.DataFrame:
    s = sig.copy()
    s["entry_hour"] = s["entry_time"].dt.hour
    s["entry_weekday"] = s["entry_time"].dt.dayofweek
    return s


def run() -> None:
    all_trades: dict[str, pd.DataFrame] = {}
    profile_rows: list[dict] = []

    for symbol in SYMBOLS:
        print(f"[v3] {symbol} ...", flush=True)
        h4 = data_mod.fetch_ohlcv(symbol, H4_TF, START_MS, END_MS)
        f = float(data_mod.fetch_funding(symbol, START_MS, END_MS).mean() or 0.0)

        sig = strategies.gen_c1(h4)
        sig["funding_per_8h"] = f
        sig["bar_hours"] = 4.0
        sig = add_time_features(sig)
        t_base = engine.run_backtest(h4, sig, symbol=symbol)

        for lbl, cond in [
            ("C1_SESSION_DEAD", ~sig["entry_hour"].isin(DEAD_HOURS)),
            ("C1_SESSION_FRI", ~sig["entry_weekday"].isin(DEAD_WEEKDAYS)),
            ("C1_SESSION_ALL", ~sig["entry_hour"].isin(DEAD_HOURS) & ~sig["entry_weekday"].isin(DEAD_WEEKDAYS)),
        ]:
            s2 = sig[cond]
            t2 = engine.run_backtest(h4, s2, symbol=symbol)
            all_trades[f"{lbl}_{symbol}"] = t2

        all_trades[f"C1_BASE_{symbol}"] = t_base

        for grp, col, val in [("hour", "entry_hour", None), ("weekday", "entry_weekday", None)]:
            for gval, sub in sig.groupby(col):
                sub_t = engine.run_backtest(h4, sub, symbol=symbol)
                if not len(sub_t):
                    continue
                m = report._metrics(sub_t)
                profile_rows.append(
                    {
                        "symbol": symbol,
                        "bucket": f"{grp}",
                        "value": gval,
                        "n": len(sub_t),
                        "expectancy_r": m["expectancy_r"],
                        "win_rate": m["win_rate"],
                        "profit_factor": m["profit_factor"],
                    }
                )

    per = OUT / "summary_v3_per_symbol.csv"
    aggr = OUT / "summary_v3.csv"
    prof = OUT / "session_profile.csv"

    rows = []
    for name, t in all_trades.items():
        if not len(t):
            continue
        lbl, sym = name.rsplit("_", 1)
        split_groups = [("ALL", t)]
        t = t.copy()
        t["_ts"] = pd.to_datetime(t["entry_time"], utc=True)
        split_groups.append(("TRAIN", t[t["_ts"] < pd.Timestamp(SPLIT_MS, unit="ms", tz="UTC")]))
        split_groups.append(("TEST", t[t["_ts"] >= pd.Timestamp(SPLIT_MS, unit="ms", tz="UTC")]))
        for part, sub in split_groups:
            if not len(sub):
                continue
            m = report._metrics(sub)
            m.update({"symbol": sym.split("/")[0], "strategy": lbl, "split": part})
            rows.append(m)
    summary = pd.DataFrame(rows)
    summary.to_csv(aggr, index=False)
    summary.to_csv(per, index=False)

    pd.DataFrame(profile_rows).to_csv(prof, index=False)

    cols = ["strategy", "split", "n", "profit_factor", "win_rate", "expectancy_r"]
    print(summary.sort_values(["strategy", "split"])[cols].to_string(index=False))

    prof = pd.DataFrame(profile_rows)
    print("\n=== Kỳ vọng R theo giờ vào lệnh (UTC, H4) — toàn danh mục ===")
    p = (
        prof[prof.bucket == "hour"]
        .groupby("value")["expectancy_r"]
        .agg(["mean", "count"])
        .reindex([0, 4, 8, 12, 16, 20])
    )
    print(p.round(3).to_string())
    print("\n=== Kỳ vọng R theo thứ (0=Mon..6=Sun) ===")
    p2 = (
        prof[prof.bucket == "weekday"]
        .groupby("value")["expectancy_r"]
        .agg(["mean", "count"])
        .reindex(range(7))
    )
    print(p2.round(3).to_string())


if __name__ == "__main__":
    run()