# Đánh giá BASE, B, Donchian 55 và Keltner H4

Ngày nghiên cứu: 07/09/2026. Dữ liệu kết thúc 31/08/2026. Đây là bản nghiên cứu mới dựa trên mã trong thư mục, đã sửa cách mô phỏng và hạch toán. Mã và cơ sở dữ liệu vận hành cũ giữ nguyên.

## Quyết định đề xuất

**Ưu tiên DON55 đã sửa thực thi để forward paper futures. Spot chọn B_SAFE làm nền quản trị để tiếp tục nghiên cứu; chưa đủ bằng chứng để tăng vốn.** DON55_TREND không cải thiện rõ trên DON55; KELTNER_TREND đáng theo dõi phụ vì giảm drawdown và số lệnh, nhưng biên lợi thế còn mỏng. Chưa chọn B_REGIME chỉ vì lợi nhuận cao hơn: kết quả phần lớn bị tác động bởi cách chia vốn và chỉ có 16 lệnh gần đây.

## 1. Những vấn đề tìm thấy trong thư mục

- [research_futures_strategy.py](../../../research_futures_strategy.py) và [futures_paper.py](../../../futures_paper.py) dùng `abs(close-entry)` để kích hoạt hòa vốn, kể cả khi giá đi ngược. Sau đó dùng cực trị nến vừa đóng để sửa trailing trước khi kiểm tra chính nến đó. TP được ưu tiên khi đồng thời chạm stop. Đây là lỗi mô phỏng, không phải một lợi thế giao dịch.
- Kiểm thử trực tiếp hàm Keltner cũ tái hiện: vào long 120, nến sau O100/H105/L95/C100 nhưng hàm trả giá thoát 120, cao hơn cả đỉnh 105. Bản mới kiểm tra stop cũ, xử lý gap, rồi mới cập nhật stop cho nến tiếp theo.
- Tham số futures `be=2` là **2 ATR = 1R** vì SL bằng 2 ATR; TP Donchian 7 ATR = 3,5R, Keltner 6 ATR = 3R. Không diễn giải chúng thành 2R/7R/6R.
- [auto_trade.py](../../../auto_trade.py) giả định khớp midpoint giữa band và close, chưa chứng minh có thể khớp limit. Stop spot được đặt lại và có thể nới xuống. [research_improvements.py](../../../research_improvements.py) lại không dùng hard stop mặc định, lọc B chỉ ở lần mua đầu và không có sổ tiền mặt thực.
- PF 6,63 trong [config.py](../../../config.py) là kết quả nghiên cứu cũ trên universe/thời đoạn khác và sau chọn tham số. Tổng lợi nhuận phần trăm từng coin của báo cáo futures không phải lợi nhuận tài khoản; DD theo chênh lệch tuyệt đối và Sharpe theo sự kiện lệnh cũng không tương đương DD theo đỉnh vốn và Sharpe theo ngày.
- Snapshot dữ liệu giấy: bốn sổ spot có tổng 1 giao dịch đã đóng; hai file futures có 0 giao dịch đã đóng. Chưa có mẫu forward paper để xác nhận thống kê. Bằng chứng và hash nguồn lưu trong `results.json`.

## 2. Quy tắc được kiểm tra

**BASE D1:** Close cắt lên SMA20(high) + 1,5 độ lệch chuẩn mẫu của high và ở trên SMA50/100/150/200. Lower band = SMA20(low) − 1,5 độ lệch chuẩn mẫu của low. Thoát khi close cắt xuống lower hoặc một SMA, thực hiện tại open kế tiếp. Hard stop = 99% mức cao nhất của lower và các SMA nằm dưới close. Mỗi lớp $50 gồm phí, tối đa 3 lớp/coin, 10 coin, tổng vốn mua $1.500 trên ví spot $3.000.

**B D1:** BASE thêm ROC5 < 20%, ROC20 < 40%, ATR14/close < 6%; áp dụng cho mọi lần thêm vị thế. ATR ở đây là SMA của true range, giữ đúng mã gốc.

**DON55 H4:** Long khi close vượt đỉnh 55 nến trước và trên EMA50; short đối xứng. ADX ≥ 20, ATR% cao hơn trung bình 50 nến của ATR%. Funding gần nhất đã biết tại đầu nến tín hiệu ≤ +0,05% cho long hoặc ≥ −0,05% cho short. SL 2 ATR, TP 7 ATR, trailing 4 ATR, BE sau close đi thuận 2 ATR. Đây là điều kiện giá nằm ngoài kênh; bản gốc không bắt buộc một giao cắt mới.

