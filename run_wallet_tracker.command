#!/bin/zsh
set -e
cd "${0:A:h}"
./.venv/bin/python -m wallet_tracker run
