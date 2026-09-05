import requests
import pandas as pd
import numpy as np
import time
from datetime import datetime

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
    # Minimum 110 bars needed for SMA100
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
    
    # Adaptive Bullish 4 SMA: If 150/200 not available, use available ones up to SMA100
    cond_50 = (df['close'] > df['sma50'])
    cond_100 = (df['close'] > df['sma100'])
    cond_150 = (df['close'] > df['sma150']) | (df['sma150'].isna())
    cond_200 = (df['close'] > df['sma200']) | (df['sma200'].isna())
    
    df['bullish_sma'] = cond_50 & cond_100 & cond_150 & cond_200
    
    # Entry crossover
    df['prev_close'] = df['close'].shift(1)
    df['prev_upper'] = df['upper_band'].shift(1)
    df['entry_signal'] = df['bullish_sma'] & (df['prev_close'] <= df['prev_upper']) & (df['close'] > df['upper_band'])
    
    # Exit conditions: Crossunder Lower Band OR any available SMA
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
    # Align all dataframes on common dates
    all_dates = set()
    for sym, df in symbols_data.items():
        all_dates.update(df['datetime'].tolist())
    
    sorted_dates = sorted(list(all_dates))
    
    # portfolio state
    # open_positions: {symbol: [{'qty': q, 'entry_price': p, 'cash': cash_per_entry}, ...]}
    open_positions = {}
    completed_trades = []
    portfolio_daily_history = []
    
    # Pre-index dataframes by datetime for speed
    data_by_date = {}
    for dt in sorted_dates:
        data_by_date[dt] = {}
        
    for sym, df in symbols_data.items():
        df_indexed = df.set_index('datetime')
        for dt, row in df_indexed.iterrows():
            if dt in data_by_date:
                data_by_date[dt][sym] = row
                
    total_cash_invested = 0.0
    
    for dt in sorted_dates:
        current_rows = data_by_date[dt]
        
        # 1. Check EXITS for currently held positions
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
        # Candidate entries for today
        candidates = []
        for sym, row in current_rows.items():
            # Check pyramid for existing position
            if sym in open_positions:
                if len(open_positions[sym]) < max_pyramid and row['entry_signal']:
                    # Prioritize pyramiding existing winning trades
                    entry_price = row['close']
                    qty = (cash_per_entry * (1.0 - commission)) / entry_price
                    open_positions[sym].append({'qty': qty, 'entry_price': entry_price, 'cash': cash_per_entry})
            else:
                # New candidate coin
                if row['entry_signal']:
                    candidates.append(sym)
                    
        # If open_positions count < max_open_coins, add new candidates
        available_slots = max_open_coins - len(open_positions)
        if available_slots > 0 and len(candidates) > 0:
            # Sort candidates by 24h volume or pick top
            for sym in candidates[:available_slots]:
                row = current_rows[sym]
                entry_price = row['close']
                qty = (cash_per_entry * (1.0 - commission)) / entry_price
                open_positions[sym] = [{'qty': qty, 'entry_price': entry_price, 'cash': cash_per_entry}]
                
        # Calculate daily portfolio equity
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

def compute_correlation_matrix(symbols_data, top_active_symbols):
    # Daily returns dataframe
    returns_dict = {}
    for sym in top_active_symbols:
        if sym in symbols_data:
            df = symbols_data[sym].set_index('datetime')
            returns_dict[sym] = df['close'].pct_change()
            
    ret_df = pd.DataFrame(returns_dict).dropna(how='all')
    corr_matrix = ret_df.corr()
    return corr_matrix

