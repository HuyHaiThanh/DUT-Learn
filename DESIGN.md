# DUTLearn — Design system: “Xanh Bách khoa”

Chốt ngày 22/11/2026 (người thực hiện chọn hướng C trong 3 hướng thử). Áp dụng cho mọi màn của `apps/web`. Đọc cùng [PRODUCT.md](PRODUCT.md). Khi triển khai: token đặt trong `apps/web/src/style.css` (`:root` + `@theme inline` của Tailwind), component dựa trên shadcn/ui hiện có, chỉ đổi giao diện — không đổi API/quyền.

## 1. Ý tưởng

Màu xanh thương hiệu **phủ mảng lớn** (dải đầu trang, khối trợ giảng), nội dung đặt trên **thẻ trắng bo tròn**, **vàng** là màu hành động/điểm nhấn và màu “trích dẫn”. Chữ to, đậm, dễ đọc trên máy chiếu. Hiện đại, tự tin, thân thiện nhưng không trẻ con (không minh họa, không gamification, không streak).

Ba điểm nhận diện phải giữ:
1. **Dải xanh đầu trang** bo góc dưới 32px, chứa tiêu đề lớn + thẻ “Tiếp tục đọc”/hành động chính nổi lên (thẻ trắng, nút vàng).
2. **Trích dẫn màu vàng** thống nhất ở mọi nơi: chip `1 · tr.133` trong câu trả lời ↔ đoạn tô vàng gạch chân trong trang ↔ thanh “Đang xem nguồn”.
3. **Trợ giảng là khối xanh đậm bo tròn** cạnh trang đọc (không phải popup, không phải trang riêng).

## 2. Token

| Nhóm | Token | Giá trị | Dùng cho |
|---|---|---|---|
| Thương hiệu | `--brand` | `#0B5CAD` | Dải đầu trang, nút chính, link, tiêu đề mục trong trang đọc |
| | `--brand-ink` | `#084887` | Hover nút chính |
| | `--deep` | `#073F7A` | Khối trợ giảng, khối mã, chương đang chọn |
| | `--sky` / `--sky-2` | `#DCEBFA` / `#EEF5FD` | Nền icon “Đọc”, thanh tiến độ rỗng, nền nguồn trích, tiêu đề bảng |
| Nền | `--ground` | `#F3F7FC` | Nền trang |
| | `--surface` | `#FFFFFF` | Thẻ, trang giáo trình |
| Chữ | `--ink` / `--ink-2` / `--ink-3` | `#0E1B2B` / `#41526A` / `#556479` | Chính / phụ / chú thích (đều ≥ 4.5:1 trên nền sáng) |
| Chữ trên xanh | `--on-blue` / `--on-blue-2` | `#F1F7FE` / `#EAF3FD` | Chữ phụ trên `--brand`/`--deep` (không dùng xanh nhạt hơn — thiếu tương phản) |
| Đường kẻ | `--line` / `--line-2` | `#D6E2EF` / `#BFD0E3` | Viền thẻ / viền điều khiển |
| Nhấn & trích dẫn | `--hl` | `#FFDD55` | Nút hành động nổi (Đọc tiếp, Tải học liệu), chip trích dẫn, focus ring, số đếm trên nav |
| | `--hl-soft` / `--hl-ink` | `#FFF3C2` / `#5C4300` | Nền đoạn trích, thanh “Đang xem nguồn”, hộp gợi ý |
| Trạng thái | `--ok` / `--ok-soft` | `#1E7A4A` / `#E3F4EA` | Đúng, đang công bố, luyện tập |
| | `--warn` / `--warn-soft` | `#A14E00` / `#FFEFDC` | Hạn nộp, thiếu căn cứ, bài tập |
| | `--bad` / `--bad-soft` | `#B42318` / `#FDECEA` | Sai, thu hồi, lỗi |
| | `--ai` / `--ai-soft` | `#5B3FA8` / `#EFEAFB` | Nhãn “AI đề xuất” (chỉ dùng cho nội dung do AI sinh chờ/đã qua duyệt) |
| Bo góc | `--r-xl` 24 · `--r-lg` 20 · `--r-md` 14 · `--r-sm` 10; nút 12; pill 999 | | |
| Đổ bóng | `--shadow` `0 14px 28px -18px rgba(7,63,122,.45)`; `--shadow-lg` `0 20px 40px -20px rgba(4,30,60,.55)` | | Thẻ nổi trên dải xanh, hover thẻ |

Trạng thái **không bao giờ chỉ dùng màu**: luôn kèm icon + chữ (`Đúng`, `Sai`, `Đã thu hồi`, `Còn 3 ngày`…).

## 3. Chữ

- **Be Vietnam Pro** (giao diện): body 16px/1.55 (15px ở ≤ 760px); nhãn nhỏ tối thiểu 12px.
- Tiêu đề trang (trong dải xanh) 44px/800, letter-spacing −0.03em (32px trên điện thoại). Tiêu đề mục 22px/800. Tiêu đề thẻ 17px/700.
- **Source Serif 4**: chỉ cho **nội dung giáo trình** trong trình đọc (18px/1.75) và trích đoạn nguồn.
- **JetBrains Mono**: chỉ cho mã và `code` (tắt ligature để sinh viên thấy đúng ký tự C).

## 4. Bố cục

