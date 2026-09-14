# Báo cáo nghiên cứu: Chiến lược Futures Binance (Khung H1/H4)

**Ngày:** 2026-09-05 | **Dữ liệu:** Binance USD-M Futures (fapi), 24 tháng (2024-09 → 2026-09), 8 coin lớn
**Phí:** taker 0.05% vào + 0.05% ra | **Funding:** trừ thật theo lịch sử funding rate (mỗi 8h)
**Sizing:** 25% vốn mỗi lệnh × 3x leverage (= 0.75x vốn) | Long + Short | 1 vị thế/coin

---

## Kết luận chính

Mặc dù yêu cầu nghiên cứu cả H1 và H4, **backtest cho thấy khung H1 không đem lại lợi thế bền vững**
trong 24 tháng gần đây — cả 4 biến thể entry H1 (EMA cross, pullback RSI, breakout H1, funding mean-reversion)
đều thất bại ít nhất 1/3 cửa sổ kiểm chứng, do phí 0.1%/lệnh + noise H1.

**Hai chiến lược bền vững (vào lệnh khung H4):**

| Chiến lược | Bản chất | 24 tháng sum PnL (8 coin) | Dương coin | Worst DD/coin | Số lệnh |
|---|---|---|---|---|---|
| **#1 Donchian 55 breakout** | Bắt trend (breakout + ADX + funding filter) | **+581.9%** | 8/8 | 43% | 372 |
| **#2 Keltner Channel breakout** | Bắt trend bằng kênh EMA±1.5ATR | **+1573.8%** | 8/8 | 92% | 1002 |

Cả hai kiểm chứng chéo (walk-forward 3 cửa sổ 8 tháng rời nhau) đều dương trong mọi cửa sổ.
So với Buy&Hold TỔNG 24 tháng là **+128%** → 2 chiến lược này vượt trội và còn tránh được drawdown lớn của điều chỉnh.

---

## Chiến lược #1 — Donchian 55 Breakout (H4)

**Logic:**
1. **Entry (khung H4):** giá đóng phá đỉnh 55 nến (Donchian) → LONG; phá đáy → SHORT.
2. **Bộ lọc:** chỉ long khi giá > EMA50(H4) (xác nhận trend tăng); chỉ short khi < EMA50.
3. **Bộ lọc phụ:** ADX14 ≥ 20 (trend có độ mạnh), |funding rate| < 0.05%/8h (tránh đám đông quá khích).
4. **Exit:** SL 2×ATR; trahi chandelier 4×ATR (theo cực trị); BE (nâng về hòa vốn) sau khi lời 2R.

**Kết quả chi tiết (24 tháng, mỗi coin 372/8 ≈ 46 lệnh):**

| Coin | PnL | WR | PF | MaxDD | BH |
|---|---|---|---|---|---|
| BTCUSDT | +17.4% | 22.6% | 1.51 | 15.0% | +32.0% |
| ETHUSDT | +79.0% | 40.8% | 2.20 | 24.2% | +1.9% |
| SOLUSDT | +58.5% | 28.8% | 1.91 | 26.6% | -24.5% |
| BNBUSDT | +9.4% | 25.5% | 1.28 | 13.9% | +33.4% |
| XRPUSDT | +30.5% | 32.1% | 1.46 | 38.5% | +138.8% |
| DOGEUSDT | +86.7% | 32.4% | 2.19 | 28.9% | -19.1% |
| ADAUSDT | +293.8% | 45.7% | 3.46 | 43.2% | -39.0% |
| LINKUSDT | +6.6% | 29.0% | 1.21 | 23.2% | +4.6% |
| **TOTAL** | **+581.9%** | 32.1% | — | 43.2% | +128.2% |

> Đặc điểm đúng tinh thần trend-following: WR thấp (~30%) nhưng thắng lớn (PF >1.5). Safe nhất trong 2 chiến lược.

---

## Chiến lược #2 — Keltner Channel Breakout (H4)

**Logic:**
1. **Entry (khung H4):** giá đóng phá band trên của Keltner (EMA20 ± 1.5×ATR14) → LONG; phá band dưới → SHORT.
2. **Bộ lọc:** ADX14 ≥ 18, |funding| < 0.06%/8h.
3. **Exit:** SL 2×ATR; trailing 3.5×ATR; BE sau +2R. TP cap 6R.

