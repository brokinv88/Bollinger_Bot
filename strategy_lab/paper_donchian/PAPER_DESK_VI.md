# Donchian H4 — phiếu lệnh và sổ PAPER

**CHỈ MÔ PHỎNG. Không có kết nối đặt lệnh hoặc API key.**

Trạng thái: đã xuất từ sổ paper; xem mốc dữ liệu bên dưới.
Vốn đầu: $1000.00 · Equity tại nến H1 đã xử lý: **$1000.00** · Tiền mặt: $1000.00
Dữ liệu sổ đến: **07/09/2026 12:00:00 giờ Việt Nam**. Đây không phải equity realtime.
Risk/lệnh 0.25% · Tổng risk ≤0.75% · Tối đa 3 vị thế · Đòn bẩy mô hình 3x.
Chặn vào mới: Không có tại lúc xuất báo cáo.

Duyệt phiếu sẽ xếp mô phỏng vào OPEN H1 kế tiếp, nằm trước lần đóng H4 tiếp theo. Giá lệch quá 0.25 ATR so với close tín hiệu sẽ bỏ lệnh. Đây là phiên bản vào trễ cần kiểm chứng riêng, không mang kết quả backtest next-open H4 sang đây.

## Phiếu đang chờ

| Coin / hướng | Trạng thái | Close tín hiệu | SL / TP dự kiến | Qty / Notional | Risk / Margin ($) | H1 dự kiến |
|---|---|---|---|---|---|---|
| — | Không có phiếu chờ | — | — | — | — | — |


## Vị thế paper

| Coin | Hướng | Entry | Qty | SL hiện tại | TP | Funding đã trả ($) |
|---|---|---|---|---|---|---|
| — | Chưa có vị thế | — | — | — | — | — |

## Nhật ký

Đã đóng 0 lệnh; net PnL đã đóng $+0.0000. Đối soát tiền: sai lệch $0.0000000000.
Xem trades.csv, equity.csv và events.jsonl trong cùng thư mục. Bỏ phiếu cũng có nhật ký. Không dùng số liệu này như lịch sử lệnh trên Binance.

## Bộ lọc mới nhất

| Coin | Hướng tín hiệu | ADX | ATR% |
|---|---|---|---|
| ADAUSDT | Không có | 25.19 | 2.177 |
| BCHUSDT | Không có | 14.26 | 2.263 |
| BNBUSDT | Không có | 35.14 | 1.561 |
| BTCUSDT | Không có | 13.45 | 0.570 |
| DOGEUSDT | Không có | 31.30 | 2.388 |
| DOTUSDT | Không có | 39.18 | 3.020 |
| ETHUSDT | Không có | 16.30 | 0.986 |
| LINKUSDT | Không có | 34.19 | 2.256 |
| LTCUSDT | Không có | 33.13 | 2.481 |
| SOLUSDT | Không có | 24.87 | 1.568 |
| UNIUSDT | Không có | 51.53 | 4.521 |
| XRPUSDT | Không có | 12.33 | 1.239 |

## Dữ liệu thiếu/lỗi

Không có lỗi ở lần quét thành công gần nhất.

## Cách vận hành

Mở run_donchian_paper.command → 1 để cập nhật → 2 để xem/duyệt phiếu → 1 sau mỗi giờ để cập nhật vị thế. Không tự chạy khi ứng dụng đóng; lần sau sẽ đọc bù các H1 đã đóng. Stop/TP là mô phỏng H1, không phải stop thật tại sàn.
Dừng ngày/tuần dùng UTC, tính cả lãi/lỗ chưa thực hiện theo close H1. DD 5% khóa mở mới để rà soát; vị thế hiện tại vẫn được mô phỏng SL/TP. Chưa mô hình thanh lý chính xác, không tự đóng toàn bộ để giả định tránh thanh lý.
Phí giả định 0,05% mỗi chiều và trượt 0,03% mỗi chiều; funding thực từng sự kiện. Không cam kết khớp giá hoặc thời điểm giống tiền thật.
