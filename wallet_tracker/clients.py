from . import config
from .chains.evm import EvmClient
from .chains.solana import SolanaClient


def make_client(chain):
    cfg = config.CHAINS[chain]
    return (SolanaClient if cfg["kind"] == "solana" else EvmClient)(chain, cfg)
