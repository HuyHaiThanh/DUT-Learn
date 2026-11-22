# Bản demo trực tuyến (T15d)

Mục đích: cho người xem (GVHD) dùng thử luồng đọc → hỏi → mở nguồn qua một đường dẫn HTTPS mà không cần máy có GPU. Đây **không** là cấu hình thực nghiệm: số liệu trong quyển đo với Ollama + Qwen2.5-7B chạy cục bộ.

## Kiến trúc

- Một container (`deploy/hf-space/Dockerfile`): build web tĩnh + API FastAPI trên cùng một origin (`serve.py`), cổng 7860. Embedding `multilingual-e5-small` chạy CPU trong container (PyTorch bản CPU).
- CSDL: PostgreSQL có pgvector bên ngoài (ví dụ Neon). Dữ liệu khôi phục từ bản dump của môi trường dev (tài khoản demo + học liệu đã ingest).
- LLM: API tương thích OpenAI (`DUT_LLM_PROVIDER=openai`).
- Học liệu: chỉ file đang công bố trong `data/materials` được chép vào image (giáo trình VOER, CC BY 3.0). File tải lên trên bản demo nằm trên đĩa tạm của container, mất khi container khởi động lại.

## Biến môi trường (đặt trong phần secrets của nền tảng, không commit)

| Biến | Giá trị |
| --- | --- |
| `DUT_DATABASE_URL` | `postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require` |
| `DUT_LLM_BASE_URL` | ví dụ `https://api.groq.com/openai/v1` |
| `DUT_LLM_API_KEY` | khóa API |
| `DUT_LLM_MODEL` | tên mô hình của nhà cung cấp |

Image đã đặt sẵn `DUT_LLM_PROVIDER=openai`, `DUT_COOKIE_SECURE=true`.

## Quy trình

1. Đổi mật khẩu mọi tài khoản mẫu trước khi dump (mật khẩu dev mặc định công khai trong repo).
2. `pg_dump --no-owner --no-privileges` CSDL dev → `pg_restore` vào CSDL đích (cần `CREATE EXTENSION vector` có sẵn).
3. `./deploy/hf-space/build_space.ps1` ghép thư mục build (script từ chối nếu có `.env`, `private/`, `evals/`).
4. Build và chạy image trên nền tảng có Docker (Hugging Face Docker Space, Google Cloud Run…), đặt các biến ở bảng trên.
5. Kiểm: `GET /api/health` trả `db` và `llm` đều `true`; đăng nhập; hỏi một câu có trong giáo trình (có trích dẫn, mở được trang) và một câu ngoài giáo trình (từ chối).
