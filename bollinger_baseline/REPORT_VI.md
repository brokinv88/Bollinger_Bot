# Backtest đối chứng Bollinger Envelopes v0

Rà soát Python; CHƯA đối chiếu giao dịch với TradingView. 48 backtest độc lập, mỗi chart vốn 10.000, mỗi entry cash 50, max 3 entry, phí 0,075% mỗi chiều. Không cộng thành danh mục vốn 5.000.

Nguồn 12 coin sống sót cố định, 2021–08/2026; không phải top 100 thanh khoản lịch sử. Chạy từ đầu dữ liệu, indicator warmup tự nhiên 200 nến. Không tối ưu tham số, không gọi khoảng này là holdout độc lập.

Không stop, target, funding, slippage, đòn bẩy/margin/thanh lý, làm tròn lot hay giới hạn Binance. Futures là tín hiệu trên giá futures theo kế toán nguyên bản, không phải mô phỏng futures thực tế. Cuối mẫu giữ vị thế mở và đánh giá theo close; lệnh chờ cuối mẫu không khớp giả.

Profit factor và win rate tính theo từng entry đã đóng (các lớp cùng vị thế không độc lập). DD tính theo đường OHLC giả định có lãi/lỗ đang mở, không khẳng định bằng số DD TradingView. Cash sizing dùng giá fill; cần xác nhận bằng export TradingView cùng Properties/symbol/khoảng dữ liệu. Không báo R vì không có stop/rủi ro ban đầu.

| Nhóm | Coin | Lớp đóng | P&L equity USD | PF lớp đóng | DD % | Lớp mở |
|---|---|---:|---:|---:|---:|---:|
| spot 4h | ADAUSDT | 138 | 228.49 | 2.11 | 1.157 | 0 |
| spot 4h | BCHUSDT | 166 | -73.44 | 0.72 | 1.753 | 0 |
| spot 4h | BNBUSDT | 192 | 43.71 | 1.24 | 0.672 | 0 |
| spot 4h | BTCUSDT | 174 | 77.60 | 1.56 | 0.351 | 0 |
| spot 4h | DOGEUSDT | 151 | 160.67 | 1.57 | 1.041 | 0 |
| spot 4h | DOTUSDT | 122 | 90.94 | 1.52 | 0.813 | 0 |
| spot 4h | ETHUSDT | 160 | 133.34 | 1.77 | 0.546 | 0 |
| spot 4h | LINKUSDT | 179 | 36.72 | 1.12 | 0.921 | 0 |
| spot 4h | LTCUSDT | 177 | -147.79 | 0.50 | 1.702 | 0 |
| spot 4h | SOLUSDT | 167 | 263.00 | 1.98 | 1.365 | 0 |
| spot 4h | UNIUSDT | 158 | 8.98 | 0.89 | 1.071 | 3 |
| spot 4h | XRPUSDT | 148 | 414.06 | 2.74 | 1.900 | 0 |
| spot 24h | ADAUSDT | 19 | 83.86 | 2.49 | 1.395 | 0 |
| spot 24h | BCHUSDT | 28 | 64.62 | 1.62 | 1.689 | 0 |
| spot 24h | BNBUSDT | 18 | 191.26 | 5.26 | 1.002 | 1 |
| spot 24h | BTCUSDT | 25 | 97.23 | 4.16 | 0.463 | 1 |
| spot 24h | DOGEUSDT | 19 | 88.18 | 2.02 | 1.184 | 0 |
| spot 24h | DOTUSDT | 13 | 44.58 | 2.76 | 0.857 | 0 |
| spot 24h | ETHUSDT | 19 | 26.31 | 1.64 | 0.682 | 1 |
| spot 24h | LINKUSDT | 22 | 79.60 | 1.72 | 0.946 | 1 |
| spot 24h | LTCUSDT | 24 | -11.19 | 0.85 | 1.005 | 0 |
| spot 24h | SOLUSDT | 27 | 248.79 | 3.86 | 2.021 | 2 |
| spot 24h | UNIUSDT | 23 | 44.22 | 1.37 | 1.277 | 3 |
| spot 24h | XRPUSDT | 23 | 180.49 | 3.41 | 1.507 | 0 |
| futures 1h | ADAUSDT | 744 | 216.61 | 1.36 | 0.995 | 0 |
| futures 1h | BCHUSDT | 798 | -44.24 | 0.93 | 1.708 | 0 |
| futures 1h | BNBUSDT | 914 | 245.05 | 1.46 | 1.010 | 0 |
| futures 1h | BTCUSDT | 856 | 16.37 | 1.04 | 0.713 | 0 |
| futures 1h | DOGEUSDT | 738 | 906.34 | 2.52 | 5.305 | 0 |
| futures 1h | DOTUSDT | 797 | 53.51 | 1.08 | 1.516 | 0 |
| futures 1h | ETHUSDT | 854 | 59.88 | 1.11 | 0.864 | 0 |
| futures 1h | LINKUSDT | 850 | 14.42 | 1.02 | 1.761 | 0 |
| futures 1h | LTCUSDT | 873 | -120.63 | 0.81 | 1.641 | 0 |
| futures 1h | SOLUSDT | 869 | 197.04 | 1.24 | 1.268 | 0 |
| futures 1h | UNIUSDT | 884 | -39.11 | 0.95 | 2.705 | 3 |
| futures 1h | XRPUSDT | 722 | 475.19 | 1.87 | 1.614 | 0 |
| futures 4h | ADAUSDT | 175 | 231.54 | 1.73 | 1.455 | 0 |
| futures 4h | BCHUSDT | 197 | 11.22 | 1.04 | 1.919 | 0 |
| futures 4h | BNBUSDT | 221 | 397.77 | 2.89 | 2.964 | 0 |
| futures 4h | BTCUSDT | 198 | 191.07 | 2.14 | 0.627 | 0 |
| futures 4h | DOGEUSDT | 172 | 705.08 | 3.07 | 4.935 | 0 |
| futures 4h | DOTUSDT | 153 | 200.32 | 1.85 | 1.288 | 0 |
| futures 4h | ETHUSDT | 194 | 232.59 | 2.06 | 0.518 | 0 |
| futures 4h | LINKUSDT | 218 | 13.22 | 1.03 | 1.372 | 0 |
| futures 4h | LTCUSDT | 212 | -77.72 | 0.78 | 2.016 | 0 |
| futures 4h | SOLUSDT | 208 | 687.26 | 2.89 | 1.350 | 0 |
| futures 4h | UNIUSDT | 193 | -10.09 | 0.87 | 1.591 | 3 |
| futures 4h | XRPUSDT | 173 | 650.96 | 3.15 | 1.863 | 0 |

DD thấp phải được đọc cùng mức vốn triển khai chỉ khoảng 150 USD/chart; không suy ra an toàn khi tăng size.

Đối chiếu: chọn đúng Binance symbol spot/perpetual, nến thường, cùng ngày bắt đầu dữ liệu và Inputs/Properties gốc; so Upper/Lower, signal, entry/exit time, qty, phí từng lớp. Lưu sai lệch trước khi dùng kết quả để chọn hệ thống.

Tệp *_signals.csv, *_trades.csv, *_equity.csv cho từng chart; summary.csv tổng hợp; manifest.json giữ hash nguồn.