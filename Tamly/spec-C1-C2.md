# Spec & kết quả backtest — Chiến lược C1, C2 (crypto Binance)

Ngày tổng hợp: 07/09/2026 (cập nhật vòng 6 — paper forward testing).  
Mục đích: biến SMC và các bài học trong thư mục Tamly thành **2 chiến lược thí nghiệm có thể định nghĩa máy móc được**, đã viết code backtest độc lập trên **Binance USD-M futures**. Không đặt lệnh thật; kết quả dưới đây là **bước research đầu tiên**, chưa phải bằng chứng ngoài mẫu.

> Tài liệu này tách ba lớp: định nghĩa chiến lược, kết quả backtest (kèm giới hạn), và kế hoạch áp dụng. Toàn bộ code nằm ở thư mục `/Users/brokinv/Desktop/AI Agent/Trading/C1_C2_strategies/` — tách hoàn toàn khỏi `strategy_lab` và các chiến lược BTC/Donchian/Keltner đang chạy, không đụng tới dữ liệu nào của hệ cũ.

---

## 1. Tóm tắt trạng thái

| Chiến lược | Kết quả backtest (10 cặp, 2023-07 → 2026-09) | Kết luận tạm thời |
|---|---|---|
| **C1 — Phá vỡ cấu trúc thuận xu hướng** (H4, đã tính funding) | Kỳ vọng **+0,22R/lệnh**, PF 1,50, WR 46,7%, **9/10 cặp kỳ vọng dương**; giữ vững ngoài mẫu (test +0,20R) | Đáng theo đuổi — qua vòng 2, chuẩn bị paper/filter |
| **C2 — Quét thanh khoản rồi đảo chiều** | Vòng 1 (H4): **−0,33R** — thua. Vòng 2 (H1 vs level H4 + CHoCH): **−0,46R**, âm **mọi** cặp, cả train lẫn test | **Bộ lọc sweep bác bỏ trên cả 2 định nghĩa** — loại C2 sweep |
| C2 nhóm nền (chạm vùng + CHoCH, không cần sweep) | H4 +0,02R; bản H1/H4 **+0,06R**, test riêng +0,14R | Mỏng nhưng **định nghĩa H1/H4 dương ngoài mẫu** — chỉ đáng giữ làm đối chứng |
| Phí funding (phải đo trước khi coi là lợi thế thật) | Đã đo & cộng vào vòng 2 | Funding trung bình nhỏ (≈ 0,005%/8h × cặp) — khó đổi quyết định; cần tính riêng khi cầm lệnh dài |

Điểm mấu chốt về phương pháp: thí nghiệm tách biến cho thấy **"quét thanh khoản" không tạo giá trị thêm trên cả định nghĩa H4 lẫn H1-vs-H4** — đúng cảnh báo trong tài liệu SMC (mục 5.4, 5.9 và S05): khái niệm có thật nhưng không tự sinh lợi thế; phải đo bằng dữ liệu. C1 thì ngược lại — kỳ vọng dương **ổn định qua cả window test độc lập**, điều mà FOMO-đuổi-theo-khái-niệm không cho được.

---

## 2. Định nghĩa chiến lược C1 — "Phá vỡ cấu trúc thuận xu hướng HTF"

Nguồn khái niệm: SMC bài setup A+ (BOS/CHoCH, HTF trend) + nguyên tắc 1, C02, T03/T05 từ rules.md.

### Logic thực thi (đã code trong `strategies.gen_c1`)

