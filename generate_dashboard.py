import sqlite3
import pandas as pd
import numpy as np
import json
import os
import requests
import time
import config
from datetime import datetime

# 4 đơn vị theo dõi song song: 2 chiến lược x 2 danh mục
UNITS = [
    {"label": "Top 100 Volume",   "strategy": "BASE",          "db": "database_volume.db",         "strat_class": "base"},
    {"label": "Top 100 MarketCap", "strategy": "BASE",          "db": "database_marketcap.db",      "strat_class": "base"},
    {"label": "Top 100 Volume",   "strategy": "CHIẾN LƯỢC B",  "db": "database_volume_stratb.db",  "strat_class": "stratb"},
    {"label": "Top 100 MarketCap", "strategy": "CHIẾN LƯỢC B",  "db": "database_marketcap_stratb.db", "strat_class": "stratb"},
]

def load_unit_data(db_file, label, strategy):
    conn = sqlite3.connect(db_file)
    try:
        trades_df = pd.read_sql_query('SELECT * FROM trade_history', conn)
        pos_df = pd.read_sql_query('SELECT * FROM positions', conn)
    except Exception:
        trades_df = pd.DataFrame()
        pos_df = pd.DataFrame()
    conn.close()
    trades_df['account'] = label
    trades_df['strategy'] = strategy
    pos_df['account'] = label
    pos_df['strategy'] = strategy
    return trades_df, pos_df

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def fetch_current_prices(symbols):
    """Lấy giá hiện tại (realtime) cho danh sách symbol."""
    prices = {}
    symbols = list(set(symbols))
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


def compute_unit_asset(pos_df, prices):
    """Chi tiết từng mã đang giữ + tổng tài sản của đơn vị (tiền mặt + giá trị coin)."""
    cap = config.TOTAL_PORTFOLIO_CAP
    rows = []
    deployed = 0.0
    coin_value = 0.0
    for _, r in pos_df.iterrows():
        qty = float(r['total_qty'])
        avg = float(r['avg_entry_price'])
        invested = float(r['total_invested'])
        cur = prices.get(r['symbol'], avg)
        value = qty * cur
        pnl = value - invested
        pnl_pct = (pnl / invested * 100) if invested else 0.0
        sl_txt = f"${r['sl_price']:.4f}" if pd.notna(r.get('sl_price')) and r['sl_price'] is not None else "—"
        rows.append({
            'symbol': r['symbol'], 'qty': qty, 'avg': avg, 'cur': cur,
            'value': value, 'invested': invested, 'pnl': pnl, 'pnl_pct': pnl_pct,
            'sl': sl_txt, 'level': int(r['pyramid_level']),
            'source': str(r.get('source') or 'manual'),
        })
        deployed += invested
        coin_value += value
    cash = max(0.0, cap - deployed)
    total_assets = cash + coin_value
    unrealized = coin_value - deployed
    return rows, {
        'cap': cap, 'deployed': deployed, 'cash': cash, 'coin_value': coin_value,
        'total_assets': total_assets, 'unrealized': unrealized,
    }


def compute_metrics(trades_df, pos_df):
    total_trades = len(trades_df)
    winning = len(trades_df[trades_df['pnl_usd'] > 0]) if total_trades > 0 else 0
    losing = total_trades - winning
    winrate = (winning / total_trades * 100) if total_trades > 0 else 0.0
    total_pnl = trades_df['pnl_usd'].sum() if total_trades > 0 else 0.0
    win_sum = trades_df[trades_df['pnl_usd'] > 0]['pnl_usd'].sum() if total_trades > 0 else 0.0
    loss_sum = abs(trades_df[trades_df['pnl_usd'] <= 0]['pnl_usd'].sum()) if total_trades > 0 else 0.0
    pf = (win_sum / loss_sum) if loss_sum > 0 else (99.0 if win_sum > 0 else 0.0)
    avg_win = trades_df[trades_df['pnl_usd'] > 0]['pnl_usd'].mean() if winning > 0 else 0.0
    avg_loss = trades_df[trades_df['pnl_usd'] <= 0]['pnl_usd'].mean() if losing > 0 else 0.0
    rr = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
    return {
        'total_trades': total_trades, 'winning': winning, 'losing': losing,
        'winrate': winrate, 'total_pnl': total_pnl, 'profit_factor': pf,
        'avg_win': avg_win, 'avg_loss': avg_loss, 'rr_ratio': rr,
        'open_count': len(pos_df)
    }

