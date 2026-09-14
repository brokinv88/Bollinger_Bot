# Hồ sơ và đặc tả Bollinger Envelopes v0

Ngày 09/09/2026. Rà soát tĩnh mã người dùng; chưa biên dịch hoặc chạy backtest. Bản gốc: `bollinger-envelopes-original-v0.pine`. Chưa sửa chiến lược hay cấu hình giao dịch.

## Hồ sơ đã xác nhận

- Ưu tiên crypto, Binance spot và futures; thời gian full-time.
- Vốn tổng dự kiến 5.000 USD; drawdown dự kiến 40%; chưa có nhật ký.
- Chưa xác định phân bổ spot/futures, coin, timeframe chính, loại futures, đòn bẩy, margin mode và cấu hình thực tế trong TradingView Properties.
- Diễn giải DD ứng viên: giảm equity so với đỉnh equity, gồm P&L chưa thực hiện và chi phí, điều chỉnh nạp/rút. Cần chốt trước vận hành. Nếu đỉnh là 5.000 USD, giảm 40% là còn 3.000 USD; cần tăng 66,67% để trở về đỉnh. Mốc tiền thay đổi khi đỉnh thay đổi. Đây là sức chịu lỗ dự kiến, chưa phải mức sizing hay cổng được cài trong mã.

## Logic chính xác ở mặc định

- Upper = SMA(high,20) + 1,5 × stdev(high,20).
- Lower = SMA(low,20) − 1,5 × stdev(low,20).
- Mid = (Upper + Lower)/2, chỉ vẽ, không tham gia quyết định.
- Chỉ Long. Close phải lớn hơn cả SMA(close) 50/100/150/200 nếu bật bộ lọc. Không yêu cầu thứ tự SMA50 > SMA100 > SMA150 > SMA200 hoặc độ dốc tăng.
- Entry: close hiện tại > upper hiện tại và close trước <= upper trước, đồng thời đạt bộ lọc. Biên hiện tại có sử dụng high của nến hiện tại.
- Tối đa ba entry cùng chiều đang mở, cùng ID Long, mỗi entry theo giá trị cash 50 đơn vị tiền tài khoản. Không phải rủi ro 50 USD; không phải tự thêm mỗi nến trên Upper. Cần crossover mới.
- Thoát toàn bộ entry ID Long khi close crossunder Lower hoặc bất kỳ một SMA nào, tùy công tắc exit. Crossunder là sự kiện cắt xuống, không đơn thuần đang ở dưới.
- Mặc định chiến lược tính khi nến đóng, market order khớp ở tick tiếp theo, thường open nến sau trong lịch sử. Properties có thể ghi đè các mặc định.
- D1/H4/H1 trong bảng chỉ là chữ và tô màu. Không có request.security, không phân tích đa khung, không hạn chế chỉ ba timeframe này.

## Các khoảng trống và vấn đề

1. initial_capital=10000 khác vốn người dùng 5000. Bản thử cá nhân hóa phải có phiên bản riêng.
2. Không có stop order bảo vệ, target, sizing theo rủi ro, giới hạn equity DD hoặc tổng rủi ro nhiều coin. Exit theo nến không giới hạn số tiền lỗ trước entry.
3. Pyramiding tối đa ba lần 50 tương đương tổng giá trị entry khoảng 150 trên một chart theo giả định USD; giá trị vị thế hiện tại biến động. DD thấp khi dùng rất ít vốn không tự chứng minh an toàn khi tăng size hoặc mở nhiều coin.
4. Phí mặc định 0,075% trên giá trị khớp mỗi chiều; chưa xác minh đúng tài khoản Binance. Không có slippage khai báo hoặc funding mô phỏng; chưa mô hình hóa đầy đủ margin/thanh lý Binance futures.
5. Tắt use_4sma chỉ bỏ lọc entry và ẩn SMA; exit SMA vẫn hoạt động nếu exit_under_any_sma=true. Bảng có thể ghi DAT: Tren 4 SMA dù bộ lọc tắt.
6. Các nhãn SMA, 3x50 và một số mô tả là chuỗi cố định; đổi tham số/Properties có thể khiến bảng sai với cấu hình. Comment cập nhật mỗi tick không phù hợp mặc định strategy không calc_on_every_tick.
7. Hai nhánh close độc lập có thể cùng được gọi một nến. Cần kiểm tra lý do exit và khớp trên TradingView khi đối chiếu; không suy ra rằng hệ thống bán gấp đôi.
8. Nếu tắt bộ lọc entry, tín hiệu vào và exit SMA có thể trùng nến. Phiên bản mới cần quy tắc ưu tiên rõ; baseline giữ nguyên để đối chiếu.
9. pos_usd = position_size × close giả định quy ước sản phẩm phù hợp; không coi là công thức tổng quát cho mọi hợp đồng/đồng tiền.

