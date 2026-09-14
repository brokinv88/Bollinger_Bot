# AI trading agent tự cải thiện: hiểu đúng Hermes và kế hoạch hành động

Ngày tổng hợp: 07/09/2026.  
Đối tượng: trader full-time muốn dùng AI để học từ lịch sử giao dịch và cải thiện phương pháp.  
Nguồn chính: transcript người dùng cung cấp, mở đầu bằng “The holy grail for AI trading agents is having an agent that's able to learn from its mistakes…”.

> Tài liệu phân biệt ba lớp: lời tác giả nói, thông tin công cụ được đối chiếu và đề xuất áp dụng. Transcript không kèm prompt triển khai đầy đủ, mã nguồn, dữ liệu hay báo cáo hiệu suất được kiểm toán. Chưa có căn cứ kết luận agent trong video đã cải thiện lợi nhuận giao dịch thật.

## 1. Điều đáng nhớ nhất

Ý tưởng hữu ích của video là xây dựng vòng lặp có ghi chép:

**Chiến lược → kết quả → phân tích → giả thuyết → kiểm thử → xem xét cập nhật.**

Khác với việc hỏi AI từng câu rời rạc, hệ thống lưu lịch sử và bài học để sử dụng trong các lần làm việc tiếp theo.

Nhưng cần phân biệt:

- Ghi nhớ được nhiều hơn không đồng nghĩa hiểu thị trường đúng hơn.
- Tự viết lại quy tắc không đồng nghĩa tạo được lợi thế giao dịch.
- Chạy liên tục không đồng nghĩa vận hành đáng tin cậy.
- Backtest tốt hơn không đồng nghĩa kết quả tương lai tốt hơn.

Với bạn, ứng dụng đầu tiên đáng làm là **trợ lý phân tích nhật ký và đề xuất thí nghiệm**, sau đó mới cân nhắc tự động hóa những quyết định đã được kiểm chứng.

## 2. Video đang đề xuất điều gì?

Tác giả muốn tạo một agent hoạt động liên tục, quan sát kết quả chiến lược, tự phân tích sai sót và cập nhật cách làm nhằm tiến gần một mục tiêu định trước.

Hệ thống trong video gồm:

| Thành phần | Vai trò được mô tả |
|---|---|
| Claude Code | Hỗ trợ thiết lập môi trường, tập tin và triển khai qua một prompt dài |
| Hermes Agent | Lưu thông tin, review kết quả, hình thành bài học và đề xuất hoặc áp dụng thay đổi |
| Chiến lược Wacko Alpha | Hệ thống giao dịch sẵn có của tác giả, được mô tả là chiến lược momentum và yield |
| Railway | Máy chủ chạy dịch vụ khi máy tính cá nhân tắt |
| Cornelius | Agent khác điều chỉnh một nhóm tham số của chiến lược |
| Hồ sơ chiến lược và sổ giao dịch | Nguồn thông tin để đánh giá mục tiêu và kết quả |

Đây là kiến trúc tác giả trình diễn, không phải bộ thành phần bắt buộc để xây một trợ lý trading hữu ích.

## 3. Bốn tiêu chí tác giả đưa ra

### 3.1. Dữ liệu chính xác

Tác giả nhấn mạnh rằng AI có thể lấy hoặc diễn giải sai dữ liệu ngay cả khi các hệ thống được yêu cầu dùng cùng một nguồn.

Ý đúng: nếu dữ liệu đầu vào sai thì phân tích sau đó mất giá trị.

Tuy nhiên, API kết nối ổn định chưa đủ bảo đảm dữ liệu đúng. Với trading, cần kiểm tra:

- Đúng tài sản, sàn, cặp giao dịch và đơn vị giá.
- Múi giờ, thời điểm cập nhật và nến đã đóng hay chưa.
- Dữ liệu thiếu, trùng, cũ hoặc bất thường.
- Phí, funding, trượt giá và cách tính P&L.
- Lệnh khớp từng phần, vị thế đang mở và giao dịch đóng nhiều lần.

Với tin tức, phải tách sự kiện có nguồn và thời điểm rõ ràng khỏi diễn giải của AI. Hai agent đồng ý không phải bằng chứng rằng kết luận đúng.

### 3.2. Vận hành đáng tin cậy

Tác giả dùng máy chủ từ xa để chương trình không phụ thuộc máy tính cá nhân.

