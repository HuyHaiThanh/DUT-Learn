import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from '@/App';
import type { Me, ClassSummary } from '@/api/types';
const student: Me = { id: 'u1', full_name: 'Nguyễn An', email: 'an@example.test', system_role: 'user', classes: [{ class_id: 'c1', role: 'student' }] };
const lecturer: Me = { ...student, classes: [{ class_id: 'c1', role: 'lecturer' }] };
function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }); }
function mockApi(me = student, classes: ClassSummary[] = []) {
  return vi.fn(async (path: string) => {
    if (path === '/api/auth/me') return response(me);
    if (path === '/api/classes') return response(classes);
    if (path === '/api/auth/login') return response({});
    if (path === '/api/auth/logout') return new Response(null, { status: 204 });
    throw new Error(`Unexpected request ${path}`);
  });
}
function Path() { const location = useLocation(); return <output aria-label="Đường dẫn">{location.pathname + location.search + location.hash}</output>; }
function mount(path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /><Path /></MemoryRouter></QueryClientProvider>);
  return client;
}
function submit() {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'an@example.test' } });
  fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'test-password' } });
  fireEvent.submit(screen.getByRole('button', { name: 'Đăng nhập' }).closest('form')!);
}
afterEach(() => vi.unstubAllGlobals());
it.each([
  [student, '/hoc', 'Lớp học của tôi'],
  [lecturer, '/giang-day', 'Lớp phụ trách'],
  [{ ...student, system_role: 'admin' } as Me, '/quan-tri', 'Không gian quản trị'],
])('đăng nhập và chuyển theo vai trò %#', async (me, path, heading) => {
  vi.stubGlobal('fetch', mockApi(me)); mount('/login'); submit();
  expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
  expect(screen.getByLabelText('Đường dẫn')).toHaveTextContent(path);
});
it.each([
  ['invalid_credentials', 'Email hoặc mật khẩu không đúng'],
  ['too_many_attempts', 'Vui lòng đợi 15 phút'],
])('hiển thị lỗi đăng nhập %s', async (code, message) => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ error: { code, message: 'lỗi', request_id: 'r1' } }, 401)));
  mount('/login'); submit();
  expect(await screen.findByRole('alert')).toHaveTextContent(message);
});
it('401 từ me chuyển login và giữ đường dẫn quay lại', async () => {
  const fetchMock = mockApi();
  fetchMock.mockResolvedValueOnce(response({ error: { code: 'unauthorized' } }, 401));
  vi.stubGlobal('fetch', fetchMock); mount('/hoc?tab=lop#danh-sach');
  await screen.findByRole('button', { name: 'Đăng nhập' }); submit();
  await screen.findByRole('heading', { name: 'Lớp học của tôi' });
  expect(screen.getByLabelText('Đường dẫn')).toHaveTextContent('/hoc?tab=lop#danh-sach');
});
it('danh sách lớp rỗng', async () => {
  vi.stubGlobal('fetch', mockApi()); mount();
  expect(await screen.findByText('Bạn chưa được ghi danh lớp nào')).toBeInTheDocument();
});
it('hiển thị hai điều hướng khi có hai vai trò', async () => {
  vi.stubGlobal('fetch', mockApi({ ...student, classes: [...student.classes, ...lecturer.classes] })); mount();
  expect(await screen.findByRole('link', { name: 'Giảng dạy' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Học tập' })).toBeInTheDocument();
});
it('lọc đúng lớp, vai trò và trạng thái sinh viên', async () => {
  vi.stubGlobal('fetch', mockApi(student, [
    { id: 'c1', course_id: 'course', code: 'ĐÃ ĐÓNG', term: '2026', status: 'closed' },
    { id: 'other', course_id: 'course', code: 'NGOÀI LỚP', term: '2026', status: 'open' },
  ])); mount('/hoc');
  await screen.findByText('Bạn chưa được ghi danh lớp nào');
  expect(screen.queryByText('NGOÀI LỚP')).not.toBeInTheDocument();
  expect(screen.queryByText('ĐÃ ĐÓNG')).not.toBeInTheDocument();
});
it('lỗi mạng và thử lại danh sách lớp', async () => {
  const fetchMock = mockApi();
  fetchMock.mockImplementationOnce(async () => response(student));
  fetchMock.mockRejectedValueOnce(new TypeError('offline'));
  vi.stubGlobal('fetch', fetchMock); mount('/hoc');
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể kết nối');
  fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
  await screen.findByText('Bạn chưa được ghi danh lớp nào');
});
it('401 khi tải danh sách lớp chuyển về login', async () => {
  const fetchMock = mockApi();
  fetchMock.mockImplementationOnce(async () => response(student));
  fetchMock.mockResolvedValueOnce(response({ error: { code: 'unauthorized' } }, 401));
  vi.stubGlobal('fetch', fetchMock); mount('/hoc');
  expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument();
});
it('đăng xuất xóa cache và chuyển login', async () => {
  const fetchMock = mockApi(); vi.stubGlobal('fetch', fetchMock); const client = mount();
  const trigger = await screen.findByRole('button', { name: 'Menu người dùng' });
  fireEvent.keyDown(trigger, { key: 'Enter' });
  fireEvent.click(await screen.findByRole('menuitem', { name: 'Đăng xuất' }));
  await screen.findByRole('button', { name: 'Đăng nhập' });
  expect(client.getQueryData(['me'])).toBeUndefined();
  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/auth/logout', expect.objectContaining({ method: 'POST', credentials: 'include' })));
});
it('404 tiếng Việt', () => {
  vi.stubGlobal('fetch', mockApi()); mount('/khong-ton-tai');
  expect(screen.getByRole('heading', { name: 'Không tìm thấy trang' })).toBeInTheDocument();
});

it('gửi đúng thông tin đăng nhập và khóa nút khi đang chờ', async () => {
  const fetchMock = vi.fn(() => new Promise<Response>(() => {}));
  vi.stubGlobal('fetch', fetchMock); mount('/login'); submit();
  expect(await screen.findByRole('button', { name: 'Đang đăng nhập…' })).toBeDisabled();
  expect(fetchMock).toHaveBeenCalledWith('/api/auth/login', expect.objectContaining({
    body: JSON.stringify({ email: 'an@example.test', password: 'test-password' }), credentials: 'include',
  }));
});
it('menu thu gọn có thể bật tắt và đóng sau khi chọn điều hướng', async () => {
  vi.stubGlobal('fetch', mockApi()); mount();
  const toggle = await screen.findByRole('button', { name: 'Menu' });
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(toggle); expect(toggle).toHaveAttribute('aria-expanded', 'true');
  fireEvent.click(screen.getByRole('link', { name: 'Học tập' }));
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
});
it('người dùng thường không thấy nội dung quản trị', async () => {
  vi.stubGlobal('fetch', mockApi()); mount('/quan-tri');
  expect(await screen.findByRole('alert')).toHaveTextContent('Bạn không có quyền quản trị');
  expect(screen.queryByRole('heading', { name: 'Người dùng' })).not.toBeInTheDocument();
});
it('lớp phụ trách hiển thị dữ liệu thật từ API', async () => {
  vi.stubGlobal('fetch', mockApi(lecturer, [{ id: 'c1', course_id: 'course', code: 'CTDL-01', term: '2026-1', status: 'closed' }])); mount('/giang-day');
  expect(await screen.findByRole('heading', { name: 'CTDL-01' })).toBeInTheDocument();
  expect(screen.getByText('Đã đóng')).toBeInTheDocument();
});
