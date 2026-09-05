"""
auto_trade.py — ĐẶT LỆNH TỰ ĐỘNG ẢO (PAPER AUTO-TRADE)
====================================================
Chạy tách riêng khỏi daily_scanner. Khi ENABLE_AUTO_TRADE = True:

1. VÀO LỆNH TỰ ĐỘNG (source='auto'):
   - Dựa trên tín hiệu nến DAILY (entry cho BASE, entry_b cho CHIẾN LƯỢC B).
   - Giá khớp ảo: midpoint giữa upper_band và close (AUTO_ENTRY_FILL).
   - Ngăn ghi trùng trong ngày: vị thế có last_entry_date == hôm nay thì không
     nhồi/pyramid thêm (tín hiệu nến hôm qua không xử lý lặp lại).
2. THOÁT THEO TÍN HIỆU (source='auto'): thủng lower band / SMA.
3. QUẢN LÝ STOP LOSS THEO GIÁ REALTIME:
   - Cập nhật SL = 0.99 x max(SMA < giá, lower band) theo công thức mới nhất mỗi lần chạy.
   - Nếu giá hiện tại <= SL -> tự chốt lỗ tại SL.
4. Gửi 1 tin Telegram tổng hợp cho cả 4 đơn vị (2 chiến lược x 2 danh mục).

Khi ENABLE_AUTO_TRADE = False: không thay đổi gì, mọi thứ như cũ (scanner tự ghi).
"""

import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

import config
import notifier
import universe
from database import PortfolioDB
from daily_scanner import get_daily_data, evaluate_signals, fetch_and_evaluate_symbol
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {"User-Agent": "Mozilla/5.0"}

# 4 đơn vị theo dõi: (tên, db_file, entry_key, strategy_label, category)
def get_units():
    vol_suffix = config.STRATEGY_B_DB_SUFFIX if config.ENABLE_STRATEGY_B else ""
    mc_suffix = config.STRATEGY_B_DB_SUFFIX if config.ENABLE_STRATEGY_B else ""
    units = []
    # BASE
    units.append(("BASE - Top 100 Volume", "database_volume.db", "entry", "BASE", "VOL"))
    units.append(("BASE - Top 100 MarketCap", "database_marketcap.db", "entry", "BASE", "MC"))
    if config.ENABLE_STRATEGY_B:
        units.append((config.STRATEGY_B_LABEL + " - Top 100 Volume", f"database_volume{vol_suffix}.db", "entry_b", config.STRATEGY_B_LABEL, "VOL"))
        units.append((config.STRATEGY_B_LABEL + " - Top 100 MarketCap", f"database_marketcap{mc_suffix}.db", "entry_b", config.STRATEGY_B_LABEL, "MC"))
    return units


def fetch_current_prices(symbols):
    """Lấy giá hiện tại (realtime) cho danh sách symbol."""
    prices = {}
    try:
        url = "https://data-api.binance.vision/api/v3/ticker/24hr"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        if isinstance(data, list):
            for item in data:
                sym = item.get('symbol', '')
                if sym in symbols and item.get('lastPrice'):
                    try:
                        prices[sym] = float(item['lastPrice'])
                    except Exception:
                        pass
    except Exception:
        pass
    # Fallback: fetch từng cái
    missing = [s for s in symbols if s not in prices]
    for sym in missing:
        try:
            r = requests.get(f"https://data-api.binance.vision/api/v3/ticker/price?symbol={sym}", headers=HEADERS, timeout=8)
            j = r.json()
            if isinstance(j, dict) and j.get('price'):
                prices[sym] = float(j['price'])
        except Exception:
            pass
        time.sleep(0.05)
    return prices


