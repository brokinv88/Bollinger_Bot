# Rules — Nguyên tắc giao dịch, kiểm soát tâm lý và sử dụng AI

Ngày tổng hợp: 07/09/2026.  
Phạm vi: bộ quy tắc thực hành rút từ các tài liệu trong thư mục Tamly, dành cho trader full-time. Bổ sung ngày 07/09/2026: bài Chris Creamer về bối cảnh, order flow và kiểm soát phiên mất kỷ luật; bài Hermes Agent desktop và sàn giao dịch AI tự động; bài Smart Money Concept về setup A+ (thanh khoản, cấu trúc, thời điểm).

> Đây là bản tổng hợp để xây dựng quy trình cá nhân, chưa phải bộ tham số đã được kiểm chứng trên tài khoản của bạn. Các ngưỡng rủi ro và điều kiện định lượng cần được xác định riêng. Tài liệu này không tự cấp quyền đặt lệnh hay sửa hệ thống cho AI.

## 1. Mười nguyên tắc đọc trước phiên

1. **Giao dịch theo setup đã định nghĩa.** Nhu cầu kiếm tiền, gỡ lỗ hoặc sợ bỏ lỡ không phải tín hiệu vào lệnh.
2. **Xác định rủi ro trước entry.** Biết điểm vô hiệu, cách thoát, khối lượng và tổng rủi ro đang mở.
3. **Không tăng size để gỡ.** Chuỗi thắng cũng không tự tạo lý do tăng size.
4. **Chấm chất lượng quyết định riêng với kết quả tiền.** Lệnh lời vẫn có thể là lệnh vi phạm; lệnh lỗ vẫn có thể thực hiện đúng.
5. **Không đổi hệ thống vì vài lệnh gần nhất.** Ghi nhận vấn đề và đánh giá theo quy trình review.
6. **Khi mất khả năng tuân thủ, dừng mở lệnh mới.** Quản lý vị thế đang mở theo kế hoạch rủi ro đã định.
7. **Ghi nhãn setup trước khi biết kết quả.** Không sửa lại câu chuyện để hợp với lệnh thắng hoặc thua.
8. **Đánh giá lợi thế sau chi phí và cùng mức rủi ro.** Không chỉ nhìn win rate hoặc tổng lợi nhuận.
9. **Thay đổi chiến lược phải có bằng chứng.** Viết giả thuyết, giữ đối chứng và kiểm tra dữ liệu mới.
10. **AI phải chứng minh bằng dữ liệu có thể đối chiếu.** Ghi nhớ tốt và giải thích thuyết phục chưa chứng minh có lợi thế giao dịch.

## 2. Quy tắc kiểm soát tâm lý

| Tình huống hoặc lỗi | Nguyên tắc | Hành động cụ thể |
|---|---|---|
| Muốn lấy lại tiền vừa mất | Lệnh trước không quyết định size lệnh sau | Kiểm tra lại setup và sizing đã định; không đủ khả năng tuân thủ thì tạm dừng |
| Hưng phấn sau chuỗi thắng | Tự tin không phải bằng chứng setup tốt hơn | Giữ quy tắc phân bổ rủi ro hiện hành |
| Sợ vào lệnh sau thua | Phân biệt cảm xúc với thay đổi chất lượng cơ hội | Kiểm tra setup, trạng thái bản thân và giới hạn rủi ro; ghi lý do nếu bỏ lệnh |
| Đuổi giá hoặc FOMO | Chỉ vào khi điều kiện entry còn hợp lệ | Nếu giá vượt điều kiện cho phép, chờ cơ hội khác theo kế hoạch |
| Nới stop để tránh nhận lỗ | Không sửa điểm vô hiệu vì không muốn thua | Thực hiện quy tắc quản lý lệnh đã viết trước entry |
| Muốn đóng lời chỉ để có ngày xanh | P&L ngày không thay thế quy tắc exit | Dùng quy tắc thoát đã định; thay đổi quy tắc được đưa vào review |
| Chưa đạt chỉ tiêu tiền ngày | Mục tiêu chi tiêu không tạo cơ hội | Không phát sinh lệnh ngoài hệ thống để đủ chỉ tiêu |
| Muốn đổi chiến lược sau vài lệnh | Mẫu ngắn chưa đủ kết luận lợi thế mất đi | Ghi nghi vấn, kiểm tra lỗi vận hành và đưa giả thuyết vào lịch review |
| Chỉ nhớ các lệnh đẹp | Ký ức chọn lọc không phải dữ liệu | Lưu cả thắng, thua, vi phạm và cơ hội bỏ qua |
| Mệt hoặc mất tập trung | Khả năng thực thi là điều kiện giao dịch | Tạm dừng mở lệnh mới; kiểm tra điều kiện quay lại |
| Thua nhưng làm đúng kế hoạch | Không tự động coi kết quả xấu là quyết định xấu | Ghi là lệnh đúng quy trình và đưa vào mẫu đánh giá |
| Thắng nhờ vi phạm | Lợi nhuận không hợp thức hóa vi phạm | Ghi rõ vi phạm và cách ngăn tái diễn |

### Quy trình sau chuỗi thua

1. Kiểm tra có lỗi dữ liệu, khớp lệnh hoặc thực thi không.
2. Kiểm tra điều kiện thị trường còn phù hợp với chiến lược không.
3. Kiểm tra bản thân còn tuân thủ được entry, exit và size không.
4. Kiểm tra giới hạn rủi ro còn cho phép không.
5. Chỉ tiếp tục khi các điều kiện của kế hoạch đều đáp ứng; ghi lại quyết định.

**Không mặc định thua hai lệnh là tilt. Không dùng lý do “chuỗi thua bình thường” để bỏ qua vi phạm.**

### Điều kiện quay lại sau khi tạm dừng

