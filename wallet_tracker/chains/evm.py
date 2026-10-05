"""EVM (Base / BSC / Ethereum / Robinhood Chain) qua JSON-RPC public.

Nhận diện swap theo ERC20 Transfer, không phụ thuộc DEX/aggregator:
  - ví NHẬN token (không phải WETH/stable) trong tx do chính ví gửi  -> BUY
  - ví GỬI token đó đi trong tx do chính ví gửi                       -> SELL
Token airdrop/spam (tx do người khác gửi) bị bỏ qua.
"""
import time

import requests

from .. import db
from .base import ChainAdapter

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
WALLET_BATCH = 50


def _topic(addr):
    return "0x" + "0" * 24 + addr[2:].lower()


def _addr(topic):
    return "0x" + topic[-40:].lower()


class EvmClient(ChainAdapter):
    def __init__(self, chain, cfg):
        super().__init__(chain, cfg)
        self.session = requests.Session()
        self._tx_from = {}
        self._decimals = {}

    def poll(self, conn, wallets):
        head = self.block_number()
        key = f"block:{self.chain}"
        cur = db.get_cursor(conn, key)
        if cur is None:                      # lần đầu: chỉ đặt mốc, không quét lịch sử
            db.set_cursor(conn, key, head)
            return []
        if head <= int(cur) or not wallets:
            db.set_cursor(conn, key, head)
            return []
        swaps = self.wallet_swaps(wallets, int(cur) + 1, head)
        db.set_cursor(conn, key, head)
        return swaps

    def decimals(self, token):
        if token not in self._decimals:
            try:
                self._decimals[token] = int(self.rpc("eth_call", [{"to": token, "data": "0x313ce567"}, "latest"]), 16)
            except Exception:
                self._decimals[token] = 18
        return self._decimals[token]

    def rpc(self, method, params):
        last = None
        for attempt in range(3):
            try:
                r = self.session.post(self.cfg["rpc"], json={"jsonrpc": "2.0", "id": 1, "method": method,
                                                             "params": params}, timeout=20)
                data = r.json()
                if "error" in data:
                    raise RuntimeError(data["error"])
                return data["result"]
            except Exception as e:
                last = e
                time.sleep(1 + attempt)
        raise RuntimeError(f"{self.chain} {method}: {last}")

    def block_number(self):
        return int(self.rpc("eth_blockNumber", []), 16)

    def block_ts(self, n):
        return int(self.rpc("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)

    def get_logs(self, frm, to, address=None, topics=None):
        logs, step, start = [], self.cfg["max_range"], frm
        while start <= to:
            end = min(start + step - 1, to)
            q = {"fromBlock": hex(start), "toBlock": hex(end), "topics": topics or []}
            if address:
                q["address"] = address
            try:
                logs += self.rpc("eth_getLogs", [q])
                start = end + 1
            except RuntimeError:
                if step <= 10:
                    raise
                step //= 2      # RPC giới hạn range/kết quả -> chia nhỏ
        return logs

    def tx_from(self, tx_hash):
        if tx_hash not in self._tx_from:
            if len(self._tx_from) > 20000:
                self._tx_from.clear()
            tx = self.rpc("eth_getTransactionByHash", [tx_hash]) or {}
            self._tx_from[tx_hash] = (tx.get("from") or "").lower()
        return self._tx_from[tx_hash]

    def wallet_swaps(self, wallets, frm, to):
        """Danh sách swap của các ví trong [frm, to]: dict(wallet, token, side, amount, tx, block)."""
        agg = {}
        for i in range(0, len(wallets), WALLET_BATCH):
            ws = [_topic(w) for w in wallets[i:i + WALLET_BATCH]]
            for side, topics in (("buy", [TRANSFER, None, ws]), ("sell", [TRANSFER, ws])):
                for log in self.get_logs(frm, to, topics=topics):
                    if len(log["topics"]) != 3:          # ERC721 có tokenId indexed
                        continue
                    token = log["address"].lower()
                    if token in self.quotes:
                        continue
                    wallet = _addr(log["topics"][2] if side == "buy" else log["topics"][1])
                    if self.tx_from(log["transactionHash"]) != wallet:
                        continue
                    raw = int(log["data"], 16) if log["data"] not in ("0x", "") else 0
                    amount = raw / 10 ** self.decimals(token)
                    key = (log["transactionHash"], wallet, token, side)
                    s = agg.setdefault(key, {"wallet": wallet, "token": token, "side": side, "amount": 0,
                                             "tx": log["transactionHash"], "block": int(log["blockNumber"], 16)})
                    s["amount"] += amount
        # Ví vừa nhận vừa gửi cùng token trong 1 tx (chuyển qua lại) -> bỏ
        out = []
        for (tx, w, t, side), s in agg.items():
            other = (tx, w, t, "sell" if side == "buy" else "buy")
            if other not in agg:
                out.append(s)
        return sorted(out, key=lambda s: s["block"])

    def block_at(self, ts):
        """Block đầu tiên có timestamp >= ts (binary search)."""
        lo, hi = 0, self.block_number()
        est = hi - int((time.time() - ts) / self.cfg["block_time"])
        lo = max(0, est - 50000)
        if self.block_ts(lo) > ts:
            lo = 0
        while lo < hi:
            mid = (lo + hi) // 2
            if self.block_ts(mid) < ts:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def early_buyers(self, token, pair, start_ts, window_s, max_logs):
        """{ví: số giây sau khi mở pool} — người nhận token từ pool trong window đầu."""
        start = self.block_at(start_ts)
        end = start + int(window_s / self.cfg["block_time"])
        logs = self.get_logs(start, end, address=token, topics=[TRANSFER, _topic(pair)])[:max_logs]
        buyers = {}
        for log in logs:
            buyer = self.tx_from(log["transactionHash"])
            if not buyer:
                continue
            delay = (int(log["blockNumber"], 16) - start) * self.cfg["block_time"]
            buyers[buyer] = min(delay, buyers.get(buyer, delay))
        return buyers
