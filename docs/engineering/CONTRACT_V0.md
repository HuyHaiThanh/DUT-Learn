# DUTLearn — Hợp đồng kỹ thuật v0

Trạng thái: v0.2 (01/11/2026, thêm quy tắc khối mã và ngưỡng thiếu căn cứ theo review kế hoạch lần 2), chủ sở hữu: Tech Lead. Mọi agent đọc file này trước khi sửa code. Thay đổi hợp đồng phải đề xuất trong báo cáo task, không tự sửa.

## 1 Ngăn xếp và phiên bản

| Thành phần | Lựa chọn | Ghi chú |
| --- | --- | --- |
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 (sync), Alembic, psycopg 3 | Quản lý gói bằng `uv`; khóa `uv.lock`. |
| DB | PostgreSQL 16 + pgvector (image `pgvector/pgvector:pg16`) | Docker Compose, cổng host 5433 để tránh trùng. |
| Embedding | `intfloat/multilingual-e5-small` (dim 384) qua sentence-transformers | Bắt buộc tiền tố `query: ` / `passage: `; tối đa 512 token; chuẩn hóa L2; cosine. |
| LLM | Ollama native `http://127.0.0.1:11434`, model `qwen2.5:7b-instruct` (Q4_K_M) | Tên model cấu hình qua env `DUT_LLM_MODEL`. |
| PDF | PyMuPDF | Chỉ PDF có lớp văn bản. |
| Frontend | React 18 + TypeScript + Vite, React Router, TanStack Query, pdf.js (`pdfjs-dist`), Tailwind CSS 4 + shadcn/ui (Radix) | Quản lý gói `npm`; khóa `package-lock.json`. shadcn/ui sao mã component vào `src/components/ui` (không khóa thư viện), Radix hỗ trợ bàn phím/ARIA cho NFR tiếp cận. Thêm ở T06. |
| Test | pytest (+ testcontainers hoặc DB compose riêng `dutlearn_test`), Vitest, Playwright | |
| Lint | ruff + mypy (backend), eslint + tsc (frontend) | |

Biến môi trường (`services/api/.env.example`): `DUT_DATABASE_URL`, `DUT_DATA_DIR` (mặc định `../../data`), `DUT_SESSION_TTL_HOURS=12`, `DUT_LLM_BASE_URL`, `DUT_LLM_MODEL`, `DUT_LLM_TIMEOUT_S=90`, `DUT_EMBED_MODEL`, `DUT_RETRIEVER=dense|hybrid`, `DUT_TOP_K=5`, `HF_HOME` (đặt ở ổ D:).

## 2 Cấu trúc thư mục

```text
services/api/app/
  main.py               # tạo app, đăng ký router (Tech Lead sở hữu)
  config.py  db.py  deps.py  errors.py
  auth/  admin/  courses/  materials/  ingest/  rag/  tutor/  assignments/  practice/  progress/
    (mỗi module: models.py, schemas.py, service.py, router.py)
services/api/alembic/   # migration: mỗi wave chỉ một agent tạo migration
services/api/tests/
apps/web/src/  api/ (client sinh từ OpenAPI)  pages/  components/  features/<module>/
infra/docker-compose.yml   infra/backup.ps1   infra/restore.ps1
evals/   data/ (gitignore)
```

## 3 Mô hình dữ liệu (bảng chính)

Mọi bảng có `id` (UUID v4, server sinh), `created_at`, `updated_at` (timestamptz UTC) trừ khi ghi khác.

