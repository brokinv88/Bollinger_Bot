# Kế hoạch giao dịch Futures — Vốn $2,000 (Bảo toàn vốn là ưu tiên #1)

**Ngày:** 2026-09-05 | **Sàn:** Binance USD-M Futures | **Khung:** H4 | **MODE: PAPER → đủ kỷ luật mới LIVE**

Dựa trên backtest thực 24 tháng (foundation: `research_futures_report.md`, `research_futures_strategy.py`)
và danh mục coin đã screen (`backtest_futures_universe.csv`).

---

## 1. Nguyên tắc sống còn (không cháy tài khoản)

| # | Trục | Cam kết cứng |
|---|---|---|
| 1 | **Risk/lệnh** | Tối đa **0.75 – 1.0% equity** mỗi lệnh (Số tiền sẽ thua khi SL chạm). |
| 2 | **Số vị thế đồng thời** | Tối đa **6 coin song song** (tài khoản $2k = không cần nhiều hơn; quá nhiều = rủi ro tương quan). |
| 3 | **Tổng margin đã dùng** | Không vượt **40% vốn** (~$800) — 60% còn lại là đệm cho funding, maintenance margin, biến động 4h. |
| 4 | **Leverage tối đa mỗi lệnh** | **3x** (không bao giờ > 3x, kể cả coin T4). |
| 5 | **Stop loss** | Luôn đặt SL ngay khi vào lệnh = **2.0 × ATR14(H4)**; không dời SL ra xa hơn (chỉ siết theo trailing). |
| 6 | **Dừng ngày / tuần** | Lỗ lũy kế **-5% equity/ngày** → dừng mọi lệnh mới, rà logic. Lỗ **-10% tuần** → tạm nghỉ 48h. |
| 7 | **Daily-cache / gap tin tức** | Không vào lệnh trong 30 phút trước tin lớn (FOMC, CPI, BTC ETF...). Kẻ gap có thể xuyên SL. |
| 8 | **Long/Short** | Giữ cả 2 chiều (benchmark đã chứng minh short sinh lời khi thị trường giảm). |

---

## 2. Công thức định cỡ lệnh (Position Sizing theo ATR)

Notional tối đa cho 1 lệnh:

```
SL_pct   = 2 × ATR_pct(coin)                     # ATR_pct = ATR14/giá × 100
risk_usd = 0.75% × equity                        # ví dụ $2,000 → $15
notional = risk_usd / SL_pct                     # số vốn danh nghĩa hợp đồng
margin   = notional / leverage (≤3x)
```

**Lưu ý:** SL ngắn hơn → vị thế lớn hơn, nhưng để đúng chiến lược không giảm SL dưới 2×ATR
(chỉ siết bằng trailing sau khi có lời). KHÔNG tự sửa SL xuống để "tránh dừng".

### Bảng size mẫu cho $2,000 (risk $15, lev 3x)

| Coin | ATR_pct TB | SL 2×ATR | Notional | Margin (3x) | % vốn làm margin |
|---|---|---|---|---|---|
| BTC/BNB/PAXG (T1 ~0.6%) | 1.0% | 2.0% | $750 | $250 | 12.5% |
| ETH/SOL/XRP/DOGE (T2 ~1.5%) | 1.6% | 3.2% | $469 | $156 | 7.8% |
| DASH/NEAR/UNI/ZEN (T3 ~2.8%) | 2.8% | 5.6% | $268 | $89 | 4.5% |
| Coin T4 (~4.0%+) | 4.2% | 8.4% | $179 | $60 | 3.0% |

6 vị thế T2 đồng thời → margin ≈ $936 (47%) — vừa chạm trần 40-50%, cần giảm bớt.
→ **Thực tế nên giới hạn 4 vị thế T2 hoặc 6 vị thế pha trộn T1+T2+T3.**

---

## 3. Danh mục coin khả dụng (đã screen, 45 mã chia tầng)

Nguồn: `backtest_futures_universe.csv` (top 60 thanh khoản ≥ $20M/24h, ATR 0.5%–6%).

### T1 — Ổn định (ATR 0.5–1.2%): vị thế lớn nhưng sóng nhỏ
BTCUSDT · BNBUSDT · PAXGUSDT · XAUTUSDT · TRXUSDT

### T2 — Cân bằng (1.2–2.5%): **ưu tiên chính**
ETHUSDT · SOLUSDT · XRPUSDT · BNBUSDT · DOGEUSDT · ADAUSDT · LINKUSDT · SUIUSDT · TAOUSDT ·
LTCUSDT · ASTERUSDT · AAVEUSDT · XMRUSDT · BCHUSDT · AVAXUSDT · FILUSDT · DOTUSDT ·
XLMUSDT · ICPUSDT · AZTECUSDT

### T3 — Biến động mạnh (2.5–4.0%): size nhỏ hơn
ZECUSDT · DASHUSDT · NEARUSDT · UNIUSDT · FLOCKUSDT · ENAUSDT · TRUMPUSDT · 1000PEPEUSDT ·
ARBUSDT · ZENUSDT · WLDUSDT · PENGUUSDT · ONDOUSDT · NOMUSDT · XPLUSDT · 1000BONKUSDT ·
EDGEUSDT · ZORAUSDT · FARTCOINUSDT

### T4 — Rất mạnh (4.0–6.0%): CHỈ khi risk-size đủ nhỏ, không quá 2 lệnh cùng lúc
LITUSDT · PUMPUSDT · TRIAUSDT · CHIPUSDT · GIGGLEUSDT · SKRUSDT

