import requests
import pandas as pd
import numpy as np
import time

def get_top_50_symbols():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    resp = requests.get(url).json()
    
    usdt_pairs = []
    # Stablecoins to exclude
    exclude = ['USDCUSDT', 'FDUSDUSDT', 'TUSDUSDT', 'BUSDUSDT', 'EURUSDT', 'AEURUSDT', 'DAIUSDT', 'WBTCUSDT', 'WBETHUSDT', 'USDEUSDT']
    
    for item in resp:
        sym = item['symbol']
        if sym.endswith('USDT') and sym not in exclude:
            quote_vol = float(item['quoteVolume']) # 24h volume in USDT
            usdt_pairs.append({'symbol': sym, 'volume': quote_vol})
            
    df = pd.DataFrame(usdt_pairs)
    df = df.sort_values(by='volume', ascending=False).reset_index(drop=True)
    top_50 = df.head(50)['symbol'].tolist()
    return top_50

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
        print(f"Error fetching {symbol}: {e}")
        return None

def run_backtest_symbol(df, symbol):
    # Need at least 200 bars for 200 SMA
    if len(df) < 220:
        return None
    
    bb_len = 20
    bb_mult = 1.5
    
    # Bollinger Envelopes 24/7 (John Bollinger)
    df['sma_high'] = df['high'].rolling(bb_len).mean()
    df['std_high'] = df['high'].rolling(bb_len).std()
    df['upper_band'] = df['sma_high'] + bb_mult * df['std_high']
    
    df['sma_low'] = df['low'].rolling(bb_len).mean()
    df['std_low'] = df['low'].rolling(bb_len).std()
    df['lower_band'] = df['sma_low'] - bb_mult * df['std_low']
    df['baseline'] = (df['upper_band'] + df['lower_band']) / 2.0
    
    # 4 SMAs: 50, 100, 150, 200
    df['sma50'] = df['close'].rolling(50).mean()
    df['sma100'] = df['close'].rolling(100).mean()
    df['sma150'] = df['close'].rolling(150).mean()
    df['sma200'] = df['close'].rolling(200).mean()
    
    # Bullish condition: Close above all 4 SMAs
    df['bullish_4sma'] = (df['close'] > df['sma50']) & \
                         (df['close'] > df['sma100']) & \
                         (df['close'] > df['sma150']) & \
                         (df['close'] > df['sma200'])
    
    # Signals
    # Entry: Bullish 4 SMA and Close crosses above upper_band
    df['prev_close'] = df['close'].shift(1)
    df['prev_upper'] = df['upper_band'].shift(1)
    df['crossover_upper'] = (df['prev_close'] <= df['prev_upper']) & (df['close'] > df['upper_band'])
    
    # Exit conditions: Crossunder Lower Band OR crossunder any of 4 SMAs
    df['prev_lower'] = df['lower_band'].shift(1)
    df['crossunder_lower'] = (df['prev_close'] >= df['prev_lower']) & (df['close'] < df['lower_band'])
    
    for s in [50, 100, 150, 200]:
        df[f'prev_sma{s}'] = df[f'sma{s}'].shift(1)
        df[f'crossunder_sma{s}'] = (df['prev_close'] >= df[f'prev_sma{s}']) & (df['close'] < df[f'sma{s}'])
        
    df['exit_signal'] = df['crossunder_lower'] | \
                        df['crossunder_sma50'] | \
                        df['crossunder_sma100'] | \
                        df['crossunder_sma150'] | \
                        df['crossunder_sma200']
    
    # Simulate Strategy
    # Pyramiding max 3, $50 per entry, max $150
    # Commission: 0.075% per trade
    commission = 0.00075
    
    cash_per_entry = 50.0
    max_pyramid = 3
    
    positions = [] # list of entries: {'price': p, 'qty': q, 'cash': cash_per_entry}
    trades = []
    
    for i in range(201, len(df)):
        row = df.iloc[i]
        
        # Check Exit first if in position
        if len(positions) > 0 and row['exit_signal']:
            exit_price = row['close']
            total_qty = sum(p['qty'] for p in positions)
            total_invested = sum(p['cash'] for p in positions)
            gross_value = total_qty * exit_price
            net_value = gross_value * (1.0 - commission)
            
            pnl_dollar = net_value - total_invested
            pnl_pct = (pnl_dollar / total_invested) * 100.0
            
            trades.append({
                'symbol': symbol,
                'entries': len(positions),
                'invested': total_invested,
                'exit_price': exit_price,
                'pnl_dollar': pnl_dollar,
                'pnl_pct': pnl_pct,
                'win': pnl_dollar > 0,
                'exit_date': row['datetime']
            })
            positions = [] # closed
            continue
            
        # Check Entry / Pyramid
        if row['bullish_4sma'] and row['crossover_upper']:
            if len(positions) < max_pyramid:
                entry_price = row['close']
                qty = (cash_per_entry * (1.0 - commission)) / entry_price
                positions.append({'price': entry_price, 'qty': qty, 'cash': cash_per_entry})
                
    # If still in position at the end, close at last price
    if len(positions) > 0:
        last_row = df.iloc[-1]
        exit_price = last_row['close']
        total_qty = sum(p['qty'] for p in positions)
        total_invested = sum(p['cash'] for p in positions)
        gross_value = total_qty * exit_price
        net_value = gross_value * (1.0 - commission)
        pnl_dollar = net_value - total_invested
        pnl_pct = (pnl_dollar / total_invested) * 100.0
        trades.append({
            'symbol': symbol,
            'entries': len(positions),
            'invested': total_invested,
            'exit_price': exit_price,
            'pnl_dollar': pnl_dollar,
            'pnl_pct': pnl_pct,
            'win': pnl_dollar > 0,
            'exit_date': last_row['datetime']
        })

    return trades

