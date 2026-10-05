"""Zerion API (free dev key: https://developers.zerion.io): lịch sử giao dịch đã giải mã + giá USD.
Định dạng response theo tài liệu Zerion v1; parse phòng thủ, thiếu trường thì bỏ qua giao dịch."""
import base64
import time
from datetime import datetime

import requests

from .. import config

API = "https://api.zerion.io/v1"
QUOTE_SYMBOLS = {"ETH", "WETH", "SOL", "WSOL", "BNB", "WBNB", "USDC", "USDT", "DAI", "USDBC", "FDUSD", "BUSD"}


def _ts(s):
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


class ZerionProvider:
    name = "zerion"

    def __init__(self):
        token = base64.b64encode(f"{config.ZERION_API_KEY}:".encode()).decode()
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Basic {token}", "accept": "application/json"})

    def _get(self, url, params=None):
        for attempt in range(3):
            r = self.session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 + attempt * 3)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()

    def _transactions(self, chain, wallet, op_types, since=None, max_pages=10):
        url = f"{API}/wallets/{wallet}/transactions/"
        params = {"currency": "usd", "page[size]": 100, "filter[operation_types]": op_types,
                  "filter[chain_ids]": config.ZERION_CHAIN_IDS.get(chain, chain), "filter[trash]": "only_non_trash"}
        for _ in range(max_pages):
            data = self._get(url, params)
            items = data.get("data") or []
            for it in items:
                yield it
            if since and items and _ts(items[-1]["attributes"].get("mined_at", "")) < since:
                return
            url = (data.get("links") or {}).get("next")
            params = None
            if not url:
                return

    def _token_id(self, chain, transfer):
        info = transfer.get("fungible_info") or {}
        for impl in info.get("implementations") or []:
            if impl.get("chain_id") == config.ZERION_CHAIN_IDS.get(chain, chain) and impl.get("address"):
                return config.norm(chain, impl["address"])
        return None

    def _is_quote(self, chain, transfer, token):
        sym = ((transfer.get("fungible_info") or {}).get("symbol") or "").upper()
        return sym in QUOTE_SYMBOLS or token is None or token in config.CHAINS[chain]["quotes"]

    def trades(self, chain, wallet, days):
        since = int(time.time()) - days * 86400
        out = []
        for it in self._transactions(chain, wallet, "trade", since):
            a = it.get("attributes") or {}
            ts = _ts(a.get("mined_at", ""))
            if ts < since:
                continue
            transfers = [t for t in a.get("transfers") or [] if t.get("fungible_info")]
            quote_usd = sum(float(t.get("value") or 0) for t in transfers
                            if self._is_quote(chain, t, self._token_id(chain, t)))
            for t in transfers:
                token = self._token_id(chain, t)
                if self._is_quote(chain, t, token):
                    continue
                qty = float((t.get("quantity") or {}).get("float") or 0)
                usd = float(t.get("value") or 0) or quote_usd
                if qty <= 0 or usd <= 0:
                    continue
                side = "buy" if t.get("direction") == "in" else "sell"
                out.append({"ts": ts, "token": token, "side": side, "qty": qty, "usd": usd})
        return sorted(out, key=lambda x: x["ts"])

    def funding_sources(self, chain, wallet, pages=3):
        """Địa chỉ đã gửi tài sản quote (ETH/SOL/stable) vào ví — cũ nhất trước."""
        senders = []
        for it in self._transactions(chain, wallet, "receive", max_pages=pages):
            for t in (it.get("attributes") or {}).get("transfers") or []:
                token = self._token_id(chain, t)
                if t.get("direction") == "in" and self._is_quote(chain, t, token) and t.get("sender"):
                    senders.append(config.norm(chain, t["sender"]))
        return list(dict.fromkeys(reversed(senders)))

    def positions(self, chain, wallet):
        """Token ví đang nắm trên chain (ví thường, không gồm vị thế DeFi), lớn nhất trước."""
        params = {"currency": "usd", "filter[positions]": "only_simple", "filter[trash]": "only_non_trash",
                  "filter[chain_ids]": config.ZERION_CHAIN_IDS.get(chain, chain), "sort": "-value", "page[size]": 100}
        out = []
        for it in (self._get(f"{API}/wallets/{wallet}/positions/", params).get("data") or []):
            a = it.get("attributes") or {}
            info = a.get("fungible_info") or {}
            token = self._token_id(chain, a)
            sym = (info.get("symbol") or "?")
            out.append({"token": token or f"native:{sym}", "symbol": sym, "name": info.get("name") or "",
                        "qty": float((a.get("quantity") or {}).get("float") or 0),
                        "value_usd": float(a.get("value") or 0), "price": float(a.get("price") or 0),
                        "is_quote": self._is_quote(chain, a, token)})
        return out
