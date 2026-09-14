# Bộ nghiên cứu chiến lược có sẵn

Điểm bắt đầu: [báo cáo đánh giá](reports/existing_strategies/REPORT_VI.md), [biểu đồ](reports/existing_strategies/comparison.png), [danh mục mới quét](reports/existing_strategies/daily_latest/SCAN_VI.md).

Đây là nhánh nghiên cứu BASE/B D1 và Donchian55/Keltner H4. Không nhầm với báo cáo `reports/REPORT_VI.md` của hai setup nghiên cứu trước. Các module mới không import bot vận hành, không cần API key, không đặt lệnh hoặc gửi Telegram.

## Theo dõi hằng ngày

Từ thư mục Trading, chạy `run_existing_daily.command`, hoặc:

```sh
.venv/bin/python -m strategy_lab.scan_existing --limit 100
```

Mỗi lần quét lấy top100 thanh khoản hiện tại riêng spot và futures, xuất 800 dòng tương ứng 8 profile. File trong `reports/existing_strategies/daily_latest` được thay bằng lần quét mới; nếu muốn giữ snapshot dùng `--output-dir` trỏ một thư mục mới. Không tự đặt lịch. Internet phải truy cập được các endpoint công khai Binance.

- `SCAN_VI.md`: ứng viên, trạng thái và lỗi.
- `scan.csv` / `scan.json`: toàn bộ điều kiện, ATR, hướng, funding đã biết và giờ vào theo mô hình UTC.
- `tradingview_PROFILE.txt`: watchlist tương ứng, gồm WATCH và tín hiệu mới/đã quá giờ; danh sách theo dõi không đồng nghĩa danh sách nên vào lệnh.

SETUP chỉ qua bộ lọc entry; kiểm tra riêng vị thế đang giữ, stop, lãi đủ 1R trước khi nhồi B_SAFE/B_REGIME, số lớp, tiền và margin còn lại. WATCH chỉ đủ một phần điều kiện nền. EXPIRED_SIGNAL đã quá 60 giây kể từ open mô hình; không dùng giá hiện tại để giả vờ đã vào tại open. INSUFFICIENT_HISTORY là thiếu lịch sử, không có tín hiệu đánh giá được. DATA_ERROR là dữ liệu lỗi, không suy diễn thành không có cơ hội.

Nến Binance D1 đóng 07:00 giờ Việt Nam. H4 đóng tại 03:00, 07:00, 11:00, 15:00, 19:00, 23:00. Quét sau nến đóng và dùng alert biểu đồ để nhận biết thời điểm; quét toàn bộ universe có thể mất vài phút nên tín hiệu được đánh dấu quá giờ. Muốn nhận tín hiệu sát open phải xây bộ theo dõi liên tục và kiểm chứng độ trễ; công cụ hiện tại là danh mục nghiên cứu hằng ngày.

Top100 hôm nay khác cohort 12 coin backtest. Top200 vốn hóa và narrative chưa được tự động hóa vì chưa có nguồn point-in-time phù hợp. Coin mới/DEX không đáp ứng warmup không được coi là đã kiểm chứng bằng các setup này.

## TradingView

1. Mở biểu đồ nến thường Binance spot **1D**, vào Pine Editor, dán [spot_base_b_monitor.pine](tradingview/existing_strategies/spot_base_b_monitor.pine), chọn BASE/B/B_SAFE/B_REGIME.
2. Với futures, dùng Binance USD-M perpetual **4H** (ticker `.P`), dán [futures_don_kelt_monitor.pine](tradingview/existing_strategies/futures_don_kelt_monitor.pine), chọn DON55/KELTNER hoặc bản TREND.
3. Sau khi script biên dịch và thêm vào biểu đồ, tạo alert điều kiện tương ứng, tần suất “Once Per Bar Close”. Alert chỉ báo bộ lọc, không kết nối webhook đặt lệnh. Đổi profile cần tạo lại alert để dùng cấu hình mới.
4. Futures alert luôn ghi **funding chưa kiểm tra**. Xác nhận funding và giới hạn vị thế bằng scanner/sổ paper trước khi quyết định. B_SAFE/B_REGIME trên Pine chỉ hiển thị bộ lọc entry và stop tham chiếu; quy tắc nhồi và stop của vị thế nằm trong engine Python.

Pine v6 mới đã được rà soát mã nhưng **chưa được TradingView compiler xác nhận** vì Pine Editor yêu cầu đăng nhập. Do đó chưa xác nhận tín hiệu trên nền tảng khớp từng dòng với Python. Các script là indicator theo dõi, không phải strategy đa coin. EMA/ADX có thể lệch nhỏ do độ dài lịch sử khởi tạo của biểu đồ. Không dùng Heikin Ashi/Renko cho đối chiếu giá khớp.

## Tái chạy nghiên cứu

```sh
.venv/bin/python -m strategy_lab.data --verify
.venv/bin/python -m strategy_lab.run_existing_research
.venv/bin/python -m strategy_lab.scan_existing --limit 100
.venv/bin/python -m strategy_lab.render_existing_report
.venv/bin/python -m unittest discover -s strategy_lab/tests
```

Lệnh nghiên cứu chỉ đọc cache đã kiểm chứng và xuất báo cáo riêng, có thể mất nhiều phút. Không cần tải lại 48 file khi hash còn đúng. Dữ liệu ending 31/08/2026; quét live hiện tại không kéo dài backtest tự động.

- [EXISTING_SPEC.md](EXISTING_SPEC.md): quy tắc cố định trước lượt chạy.
- [existing_signals.py](existing_signals.py): định nghĩa tín hiệu đúng chỉ báo của mã gốc.
- [existing_engine.py](existing_engine.py): sổ vốn, khớp open/stop, funding và thứ tự cập nhật stop.
- [results.json](reports/existing_strategies/results.json): tham số, kết quả, cờ audit, bootstrap và hash nguồn.
- `trades_*`, `equity_*`, `fills_*`: giao dịch, equity và chi tiết thực thi; `comparison.csv`, `yearly.csv`, `by_symbol_direction.csv` để kiểm tra lại.
- `recommended_account.json`: ghép B_SAFE + DON55 sau khi đánh giá, chỉ mang tính mô tả.

Backtest đã kiểm chứng thứ tự dữ liệu và hạch toán nhưng còn giới hạn universe sống sót, chưa có mô hình tick/thanh lý chính xác, chưa áp dụng dừng ngày/tuần và chưa có forward sample. “PAPER_CANDIDATE” chỉ là qua tiêu chí nghiên cứu để tiếp tục mô phỏng.