- Nguyên nhân tạm dừng đã được kiểm tra và xử lý.
- Có thể nêu rõ setup, rủi ro và cách thoát của lệnh dự định.
- Không dùng mục tiêu gỡ tiền làm lý do vào lệnh.
- Điều kiện thị trường và ngân sách rủi ro vẫn cho phép.
- Nếu đã chạm giới hạn dừng của kế hoạch, tuân thủ thời điểm reset đã định; không tự xóa giới hạn giữa phiên.

## 3. Quy tắc quản trị vốn và vị thế

### R01 — Viết rủi ro trước lệnh

Ghi điểm vô hiệu hoặc stop theo hệ thống, mức tiền dự kiến chịu rủi ro, khối lượng và quy tắc quản lý vị thế. Phân biệt rủi ro dự kiến với tổn thất thực tế có thể vượt dự kiến.

### R02 — Xét tổng rủi ro đang mở

Không chỉ kiểm tra từng lệnh riêng. Xem các vị thế có cùng chịu biến động của một thị trường hoặc một sự kiện hay không.

### R03 — Không tăng rủi ro theo cảm xúc

Không tăng size vì muốn gỡ, vừa thắng liên tiếp hoặc muốn đạt chỉ tiêu nhanh hơn. Thay đổi size cần nằm trong quy tắc được kiểm tra trước.

### R04 — Không nới giới hạn trong lúc chịu áp lực

Các giới hạn rủi ro phải được xác định trước khi sử dụng. Đề xuất thay đổi được đánh giá ngoài phiên, với lý do và dữ liệu; không dùng để hợp thức hóa một vị thế hiện tại.

### R05 — Kiểm tra kịch bản xấu

Đánh giá gap, trượt giá, thiếu thanh khoản và tình huống nhiều vị thế cùng bất lợi. Stop không bảo đảm giá khớp như dự kiến.

### R06 — Tăng size ở A+ cần bằng chứng riêng

Nhãn A+ phải có trước entry, có số mẫu và kết quả trên dữ liệu mới. So sánh sizing khác nhau trên ngân sách rủi ro tương đương, kèm drawdown và chi phí.

### R07 — Không sao chép tỷ lệ từ video

Không mặc định 1%/lệnh là an toàn, 1,5 lần là size tối ưu hoặc Kelly cho ra mức cược phù hợp thực tế. Chọn ngưỡng theo hệ thống, mức bất định và khả năng chịu tổn thất của bản thân.

### R08 — Tách vốn nghề nghiệp và tiền sinh hoạt

Không để nhu cầu thanh toán hằng ngày trở thành lý do tăng rủi ro hoặc tạo lệnh ngoài hệ thống. Đánh giá mục tiêu thu nhập theo kỳ phù hợp với tính biến động của nghề.

## 4. Quy tắc chọn setup và thực thi

- Định nghĩa entry, exit, điều kiện không giao dịch và sizing bằng tiêu chí đủ rõ để review.
- Chấm setup trước khi vào; giữ nguyên bản ghi gốc nếu bổ sung nhận xét sau lệnh.
- Phân biệt giới hạn số lệnh, lọc chất lượng và phân bổ size: đây là ba quyết định khác nhau.
- Không coi setup yếu hơn là setup chắc chắn kỳ vọng âm; cũng không coi hệ thống có lời là bằng chứng mọi nhóm setup đều đáng đánh.
- Ghi các setup hợp lệ bỏ qua và lý do. Lịch sử broker không phản ánh những cơ hội chưa giao dịch.
- Không coi đang lời hoặc đang lỗ trong ngày là điều kiện đủ để tiếp tục hay dừng. Áp dụng kế hoạch về cơ hội, trạng thái và rủi ro.
- Không sửa quy tắc thực thi giữa phiên để phù hợp với cảm xúc hoặc kết quả vừa xảy ra.

## 5. Quy tắc dữ liệu và nhật ký

### D01 — Giữ bản gốc và khả năng đối chiếu

Giữ lịch sử nguồn; đánh dấu các chỉnh sửa làm sạch dữ liệu. Kết luận cần truy ngược được về giao dịch và phiên bản chiến lược liên quan.

### D02 — Kiểm tra trước khi phân tích

Kiểm tra tài sản, sàn, múi giờ, dữ liệu thiếu/trùng/cũ, nến chưa đóng, lệnh khớp từng phần và cách tính phí. Đối chiếu P&L với báo cáo nguồn.

### D03 — Không tự điền thông tin không có

Nếu thiếu nhãn setup, rủi ro dự kiến hoặc trạng thái cảm xúc thì ghi thiếu. Không suy ngược các trường đó từ kết quả lời/lỗ.

### D04 — Chuẩn hóa phép đo

- 1R là số tiền dự kiến chịu rủi ro lúc mở lệnh.
- Tính lợi nhuận sau phí, funding và các chi phí liên quan; không trừ phí hai lần.
- Phân biệt kết quả vị thế đã đóng và giá trị tài khoản gồm vị thế đang mở.
- Ghi rõ cách tính drawdown; chỉ dùng lệnh đã đóng có thể bỏ sót sụt giảm trong lúc giữ lệnh.

### D05 — Bộ trường cần ghi

| Trước hoặc tại entry | Sau và trong giao dịch |
|---|---|
| Thời điểm, tài sản, sàn, hướng lệnh | Giá khớp và khối lượng thực tế |
| Setup và nhãn chất lượng | Các lần đóng hoặc điều chỉnh vị thế |
| Điều kiện thị trường | Phí, funding và P&L ròng |
| Stop/điểm vô hiệu và rủi ro dự kiến | Kết quả theo R nếu đủ dữ liệu |
| Trạng thái bản thân | Vi phạm cụ thể và cách giảm lỗi |
| Phiên bản quy tắc | Nhận xét sau giao dịch, tách khỏi bản ghi trước entry |

