class LocalProvider:
    """Dùng các swap bot đã quan sát (bảng trades). Chỉ có dữ liệu từ lúc bắt đầu theo dõi ví."""
    name = "local"

    def __init__(self, conn):
        self.conn = conn

    def trades(self, chain, wallet, days):
        import time
        since = int(time.time()) - days * 86400
        rows = self.conn.execute("SELECT ts, token, side, amount, price FROM trades WHERE chain=? AND wallet=?"
                                 " AND ts>=? AND price IS NOT NULL ORDER BY ts", (chain, wallet, since)).fetchall()
        return [{"ts": r["ts"], "token": r["token"], "side": r["side"], "qty": r["amount"],
                 "usd": r["amount"] * r["price"]} for r in rows]

    def funding_sources(self, chain, wallet):
        return []
