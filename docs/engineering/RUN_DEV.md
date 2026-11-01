# Chạy DUTLearn trên Windows (PowerShell)

Yêu cầu: Python 3.11, uv, Node.js 22 trở lên, npm, Docker Desktop chạy Linux containers. Không cần tải model để chạy bộ khung. Ollama là dịch vụ native tùy chọn trên host.

## Chuẩn bị từ checkout sạch

Mở PowerShell tại gốc repo. Cache đặt trong worktree vì phiên thực thi T04 không được ghi cache mặc định trên ổ C:.

```powershell
$env:COMPOSE_PROJECT_NAME = 'dut_t04'
$env:DUT_DB_PORT = '5433'
$env:UV_CACHE_DIR = "$PWD/.codex-build/uv-cache"
$env:npm_config_cache = "$PWD/.codex-build/npm-cache"
$env:DUT_DATABASE_URL = 'postgresql+psycopg://dutlearn:dutlearn@127.0.0.1:5433/dutlearn'
$env:DUT_TEST_DATABASE_URL = 'postgresql+psycopg://dutlearn:dutlearn@127.0.0.1:5433/dutlearn_test'
docker info
docker compose -f infra/docker-compose.yml config --quiet
docker compose -f infra/docker-compose.yml up -d db
docker compose -f infra/docker-compose.yml ps
```

Đợi DB healthy trước khi chạy migration. DB `dutlearn_test` được tạo bởi script init khi volume mới khởi tạo lần đầu. Nếu dùng volume đã tồn tại trước khi thêm script, cần tạo riêng DB test; không xóa volume có dữ liệu để xử lý lỗi này. Tên project tách mạng và volume giữa các worktree; mỗi worktree đồng thời cần cổng host riêng.

```powershell
cd services/api
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Cấu hình mặc định đủ để chạy local. Có thể chép `.env.example` thành `.env` trong `services/api/` rồi chỉnh khi cần; biến môi trường của tiến trình ưu tiên hơn `.env`. Không commit `.env`. `HF_HOME` chỉ dành cho module embedding về sau, T04 không tải model.

Trong cửa sổ PowerShell khác, tại gốc repo:

```powershell
$env:npm_config_cache = "$PWD/.codex-build/npm-cache"
cd apps/web
npm ci
npm run dev
```

Mở `http://127.0.0.1:5173`. Vite chuyển `/api` đến `127.0.0.1:8000`. Trang chủ hiển thị kết nối DB và Ollama, có thông báo đang tải/lỗi và nút kiểm tra lại.

Script rút gọn tại gốc repo: `./scripts/dev.ps1` khởi động DB, đợi healthy, đồng bộ backend và chạy migration; sau đó in lệnh chạy API/web. Nếu DB lỗi, script dừng ngay.

## Nghiệm thu

Giữ các biến môi trường ở bước chuẩn bị. Tại gốc repo chạy `./scripts/check.ps1`; script dừng ngay khi có lệnh lỗi. Các lệnh tương đương:

```powershell
cd services/api
uv run ruff check .
uv run mypy app
uv run pytest
cd ../../apps/web
npm run lint
npm run typecheck
npm test
npm run build
```

Test DB bắt buộc dùng `DUT_TEST_DATABASE_URL` trỏ vào database có hậu tố `_test`. Mỗi phiên tạo schema UUID riêng, chạy migration thật rồi xóa schema trong teardown. Không tự thay DB thật bằng mock hoặc bỏ qua test khi thiếu DB. Các test health giả lập HTTP Ollama để kết quả ổn định; bước native sau đây kiểm chứng kết nối Ollama thật:

```powershell
$response = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 15
$response.StatusCode
$response.Headers['X-Request-ID']
$response.Content
```

Compose đầy đủ (API tự migrate khi khởi động, web được build tĩnh qua nginx):

```powershell
docker compose -f infra/docker-compose.yml --profile full up -d --build
```

Mở `http://127.0.0.1:8080`. Mật khẩu Compose là giá trị phát triển local; cổng DB/API/web chỉ bind loopback.

Kiểm chứng ADR-09 từ đúng mạng Compose:

```powershell
docker run --rm --network dut_t04_default --add-host host.docker.internal:host-gateway curlimages/curl --max-time 5 -sS http://host.docker.internal:11434/api/version
```

Nếu kết nối Ollama từ container thất bại, kiểm tra quyền Docker trước, sau đó mới kiểm tra địa chỉ listen và firewall của Ollama với người quản lý máy. Không tự đổi cấu hình host. Native `llm:true` chưa chứng minh container truy cập được Ollama.

## Bằng chứng nghiệm thu T04 (01/11/2026)

Agent Codex tạo mã trong sandbox (bị chặn Docker, subprocess esbuild và metadata Git). Tech Lead chạy lại nghiệm thu ngoài sandbox trên cùng máy:

- `docker compose -f infra/docker-compose.yml up -d db` (`COMPOSE_PROJECT_NAME=dut_t04`, `DUT_DB_PORT=5433`): container healthy.
- `uv run alembic upgrade head` trên DB trống: tạo `alembic_version`, `users`, `sessions`; extension `vector` 0.8.7.
- `uv run ruff check .`: `All checks passed!`; `uv run mypy app`: `Success: no issues found in 16 source files`.
- `uv run pytest -q` với `DUT_TEST_DATABASE_URL`: `7 passed, 2 warnings`.
- `npm ci`, `npm run lint`, `npm run typecheck`: đạt; `npm test`: `2 passed`; `npm run build`: thành công.
- ADR-09: `docker run --rm --add-host host.docker.internal:host-gateway curlimages/curl -sS http://host.docker.internal:11434/api/version` → `{"version":"0.40.13"}` (Ollama native bind mặc định, không đổi cấu hình host).
- Chưa kiểm chứng: `docker compose --profile full` build API/web, giao diện trên trình duyệt, GitHub CI.

## Tài khoản mẫu (T05, chỉ dùng phát triển)

Sau migration, tại `services/api` chạy `uv run python -m app.seed`. Chạy lại không tạo trùng và không đổi mật khẩu/tài khoản đã tồn tại. Đặt `DUT_SEED_PASSWORD` trước lần seed đầu; mặc định dev là `dutlearn-dev`. Không dùng seed hoặc mật khẩu mẫu cho triển khai thật.

| Email | Vai trò | Lớp |
| --- | --- | --- |
| admin@dutlearn.local | Admin | Không ghi danh, không mặc nhiên đọc nội dung lớp |
| gv1@dutlearn.local | Giảng viên | KTLT-01, KTLT-CLOSED |
| gv2@dutlearn.local | Giảng viên | KTLT-02 |
| sv1@dutlearn.local | Sinh viên | KTLT-01, KTLT-CLOSED |
| sv2@dutlearn.local | Sinh viên | KTLT-01 |
| sv3@dutlearn.local | Sinh viên | KTLT-02 |
| sv4@dutlearn.local | Sinh viên | KTLT-02 |

Môn `KTLT` — Kỹ thuật lập trình; học kỳ `2026-2027.1`. `KTLT-CLOSED` là lớp đóng: sinh viên không đọc được; danh sách `/api/classes` chỉ trả lớp mở.

Phiên mặc định 12 giờ (`DUT_SESSION_TTL_HOURS`), cookie `dut_session` có HttpOnly/SameSite=Lax. Đặt `DUT_COOKIE_SECURE=true` khi dùng HTTPS; dev HTTP mặc định false. Mọi request ghi, kể cả đăng nhập/đăng xuất, cần `X-DUT-CSRF: 1`.
