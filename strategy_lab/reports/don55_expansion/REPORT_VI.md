# Sàng lọc mở rộng danh mục DON55 H4

Ngày chốt dữ liệu: 01/09/2026 (UTC, không gồm ngày này).

## Kết luận sử dụng

Thêm **SUIUSDT** và **WLDUSDT** vào phễu Phase 1 dưới nhãn **mở rộng đang kiểm chứng forward**. Giữ nguyên rủi ro 0,25% vốn mỗi lệnh, tổng rủi ro mở tối đa 0,75% và tối đa ba vị thế. Không thêm ARB hoặc các ứng viên còn lại.

## Cách kiểm tra

- Engine: DON55 đã sửa, cùng logic tín hiệu và quản lý lệnh của hệ thống hiện tại.
- Dữ liệu: Binance USD-M Futures H1, mark-price H1 và funding thực tế.
- Danh sách ứng viên được cố định trước khi chạy: ZEC, SUI, 1000PEPE, WLD, NEAR, AAVE, AVAX, FIL, XLM, ARB, INJ và APT.
- Giai đoạn xác nhận: 01/01/2024–01/01/2025.
- Giai đoạn kiểm tra sau: 01/01/2025–01/09/2026.
- Stress test: gấp đôi phí và trượt giá.
- Điều kiện đạt: có lãi trong năm xác nhận, có lãi ở cả 2025 và phần 2026, tổng giai đoạn sau có lãi, PF tối thiểu 1,15, tối thiểu 20 lệnh, DD không quá 12%, stress test vẫn có lãi và không có cờ rủi ro thanh lý.
- Lợi nhuận từng năm được đo trên một đường vốn liên tục; vị thế mở qua ngày 1/1 không bị đóng giả tạo.

## Hai coin đạt điều kiện

| Coin | 2024 | 2025 | 01–08/2026 | PF giai đoạn sau | Số lệnh | DD tối đa | Stress |
|---|---:|---:|---:|---:|---:|---:|---:|
| SUIUSDT | +3,62% | +6,79% | +3,20% | 2,27 | 27 | 3,61% | +9,49% |
| WLDUSDT | +4,36% | +2,68% | +0,49% | 1,19 | 42 | 4,63% | +1,82% |

WLD có biên an toàn thấp hơn SUI vì PF chỉ nhỉnh hơn ngưỡng và lợi nhuận 2026 nhỏ. Vì vậy cả hai được đưa vào forward test, trong đó WLD cần được xem là ứng viên yếu hơn.

## Ảnh hưởng lên danh mục chung

Các số dưới đây dùng đúng ngân sách Phase 1: vốn 1.000 USD, rủi ro 0,25% mỗi lệnh và tối đa ba vị thế.

| Danh mục | Giai đoạn | Lợi nhuận | PF | DD tối đa | Số lệnh |
|---|---|---:|---:|---:|---:|
| 12 coin nền | 2024 | +6,43% | 1,32 | 6,77% | 162 |
| 14 coin | 2024 | +6,44% | 1,29 | 5,85% | 172 |
| 12 coin nền | 2025–08/2026 | +12,43% | 1,38 | 4,72% | 245 |
| 14 coin | 2025–08/2026 | +18,23% | 1,58 | 4,40% | 251 |
| 12 coin nền | Stress 2025–08/2026 | +9,35% | 1,29 | 5,47% | 244 |
| 14 coin | Stress 2025–08/2026 | +15,42% | 1,49 | 4,59% | 251 |

Kiểm toán mô phỏng không ghi nhận bar mơ hồ, dữ liệu funding thay thế, lỗi nhìn trước hay cờ rủi ro thanh lý trong các lượt danh mục.

## Các coin chưa thêm

- XLM, INJ, AVAX và 1000PEPE: thất bại ở giai đoạn xác nhận 2024.
- ARB và ZEC: âm trong năm 2025.
- APT: PF dưới ngưỡng, âm trong phần 2026 và stress test âm.
- NEAR, AAVE và FIL: không đạt nhiều tiêu chí; FIL có DD 14,11% ở mức rủi ro kiểm tra.

Đây là sàng lọc lịch sử có chi phí và funding, chưa phải bằng chứng về lợi nhuận tương lai. Giai đoạn 2025–08/2026 đã được dùng để chọn coin nên không còn là mẫu độc lập. Quyết định hợp lý là nhận cảnh báo và ghi riêng kết quả forward của SUI/WLD trước khi coi chúng ngang hàng với nhóm nền.
