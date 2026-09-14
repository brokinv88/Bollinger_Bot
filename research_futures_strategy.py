"""Hai chiến lược futures H1/H4 + backtest toàn danh mục.

Chiến lược #1 — "MTF Trend H4+H1": trend-following đa khung.
  - Filter cao (H4): close H4 > EMA50(H4) => only long / < => only short; ADX(H4) >= 18.
  - Entry (H1): EMA20(H1) cắt EMA50(H1) đúng chiều trend H4, RSI14 trong vùng kéo về (long 42..68, short 32..58).
  - Exit: SL 1.5*ATR(H1); trailing chandelier 3.0*ATR(H1) từ cực trị.

Chiến lược #2 — "H4 Breakout Donchian55 + Funding": bắt trend H4 dài hơi.
  - Entry: close phá Donchian55 theo chiều trend (close > EMA50(H4) => chỉ long, < => chỉ short).
  - Bộ lọc: ATR mở rộng (atr_pct > SMA50), funding không quá đắt (|funding| < 0.05%/8h).
  - Exit: SL 2.0*ATR(H4); trailing chandelier 3.0*ATR(H4).
"""
import pandas as pd
import numpy as np
import time
import os
import sys
from research_futures_framework import (
    fetch_klines, fetch_funding, add_indicators, merge_funding,
    trade_simulator, summarize, CORE_SYMBOLS, TAKER_FEE,
)

CACHE_DIR = "futures_cache"
os.makedirs(CACHE_DIR, exist_ok=True)


def download_all(symbol, months, refresh=False, end_offset_days=0):
    """Download klines 1h/4h + funding, append add_indicators. Cache ra csv."""
    tag = f"{CACHE_DIR}/{symbol}_{int(months)}m_off{int(end_offset_days)}"
    p1, p4, pf = f"{tag}.1h.csv", f"{tag}.4h.csv", f"{tag}.funding.csv"
    if not refresh and os.path.exists(p1) and os.path.exists(p4) and os.path.exists(pf):
        df1 = pd.read_csv(p1); df4 = pd.read_csv(p4)
        fund = pd.read_csv(pf)
        return df1, df4, fund

    end = pd.Timestamp.now("UTC").timestamp() * 1000 - end_offset_days * 86400 * 1000
    start = end - months * 30 * 86400 * 1000
    df1 = fetch_klines(symbol, "1h", int(start), int(end))
    df4 = fetch_klines(symbol, "4h", int(start), int(end))
    fund = fetch_funding(symbol, int(start), int(end))
    if len(df1) < 200 or len(df4) < 200:
        return df1, df4, fund
    df1 = merge_funding(add_indicators(df1), fund, uptime_col="open_time")
    df4 = merge_funding(add_indicators(df4), fund, uptime_col="open_time")
    df1.to_csv(p1, index=False); df4.to_csv(p4, index=False); fund.to_csv(pf, index=False)
    return df1, df4, fund