**KELTNER H4:** Long trên EMA20 + 1,5 ATR, short dưới EMA20 − 1,5 ATR, ADX ≥ 18, funding một phía ±0,06%. SL 2 ATR, TP 6 ATR, trailing 3,5 ATR, BE sau close đi thuận 2 ATR. Không tự thêm EMA50 hay D1 vào bản nền.

**Bốn phần phát triển:** B_SAFE cấm nới stop và chỉ nhồi khi vị thế đã lãi ít nhất 1R theo close D1; B_REGIME thêm BTC D1 > SMA200 và chia khối lượng theo rủi ro. DON55_TREND/KELTNER_TREND thêm xu hướng coin D1 so với EMA200 đã biết tại đầu nến H4, bắt buộc giao cắt mới, BE sau 4 ATR = 2R và bù phí/trượt giá thoát. Funding tương lai vẫn không được bảo đảm bởi mức BE này. Quy tắc được ghi trước khi chạy kết quả mới trong [EXISTING_SPEC.md](../../EXISTING_SPEC.md).

## 3. Phương pháp và giới hạn

12 coin BTC, ETH, BNB, XRP, ADA, DOGE, LINK, LTC, BCH, DOT, UNI, SOL trên Binance, dữ liệu từ 2021 để khởi tạo chỉ báo, giao dịch 2022–08/2026. Đây là **cohort các coin còn tồn tại**, không phải top100 thanh khoản được tái lập tại từng thời điểm. Chưa có dữ liệu vốn hóa/narrative lịch sử hoặc coin hủy niêm yết; không suy rộng kết quả sang new coin/DEX.

Mỗi ví có sổ vốn và vị thế đồng thời. Spot signal D1, stop trên H4; futures signal H4, stop trên H1. Lệnh ở open sau khi nến tín hiệu hoàn tất, stop trước TP nếu không rõ thứ tự trong nến, trailing chỉ hiệu lực sau khi nến tạo nó đóng. Phí giả định spot 0,10%/chiều + trượt 0,05%; futures 0,05%/chiều + trượt 0,03%, cộng funding từng sự kiện thực. Đây là giả định chi phí, không xác nhận biểu phí tài khoản Binance của bạn. Test stress nhân đôi phí và trượt giá, giữ funding thực.

Funding cũ thiếu markPrice dùng mark OPEN H1 đã biết, có đếm trong audit; giai đoạn gần đây không cần proxy ở các giao dịch này. Đối soát vốn và tổng PnL sai lệch dưới $0,000001. Dữ liệu gốc được kiểm hash 48 file; một số nến spot có close_time rút ngắn trong 2021 chỉ nằm ở warmup, không sửa dữ liệu để che vấn đề.

Các sửa đổi cũng gồm yêu cầu đủ 200 nến chỉ báo, áp dụng đầy đủ filter khi nhồi và khớp open thay midpoint/close. Vì thế đây là kiểm tra phiên bản quy tắc có thể thực thi, **không phải tái tạo nguyên xi các con số cũ**. Diagnostic bỏ hard stop gần đây: BASE +0.70%, B +2.58%.

Kỳ 2025–08/2026 là mẫu thời gian sau nhưng đã được xem trong nghiên cứu trước: **không gọi là holdout độc lập** dù tên file dùng `holdout`. Các lần chạy theo kỳ/năm đều khởi đầu lại với tiền mặt; toàn kỳ là đường vốn liên tục, không cộng số từng năm. Đã kiểm tra chi phí, chia vốn, năm, long/short và độ tập trung; chưa chạy walk-forward tối ưu tham số hoặc quét toàn bộ tham số lân cận.

Chưa mô hình hóa tick, order book, bước lượng/min-notional của từng hợp đồng, maintenance tier và thanh lý chính xác. Audit thanh lý chỉ là ngưỡng cảnh báo, không thay mô hình thanh lý. Chưa áp dụng công tắc dừng lỗ ngày/tuần của cấu hình vận hành vào nghiên cứu này; số liệu đo setup với giới hạn vị thế/margin, chưa phải kết quả hệ thống vận hành hoàn chỉnh. Do những giới hạn này chưa thể gọi là backtest đầy đủ cho triển khai tiền thật.

