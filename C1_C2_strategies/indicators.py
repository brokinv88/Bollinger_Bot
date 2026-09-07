from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def swing_points(df: pd.DataFrame, k: int = 2) -> pd.DataFrame:
    """Điểm swing (breakout pivot) trên khung cho sẵn, dùng cận trái/phải k nến."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)
    sw_hi = np.full(n, np.nan)
    sw_lo = np.full(n, np.nan)
    for i in range(k, n - k):
        window_hi = highs[i - k : i + k + 1]
        window_lo = lows[i - k : i + k + 1]
        if highs[i] == window_hi.max():
            sw_hi[i] = highs[i]
        if lows[i] == window_lo.min():
            sw_lo[i] = lows[i]
    out = pd.DataFrame({"swing_high": sw_hi, "swing_low": sw_lo}, index=df.index)
    return out


def last_return_of(s: pd.Series) -> float:
    return float(s.iloc[-1]) / float(s.iloc[0]) - 1.0