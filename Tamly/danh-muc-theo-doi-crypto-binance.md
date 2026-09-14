# Danh mục theo dõi crypto Binance — bối cảnh ngày 07/09/2026

Ngày tạo: 07/09/2026. Đây là **danh mục quan sát**, không phải tín lệnh mua/bán. Mỗi dòng chỉ là ứng viên cho **chiến lược thí nghiệm C1/C2** (xem `spec-C1-C2.md`). Khi giá chạm điều kiện, tín hiệu phải được xác nhận lại bằng quy tắc trước entry; chưa có lệnh nào được đề xuất ở mức độ này.

Dữ liệu: Binance USD-M futures, khung H4, giá thời điểm scan (đầu giờ 07/09/2026).

---

## 1. Bối cảnh chung

- **BTC/USDT ~ $79.100** — trend H4 UP (EMA50 > EMA200), đang gần swing low (khoảng cách −0,03%), cách swing high −1,78%. Giá đang ở vùng có thể quét thanh khoản quanh swing low.
- Đa số top-20 volume đang uptrend H4; một số cặp chưa có tín hiệu rõ (SOL, HYPE, SUI trend mâu thuẫn).
- Cảnh báo 24h: cặp rác/pump mới (DOOD +47%, BULLA +25%, MARSCOIN −26%, HEMI −27%) — không nằm trong vũ trụ C1/C2 vì thanh khoản và thời gian niêm yết không đạt.

## 2. Ứng viên C1 — phá vỡ cấu trúc thuận xu hướng (quan sát, chưa vào)

Điều kiện C1: trend H4 rõ (UP hoặc DOWN) và giá trong vòng ~1% của swing để chờ break. Chi tiết thuật toán: `strategies.gen_c1`.

| Cặp | Giá | Trend H4 | Cách swing đến (ngắn) | Ghi chú quan sát |
|---|---|---|---|---|
| BTC/USDT | ~79.100 | UP | cách swing low −0,03% | Chờ phá swing high hoặc xác nhận xuống breakthrough; không vào sớm |
| ETH/USDT | ~2.479 | UP | cách swing high −1,76% | Gần swing low hơn (+0,82%) — quan sát hướng breakout |
| XRP/USDT | ~1,39 | UP | gần swing low −0,22% | Vùng quét tiềm năng; chờ xác nhận |
| BNB/USDT | ~742 | UP | gần swing low +0,17% | Tương tự BTC, phá swing high ~5% mới hợp lệ |
| XAU/USDT | ~4.522 | DOWN | gần swing low −0,00% | Trend DOWN — quan sát theo hướng short của C1 |
| SNDK/USDT | ~1.787 | UP | cách swing high −0,57% | Ứng viên phá high ngắn hạn, thanh khoản trung bình |
| CL/USDT | ~91,8 | UP | cách swing high −0,48% | Ứng viên phá high, ATR thấp (0,77%) — dễ chạy hơn |

## 3. Ứng viên C2 — vùng cũ (chỉ quan sát, C2 đã bác bỏ để vào lệnh)

> **Cập nhật vòng 2 (07/09/2026):** bộ lọc sweep của C2 đã bị bác bỏ trên cả 2 định nghĩa (H4 và H1-vs-H4), đều âm ngoài mẫu. Với nhóm nền kỳ vọng chỉ +0,06R (test +0,14R), kết luận là **không dùng họ C2 để vào lệnh** — các mức dưới đây chỉ là mức quan sát cho C1 (chạm/swing).

| Cặp | Giá | Mức quan sát | Hướng |
|---|---|---|---|
| BTC/USDT | ~79.100 | swing low ~79.100 (đang chạm) | Theo dõi cho C1: chờ BOS hướng tăng xác nhận xu hướng, không vào theo "quét xong đóng lại" |
| XRP/USDT | ~1,39 | swing low ~1,39 | Theo dõi C1 long nếu BOS thuận xu hướng |
| XAU/USDT | ~4.522 | swing low ~4.522 | Theo dõi C1 short nếu BOS giảm xác nhận |
| BNB/USDT | ~742 | swing low ~742 | Theo dõi C1, chờ xác nhận |
| CL/USDT | ~91,8 | quanh swing high/low | Quan sát 2 chiều |

## 4. Nguyên tắc khi dùng danh mục này

- Danh sách sinh ra từ **điều kiện quan sát tự động** (`scan_market.py`), chưa phải tín hiệu entry — cần xác nhận theo hệ thống trước khi vào (C02).
- **C2 đã bị bác bỏ sau 2 vòng (H4 và H1/H4), kỳ vọng âm mọi cặp cả train lẫn test — không dùng C2 hay nhóm nền C2 để vào lệnh.** Chỉ còn C1 là ứng viên.
- C1 có kỳ vọng dương ở backtest (kể cả ngoài mẫu) nhưng chưa qua forward test; nếu muốn theo dõi, chỉ quan sát + ghi nhật ký, chưa đặt lệnh thật.
- Cập nhật lại mỗi phiên bằng lệnh chạy scanner; không tự coi danh sách này là "gợi ý mua hôm nay".

Dữ liệu chi tiết: `C1_C2_strategies/reports/watchlist_market_context_gainers_losers.csv`, `watchlist_strategy_state.csv`, `watchlist_top_volume.csv`.