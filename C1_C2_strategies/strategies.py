"""Sinh tín hiệu cho 2 chiến lược thí nghiệm (spec: Tamly/spec-C1-C2.md).

C1 — phá vỡ cấu trúc thuận xu hướng HTF (trend-following, BOS).
C2 — quét thanh khoản rồi đảo chiều tại vùng cũ (sweep + CHoCH),
     kèm nhóm nền "touch + CHoCH" để tách giá trị thêm của bộ lọc sweep (S05).
"""

from __future__ import annotations

import pandas as pd

from . import indicators as ind


def _structure_hl(data: pd.DataFrame, k: int) -> pd.DataFrame:
    sw = ind.swing_points(data, k=k)
    sw["prev_swing_high"] = sw["swing_high"].ffill()
    sw["prev_swing_low"] = sw["swing_low"].ffill()
    return sw


def gen_c1(
    data: pd.DataFrame,
    trend_span_fast: int = 50,
    trend_span_slow: int = 200,
    atr_period: int = 14,
    k: int = 2,
    rr: float = 2.0,
    time_stop_bars: int = 20,
    fresh_close_window: int = 0,
) -> pd.DataFrame:
    """C1: vào theo phá vỡ swing cùng hướng trend EMA50/200 trên chính khung.

    fresh_close_window>0 (ex-ante): thêm điều kiện "close tạo cấu trúc mới rõ" —
    close hiện tại phải là mức đóng cửa cao/thấp nhất trong window nến gần nhất
    (kể cả nến hiện tại). Lọc bỏ các nến breakout "yếu" tái chạm level cũ
    (dành cho bài toán giảm nhiễu LTC, một biến duy nhất mỗi vòng — T05).

    Trả về DataFrame tín hiệu: entry index, hướng, giá vào, stop, target, thời gian dừng.
    """
    sw = _structure_hl(data, k)
    fast = ind.ema(data["close"], trend_span_fast)
    slow = ind.ema(data["close"], trend_span_slow)
    a = ind.atr(data, atr_period)
    roll_high = data["close"].rolling(fresh_close_window, min_periods=fresh_close_window).max() if fresh_close_window else None
    roll_low = data["close"].rolling(fresh_close_window, min_periods=fresh_close_window).min() if fresh_close_window else None

    rows = []
    closes = data["close"].to_numpy()
    highs = data["high"].to_numpy()
    signal_prev_high = sw["prev_swing_high"].to_numpy()
    signal_prev_low = sw["prev_swing_low"].to_numpy()
    a_np = a.to_numpy()
    fast_np = fast.to_numpy()
    slow_np = slow.to_numpy()
    rhi = roll_high.to_numpy() if roll_high is not None else None
    rlo = roll_low.to_numpy() if roll_low is not None else None

    n = len(data)
    for i in range(1, n - 1):
        entry = closes[i]
        if pd.isna(entry) or pd.isna(a_np[i]) or pd.isna(fast_np[i]) or pd.isna(slow_np[i]):
            continue
        direction = None
        if fast_np[i] > slow_np[i] and not pd.isna(signal_prev_high[i]):
            if closes[i] > signal_prev_high[i]:
                if rhi is not None and not (pd.isna(rhi[i]) or closes[i] >= rhi[i]):
                    continue  # chưa tạo close mới rõ ràng
                direction = 1
                stop = entry - 2.0 * a_np[i]
                level = signal_prev_high[i]
        elif fast_np[i] < slow_np[i] and not pd.isna(signal_prev_low[i]):
            if closes[i] < signal_prev_low[i]:
                if rlo is not None and not (pd.isna(rlo[i]) or closes[i] <= rlo[i]):
                    continue  # chưa tạo close mới rõ ràng
                direction = -1
                stop = entry + 2.0 * a_np[i]
                level = signal_prev_low[i]
        if direction is None:
            continue
        if direction == 1:
            target = entry + rr * (entry - stop)
        else:
            target = entry - rr * (stop - entry)
        rows.append(
            {
                "signal_time": data.index[i],
                "entry_time": data.index[i + 1],
                "direction": direction,
                "level": float(level),
                "entry": entry,
                "stop": float(stop),
                "target": float(target),
                "time_stop_bars": time_stop_bars,
                "atr": float(a_np[i]),
            }
        )
    cols = ["signal_time", "entry_time", "direction", "level", "entry", "stop", "target", "time_stop_bars", "atr"]
    df = pd.DataFrame(rows, columns=cols)
    if len(df):
        df["entry_price"] = df["entry"]  # khớp tại open nến entry_time; set trong engine
    return df


