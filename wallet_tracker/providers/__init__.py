"""Nguồn lịch sử giao dịch ví để chấm điểm. Thêm nguồn mới (Birdeye, Covalent...): viết class có
trades(chain, wallet, days) và funding_sources(chain, wallet), rồi thêm vào get_provider()."""
from .. import config
from .local import LocalProvider
from .zerion import ZerionProvider


def get_provider(conn):
    return ZerionProvider() if config.ZERION_API_KEY else LocalProvider(conn)
