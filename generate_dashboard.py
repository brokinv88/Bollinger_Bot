import sqlite3
import pandas as pd
import numpy as np
import json
import os
import requests
import time
import config
from datetime import datetime, timezone, timedelta

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

def load_futures_data():
    """Đọc state + trades + equity của futures paper trader (futures_paper.py)."""
    import futures_paper as fp
    data = {"enabled": config.ENABLE_FUTURES_AUTO_TRADE}
    if not data["enabled"]:
        return data
    if not os.path.exists(fp.STATE_FILE):
        data["error"] = "Chưa có paper_state.json — chạy `python futures_paper.py --scan` để khởi tạo account futures áo."
        return data
    with open(fp.STATE_FILE) as f:
        st = json.load(f)
    trades = pd.DataFrame()
    if os.path.exists(fp.TRADES_CSV):
        trades = pd.read_csv(fp.TRADES_CSV)
    equity = pd.DataFrame()
    if os.path.exists(fp.EQUITY_CSV):
        equity = pd.read_csv(fp.EQUITY_CSV)
        equity = equity.drop_duplicates(subset=["ts"]).reset_index(drop=True)
    data.update(
        equity_start=fp.EQUITY0,
        equity=st.get("equity", fp.EQUITY0),
        peak=st.get("peak", fp.EQUITY0),
        n_trades=st.get("n_trades", 0),
        max_pos=fp.MAX_POS,
        max_margin_pct=fp.MAX_MARGIN_PCT,
        lev=fp.LEV,
        positions=st.get("positions", []),
        trades=trades,
        equity_curve=equity,
        last_ts=st.get("last_ts"),
    )
    return data


def compute_futures_metrics(fd):
    t = fd.get("trades")
    if t is None or len(t) == 0:
        return {"total": 0, "win": 0, "loss": 0, "winrate": 0, "pnl": 0.0,
                "pf": 0.0, "avg_win": 0, "avg_loss": 0, "rr": 0.0,
                "by_strategy": {}}
    winning = t[t["net_usd"] > 0]
    losing = t[t["net_usd"] <= 0]
    pnl = t["net_usd"].sum()
    ws = winning["net_usd"].sum() if len(winning) else 0.0
    ls = abs(losing["net_usd"].sum()) if len(losing) else 0.0
    pf = ws / ls if ls > 0 else (99.0 if ws > 0 else 0.0)
    aw = winning["net_usd"].mean() if len(winning) else 0.0
    al = losing["net_usd"].mean() if len(losing) else 0.0
    rr = abs(aw / al) if al != 0 else 0.0
    by_strategy = t.groupby("strategy")["net_usd"].sum().to_dict()
    return {"total": len(t), "win": len(winning), "loss": len(losing),
            "winrate": len(winning) / len(t) * 100, "pnl": pnl, "pf": pf,
            "avg_win": aw, "avg_loss": al, "rr": rr, "by_strategy": by_strategy}


def fetch_futures_prices(symbols):
    """Giá realtime futures (USDT-M) — fallback spot nếu fapi fail."""
    prices = {}
    try:
        url = "https://fapi.binance.com/fapi/v1/ticker/price"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        data = resp.json()
        if isinstance(data, list):
            for item in data:
                sym = item.get("symbol", "")
                if sym in symbols and item.get("price"):
                    try:
                        prices[sym] = float(item["price"])
                    except Exception:
                        pass
    except Exception:
        pass
    missing = [s for s in symbols if s not in prices]
    if missing:
        prices.update(fetch_current_prices(missing))
    return prices


def fmt_ms(ms):
    try:
        return (pd.Timestamp(ms, unit="ms", tz="UTC") + timedelta(hours=7)).strftime("%d/%m %H:%M")
    except Exception:
        return "-"