# ----------------------------------------------------------------------------
# Chiến lược #1: MTF Trend H4+H1 (trend-following, trailing thay TP cứng)
# ----------------------------------------------------------------------------
def strategy_mtf_trend(df_h1, df_h4, sl_atr=2.0, tp_atr=6.0, trail_atr=3.0, be_rmult=2.0, adx_min=18):
    # Chỉ dùng nến H4 ĐÃ ĐÓNG tại thời điểm ra tín hiệu H1: quy đổi sang close_time
    h4 = df_h4[["close_time", "ema50", "close", "adx14"]].rename(columns={
        "close_time": "h4t", "ema50": "h4_ema50", "close": "h4_close", "adx14": "h4_adx"})
    df = df_h1.copy()
    df["_t"] = df["open_time"]
    merged = pd.merge_asof(df, h4, left_on="_t", right_on="h4t", direction="backward")
    df["h4_trend"] = np.where(merged["h4_close"] > merged["h4_ema50"], 1.0, -1.0)
    df["h4_adx"] = merged["h4_adx"]

    ema20, ema50 = df["ema20"], df["ema50"]
    cross_up = (ema20 > ema50) & (ema20.shift(1) <= ema50.shift(1))
    cross_dn = (ema20 < ema50) & (ema20.shift(1) >= ema50.shift(1))
    rsi, atr = df["rsi14"], df["atr"]

    trades, pos = [], 0.0
    entry_px = entry_idx = entry_r = None
    trail = None; be_done = False
    for i in range(1, len(df)):
        if pos == 0:
            long_sig = cross_up.iloc[i] and df["h4_trend"].iloc[i] == 1 and df["h4_adx"].iloc[i] >= adx_min \
                       and not pd.isna(rsi.iloc[i]) and 42 <= rsi.iloc[i] <= 68
            short_sig = cross_dn.iloc[i] and df["h4_trend"].iloc[i] == -1 and df["h4_adx"].iloc[i] >= adx_min \
                        and not pd.isna(rsi.iloc[i]) and 32 <= rsi.iloc[i] <= 58
            if (long_sig or short_sig) and not pd.isna(atr.iloc[i]) and atr.iloc[i] > 0:
                pos = 1 if long_sig else -1
                entry_px, entry_idx = df["close"].iloc[i], i
                entry_r = atr.iloc[i] or 0.0001
                trail = entry_px - pos * sl_atr * entry_r
                be_done = False
        else:
            # nâng stop về BE sau khi đạt be_rmult*R
            if not be_done and abs(df["close"].iloc[i] - entry_px) >= be_rmult * entry_r:
                trail = entry_px
                be_done = True
            extreme = df["high"].iloc[i] if pos == 1 else df["low"].iloc[i]
            if pos == 1:
                trail = max(trail, extreme - trail_atr * entry_r)
            else:
                trail = min(trail, extreme + trail_atr * entry_r)
            tp = entry_px + pos * tp_atr * entry_r
            exit_px = None
            hit_tp = (pos == 1 and df["high"].iloc[i] >= tp) or (pos == -1 and df["low"].iloc[i] <= tp)
            hit_trail = (pos == 1 and df["low"].iloc[i] <= trail) or (pos == -1 and df["high"].iloc[i] >= trail)
            if hit_tp:
                exit_px = tp
            elif hit_trail:
                exit_px = trail
            if exit_px is not None:
                trades.append(dict(direction=pos, entry=entry_px, entry_idx=entry_idx, exit=exit_px,
                                   exit_idx=i, reason="TP" if hit_tp else "TRAIL"))
                pos = 0.0
    return df, trades


