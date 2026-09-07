from __future__ import annotations

import json
from pathlib import Path

from . import engine, indicators, strategies

HERE = Path(__file__).resolve().parent


def _metrics(trades: "pd.DataFrame") -> dict:
    import pandas as pd
    if not len(trades):
        return {"n": 0}
    n = len(trades)
    wins = trades[trades["r"] > 0]
    losses = trades[trades["r"] <= 0]
    wr = len(wins) / n
    avg_win = wins["r"].mean() if len(wins) else 0.0
    avg_loss = losses["r"].mean() if len(losses) else 0.0
    gross_win = trades["r"].clip(lower=0).sum()
    gross_loss = -trades["r"].clip(upper=0).sum()
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    total_r = trades["r"].sum()
    cum = trades["r"].cumsum()
    peak = cum.max()
    dd = (peak - cum).max()
    return {
        "n": int(n),
        "win_rate": round(wr, 4),
        "avg_win_r": round(avg_win, 3),
        "avg_loss_r": round(avg_loss, 3),
        "profit_factor": round(pf, 3),
        "expectancy_r": round(trades["r"].mean(), 4),
        "total_r": round(total_r, 2),
        "max_dd_r": round(dd, 2),
        "avg_bars": round(trades["bars_held"].mean(), 1) if n else 0,
        "long_share": round((trades["direction"] == 1).mean(), 3),
    }


def _equity_path(trades: "pd.DataFrame", start_equity: float = 10000, risk_pct: float = 0.01):
    """Equity compounding với risk_pct mỗi lệnh -> curve lấy từ R."""
    eq = []
    cur = start_equity
    for r in trades["r"]:
        cur = cur * (1 + risk_pct * r)
        eq.append(cur)
    return eq


def trades_summary(trades: "pd.DataFrame", symbol: str, timeframes_meta: dict) -> dict:
    m = _metrics(trades)
    m.update({"symbol": symbol, **timeframes_meta})
    return m


def bh_return(df: "pd.DataFrame") -> float:
    return indicators.last_return_of(df["close"])


def max_drawdown_pct(curve) -> float:
    peak = -1e18
    mdd = 0.0
    for v in curve:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    return mdd


def run_all(
    source: dict,
    output_dir: Path,
    start_equity: float = 10000.0,
    risk_pct: float = 0.01,
):
    import pandas as pd

    rows = []
    for symbol, bundle in source.items():
        df = bundle["df"]
        bh = bh_return(df)
        for label, tdf in bundle["trades"].items():
            if not len(tdf):
                continue
            rec = trades_summary(tdf, symbol, {"strategy": label})
            rec["bh_return"] = round(bh, 4)
            eq = _equity_path(tdf, start_equity, risk_pct)
            rec["max_dd_pct"] = round(max_drawdown_pct(eq), 4)
            rec["final_equity"] = round(eq[-1], 2)
            rows.append(rec)

    summary = pd.DataFrame(rows)
    output_dir.mkdir(exist_ok=True)
    summary.to_csv(output_dir / "summary.csv", index=False)
    return summary