def render_futures_section(fd):
    if not fd.get("enabled"):
        return ("<div class='section-title'>FUTURES ÁO (H4) — KẾT NỐI TÀI KHOẢN REALTIME</div>"
                "<div class='helper-box'>⚠️ Cấu phần Futures áo đang tắt (ENABLE_FUTURES_AUTO_TRADE=False) hoặc "
                "state chưa có — chạy <code>python futures_paper.py --scan</code> để khởi tạo.</div>")

    if fd.get("error"):
        return ("<div class='section-title'>FUTURES ÁO (H4)</div>"
                f"<div class='helper-box'>⚠️ {fd['error']}</div>")

    m = compute_futures_metrics(fd)

    # Giá realtime cho vị thế đang mở → equity live (realized + unrealized)
    prices = fetch_futures_prices([p["symbol"] for p in fd["positions"]]) if fd["positions"] else {}
    unreal = sum(
        p["direction"] * (prices.get(p["symbol"], p["entry_px"]) - p["entry_px"])
        / p["entry_px"] * float(p["notional"])
        for p in fd["positions"]
    )
    eq = fd["equity"] + unreal
    start = fd["equity_start"]
    curve = fd.get("equity_curve")
    curve_peak = float(curve["equity"].max()) if curve is not None and len(curve) else 0.0
    peak = max(fd["peak"], curve_peak, eq)
    total_pnl = eq - start
    total_pnl_cls = "positive" if total_pnl >= 0 else "negative"

    # Max drawdown từ equity curve (snapshot là equity theo giá) kèm điểm live hiện tại
    mdd_pct = 0.0
    if curve is not None and len(curve):
        eqs = np.concatenate([curve["equity"].to_numpy(dtype=float), np.array([eq])])
        run_peak = np.maximum.accumulate(eqs)
        dd = (eqs / run_peak - 1.0) * 100.0
        mdd_pct = float(dd.min())
    elif eq < start:
        mdd_pct = (eq / start - 1.0) * 100.0
    mdd_cls = "negative" if mdd_pct < 0 else "positive"

    margin_usd = sum(float(p.get("margin", 0) or 0) for p in fd["positions"])
    margin_pct = margin_usd / eq * 100 if eq > 0 else 0
    dn = m["by_strategy"].get("DON", 0)
    kt = m["by_strategy"].get("KELT", 0)

    # Bảng lệnh đang mở
    pos_rows = ""
    if fd["positions"]:
        for p in fd["positions"]:
            side = "LONG" if p["direction"] == 1 else "SHORT"
            is_long = p["direction"] == 1
            cur = prices.get(p["symbol"], p["entry_px"])
            gross = p["direction"] * (cur - p["entry_px"]) / p["entry_px"] * 100
            pnl_cls = "positive" if gross >= 0 else "negative"
            pos_rows += f"""
            <tr>
                <td><strong>{p['symbol']}</strong></td>
                <td><span class="badge {'auto' if is_long else 'manual'}">{side}</span></td>
                <td><span class="badge stratb">{p['strategy']}</span></td>
                <td>${p['entry_px']:.4f}</td>
                <td>${cur:.4f}</td>
                <td>${p['notional']:,.0f}</td>
                <td>${p['margin']:,.0f}</td>
                <td class="{pnl_cls}"><strong>{gross:+.2f}%</strong></td>
                <td>{fmt_ms(p['entry_time'])}</td>
            </tr>"""
    else:
        pos_rows = "<tr><td colspan='9' style='text-align:center; padding:24px; color:#888;'>Không có vị thế mở.</td></tr>"

    trd_rows = ""
    if m["total"] > 0:
        t = fd["trades"].sort_values("exit_time", ascending=False).head(25)
        for _, r in t.iterrows():
            cls = "positive" if r["net_usd"] >= 0 else "negative"
            side = "LONG" if r["direction"] == 1 else "SHORT"
            pnl_pct = r["net_usd"] / r["notional"] * 100 if r["notional"] else 0.0
            trd_rows += f"""
            <tr>
                <td><strong>{r['symbol']}</strong></td>
                <td><span class="badge {'auto' if r['direction'] == 1 else 'manual'}">{side}</span></td>
                <td><span class="badge stratb">{r['strategy']}</span></td>
                <td>{fmt_ms(r['entry_time'])}</td>
                <td>{fmt_ms(r['exit_time'])}</td>
                <td>${r['entry_px']:.4f} → ${r['exit_px']:.4f}</td>
                <td>{r['reason']}</td>
                <td class="{cls}"><strong>{r['net_usd']:+,.2f}$</strong></td>
                <td class="{cls}">{pnl_pct:+.2f}%</td>
            </tr>"""
    else:
        trd_rows = "<tr><td colspan='9' style='text-align:center; padding:24px; color:#888;'>Chưa có lệnh nào đóng.</td></tr>"

    last_scan = fmt_ms(fd["last_ts"]) if fd.get("last_ts") else "-"
    return f"""<div class="section-title">FUTURES ÁO (HỢP ĐỒNG TƯƠNG LAI H4)</div>
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">Tài Khoản (Vốn + Lời/Lỗ)</div>
            <div class="kpi-value {total_pnl_cls}">${eq:,.2f}</div>
            <div class="kpi-desc">Vốn bắt đầu: ${start:,.0f} | Peak: ${peak:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Tổng Lợi Nhuận</div>
            <div class="kpi-value {total_pnl_cls}">{total_pnl:+,.2f}$</div>
            <div class="kpi-desc">({total_pnl/start*100:+.2f}%) | DON: {dn:+,.0f}$ | KELT: {kt:+,.0f}$</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Max Drawdown</div>
            <div class="kpi-value {mdd_cls}">{mdd_pct:.2f}%</div>
            <div class="kpi-desc">Từ đỉnh cao nhất (equity theo giá, cập nhật mỗi scan)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Vị Thế Mở / Margin</div>
            <div class="kpi-value" style="color: var(--accent-blue);">{len(fd['positions'])}/{fd['max_pos']}</div>
            <div class="kpi-desc">Đã dùng margin: ${margin_usd:,.0f} = {margin_pct:.1f}% (trần {fd['max_margin_pct']*100:.0f}%)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Tỷ Lệ Thắng Futures</div>
            <div class="kpi-value" style="color: #ffb800;">{m['winrate']:.1f}%</div>
            <div class="kpi-desc">{m['win']} Thắng / {m['loss']} Thua | PF {m['pf']:.2f} | R:R {m['rr']:.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Đòn Bẩy / Scan gần nhất</div>
            <div class="kpi-value" style="color: var(--accent-purple);">{fd['lev']}x</div>
            <div class="kpi-desc">Lần scan H4 cuối: {last_scan}</div>
        </div>
    </div>

    <div class="section-title">Vị Thế Futures Đang Mở</div>
    <div class="table-container">
        <table>
            <thead><tr>
                <th>PAIR</th><th>HƯỚNG</th><th>CHIẾN LƯỢC</th><th>GIÁ VÀO</th><th>GIÁ HIỆN TẠI</th>
                <th>NOTIONAL</th><th>MARGIN</th><th>P/L %</th><th>NGÀY VÀO</th>
            </tr></thead>
            <tbody>{pos_rows}</tbody>
        </table>
    </div>

    <div class="section-title">Giao Dịch Futures Gần Đây (25 lệnh)</div>
    <div class="table-container">
        <table>
            <thead><tr>
                <th>PAIR</th><th>HƯỚNG</th><th>CHIẾN LƯỢC</th><th>VÀO</th><th>THOÁT</th>
                <th>GIÁ</th><th>LÝ DO</th><th>P/L ($)</th><th>P/L %</th>
            </tr></thead>
            <tbody>{trd_rows}</tbody>
        </table>
    </div>"""


