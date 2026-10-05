"""Registry adapter theo loại chain. Thêm chain mới cùng loại: chỉ thêm cấu hình trong config.CHAINS.
Thêm loại chain mới (vd Tron, Sui): viết class kế thừa ChainAdapter rồi đăng ký vào ADAPTERS."""
from .. import config
from .base import ChainAdapter
from .evm import EvmClient
from .solana import SolanaClient

ADAPTERS = {"evm": EvmClient, "solana": SolanaClient}


def make_client(chain) -> ChainAdapter:
    cfg = config.CHAINS[chain]
    return ADAPTERS[cfg["kind"]](chain, cfg)
