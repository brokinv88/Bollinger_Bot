# Kiến trúc bộ công cụ trading — Hermes + ChatGPT + Claude + backtest nội bộ

Ngày soạn: 07/09/2026.  
Đây là bản thiết kế vận hành bộ công cụ cá nhân, **thống nhất với toàn bộ rules.md** và dùng chung nền tảng dữ liệu với backtest C1/C2 (`/Users/brokinv/Desktop/AI Agent/Trading/C1_C2_strategies/`). Nguyên tắc bao trùm: **nghiên cứu (chỉ đọc) tách tuyệt đối khỏi thực thi (đặt lệnh)** — đúng A03/A04/H07.

> Tài liệu này đang ở mức thiết kế khuyến nghị. Trước khi kích hoạt bất kỳ tầng tự động nào, chạy lại đúng trình tự giai đoạn ở mục 6 và cập nhật quyền của agent trong rules.md mục 11.

---

## 1. Mục tiêu và triết lý

- **Mục tiêu:** một pipeline nghiên cứu + theo dõi kỷ luật, trong đó AI (phản biện, đối chiếu, tự động hoá backtest) giúp bạn có **mẫu dữ liệu lớn hơn và nhiều luồng kiểm tra hơn**, chứ không tự tăng quyền đặt lệnh.
- **Điều tuyệt đối không cho phép:** agent tự đặt lệnh, tự sửa giới hạn rủi ro, tự thay baseline, tự backtest ra kết quả đẹp rồi kết luận lợi thế (A02, A06, H07).
- **Đo AI bằng gì:** độ chính xác đối chiếu số liệu, thời gian review tiết kiệm, số giả thuyết được kiểm chứng — không phải lợi nhuận mà dashboard hiển thị.

## 2. Bốn thành phần và vai trò

| Thành phần | Công cụ chính | Vai trò bổ sung |
|---|---|---|
| **Lớp dữ liệu & nghiên cứu** | Python + ccxt (đã có: `C1_C2_strategies/data.py`) | Fetch OHLCV Binance, cache, tạo dataset sạch (D02) |
| **Động cơ backtest** | Nội bộ `C1_C2_strategies/` (pandas/numpy) | Chạy C1/C2 + thí nghiệm mới, tính R, PF, DD, so baseline |
| **Trợ lý review/phản biện** | Claude (chính) + ChatGPT (phản biện chéo) | Đối chiếu journal vs broker, phát hiện vi phạm, đọc spec, đề xuất thí nghiệm theo T05 |
| **Agent tự động hoá** | Hermes Agent desktop (có memory, cron, MCP) | Lập lịch chạy scanner/backtest, tóm tắt báo cáo, soạn nhắc cho Claude |

Nguyên tắc phân vai:
- **Claude** = "trợ lý review kỷ luật & chiến lược": cho nó đọc nhật ký, spec, CSV kết quả → trả về kiểm tra vi phạm, tính số, đặt câu hỏi cho thí nghiệm.
- **ChatGPT** = "người phản biện": chạy song song một yêu cầu để so sánh quan điểm; mọi kết luận khác nhau đều đi qua nhưng không coi là quyết định.
- **Hermes** = "bộ phận hành chính": chạy lịch, nhắc nhở checklist, đẩy báo cáo. **Không được gắn quyền đặt lệnh.**

## 3. Sơ đồ luồng vận hành

```
[Hàng ngày 07:01 VN]
   Hermes (cron)  →  chạy scan_market.py → snapshot CSV
   Claude (manual) →  đọc snapshot + journal + spec → nhận xét tuân thủ, nghi vấn
   Bạn            →  xác nhận có entry hợp lệ theo hệ thống CHỨ KHÔNG theo gợi ý AI

[Hàng tuần review]
   Hermes         →  gom trade CSV + equity
   Claude+ChatGPT →  tính R/PF/DD theo setup, tách vi phạm, đề xuất 1 thí nghiệm
   Bạn            →  duyệt HUỶ/chấp thuận thí nghiệm; chạy backtest có baseline

[Khi có thí nghiệm cần chạy]
   Bạn            →  viết giả thuyết + điều kiện bác bỏ
   Claude         →  soát tính hợp lệ của thiết kế (một biến, dữ liệu mới? T05/T06)
   Backtest nội bộ →  chạy, ghi kết quả kèm thất bại
   Claude         →  báo cáo so với baseline; KHÔNG tự kết luận "thắng"
```

