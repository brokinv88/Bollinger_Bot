"""Paper trade: nhiều book song song (cấu hình settings BOOKS), mỗi book vốn riêng.
Nghe sự kiện 'signal': mua lần đầu -> mở lệnh; ví nguồn bán -> book mirror bán theo cùng tỷ lệ."""
import time

from . import db, events, exits, settings


def open_positions(conn, book=None, chain=None):
    sql, args = "SELECT * FROM positions WHERE status='open'", []
    if book:
        sql += " AND book=?"
        args.append(book)
    if chain:
        sql += " AND chain=?"
        args.append(chain)
    return conn.execute(sql, args).fetchall()


def cash(conn, book):
    realized, sizes = conn.execute("SELECT COALESCE(SUM(realized_usd),0), COALESCE(SUM(size_usd),0)"
                                   " FROM positions WHERE book=?", (book,)).fetchone()
    return settings.get(conn, "PAPER_CAPITAL_USD") + realized - sizes


def equity(conn, book):
    held = sum((p["remaining_qty"] or 0) * (p["last_price"] or 0) * (1 - settings.get(conn, "PAPER_COST_PCT"))
               for p in open_positions(conn, book))
    return cash(conn, book) + held


def try_open(conn, book, chain, token, symbol, wallet, price, now):
    """Mở lệnh nếu còn vốn và chưa giữ token này. Trả (id|None, lý do)."""
    if conn.execute("SELECT 1 FROM positions WHERE book=? AND chain=? AND token=? AND status='open'",
                    (book, chain, token)).fetchone():
        return None, "đang giữ"
    size = settings.get(conn, "PAPER_SIZE_USD")
    if cash(conn, book) < size:
        return None, "hết vốn"
    entry = price * (1 + settings.get(conn, "PAPER_COST_PCT"))
    qty = size / entry
    cur = conn.execute(
        "INSERT INTO positions(book,chain,token,symbol,wallet,entry_price,entry_ts,size_usd,qty,remaining_qty,"
        "realized_usd,peak_price,last_price,tp_level) VALUES (?,?,?,?,?,?,?,?,?,?,0,?,?,0)",
        (book, chain, token, symbol, wallet, entry, int(now), size, qty, qty, price, price))
    conn.execute("INSERT INTO fills(position_id,ts,side,price,qty,usd,reason) VALUES (?,?,?,?,?,?,?)",
                 (cur.lastrowid, int(now), "buy", entry, qty, size, "mở"))
    conn.commit()
    return cur.lastrowid, "ok"


def sell(conn, pos, fraction, price, reason, now, updates=None):
    """Bán `fraction` phần còn lại. Hết khối lượng -> đóng lệnh. Phát sự kiện position_fill."""
    pos = dict(conn.execute("SELECT * FROM positions WHERE id=?", (pos["id"],)).fetchone())
    qty = pos["remaining_qty"] * min(1.0, max(0.0, fraction))
    if qty <= 0:
        return None
    exit_price = price * (1 - settings.get(conn, "PAPER_COST_PCT"))
    usd = qty * exit_price
    remaining = pos["remaining_qty"] - qty
    realized = (pos["realized_usd"] or 0) + usd
    closed = remaining <= pos["qty"] * 1e-6
    sets = {"remaining_qty": 0.0 if closed else remaining, "realized_usd": realized, **(updates or {})}
    if closed:
        sets.update(status="closed", exit_price=exit_price, exit_ts=int(now), reason=reason,
                    pnl_usd=realized - pos["size_usd"])
    conn.execute(f"UPDATE positions SET {','.join(f'{k}=?' for k in sets)} WHERE id=?", [*sets.values(), pos["id"]])
    conn.execute("INSERT INTO fills(position_id,ts,side,price,qty,usd,reason) VALUES (?,?,?,?,?,?,?)",
                 (pos["id"], int(now), "sell", exit_price, qty, usd, reason))
    conn.commit()
    fill = pos | sets | {"fill_qty": qty, "fill_usd": usd, "fill_pnl": qty * (exit_price - pos["entry_price"]),
                         "reason": reason, "closed": closed}
    events.emit("position_fill", conn=conn, fill=fill)
    return fill