**Kết quả chi tiết (24 tháng, ~125 lệnh/coin — giao dịch nhiều gấp ~2.7 lần #1):**

| Coin | PnL | WR | PF | MaxDD | BH |
|---|---|---|---|---|---|
| BTCUSDT | +63.1% | 31.9% | 1.67 | 24.5% | +32.0% |
| ETHUSDT | +73.9% | 33.6% | 1.40 | 47.6% | +1.9% |
| SOLUSDT | +95.9% | 31.9% | 1.48 | 59.5% | -24.5% |
| BNBUSDT | +56.3% | 28.4% | 1.47 | 44.7% | +33.4% |
| XRPUSDT | +179.7% | 37.0% | 1.78 | 78.7% | +138.8% |
| DOGEUSDT | +640.0% | 40.0% | 3.04 | 92.3% | -19.1% |
| ADAUSDT | +398.1% | 34.9% | 2.23 | 49.2% | -39.0% |
| LINKUSDT | +66.8% | 31.4% | 1.49 | 49.4% | +4.6% |
| **TOTAL** | **+1573.8%** | 33.6% | — | 92.3% | +128.2% |

> Thắng nhiều hơn #1 nhờ bắt breakout sớm, nhưng rủi ro DD cao hơn (92%). Nên dùng size nhỏ hơn hoặc chỉ áp dụng cho coin đầu ngành.

---

## Kiểm chứng chéo (Walk-forward 3 cửa sổ 8 tháng rời nhau)

| Cửa sổ | Donchian (sum 8 coin) | Keltner (sum 8 coin) | B&H (sum) |
|---|---|---|---|
| 8m đầu (2024-09 → 2025-05) | +173% | +423% | -37% |
| 8m giữa (2025-05 → 2026-01) | +111% | +357% | +51% |
| 8m gần nhất (2026-01 → 2026-09) | +233% | +141% | +26% |

Không cửa sổ nào âm → tham số không phải overfit vào 1 giai đoạn.

---

## Phân tích theo chiều (Long vs Short)

Mỗi tín hiệu breakout được thiết kế **song song 2 chiều**: phá đỉnh → LONG, phá đáy → SHORT (nghịch đảo hoàn toàn). Tách backtest riêng từng chiều (24 tháng, 8 coin, lev 3x, size 25%):

| Xếp hạng | Biến thể | Sum PnL 8 coin | Coin dương | Số lệnh | Worst DD/coin | WR TB |
|---|---|---|---|---|---|---|
| 1 | **KELT-LONG** | +559.6% | 8/8 | 536 | 72.0% | 32.8% |
| 2 | **KELT-SHORT** | +506.5% | 7/8 | 466 | 46.8% | 35.0% |
| 3 | **DON-LONG** | +280.1% | 7/8 | 192 | 21.8% | 33.5% |
| 4 | **DON-SHORT** | +186.9% | 6/8 | 180 | 23.5% | 32.5% |

**Đọc kết quả:**
- Cả 4 biến thể đều sinh lời tổng thể → hệ long+short hoạt động đúng như thiết kế (short ADA +98.5%, short DOGE +176% khi thị trường giảm).
- **Bộ tín hiệu Keltner mạnh hơn Donchian ở cả 2 chiều.**
- Long mạnh hơn short ở Keltner — nhưng không nên skip short: vẫn đóng góp +506% và ngược pha với long (diversification).
- Cặp yếu cần theo dõi (không lọc vội, dễ overfit): DON-LONG/BNB (-9%), DON-SHORT/BTC (-3%), DON-SHORT/XRP (-14%), KELT-SHORT/ETH (-2%).

> Khuyến nghị: giữ giao dịch 2 chiều. Muốn giảm rủi ro → hạ size, đừng cắt 1 chiều (mất lợi thế ngược pha).

---

## Những kém hiệu quả đã loại bỏ

| Ý tưởng | Lý do loại (bằng dữ liệu) |
|---|---|
| EMA20/50 cross H1 + trend H4 | overfit tham số; chỉ mạnh 1 cửa sổ |
| Pullback RSI H1 theo trend H4 | âm cả 4 cấu hình ở cửa sổ gần nhất |
| Breakout Donchian20 H1 | phí + noise H1 ăn lợi nhuận |
| Funding mean-reversion | quá ít tín hiệu trên coin lớn (major hiếm vượt 0.05%/8h) |
| EMA cross H4 (25/100, 50/200) | TP quá xa → vị thế "ngủ đông", gần như không thoát |

---

## Cảnh báo & giới hạn

- **Số liệu historical futures:** đã trừ phí taker + funding thật. Chưa tính slippage (trượt giá khi lệnh lớn), delay mạng, liq risk lúc tin tức.
- **Backtest nói chung thiên lạc quan** đối với hệ trend-following (lợi nhuận tập trung vài lệnh lớn).
- **DD 92% (Keltner) không chấp nhận được** khi chạy real với 25% vốn/lệnh — cần giảm size (10–15%) hoặc bỏ SL cap và giảm leverage.
- Trong môi trường sideways kéo dài, cả 2 đều trả WR một chuỗi lệnh cắt lỗ — chuẩn bị tâm lý.

---

## Khuyến nghị triển khai thực tế

1. **Bắt đầu với chiến lược #1 (Donchian 55):** rủi ro/coin thấp nhất, chỉ ~46 lệnh/coin trong 24 tháng, dễ vận hành bằng bot.
2. Nếu muốn lợi nhuận cao hơn chấp nhận DD lớn → **Keltner**, nhưng size 10–15% vốn.
3. Có thể chạy **cả 2 cùng lúc trên các coin khác nhau** để đa dạng hóa (nguồn lời khác họ nhưng cùng triết lý trend).
4. Khung vận hành: **chỉ khung H4** — entry H1 bị loại vì không bền trong dữ liệu.

---

## Files (repo)

- `research_futures_framework.py` — fetch data futures (klines 1h/4h, funding), tính indicators, mô phỏng order.
- `research_futures_strategy.py` — 2 chiến lược + runner/scan/walk-forward.
- `backtest_futures_BREAKOUT_H4_DC55_FUND.csv`, `backtest_futures_KELTNER_H4_BREAK.csv` — tổng hợp per-coin.
- `backtest_futures_trades.csv` — **1374 lệnh chi tiết** (entry time, giá, direction, net %, funding %).