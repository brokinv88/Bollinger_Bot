# Hai setup theo dõi trên TradingView

Hai file Pine v6 triển khai quy tắc tín hiệu đã chốt trong `strategy_lab/SPEC.md`. Chúng dùng để xem từng biểu đồ, nhận cảnh báo và kiểm tra giao dịch mô phỏng. Kết quả Python là báo cáo nghiên cứu danh mục; Strategy Tester trên từng chart không thay thế báo cáo đó. Nhãn `RESEARCH ONLY` được giữ trên cả hai script: có code chạy được không có nghĩa là chiến lược đã đạt tiêu chí lợi nhuận ngoài mẫu.

**Trạng thái kiểm tra ngày 06/09/2026:** đã rà soát tĩnh mã nguồn và đối chiếu tài liệu Pine v6 chính thức. Đã mở Pine Editor trên TradingView và nạp mã spot; nút **Add to chart** yêu cầu đăng nhập trước khi biên dịch. Vì vậy **chưa xác nhận biên dịch/chạy thành công bằng trình biên dịch TradingView** cho hai file. Chưa lưu script, tạo alert hoặc đặt lệnh vào tài khoản của người dùng.

| File | Biểu đồ bắt buộc | Quy tắc cố định |
|---|---|---|
| `spot_d1_h4_breakout.pine` | Binance spot USDT, nến chuẩn, **4H**; ví dụ `BINANCE:BTCUSDT` | D1 tăng; BTC D1 trên EMA200; altcoin ROC20 cao hơn BTC; median turnover30 ≥10 triệu USDT; H4 mới vượt đỉnh 20 nến trước, trên EMA20; long |
| `futures_h4_h1_pullback.pine` | Binance USDT perpetual, nến chuẩn, **1H**; ví dụ `BINANCE:BTCUSDT.P` | H4 tăng/giảm và EMA50 cùng độ dốc; median turnover30 ≥20 triệu USDT; H1 hồi chạm EMA20 rồi đóng vượt high/low nến trước; long/short |

Spot cần ít nhất 200 nến D1 đã hoàn tất, gồm BTC tham chiếu. Futures cần 200 nến H4 và 30 nến D1 hoàn tất. Phần chi tiết trigger futures vẫn đúng SPEC: long có low nến trước ≤EMA20 nến trước, close nến trước >EMA50 nến trước, close hiện tại >high nến trước và EMA20 hiện tại >EMA50; short đảo chiều từng điều kiện.

## Cài đặt và nhận cảnh báo

1. Mở đúng cặp và khung thời gian trong bảng, chọn loại nến tiêu chuẩn.
2. Mở **Pine Editor**, tạo script mới, thay toàn bộ nội dung bằng một file `.pine` rồi chọn **Add to chart**. Lưu thành script riêng nếu muốn dùng lại. Nếu có lỗi biên dịch, giữ nguyên nội dung lỗi và số dòng để sửa trước khi dùng.
3. Mặc định `Giới hạn ngày khi backtest` tắt để tiếp tục theo dõi nến mới. Bật khi muốn giới hạn giao dịch: ngày đề xuất sẵn là 01/01/2022 đến trước 01/09/2026 UTC. Bộ lọc ngày giới hạn lệnh mới, không cắt dữ liệu khởi tạo indicator. Vị thế còn mở tới cuối khoảng sẽ có lệnh thoát ở lần mở nến kế tiếp; xử lý này có thể khác việc chốt sổ cuối dữ liệu trong Python.
4. Trong **Properties**, giữ **On every tick**, **After order is filled** và **On bar close** tắt. Phí mặc định là spot **0,10% mỗi chiều**, futures **0,05% mỗi chiều**. Mặc định trượt giá của TradingView là **1 tick**, không tương đương giả định bps của Python; xem mục chi phí dưới đây.
5. Tạo alert, chọn tên strategy và sự kiện **alert() function calls only** (hoặc tên tương đương trên giao diện). Script gọi `alert.freq_once_per_bar_close`, nên tín hiệu chỉ gửi khi H4/H1 đã đóng. Không điền webhook giao dịch tự động.
6. Mặc định chế độ cảnh báo là **Tín hiệu setup**: báo khi điều kiện giá xuất hiện, kể cả chart đã có vị thế mô phỏng hoặc đã chạm ngưỡng dừng nghiên cứu. Chế độ **Lệnh mô phỏng đủ điều kiện** chỉ báo khi bộ mô phỏng riêng của chart có thể mở lệnh. Cả hai đều cần kiểm tra scanner và rủi ro toàn danh mục trước quyết định thực tế.