- **Khung trang thường:** dải xanh (nav dạng pill + tiêu đề + thẻ nổi) → nội dung tối đa 1240px, lưới `1fr | 360px` (cột phải là thông tin phụ). Nội dung đầu tiên có thể “nhấc” lên đè mép dải xanh (−22px).
- **Nav:** pill trắng trong nền xanh mờ; mục hiện tại là pill trắng chữ xanh; số đếm việc là badge vàng. Sinh viên: Tổng quan · Lớp học · Bài tập. Giảng viên: Việc cần xử lý · Duyệt câu hỏi · Học liệu.
- **Trang lớp:** dải chương dạng thẻ (`I`…`X`, chương hiện tại nền `--deep`, viền vàng) lấy từ mục lục PDF; danh sách mục của chương là các thẻ có icon theo loại: Đọc (sky), Hỏi trợ giảng (vàng nhạt), Luyện tập (xanh lá), Bài tập (cam).
- **Trình đọc:** thanh trên xanh (logo về lớp · tên tài liệu · Mục lục · PDF/Văn bản · chuyển trang) → 3 vùng: mục lục (ẩn mặc định, mở bằng nút) | trang giáo trình (thẻ trắng 24px) | khối trợ giảng `--deep` 420px, cuộn độc lập, ô hỏi luôn ở đáy.
- **Trợ giảng:** tab `Trợ giảng | Luyện tập`; công tắc `Trả lời | Dẫn dắt từng bước` dạng pill to; nút gợi ý theo ngữ cảnh (tóm tắt trang, ví dụ khác); khối mã có nút vàng “Giải thích mã”; bôi đen đoạn → thanh “Hỏi về đoạn này / Dẫn dắt để tự hiểu”, đoạn trích gắn vào ô hỏi (tổng ≤ 2000 ký tự). Câu hỏi người dùng: bóng xanh `--brand` bên phải; câu trả lời: thẻ trắng bên trái.
- **Giảng viên:** dải xanh + 3 thẻ đếm nổi (số 40px/800) dẫn tới việc cần làm; bảng tiến độ trên thẻ trắng, tiêu đề cột nền `--sky-2`. Duyệt câu AI: thẻ chia đôi, trái là câu hỏi + nút Duyệt/Sửa/Loại bỏ, phải là đoạn nguồn nền `--sky-2` tô vàng.

## 5. Thành phần

| Thành phần | Quy tắc |
|---|---|
| Nút | Cao ≥ 44px (nhỏ 36px). Chính: nền `--brand`. Hành động nổi bật trên/ cạnh dải xanh: nền `--hl` chữ `--deep`. Phụ: trắng viền `--line-2`. Không quá một nút vàng mỗi vùng nhìn. |
| Thẻ | Trắng, viền `--line`, bo 20; hover nhấc 2px + `--shadow`. Không lồng thẻ trong thẻ. |
| Pill trạng thái | Bo tròn, 13px/700, icon + chữ, cặp màu `*-soft` / màu đậm. |
| Chip trích dẫn | Nền `--hl`, chữ `--deep`, nội dung `số · tr.trang`, là `<button>` có `aria-label` “Nguồn n, trang p”. Danh sách nguồn dưới câu trả lời: mỗi nguồn là nút “Mở đoạn này”. |
| Thanh “Đang xem nguồn” | Dính đầu vùng đọc, nền `--hl-soft` viền `--hl`, có “Về chỗ đang đọc” và (điện thoại) “Về câu trả lời”; nhận focus sau khi mở nguồn. |
| Ô nhập | Viền 2px `--line`, focus viền `--brand`; focus ring toàn cục 3px `--hl`. |
| Trạng thái chờ trợ giảng | Thẻ trắng: spinner + “Đang tìm trong học liệu và soạn câu trả lời…”, skeleton, “Đã chờ n giây”, nút “Hủy chờ” cùng khối (không streaming, không hứa thời gian). |
| Thiếu căn cứ / bận / lỗi | Thẻ `--warn-soft` có tiêu đề in đậm + icon, nói rõ lý do và bước tiếp theo; câu hỏi được giữ lại trong ô nhập. |

## 6. Responsive

- ≤ 1180px: cột trợ giảng 380px, mục lục 220px khi mở.
- ≤ 960px: một cột; trình đọc dùng tab dính `Tài liệu | Trợ giảng` ngay dưới thanh xanh; mục lục mở thành khối trong luồng; ô hỏi dính đáy.
- ≤ 760px: nav pill ẩn, thay bằng **thanh điều hướng đáy** (Tổng quan · Lớp học · Bài tập; ẩn khi đang đọc); dải chương đổi thành `<select>`; tiêu đề 32px; không cuộn ngang ở 360px.

## 7. Chuyển động & trợ năng

- 150–250ms cho hover/chuyển trạng thái; nhấp nháy viền vàng 1,4s khi mở đoạn trích; tắt hết khi `prefers-reduced-motion`.
- Mọi điều khiển có nhãn tiếng Việt; tab dùng `role=tab` + phím ←/→; nút đổi nhãn theo trạng thái **không** dùng `aria-pressed`; Esc đóng thanh chọn đoạn.

## 8. Không làm

Gradient trang trí, glassmorphism, quầng sáng; thẻ icon-trên-tiêu-đề lặp lại kiểu template; minh họa/emoji; streak, huy hiệu; số liệu suy ra năng lực; thông tin backend không cung cấp (xem bảng đối chiếu hợp đồng trong brief).

## 9. Tham chiếu

Prototype tương tác 8 màn (cục bộ, không commit): `private/design/ui-v3-xanh/index.html`. Triển khai theo task: shell + trình đọc/trợ giảng → T13; chế độ dẫn dắt → T17; bài tập → T19–T20; luyện tập + duyệt câu → T21–T22; tiến độ → T23.