def render_unit_kpi(unit, m, asset_rows, asset):
    strat_badge = (
        f'<span class="badge stratb">CHIẾN LƯỢC B</span>'
        if unit['strategy'] == 'CHIẾN LƯỢC B'
        else '<span class="badge">BASE</span>'
    )
    pnl_class = "positive" if m['total_pnl'] >= 0 else "negative"
    row_badges = {
        'auto': '<span class="badge auto">TỰ ĐỘNG</span>',
        'manual': '<span class="badge manual">THỦ CÔNG</span>',
    }
    coin_rows = ""
    for r in asset_rows:
        pnl_cls = "positive" if r['pnl'] >= 0 else "negative"
        coin_rows += f"""
            <tr>
                <td><strong>{r['symbol']}</strong> <span class="pyramid-badge">Tầng {r['level']}/3</span></td>
                <td>{r['qty']:.4f}</td>
                <td>${r['avg']:.4f}</td>
                <td>${r['cur']:.4f}</td>
                <td>${r['value']:.2f}</td>
                <td>{row_badges.get(r['source'], row_badges['manual'])}</td>
                <td class="{pnl_cls}">{r['pnl_pct']:+.2f}%</td>
                <td class="{pnl_cls}"><strong>{r['pnl']:+,.2f}$</strong></td>
            </tr>"""
    if not coin_rows:
        coin_rows = "<tr><td colspan='8' style='text-align:center; padding:24px; color:#888;'>Chưa có mã nào đang giữ trong đơn vị này.</td></tr>"

    total_pnl_all = m['total_pnl'] + asset['unrealized']
    total_pnl_all_cls = "positive" if total_pnl_all >= 0 else "negative"
    return f"""
    <div class="unit-block">
        <div class="unit-header">
            <h3>🎯 {unit['label']}</h3>
            {strat_badge}
        </div>
        <div class="asset-summary">
            <div class="asset-item">
                <div class="kpi-title">TỔNG TÀI SẢN (TIỀN MẶT + COIN)</div>
                <div class="kpi-value {pnl_class if asset['total_assets'] >= asset['cap'] else 'negative'}">${asset['total_assets']:,.2f}</div>
                <div class="kpi-desc">Vốn trần: ${asset['cap']:,.0f} | Đã dùng: ${asset['deployed']:,.2f}</div>
            </div>
            <div class="asset-item">
                <div class="kpi-title">TIỀN MẶT KHẢ DỤNG</div>
                <div class="kpi-value" style="color: var(--accent-blue);">${asset['cash']:,.2f}</div>
                <div class="kpi-desc">{asset['open_n']} mã đang giữ</div>
            </div>
            <div class="asset-item">
                <div class="kpi-title">GIÁ TRỊ COIN HIỆN TẠI</div>
                <div class="kpi-value" style="color: #ffb800;">${asset['coin_value']:,.2f}</div>
                <div class="kpi-desc">Theo giá realtime</div>
            </div>
            <div class="asset-item">
                <div class="kpi-title">LỢI NHUẬN DANH MỤC (ĐÃ CHỐT + CHƯA CHỐT)</div>
                <div class="kpi-value {total_pnl_all_cls}">{total_pnl_all:+,.2f}$</div>
                <div class="kpi-desc">Đã chốt: ${m['total_pnl']:+,.2f} | Chưa chốt: ${asset['unrealized']:+,.2f}</div>
            </div>
        </div>
        <div class="coin-table-container">
            <div class="coin-table-title">💼 CHI TIẾT TỪNG MÃ TRONG DANH MỤC</div>
            <table>
                <thead>
                    <tr>
                        <th>MÃ COIN</th>
                        <th>SỐ LƯỢNG</th>
                        <th>GIÁ MUA TB</th>
                        <th>GIÁ HIỆN TẠI</th>
                        <th>GIÁ TRỊ HIỆN TẠI</th>
                        <th>NGUỒN</th>
                        <th>LỜI/LỖ %</th>
                        <th>LỜI/LỖ $</th>
                    </tr>
                </thead>
                <tbody>
                    {coin_rows}
                </tbody>
            </table>
        </div>
        <div class="kpi-subgrid">
            <div class="kpi-card">
                <div class="kpi-title">Lợi Nhuận Đã Chốt</div>
                <div class="kpi-value {pnl_class}">${m['total_pnl']:+,.2f}</div>
                <div class="kpi-desc">{m['total_trades']} lệnh đã đóng</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Win Rate</div>
                <div class="kpi-value" style="color: var(--accent-blue);">{m['winrate']:.1f}%</div>
                <div class="kpi-desc">{m['winning']} Thắng / {m['losing']} Thua</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Profit Factor</div>
                <div class="kpi-value" style="color: #ffb800;">{m['profit_factor']:.2f}</div>
                <div class="kpi-desc">Đang giữ: {m['open_count']} mã</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Tỷ Lệ R:R</div>
                <div class="kpi-value" style="color: var(--accent-purple);">{m['rr_ratio']:.2f} : 1</div>
                <div class="kpi-desc">Lãi TB +${m['avg_win']:.1f} | Lỗ TB -${abs(m['avg_loss']):.1f}</div>
            </div>
        </div>
    </div>
    """

