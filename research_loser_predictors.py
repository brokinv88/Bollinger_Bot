import requests
import pandas as pd
import numpy as np
import time

def get_top_100_symbols():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    resp = requests.get(url).json()
    usdt_pairs = []
    exclude = ['USDCUSDT', 'FDUSDUSDT', 'TUSDUSDT', 'BUSDUSDT', 'EURUSDT', 'AEURUSDT', 'DAIUSDT', 'WBTCUSDT', 'WBETHUSDT', 'USDEUSDT']
    for item in resp:
        sym = item['symbol']
        if sym.endswith('USDT') and sym not in exclude:
            quote_vol = float(item['quoteVolume'])
            usdt_pairs.append({'symbol': sym, 'volume': quote_vol})
    df = pd.DataFrame(usdt_pairs).sort_values(by='volume', ascending=False).reset_index(drop=True)
    return df.head(100)['symbol'].tolist()

def get_daily_klines(symbol, limit=1000):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if not isinstance(data, list):
            return None
        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
        return df[['datetime', 'open', 'high', 'low', 'close', 'volume']]
    except Exception:
        return None

def compute_indicators(df, symbol):
    if len(df) < 220:
        return None
    bb_len, bb_mult = 20, 1.5

    df['sma_high'] = df['high'].rolling(bb_len).mean()
    df['std_high'] = df['high'].rolling(bb_len).std()
    df['upper_band'] = df['sma_high'] + bb_mult * df['std_high']
    df['sma_low'] = df['low'].rolling(bb_len).mean()
    df['std_low'] = df['low'].rolling(bb_len).std()
    df['lower_band'] = df['sma_low'] - bb_mult * df['std_low']
    df['baseline'] = (df['upper_band'] + df['lower_band']) / 2.0

    df['sma50'] = df['close'].rolling(50).mean()
    df['sma100'] = df['close'].rolling(100).mean()
    df['sma150'] = df['close'].rolling(150).mean()
    df['sma200'] = df['close'].rolling(200).mean()

    df['bullish_4sma'] = (df['close'] > df['sma50']) & (df['close'] > df['sma100']) & \
                         (df['close'] > df['sma150']) & (df['close'] > df['sma200'])

    df['prev_close'] = df['close'].shift(1)
    df['prev_upper'] = df['upper_band'].shift(1)
    df['crossover_upper'] = (df['prev_close'] <= df['prev_upper']) & (df['close'] > df['upper_band'])

    df['prev_lower'] = df['lower_band'].shift(1)
    df['crossunder_lower'] = (df['prev_close'] >= df['prev_lower']) & (df['close'] < df['lower_band'])
    for s in [50, 100, 150, 200]:
        df[f'prev_sma{s}'] = df[f'sma{s}'].shift(1)
        df[f'crossunder_sma{s}'] = (df['prev_close'] >= df[f'prev_sma{s}']) & (df['close'] < df[f'sma{s}'])
    df['exit_signal'] = df['crossunder_lower'] | df['crossunder_sma50'] | df['crossunder_sma100'] | \
                        df['crossunder_sma150'] | df['crossunder_sma200']

    # === ADVANCED / EARLY-WARNING INDICATORS ===
    close = df['close']

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi14'] = 100 - (100 / (1 + rs))

    # RSI 7 (more sensitive)
    gain7 = delta.clip(lower=0).rolling(7).mean()
    loss7 = (-delta.clip(upper=0)).rolling(7).mean()
    rs7 = gain7 / loss7.replace(0, np.nan)
    df['rsi7'] = 100 - (100 / (1 + rs7))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']

    # ADX (trend strength)
    up = df['high'].diff()
    down = -df['low'].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([df['high'] - df['low'], (df['high'] - close.shift()).abs(), (df['low'] - close.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(14).mean() / atr14.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(14).mean() / atr14.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    df['adx14'] = dx.rolling(14).mean()
    df['plus_di'] = plus_di

    # ATR (volatility) - normalized
    df['atr14'] = atr14
    df['atr_pct'] = atr14 / close * 100.0

    # Volume: current vs 20d average (volume expansion / divergence)
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20'].replace(0, np.nan)

    # Price distance above SMA20 (extended = chase risk)
    df['sma20'] = close.rolling(20).mean()
    df['dist_sma20_pct'] = (close / df['sma20'] - 1) * 100.0
    df['dist_sma50_pct'] = (close / df['sma50'] - 1) * 100.0
    df['dist_sma200_pct'] = (close / df['sma200'] - 1) * 100.0

    # Distance above upper band (how far extended at entry)
    df['dist_upper_pct'] = (close / df['upper_band'] - 1) * 100.0

    # Rate of change / momentum
    df['roc5'] = close.pct_change(5) * 100.0
    df['roc20'] = close.pct_change(20) * 100.0

    # 20d high proximity (% below 20-day high) -- buying near highs
    df['high20'] = df['high'].rolling(20).max()
    df['pct_off_high20'] = (close / df['high20'] - 1) * 100.0

    # Distance from 52w high
    df['high250'] = df['high'].rolling(250).max()
    df['pct_off_high250'] = (close / df['high250'] - 1) * 100.0

    df['symbol'] = symbol
    return df

def run_backtest_with_features(symbols):
    commission = 0.00075
    cash_per_entry = 50.0
    max_pyramid = 3
    trades = []

    for sym in symbols:
        time.sleep(0.03)
        df = get_daily_klines(sym, limit=1000)
        if df is None:
            continue
        df = compute_indicators(df, sym)
        if df is None:
            continue

        positions = []
        entry_features = []  # features snapshot at each live entry
        filled_pyramids = []  # features + qty/cash per pyramid entered

        for i in range(201, len(df)):
            row = df.iloc[i]
            exit_now = row['exit_signal'] and len(positions) > 0

            # Grab features from the LAST live position's saved snapshot for exit-side analysis
            # (we want, per closed trade, the features recorded at its entry day)

            if exit_now:
                idx = row.name
                exit_price = row['close']
                total_qty = sum(p['qty'] for p in positions)
                total_invested = sum(p['cash'] for p in positions)
                net_val = total_qty * exit_price * (1 - commission)
                pnl = net_val - total_invested
                pnl_pct = pnl / total_invested * 100.0

                # Features AT FIRST ENTRY (most predictive for 'should I have entered')
                fe = entry_features[0]
                # Days held
                try:
                    days_held = (df.index.get_loc(row.name) - df.index.get_loc(fe['entry_idx']))
                except Exception:
                    days_held = np.nan

                # Did it lose immediately (max adverse excursion before exit)? Simulate intrabar from entry onward
                fe['sym'] = sym
                fe['pnl_pct'] = pnl_pct
                fe['pnl_usd'] = pnl
                fe['win'] = pnl > 0
                fe['entries'] = len(positions)
                fe['days_held'] = days_held
                fe['exit_reason_lower'] = bool(row['crossunder_lower'])
                fe['exit_reason_sma'] = bool(row['exit_signal']) and not bool(row['crossunder_lower'])
                fe['entry_date'] = str(df.iloc[fe['entry_idx']]['datetime'])[:10]
                fe['exit_date'] = str(row['datetime'])[:10]
                trades.append(fe)

                positions = []
                entry_features = []
                filled_pyramids = []
                continue

            if row['bullish_4sma'] and row['crossover_upper']:
                if len(positions) < max_pyramid:
                    idx = row.name
                    qty = (cash_per_entry * (1 - commission)) / row['close']
                    positions.append({'qty': qty, 'cash': cash_per_entry})
                    feat = {
                        'entry_idx': idx,
                        'close': row['close'],
                        'rsi14': row['rsi14'],
                        'rsi7': row['rsi7'],
                        'macd_hist': row['macd_hist'],
                        'adx14': row['adx14'],
                        'plus_di': row['plus_di'],
                        'atr_pct': row['atr_pct'],
                        'vol_ratio': row['vol_ratio'],
                        'dist_sma20_pct': row['dist_sma20_pct'],
                        'dist_sma50_pct': row['dist_sma50_pct'],
                        'dist_sma200_pct': row['dist_sma200_pct'],
                        'dist_upper_pct': row['dist_upper_pct'],
                        'roc5': row['roc5'],
                        'roc20': row['roc20'],
                        'pct_off_high20': row['pct_off_high20'],
                        'pct_off_high250': row['pct_off_high250'],
                    }
                    entry_features.append(feat)
                    filled_pyramids.append(feat)

    return trades

def main():
    print("Fetching symbols...")
    symbols = get_top_100_symbols()
    print(f"Backtesting {len(symbols)} symbols with feature capture...")
    trades = run_backtest_with_features(symbols)

    if not trades:
        print("No trades.")
        return

    tdf = pd.DataFrame(trades)
    tdf.to_csv('research_trades_with_features.csv', index=False)

    print(f"\nTotal trades: {len(tdf)} | Wins: {(tdf['win']).sum()} | Losses: {(~tdf['win']).sum()}")
    print(f"Overall PnL: ${tdf['pnl_usd'].sum():,.2f}")

    wins = tdf[tdf['win']]
    losses = tdf[~tdf['win']]

    feat_cols = ['rsi14','rsi7','macd_hist','adx14','plus_di','atr_pct','vol_ratio',
                 'dist_sma20_pct','dist_sma50_pct','dist_sma200_pct','dist_upper_pct',
                 'roc5','roc20','pct_off_high20','pct_off_high250']

    print("\n=== TRUNG BÌNH CHỈ BÁO TẠI LÚC VÀO LỆNH: THẮNG vs THUA ===")
    comp = pd.DataFrame({
        'Winner mean': wins[feat_cols].mean(),
        'Loser mean': losses[feat_cols].mean(),
        'Diff': losses[feat_cols].mean() - wins[feat_cols].mean(),
    })
    print(comp.round(2).to_string())

    print("\n=== PHÂN PHỐI PnL theo LOẠI CẢNH BÁO ===")
    for col, thr, direction in [
        ('rsi14', 70, 'high'),      # overbought at entry
        ('rsi14', 65, 'high'),
        ('dist_sma20_pct', 10, 'high'),  # extended >10% above sma20
        ('dist_sma20_pct', 15, 'high'),
        ('dist_upper_pct', 3, 'high'),
        ('adx14', 30, 'low'),       # weak/no trend
        ('vol_ratio', 2.0, 'high'), # volume spike (possibly blowoff)
        ('roc20', 40, 'high'),      # huge 20d momentum
        ('roc5', 20, 'high'),
        ('macd_hist', 0, 'low'),    # MACD histogram negative
        ('pct_off_high250', -5, 'high'),  # near 250d high (<5% below)
    ]:
        if direction == 'high':
            mask = tdf[col] > thr
        else:
            mask = tdf[col] < thr
        if mask.sum() == 0:
            continue
        sub = tdf[mask]
        subw = sub['win'].mean() * 100
        subpnl = sub['pnl_usd'].sum()
        rest = tdf[~mask]
        restw = rest['win'].mean() * 100
        restpnl = rest['pnl_usd'].sum()
        print(f"  {col} {direction} {thr}: n={mask.sum():3d} | WR={subw:5.1f}% PnL={subpnl:+8.2f}$ | "
              f"vs rest WR={restw:5.1f}% PnL={restpnl:+8.2f}$")

if __name__ == "__main__":
    main()