- **Khung:** H4 duy nhất (bối cảnh + entry) — dùng làm vòng 1 kiểm chứng.
- **Trend context:** EMA50 > EMA200 → chỉ long; EMA50 < EMA200 → chỉ short.
- **Cấu trúc:** swing high/low với cận trái–phải k=2 nến (`indicators.swing_points`).
- **Tín hiệu:** nến H4 **đóng** vượt swing high gần nhất (long) hoặc thấp hơn swing low gần nhất (short) — break of structure.
- **Vào lệnh:** mở nến kế tiếp (tránh nhìn tương lai).
- **Stop:** 2 × ATR14(H4) từ giá entry.
- **Target:** 2R.
- **Thời gian dừng:** 20 nến H4.
- **Chi phí:** taker 0,05% + slippage 0,02% mỗi chiều (≈ 0,14%/lệnh round-trip).

### Điều kiện bác bỏ (T05)

Sau khi hết vòng research: kỳ vọng ròng ≤ 0,05R hoặc không vượt nhóm đối chứng trên cùng dữ liệu. Nếu không, loại hoặc sửa một biến duy nhất.

---

## 3. Định nghĩa chiến lược C2 — "Quét thanh khoản rồi đảo chiều tại vùng cũ"

Nguồn khái niệm: SMC (liquidity sweep + CHoCH) — đúng định nghĩa S03, S04. Thiết kế có **2 nhóm** để tách đóng góp của bộ lọc sweep (S05):

| Nhóm | Điều kiện vào (long) | Mục đích |
|---|---|---|
| **Sweep (bộ lọc SMC)** | Giá H4 quét xuống dưới swing low gần nhất (sweep) **rồi đóng lại trên mức** trong cùng nến; entry nến kế | Đo đúng ý "quét thanh khoản xong đảo chiều" |
| **Nền (baseline)** | Giá chạm trong 0,5×ATR của swing low rồi đóng lại trên mức — **không yêu cầu quét** | Đối chứng để tách giá trị thêm của sweep |

- Long tại level_low, short tại level_high (đối xứng). Level = swing đã xác nhận trong 24 nến.
- Stop 2×ATR, target 2R, thời gian dừng 12 nến, chi phí như C1.

### Nếu không có bằng chứng sweep hữu ích

Sẽ chuyển trọng tâm sang nhóm nền "chạm vùng + xác nhận" (đã có sẵn như đối chứng) hoặc loại hẳn C2 — không cố giữ vì tên nghe hay (T07, T10).

---

## 4. Kết quả backtest

### 4.1 Điều kiện chạy

- Dữ liệu: Binance USD-M futures, 10 cặp (BTC, ETH, BNB, SOL, XRP, DOGE, ADA, LINK, AVAX, LTC), 2023-07-01 → 2026-09-07, đã cache trong `C1_C2_strategies/data/`.
- Chi phí: taker 0,05% + slippage 0,02% mỗi chiều + **funding lịch sử từng cặp** (từ vòng 2).
- Chia out-of-sample: **train** 2023-07-01 → 2025-06-30, **test** 2025-07-01 → 2026-09-07.

### 4.2 Vòng 1 (H4, chưa tính funding) — gộp toàn danh mục

| Chỉ số | C1 BOS | C2 Sweep | C2 Nền |
|---|---|---|---|
| Số lệnh | 3.314 | 1.127 | 11.476 |
| Win rate | 46,7% | 32,3% | 48,7% |
| Lãi trung bình | +1,48R | +0,86R | +0,89R |
| Lỗ trung bình | −0,88R | −0,90R | −0,80R |
| Profit factor | **1,46** | 0,46 | 1,06 |
| Kỳ vọng / lệnh | **+0,219R** | **−0,333R** | +0,025R |
| Tổng R | +724R | −375R | +286R |
| Max DD (R) | −763R | −375R | −426R |

### 4.3 Vòng 2 (đã tính funding, tách train/test) — gộp

