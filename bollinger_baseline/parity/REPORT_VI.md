# Đối chiếu mẫu TradingView — BTCUSDT spot H4

Ngày 09/09/2026. Nguồn: bảng List of Trades hiển thị trực tiếp trên TradingView, BINANCE:BTCUSDT, Candles, H4, UTC, chiến lược Bollinger Envelopes baseline parity. Người dùng đã đăng nhập và chạy script. Script giữ logic giao dịch/default gốc, chỉ bỏ bảng và một số đường vẽ. Report UI: Jan 1 2024–Sep 8 2026, 102 lệnh, P&L31.69 USDT, PF1.446. Không đối chiếu các tổng này vì khác khoảng dữ liệu/start state.

## Kết quả

7/7 lớp entry #95–101 (10/07–28/08/2026) khớp thời gian entry/exit và giá khớp chính xác với Python. Đây là 5 vị thế/chu kỳ đóng, gồm hai nhóm pyramid (2 và 3 entry). Không phải 7 quan sát chiến lược độc lập. Lệnh #102 ngoài dữ liệu local kết thúc tháng 8 nên không đưa vào mẫu.

Python gốc dùng qty=50/giá fill, không làm tròn. Quantity TradingView hiển thị trong mẫu khớp floor(50/giá fill / 0.00001)*0.00001. Đây là quy tắc suy ra từ mẫu BTCUSDT, chưa phải xác nhận mincontract cho mọi symbol. Thêm tham số tùy chọn qty_step vào simulate, dùng 0.00001 riêng cho lượt đối chiếu; mặc định cũ giữ nguyên, chưa chạy đè 48 kết quả cũ.

Sau làm tròn: 7/7 quantity khớp; 7/7 P&L ròng khớp tới cent hiển thị (sai số <=0.005 USDT). Phí tính 0.075% trên notional thực khớp mỗi chiều. Không đọc được phí riêng từ bảng mẫu nên đây là xác nhận P&L phù hợp công thức phí, không phải đối chiếu trường commission độc lập.

Ví dụ #100: giá mua68554, bán77580.03; Python cũ P&L6.503216, TradingView6.42; qty0.00072 cho P&L6.419829, hiển thị6.42.

## Giới hạn cần giữ

Nút Download.csv bị chặn bởi gói Basic, yêu cầu Essential. Không tải được export; tv_visible_sample.csv là bản chép các dòng đang hiển thị, KHÔNG phải file xuất chính thức. Không thực hiện thu thập hàng loạt để thay thế tính năng trả phí.

Mới xác nhận mẫu khớp lệnh, chưa xác nhận toàn bộ signal/indicator, warmup, giao dịch thiếu/thừa ngoài mẫu, equity/drawdown hay toàn bộ report. Qty step là giả thuyết đã khớp mẫu, cần xác nhận thông số symbol. Các kết quả 48 chart cũ vẫn có giả định fractional quantity và chưa được chứng nhận parity.

## Tái lập

Chạy tại Trading:

```sh
.venv/bin/python -m bollinger_baseline.parity.compare
.venv/bin/python -m unittest bollinger_baseline.test_baseline -v
```

comparison.csv chứa dữ liệu hai phía và các cờ khớp. tv_visible_sample.csv giữ nguyên số hiển thị, thời gian UTC.

Cổng mở rộng top100: CHƯA hoàn tất đối chiếu export toàn chart. Cần bản export chính thức cùng cấu hình/nguồn dữ liệu hoặc quyền xuất của tài khoản hiện tại. Không cần gửi mật khẩu; không có hành động nâng cấp gói hay thanh toán nào được thực hiện.

## Phương án không phụ thuộc CSV — kiểm chứng hai cách tính

Đã bổ sung independent_check.py: tự tính SMA/stdev bằng cửa sổ NumPy từ OHLC, tự xác định crossover/crossunder; ghép entry theo từng khoảng giữa exit và chọn tối đa ba lớp. Dòng tiền và equity được dựng bằng mảng cộng dồn, không dùng vòng xử lý lệnh của simulate để tạo kết quả tham chiếu.

Kết quả: 10.786 nến, 208 tín hiệu entry, 937 tín hiệu exit; 174 lớp đã đóng khớp thời gian/quantity/P&L. Toàn bộ equity tại close khớp, sai lệch tối đa khoảng 1,82e-11 USDT. Kết quả PASS_INTERNAL_ONLY trong independent_result.json. Chạy lại: `.venv/bin/python -m bollinger_baseline.parity.independent_check`.

Đây là bằng chứng bổ sung về tính nhất quán của bộ mô phỏng, kết hợp với 7 lệnh TradingView quan sát trước đó. Không đổi trạng thái thành đã đối chiếu toàn chart TradingView; không kiểm chứng độc lập feed, intrabar drawdown hoặc quy ước quantity các coin khác. Có thể tiếp tục chuẩn bị nghiên cứu top100 với nhãn giới hạn này, nhưng không dùng kết quả làm chứng nhận triển khai tiền thật.
