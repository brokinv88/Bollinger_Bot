import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

import config
import notifier
from database import PortfolioDB
import universe

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_daily_data(symbol, limit=250):
    url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10).json()
        if not isinstance(resp, list):
            url_alt = f"https://api3.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
            resp = requests.get(url_alt, headers=HEADERS, timeout=10).json()
            if not isinstance(resp, list):
                return None
        df = pd.DataFrame(resp, columns=[
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

def evaluate_signals(df):
    if len(df) < 110:
        return None
        
    bb_len = config.BB_LEN
    bb_mult = config.BB_MULT
    
    # Bollinger Envelopes 24/7
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
    
    cond_50 = (df['close'] > df['sma50'])
    cond_100 = (df['close'] > df['sma100'])
    cond_150 = (df['close'] > df['sma150']) | (df['sma150'].isna())
    cond_200 = (df['close'] > df['sma200']) | (df['sma200'].isna())
    
    df['bullish_sma'] = cond_50 & cond_100 & cond_150 & cond_200
    
    c_prev = df.iloc[-3]
    c_curr = df.iloc[-2]
    
    entry_signal = c_curr['bullish_sma'] and (c_prev['close'] <= c_prev['upper_band']) and (c_curr['close'] > c_curr['upper_band'])
    
    exit_lower = (c_prev['close'] >= c_prev['lower_band']) and (c_curr['close'] < c_curr['lower_band'])
    exit_sma50 = (c_prev['close'] >= c_prev['sma50']) and (c_curr['close'] < c_curr['sma50'])
    exit_sma100 = (c_prev['close'] >= c_prev['sma100']) and (c_curr['close'] < c_curr['sma100'])
    exit_sma150 = (c_prev['close'] >= c_prev['sma150']) and (c_curr['close'] < c_curr['sma150']) if pd.notna(c_curr['sma150']) else False
    exit_sma200 = (c_prev['close'] >= c_prev['sma200']) and (c_curr['close'] < c_curr['sma200']) if pd.notna(c_curr['sma200']) else False
    
    exit_signal = exit_lower or exit_sma50 or exit_sma100 or exit_sma150 or exit_sma200
    exit_reason = "Thủng Lower Band" if exit_lower else "Thủng đường SMA"
    
    roc_20 = (c_curr['close'] - df.iloc[-22]['close']) / df.iloc[-22]['close'] * 100.0 if len(df) >= 22 else 0.0
    
    valid_smas = [c_curr['sma50'], c_curr['sma100']]
    if pd.notna(c_curr['sma150']): valid_smas.append(c_curr['sma150'])
    if pd.notna(c_curr['sma200']): valid_smas.append(c_curr['sma200'])
    
    hard_stop_ref = max([s for s in valid_smas if s < c_curr['close']] + [c_curr['lower_band']])
    hard_stop_price = hard_stop_ref * 0.99
    
    return {
        'entry': entry_signal,
        'exit': exit_signal,
        'exit_reason': exit_reason,
        'close': c_curr['close'],
        'upper_band': c_curr['upper_band'],
        'hard_stop_price': hard_stop_price,
        'date': str(c_curr['datetime'])[:10],
        'roc_20': roc_20
    }

def scan_account(account_name: str, db_file: str, symbols: list, kline_cache: dict):
    db = PortfolioDB(db_file)
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime('%Y-%m-%d')
    today_vn = (now_utc + timedelta(hours=7)).strftime('%d/%m/%Y %H:%M')
    
    print(f"\n[{account_name.upper()}] Bắt đầu phân tích {len(symbols)} mã...")
    open_positions = db.get_open_positions()
    
    data_dict = {}
    for sym in symbols:
        if sym not in kline_cache:
            df = get_daily_data(sym)
            if df is not None:
                kline_cache[sym] = evaluate_signals(df)
            else:
                kline_cache[sym] = None
                
        eval_res = kline_cache[sym]
        if eval_res is not None:
            data_dict[sym] = eval_res
                
    # 1. Check Exit
    alerts_exit = []
    for sym, pos in list(open_positions.items()):
        if sym not in data_dict:
            continue
        res = data_dict[sym]
        curr_price = res['close']
        if res['exit']:
            pnl_usd, pnl_pct, invested = db.close_position_db(sym, curr_price, today_str, res['exit_reason'])
            alerts_exit.append(
                f"🔴 *BÁN/ĐÓNG:* `{sym}`\n"
                f"• Lý do: {res['exit_reason']}\n"
                f"• Giá bán: `{curr_price}$` | Lời/Lỗ: *{pnl_pct:+.2f}%* (`{pnl_usd:+.2f}$`)"
            )
            del open_positions[sym]
            
    # 2. Check Entry
    alerts_entry = []
    candidates = []
    for sym, res in data_dict.items():
        if res['entry']:
            if sym in open_positions:
                pos = open_positions[sym]
                if pos['pyramid_level'] < config.MAX_PYRAMID:
                    qty = (config.CASH_PER_ENTRY * 0.99925) / res['close']
                    new_lvl = db.add_or_pyramid_position(sym, qty, config.CASH_PER_ENTRY, res['close'], today_str)
                    alerts_entry.append(
                        f"🟡 *NHỒI LỆNH (TẦNG {new_lvl}/3):* `{sym}`\n"
                        f"• Vốn: `{config.CASH_PER_ENTRY}$` (Tổng: `{pos['total_invested'] + config.CASH_PER_ENTRY}$`)\n"
                        f"🎯 *Lệnh Limit (15-30p):* Kê `{res['upper_band']:.4f}$` - `{res['close']:.4f}$`\n"
                        f"🛡 *Cắt lỗ treo sàn:* `STOP_LOSS_LIMIT` tại `{res['hard_stop_price']:.4f}$`"
                    )
            else:
                candidates.append((sym, res['roc_20'], res['close'], res['upper_band'], res['hard_stop_price']))
                
    candidates.sort(key=lambda x: x[1], reverse=True)
    available_slots = config.MAX_OPEN_COINS - len(open_positions)
    for sym, roc, price, upper, stop in candidates[:available_slots]:
        qty = (config.CASH_PER_ENTRY * 0.99925) / price
        db.add_or_pyramid_position(sym, qty, config.CASH_PER_ENTRY, price, today_str)
        open_positions[sym] = True
        alerts_entry.append(
            f"🟢 *MUA MỚI (LẦN 1/3):* `{sym}`\n"
            f"• Vốn: `{config.CASH_PER_ENTRY}$` | ROC 20d: `{roc:+.1f}%`\n"
            f"🎯 *Lệnh Limit (15-30p):* Kê `{upper:.4f}$` - `{price:.4f}$`\n"
            f"🛡 *Cắt lỗ treo sàn:* `STOP_LOSS_LIMIT` tại `{stop:.4f}$`"
        )
        
    # Message
    header = f"🏛 *DANH MỤC: {account_name.upper()}*\n🗓 Ngày: `{today_vn}` | Mode: `{config.MODE}`\n" + "="*30 + "\n"
    body = ""
    if alerts_exit: body += "\n" + "\n\n".join(alerts_exit) + "\n"
    if alerts_entry: body += "\n" + "\n\n".join(alerts_entry) + "\n"
    if not alerts_exit and not alerts_entry:
        body = "\n😴 Không có tín hiệu mua/bán mới. Tiếp tục nắm giữ.\n"
        
    current_portfolio = db.get_open_positions()
    total_invested = sum(p['total_invested'] for p in current_portfolio.values())
    footer = (
        "\n" + "="*30 + "\n"
        f"💼 Đang giữ: `{len(current_portfolio)}/{config.MAX_OPEN_COINS}` mã\n"
        f"💰 Vốn giải ngân: `{total_invested:.2f}$ / {config.TOTAL_PORTFOLIO_CAP:.2f}$`\n"
        f"📌 Nắm giữ: " + (", ".join([f"`{s}`" for s in current_portfolio.keys()]) if current_portfolio else "Trống")
    )
    notifier.send_telegram_alert(header + body + footer)

def main():
    print("=== CHẠY QUÉT SONG SONG 2 TÀI KHOẢN BINANCE (CHẾ ĐỘ TỐI ƯU TỐC ĐỘ) ===")
    vol_symbols = universe.get_top_100_volume_symbols()
    mc_symbols = universe.get_top_100_marketcap_symbols()
    
    kline_cache = {}
    
    # 1. Quét Tài khoản 1: Top 100 Volume
    scan_account("Tài Khoản 1 (Top 100 Volume)", "database_volume.db", vol_symbols, kline_cache)
    
    # 2. Quét Tài khoản 2: Top 100 MarketCap (Sử dụng lại cache các mã trùng lặp)
    scan_account("Tài Khoản 2 (Top 100 MarketCap)", "database_marketcap.db", mc_symbols, kline_cache)
    print(f"\n[HOÀN TẤT QUÉT CẢ 2 DANH MỤC TRONG {len(kline_cache)} MÃ COIN]")

if __name__ == "__main__":
    main()
