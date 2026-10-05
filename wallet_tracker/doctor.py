"""Kiểm tra kết nối từng dịch vụ: python -m wallet_tracker doctor [ví_để_thử_zerion]"""
import time

import requests

from . import config
from .chains import make_client
from .chains.evm import TRANSFER

TEST_WALLET = "0x8f86b823cd79b0cbc328e18b1cc0c66cc1b583f5"


def _check(name, fn):
    t = time.time()
    try:
        msg = fn()
        print(f"✅ {name:22} {msg}  ({time.time() - t:.1f}s)")
    except Exception as e:
        print(f"❌ {name:22} {type(e).__name__}: {str(e)[:300]}")


def run(wallet=None):
    wallet = wallet or TEST_WALLET

    def telegram():
        if not config.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("chưa điền WT_TELEGRAM_BOT_TOKEN")
        r = requests.get(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getMe", timeout=15).json()
        if not r.get("ok"):
            raise RuntimeError(r)
        return f"bot @{r['result']['username']}, chat_id={'có' if config.TELEGRAM_CHAT_ID else 'CHƯA ĐIỀN'}"

    _check("Telegram", telegram)
    def dexscreener():
        url = "https://api.dexscreener.com/latest/dex/tokens/0x4200000000000000000000000000000000000006"
        return f"{len(requests.get(url, timeout=15).json().get('pairs') or [])} pool WETH"

    _check("DexScreener", dexscreener)

    for chain in config.active_chains():
        c = make_client(chain)
        if config.CHAINS[chain]["kind"] != "evm":
            _check(f"RPC {chain}", lambda c=c: f"slot {c.rpc('getSlot', [])}")
            continue
        ok = []
        for url in c.endpoints:
            def logs(url=url):
                head = int(c.call(url, "eth_blockNumber", []), 16)
                topic = "0x" + "0" * 24 + wallet[2:].lower()
                c.call(url, "eth_getLogs", [{"fromBlock": hex(head - 50), "toBlock": hex(head),
                                             "topics": [TRANSFER, None, [topic]]}])
                ok.append(url)
                return f"block {head}, lọc log theo ví OK"
            _check(f"RPC {chain}", logs)
            print(f"   ↳ {url}")
        if not ok:
            print(f"   ⚠️  {chain}: không URL nào lọc log theo ví được -> điền {chain.upper()}_RPC_URL bằng RPC có key "
                  f"(Alchemy/dRPC free) trong .env")

    if config.HELIUS_API_KEY:
        def helius():
            url = f"{config.HELIUS_API_URL}/v0/addresses/So11111111111111111111111111111111111111112/transactions"
            r = requests.get(url, params={"api-key": config.HELIUS_API_KEY, "limit": 1}, timeout=20)
            r.raise_for_status()
            return f"parse API OK ({len(r.json())} tx)"
        _check("Helius", helius)

    if not config.ZERION_API_KEY:
        print("⚠️  Zerion                 chưa điền ZERION_API_KEY")
        return
    from .providers.zerion import API, ZerionProvider
    p = ZerionProvider()

    def zerion_raw():
        r = p.session.get(f"{API}/wallets/{wallet}/transactions/",
                          params={"currency": "usd", "page[size]": 5, "filter[operation_types]": "trade"}, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        items = r.json().get("data") or []
        chains = {(i.get("relationships") or {}).get("chain", {}).get("data", {}).get("id") for i in items}
        return f"{len(items)} giao dịch trade gần nhất, chain: {', '.join(sorted(c for c in chains if c)) or '—'}"

    _check("Zerion API", zerion_raw)
    def zerion_positions():
        rows = p.positions("robinhood" if "robinhood" in config.active_chains() else "base", wallet)
        top = ", ".join(f"{r['symbol']} ${r['value_usd']:,.0f}" for r in rows[:5])
        return f"{len(rows)} token đang nắm" + (f": {top}" if top else "")

    _check("Zerion danh mục", zerion_positions)
    for chain in [c for c in ("base", "bsc", "ethereum", "robinhood") if c in config.active_chains()]:
        def zerion_parse(chain=chain):
            trades = p.trades(chain, wallet, 30)
            return f"{len(trades)} lệnh mua/bán 30 ngày" + (f", vd {trades[-1]}" if trades else "")
        _check(f"Zerion parse {chain}", zerion_parse)