## 4. Bảo mật và quyền

- **Không API key trong code.** `config.py` và `account.example.json` đã làm mẫu đúng; Hermes token/API key chỉ dùng qua biến môi trường.
- **MCP:** Hermes có thể kết nối Trader Dev hoặc thư mục `C1_C2_strategies` để gọi backtest. Nhưng quyền MCP đọc-ghi chỉ mở khi: đã đọc giới hạn dữ liệu dịch vụ, đã có đối chứng baseline, có khả năng dừng/khôi phục (H05).
- **Agent KHÔNG được nằm trong luồng đặt lệnh thật:** mọi lệnh do bạn quyết định; dashboard/agent chỉ hiển thị quan sát (H08/A02).

## 5. Bối cảnh bạn đưa cho AI (prompt chuẩn)

Tạo file `sysprompt.txt` (hoặc skill trong Hermes) chứa:
- Tóm tắt baseline hiện tại (không phải code đặt lệnh).
- `rules.md` — để AI đối chiếu vi phạm với đúng mục.
- Định nghĩa C1/C2 (spec-C1-C2.md) — để AI biết điều kiện quan sát/entry.
- Yêu cầu trả lời đúng định dạng: quan sát / giả thuyết / kết luận / hành động đề xuất (A02).

## 6. Lộ trình kích hoạt (chỉ chuyển bước khi bước trước đạt)

| Giai đoạn | Nội dung | Điều kiện hoàn thành |
|---|---|---|
| **0. Khảo sát** (đang ở đây) | Có code backtest nội bộ + funding + train/test, có scanner | C1 có kết quả rõ & ổn định ngoài mẫu; C2 đã bác bỏ sau 2 vòng — ghi nhận |
| **1. Paper theo dõi** | Chạy scanner 1 tuần, so với backtest; ghi nhật ký quan sát | Snapshot 7 ngày liên tục, không lệch dữ liệu |
| **2. Trợ lý review** | Cho Claude đọc journal + CSV hằng ngày | 2 tuần trả lời đúng về vi phạm & tính số |
| **3. Tự động hoá research** | Hermes lập lịch chạy backtest theo giả thuyết duyệt trước | Không agent nào tự đổi parameter |
| **4. (Nếu muốn) gated execution** | Quy trình riêng, khả năng dừng/khôi phục, paper→live | Sau khi forward test C1 thực sự cải thiện |

## 7. Checklist hằng ngày cho người vận hành

- [ ] Scanner chạy đủ 24h, không lệch giờ (A07).
- [ ] Claude báo cáo khớp số với CSV; nếu lệch = chặn, không ghi đè (D01/D03).
- [ ] Mọi "tín hiệu AI" đều chưa phải lệnh: kiểm tra entry theo hệ thống đã định trước (C02).
- [ ] Không có thay đổi cấu hình ngoài hàng đợi đã duyệt (A05/H01).
- [ ] Chi phí token/MCP đang trong ngân sách (A09/H04).
- [ ] Không để dashboard đẹp thay thế bằng chứng (H08).

## 8. Files tham chiếu

- `C1_C2_strategies/` — code backtest + scanner (chi tiết: `spec-C1-C2.md`).
- `rules.md` — mọi quy tắc điều hành (mục 8 = AI, mục 14 = checklist agent).
- `spec-C1-C2.md` — định nghĩa 2 chiến lược + kết quả vòng 1 & 2.
- `danh-muc-theo-doi-crypto-binance.md` — danh mục quan sát hiện tại.