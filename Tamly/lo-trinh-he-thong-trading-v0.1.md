# Lộ trình hệ thống trading cá nhân — v0.1

Ngày: 08/09/2026. Trạng thái: bản khởi tạo để cùng người dùng cá nhân hóa; chưa phải chiến lược đã kiểm chứng.

## Cơ sở và cách sử dụng

- `rules.md`: nguyên tắc quản trị, tâm lý, dữ liệu và kiểm chứng do người dùng yêu cầu áp dụng.
- Giáo trình BEAST-FX đính kèm: nguồn ý tưởng và ngôn ngữ phân tích; không phải bằng chứng lợi thế.
- Ba ảnh HERMES: tham khảo bố cục command center, nhật ký, review và trạng thái vận hành. Không suy ra hệ thống thực tế hay hiệu suất từ ảnh.
- README hiện có cho thấy `strategy_lab` và `donchian-web` đã có nghiên cứu/paper crypto. Chưa kiểm toán lại mã hay kết quả trong bước này; chưa quyết định tích hợp.

## Những điểm cần xử lý trước khi dùng giáo trình

1. Không mặc định rủi ro 1–2%/lệnh, target 2R hoặc tăng size A+; theo R07, S02, S10 cần cá nhân hóa và kiểm chứng.
2. Day 19 viết bullish sweep xuống dưới các “đỉnh trước”; không nhất quán với SSL dưới đáy ở Day 8. Khi định nghĩa ứng viên sẽ dùng quét đáy, và ghi rõ điều kiện xác nhận.
3. Giáo trình dùng nhiều bộ khung thời gian khác nhau. Chọn một bộ cố định cho mỗi phiên bản thử nghiệm.
4. Các mô tả “nến mạnh”, “zone chất lượng”, “xác nhận”, “swing quan trọng” cần tiêu chí có thể chấm lại trước khi biết kết quả.
5. Những câu tuyệt đối về lấp FVG, số lần chạm làm vùng mạnh hơn hoặc quan hệ USD/vàng không được chuyển thẳng thành quy tắc giao dịch.
6. Không suy ra lệnh tổ chức từ OHLC; OB/FVG là đặc trưng giá ứng viên theo S04.

## Các bước và đầu ra

| Bước | Công việc | Đầu ra / điều kiện chuyển bước |
|---|---|---|
| 1. Hồ sơ | Chọn thị trường, broker, lịch giao dịch, vốn chịu rủi ro, kinh nghiệm và giới hạn hiện hành | Hồ sơ đủ để lựa chọn phạm vi; các ô chưa biết giữ trống |
| 2. Một setup | Định nghĩa bối cảnh, swing, vùng, trigger, entry, SL, exit, sizing, điều kiện bỏ qua | Hai lượt chấm replay thống nhất được; không nhìn nến tương lai |
| 3. Nhật ký và kiểm tra rủi ro | Ghi kế hoạch trước entry, thực thi, phí, cảm xúc, vi phạm và cơ hội bỏ qua | Bản ghi truy ngược được; số thiếu hiển thị thiếu |
| 4. Kiểm chứng | Baseline cố định, chia dữ liệu theo thời gian, chi phí, kiểm tra độ nhạy và ngoài mẫu | Báo cáo cả thất bại, số thử nghiệm, độ bất định; có thể kết luận chưa đủ bằng chứng |
| 5. Paper/forward | Dùng quy tắc cố định trên dữ liệu mới, ghi giá có thể khớp và sai lệch vận hành | Đánh giá chi phí thực tế, tuân thủ và chất lượng dữ liệu trước khi xét bước tiếp |
| 6. Dashboard và trợ lý | Tổng hợp dữ liệu đã đối chiếu; hỗ trợ review và đề xuất thí nghiệm | Mọi chỉ số có nguồn, thời điểm, phiên bản và cách tính |

Không gắn lịch hoàn thành cứng vào số ngày của giáo trình. Số mẫu và tiêu chí đánh giá sẽ được viết trước thí nghiệm; không có một số lệnh bảo đảm lợi thế.

## Bộ công cụ ưu tiên

1. Phiếu kế hoạch và nhật ký: trước phiên → trước lệnh → sau lệnh → review phiên/tuần.
2. Bộ tính khối lượng và kiểm tra giới hạn: cần tick size/value, bước lot, đồng tiền tài khoản, phí và thông số đúng broker. Thiếu thông số thì không xuất khối lượng có vẻ chính xác.
3. Trình nhập và đối chiếu lịch sử: giữ bản gốc, chống trùng, xử lý đóng từng phần, phí/swap và múi giờ.
4. Replay/backtest: chỉ dùng thông tin có ở thời điểm quyết định; swing cần nến bên phải phải chờ được xác nhận. Nến chạm cả SL và TP cần dữ liệu chi tiết hơn hoặc giả định bảo thủ được công bố.
5. Dashboard: P&L ròng, R thực hiện, drawdown equity, số mẫu, tuân thủ, vi phạm, cơ hội bỏ qua, độ mới dữ liệu.

R thực hiện = P&L ròng / rủi ro tiền ban đầu đã ghi. Thiếu rủi ro ban đầu thì R để trống. R:R kế hoạch hiển thị riêng. Drawdown equity cần dữ liệu vị thế đang mở và xử lý nạp/rút; không gọi đường lệnh đã đóng là equity đầy đủ.

Trong ảnh HERMES có RSI null, equity NaN và 10 realized trades đi cùng 45 reflection cycles. Đây là những điểm cần kiểm tra dữ liệu và ý nghĩa chỉ số nếu triển khai tương tự; ảnh không đủ xác nhận nguyên nhân. Bản mới cần hiện “thiếu dữ liệu/chưa đủ mẫu” thay cho số giả hoặc dự báo chắc chắn.

## Setup nghiên cứu ứng viên nếu chọn XAUUSD

Theo hướng khung cao → chờ hồi về vùng xác định trước → quét mức swing → nến đóng xác nhận cấu trúc → entry theo quy tắc → stop tại điểm vô hiệu → exit cố định.

Đây mới là khung ý tưởng. Chưa ấn định bộ timeframe, thuật toán swing, độ rộng vùng, thời hạn xác nhận, loại lệnh, bộ lọc tin, stop buffer hay target. Trước khi kiểm thử cần điền đủ và đóng phiên bản; OB/FVG là bộ lọc thử riêng để đo giá trị bổ sung.

## Hồ sơ cần người dùng bổ sung

- Ưu tiên Forex/XAUUSD, crypto hiện có, hay cả hai theo thứ tự nào:
- Kinh nghiệm và setup đang thực sự dùng:
- Broker/nền tảng, loại tài khoản demo/thật/prop, đồng tiền tài khoản:
- Vốn dành riêng và giới hạn lỗ hiện hành; với prop cần cơ chế drawdown/reset:
- Khung giờ có thể giao dịch theo giờ Việt Nam, thời gian giữ lệnh phù hợp:
- Vấn đề lớn nhất hiện tại và dữ liệu nhật ký/lịch sử sẵn có:

## Cách đồng hành

Mỗi vòng giải quyết một quyết định, tạo đầu ra có thể xem lại và ghi điều còn thiếu. Trước phiên hỗ trợ viết kịch bản; sau phiên đối chiếu kế hoạch với thực thi; review tách chất lượng quyết định khỏi kết quả tiền. AI hỗ trợ nghiên cứu và công cụ trong phạm vi yêu cầu hiện tại. Việc kết nối thực thi hoặc thay giới hạn tài khoản là một phạm vi cần xác định riêng khi có nhu cầu cụ thể.