def main():
    print("Fetching Top 100 USDT symbols from Binance...")
    symbols = get_top_100_symbols()
    print(f"Retrieved {len(symbols)} symbols. Processing Kline data...")
    
    symbols_data = {}
    eligible_count = 0
    
    for sym in symbols:
        time.sleep(0.04)
        df = get_daily_klines(sym, limit=1000)
        if df is None:
            continue
        ind_df = compute_indicators(df, sym)
        if ind_df is not None:
            symbols_data[sym] = ind_df
            eligible_count += 1
            
    print(f"Mã đủ dữ liệu (>= 110 nến, tính đến SMA100): {eligible_count} / 100")
    
    # 1. Run Portfolio Simulation with 10 max concurrent coins
    trades, equity_df = simulate_portfolio(symbols_data, max_open_coins=10, cash_per_entry=50.0, max_pyramid=3)
    
    trades_df = pd.DataFrame(trades)
    total_trades = len(trades_df)
    wins = sum(1 for t in trades if t['win'])
    total_pnl = sum(t['pnl_usd'] for t in trades)
    wr = (wins / total_trades) * 100.0 if total_trades > 0 else 0
    
    win_pnls = [t['pnl_usd'] for t in trades if t['win']]
    loss_pnls = [t['pnl_usd'] for t in trades if not t['win']]
    avg_win = np.mean(win_pnls) if len(win_pnls) > 0 else 0.0
    avg_loss = np.mean(loss_pnls) if len(loss_pnls) > 0 else 0.0
    pf = abs(sum(win_pnls) / sum(loss_pnls)) if sum(loss_pnls) != 0 else 0.0
    
    # Max Drawdown of Portfolio
    equity_df['peak'] = equity_df['total_equity_pnl'].cummax()
    equity_df['drawdown'] = equity_df['total_equity_pnl'] - equity_df['peak']
    max_dd = equity_df['drawdown'].min()
    max_capital_used = equity_df['invested_capital'].max()
    
    print("\n" + "="*70)
    print("KẾT QUẢ DANH MỤC TOP 100 (GIỚI HẠN TỐI ĐA 10 CON CÙNG LÚC)")
    print("="*70)
    print(f"Vốn tối đa được sử dụng đồng thời : ${max_capital_used:,.2f} USD (Trên trần 10 x $150 = $1,500)")
    print(f"Tổng Lợi Nhuận Ròng (Net PnL)      : ${total_pnl:,.2f} USD")
    print(f"Lợi nhuận trên vốn tối đa         : +{(total_pnl / max_capital_used)*100:.1f}%")
    print(f"Tổng số lệnh thực thi              : {total_trades}")
    print(f"Tỷ lệ thắng (Winrate)              : {wr:.2f}% ({wins} Thắng / {total_trades - wins} Thua)")
    print(f"Lệnh thắng trung bình (Avg Win)    : +${avg_win:.2f}")
    print(f"Lệnh thua trung bình (Avg Loss)   : -${abs(avg_loss):.2f}")
    print(f"Tỷ lệ R:R Thực tế                  : {abs(avg_win / avg_loss):.2f} : 1")
    print(f"Profit Factor                      : {pf:.2f}")
    print(f"Max Drawdown (Sụt giảm lớn nhất)  : ${max_dd:.2f} USD")
    print("="*70)
    
    # Top individual contributors
    sym_contrib = trades_df.groupby('symbol').agg(
        trades=('pnl_usd', 'count'),
        wins=('win', 'sum'),
        total_pnl=('pnl_usd', 'sum')
    ).reset_index()
    sym_contrib['winrate'] = (sym_contrib['wins'] / sym_contrib['trades']) * 100.0
    sym_contrib = sym_contrib.sort_values(by='total_pnl', ascending=False).reset_index(drop=True)
    
    print("\nTOP 10 COIN ĐÓNG GÓP LÃI NHIỀU NHẤT TRONG DANH MỤC 10 CON:")
    top_10_coins = sym_contrib.head(10)
    print(top_10_coins.to_string())
    
    # Correlation Analysis
    top_syms = sym_contrib.head(10)['symbol'].tolist()
    corr_matrix = compute_correlation_matrix(symbols_data, top_syms)
    
    print("\n" + "="*70)
    print("MA TRẬN TƯƠNG QUAN (CORRELATION MATRIX) GIỮA CÁC COIN HÀNG ĐẦU:")
    print("="*70)
    print(corr_matrix.round(2).to_string())
    
    avg_corr = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()
    print(f"\n>> Tương quan trung bình danh mục (Average Portfolio Correlation): {avg_corr:.2f}")

if __name__ == "__main__":
    main()
