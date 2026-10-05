# Plan: Wallet Tracker — theo dõi ví mua sớm / smart money / sniper để copy trade

> Trạng thái: DRAFT — chưa code. Chế độ: **Alert Telegram + Paper trade** (không dùng private key, không swap thật).

## 1. Phạm vi đã chốt
| Hạng mục | Quyết định |
|---|---|
| Chain | Solana, Base, BSC, Ethereum, Robinhood Chain |
| Mức tự động | Alert Telegram + paper trade |
| Data | Free tier (public RPC / Helius free / DexScreener / GeckoTerminal / GoPlus) |
| Nguồn ví | Nhập tay + bot tự tìm & chấm điểm |
| Code | Module riêng `wallet_tracker/`, không đụng code Bollinger/futures |

## 2. Kiến trúc
```
wallet_tracker/
  config.py          # chain, RPC URL, ngưỡng lọc, TP/SL paper (đọc env, không hardcode key)
  db.py              # SQLite: wallets, wallet_trades, tokens, signals, paper_positions
  chains/
    base.py          # interface: get_swaps(wallet, since) -> list[Swap]; get_early_buyers(token, window)
    evm.py           # Base / BSC / ETH / Robinhood: eth_getLogs (Transfer + Swap Uniswap V2/V3) theo topic ví
    solana.py        # getSignaturesForAddress + parse swap (Raydium/pump.fun/Jupiter); Helius free parse API
  discovery.py       # tìm token đã x5+ (DexScreener/GeckoTerminal) -> lấy người mua trong N phút đầu
  scoring.py         # chấm & gắn nhãn ví
  monitor.py         # vòng lặp poll ví đang theo dõi -> phát hiện lệnh MUA mới
  safety.py          # lọc token: honeypot/tax (GoPlus), thanh khoản, tuổi pool, holder concentration
  paper.py           # mô phỏng vào/ra lệnh có độ trễ + slippage + phí
  alerts.py          # dùng lại notifier.send_telegram_alert
  report.py          # báo cáo hiệu quả theo ví / theo nhãn / theo chain
  wallets_manual.csv # danh sách ví nhập tay (address, chain, note)
```

## 3. Luồng chạy
1. **Discovery (1 lần/ngày)**: token có giá ≥ 5x từ lúc mở pool, thanh khoản ≥ $X → lấy ví mua trong 60 phút đầu.
2. **Scoring**: với mỗi ví, kéo lịch sử swap 30–90 ngày, tính:
   - số lần vào sớm, winrate, PnL đã chốt, expectancy/lệnh, thời gian giữ trung vị
   - thời gian từ lúc mở pool → lúc mua (giây/block)
   - nguồn nạp tiền (có trùng deployer/ví funding chung không)
3. **Gắn nhãn**:
   - `sniper`: mua trong ≤ 1–2 block / < 60s, giữ ngắn → chỉ dùng làm *tín hiệu tham khảo*, KHÔNG copy (không thể vào kịp)
   - `insider`: được nạp tiền từ deployer/cụm ví deployer → cờ đỏ cho token, không copy
   - `smart_money`: vào sớm nhưng không phải bot, ≥ 10 lệnh, winrate & expectancy dương, giữ ≥ vài giờ → **đối tượng copy chính**
   - `bot/mev`: tần suất cực cao, sandwich → loại
4. **Monitor**: poll ví `smart_money` + ví nhập tay mỗi 15–60s (tùy rate limit) → có lệnh mua mới → `safety.py` → nếu pass: alert + mở lệnh paper.
5. **Tín hiệu hợp lưu** (ưu tiên cao): ≥ 2–3 ví smart money mua cùng token trong 1 giờ.
6. **Paper exit**: TP/SL/trailing cố định *hoặc* bán theo khi ví nguồn bán (chạy cả 2 để so sánh).

## 4. Hosting
- Discovery + scoring + report: **GitHub Actions** cron hằng ngày (giống các workflow hiện có).
- Monitor: cần process chạy liên tục — GitHub Actions cron tối thiểu 5 phút và hay bị trễ → **không đủ nhanh**. Dùng máy local (`start_local.sh`) hoặc VPS free (Oracle Cloud Always Free).
- Paper trade vẫn ghi nhận độ trễ thực tế của setup này → kết quả phản ánh đúng khả năng copy thật.

## 5. Lộ trình
| Phase | Nội dung | Gate để qua phase sau |
|---|---|---|
| P1 | Solana + Base: adapter, DB, nhập ví tay, monitor + alert | Alert đúng ≥ 95% lệnh mua thật của 5 ví test, trễ < 60s |
| P2 | Discovery + scoring + nhãn | Kiểm tra tay 20 ví được nhãn smart_money, ≥ 80% hợp lý |
| P3 | Safety + paper trade + report | Chạy ổn 1 tuần |
| P4 | Thêm BSC + ETH | — |
| P5 | Robinhood Chain | Xác nhận có RPC public, DEX có thanh khoản, explorer API (L2 Arbitrum Orbit, EVM → tái dùng `evm.py`) |
| Gate tiền thật | ≥ 4 tuần paper, ≥ 100 tín hiệu, expectancy > 0 **sau** trễ + slippage + phí, max drawdown chấp nhận được | Mới bàn tiếp auto trade |

## 6. Munger check (rủi ro chính)
- **ĐẢO**: copy = luôn vào *sau* ví nguồn → mình là thanh khoản thoát hàng của họ. Sniper vào trong vài giây; với free tier poll 15–60s, copy sniper gần như chắc chắn lỗ. → Chỉ copy ví giữ lâu (smart_money), sniper chỉ là tín hiệu.
- **NÃO (survivorship)**: chọn ví từ token đã x10 sẽ thổi phồng winrate. → Scoring phải tính *toàn bộ* lệnh của ví, kể cả token chết/rug.
- **LỢI**: ví "smart money" công khai thường bị theo dõi bởi nhiều bot → edge giảm; một số ví cố tình mua nhỏ để dụ người copy rồi xả. → Theo dõi edge decay theo thời gian, loại ví có expectancy giảm.
- **Paper quá đẹp**: phải mô phỏng giá tại thời điểm *phát hiện* + slippage theo thanh khoản pool, không dùng giá vào của ví nguồn.

## 7. Câu hỏi còn mở (trả lời trước khi code P1)
1. Vốn giả lập mỗi lệnh paper (vd $100) và tổng vốn?
2. Ngưỡng thanh khoản tối thiểu của token (vd $20k)?
3. Có Telegram bot token sẵn trong `config.py`/secrets chưa — dùng chung chat hay chat riêng?
4. Monitor chạy trên máy bạn hay VPS?
5. Danh sách ví nhập tay ban đầu (address + chain)?
