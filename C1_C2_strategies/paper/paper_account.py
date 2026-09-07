"""Quản lý trạng thái tài khoản paper $1000: cash, equity, vị thế, nhật ký.

State được lưu dưới JSON để sống qua nhiều lần chạy (forward test nhiều ngày).
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from . import paper_config as cfg


@dataclass
class Position:
    symbol: str
    direction: int
    entry: float
    stop: float
    target: float
    qty: float
    entry_time: str
    signal_time: str
    entry_equity: float
    opened_at_bars: int = 0


@dataclass
class PaperAccount:
    cash: float = cfg.START_CASH
    equity_high_water: float = cfg.START_CASH
    positions: list = field(default_factory=list)
    closed_trades: int = 0
    realized_pnl: float = 0.0
    created_at: str = ""
    last_update: str = ""
    last_seen_signal: dict = field(default_factory=dict)  # symbol -> signal_time ISO đã xử lý

    def open_position(self, pos: Position) -> bool:
        """Mở vị thế nếu đủ tiền (margin 10x tối đa giới hạn — futures)."""
        notional = pos.qty * pos.entry
        # Binance USDT-M thường margin ~ không cần ký quỹ 1:1; dùng 5x tối đa giữ an toàn
        # Đơn giản: kiểm tra đủ cash cho notional tối đa 3x equity (bảo thủ).
        if notional > 3 * self.equity():
            return False
        self.positions.append(pos)
        return True

    def equity(self) -> float:
        """Tiền mặt + giá trị ký quỹ vị thế đang mở (unrealized chưa tính)."""
        return self.cash  # vị thế chưa đóng chưa ảnh hưởng equity (futures margin riêng)

    def _risk_amount(self) -> float:
        return max(cfg.START_CASH, self.equity()) * cfg.RISK_PCT  # dùng equity, min $5

    def size_for(self, risk_price: float) -> float:
        """qty sao cho tổn thất tại stop = RISK_PCT * equity."""
        if risk_price <= 0:
            return 0.0
        return self._risk_amount() / risk_price


def load(path: Path = cfg.STATE_FILE) -> PaperAccount:
    if not path.exists():
        acct = PaperAccount(created_at=_now())
        save(acct, path)
        return acct
    with open(path) as f:
        d = json.load(f)
    acct = PaperAccount(
        cash=d.get("cash", cfg.START_CASH),
        equity_high_water=d.get("equity_high_water", cfg.START_CASH),
        positions=[Position(**p) for p in d.get("positions", [])],
        closed_trades=d.get("closed_trades", 0),
        realized_pnl=d.get("realized_pnl", 0.0),
        created_at=d.get("created_at", ""),
        last_update=d.get("last_update", ""),
        last_seen_signal=d.get("last_seen_signal", {}),
    )
    return acct


def save(acct: PaperAccount, path: Path = cfg.STATE_FILE) -> None:
    acct.last_update = _now()
    d = asdict(acct)
    d["equity"] = round(acct.equity(), 2)
    d["risk_amount"] = round(acct._risk_amount(), 2)
    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as f:
        json.dump(d, f, indent=2, default=str)


def _now() -> str:
    import pandas as pd
    return pd.Timestamp.now(tz="UTC").isoformat()


def append_journal(trade: dict, path: Path = cfg.JOURNAL_FILE) -> None:
    import pandas as pd
    row = pd.DataFrame([trade])
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        old = pd.read_csv(path)
        row = pd.concat([old, row], ignore_index=True)
    row.to_csv(path, index=False)


def append_equity_point(t: str, equity: float, path: Path = cfg.EQUITY_FILE) -> None:
    import pandas as pd
    row = pd.DataFrame([{"ts": t, "equity": round(equity, 2)}])
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        old = pd.read_csv(path)
        row = pd.concat([old, row], ignore_index=True)
    row.to_csv(path, index=False)