Đây là điều kiện hữu ích nhưng chưa đủ. Hệ thống còn cần biết khi nào dữ liệu ngừng cập nhật, lệnh gửi thất bại, API mất kết nối hoặc trạng thái tài khoản không khớp với sổ nội bộ.

Đặc biệt, thử gửi lại một yêu cầu sau lỗi không được vô tình tạo lệnh trùng. Khi khởi động lại, chương trình cần đối chiếu trạng thái thật trước khi hành động tiếp.

### 3.3. Mục tiêu và thất bại được định nghĩa rõ

Tác giả muốn agent biết thế nào là tiến bộ và thế nào là đi sai hướng. Các ví dụ gồm lợi nhuận, Sharpe và drawdown.

Bài học tốt là viết tiêu chí thành con số và điều kiện kiểm tra được. Nhưng chỉ đặt mục tiêu lợi nhuận cao có thể khiến hệ thống tăng rủi ro, giao dịch nhiều hoặc chọn một phương án vừa khít lịch sử.

Nên định nghĩa mục tiêu theo thứ tự:

1. Không vi phạm giới hạn vốn và vận hành.
2. Dữ liệu và phép đo đáng tin.
3. Có bằng chứng về hiệu quả sau chi phí trên dữ liệu mới.
4. Sau đó mới tối ưu lợi nhuận trong phạm vi đã chấp nhận.

Sharpe là thước đo lợi nhuận vượt mức tham chiếu so với độ biến động lợi nhuận, không đơn thuần là điểm lợi nhuận. Khi so sánh phải thống nhất cách lấy mẫu, quy đổi theo năm và chi phí; Sharpe cũng không phản ánh đầy đủ mọi rủi ro đuôi.

### 3.4. Tự cải thiện có phương pháp

Agent cần tổ chức thông tin, phân tích kết quả, đưa ra giả thuyết về nguyên nhân và đề xuất thay đổi để kiểm tra.

Tác giả khuyến nghị thay một biến mỗi lần. Đây là cách khởi đầu dễ theo dõi, nhưng phương pháp khoa học rộng hơn: giả thuyết có thể bị bác bỏ, dữ liệu phù hợp, đối chứng và kiểm tra lại trên dữ liệu mới. Đôi khi các biến tương tác với nhau, nên thay từng biến cũng có giới hạn.

Không nên coi cứ có phiên bản backtest tốt hơn là lập tức thay baseline. Cần tính đến bất định, số lần thử và kết quả ngoài mẫu.

## 4. Quy trình triển khai được trình diễn

Transcript mô tả hành trình sau; không cung cấp đủ nguyên văn tất cả các bước và prompt để tái lập chính xác:

1. **Kiểm tra môi trường:** xác định hệ điều hành và công cụ đang có.
2. **Xác định chiến lược:** dùng chiến lược sẵn có hoặc nhờ AI tạo bản đầu tiên.
3. **Viết hồ sơ:** tài sản, mục tiêu, thất bại, vị thế, trượt giá và lịch review.
4. **Tạo cấu trúc dữ liệu:** tổ chức thư mục, tài liệu và sổ giao dịch để Hermes đọc.
5. **Triển khai dịch vụ:** dùng Railway; tác giả phải đăng nhập thủ công khi phiên làm việc không hỗ trợ đăng nhập tương tác.
6. **Cài và bàn giao cho Hermes:** agent được kết nối với hồ sơ chiến lược và lịch sử.
7. **Chạy review ban đầu:** tạo báo cáo trước khi cho phép thay đổi chiến lược.

Các chi tiết được tác giả nêu:

- Chiến lược đã tích lũy khoảng 1,5 triệu điểm dữ liệu trong sáu đến tám tuần.
- Khi chuyển đổi sổ, có 24 giao dịch lời và 22 giao dịch lỗ được nhắc đến.
- Số vị thế tối đa là 12 trong cấu hình trình diễn.
- Dịch vụ chiến lược chạy theo chu kỳ 30 phút, có hoạt động điều chỉnh hằng ngày.
- Cornelius cập nhật một nhóm tham số hằng tuần.
- Hermes review hằng tuần, lệch Cornelius ba ngày.

Đây là thông số của tác giả. Không có bằng chứng trong transcript rằng chúng phù hợp với hệ thống của bạn.

## 5. Hermes thực sự “tự học” theo nghĩa nào?

