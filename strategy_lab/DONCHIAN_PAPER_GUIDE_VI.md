# Bắt đầu dùng phiếu Donchian và bộ quản lý paper

Bạn dùng công cụ này để tập vận hành Donchian H4 trên dữ liệu Binance thật, với **tiền mô phỏng**. Không cần API key, không chuyển tiền, không có chức năng đặt lệnh trên sàn.

## 1. Mở công cụ

Trong thư mục **Trading**, mở `run_donchian_paper.command`. Công cụ hiện menu tiếng Việt. Sổ lần đầu mặc định $1.000, risk 0,25%/lệnh ($2,50 ban đầu), tối đa 3 vị thế, tổng risk ban đầu các vị thế không vượt 0,75% equity, margin ≤40%, đòn bẩy mô hình 3x.

Sổ riêng nằm tại `strategy_lab/paper_donchian`. Không dùng `paper_state.json`, `futures_paper.py`, `live_bridge.py` hoặc chế độ LIVE của bot cũ cho quy trình này. Chạy `init` lần thứ hai bị từ chối để tránh xóa lịch sử.

## 2. Cập nhật dữ liệu — chọn số 1

Công cụ đọc dữ liệu công khai của 12 hợp đồng USDT perpetual đã nghiên cứu: BTC, ETH, BNB, XRP, ADA, DOGE, LINK, LTC, BCH, DOT, UNI và SOL. Nó cập nhật vị thế cũ trước, rồi tạo phiếu từ nến H4 hoàn tất mới nhất.

Đọc dòng **“Đã cập nhật đến…”**. Đây là thời điểm kết thúc H1 gần nhất đã xử lý, không phải giá realtime. Nếu thiếu nến/funding/mark của vị thế đang giữ, chương trình dừng lần cập nhật và giữ nguyên sổ trước đó; không giả định funding bằng 0 hoặc bỏ qua stop. Nếu chỉ một coin chưa có vị thế bị lỗi, phần lỗi sẽ ghi tên coin đó.

Sau mỗi lần cập nhật, mở [PAPER_DESK_VI.md](paper_donchian/PAPER_DESK_VI.md) bằng Codex hoặc trình đọc Markdown để xem phiếu, vị thế và nhật ký. Chọn số 3 trong menu cũng xem được nội dung này.

**Không có phiếu là kết quả bình thường.** Không tạo lệnh chỉ để đủ chỉ tiêu. Một coin có ADX cao chưa có nghĩa đã phá Donchian và qua đủ bộ lọc ATR/funding.

## 3. Đọc và duyệt phiếu — chọn số 2

Chương trình làm mới dữ liệu trước khi hiển thị danh sách. Mỗi phiếu có:

| Mục | Bạn kiểm tra gì? |
|---|---|
| Coin và LONG/SHORT | Đúng hợp đồng Binance futures, đúng hướng |
| Giờ tín hiệu | Nến H4 đã đóng, phiếu chưa hết hạn |
| Close và ATR tín hiệu | Giá tham chiếu; ATR là SMA14 true range |
| ADX, ATR%, funding | Đúng bộ lọc Donchian; dữ liệu funding có thật |
| Entry/SL/TP dự kiến | SL 2 ATR, TP 7 ATR = 3,5R, làm tròn bước giá |
| Qty, notional và margin | Khối lượng làm tròn xuống, không ép tăng để đủ minimum |
| Risk dự kiến | Đã tính phí hai chiều và dự phòng trượt giá thoát; không gồm funding tương lai/gap vô hạn |

Nhập số phiếu. Gõ **PAPER** để duyệt, **BO** để bỏ, hoặc Enter để quay lại. Không có thao tác nào trong menu là chấp thuận lệnh tiền thật.

Sau khi duyệt, phiếu chuyển sang **QUEUED**. Bạn chưa có vị thế ngay lập tức. Nó được xếp vào **open H1 kế tiếp**, còn trước lần đóng H4 tiếp theo. Đến lúc xử lý nến đó, công cụ tính lại khối lượng, SL/TP, margin và risk theo open H1, equity hiện có và quy tắc bước giá/khối lượng mới đọc.

