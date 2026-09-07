"""Quét thị trường Binance USD-M futures -> danh mục theo dõi cho C1/C2.

Không đưa ra lệnh mua bán; chỉ xác định các cặp đáp ứng điều kiện quan sát của
2 chiến lược thí nghiệm, kèm bối cảnh thị trường (top tăng/giảm, thanh khoản).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from . import data as data_mod
from . import indicators as ind

HERE = Path(__file__).resolve().parent
TF = "4h"
START_MS = int(pd.Timestamp("2025-09-01", tz="UTC").value // 1_000_000)
END_MS = int(time.time() * 1000)
UNIVERSE_FALLBACK = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "BNB/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
    "ADA/USDT:USDT",
    "LINK/USDT:USDT",
    "AVAX/USDT:USDT",
    "LTC/USDT:USDT",
    "XLM/USDT:USDT",
    "DOT/USDT:USDT",
    "UNI/USDT:USDT",
    "AAVE/USDT:USDT",
    "NEAR/USDT:USDT",
    "SUI/USDT:USDT",
    "TAO/USDT:USDT",
    "INJ/USDT:USDT",
    "SEI/USDT:USDT",
    "TIA/USDT:USDT",
]


def _expand(symbol: str) -> str:
    return symbol


def market_context() -> pd.DataFrame:
    """Snapshot ticker: top gainers/losers + top quoteVolume."""
    ex = data_mod._client()
    tickers = ex.fetch_tickers()
    rows = []
    for s, t in tickers.items():
        if not s.endswith("/USDT:USDT"):
            continue
        last = t.get("last")
        pct = t.get("percentage")
        qv = t.get("quoteVolume")
        if last is None or pct is None or qv is None:
            continue
        rows.append({"symbol": s, "price": last, "chg_24h_pct": pct, "qvol_24h": qv})
    df = pd.DataFrame(rows)
    return df


def scan_universe(df_price: pd.DataFrame) -> pd.DataFrame:
    """Tính trạng thái quan sát của từng cặp cho C1 (BOS tiềm năng) và C2 (level để sweep)."""
    rows = []
    for _, t in df_price.iterrows():
        sym = t["symbol"]
        try:
            ohlcv = data_mod.fetch_ohlcv(sym, TF, START_MS, END_MS)
        except Exception as e:  # noqa: BLE001
            print(f"  skip {sym}: {e}", file=sys.stderr)
            continue
        close = ohlcv["close"]
        last = float(close.iloc[-1])
        ema_f = ind.ema(close, 50).iloc[-1]
        ema_s = ind.ema(close, 200).iloc[-1]
        a = float(ind.atr(ohlcv, 14).iloc[-1])
        sw = ind.swing_points(ohlcv, k=2)
        prev_hi = sw["swing_high"].dropna()
        prev_lo = sw["swing_low"].dropna()
        recent_hi = float(prev_hi.iloc[-1]) if len(prev_hi) else float("nan")
        recent_lo = float(prev_lo.iloc[-1]) if len(prev_lo) else float("nan")
        dist_hi = (last - recent_hi) / recent_hi if not pd.isna(recent_hi) else float("nan")
        dist_lo = (last - recent_lo) / recent_lo if not pd.isna(recent_lo) else float("nan")
        trend = "UP" if ema_f > ema_s else ("DOWN" if ema_f < ema_s else "FLAT")
        roc7 = float(close.iloc[-1] / close.iloc[-8] - 1) if len(close) > 8 else float("nan")
        rows.append(
            {
                "symbol": sym,
                "price": round(last, 6),
                "trend_h4": trend,
                "ema50": round(float(ema_f), 6),
                "ema200": round(float(ema_s), 6),
                "atr_pct": round(a / last * 100, 3),
                "dist_to_swing_high_pct": round(dist_hi * 100, 3),
                "dist_to_swing_low_pct": round(dist_lo * 100, 3),
                "roc7_pct": round(roc7 * 100, 2),
"c1_watch": 1.0 if (trend in ("UP", "DOWN") and (abs(dist_hi) < 0.01 or abs(dist_lo) < 0.01)) else 0.0,
        "c2_watch": 1.0 if abs(dist_hi) < 0.0075 or abs(dist_lo) < 0.0075 else 0.0,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    ctx = market_context()
    gainers = ctx.sort_values("chg_24h_pct", ascending=False).head(10)
    losers = ctx.sort_values("chg_24h_pct").head(10)
    by_vol = ctx.sort_values("qvol_24h", ascending=False).head(20)

    out_dir = HERE / "reports"
    out_dir.mkdir(exist_ok=True)

    gainers.to_csv(out_dir / "watchlist_market_context_gainers_losers.csv", index=False)
    by_vol.to_csv(out_dir / "watchlist_top_volume.csv", index=False)

    watch = scan_universe(by_vol[["symbol"]].assign(price=by_vol["price"]))
    watch.to_csv(out_dir / "watchlist_strategy_state.csv", index=False)

    print("=== TOP TANG 24H ===")
    print(gainers[["symbol", "price", "chg_24h_pct", "qvol_24h"]].to_string(index=False))
    print("\n=== TOP GIAM 24H ===")
    print(losers[["symbol", "price", "chg_24h_pct", "qvol_24h"]].to_string(index=False))
    print("\n=== TRANG THAI STRATEGY (top 20 volume) ===")
    print(watch.to_string(index=False))


if __name__ == "__main__":
    main()