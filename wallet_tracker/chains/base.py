class ChainAdapter:
    """Giao diện chung. Mỗi swap: dict(wallet, token, side='buy'|'sell', amount (đã chia decimals), tx)."""

    def __init__(self, chain, cfg):
        self.chain = chain
        self.cfg = cfg
        self.quotes = set(cfg["quotes"])

    def poll(self, conn, wallets):
        """Swap mới của các ví kể từ lần gọi trước. Adapter tự lưu con trỏ (block/chữ ký) trong DB."""
        raise NotImplementedError

    def early_buyers(self, token, pair, start_ts, window_s, max_logs):
        """{ví: số giây sau khi mở pool}."""
        raise NotImplementedError(f"Discovery chưa hỗ trợ cho {self.chain}")
