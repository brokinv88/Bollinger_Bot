import requests
import pandas as pd
import numpy as np
import time

def get_top_50_symbols():
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
    return df.head(50)['symbol'].tolist()

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

def run_backtest_symbol(df, symbol):
    if len(df) < 220:
        return None
    
    bb_len = 20
    bb_mult = 1.5
    
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
    
    df['bullish_4sma'] = (df['close'] > df['sma50']) & \
                         (df['close'] > df['sma100']) & \
                         (df['close'] > df['sma150']) & \
                         (df['close'] > df['sma200'])
    
    df['prev_close'] = df['close'].shift(1)
    df['prev_upper'] = df['upper_band'].shift(1)
    df['crossover_upper'] = (df['prev_close'] <= df['prev_upper']) & (df['close'] > df['upper_band'])
    
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
    
    commission = 0.00075
    cash_per_entry = 50.0
    max_pyramid = 3
    
    positions = []
    trades = []
    
    for i in range(201, len(df)):
        row = df.iloc[i]
        
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
                'exit_date': str(row['datetime'])[:10]
            })
            positions = []
            continue
            
        if row['bullish_4sma'] and row['crossover_upper']:
            if len(positions) < max_pyramid:
                entry_price = row['close']
                qty = (cash_per_entry * (1.0 - commission)) / entry_price
                positions.append({'price': entry_price, 'qty': qty, 'cash': cash_per_entry})
                
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
            'exit_date': str(last_row['datetime'])[:10]
        })

    return trades

def main():
    symbols = get_top_50_symbols()
    all_summary = []
    
    for sym in symbols:
        time.sleep(0.05)
        df = get_daily_klines(sym, limit=1000)
        if df is None:
            continue
        trades = run_backtest_symbol(df, sym)
        if trades is not None and len(trades) > 0:
            total_t = len(trades)
            wins = sum(1 for t in trades if t['win'])
            losses = total_t - wins
            pnl_usd = sum(t['pnl_dollar'] for t in trades)
            win_pnls = [t['pnl_dollar'] for t in trades if t['win']]
            loss_pnls = [t['pnl_dollar'] for t in trades if not t['win']]
            
            avg_win = np.mean(win_pnls) if len(win_pnls) > 0 else 0.0
            avg_loss = np.mean(loss_pnls) if len(loss_pnls) > 0 else 0.0
            max_win = max(win_pnls) if len(win_pnls) > 0 else 0.0
            max_loss = min(loss_pnls) if len(loss_pnls) > 0 else 0.0
            wr = (wins / total_t) * 100.0
            pf = abs(sum(win_pnls) / sum(loss_pnls)) if sum(loss_pnls) != 0 else 999.0
            
            all_summary.append({
                'Symbol': sym,
                'Lệnh': total_t,
                'Thắng': wins,
                'Thua': losses,
                'WinRate%': wr,
                'PnL($)': pnl_usd,
                'ProfitFactor': pf,
                'MaxWin($)': max_win,
                'MaxLoss($)': max_loss,
                'AvgWin($)': avg_win,
                'AvgLoss($)': avg_loss
            })
            
    res_df = pd.DataFrame(all_summary).sort_values(by='PnL($)', ascending=False).reset_index(drop=True)
    
    # Save markdown and CSV
    res_df.to_csv('detailed_backtest_report.csv', index=False)
    
    # Format table for clean display
    display_df = res_df.copy()
    display_df['WinRate%'] = display_df['WinRate%'].map(lambda x: f"{x:.1f}%")
    display_df['PnL($)'] = display_df['PnL($)'].map(lambda x: f"${x:+,.2f}")
    display_df['ProfitFactor'] = display_df['ProfitFactor'].map(lambda x: f"{x:.2f}")
    display_df['MaxWin($)'] = display_df['MaxWin($)'].map(lambda x: f"${x:,.2f}")
    display_df['MaxLoss($)'] = display_df['MaxLoss($)'].map(lambda x: f"${x:,.2f}")
    display_df['AvgWin($)'] = display_df['AvgWin($)'].map(lambda x: f"${x:,.2f}")
    display_df['AvgLoss($)'] = display_df['AvgLoss($)'].map(lambda x: f"${x:,.2f}")
    
    print(display_df.to_markdown(index=True))

if __name__ == "__main__":
    main()
