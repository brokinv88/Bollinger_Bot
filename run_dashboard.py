"""Mở dashboard web local theo dõi paper C1.

Cách dùng:
    .venv/bin/python run_dashboard.py            # http://127.0.0.1:8787
    .venv/bin/python run_dashboard.py --port 8080
Chỉ bind localhost (127.0.0.1) để an toàn.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from C1_C2_strategies.paper import dashboard  # noqa: E402


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Paper C1 dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    dashboard.main(args.host, args.port, args.debug)


if __name__ == "__main__":
    main()