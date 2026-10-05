"""Paper trade: 2 book song song (fixed TP/SL và mirror bán theo ví nguồn), mỗi book vốn riêng."""
from . import config


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
    realized = conn.execute("SELECT COALESCE(SUM(pnl_usd),0) FROM positions WHERE book=? AND status='closed'",
                            (book,)).fetchone()[0]
    in_use = conn.execute("SELECT COALESCE(SUM(size_usd),0) FROM positions WHERE book=? AND status='open'",
                          (book,)).fetchone()[0]
    return config.PAPER_CAPITAL_USD + realized - in_use


def try_open(conn, book, chain, token, symbol, wallet, price, now):
    """Mở lệnh nếu còn vốn và chưa giữ token này. Trả (id|None, lý do)."""
    if conn.execute("SELECT 1 FROM positions WHERE book=? AND chain=? AND token=? AND status='open'",
                    (book, chain, token)).fetchone():
        return None, "đang giữ"
    if cash(conn, book) < config.PAPER_SIZE_USD:
        return None, "hết vốn"
    entry = price * (1 + config.PAPER_COST_PCT)
    cur = conn.execute("INSERT INTO positions(book,chain,token,symbol,wallet,entry_price,entry_ts,size_usd)"
                       " VALUES (?,?,?,?,?,?,?,?)",
                       (book, chain, token, symbol, wallet, entry, int(now), config.PAPER_SIZE_USD))
    conn.commit()
    return cur.lastrowid, "ok"


def close(conn, pos, price, reason, now):
    exit_price = price * (1 - config.PAPER_COST_PCT)
    pnl = pos["size_usd"] * (exit_price / pos["entry_price"] - 1)
    conn.execute("UPDATE positions SET status='closed', exit_price=?, exit_ts=?, reason=?, pnl_usd=? WHERE id=?",
                 (exit_price, int(now), reason, pnl, pos["id"]))
    conn.commit()
    return dict(pos) | {"exit_price": exit_price, "reason": reason, "pnl_usd": pnl}


def on_source_sell(conn, chain, token, wallet, price, now):
    """Ví nguồn bán -> đóng lệnh ở các book mirror."""
    closed = []
    for book, rules in config.BOOKS.items():
        if not rules["mirror"]:
            continue
        for pos in conn.execute("SELECT * FROM positions WHERE book=? AND chain=? AND token=? AND wallet=?"
                                " AND status='open'", (book, chain, token, wallet)).fetchall():
            closed.append(close(conn, pos, price, "ví nguồn bán", now))
    return closed


def update_prices(conn, chain, prices, now):
    """prices: {token: giá}. Áp TP/SL/time-stop. Token mất giá (rug/không còn pool) quá hạn -> đóng ở 0."""
    closed = []
    for pos in open_positions(conn, chain=chain):
        rules = config.BOOKS[pos["book"]]
        price = prices.get(pos["token"])
        expired = now - pos["entry_ts"] >= rules["max_hold_h"] * 3600
        if not price:
            if expired:
                closed.append(close(conn, pos, 0.0, "không còn giá", now))
            continue
        ret = price / pos["entry_price"] - 1
        if rules["tp"] is not None and ret >= rules["tp"]:
            closed.append(close(conn, pos, price, "TP", now))
        elif ret <= rules["sl"]:
            closed.append(close(conn, pos, price, "SL", now))
        elif expired:
            closed.append(close(conn, pos, price, "hết thời gian", now))
    return closed


def book_stats(conn):
    out = {}
    for book in config.BOOKS:
        rows = conn.execute("SELECT pnl_usd FROM positions WHERE book=? AND status='closed'", (book,)).fetchall()
        pnls = [r[0] for r in rows]
        out[book] = {
            "closed": len(pnls),
            "winrate": sum(p > 0 for p in pnls) / len(pnls) if pnls else 0.0,
            "pnl": sum(pnls),
            "open": len(open_positions(conn, book)),
            "cash": cash(conn, book),
        }
    return out


def wallet_stats(conn, book="fixed"):
    return conn.execute(
        "SELECT chain, wallet, COUNT(*) n, SUM(pnl_usd>0)*1.0/COUNT(*) winrate, SUM(pnl_usd) pnl"
        " FROM positions WHERE book=? AND status='closed' GROUP BY chain, wallet ORDER BY pnl DESC",
        (book,)).fetchall()
