"""Decision gate tự động — so số liệu paper thực tế với tiêu chí nghiệm thu REAL.

Tiêu chí (futures_trading_plan.md mục 6 & 7):
  1. Chạy paper >= 30 ngày (mục 7.2)
  2. Profit Factor > 1.3
  3. Win rate chấp nhận 25–40% (đặc tính trend-following)
  4. Max DD tài khoản < 20%
  5. Số lệnh đóng đủ để PF có nghĩa thống kê (>= 30 lệnh)

Usage: python futures_acceptance_gate.py [--notify] [--trades paper_trades.csv] [--day-conf <secs>]
Kết quả: in bảng + verdict GREEN/AMBER/RED; --notify gửi Telegram.
"""
import argparse
import csv
import json
import math
import os
import time

DB_DIR = os.path.join(os.path.dirname(__file__), "futures_db")
TRADES_DEFAULT = "paper_trades.csv"
EQUITY_DEFAULT = "paper_equity.csv"
STATE_DEFAULT = "paper_state.json"
REQUIRED_DAYS = 30
MIN_PF = 1.3
MIN_TRADES = 30
MAX_DD_PCT = 20.0
WR_LOW, WR_HIGH = 25.0, 40.0


def _load(path):
    cands = [x for x in [path, os.path.join(DB_DIR, path)] if x and os.path.exists(x)]
    return cands[0] if cands else None


def _ts_now():
    return int(time.time() * 1000)


def run_gate(trades_path, equity_path, state_path, days_conf=REQUIRED_DAYS):
    tp, ep, sp = _load(trades_path), _load(equity_path), _load(state_path)

    closed = []
    first_equity_ts = None
    if ep:
        with open(ep) as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            if r.get("note") == "day":
                first_equity_ts = int(r["ts"]) if first_equity_ts is None else first_equity_ts
        eq_series = [float(r["equity"]) for r in rows]
    else:
        eq_series = []

    if tp:
        with open(tp) as f:
            closed = [r for r in csv.DictReader(f)]
    else:
        closed = []

    state = {}
    if sp:
        with open(sp) as f:
            state = json.load(f)

    n_trades = len(closed)
    wins = [r for r in closed if float(r.get("net_usd", 0)) > 0]
    losses = [r for r in closed if float(r.get("net_usd", 0)) < 0]
    wr = (len(wins) / n_trades * 100.0) if n_trades else 0.0
    gross_win = sum(float(r.get("net_usd", 0)) for r in wins)
    gross_loss = abs(sum(float(r.get("net_usd", 0)) for r in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (math.inf if gross_win > 0 else 0.0)

    peak, max_dd = -math.inf, 0.0
    for v in eq_series:
        peak = max(peak, v)
        if peak > 0:
            dd = (peak - v) / peak * 100.0
            max_dd = max(max_dd, dd)

    days = 0
    if first_equity_ts:
        days = round((_ts_now() - first_equity_ts) / 86400000.0, 1)
        days = max(days, 0.0)

    equity = float(state.get("equity", eq_series[-1] if eq_series else 0.0))
    n_open = len(state.get("positions", []))
    n_total = int(state.get("n_trades", n_trades))

    rows = [
        ("Số ngày chạy paper", f"{days:.1f}", f">= {days_conf}"),
        ("Lệnh đóng", str(n_trades), f">= {MIN_TRADES}"),
        ("Win rate", f"{wr:.1f}%", f"{WR_LOW}–{WR_HIGH}%"),
        ("Profit Factor", "%.2f" % (pf if pf != math.inf else 99.0), f"> {MIN_PF}"),
        ("Max DD tài khoản", f"{max_dd:.1f}%", f"< {MAX_DD_PCT}%"),
        ("Equity hiện tại", f"${equity:,.2f}", "—"),
        ("Vị thế đang mở", str(n_open), "—"),
    ]

    verdict, reasons = "RED", []
    pf_check = (pf if pf != math.inf else 99.0) > MIN_PF
    checks = [
        ("Số ngày chạy paper", days >= days_conf),
        ("Lệnh đóng", n_trades >= MIN_TRADES),
        ("Profit Factor", pf_check),
        ("Max DD tài khoản", max_dd < MAX_DD_PCT),
        ("Win rate", len(closed) >= min(3, MIN_TRADES) and WR_LOW <= wr <= WR_HIGH),
    ]
    passed = sum(1 for _, ok in checks if ok)
    if passed == len(checks):
        verdict = "GREEN"
    elif passed >= max(3, len(checks) - 1):
        verdict = "AMBER"
    reasons = [name for name, ok in checks if not ok]

    lines = ["📊 FUTURES DECISION GATE", "=" * 34]
    for name, val, want in rows:
        lines.append(f"{name:<18} {val:>10}  (cần {want})")
    lines.append("=" * 34)
    status_map = {
        "GREEN": "✅ GREEN — ĐỦ ĐIỀU KIỆN NGHIỆM THU REAL",
        "AMBER": "🟡 AMBER — GẦN ĐẠT, chỉ còn vài tiêu chí",
        "RED": "🔴 RED — CHƯA ĐẠT, cần tiếp tục paper",
    }
    lines.append(status_map[verdict])
    if reasons:
        lines.append("Chưa đạt: " + ", ".join(reasons) + ("." if not reasons[0] == "" else ""))
    else:
        lines.append("Tất cả tiêu chí nghiệm thu đã đạt.")
    if verdict != "GREEN":
        lines.append(
            f"Sau {max(0, days_conf - days):.0f} ngày nữa sẽ đánh giá lại tự động."
        )
    return "\n".join(lines), verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notify", action="store_true")
    ap.add_argument("--trades", default=TRADES_DEFAULT)
    ap.add_argument("--equity", default=EQUITY_DEFAULT)
    ap.add_argument("--state", default=STATE_DEFAULT)
    ap.add_argument("--day-conf", type=int, default=REQUIRED_DAYS)
    args = ap.parse_args()
    msg, verdict = run_gate(args.trades, args.equity, args.state, args.day_conf)
    print(msg)
    print(f"EXIT={verdict}")
    if args.notify:
        try:
            from notifier import send_telegram_alert
            send_telegram_alert(msg)
        except Exception as e:
            print(f"[notify skip] {e}")
    # Luôn exit 0: đây là báo cáo định kỳ, không phải gate CI tự chặn.
    # Trạng thái RED/AMBER nằm trong nội dung message (Telegram/console).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())