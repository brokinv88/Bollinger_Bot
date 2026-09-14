# Rules — Tổng kết tinh gọn (từ Tamly/rules.md, 07/09/2026)

Bản tổng hợp để xây dựng quy trình cá nhân, **chưa phải tham số đã kiểm chứng**. Mọi ngưỡng rủi ro/điều kiện định lượng phải xác định trên dữ liệu riêng. Tài liệu không tự cấp quyền đặt lệnh/sửa hệ thống cho AI.

## 1. Nguyên tắc nền (đọc trước phiên)
1. Chỉ giao dịch theo setup đã định nghĩa; nhu cầu kiếm tiền/gỡ lỗ/FOMO không phải tín hiệu.
2. Xác định rủi ro trước entry: điểm vô hiệu, cách thoát, khối lượng, tổng rủi ro mở.
3. Không tăng size để gỡ.
4. Tách chất lượng quyết định với kết quả tiền (lệnh lời có thể vẫn vi phạm).
5. Không đổi hệ thống vì vài lệnh gần nhất.
6. Mất khả năng tuân thủ → dừng mở lệnh mới, vẫn quản lý vị thế đang mở theo kế hoạch.
7. Ghi nhãn setup trước khi biết kết quả; không sửa câu chuyện.
8. Đánh giá lợi thế sau chi phí, cùng mức rủi ro — không chỉ win rate/lợi nhuận.
9. Thay đổi chiến lược phải có bằng chứng: giả thuyết + đối chứng + dữ liệu mới.
10. AI phải chứng minh bằng dữ liệu đối chiếu được; ghi nhớ tốt ≠ lợi thế.

## 2. Tâm lý — chống trắng 12 lỗi chính
- Muốn gỡ → không gắn size lệnh sau với lệnh trước.
- Hưng phấn sau thắng → tự tin không phải bằng chứng; giữ quy tắc rủi ro.
- Sợ vào sau thua → phân biệt cảm xúc với chất lượng cơ hội; ghi lý do bỏ lệnh.
- Đuổi giá/FOMO → chỉ vào khi entry còn hợp lệ; không thì chờ cơ hội khác.
- Nới stop → không sửa điểm vô hiệu vì không muốn thua.
- Đóng lời làm ngày xanh → P&L ngày không thay quy tắc exit.
- Chưa đạt chỉ tiêu → mục tiêu chi tiêu không tạo cơ hội; không lệnh ngoài hệ thống.
- Muốn đổi chiến lược sau vài lệnh → ghi nghi vấn, đưa vào review.
- Chỉ nhớ lệnh đẹp → lưu cả thắng/thua/vi phạm/cơ hội bỏ.
- Mệt/mất tập trung → tạm dừng, kiểm tra điều kiện quay lại.
- Thua đúng kế hoạch → là lệnh đúng quy trình, không phải quyết định xấu.
- Thắng nhờ vi phạm → lợi nhuận không hợp thức hóa vi phạm.

**Chuỗi thua:** kiểm tra lỗi vận hành → điều kiện thị trường → khả năng tuân thủ → giới hạn rủi ro → mới quyết định tiếp tục. Không mặc định thua 2 lệnh là tilt, cũng không dùng "chuỗi thua bình thường" để bỏ qua vi phạm.

**Điều kiện quay lại sau tạm dừng:** nguyên nhân đã xử lý; nêu rõ setup/rủi ro/thoát; không gỡ tiền; thị trường + ngân sách còn cho phép; tuân thủ thời điểm reset, không tự xóa giới hạn giữa phiên.

**Cấu trúc quy tắc hành vi:** *Khi [dấu hiệu] → thực hiện [hành động] → quản lý vị thế mở theo [kế hoạch] → quay lại khi [điều kiện].* Không đóng máy móc mọi vị thế khi đang tạm dừng.

