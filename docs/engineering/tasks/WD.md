# W-D — Schema chung cho bài tập, luyện tập, sự kiện học + khung trang lớp

- Nhánh `feat/WD-shared-schema`, worktree `D:\Documents\DUT_LEARN\wt\WD`, tạo từ `main` (44c5915).
- Mục tiêu: dựng nền chung để ba task chạy song song mà không giẫm chân nhau:
  - T19–T20: bài tập, nộp, chấm, công bố;
  - T21a–T22: luyện tập do giảng viên soạn, sinh viên làm;
  - T23: sự kiện học và tiến độ.
- Căn cứ: hợp đồng `docs/engineering/CONTRACT_V0.md` §3 (bảng), §4 (quyền), §5 (API), **§5.2 (mới, đọc kỹ)**; các bất biến I1, I5, I6, I7.
- Không làm API nghiệp vụ hay màn hình thật của ba task trên.

## Phạm vi

### Máy chủ (`services/api`)

1. **Migration `alembic/versions/0006_assignments_practice_events.py`** (`down_revision` = 0005). Tạo 8 bảng theo §3 + §5.2:
   - `assignments`, `submissions`, `submission_versions`, `grade_revisions`, `practice_questions`, `practice_attempts`, `idempotency_keys`, `learning_events`.
   - CHECK cho mọi cột trạng thái/loại: `assignments.status`, `grade_revisions.status`, `practice_questions.kind/origin/status`, `learning_events.type`.
   - CHECK `grade BETWEEN 0 AND 10`, `version_no >= 1`, `revision_no >= 1`.
   - Các unique theo §3.
   - Index: `(class_id)` cho `assignments` và `practice_questions`; `(class_id, user_id)` cho `learning_events`; `(question_id, student_id)` cho `practice_attempts`.
   - FK tới `classes`, `lessons`, `users`, `chunks`, `material_versions` như §3. Khi xóa lớp hay bài học thì **không** cascade: dữ liệu học tập phải giữ lại.
   - `downgrade()` xóa đúng thứ tự.
2. **Models SQLAlchemy** theo phong cách `app/progress/models.py` hiện có:
   - `app/assignments/models.py`: `Assignment`, `Submission`, `SubmissionVersion`, `GradeRevision`;
   - `app/practice/models.py`: `PracticeQuestion`, `PracticeAttempt`;
   - `app/progress/models.py`: thêm `LearningEvent`;
   - `app/idempotency.py`: `IdempotencyKey`.

   Đăng ký các model ở nơi Alembic/metadata đang import model (xem `alembic/env.py` hoặc `app/db.py`).
3. **`app/idempotency.py`** (I7), API gợi ý:
   ```python
   def payload_hash(payload: Mapping[str, Any]) -> str
   def find(db, user_id, operation, key, payload) -> tuple[str, UUID] | None
       # same hash -> (ref_type, ref_id); different hash -> raise ApiError 409 idempotency_conflict
   def remember(db, user_id, operation, key, payload, ref_type, ref_id) -> None
       # add in caller's transaction; no commit
   ```
   Dùng cơ chế lỗi chuẩn hiện có (`app/errors.py`) để trả `{error:{code:"idempotency_conflict",...}}`. Có hàm `validate_key(key)`: 8–100 ký tự, nếu sai trả 422.
4. **`app/progress/events.py`**: `record_event(db, user_id, class_id, type, ref_type=None, ref_id=None)` theo §5.2; kiểu `type` là `Literal` khớp CHECK.
5. **Test** `tests/test_shared_schema.py`:
   - migration upgrade → downgrade → upgrade trên DB test (theo mẫu `test_migration_roundtrip` có sẵn);
   - ràng buộc CHECK và unique chặn dữ liệu sai: điểm 11, `status` lạ, nộp trùng `(assignment_id, student_id)`;
   - `idempotency`: cùng payload thì trả ref cũ, khác payload thì 409, key sai độ dài thì 422, hash không phụ thuộc thứ tự khóa;
   - `record_event` ghi đúng một dòng và không commit.

### Web (`apps/web`) — khung trang lớp có mục con

6. Tách tiêu đề lớp thành `pages/class/ClassLayout.tsx`, gồm:
   - liên kết quay lại, `h1` tên học phần, dòng "mã lớp · học kỳ";
   - **thanh mục con** (liên kết ngang, có `aria-current`, cuộn ngang nội bộ nếu hẹp, không tràn trang ở 320 px): "Bài học" (`/lop/:classId`, `end`), "Bài tập" (`/lop/:classId/bai-tap`), "Luyện tập" (`/lop/:classId/luyen-tap`), "Tiến độ" (`/lop/:classId/tien-do`).

   Layout dùng `useQuery(['class', classId])` sẵn có để có `course_name`/`code`/`term`/`role`, và truyền `{ classroom, me }` xuống qua `Outlet` context (kiểu `ClassOutletContext` export từ file layout). Xử lý 404/lỗi/đang tải **một lần** ở layout. Phần "Bài học" (nội dung hiện tại của `ClassPage`) bỏ tiêu đề trùng và lấy dữ liệu lớp từ context.
7. Route lồng trong `App.tsx`:
   ```text
   /lop/:classId            → ClassLayout
     index                  → ClassPage (Bài học)
     bai-tap/*              → pages/class/Assignments.tsx   (giữ chỗ)
     luyen-tap/*            → pages/class/Practice.tsx      (giữ chỗ)
     tien-do                → pages/class/Progress.tsx      (giữ chỗ)
   ```
   Mỗi file giữ chỗ export một component hiện `h2` tên mục và đoạn "Mục này đang được xây dựng." Ba task sau **chỉ sửa file của mình** (và route con `*` bên trong), không sửa `App.tsx`.
8. Kiểu dùng chung `apps/web/src/api/types.ts`: không thêm gì ngoài kiểu context nếu cần.
9. Test web: cập nhật test `ClassPage` hiện có cho khớp layout mới (giữ nguyên các khẳng định hành vi), thêm test thanh mục con (4 liên kết, `aria-current` đúng mục; 404 ở layout hiện thông báo cũ).

## Không làm

- Không viết router API cho bài tập, luyện tập hay tiến độ.
- Không sửa `CONTRACT_V0.md`: §5.2 đã do Tech Lead viết.
- Không thêm thư viện.

## Nghiệm thu

- `uv run ruff check . ; uv run mypy app ; uv run pytest` (Tech Lead chạy với DB).
- `npm run lint ; npm run typecheck ; npm test ; npm run build`. Sandbox có thể chặn: ghi nguyên văn lỗi.
- Không push, không merge, không commit.

## Báo cáo cuối

Thay đổi / File chính / Kiểm thử đã chạy (lệnh + kết quả thật) / Chưa kiểm tra / Rủi ro / Đề xuất đổi hợp đồng.