def load_bridge_data():
    """Đọc state + trades + equity + orders của live_bridge (dry-run/real)."""
    import live_bridge as lb
    data = {"enabled": config.ENABLE_FUTURES_AUTO_TRADE}
    if not data["enabled"]:
        return data
    if not os.path.exists(lb.BRIDGE_STATE):
        data["error"] = "Chưa có bridge_state.json — chạy `python live_bridge.py --seed` rồi `--scan`."
        return data
    with open(lb.BRIDGE_STATE) as f:
        st = json.load(f)
    trades = pd.DataFrame()
    if os.path.exists(lb.BRIDGE_TRADES):
        trades = pd.read_csv(lb.BRIDGE_TRADES)
    equity = pd.DataFrame()
    if os.path.exists(lb.BRIDGE_EQUITY):
        equity = pd.read_csv(lb.BRIDGE_EQUITY)
        equity = equity.drop_duplicates(subset=["ts"]).reset_index(drop=True)
    orders = []
    if os.path.exists(lb.BRIDGE_ORDERS):
        for line in open(lb.BRIDGE_ORDERS, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                orders.append(json.loads(line))
            except Exception:
                pass
    data.update(
        equity_start=lb.fp.EQUITY0,
        equity=st.get("equity", lb.fp.EQUITY0),
        peak=st.get("peak", lb.fp.EQUITY0),
        n_trades=st.get("n_trades", 0),
        max_pos=lb.fp.MAX_POS,
        max_margin_pct=lb.fp.MAX_MARGIN_PCT,
        lev=lb.fp.LEV,
        positions=st.get("positions", []),
        trades=trades,
        equity_curve=equity,
        orders=orders,
        last_ts=st.get("last_ts"),
        mode="REAL" if lb.REAL else "DRY_RUN",
    )
    return data


def render_bridge_section(fd):
    if not fd.get("enabled"):
        return ("<div class='section-title'>LIVE BRIDGE (FUTURES THẬT) — DRY-RUN</div>"
                "<div class='helper-box'>⚠️ Cấu phần Futures áo đang tắt (ENABLE_FUTURES_AUTO_TRADE=False).</div>")
    if fd.get("error"):
        return ("<div class='section-title'>LIVE BRIDGE (FUTURES THẬT)</div>"
                f"<div class='helper-box'>⚠️ {fd['error']}</div>")

    m = compute_futures_metrics(fd)
    prices = fetch_futures_prices([p["symbol"] for p in fd["positions"]]) if fd["positions"] else {}
    unreal = sum(
        p["direction"] * (prices.get(p["symbol"], p["entry_px"]) - p["entry_px"])
        / p["entry_px"] * float(p["notional"])
        for p in fd["positions"]
    )
    eq = fd["equity"] + unreal
    start = fd["equity_start"]
    curve = fd.get("equity_curve")
    curve_peak = float(curve["equity"].max()) if curve is not None and len(curve) else 0.0
    peak = max(fd["peak"], curve_peak, eq)
    total_pnl = eq - start
    tpc = "positive" if total_pnl >= 0 else "negative"
    mdd_pct = 0.0
    if curve is not None and len(curve):
        eqs = np.concatenate([curve["equity"].to_numpy(dtype=float), np.array([eq])])
        mdd_pct = float(((eqs / np.maximum.accumulate(eqs) - 1.0) * 100.0).min())
    elif eq < start:
        mdd_pct = (eq / start - 1.0) * 100.0
    mdd_cls = "negative" if mdd_pct < 0 else "positive"
    margin_usd = sum(float(p.get("margin", 0) or 0) for p in fd["positions"])
    margin_pct = margin_usd / eq * 100 if eq > 0 else 0
    dn = m["by_strategy"].get("DON", 0)
    kt = m["by_strategy"].get("KELT", 0)

    pos_rows = ""
    if fd["positions"]:
        for p in fd["positions"]:
            side = "LONG" if p["direction"] == 1 else "SHORT"
            is_long = p["direction"] == 1
            cur = prices.get(p["symbol"], p["entry_px"])
            gross = p["direction"] * (cur - p["entry_px"]) / p["entry_px"] * 100
            pnl_cls = "positive" if gross >= 0 else "negative"
            pos_rows += f"""
            <tr>
                <td><strong>{p['symbol']}</strong></td>
                <td><span class="badge {'auto' if is_long else 'manual'}">{side}</span></td>
                <td><span class="badge stratb">{p['strategy']}</span></td>
                <td>${p['entry_px']:.4f}</td>
                <td>${cur:.4f}</td>
                <td>${p['notional']:,.0f}</td>
                <td>${p['margin']:,.0f}</td>
                <td class="{pnl_cls}"><strong>{gross:+.2f}%</strong></td>
                <td>{fmt_ms(p['entry_time'])}</td>
            </tr>"""
    else:
        pos_rows = "<tr><td colspan='9' style='text-align:center; padding:24px; color:#888;'>Không có vị thế mở.</td></tr>"

    ord_rows = ""
    if fd.get("orders"):
        for r in fd["orders"][-15:]:
            o = r.get("order", {})
            side = "SELL" if o.get("side") == "SELL" else "BUY"
            verb_badge = {"PLACE": ("badge auto", "MỞ"), "UPDATE": ("badge manual", "DỊCH"),
                          "CANCEL+CLOSE": ("badge stratb", "ĐÓNG")}.get(r.get("verb"), ("badge", r.get("verb", "")))
            px = f" stop={o.get('stopPrice')}" if o.get("stopPrice") else ""
            ord_rows += f"""
            <tr>
                <td><span class="badge {'auto' if r.get('verb')=='PLACE' else 'manual'}">{r.get('verb')}</span></td>
                <td><strong>{o.get('symbol')}</strong></td>
                <td><span class="badge {'auto' if side=='BUY' else 'manual'}">{side}</span></td>
                <td>{o.get('type')} <span class="badge stratb">reduceOnly</span></td>
                <td>${o.get('price_hint', o.get('stopPrice', 0)):.4f}</td>
                <td>{o.get('qty', 0):.6g}</td>
                <td>{r.get('mode', 'DRY_RUN')}</td>
                <td>{fmt_ms(r.get('ts_ms', 0))}</td>
            </tr>"""
    else:
        ord_rows = "<tr><td colspan='8' style='text-align:center; padding:24px; color:#888;'>Chưa có lệnh nào được log (chờ scan/monitor có thay đổi vị thế).</td></tr>"

    mode_badge = ("<span class='badge manual'>REAL</span>" if fd.get("mode") == "REAL"
                  else "<span class='badge auto'>DRY-RUN · KHÔNG RỦI RO</span>")
    last_scan = fmt_ms(fd["last_ts"]) if fd.get("last_ts") else "-"
    return f"""<div class="section-title">LIVE BRIDGE — FUTURES THẬT (SO SÁNH VỚI BOT GIẤY) {mode_badge}</div>
    <div class="helper-box">Chạy đúng engine futures_paper nhưng ghi file <code>*_bridge.*</code> riêng.
    Mỗi quyết định được log dạng order chuẩn Binance (<code>STOP_MARKET</code> <code>reduceOnly</code>) vào
    <code>bridge_orders.jsonl</code> — dry-run <strong>không gọi API thật, không cần API key</strong>.
    Khi <code>FUTURES_BRIDGE_REAL=1</code> thì module này sẽ đặt lệnh thật.</div>

    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-title">Tài Khoản (Vốn + Lời/Lỗ)</div>
            <div class="kpi-value {tpc}">${eq:,.2f}</div>
            <div class="kpi-desc">Bắt đầu: ${start:,.0f} | Peak: ${peak:,.2f}</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Tổng Lợi Nhuận</div>
            <div class="kpi-value {tpc}">{total_pnl:+,.2f}$</div>
            <div class="kpi-desc">({total_pnl/start*100:+.2f}%) | DON: {dn:+,.0f}$ | KELT: {kt:+,.0f}$</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Max Drawdown</div>
            <div class="kpi-value {mdd_cls}">{mdd_pct:.2f}%</div>
            <div class="kpi-desc">Từ đỉnh (equity theo giá)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Vị Thế Mở / Margin</div>
            <div class="kpi-value" style="color: var(--accent-blue);">{len(fd['positions'])}/{fd['max_pos']}</div>
            <div class="kpi-desc">Margin {margin_pct:.1f}% (trần {fd['max_margin_pct']*100:.0f}%)</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-title">Tỷ Lệ Thắng</div>
            <div class="kpi-value" style="color: #ffb800;">{m['winrate']:.1f}%</div>
            <div class="kpi-desc">{m['win']}W/{m['loss']}L | PF {m['pf']:.2f} | Scan: {last_scan}</div>
        </div>
    </div>

    <div class="section-title">Vị Thế Bridge Đang Mở</div>
    <div class="table-container">
        <table>
            <thead><tr>
                <th>PAIR</th><th>HƯỚNG</th><th>CHIẾN LƯỢC</th><th>GIÁ VÀO</th><th>GIÁ HIỆN TẠI</th>
                <th>NOTIONAL</th><th>MARGIN</th><th>P/L %</th><th>NGÀY VÀO</th>
            </tr></thead>
            <tbody>{pos_rows}</tbody>
        </table>
    </div>

    <div class="section-title">Would-be Orders (định dạng Binance, đã log)</div>
    <div class="table-container">
        <table>
            <thead><tr>
                <th>HÀNH ĐỘNG</th><th>PAIR</th><th>SIDE</th><th>LOẠI</th><th>GIÁ</th><th>QTY</th><th>MODE</th><th>LÚC</th>
            </tr></thead>
            <tbody>{ord_rows}</tbody>
        </table>
    </div>"""


def render_futures_logic():
    """Mô tả logic 2 chiến lược autotrade futures áo (Donchian55 + Keltner H4)."""
    import futures_paper as fp

    don = fp.DON
    kelt = fp.KELT

    sl_don = f"{don['sl']:.0f}×ATR (cắt lỗ ban đầu) ⇒ entry ± {don['sl']/don['tp']*100:.0f}% của tp"
    blocks_don = [
        ("📊", "Chỉ báo kỹ thuật",
         f"Khung H4 (chỉ xử lý nến H4 đã đóng, giờ scan = 00:05/04:05/08:05/12:05/16:05/20:05 UTC):\n"
         f"• Donchian {int(don['dc'])} H4: Đỉnh/Đáy 55 nến — đường breakout\n"
         f"• EMA 50 + ADX(14) ≥ {don['adx']:.0f} (bộ lọc sức trend)\n"
         f"• ATR(14)% so SMA50(ATR%): chỉ vào khi biến động đang mở rộng\n"
         f"• Funding rate ≤ +{don['fdmax']*100:.2f}% (long) / ≥ −{don['fdmax']*100:.2f}% (short)"),
        ("📈", "Tín hiệu VÀO LỆNH (LONG / SHORT)",
         f"LONG khi đóng nến > DC_high, > EMA50, ADX ≥ {don['adx']:.0f}, ATR% > SMA50(ATR%), funding bình thường.\n"
         f"SHORT khi đóng nến < DC_low, < EMA50, ADX ≥ {don['adx']:.0f}, điều kiện ATR + funding tương ứng phản chiếu.\n"
         f"→ 1 slot/symbol (chiến lược đến trước chiếm slot)."),
        ("🛡", "Quản lý thoát lệnh (Chandelier Exit)",
         f"• Cắt lỗ ban đầu: entry ∓ {don['sl']:.0f}×ATR ({sl_don})\n"
         f"• Trailing: bám theo {don['trail']:.0f}×ATR dưới đỉnh (long) / trên đáy (short)\n"
         f"• Break-even: khi lãi ≥ {don['be']:.0f}×ATR → kéo SL về entry (miễn phí rủi ro)\n"
         f"• Chốt lời: take-profit {don['tp']:.0f}×ATR"),
        ("💼", "Sizing & Quản lý vốn",
         f"• Risk mỗi lệnh: {don['risk']*100:.2f}% equity (SL = 2×ATR ⇒ notional = risk / (2×ATR%))\n"
         f"• Đòn bẩy {fp.LEV:.0f}x, cụm {don['tp']/don['sl']:.1f}R:1 (~{don['tp']/don['sl']*.6:.1f} net R)\n"
         f"• Trần margin {fp.MAX_MARGIN_PCT*100:.0f}% equity, tối đa {fp.MAX_POS} vị thế (slot DON ≤ {fp.MAX_STRAT['DON']})"),
    ]

    blocks_kelt = [
        ("📊", "Chỉ báo kỹ thuật",
         f"Khung H4, cùng khung giờ scan futures (H4 close):\n"
         f"• Kênh Keltner {kelt['mult']:.1f}×ATR(14) quanh EMA20 (mid)\n"
         f"• ADX(14) ≥ {kelt['adx']:.0f} (bộ lọc sức trend)\n"
         f"• Funding rate ≤ +{kelt['fdmax']*100:.2f}% (long) / ≥ −{kelt['fdmax']*100:.2f}% (short)"),
        ("📈", "Tín hiệu VÀO LỆNH (LONG / SHORT)",
         f"LONG khi đóng nến phá lên trên kênh Keltner upper (EMA20 + {kelt['mult']:.1f}×ATR) và ADX ≥ {kelt['adx']:.0f}.\n"
         f"SHORT khi đóng nến phá xuống dưới kênh Keltner lower (EMA20 − {kelt['mult']:.1f}×ATR) và ADX ≥ {kelt['adx']:.0f}.\n"
         f"→ 1 slot/symbol, 2 chiến lược DON + KELT chạy song song."),
        ("🛡", "Quản lý thoát lệnh (Chandelier Exit)",
         f"• Cắt lỗ ban đầu: entry ∓ {kelt['sl']:.0f}×ATR\n"
         f"• Trailing: bám theo {kelt['trail']:.1f}×ATR dưới đỉnh (long) / trên đáy (short)\n"
         f"• Break-even: khi lãi ≥ {kelt['be']:.0f}×ATR → kéo SL về entry\n"
         f"• Chốt lời: take-profit {kelt['tp']:.0f}×ATR"),
        ("💼", "Sizing & Quản lý vốn",
         f"• Risk mỗi lệnh: {kelt['risk']*100:.2f}% equity (SL = 2×ATR ⇒ notional = risk / (2×ATR%))\n"
         f"• Đòn bẩy {fp.LEV:.0f}x, cụm {kelt['tp']/kelt['sl']:.1f}R:1 (~{kelt['tp']/kelt['sl']*.6:.1f} net R)\n"
         f"• Trần margin {fp.MAX_MARGIN_PCT*100:.0f}% equity, slot KELT ≤ {fp.MAX_STRAT['KELT']})"),
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

    sub = (f"Vốn ${fp.EQUITY0:,.0f} | Lev {fp.LEV:.0f}x | Tối đa {fp.MAX_POS} vị thế | "
           f"Margin ≤ {fp.MAX_MARGIN_PCT*100:.0f}% | Freeze −{abs(fp.DAILY_LOSS)*100:.0f}%/ngày, −{abs(fp.WEEKLY_LOSS)*100:.0f}/tuần")
    cards = [build_card("DONCHAIN 55 — BREAKOUT H4", "#00b4d8", sub, blocks_don),
             build_card("KELTNER CHANNEL — TREND H4", "#c084fc", sub, blocks_kelt)]
    sl_rt = ("<div class='helper-box'>🛰️ <strong>SL REALTIME chống gap:</strong> giữa các móc nến H4, "
             "giá futures được đọc realtime (fapi) và lệnh đóng ngay khi giá xuyên mức SL/BE/trailing hiện tại "
             "— khớp theo giá thị trường thật (mô phỏng slippage/gap khi thị trường biến động mạnh). "
             "Chạy lệnh <code>python futures_paper.py --monitor</code> hoặc do cron đảm nhiệm.</div>")
    return f"<div class='section-title'>LOGIC CHIẾN LƯỢC AUTOTRADE FUTURES (TÓM TẮT ĐỂ ĐÁNH GIÁ)</div><div class='logic-grid'>" + "".join(cards) + f"</div>{sl_rt}"


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

    # 1d. Cấu phần FUTURES ÁO (paper trader H4)
    futures_data = load_futures_data()
    futures_html = render_futures_section(futures_data)
    futures_logic_html = render_futures_logic()
    bridge_data = load_bridge_data()
    bridge_html = render_bridge_section(bridge_data)

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
            <div style="font-size: 13px; color: var(--text-secondary);">Cập nhật lúc: <strong>(Giờ VN)</strong></div>
            <div style="font-weight: 600;">{(datetime.now(timezone.utc) + timedelta(hours=7)).strftime('%d/%m/%Y %H:%M:%S')}</div>
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

    {futures_html}

    {bridge_html}

    {futures_logic_html}

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