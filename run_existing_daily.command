#!/bin/zsh
set -e
cd "${0:A:h}"
./.venv/bin/python -m strategy_lab.scan_existing --limit 100
print "Báo cáo: strategy_lab/reports/existing_strategies/daily_latest/SCAN_VI.md"