## 6. Quy tắc đánh giá và cải thiện chiến lược

### T01 — Đánh giá riêng phương pháp và thực thi

Tách các lệnh đúng hệ thống khỏi lệnh vi phạm để hiểu nguồn vấn đề, đồng thời vẫn báo cáo toàn bộ kết quả tài khoản. Không bỏ lệnh xấu khỏi báo cáo tổng chỉ vì chúng là vi phạm.

### T02 — Không kết luận từ mẫu quá nhỏ

Luôn ghi số mẫu, giai đoạn và điều kiện thị trường. Nhiều dòng dữ liệu không đồng nghĩa nhiều quan sát độc lập. Không có một mốc số lệnh chung bảo đảm kết luận đúng.

### T03 — Đo kỳ vọng ròng thay vì chỉ win rate

Kỳ vọng phụ thuộc tỷ lệ thắng, lãi trung bình, lỗ trung bình và chi phí. Khi kiểm tra sau chuỗi thua hoặc theo nhóm setup, xem cả phân phối tổn thất và độ bất định.

### T04 — Giữ một phiên bản đối chứng

Lưu phiên bản chuẩn để so sánh. Mỗi giao dịch phải gắn với quy tắc đã tạo ra nó; không trộn các phiên bản rồi coi là một hệ thống không đổi.

### T05 — Viết giả thuyết trước khi tối ưu

Mỗi thí nghiệm ghi rõ: vấn đề, thay đổi, lý do, chỉ số đánh giá, điều kiện bác bỏ và dữ liệu kiểm tra. Ưu tiên một thay đổi mỗi vòng để dễ giải thích; ghi nhận nếu có tương tác giữa các biến.

### T06 — Kiểm tra trên dữ liệu mới

Tách dữ liệu dùng chọn quy tắc khỏi dữ liệu kiểm tra theo thời gian. Nếu liên tục xem tập kiểm tra để sửa quy tắc, không tiếp tục gọi nó là bằng chứng độc lập.

### T07 — Lưu cả thất bại

Lưu số phương án đã thử, kết quả không cải thiện và các giả thuyết bị bác bỏ. Không chỉ lưu phiên bản đẹp nhất.

### T08 — So sánh công bằng

So lợi nhuận, drawdown, chi phí, số cơ hội và rủi ro sử dụng. Tăng lợi nhuận nhờ đặt cược lớn hơn chưa chứng minh chiến lược tốt hơn.

### T09 — Chạy quan sát trước khi thay thế

Sau kiểm thử lịch sử, ghi nhận kết quả trên dữ liệu mới bằng mô phỏng hoặc chạy song song. Không đưa phiên bản thắng backtest vào giao dịch thật chỉ vì một chỉ số tăng.

### T10 — Chấp nhận chưa đủ bằng chứng

Không ép mỗi vòng review phải tạo ra thay đổi. Giữ nguyên và tiếp tục thu thập dữ liệu là quyết định hợp lệ.

## 7. Những quy tắc phải kiểm chứng trước khi chọn ngưỡng

| Quy tắc ứng viên | Cần kiểm tra |
|---|---|
| Nghỉ sau hai lệnh thua | Kỳ vọng lệnh tiếp theo, hành vi vi phạm, cách reset và cơ hội bỏ lỡ |
| Giới hạn số lệnh/ngày | Chất lượng theo thứ tự lệnh, thời gian, mệt mỏi và tác động rủi ro |
| Dừng khi đạt lợi nhuận ngày | Chất lượng cơ hội còn lại và trạng thái thực thi sau khi có lời |
| Mức giới hạn lỗ ngày | Khả năng chịu lỗ, rủi ro thực tế, phân phối kết quả và điều kiện tài khoản |
| Chỉ giao dịch A+ | Nhãn trước entry, kỳ vọng ròng, số mẫu và lợi nhuận cơ hội bị bỏ |
| Tăng size ở A+ | Bằng chứng ngoài mẫu, mức rủi ro tương đương và tổn thất trong giai đoạn xấu |
| Thay tham số mỗi tuần | Lượng thông tin mới, độ ổn định và rủi ro tối ưu quá mức |

Không tự bãi bỏ một giới hạn hiện hành chỉ vì chưa hoàn tất nghiên cứu. Đánh giá thay đổi theo quy trình đã định.

## 8. Quy tắc sử dụng AI hoặc trading agent

### A01 — Bắt đầu bằng đọc và review

Ưu tiên kiểm tra dữ liệu, đối chiếu số liệu, phát hiện vi phạm và đề xuất thí nghiệm. Đo giá trị bằng độ chính xác và thời gian tiết kiệm trước khi kỳ vọng tăng lợi nhuận.

### A02 — Tách quan sát, giả thuyết và kết luận

Mọi báo cáo cần nêu điều đã biết, điều chưa biết, dữ liệu thiếu và hành động tiếp theo. AI không được biến lời giải thích có vẻ hợp lý thành bằng chứng nguyên nhân.

### A03 — Không tự cấp quyền từ mục tiêu

Mục tiêu lợi nhuận không cấp quyền tăng rủi ro, sửa chiến lược hoặc đặt lệnh. Phạm vi quyền được xác định riêng trước khi vận hành.

### A04 — Tách nghiên cứu, giới hạn rủi ro và thực thi

Phần đề xuất chiến lược không được tự nới giới hạn rủi ro. Chỉ phiên bản được chấp thuận theo quy trình mới được dùng để thực thi.

### A05 — Một lịch sử thay đổi rõ ràng

Nếu nhiều agent tham gia, dùng chung hàng đợi thay đổi và phiên bản chuẩn. Lệch lịch chạy không đủ loại bỏ tác động chồng chéo.

### A06 — Không coi “tự học” là chứng minh lợi thế