## 3. Quản trị vốn (R01–R08)
- R01 Viết rủi ro trước lệnh (stop, tiền rủi ro, khối lượng, quản lý vị thế).
- R02 Xét tổng rủi ro mở, kể cả vị thế cùng chịu một biến động/sự kiện.
- R03 Không tăng rủi ro theo cảm xúc; đổi size chỉ trong quy tắc đã kiểm tra.
- R04 Không nới giới hạn dưới áp lực; mọi đề xuất đánh giá ngoài phiên.
- R05 Kiểm tra kịch bản xấu: gap, trượt giá, thiếu thanh khoản, stop không đảm bảo giá khớp.
- R06 Tăng size ở A+ cần bằng chứng riêng (nhãn trước entry, số mẫu, dữ liệu mới).
- R07 Không sao chép tỷ lệ từ video (1%/lệnh, 1,5x, Kelly…).
- R08 Tách vốn nghề và tiền sinh hoạt; chỉ tiêu theo kỳ phù hợp biến động.
- Prop firm: phân biệt tài khoản danh nghĩa với khoảng chịu lỗ thực tế; không lấy profit target/drawdown làm R của lệnh.

## 4. Chọn setup & thực thi
- Định nghĩa entry/exit/không giao dịch/sizing đủ rõ để review.
- Chấm setup trước entry; giữ bản ghi gốc.
- Khác nhau 3 quyết định: giới hạn số lệnh / lọc chất lượng / phân bổ size.
- Setup yếu ≠ kỳ vọng âm; hệ thống lời ≠ mọi nhóm setup đáng đánh.
- Ghi setup hợp lệ bỏ qua và lý do; đang lời/lỗ trong ngày không phải điều kiện tiếp tục.
- Không sửa quy tắc thực thi giữa phiên.
- Chạm vùng (Fib, value area, gamma wall) mới chỉ là quan sát — cần xác nhận hệ thống, không vào vì "giá rẻ".
- Định rõ nơi ý tưởng sai: gắn stop/thoát/trailing với điều kiện trước; không dời stop vì P&L đỏ; hòa vốn theo giá chưa chắc sau chi phí.

## 5. Dữ liệu & nhật ký (D01–D05)
- Đối chiếu được: giữ lịch sử gốc, đánh dấu chỉnh sửa, truy ngược về giao dịch và phiên bản chiến lược.
- Kiểm tra trước khi phân tích: tài sản/sàn/múi giờ, thiếu/trùng/cũ, nến chưa đóng, khớp từng phần, phí.
- Không tự điền trường thiếu (nhãn setup, rủi ro dự kiến, trạng thái cảm xúc).
- Chuẩn hóa: 1R = rủi ro dự kiến lúc mở lệnh; lời sau phí (không trừ 2 lần); phân biệt vị thế đóng với tài khoản; ghi rõ cách tính drawdown.
- Bộ trường entry: thời điểm/tài sản/sàn/hướng, setup&nhãn, điều kiện thị trường, stop&rủi ro, trạng thái bản thân, phiên bản quy tắc. Sau giao dịch: giá khớp/thực tế, đóng/điều chỉnh, phí/funding/P&L ròng, kết quả theo R, vi phạm & cách giảm, nhận xét tách khỏi bản ghi trước entry.