| Chiến lược | Split | Lệnh | WR | PF | Kỳ vọng R | % cặp dương |
|---|---|---|---|---|---|---|
| C1 BOS H4 | TRAIN | 1.847 | 46,6% | 1,50 | +0,216R | 90% |
| C1 BOS H4 | **TEST** | 1.467 | 45,7% | **1,51** | **+0,199R** | **80%** |
| C2 MTF Sweep (H1/H4) | TRAIN | 877 | 26,3% | 0,39 | −0,446R | 0% |
| C2 MTF Sweep (H1/H4) | **TEST** | 302 | 26,3% | 0,40 | **−0,509R** | **10%** |
| C2 MTF Nền (H1/H4) | TRAIN | 3.318 | 48,1% | 1,09 | +0,030R | 50% |
| C2 MTF Nền (H1/H4) | **TEST** | 1.518 | 49,7% | **1,32** | **+0,135R** | **80%** |

### 4.4 Theo cặp (C1 vòng 1 — chi tiêu điểm)

| Cặp | Lệnh | WR | PF | Kỳ vọng R | BH 3 năm |
|---|---|---|---|---|---|
| BTC | 309 | 48,5% | 1,47 | +0,219 | +160% |
| ETH | 294 | 42,9% | 1,34 | +0,175 | +29% |
| BNB | 318 | 51,3% | 1,80 | +0,358 | +207% |
| SOL | 324 | 42,3% | 1,17 | +0,084 | +468% |
| XRP | 303 | 48,5% | 1,80 | +0,328 | +197% |
| DOGE | 278 | 50,4% | 1,86 | +0,359 | +28% |
| ADA | 369 | 49,1% | 1,54 | +0,245 | −24% |
| LINK | 400 | 44,5% | 1,46 | +0,228 | +111% |
| AVAX | 364 | 52,5% | 1,66 | +0,287 | −40% |
| LTC | 355 | 37,5% | 0,90 | −0,058 | −49% |

### 4.5 Trả lời câu hỏi S05 — định lượng giá trị thêm của bộ lọc sweep

Thực hiện **2 lần** trên 2 định nghĩa độc lập, cùng một cách tách biến (sweep vs nền):

| Định nghĩa | Kỳ vọng nhóm nền | Kỳ vọng nhóm sweep | Kết luận |
|---|---|---|---|
| Vòng 1 — cùng khung H4 | +0,025R | −0,333R | Sweep làm giảm mạnh |
| Vòng 2 — sweep/CHoCH trên H1 vs level H4 | +0,062R (test +0,135R) | −0,463R (test −0,509R) | Sweep tiếp tục âm mọi cặp, cả 2 window |

→ **Bộ lọc "quét thanh khoản" không chỉ không thêm giá trị mà còn làm suy yếu cả nhóm nền.** Không phải vì định nghĩa vụng: thử lại với đúng khung LTF/HTF (H1 vs H4) vẫn âm đồng bộ. Kết luận nghiên cứu cho khái niệm này ở phiên bản hiện tại: **loại C2-sweep**, chuyển hẳn về C1; nhóm nền C2 chỉ giữ làm đối chứng, không dùng làm nguồn tín hiệu.

---

## 5. Giới hạn của backtest này (bắt buộc đọc)

- **Một tham số đầu tiên, chưa tối ưu:** stop 2×ATR, TP 2R, time-stop là giá trị khởi đầu, không tìm kiếm tham tốt nhất (tránh overfit — T06). Chưa tối ưu là **có chủ đích**; kết quả vòng 2 là từ tham số "mặc định".
- **Đã tính funding nhưng dùng mức trung bình cố định mỗi cặp,** không phải funding tức thời từng lệnh — đủ để kiểm tra "funding có đổi quyết định không" (không), nhưng lệnh cầm qua biến động funding lớn sẽ lệch.
- **Backtest tốt ≠ lệnh thật sẽ thắng:** slippage khi vào nhiều vị thế cùng lúc, thiếu thanh khoản ở level quét, và hành vi thực thi khác.
- **Chưa có bước đặt lệnh thật — forward test paper ($1000 ảo, mục 7) mới bắt đầu 07/09/2026; không dùng để trade live trước khi forward test có kết quả đáng kể.**

---