## 4. Kết quả sau chi phí: 01/2025–08/2026

| Setup | Lợi nhuận | Max DD | PF | Lệnh | Chi phí ×2: lợi nhuận |
|---|---|---|---|---|---|
| BASE | -0.12% | 5.54% | 0.98 | 49 | -0.46% |
| B | +1.67% | 3.75% | 1.53 | 33 | +1.43% |
| B_SAFE | +1.45% | 3.57% | 1.62 | 33 | +1.24% |
| B_REGIME | +6.29% | 6.98% | 2.18 | 16 | +5.37% |
| DON55 | +39.31% | 13.87% | 1.38 | 245 | +28.36% |
| KELTNER | +17.42% | 24.73% | 1.11 | 442 | +8.05% |
| DON55_TREND | +15.40% | 13.66% | 1.23 | 161 | +9.16% |
| KELTNER_TREND | +13.70% | 13.19% | 1.16 | 259 | +5.89% |

Lợi nhuận là lũy kế khoảng 20 tháng; spot tính trên $3.000, futures trên $1.000. DD tính từ đỉnh equity có lãi/lỗ chưa thực hiện, không phải từ tổng vốn từng lệnh. Không cộng các phần trăm này.

| Setup | 2022–23 | 2024 | 2025–08/2026 | Toàn kỳ: lợi nhuận / DD |
|---|---|---|---|---|
| BASE | +14.68% | +22.45% | -0.12% | +35.55% / 11.31% |
| B | +6.04% | +17.67% | +1.67% | +25.58% / 8.88% |
| B_SAFE | +4.79% | +16.16% | +1.45% | +23.76% / 7.47% |
| B_REGIME | -1.07% | +6.25% | +6.29% | +15.58% / 6.98% |
| DON55 | +17.72% | +19.01% | +39.31% | +95.16% / 25.23% |
| KELTNER | +2.67% | +7.39% | +17.42% | +25.00% / 30.63% |
| DON55_TREND | +16.98% | +13.54% | +15.40% | +53.28% / 15.69% |
| KELTNER_TREND | +21.44% | +9.46% | +13.70% | +51.14% / 13.19% |

### Hiệu quả qua từng năm, khởi đầu lại với tiền mặt

| Setup | 2022 | 2023 | 2024 | 2025 | 2026 đến hết T8 |
|---|---|---|---|---|---|
| BASE | -1.87% | +16.55% | +22.45% | -0.79% | +0.71% |
| B | -0.91% | +6.94% | +17.67% | +1.24% | +0.47% |
| B_SAFE | -0.88% | +5.67% | +16.16% | +0.83% | +0.47% |
| B_REGIME | +0.00% | -1.07% | +6.25% | +0.26% | +6.01% |
| DON55 | +12.25% | +6.25% | +19.01% | +11.28% | +34.76% |
| KELTNER | +14.30% | -7.52% | +7.39% | +20.68% | -3.01% |
| DON55_TREND | +12.84% | +5.31% | +13.54% | +1.84% | +15.01% |
| KELTNER_TREND | +16.35% | +7.82% | +9.46% | +9.30% | +9.95% |

### Phát triển thêm có thật sự tốt hơn?

- B_SAFE giảm stop nới xuống từ 77 lần ở B xuống 0, DD từ 3,75% xuống 3,57%, lợi nhuận giảm nhẹ từ 1,67% xuống 1,45%. Đây là thay đổi quản trị dễ kiểm soát, chưa chứng minh tăng lợi nhuận.
- B_REGIME native đạt 6,29% nhưng fixed $50 chỉ đạt +1.78%/30 lệnh. Không quy toàn bộ chênh lệch cho bộ lọc BTC. Native thay cả vốn/lệnh và khả năng đủ chỗ nhận lệnh, mẫu còn 16.
- DON55_TREND giảm lợi nhuận gần đây 39,31% → 15,40% trong khi DD gần như ngang nhau. Toàn kỳ, bản TREND có ưu điểm giảm DD 25,23% → 15,69%, đổi lại lợi nhuận 95,16% → 53,28%. Giữ DON55 đơn giản làm ứng viên chính trong phân bổ ví futures nhỏ; bản TREND là lựa chọn để thử nếu ưu tiên giảm DD qua nhiều năm.
- KELTNER_TREND giảm DD 24,73% → 13,19%, số lệnh 442 → 259; PF 1,108 → 1,158. Đổi lại lợi nhuận 17,42% → 13,70%. Đây là ứng viên phụ để thử forward, chưa phải bằng chứng chắc chắn về lợi thế ổn định.
- Khi đồng nhất risk futures về 0,75%, KELTNER_TREND đạt +16.74%, DD 16.24%. So sánh native của nó với KELTNER vẫn cùng 0,60%/lệnh.
- Diagnostic không phí/trượt giá vẫn tính funding. Thay chi phí làm thay khối lượng, vị thế được nhận và dòng lệnh; không lấy chênh lệch return hai lần chạy để gọi là số phí đã trả.

