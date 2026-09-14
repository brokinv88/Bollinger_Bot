"""Screen toàn bộ danh mục Binance USD-M futures để chọn coin phù hợp chiến lược breakout H4.

Tiêu chí lọc:
  - Contract PERPETUAL, quote USDT, status TRADING.
  - Thanh khoản: quoteVolume 24h >= $20M (đủ để vào/ra không trượt quá lắm).
  - Tuổi: có >= 60 nến H4 (10 ngày) để tính chỉ báo ổn định.
  - ATR14 (H4) trung bình nằm trong 0.5%..6% — đủ biến động để breakout có sóng
    nhưng không quá cuồng (tránh coin rác / sắp niêm yết pump).
  - Exclude các symbol ký hiệu lạ (chứa ký tự không phải chữ-số như 牛来).
"""
import requests
import pandas as pd
import numpy as np
import time
from research_futures_framework import fetch_klines, add_indicators

HEADERS = {"User-Agent": "Mozilla/5.0"}
FAPI = "https://fapi.binance.com"

KNOWN = {"BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","LINKUSDT"}


def get_universe():
    r = requests.get(f"{FAPI}/fapi/v1/exchangeInfo", headers=HEADERS, timeout=15)
    info = r.json()
    perps = [s["symbol"] for s in info["symbols"]
             if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"
             and s.get("status") == "TRADING" and s["symbol"].isascii() and s["symbol"].isalnum()]
    r2 = requests.get(f"{FAPI}/fapi/v1/ticker/24hr", headers=HEADERS, timeout=15)
    tick = {t["symbol"]: dict(quote_vol=float(t["quoteVolume"]), chg=float(t.get("priceChangePercent", 0) or 0)) for t in r2.json()}
    return perps, tick


def stats_symbol(symbol):
    """Tải 60 nến H4 gần nhất, tính ATR% TB và biến động."""
    end = int(pd.Timestamp.now("UTC").timestamp() * 1000)
    start = end - 45 * 24 * 3600 * 1000  # 45 ngày
    df = fetch_klines(symbol, "4h", start, end)
    if len(df) < 60:
        return None
    df = add_indicators(df)
    atr_pct = df["atr_pct"].dropna()
    return dict(
        atr_pct_avg=float(atr_pct.mean()),
        atr_pct_p90=float(atr_pct.quantile(0.9)),
        vol_avg=float(df["volume"].mean()),
        n_bars=len(df),
        last=float(df["close"].iloc[-1]),
        first=float(df["close"].iloc[0]),
        ret_45d=(float(df["close"].iloc[-1]) / float(df["close"].iloc[3]) - 1) * 100,
    )


def main():
    print("Lấy danh mục...", flush=True)
    perps, tick = get_universe()
    print(f"Tổng USDT perpetual: {len(perps)}", flush=True)

    liq = [(s, tick.get(s, {}).get("quote_vol", 0)) for s in perps]
    liq.sort(key=lambda x: -x[1])
    keep = [s for s, v in liq if v >= 20e6][:60]  # top thanh khoản thực
    print(f"Pass thanh khoản >= $20M/24h: {len(keep)}", flush=True)

    rows = []
    for s in keep:
        try:
            st = stats_symbol(s)
            if st is None:
                continue
            st["symbol"] = s
            st["vol24h"] = tick.get(s, {}).get("quote_vol", 0)
            st["chg24h"] = tick.get(s, {}).get("chg", 0)
            rows.append(st)
        except Exception as e:
            print(f"  skip {s}: {e}", flush=True)
        time.sleep(0.1)

    df = pd.DataFrame(rows)
    if len(df) == 0:
        print("Không có dữ liệu hợp lệ.")
        return
    df = df.sort_values("vol24h", ascending=False).reset_index(drop=True)

    # Phân tầng ATR
    def tier(r):
        a = r["atr_pct_avg"]
        if a < 0.5: return "QUÁ NHỎ (bỏ)"
        if a < 1.2: return "T1 - ổn định"
        if a < 2.5: return "T2 - cân bằng"
        if a < 4.0: return "T3 - biến động mạnh"
        if a < 6.0: return "T4 - rất mạnh (size nhỏ)"
        return "QUÁ MẠNH (bỏ)"
    df["tier"] = df.apply(tier, axis=1)

    df.to_csv("backtest_futures_universe.csv", index=False)
    print("\n===== Kết quả screening (top 60 theo volume) =====")
    print(df[["symbol", "tier", "atr_pct_avg", "atr_pct_p90", "vol24h", "ret_45d"]].round(3).to_string(index=False))

    print("\n===== Phân bố theo tầng =====")
    print(df["tier"].value_counts().to_string())


if __name__ == "__main__":
    main()