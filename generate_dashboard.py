import sqlite3
import pandas as pd
import numpy as np
import json
import os
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

def render_unit_kpi(unit, m):
    strat_badge = (
        f'<span class="badge stratb">CHIẾN LƯỢC B</span>'
        if unit['strategy'] == 'CHIẾN LƯỢC B'
        else '<span class="badge">BASE</span>'
    )
    pnl_class = "positive" if m['total_pnl'] >= 0 else "negative"
    return f"""
    <div class="unit-block">
        <div class="unit-header">
            <h3>🎯 {unit['label']}</h3>
            {strat_badge}
        </div>
        <div class="kpi-subgrid">
            <div class="kpi-card">
                <div class="kpi-title">Lợi Nhuận Net</div>
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

def generate_dashboard():
    # 1. Load & tính chỉ số cho 4 đơn vị
    units_data = []
    all_trades_list = []
    all_pos_list = []
    for u in UNITS:
        t, p = load_unit_data(u['db'], u['label'], u['strategy'])
        m = compute_metrics(t, p)
        units_data.append({'unit': u, 'metrics': m})
        if len(t): all_trades_list.append(t)
        if len(p): all_pos_list.append(p)

    all_trades = pd.concat(all_trades_list, ignore_index=True) if all_trades_list else pd.DataFrame()
    all_pos = pd.concat(all_pos_list, ignore_index=True) if all_pos_list else pd.DataFrame()

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

    # 3. Render 4 cụm KPI riêng
    unit_sections = "".join(render_unit_kpi(ud['unit'], ud['metrics']) for ud in units_data)

    # 4. Bảng lệnh đã đóng (có badge chiến lược)
    def strategy_badge(strategy):
        if strategy == 'CHIẾN LƯỢC B':
            return '<span class="badge stratb">CHIẾN LƯỢC B</span>'
        return '<span class="badge">BASE</span>'

    trades_rows = ""
    if total_trades > 0:
        for _, r in all_trades.iterrows():
            pnl_class = "positive" if r['pnl_usd'] >= 0 else "negative"
            trades_rows += f"""
            <tr>
                <td><span class="badge acc">{r['account']}</span></td>
                <td>{strategy_badge(r['strategy'])}</td>
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
        trades_rows = "<tr><td colspan='10' style='text-align:center; padding:30px; color:#888;'>Chưa có lệnh đóng nào.</td></tr>"

    active_rows = ""
    if len(all_pos) > 0:
        for _, r in all_pos.iterrows():
            active_rows += f"""
            <tr>
                <td><span class="badge acc">{r['account']}</span></td>
                <td>{strategy_badge(r['strategy'])}</td>
                <td><strong>{r['symbol']}</strong></td>
                <td><span class="pyramid-badge">Tầng {r['pyramid_level']}/3</span></td>
                <td>${r['total_invested']:.2f}</td>
                <td>${r['avg_entry_price']:.4f}</td>
                <td>{r['first_entry_date']}</td>
                <td>{r['last_entry_date']}</td>
            </tr>
            """
    else:
        active_rows = "<tr><td colspan='8' style='text-align:center; padding:30px; color:#888;'>Hiện không có vị thế nào đang mở.</td></tr>"

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
            <div class="kpi-title">Tổng Lợi Nhuận Net</div>
            <div class="kpi-value {'positive' if total_pnl >= 0 else 'negative'}">${total_pnl:+,.2f}</div>
            <div class="kpi-desc">Lợi nhuận ròng toàn danh mục (cả 2 chiến lược)</div>
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

    <div class="section-title">Vị Thế Đang Nắm Giữ (Active Positions)</div>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>TÀI KHOẢN</th>
                    <th>CHIẾN LƯỢC</th>
                    <th>CẶP COIN</th>
                    <th>TẦNG PYRAMID</th>
                    <th>VỐN ĐÃ VÀO</th>
                    <th>GIÁ VỐN TRUNG BÌNH</th>
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