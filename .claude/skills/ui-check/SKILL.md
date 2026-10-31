---
name: ui-check
description: Kiểm tra giao diện DUTLearn trên trình duyệt thật bằng Playwright MCP — luồng theo vai trò, desktop và 360 px, bàn phím, trạng thái lỗi/rỗng, console. Dùng sau khi sửa màn hình hoặc trước demo.
---

# Kiểm tra giao diện

1. Chạy DB + API + web (`docs/engineering/RUN_DEV.md`). Với chức năng AI, Ollama phải chạy và đã làm nóng model.
2. Dùng MCP **`playwright`** (Edge, profile isolated, không lưu phiên). Mở `http://localhost:5173`.
3. Với mỗi màn hình đã đổi:
   - Thực hiện luồng chính theo từng vai trò bị ảnh hưởng (tài khoản seed: admin, giảng viên, sinh viên); kiểm thêm một tài khoản **không có quyền** để chắc chắn bị chặn.
   - Viewport 1280×800 và 360×740: không tràn ngang, điều khiển chính bấm được.
   - Bàn phím: Tab đến được mọi điều khiển, focus nhìn thấy, Enter/Esc hoạt động; điều khiển có nhãn.
   - Trạng thái: đang tải, rỗng, lỗi mạng/API, lỗi quyền, mô hình bận/không sẵn sàng.
   - Console và network: không lỗi đỏ, không request trả 5xx ngoài ca thử lỗi.
4. Chụp ảnh màn hình các trạng thái chính vào `.playwright-mcp/` (bị ignore); ảnh dùng cho báo cáo thì chọn lọc và chuyển sang `private/bao-cao/hinh/`.
5. Báo cáo: đạt/chưa đạt theo từng mục, kèm ảnh và lỗi cụ thể. Đây là tự kiểm của nhóm phát triển, không gọi là thử nghiệm người dùng.

Nguyên tắc thiết kế: dùng skill `frontend-design` và component shadcn/ui; tiếng Việt rõ ràng; không chỉ dùng màu để biểu đạt trạng thái; trích dẫn luôn mở được về đúng nguồn.
