# Bộ lọc Binance hằng ngày

Công cụ đọc API công khai Binance, xuất danh sách quan sát và watchlist TradingView. Không yêu cầu API key. Đây là bộ lọc nghiên cứu, không gửi lệnh, không quản lý tài khoản đang mở.

**Theo kết quả kiểm thử hiện tại:** spot breakout là ứng viên để paper trade; chưa đạt cổng tối thiểu 100 lệnh ngoài mẫu. Futures pullback không đạt hiệu quả ngoài mẫu. Các tín hiệu trong bộ lọc không phải khuyến nghị giao dịch tiền thật. Xem [báo cáo backtest](reports/REPORT_VI.md).

## Chạy mỗi ngày

Mở `run_daily.command` trong thư mục này bằng Terminal trên macOS. File chạy từ vị trí của chính nó, không phụ thuộc thư mục Terminal hiện tại. Kết quả gần nhất nằm ở [reports/daily_latest/scan_vi.md](reports/daily_latest/scan_vi.md). Đây là công cụ chạy theo yêu cầu, **chưa cài lịch tự chạy nền**.

Nếu chạy từ Terminal tại thư mục dự án Trading:

```sh
.venv/bin/python -m strategy_lab.scanner --limit 100 --output-dir strategy_lab/reports/daily_latest
```

Nên cập nhật danh sách sau 07:00 giờ Việt Nam, khi ngày UTC mới bắt đầu. Theo dõi trigger bằng Pine tại các lần đóng H4: 03:00, 07:00, 11:00, 15:00, 19:00, 23:00; futures H1 mỗi giờ. Báo cáo ngày không bắt được tất cả tín hiệu trong ngày. Tín hiệu ngoài mẫu giả định vào ngay mở nến sau; không diễn giải một tín hiệu đã cũ thành điểm vào hiện tại.

## Tiêu chí lọc

1. Chỉ cặp USDT còn được Binance cho giao dịch. Futures phải là USD-M perpetual, ký quỹ USDT. Loại stablecoin, tài sản neo, wrapper và token đòn bẩy theo danh sách minh bạch trong mã.
2. Chọn top 100 mỗi thị trường theo quoteVolume 24 giờ hiện tại. Đây là bước thu hẹp dữ liệu, **không phải top 100 lịch sử hoặc xếp hạng theo trung vị 30 ngày toàn sàn**.
3. Xác nhận trung vị giá trị giao dịch ngày của 30 ngày hoàn tất: spot ≥10 triệu USDT; futures ≥20 triệu USDT.
4. Spot cần 200 ngày lịch sử, D1 giá >EMA50 >EMA200, BTC D1 trên EMA200; ROC20 altcoin >ROC20 BTC. BTC được miễn so sánh với chính mình. Futures cần 200 H4, 30 D1, xu hướng H4 và độ dốc EMA50 đúng hướng.
5. Kiểm tra trigger đúng quy tắc [SPEC](SPEC.md) trên nến H4/H1 gần nhất đã đóng. Dữ liệu khung lớn chỉ có hiệu lực khi đã biết tại lúc mở nến tín hiệu.
6. Coin cùng vượt điều kiện được sắp theo trung vị doanh số ngày đã xác nhận giảm dần, sau đó mã coin. Không sắp theo kết quả tương lai.

Công cụ hiện không lọc top 200 market cap: Binance không trả market cap từ các endpoint đang dùng. Narrative là nhãn do bạn nhập, không tự nhận định nhóm nào đang hot. Các coin ngoài 12 cặp backtest đều cần theo dõi thử riêng; kết quả cả watchlist mở rộng mang nhãn `EXPANDED_UNVALIDATED`.

Thanh khoản ở đây là doanh số, chưa đo spread/độ sâu sổ lệnh tại giá và khối lượng thực tế. Cần kiểm tra khả năng khớp lệnh lúc vào; không coi volume lớn là bảo đảm trượt giá thấp.

## Đọc kết quả

| Trạng thái | Ý nghĩa |
|---|---|
| WATCH | Đạt bộ lọc, chưa có trigger trên nến vừa đóng |
| SETUP | Có trigger; thời điểm mở nến theo mô hình mới qua không quá 60 giây. Vẫn cần kiểm tra thực tế; không bảo đảm giá mở còn khớp được |
| EXPIRED_SIGNAL | Có trigger nhưng thời điểm vào theo mô hình đã qua hơn 60 giây; chỉ lưu để theo dõi, không đuổi giá |
| FILTERED_OUT | Chưa đạt một hoặc nhiều điều kiện |
| INSUFFICIENT_HISTORY | Chưa đủ lịch sử; token mới bị loại |
| DATA_ERROR | Thiếu, cũ, lệch thời gian hoặc dữ liệu không hợp lệ; không đưa ra tín hiệu |