| Bảng | Cột chính | Ràng buộc |
| --- | --- | --- |
| users | email (unique, lower), full_name, password_hash, system_role `admin|user`, is_active | |
| sessions | user_id, token_hash (unique, SHA-256 của token), expires_at, revoked_at, user_agent | Token gốc chỉ nằm trong cookie. |
| courses | code (unique), name | |
| classes | course_id, code, term, status `open|closed`, content_version INT default 0 | unique(course_id, code, term); content_version tăng trong cùng transaction với mọi publish/supersede/revoke/đổi visibility |
| class_members | class_id, user_id, role `lecturer|student` | unique(class_id, user_id) |
| lessons | class_id, title, position, is_published | |
| materials | class_id, lesson_id NULL, title, kind `pdf|text`, visibility `students|lecturers`, source_note, license_note, active_version_id NULL | active_version_id trỏ đến bản `published` duy nhất |
| material_versions | material_id, version_no, status `uploaded|processing|ready|failed|published|superseded|revoked`, storage_key, checksum_sha256, page_count, quality_report JSONB, error, published_at/by, revoked_at/by | unique(material_id, version_no) |
| chunks | version_id, ordinal, kind `text|code`, page_index (0-based), page_index_end, page_label, char_start, char_end, code_block_id NULL, part_no NULL, text, token_count, embedding vector(384) | index (version_id); chỉ tạo khi version thuộc material |
| chat_sessions | user_id, class_id, lesson_id NULL, material_id NULL | |
| chat_messages | session_id, role `user|assistant`, mode `answer|hint`, content, status `ok|insufficient_evidence|error`, error_code, retriever, model, prompt_version, latency_ms, request_id | |
| citations | message_id, chunk_id, version_id, page_index, excerpt, ordinal | |
| assignments | class_id, lesson_id NULL, title, instructions, criteria (text), due_at, status `draft|published|closed` | |
| submissions | assignment_id, student_id | unique(assignment_id, student_id) |
| submission_versions | submission_id, version_no, content, submitted_at | unique(submission_id, version_no) |
| grade_revisions | submission_version_id, revision_no, grade NUMERIC(4,2) NULL, comment, criteria_snapshot, created_by, status `draft|published`, published_at, published_by | bất biến sau khi `published`; sửa điểm = revision mới; điểm hiện hành = revision published mới nhất |
| idempotency_keys | user_id, operation, key, payload_hash, response_ref_type, response_ref_id | unique(user_id, operation, key); cùng hash → trả kết quả cũ; khác hash → 409 `idempotency_conflict` |
| practice_questions | class_id, lesson_id NULL, kind `mcq|short`, stem, options JSONB, answer_key, explanation, source_chunk_id NULL, source_version_id NULL, origin `ai|lecturer`, status `draft|approved|published|retired`, supersedes_id NULL, approved_by/at, published_at | answer_key/explanation không bao giờ vào chunks; sửa câu đã `published` = tạo câu mới `supersedes_id`, câu cũ `retired` |
| practice_attempts | question_id, student_id, question_snapshot JSONB, response, is_correct NULL, submitted_at | chống trùng qua idempotency_keys (operation `practice_attempt`) |
| learning_events | user_id, class_id, type `material_opened|question_asked|citation_opened|submission_created|practice_attempted|feedback_viewed`, ref_type, ref_id, occurred_at | không có updated_at |
| audit_events | actor_id, action, target_type, target_id, detail JSONB | |

## 4 Quy tắc quyền (máy chủ)

Hàm trung tâm trong `deps.py`/`auth/policy.py`, không viết lại trong router:

- `require_user()` → user từ cookie `dut_session`; 401 nếu không hợp lệ/hết hạn/thu hồi.
- `require_admin()` → `system_role == admin`.
- `class_role(user, class_id)` → `lecturer|student|None`. Admin **không** mặc nhiên có quyền đọc nội dung học thuật.
- Sinh viên: chỉ đọc lớp `open` đã ghi danh; học liệu `visibility=students` có `active_version` `published`; câu luyện tập `published` (schema không có answer_key/explanation trước khi nộp); bài nộp và feedback `published` của chính mình.
- Giảng viên: toàn quyền nghiệp vụ trong lớp mình là `lecturer`.
- Tài nguyên không có quyền trả **404** (không lộ tồn tại), thiếu vai trò trên lớp đã biết trả 403.

Truy xuất cho trợ giảng (bất biến I2) — điều kiện SQL bắt buộc:

```sql
chunks.version_id = materials.active_version_id
AND material_versions.status = 'published'
AND materials.visibility = 'students'      -- với người hỏi là sinh viên
AND materials.class_id = :class_id
AND :user là thành viên của :class_id
```

## 5 API v0 (tiền tố `/api`)

Lỗi chung: `{"error": {"code": "string_snake", "message": "tiếng Việt", "request_id": "..."}}`. Mọi response có header `X-Request-ID`. Request ghi (POST/PUT/PATCH/DELETE) phải có header `X-DUT-CSRF: 1`.