## Bước tiếp theo

1. Chốt coin và timeframe người dùng đang sử dụng, 50 USD là giá trị mua mong muốn hay ý định rủi ro, cùng cấu hình futures hiện hành.
2. Đóng baseline nguyên trạng. Ghi lại chart standard OHLC, symbol/sàn, timeframe, khoảng ngày, Inputs và Properties thực tế để tái lập.
3. Tạo bản nghiên cứu với vốn 5000, chi phí đúng từng thị trường; so kết quả trên ngân sách danh mục chung. Spot và futures báo cáo riêng. Không tự thêm Short.
4. Nhật ký ghi signal time, fill time, symbol/market/timeframe/version, entry lần mấy, qty/notional, phí/funding, exit reason, P&L ròng, trạng thái và vi phạm. Baseline không có rủi ro tiền ban đầu xác định thì R để trống, không lấy 50 làm 1R.
5. Đo baseline trước; thử stop bảo vệ và sizing như thí nghiệm riêng theo rules R01/R07/T04–T06. Không trộn kết quả bản sửa với bản gốc.

## Cập nhật phạm vi và đề xuất nghiên cứu

Người dùng xác nhận: top 100 thanh khoản bình quân 20 ngày; spot H4/D1, futures H1/H4. Giá trị 50 USD chỉ để thử nghiệm. Chưa chọn đòn bẩy và margin mode.

Quy ước nghiên cứu đề xuất: thanh khoản là trung bình quote volume USDT của 20 ngày UTC đã đóng, xếp hạng lại đầu mỗi ngày, tách spot và USDⓈ-M perpetual USDT. Loại cặp stablecoin/stablecoin và token đòn bẩy; cần đủ 20 ngày để xếp hạng và đủ nến chỉ báo. Tái tạo danh sách theo từng thời điểm lịch sử, gồm sản phẩm hủy niêm yết khi có dữ liệu; không dùng top 100 hôm nay cho toàn bộ quá khứ. Nếu không tái tạo được lịch sử niêm yết, phải công bố giới hạn thiên lệch. Rời top 100 chặn entry mới; vị thế cũ vẫn theo exit, trừ sự kiện sản phẩm cần quy tắc riêng.

Bốn nhánh đối chứng: spot H4, spot D1, futures H1, futures H4; đều Long-only theo bản gốc. Chưa chọn nhánh thắng trước khi kiểm thử. Portfolio dùng tổng vốn chung 5000; không cộng bốn backtest vốn 5000 riêng rồi gọi là danh mục vốn 5000.

Đề xuất cho paper futures: isolated, 2x, USDⓈ-M perpetual USDT, one-way, không tự bổ sung margin. Đây là cấu hình vận hành ứng viên, chưa được áp dụng trên tài khoản. Cross chia sẻ collateral giữa các vị thế cross liên quan; isolated hỗ trợ kiểm soát khoản margin phân bổ từng vị thế, không thay thế stop-loss. Không tính khoảng thanh lý đơn giản bằng 1/leverage; phải xét mark price, maintenance margin tier, funding, phí và margin thực tế.

Thiết kế nhánh quản trị rủi ro riêng sau baseline: stop bảo vệ xác định trước entry; ngân sách rủi ro khởi đầu để thử 0,25% equity cho toàn bộ một ý tưởng/coin, kể cả các lần pyramid và vị thế spot/futures liên quan; tổng rủi ro dự kiến đang mở 1% equity. Đây là ngưỡng đề xuất chưa được kiểm chứng, không phải tuyên bố an toàn hay tối ưu. Không tăng size vì người dùng chấp nhận DD 40%. Chưa có stop thì chưa tính được risk sizing này. Stress gap/slippage/correlation và giới hạn notional/margin cần được kiểm thử thêm.

Ví dụ toán học trước phí: equity 5000, risk 0,25%=12,50; stop cách entry 5% => notional 250; ở 2x initial margin xấp xỉ 125. Chi phí/buffer làm notional cho phép nhỏ hơn. Stop thực tế có thể trượt; 12,50 không phải trần tổn thất được bảo đảm.

Nguồn: https://www.binance.com/en/academy/articles/what-are-isolated-margin-and-cross-margin-in-crypto-trading và https://www.binance.com/fr-AF/blog/futures/5845477141003990750

Nguồn về cơ chế Pine: https://www.tradingview.com/pine-script-docs/v5/concepts/strategies/
