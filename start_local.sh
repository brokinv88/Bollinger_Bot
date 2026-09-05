#!/bin/bash
# start_local.sh — active failover local sau khi mở máy.
# Cron đã cài sẽ tự chạy; script này để verify + đuổi kịp móc bị bỏ lỡ khi sleep/off.
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/4 git pull (đón state mới từ Actions/local) =="
git pull --rebase --autostash origin main

echo "== 2/4 Paper scan (backfill từ cursor, không scan trùng) =="
.venv/bin/python futures_paper.py --scan --notify

echo "== 3/4 Bridge scan (dry-run, log would-be orders) =="
.venv/bin/python live_bridge.py --scan

echo "== 4/4 Publish dashboard =="
.venv/bin/python publish_dashboard.py

echo "== Hoàn tất. Cron sẽ tự lo các móc tiếp theo khi máy bật. =="