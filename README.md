# DUTLearn

Đề tài: **Xây dựng nền tảng học tập tích hợp trợ giảng AI**.

DUTLearn là dự án đồ án tốt nghiệp xây dựng nền tảng web kết nối học liệu, trợ giảng AI, bài tập, luyện tập và phản hồi của giảng viên. Sinh viên có thể đọc tài liệu và đặt câu hỏi ngay trong ngữ cảnh bài học; giảng viên kiểm soát học liệu, câu luyện tập và kết quả đánh giá được công bố.

**Trạng thái ngày 17/10/2026:** đã chuẩn bị bản dự thảo đề cương, kế hoạch chi tiết và bảng Trello. Ứng dụng chưa được triển khai; chức năng, kiến trúc và phép đánh giá bên dưới là kế hoạch thực hiện. Tên đề tài, phạm vi và môn thí điểm đang chờ thống nhất với giảng viên hướng dẫn.

## Liên kết dự án

| Nội dung | Liên kết |
| --- | --- |
| Kho mã nguồn | [HuyHaiThanh/DUT-Learn](https://github.com/HuyHaiThanh/DUT-Learn) |
| Công việc và tiến độ | [Trello DUTLearn](https://trello.com/b/Eqscsjcw/dutlearn) |

Tên sản phẩm thống nhất là **DUTLearn**; tên repository và đường dẫn GitHub hiện giữ nguyên `DUT-Learn`.

## Mục tiêu

- Hỗ trợ sinh viên học theo tài liệu môn học, nhận giải thích và gợi ý từng bước, mở được nguồn để kiểm tra câu trả lời.
- Kết nối hoạt động đọc học liệu, giao–nộp bài, luyện tập và phản hồi trong cùng một nền tảng.
- Giữ quyền quyết định nội dung công bố và điểm chính thức ở giảng viên.
- Đánh giá chất lượng trợ giảng bằng dữ liệu và thực nghiệm có thể kiểm tra lại, cùng độ trễ, tài nguyên và giới hạn của hệ thống.

## Phạm vi phiên bản đồ án

Bản cơ sở tập trung vào **một môn/lớp thí điểm**, tài khoản cấp sẵn và học liệu PDF có lớp văn bản, được phép sử dụng. Môn học, học liệu và người tham gia được xác nhận trước khi thí điểm. Hệ thống có ba vai trò:

| Vai trò | Chức năng dự kiến trong bản cơ sở |
| --- | --- |
| Sinh viên | Xem lớp/bài học được cấp quyền; đọc PDF; hỏi trợ giảng và mở nguồn; nhận gợi ý; nộp bài văn bản; làm câu luyện tập đã duyệt; xem phản hồi và tiến độ. |
| Giảng viên | Quản lý lớp phụ trách; tải, kiểm tra và công bố học liệu; giao bài với tiêu chí ngắn; phản hồi/chấm bài thủ công; duyệt câu luyện tập; xem tổng hợp hoạt động lớp. |
| Quản trị | Cấp tài khoản, phân vai và quản lý danh mục môn/lớp bằng công cụ nội bộ tối thiểu. |

Các nguyên tắc chính:

- Trợ giảng chỉ sử dụng nguồn còn hiệu lực, được công bố và nằm trong quyền truy cập của người hỏi.
- Trích dẫn được máy chủ kiểm tra và mở về đúng tài liệu, phiên bản, trang hoặc đoạn tương ứng. Mức nguồn hỗ trợ câu trả lời được đánh giá riêng.
- Khi thiếu bằng chứng, trợ giảng thông báo giới hạn hoặc hỏi lại; đáp án riêng của giảng viên không được đưa vào ngữ cảnh sinh viên.
- AI không tự công bố điểm chính thức. Câu luyện tập phải được giảng viên duyệt trước khi sử dụng.
- Tiến độ phân biệt hoạt động đã xem, đã nộp và kết quả làm bài; việc mở tài liệu không tự chứng minh người học đã hiểu bài.

## Hướng kỹ thuật dự kiến

| Thành phần | Lựa chọn ban đầu |
| --- | --- |
| Giao diện web | React, TypeScript, Vite; trình đọc PDF và khung trợ giảng theo ngữ cảnh. |
| Dịch vụ nghiệp vụ và AI | Python, FastAPI; tách các mô-đun tài khoản, môn/lớp, học liệu, bài tập, trợ giảng, luyện tập và tiến độ. |
| Dữ liệu | PostgreSQL, pgvector; lưu quan hệ nghiệp vụ, phiên bản nguồn và chỉ mục véc-tơ. |
| Xử lý học liệu | Trích xuất theo trang → chia đoạn → embedding → tạo chỉ mục → kiểm tra và công bố; hỗ trợ thay thế/thu hồi phiên bản. |
| Truy xuất | Cấu hình cơ sở dùng tìm kiếm ngữ nghĩa; so sánh với tìm kiếm kết hợp BM25 và ngữ nghĩa. |
| Kết nối mô hình | Adapter cho runtime local; giới hạn thời gian, số yêu cầu đồng thời và độ dài đầu vào/đầu ra. |
| Tác vụ nền | Worker Python và trạng thái job trong PostgreSQL; thử lại có giới hạn và chống tạo dữ liệu trùng. |
| Vận hành | Ưu tiên chạy cục bộ, phần mềm mã nguồn mở và tài nguyên sẵn có; chọn mô hình sau phép thử chất lượng và phần cứng. |

Luồng hỏi đáp dự kiến:

```text
Sinh viên đọc bài và đặt câu hỏi
  → API kiểm tra phiên, lớp và quyền nguồn
  → Truy xuất các đoạn học liệu được phép
  → Mô hình tạo câu trả lời hoặc gợi ý
  → Máy chủ kiểm tra thông tin trích dẫn
  → Hiển thị câu trả lời, giới hạn và nguồn để mở lại
```

Các công nghệ trên chưa được cài đặt hoặc khóa phiên bản trong repo. Cấu hình cuối cùng được chốt sau thử nghiệm tương thích và benchmark trên máy thực tế.

## Kế hoạch triển khai

Dự án thực hiện cá nhân với năng lực dự kiến **15–20 giờ/tuần**. Kế hoạch cơ sở dùng mức 15 giờ: **12 giờ công việc + 3 giờ dự phòng mỗi tuần**, trong 12 tuần từ **19/10/2026 đến 10/01/2027**. Tổng cộng 144 giờ công việc và 36 giờ dự phòng.

| Giai đoạn | Thời gian | Đầu ra dự kiến |
| --- | --- | --- |
| W01–W02 | 19/10–01/11/2026 | Hoàn thiện đề cương; chuẩn bị corpus và benchmark máy; thiết kế dữ liệu, khởi tạo nền tảng và phân quyền. |
| W03–W05 | 02–22/11/2026 | Môn/lớp, học liệu riêng tư, trình đọc PDF, xử lý tài liệu và demo đọc → hỏi → mở nguồn. |
| W06 | 23–29/11/2026 | Bộ phát triển 36 trường hợp; đo baseline; hoàn thành báo cáo lần 1 trước hạn 28/11. |
| W07 | 30/11–06/12/2026 | Truy xuất kết hợp, xử lý thiếu nguồn, gợi ý và kiểm thử quyền/chỉ dẫn đánh lừa. |
| W08–W09 | 07–20/12/2026 | Giao–nộp–phản hồi bài; câu luyện tập có duyệt; ghi nhận sự kiện và dashboard tiến độ. |
| W10 | 21–27/12/2026 | Khóa 24 trường hợp kiểm tra; so sánh hai cấu hình truy xuất; kiểm thử lỗi, chống trùng và sao lưu. |
| W11–W12 | 28/12/2026–10/01/2027 | Báo cáo lần 2, kiểm thử tích hợp, hoàn thiện kết quả, chạy từ checkout sạch, phục hồi, quyển báo cáo và slide/demo. |

Các mốc học vụ theo kế hoạch đã đối chiếu; thời điểm nộp và bảo vệ cụ thể thực hiện theo thông báo của khoa/GVHD:

| Mốc | Khoảng thời gian |
| --- | --- |
| Đề cương có xác nhận GVHD | 19–31/10/2026 |
| Báo cáo tiến độ lần 1 | 23–28/11/2026 |
| Báo cáo tiến độ lần 2 | 28/12/2026–02/01/2027 |
| Khóa bản nộp nội bộ | Mục tiêu 10/01/2027 |
| Nộp đồ án và phản biện | 11–16/01/2027 |
| Bảo vệ | Từ 18/01/2027, theo lịch được phân công |

Tuần nộp và bảo vệ dành cho thủ tục, sửa lỗi trọng yếu và diễn tập. Phần giờ tăng thêm ưu tiên bù sai lệch, dữ liệu và chất lượng trước khi cân nhắc tính năng mới.

## Theo dõi trên Trello

[Bảng DUTLearn](https://trello.com/b/Eqscsjcw/dutlearn) có 67 thẻ kế hoạch: 1 tổng quan, 6 mốc, 12 tuần, 36 việc cốt lõi và 12 gói dài hạn. Cấu trúc này đã được kiểm tra trên giao diện ngày 17/10/2026; trạng thái công việc thay đổi theo quá trình triển khai.

- Bắt đầu từ **PLAN-000** để xem phạm vi và cách vận hành, sau đó mở **W01**.
- **W01–W12:** ba việc mỗi tuần, checklist và liên kết đến thẻ chi tiết.
- **CORE-001–CORE-036:** bước làm, phụ thuộc, ước lượng, hạn, tiêu chí đạt, kiểm chứng và bằng chứng cần lưu.
- Luồng thực hiện: **Backlog → Đang làm → Kiểm tra → Hoàn thành**. Chỉ đánh dấu hoàn thành khi có kết quả và bằng chứng đạt tiêu chí.
- **WP01–WP12:** lộ trình dài hạn gồm 72 việc, chưa cam kết ngày; có phần giao với CORE nên không cộng trùng tiến độ hoặc giờ.

## Đánh giá và nghiệm thu dự kiến

Câu hỏi thực nghiệm chính là ảnh hưởng của truy xuất kết hợp từ khóa và ngữ nghĩa so với truy xuất ngữ nghĩa đơn thuần đến khả năng tìm nguồn, độ đúng câu trả lời và tài nguyên sử dụng.

- Chuẩn bị 60 trường hợp thuộc sáu nhóm: tìm thông tin, giải thích, nối nguồn, gợi ý, thiếu bằng chứng và quyền/chỉ dẫn đánh lừa.
- Tách theo họ câu hỏi thành **36 trường hợp phát triển và 24 trường hợp kiểm tra**; khóa tập kiểm tra trước phép đo cuối.
- Giữ cùng mô hình sinh, corpus và cách chấm khi so sánh cấu hình truy xuất.
- Đo Recall@5, độ đúng nội dung, nguồn mở đúng vị trí/phiên bản, mức nguồn hỗ trợ phát biểu, xử lý thiếu nguồn và từ chối nhầm.
- Đo thời gian phản hồi, tài nguyên và lỗi trong cấu hình phần cứng/tải được ghi rõ; lưu dữ liệu thô, cấu hình và kết quả từng nhóm.
- Kiểm thử luồng hai vai trò, cô lập lớp/người dùng, tài liệu bị thu hồi, thao tác gửi lặp và lỗi mô hình.

Đây là thiết kế đánh giá, chưa có số liệu thực nghiệm. Tập mẫu nhỏ và việc tự chấm phải được nêu trong giới hạn; chỉ báo cáo thử nghiệm có người dùng khi đã tổ chức thực tế.

## Các hướng phát triển sau bản cơ sở

Workflow nhiều bước và công cụ AI, thông tin nhớ có kiểm soát, đồ thị khái niệm, AI phản hồi bài theo rubric, reranking và tinh chỉnh mô hình là các nhánh có điều kiện trong lộ trình dài hạn. Chỉ chọn thêm sau khi bản cơ sở ổn định và có đủ thời gian, dữ liệu, tài nguyên.

Ứng dụng mobile riêng, SSO/đồng bộ hệ thống đào tạo, OCR/video và vận hành toàn trường nằm ngoài phạm vi nghiệm thu cơ sở của đồ án.

## Tài liệu và trạng thái repository

Hiện repository phục vụ chuẩn bị đề cương và kế hoạch; chưa có scaffold ứng dụng, bản demo hoặc lệnh cài/chạy được kiểm chứng.

Các tài liệu làm việc đang lưu cục bộ trong `docs/`:

| Tài liệu | Vị trí trong bản làm việc |
| --- | --- |
| Bản dự thảo đề cương theo mẫu | `docs/DE_CUONG_DATN_DUTLEAN.md` |
| Đề cương PDF để gửi GVHD | `docs/deliverables/DE_CUONG_DATN_DUTLEAN.pdf` |
| Kế hoạch triển khai chi tiết | `docs/KE_HOACH_CHI_TIET_DUTLEAN.md` và PDF tương ứng trong `docs/deliverables/` |
| Backlog có cấu trúc | `docs/DUTLEAN_BACKLOG.json` |
| Nội dung Trello và bản đối chiếu lần cập nhật | `docs/TRELLO_PUBLISHED_CARDS.json`, `docs/TRELLO_REMOTE_VERIFICATION.json`, `docs/TRELLO_UPDATE_STATUS.md` |

`docs/` hiện được bỏ qua bởi `.gitignore`, nên bảng trên mô tả file của bản làm việc local, chưa phải tài liệu đã xuất bản trên GitHub. Đề cương và kế hoạch PDF được gửi riêng cho GVHD; liên kết thư mục báo cáo sẽ bổ sung khi có địa chỉ và quyền truy cập được xác nhận.

Học liệu riêng, thông tin sinh viên, dữ liệu học tập, khóa API và cấu hình bí mật được giữ ngoài nội dung công khai. Repo và Trello chỉ dùng các bằng chứng được phép chia sẻ.
