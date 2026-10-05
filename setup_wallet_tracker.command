#!/bin/zsh
# Cài Wallet Tracker trên máy: tạo .venv (nếu chưa có), cài thư viện, tạo file .env, kiểm tra.
set -e
cd "${0:A:h}"

echo "== 1/4 Lấy code mới nhất =="
git pull --autostash || echo "(bỏ qua git pull)"

echo "== 2/4 Môi trường Python =="
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
./.venv/bin/python -m pip install -q --upgrade pip
./.venv/bin/python -m pip install -q -r wallet_tracker/requirements.txt
echo "OK: $(./.venv/bin/python --version)"

echo "== 3/4 File cấu hình wallet_tracker/.env =="
if [ ! -f wallet_tracker/.env ]; then
  cp wallet_tracker/.env.example wallet_tracker/.env
  echo "Đã tạo wallet_tracker/.env — điền WT_TELEGRAM_BOT_TOKEN, WT_TELEGRAM_CHAT_ID, HELIUS_API_KEY (ZERION_API_KEY tùy chọn)"
  open -e wallet_tracker/.env 2>/dev/null || true
else
  echo "Đã có wallet_tracker/.env (giữ nguyên)"
fi

echo "== 4/4 Kiểm tra =="
./.venv/bin/python -m wallet_tracker list
chmod +x run_wallet_tracker.command
echo ""
echo "Xong. Điền .env rồi bấm đúp run_wallet_tracker.command -> mở http://localhost:5050"