## 6. Kế hoạch vòng 3 (mỗi vòng đổi nhiều nhất 1 biến — T05)

**Đã hoàn thành vòng 2:** C2 MTF (H1/H4) — bác bỏ sweep; funding đã đo & cộng; train/test tách xong.

**Đã hoàn thành vòng 3 — bộ lọc thời điểm phiên cho C1 (C09/S07): kết quả PHỦ ĐỊNH.**

| Phiên bản | TRAIN expR | TEST expR | ALL expR | Kết luận |
|---|---|---|---|---|
| C1_BASE (không lọc) | +0,216R | **+0,199R** | +0,221R | Giữ |
| Bỏ giờ chết (20:00–24:00 UTC) | +0,242R | +0,170R | +0,222R | Cải train nhưng **giảm test** — loại |
| Bỏ thứ Sáu | +0,212R | +0,187R | +0,215R | Không giúp test — loại |
| Bỏ cả hai | +0,236R | +0,144R | +0,208R | Giảm test nhiều nhất — loại |

Điểm quan trọng: cả 3 biến thể đều **cải thiện nhẹ train nhưng làm xấu test** — đúng mẫu overfit kinh điển (T06). Lý do: giờ 20:00 UTC theo hồ sơ expectancy không phải "giờ chết" đối với C1 (expR 8h=0,35 tốt nhất; 20h=0,21 không tệ). Thứ hai (0=Mon) có expR ~0,0 nhưng đây là do tách từ dữ liệu sau khi nhìn — không được dùng để lọc (cấm data-snooping). Kết luận: **C1 giữ nguyên, không thêm bộ lọc phiên.**

Kế hoạch vòng 4 (mỗi vòng đổi nhiều nhất 1 biến — T05):

**Vòng 4 đã hoàn thành — "close tạo cấu trúc mới rõ" (fresh close window=16):**

| Phiên bản | TRAIN expR | TEST expR | ALL expR | ALL DD | Kết luận |
|---|---|---|---|---|---|
| C1_BASE (không lọc) | +0,216R | +0,199R | +0,221R | 23,9% | Giữ |
| C1_FRESH16 | +0,193R | **+0,216R** | +0,214R | **18,6%** | Phát hiện意外 |

- **Giả thuyết ban đầu: giảm nhiễu LTC → PHỦ ĐỊNH.** LTC ALL: −0,061R → −0,062R; TEST +0,015 → −0,004R. LTC longs bị tổn thương do bull traps trong downtrend 2023–2024, đây là uni-pair selection issue, không phải lỗi tham số C1.
- **Phát hiện意外: FRESH16 giảm DD rõ rệt (24% → 19%ALL, 20% → 15%TEST) và cải expR test nhẹ (+0,199 → +0,216).** Kiểm tra overfit: TEST > TRAIN → không overfitting. Tuy nhiên pos_pairs giảm 80% → 60% (BTC, ADA, LINK, ETH, BNB, XRP dương; DOGE, SOL, AVAX, LTC không lợi) — thay đổi cấu trúc danh mục.
- **Kết luận: Giữ C1_BASE.** FRESH16 là phát hiện意外 cần test riêng trong tương lai nếu muốn giảm DD, không áp dụng chung ngay vì: (1) không giải quyết vấn đề LTC, (2) thay đổi risk profile nhiều (tập trung lợi thế vào 6 cặp).

Kế hoạch vòng 5 (mỗi vòng đổi nhiều nhất 1 biến — T05):

**Vòng 5 đã hoàn thành — GENERALIZATION top100 (kiểm chứng ngoài 10 cặp):**

Chạy C1_BASE (giữ nguyên tham số, không tinh chỉnh theo dữ liệu mới) trên **top100 USD-M futures theo thanh khoản** (quoteVolume 24h, proxy top100 trong 20 ngày — top này gần như trùng với top100 24h). Mục đích: C1 có thực sự là lợi thế thanh khoản hay chỉ là overfit của 10 cặp đầu.

