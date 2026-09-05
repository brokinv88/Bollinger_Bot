"""Backtest framework cho Binance USD-M Futures trên khung H1/H4.

- Fetch klines futures (fapi), funding rate, open interest.
- Mô phỏng: phí taker, funding mỗi 8h, long + short, leverage cố định.
- Benchmark: Buy & Hold.
"""
import requests
import pandas as pd
import numpy as np
import time
import sys

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
FAPI = "https://fapi.binance.com"

# Phí futures Binance (USDT-M): taker 0.05%, maker 0.02% (mặc định không BNB)
TAKER_FEE = 0.0005
MAKER_FEE = 0.0002
# Funding rate lấy thật từ API, tính vào PnL mỗi 8h theo vị thế
CORE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT"]


def fetch_klines(symbol, interval, start_ms, end_ms, limit=1500):
    """Fetch klines futures với phân trang."""
    all_rows = []
    cur = start_ms
    while cur < end_ms:
        url = f"{FAPI}/fapi/v1/klines"
        params = {"symbol": symbol, "interval": interval, "startTime": cur,
                  "endTime": end_ms, "limit": limit}
        for attempt in range(4):
            try:
                r = requests.get(url, params=params, headers=HEADERS, timeout=15)
                if r.status_code == 429:
                    time.sleep(2); continue
                data = r.json()
                break
            except Exception:
                time.sleep(1.5)
        else:
            print(f"  [warn] không lấy được klines {symbol} {interval}", flush=True)
            break
        if not isinstance(data, list) or len(data) == 0:
            if isinstance(data, dict) and ("code" in data or "msg" in data):
                print(f"  [warn] {symbol} {interval} API error: {data.get('code')} {data.get('msg')} "
                      f"(HTTP {r.status_code})", flush=True)
            else:
                print(f"  [warn] {symbol} {interval} không phải list (HTTP {r.status_code}, "
                      f"type {type(data).__name__}, len {len(data) if hasattr(data, '__len__') else '?'})", flush=True)
            break
        all_rows.extend(data)
        last_open = data[-1][0]
        if last_open <= cur:
            break
        cur = last_open + 1
        time.sleep(0.15)
    if not all_rows:
        return pd.DataFrame()
    df = pd.DataFrame(all_rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_base", "taker_quote", "ignore"])
    df = df[["open_time", "open", "high", "low", "close", "volume", "quote_vol", "close_time"]].astype(float)
    df["open_time"] = df["open_time"].astype(np.int64)
    df["close_time"] = df["close_time"].astype(np.int64)
    df = df.drop_duplicates(subset="open_time").sort_values("open_time").reset_index(drop=True)
    return df


def fetch_funding(symbol, start_ms, end_ms, limit=1000):
    """Fetch lịch sử funding rate (mỗi 8h)."""
    rows = []
    cur = start_ms
    while cur < end_ms:
        url = f"{FAPI}/fapi/v1/fundingRate"
        params = {"symbol": symbol, "startTime": cur, "endTime": end_ms, "limit": limit}
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=15)
            data = r.json()
        except Exception:
            time.sleep(1); data = []
        if not isinstance(data, list) or len(data) == 0:
            break
        rows.extend(data)
        last = data[-1]["fundingTime"]
        if last <= cur:
            break
        cur = last + 1
        time.sleep(0.15)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["fundingTime"] = df["fundingTime"].astype(np.int64)
    df["fundingRate"] = df["fundingRate"].astype(float)
    return df[["fundingTime", "fundingRate"]].drop_duplicates(subset="fundingTime").sort_values("fundingTime")


def add_indicators(df, atr_len=14):
    """Thêm ATR, EMA/SMA, RSI, Donchian, ADX."""
    df = df.copy()
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(atr_len).mean()
    df["atr_pct"] = df["atr"] / close * 100.0
    # EMA
    df["ema20"] = close.ewm(span=20, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()
    df["ema200"] = close.ewm(span=200, adjust=False).mean()
    df["sma20"] = close.rolling(20).mean()
    df["sma50"] = close.rolling(50).mean()
    df["sma100"] = close.rolling(100).mean()
    # Donchian
    df["dc_high20"] = high.rolling(20).max().shift(1)
    df["dc_low20"] = low.rolling(20).min().shift(1)
    df["dc_high55"] = high.rolling(55).max().shift(1)
    df["dc_low55"] = low.rolling(55).min().shift(1)
    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi14"] = 100 - 100 / (1 + rs)
    # ADX
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    trn = tr.ewm(alpha=1/atr_len, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1/atr_len, adjust=False).mean() / trn
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1/atr_len, adjust=False).mean() / trn
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df["adx14"] = dx.ewm(alpha=1/atr_len, adjust=False).mean()
    return df


