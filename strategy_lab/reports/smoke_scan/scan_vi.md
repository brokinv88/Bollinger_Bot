# Danh sách Binance hằng ngày — chỉ đọc

Thời điểm quét: **2026-09-06T23:43:19+00:00** (UTC).

**EXPANDED_UNVALIDATED**: danh sách top thanh khoản hiện tại chưa được kiểm chứng lịch sử như một danh mục. Kết quả nghiên cứu trên 12 coin cố định không chứng minh lợi thế của top 100 hoặc narrative.

SETUP chỉ có nghĩa là nến đã đóng tạo tín hiệu; không có lệnh được gửi. EXPIRED_SIGNAL là tín hiệu có thời điểm vào theo mô hình đã qua hơn 60 giây: không dùng bảng này để đuổi giá. WATCH là đạt bộ lọc nhưng chưa có trigger.

Trạng thái dữ liệu: **OK**. Số lượng: FILTERED_OUT=2, WATCH=4.

Giá vào/stop/target và khối lượng chỉ là ví dụ tính từ giá đóng nến, gồm giả định phí/trượt giá; phải tính lại tại giá khớp thực tế. Các tín hiệu hết hạn không được giữ chỗ rủi ro. Thứ tự ưu tiên: median doanh số ngày đã xác nhận, rồi symbol.

Tài khoản: chưa cung cấp trạng thái; mặc định giả định spot 3.000, futures 1.000, dự phòng 1.000 USDT và không có vị thế. Khối lượng chỉ minh họa.

## Coin đạt bộ lọc

| Thị trường | Coin | Trạng thái | Hướng | Median ngày (USDT) | Giờ vào mô hình UTC | Khối lượng tham khảo | Trạng thái size |
|---|---|---|---|---:|---|---:|---|
| futures | BTCUSDT | WATCH | none | 9,401,390,695 | 2026-09-06T23:00:00+00:00 | 0 | NO_SIGNAL |
| futures | ETHUSDT | WATCH | none | 7,862,909,210 | 2026-09-06T23:00:00+00:00 | 0 | NO_SIGNAL |
| futures | ZECUSDT | WATCH | none | 956,499,811 | 2026-09-06T23:00:00+00:00 | 0 | NO_SIGNAL |
| spot | ZECUSDT | WATCH | none | 132,984,914 | 2026-09-06T20:00:00+00:00 | 0 | NO_SIGNAL |

## Cách đọc

- FILTERED_OUT: chưa đạt bộ lọc xu hướng, sức mạnh hoặc thanh khoản; xem đầy đủ trong CSV/JSON.
- INSUFFICIENT_HISTORY: chưa đủ dữ liệu; token mới không được lách điều kiện lịch sử.
- Giữ chỗ rủi ro chỉ là mô phỏng trên các SETUP trong lần quét này, không biết các thay đổi tài khoản sau thời điểm nhập.
- Narrative là nhãn nhập thủ công, không phải dữ liệu đang thịnh hành. Không có bộ lọc market cap vì Binance không cung cấp market cap trong các endpoint này.
- Tổng khối lượng futures dùng 3× để minh họa ký quỹ. Funding chưa biết trong tương lai không được tính vào ngân sách stop; quản lý riêng khi giữ vị thế.
- Quét ngày có thể bỏ lỡ trigger H1/H4; dùng Pine alerts khi nến đóng để theo dõi giữa các lần quét.
- Tệp tradingview_spot.txt / tradingview_futures.txt gồm coin đạt bộ lọc để nhập vào watchlist; tính năng nhập tùy gói TradingView.
