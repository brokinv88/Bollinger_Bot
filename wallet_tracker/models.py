from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Signal:
    chain: str
    wallet: str
    token: str
    side: str                 # buy | sell
    kind: str                 # buy | buy_more | sell_partial | sell_all
    amount: float
    tx: str
    ts: int
    symbol: str = "?"
    price: float | None = None
    liquidity: float | None = None
    pair: dict | None = None
    wallet_status: str = ""
    wallet_note: str = ""
    labels: list = field(default_factory=list)
    confluence: int = 1
    sell_fraction: float = 0.0    # tỷ lệ vị thế ví nguồn vừa bán
    passed: bool = False
    reasons: list = field(default_factory=list)
    actions: list = field(default_factory=list)   # subscriber ghi kết quả (vd paper)
    id: int | None = None