# ----------------------------------------------------------------------------
# Chiến lược #2: H4 Breakout Donchian55 + trend + funding filter
# ----------------------------------------------------------------------------
def strategy_breakout_h4(df_h4, sl_atr=2.0, tp_atr=7.0, trail_atr=4.0, be_rmult=2.0,
                         dc_len=55, funding_max=0.0005, adx_min=20):
    df = df_h4.copy()
    df["atr_sma50"] = df["atr_pct"].rolling(50).mean()
    dc_hi = df[f"dc_high{dc_len}"]
    dc_lo = df[f"dc_low{dc_len}"]

    trades, pos = [], 0.0
    entry_px = entry_idx = entry_r = None
    trail = None; be_done = False
    for i in range(1, len(df)):
        if pos == 0:
            atr_ok = not pd.isna(df["atr_sma50"].iloc[i]) and df["atr_pct"].iloc[i] > df["atr_sma50"].iloc[i]
            adx_ok = adx_min == 0 or (not pd.isna(df["adx14"].iloc[i]) and df["adx14"].iloc[i] >= adx_min)
            if not (atr_ok and adx_ok):
                continue
            fr = df["funding_rate"].fillna(0).iloc[i]
            long_sig = df["close"].iloc[i] > dc_hi.iloc[i] and df["close"].iloc[i] > df["ema50"].iloc[i] \
                       and fr <= funding_max
            short_sig = df["close"].iloc[i] < dc_lo.iloc[i] and df["close"].iloc[i] < df["ema50"].iloc[i] \
                        and fr >= -funding_max
            if long_sig:
                pos, entry_px, entry_idx = 1, df["close"].iloc[i], i
                entry_r = df["atr"].iloc[i]
            elif short_sig:
                pos, entry_px, entry_idx = -1, df["close"].iloc[i], i
                entry_r = df["atr"].iloc[i]
            if pos != 0:
                trail = entry_px - pos * sl_atr * entry_r
                be_done = False
        else:
            if not be_done and abs(df["close"].iloc[i] - entry_px) >= be_rmult * entry_r:
                trail = entry_px
                be_done = True
            extreme = df["high"].iloc[i] if pos == 1 else df["low"].iloc[i]
            if pos == 1:
                trail = max(trail, extreme - trail_atr * entry_r)
            else:
                trail = min(trail, extreme + trail_atr * entry_r)
            tp = entry_px + pos * tp_atr * entry_r
            exit_px = None
            hit_tp = (pos == 1 and df["high"].iloc[i] >= tp) or (pos == -1 and df["low"].iloc[i] <= tp)
            hit_trail = (pos == 1 and df["low"].iloc[i] <= trail) or (pos == -1 and df["high"].iloc[i] >= trail)
            if hit_tp:
                exit_px = tp
            elif hit_trail:
                exit_px = trail
            if exit_px is not None:
                trades.append(dict(direction=pos, entry=entry_px, entry_idx=entry_idx, exit=exit_px,
                                   exit_idx=i, reason="TP" if hit_tp else "TRAIL"))
                pos = 0.0
    return df, trades


# ----------------------------------------------------------------------------
# Chiến lược #2: H4 Keltner Channel Breakout + ADX + funding filter
# Khác họ với Donchian (#1): dùng EMA-based channel, ít nhiễu, đa dạng hóa.
# ----------------------------------------------------------------------------
def strategy_keltner_h4(df_h4, mult=1.5, sl_atr=2.0, tp_atr=6.0, trail_atr=3.5,
                        be_rmult=2.0, funding_max=0.0006, adx_min=18):
    df = df_h4.copy()
    mid = df["close"].ewm(span=20, adjust=False).mean()
    df["k_up"] = mid + df["atr"] * mult
    df["k_lo"] = mid - df["atr"] * mult

    trades, pos = [], 0.0
    entry_px = entry_idx = entry_r = None
    trail = None; be_done = False
    for i in range(1, len(df)):
        if pos == 0:
            fr = df["funding_rate"].fillna(0).iloc[i]
            adx = df["adx14"].iloc[i]
            aok = not pd.isna(adx) and adx >= adx_min
            long_sig = df["close"].iloc[i] > df["k_up"].iloc[i] and aok and fr <= funding_max
            short_sig = df["close"].iloc[i] < df["k_lo"].iloc[i] and aok and fr >= -funding_max
            if long_sig:
                pos, entry_px, entry_idx = 1, df["close"].iloc[i], i
                entry_r = df["atr"].iloc[i]
            elif short_sig:
                pos, entry_px, entry_idx = -1, df["close"].iloc[i], i
                entry_r = df["atr"].iloc[i]
            if pos != 0:
                trail = entry_px - pos * sl_atr * entry_r
                be_done = False
        else:
            if not be_done and abs(df["close"].iloc[i] - entry_px) >= be_rmult * entry_r:
                trail = entry_px
                be_done = True
            extreme = df["high"].iloc[i] if pos == 1 else df["low"].iloc[i]
            if pos == 1:
                trail = max(trail, extreme - trail_atr * entry_r)
            else:
                trail = min(trail, extreme + trail_atr * entry_r)
            tp = entry_px + pos * tp_atr * entry_r
            exit_px = None
            hit_tp = (pos == 1 and df["high"].iloc[i] >= tp) or (pos == -1 and df["low"].iloc[i] <= tp)
            hit_trail = (pos == 1 and df["low"].iloc[i] <= trail) or (pos == -1 and df["high"].iloc[i] >= trail)
            if hit_tp:
                exit_px = tp
            elif hit_trail:
                exit_px = trail
            if exit_px is not None:
                trades.append(dict(direction=pos, entry=entry_px, entry_idx=entry_idx, exit=exit_px,
                                   exit_idx=i, reason="TP" if hit_tp else "TRAIL"))
                pos = 0.0
    return df, trades