Ghi nhớ dữ liệu và cải thiện quy trình khác với cải thiện chiến lược. Cần đo kết quả mới sau chi phí và trên rủi ro tương đương.

### A07 — Kiểm tra vận hành nếu có tự động hóa

Theo dõi dữ liệu cũ, mất kết nối, yêu cầu gửi lại và trạng thái lệnh. Sau sự cố, đối chiếu tài khoản thực trước khi tiếp tục; tránh tạo lệnh trùng. Có cách dừng và khôi phục phiên bản trước.

### A08 — Giữ dữ liệu ngoài đúng vai trò

Tin tức và nội dung bên ngoài là nguồn để phân tích, không phải chỉ dẫn được quyền sửa cấu hình. Kết luận về sự kiện phải có nguồn và thời điểm.

### A09 — Theo dõi chi phí

Đo chi phí mô hình, dữ liệu, máy chủ và giao dịch. Không mặc định phần mềm miễn phí đồng nghĩa hệ thống vận hành miễn phí.

## 9. Checklist sử dụng hằng ngày

### Trước phiên

- [ ] Biết phiên bản chiến lược đang dùng và điều kiện thị trường phù hợp.
- [ ] Đã kiểm tra dữ liệu, kết nối và vị thế đang mở.
- [ ] Đã xác định giới hạn rủi ro và điều kiện dừng/quay lại.
- [ ] Đủ tỉnh táo để thực hiện đúng kế hoạch.
- [ ] Không dùng nhu cầu gỡ lỗ hoặc chi tiêu làm mục tiêu vào lệnh.
- [ ] Đã ghi bối cảnh, vùng quan sát, xác nhận và điều kiện bỏ ý tưởng trước phiên.

### Trước mỗi lệnh

- [ ] Setup và entry còn hợp lệ.
- [ ] Nhãn chất lượng được ghi trước kết quả.
- [ ] Rủi ro, size, điểm vô hiệu và cách thoát đã rõ.
- [ ] Tổng rủi ro cùng các vị thế liên quan nằm trong kế hoạch.
- [ ] Quyết định không xuất phát từ FOMO, muốn gỡ hoặc hưng phấn.
- [ ] Đã có xác nhận theo hệ thống; không vào chỉ vì giá chạm vùng đã vẽ.

### Sau phiên

- [ ] Đối chiếu giao dịch và chi phí.
- [ ] Ghi cả vi phạm có lời và lệnh thua thực hiện đúng.
- [ ] Ghi cơ hội hợp lệ bỏ qua cùng lý do.
- [ ] Chọn lỗi cần giảm, không vội đổi hệ thống.
- [ ] Lưu nghi vấn vào danh sách review.
- [ ] Chấm phiên A/B/C độc lập P&L; xác định dấu hiệu đầu tiên trước vi phạm nếu có.

### Theo lịch review

- [ ] Đánh giá toàn tài khoản và từng nhóm giao dịch.
- [ ] Xem kỳ vọng ròng, drawdown, số mẫu và độ bất định.
- [ ] Kiểm tra hành vi sau chuỗi thắng/thua.
- [ ] Đối chiếu với phiên bản chuẩn và lưu toàn bộ thử nghiệm.
- [ ] Chỉ đổi quy tắc khi có lý do và bằng chứng phù hợp.

## 10. Mẫu ghi một lỗi và cách giảm lỗi

```text
Ngày / mã giao dịch:
Quy tắc liên quan:
Điều gì đã xảy ra:
Dữ liệu hoặc bằng chứng:
Kế hoạch ban đầu:
Hành vi thực tế khác kế hoạch ở đâu:
Tác nhân kích hoạt quan sát được:
Nguyên nhân giả định, chưa coi là kết luận:
Cách ngăn lỗi lần sau, viết thành hành động cụ thể:
Chỉ số để kiểm tra lỗi có giảm không:
Thời điểm review:
Kết quả review / chưa đủ dữ liệu:
```

Ví dụ: thay “tôi phải kỷ luật hơn” bằng “trước khi gửi lệnh, đối chiếu khối lượng với mức rủi ro đã ghi; nếu khác kế hoạch thì tính lại và ghi lý do trước khi tiếp tục”.

## 11. Các thông số cần cá nhân hóa

| Thông số | Giá trị của tôi |
|---|---|
| Chiến lược / phiên bản đang dùng | Chưa điền |
| Rủi ro cơ sở mỗi lệnh | Chưa điền |
| Tổng rủi ro đang mở tối đa | Chưa điền |
| Giới hạn cho các vị thế cùng nguồn rủi ro | Chưa điền |
| Giới hạn lỗ và thời điểm reset | Chưa điền |
| Mức drawdown kích hoạt review hoặc dừng | Chưa điền |
| Dấu hiệu tạm dừng do trạng thái thực thi | Chưa điền |
| Điều kiện quay lại | Chưa điền |
| Lịch review và tiêu chí đánh giá mẫu | Chưa điền |
| Quyền của AI / agent | Chưa điền; đề xuất ban đầu: chỉ đọc và báo cáo |
| Khung giờ và điều kiện thanh khoản phù hợp | Chưa điền; cần kiểm chứng |
| Dấu hiệu sớm trước khi mất kiểm soát | Chưa điền |
| Vi phạm trọng yếu để xếp phiên C-game | Chưa điền |
| Profile, feed và cấu hình xác nhận nếu dùng order flow | Chưa điền |

Không để AI tự điền các ngưỡng bằng con số trong video. Việc ghi tài liệu này chưa thay đổi cấu hình hoặc quy tắc của tài khoản đang chạy.

## 12. Bổ sung từ Chris Creamer — Bối cảnh và ngăn phiên mất kỷ luật

Các quy tắc dưới đây mở rộng phần tâm lý và thực thi ở trên. Những yêu cầu về footprint/GEX chỉ áp dụng khi chiến lược của bạn sử dụng chúng; không bắt buộc thêm công cụ vào hệ thống đang có.