## 6. Đánh giá & cải thiện (T01–T10)
- T01 Tách phương pháp khỏi thực thi; vẫn báo cáo toàn bộ kết quả (không giấu lệnh vi phạm).
- T02 Không kết luận từ mẫu nhỏ; ghi số mẫu/giai đoạn/điều kiện.
- T03 Đo kỳ vọng ròng (win rate, lãi/lỗ TB, chi phí) chứ không chỉ win rate; xem phân phối tổn thất.
- T04 Giữ phiên bản đối chứng; mỗi lệnh gắn quy tắc sinh ra nó.
- T05 Giả thuyết trước khi tối ưu: vấn đề/thay đổi/lý do/chỉ số/điều kiện bác bỏ/dữ liệu; một thay đổi mỗi vòng.
- T06 Kiểm tra trên dữ liệu mới; xem lại tập kiểm tra lặp thì không còn là bằng chứng độc lập.
- T07 Lưu cả thất bại.
- T08 So sánh công bằng (lợi nhuận/drawdown/chi phí/số cơ hội/rủi ro).
- T09 Quan sát trước khi thay thế (mô phỏng/song song); không đưa bản thắng backtest vào thật.
- T10 "Chưa đủ bằng chứng" là kết quả hợp lệ; không ép mỗi review ra thay đổi.
- Chấm phiên A/B/C: A=tuân thủ kế hoạch (kể cả lỗ); B=lỗi nhỏ bị chặn; C=vi phạm trọng yếu (dù lời). Theo dõi tỷ lệ C-game.

## 7. Ngưỡng chưa kiểm chứng — phải cá nhân hóa trước khi dùng
Nghỉ sau 2 lệnh thua; giới hạn số lệnh/ngày; dừng khi đạt lợi nhuận ngày; giới hạn lỗ ngày; chỉ giao dịch A+; tăng size A+; thay tham số tuần. **Không tự bãi bỏ giới hạn hiện hành vì chưa xong nghiên cứu.**

## 8. Sử dụng AI / trading agent (A01–A09 + H01–H08)
- Bắt đầu bằng đọc/review/đối chiếu, không kỳ vọng tăng lợi nhuận.
- Tách quan sát – giả thuyết – kết luận; giải thích hợp lý ≠ bằng chứng nguyên nhân.
- Mục tiêu lợi nhuận không cấp quyền tăng rủi ro/sửa chiến lược/đặt lệnh.
- Tách nghiên cứu, giới hạn rủi ro và thực thi; chỉ bản được chấp thuận mới thực thi.
- Nhiều agent → dùng chung hàng đợi thay đổi + phiên bản chuẩn.
- "Tự học/nhớ context" không chứng minh lợi thế (đo kết quả mới, sau chi phí, cùng rủi ro).
- Đặt lệnh/gửi lệnh/sửa giới hạn rủi ro là quyền cấp riêng, phải dừng/khôi phục được; nghiên cứu là chỉ đọc. Không cấp quyền vì "backtest tốt".
- Tự động hóa nghiên cứu ≠ tự động hóa quyết định giao dịch.
- Loop tự sinh chiến lược phải kèm baseline, một thay đổi/thí nghiệm, dữ liệu kiểm tra riêng, điều kiện bác bỏ; không để agent tự chọn bản backtest đẹp thay baseline.
- Đo chi phí trước khi mở rộng (lịch 15 phút ≈ 96 lượt/ngày); "miễn phí" không đồng nghĩa rẻ.
- Xác minh phạm vi dữ liệu MCP từ tài liệu chính thức, không đoán từ video.
- Không lộ token bot/API key/tài khoản; kiểm tra quyền agent trước khi bật tool ghi/gửi.
- Dashboard chỉ là ghi chép, phải truy ngược về chiến lược/tham số/dữ liệu/phí. Kiểm tra vận hành: dữ liệu cũ, mất kết nối, lệnh trùng, cách dừng.

