"""Thực thi tín hiệu thành giao dịch trên dữ liệu khung entry, tính R chuẩn hóa."""

from __future__ import annotations

import numpy as np
import pandas as pd

COST_PCT = 0.0007  # taker 0.05% + slippage 0.02%


def _funding_cost(direction: int, bars_held: int, funding_per_8h: float, bar_hours: float) -> float:
    if funding_per_8h == 0.0:
        return 0.0
    periods = (bars_held - 1) * bar_hours / 8.0  # cầm qua các chu kỳ funding
    return -direction * funding_per_8h * periods  # long trả funding dương, short nhận


def _fill(data: pd.DataFrame, sig: pd.Series) -> dict:
    """Khớp một tín hiệu trên dữ liệu. Trả về trade record hoặc None nếu entry hết dữ liệu."""
    t0 = sig["entry_time"]
    idx_pos = data.index.get_indexer([t0], method="pad")
    start = int(idx_pos[0])
    if start < 0 or start >= len(data):
        return None
    if sig["entry_time"] > data.index[-1]:
        return None
    entry = float(data["open"].iloc[start])
    direction = int(sig["direction"])
    stop = float(sig["stop"])
    target = float(sig["target"])
    max_bars = int(sig["time_stop_bars"])
    risk_price = abs(entry - stop)
    if risk_price <= 0:
        return None

    trades = []
    end = min(len(data) - 1, start + max_bars)
    exit_price = None
    reason = "TIMEOUT"
    exit_t = data.index[start]
    for j in range(start, end + 1):
        hi = float(data["high"].iloc[j])
        lo = float(data["low"].iloc[j])
        cl = float(data["close"].iloc[j])
        if direction == 1:
            if lo <= stop:
                exit_price, reason, exit_t = stop, "SL", data.index[j]
                break
            if hi >= target:
                exit_price, reason, exit_t = target, "TP", data.index[j]
                break
        else:
            if hi >= stop:
                exit_price, reason, exit_t = stop, "SL", data.index[j]
                break
            if lo <= target:
                exit_price, reason, exit_t = target, "TP", data.index[j]
                break
        exit_price, exit_t = cl, data.index[j]
    if exit_price is None:
        return None

    gross = direction * (exit_price - entry) / entry
    funding = _funding_cost(direction, int(end - start + 1), float(sig.get("funding_per_8h", 0.0)), float(sig.get("bar_hours", 4.0)))
    net = gross - COST_PCT * 2.0 + funding
    r_mult = net / (risk_price / entry)
    sw = sig.get("swept")
    swept = False if (sw is np.nan or pd.isna(sw)) else bool(sw)
    return {
        "symbol": sig.get("symbol", ""),
        "signal_time": sig["signal_time"],
        "entry_time": data.index[start],
        "exit_time": exit_t,
        "direction": direction,
        "entry": entry,
        "exit": float(exit_price),
        "stop": stop,
        "target": target,
        "reason": reason,
        "bars_held": int(end - start + 1),
        "r": r_mult,
        "swept": swept,
        "atr": float(sig.get("atr", np.nan)),
        "level": float(sig.get("level", np.nan)),
    }


def run_backtest(data: pd.DataFrame, signals: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
    """Chạy toàn bộ tín hiệu đã có entry_time trên dữ liệu. Trả về DataFrame trade."""
    if not len(signals):
        return pd.DataFrame()
    recs = []
    for _, sig in signals.iterrows():
        s = sig.copy()
        s["symbol"] = symbol
        r = _fill(data, s)
        if r is not None:
            recs.append(r)
    df = pd.DataFrame(recs)
    if len(df):
        df = df.sort_values("entry_time").reset_index(drop=True)
    return df