### C01 — Chuẩn bị kịch bản trước phiên

Viết bối cảnh, vùng muốn giao dịch, xác nhận bắt buộc và điều kiện bỏ ý tưởng trước lúc thị trường chạy nhanh. Nếu bối cảnh thay đổi, đánh giá lại; không cố bảo vệ dự báo ban đầu.

### C02 — Chạm vùng chưa đủ để vào lệnh

Vùng hỗ trợ, Fibonacci, value area hoặc gamma wall là vị trí quan sát. Chỉ vào khi đạt điều kiện xác nhận của hệ thống; không dùng câu “giá đã rẻ” thay thế tín hiệu.

### C03 — Phân biệt nỗ lực với kết quả

Nếu dùng order flow, xem hoạt động chủ động có tạo tiến triển giá không. Delta lớn hoặc absorption riêng lẻ không chứng minh đảo chiều. Viết rõ cần thấy phản ứng và lần thử lại nào trước entry.

### C04 — Xác định nơi ý tưởng sai

Gắn stop, thoát sớm và trailing với điều kiện đã định trước. Không dời stop chỉ để tránh nhìn P&L đỏ; cũng không cố giữ mục tiêu khi điều kiện vô hiệu đã xảy ra. Hòa vốn theo giá chưa chắc hòa vốn sau chi phí.

### C05 — Chấm chất lượng cả phiên

Rubric đề xuất, cần định nghĩa lỗi trọng yếu trước khi dùng:

| Loại | Tiêu chí |
|---|---|
| A-game | Tuân thủ kế hoạch và giới hạn, kể cả phiên lỗ hoặc không có setup |
| B-game | Lỗi quy trình nhỏ được nhận ra và chặn lại, không vi phạm giới hạn trọng yếu |
| C-game | Vi phạm trọng yếu hoặc quyết định cảm xúc phá quy tắc, dù phiên vẫn có lời |

Theo dõi tỷ lệ phiên có vi phạm trọng yếu và tần suất từng lỗi. Tiếp tục báo cáo P&L toàn tài khoản; không xóa C-game khỏi dữ liệu để làm đẹp hiệu suất.

### C06 — Tìm dấu hiệu sớm trước lệnh thua lớn

Review dòng thời gian từ tác nhân kích hoạt tới vi phạm đầu tiên. Không mặc định lệnh lỗ lớn là nơi tilt bắt đầu. Chọn điểm có thể can thiệp sớm, như xem người khác khoe lời, đổi size ngoài kế hoạch hoặc bỏ qua xác nhận.

### C07 — Quy tắc phải có hành động và điều kiện quay lại

Dùng cấu trúc: **Khi [dấu hiệu] → thực hiện [hành động] → quản lý vị thế đang mở theo [kế hoạch] → quay lại khi [điều kiện].**

Ví dụ đề xuất: khi phát hiện mình chuẩn bị tăng size chỉ để gỡ, hủy thao tác tăng rủi ro, tạm dừng mở lệnh mới và ghi tác nhân; chỉ quay lại khi đáp ứng điều kiện ở mục 2. Không tự đóng mọi vị thế một cách máy móc chỉ vì đang tạm dừng.

### C08 — Chặn nguồn FOMO có thể kiểm soát

Nếu lịch sử cho thấy bảng thành tích hoặc ảnh P&L cộng đồng kích hoạt lệnh ngoài kế hoạch, tắt chúng trong phiên. Đánh giá mình theo dữ liệu và quy trình cá nhân, không theo ảnh kết quả của người khác.

### C09 — Phù hợp cường độ với khả năng thực thi

Chọn khung giờ và tần suất theo dữ liệu chất lượng thực thi, thanh khoản và chiến lược. Không có lệnh khi không có setup hợp lệ là một kết quả tuân thủ. Không ép scalping liên tục chỉ vì công cụ hiển thị thêm tín hiệu.

### C10 — Khi vi phạm lặp lại, chuyển trọng tâm sang luyện thực thi

Cân nhắc replay hoặc mức rủi ro nhỏ phù hợp để thực hành một setup ổn định. Tiêu chí tiến bộ là giảm vi phạm và thực hiện nhất quán, không phải payout hay ảnh lợi nhuận. Giảm size không tự tạo lợi thế cho phương pháp.

### C11 — Không theo đuổi tiền và thời gian đã mất

Đánh giá việc tiếp tục dựa trên dữ liệu hiện tại, nguồn lực và kế hoạch; không vì “đã bỏ quá nhiều nên phải gỡ bằng được”. Không biến câu chuyện vượt khó của người thắng thành lý do đặt sinh kế vào rủi ro lớn hơn.

### C12 — Phân biệt tài khoản danh nghĩa và khoảng chịu lỗ thực tế

Nếu dùng prop firm, xác định khoảng cách tới ngưỡng vi phạm cùng cơ chế drawdown của tài khoản. Không lấy tỷ lệ profit target/drawdown làm R của một lệnh và không coi thi đánh giá là lý do phải cược lớn.

### C13 — Ghi cấu hình khi dùng dữ liệu chuyên sâu

Lưu sản phẩm, hợp đồng, feed, phiên profile, cách tính imbalance và thời điểm cập nhật GEX. Không coi footprint của MNQ tương đương NQ hoặc áp ngưỡng volume sang thị trường khác. GEX là ước lượng theo mô hình, không phải tín hiệu hướng giá chắc chắn.

### Những ngưỡng từ bài này vẫn cần kiểm chứng