def update_prices(conn, chain, prices, now):
    """prices: {token: giá}. Áp luật thoát của book. Token mất giá (rug) quá time_stop -> đóng ở 0."""
    books = settings.get(conn, "BOOKS")
    fills = []
    for pos in open_positions(conn, chain=chain):
        rules = (books.get(pos["book"]) or {}).get("exits", [])
        price = prices.get(pos["token"])
        if not price:
            ts = next((r for r in rules if r["rule"] == "time_stop"), None)
            if ts and exits.time_stop(pos, 0, now, ts):
                fills.append(sell(conn, pos, 1.0, 0.0, "không còn giá", now))
            continue
        peak = max(pos["peak_price"] or price, price)
        conn.execute("UPDATE positions SET peak_price=?, last_price=? WHERE id=?", (peak, price, pos["id"]))
        conn.commit()
        pos = dict(pos) | {"peak_price": peak, "last_price": price}
        res = exits.evaluate(pos, price, now, rules)
        if res:
            fraction, reason, updates = res
            fills.append(sell(conn, pos, fraction, price, reason, now, updates))
    return [f for f in fills if f]


def snapshot(conn, now=None):
    now = int(now or time.time())
    for book in settings.get(conn, "BOOKS"):
        conn.execute("INSERT INTO equity_snapshots VALUES (?,?,?,?)", (now, book, equity(conn, book), cash(conn, book)))
    conn.commit()


def book_stats(conn):
    out = {}
    for book in settings.get(conn, "BOOKS"):
        pnls = [r[0] for r in conn.execute("SELECT pnl_usd FROM positions WHERE book=? AND status='closed'", (book,))]
        out[book] = {
            "closed": len(pnls),
            "winrate": sum(p > 0 for p in pnls) / len(pnls) if pnls else 0.0,
            "pnl": sum(pnls),
            "open": len(open_positions(conn, book)),
            "cash": cash(conn, book),
            "equity": equity(conn, book),
        }
    return out


def wallet_stats(conn, book="fixed", chain=None, wallet=None):
    sql, args = ("SELECT chain, wallet, COUNT(*) n, SUM(pnl_usd>0)*1.0/COUNT(*) winrate, SUM(pnl_usd) pnl"
                 " FROM positions WHERE book=? AND status='closed'", [book])
    if wallet:
        sql += " AND chain=? AND wallet=?"
        args += [chain, wallet]
    return conn.execute(sql + " GROUP BY chain, wallet ORDER BY pnl DESC", args).fetchall()


# --- subscriber ---
@events.on("signal")
def on_signal(conn, sig):
    books = settings.get(conn, "BOOKS")
    if sig.side == "buy":
        if sig.kind != "buy" or not sig.passed or sig.wallet_status != "active":
            return
        for book in books:
            pid, why = try_open(conn, book, sig.chain, sig.token, sig.symbol, sig.wallet, sig.price, sig.ts)
            sig.actions.append(f"Paper {book}: " + (f"mở ${settings.get(conn, 'PAPER_SIZE_USD'):.0f}" if pid else why))
        return
    if not sig.price:
        return                      # không có giá -> để update_prices xử lý (time-stop)
    for book, cfg in books.items():
        if not cfg.get("mirror"):
            continue
        for pos in conn.execute("SELECT * FROM positions WHERE book=? AND chain=? AND token=? AND wallet=?"
                                " AND status='open'", (book, sig.chain, sig.token, sig.wallet)).fetchall():
            sell(conn, pos, sig.sell_fraction, sig.price, f"ví nguồn bán {sig.sell_fraction:.0%}", sig.ts)