def main():
    print("Fetching Top 50 USDT symbols by 24h volume on Binance...")
    symbols = get_top_50_symbols()
    print(f"Top symbols: {symbols[:10]} ...")
    
    all_trades = []
    symbol_results = []
    
    for idx, sym in enumerate(symbols):
        time.sleep(0.1)
        df = get_daily_klines(sym, limit=1000)
        if df is None:
            continue
        trades = run_backtest_symbol(df, sym)
        if trades is not None and len(trades) > 0:
            all_trades.extend(trades)
            sym_pnl = sum(t['pnl_dollar'] for t in trades)
            sym_wins = sum(1 for t in trades if t['win'])
            total_t = len(trades)
            wr = (sym_wins / total_t) * 100 if total_t > 0 else 0
            symbol_results.append({
                'symbol': sym,
                'trades': total_t,
                'pnl_usd': sym_pnl,
                'winrate': wr,
                'days_data': len(df)
            })
        else:
            days = len(df) if df is not None else 0
            print(f"Symbol {sym} had insufficient data or 0 trades ({days} days).")
            
    res_df = pd.DataFrame(symbol_results)
    if len(res_df) == 0:
        print("No trades generated.")
        return
        
    res_df = res_df.sort_values(by='pnl_usd', ascending=False).reset_index(drop=True)
    
    total_trades = len(all_trades)
    winning_trades = sum(1 for t in all_trades if t['win'])
    total_pnl = sum(t['pnl_dollar'] for t in all_trades)
    avg_winrate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    win_pnls = [t['pnl_dollar'] for t in all_trades if t['win']]
    loss_pnls = [t['pnl_dollar'] for t in all_trades if not t['win']]
    
    avg_win = np.mean(win_pnls) if len(win_pnls) > 0 else 0
    avg_loss = np.mean(loss_pnls) if len(loss_pnls) > 0 else 0
    profit_factor = abs(sum(win_pnls) / sum(loss_pnls)) if sum(loss_pnls) != 0 else np.nan
    
    print("\n" + "="*60)
    print("TỔNG HỢP KẾT QUẢ BACKTEST TOP 50 CRYPTO (KHUNG D1)")
    print("="*60)
    print(f"Số mã có đủ dữ liệu & phát sinh lệnh : {len(res_df)} / 50")
    print(f"Tổng số lệnh thực thi               : {total_trades}")
    print(f"Tỷ lệ thắng (Win Rate)               : {avg_winrate:.2f}% ({winning_trades} Thắng / {total_trades - winning_trades} Thua)")
    print(f"Tổng Lợi Nhuận (PnL Net)             : ${total_pnl:,.2f} USD")
    print(f"Lệnh thắng trung bình                : +${avg_win:.2f}")
    print(f"Lệnh thua trung bình                 : -${abs(avg_loss):.2f}")
    print(f"Profit Factor (Lãi gộp / Lỗ gộp)    : {profit_factor:.2f}")
    print(f"Tỷ lệ R:R Thực tế (Avg Win / Avg Loss): {abs(avg_win / avg_loss):.2f}")
    print("="*60)
    
    print("\nTOP 10 CÁC ĐỒNG COIN HIỆU QUẢ NHẤT:")
    print(res_df.head(10).to_string())
    
    print("\nTOP 5 CÁC ĐỒNG COIN THUA LỖ NHẤT:")
    print(res_df.tail(5).to_string())

if __name__ == "__main__":
    main()
