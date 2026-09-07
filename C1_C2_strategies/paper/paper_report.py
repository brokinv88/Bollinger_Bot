"""Tạo báo cáo định kỳ cho tài khoản paper C1 từ state + journal.

Chạy sau paper_runner; xuất csv summary + console.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import paper_account as acc
from . import paper_config as cfg


def report() -> None:
    acct = acc.load()
    journal_path = cfg.JOURNAL_FILE
    closed = []
    if journal_path.exists():
        closed = pd.read_csv(journal_path)

    txt = []
    txt.append("=" * 58)
    txt.append(f"BÁO CÁO PAPER C1 — ${cfg.START_CASH:.0f} ảo  ({acct.last_update})")
    txt.append("=" * 58)
    txt.append(f"  Số dư   : ${acct.cash:,.2f}")
    txt.append(f"  Equity  : ${acct.equity():,.2f}")
    txt.append(f"  Peak    : ${acct.equity_high_water:,.2f}")
    txt.append(f"  PnL thực : ${acct.realized_pnl:,.2f}")
    txt.append(f"  Đã đóng : {acct.closed_trades} lệnh")
    txt.append(f"  Đang mở : {len(acct.positions)} lệnh")

    if closed is not None and len(closed):
        total_usd = closed["pnl_usd"].sum()
        wins = closed[closed["pnl_usd"] > 0]
        losses = closed[closed["pnl_usd"] <= 0]
        txt.append(f"\n--- {len(closed)} lệnh đã đóng ---")
        txt.append(f"  Win rate : {100*len(wins)/len(closed):.1f}%")
        txt.append(f"  PnL      : ${total_usd:+.2f}")
        txt.append(f"  Lợi TB/R : {closed['r'].mean():+.3f}")
        txt.append("\n  10 lệnh gần nhất:")
        for r in closed.tail(10).itertuples():
            txt.append(f"    {r.symbol[:12]:12s} {r.direction:>2} {r.reason:7s} "
                       f"R={r.r:+.3f} ${r.pnl_usd:+.2f}")
    else:
        txt.append("\n  (chưa có lệnh đóng — forward test mới bắt đầu)")

    if acct.positions:
        txt.append("\n  Vị thế đang mở:")
        for p in acct.positions:
            txt.append(f"    {p.symbol[:12]:12s} {'L' if p.direction==1 else 'S'} "
                       f"qty={p.qty:.6g} entry={p.entry:.6g} stop={p.stop:.6g}")

    out = "\n".join(txt)
    print(out)
    (cfg.REPORTS / "paper_report.txt").write_text(out)

    # Lưu summary csv của lệnh đã đóng (forward test journal metrics)
    if closed is not None and len(closed):
        metrics = {
            "n_trades": len(closed),
            "win_rate": round(len(wins) / len(closed), 4),
            "total_pnl_usd": round(total_usd, 2),
            "avg_pnl_usd": round(closed["pnl_usd"].mean(), 2),
            "avg_r": round(closed["r"].mean(), 4),
            "total_r": round(closed["r"].sum(), 2),
            "profit_factor": round(
                closed["pnl_usd"][closed["pnl_usd"] > 0].sum()
                / -closed["pnl_usd"][closed["pnl_usd"] < 0].sum()
                if (closed["pnl_usd"] < 0).any() else float("inf"), 3
            ),
            "max_dd_pct": round(
                100 * (acct.equity_high_water - acct.equity()) / acct.equity_high_water, 2
            ),
        }
        pd.DataFrame([metrics]).to_csv(cfg.REPORTS / "paper_metrics.csv", index=False)


if __name__ == "__main__":
    report()
