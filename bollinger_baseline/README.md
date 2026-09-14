# Bollinger Envelopes — baseline nguyên gốc

Chạy từ thư mục Trading:

```sh
.venv/bin/python -m unittest bollinger_baseline.test_baseline -v
.venv/bin/python -m bollinger_baseline.run
```

Đọc REPORT_VI.md và results/summary.csv. Bản Pine gốc nằm ở ../Tamly/bollinger-envelopes-original-v0.pine.

Phạm vi: mặc định script, Long-only, vốn 10000, cash50 mỗi entry, pyramiding3, commission0.075% mỗi chiều. Không tự sửa thành vốn5000, thêm stop hay risk sizing. Cash order chia giá fill, fractional quantity, không làm tròn lot; chưa chứng nhận parity TradingView. Mỗi chart có ledger độc lập; không phải danh mục top100 hoặc 5000 USD.

Dữ liệu: 12 coin có sẵn. Nguồn được kiểm tra finite/OHLC/trùng/gap. Với nguồn có nến rút ngắn, cắt toàn bộ prefix đến hết nến bất thường cuối; chỉ resample bucket UTC đầy đủ. Ngày thực dùng nằm trong summary, số dòng loại nằm trong manifest. Cắt prefix thay đổi điểm warmup so với chart có toàn lịch sử; cần khớp ngày nguồn khi đối chiếu TradingView.

Futures giữ giả định Pine không funding/slippage/thanh lý để tách đối chứng nguyên bản; không dùng làm dự báo kết quả tài khoản futures. Các lớp pyramid có tương quan; win rate/PF theo lớp không phải số mẫu độc lập. Equity cuối bao gồm vị thế mở, không ép đóng cuối mẫu. Không có R vì thiếu rủi ro ban đầu.

Bước xác nhận tiếp: export TradingView cùng symbol, chart OHLC thường, khoảng dữ liệu và Properties; so thời gian signal/fill, indicator, quantity, fee và P&L từng lớp. Sau đó mới mở rộng dữ liệu point-in-time top100 và portfolio vốn5000 theo một đặc tả riêng. Không gọi dữ liệu cũ từng nghiên cứu là holdout mới.