| Ngưỡng/ý tưởng của Chris | Việc cần làm trước khi áp dụng |
|---|---|
| Chỉ giao dịch 90 phút đầu phiên | Đo chất lượng setup và thực thi theo thời gian của bản thân |
| Nghỉ sau hai lệnh thua | Xác định điểm mất kiểm soát cá nhân và tác động lên cơ hội |
| 20.000 hợp đồng/nến MNQ 5 phút | Kiểm tra feed, sản phẩm, kỳ quan sát và biến động volume |
| Imbalance 400% | Ghi đúng cách so bid/ask và đo giá trị bổ sung của bộ lọc |
| Fib 0,705 / 0,788 / 0,886 trong transcript | Xác nhận mức và cách neo swing; kiểm thử trước khi dùng |
| Chờ xác nhận thay vì entry sớm | So kỳ vọng ròng, giá entry, stop và số tín hiệu bị bỏ |
| Dời hòa vốn/trailing khi gặp vùng cản | Định nghĩa điều kiện và kiểm tra cả chi phí lẫn cơ hội bị cắt |

## 13. Bổ sung từ Hermes Agent desktop — Vận hành agent và "sàn giao dịch AI"

Các quy tắc dưới đây mở rộng phần sử dụng AI ở mục 8 khi bạn chạy agent tự động hóa nghiên cứu, điểm chốt ở chỗ: tự động hóa **quy trình nghiên cứu** khác với tự động hóa **quyết định giao dịch**. Nhận định công cụ (Hermes desktop, Trader Dev MCP) đã đối chiếu tài liệu; hiệu suất và thành tích tác giả video nói chưa được kiểm toán.

### H01 — Bật loop sinh chiến lược phải kèm baseline và giả thuyết

Agent chạy lịch tạo chiến lược liên tục (ví dụ mỗi 15 phút) chỉ có giá trị khi có: phiên bản chuẩn cố định, một thay đổi mỗi thí nghiệm, dữ liệu kiểm tra riêng và điều kiện bác bỏ. Không được để agent chọn bừa phiên bản backtest đẹp nhất để tự thay thế baseline.

### H02 — "Nhớ context" và "tự cải thiện" là đặc tính quy trình

Agent nhớ lịch sử và cải thiện kỹ năng xử lý không tự chứng minh lợi thế giao dịch. Bằng chứng lợi thế là kết quả ngoài mẫu, sau mọi chi phí, trên rủi ro tương đương. Không cấp thêm quyền vì agent "học tốt hơn" hoặc "có dashboard đẹp".

### H03 — Mỗi topic/văn phòng là một ngữ cảnh, chưa phải hệ thống độc lập

Các topic trong nhóm là các ngữ cảnh của cùng một agent, thường đọc/ghi chung một database. Cần hàng đợi thay đổi và phiên bản chuẩn dùng chung; lệch lịch chạy không đủ tạo đối chứng (nối tiếp A05).

### H04 — Loop 24/7 phải đo chi phí trước khi mở rộng

Một lịch mỗi 15 phút là khoảng 96 lượt chạy/ngày. Đo token, mức dùng API/MCP và tài nguyên máy; "công cụ miễn phí" không đồng nghĩa hệ thống chạy miễn phí (củng cố A09).

### H05 — Kiểm tra phạm vi dữ liệu của dịch vụ, không đoán từ video

Trước khi xây hệ thống quanh MCP backtest, xác nhận tài liệu chính thức hỗ trợ những cặp/loại tài sản, giới hạn số liệu/mỗi lượt và điều kiện sử dụng. Không giả định vàng/forex/crypto chỉ vì video nói.

### H06 — Không công khai token bot, API key và thông tin tài khoản

Token bot, mã API và tài khoản trao quyền truy cập dịch vụ. Nếu dùng Telegram, xóa token khỏi khung nhìn/màn hình được quay lại; chỉ dùng token trong cấu hình riêng tư. Kiểm tra quyền agent trước khi bật tool có thể ghi hoặc gửi lệnh.

### H07 — Agent nghiên cứu không được đặt lệnh thật trừ khi có quy trình riêng

Chạy backtest, đề xuất thí nghiệm và tạo dashboard là nghiên cứu (chỉ đọc). Đặt lệnh, gửi lệnh lên sàn hoặc tự sửa giới hạn rủi ro là quyền cấp riêng, cần dừng và khôi phục được; không mở quyền vì "backtest tốt" hoặc vì thấy agent trả lời nhanh thuận tiện.

### H08 — Dashboard chỉ là ghi chép

Kết quả hiển thị trên dashboard cần truy ngược về chiến lược, tham số, dữ liệu và phí. Không coi một bảng chỉ báo "tương tác tốt" là bằng chứng nguyên nhân hoạt động hiệu quả (nối tiếp A08).

### Điều kiện trước khi bật agent tự sinh chiến lược

| Điều kiện | Mục đích |
|---|---|
| Baseline đã đối chiếu, có phí và múi giờ | So sánh công bằng |
| Một thay đổi mỗi thí nghiệm, có điều kiện bác bỏ | Dễ giải thích và kiểm chứng |
| Dữ liệu kiểm tra riêng, không nhìn lại | Tránh tối ưu quá mức |
| Giới hạn số phương án và lịch chạy | Kiểm soát chi phí và mức thử |
| Lưu cả thử nghiệm thất bại | Không chỉ giữ phiên bản đẹp |
| Agent ở chế độ chỉ đọc/báo cáo | Tách nghiên cứu khỏi thực thi |

## 14. Checklist ngày khi vận hành agent

Checklist dùng cho ngày **làm việc với AI hoặc agent nghiên cứu** (Hermes, Trợ lý review, MCP backtest). Không thay thế checklist phiên giao dịch ở mục 9; hai danh sách này chạy song song. Tick ô nào bỏ qua cũng ghi rõ lý do (theo D03 — không tự điền đạt khi không kiểm tra).

### Trước phiên / trước khi mở phiên làm việc với agent

