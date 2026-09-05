# ==========================================
# CẤU HÌNH BOT GIAO DỊCH (CONFIG DUAL ACCOUNTS)
# ==========================================

import os

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
#    TOKEN KHÔNG ghi trong code. Đọc từ biến môi trường TELEGRAM_BOT_TOKEN
#    (do GitHub Actions secret cấp) để không lộ khi repo public.
#    Gõ lệnh bên dưới để chạy local:
#      export TELEGRAM_BOT_TOKEN="TOKEN_MỚI_TỪ_BOTFATHER"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "1050194344")

# 5. API Binance Tài khoản 1 (Danh mục Top 100 Volume)
BINANCE_ACC1_API_KEY = "YOUR_ACC1_API_KEY"
BINANCE_ACC1_API_SECRET = "YOUR_ACC1_API_SECRET"

# 6. API Binance Tài khoản 2 (Danh mục Top 100 MarketCap)
BINANCE_ACC2_API_KEY = "YOUR_ACC2_API_KEY"
BINANCE_ACC2_API_SECRET = "YOUR_ACC2_API_SECRET"

# 7. CHIẾN LƯỢC B (chạy song song với BASE trên cả 2 danh mục)
#    Cùng quy tắc vào/thoát như BASE, NHƯNG thêm bộ lọc "tránh đuổi đỉnh & coin rủi ro cao"
#    Kết quả backtest (86 coin Top 100, D1): PnL +$1,659, WR 28.6%, PF 6.63, MaxDD -$813
#    So với BASE: PnL +$1,315, WR 18.8%, PF 2.27, MaxDD -$1,684
ENABLE_STRATEGY_B = True
STRATEGY_B_LABEL = "CHIẾN LƯỢC B"
STRATEGY_B_MAX_ROC5 = 20.0     # Chặn lệnh mua khi coin tăng quá nóng trong 5 ngày (đuổi đỉnh)
STRATEGY_B_MAX_ROC20 = 40.0    # Chặn lệnh mua sau cơn bùng nổ 20 ngày
STRATEGY_B_MAX_ATR_PCT = 6.0   # Chỉ vào lệnh coin có độ biến động (ATR 14d) < 6% để giảm rủi ro
# DB riêng cho Strategy B (BASE giữ DB cũ, không đụng dữ liệu hiện có)
STRATEGY_B_DB_SUFFIX = "_stratb"   # vd: database_volume_stratb.db

# 8. ĐẶT LỆNH TỰ ĐỘNG ẢO (PAPER AUTO-TRADE)
#    Bot tự khớp mua/bán ảo, tự cập nhật SL, tự ghi PnL vào dashboard theo 4 đơn vị
#    (2 chiến lược BASE/STRATEGY B x 2 danh mục). Giá mua ảo dùng midpoint upper_band/close,
#    giá SL = 0.99 x max(SMA < giá, lower band), cập nhật theo công thức mới nhất mỗi lần chạy.
ENABLE_AUTO_TRADE = True
AUTO_TRADE_LABEL = "TỰ ĐỘNG ẢO"
# Giá khớp mua ảo: nội suy giữa upper_band và close (0.0 = khớp tại close, 1.0 = khớp tại upper_band)
AUTO_ENTRY_FILL = 0.5
# Chạy scan hàng ngày lúc 07:01 VN. Các giờ bổ sung trong ngày (VN) chỉ auto_trade:
#   cập nhật giá realtime, cập nhật SL, tự chốt lỗ khi giá cắt SL. Không phát sinh tín hiệu mua/bán mới
#   (tín hiệu vào/thoát vẫn theo nến DAILY, chỉ xử tại giờ scan 07:01).

# 9. AUTOTRADE FUTURES ẢO (PAPER FUTURES AUTO-TRADE) — cấu phần song song của #8
#    Chiến lược Donchian55 H4 + Keltner H4 (research_futures_strategy.py), long+short,
#    sizing theo fiat futures_trading_plan.md ($2,000, risk 0.75%/0.60%, lev 3x, margin ≤ 40%).
#    Chạy như một cấu phần trong auto_trade.py; khung giờ scan = H4 UTC (ưu tiên cho futures).
ENABLE_FUTURES_AUTO_TRADE = True
FUTURES_START_EQUITY = 2000.0
FUTURES_LEVERAGE = 3.0
FUTURES_MAX_POS = 6
FUTURES_MAX_MARGIN_PCT = 0.40
FUTURES_DAILY_LOSS = -0.05
FUTURES_WEEKLY_LOSS = -0.10
FUTURES_RISK_DON = 0.0075
FUTURES_RISK_KELT = 0.0060
FUTURES_STATE_FILE = "paper_state.json"
FUTURES_TRADES_CSV = "paper_trades.csv"
FUTURES_EQUITY_CSV = "paper_equity.csv"
# H4 scan: chạy sau móc đóng nến H4 (00:01/04:01/08:01/12:01/16:01/20:01 UTC).
FUTURES_SCAN_MINUTES_UTC = "1 0,4,8,12,16,20 * * *"