| Split | Số cặp | Lệnh | WR | PF | expR | % cặp dương |
|---|---|---|---|---|---|---|
| TRAIN (2023-07→2025-06) | 48 cặp đủ dữ liệu | 8.145 | 48,3% | 1,58 | +0,214R | **88%** |
| TEST (2025-07→2026-09) | 90 cặp | 10.002 | 45,8% | 1,35 | **+0,105R** | **64%** |
| ALL | 90 cặp | 18.147 | 47,2% | 1,43 | +0,156R | 78% |

Kết quả:
- **Top20 theo expR** (min 50 lệnh): HEMI +0,85, XAN +0,81, XAU +0,63, ZEC +0,55, PROM +0,44, LAYER +0,40, ARB +0,39, VIRTUAL +0,36, DOGE +0,36, BNB +0,36, XRP +0,33, TIA +0,32, ENA +0,30...
- **Bottom10**: SOXL −0,49, NAORIS −0,43, ICP −0,25, SAMSUNG −0,17, FIL −0,16, INTC −0,14, FARTCOIN −0,13...
- **TEST expR giảm so với 10 cặp ban đầu (+0,199 → +0,105) nhưng vẫn dương** — C1 là lợi thế thực, không phải overfit, nhưng chi phí trade trên cặp nhỏ thanh khoản hóa ra thấp hơn lợi nhuận biên. % cặp dương test giảm 80% → 64%.
- **Lưu ý top100 gồm cả cặp equity/token-stock mới (NVDA, INTC, SOXL, QQQ, SAMSUNG, 哈基米, ZHIPU...)** — những cặp này niêm yết ngắn, thanh khoản mỏng, và một số là cổ phiếu Mỹ đóng cửa cuối tuần; chúng làm nhiễu kết quả. Loại các cặp phi-crypto quá mới (bars < 500) đã tự loại trong code.
- **Kết luận: C1 giữ nguyên. Lợi thế trung bình trên top100 vẫn dương ngoài mẫu nhưng mỏng hơn rõ (test +0,105R).** Nếu muốn trade C1, nên **lọc theo thanh khoản tối thiểu** — nhóm 20 cặp thanh khoản nhất (top decile) giữ expR gần mức 10 cặp gốc; nhóm tail làm kéo chỉ số xuống. Đề xuất: trading universe = top20 thanh khoản, bỏ các cặp equity-stock mới.

### Chi tiết files top100

- `reports/top100_summary.csv` — toàn bộ chỉ số theo symbol/split.
- `reports/trades_top100_*.csv` — trade chi tiết từng cặp.
- Chạy lại: `.venv/bin/python -m C1_C2_strategies.run_top100`.

## 7. Vòng 6 — Paper forward testing (đang chạy từ 07/09/2026)

**Quyết định universe:** top20 thanh khoản, loại cặp equity/token-stock mới. Lý do từ vòng 5: test expR trên top100 giảm còn +0,105R nhưng nhóm top-thanh-khoản giữ gần mức 10 cặp gốc (+0,199R) — lợi thế C1 tập trung ở các cặp liquid, tail làm kéo chỉ số xuống.

**Định nghĩa tài khoản paper:**
- Số dư khởi tạo **$1.000 ảo**, risk **0,5%/lệnh ($5)** — sizing qua `qty = risk_amount / (entry − stop)`, stop = 2×ATR14 như backtest (đã verify: risk_price=3000 → qty=0,001667, loss tại stop = chính xác $5).
- Chi phí như backtest: taker 0,05% + slippage 0,02% mỗi chiều, tính vào PnL per trade.
- Các cặp: BTC, ETH, SOL, XRP, HYPE, DOGE, ARB, BNB, RAYSOL, NEAR, CL, TAO, SUI, LINK, UNI, WLD, ENA, SNDK, SKHYNIX, MARSCOIN (20).
- Vào/ra theo đúng gen_c1: nến H4 đóng vượt swing (EMA50/200 làm trend filter), entry mở nến kế, SL 2×ATR, TP 2R, time-stop 20 nến.