## 5. Độ chắc chắn và sự phụ thuộc vài lệnh lớn

| Setup | Win rate | Chuỗi thua dài nhất | PnL bỏ 5 lệnh tốt nhất ($) | Bootstrap P5…P95 lợi nhuận |
|---|---|---|---|---|
| BASE | 18.4% | 22 | -133.06 | -10.7% … +11.5% |
| B | 24.2% | 13 | -79.13 | -6.7% … +10.2% |
| B_SAFE | 27.3% | 13 | -53.59 | -6.0% … +9.0% |
| B_REGIME | 31.2% | 8 | -159.47 | -10.1% … +28.6% |
| DON55 | 35.5% | 11 | +233.81 | -3.6% … +99.8% |
| KELTNER | 34.2% | 20 | +64.68 | -19.7% … +73.9% |
| DON55_TREND | 37.3% | 11 | +15.72 | -15.9% … +62.1% |
| KELTNER_TREND | 35.5% | 10 | +40.72 | -14.5% … +52.7% |

Bootstrap lấy lại các block 7 ngày, 1.000 mẫu, chỉ mô tả độ nhạy của đường vốn. Tất cả khoảng P5–P95 đều chứa lợi nhuận âm; không phải khoảng dự báo hay xác nhận độc lập. Spot mất lợi nhuận nếu loại năm lệnh tốt nhất. DON55 còn +$233,81 trong cùng phép thử; lợi thế đo được phân tán hơn nhưng vẫn có chuỗi 11 lệnh thua.

| Setup | PnL long ($) | PnL short ($) | Coin tốt nhất: PnL ($) | Coin kém nhất: PnL ($) |
|---|---|---|---|---|
| BASE | -3.61 | +0.00 | BNBUSDT: +61.07 | ADAUSDT: -26.50 |
| B | +50.00 | +0.00 | BNBUSDT: +61.07 | BTCUSDT: -11.52 |
| B_SAFE | +43.50 | +0.00 | BNBUSDT: +44.34 | ADAUSDT: -9.80 |
| B_REGIME | +188.72 | +0.00 | XRPUSDT: +134.19 | LTCUSDT: -19.75 |
| DON55 | +178.70 | +214.35 | ADAUSDT: +124.10 | DOTUSDT: -71.45 |
| KELTNER | -22.40 | +196.60 | ADAUSDT: +60.37 | LTCUSDT: -18.09 |
| DON55_TREND | -40.91 | +194.93 | ETHUSDT: +65.19 | BCHUSDT: -33.89 |
| KELTNER_TREND | -27.64 | +164.65 | ETHUSDT: +65.60 | BCHUSDT: -30.13 |

Không dùng bảng này để loại coin thua trong quá khứ rồi gọi đó là một kiểm định mới. Chi tiết từng lệnh, phí, funding và coin/hướng đã xuất cùng báo cáo.

## 6. Ghép vào tài khoản $5.000

Giả định spot $3.000 + futures $1.000 + dự phòng $1.000, các ví độc lập. Hai setup futures chạy chung một sổ có giới hạn vị thế/margin, không cộng equity của hai ví $1.000 riêng.

| Danh mục $5.000 | Cuối kỳ gần đây ($) | Lợi nhuận gần đây | DD gần đây | Lợi nhuận toàn kỳ | DD toàn kỳ |
|---|---|---|---|---|---|
| BASE_AND_DON_KELT | 5251.31 | +5.03% | 9.99% | +38.18% | 10.51% |
| B_AND_DON_KELT | 5304.92 | +6.10% | 8.95% | +32.20% | 10.26% |
| B_REGIME_AND_TREND | 5249.61 | +4.99% | 6.74% | +29.50% | 8.13% |
| B_SAFE + DON55 (chọn sau đánh giá) | 5436.56 | +8.73% | 3.63% | +33.29% | 7.63% |
| 60% BTC + 40% tiền mặt | 4511.73 | -9.77% | 35.67% | +41.71% | 42.89% |