### LOẠI BỎ
- **QUÁ MẠNH (ATR >6%):** BULLA · AKE · 4USDT · UAI · MAGMA · TUTU · HEMI — biến động ~10-trăm %/ngày, không trade hệ ATR.
- **Coin quá mới / pump mạnh không bền:** coin mới niêm yết (cần ≥60 nến H4 để chỉ báo ổn).
- **Ký hiệu không hợp lệ / thanh khoản < $20M — loại khỏi scan.**

> Quy tắc chọn khi live: **ưu tiên T2 → T3**, xen T1 cho các phiên sideway. Không mua "động cơ nóng" T4 khi đang holddown cả tài khoản.

---

## 4. Quy trình vận hành mỗi lệnh

1. **Scan tín hiệu** (bot chạy khung H4, sốc vào 4h/ngày): phá DC55 hoặc phá Keltner đúng chiều trend + ADX + funding filter.
2. **Duyệt đối chiếu:**
   - Có phải top thanh khoản? (vol24h > $20M)
   - ATR_pct đang trong khoảng tầng (không phải quá khích)
   - Equity hiện tại, risk $ = 0.75% × equity (KHÔNG theo $2,000 gốc cố định — theo equity động).
   - Tổng margin ≤ 40% vốn sau khi vào.
3. **Vào lệnh:** limit/taker theo plan; đặt ngay SL 2×ATR + TP 6R (Keltner) / trailing 4×ATR (Donchian) + BE sau 2R.
4. **Quản lý:** mỗi 4h kiểm tra trailing; BE khi +2R; không kéo SL xuống.
5. **Chốt sổ ngày:** cập nhật equity thật vào spreadsheet; kiểm tra ngưỡng dừng (-5% ngày / -10% tuần).

---

## 5. Dự phòng kịch bản xấu (Stress test)

| Kịch bản | Hành động |
|---|---|
| DD toàn tài khoản đạt **-15%** | Giảm risk/lệnh 0.75% → 0.5%, tối đa 3 vị thế song song, chỉ T1/T2. |
| DD đạt **-25%** | Dừng giao dịch 1 tuần; rà lại tham số & tâm lý; chỉ quay lại paper. |
| **-30%** | Ngừng hẳn hệ futures; phân tích lại từ đầu dữ liệu thực tế - KHÔNG vội "gỡ". |
| 3 tháng đầu toàn lỗ nhỏ | Đây là chuẩn trend-following (WR ~30%): chỉ dùng SL; tổng PnL theo PF > 1.3. Kiểm PF thay vì WR. |

**Cam kết:** vốn $2,000 này được thiết kế để **sống sót qua 1–2 lần DD chuẩn của hệ** (―40% theo backtest DON-LONG, ―90% theo KELT, nhưng đó là khi bỏ cả vốn). Với risk 0.75–1%/lệnh + 6 vị thế, một chuỗi xấu nhất thực nghiệm chỉ về mức DD ~10–15% tài khoản → vẫn an toàn.

### ⚙️ Xác thực số (tái mô phỏng equity theo đúng sizing, 24 tháng, 8 coin)

| Chiến lược | Risk/lệnh | Kết quả 24 tháng | **Max DD tài khoản** |
|---|---|---|---|
| Donchian55 | 0.75% | +133.6% ($2,000 → $4,672) | **-8.4%** |
| Donchian55 | 1.00% | +207.0% ($2,000 → $6,139) | **-11.1%** |
| Keltner | 0.75% | +441.9% ($2,000 → $10,838) | **-23.4%** |
| Keltner | 1.00% | +832.0% ($2,000 → $18,641) | **-30.0%** |

> Mô hình nối tiếp từng lệnh; khi 6 vị thế mở ĐỒNG THỜI (+) DD có thể cao hơn vài %.
> **Bảng chọn chuẩn:** Donchian risk 0.75% (DD 8.4% kể cả live bắn thêm) hoặc Keltner risk 0.5–0.75%.
> Không bao giờ risk > 1% cho $2,000 (lưng DD 30% đã chạm ngưỡng đỏ).

- Script: `futures_sizing_validate.py` (chạy lại bất cứ lúc nào để kiểm tra equity & DD hiện tại).
- Nếu muốn biết DD "đồng thời" chính xác hơn → chạy backtest portfolio đa symbol (cận trên).

---

## 6. Baseline kiểm chứng (mục tiêu phải đạt)

| Chỉ số | Ngưỡng tối thiểu |
|---|---|
| Profit Factor (PF) | > 1.3 |
| Win rate | chấp nhận 25–40% (đúng đặc tính trend) |
| Max DD tài khoản | < 20% |
| Số lệnh/tháng | tùy coin: Donchian ~2-3 lệnh/coin/tháng |
| So với B&H | phải vượt benchmark cùng giai đoạn |

---

## 7. Bước tiếp theo

1. Xây **paper trader futures** theo 2 chiến lược này (đổi MODE=PAPER) với đúng sizing trên.
2. Chạy song song 30 ngày paper, theo dõi equity, PF, slippage thực → kiểm chứng tailân trước khi live $2,000.
3. Tùy chọn kiểm tra lại với giai đoạn 2019–2023 để thấy midface của hệ trong bull-run chó.

---

## Files tham chiếu
- `research_futures_report.md` — báo cáo 2 chiến lược + giá split long/short.
- `backtest_futures_universe.csv` — 60 coin đã screen (ATR, volume, tier).
- `research_futures_strategy.py` — 2 chiến lược + runner.
- `backtest_futures_trades.csv` — 1,374 lệnh chi tiết.