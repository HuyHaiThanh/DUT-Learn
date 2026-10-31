# DUTLearn

Đề tài: **Xây dựng nền tảng học tập tích hợp trợ giảng AI cho sinh viên công nghệ thông tin**.

DUTLearn là dự án đồ án tốt nghiệp xây dựng nền tảng web kết nối học liệu, trợ giảng AI, bài tập, luyện tập và phản hồi của giảng viên. Sinh viên có thể đọc tài liệu và đặt câu hỏi ngay trong ngữ cảnh bài học; giảng viên kiểm soát học liệu, câu luyện tập và kết quả đánh giá được công bố.

**Trạng thái ngày 01/11/2026:** đề cương đã chốt. Đã có khung ứng dụng chạy được (FastAPI, React + Vite, PostgreSQL + pgvector, CI) và phép thử mô hình trên máy thật (Qwen2.5-7B-Instruct qua Ollama). Các chức năng nghiệp vụ và trợ giảng đang được xây dựng; phần mô tả chức năng và đánh giá bên dưới là phạm vi thực hiện, chưa phải kết quả đã đạt.

## Liên kết dự án

| Nội dung | Liên kết |
| --- | --- |
| Kho mã nguồn | [HuyHaiThanh/DUT-Learn](https://github.com/HuyHaiThanh/DUT-Learn) |
| Công việc và tiến độ | [Trello DUTLearn](https://trello.com/b/Eqscsjcw/dutlearn) |

## Mục tiêu

- Hỗ trợ sinh viên học theo tài liệu môn học, nhận giải thích và gợi ý từng bước, mở được nguồn để kiểm tra câu trả lời.
- Kết nối hoạt động đọc học liệu, giao–nộp bài, luyện tập và phản hồi trong cùng một nền tảng.
- Giữ quyền quyết định nội dung công bố và điểm chính thức ở giảng viên.
- Đánh giá chất lượng trợ giảng bằng dữ liệu và thực nghiệm có thể kiểm tra lại, cùng độ trễ, tài nguyên và giới hạn của hệ thống.

## Phạm vi phiên bản đồ án

Bản cơ sở tập trung vào **học liệu của một môn học**, tài khoản cấp sẵn, học liệu PDF có lớp văn bản hoặc văn bản thuần, được phép sử dụng.

| Vai trò | Chức năng |
| --- | --- |
| Sinh viên | Xem lớp/bài học được cấp quyền; đọc học liệu; hỏi trợ giảng và mở nguồn; nhận gợi ý từng bước; nộp bài văn bản; làm câu luyện tập đã duyệt; xem phản hồi, kết quả và tiến độ. |
| Giảng viên | Quản lý lớp phụ trách; tải, kiểm tra, công bố, thay và thu hồi học liệu; giao bài với tiêu chí; phản hồi và quyết định điểm; duyệt câu luyện tập do AI đề xuất; xem tổng hợp hoạt động lớp. |
| Quản trị | Cấp tài khoản, phân vai, quản lý danh mục môn/lớp và ghi danh. |

Nguyên tắc chính:

- Máy chủ kiểm tra quyền; trợ giảng chỉ dùng học liệu đã công bố, còn hiệu lực và nằm trong quyền truy cập của người hỏi.
- Trích dẫn được máy chủ kiểm tra và mở về đúng tài liệu, phiên bản, trang; mức nguồn hỗ trợ câu trả lời được đánh giá riêng.
- Khi thiếu căn cứ, trợ giảng nêu rõ giới hạn; đáp án riêng không đưa vào ngữ cảnh của sinh viên.
- AI không công bố điểm chính thức; câu luyện tập phải được giảng viên duyệt.
- Tiến độ dựa trên sự kiện thật, tách hoạt động và kết quả; không suy ra "hiểu bài" từ số lần truy cập.

Ngoài phạm vi: ứng dụng di động riêng, OCR/video, SSO hoặc đồng bộ hệ thống đào tạo, chấm bài lập trình tự động, huấn luyện mô hình từ đầu, triển khai toàn trường.

## Kiến trúc

| Thành phần | Công nghệ |
| --- | --- |
| Giao diện | React, TypeScript, Vite, Tailwind CSS, shadcn/ui, pdf.js |
| API | Python 3.11, FastAPI, SQLAlchemy, Alembic |
| Dữ liệu | PostgreSQL 16 + pgvector |
| Xử lý học liệu | PyMuPDF → chia đoạn theo tokenizer → embedding `multilingual-e5-small` |
| Truy xuất | Ngữ nghĩa (cơ sở) và kết hợp BM25 + ngữ nghĩa (so sánh) |
| Mô hình sinh | Qwen2.5-7B-Instruct (Q4_K_M) qua Ollama, chạy cục bộ |
| Đóng gói | Docker Compose (DB, API, web); Ollama chạy trên máy chủ |

```text
Sinh viên đọc bài và đặt câu hỏi
  → API kiểm tra phiên, lớp và quyền nguồn
  → Truy xuất các đoạn học liệu được phép
  → Mô hình tạo câu trả lời hoặc gợi ý
  → Máy chủ kiểm tra trích dẫn và hiệu lực nguồn
  → Hiển thị câu trả lời, giới hạn và nguồn để mở lại
```

Chi tiết schema, API và quy tắc quyền: [docs/engineering/CONTRACT_V0.md](docs/engineering/CONTRACT_V0.md).

## Chạy thử

Yêu cầu: Windows 10/11, Docker Desktop, Python 3.11 + `uv`, Node.js 20+, Ollama. Hướng dẫn đầy đủ: [docs/engineering/RUN_DEV.md](docs/engineering/RUN_DEV.md).

```powershell
docker compose -f infra/docker-compose.yml up -d db
cd services/api; uv sync; uv run alembic upgrade head; uv run uvicorn app.main:app --port 8000
cd apps/web; npm ci; npm run dev     # http://localhost:5173
```

Kiểm tra toàn bộ: `./scripts/check.ps1`.

## Cấu trúc repository

```text
services/api/       API FastAPI, migration, test
apps/web/           Ứng dụng web
infra/              Docker Compose
evals/              Thực nghiệm AI (cấu hình, script, báo cáo)
scripts/            Kiểm tra và chạy dev
docs/engineering/   Hợp đồng kỹ thuật, hướng dẫn chạy, brief task
demo/               Prototype giao diện tĩnh ban đầu (dữ liệu minh họa)
```

## Lộ trình

| Mốc | Thời gian |
| --- | --- |
| Nền móng, xử lý học liệu, luồng hỏi–mở nguồn đầu tiên | 02–22/11/2026 |
| Báo cáo tiến độ lần 1 | 23–28/11/2026 |
| Truy xuất kết hợp, bài tập, luyện tập, tiến độ | 30/11–20/12/2026 |
| Thực nghiệm so sánh, độ bền, kiểm thử đầu-cuối | 21–27/12/2026 |
| Báo cáo tiến độ lần 2 | 28/12/2026–02/01/2027 |
| Khóa bản nội bộ | 10/01/2027 |
| Nộp, phản biện, bảo vệ | Từ 11/01/2027 theo lịch của khoa |

## Đánh giá

Câu hỏi thực nghiệm chính: truy xuất kết hợp BM25 + ngữ nghĩa so với truy xuất ngữ nghĩa ảnh hưởng thế nào đến khả năng tìm đúng nguồn, độ đúng câu trả lời và độ trễ, trong cùng mô hình sinh và corpus.

- **Truy xuất:** câu hỏi có tập trang nguồn chấp nhận; Hit@5 mức trang, MRR@10; so sánh từng cặp trên cùng câu hỏi.
- **Câu trả lời:** chấm theo rubric (độ đúng, mức nguồn hỗ trợ, xử lý câu thiếu căn cứ, từ chối nhầm), người chấm không biết cấu hình.
- **An toàn và quyền:** kiểm thử tự động cho truy cập khác lớp, tài liệu thu hồi, đáp án riêng, chỉ dẫn đánh lừa.
- Dữ liệu phát triển và kiểm tra tách theo chủ đề; tập kiểm tra khóa trước phép đo cuối; lưu cấu hình và đầu ra thô.

Phép thử ban đầu trên máy thật: [evals/ex01/REPORT.md](evals/ex01/REPORT.md).

Học liệu riêng, thông tin sinh viên, dữ liệu học tập, khóa API và cấu hình bí mật không được đưa vào repo.