Chấm tròn cam là setup có mặt nhưng chart không mở vị thế; tam giác là nến phát lệnh mô phỏng, dự kiến khớp ở lần mở nến tiếp theo. Cảnh báo ghi khoảng stop và khối lượng ước tính, không hứa giá khớp tương lai. Alert nhận qua **order fills** chỉ là fill của broker emulator, không phải khớp lệnh Binance. TradingView lưu ảnh chụp cấu hình khi tạo alert; sau khi đổi code, symbol, timeframe hoặc input, cần tạo lại alert để áp dụng cấu hình mới. [Tài liệu alerts](https://www.tradingview.com/pine-script-docs/concepts/alerts/).

## Thời điểm tín hiệu và lệnh thoát

- Mọi dữ liệu khung lớn đều lùi ít nhất một nến **bên trong** `request.security`, với `lookahead_on`. Dữ liệu này đã biết tại **lúc mở** nến thực thi. Ví dụ H1 03:00–04:00 UTC chưa dùng H4 00:00–04:00 vừa hoàn tất khi H1 đóng; H1 04:00 mới dùng nến H4 đó. Đây là quy ước cố định của nghiên cứu, nhằm tránh khác nhau giữa lịch sử và thời gian thực. Độ dốc EMA50 H4 so với ba H4 trước được đọc bằng EMA50 `[1]` và `[4]`. [TradingView: dữ liệu khung khác](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/).
- EMA khởi tạo bằng close đầu tiên của lịch sử được TradingView cấp, rồi cập nhật với hệ số `2/(length+1)`. ATR là Wilder RMA14 của true range, khởi tạo bằng SMA của 14 giá trị đầu. Số nến tối thiểu không bảo đảm EMA200 trùng tuyệt đối nếu lịch sử đầu vào khác nhau. Python bắt đầu dữ liệu từ 2021, scanner dùng cửa sổ riêng, còn chart tùy gói/lịch sử khả dụng; phải so sánh EMA tại cùng mốc và tránh diễn giải các chênh lệch sát ngưỡng như lỗi tín hiệu.
- Khi nến tín hiệu đóng, script cố định khoảng stop `2 × ATR14`, làm tròn **lên** một số nguyên tick. Target là **3 lần khoảng stop đã làm tròn**. Gửi `strategy.entry` cùng `strategy.exit(loss=..., profit=...)`; loss/profit là khoảng cách tick từ **giá khớp mô phỏng thực tế**, nên gap mở nến không khiến stop bị neo sai vào close tín hiệu. Không bật tính toán lại sau mỗi fill. [TradingView: lệnh và broker emulator](https://www.tradingview.com/pine-script-docs/concepts/strategies/).
- Nến khớp entry là nến giữ thứ 1. Spot gửi thoát thời gian khi đóng nến thứ **90 H4**; futures khi đóng nến thứ **72 H1**; khớp ở lần mở nến sau. Không trailing, chốt từng phần, pyramiding hoặc đảo chiều vị thế đang mở.
- Nếu một vị thế đã thoát trong nến hiện tại, setup tại lúc đóng nến vẫn có thể gửi entry cho **nến kế tiếp**. Do không tính lại sau fill và không khớp ở close, script không mở lại vị thế trong cùng nến vừa thoát.

## Vốn mô phỏng và khác biệt với giao dịch thật

| | Spot A | Futures B |
|---|---:|---:|
| Vốn mô phỏng riêng trên một chart | 3.000 USD | 1.000 USD |
| Ngân sách lỗ tham chiếu ban đầu | 20 USD/lệnh | 12,50 USD/lệnh |
| Trần giá trị vị thế mỗi lệnh | 25% equity chart; ban đầu 750 USD | 100% equity chart; ban đầu 1.000 USD |
| Ký quỹ mô phỏng | 100% | Khoảng 33,33%, tương ứng 3× |
| Giảm quy mô / dừng mở mới | DD chart 8% / 12% | DD chart 8% / 12% |

Khối lượng lấy số nhỏ hơn giữa ngân sách rủi ro và trần giá trị vị thế. Ngân sách tăng/giảm theo equity mô phỏng của từng chart. Công thức khối lượng dành đệm cho phí và slippage hai chiều theo giả định SPEC, dùng close tín hiệu để ước tính giá mở kế tiếp. Do chưa biết open, **khối lượng và trần vốn thực tế có thể lệch** khi gap/slippage lớn. Tính lại sizing theo giá vào thực tế trước giao dịch. Tick/khối lượng làm tròn theo metadata TradingView, không xác minh đầy đủ Binance `LOT_SIZE`, `MARKET_LOT_SIZE` hoặc min notional; scanner chịu trách nhiệm đối chiếu bộ lọc hiện hành.

Khi DD chart đạt 8%, rủi ro và trần notional cho lệnh mới giảm một nửa. Khi đạt 12%, mô phỏng ngừng mở mới cho phần còn lại của lần chạy; stop/target của vị thế cũ vẫn hoạt động. DD ở đây tính equity tại **đóng nến**, không bao quát đường đi nội nến. Nhiều chart không chia sẻ equity hay trạng thái dừng. 1.000 USD dự phòng ngoài spot/futures không thuộc các chart này. Tắt guardrails chỉ để xem hệ thống thô trong nghiên cứu; không coi đó là tự động cho phép tăng rủi ro thực tế.

## Vì sao số TradingView khác báo cáo Python

1. **Thanh khoản:** trên dữ liệu `base`, Pine dùng `volume × close` của D1; nếu provider xác định volume là `quote`, dùng volume. Trường hợp volume là `tick` hoặc `n/a`, bộ lọc mặc định chặn tín hiệu. `volume × close` chỉ là xấp xỉ, không phải tổng giá trị giao dịch thật `quoteVolume` của Binance. Vì vậy coin gần mức 10/20 triệu có thể đỗ ở một nơi và trượt ở nơi kia. Nếu muốn xem riêng trigger giá, tắt lọc ước tính và chỉ giao dịch những coin đã được scanner xác nhận. [TradingView: volume và metadata symbol](https://www.tradingview.com/pine-script-docs/concepts/chart-information/).
2. **Chi phí và đường đi giá:** Python dùng spot fee10bps + slip5bps/chiều, futures fee5bps + slip3bps/chiều. Pine tính commission theo %, nhưng execution slippage trong Properties là **số tick cố định**. Có thể ước tính `ticks ≈ giá tham chiếu × bps / 10000 / mintick`, rồi làm tròn lên; mức đó chỉ khớp bps tại một giá. Target Pine là limit; emulator có thể khớp tốt hơn target khi gap và không áp market slippage lên limit như mô hình Python. Broker emulator cũng không bảo đảm stop được ưu tiên nếu một nến chạm cả stop lẫn target. Bar Magnifier có thể cung cấp dữ liệu nội nến, nhưng vẫn không biến kết quả thành mô hình bảo thủ của Python. [Tài liệu strategy properties](https://www.tradingview.com/support/solutions/43000628599-strategy-properties/).
3. **Funding và thanh lý:** chart futures này không tính funding lịch sử, lịch thu funding thay đổi, mark price, maintenance margin tiers hay thanh lý đúng Binance. Mức 3× chỉ là giả định ký quỹ của emulator. Kết quả futures Strategy Tester có thể lạc quan hơn báo cáo có funding.
4. **Danh mục:** mỗi chart chỉ giữ một vị thế. Không thực thi đồng thời giới hạn 4 vị thế spot/2 futures, tổng risk sleeve 2%, tổng futures gross notional 2× sleeve, thứ tự xếp theo turnover khi nhiều setup xuất hiện, hoặc rủi ro tương quan/narrative. Không cộng lợi nhuận nhiều chart với cùng vốn ban đầu để suy ra lợi nhuận tài khoản 5.000 USD.
5. **Lịch sử:** nguồn, nến thiếu, độ dài khởi tạo EMA, cách đánh dấu equity và chốt cuối khoảng có thể khác. Danh sách coin lịch sử cố định có thiên lệch sống sót; Pine không tự khôi phục top200 marketcap hoặc top100 thanh khoản tại thời điểm quá khứ.

Lịch dùng đề xuất: sau 07:00 giờ Việt Nam cập nhật danh sách đủ thanh khoản bằng scanner; theo dõi spot ở các lần đóng H4 03:00, 07:00, 11:00, 15:00, 19:00, 23:00 và futures khi H1 đóng. Đối chiếu thời điểm nến hoàn tất bằng UTC trong alert. Chỉ dùng kết quả nghiên cứu đã đạt tiêu chí trong báo cáo và dữ liệu forward-test để quyết định triển khai vốn; script tự nó không xác nhận lợi thế.
