"""Danh mục token các ví theo dõi đang nắm (Zerion; không có key thì suy ra từ swap đã thấy)."""
from . import db, settings
from .providers import get_provider

WATCHED = ("active", "watch_only")


def refresh_wallet(conn, chain, wallet, provider=None):
    provider = provider or get_provider(conn)
    min_usd = settings.get(conn, "MIN_POSITION_USD")
    rows = [r for r in provider.positions(chain, wallet) if r["value_usd"] is None or r["value_usd"] >= min_usd]
    db.save_positions(conn, chain, wallet, rows)
    return rows


def refresh_all(conn, provider=None):
    provider = provider or get_provider(conn)
    n = 0
    for w in db.list_wallets(conn, statuses=WATCHED):
        try:
            refresh_wallet(conn, w["chain"], w["address"], provider)
            n += 1
        except Exception as e:
            print(f"[positions] {w['chain']} {w['address']}: {e}")
    return n


def aggregate(conn, chain=None, include_quotes=False, min_wallets=1):
    """Token được nhiều ví theo dõi cùng nắm: số ví, tổng giá trị, danh sách ví."""
    sql = ("SELECT p.chain, p.token, MAX(p.symbol) symbol, MAX(p.name) name, COUNT(DISTINCT p.wallet) n_wallets,"
           " SUM(p.value_usd) total_usd, MAX(p.price) price, GROUP_CONCAT(p.wallet) wallets, MAX(p.updated_at) updated_at"
           " FROM wallet_positions p JOIN wallets w ON w.chain=p.chain AND w.address=p.wallet"
           " WHERE w.status IN ('active','watch_only')")
    args = []
    if chain:
        sql += " AND p.chain=?"
        args.append(chain)
    if not include_quotes:
        sql += " AND p.is_quote=0"
    sql += " GROUP BY p.chain, p.token HAVING n_wallets>=? ORDER BY n_wallets DESC, total_usd DESC LIMIT 300"
    return conn.execute(sql, args + [min_wallets]).fetchall()
