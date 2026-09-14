"""Helper định cỡ lệnh theo kế hoạch futures_trading_plan.md.

Cách dùng nhanh (không tham số → in bảng tra mẫu cho $2,000):
    python futures_sizing.py                    # bảng với 8 coin đại diện
    python futures_sizing.py --eq 2000 --risk 0.75 --atr 1.6   # 1 con số cụ thể
"""
import argparse

MAX_LEV = 3.0
MAX_MARGIN_PCT = 0.40  # 40% vốn, dừng nhận size nếu vượt

META = [
    ("T1 BT C", 0.60), ("BTCUSDT", 1.03), ("BNBUSDT", 1.05),
    ("ETHUSDT", 1.41), ("SOLUSDT", 1.67), ("XRPUSDT", 1.88),
    ("DOGEUSDT", 1.78), ("ADAUSDT", 2.46), ("LINKUSDT", 1.94),
    ("DASHUSDT", 2.65), ("NEARUSDT", 2.55), ("UNIUSDT", 3.08),
    ("ZECUSDT", 2.84), ("ZENUSDT", 2.71),
]


def size(equity, risk_pct, atr_pct, lev=MAX_LEV):
    """Notional + margin cho 1 lệnh theo risk cố định."""
    sl_pct = 2.0 * atr_pct / 100.0
    risk_usd = equity * risk_pct / 100.0
    notional = risk_usd / sl_pct
    margin = notional / lev
    return notional, margin, sl_pct * 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eq", type=float, default=2000.0)
    ap.add_argument("--risk", type=float, default=0.75)
    ap.add_argument("--atr", type=float, default=None)
    a = ap.parse_args()

    if a.atr is not None:
        n, m, sl = size(a.eq, a.risk, a.atr)
        print(f"equity ${a.eq:,.0f}  risk {a.risk}%  ATR {a.atr}%")
        print(f"  SL = 2*ATR = {sl:.2f}%     notional ${n:,.0f}   margin({MAX_LEV}x) ${m:,.0f}  ({m/a.eq*100:.1f}% vốn)")
        flag = "⚠️ VƯỢT TRẦN margin 40%" if m / a.eq > MAX_MARGIN_PCT else "OK"
        print(f"  {flag}")
        return

    print(f"{'Coin':<10}{'ATR%':>6}{'SL%':>7}{'Notional':>10}{'Margin':>9}{'%Vốn':>7}")
    for name, a_pct in META:
        n, m, sl = size(a.eq, a.risk, a_pct)
        print(f"{name:<10}{a_pct:>6.2f}{sl:>7.2f}{'$'+f'{n:,.0f}':>10}{'$'+f'{m:,.0f}':>9}{m/a.eq*100:>6.1f}%")


if __name__ == "__main__":
    main()