# Đặc tả sơ bộ AI Trading OS theo video Hermes

Nguồn: https://www.youtube.com/watch?v=07C2M4_AIxU&t=448s

Video: “I Think I Built the Future of Trading (Fable 5 + Hermes)” — Dan | FXC, đăng 13/07/2026, dài 10:52. Nghiên cứu ngày 08/09/2026 qua toàn bộ bản chép lời YouTube và quan sát giao diện tại khoảng 7:46. Bản chép lời tự động có thể sai tên riêng và thuật ngữ; chưa xác minh mã nguồn, hiệu quả thực tế hay toàn bộ thao tác trong video.

## Những gì video trình bày

| Mốc | Chức năng / thông tin | Mức độ xác nhận |
|---|---|---|
| 0:25–0:41 | Hệ thống hỗ trợ nâng cao chất lượng trading; tác giả nói chưa tự đặt lệnh | Lời tác giả |
| 0:55–1:22 | Đọc lịch sử cTrader, tự ghi nhật ký và nhận xét giao dịch | Lời tác giả |
| 1:29–1:46 | Phân tích hiệu suất, chiến lược, tâm lý, thực thi, quản trị rủi ro, chất lượng nhật ký | Lời tác giả |
| 1:46–2:16 | Reflection cycle: tổng kết và đối chiếu giao dịch trước để tìm mẫu lặp lại | Lời tác giả |
| 2:25–3:45 | Khoảng 15–18 agent; giao tiếp Telegram; các vai trò dashboard designer, reflection coach, portfolio manager | Số lượng được tác giả nói không nhất quán |
| 4:07–4:42 | Đưa kiến thức chiến lược vào hệ thống: Fibonacci, EMA 200, EMA 200 tuần, vùng tháng, key level | Thiếu định nghĩa và quy tắc chính xác |
| 6:17–6:43 | Agent đề xuất prompt theo tuần/cuối phiên; macro regime watcher gắn bối cảnh cho lệnh | Lời tác giả; thuật ngữ regime trong phụ đề chưa rõ |
| 6:51–7:15 | Agent quản lý còn muốn bổ sung; backtest research Q&A đang idle vì thiếu hướng dẫn | Chưa hoàn thiện |
| Khoảng 7:46 | Giao diện tối, tab Command/Analytics/Journal/Geopolitics, reflection panel, scanner, Monte Carlo projection, danh sách giao dịch | Quan sát một khung hình; chưa xác minh công thức hoặc dữ liệu |
| 8:51–9:26 | Tích hợp nguồn tin/sự kiện địa chính trị bên thứ ba | Chưa biết nhà cung cấp |
| 9:43–10:09 | Đọc hành động thực tế trên cTrader và đề xuất cải thiện | Mục tiêu cốt lõi theo tác giả |

Không suy ra việc có nhiều agent hoặc dùng từ “self-improves” là bằng chứng tăng lợi nhuận. Video có nêu lỗi thiếu entry/exit/SL và lọc sản phẩm sai tại 5:36–6:08.

## Thiết kế đề xuất cho dự án này

Các mục sau là đề xuất triển khai, không phải tính năng đã xác minh trong video.

