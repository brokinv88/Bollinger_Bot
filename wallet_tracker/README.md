# Wallet Tracker

Theo dõi ví mua sớm / smart money / sniper → **alert Telegram + paper trade**. Không dùng private key, không swap thật.
Plan: [`docs/wallet_tracker_plan.md`](../docs/wallet_tracker_plan.md).

## Cài đặt (máy local)
```bash
cp wallet_tracker/.env.example wallet_tracker/.env   # điền Telegram bot riêng + HELIUS_API_KEY
./.venv/bin/pip install requests
```
- Telegram: tạo bot mới qua @BotFather, nhắn 1 tin cho bot, lấy chat id ở `https://api.telegram.org/bot<TOKEN>/getUpdates`.
- Solana cần `HELIUS_API_KEY` (free). EVM (Base/BSC/ETH) dùng RPC public sẵn. Robinhood Chain bật khi điền `ROBINHOOD_RPC_URL` + `ROBINHOOD_QUOTES`.

## Dùng
```bash
python -m wallet_tracker add base 0x0f9a... --note "vào sớm 6 phút"   # thêm ví smart money
python -m wallet_tracker add solana <ví> --sniper                    # sniper: chỉ alert
python -m wallet_tracker import wallet_tracker/wallets_manual.csv    # nhập hàng loạt (chain,address,note)
python -m wallet_tracker discover base <token>                       # quét người mua sớm của token thắng
python -m wallet_tracker list [--all]
python -m wallet_tracker monitor                                     # chạy liên tục (hoặc ./run_wallet_tracker.command)
python -m wallet_tracker report
```
Telegram (chỉ nhận từ chat đã cấu hình): `/add <chain> <ví> [ghi chú]`, `/remove <chain> <ví>`, `/list`, `/stats`.

## Cơ chế
- **Phát hiện swap**: EVM theo ERC20 Transfer vào/ra ví trong tx do chính ví gửi (bỏ qua airdrop spam); Solana qua Helius parse.
- **Lọc token**: thanh khoản ≥ $100k, không honeypot, tax ≤ 10% (GoPlus, EVM).
- **Paper**: 2 book, mỗi book $1000, $100/lệnh, phí+trượt giá 1.5% mỗi chiều, giá vào = giá lúc bot *phát hiện*.
  - `fixed`: TP +100%, SL −30%, tối đa 72h. `mirror`: bán khi ví nguồn bán, SL −50%, tối đa 7 ngày.
- **Hợp lưu**: ≥ 2 ví theo dõi mua cùng token trong 1h → đánh dấu 🔥.
- **Tự thêm ví**: người mua trong 60 phút đầu của token thắng → `candidate`; vào sớm ≥ 2 token → tự theo dõi
  (`watch_only` nếu trễ trung vị < 60s = sniper, ngược lại `active`). Monitor tự chạy discovery mỗi 6h cho token mà
  ví theo dõi mua rồi tăng ≥ 5x.
- **Tự tắt ví**: ví discovery có ≥ 10 lệnh paper đóng mà tổng lỗ → `disabled` (ví nhập tay chỉ cảnh báo).

## Giới hạn Phase 1
- Discovery chỉ EVM; Solana thêm ví bằng tay.
- Lần đầu chạy chỉ đặt mốc, không quét lịch sử. Solana: > 100 tx mới giữa 2 vòng poll sẽ bị sót tx cũ.
- RPC public có giới hạn tốc độ; nếu lỗi nhiều, điền RPC riêng (Alchemy/QuickNode free) trong `.env`.

## Test
```bash
python -m pytest wallet_tracker/test_wallet_tracker.py
```