## 9. Checklist (rút gọn)
- **Trước phiên:** biết phiên bản chiến lược + điều kiện thị trường; đã kiểm tra dữ liệu/kết nối/vị thế; xác định giới hạn rủi ro + điều kiện dừng/quay lại; tỉnh táo; ghi bối cảnh/vùng/xác nhận/điều kiện bỏ ý tưởng.
- **Trước lệnh:** setup & entry còn hợp lệ; nhãn trước kết quả; rủi ro/size/điểm vô hiệu/thoát rõ; tổng rủi ro trong kế hoạch; không FOMO/gỡ/hưng phấn; có xác nhận hệ thống, không vào chỉ vì chạm vùng.
- **Sau phiên:** đối chiếu giao dịch & phí; ghi cả vi phạm có lời lẫn lệnh thua đúng quy trình; ghi cơ hội bỏ qua; chọn 1 lỗi cần giảm; đưa nghi vấn vào review; chấm phiên A/B/C độc lập P&L.
- **Review định kỳ:** xét toàn tài khoản + từng nhóm; kỳ vọng ròng/drawdown/mẫu/bất định; hành vi sau chuỗi; đối chiếu bản chuẩn; đổi quy tắc chỉ khi có bằng chứng.
- **Với agent:** kiểm tra cron chạy đúng/không trùng; baseline không đổi ngoài hàng đợi; dữ liệu nguồn đúng; ngân sách chi phí; quyền agent không đổi; kết quả truy ngược được; lưu cả thử thất bại; không duyệt đề xuất chạm thực thi thật ngoài quy trình.

## 10. Mẫu ghi 1 lỗi (8–10 dòng là đủ)
Ngày/mã giao dịch, quy tắc liên quan, điều gì xảy ra, bằng chứng, kế hoạch ban đầu, lệch ở đâu, tác nhân kích hoạt, nguyên nhân giả định (chưa phải kết luận), hành động ngăn lỗi cụ thể, chỉ số kiểm tra, thời điểm review. Ví dụ thay "phải kỷ luật hơn" bằng "trước khi gửi lệnh, đối chiếu khối lượng với rủi ro đã ghi".

## 11. SMC (S01–S10) — nếu cân nhắc ngôn ngữ SMC
- Thuật ngữ không chuẩn hóa: viết định nghĩa đủ rõ để chấm lại trước khi đánh vùng.
- "3 hợp lưu A+ = xác suất cao" là giả thuyết cần số liệu riêng.
- ChOCh/BOS "hợp lệ" phải định nghĩa trước entry (nhãn trước kết quả).
- Order block/FVG là diễn giải chủ quan từ chart, không phải dữ liệu lệnh; đo giá trị thêm so với hỗ trợ/kháng cự cổ điển.
- Đo từng yếu tố hợp lưu riêng rồi mới đo kết hợp; một biến/vòng.
- Win rate cao ≠ kỳ vọng dương (ví dụ Liquidity Sweep 71,9% nhưng vẫn lỗ).
- Giờ "chết" hợp lý về tinh thần nhưng phải đo theo cặp/sàn/thời gian của bạn.
- Bonus sàn (XM) là tín dụng không rút được thường; không làm đầu vào sizing.
- Không đổi hệ thống vì ví dụ SMC đẹp (đều short, chọn sau khi giá đi xong).
- Target 2R / vào khung nhỏ = tham số cần backtest, không lấy từ video.
- Mục tiêu 2R, tránh cuối phiên/thứ 6/4–7h sáng, order block mạnh, bonus — đều cần kiểm chứng.

## 12. Các thông số cần điền (chưa có, không để AI tự điền từ video)
Chiến lược/phiên bản; rủi ro cơ sở/lệnh; tổng rủi ro mở tối đa; giới hạn vị thế cùng nguồn rủi ro; giới hạn lỗ + thời điểm reset; drawdown kích hoạt review/dừng; dấu hiệu tạm dừng; điều kiện quay lại; lịch review + tiêu chí mẫu; quyền AI (đề xuất: chỉ đọc/báo cáo); khung giờ/thanh khoản; dấu hiệu sớm mất kiểm soát; vi phạm trọng yếu xếp C-game; config order flow nếu dùng.

## Nguồn tài liệu
Tổng hợp tâm lý trading + kế hoạch hành động; Hermes & kế hoạch; Chris Creamer (bối cảnh/order flow/C-game); Hermes Agent desktop & sàn AI tự động; Smart Money Concept setup A+; spec-C1-C2; danh mục crypto Binance; kiến trúc bộ công cụ Hermes+ChatGPT+Claude (tất cả trong `Tamly/`).