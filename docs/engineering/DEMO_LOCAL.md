# Chạy demo DUTLearn tại máy

Dùng DB riêng cho buổi demo. Toàn bộ tài khoản và hoạt động được tạo là **Dữ liệu minh họa**.
Không dùng dữ liệu người thật. Học phần KTLT có sẵn sẽ được dùng lại.

1. Chuẩn bị Python 3.11, uv, Node.js, Docker và Ollama. Tại gốc repo:

   ```powershell
   $env:COMPOSE_PROJECT_NAME = 'dut_demo'
   $env:DUT_DB_PORT = '5435'
   $dbConnection = Read-Host 'Chuỗi kết nối PostgreSQL tới DB demo riêng (cổng 5435)' -AsSecureString
   $env:DUT_DATABASE_URL = [System.Net.NetworkCredential]::new('', $dbConnection).Password
   Remove-Variable dbConnection
   $env:UV_CACHE_DIR = 'D:/uv-cache'
   docker compose -f infra/docker-compose.yml up -d db
   cd services/api
   uv sync --frozen
   uv run alembic upgrade head
   ```

   Đợi DB healthy trước khi migrate. Chọn cổng chưa được worktree khác sử dụng.
   Chuẩn bị mô hình embedding theo cấu hình `DUT_EMBED_MODEL` khi xử lý PDF;
   đặt `HF_HOME` ở ổ D nếu cần. Ollama phục vụ trợ giảng tại `127.0.0.1:11434`:

   ```powershell
   ollama pull qwen2.5:7b-instruct
   ```

   Nếu Ollama chưa chạy, mở `ollama serve` ở cửa sổ riêng. Seed không gọi mô hình sinh.

2. Tại `services/api`, nhập mật khẩu riêng tối thiểu 10 ký tự; không ghi vào mã hay tài liệu:

   ```powershell
   $secret = Read-Host 'Nhập mật khẩu demo (ít nhất 10 ký tự)' -AsSecureString
   $env:DUT_DEMO_PASSWORD = [System.Net.NetworkCredential]::new('', $secret).Password
   uv run python -m app.demo_seed --pdf D:\path\to\voer_giao_trinh_lap_trinh_can_ban.pdf
   Remove-Item Env:DUT_DEMO_PASSWORD
   Remove-Variable secret
   ```

   PDF phải có lớp văn bản, được phép sử dụng. Có thể bỏ `--pdf`: seed cảnh báo và tạo
   các phần còn lại. Chạy lại không nhân đôi dữ liệu và giữ mật khẩu tài khoản đã có.
   Khi xử lý PDF thất bại, kiểm tra học liệu rồi chạy lại cùng lệnh.
   Tóm tắt cuối lệnh có email, mã lớp, liên kết `/lop/<class_id>` và số lượng dữ liệu.

3. Khởi động API và web trong hai cửa sổ, cùng cấu hình DB ở bước 1:

   ```powershell
   # Tại services/api
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

   ```powershell
   # Tại apps/web
   npm ci
   npm run dev
   ```

   Mở `http://127.0.0.1:5173`. Các email có đuôi `@demo.dutlearn.local`:
   `quantri` (quản trị), `gv.chau` (giảng viên), `sv.thao`, `sv.duc`, `sv.bao`, `sv.anh`.
   Dùng tài khoản `sv.anh` để thao tác trực tiếp vì chưa có bài nộp hay lượt luyện tập.
   Quản trị không được ghi danh vào lớp. Điểm 7,0 của Đức ở Bài 1 là nháp;
   chỉ giảng viên thấy. Câu luyện tập do giảng viên tạo; không có lịch sử chat AI giả.

Nếu cần xóa dữ liệu demo, dừng API/web và dựng lại **DB riêng dành cho demo**,
rồi migrate và seed lại. Kiểm tra đúng DB, project và volume trước khi thao tác;
không xóa DB đang dùng chung hay có dữ liệu cần giữ. Không có lệnh xóa tự động.