def run_unit(unit_label, db_file, entry_key, strategy_label, data_dict, prices, today_str, actions):
    db = PortfolioDB(db_file)
    open_positions = db.get_open_positions()
    res = None

    # ============ 1. THOÁT THEO TÍN HIỆU (nến ngày) ============
    for sym, pos in list(open_positions.items()):
        res_info = data_dict.get(sym)
        if not res_info:
            continue
        if res_info['exit']:
            exit_price = res_info['close']
            pnl_usd, pnl_pct, invested = db.close_position_db(sym, exit_price, today_str, res_info['exit_reason'], source="auto")
            actions.append(
                f"🔴 *TỰ ĐÓNG (Tín hiệu thoát):* `{sym}` [{strategy_label} / {unit_label}]\n"
                f"• Lý do: {res_info['exit_reason']} | Giá: `{exit_price}$`\n"
                f"• PnL: *{pnl_pct:+.2f}%* (`{pnl_usd:+.2f}$`)"
            )
            del open_positions[sym]

    # ============ 2. STOP LOSS THEO GIÁ REALTIME ============
    for sym, pos in list(open_positions.items()):
        res_info = data_dict.get(sym)
        if not res_info:
            continue
        new_sl = res_info['hard_stop_price']
        # Cập nhật SL theo công thức mới nhất (không phải trailing)
        if pos['sl_price'] is None or abs(pos['sl_price'] - new_sl) > 1e-9:
            db.update_sl_price(sym, new_sl)
            actions.append(f"🛡 *CẬP NHẬT SL:* `{sym}` → `{new_sl:.4f}$` [{strategy_label}]")
            pos['sl_price'] = new_sl

        price = prices.get(sym)
        if price is not None and pos['sl_price'] is not None and price <= pos['sl_price']:
            pnl_usd, pnl_pct, invested = db.close_position_db(sym, pos['sl_price'], today_str, "Stop Loss", source="auto")
            actions.append(
                f"🛑 *CẮT LỖ STOP (giá chạm SL):* `{sym}` [{strategy_label} / {unit_label}]\n"
                f"• Giá realtime: `{price}$` | SL: `{pos['sl_price']:.4f}$`\n"
                f"• PnL: *{pnl_pct:+.2f}%* (`{pnl_usd:+.2f}$`)"
            )
            del open_positions[sym]

    # ============ 3. VÀO LỆNH / PYRAMID TỰ ĐỘNG (nến ngày) ============
    # Lưu ý: tín hiệu entry chỉ xử lý MỘT LẦN / ngày (guard last_entry_date == today)
    # để không ghi trùng khi chạy nhiều lần trong ngày.
    candidates = []
    for sym, res_info in data_dict.items():
        if not res_info or not res_info[entry_key]:
            continue
        if sym in open_positions:
            pos = open_positions[sym]
            if pos['pyramid_level'] < config.MAX_PYRAMID and pos['last_entry_date'] != today_str:
                fill_price = res_info['close'] + config.AUTO_ENTRY_FILL * (res_info['upper_band'] - res_info['close'])
                qty = (config.CASH_PER_ENTRY * 0.99925) / fill_price
                new_lvl = db.add_or_pyramid_position(sym, qty, config.CASH_PER_ENTRY, fill_price, today_str, source="auto", sl_price=res_info['hard_stop_price'])
                open_positions[sym]['pyramid_level'] = new_lvl
                open_positions[sym]['last_entry_date'] = today_str
                actions.append(
                    f"🟡 *TỰ NHỒI (TẦNG {new_lvl}/3):* `{sym}` [{strategy_label} / {unit_label}]\n"
                    f"• Vốn: `{config.CASH_PER_ENTRY}$` | Giá khớp ảo: `{fill_price:.4f}$`"
                )
        else:
            if not db.auto_entered_today(sym, today_str):
                candidates.append((sym, res_info))

    candidates.sort(key=lambda x: x[1]['roc_20'], reverse=True)
    available_slots = config.MAX_OPEN_COINS - len(open_positions)
    for sym, res_info in candidates[:available_slots]:
        fill_price = res_info['close'] + config.AUTO_ENTRY_FILL * (res_info['upper_band'] - res_info['close'])
        qty = (config.CASH_PER_ENTRY * 0.99925) / fill_price
        db.add_or_pyramid_position(sym, qty, config.CASH_PER_ENTRY, fill_price, today_str, source="auto", sl_price=res_info['hard_stop_price'])
        actions.append(
            f"🟢 *TỰ MUA MỚI (LẦN 1/3):* `{sym}` [{strategy_label} / {unit_label}]\n"
            f"• Vốn: `{config.CASH_PER_ENTRY}$` | Giá khớp ảo: `{fill_price:.4f}$`\n"
            f"• SL ban đầu: `{res_info['hard_stop_price']:.4f}$`"
        )