| Method | Path | Vai trò | Ghi chú |
| --- | --- | --- | --- |
| POST | /auth/login | — | `{email,password}` → set cookie; giới hạn 5 lần sai/15 phút/email |
| POST | /auth/logout | user | thu hồi phiên |
| GET | /auth/me | user | `{id,email,full_name,system_role,classes:[{class_id,role}]}` |
| POST/GET | /admin/users, /admin/courses, /admin/classes, /admin/classes/{id}/members | admin | CRUD tối thiểu |
| GET | /classes | user | lớp `open` mà tôi là thành viên: `[{id, course_id, code, term, status, content_version, course_code, course_name, role}]` (T05) |
| GET | /classes/{id} | member | gồm lessons đã công bố (GV thấy cả nháp) |
| POST/PATCH | /classes/{id}/lessons, /lessons/{id} | lecturer | |
| GET | /classes/{id}/materials | member | SV: chỉ bản công bố |
| POST | /classes/{id}/materials | lecturer | multipart PDF hoặc TXT/MD UTF-8 ≤ 50 MB → material + version 1 `uploaded`, kích hoạt ingest |
| POST | /materials/{id}/versions | lecturer | tải bản mới |
| GET | /material-versions/{id} | lecturer | trạng thái + quality_report |
| POST | /material-versions/{id}/publish | lecturer | chỉ từ `ready`; bản cũ → `superseded`; nguyên tử |
| POST | /material-versions/{id}/revoke | lecturer | → `revoked`; nếu là active thì active=NULL |
| PATCH | /materials/{id} | lecturer | đổi title/visibility/lesson; đổi visibility tăng content_version |
| POST | /material-versions/{id}/reprocess | lecturer | từ `failed` |
| GET | /material-versions/{id}/file | member có quyền | stream PDF, `Cache-Control: private, no-store` |
| GET | /material-versions/{id}/pages/{page}/text | member có quyền | cho đánh dấu đoạn |
| POST | /tutor/ask | member | xem 5.1 |
| GET | /tutor/sessions?class_id= , /tutor/sessions/{id}/messages | owner | |
| GET | /citations/{id}/open | owner + còn quyền | `{version_id,page_index,excerpt,char_start,char_end}` hoặc 410 `source_revoked` |
| CRUD | /classes/{id}/assignments, /assignments/{id} | lecturer (ghi), member (đọc published) | |
| POST | /assignments/{id}/submissions | student | `{content, idempotency_key}` |
| GET | /assignments/{id}/submissions | lecturer | |
| POST | /submission-versions/{id}/grades, /grade-revisions/{id}/publish | lecturer | |
| POST | /classes/{id}/practice/generate | lecturer | `{material_id, page_from, page_to, count}` → câu `draft` |
| PATCH | /practice/{id} ; POST /practice/{id}/approve, /publish, /retire | lecturer | |
| GET | /classes/{id}/practice | member | SV: published, không answer_key |
| POST | /practice/{id}/attempts | student | `{response, idempotency_key}`; trả kết quả + giải thích sau nộp |
| POST | /events | member | chỉ các type phía client (material_opened, citation_opened, feedback_viewed) |
| GET | /classes/{id}/progress/me ; /classes/{id}/progress | student ; lecturer | |

### 5.1 Hợp đồng trợ giảng

Request:

```json
{"class_id":"uuid","lesson_id":"uuid|null","material_id":"uuid|null","page_index":3,
 "session_id":"uuid|null","mode":"answer|hint","question":"string ≤ 2000 ký tự"}
```

Response 200:

```json
{"session_id":"uuid","message_id":"uuid","status":"ok|insufficient_evidence",
 "answer":"markdown, citation dạng [1], [2]",
 "citations":[{"id":"uuid","ordinal":1,"material_id":"uuid","material_title":"...","version_id":"uuid",
               "page_index":3,"page_label":"4","excerpt":"..."}],
 "limitation":"string|null","retriever":"dense","model":"qwen2.5:7b-instruct","latency_ms":4210,"request_id":"..."}
```

Lỗi: 503 `llm_unavailable`, 504 `llm_timeout`, 429 `llm_busy` (hàng đợi đầy hoặc chờ > 30 s), 409 `source_changed` (nguồn bị thay/thu hồi trong lúc sinh).

`LLMClient`: semaphore 1 request đang sinh, hàng đợi tối đa 3. Dev gọi `http://127.0.0.1:11434`; trong Compose gọi `http://host.docker.internal:11434` (kiểm chứng ở T04).

