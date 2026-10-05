"""Giá / thanh khoản (DexScreener) và kiểm tra an toàn token (GoPlus) — đều free."""
import requests

from . import config

_sec_cache = {}

DEXSCREENER = "https://api.dexscreener.com/latest/dex/tokens/"
GOPLUS = "https://api.gopluslabs.io/api/v1/token_security/"


def token_pairs(chain, tokens):
    """{token: {price, liquidity, symbol, pair, created_ts}} — chọn pool thanh khoản lớn nhất trên đúng chain."""
    cfg = config.CHAINS[chain]
    tokens = list(dict.fromkeys(tokens))
    out = {}
    for i in range(0, len(tokens), 30):
        batch = tokens[i:i + 30]
        try:
            resp = requests.get(DEXSCREENER + ",".join(batch), timeout=15)
            pairs = resp.json().get("pairs") or []
        except Exception as e:
            print(f"[dexscreener] lỗi: {e}")
            continue
        for p in pairs:
            if p.get("chainId") != cfg["dexscreener"]:
                continue
            token = config.norm(chain, p["baseToken"]["address"])
            if token not in batch:
                continue
            liq = float((p.get("liquidity") or {}).get("usd") or 0)
            if token in out and out[token]["liquidity"] >= liq:
                continue
            out[token] = {
                "price": float(p.get("priceUsd") or 0),
                "liquidity": liq,
                "symbol": p["baseToken"].get("symbol", "?"),
                "pair": config.norm(chain, p["pairAddress"]),
                "created_ts": (p.get("pairCreatedAt") or 0) / 1000,
                "url": p.get("url", ""),
            }
    return out


def token_security(chain, token):
    key = (chain, token)
    if key not in _sec_cache:
        _sec_cache[key] = _token_security(chain, token)
    return _sec_cache[key]


def _token_security(chain, token):
    """{honeypot, buy_tax, sell_tax, creator}. None = không có dữ liệu."""
    gid = config.CHAINS[chain].get("goplus")
    empty = {"honeypot": None, "buy_tax": None, "sell_tax": None, "creator": None}
    if not gid:
        return empty
    try:
        res = requests.get(GOPLUS + gid, params={"contract_addresses": token}, timeout=15).json()
        info = (res.get("result") or {}).get(token.lower())
    except Exception as e:
        print(f"[goplus] lỗi: {e}")
        return empty
    if not info:
        return empty

    def f(k):
        v = info.get(k)
        return float(v) if v not in (None, "") else None

    return {"honeypot": info.get("is_honeypot") == "1", "buy_tax": f("buy_tax"), "sell_tax": f("sell_tax"),
            "creator": (info.get("creator_address") or "").lower() or None}
