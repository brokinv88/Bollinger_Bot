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
    except Exception as e:
        return None

def compute_indicators(df, symbol):
    if len(df) < 110:
        return None
        
    bb_len = 20
    bb_mult = 1.5
    
    # 24/7 Bollinger Envelopes
    df['sma_high'] = df['high'].rolling(bb_len).mean()
    df['std_high'] = df['high'].rolling(bb_len).std()
    df['upper_band'] = df['sma_high'] + bb_mult * df['std_high']
    
    df['sma_low'] = df['low'].rolling(bb_len).mean()
    df['std_low'] = df['low'].rolling(bb_len).std()
    df['lower_band'] = df['sma_low'] - bb_mult * df['std_low']
    df['baseline'] = (df['upper_band'] + df['lower_band']) / 2.0
    
    # SMAs
    df['sma50'] = df['close'].rolling(50).mean()
    df['sma100'] = df['close'].rolling(100).mean()
    df['sma150'] = df['close'].rolling(150).mean() if len(df) >= 160 else np.nan
    df['sma200'] = df['close'].rolling(200).mean() if len(df) >= 210 else np.nan
    
    # Adaptive Bullish 4 SMA
    cond_50 = (df['close'] > df['sma50'])
    cond_100 = (df['close'] > df['sma100'])
    cond_150 = (df['close'] > df['sma150']) | (df['sma150'].isna())
    cond_200 = (df['close'] > df['sma200']) | (df['sma200'].isna())
    df['bullish_sma'] = cond_50 & cond_100 & cond_150 & cond_200
    
    # Entry crossover
    df['prev_close'] = df['close'].shift(1)
    df['prev_upper'] = df['upper_band'].shift(1)
    df['entry_signal'] = df['bullish_sma'] & (df['prev_close'] <= df['prev_upper']) & (df['close'] > df['upper_band'])
    
    # Exit conditions
    df['prev_lower'] = df['lower_band'].shift(1)
    exit_lower = (df['prev_close'] >= df['prev_lower']) & (df['close'] < df['lower_band'])
    exit_sma50 = (df['prev_close'] >= df['sma50'].shift(1)) & (df['close'] < df['sma50'])
    exit_sma100 = (df['prev_close'] >= df['sma100'].shift(1)) & (df['close'] < df['sma100'])
    exit_sma150 = (df['prev_close'] >= df['sma150'].shift(1)) & (df['close'] < df['sma150']) & df['sma150'].notna()
    exit_sma200 = (df['prev_close'] >= df['sma200'].shift(1)) & (df['close'] < df['sma200']) & df['sma200'].notna()
    
    df['exit_signal'] = exit_lower | exit_sma50 | exit_sma100 | exit_sma150 | exit_sma200
    df['symbol'] = symbol
    return df

def simulate_portfolio(symbols_data, max_open_coins=10, cash_per_entry=50.0, max_pyramid=3, commission=0.00075):
    all_dates = set()
    for sym, df in symbols_data.items():
        all_dates.update(df['datetime'].tolist())
    sorted_dates = sorted(list(all_dates))
    
    open_positions = {}
    completed_trades = []
    portfolio_daily_history = []
    
    data_by_date = {dt: {} for dt in sorted_dates}
    for sym, df in symbols_data.items():
        df_indexed = df.set_index('datetime')
        for dt, row in df_indexed.iterrows():
            if dt in data_by_date:
                data_by_date[dt][sym] = row
                
    for dt in sorted_dates:
        current_rows = data_by_date[dt]
        
        # 1. Check EXITS
        held_symbols = list(open_positions.keys())
        for sym in held_symbols:
            if sym not in current_rows:
                continue
            row = current_rows[sym]
            if row['exit_signal']:
                exit_price = row['close']
                pos_list = open_positions[sym]
                total_qty = sum(p['qty'] for p in pos_list)
                total_invested = sum(p['cash'] for p in pos_list)
                net_val = (total_qty * exit_price) * (1.0 - commission)
                pnl = net_val - total_invested
                
                completed_trades.append({
                    'symbol': sym,
                    'entries': len(pos_list),
                    'invested': total_invested,
                    'pnl_usd': pnl,
                    'pnl_pct': (pnl / total_invested) * 100.0,
                    'win': pnl > 0,
                    'exit_date': dt
                })
                del open_positions[sym]
                
        # 2. Check ENTRIES / PYRAMID
        candidates = []
        for sym, row in current_rows.items():
            if sym in open_positions:
                # Pyramiding only if max_pyramid > 1
                if max_pyramid > 1 and len(open_positions[sym]) < max_pyramid and row['entry_signal']:
                    entry_price = row['close']
                    qty = (cash_per_entry * (1.0 - commission)) / entry_price
                    open_positions[sym].append({'qty': qty, 'entry_price': entry_price, 'cash': cash_per_entry})
            else:
                if row['entry_signal']:
                    candidates.append(sym)
                    
        available_slots = max_open_coins - len(open_positions)
        if available_slots > 0 and len(candidates) > 0:
            for sym in candidates[:available_slots]:
                row = current_rows[sym]
                entry_price = row['close']
                qty = (cash_per_entry * (1.0 - commission)) / entry_price
                open_positions[sym] = [{'qty': qty, 'entry_price': entry_price, 'cash': cash_per_entry}]
                
        # Portfolio equity
        current_invested = sum(sum(p['cash'] for p in pos_list) for pos_list in open_positions.values())
        current_market_val = 0.0
        for sym, pos_list in open_positions.items():
            if sym in current_rows:
                curr_price = current_rows[sym]['close']
                tot_qty = sum(p['qty'] for p in pos_list)
                current_market_val += tot_qty * curr_price
            else:
                current_market_val += sum(p['cash'] for p in pos_list)
                
        realized_pnl = sum(t['pnl_usd'] for t in completed_trades)
        unrealized_pnl = current_market_val - current_invested
        total_pnl = realized_pnl + unrealized_pnl
        
        portfolio_daily_history.append({
            'datetime': dt,
            'open_coins': len(open_positions),
            'invested_capital': current_invested,
            'total_equity_pnl': total_pnl
        })
        
    return completed_trades, pd.DataFrame(portfolio_daily_history)