- [ ] Agent còn trực tuyến; các lịch đã khai báo (cron) thực thi đúng giờ, không bị bỏ hoặc chạy trùng (A07, H04).
- [ ] Baseline vẫn là phiên bản chuẩn; không có thay đổi nào ngoài hàng đợi đã duyệt (A05, H01).
- [ ] Dữ liệu nguồn còn đúng: cặp, khung giờ, nến đã đóng, cập nhật không bị cũ (D02).
- [ ] Đã ghi ngân sách chi phí (token, MCP, đám mây); không bật lịch mới ngoài kế hoạch (A09, H04).
- [ ] Quyền của agent (chỉ đọc/báo cáo) chưa bị thay đổi so với thiết lập đã chấp thuận (A03, H07).

### Khi agent đưa ra kết quả hoặc đề xuất

- [ ] Kết quả backtest truy ngược được về chiến lược, tham số cụ thể và dữ liệu đã dùng (H08, A02).
- [ ] Số thử nghiệm trong ngày và số thử nghiệm thất bại được lưu; không chỉ lưu bản đẹp nhất (T07).
- [ ] Mỗi đề xuất chỉ đổi một biến và có điều kiện bác bỏ đã viết trước (T05, H01).
- [ ] Dữ liệu kiểm tra chưa bị agent xem lại lặp để sửa quy tắc (T06).
- [ ] Kết luận không phụ thuộc vào câu trả lời thuyết phục hay dashboard đẹp; tách quan sát, giả thuyết, đã kiểm tra (A02, A06).

### Trước khi duyệt một đề xuất của agent

- [ ] Đề xuất là nghiên cứu (chỉ đọc); không tự đặt lệnh, không tăng giới hạn rủi ro, không sửa cấu hình thực thi (H07, A03, A04).
- [ ] So với baseline trên cùng ngân sách rủi ro, sau phí, funding và trượt giá (T08, D04).
- [ ] "Chưa đủ bằng chứng" được coi là kết quả hợp lệ; không ép mỗi phiên phải ra thay đổi (T10).
- [ ] Nếu đề xuất chạm tới thực thi thật: đợi quy trình chấp thuận riêng và có cách dừng, khôi phục phiên bản cũ (A04, A07).

### Sau phiên / cuối ngày

- [ ] Đối chiếu số lịch đã chạy với số báo cáo nhận được; ghi nhận lịch chạy lệch giờ hoặc trùng (A07).
- [ ] Kiểm tra agent có tự sửa cấu hình ngoài quyền không; ghi vi phạm (cả trường hợp có lời) và cách ngăn tái diễn (theo mẫu mục 10).
- [ ] Lưu nhận xét ngày: lỗi dữ liệu phát hiện, nghi vấn, câu hỏi cho review tuần.
- [ ] Ghi lại chi phí thực tế của ngày và so với ngân sách.
- [ ] Chọn một ưu tiên duy nhất cho ngày sau; không đổi baseline chỉ vì một ngày tốt/xấu (T01, T10).

### Theo lịch review tuần

- [ ] Đánh giá toàn bộ thử nghiệm mới theo kỳ vọng ròng, drawdown, số mẫu và độ bất định (T02, T03).
- [ ] Kiểm tra độ ổn định theo thời gian (và theo cặp/tài sản nếu có) thay vì một chỉ số đơn lẻ (T08).
- [ ] Giữ, loại bỏ hoặc thử giới hạn từng thay đổi có lý do bằng dữ liệu; không tối ưu một chỉ số (A02, T05).
- [ ] Đối chiếu mức thử nghiệm tăng lên bao nhiêu qua số lịch chạy — mức thử càng cao càng cần bằng chứng dữ liệu mới mạnh hơn (H01, H04).

## 15. Bổ sung từ Smart Money Concept — Setup A+ qua thanh khoản, cấu trúc và thời điểm

Các quy tắc dưới đây mở rộng phần chọn setup và điều kiện kiểm chứng khi bạn xem xét ngôn ngữ SMC. Điểm mấu chốt: hiện tượng nền (stop clustering, quét thanh khoản) có thật trong cơ chế khớp lệnh, nhưng lợi thế giao dịch của SMC chưa được chứng minh; phần định lượng từ video bắt buộc phải kiểm chứng trên dữ liệu cá nhân trước khi dùng.

### S01 — Thuật ngữ SMC không chuẩn hóa; viết định nghĩa trước khi đánh dấu vùng

Order block, CHoCH, BOS, FVG/imbalance có định nghĩa khác nhau giữa các giáo viên và thường trùng khái niệm tài chính cũ (hỗ trợ/kháng cự, breakout, vùng chưa cân bằng). Trước khi dùng, ghi rõ định nghĩa của bạn đủ cụ thể để chấm lại được; không dùng tên gọi làm giá trị.

### S02 — "Xác suất thắng cao khi đủ hợp lưu" là giả thuyết, cần số liệu

Không coi khung "A+" ba hợp lưu (thanh khoản + cấu trúc + thời điểm) là sự thật sẵn có. Cần ghi tần suất xuất hiện, win rate, phân phối tổn thất và kỳ vọng ròng trên dữ liệu của bạn, so với phương án không có hợp lưu (theo T05, T03).

### S03 — CHoCH/BOS "hợp lệ hay không" phải định nghĩa trước entry

Phân biệt "hợp lệ / không hợp lệ" trong video chủ yếu mô tả lại diễn biến đã biết. Nếu dùng, phải là quy tắc đủ rõ để hai người chấm cùng một kết quả trước khi biết hướng giá (nguyên tắc 7 — nhãn setup trước kết quả).

### S04 — Vùng/order block/FVG là suy diễn từ chart, không phải dữ liệu lệnh