def _levels(data: pd.DataFrame, lookback: int, k: int) -> pd.DataFrame:
    """Các mức hỗ trợ/kháng cự = swing high/low đã xác nhận, hợp lệ trong `lookback` nến."""
    sw = ind.swing_points(data, k)
    n = len(data)
    hi = sw["swing_high"].to_numpy()
    lo = sw["swing_low"].to_numpy()
    out_hi = pd.Series(index=data.index, dtype=float)
    out_lo = pd.Series(index=data.index, dtype=float)
    for i in range(n):
        w = slice(max(0, i - lookback), i + 1)
        out_hi.iloc[i] = hi[w][~pd.isna(hi[w])].max() if (~pd.isna(hi[w])).any() else float("nan")
        out_lo.iloc[i] = lo[w][~pd.isna(lo[w])].min() if (~pd.isna(lo[w])).any() else float("nan")
    return pd.DataFrame({"level_high": out_hi, "level_low": out_lo}, index=data.index)


def gen_c2(
    data: pd.DataFrame,
    lookback: int = 24,
    k: int = 3,
    atr_period: int = 14,
    rr: float = 2.0,
    sweep_band_atr: float = 0.0,
    touch_band_atr: float = 0.5,
    time_stop_bars: int = 12,
    require_sweep: bool = True,
) -> pd.DataFrame:
    """C2 long/short tại vùng cũ (cùng khung).

    - require_sweep=True : bộ lọc SMC — giá quét xuyên mức (sweep) rồi đóng trở lại.
    - require_sweep=False: nhóm nền — chạm vùng (trong touch_band×ATR) rồi đóng trở lại,
      không yêu cầu quét. Dùng để tách giá trị thêm của sweep (S05).
    """
    lv = _levels(data, lookback, k)
    a = ind.atr(data, atr_period)
    n = len(data)
    lv_hi = lv["level_high"].to_numpy()
    lv_lo = lv["level_low"].to_numpy()
    a_np = a.to_numpy()
    hi_np = data["high"].to_numpy()
    lo_np = data["low"].to_numpy()
    cl_np = data["close"].to_numpy()

    rows = []
    for i in range(1, n - 1):
        if pd.isna(a_np[i]) or pd.isna(lv_hi[i]) or pd.isna(lv_lo[i]):
            continue
        # SIGNAL tại đóng nến i, vào nến i+1
        # LONG
        level = lv_lo[i]
        sweep = lo_np[i] < level - sweep_band_atr * a_np[i]
        touch = lo_np[i] <= level + touch_band_atr * a_np[i]
        confirm = cl_np[i] > level
        if (sweep if require_sweep else touch) and confirm:
            entry = cl_np[i]
            stop = entry - 2.0 * a_np[i]
            target = entry + rr * (entry - stop)
            rows.append(
                {
                    "signal_time": data.index[i],
                    "entry_time": data.index[i + 1],
                    "direction": 1,
                    "level": float(level),
                    "entry": entry,
                    "stop": float(stop),
                    "target": float(target),
                    "time_stop_bars": time_stop_bars,
                    "atr": float(a_np[i]),
                    "swept": bool(sweep),
                }
            )
        # SHORT
        level = lv_hi[i]
        sweep = hi_np[i] > level + sweep_band_atr * a_np[i]
        touch = hi_np[i] >= level - touch_band_atr * a_np[i]
        confirm = cl_np[i] < level
        if (sweep if require_sweep else touch) and confirm:
            entry = cl_np[i]
            stop = entry + 2.0 * a_np[i]
            target = entry - rr * (stop - entry)
            rows.append(
                {
                    "signal_time": data.index[i],
                    "entry_time": data.index[i + 1],
                    "direction": -1,
                    "level": float(level),
                    "entry": entry,
                    "stop": float(stop),
                    "target": float(target),
                    "time_stop_bars": time_stop_bars,
                    "atr": float(a_np[i]),
                    "swept": bool(sweep),
                }
            )
    cols = ["signal_time", "entry_time", "direction", "level", "entry", "stop", "target", "time_stop_bars", "atr", "swept"]
    df = pd.DataFrame(rows, columns=cols)
    if len(df):
        df["entry_price"] = df["entry"]
    return df

