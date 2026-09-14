#!/bin/zsh
set -eu
TASK_DIR="${0:A:h}"
PROJECT_DIR="${TASK_DIR:h}"
cd "$PROJECT_DIR"
if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  print 'Chưa tìm thấy môi trường Python của dự án. Xem strategy_lab/README_VI.md.'
  exit 1
fi
print 'Đang đọc dữ liệu Binance để lọc danh mục. Không đặt lệnh.'
TASK_SCAN_ARGS=(--limit 100 --output-dir "$TASK_DIR/reports/daily_latest")
if [[ -f "$TASK_DIR/account.json" ]]; then
  TASK_SCAN_ARGS+=(--account "$TASK_DIR/account.json")
fi
if [[ -f "$TASK_DIR/narratives.json" ]]; then
  TASK_SCAN_ARGS+=(--narratives "$TASK_DIR/narratives.json")
fi
if "$PROJECT_DIR/.venv/bin/python" -m strategy_lab.scanner "${TASK_SCAN_ARGS[@]}"; then
  print "Đã xong: $TASK_DIR/reports/daily_latest/scan_vi.md"
else
  print "Lần quét có lỗi hoặc chỉ đủ một phần dữ liệu. Xem: $TASK_DIR/reports/daily_latest/scan_vi.md"
  exit 2
fi