Không thể nhìn thấy lệnh tổ chức trên chart giá; gọi nến thân lớn là order block là diễn giải chủ quan. Đo giá trị thêm của bộ lọc so với chỉ dùng hỗ trợ/kháng cự cổ điển thay vì coi nó là lý do đủ để vào lệnh (nối tiếp C02).

### S05 — Đo từng yếu tố hợp lưu riêng rồi mới đo tác động kết hợp

Đo giá trị của thanh khoản, cấu trúc và thời điểm mỗi yếu tố một mình; sau đó mới đo xem kết hợp có thêm lợi thế thật hay không. Mỗi vòng thí nghiệm chỉ đổi một biến (T05); nếu có tương tác giữa các biến thì ghi nhận riêng.

### S06 — Win rate cao không đồng nghĩa kỳ vọng dương

Minh họa: Liquidity Sweep thắng 71,9% số lần trong backtest cơ khí nhưng tổng kết vẫn lỗ do các lệnh thua lớn hơn. Luôn đo kỳ vọng ròng sau chi phí, không chỉ tỷ lệ thắng (chi tiết tại T03).

### S07 — Giờ phiên tối ưu là giả thuyết thanh khoản, cần đo theo cặp

Lời khuyên tránh cuối phiên, thứ Sáu hoặc "giờ chết" 4:00–7:00 sáng giờ VN hợp lý về tinh thần nhưng cần đo chất lượng setup theo cặp, sàn và thời gian thực thi của bạn (nối tiếp C09).

### S08 — Bonus sàn là tín dụng giao dịch có điều kiện, không phải vốn tự do

Bonus như của XM (100%/50%/20% tối đa 100/500/10.000 USD) theo điều khoản thường **không rút được**, rút tiền sẽ cắt bonus theo tỷ lệ, và chỉ nhận một lần. Không dùng con số quảng bá làm đầu vào sizing và không để "thêm vốn" trở thành lý do tăng rủi ro (R03, R07, R08).

### S09 — Không đổi hệ thống vì ví dụ SMC đẹp

Ba kịch bản minh họa trong video đều là short, được chọn sau khi giá đi xong. Nếu muốn thu thập bằng chứng SMC, thực hiện như thí nghiệm có đối chứng (giữ baseline, dữ liệu kiểm tra riêng, lưu cả thất bại) thay vì lấy mẫu nhỏ làm lý do thay chiến lược (nguyên tắc 5).

### S10 — Mục tiêu 2R và "vào khung nhỏ tối ưu R:R" là tham số cần backtest

Các ngưỡng "tối thiểu 2R", "stop gần nhờ vào lệnh khung nhỏ" là lựa chọn hình thức hợp lý, chưa phải tham số tối ưu. Kiểm chứng trên dữ liệu của bạn và không sao chép tỷ lệ từ video (kết nối R07).

### Những ngưỡng từ bài này vẫn cần kiểm chứng

| Ngưỡng/ý tưởng | Việc cần làm trước khi áp dụng |
|---|---|
| "A+ phải đủ ba hợp lưu thanh khoản + cấu trúc + thời điểm" | Định nghĩa trước; đo kỳ vọng ròng riêng của bạn và cơ hội bị lọc bỏ |
| Target tối thiểu 2R | Backtest trên dữ liệu mình; không lấy từ video |
| Tránh cuối phiên, thứ Sáu, 4:00–7:00 sáng VN | Đo chất lượng setup theo giờ/cặp của bạn (C09) |
| Order block / FVG là điểm vào mạnh | Định nghĩa máy móc được; so với hỗ trợ/kháng cự cổ điển |
| Bonus XM "không điều kiện ẩn" | Đọc T&Cs hiện hành; bonus không rút được, rút tiền cắt bonus tỷ lệ |

## 16. Tài liệu nguồn

- [Tổng hợp tâm lý trading và kế hoạch hành động](/Users/brokinv/Desktop/AI%20Agent/Trading/Tamly/Tong-hop-tam-ly-trading-va-ke-hoach-hanh-dong.md).
- [AI trading agent tự cải thiện — Hermes và kế hoạch hành động](/Users/brokinv/Desktop/AI%20Agent/Trading/Tamly/AI-trading-agent-tu-cai-thien-Hermes-va-ke-hoach-hanh-dong.md).

- [Chris Creamer — Bối cảnh, order flow và kiểm soát C-game](</Users/brokinv/Desktop/AI Agent/Trading/Tamly/Chris-Creamer-boi-canh-order-flow-va-kiem-soat-C-game.md>).

- [Hermes Agent desktop và sàn giao dịch AI tự động](/Users/brokinv/Desktop/AI%20Agent/Trading/Tamly/Hermes-Agent-desktop-va-san-giao-dich-AI-tu-dong.md).

- [Smart Money Concept và setup A+ — thanh khoản, cấu trúc và thời điểm giao dịch](/Users/brokinv/Desktop/AI%20Agent/Trading/Tamly/Smart-Money-Concept-A-setups-thanh-khoan-cau-truc-thoi-diem.md).

- [Spec & kết quả backtest Chiến lược C1, C2 (crypto Binance)](/Users/brokinv/Desktop/AI%20Agent/Trading/Tamly/spec-C1-C2.md).

- [Danh mục theo dõi crypto Binance — 07/09/2026](/Users/brokinv/Desktop/AI%20Agent/Trading/Tamly/danh-muc-theo-doi-crypto-binance.md).

- [Kiến trúc bộ công cụ trading — Hermes + ChatGPT + Claude](/Users/brokinv/Desktop/AI%20Agent/Trading/Tamly/kien-truc-bo-cong-cu-trading-hermes-chatgpt-claude.md).

Các quy tắc được biên tập từ các tài liệu trên để dễ áp dụng và review. Phần định lượng vẫn cần kiểm chứng bằng dữ liệu cá nhân; các nguồn đối chiếu và giới hạn của video được lưu trong tài liệu gốc.