def render_strategy_logic():
    """Mô tả chi tiết logic từng chiến lược (BASE & CHIẾN LƯỢC B) để tiện đánh giá."""
    bb = config.BB_LEN
    mult = config.BB_MULT
    smas = "50/100/150/200"
    sma_cond = "Giá đóng trên SMA 50, 100, 150, 200 (SMA không có dữ liệu thì bỏ qua điều kiện đó)"
    fill_pct = (0.99925 * 100) - 100
    fee_txt = "phí 0.075%"
    sl_txt = "0.99 × max(lower band, các SMA nằm dưới giá đóng)"

    base_blocks = [
        ("📊", "Chỉ báo kỹ thuật",
         f"Bollinger Envelopes 24/7 theo {bb} phiên (bội số {mult}σ), tính trên HIGH/LOW thay vì close:\n"
         f"• Băng trên = SMA{bb}(HIGH) + {mult}×σ(HIGH)\n"
         f"• Băng dưới = SMA{bb}(LOW) − {mult}×σ(LOW)\n"
         f"• Baseline = trung bình (upper + lower)"),
        ("📈", "Tín hiệu VÀO LỆNH (Mua mới hoặc nhồi)",
         f"Nến hôm qua đủ điều kiện:\n"
         f"• {sma_cond}\n"
         f"• Hôm trước đóng ≤ Băng trên, hôm nay đóng > Băng trên (vượt kênh Bollinger)\n"
         f"→ Mua mới $50, hoặc nhồi thêm tầng nếu mã đang giữ (tối đa {config.MAX_PYRAMID} tầng, mỗi tầng ${config.CASH_PER_ENTRY:.0f})."),
        ("📉", "Tín hiệu THOÁT LỆNH (Bán hết)",
         "Nến đóng cắt xuống dưới 1 trong các mức sau:\n"
         "• Băng dưới Bollinger\n"
         "• SMA 50, 100, 150 hoặc 200\n"
         "→ Đóng toàn bộ vị thế và ghi nhận PnL."),
        ("🛡", "Cắt lỗ treo (Hard Stop)",
         f"Áp dụng cho mọi lệnh đang giữ, cập nhật mỗi lần quét:\n"
         f"• Giá SL = {sl_txt}\n"
         f"• Nếu giá realtime ≤ SL → đóng lệnh ngay, không chờ nến. Khi giá tăng, SL tự nâng theo (bám sát đáy của SMA dưới giá)."),
        ("💼", "Quản lý vốn",
         f"• {config.MAX_OPEN_COINS} mã mở tối đa song song\n"
         f"• ${config.CASH_PER_ENTRY:.0f}/lệnh, tối đa {config.MAX_PYRAMID} tầng ⇒ ${config.CASH_PER_ENTRY*config.MAX_PYRAMID:.0f}/mã\n"
         f"• Trần vốn danh mục ${config.TOTAL_PORTFOLIO_CAP:.0f}\n"
         f"• Chi phí mua {fee_txt} trên mỗi lệnh (giá khớp ~ tại giữa Close và Băng trên khi tự động ảo)."),
    ]

    blocks_b = [
        ("🧪", "Nền tảng",
         "Kế thừa 100% logic BASE (chỉ báo, vào/thoát, pyramid, SL) nhưng thêm bộ lọc rủi ro trước khi mua."),
        ("🚦", "Bộ lọc tránh đuổi đỉnh",
         f"• ROC 5 ngày < {config.STRATEGY_B_MAX_ROC5:.0f}% (loại coin tăng quá nóng trong 5 phiên)\n"
         f"• ROC 20 ngày < {config.STRATEGY_B_MAX_ROC20:.0f}% (loại coin bùng nổ trong 20 phiên)"),
        ("🛡", "Bộ lọc biến động",
         f"• ATR 14 phiên < {config.STRATEGY_B_MAX_ATR_PCT:.1f}% (chỉ mua coin biến động thấp để giảm rủi ro giật giá)\n"
         f"• Bất kỳ lọc nào vi phạm đều chặn lệnh mua (AND logic)."),
        ("💾", "Dữ liệu riêng",
         f"Toàn bộ lệnh lưu DB riêng (`*_stratb.db`), không đụng dữ liệu/ghi lịch sử của BASE."),
    ]

    def build_card(title, color, subtitle, blocks):
        rows = "".join(
            f"<div class='logic-row'><div class='logic-icon'>{icon}</div><div class='logic-body'><div class='logic-row-title'>{t}</div><div class='logic-row-desc'>{d.replace(chr(10), '<br>')}</div></div></div>"
            for icon, t, d in blocks
        )
        return f"""
        <div class="logic-card">
            <div class="logic-header" style="border-left-color: {color};">
                <div>
                    <div class="logic-title">{title}</div>
                    <div class="logic-subtitle">{subtitle}</div>
                </div>
            </div>
            {rows}
        </div>"""

    perf_base = ("Đối chứng từ config: chuẩn so sánh với CHIẾN LƯỢC B")
    cards = [build_card("STRATEGY BASE", "#00b4d8", perf_base, base_blocks)]
    if config.ENABLE_STRATEGY_B:
        cards.append(build_card("CHIẾN LƯỢC B", "#c084fc",
                                "BASE + bộ lọc rủi ro để tránh đuổi đỉnh & coin biến động cao (backtest PnL +$1,659, WR 28.6%, PF 6.63 vs BASE PnL +$1,315, WR 18.8%, PF 2.27)",
                                blocks_b))
    return f"<div class='section-title'>LOGIC CHIẾN LƯỢC (TÓM TẮT ĐỂ ĐÁNH GIÁ)</div><div class='logic-grid'>" + "".join(cards) + "</div>"

