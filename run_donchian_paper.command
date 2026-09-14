#!/bin/zsh
set -e
cd "${0:A:h}"
./.venv/bin/python -m strategy_lab.donchian_paper menu