1. Nhật ký chuẩn hóa: tài khoản, nguồn, mã giao dịch, sản phẩm, chiều, thời gian, giá và khối lượng khớp, phí, funding nếu có, stop ban đầu, chiến lược và phiên bản, ghi chú trước/sau lệnh. Nhập lặp không tạo giao dịch trùng; hỗ trợ nhiều lần khớp và đóng một phần. Dữ liệu thiếu phải được đánh dấu.
2. Analytics tính bằng chương trình: P&L ròng, win rate, profit factor, expectancy, R khi đủ stop ban đầu, drawdown theo equity. Nếu chỉ có lịch sử đóng lệnh thì ghi rõ đường vốn chỉ dựa trên lệnh đóng. Mọi nhận xét AI dẫn tới lệnh và phép tính cụ thể.
3. Kho quy tắc chiến lược có phiên bản: setup, timeframe, điều kiện vào/ra, stop/target, điều kiện bỏ lệnh và giới hạn rủi ro. Agent kiểm tra tuân thủ đối với phiên bản có hiệu lực tại lúc giao dịch.
4. Các vai trò phân tích ban đầu: hiệu suất, tuân thủ chiến lược, rủi ro, thực thi, chất lượng nhật ký/tâm lý. Nhận định tâm lý phải dựa trên ghi chú của trader; không kết luận FOMO hoặc revenge trading chỉ từ lệnh thua.
5. Reflection theo lệnh đóng hoặc cuối phiên: dữ kiện → đối chiếu quy tắc → mẫu lặp → giả thuyết → đề xuất kiểm chứng → theo dõi kết quả. Có mã chu kỳ, trạng thái, lịch sử, giới hạn thời gian và chi phí.
6. Bộ điều phối: hàng đợi tác vụ, retry giới hạn, timeout, trạng thái idle/running/failed, nhật ký lỗi. Không cần chạy 15–18 tiến trình AI liên tục để tái tạo các vai trò của video.
7. Chat trong ứng dụng và Telegram: truy vấn nhật ký, yêu cầu tổng kết, nhận báo cáo; cấu hình tài khoản người dùng được phép truy cập.
8. Nghiên cứu/backtest: tách giả thuyết mới khỏi chiến lược đang dùng; kiểm thử ngoài mẫu, chi phí, độ nhạy; lưu dữ liệu và phiên bản. Prompt/chiến lược mới là bản đề xuất cho tới khi được kiểm chứng.
9. Tin tức và chế độ thị trường: lưu nguồn, thời gian sự kiện, thời gian hệ thống nhận tin; không dùng tin xuất hiện sau giao dịch để giải thích như thông tin đã biết trước.

## Chiến lược cần nghiên cứu tiếp

Video này chưa đủ để viết bản sao chiến lược tác giả. Cần xác minh: thị trường/timeframe, cách xác định key level và vùng tháng, cách neo Fibonacci, tham số EMA và dữ liệu tuần, trigger vào lệnh, stop/target, sizing, phiên giao dịch và bộ lọc tin. Một từ được phụ đề ghi là “keybo” chưa được xác minh.

Chưa lựa chọn Fable 5 hoặc một framework Hermes cụ thể chỉ dựa trên tên gọi trong video. Cần xác minh sản phẩm, API, tài liệu chính thức và khả năng vận hành trước khi chốt công nghệ.

## Đối chiếu thư mục hiện có

Đã đọc `strategy_lab/README_VI.md` và `donchian-web/README.md`; đây là đối chiếu tài liệu, chưa phải kiểm toán mã hoặc chạy lại kết quả.

- Strategy Lab đã mô tả nghiên cứu và dữ liệu kiểm thử chiến lược crypto. Có thể dùng kết quả làm đầu vào cho agent nghiên cứu sau khi kiểm tra schema và nguồn dữ liệu.
- Donchian Web đã mô tả giao dịch mô phỏng, lưu sổ lệnh và dashboard tiếng Việt. Có thể bổ sung lớp journal/reflection nếu người dùng chọn nền tảng crypto hiện tại.
- Chưa xác minh kết nối cTrader, bộ điều phối AI hay reflection đã tồn tại trong mã.
- Không coi Donchian hoặc spot breakout hiện có là chiến lược trong video.

## Thứ tự triển khai

Giai đoạn 1: thống nhất nguồn giao dịch → chuẩn hóa nhật ký → analytics kiểm chứng được → reflection với bằng chứng và báo cáo tiếng Việt.

Giai đoạn 2: kho chiến lược và kiểm tra tuân thủ → điều phối các vai trò AI → Telegram → bộ nhớ các đề xuất và kết quả.

Giai đoạn 3: backtest giả thuyết, thông tin thị trường và dashboard nâng cao. Monte Carlo chỉ bổ sung khi đã xác định rõ phương pháp, giả định và dữ liệu đủ phù hợp.

Điều kiện nghiệm thu đầu tiên: nhập cùng dữ liệu hai lần không trùng; đối soát phí và P&L; số liệu thiếu không bị bịa; báo cáo liên kết đúng lệnh; tác vụ lỗi hiển thị rõ; có thể tái tạo báo cáo từ cùng snapshot dữ liệu và phiên bản quy tắc. Chưa kết nối tài khoản hoặc đặt lệnh trong đợt nghiên cứu này.