Tài liệu chính thức mô tả Hermes có bộ nhớ và cơ chế tạo, tái sử dụng, cải thiện các kỹ năng dạng quy trình. Bộ nhớ lưu thông tin bền vững; kỹ năng lưu hướng dẫn dài hơn để dùng khi cần. [Tài liệu Hermes](https://hermes-agent.nousresearch.com/docs/) · [Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)

Có thể hình dung ba mức:

| Mức | Ví dụ | Chứng minh được điều gì? |
|---|---|---|
| Ghi nhớ | Nhớ bạn dùng múi giờ nào, cách ghi 1R | Làm việc nhất quán hơn |
| Cải thiện quy trình | Lưu cách đối chiếu phí và phát hiện dòng trùng | Có thể giảm lỗi vận hành hoặc phân tích |
| Cải thiện chiến lược | Đề xuất bộ lọc mới giúp tăng kỳ vọng trên dữ liệu mới | Cần bằng chứng giao dịch riêng |

Tài liệu về bộ nhớ và kỹ năng hỗ trợ hai mức đầu. Nó không tự chứng minh mức cuối. Cũng không nên hiểu rằng sau mỗi lần review, trọng số của mô hình ngôn ngữ được huấn luyện lại.

Ví dụ phù hợp: agent học rằng báo cáo broker ghi giờ UTC và sửa quy trình đọc dữ liệu. Ví dụ chưa đủ căn cứ: agent thấy ba lệnh breakout thua rồi kết luận breakout không hiệu quả và tự bỏ chiến lược.

## 6. Những điểm cần đọc với sự thận trọng

### 6.1. “Miễn phí” không đồng nghĩa toàn bộ hệ thống chạy miễn phí

Chi phí sử dụng mô hình, dữ liệu, máy chủ và giao dịch là các khoản riêng. Railway có cơ chế dùng thử hoặc hạn mức miễn phí cùng tính phí theo gói và tài nguyên; không nên suy từ lời tác giả rằng mọi agent chạy 24/7 đều miễn phí. [Railway Pricing](https://docs.railway.com/pricing) · [Pricing FAQs](https://docs.railway.com/pricing/faqs)

Cần đặt ngân sách vận hành và đo số lần gọi AI thực tế trước khi mở rộng. Chính sách dịch vụ có thể thay đổi.

### 6.2. Mục tiêu lợi nhuận trong transcript chưa nhất quán

Tác giả nói đến thử thách 50.000 bảng lên 500.000 bảng trong một năm, nhưng đoạn sau có nhắc 10 lần trong sáu tháng. Cũng có câu “4.7, which is 47%” mà không giải thích đơn vị.

Nếu dùng tỷ lệ thập phân thông thường, 47% là 0,47; 4,7 là 470%. Có thể đây là lỗi nói, phiên âm hoặc một quy ước riêng, nên không thể tự chọn một cách hiểu rồi đưa vào cấu hình.

Để thấy mức độ tham vọng: tăng vốn 10 lần trong 12 tháng cần khoảng 21,15%/tháng khi lãi kép đều; trong sáu tháng cần khoảng 46,78%/tháng. Đây chỉ là phép quy đổi toán học, không phải mức lợi nhuận nên đặt cho bạn.

### 6.3. Nhiều điểm dữ liệu không tương đương nhiều bằng chứng độc lập

1,5 triệu dòng dữ liệu có thể là giá hoặc lần cập nhật tương quan cao. Chúng không tương đương 1,5 triệu giao dịch độc lập.

46 giao dịch được nhắc trong sổ chỉ là một phần thông tin trình diễn; không đủ để kết luận chắc chắn về lợi thế bền vững. Cần biết thời gian, số cơ hội, số giao dịch đóng, điều kiện thị trường và phân phối kết quả.

### 6.4. Trạng thái “live” chưa rõ

Đầu video, tác giả nói chiến lược đang giao dịch tiền thật. Cuối video, lớp Hermes được mô tả là chỉ đọc và review ở vòng đầu, sau đó cần thay mode để cho phép ghi thay đổi. Có đoạn nói Hermes tự quyết định sẵn sàng, đoạn khác nói chủ tài khoản sẽ duyệt.

Cách đọc thận trọng: chiến lược nền có thể đã chạy thật, còn quyền sửa chiến lược của Hermes chưa được bật. Transcript chưa đủ để xác định chắc toàn bộ cơ chế. Không nên coi demo là bằng chứng một agent tự tối ưu đã giao dịch thật thành công.

### 6.5. Liên tục cải tiến dễ trở thành tối ưu quá mức

Thử nhiều phiên bản rồi chọn phiên bản đẹp nhất làm tăng nguy cơ chọn nhầm may mắn. Một tập kiểm tra cũng mất tính độc lập nếu được nhìn vào và dùng để sửa chiến lược lặp đi lặp lại. [Nghiên cứu về xác suất backtest overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)

Cần lưu cả thử nghiệm thất bại, kiểm tra theo thời gian và đo trên dữ liệu chưa dùng để chọn phương án. Tự động hóa việc thử làm vấn đề này quan trọng hơn.

### 6.6. Hai agent thay đổi khác nhóm tham số vẫn có thể ảnh hưởng lẫn nhau

Lệch lịch ba ngày không đủ tạo đối chứng. Bộ lọc thay đổi danh sách lệnh, còn phân bổ vốn thay đổi đóng góp của từng lệnh. Khi cả hai cùng đổi, khó biết yếu tố nào tạo ra kết quả.

Nên có một phiên bản chuẩn, một hàng đợi thay đổi và bản ghi rõ phiên bản nào tạo ra giao dịch nào.

### 6.7. Một prompt không thay thế thiết kế và kiểm chứng

Prompt có thể giúp dựng hệ thống nhanh, nhưng vẫn cần xác nhận kết quả thực tế: dữ liệu đúng, phép tính đúng, lịch chạy đúng và quyền truy cập đúng.

Tác giả bật chế độ bỏ qua yêu cầu quyền trong demo. Đây là lựa chọn thao tác của tác giả, không phải điều kiện bắt buộc của một agent hữu ích. Với hệ thống có thể chạm tới tiền thật, quyền sửa quy tắc và quyền đặt lệnh nên được kiểm soát riêng.

## 7. Liên hệ với bài tâm lý trading trước

Bài trước đặt câu hỏi: một quy tắc tâm lý có thật sự cải thiện kết quả của bạn không? Bài này đưa ra cách tự động hóa việc đặt và kiểm tra câu hỏi đó.

Nhưng AI cũng có thể khuếch đại lỗi tâm lý của trader:

| Lỗi quen thuộc | Khi đưa vào agent | Cách giảm lỗi |
|---|---|---|
| Đổi chiến lược sau vài lệnh thua | Agent sửa tham số sau mỗi chuỗi thua | Quy định lịch review và yêu cầu bằng chứng |
| Muốn gỡ nhanh | Đặt mục tiêu lợi nhuận buộc agent tăng rủi ro | Giới hạn rủi ro nằm ngoài quyền tự sửa |
| Chỉ nhớ giao dịch thắng | Bộ nhớ chỉ lưu thử nghiệm thành công | Lưu toàn bộ thử nghiệm và thất bại |
| Gắn nhãn A+ sau khi thắng | AI diễn giải lại setup theo kết quả | Lưu nhãn và thông tin trước entry |
| Tự tin vì backtest đẹp | Tự đưa phiên bản thắng backtest vào live | Kiểm tra dữ liệu mới và chạy quan sát trước |

Kỷ luật cần được thể hiện trong thiết kế vòng lặp nghiên cứu, không chỉ trong hành vi bấm lệnh.

## 8. Bạn nên bắt đầu với agent nào?

Đề xuất ban đầu: **trợ lý review giao dịch ở chế độ chỉ đọc**.

Nhiệm vụ:

1. Đọc lịch sử và đối chiếu số liệu với báo cáo broker.
2. Tính kết quả ròng, R, drawdown và chất lượng thực thi.
3. Tìm câu hỏi đáng nghiên cứu: sau chuỗi thua, theo giờ, theo nhóm setup.
4. Nêu giả thuyết cùng bằng chứng và điểm chưa biết.
5. Đề xuất tối đa một thay đổi ưu tiên cho vòng kiểm tra tiếp theo.

Lợi ích đầu tiên có thể là giảm thời gian review và giảm lỗi tính toán, dù chưa tạo thêm lợi nhuận. Đây là kết quả đo được và hữu ích cho công việc full-time.

Không cần bắt đầu bằng Hermes nếu quy trình dữ liệu và review hiện tại chưa ổn. Công cụ nên phục vụ quy trình đã được mô tả rõ.

## 9. Kiến trúc nên hướng tới nếu sau này triển khai

`Dữ liệu → kiểm tra chất lượng → sổ giao dịch → báo cáo → giả thuyết → kiểm thử → duyệt phiên bản → quan sát → áp dụng có giới hạn`

Ba vai trò cần phân biệt:

- **Bộ phận nghiên cứu:** đọc dữ liệu, giải thích và đề xuất.
- **Bộ kiểm tra rủi ro:** áp dụng giới hạn rõ ràng, không để phần nghiên cứu tự nới.
- **Bộ thực thi:** chỉ chạy phiên bản đã được chấp thuận, ghi đầy đủ kết quả.

Chúng có thể là các phần của một hệ thống; không nhất thiết phải là nhiều agent AI.

Nếu tới giai đoạn đặt lệnh thật, cần khả năng dừng, khôi phục phiên bản trước và kiểm tra trạng thái tài khoản sau sự cố. Dữ liệu ngoài như bài báo phải được coi là nội dung để phân tích, không phải chỉ dẫn được quyền sửa cấu hình.

## 10. Bộ dữ liệu tối thiểu

| Nhóm | Thông tin nên lưu |
|---|---|
| Nhận diện | Mã giao dịch, tài sản, sàn, hướng lệnh |
| Thời gian | Thời điểm tín hiệu, entry, exit và múi giờ |
| Kế hoạch | Setup, nhãn chất lượng trước entry, stop và rủi ro dự kiến |
| Thực tế | Giá khớp, khối lượng, đóng từng phần, phí, funding, P&L ròng |
| Bối cảnh | Điều kiện thị trường, vị thế liên quan đang mở |
| Hành vi | Tuân thủ, loại vi phạm, trạng thái trước lệnh |
| Phiên bản | Quy tắc và bộ tham số tạo ra giao dịch |
| Cơ hội bỏ qua | Setup hợp lệ không đánh và lý do |

Nếu thiếu một trường, agent phải ghi thiếu. Không tự suy ra nhãn A+ hoặc trạng thái cảm xúc từ kết quả lời/lỗ.

## 11. Đánh giá agent bằng gì?

### Chất lượng công việc

- Tổng P&L và phí có khớp nguồn gốc không?
- Có truy ngược kết luận tới từng giao dịch không?
- Có đánh dấu thiếu dữ liệu và bất định không?
- Có xử lý nhất quán giao dịch đóng từng phần không?
- Review có giúp tiết kiệm thời gian và phát hiện lỗi thực thi không?

### Chất lượng đề xuất chiến lược

- Hiệu quả sau mọi chi phí.
- Drawdown và tổn thất trong giai đoạn xấu.
- Số mẫu, độ bất định và độ ổn định theo giai đoạn.
- So sánh với baseline trên cùng ngân sách rủi ro.
- Kết quả dữ liệu mới và độ nhạy với thay đổi nhỏ của tham số.
- Số phương án đã thử trước khi chọn phương án thắng.

Không nên tối ưu một chỉ số đơn lẻ. Tăng lợi nhuận bằng tăng rủi ro không tự chứng minh agent tạo thêm lợi thế.

## 12. Lộ trình 30 ngày phù hợp

30 ngày dùng để xây quy trình và bắt đầu đo, không phải cam kết đủ thời gian xác nhận lợi thế.

### Tuần 1 — Viết rõ hệ thống hiện tại

- Chọn một setup hoặc chiến lược để nghiên cứu trước.
- Ghi entry, exit, điều kiện không giao dịch và cách sizing.
- Chuẩn hóa lịch sử và định nghĩa đơn vị R, phí, drawdown.
- Viết mục tiêu công việc của trợ lý: đối chiếu đúng, review nhất quán, đề xuất có bằng chứng.

**Đầu ra:** hồ sơ chiến lược và dữ liệu đã đối chiếu.

### Tuần 2 — Tạo baseline chỉ đọc

- Phân tích kết quả hiện tại, không sửa chiến lược.
- Kiểm tra một số giao dịch đối chiếu thủ công, gồm cả đóng từng phần và trường hợp bất thường.
- Tách lệnh đúng hệ thống khỏi lệnh vi phạm.
- Chọn một vấn đề có đủ dữ liệu để nghiên cứu.

**Đầu ra:** báo cáo baseline với điểm thiếu dữ liệu rõ ràng.

### Tuần 3 — Chạy một thí nghiệm có đối chứng

Ví dụ: “Sau hai lệnh thua, setup hợp lệ tiếp theo có kỳ vọng ròng thấp hơn bình thường không?”

- Viết giả thuyết trước khi xem kết quả chi tiết.
- Định nghĩa chính xác quy tắc nghỉ và thời điểm được quay lại.
- Chọn tiêu chí đánh giá và dữ liệu theo thời gian.
- Ghi cả tác động lên lợi nhuận, drawdown, số cơ hội và mức rủi ro.
- Giữ lại thử nghiệm thất bại.

**Đầu ra:** chấp nhận để kiểm tra thêm, bác bỏ hoặc chưa đủ bằng chứng. “Chưa biết” là kết quả hợp lệ.

### Tuần 4 — Theo dõi trên dữ liệu mới

- Giữ nguyên phiên bản thử nghiệm trong giai đoạn quan sát đã định.
- Ghi tín hiệu và kết quả song song, chưa để agent tự sửa hệ thống đang giao dịch.
- Đánh giá khác biệt giữa dự kiến và thực tế.
- Quyết định tiếp tục thu thập, loại bỏ hoặc thử ở phạm vi giới hạn khi đủ căn cứ.

**Đầu ra:** báo cáo tiến về phía trước và quyết định có lý do.

## 13. Mẫu yêu cầu cho trợ lý review

Đây là mẫu đề xuất cho nhu cầu của bạn, không phải prompt nguyên văn trong video và không phải prompt cài đặt Hermes.

```text
Bạn là trợ lý nghiên cứu và review giao dịch của tôi. Làm việc ở chế độ chỉ đọc.

Đầu vào gồm hồ sơ chiến lược và lịch sử giao dịch tôi cung cấp.

1. Kiểm tra định dạng, múi giờ, giao dịch trùng, thiếu dữ liệu, phí và cách ghép các lần khớp lệnh. Không tự điền thông tin không có.
2. Đối chiếu số lệnh, P&L ròng và phí với báo cáo nguồn. Nêu rõ phần chưa đối chiếu được.
3. Tạo baseline gồm kỳ vọng ròng, kết quả theo R nếu tính được, drawdown, số mẫu và phân phối kết quả. Nêu rõ giả định cho mọi phép tính.
4. Nếu dữ liệu cho phép, tách theo setup, giờ giao dịch, sau chuỗi thua và mức tuân thủ. Không gắn nhãn chất lượng dựa vào kết quả đã biết.
5. Chọn một giả thuyết ưu tiên. Phân biệt quan sát, giả thuyết nguyên nhân và kết luận đã kiểm tra.
6. Đề xuất một thí nghiệm có baseline, tiêu chí đánh giá, dữ liệu kiểm tra theo thời gian và điều kiện bác bỏ. Lưu số phương án đã thử và cả kết quả thất bại.
7. So sánh trên ngân sách rủi ro tương đương, có chi phí thực tế. Không coi lợi nhuận tăng do size lớn hơn là bằng chứng có thêm lợi thế.
8. Kết thúc bằng: điều đã biết; điều chưa biết; dữ liệu cần bổ sung; hành động tiếp theo.

Không đặt lệnh, không sửa cấu hình giao dịch đang chạy, không tăng giới hạn rủi ro. Khi mẫu chưa đủ, kết luận chưa đủ bằng chứng.
```

## 14. Hành động ưu tiên cho bạn

1. Gom hồ sơ của một chiến lược và lịch sử giao dịch có phí để xây baseline.
2. Dùng AI kiểm tra dữ liệu và review hành vi trước khi yêu cầu tối ưu lợi nhuận.
3. Chọn một câu hỏi từ bài tâm lý trước để nghiên cứu: nghỉ sau chuỗi thua, mục tiêu ngày hoặc chất lượng setup.
4. Chỉ mở rộng mức tự động hóa khi phép tính, dữ liệu và quá trình kiểm tra đã đáng tin.

Mục tiêu ban đầu nên là một hệ thống giúp bạn học chính xác hơn từ giao dịch. Quyền tự thay đổi chiến lược và giao dịch tiền thật là bước riêng, cần bằng chứng mạnh hơn việc một demo cài đặt chạy thành công.

## 15. Nguồn đối chiếu

- [Hermes Agent — tài liệu chính thức](https://hermes-agent.nousresearch.com/docs/): mô tả hệ thống agent, bộ nhớ và kỹ năng.
- [Hermes Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/): quan hệ giữa bộ nhớ và quy trình tái sử dụng.
- [Railway Pricing](https://docs.railway.com/pricing) và [Pricing FAQs](https://docs.railway.com/pricing/faqs): chi phí gói và tài nguyên.
- [Bailey và cộng sự — The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf): rủi ro chọn chiến lược qua nhiều thử nghiệm trên dữ liệu lịch sử.

Các nguồn công cụ được đối chiếu ngày 07/09/2026. Chúng xác nhận cơ chế và thông tin dịch vụ được dẫn, không xác nhận hiệu suất chiến lược trong video.
