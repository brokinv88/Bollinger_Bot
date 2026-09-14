"""Xác thực kế hoạch $2000: tái mô phỏng equity tài khoản duy nhất
với sizing theo risk 0.75%/1% (notional = risk / (2xATR@entry)), nối chuỗi lệnh
lịch sử đúng thứ tự thời gian qua 8 coin, đo DD tài khoản thực tế.

Cảnh báo: mô hình nối tiếp (1 lệnh/lúc) KHÔNG tính đúng tương quan khi 6 vị thế
mở cùng lúc, nên kết quả DD ở đây là mức chuỗi lỗ liên tiếp — sử dụng như cận
dưới ước lượng; DD đồng thời có thể cao hơn vài phần trăm.
"""
import pandas as pd
import numpy as np
from research_futures_framework import add_indicators
from research_futures_strategy import download_all, strategy_breakout_h4, strategy_keltner_h4, CORE_SYMBOLS

P1 = (2.0, 7.0, 4.0, 2.0, 55, 0.0005, 20)   # Donchian55
P2 = (1.5, 2.0, 6.0, 3.5, 2.0, 0.0006, 18)  # Keltner


def atr_at_entry(df, entry_idx):
    return float(df["atr_pct"].iloc[entry_idx])


def simulate(strat_name, eq=2000.0, risk=0.75):
    """Trả về equity curve chuỗi thời gian + DD cho 1 chiến lược."""
    events = []
    for sym in CORE_SYMBOLS:
        df1, df4, _ = download_all(sym, 24)
        df4 = add_indicators(df4)
        if strat_name == "DON":
            _, tr = strategy_breakout_h4(df4, *P1)
        else:
            _, tr = strategy_keltner_h4(df4, *P2)
        for t in tr:
            direction = t["direction"]
            gross = direction * (t["exit"] - t["entry"]) / t["entry"]
            held = df4.iloc[t["entry_idx"]:t["exit_idx"] + 1]
            open_ts = held["open_time"].to_numpy()
            frs = df4["funding_rate"].iloc[t["entry_idx"]:t["exit_idx"] + 1].to_numpy()
            is_funding_ts = (open_ts % (8 * 3600 * 1000)) == 0
            fund_cost = -direction * float(np.sum(frs[is_funding_ts]))
            net = gross - 2 * 0.0005 + fund_cost
            events.append((df4.index[t["entry_idx"]], df4.index[t["exit_idx"]],
                           net, atr_at_entry(df4, t["entry_idx"]), sym))
    events.sort(key=lambda e: (e[1], e[0]))
    eq_curve, dd_curve, peak = [], [], eq
    for inx, outx, net, atr, sym in events:
        sl_pct = 2.0 * atr / 100.0
        notional_frac = (risk / 100.0) / sl_pct if sl_pct > 0 else 0.0
        eq *= (1 + net * notional_frac)
        peak = max(peak, eq)
        dd_curve.append((eq / peak - 1) * 100.0)
        eq_curve.append(eq)
    dd_max = min(dd_curve)
    n_trades = len(events)
    wins = sum(1 for e in events if e[2] > 0)
    return eq, dd_max, n_trades, wins, events


for name in ("DON", "KELT"):
    for risk in (0.75, 1.0):
        eq, dd, n, w, _ = simulate(name, 2000.0, risk)
        print(f"{name:5s} risk={risk:.2f}%/lệnh | 24tháng: ${eq:,.0f} ({(eq/2000-1)*100:+7.1f}%) | "
              f"maxDD tài khoản {dd:5.1f}% | {n} lệnh, WR {w/n*100:.0f}%")