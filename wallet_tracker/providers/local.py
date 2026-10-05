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

    def positions(self, chain, wallet):
        """Không có Zerion: số dư suy ra từ các swap bot đã thấy (không có giá trị USD)."""
        rows = self.conn.execute("SELECT h.token, h.qty, t.symbol, t.max_price FROM holdings h LEFT JOIN tokens t"
                                 " ON t.chain=h.chain AND t.token=h.token WHERE h.chain=? AND h.wallet=? AND h.qty>0",
                                 (chain, wallet)).fetchall()
        return [{"token": r["token"], "symbol": r["symbol"] or "?", "qty": r["qty"], "value_usd": None,
                 "price": None, "is_quote": False} for r in rows]
