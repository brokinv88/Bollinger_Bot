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

    df['sma20'] = df['close'].rolling(20).mean()
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

    # Advanced indicators
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi14'] = 100 - (100 / (1 + rs))

    df['roc5'] = df['close'].pct_change(5) * 100.0
    df['roc20'] = df['close'].pct_change(20) * 100.0
    df['dist_sma20_pct'] = (df['close'] / df['sma20'] - 1) * 100.0
    df['dist_upper_pct'] = (df['close'] / df['upper_band'] - 1) * 100.0

    up = df['high'].diff()
    down = -df['low'].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([df['high'] - df['low'], (df['high'] - df['close'].shift()).abs(), (df['low'] - df['close'].shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    df['atr14'] = atr14
    df['atr_pct'] = atr14 / df['close'] * 100.0

    df['symbol'] = symbol
    return df

class SimConfig:
    def __init__(self, name, max_roc5=None, max_roc20=None, max_dsma20=None,
                 max_atr_pct=None, time_stop_days=None, hard_stop_atr=None):
        self.name = name
        self.max_roc5 = max_roc5
        self.max_roc20 = max_roc20
        self.max_dsma20 = max_dsma20
        self.max_atr_pct = max_atr_pct
        self.time_stop_days = time_stop_days
        self.hard_stop_atr = hard_stop_atr

def simulate(symbols_data, cfg, max_open_coins=10, cash_per_entry=50.0, max_pyramid=3, commission=0.00075):
    all_dates = set()
    for sym, df in symbols_data.items():
        all_dates.update(df['datetime'].tolist())
    sorted_dates = sorted(list(all_dates))
    date_pos = {dt: i for i, dt in enumerate(sorted_dates)}

    data_by_date = {dt: {} for dt in sorted_dates}
    for sym, df in symbols_data.items():
        dfi = df.set_index('datetime')
        for dt, row in dfi.iterrows():
            if dt in data_by_date:
                data_by_date[dt][sym] = row

    # position: symbol -> list of {qty, entry_price, cash, entry_idx}
    open_positions = {}
    completed = []
    daily = []

    for i, dt in enumerate(sorted_dates):
        current_rows = data_by_date[dt]

        # EXITS
        for sym in list(open_positions.keys()):
            if sym not in current_rows:
                continue
            row = current_rows[sym]
            pos_list = open_positions[sym]
            exit_price = row['close']
            avg_entry = sum(p['entry_price'] for p in pos_list) / len(pos_list)
            # entry index for the position (first entry)
            entry_idx = pos_list[0]['entry_idx']
            days_held = i - entry_idx
            pnl_so_far = (exit_price - avg_entry) / avg_entry * 100.0
            # Detect bar high/low for stops (conservative: use high/low of day)
            day_high = row['high']; day_low = row['low']

            exit_now = False
            reason = None

            # Hard stop: price falls below avg_entry * (1 - atr_stop)
            if cfg.hard_stop_atr:
                stop_price = avg_entry - cfg.hard_stop_atr * row['atr14']
                if day_low <= stop_price:
                    exit_now = True
                    reason = f"HardStop ATRx{cfg.hard_stop_atr}"
                    exit_price = stop_price

            # Time stop: underwater after N days
            if cfg.time_stop_days and (not exit_now) and days_held >= cfg.time_stop_days and pnl_so_far < 0:
                exit_now = True
                reason = f"TimeStop {cfg.time_stop_days}d underwater"
                exit_price = row['close']

            # Signal exit
            if (not exit_now) and row['exit_signal']:
                exit_now = True
                reason = "SMA/Lower"
                exit_price = row['close']

            if exit_now:
                total_qty = sum(p['qty'] for p in pos_list)
                total_invested = sum(p['cash'] for p in pos_list)
                net_val = total_qty * min(exit_price, max(day_high, exit_price)) * (1 - commission) if False else total_qty * exit_price * (1 - commission)
                net_val = total_qty * exit_price * (1 - commission)
                pnl = net_val - total_invested
                completed.append({'symbol': sym, 'pnl_usd': pnl, 'win': pnl > 0,
                                  'pnl_pct': pnl/total_invested*100, 'days_held': days_held,
                                  'reason': reason, 'entries': len(pos_list)})
                del open_positions[sym]

        # ENTRIES
        candidates = []
        entry_col = 'entry_signal' if 'entry_signal' in symbols_data or True else None
        for sym, row in current_rows.items():
            if sym in open_positions:
                if len(open_positions[sym]) < max_pyramid and row['crossover_upper']:
                    entry_price = row['close']
                    qty = (cash_per_entry * (1-commission)) / entry_price
                    open_positions[sym].append({'qty': qty, 'entry_price': entry_price,
                                                'cash': cash_per_entry, 'entry_idx': i})
            else:
                if row['crossover_upper'] and row['bullish_4sma']:
                    # ENTRY FILTERS
                    ok = True
                    if cfg.max_roc5 is not None and not (row['roc5'] < cfg.max_roc5): ok = False
                    if cfg.max_roc20 is not None and not (row['roc20'] < cfg.max_roc20): ok = False
                    if cfg.max_dsma20 is not None and not (row['dist_sma20_pct'] < cfg.max_dsma20): ok = False
                    if cfg.max_atr_pct is not None and not (row['atr_pct'] < cfg.max_atr_pct): ok = False
                    if ok:
                        candidates.append(sym)

        avail = max_open_coins - len(open_positions)
        for sym in (candidates[:avail] if avail > 0 else []):
            row = current_rows[sym]
            entry_price = row['close']
            qty = (cash_per_entry * (1-commission)) / entry_price
            open_positions[sym] = [{'qty': qty, 'entry_price': entry_price,
                                    'cash': cash_per_entry, 'entry_idx': i}]

        # equity
        invested = sum(sum(p['cash'] for p in pl) for pl in open_positions.values())
        mv = 0.0
        for sym, pl in open_positions.items():
            if sym in current_rows:
                mv += sum(p['qty'] for p in pl) * current_rows[sym]['close']
            else:
                mv += sum(p['cash'] for p in pl)
        realized = sum(t['pnl_usd'] for t in completed)
        unrealized = mv - invested
        daily.append({'datetime': dt, 'invested': invested,
                      'total_pnl': realized + unrealized})

    return completed, pd.DataFrame(daily)

def analyze(trades, eq_df, name):
    if len(trades) == 0:
        return {'Chiến lược': name, 'Lệnh': 0, 'PnL($)': 0, 'ROI%': 0, 'WR%': 0,
                'AvgWin': 0, 'AvgLoss': 0, 'RR': 0, 'PF': 0, 'MaxDD($)': 0, 'MaxDD%': 0}
    df_t = pd.DataFrame(trades)
    wins = df_t[df_t.win]; losses = df_t[~df_t.win]
    total_t = len(df_t)
    wr = (len(wins)/total_t)*100
    total_pnl = df_t.pnl_usd.sum()
    avg_win = wins.pnl_usd.mean() if len(wins) else 0
    avg_loss = losses.pnl_usd.mean() if len(losses) else 0
    pf = abs(wins.pnl_usd.sum()/losses.pnl_usd.sum()) if losses.pnl_usd.sum() else 999
    eq = eq_df.copy()
    eq['peak'] = eq['total_pnl'].cummax()
    eq['dd'] = eq['total_pnl'] - eq['peak']
    max_dd = eq['dd'].min()
    max_cap = eq['invested'].max() if eq['invested'].max() > 0 else 1500
    roi = total_pnl / max_cap * 100
    return {'Chiến lược': name, 'Lệnh': total_t, 'PnL($)': round(total_pnl,2),
            'ROI%': round(roi,2), 'WR%': round(wr,2),
            'AvgWin': round(avg_win,2), 'AvgLoss': round(avg_loss,2),
            'RR': round(abs(avg_win/avg_loss),2) if avg_loss else 999,
            'PF': round(pf,2), 'MaxDD($)': round(max_dd,2),
            'MaxDD%': round(max_dd/max_cap*100,2)}

def main():
    print("Loading data...")
    symbols = get_top_100_symbols()
    symbols_data = {}
    for sym in symbols:
        time.sleep(0.03)
        df = get_daily_klines(sym, limit=1000)
        if df is None:
            continue
        ind = compute_indicators(df, sym)
        if ind is not None:
            symbols_data[sym] = ind
    print(f"Loaded {len(symbols_data)} symbols.\n")

    cfgs = [
        SimConfig("BASE (hiện tại)", ),
        # === VÒNG 1: TINH QUANH VÙNG MAX PnL (R5 x R20) ===
        SimConfig("R5<20+R20<45", max_roc5=20, max_roc20=45),
        SimConfig("R5<20+R20<50", max_roc5=20, max_roc20=50),
        SimConfig("R5<22+R20<50", max_roc5=22, max_roc20=50),
        SimConfig("R5<25+R20<45", max_roc5=25, max_roc20=45),
        SimConfig("R5<25+R20<50", max_roc5=25, max_roc20=50),
        SimConfig("R5<22+R20<55", max_roc5=22, max_roc20=55),
        SimConfig("R5<25+R20<55", max_roc5=25, max_roc20=55),
        SimConfig("R5<25+R20<60", max_roc5=25, max_roc20=60),
        SimConfig("R5<28+R20<50", max_roc5=28, max_roc20=50),
        # === VÒNG 2: TINH QUANH VÙNG ỔN ĐỊNH (dS20 x ATR) ===
        SimConfig("A2+dS20<22%", max_roc5=20, max_roc20=40, max_dsma20=22),
        SimConfig("A2+dS20<23%", max_roc5=20, max_roc20=40, max_dsma20=23),
        SimConfig("A2+dS20<25%", max_roc5=20, max_roc20=40, max_dsma20=25),
        SimConfig("A2+dS20<27%", max_roc5=20, max_roc20=40, max_dsma20=27),
        SimConfig("A2+ATR<6", max_roc5=20, max_roc20=40, max_atr_pct=6),
        SimConfig("A2+ATR<6.5", max_roc5=20, max_roc20=40, max_atr_pct=6.5),
        SimConfig("A2+ATR<7.5", max_roc5=20, max_roc20=40, max_atr_pct=7.5),
        SimConfig("A2+ATR<8", max_roc5=20, max_roc20=40, max_atr_pct=8),
        # === KẾT HỢP TINH ===
        SimConfig("A2+dS20<22+ATR<7", max_roc5=20, max_roc20=40, max_dsma20=22, max_atr_pct=7),
        SimConfig("A2+dS20<25+ATR<7", max_roc5=20, max_roc20=40, max_dsma20=25, max_atr_pct=7),
        SimConfig("A2+dS20<20+ATR<8", max_roc5=20, max_roc20=40, max_dsma20=20, max_atr_pct=8),
        SimConfig("R5<25+R20<50+dS20<25", max_roc5=25, max_roc20=50, max_dsma20=25),
        SimConfig("R5<25+R20<50+ATR<7", max_roc5=25, max_roc20=50, max_atr_pct=7),
    ]

    results = []
    for cfg in cfgs:
        trades, eq = simulate(symbols_data, cfg)
        results.append(analyze(trades, eq, cfg.name))
        print(f"  done: {cfg.name}")

    res_df = pd.DataFrame(results)
    pd.set_option('display.width', 200)
    pd.set_option('display.max_columns', None)
    print("\n" + "="*120)
    print("BẢNG BÁO CÁO SO SÁNH CÁC CẢI TIẾN CHIẾN LƯỢC (Backtest Top 100, D1, vốn $1500, 3 pyramid, max 10 mã)")
    print("="*120)
    print(res_df.to_string(index=False))
    res_df.to_csv('improvement_proposals_report.csv', index=False)
    print("\nĐã lưu: improvement_proposals_report.csv")

if __name__ == "__main__":
    main()