def gen_c2_mtf(
    h1: pd.DataFrame,
    h4_levels: pd.DataFrame,
    atr_period: int = 14,
    rr: float = 2.0,
    sweep_band_atr: float = 0.0,
    touch_band_atr: float = 0.5,
    time_stop_bars: int = 24,
    require_sweep: bool = True,
) -> pd.DataFrame:
    """C2 đa khung: level lấy từ H4 (swing đã xác nhận), tín hiệu sweep/CHoCH trên H1.

    - Level hợp lệ là swing H4 trong lookback; vẽ lên từng nến H1 (ffill).
    - require_sweep=True : H1 quét xuyên level rồi đóng lại → bộ lọc SMC.
    - require_sweep=False: H1 chạm trong touch_band×ATR rồi đóng lại → nhóm nền.
    Khớp đúng nội dung "quét thanh khoản vùng cũ" trong khái niệm SMC.
    """
    lv_hi = h4_levels["level_high"].reindex(h1.index, method="ffill").to_numpy()
    lv_lo = h4_levels["level_low"].reindex(h1.index, method="ffill").to_numpy()
    a = ind.atr(h1, atr_period)
    n = len(h1)
    hi_np = h1["high"].to_numpy()
    lo_np = h1["low"].to_numpy()
    cl_np = h1["close"].to_numpy()
    a_np = a.to_numpy()

    rows = []
    for i in range(1, n - 1):
        if pd.isna(a_np[i]) or pd.isna(lv_hi[i]) or pd.isna(lv_lo[i]):
            continue
        # LONG tại level_low H4
        level = lv_lo[i]
        sweep = lo_np[i] < level - sweep_band_atr * a_np[i]
        touch = lo_np[i] <= level + touch_band_atr * a_np[i]
        confirm = cl_np[i] > level
        if (sweep if require_sweep else touch) and confirm:
            entry = cl_np[i]
            stop = entry - 2.0 * a_np[i]
            target = entry + rr * (entry - stop)
            rows.append(
                {
                    "signal_time": h1.index[i],
                    "entry_time": h1.index[i + 1],
                    "direction": 1,
                    "level": float(level),
                    "entry": entry,
                    "stop": float(stop),
                    "target": float(target),
                    "time_stop_bars": time_stop_bars,
                    "atr": float(a_np[i]),
                    "swept": bool(sweep),
                }
            )
        # SHORT tại level_high H4
        level = lv_hi[i]
        sweep = hi_np[i] > level + sweep_band_atr * a_np[i]
        touch = hi_np[i] >= level - touch_band_atr * a_np[i]
        confirm = cl_np[i] < level
        if (sweep if require_sweep else touch) and confirm:
            entry = cl_np[i]
            stop = entry + 2.0 * a_np[i]
            target = entry - rr * (stop - entry)
            rows.append(
                {
                    "signal_time": h1.index[i],
                    "entry_time": h1.index[i + 1],
                    "direction": -1,
                    "level": float(level),
                    "entry": entry,
                    "stop": float(stop),
                    "target": float(target),
                    "time_stop_bars": time_stop_bars,
                    "atr": float(a_np[i]),
                    "swept": bool(sweep),
                }
            )
    cols = ["signal_time", "entry_time", "direction", "level", "entry", "stop", "target", "time_stop_bars", "atr", "swept"]
    df = pd.DataFrame(rows, columns=cols)
    if len(df):
        df["entry_price"] = df["entry"]
    return df