Nếu giá open lệch hơn **0,25 ATR** so với close tín hiệu, funding mới không còn phù hợp, hết chỗ giữ vị thế, thiếu ngân sách risk hoặc không đạt minimum order, phiếu chuyển **SKIPPED** và không trừ tiền vào lệnh. Không tăng risk để ép khớp.

## 4. Hiểu đúng thời điểm vào lệnh

Ví dụ giờ Việt Nam: H4 đóng **11:00**; bạn duyệt lúc **11:10** → dự kiến vào open **12:00**. Khi chạy cập nhật sau **13:00**, nến H1 12:00–13:00 đã hoàn tất; sổ mới phản ánh entry, funding và khả năng SL/TP trong giờ đó. Phê duyệt được ghi trước entry nên không có việc nhìn kết quả rồi chọn giá vào cũ.

Nếu duyệt lúc 13:10, giờ dự kiến là 14:00. Nếu đến 14:10 mới duyệt, H1 kế tiếp là 15:00, trùng lần đóng H4 mới: phiếu cũ bị từ chối, chờ tín hiệu mới. Phiếu đã qua giờ vào dự kiến không được hủy ngược thời gian; phải cập nhật sổ trước.

**Bản này dùng chung logic tín hiệu, tính rủi ro, xử lý stop và dời hòa vốn với engine nghiên cứu đã sửa, nhưng cách vào lệnh có duyệt là một phiên bản thực thi khác.** Nó còn thêm giới hạn giá lệch, kiểm lại funding lúc entry, bước lượng và giới hạn lỗ. Vì vậy lợi nhuận +39,31% của backtest cũ không phải kết quả của bộ paper này. Phải đánh giá nhật ký forward riêng.

## 5. Theo dõi vị thế — tiếp tục chọn số 1

Chạy cập nhật sau mỗi giờ nếu đang có vị thế. Công cụ tự thực hiện các việc sau trong sổ mô phỏng:

1. Đọc bù H1 chưa xử lý; không thu phí hoặc funding lại khi chạy hai lần.
2. Kiểm tra stop cũ và TP. Gap qua stop thoát tại open bất lợi; nếu cùng nến chạm cả SL/TP mà không rõ thứ tự thì ưu tiên stop.
3. Ghi funding theo sự kiện thực; event ngay đầu giờ chỉ áp vào vị thế đã giữ trước thời điểm đó. Funding trong giờ tính trước lần thoát được xấp xỉ ở cuối giờ.
4. Sau khi H4 hoàn tất, nếu vị thế còn tồn tại mới tính trailing **4 ATR ban đầu**. Với entry muộn, không dùng đỉnh/đáy xảy ra trước khi bắt đầu giữ vị thế.
5. Hòa vốn khi close đi thuận ít nhất **2 ATR ban đầu = 1R**; stop có hiệu lực từ giờ tiếp theo, không quay lại đóng ở giá không thể khớp của giờ cũ. Hòa vốn tại entry vẫn có thể lỗ phí/funding.

Vị thế được giữ qua các lần cập nhật và qua việc đóng/mở chương trình. Không tự đóng cuối ngày hoặc cuối lần chạy để làm đẹp số liệu. **Stop ở đây chỉ là mô phỏng H1; không có lệnh stop thật nằm trên Binance.** Chưa mô hình hóa order book, khớp một phần hoặc thanh lý chính xác.

## 6. Tạm dừng và giới hạn vốn

