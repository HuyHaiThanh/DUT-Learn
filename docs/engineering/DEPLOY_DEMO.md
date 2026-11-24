# Bản demo trực tuyến (T15d)

Mục đích: cho người xem (GVHD) dùng thử luồng đọc → hỏi → mở nguồn qua một đường dẫn HTTPS luôn sẵn sàng, không phụ thuộc máy có GPU. Đây **không** là cấu hình thực nghiệm: số liệu trong quyển đo với Ollama + Qwen2.5-7B chạy cục bộ.

## Kiến trúc

- Một container (`deploy/hf-space/Dockerfile`): build web tĩnh + API FastAPI trên cùng một origin (`serve.py`), cổng 7860. Embedding `multilingual-e5-small` chạy CPU trong container (PyTorch bản CPU, mô hình nạp sẵn trong image).
- Nơi chạy: Google Cloud Run (`deploy/hf-space/deploy_cloud_run.ps1`), tối đa 1 instance, tự tắt khi không có người dùng. Lần mở đầu sau một thời gian không dùng phải chờ container khởi động. Hugging Face Docker/Gradio Space không còn gói CPU miễn phí cho tài khoản mới (11/2026), nên không dùng.
- CSDL: PostgreSQL có pgvector bên ngoài (Neon). Dữ liệu khôi phục từ bản dump của môi trường dev (tài khoản demo + học liệu đã ingest).
- LLM: API tương thích OpenAI (`DUT_LLM_PROVIDER=openai`), mặc định Groq `qwen/qwen3.8-27b`. Gói miễn phí giới hạn khoảng 8.000 token/phút và 1.000 yêu cầu/ngày; client chờ theo `Retry-After` (tối đa 2 lần, mỗi lần ≤ 20 s, trong ngân sách thời gian), quá mức thì trả `llm_busy`.
- Học liệu: chỉ file đang công bố trong `data/materials` được chép vào image (giáo trình VOER, CC BY 3.0). File tải lên trên bản demo nằm trên đĩa tạm của container, mất khi container khởi động lại.

## Biến môi trường (đặt khi deploy, không commit)

| Biến | Giá trị |
| --- | --- |
| `DUT_DATABASE_URL` | `postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require` — dùng endpoint **trực tiếp** của Neon, không dùng `-pooler` |
| `DUT_LLM_BASE_URL` | ví dụ `https://api.groq.com/openai/v1` |
| `DUT_LLM_API_KEY` | khóa API |
| `DUT_LLM_MODEL` | tên mô hình của nhà cung cấp |

Image đã đặt sẵn `DUT_LLM_PROVIDER=openai`, `DUT_COOKIE_SECURE=true`. Script deploy đọc `DEMO_NEON_URL` và `DUT_LLM_API_KEY` từ `.env` ở gốc repo, ghi ra file tạm và xóa sau khi deploy.

## Quy trình

1. Đổi mật khẩu mọi tài khoản mẫu trước khi dump (mật khẩu dev mặc định công khai trong repo).
2. `pg_dump -Fc --no-owner --no-privileges` CSDL dev → `CREATE EXTENSION vector` trên CSDL đích → `pg_restore --no-owner --no-privileges`. Sau khi restore qua pooler, đặt `ALTER DATABASE <db> SET search_path TO "$user", public` (pg_restore để lại `search_path` rỗng trong phiên mà pooler giữ lại).
3. `gcloud auth login`, rồi `./deploy/hf-space/deploy_cloud_run.ps1 -Project <id>`: script ghép thư mục build (`build_space.ps1` từ chối nếu có `.env`, `private/`, `evals/`), bật API Cloud Run/Cloud Build/Artifact Registry, build trên Cloud Build và deploy.
4. Kiểm: `GET /api/health` trả `db` và `llm` đều `true`; đăng nhập; hỏi một câu có trong giáo trình (có trích dẫn, mở được trang) và một câu ngoài giáo trình (từ chối); kiểm giao diện ở 1280 px và 360 px.

## Kiểm tra sơ bộ mô hình demo (22/11/2026)

Chạy 16 câu dev đã xác minh (14 trả lời được, 2 ngoài giáo trình) qua API thật, cùng CSDL và bộ truy xuất, mỗi câu cách 25 s để không chạm giới hạn token. Groq `qwen/qwen3.8-27b`: 11/14 câu trích đúng trang chấp nhận, 2/2 câu ngoài giáo trình bị từ chối, 0,6–3,1 s mỗi câu. Chỉ để chọn mô hình cho demo; không dùng làm số liệu thực nghiệm.
