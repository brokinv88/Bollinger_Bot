"""Tiện ích dòng lệnh: forward test C1 paper $1000.

Cách dùng (chạy từ project root):
    .venv/bin/python run_paper.py run     # quét + cập nhật + mở/đóng vị thế
    .venv/bin/python run_paper.py report  # in báo cáo định kỳ
    .venv/bin/python run_paper.py reset   # XOÁ state, bắt đầu lại $1000 (dùng có chủ đích)

Chạy 'run' định kỳ (ví dụ cron mỗi ngày) để forward test tích luỹ.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from C1_C2_strategies.paper import paper_account as acc
from C1_C2_strategies.paper import paper_config as cfg
from C1_C2_strategies.paper import paper_report, paper_runner


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        paper_runner.run()
    elif cmd == "report":
        paper_report.report()
    elif cmd == "reset":
        for f in (cfg.STATE_FILE, cfg.JOURNAL_FILE, cfg.EQUITY_FILE):
            if f.exists():
                f.unlink()
        acc.load()  # tạo lại state sạch $1000
        print("Đã reset paper account về $1000.")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
