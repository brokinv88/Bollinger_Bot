"""App web local cho Wallet Tracker. Mỗi màn hình là 1 route; thêm màn hình = thêm route + template."""
import json
import os
import time
from datetime import datetime

from flask import Flask, Response, flash, g, redirect, render_template, request, url_for

from .. import config, db, discovery, paper, plugins, scoring, settings

EXPLORERS = {"base": "https://basescan.org/address/", "bsc": "https://bscscan.com/address/",
             "ethereum": "https://etherscan.io/address/", "solana": "https://solscan.io/account/"}
GMGN = {"base": "base", "bsc": "bsc", "ethereum": "eth", "solana": "sol"}
STATUSES = ["active", "watch_only", "candidate", "disabled"]
KINDS = ["buy", "buy_more", "sell_partial", "sell_all"]
SORTS = {"score": "m.score", "pnl_30d": "m.pnl_30d", "winrate_30d": "m.winrate_30d",
         "early_hits": "w.early_hits", "paper_pnl": "paper_pnl", "added": "w.added_at"}


def create_app(db_path=None):
    app = Flask(__name__)
    app.secret_key = os.environ.get("WT_WEB_SECRET", "wallet-tracker-local")
    password = os.environ.get("WT_WEB_PASSWORD", "")
    plugins.load()

    def conn():
        if "conn" not in g:
            g.conn = db.connect(db_path)
        return g.conn

    @app.teardown_appcontext
    def _close(_):
        c = g.pop("conn", None)
        if c:
            c.close()

    @app.before_request
    def _auth():
        if not password:
            return None
        a = request.authorization
        if not a or a.password != password:
            return Response("Cần đăng nhập", 401, {"WWW-Authenticate": 'Basic realm="wallet-tracker"'})

    # --- filters cho template ---
    @app.template_filter("dt")
    def _dt(ts):
        return datetime.fromtimestamp(ts).strftime("%d/%m %H:%M") if ts else "—"

    @app.template_filter("short")
    def _short(a):
        return f"{a[:6]}…{a[-4:]}" if a and len(a) > 12 else (a or "")

    @app.template_filter("money")
    def _money(v):
        if v is None:
            return "—"
        sign = "-" if v < 0 else ""
        return f"{sign}${abs(v):,.2f}" if abs(v) < 1000 else f"{sign}${abs(v):,.0f}"

    @app.template_filter("pct")
    def _pct(v):
        return "—" if v is None else f"{v:.0%}"

    @app.template_filter("hold")
    def _hold(s):
        if s is None:
            return "—"
        return f"{s / 60:.0f}m" if s < 3600 else f"{s / 3600:.1f}h" if s < 86400 else f"{s / 86400:.1f}d"

    @app.template_filter("fromjson")
    def _fromjson(s):
        return json.loads(s or "[]")

    @app.context_processor
    def _ctx():
        return {"chains": list(config.CHAINS), "explorers": EXPLORERS, "gmgn": GMGN,
                "active_chains": config.active_chains()}

    # --- Dashboard ---
    @app.route("/")
    def dashboard():
        c = conn()
        snaps = c.execute("SELECT ts, book, equity FROM equity_snapshots WHERE ts>=? ORDER BY ts",
                          (int(time.time()) - 30 * 86400,)).fetchall()
        series = {}
        for s in snaps:
            series.setdefault(s["book"], []).append({"x": s["ts"] * 1000, "y": round(s["equity"], 2)})
        counts = {r[0]: r[1] for r in c.execute("SELECT status, COUNT(*) FROM wallets GROUP BY status")}
        return render_template("dashboard.html", stats=paper.book_stats(c), series=series, counts=counts,
                               signals=c.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 15").fetchall(),
                               positions=paper.open_positions(c),
                               capital=settings.get(c, "PAPER_CAPITAL_USD"))

    # --- Ví (Wallet Radar) ---
    @app.route("/wallets")
    def wallets():
        c, a = conn(), request.args
        sql = ("SELECT w.*, m.score, m.pnl_7d, m.pnl_30d, m.winrate_30d, m.tokens_30d, m.avg_hold_s, m.updated_at,"
               " (SELECT GROUP_CONCAT(label, ',') FROM wallet_labels l WHERE l.chain=w.chain AND l.address=w.address)"
               " labels,"
               " (SELECT SUM(pnl_usd) FROM positions p WHERE p.chain=w.chain AND p.wallet=w.address"
               "  AND p.book='fixed' AND p.status='closed') paper_pnl"
               " FROM wallets w LEFT JOIN wallet_metrics m ON m.chain=w.chain AND m.address=w.address WHERE 1=1")
        args = []
        if a.get("chain"):
            sql += " AND w.chain=?"
            args.append(a["chain"])
        if a.get("status"):
            sql += " AND w.status=?"
            args.append(a["status"])
        else:
            sql += " AND w.status!='disabled'"
        if a.get("q"):
            sql += " AND (w.address LIKE ? OR w.note LIKE ?)"
            args += [f"%{a['q']}%"] * 2
        if a.get("label"):
            sql += " AND EXISTS (SELECT 1 FROM wallet_labels l WHERE l.chain=w.chain AND l.address=w.address AND l.label=?)"
            args.append(a["label"])
        for field, col, scale in (("min_winrate", "m.winrate_30d", 0.01), ("min_pnl", "m.pnl_30d", 1),
                                  ("min_tokens", "m.tokens_30d", 1), ("min_hits", "w.early_hits", 1)):
            if a.get(field):
                sql += f" AND {col}>=?"
                args.append(float(a[field]) * scale)
        sql += f" ORDER BY {SORTS.get(a.get('sort'), 'm.score')} DESC NULLS LAST LIMIT 500"
        labels = [r[0] for r in c.execute("SELECT DISTINCT label FROM wallet_labels ORDER BY label")]
        return render_template("wallets.html", rows=c.execute(sql, args).fetchall(), labels=labels,
                               statuses=STATUSES, sorts=list(SORTS), a=a)

    @app.post("/wallets/add")
    def wallet_add():
        f = request.form
        if f.get("chain") in config.CHAINS and f.get("address", "").strip():
            new = db.add_wallet(conn(), f["chain"], f["address"], status=f.get("status", "active"), note=f.get("note", ""))
            flash(("Đã thêm ví" if new else "Đã cập nhật ví") + f" {f['address'].strip()}")
        return redirect(request.referrer or url_for("wallets"))

    @app.post("/wallet/<chain>/<address>/update")
    def wallet_update(chain, address):
        f, c = request.form, conn()
        if f.get("status") in STATUSES:
            db.set_status(c, chain, address, f["status"])
        if "note" in f:
            db.set_note(c, chain, address, f["note"])
        flash("Đã lưu")
        return redirect(request.referrer or url_for("wallet_detail", chain=chain, address=address))

    @app.post("/wallet/<chain>/<address>/score")
    def wallet_score(chain, address):
        try:
            scoring.score_wallet(conn(), chain, address)
            st = discovery.evaluate(conn(), chain, address)
            flash("Đã chấm điểm" + (f" — tự thêm theo dõi ({st})" if st else ""))
        except Exception as e:
            flash(f"Lỗi chấm điểm: {e}", "error")
        return redirect(url_for("wallet_detail", chain=chain, address=address))

    @app.route("/wallet/<chain>/<address>")
    def wallet_detail(chain, address):
        c = conn()
        w = db.get_wallet(c, chain, address)
        if not w:
            return render_template("base.html", body="Không tìm thấy ví"), 404
        return render_template(
            "wallet.html", w=w, m=db.get_metrics(c, chain, w["address"]), statuses=STATUSES,
            labels=c.execute("SELECT * FROM wallet_labels WHERE chain=? AND address=?", (chain, w["address"])).fetchall(),
            early=c.execute("SELECT e.*, t.symbol FROM early_buys e LEFT JOIN tokens t ON t.chain=e.chain AND t.token=e.token"
                            " WHERE e.chain=? AND e.wallet=? ORDER BY e.delay_s", (chain, w["address"])).fetchall(),
            signals=c.execute("SELECT * FROM signals WHERE chain=? AND wallet=? ORDER BY id DESC LIMIT 50",
                              (chain, w["address"])).fetchall(),
            positions=c.execute("SELECT * FROM positions WHERE chain=? AND wallet=? ORDER BY id DESC LIMIT 50",
                                (chain, w["address"])).fetchall(),
            pstats=paper.wallet_stats(c, "fixed", chain, w["address"]))

    # --- Tín hiệu ---
    @app.route("/signals")
    def signals():
        c, a = conn(), request.args
        sql, args = "SELECT * FROM signals WHERE 1=1", []
        for field in ("chain", "kind"):
            if a.get(field):
                sql += f" AND {field}=?"
                args.append(a[field])
        if a.get("passed") in ("0", "1"):
            sql += " AND passed=?"
            args.append(int(a["passed"]))
        return render_template("signals.html", rows=c.execute(sql + " ORDER BY id DESC LIMIT 300", args).fetchall(),
                               kinds=KINDS, a=a)

    # --- Lệnh paper ---
    @app.route("/positions")
    def positions():
        c, a = conn(), request.args
        sql, args = "SELECT * FROM positions WHERE 1=1", []
        for field in ("book", "status", "chain"):
            if a.get(field):
                sql += f" AND {field}=?"
                args.append(a[field])
        rows = c.execute(sql + " ORDER BY id DESC LIMIT 300", args).fetchall()
        fills = {}
        if rows:
            ids = [r["id"] for r in rows]
            for f in c.execute(f"SELECT * FROM fills WHERE position_id IN ({','.join('?' * len(ids))}) ORDER BY id", ids):
                fills.setdefault(f["position_id"], []).append(f)
        return render_template("positions.html", rows=rows, fills=fills, books=list(settings.get(c, "BOOKS")), a=a)

    # --- Cài đặt + discover + blacklist ---
    @app.route("/settings", methods=["GET", "POST"])
    def settings_page():
        c = conn()
        if request.method == "POST":
            errors = 0
            for key in config.DEFAULTS:
                raw = request.form.get(key)
                if raw is None:
                    continue
                try:
                    value = json.loads(raw)
                    if value != settings.get(c, key):
                        settings.set(c, key, value)
                except Exception as e:
                    errors += 1
                    flash(f"{key}: {e}", "error")
            if not errors:
                flash("Đã lưu cài đặt (monitor áp dụng ở vòng kế tiếp)")
            return redirect(url_for("settings_page"))
        overridden = {r[0] for r in c.execute("SELECT key FROM settings")}
        values = {k: json.dumps(v, ensure_ascii=False, indent=1 if isinstance(v, dict) else None)
                  for k, v in settings.all(c).items()}
        return render_template("settings.html", values=values, overridden=overridden,
                               blacklist=c.execute("SELECT * FROM blacklist ORDER BY added_at DESC").fetchall())

    @app.post("/settings/reset/<key>")
    def settings_reset(key):
        settings.reset(conn(), key)
        flash(f"Đã về mặc định: {key}")
        return redirect(url_for("settings_page"))

    @app.post("/blacklist")
    def blacklist():
        f, c = request.form, conn()
        if f.get("action") == "remove":
            db.blacklist_remove(c, f["chain"], f["token"])
        elif f.get("token", "").strip():
            db.blacklist_add(c, f.get("chain") or "*", f["token"].strip(), f.get("reason", ""))
        return redirect(url_for("settings_page"))

    @app.post("/discover")
    def discover():
        f = request.form
        try:
            res = discovery.discover_token(conn(), f["chain"], f["token"].strip(), int(f.get("minutes") or 60))
            flash(discovery.format_discovery(f["chain"], res))
        except Exception as e:
            flash(f"Lỗi discovery: {e}", "error")
        return redirect(url_for("wallets", status="candidate", chain=f.get("chain")))

    return app