# ----------------------------------------------------------------------------
# Backtest per-symbol
# ----------------------------------------------------------------------------
def backtest_symbol(symbol, months, params1, params2, lev, cap, refresh=False, end_off=0):
    df1, df4, _ = download_all(symbol, months, refresh=refresh, end_offset_days=end_off)
    if len(df4) < 200 or len(df1) < 200:
        return [], [], None, None
    bh = (df4["close"].iloc[-1] / df4["close"].iloc[0] - 1) * 100
    df1b, t1 = strategy_mtf_trend(df1, df4, *params1)
    df4b, t2 = strategy_breakout_h4(df4, *params2)
    for t in t1: t["symbol"] = symbol
    for t in t2: t["symbol"] = symbol
    return (trade_simulator(df1b, t1, leverage=lev, cap_pct=cap),
            trade_simulator(df4b, t2, leverage=lev, cap_pct=cap), bh, df4b)


# ----------------------------------------------------------------------------
# Scan tham số nhanh trên tập khóa
# ----------------------------------------------------------------------------
def scan_params(symbols, months, lev, cap):
    """Tìm tham số tốt cho từng chiến lược trên tập khóa."""
    print("\n-- BRK Donchian55 (H4 breakout + funding) --")
    for sl, tp, trail, be, adx in [(2.0, 7.0, 4.0, 2.0, 20), (2.0, 6.0, 3.0, 2.0, 18),
                                   (1.5, 5.0, 3.0, 1.5, 20), (2.0, 8.0, 5.0, 2.5, 25)]:
        total, dds = 0, []
        for sym in symbols:
            df1, df4, _ = download_all(sym, months)
            if len(df4) < 200:
                continue
            _, t = strategy_breakout_h4(df4, sl, tp, trail, be, 55, 0.0005, adx)
            s = trade_simulator(df4, t, leverage=lev, cap_pct=cap)
            total += (s["equity"].iloc[-1] - 100) if len(s) else 0
            dds.append(s["drawdown"].max() if len(s) else 99)
        print(f"  BRK sl={sl} tp={tp} trail={trail} be={be} adx={adx}: sumPnL {total:+7.1f}%  worstDD {max(dds):5.1f}%", flush=True)
    print("\n-- Keltner (H4 breakout + funding) --")
    for mult, sl, tp, trail, be, adx in [(1.5, 2.0, 6.0, 3.5, 2.0, 18), (2.0, 2.0, 6.0, 3.5, 2.0, 18),
                                         (1.5, 2.0, 5.0, 3.0, 1.5, 15), (1.5, 1.5, 6.0, 3.0, 1.5, 18)]:
        total, dds = 0, []
        for sym in symbols:
            df1, df4, _ = download_all(sym, months)
            if len(df4) < 200:
                continue
            _, t = strategy_keltner_h4(df4, mult, sl, tp, trail, be, 0.0006, adx)
            s = trade_simulator(df4, t, leverage=lev, cap_pct=cap)
            total += (s["equity"].iloc[-1] - 100) if len(s) else 0
            dds.append(s["drawdown"].max() if len(s) else 99)
        print(f"  KELT mult={mult} sl={sl} tp={tp} trail={trail} be={be} adx={adx}: sumPnL {total:+7.1f}%  worstDD {max(dds):5.1f}%", flush=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    months = 9.0
    lev, cap = 3.0, 0.25
    end_off = 0
    skip_next = False
    clean = []
    for a in sys.argv[1:]:
        if skip_next:
            skip_next = False; continue
        if a.startswith("--"):
            skip_next = True; continue
        clean.append(a)
    if "--months" in sys.argv:
        months = float(sys.argv[sys.argv.index("--months") + 1])
    if "--lev" in sys.argv:
        lev = float(sys.argv[sys.argv.index("--lev") + 1])
    if "--endoff" in sys.argv:
        end_off = int(sys.argv[sys.argv.index("--endoff") + 1])
    symbols = clean or CORE_SYMBOLS

    if "--scan" in sys.argv:
        print(f"SCAN tham số trên {len(symbols)} symbol (months={months}, lev={lev})", flush=True)
        scan_params(symbols, months, lev, cap)
        return

    params1 = (2.0, 7.0, 4.0, 2.0, 55, 0.0005, 20)   # BRKDonchian #1
    if "--dc2" in sys.argv:
        params1 = (params1[0], params1[1], params1[2], params1[3], int(sys.argv[sys.argv.index("--dc2") + 1]), params1[5], params1[6])
    params2 = (1.5, 2.0, 6.0, 3.5, 2.0, 0.0006, 18)  # Keltner #2

    all1, all2, all3, bh_map = [], [], [], {}
    for sym in symbols:
        t0 = time.time()
        print(f"=== {sym} === ", flush=True)
        try:
            df1, df4, _ = download_all(sym, months, end_offset_days=end_off)
            if len(df4) < 200:
                raise ValueError(f"{sym} thiếu data")
            bh = (df4["close"].iloc[-1] / df4["close"].iloc[0] - 1) * 100
            bh_map[sym] = bh
            _, t1 = strategy_breakout_h4(df4, *params1)
            _, t2 = strategy_keltner_h4(df4, *params2)
            for t in t1: t["symbol"] = sym
            for t in t2: t["symbol"] = sym
            s1 = trade_simulator(df4, t1, leverage=lev, cap_pct=cap)
            s2 = trade_simulator(df4, t2, leverage=lev, cap_pct=cap)
            if len(s1): all1.append(s1)
            if len(s2): all2.append(s2)
        except Exception as e:
            print(f"  [warn] {sym} fail: {e}", flush=True)
        print(f"  ({time.time()-t0:.1f}s)", flush=True)

    for name, allsim in [("BREAKOUT_H4_DC55_FUND", all1), ("KELTNER_H4_BREAK", all2)]:
        print(f"\n{'='*78}\n{name}\n{'='*78}")
        rows = []
        for s in allsim:
            r = summarize(s, s["symbol"].iloc[0], name, benchmark_bh=bh_map.get(s["symbol"].iloc[0]))
            if not r: continue
            rows.append(r)
            bh = f"  BH {r['benchmark_bh']:+7.1f}%" if r["benchmark_bh"] is not None else ""
            print(f"  {r['symbol']:<10} PnL {r['total_return']:+8.1f}%  WR {r['winrate']:5.1f}%  "
                  f"PF {r['profit_factor']:5.2f}  DD {r['max_dd']:6.1f}%  T {r['trades']:3d}  avgBars {r['avg_bars']:5.1f}{bh}")
        if rows:
            df = pd.DataFrame(rows)
            tot = pd.DataFrame({
                "symbol": ["TOTAL"], "trades": [df.trades.sum()],
                "winrate": [df.winrate.mean()], "profit_factor": [df.profit_factor.sum()],
                "total_return": [df.total_return.sum()], "max_dd": [df.max_dd.max()],
                "benchmark_bh": [sum([x for x in df.benchmark_bh if x is not None])],
            })
            print(f"  {'TOTAL':<10} PnL {tot.total_return.iloc[0]:+8.1f}%  WR {tot.winrate.iloc[0]:5.1f}%  "
                  f"PF {tot.profit_factor.iloc[0]:5.2f}  DD {tot.max_dd.iloc[0]:6.1f}%  T {tot.trades.iloc[0]:3d}  "
                  f"BH {tot.benchmark_bh.iloc[0]:+7.1f}%")
            out = f"backtest_futures_{name}.csv"
            pd.concat([df, tot]).to_csv(out, index=False)
            print(f"  -> {out}")


if __name__ == "__main__":
    main()