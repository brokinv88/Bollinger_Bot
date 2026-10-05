# Wallet Tracker

Theo dõi ví mua sớm / smart money / sniper → **alert Telegram + paper trade + app web**. Không dùng private key.
Plan: [`docs/wallet_tracker_plan.md`](../docs/wallet_tracker_plan.md).

## Cài đặt (máy local)
```bash
./setup_wallet_tracker.command   # 1 lần: tạo .venv, cài thư viện, tạo wallet_tracker/.env rồi mở để điền
./run_wallet_tracker.command     # chạy monitor + app -> http://localhost:5050
```
- Telegram: tạo bot qua @BotFather, nhắn 1 tin cho bot, lấy chat id ở `https://api.telegram.org/bot<TOKEN>/getUpdates`.
- `HELIUS_API_KEY` (free): bắt buộc cho Solana. `ZERION_API_KEY` (free dev): chấm PnL/winrate ví + phát hiện insider/bundler.
  Không có Zerion -> chấm điểm chỉ dựa trên giao dịch bot đã thấy.
- Mở app từ điện thoại cùng wifi: `python -m wallet_tracker run --host 0.0.0.0` và đặt `WT_WEB_PASSWORD` trong `.env`.

## App web
| Màn hình | Nội dung |
|---|---|
| Tổng quan | Equity từng book, biểu đồ 30 ngày, lệnh đang mở, tín hiệu mới |
| Ví | Thêm ví, quét người mua sớm (discover), **lọc kiểu Wallet Radar** (chain, trạng thái, nhãn, winrate/PnL/số token 30D, vào sớm), đổi trạng thái |
| Chi tiết ví | PnL/winrate 7D-30D, thời gian giữ, nhãn + lý do, token vào sớm, tín hiệu, lệnh paper, link Explorer/GMGN/Zerion, chấm điểm ngay |
| Danh mục | Token các ví theo dõi đang nắm (Zerion), sắp theo số ví cùng nắm, tổng giá trị, link chart |
| Cách hoạt động | Logic tín hiệu, bộ lọc, luật thoát lệnh với tham số hiện tại |
| Tín hiệu | Mọi lệnh mua / mua thêm / bán một phần / bán hết, lý do bị chặn, kết quả paper |
| Lệnh paper | Lọc book/trạng thái, từng lần khớp (TP nấc, trailing, bán theo ví) |
| Cài đặt | Sửa mọi tham số (ngưỡng, luật thoát lệnh từng book), blacklist token |

## CLI
```bash
python -m wallet_tracker add base 0x0f9a... --note "kol"   # --sniper: chỉ alert
python -m wallet_tracker import wallet_tracker/wallets_manual.csv
python -m wallet_tracker discover base <token>
python -m wallet_tracker score [chain ví]                  # chấm 1 ví hoặc các ví đến hạn
python -m wallet_tracker blacklist add '*' <token> --reason scam
python -m wallet_tracker set MIN_LIQUIDITY_USD 50000       # xem/sửa tham số (JSON)
python -m wallet_tracker positions                       # cập nhật danh mục token ví đang nắm
python -m wallet_tracker doctor                          # kiểm tra kết nối
python -m wallet_tracker list [--all] | report | once | daily | monitor | web
```
Telegram: `/add <chain> <ví> [ghi chú]`, `/remove <chain> <ví>`, `/list`, `/stats`.

## Kiến trúc (thêm tính năng rẻ)
```
chains/      adapter theo loại chain (registry ADAPTERS)        -> thêm chain: config.CHAINS hoặc 1 class
providers/   nguồn lịch sử ví (Zerion, local)                    -> thêm Birdeye...: 1 class
filters.py   bộ lọc tín hiệu (@signal_filter)                    -> thêm bộ lọc: 1 hàm
exits.py     luật thoát lệnh (@rule)                             -> thêm luật: 1 hàm + khai báo trong BOOKS
scoring.py   chỉ số + nhãn ví (@labeler)                         -> thêm nhãn: 1 hàm
events.py    signal / position_fill / wallet_changed             -> tính năng mới = subscriber
plugins.py   danh sách subscriber (paper, alerts, + WT_PLUGINS)  -> webhook / Discord / giao dịch thật
settings.py  tham số lưu DB, sửa trên app                        -> thêm tham số: 1 dòng trong config.DEFAULTS
web/         Flask: 1 route + 1 template mỗi màn hình
```
Luồng: `monitor` lấy swap từ adapter → dựng `Signal` (mua / mua thêm / bán %) → `filters` → lưu → `events.emit("signal")`
→ `paper` mở/bán theo → `alerts` gửi Telegram. Mỗi 6h: chấm điểm ví → tự thêm ứng viên đạt chuẩn → auto-discovery → tắt ví lỗ.

## Nhãn ví
| Nhãn | Ý nghĩa | Mặc định |
|---|---|---|
| `sniper` | vào < 60s sau khi mở pool | chỉ alert |
| `insider` | được creator token nạp tiền | chặn |
| `bundler` | ≥ 3 ví mua sớm chung nguồn nạp tiền | chặn |
| `wash_trader` | ≥ 10 lệnh/giờ cùng token, hòa vốn | chặn |
| `bot_flipper` | ≥ 50% token bán trong < 60s | chặn |
| `high_winrate` | win ≥ 60%, ≥ 10 token 30D, lãi | — |
| `losing` | PnL 30D âm | — |

Danh sách chặn sửa ở `BLOCK_LABELS`.

## Giới hạn
- Discovery chỉ EVM; Solana thêm ví bằng tay. Bundler có thể nhầm khi nguồn nạp tiền là ví sàn (CEX).
- Lần đầu chạy chỉ đặt mốc, không quét lịch sử. Solana: > 100 tx mới giữa 2 vòng poll sẽ sót tx cũ.
- RPC public có giới hạn; lỗi nhiều thì điền RPC riêng trong `.env`.
- Định dạng Zerion API theo tài liệu công khai, chưa chạy thử với key thật.

## Test
```bash
python -m pytest wallet_tracker/test_wallet_tracker.py
```
