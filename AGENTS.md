# Hướng dẫn cho agent Codex — DUTLearn

1. Đọc brief task được giao (`docs/engineering/tasks/<Txx>.md`) và `docs/engineering/CONTRACT_V0.md` trước khi sửa code. Chỉ sửa file trong phạm vi brief; file chung (`services/api/app/main.py`, `alembic/versions/`, `pyproject.toml`/`uv.lock`, `apps/web/package.json`) chỉ sửa khi brief giao quyền sở hữu.
2. Backend: Python 3.11, `uv`; chạy `uv run ruff check .`, `uv run mypy app`, `uv run pytest` trong `services/api`. Frontend: `npm run lint`, `npm run typecheck`, `npm test` trong `apps/web`.
3. Sandbox Windows có thể chặn Docker, subprocess esbuild và ghi metadata git. Khi bị chặn: ghi nguyên văn lỗi, không giả lập kết quả, không bỏ test; Tech Lead sẽ chạy lại ngoài sandbox.
4. Quyền luôn kiểm ở máy chủ qua hàm chung trong `app/auth`/`app/deps.py`; mọi chức năng chạm dữ liệu lớp/học liệu phải kèm test quyền (người ngoài lớp, sai vai trò, tài liệu thu hồi).
5. Không commit dữ liệu thật, `.env`, `data/`, model weights. Không thêm dependency ngoài brief khi chưa nêu lý do.
6. Báo cáo cuối bằng tiếng Việt theo mẫu: Thay đổi / File chính / Kiểm thử đã chạy (lệnh + kết quả thật) / Chưa kiểm tra / Rủi ro / Đề xuất đổi hợp đồng.
