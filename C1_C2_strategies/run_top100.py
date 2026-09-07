"""Backtest C1_BASE trên top100 USD-M futures theo thanh khoản.

Lấy top100 từ 24h quoteVolume (proxy cho 20 ngày — 거의 giống nhau),
chạy gen_c1 trên H4, tách train/test, lưu toàn bộ kết quả.
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


def get_top100(n: int = 100) -> list[str]:
    ex = data_mod._client()
    tickers = ex.fetch_tickers()
    perp = {
        s: t
        for s, t in tickers.items()
        if s.endswith("/USDT:USDT") and (t.get("quoteVolume") or 0) > 0
    }
    ranked = sorted(perp.items(), key=lambda kv: kv[1]["quoteVolume"], reverse=True)
    top = [s for s, _ in ranked[:n]]
    print(f"Top {n} by 24h quoteVolume (proxy cho 20 ngày — top 100 gần như trùng):")
    for i, s in enumerate(top[:20], 1):
        vol = perp[s]["quoteVolume"] / 1e6
        print(f"  {i:3d}. {s:20s} {vol:>10.1f}M")
    if n > 20:
        print(f"  ... ({n-20} more)")
    return top


def run(n: int = 100) -> None:
    OUT.mkdir(exist_ok=True)
    symbols = get_top100(n)

    rows = []
    errors = []
    for i, symbol in enumerate(symbols, 1):
        tag = f"[{i}/{len(symbols)}]"
        print(f"{tag} {symbol} ...", flush=True, end=" ")
        try:
            h4 = data_mod.fetch_ohlcv(symbol, H4_TF, START_MS, END_MS)
            if len(h4) < 500:
                print(f"skip ({len(h4)} bars)")
                continue
            sig = strategies.gen_c1(h4)
            if not len(sig):
                print("no signals")
                continue
            t = engine.run_backtest(h4, sig, symbol=symbol)
        except Exception as e:
            print(f"error: {e}")
            errors.append((symbol, str(e)))
            continue

        t.to_csv(OUT / f"trades_top100_{symbol.replace('/', '_').replace(':', '_')}.csv", index=False)

        for part, sub in [
            ("ALL", t),
            ("TRAIN", t[pd.to_datetime(t["entry_time"], utc=True) < pd.Timestamp(SPLIT_MS, unit="ms", tz="UTC")]),
            ("TEST", t[pd.to_datetime(t["entry_time"], utc=True) >= pd.Timestamp(SPLIT_MS, unit="ms", tz="UTC")]),
        ]:
            if not len(sub):
                continue
            m = report._metrics(sub)
            eq = report._equity_path(sub)
            m.update(
                {
                    "symbol": symbol.split("/")[0],
                    "split": part,
                    "bars": len(h4),
                    "total_trades": len(t),
                    "trades": len(sub),
                }
            )
            rows.append(m)
        print(f"n={len(t):4d} expR={report._metrics(t)['expectancy_r']:+.3f}")

    summary = pd.DataFrame(rows)
    summary.to_csv(OUT / "top100_summary.csv", index=False)

    print("\n=== Gộp theo split ===")
    for sp in ["ALL", "TRAIN", "TEST"]:
        d = summary[summary.split == sp]
        if not len(d):
            continue
        print(
            f"{sp:5s} n={d.trades.sum():7d} "
            f"WR={d.win_rate.mean():.3f} PF={d.profit_factor.mean():.3f} "
            f"expR={d.expectancy_r.mean():+.4f} "
            f"pos={100*(d.expectancy_r>0).mean():.0f}% "
            f"pairs={len(d)}"
        )

    print(f"\n=== Top 20 theo ALL expR (min 50 lệnh) ===")
    top20 = summary[(summary.split == "ALL") & (summary.trades >= 50)].sort_values(
        "expectancy_r", ascending=False
    ).head(20)
    for r in top20.itertuples():
        print(f"  {r.symbol:10s} expR={r.expectancy_r:+.3f} n={r.trades:4d} PF={r.profit_factor:.2f}")

    print(f"\n=== Bottom 10 theo ALL expR (min 50 lệnh) ===")
    bot10 = summary[(summary.split == "ALL") & (summary.trades >= 50)].sort_values(
        "expectancy_r"
    ).head(10)
    for r in bot10.itertuples():
        print(f"  {r.symbol:10s} expR={r.expectancy_r:+.3f} n={r.trades:4d} PF={r.profit_factor:.2f}")

    if errors:
        print(f"\n=== {len(errors)} lỗi fetch ===")
        for s, e in errors[:5]:
            print(f"  {s}: {e[:60]}")


if __name__ == "__main__":
    run()