def generate_dashboard():
    # 1. Load & tính chỉ số cho 4 đơn vị
    units_data = []
    all_trades_list = []
    all_pos_list = []
    for u in UNITS:
        t, p = load_unit_data(u['db'], u['label'], u['strategy'])
        m = compute_metrics(t, p)
        units_data.append({'unit': u, 'metrics': m, 'pos_df': p})
        if len(t): all_trades_list.append(t)
        if len(p): all_pos_list.append(p)

    all_trades = pd.concat(all_trades_list, ignore_index=True) if all_trades_list else pd.DataFrame()
    all_pos = pd.concat(all_pos_list, ignore_index=True) if all_pos_list else pd.DataFrame()

    # 1b. Fetch giá realtime cho toàn bộ mã đang giữ
    open_symbols = set(all_pos['symbol']) if len(all_pos) > 0 else set()
    prices = fetch_current_prices(open_symbols)

    # 1c. Tính tài sản từng đơn vị (tiền mặt + coin theo giá hiện tại)
    for ud in units_data:
        rows, asset = compute_unit_asset(ud['pos_df'], prices)
        asset['open_n'] = len(rows)
        ud['asset_rows'] = rows
        ud['asset'] = asset

    # 2. Tổng hợp toàn danh mục
    total_trades = len(all_trades)
    winning_trades = len(all_trades[all_trades['pnl_usd'] > 0]) if total_trades > 0 else 0
    losing_trades = total_trades - winning_trades
    winrate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    total_pnl = all_trades['pnl_usd'].sum() if total_trades > 0 else 0.0
    win_sum = all_trades[all_trades['pnl_usd'] > 0]['pnl_usd'].sum() if total_trades > 0 else 0.0
    loss_sum = abs(all_trades[all_trades['pnl_usd'] <= 0]['pnl_usd'].sum()) if total_trades > 0 else 0.0
    profit_factor = (win_sum / loss_sum) if loss_sum > 0 else (99.0 if win_sum > 0 else 0.0)
    avg_win = all_trades[all_trades['pnl_usd'] > 0]['pnl_usd'].mean() if winning_trades > 0 else 0.0
    avg_loss = all_trades[all_trades['pnl_usd'] <= 0]['pnl_usd'].mean() if losing_trades > 0 else 0.0
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

    total_deployed = sum(ud['asset']['deployed'] for ud in units_data)
    total_cash = sum(ud['asset']['cash'] for ud in units_data)
    total_coin_value = sum(ud['asset']['coin_value'] for ud in units_data)
    total_assets_all = sum(ud['asset']['total_assets'] for ud in units_data)
    total_unrealized = sum(ud['asset']['unrealized'] for ud in units_data)
    total_pnl_all = total_pnl + total_unrealized
    grand_cap = config.TOTAL_PORTFOLIO_CAP * len(UNITS)

    # 3. Render 4 cụm KPI riêng
    unit_sections = "".join(render_unit_kpi(ud['unit'], ud['metrics'], ud['asset_rows'], ud['asset']) for ud in units_data)
    strategy_logic_html = render_strategy_logic()

    # 4. Bảng lệnh đã đóng (có badge chiến lược)
    def strategy_badge(strategy):
        if strategy == 'CHIẾN LƯỢC B':
            return '<span class="badge stratb">CHIẾN LƯỢC B</span>'
        return '<span class="badge">BASE</span>'

    def source_badge(source):
        if str(source or 'manual') == 'auto':
            return '<span class="badge auto">TỰ ĐỘNG</span>'
        return '<span class="badge manual">THỦ CÔNG</span>'

    trades_rows = ""
    if total_trades > 0:
        for _, r in all_trades.iterrows():
            pnl_class = "positive" if r['pnl_usd'] >= 0 else "negative"
            trades_rows += f"""
            <tr>
                <td><span class="badge acc">{r['account']}</span></td>
                <td>{strategy_badge(r['strategy'])}</td>
                <td>{source_badge(r.get('source'))}</td>
                <td><strong>{r['symbol']}</strong></td>
                <td>{r['entry_date']}</td>
                <td>{r['exit_date']}</td>
                <td>${r['invested']:.2f}</td>
                <td>${r['exit_price']:.4f}</td>
                <td class="{pnl_class}">{r['pnl_pct']:+.2f}%</td>
                <td class="{pnl_class}"><strong>${r['pnl_usd']:+.2f}</strong></td>
                <td>{r.get('reason', 'Kỹ thuật')}</td>
            </tr>
            """
    else:
        trades_rows = "<tr><td colspan='11' style='text-align:center; padding:30px; color:#888;'>Chưa có lệnh đóng nào.</td></tr>"

    active_rows = ""
    if len(all_pos) > 0:
        for _, r in all_pos.iterrows():
            sl_txt = f"${r['sl_price']:.4f}" if pd.notna(r.get('sl_price')) and r['sl_price'] is not None else "—"
            active_rows += f"""
            <tr>
                <td><span class="badge acc">{r['account']}</span></td>
                <td>{strategy_badge(r['strategy'])}</td>
                <td>{source_badge(r.get('source'))}</td>
                <td><strong>{r['symbol']}</strong></td>
                <td><span class="pyramid-badge">Tầng {r['pyramid_level']}/3</span></td>
                <td>${r['total_invested']:.2f}</td>
                <td>${r['avg_entry_price']:.4f}</td>
                <td>{sl_txt}</td>
                <td>{r['first_entry_date']}</td>
                <td>{r['last_entry_date']}</td>
            </tr>
            """
    else:
        active_rows = "<tr><td colspan='10' style='text-align:center; padding:30px; color:#888;'>Hiện không có vị thế nào đang mở.</td></tr>"

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Crypto Portfolio 360 Analytics Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-main: #0b0e14;
            --bg-card: rgba(22, 27, 34, 0.85);
            --border: rgba(255, 255, 255, 0.08);
            --accent-green: #00f090;
            --accent-red: #ff3366;
            --accent-blue: #00b4d8;
            --accent-purple: #7928ca;
            --text-primary: #f0f6fc;
            --text-secondary: #8b949e;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Outfit', sans-serif; }}
        body {{
            background: var(--bg-main);
            color: var(--text-primary);
            padding: 40px 60px;
            min-height: 100vh;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }}
        .header h1 {{
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #00b4d8, #00f090);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .header .subtitle {{ color: var(--text-secondary); font-size: 14px; margin-top: 5px; }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .kpi-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            backdrop-filter: blur(10px);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}
        .kpi-card:hover {{ transform: translateY(-4px); border-color: rgba(0, 180, 216, 0.4); }}
        .kpi-title {{ font-size: 13px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }}
        .kpi-value {{ font-size: 32px; font-weight: 700; margin: 10px 0 5px; }}
        .kpi-desc {{ font-size: 13px; color: var(--text-secondary); }}

        .unit-block {{
            margin-bottom: 20px;
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            background: rgba(22, 27, 34, 0.45);
        }}
        .unit-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .unit-header h3 {{ font-size: 18px; font-weight: 600; }}
        .kpi-subgrid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
        }}
        .asset-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 18px;
        }}
        .asset-item {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 18px;
        }}
        .coin-table-container {{
            margin-bottom: 18px;
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            background: var(--bg-card);
        }}
        .coin-table-title {{
            padding: 12px 20px;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.03);
        }}

        .section-title {{
            font-size: 20px;
            font-weight: 600;
            margin: 40px 0 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-title::before {{
            content: '';
            width: 4px;
            height: 20px;
            background: var(--accent-blue);
            border-radius: 2px;
        }}

        .table-container {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            backdrop-filter: blur(10px);
            margin-bottom: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 14px;
        }}
        th {{
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 16px 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }}
        tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}

        .badge {{
            background: rgba(0, 240, 144, 0.12);
            color: var(--accent-green);
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            white-space: nowrap;
        }}
        .badge.acc {{ background: rgba(0, 180, 216, 0.15); color: var(--accent-blue); }}
        .badge.stratb {{ background: rgba(121, 40, 202, 0.2); color: #c084fc; }}
        .badge.auto {{ background: rgba(0, 240, 144, 0.12); color: var(--accent-green); }}
        .badge.manual {{ background: rgba(255, 255, 255, 0.08); color: var(--text-secondary); }}
        .pyramid-badge {{
            background: rgba(255, 184, 0, 0.15);
            color: #ffb800;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
        }}
        .positive {{ color: var(--accent-green); }}
        .negative {{ color: var(--accent-red); }}

        .helper-box {{
            background: rgba(0, 180, 216, 0.05);
            border: 1px dashed rgba(0, 180, 216, 0.3);
            border-radius: 12px;
            padding: 20px;
            margin-top: 30px;
            font-size: 14px;
            line-height: 1.6;
        }}
        .helper-box code {{
            background: rgba(255, 255, 255, 0.1);
            padding: 2px 8px;
            border-radius: 4px;
            color: var(--accent-green);
        }}

        .logic-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 10px;
        }}
        .logic-card {{
            background: rgba(22, 27, 34, 0.7);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
        }}
        .logic-header {{
            padding: 18px 24px;
            border-left: 4px solid var(--accent-blue);
            border-bottom: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.02);
        }}
        .logic-title {{ font-size: 18px; font-weight: 700; }}
        .logic-subtitle {{ font-size: 12px; color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }}
        .logic-row {{
            display: flex;
            gap: 14px;
            padding: 14px 24px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }}
        .logic-row:last-child {{ border-bottom: none; }}
        .logic-icon {{ font-size: 18px; flex-shrink: 0; }}
        .logic-row-title {{ font-weight: 600; font-size: 14px; margin-bottom: 5px; }}
        .logic-row-desc {{ font-size: 13px; color: var(--text-secondary); line-height: 1.7; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>CRYPTO PORTFOLIO 360 ANALYTICS</h1>
            <div class="subtitle">Theo dõi 4 đơn vị song song: 2 Chiến lược (BASE / CHIẾN LƯỢC B) x 2 Danh mục (Top 100 Volume / Top 100 MarketCap)</div>
        </div>
        <div style="text-align: right;">
            <div style="font-size: 13px; color: var(--text-secondary);">Cập nhật lúc:</div>
            <div style="font-weight: 600;">{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</div>
        </div>
    </div>

    <div class="section-title">TỔNG QUAN TOÀN DANH MỤC</div>
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">Tổng Tài Sản (Tiền Mặt + Coin)</div>
            <div class="kpi-value {'positive' if total_assets_all >= grand_cap else 'negative'}">${total_assets_all:,.2f}</div>
            <div class="kpi-desc">Vốn trần: ${grand_cap:,.0f} | Tiền mặt: ${total_cash:,.2f} | Coin: ${total_coin_value:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Tổng Lợi Nhuận (Đã Chốt + Chưa Chốt)</div>
            <div class="kpi-value {'positive' if total_pnl_all >= 0 else 'negative'}">${total_pnl_all:+,.2f}</div>
            <div class="kpi-desc">Đã chốt: ${total_pnl:+,.2f} | Chưa chốt: ${total_unrealized:+,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Tỷ Lệ Thắng (Win Rate)</div>
            <div class="kpi-value" style="color: var(--accent-blue);">{winrate:.1f}%</div>
            <div class="kpi-desc">{winning_trades} Thắng / {losing_trades} Thua</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Profit Factor</div>
            <div class="kpi-value" style="color: #ffb800;">{profit_factor:.2f}</div>
            <div class="kpi-desc">Tổng lãi gộp / Tổng lỗ gộp</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Tỷ Lệ R:R Thực Tế</div>
            <div class="kpi-value" style="color: var(--accent-purple);">{rr_ratio:.2f} : 1</div>
            <div class="kpi-desc">Lãi TB: +${avg_win:.1f} | Lỗ TB: -${abs(avg_loss):.1f}</div>
        </div>
    </div>

    <div class="section-title">HIỆU SUẤT THEO CHIẾN LƯỢC & DANH MỤC (4 ĐƠN VỊ)</div>
    {unit_sections}

    {strategy_logic_html}

    <div class="section-title">Vị Thế Đang Nắm Giữ (Active Positions)</div>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>TÀI KHOẢN</th>
                    <th>CHIẾN LƯỢC</th>
                    <th>NGUỒN</th>
                    <th>CẶP COIN</th>
                    <th>TẦNG PYRAMID</th>
                    <th>VỐN ĐÃ VÀO</th>
                    <th>GIÁ VỐN TRUNG BÌNH</th>
                    <th>MỨC CẮT LỖ (SL)</th>
                    <th>NGÀY VÀO ĐẦU TIÊN</th>
                    <th>LẦN NHỒI GẦN NHẤT</th>
                </tr>
            </thead>
            <tbody>
                {active_rows}
            </tbody>
        </table>
    </div>

    <div class="section-title">Lịch Sử Lệnh Đã Đóng (Closed Trades History)</div>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>TÀI KHOẢN</th>
                    <th>CHIẾN LƯỢC</th>
                    <th>NGUỒN</th>
                    <th>CẶP COIN</th>
                    <th>NGÀY MUA</th>
                    <th>NGÀY BÁN</th>
                    <th>VỐN ĐẦU TƯ</th>
                    <th>GIÁ BÁN</th>
                    <th>TỶ SUẤT (%)</th>
                    <th>LỜI/LỖ ($)</th>
                    <th>LÝ DO THOÁT</th>
                </tr>
            </thead>
            <tbody>
                {trades_rows}
            </tbody>
        </table>
    </div>

    <div class="helper-box">
        💡 <strong>CÁCH GHI NHẬN LỆNH TAY NHANH CHÓNG TỪ TERMINAL:</strong><br>
        • Mua mới hoặc nhồi lệnh: <code>python log_trade.py --account volume --strategy base --action buy --symbol SUI --price 3.25 --cash 50</code><br>
        • Nhồi lệnh chiến lược B: <code>python log_trade.py --account volume --strategy stratb --action buy --symbol SUI --price 3.25 --cash 50</code><br>
        • Bán chốt lời / cắt lỗ: <code>python log_trade.py --account volume --strategy base --action sell --symbol SUI --price 4.10 --reason "Chốt lời"</code><br>
        • Tự động tạo lại báo cáo mới nhất: <code>python generate_dashboard.py</code>
    </div>
</body>
</html>
"""
    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ Đã tạo thành công trang báo cáo: dashboard.html")

if __name__ == "__main__":
    generate_dashboard()