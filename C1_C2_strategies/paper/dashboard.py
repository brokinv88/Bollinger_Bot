"""Dashboard web local theo dõi paper trading C1 $1000 (Flask, không cần internet).

Chạy:     .venv/bin/python run_dashboard.py [--port 8787] [--host 127.0.0.1]
API:      /api/overview, /api/trades, /api/equity, /api/universe, /api/mark
Hành động: POST/GET /api/run -> chạy paper_runner.run() (mở/đóng lệnh một lần).

Chỉ bind localhost mặc định; không để lộ qua mạng ngoài.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template_string, request

from .. import data as data_mod
from .. import indicators as ind
from .. import strategies
from . import paper_account as acc
from . import paper_config as cfg
from . import paper_runner

app = Flask(__name__)


def _load_journal() -> pd.DataFrame | None:
    if not cfg.JOURNAL_FILE.exists():
        return None
    df = pd.read_csv(cfg.JOURNAL_FILE)
    return df if len(df) else None


def _load_equity() -> pd.DataFrame | None:
    if not cfg.EQUITY_FILE.exists():
        return None
    df = pd.read_csv(cfg.EQUITY_FILE)
    return df if len(df) else None


def _metrics() -> dict:
    acct = acc.load()
    j = _load_journal()
    eq = _load_equity()

    m = {
        "cash": round(acct.cash, 2),
        "equity": round(acct.equity(), 2),
        "peak": round(acct.equity_high_water, 2),
        "realized_pnl": round(acct.realized_pnl, 2),
        "closed_trades": acct.closed_trades,
        "open_positions": len(acct.positions),
        "created_at": acct.created_at,
        "last_update": acct.last_update,
        "risk_amount": round(acct._risk_amount(), 2),
        "risk_pct": cfg.RISK_PCT * 100,
        "start_cash": cfg.START_CASH,
        "universe_size": len(cfg.get_universe()),
        "marked_symbols": sum(1 for s in cfg.get_universe() if s in acct.last_seen_signal),
        "win_rate": None,
        "profit_factor": None,
        "avg_r": None,
        "total_r": None,
        "max_dd_pct": None,
    }
    m["drawdown_pct"] = round(
        100 * (acct.equity_high_water - acct.equity()) / acct.equity_high_water, 2
    ) if acct.equity_high_water > 0 else 0.0

    if j is not None:
        wins = j[j["pnl_usd"] > 0]
        losses = j[j["pnl_usd"] < 0]
        m["win_rate"] = round(100 * len(wins) / len(j), 1) if len(j) else None
        m["avg_r"] = round(float(j["r"].mean()), 4) if len(j) else None
        m["total_r"] = round(float(j["r"].sum()), 2) if len(j) else None
        if len(losses) and j["pnl_usd"].sum() > 0:
            m["profit_factor"] = round(
                float(j["pnl_usd"][j["pnl_usd"] > 0].sum() / -j["pnl_usd"][j["pnl_usd"] < 0].sum()), 3
            )
        elif len(losses) == 0 and len(j):
            m["profit_factor"] = None  # chưa lỗ lần nào -> vô cùng, hiển thị "∞"

    if eq is not None and len(eq):
        eq = eq.copy()
        eq = eq.sort_values("ts")
        peak = eq["equity"].cummax()
        dd = (peak - eq["equity"]) / peak
        m["max_dd_pct"] = round(float(dd.max() * 100), 2)
    return m


def _open_positions() -> list[dict]:
    acct = acc.load()
    return [
        {
            "symbol": p.symbol,
            "direction": p.direction,
            "entry": p.entry,
            "stop": p.stop,
            "target": p.target,
            "qty": p.qty,
            "entry_time": p.entry_time,
        }
        for p in acct.positions
    ]


@app.route("/")
def index() -> str:
    return render_template_string(TEMPLATE)


@app.route("/api/overview")
def api_overview():
    m = _metrics()
    m["positions"] = _open_positions()
    return jsonify(m)


@app.route("/api/trades")
def api_trades():
    j = _load_journal()
    if j is None:
        return jsonify([])
    j = j.sort_values("exit_time", ascending=False)
    return jsonify(json.loads(j.to_json(orient="records", date_format="iso")))


@app.route("/api/equity")
def api_equity():
    eq = _load_equity()
    if eq is None:
        return jsonify([])
    eq = eq.sort_values("ts")
    return jsonify(
        {"ts": eq["ts"].tolist(), "equity": eq["equity"].tolist()}
    )


@app.route("/api/universe")
def api_universe():
    acct = acc.load()
    rows = []
    for s in cfg.get_universe():
        rows.append({"symbol": s, "last_seen": acct.last_seen_signal.get(s, None)})
    return jsonify(rows)


@app.route("/api/watchlist")
def api_watchlist():
    """Trạng thái "đang chờ" của từng cặp: trend EMA50/200, mức trigger (swing + close để break),
    gần mức đó bao nhiêu, tín hiệu mới nhất vs marker."""
    acct = acc.load()
    now_ms = int(paper_runner._now_ms())
    out = []
    for s in cfg.get_universe():
        try:
            df = data_mod.fetch_ohlcv(s, cfg.TF, cfg.START_MS, now_ms)
        except Exception as e:  # noqa: BLE001
            out.append({"symbol": s, "error": str(e)[:80]})
            continue
        if len(df) < 250:
            out.append({"symbol": s, "short_history": True})
            continue
        sw = ind.swing_points(df, k=2)
        fast = ind.ema(df["close"], 50)
        slow = ind.ema(df["close"], 200)
        a = ind.atr(df, 14)
        trend_up = float(fast.iloc[-1]) > float(slow.iloc[-1])
        prev_hi = sw["swing_high"].ffill().iloc[-1]
        prev_lo = sw["swing_low"].ffill().iloc[-1]
        close = float(df["close"].iloc[-1])
        idx_last = df.index[-1]
        trig = float(prev_hi) if trend_up else float(prev_lo)
        if trend_up:
            dist_pct = 100.0 * (trig - close) / close if close else None
        else:
            dist_pct = 100.0 * (close - trig) / close if close else None
        sigs = strategies.gen_c1(df)
        last_sig = None
        if len(sigs):
            last_sig = str(sigs["entry_time"].iloc[-1])
        marker = acct.last_seen_signal.get(s)
        fired = marker is not None and last_sig is not None and pd.Timestamp(last_sig) > pd.Timestamp(marker)
        out.append(
            {
                "symbol": s,
                "trend": "up" if trend_up else "down",
                "close": round(close, 2),
                "trigger_level": round(trig, 2),
                "dist_pct": round(dist_pct, 2) if dist_pct is not None else None,
                "atr": round(float(a.iloc[-1]), 2) if not pd.isna(a.iloc[-1]) else None,
                "last_bar": str(idx_last)[:16],
                "last_signal": last_sig,
                "marker": marker,
                "new_signal_fired": bool(fired),
            }
        )
    out.sort(key=lambda r: r.get("dist_pct") if r.get("dist_pct") is not None else 1e9)
    return jsonify(out)


@app.route("/api/run", methods=["GET", "POST"])
def api_run():
    """Online-only: forward test chạy trên GitHub Actions. Dashboard chỉ ĐỒNG BỘ state
    mới nhất từ GitHub về máy local (git pull), không chạy engine ở local."""
    repo = Path(__file__).resolve().parent.parent.parent
    try:
        r = subprocess.run(
            ["git", "pull", "--rebase", "--autostash", "origin", "main"],
            cwd=str(repo), capture_output=True, text=True, timeout=120,
        )
        msg = (r.stdout or "").strip().splitlines()
        msg += (r.stderr or "").strip().splitlines()
        return jsonify({"ok": r.returncode == 0, "git": msg[-3:] if msg else [], **_metrics()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), **_metrics()})


TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Paper C1 — Dashboard</title>
<style>
  :root{--bg:#0f1115;--card:#171b22;--line:#232936;--txt:#e6e9ef;--dim:#8b93a5;
        --up:#22c55e;--down:#ef4444;--accent:#60a5fa}
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.5 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--bg);color:var(--txt);padding:24px}
  h1{font-size:20px;margin:0 0 4px}
  .sub{color:var(--dim);font-size:12px;margin-bottom:20px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
  .card .label{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.4px}
  .card .val{font-size:22px;font-weight:600;margin-top:4px;font-variant-numeric:tabular-nums}
  .val.up{color:var(--up)} .val.down{color:var(--down)}
  .row{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;flex:1;min-width:300px}
  .panel h2{font-size:14px;margin:0 0 10px;color:var(--accent)}
  table{width:100%;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums}
  th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
  th{color:var(--dim);font-weight:500;font-size:11px;text-transform:uppercase;letter-spacing:.4px}
  td.r,th.r{text-align:right}
  .tag{display:inline-block;padding:1px 7px;border-radius:6px;font-size:11px;font-weight:600}
  .tag.l{background:rgba(34,197,94,.15);color:var(--up)}
  .tag.s{background:rgba(239,68,68,.15);color:var(--down)}
  .btn{background:var(--accent);color:#0b1020;border:0;border-radius:8px;padding:8px 14px;
       font-weight:600;cursor:pointer;font-size:13px}
  .btn:disabled{opacity:.5;cursor:wait}
  .btn.ghost{background:transparent;color:var(--dim);border:1px solid var(--line)}
  #eq svg{width:100%;height:220px}
  .scroll{max-height:360px;overflow:auto}
  .pos-title{font-weight:600}
  .empty{color:var(--dim);padding:12px 0}
  .statusbar{display:flex;gap:8px;align-items:center;margin-bottom:16px;flex-wrap:wrap}
  #status{color:var(--dim);font-size:12px}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--up);display:inline-block;margin-right:6px}
</style>
</head>
<body>
  <h1>Paper Trading — C1 (BOS thuận xu hướng H4)</h1>
  <div class="sub">Tài khoản ảo $1.000 · risk 0,5%/lệnh · Binance USD-M futures · forward test từ
    <span id="created">—</span> · <b>engine chạy trên GitHub Actions</b>, dashboard chỉ xem</div>

  <div class="statusbar">
    <button class="btn" id="runBtn" onclick="runNow()">⟳ Đồng bộ từ GitHub</button>
    <button class="btn ghost" onclick="refresh()">⟳ Refresh</button>
    <span id="status"><span class="dot"></span>Đang tải…</span>
  </div>

  <div class="grid" id="kpis"></div>

  <div class="row">
    <div class="panel">
      <h2>Đường Equity (forward test)</h2>
      <div id="eq"><div class="empty">Chưa có dữ liệu equity.</div></div>
    </div>
    <div class="panel">
      <h2>Vị thế đang mở</h2>
      <div id="open"><div class="empty">Không có vị thế mở.</div></div>
    </div>
  </div>

  <div class="row">
    <div class="panel">
      <h2>Nhật ký lệnh đã đóng</h2>
      <div class="scroll"><table id="trades"><thead>
        <tr><th>Symbol</th><th class="r">Hướng</th><th class="r">Entry</th><th class="r">Exit</th>
            <th class="r">R</th><th class="r">PnL</th><th>Lý do</th><th>Đóng lúc</th></tr>
      </thead><tbody></tbody></table></div>
    </div>
    <div class="panel">
      <h2>Universe (top20 thanh khoản)</h2>
      <div class="scroll"><table id="uni"><thead>
        <tr><th>Symbol</th><th>Tín hiệu gần nhất</th></tr>
      </thead><tbody></tbody></table></div>
    </div>
  </div>

  <div class="panel">
    <h2>Watchlist — khoảng cách tới tín hiệu C1 tiếp theo</h2>
    <div id="wl"><div class="empty">Đang tải…</div></div>
  </div>

<script>
let autoTimer = null;
async function j(url, opts){const r=await fetch(url,opts);return r.json();}
function fmt(n,d=2){return (n===null||n===undefined)?'—':Number(n).toLocaleString('en-US',{maximumFractionDigits:d});}
function dirTag(d){return d===1?`<span class="tag l">LONG</span>`:`<span class="tag s">SHORT</span>`;}
function trendTag(up){return up?'<span class="tag l">UP</span>':'<span class="tag s">DOWN</span>';}

function renderKpis(o){
  document.getElementById('created').innerText=(o.created_at||'—').slice(0,10);
  const ddOk = o.drawdown_pct<=0;
  const items=[
    ['Equity', fmt(o.equity,2), o.equity>=o.start_cash?'up':'down'],
    ['Cash', '$'+fmt(o.cash,2), ''],
    ['Đỉnh (high-water)', '$'+fmt(o.peak,2), ''],
    ['Max DD', fmt(o.max_dd_pct,2)+'%', o.max_dd_pct===null?'':(o.max_dd_pct<=10?'up':'down')],
    ['DD hiện tại', fmt(o.drawdown_pct,2)+'%', ddOk?'up':'down'],
    ['PnL thực hiện', '$'+fmt(o.realized_pnl,2), o.realized_pnl>=0?'up':'down'],
    ['Lệnh đóng', o.closed_trades, ''],
    ['Lệnh mở', o.open_positions, ''],
    ['Win rate', (o.win_rate===null)?'—':fmt(o.win_rate,1)+'%', o.win_rate>=45?'up':'down'],
    ['Profit factor', o.profit_factor===null?'—':fmt(o.profit_factor,2), o.profit_factor>=1?'up':'down'],
    ['Kỳ vọng / lệnh (R)', o.avg_r===null?'—':fmt(o.avg_r,3), (o.avg_r??0)>=0?'up':'down'],
    ['Tổng R', o.total_r===null?'—':fmt(o.total_r,2), (o.total_r??0)>=0?'up':'down'],
  ];
  document.getElementById('kpis').innerHTML=items.map(([l,v,c])=>
    `<div class="card"><div class="label">${l}</div><div class="val ${c}">${v}</div></div>`).join('');

  // open positions
  const op=document.getElementById('open');
  if(!o.positions||!o.positions.length){op.innerHTML='<div class="empty">Không có vị thế mở.</div>';}
  else{
    op.innerHTML='<table><thead><tr><th>Symbol</th><th class="r">Hướng</th><th class="r">Qty</th>'+
      '<th class="r">Entry</th><th class="r">Stop</th><th class="r">Target</th></tr></thead><tbody>'+
      o.positions.map(p=>`<tr>
        <td class="pos-title">${p.symbol}</td>
        <td class="r">${dirTag(p.direction)}</td>
        <td class="r">${fmt(p.qty,4)}</td>
        <td class="r">${fmt(p.entry,3)}</td>
        <td class="r">${fmt(p.stop,3)}</td>
        <td class="r">${fmt(p.target,3)}</td></tr>`).join('')+'</tbody></table>';
  }
}

async function renderEquity(){
  const d=await j('/api/equity');
  if(!d||!d.ts||!d.ts.length){document.getElementById('eq').innerHTML='<div class="empty">Chưa có dữ liệu equity.</div>';return;}
  const W=780,H=220,PAD={l:8,r:8,t:14,b:22},vals=d.equity;
  const mn=Math.min(...vals),mx=Math.max(...vals),rng=(mx-mn)||1;
  const x=i=>PAD.l+(W-PAD.l-PAD.r)*i/(vals.length-1||1);
  const y=v=>H-PAD.b-(H-PAD.t-PAD.b)*(v-mn)/rng;
  // baseline = $1000
  const base=(H-PAD.b)-(H-PAD.t-PAD.b)*(1000-mn)/rng;
  let pts=vals.map((v,i)=>`${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const color = vals[vals.length-1]>=vals[0]? '#22c55e':'#ef4444';
  const area=pts+' '+x(vals.length-1)+','+(H-PAD.b)+' '+x(0)+','+(H-PAD.b);
  const svg=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${color}" stop-opacity=".35"/>
      <stop offset="1" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    <line x1="${PAD.l}" y1="${base.toFixed(1)}" x2="${W-PAD.r}" y2="${base.toFixed(1)}"
          stroke="#334" stroke-dasharray="4 4"/>
    <polygon points="${area}" fill="url(#g)"/>
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2"/>
    <text x="${PAD.l}" y="${H-6}" fill="#8b93a5" font-size="11">${d.ts[0]}</text>
    <text x="${W-PAD.r}" y="${H-6}" fill="#8b93a5" font-size="11" text-anchor="end">${d.ts[d.ts.length-1]}</text>
  </svg>`;
  document.getElementById('eq').innerHTML=svg;
}

async function renderTrades(){
  const t=await j('/api/trades');
  const tb=document.querySelector('#trades tbody');
  if(!t||!t.length){document.getElementById('trades').innerHTML='<tr><td colspan="8" class="empty">Chưa có lệnh đóng.</td></tr>';return;}
  tb.innerHTML=t.map(r=>`<tr>
    <td>${r.symbol}</td>
    <td class="r">${dirTag(r.direction)}</td>
    <td class="r">${fmt(r.entry,4)}</td>
    <td class="r">${fmt(r.exit,4)}</td>
    <td class="r ${r.r>=0?'up':'down'}">${fmt(r.r,2)}</td>
    <td class="r ${r.pnl_usd>=0?'up':'down'}">$${fmt(r.pnl_usd,2)}</td>
    <td>${r.reason}</td>
    <td>${(r.exit_time||'').replace('T',' ').slice(0,16)}</td></tr>`).join('');
}

async function renderUniverse(){
  const u=await j('/api/universe');
  document.querySelector('#uni tbody').innerHTML=u.map(r=>`<tr>
    <td class="pos-title">${r.symbol}</td>
    <td>${r.last_seen?r.last_seen:'<span class="empty">chưa ghi nhận</span>'}</td></tr>`).join('');
}

async function renderWatchlist(){
  const w=await j('/api/watchlist');
  const el=document.getElementById('wl');
  const ok=w.filter(r=>r.dist_pct!==undefined);
  const err=w.filter(r=>r.dist_pct===undefined);
  if(!ok.length){el.innerHTML=`<div class="empty">Không có dữ liệu hợp lệ.</div>`;return;}
  let rows=ok.map(r=>{
    const dir = r.trend==='up' ? 'LONG khi close >' : 'SHORT khi close <';
    const fired = r.new_signal_fired ? `<span class="tag l">SIGNAL MỚI</span>` : '';
    return `<tr>
      <td class="pos-title">${r.symbol} ${fired}</td>
      <td>${trendTag(r.trend==='up')}</td>
      <td class="r">${fmt(r.close,3)}</td>
      <td class="r">${dir} ${fmt(r.trigger_level,3)}</td>
      <td class="r ${r.dist_pct<=0.5?'up':'down'}">${fmt(r.dist_pct,2)}%</td>
      <td>${r.last_bar}</td></tr>`;
  }).join('');
  el.innerHTML=`<table><thead><tr><th>Symbol</th><th>Trend</th><th class="r">Close</th>
    <th class="r">Điều kiện vào</th><th class="r">% tới trigger</th><th>Nến gần nhất</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <div style="color:var(--dim);font-size:11px;margin-top:8px">
      Giải thích: tín hiệu C1 chỉ bật khi nến 4h ĐÓNG cửa vượt mức trigger (swing theo trend EMA50/200).
      % tới trigger càng nhỏ ⇒ càng gần bật. Forward test chỉ mở tín hiệu MỚI xuất hiện sau khi bắt đầu
      (không backfill 3 năm) — nên ban đầu "chưa thấy gì" là bình thường, chỉ cần chờ tín hiệu mới.
      ${err.length?`<br>Không lấy được: ${err.map(e=>e.symbol).join(', ')}`:''}
    </div>`;
}

async function refresh(){
  const [o]=await Promise.all([j('/api/overview'), renderEquity(), renderTrades(), renderUniverse(), renderWatchlist()]);
  renderKpis(o);
  const st=document.getElementById('status');
  st.innerHTML=`<span class="dot"></span>Lần cập nhật cuối: <b>${o.last_update||'—'}</b> · auto-refresh 60s`;
  scheduleAuto();
}
function scheduleAuto(){clearInterval(autoTimer);autoTimer=setInterval(()=>{document.getElementById('status');
  refresh().then(()=>{});},60000);}

async function runNow(){
  const btn=document.getElementById('runBtn'), st=document.getElementById('status');
  btn.disabled=true; btn.innerText='⏳ Đang đồng bộ từ GitHub…';
  st.innerHTML='Đang git pull state mới nhất từ GitHub (engine chạy cloud, không chạy local)…';
  try{
    const o=await j('/api/run');
    renderKpis(o); await renderEquity(); await renderTrades(); await renderUniverse(); await renderWatchlist();
    if(o.ok===false) st.innerHTML=`<span style="color:var(--down)">Git pull lỗi: ${o.error||'xem log'}</span>`;
    else st.innerHTML=`<span class="dot"></span>Đã đồng bộ lúc <b>${new Date().toLocaleTimeString()}</b>`;
  }catch(e){st.innerHTML=`<span style="color:var(--down)">Lỗi đồng bộ: ${e}</span>`;}
  finally{btn.disabled=false;btn.innerText='⟳ Đồng bộ từ GitHub';}
}

refresh();
setInterval(()=>{}, 0);
</script>
</body>
</html>
"""


def main(host: str = "127.0.0.1", port: int = 8787, debug: bool = False) -> None:
    print(f"Paper C1 dashboard: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Paper C1 dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    main(args.host, args.port, args.debug)