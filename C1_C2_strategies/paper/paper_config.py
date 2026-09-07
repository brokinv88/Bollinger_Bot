"""Cấu hình paper trading C1 $1000 (forward test).

Triết lý (khớp T01/T03/T06/R01-R08):
- Ex-ante universe: top20 theo thanh khoản 24h, LOẠI cổ phiếu/token-stock mới
  (SOXL, NVDA, INTC, ...) — không chọn theo kết quả backtest (chống data-snooping).
- Risk 0,5% mỗi lệnh, nền $1000 ảo. Chi phí như backtest engine.
- Không copy-paste "tham số tối ưu": giữ nguyên gen_c1 mặc định.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS = HERE.parent / "reports"
REPORTS.mkdir(exist_ok=True)

START_CASH = 1000.0
RISK_PCT = 0.005          # 0,5% equity mỗi lệnh (~$5 trên $1000)
TF = "4h"
COST_PCT = 0.0007         # khớp engine.py (taker 0.05% + slippage 0.02%)

# Ex-ante: top20 thanh khoản 24h, bỏ cổ phiếu/token-stock mới & cặp equity.
# SOXL (stock ETF) và ZEC/XAU (kim loại/mới, thanh khoản ổn định hơn) cố ý loại bỏ
# vì không thuộc họ crypto beta thuần mà C1 được kiểm chứng trên đó.
UNIVERSE = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "HYPE/USDT:USDT",
    "DOGE/USDT:USDT",
    "ARB/USDT:USDT",
    "BNB/USDT:USDT",
    "RAYSOL/USDT:USDT",
    "NEAR/USDT:USDT",
    "CL/USDT:USDT",
    "TAO/USDT:USDT",
    "SUI/USDT:USDT",
    "LINK/USDT:USDT",
    "UNI/USDT:USDT",
    "WLD/USDT:USDT",
    "ENA/USDT:USDT",
    "SNDK/USDT:USDT",
    "SKHYNIX/USDT:USDT",
    "MARSCOIN/USDT:USDT",
]

START_MS = int(__import__("pandas").Timestamp("2023-07-01", tz="UTC").value // 1_000_000)

# Chống backfill: nếu hệ nghỉ lâu (máy tắt / GitHub Actions trễ lịch), chỉ MỞ tín hiệu
# có entry_time trong cửa sổ này tính tới lúc chạy. Tín hiệu cũ hơn chỉ được cập nhật
# marker (đánh dấu đã thấy), KHÔNG mở lệnh — để forward test không bị trộn backfill.
MAX_SIGNAL_AGE_H = 12

STATE_FILE = REPORTS / "paper_state.json"
JOURNAL_FILE = REPORTS / "paper_journal.csv"
EQUITY_FILE = REPORTS / "paper_equity.csv"


def get_universe() -> list[str]:
    """Universe đóng băng để forward test không bị thay đổi giữa chừng."""
    return list(UNIVERSE)
