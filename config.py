# ==========================================
# CẤU HÌNH BOT GIAO DỊCH (CONFIG DUAL ACCOUNTS)
# ==========================================

# 1. Chế độ hoạt động chung: "PAPER" (Mô phỏng/Bắn tín hiệu) hoặc "LIVE" (Đặt lệnh thật)
MODE = "PAPER"

# 2. Ràng buộc danh mục (Áp dụng riêng cho từng tài khoản)
MAX_OPEN_COINS = 10         # Tối đa 10 mã đồng thời / mỗi tài khoản
CASH_PER_ENTRY = 50.0       # $50 USD mỗi lần vào lệnh
MAX_PYRAMID = 3             # Nhồi tối đa 3 lần ($150/mã)
TOTAL_PORTFOLIO_CAP = 1500.0# Tổng vốn trần danh mục mỗi tài khoản

# 3. Thông số kỹ thuật Bollinger Envelopes & SMA
BB_LEN = 20
BB_MULT = 1.5
SMA_PERIODS = [50, 100, 150, 200]

# 4. Cấu hình Telegram (Nhận thông báo chung hoặc riêng)
TELEGRAM_BOT_TOKEN = "8832797099:AAGy-6NBbK2Hgtssh2PF-4t2BhRyI986xB8"
TELEGRAM_CHAT_ID = "1050194344"

# 5. API Binance Tài khoản 1 (Danh mục Top 100 Volume)
BINANCE_ACC1_API_KEY = "YOUR_ACC1_API_KEY"
BINANCE_ACC1_API_SECRET = "YOUR_ACC1_API_SECRET"

# 6. API Binance Tài khoản 2 (Danh mục Top 100 MarketCap)
BINANCE_ACC2_API_KEY = "YOUR_ACC2_API_KEY"
BINANCE_ACC2_API_SECRET = "YOUR_ACC2_API_SECRET"
