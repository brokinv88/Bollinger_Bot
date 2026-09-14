# Nghiên cứu setup và bộ lọc Binance cho vốn 5.000 USD

**Kết luận:** giữ spot breakout D1/H4 làm ứng viên paper trade; loại futures pullback H4/H1 khỏi kế hoạch dùng tiền thật theo cấu hình đang kiểm thử. Spot có kết quả tích cực nhưng chỉ có 85 lệnh ngoài mẫu, chưa đạt cổng tối thiểu 100 lệnh đã đặt trước. Chưa setup nào được thông qua để triển khai vốn thật.

## Mở các kết quả

| Nội dung | Tệp |
|---|---|
| Kết quả, quy tắc, chi phí và giới hạn kiểm thử | [Báo cáo đầy đủ](reports/REPORT_VI.md) |
| Đường vốn và drawdown | [Biểu đồ](reports/equity_drawdown.png) |
| Kết quả quét 100 spot + 100 futures gần nhất | [Danh sách hằng ngày](reports/daily_latest/scan_vi.md) |
| Hướng dẫn dùng bộ lọc và cập nhật vốn | [Hướng dẫn scanner](SCANNER_VI.md) |
| Chạy bộ lọc bằng Terminal trên macOS | [run_daily.command](run_daily.command) |
| Setup spot trên TradingView | [Mã Pine spot](tradingview/spot_d1_h4_breakout.pine) |
| Setup futures bị loại, giữ để kiểm tra nghiên cứu | [Mã Pine futures](tradingview/futures_h4_h1_pullback.pine) |
| Cài Pine, cảnh báo, khác biệt với Python | [Hướng dẫn TradingView](tradingview/README_VI.md) |

Hai script Pine đã được rà soát tĩnh và đưa mã spot vào Pine Editor. TradingView yêu cầu đăng nhập trước khi biên dịch, nên **chưa xác nhận biên dịch thành công**. Chưa lưu script hay tạo cảnh báo trên tài khoản của bạn.

## Kết quả ngoài mẫu

Khoảng **01/01/2025–31/08/2026**, phí và trượt giá cả hai chiều, funding thực cho futures:

| Chỉ tiêu | Spot D1/H4 | Futures H4/H1 |
|---|---:|---:|
| Vốn riêng lúc bắt đầu | 3.000 USD | 1.000 USD |
| Số lệnh | 85 | 464 |
| Lãi/lỗ ròng | +436,35 USD | −572,46 USD |
| Lợi nhuận trên vốn riêng | +14,55% | −57,25% |
| Profit factor | 1,41 | 0,76 |
| Tỷ lệ thắng | 35,29% | 26,94% |
| Kỳ vọng trung bình mỗi lệnh | +0,26R | −0,13R |
| Drawdown tối đa của phần vốn riêng | 10,20% | 68,30% |
| Lợi nhuận khi phí + trượt giá tăng gấp đôi | +9,56% | −75,70% |

Đây là **bản chạy liên tục không bật dừng tại drawdown 12%**, nhằm đo lợi thế nguyên gốc. Bản có giảm rủi ro và dừng mở mới được báo riêng. Sau khi dừng, bản đó giữ tiền và không tự khởi động lại; không coi sự đi ngang do ngừng giao dịch là bằng chứng chiến lược tốt.

Nếu chỉ mô phỏng spot 3.000 USD và giữ 2.000 USD tiền mặt trong cùng khoảng: tổng 5.000 USD thành 5.436,35 USD, lợi nhuận **8,73%**, drawdown equity **6,25%**. Nếu thêm setup futures như thử nghiệm, tổng còn 4.863,89 USD. Đây là so sánh lịch sử sau khi quan sát kết quả, không phải một danh mục mới đã được xác nhận ngoài mẫu.

Spot có 8/9 cấu hình lân cận có lãi trên 2022–2023 và 8/9 trên 2024; mặc định vẫn giữ nguyên 2 ATR và 3R. Dù vậy, bootstrap theo khối lợi nhuận ngày cho khoảng mô tả 5%–95% từ **−7,08% đến +42,63%** trên vốn spot trong khoảng ngoài mẫu. Lợi thế vẫn có bất định; không đủ căn cứ đặt mục tiêu thu nhập tháng.