def main():
    print("Fetching Top 100 symbols and Kline data...")
    symbols = get_top_100_symbols()
    symbols_data = {}
    for sym in symbols:
        time.sleep(0.03)
        df = get_daily_klines(sym, limit=1000)
        if df is None:
            continue
        ind_df = compute_indicators(df, sym)
        if ind_df is not None:
            symbols_data[sym] = ind_df
            
    print(f"Loaded {len(symbols_data)} eligible symbols.")
    
    # 1. Run Baseline: Pyramid 3 (50$ x 3 = 150$)
    trades_p3, eq_p3 = simulate_portfolio(symbols_data, max_open_coins=10, cash_per_entry=50.0, max_pyramid=3)
    
    # 2. Run Single Entry: Pyramid 0 (Không nhồi lệnh, 150$ 1 lần duy nhất)
    trades_p0, eq_p0 = simulate_portfolio(symbols_data, max_open_coins=10, cash_per_entry=150.0, max_pyramid=1)
    
    def analyze_results(trades, eq_df, name):
        df_t = pd.DataFrame(trades)
        total_t = len(df_t)
        wins = sum(1 for t in trades if t['win'])
        losses = total_t - wins
        wr = (wins / total_t) * 100.0 if total_t > 0 else 0
        total_pnl = sum(t['pnl_usd'] for t in trades)
        
        win_pnls = [t['pnl_usd'] for t in trades if t['win']]
        loss_pnls = [t['pnl_usd'] for t in trades if not t['win']]
        avg_win = np.mean(win_pnls) if len(win_pnls) > 0 else 0.0
        avg_loss = np.mean(loss_pnls) if len(loss_pnls) > 0 else 0.0
        pf = abs(sum(win_pnls) / sum(loss_pnls)) if sum(loss_pnls) != 0 else 0.0
        
        eq_df['peak'] = eq_df['total_equity_pnl'].cummax()
        eq_df['drawdown'] = eq_df['total_equity_pnl'] - eq_df['peak']
        max_dd = eq_df['drawdown'].min()
        max_cap = eq_df['invested_capital'].max()
        
        return {
            'Chiến Lược': name,
            'Vốn Cực Đại': max_cap,
            'Tổng PnL ($)': total_pnl,
            'ROI (%)': (total_pnl / max_cap) * 100 if max_cap > 0 else 0,
            'Số Lệnh': total_t,
            'Winrate (%)': wr,
            'Lãi TB ($)': avg_win,
            'Lỗ TB ($)': avg_loss,
            'Tỷ Lệ R:R': abs(avg_win / avg_loss) if avg_loss != 0 else 0,
            'Profit Factor': pf,
            'Max Drawdown ($)': max_dd
        }
        
    res_p3 = analyze_results(trades_p3, eq_p3, "Pyramid 3 (3 lần x $50 = $150)")
    res_p0 = analyze_results(trades_p0, eq_p0, "Pyramid 0 (Vào 1 lần $150)")
    
    comp_df = pd.DataFrame([res_p3, res_p0])
    
    print("\n" + "="*80)
    print("BẢNG SO SÁNH HIỆU QUẢ DANH MỤC: PYRAMID 3 VS PYRAMID 0 (VỐN $1,500 - MAX 10 MÃ)")
    print("="*80)
    print(comp_df.to_string(index=False))
    
    # Save CSV
    comp_df.to_csv('pyramid_comparison_report.csv', index=False)
    
if __name__ == "__main__":
    main()
