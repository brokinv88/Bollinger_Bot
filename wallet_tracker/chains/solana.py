"""Solana: RPC getSignaturesForAddress (rẻ) để phát hiện tx mới, Helius parse API để đọc swap."""
import time

import requests

from .. import config


class SolanaClient:
    def __init__(self, chain, cfg):
        self.chain = chain
        self.cfg = cfg
        self.quotes = set(cfg["quotes"])
        self.session = requests.Session()

    def rpc(self, method, params):
        for attempt in range(3):
            try:
                data = self.session.post(self.cfg["rpc"], json={"jsonrpc": "2.0", "id": 1, "method": method,
                                                                "params": params}, timeout=20).json()
                if "error" in data:
                    raise RuntimeError(data["error"])
                return data["result"]
            except Exception as e:
                last = e
                time.sleep(1 + attempt)
        raise RuntimeError(f"solana {method}: {last}")

    def signatures(self, wallet, until=None, limit=100):
        opts = {"limit": limit}
        if until:
            opts["until"] = until
        return self.rpc("getSignaturesForAddress", [wallet, opts])

    def parse(self, sigs):
        url = f"{config.HELIUS_API_URL}/v0/transactions?api-key={config.HELIUS_API_KEY}"
        out = []
        for i in range(0, len(sigs), 100):
            r = self.session.post(url, json={"transactions": sigs[i:i + 100]}, timeout=30)
            r.raise_for_status()
            out += r.json()
        return out

    def wallet_swaps(self, wallet, until):
        """Trả (swaps, chữ ký mới nhất). Lần đầu (until=None) chỉ đặt mốc, không quét lịch sử."""
        sigs = self.signatures(wallet, until=until)
        if not sigs:
            return [], until
        newest = sigs[0]["signature"]
        if until is None:
            return [], newest
        ok = [s["signature"] for s in sigs if s.get("err") is None]
        swaps = []
        for tx in self.parse(ok) if ok else []:
            if tx.get("feePayer") != wallet:
                continue
            deltas = {}
            for t in tx.get("tokenTransfers") or []:
                amt = float(t.get("tokenAmount") or 0)
                if t.get("toUserAccount") == wallet:
                    deltas[t["mint"]] = deltas.get(t["mint"], 0) + amt
                if t.get("fromUserAccount") == wallet:
                    deltas[t["mint"]] = deltas.get(t["mint"], 0) - amt
            for mint, d in deltas.items():
                if mint in self.quotes or abs(d) < 1e-12:
                    continue
                swaps.append({"wallet": wallet, "token": mint, "side": "buy" if d > 0 else "sell",
                              "amount": abs(d), "tx": tx["signature"], "ts": tx.get("timestamp")})
        return sorted(swaps, key=lambda s: s.get("ts") or 0), newest
