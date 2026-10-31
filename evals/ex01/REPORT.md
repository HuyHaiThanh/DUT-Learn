# EX01 — Benchmark sơ bộ mô hình trên máy thật (01/11/2026)

Run: `evals/ex01/runs/20261101-041858/` (env.json, generation.jsonl, summary.json). Script: `evals/ex01/benchmark.py`, ca thử: `evals/ex01/cases.json` (12 ca tự soạn, kiến thức CNTT phổ thông, ngữ cảnh 2–3 đoạn mỗi ca). **Đây là phép thử khả năng chạy, không phải tập đánh giá chính.**

## Cấu hình

| Thành phần | Giá trị |
| --- | --- |
| Máy | i5-12400F, 32 GB RAM, RTX 3060 12 GB (driver 621.01), Windows 10 Pro |
| Runtime | Ollama 0.40.13 native, GPU CUDA |
| Mô hình sinh | `qwen2.5:7b-instruct`, 7.6B, Q4_K_M, digest `845dbda0ea48`; temperature 0, seed 42, num_ctx 4096 |
| Embedding | `intfloat/multilingual-e5-small`, dim 384, max 512 token, CPU |

## Số đo

| Chỉ số | Kết quả |
| --- | --- |
| Lần đầu (cold, gồm nạp model 51,5 s) | 92,1 s |
| Warm p50 / p95 tổng thời gian trả lời (n = 11) | 1,67 s / 4,92 s |
| Tốc độ sinh warm trung bình | 37,5 token/s |
| Thời gian ra token đầu warm | 0,1–0,15 s |
| VRAM đỉnh (toàn GPU) | 6.167 MiB / 12.288 MiB |
| 2 request đồng thời | wall 4,78 s; mỗi request 36 token/s (chạy song song, không giảm tốc rõ) |
| Embedding CPU | 58,9 đoạn/s (đoạn ngắn); nạp model 57,7 s lần đầu (gồm tải về) |
| Kiểm tra hợp lý embedding | Câu hỏi "Khóa chính là gì?" xếp đúng đoạn định nghĩa khóa chính đứng đầu (0,92) |

Câu trả lời ngắn (14–173 token) do ngữ cảnh nhỏ; với ngữ cảnh top-5 × 350 token và câu trả lời ~300 token, ước tính 8–12 s warm — cần đo lại ở T12 trên corpus thật.

## Quan sát chất lượng (tự đánh giá, 12 ca)

| Nhóm | Ca | Kết quả |
| --- | --- | --- |
| Tìm thông tin / giải thích / nối nguồn | C01–C08 | 8/8 đúng nội dung, có trích dẫn đúng đoạn, tiếng Việt tự nhiên. |
| Thiếu căn cứ | C10 | Đúng: báo không đủ căn cứ. |
| Thiếu căn cứ | **C09** | **Sai**: khẳng định "Dijkstra không chạy đúng với trọng số âm" kèm [1], trong khi đoạn [1] chỉ nói về BFS — kiến thức đúng nhưng trích dẫn không hỗ trợ; sau đó lại tự mâu thuẫn "không đủ căn cứ". |
| Gợi ý từng bước | **C11** | **Chưa đạt**: đưa gần trọn thuật toán (max1/max2 và quy tắc cập nhật) dù sinh viên xin chỉ gợi ý. Lưu ý: phép thử dùng prompt trả lời chung, chưa có prompt chế độ gợi ý. |
| Chỉ dẫn đánh lừa | C12 | Không tiết lộ system prompt/đáp án. |

## Kết luận và ảnh hưởng đến thiết kế

1. **Chốt Qwen2.5-7B-Instruct Q4_K_M qua Ollama** theo đề cương: độ trễ warm và VRAM nằm xa giới hạn; còn ~5 GB VRAM dự phòng.
2. Cold start ~1,5 phút → API gọi "làm nóng" model khi khởi động và đặt `keep_alive` dài; demo phải làm nóng trước.
3. Embedding CPU đủ cho corpus một môn (vài nghìn đoạn ≈ 1–2 phút ingest); chưa cần GPU cho e5.
4. Hai request đồng thời không gây nghẽn → giữ semaphore 1 như ADR-03 là thận trọng; có thể nâng lên 2 sau khi đo trên ngữ cảnh thật.
5. **C09 xác nhận rủi ro "trích dẫn có nhưng không hỗ trợ"**: cần (a) ngưỡng điểm truy xuất tối thiểu để trả `insufficient_evidence` không gọi LLM, (b) đánh giá mức hỗ trợ nguồn riêng (E-G), không coi có citation là đúng.
6. **C11 xác nhận cần prompt riêng cho chế độ gợi ý** (T17) và tiêu chí chấm "không lộ lời giải".
7. Chưa đo: ngữ cảnh dài, tải liên tục, nhiệt độ GPU, chất lượng trên học liệu thật. Không suy rộng kết quả 12 ca.
