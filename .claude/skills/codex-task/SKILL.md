---
name: codex-task
description: Giao một task lập trình DUTLearn cho agent Codex trong git worktree riêng, rồi nghiệm thu ngoài sandbox và commit. Dùng khi bắt đầu một task Txx có brief trong docs/engineering/tasks/.
---

# Giao task cho Codex và nghiệm thu

## 1. Chuẩn bị

- Brief `docs/engineering/tasks/<Txx>.md` phải có: mục tiêu, căn cứ, phạm vi file, phụ thuộc, tiêu chí nghiệm thu, test bắt buộc, chủ sở hữu file chung, mẫu báo cáo. Nếu thiếu, viết bổ sung trước.
- Phụ thuộc đã merge vào `main`. Hợp đồng `docs/engineering/CONTRACT_V0.md` cập nhật.

## 2. Worktree

```powershell
git worktree add -b feat/<Txx>-<slug> D:\Documents\DUT_LEARN\wt\<Txx> main
```

Mỗi worktree dùng `COMPOSE_PROJECT_NAME=dut_<txx>` và cổng DB riêng (`DUT_DB_PORT` = 5434, 5435…). Brief chưa commit thì sao vào worktree.

## 3. Chạy Codex

Codex CLI: `C:\Users\Admin\.vscode\extensions\openai.chatgpt-26.51021.22027-win32-x64\bin\windows-x86_64\codex.exe` (phiên bản có thể đổi khi extension cập nhật — tìm lại bằng Glob `**/bin/windows-x86_64/codex.exe` dưới `~/.vscode/extensions`).

```bash
codex exec -C "D:/Documents/DUT_LEARN/wt/<Txx>" -s workspace-write \
  -c sandbox_workspace_write.network_access=true -c model_reasoning_effort="medium" - < prompt.txt > out.txt 2>&1
```

Chạy nền (`run_in_background`). Prompt ngắn: vai trò, đường dẫn brief, "không push/merge", "báo cáo theo mẫu kèm output thật". Review độc lập: cùng lệnh với `-s read-only` và brief review.

## 4. Nghiệm thu (bắt buộc, ngoài sandbox)

Sandbox chặn Docker, esbuild và metadata git, nên Claude tự chạy:

1. `docker compose -f infra/docker-compose.yml up -d db` → healthy; `uv run alembic upgrade head` trên DB trống.
2. `uv run ruff check . ; uv run mypy app ; uv run pytest` với `DUT_TEST_DATABASE_URL=...5433/dutlearn_test` (đổi cổng theo worktree).
3. `npm ci ; npm run lint ; npm run typecheck ; npm test ; npm run build`.
4. Đọc diff: đúng hợp đồng, quyền kiểm ở máy chủ, có test quyền, không secret, không file ngoài phạm vi.
5. Với UI: skill `ui-check`.
6. Ghi bằng chứng thật vào `docs/engineering/RUN_DEV.md` hoặc mô tả commit; nêu phần chưa kiểm.

Không tin câu "đã xong" của agent. Lỗi → gửi lại agent với lỗi cụ thể (`codex exec resume --last` trong worktree) hoặc tự sửa nhỏ.

## 5. Commit và tích hợp

- Commit trên nhánh task (`<Txx>: ...`, kèm dòng Co-Authored-By theo hướng dẫn hệ thống).
- `git merge --no-ff feat/<Txx>-...` vào `main`, chạy lại toàn bộ kiểm tra trên `main`.
- Dọn: `docker compose -p dut_<txx> down -v`, `git worktree remove D:\Documents\DUT_LEARN\wt\<Txx>`.
- Cập nhật Trello (thẻ việc tương ứng, bình luận bằng chứng) và tiến độ trong kế hoạch.
- Ghi một mục vào sổ tay chuẩn bị bảo vệ (tài liệu nội bộ, xem CLAUDE.local.md): quyết định, lý do, phương án khác, bằng chứng, câu hỏi phản biện có thể gặp.
