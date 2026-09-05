import sqlite3
import pandas as pd
from datetime import datetime, timezone as dt_tz, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from database import PortfolioDB
from generate_dashboard import fetch_current_prices, compute_unit_asset, render_strategy_logic

app = Flask(__name__)

UNITS = [
    {"label": "Top 100 Volume",    "strategy": "BASE",          "db": "database_volume.db",             "strat_class": "base"},
    {"label": "Top 100 MarketCap", "strategy": "BASE",          "db": "database_marketcap.db",          "strat_class": "base"},
    {"label": "Top 100 Volume",    "strategy": "CHIẾN LƯỢC B", "db": "database_volume_stratb.db",      "strat_class": "stratb"},
    {"label": "Top 100 MarketCap", "strategy": "CHIẾN LƯỢC B", "db": "database_marketcap_stratb.db",   "strat_class": "stratb"},
]

# account select value -> (db_file cho BASE, db_file cho STRATEGY B)
ACCOUNT_DB = {
    "volume":     {"base": "database_volume.db",         "stratb": "database_volume_stratb.db"},
    "marketcap":  {"base": "database_marketcap.db",      "stratb": "database_marketcap_stratb.db"},
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Trading Manager - Web Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0b0e14;
            --card-bg: rgba(22, 27, 34, 0.95);
            --border: rgba(255, 255, 255, 0.08);
            --accent-green: #00f090;
            --accent-red: #ff3366;
            --accent-blue: #00b4d8;
            --accent-gold: #ffb800;
            --text: #f0f6fc;
            --text-dim: #8b949e;
        }
        * { margin:0; padding:0; box-sizing:border-box; font-family:'Outfit', sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 30px 50px; min-height: 100vh; }
        
        .header { display:flex; justify-content:space-between; align-items:center; margin-bottom:30px; border-bottom:1px solid var(--border); padding-bottom:20px; }
        .header h1 { font-size:26px; font-weight:700; background:linear-gradient(135deg, var(--accent-blue), var(--accent-green)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
        .header .clock { font-size:13px; color:var(--text-dim); }

        .grid-layout { display:grid; grid-template-columns: 380px 1fr; gap: 30px; }

        /* Form Card */
        .form-card { background:var(--card-bg); border:1px solid var(--border); border-radius:16px; padding:24px; height:fit-content; }
        .form-title { font-size:18px; font-weight:600; margin-bottom:20px; display:flex; align-items:center; gap:8px; }
        .form-title::before { content:''; width:4px; height:18px; background:var(--accent-blue); border-radius:2px; }
        
        .form-group { margin-bottom:16px; }
        label { display:block; font-size:13px; color:var(--text-dim); margin-bottom:6px; }
        input, select { width:100%; padding:12px; background:rgba(255,255,255,0.05); border:1px solid var(--border); border-radius:8px; color:#fff; font-size:14px; outline:none; transition:border 0.2s; }
        input:focus, select:focus { border-color:var(--accent-blue); }
        
        .btn { width:100%; padding:14px; border:none; border-radius:8px; font-weight:600; font-size:15px; cursor:pointer; transition:all 0.2s; display:flex; justify-content:center; align-items:center; gap:8px; }
        .btn-buy { background:linear-gradient(135deg, #00b4d8, #00f090); color:#000; margin-top:10px; }
        .btn-buy:hover { opacity:0.9; transform:translateY(-2px); }
        .btn-sell { background:rgba(255, 51, 102, 0.15); color:var(--accent-red); border:1px solid var(--accent-red); padding:8px 14px; border-radius:6px; font-size:13px; font-weight:600; cursor:pointer; }
        .btn-sell:hover { background:var(--accent-red); color:#fff; }

        /* KPI Overview */
        .kpi-row { display:grid; grid-template-columns:repeat(4, 1fr); gap:16px; margin-bottom:24px; }
        .kpi-card { background:var(--card-bg); border:1px solid var(--border); border-radius:12px; padding:18px; }
        .kpi-name { font-size:12px; color:var(--text-dim); text-transform:uppercase; }
        .kpi-val { font-size:24px; font-weight:700; margin:6px 0; }
        .kpi-desc { font-size:12px; color:var(--text-dim); }

        /* Tables */
        .table-card { background:var(--card-bg); border:1px solid var(--border); border-radius:16px; padding:20px; margin-bottom:24px; }
        .table-title { font-size:16px; font-weight:600; margin-bottom:16px; }
        table { width:100%; border-collapse:collapse; font-size:13px; }
        th { text-align:left; padding:12px; color:var(--text-dim); border-bottom:1px solid var(--border); font-weight:500; }
        td { padding:14px 12px; border-bottom:1px solid rgba(255,255,255,0.03); }
        tr:hover td { background:rgba(255,255,255,0.02); }

        .badge { background:rgba(0,180,216,0.15); color:var(--accent-blue); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600; }
        .badge-mc { background:rgba(255,184,0,0.15); color:var(--accent-gold); }
        .badge-base { background:rgba(0,240,144,0.12); color:var(--accent-green); }
        .badge-stratb { background:rgba(121,40,202,0.2); color:#c084fc; }
        .badge-auto { background:rgba(0,240,144,0.15); color:var(--accent-green); }
        .badge-manual { background:rgba(139,148,158,0.2); color:var(--text-dim); }
        .badge-pyramid { background:rgba(0,240,144,0.15); color:var(--accent-green); padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600; }
        .pos { color:var(--accent-green); font-weight:600; }
        .neg { color:var(--accent-red); font-weight:600; }

        /* 4 cụm KPI theo đơn vị */
        .unit-block { background:var(--card-bg); border:1px solid var(--border); border-radius:16px; padding:20px; margin-bottom:18px; }
        .unit-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }
        .unit-header h3 { font-size:16px; font-weight:600; }
        .unit-kpis { display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; }
        .unit-kpis .kpi-card { padding:14px; }
        .unit-kpis .kpi-val { font-size:20px; }
        .unit-assets { display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin-bottom:14px; }
        .unit-assets .kpi-card { padding:14px; border:1px solid rgba(0, 240, 144, 0.25); background: rgba(0, 240, 144, 0.04); }
        .unit-assets .kpi-val { font-size:20px; }
        .section-title { font-size:16px; font-weight:600; margin:28px 0 14px; display:flex; align-items:center; gap:8px; }
        .section-title::before { content:''; width:4px; height:18px; background:var(--accent-blue); border-radius:2px; }

        .logic-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(400px, 1fr)); gap:16px; margin-bottom:16px; }
        .logic-card { background:rgba(22,27,34,0.7); border:1px solid var(--border); border-radius:14px; overflow:hidden; }
        .logic-header { padding:16px 18px; border-left:4px solid var(--accent-blue); border-bottom:1px solid var(--border); }
        .logic-title { font-size:16px; font-weight:700; }
        .logic-subtitle { font-size:12px; color:var(--text-dim); margin-top:4px; line-height:1.5; }
        .logic-row { display:flex; gap:12px; padding:12px 18px; border-bottom:1px solid rgba(255,255,255,0.04); }
        .logic-row:last-child { border-bottom:none; }
        .logic-icon { font-size:16px; flex-shrink:0; }
        .logic-row-title { font-weight:600; font-size:13px; margin-bottom:4px; }
        .logic-row-desc { font-size:12px; color:var(--text-dim); line-height:1.7; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>CRYPTO PORTFOLIO MANAGER</h1>
            <div style="font-size:13px; color:var(--text-dim); margin-top:4px;">Cổng nhập liệu lệnh tay & Theo dõi hiệu suất tự động</div>
        </div>
        <div class="clock">Cập nhật lúc (Giờ VN): <strong>{{ now_vn }}</strong></div>
    </div>

    <div class="grid-layout">
        <!-- FORM NHẬP LỆNH TAY -->
        <div class="form-card">
            <div class="form-title">NHẬP LỆNH TAY NHANH</div>
            <form method="POST" action="/submit-trade">
                <div class="form-group">
                    <label>Tài Khoản Giao Dịch</label>
                    <select name="account">
                        <option value="volume">Tài Khoản 1 (Top 100 Volume)</option>
                        <option value="marketcap">Tài Khoản 2 (Top 100 MarketCap)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Chiến Lược</label>
                    <select name="strategy">
                        <option value="base">BASE</option>
                        <option value="stratb">CHIẾN LƯỢC B</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Loại Lệnh</label>
                    <select name="action" id="action-select">
                        <option value="buy">MUA MỚI / NHỒI LỆNH (BUY)</option>
                        <option value="sell">BÁN CHỐT LỜI / CẮT LỖ (SELL)</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Mã Coin (Symbol)</label>
                    <input type="text" name="symbol" placeholder="VD: SUI, BTC, ETH" required autocomplete="off" style="text-transform:uppercase;">
                </div>
                <div class="form-group">
                    <label>Giá Khớp Thực Tế ($)</label>
                    <input type="number" step="any" name="price" placeholder="VD: 3.25" required>
                </div>
                <div class="form-group" id="cash-group">
                    <label>Số Tiền Vào Lệnh ($)</label>
                    <input type="number" step="any" name="cash" value="50" placeholder="Mặc định: 50$">
                </div>
                <div class="form-group" id="reason-group" style="display:none;">
                    <label>Lý Do Thoát Lệnh</label>
                    <input type="text" name="reason" placeholder="VD: Chốt lời đỉnh / Thủng Lower Band">
                </div>
                <button type="submit" class="btn btn-buy">XÁC NHẬN GHI LỆNH</button>
            </form>
        </div>

        <!-- DASHBOARD HIỆU SUẤT & DANH SÁCH -->
        <div>
            <!-- 4 CỤM KPI THEO ĐƠN VỊ (2 chiến lược x 2 danh mục) -->
            <div class="section-title">HIỆU SUẤT THEO CHIẾN LƯỢC & DANH MỤC</div>
            {% for u in units_metrics %}
            <div class="unit-block">
                <div class="unit-header">
                    <h3>🎯 {{ u.label }}</h3>
                    <span class="badge {{ 'badge-stratb' if u.strategy == 'CHIẾN LƯỢC B' else 'badge-base' }}">{{ u.strategy }}</span>
                </div>
                <!-- TỔNG TÀI SẢN ĐƠN VỊ -->
                {% set a = u.asset %}
                <div class="unit-assets">
                    <div class="kpi-card">
                        <div class="kpi-name">TỔNG TÀI SẢN (TIỀN MẶT + COIN)</div>
                        <div class="kpi-val {{ 'pos' if a.total_assets >= a.cap else 'neg' }}">${{ "{:,.2f}".format(a.total_assets) }}</div>
                        <div class="kpi-desc">Vốn trần: ${{ "{:,.0f}".format(a.cap) }} | Đã dùng: ${{ "{:,.2f}".format(a.deployed) }}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-name">TIỀN MẶT KHẢ DỤNG</div>
                        <div class="kpi-val" style="color:var(--accent-blue);">${{ "{:,.2f}".format(a.cash) }}</div>
                        <div class="kpi-desc">{{ a.open_n }} mã đang giữ</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-name">GIÁ TRỊ COIN HIỆN TẠI</div>
                        <div class="kpi-val" style="color:var(--accent-gold);">${{ "{:,.2f}".format(a.coin_value) }}</div>
                        <div class="kpi-desc">Theo giá realtime</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-name">LỢI NHUẬN DANH MỤC</div>
                        <div class="kpi-val {{ 'pos' if u.total_pnl + a.unrealized >= 0 else 'neg' }}">${{ "{:+,.2f}".format(u.total_pnl + a.unrealized) }}</div>
                        <div class="kpi-desc">Đã chốt: ${{ "{:+,.2f}".format(u.total_pnl) }} | Chưa chốt: ${{ "{:+,.2f}".format(a.unrealized) }}</div>
                    </div>
                </div>
                <!-- CHI TIẾT TỪNG MÃ -->
                <div class="table-card" style="margin-bottom:16px;">
                    <div class="table-title">💼 CHI TIẾT TỪNG MÃ TRONG DANH MỤC</div>
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
                            {% if a.open_n > 0 %}
                                {% for r in u.asset_rows %}
                                <tr>
                                    <td><strong>{{ r.symbol }}</strong> <span class="badge-pyramid">Tầng {{ r.level }}/3</span></td>
                                    <td>{{ "{:.4f}".format(r.qty) }}</td>
                                    <td>${{ "{:.4f}".format(r.avg) }}</td>
                                    <td>${{ "{:.4f}".format(r.cur) }}</td>
                                    <td>${{ "{:.2f}".format(r.value) }}</td>
                                    <td>{% if r.source == 'auto' %}<span class="badge badge-auto">TỰ ĐỘNG</span>{% else %}<span class="badge badge-manual">THỦ CÔNG</span>{% endif %}</td>
                                    <td class="{{ 'pos' if r.pnl >= 0 else 'neg' }}">{{ "{:+.2f}%".format(r.pnl_pct) }}</td>
                                    <td class="{{ 'pos' if r.pnl >= 0 else 'neg' }}"><strong>{{ "{:+,.2f}$".format(r.pnl) }}</strong></td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr><td colspan="8" style="text-align:center; color:var(--text-dim); padding:20px;">Chưa có mã nào đang giữ trong đơn vị này.</td></tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
                <div class="unit-kpis">
                    <div class="kpi-card">
                        <div class="kpi-name">Lợi Nhuận Đã Chốt</div>
                        <div class="kpi-val {{ 'pos' if u.total_pnl >= 0 else 'neg' }}">${{ "{:+,.2f}".format(u.total_pnl) }}</div>
                        <div class="kpi-desc">{{ u.total_trades }} lệnh đã đóng | {{ u.open_count }} mã đang giữ</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-name">Win Rate</div>
                        <div class="kpi-val" style="color:var(--accent-blue);">{{ "{:.1f}%".format(u.winrate) }}</div>
                        <div class="kpi-desc">{{ u.winning }} Thắng / {{ u.losing }} Thua</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-name">Profit Factor</div>
                        <div class="kpi-val" style="color:var(--accent-gold);">{{ "{:.2f}".format(u.profit_factor) }}</div>
                        <div class="kpi-desc">Lãi gộp / Lỗ gộp</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-name">Tỷ Lệ R:R</div>
                        <div class="kpi-val" style="color:#b5179e;">{{ "{:.2f} : 1".format(u.rr_ratio) }}</div>
                        <div class="kpi-desc">Lãi TB +${{ "{:.1f}".format(u.avg_win) }} | Lỗ TB -${{ "{:.1f}".format(u.avg_loss) }}</div>
                    </div>
                </div>
            </div>
            {% endfor %}

            {{ strategy_logic | safe }}

            <!-- BẢNG VỊ THẾ ĐANG MỞ -->
            <div class="table-card">
                <div class="table-title">📌 VỊ THẾ ĐANG NẮM GIỮ (ACTIVE POSITIONS)</div>
                <table>
                    <thead>
                        <tr>
                            <th>TÀI KHOẢN</th>
                            <th>CHIẾN LƯỢC</th>
                            <th>NGUỒN</th>
                            <th>MÃ COIN</th>
                            <th>PYRAMID</th>
                            <th>VỐN ĐÃ VÀO</th>
                            <th>GIÁ VỐN TB</th>
                            <th>MỨC CẮT LỖ</th>
                            <th>NGÀY VÀO</th>
                            <th>THAO TÁC</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if open_positions %}
                            {% for p in open_positions %}
                            <tr>
                                <td><span class="badge {{ 'badge-mc' if 'MarketCap' in p.account else '' }}">{{ p.account }}</span></td>
                                <td><span class="badge {{ 'badge-stratb' if p.strategy == 'CHIẾN LƯỢC B' else 'badge-base' }}">{{ p.strategy }}</span></td>
                                <td>{% if p.source == 'auto' %}<span class="badge badge-auto">TỰ ĐỘNG</span>{% else %}<span class="badge badge-manual">THỦ CÔNG</span>{% endif %}</td>
                                <td><strong>{{ p.symbol }}</strong></td>
                                <td><span class="badge-pyramid">Tầng {{ p.pyramid_level }}/3</span></td>
                                <td>${{ "{:.2f}".format(p.total_invested) }}</td>
                                <td>${{ "{:.4f}".format(p.avg_entry_price) }}</td>
                                <td>{% if p.sl_price is not none %}${{ "{:.4f}".format(p.sl_price) }}{% else %}—{% endif %}</td>
                                <td>{{ p.first_entry_date }}</td>
                                <td>
                                    <form method="POST" action="/quick-sell" style="display:inline;">
                                        <input type="hidden" name="db_file" value="{{ p.db_file }}">
                                        <input type="hidden" name="symbol" value="{{ p.symbol }}">
                                        <input type="number" step="any" name="exit_price" placeholder="Giá bán" required style="width:90px; padding:6px; margin-right:6px; font-size:12px;">
                                        <button type="submit" class="btn-sell">Bán Hết</button>
                                    </form>
                                </td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr><td colspan="10" style="text-align:center; color:var(--text-dim); padding:25px;">Chưa có vị thế nào. Hãy nhập lệnh mua mới bên trái.</td></tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>

            <!-- LỊCH SỬ GIAO DỊCH -->
            <div class="table-card">
                <div class="table-title">📜 LỊCH SỬ LỆNH ĐÃ ĐÓNG (CLOSED TRADES)</div>
                <table>
                    <thead>
                        <tr>
                            <th>TÀI KHOẢN</th>
                            <th>CHIẾN LƯỢC</th>
                            <th>NGUỒN</th>
                            <th>MÃ COIN</th>
                            <th>NGÀY VÀO</th>
                            <th>NGÀY RA</th>
                            <th>VỐN VÀO</th>
                            <th>GIÁ BÁN</th>
                            <th>TỶ SUẤT</th>
                            <th>LÃI/LỖ</th>
                            <th>LÝ DO</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% if closed_trades %}
                            {% for t in closed_trades %}
                            <tr>
                                <td><span class="badge {{ 'badge-mc' if 'MarketCap' in t.account else '' }}">{{ t.account }}</span></td>
                                <td><span class="badge {{ 'badge-stratb' if t.strategy == 'CHIẾN LƯỢC B' else 'badge-base' }}">{{ t.strategy }}</span></td>
                                <td>{% if t.source == 'auto' %}<span class="badge badge-auto">TỰ ĐỘNG</span>{% else %}<span class="badge badge-manual">THỦ CÔNG</span>{% endif %}</td>
                                <td><strong>{{ t.symbol }}</strong></td>
                                <td>{{ t.entry_date }}</td>
                                <td>{{ t.exit_date }}</td>
                                <td>${{ "{:.2f}".format(t.invested) }}</td>
                                <td>${{ "{:.4f}".format(t.exit_price) }}</td>
                                <td class="{{ 'pos' if t.pnl_usd >= 0 else 'neg' }}">{{ "{:+.2f}%".format(t.pnl_pct) }}</td>
                                <td class="{{ 'pos' if t.pnl_usd >= 0 else 'neg' }}"><strong>${{ "{:+.2f}".format(t.pnl_usd) }}</strong></td>
                                <td>{{ t.reason }}</td>
                            </tr>
                            {% endfor %}
                        {% else %}
                            <tr><td colspan="11" style="text-align:center; color:var(--text-dim); padding:25px;">Chưa có lịch sử lệnh đóng.</td></tr>
                        {% endif %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        document.getElementById('action-select').addEventListener('change', function() {
            var val = this.value;
            if (val === 'sell') {
                document.getElementById('cash-group').style.display = 'none';
                document.getElementById('reason-group').style.display = 'block';
            } else {
                document.getElementById('cash-group').style.display = 'block';
                document.getElementById('reason-group').style.display = 'none';
            }
        });
    </script>
</body>
</html>
"""

def load_db(db_file, label, strategy):
    conn = sqlite3.connect(db_file)
    try:
        t = pd.read_sql_query('SELECT * FROM trade_history', conn)
        p = pd.read_sql_query('SELECT * FROM positions', conn)
    except Exception:
        t, p = pd.DataFrame(), pd.DataFrame()
    conn.close()
    if len(t):
        t['account'] = label
        t['strategy'] = strategy
    if len(p):
        p['account'] = label
        p['strategy'] = strategy
        p['db_file'] = db_file
    return t, p

def unit_metrics(trades_df, pos_df):
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
        'total_pnl': total_pnl, 'winrate': winrate, 'winning': winning, 'losing': losing,
        'profit_factor': pf, 'avg_win': avg_win, 'avg_loss': avg_loss, 'rr_ratio': rr,
        'total_trades': total_trades, 'open_count': len(pos_df)
    }

def get_data():
    all_trades = []
    all_pos = []
    units_metrics = []
    for u in UNITS:
        t, p = load_db(u['db'], u['label'], u['strategy'])
        units_metrics.append({**u, **unit_metrics(t, p)})
        if len(t): all_trades.append(t)
        if len(p): all_pos.append(p)

    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    positions = pd.concat(all_pos, ignore_index=True) if all_pos else pd.DataFrame()

    # Giá realtime + tài sản từng đơn vị (tiền mặt + coin theo giá hiện tại)
    open_symbols = set(positions['symbol']) if len(positions) > 0 else set()
    prices = fetch_current_prices(open_symbols)
    for um in units_metrics:
        t, p = load_db(um['db'], um['label'], um['strategy'])
        rows, asset = compute_unit_asset(p, prices)
        asset['open_n'] = len(rows)
        um['asset_rows'] = rows
        um['asset'] = asset

    return {
        'units_metrics': units_metrics,
        'open_positions': positions.to_dict('records') if not positions.empty else [],
        'closed_trades': trades.to_dict('records') if not trades.empty else [],
        'strategy_logic': render_strategy_logic(),
        'now_vn': (datetime.now(dt_tz.utc) + timedelta(hours=7)).strftime('%d/%m/%Y %H:%M:%S')
    }

@app.route('/')
def index():
    data = get_data()
    return render_template_string(HTML_TEMPLATE, **data)

@app.route('/submit-trade', methods=['POST'])
def submit_trade():
    account = request.form.get('account')
    strategy = request.form.get('strategy', 'base')
    action = request.form.get('action')
    symbol = request.form.get('symbol').upper().strip()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'
    price = float(request.form.get('price'))
    cash = float(request.form.get('cash', 50))
    reason = request.form.get('reason', 'Thủ công')
    
    db_file = ACCOUNT_DB.get(account, ACCOUNT_DB["volume"]).get(strategy, ACCOUNT_DB["volume"]["base"])
    db = PortfolioDB(db_file)
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    if action == 'buy':
        qty = (cash * 0.99925) / price
        db.add_or_pyramid_position(symbol, qty, cash, price, today_str, source="manual")
    elif action == 'sell':
        db.close_position_db(symbol, price, today_str, reason, source="manual")
        
    return redirect(url_for('index'))

@app.route('/quick-sell', methods=['POST'])
def quick_sell():
    db_file = request.form.get('db_file')
    symbol = request.form.get('symbol')
    exit_price = float(request.form.get('exit_price'))
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    db = PortfolioDB(db_file)
    db.close_position_db(symbol, exit_price, today_str, "Bán Nhanh qua Web", source="manual")
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("\n🌐 KHỞI ĐỘNG CỔNG WEB QUẢN LÝ DANH MỤC CRYPTO TẠI: http://127.0.0.1:5001\n")
    app.run(host='127.0.0.1', port=5001, debug=False)