Quy trình máy chủ: kiểm quyền → truy xuất top-k trong phạm vi (ưu tiên tài liệu/trang đang mở nếu có, không loại các nguồn khác) → nếu **điểm cosine cao nhất** trong các đoạn cuối cùng (với cả dense và hybrid — không dùng điểm RRF) < ngưỡng của cấu hình đang chạy (`DUT_MIN_SCORE_DENSE` / `DUT_MIN_SCORE_HYBRID`, hiệu chỉnh trên dev cùng một quy tắc, khóa trước test) thì trả `insufficient_evidence` không gọi LLM → dựng prompt (`prompt_version` cố định trong code, các đoạn đánh số [1..k]) → gọi LLM → phân tích các `[n]` trong câu trả lời, **loại mọi số không thuộc 1..k**, chỉ lưu citation hợp lệ → nếu không còn citation hợp lệ và LLM không tự báo thiếu căn cứ thì gắn `limitation` → **kiểm lại** (truy vấn SQL I2) mọi version được trích còn là active/published/visible; nếu không → bỏ câu trả lời, trả 409 `source_changed` → lưu message + citations + latency.

Đọc lịch sử: với người xem là sinh viên, message assistant có citation trỏ tới version không còn hiệu lực trả `content=null`, `status=source_withdrawn` và thông báo thay thế; bản gốc giữ trong DB.

Hybrid (T16): tập tài liệu BM25 = kết quả SQL I2; cache chỉ mục theo `(class_id, content_version)`; RRF k=60; kiểm lại quyền đoạn trước khi đưa vào prompt.

Prompt chống chỉ dẫn đánh lừa: nội dung học liệu và câu hỏi đặt trong khối phân định; hướng dẫn hệ thống nêu rõ không làm theo chỉ dẫn nằm trong tài liệu/câu hỏi đòi tiết lộ đáp án, prompt hay dữ liệu người khác. Chế độ `hint`: trả tối đa 3 bước gợi mở, không đưa đáp án cuối.

## 6 Ingest

`uploaded → processing → ready|failed`. Một worker thread; nhận job bằng `UPDATE … SET status='processing' WHERE id=? AND status IN ('uploaded','failed') RETURNING`. Bước: kiểm tra magic `%PDF` (PDF) hoặc giải mã UTF-8 hợp lệ (TXT/MD; mỗi "trang" = khối ~3000 ký tự, cắt ở ranh giới đoạn), lưu `data/materials/<material_id>/<version_id>.pdf` (tên do server sinh) → checksum → PyMuPDF trích theo trang → cảnh báo trang rỗng/ít chữ (quality_report: page_count, empty_pages, chars_per_page, sample) → chia đoạn theo tokenizer e5: văn bản mục tiêu 350 token, chồng 50, không vượt trang. **Khối mã** (nhận diện bằng font đơn cách/thụt lề của PyMuPDF hoặc rào ``` trong TXT/MD): giữ nguyên khoảng trắng; nếu ≤ 480 token thì là một chunk `kind=code` (được phép kéo qua trang: `page_index` = trang bắt đầu, `page_index_end` = trang kết thúc); nếu dài hơn thì chia tại ranh giới dòng (ưu tiên dòng trống/dấu `}`), mỗi phần ≤ 480 token, cùng `code_block_id`, `part_no` tăng dần, lặp lại dòng khai báo hàm ở đầu mỗi phần nếu có. PDF nhiều cột: dùng thứ tự khối của PyMuPDF theo cột; ghi cảnh báo vào quality_report nếu thứ tự đọc bất thường → embedding batch `passage: ` → trong **một transaction**: xóa chunk cũ của version, ghi toàn bộ chunk mới, chuyển `ready`. Lỗi bất kỳ → `failed` + `error` (không có chunk dở vì chưa ghi). Publish chỉ bằng `UPDATE … WHERE status='ready'`. Khởi động app: version `processing` quá 30 phút → `failed`.

## 7 Quy ước làm việc cho agent

- Nhánh `feat/<task-id>`; commit nhỏ, thông điệp tiếng Anh dạng `T05: add session auth`.
- Không sửa file ngoài phạm vi brief; file chung chỉ sửa khi brief ghi rõ quyền sở hữu.
- Không thêm dependency ngoài danh sách nếu không nêu lý do trong báo cáo.
- Không commit `data/`, `.env`, model weights, học liệu riêng.
- Bắt buộc chạy: `uv run ruff check . && uv run mypy app && uv run pytest` (backend), `npm run lint && npm run typecheck && npm test` (frontend) trước khi báo xong; dán output tóm tắt vào báo cáo.
- Báo cáo cuối theo mẫu: Thay đổi / File / Kiểm thử đã chạy (lệnh + kết quả) / Chưa kiểm tra / Rủi ro / Đề xuất đổi hợp đồng.