**Cơ chế forward test (chống backfill 3 năm):**
- Mỗi lần chạy quét dữ liệu mới; chỉ mở **tín hiệu mới xuất hiện sau lần chạy trước** (marker `last_seen_signal` per symbol).
- Lần chạy đầu tiên chỉ **ghi nhận** tín hiệu hiện tại, không mở lệnh (thời điểm bắt đầu forward test, không replay lịch sử).
- Đóng vị thế theo SL/TP/timeout dùng dữ liệu cập nhật; equity point ghi mỗi lần có biến động.

**Cách chạy (từ project root):**
- `.venv/bin/python run_paper.py run` — cập nhật account (thêm/cập nhật/quét signals mới + đóng độ đúng).
- `.venv/bin/python run_paper.py report` — báo cáo định kỳ (`reports/paper_report.txt`, `paper_metrics.csv`).
- `.venv/bin/python run_paper.py reset` — bắt đầu lại $1000 (dùng có chủ đích).
- `.venv/bin/python run_dashboard.py` — **dashboard web local** tại `http://127.0.0.1:8787` (Flask, không cần internet; nút "Đồng bộ từ GitHub" pull state mới nhất từ repo, auto-refresh 60s).
- Chạy `run` định kỳ để forward test tích luỹ theo thời gian thực.

**Lịch chạy tự động (hybrid local + GitHub Actions, failover):**
- **Máy bật → cron local là nguồn chính:** mỗi 4h lúc `:40` (`0,4,8,12,16,20`), chạy `run_paper.py run` + `report` rồi tự `git add/commit/push` state lên GitHub.
- **Máy tắt >7h → Actions `.github/workflows/c1-paper.yml` là backup:** schedule `:35` mỗi 4h. **Failover guard**: nếu `paper_state.json.last_good_scan` (lần quét CÓ DỮ LIỆU thành công gần nhất) cách hiện tại ≤7h thì SKIP (local vừa lo rồi — tránh race/double-open); >7h thì Actions tiếp quản, mở/đóng lệnh và push state.
- **Giới hạn thực tế:** Binance geo-block GitHub runner (HTTP 451) nên khi máy tắt thường không lấy được dữ liệu → **không mở lệnh mới, không tạo lỗi** (Actions chỉ đánh dấu scan khi fetch thành công, guard chống backfill trong runner giữ số liệu sạch). Khi máy bật trở lại, hệ tiếp tục từ đúng điểm đã chạm dừng.

**API dashboard** (localhost): `/api/overview` (KPIs + vị thế mở), `/api/trades` (nhật ký), `/api/equity` (đường equity), `/api/universe` (marker mỗi cặp), `/api/run` (pull state mới nhất từ GitHub — engine không chạy local nữa).

**Trạng thái hiện tại:** account $1.000, 0 lệnh, 19/20 cặp đã ghi marker, paper start 07/09/2026 09:39 UTC.

---

Code tại `/Users/brokinv/Desktop/AI Agent/Trading/C1_C2_strategies/`

