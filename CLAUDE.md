# DUTLearn — hướng dẫn cho Claude Code

Đồ án tốt nghiệp cá nhân: **Xây dựng nền tảng học tập tích hợp trợ giảng AI cho sinh viên công nghệ thông tin** (sản phẩm DUTLearn). Claude là PM/Tech Lead; agent Codex viết mã theo brief; người thực hiện quyết định phạm vi, review và viết quyển.

## Nguồn sự thật

- Phạm vi: đề cương đã chốt (không mở rộng/đổi tên đề tài).
- Hợp đồng kỹ thuật: [docs/engineering/CONTRACT_V0.md](docs/engineering/CONTRACT_V0.md). Không đổi schema/API/quyền mà không cập nhật file này.
- Cách chạy: [docs/engineering/RUN_DEV.md](docs/engineering/RUN_DEV.md). Brief task: `docs/engineering/tasks/<Txx>.md`.
- Kế hoạch, đề cương, nghiên cứu, báo cáo nằm trong `private/` (bị Git bỏ qua) — xem `CLAUDE.local.md`.

## Cấu trúc

```text
services/api/   FastAPI + SQLAlchemy + Alembic + pytest (uv)
apps/web/       React + TypeScript + Vite (npm)
infra/          docker-compose (PostgreSQL 16 + pgvector; profile full: api + web)
evals/          thực nghiệm AI (evals/runs/ bị ignore)
scripts/        check.ps1, dev.ps1
docs/engineering/  tài liệu kỹ thuật công khai
private/        tài liệu nội bộ (ignore)
```

## Lệnh

```powershell
$env:COMPOSE_PROJECT_NAME='dut_main'; docker compose -f infra/docker-compose.yml up -d db
cd services/api; uv run alembic upgrade head; uv run pytest      # cần DUT_TEST_DATABASE_URL
cd apps/web; npm run lint; npm run typecheck; npm test; npm run build
./scripts/check.ps1                                               # toàn bộ kiểm tra
```

Ollama chạy native: `$env:OLLAMA_MODELS='D:\ollama-models'; ollama serve` — model `qwen2.5:7b-instruct` (Q4_K_M). Cache đặt ở ổ D: (`HF_HOME=D:/hf-cache`, `UV_CACHE_DIR=D:/uv-cache`) vì ổ C: ít chỗ.

## Quy tắc bắt buộc

- Quyền kiểm ở máy chủ; truy xuất chỉ lấy học liệu đã công bố, còn hiệu lực, đúng lớp (bất biến I1–I7 trong hợp đồng). Thay đổi chạm quyền/truy xuất phải có test quyền.
- Repo GitHub **công khai**: không commit `private/`, `data/`, `.env`, học liệu riêng, dữ liệu sinh viên, model weights.
- Không báo "xong" khi chưa chạy kiểm tra thật; phân biệt mock với tích hợp thật; ghi rõ phần chưa kiểm.
- Commit theo task (`T05: ...`) trên nhánh `feat/<task>`; merge vào `main` sau khi nghiệm thu. Không push nếu người thực hiện chưa yêu cầu.
- Văn bản cho người dùng và giao diện bằng tiếng Việt; mã và commit message bằng tiếng Anh.

## Làm việc với Codex

Dùng skill `codex-task`. Sandbox Codex trên Windows chặn Docker, subprocess của esbuild/Vite và metadata git worktree → Codex viết mã và chạy test không cần DB; Claude chạy nghiệm thu đầy đủ và commit bên ngoài sandbox.

## Giao diện

React + Vite + Tailwind CSS + shadcn/ui (thêm ở task T06). Dùng skill `frontend-design` khi dựng màn hình, MCP `shadcn` để tra component, MCP `playwright` (Edge, isolated) để kiểm tra trên trình duyệt ở 1280 px và 360 px, MCP `context7` để tra tài liệu thư viện đúng phiên bản. Skill `ui-check` mô tả quy trình kiểm tra giao diện.