## Setup spot nên tiếp tục theo dõi

- Danh sách đủ thanh khoản, có ít nhất 200 nến D1; turnover ngày trung vị 30 ngày ≥10 triệu USDT.
- D1 giá trên EMA50, EMA50 trên EMA200; BTC D1 trên EMA200.
- Với altcoin, hiệu suất 20 ngày cao hơn BTC; BTC không so sánh với chính nó.
- Nến H4 đóng vượt đỉnh 20 nến trước, trong khi nến H4 trước chưa vượt ngưỡng tương ứng; giá trên EMA20 H4.
- Vào ở mở H4 tiếp theo. Stop cách giá fill 2 ATR14 H4, target 3 lần khoảng stop, thoát thời gian sau 90 nến H4 nếu chưa chạm stop/target.
- Rủi ro tham chiếu 20 USD/lệnh trên vốn spot 3.000, có tính chi phí và trần vốn. Với paper trade, ghi đúng giá có thể khớp và lý do bỏ lệnh, không sửa quy tắc khi đang kiểm tra.

Không chọn lại coin hoặc thông số vì thấy chúng thắng trên phần ngoài mẫu. Đạt thêm 15 lệnh cũng không tự động chứng minh lợi thế: cần mẫu đủ đa dạng, chi phí thực phù hợp và tuân thủ quy tắc ổn định. Các coin ngoài nhóm 12 cặp cần đánh giá forward riêng.

## Dữ liệu và phạm vi

Dữ liệu từ Binance 2021–08/2026: 12 cặp cố định, 48 chuỗi spot H4, futures H1, mark H1 và funding; dữ liệu 2021 khởi tạo chỉ báo. Development 2022–2023, validation 2024, holdout 2025–08/2026. Có 36 cấu hình độ nhạy trên development/validation, các năm kiểm tra riêng, kiểm tra chi phí và equity danh mục.

**Đây không phải backtest toàn bộ top 200/top 100 lịch sử.** Nhóm 12 coin được chọn hôm nay có thiên lệch sống sót và không gồm các thất bại đã hủy niêm yết. Bộ lọc live quét rộng hơn được đánh dấu `EXPANDED_UNVALIDATED`. Market cap và narrative point-in-time chưa được kiểm thử.

Kho dữ liệu gốc có hash trong [manifest](data/manifest.json). 5 nến spot H4 rút ngắn năm 2021 trên mỗi cặp được giữ nguyên, ghi cảnh báo; khoảng giao dịch 2022 trở đi đủ nến tiêu chuẩn. Funding cũ thiếu markPrice tại sự kiện được định giá bằng mark OPEN H1 tương ứng, có ghi số lần xấp xỉ. Chưa mô phỏng chính xác khớp lệnh tick, risk tier thanh lý hoặc lịch sử thay đổi min notional. Chi tiết nằm trong báo cáo.

## Tái lập từ thư mục Trading

Môi trường dự án hiện có dùng `.venv/bin/python`. Nếu dựng môi trường mới, cài các thư viện trong `strategy_lab/requirements.txt` trước. Các lệnh sau chỉ đọc dữ liệu thị trường và ghi tệp nghiên cứu:

```sh
.venv/bin/python -m strategy_lab.data --start 2021-01-01 --end 2026-09-01
.venv/bin/python -m strategy_lab.data --verify
.venv/bin/python -m strategy_lab.run_research
.venv/bin/python -m strategy_lab.plot_report
.venv/bin/python -m unittest discover -s strategy_lab/tests -v
.venv/bin/python -m unittest strategy_lab.test_data -v
```

Tệp CSV giao dịch và equity đầy đủ nằm trong `reports`. Danh sách nguồn chính thức và các giả định khớp lệnh có trong báo cáo. Công cụ nằm riêng trong `strategy_lab`; không thay đổi hệ thống giao dịch, dashboard hoặc tiến trình cũ của bạn. Bộ lọc ngày hiện chạy theo yêu cầu, chưa có lịch nền và không đặt lệnh.