Nếu lần quét kéo dài qua lần đóng nến kế tiếp, các dòng bị ảnh hưởng sẽ bị đánh dấu dữ liệu cũ. `OK` chỉ nói dữ liệu quét thành công, không phải setup đã được kiểm định sinh lời. `PARTIAL` ghi rõ các cặp không lấy được dữ liệu. `FAILED` không được diễn giải là thị trường không có cơ hội.

Mỗi lần quét xuất:

- `scan_vi.md`: bảng đọc nhanh bằng tiếng Việt.
- `scan.csv`: toàn bộ tiêu chí, trạng thái và sizing tham khảo.
- `scan.json`: nguồn, thời gian và dữ liệu để kiểm toán.
- `tradingview_spot.txt`, `tradingview_futures.txt`: danh sách nhập TradingView; perpetual có hậu tố `.P`. Quyền import tùy gói TradingView.

## Vốn và vị thế đang mở

Mặc định giả định spot 3.000, futures 1.000, dự phòng 1.000 USD và không có vị thế. Đây chỉ là **kịch bản minh họa**, không đọc số dư Binance của bạn.

Để phản ánh tài khoản: sao chép `account.example.json` thành `account.json`, cập nhật equity gồm lãi/lỗ chưa chốt, đỉnh equity từng phần, vốn dự phòng và vị thế đang mở. File chạy mỗi ngày tự đọc `account.json` nếu có. Khi chạy lệnh trực tiếp, thêm `--account strategy_lab/account.json`.

Một vị thế mẫu trong mảng `positions`:

```json
{
  "market": "spot",
  "symbol": "ETHUSDT",
  "side": "long",
  "initial_risk_usdt": 20,
  "notional_usdt": 500
}
```

`notional_usdt` cần cập nhật giá trị vị thế hiện tại. `initial_risk_usdt` là rủi ro ban đầu còn đang giữ chỗ; bộ lọc chưa mô hình hóa trailing hoặc chốt từng phần. Khi drawdown chạm 12%, đặt trường `spot_halted` hoặc `futures_halted` thành `true` và giữ trạng thái đó cho tới khi hoàn tất đánh giá lại. Công cụ không tự ghi nhớ đỉnh hoặc lịch sử dừng giữa các lần quét; bạn cung cấp trạng thái đúng.

Ngân sách tham chiếu: spot 20/3.000 equity, futures 12,50/1.000 equity; trần tổng rủi ro ban đầu mỗi phần 2%. Nếu không còn đủ toàn bộ ngân sách cơ sở thì bỏ qua, không tự chia nhỏ để nhét thêm lệnh. Vì vậy futures thường chỉ còn chỗ cho một lệnh với ngân sách đầy đủ. Trần một lệnh: spot 25% equity, futures 100% equity; tối đa 4 spot/2 futures; gross futures ≤2× và ký quỹ minh họa3×.

Từ drawdown8%, giảm nửa ngân sách và trần notional cho lệnh mới; từ12% ngừng gợi ý khối lượng mới. Trong một lần quét, công cụ chỉ giữ chỗ rủi ro cho các SETUP chưa hết hạn. Giá dùng tính khối lượng là close tham khảo có phí/trượt giá, **không phải giá vào được bảo đảm**. Stop làm tròn theo tick, khối lượng làm tròn xuống theo các LOT_SIZE hiện tại và kiểm tra min notional. Sai khác so với giá fill thực tế phải được tính lại.

## Narrative

Sao chép `narratives.example.json` thành `narratives.json`, chỉnh các nhãn theo nghiên cứu của bạn. File chạy mỗi ngày sẽ đọc tự động; lệnh trực tiếp dùng `--narratives strategy_lab/narratives.json`.

Các vị thế cùng nhãn và cùng hướng, hoặc cùng coin ở hai thị trường, được cộng rủi ro với hạn mức 0,75% tổng equity. Đây là giới hạn bổ sung khi quản lý live, chưa được backtest như bộ lọc narrative lịch sử. Không có nhãn không đồng nghĩa các coin độc lập.

## Kiểm tra và tái lập

```sh
.venv/bin/python -m unittest discover -s strategy_lab/tests -v
.venv/bin/python -m strategy_lab.scanner --limit 3 --output-dir strategy_lab/reports/smoke_scan
```

Công cụ lấy dữ liệu mới vào bộ nhớ và xuất báo cáo riêng; không sửa kho dữ liệu lịch sử có hash. Nếu Binance chặn mạng hoặc rate limit, không tự chuyển sang dữ liệu giả hoặc coi funding/giá thiếu là0.