def merge_funding(df, funding_df, uptime_col="open_time"):
    """Gán funding rate gần nhất cho từng nến (theo thời điểm nến mở)."""
    if funding_df is None or len(funding_df) == 0:
        df["funding_rate"] = 0.0
        return df
    f = funding_df.rename(columns={"fundingTime": "ft", "fundingRate": "fr"})
    f["ft"] = f["ft"].astype(np.int64)
    df = df.sort_values(uptime_col).reset_index(drop=True)
    merged = pd.merge_asof(df, f, left_on=uptime_col, right_on="ft", direction="backward")
    df["funding_rate"] = merged["fr"].fillna(0.0)
    return df


def trade_simulator(df, trades, leverage=2.0, cap_pct=1.0, fee=TAKER_FEE):
    """Chạy mô phỏng equity từ danh sách lệnh.

    Mỗi lệnh: dict(direction in {-1,1}, entry_idx, exit_idx, entry, exit...)
    - full margin: notional = equity * cap_pct * leverage (fixed fractional, 1 vị thế tại 1 thời điểm)
    - phí: taker vào + taker ra (2*cap_pct*equity*fee)
    - funding: tính theo notional mỗi 8h (nếu có funding rate trên nến)
    """
    rows = []
    for t in trades:
        direction = t["direction"]
        entry = t["entry"]
        exit_px = t["exit"]
        hold_len = max(1, t["exit_idx"] - t["entry_idx"])
        gross = direction * (exit_px - entry) / entry
        # funding: Binance trừ mỗi 8h (00/08/16 UTC); chỉ tính ở nến mở đúng móc 8h
        held = df.iloc[t["entry_idx"]:t["exit_idx"] + 1]
        if len(held):
            open_ts = held["open_time"].to_numpy()
            frs = df["funding_rate"].iloc[t["entry_idx"]:t["exit_idx"] + 1].to_numpy()
            is_funding_ts = (open_ts % (8 * 3600 * 1000)) == 0
            fund_cost = -direction * np.sum(frs[is_funding_ts])
        else:
            fund_cost = 0.0
        net = gross - 2 * fee + fund_cost
        rows.append({
            "symbol": t.get("symbol", "?"), "direction": direction,
            "entry_time": df["open_time"].iloc[t["entry_idx"]],
            "exit_time": df["open_time"].iloc[t["exit_idx"]],
            "entry": entry, "exit": exit_px, "bars": hold_len,
            "gross_pct": gross * 100, "funding_pct": fund_cost * 100,
            "net_pct": net * 100, "reason": t.get("reason", ""),
        })
    tr = pd.DataFrame(rows)
    if len(tr) == 0:
        return tr
    # equity theo chiến lược: 1 lệnh tại 1 thời điểm/symbol. Dùng cap_pct vốn mỗi lệnh.
    lump = cap_pct * leverage
    tr["ret"] = np.clip((tr["net_pct"] / 100.0) * lump, -lump, None)
    tr["equity"] = 100.0 * (1 + tr["ret"]).cumprod()
    tr["equity"] = tr["equity"].clip(lower=0.001)
    tr["drawdown"] = tr["equity"].cummax() - tr["equity"]
    tr["win"] = tr["ret"] > 0
    return tr


def summarize(trades_df, symbol, strategy_name, benchmark_bh=None):
    """Tổng hợp metrics."""
    if len(trades_df) == 0:
        return None
    n = len(trades_df)
    wins = trades_df[trades_df["win"]]
    losses = trades_df[~trades_df["win"]]
    wr = len(wins) / n * 100
    gp = wins["ret"].sum() * 100
    gl = abs(losses["ret"].sum() * 100)
    pf = gp / gl if gl > 0 else 99.0
    avg_win = wins["ret"].mean() * 100 if len(wins) > 0 else 0
    avg_loss = losses["ret"].mean() * 100 if len(losses) > 0 else 0
    total_ret = trades_df["equity"].iloc[-1] - 100
    max_dd = trades_df["drawdown"].max()
    # Sharpe (hàng ngày, từ equity chuỗi - xấp xỉ mỗi nến)
    eq = trades_df["equity"]
    rets = eq.pct_change().dropna()
    sharpe = (rets.mean() / rets.std() * np.sqrt(365 * 24 / 1)) if rets.std() > 0 and len(rets) > 1 else 0.0
    bh_ret = benchmark_bh if benchmark_bh is not None else None
    return {
        "strategy": strategy_name, "symbol": symbol, "trades": n,
        "winrate": wr, "profit_factor": pf, "total_return": total_ret,
        "max_dd": max_dd, "avg_win": avg_win, "avg_loss": avg_loss,
        "payoff": avg_win / abs(avg_loss) if avg_loss != 0 else 0,
        "sharpe_approx": sharpe,
        "avg_bars": trades_df["bars"].mean(),
        "benchmark_bh": bh_ret,
    }