def scan_all():
    start = time.time()
    print("=== PAPER AUTO-TRADE: TỰ GHI MUA/BÁN CHO 4 ĐƠN VỊ ===")

    vol_symbols = universe.get_top_100_volume_symbols()
    mc_symbols = universe.get_top_100_marketcap_symbols()
    unique_symbols = list(set(vol_symbols + mc_symbols))

    print(f">> Phân tích {len(unique_symbols)} mã coin...")
    kline_cache = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(fetch_and_evaluate_symbol, sym): sym for sym in unique_symbols}
        for future in as_completed(futures):
            sym, res_eval = future.result()
            kline_cache[sym] = res_eval

    # Giá realtime cho các symbol có vị thế
    open_symbols = set()
    for _, db_file, _, _, _ in get_units():
        db = PortfolioDB(db_file)
        open_symbols.update(db.get_open_positions().keys())
    prices = fetch_current_prices(open_symbols) if open_symbols else {}
    print(f">> Đã lấy giá realtime cho {len(prices)} mã đang giữ.")

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime('%Y-%m-%d')
    today_vn = (now_utc + timedelta(hours=7)).strftime('%d/%m/%Y %H:%M')

    # Phân loại dữ liệu theo danh mục
    base_data = {sym: kline_cache[sym] for sym in vol_symbols if kline_cache.get(sym) is not None}
    stratb_data = {sym: kline_cache[sym] for sym in mc_symbols if kline_cache.get(sym) is not None}

    actions = []
    units = get_units()
    for label, db_file, entry_key, strat_label, category in units:
        data_dict = stratb_data if category == "MC" else base_data
        run_unit(label, db_file, entry_key, strat_label, data_dict, prices, today_str, actions)

    if actions:
        body = "\n\n".join(actions)
    else:
        body = "😴 Không có giao dịch mới. Tiếp tục nắm giữ."

    header = (
        f"🤖 *PAPER AUTO-TRADE* | Mode: `{config.MODE}`\n"
        f"🗓 Lúc: `{today_vn}`\n" + "="*30 + "\n"
    )

    # Cấu phần FUTURES ÁO: chạy cùng giờ scan H4 (đóng nến 0/4/8/12/16/20 UTC),
    # gộp kết quả vào cùng báo cáo Telegram thay vì gửi tin riêng.
    # Chỉ chạy trên máy local (state file + fapi persistent); GitHub Actions bỏ qua
    # vì runner không commit paper_state.json và fapi chưa xác nhận chạy được.
    futures_text = None
    if (
        config.ENABLE_AUTO_TRADE
        and config.ENABLE_FUTURES_AUTO_TRADE
        and not os.environ.get("GITHUB_ACTIONS")
    ):
        try:
            import futures_paper
            futures_text = futures_paper.scan_futures(notify_tg=False)
        except Exception as e:
            futures_text = None
            print(f"[FUTURES] lỗi cấu phần: {e}", flush=True)

    if futures_text:
        body = body + "\n\n---\n" + futures_text

    notifier.send_telegram_alert(header + body)

    elapsed = time.time() - start
    print(f"[HOÀN TẤT AUTO-TRADE TRONG {elapsed:.1f} GIÂY]")


def main():
    if not config.ENABLE_AUTO_TRADE:
        print("ENABLE_AUTO_TRADE = False -> bỏ qua (scanner tự ghi như cũ).")
        return
    scan_all()


if __name__ == "__main__":
    main()