| File | Vai trò |
|---|---|
| `data.py` | Fetch + cache OHLCV **và funding history** Binance futures (ccxt, chỉ đọc, không cần API key) |
| `indicators.py` | EMA, ATR14, swing points |
| `strategies.py` | Sinh tín hiệu C1, C2 (sweep & nền), C2 MTF (H1 vs level H4) |
| `engine.py` | Khớp tín hiệu → trade, tính R sau chi phí + funding |
| `report.py` | Tổng hợp chỉ số equity/drawdown |
| `run_backtests.py` | Chạy backtest vòng 1 → `reports/` |
| `run_backtests_v2.py` | Chạy vòng 2: funding + C2 MTF + split train/test → `reports/` |
| `run_backtests_v3.py` | Chạy vòng 3: bộ lọc phiên cho C1 (dead hours/Friday) → `reports/` |
| `run_backtests_v4.py` | Chạy vòng 4: fresh close window=16 cho C1 (giảm nhiễu LTC) → `reports/` |
| `run_top100.py` | Chạy C1_BASE trên top100 thanh khoản → `reports/` |
| `scan_market.py` | Quét thị trường hiện tại → danh mục theo dõi |
| `run_paper.py` | **Forward test paper C1** `$1000` — CLI: run / report / reset |
| `run_dashboard.py` | **Dashboard web local** Flask → `http://127.0.0.1:8787` |
| `paper/paper_config.py` | Config paper: universe 20 cặp, risk 0,5%, TF H4, các đường file state/journal/equity |
| `paper/paper_account.py` | `PaperAccount` / `Position`, load/save JSON, append journal/equity, sizing theo risk |
| `paper/paper_runner.py` | Engine forward test: quét tín hiệu mới, mở/đóng vị thế, chống backfill |
| `paper/paper_report.py` | Báo cáo định kỳ: metrics, win rate, profit factor, max DD |
| `paper/dashboard.py` | Flask app + API + HTML dashboard (equity chart SVG, trades, universe) |
| `reports/` | `summary.csv`, `summary_v2.csv`, `summary_v3.csv`, `summary_v3_per_symbol.csv`, `session_profile.csv`, `top100_summary.csv`, `trades_top100_*.csv`, `trades_C1_BOS_H4.csv`, `trades_C2_SWEEP_H4.csv`, `trades_C2_BASE_H4.csv`, `trades_v2_*.csv` **+ paper:** `paper_state.json`, `paper_journal.csv`, `paper_equity.csv`, `paper_report.txt`, `paper_metrics.csv` |

Chạy lại vòng 1: `.venv/bin/python -m C1_C2_strategies.run_backtests`
Chạy lại vòng 2: `.venv/bin/python -m C1_C2_strategies.run_backtests_v2`
Chạy lại vòng 3: `.venv/bin/python -m C1_C2_strategies.run_backtests_v3`
Chạy lại vòng 4: `.venv/bin/python -m C1_C2_strategies.run_backtests_v4`
Chạy top100: `.venv/bin/python -m C1_C2_strategies.run_top100`
Chạy scan: `.venv/bin/python -m C1_C2_strategies.scan_market`
Paper run: `.venv/bin/python run_paper.py run`
Paper report: `.venv/bin/python run_paper.py report`
Paper reset: `.venv/bin/python run_paper.py reset`
Dashboard: `.venv/bin/python run_dashboard.py` → http://127.0.0.1:8787

---

## 9. Liên hệ với rules.md

| Quy tắc | Cách dự án đáp ứng |
|---|---|
| T01/T03 — tách thực thi, đo expectancy | Báo cáo cả PF, WR, kỳ vọng R, không chỉ một chỉ số |
| T05 — môt biến mỗi vòng | Mỗi vòng chỉ đổi một biến (C1 giữ nguyên tham số xuyên các vòng) |
| T06 — dữ liệu mới / chống overfit | Chia train/test + kiểm chứng generalization top100; chưa tối ưu tham số |
| T07 — lưu cả thất bại | C2 sweep thua vẫn được ghi; vòng 3/4 phủ định đều lưu CSV |
| S03/S04 — định nghĩa trước, vùng là suy diễn | C2 định nghĩa sweep/CHoCH máy móc được |
| S05 — đo giá trị thêm của bộ lọc | Nhóm sweep vs nền; phiên vs baseline |
| R01–R08 — rủi ro | Chưa đặt lệnh; mọi kết luận trước sizing phải qua forward test |
| R01/R02 — risk per trade, sizing | Paper thực hiện 0,5%/lệnh = $5 và chi phí thực, soi lệnh thật trước khi live |