- Chọn **4**: tạm dừng nhận lệnh mới, hủy các phiếu đã xếp nhưng chưa đến giờ vào. Vị thế hiện có vẫn được quản lý SL/TP khi bạn cập nhật.
- Chọn **5**: bỏ tạm dừng do bạn đặt. Không xóa khóa do drawdown và không reset lịch sử.
- Lỗ ngày 1% hoặc tuần 3%: chặn entry mới cho kỳ đó. Ngày/tuần tính UTC, tương ứng ngày mới lúc 07:00 và tuần mới thứ Hai 07:00 giờ Việt Nam.
- DD 5% từ đỉnh equity: khóa entry để rà soát. Không mặc nhiên đóng toàn bộ ở một giá giả định; vị thế cũ tiếp tục SL/TP. Đổi thông số hoặc mở lại sau DD cần đánh giá và migration có chủ đích.

Các giới hạn tính theo equity ở các mốc H1, chưa kiểm soát biến động từng tick. Gap/trượt giá có thể vượt số USD dự kiến. Khoản risk được giữ theo rủi ro ban đầu của vị thế ngay cả khi đã dời BE, nhằm tránh giải phóng chỗ để tăng vị thế quá nhanh.

## 7. Lịch thao tác thực tế

H4 đóng lúc **03:00, 07:00, 11:00, 15:00, 19:00, 23:00 giờ Việt Nam**. Chọn những ca bạn có thể theo dõi; ghi nhận rằng việc bỏ ca làm thay đổi tập tín hiệu được giao dịch. Không cần thức dậy để tạo lệnh mới, nhưng mô hình manual sẽ khác mô hình chạy đủ mọi ca.

Sau H4 đóng: chọn 2 → xem phiếu → PAPER hoặc BO. Khi giữ vị thế: cập nhật sau mỗi giờ. Cuối ngày: chọn 3, kiểm tra equity, SL và các lệnh đóng. Công cụ chưa chạy theo lịch; đóng Terminal không làm sổ được cập nhật tự động. Có thể đọc bù khi mở lại, tối đa 990 giờ (~41 ngày); quá thời gian đó cần phục hồi lịch sử, không tự nhảy qua đoạn thiếu.

## 8. Các file bạn cần xem

| File trong `paper_donchian` | Nội dung |
|---|---|
| `PAPER_DESK_VI.md` | Phiếu và sổ bằng tiếng Việt |
| `tickets.csv` | Các phiếu READY/QUEUED và số dự kiến |
| `trades.csv` | Lệnh đã đóng: entry, exit, fees, funding, net PnL, R |
| `equity.csv` | Equity theo các H1 đã xử lý |
| `events.jsonl` | Tạo, duyệt, bỏ phiếu, entry, sửa stop, funding, exit |
| `state.json` | Sổ gốc; không sửa tay hoặc xóa để bỏ lệnh lỗ |
| `snapshots/*.json.gz` | Snapshot dữ liệu công khai dùng cho mỗi lần cập nhật |
| `last_error.json` | Lỗi thao tác/cập nhật gần nhất, nếu có |

Chỉ có một thao tác được ghi sổ tại một thời điểm. Sổ lưu bằng thay thế nguyên file; các báo cáo là bản xuất từ sổ. Mã thay đổi sau khi tạo sổ sẽ chặn tiếp tục giao dịch để tránh trộn phiên bản; vẫn có thể xem sổ.

## Lệnh tùy chọn nếu bạn muốn dùng Terminal

Chạy từ thư mục Trading:

```sh
.venv/bin/python -m strategy_lab.donchian_paper menu
.venv/bin/python -m strategy_lab.donchian_paper refresh
.venv/bin/python -m strategy_lab.donchian_paper status
```

Tạo sổ thử khác, giữ nguyên sổ chính:

```sh
.venv/bin/python -m strategy_lab.donchian_paper --book strategy_lab/paper_donchian_trial init --capital 1000 --risk 0.0025
```

Tham số `--risk 0.0025` nghĩa là 0,25%, không phải 0,0025%. Chương trình không đọc khóa Binance; không có lệnh bật LIVE.

Nguồn quy tắc bước giá/khối lượng: [Binance USD-M common definitions](https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/common-definition). Dữ liệu nến/funding/mark dùng [Binance USD-M market data](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data).
