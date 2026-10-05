"""Cấu hình Wallet Tracker. Secrets đọc từ biến môi trường hoặc wallet_tracker/.env (đã gitignore)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_env_file(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR / ".env")


def _env(name, default=""):
    return os.environ.get(name, default)


DB_PATH = _env("WT_DB_PATH", str(BASE_DIR / "wallet_tracker.db"))

# Telegram riêng cho wallet tracker (không dùng chung bot của Bollinger)
TELEGRAM_BOT_TOKEN = _env("WT_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _env("WT_TELEGRAM_CHAT_ID")

HELIUS_API_KEY = _env("HELIUS_API_KEY")
HELIUS_API_URL = _env("HELIUS_API_URL", "https://api.helius.xyz")

# --- Paper trade ---
PAPER_CAPITAL_USD = 1000.0       # vốn mỗi book
PAPER_SIZE_USD = 100.0           # mỗi lệnh
PAPER_COST_PCT = 0.015           # phí + trượt giá mỗi chiều (memecoin thực tế 1-3%)
BOOKS = {
    # TP/SL cố định
    "fixed": {"tp": 1.00, "sl": -0.30, "max_hold_h": 72, "mirror": False},
    # Bán theo khi ví nguồn bán (+ SL an toàn)
    "mirror": {"tp": None, "sl": -0.50, "max_hold_h": 168, "mirror": True},
}

# --- Lọc token ---
MIN_LIQUIDITY_USD = 100_000
MAX_TAX = 0.10
CONFLUENCE_WINDOW_S = 3600

# --- Discovery / chấm ví ---
DISCOVERY_PUMP_X = 5.0           # token tăng >= 5x so với giá lúc ví theo dõi mua -> quét người mua sớm
DISCOVERY_WINDOW_MIN = 60        # người mua trong 60 phút đầu sau khi mở pool
DISCOVERY_MAX_LOGS = 300
PROMOTE_MIN_HITS = 2             # vào sớm >= 2 token thắng -> tự thêm vào danh sách theo dõi
SNIPER_DELAY_S = 60              # trễ trung vị < 60s -> sniper (chỉ alert, không paper)
DEMOTE_MIN_TRADES = 10           # ví discovery có >= 10 lệnh paper đóng mà lỗ -> tắt

POLL_INTERVAL_S = int(_env("WT_POLL_INTERVAL_S", "30"))

_SOL_RPC = (f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY
            else "https://api.mainnet-beta.solana.com")

CHAINS = {
    "solana": dict(
        kind="solana", rpc=_env("SOLANA_RPC_URL", _SOL_RPC), dexscreener="solana", goplus=None,
        quotes=["So11111111111111111111111111111111111111112",
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY2W1PbgM7uHHo3w"],
    ),
    "base": dict(
        kind="evm", rpc=_env("BASE_RPC_URL", "https://base-rpc.publicnode.com"), block_time=2.0,
        max_range=1000, dexscreener="base", goplus="8453",
        quotes=["0x4200000000000000000000000000000000000006", "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
                "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca", "0x50c5725949a6f0c72e6c4a641f24049a917db0cb"],
    ),
    "bsc": dict(
        kind="evm", rpc=_env("BSC_RPC_URL", "https://bsc-rpc.publicnode.com"), block_time=0.75,
        max_range=1000, dexscreener="bsc", goplus="56",
        quotes=["0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c", "0x55d398326f99059ff775485246999027b3197955",
                "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d", "0xe9e7cea3dedca5984780bafc599bd69add087d56",
                "0xc5f0f7b66764f6ec8c8dff7ba683102295e16409"],
    ),
    "ethereum": dict(
        kind="evm", rpc=_env("ETH_RPC_URL", "https://ethereum-rpc.publicnode.com"), block_time=12.0,
        max_range=1000, dexscreener="ethereum", goplus="1",
        quotes=["0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                "0xdac17f958d2ee523a2206206994597c13d831ec7", "0x6b175474e89094c44da98b954eedeac495271d0f"],
    ),
    # Robinhood Chain (Arbitrum Orbit, EVM). Tắt cho tới khi điền ROBINHOOD_RPC_URL.
    "robinhood": dict(
        kind="evm", rpc=_env("ROBINHOOD_RPC_URL"), block_time=float(_env("ROBINHOOD_BLOCK_TIME", "0.25")),
        max_range=int(_env("ROBINHOOD_MAX_RANGE", "5000")), dexscreener=_env("ROBINHOOD_DEXSCREENER_ID", "robinhood"),
        goplus=_env("ROBINHOOD_GOPLUS_ID") or None,
        quotes=[a.strip().lower() for a in _env("ROBINHOOD_QUOTES").split(",") if a.strip()],
    ),
}

ENABLED_CHAINS = [c.strip() for c in _env("WT_CHAINS", ",".join(CHAINS)).split(",") if c.strip()]


def active_chains():
    """Chain được bật và có RPC. Solana cần HELIUS_API_KEY để parse swap."""
    out = []
    for name in ENABLED_CHAINS:
        cfg = CHAINS.get(name)
        if not cfg or not cfg["rpc"]:
            continue
        if cfg["kind"] == "solana" and not HELIUS_API_KEY:
            continue
        out.append(name)
    return out


def norm(chain: str, address: str) -> str:
    """EVM: lowercase. Solana: base58 phân biệt hoa thường, giữ nguyên."""
    address = address.strip()
    return address if CHAINS[chain]["kind"] == "solana" else address.lower()