Danh mục B_SAFE + DON55 là phép ghép mô tả sau khi đọc kết quả, không phải một lần kiểm định độc lập. DD thấp một phần do spot $50/lớp và nhiều tiền mặt chưa sử dụng; tăng quy mô sẽ thay đổi rủi ro. Benchmark BTC có mức phơi nhiễm khác nên không dùng để khẳng định alpha đã điều chỉnh rủi ro.

Cho giai đoạn paper, giữ reference $50/lớp của B_SAFE và risk DON55 0,75% ví futures (ban đầu $7,50), 3x, tối đa 3 vị thế DON55, margin toàn ví ≤40%. Đây là cấu hình đã mô phỏng. Nếu triển khai tiền thật sau kiểm chứng, có thể bắt đầu 0,25–0,50% ví futures/lệnh; đây là đề xuất thận trọng, chưa phải một kết quả backtest trong bảng. Max DD 40% của bạn là giới hạn chịu đựng toàn tài khoản, không phải mục tiêu vận hành.

Tiêu chí PAPER_CANDIDATE đặt trước: lãi năm 2024 và kỳ gần đây, PF gần đây ≥1,15, ≥100 lệnh, DD ví ≤20%, stress vẫn lãi, không có cờ thanh lý. DON55, DON55_TREND và KELTNER_TREND qua cổng này. Các bản spot chưa đủ 100 lệnh gần đây; KELTNER gốc không đạt PF và DD. Không có nhãn “được phép chạy live”. Forward paper cần log tín hiệu/giá khớp/chi phí và ít nhất 100 lệnh đóng; mốc 100 là điều kiện cần, không đảm bảo đủ độ tin cậy.

## 7. Bộ lọc và TradingView đã bổ sung

Quét công khai Binance lúc 2026-09-07T04:29:44+00:00: OK, 800 kết quả profile–coin; phân bố {'FILTERED_OUT': 355, 'WATCH': 334, 'INSUFFICIENT_HISTORY': 70, 'EXPIRED_SIGNAL': 41}. Universe hiện tại top100 thanh khoản USDT riêng spot và USD-M perpetual, bỏ stable/pegged và token đòn bẩy. BASE/B cần ≥200 D1; futures gốc ≥200 H4, bản TREND thêm ≥200 D1. Bộ lọc dùng nến đóng, funding thực và đánh dấu tín hiệu đã quá thời điểm open. Kết quả top100 là universe mở rộng **chưa được kiểm định lịch sử**. Chưa có bộ lọc top200 vốn hóa hoặc narrative tự động.

[Mở danh mục quét](daily_latest/SCAN_VI.md). WATCH chỉ đạt một phần điều kiện nền; SETUP vẫn cần kiểm tra vị thế và giới hạn vốn; EXPIRED_SIGNAL không phải điểm vào để đuổi giá. Scanner chưa đọc vị thế thật, chưa quyết định nhồi hoặc khối lượng. Chạy lại thủ công bằng `run_existing_daily.command`; chưa tạo lịch tự động.

Hai Pine v6 monitor cho spot D1 và futures H4 có chọn profile, band và alert khi nến đóng. Futures Pine chỉ kiểm tra điều kiện giá, không có funding Binance tương đương; phải đối chiếu scanner. Spot Pine không quản lý lãi vị thế/nhồi/cash. Chưa biên dịch được trong TradingView do chưa có phiên đăng nhập Pine Editor; chưa xác nhận parity runtime. Không dùng Strategy Tester của một biểu đồ để thay cho backtest danh mục ở đây.

[Hướng dẫn sử dụng và tái chạy](../../EXISTING_README_VI.md). [Kết quả máy đọc](results.json). [Biểu đồ](comparison.png).

## Tài liệu đối chiếu

Giả định mô phỏng lệnh, thứ tự khớp và intrabar cần được phân biệt với kết quả biểu đồ: [TradingView Strategies](https://www.tradingview.com/pine-script-docs/concepts/strategies/). Lấy D1 đã xác nhận tại đầu H4 theo mẫu offset `[1]` cùng lookahead: [TradingView Other timeframes and data](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/). Nguồn endpoint nến/funding/mark: [Binance USD-M Market Data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).
