import { act, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from '@/App';
import type { Me, ClassSummary } from '@/api/types';
const student: Me = { id: 'u1', full_name: 'Nguyễn An', email: 'an@example.test', system_role: 'user', classes: [{ class_id: 'c1', role: 'student' }] };
const classSummary: ClassSummary = { id: 'c1', course_id: 'course', course_code: 'KTLT', course_name: 'Kỹ thuật lập trình', role: 'student', code: 'KTLT-01', term: '2026-2027.1', status: 'open', content_version: 1 };
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
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.useRealTimers(); });
it.each([
  [student, '/hoc', 'Chào An'],
  [lecturer, '/giang-day', 'Lớp phụ trách'],
  [{ ...student, system_role: 'admin' } as Me, '/quan-tri', 'Quản trị'],
])('đăng nhập và chuyển theo vai trò %#', async (me, path, heading) => {
  vi.stubGlobal('fetch', mockApi(me)); mount('/login'); submit();
  expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
  expect(screen.getByLabelText('Đường dẫn')).toHaveTextContent(path);
});
it('401 từ me chuyển login và giữ đường dẫn quay lại', async () => {
  const fetchMock = mockApi();
  fetchMock.mockResolvedValueOnce(response({ error: { code: 'unauthorized' } }, 401));
  vi.stubGlobal('fetch', fetchMock); mount('/hoc?tab=lop#danh-sach');
  await screen.findByRole('button', { name: 'Đăng nhập' }); submit();
  await screen.findByRole('heading', { name: 'Chào An' });
  expect(screen.getByLabelText('Đường dẫn')).toHaveTextContent('/hoc?tab=lop#danh-sach');
});
it('danh sách lớp rỗng', async () => {
  vi.stubGlobal('fetch', mockApi()); mount();
  expect(await screen.findByText('Bạn chưa được ghi danh lớp nào')).toBeInTheDocument();
});
it('hiển thị hai điều hướng khi có hai vai trò', async () => {
  vi.stubGlobal('fetch', mockApi({ ...student, classes: [...student.classes, { class_id: 'c2', role: 'lecturer' }] })); mount();
  expect(await screen.findByRole('link', { name: 'Giảng dạy' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Học tập' })).toBeInTheDocument();
});
it('lọc đúng lớp, vai trò và trạng thái sinh viên', async () => {
  vi.stubGlobal('fetch', mockApi(student, [
    { ...classSummary, code: 'ĐÃ ĐÓNG', term: '2026', status: 'closed' },
    { ...classSummary, id: 'other', code: 'NGOÀI LỚP', term: '2026', status: 'open' },
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
  const trigger = await screen.findByRole('button', { name: 'Nguyễn An' });
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
  vi.stubGlobal('fetch', mockApi(lecturer, [{ ...classSummary, role: 'lecturer' }])); mount('/giang-day');
  expect(await screen.findByRole('link', { name: /Kỹ thuật lập trình/ })).toHaveAttribute('href', '/lop/c1');
  expect(screen.getByText('KTLT-01 · Học kỳ 1, 2026–2027 · vai trò giảng viên')).toBeInTheDocument();
});

it.each([3, 2, 1, 0, 4, 5, undefined])('401 hiển thị số lần thử phù hợp: %s', async attempts => {
  vi.stubGlobal('fetch', vi.fn(async () => response({ error: { code: 'invalid_credentials', details: { attempts_remaining: attempts } } }, 401)));
  mount('/login'); submit();
  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent('Email hoặc mật khẩu không đúng.');
  if (attempts === 0) expect(alert).toHaveTextContent('Lần sai tiếp theo sẽ tạm khóa đăng nhập 15 phút.');
  else if (attempts !== undefined && attempts <= 3) expect(alert).toHaveTextContent(`Bạn còn ${attempts} lần thử trước khi bị tạm khóa 15 phút.`);
  else expect(alert).not.toHaveTextContent('15 phút');
  for (const name of ['Email', 'Mật khẩu']) {
    expect(screen.getByLabelText(name)).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText(name)).toHaveAttribute('aria-describedby', alert.id);
  }
});
it('429 làm tròn phút, chặn gửi lại và mở nút sau đếm ngược', async () => {
  vi.useFakeTimers();
  const fetchMock = vi.fn(async () => response({ error: { code: 'too_many_attempts', details: { retry_after_seconds: 61 } } }, 429));
  vi.stubGlobal('fetch', fetchMock); mount('/login'); submit();
  await act(async () => { await vi.advanceTimersByTimeAsync(50); });
  expect(screen.getByRole('alert')).toHaveTextContent('Bạn đã thử quá nhiều lần. Thử lại sau 2 phút.');
  const button = screen.getByRole('button', { name: 'Đăng nhập' });
  expect(button).toBeDisabled();
  fireEvent.submit(button.closest('form')!);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  act(() => { vi.advanceTimersByTime(2000); });
  expect(screen.getByRole('alert')).toHaveTextContent('Thử lại sau 1 phút.');
  act(() => { vi.advanceTimersByTime(60000); });
  expect(button).toBeEnabled();
  expect(screen.getByRole('alert')).toHaveTextContent('Bạn có thể thử đăng nhập lại.');
});
it('hàng lớp hiển thị tên môn, mã lớp, học kỳ và dẫn tới trang giữ chỗ', async () => {
  const fetchMock = mockApi(student, [classSummary]);
  vi.stubGlobal('fetch', fetchMock); mount('/hoc');
  const row = await screen.findByRole('link', { name: /Kỹ thuật lập trình/ });
  expect(row).toHaveAttribute('href', '/lop/c1');
  expect(screen.getByText('Học kỳ 1, 2026–2027')).toBeInTheDocument();
  expect(screen.queryByText(/Tiếp tục đọc/)).not.toBeInTheDocument();
  expect(screen.queryByText('Việc cần làm')).not.toBeInTheDocument();
  expect(screen.queryByText('Phản hồi mới')).not.toBeInTheDocument();
  fireEvent.click(row);
  expect(await screen.findByRole('heading', { name: 'Trang lớp đang được xây dựng' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Quay lại danh sách lớp' })).toHaveAttribute('href', '/hoc');
  expect(fetchMock.mock.calls.every(([path]) => path === '/api/auth/me' || path === '/api/classes')).toBe(true);
});
it('nút tài khoản có đúng họ tên hiển thị trong tên trợ năng và mở menu', async () => {
  vi.stubGlobal('fetch', mockApi({ ...student, full_name: 'Nguyễn Văn Huy' })); mount('/hoc');
  const trigger = await screen.findByRole('button', { name: 'Nguyễn Văn Huy' });
  expect(trigger).toHaveTextContent('Nguyễn Văn Huy');
  expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
  fireEvent.keyDown(trigger, { key: 'Enter' });
  expect(await screen.findByRole('menuitem', { name: 'Đăng xuất' })).toBeInTheDocument();
});
it.each([
  [student, ['Học tập'], ['Giảng dạy', 'Quản trị']],
  [lecturer, ['Giảng dạy'], ['Học tập', 'Quản trị']],
  [{ ...student, system_role: 'admin', classes: [] } as Me, ['Quản trị'], ['Học tập', 'Giảng dạy']],
])('điều hướng chỉ có các vai trò đã cấp %#', async (me, visible, hidden) => {
  vi.stubGlobal('fetch', mockApi(me)); mount();
  for (const name of visible) expect(await screen.findByRole('link', { name })).toBeInTheDocument();
  for (const name of hidden) expect(screen.queryByRole('link', { name })).not.toBeInTheDocument();
});
it('người chưa có vai trò lớp không thấy điều hướng sinh viên hay giảng viên', async () => {
  vi.stubGlobal('fetch', mockApi({ ...student, classes: [] })); mount('/hoc');
  await screen.findByRole('heading', { name: 'Chào An' });
  for (const name of ['Học tập', 'Giảng dạy', 'Quản trị']) expect(screen.queryByRole('link', { name })).not.toBeInTheDocument();
});
it('lỗi danh sách có đường về trang chủ giảng viên', async () => {
  const fetchMock = mockApi(lecturer);
  fetchMock.mockImplementationOnce(async () => response(lecturer));
  fetchMock.mockRejectedValueOnce(new TypeError('offline'));
  vi.stubGlobal('fetch', fetchMock); mount('/giang-day');
  await screen.findByRole('alert');
  expect(screen.getByRole('link', { name: 'Về trang chủ' })).toHaveAttribute('href', '/giang-day');
});
it('không hiện lớp sai vai trò dù đã ghi danh lớp khác', async () => {
  vi.stubGlobal('fetch', mockApi(student, [{ ...classSummary, role: 'lecturer' }])); mount('/hoc');
  await screen.findByText('Bạn chưa được ghi danh lớp nào');
  expect(screen.queryByRole('link', { name: /Kỹ thuật lập trình/ })).not.toBeInTheDocument();
});
it('trạng thái tải lớp có thông báo trợ năng', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path === '/api/auth/me' ? response(student) : new Promise<Response>(() => {})));
  mount('/hoc');
  expect(await screen.findByText('Đang tải danh sách lớp…')).toHaveAttribute('role', 'status');
});
it('quản trị hiển thị ba hàng với mô tả và nhãn sắp có', async () => {
  vi.stubGlobal('fetch', mockApi({ ...student, system_role: 'admin', classes: [] })); mount('/quan-tri');
  expect(await screen.findByRole('heading', { name: 'Quản trị' })).toBeInTheDocument();
  for (const name of ['Người dùng', 'Môn học', 'Lớp học & ghi danh']) expect(screen.getByRole('heading', { name })).toBeInTheDocument();
  expect(screen.getAllByText('Sắp có')).toHaveLength(3);
});
it('404 có đường về trang chủ theo vai trò', async () => {
  vi.stubGlobal('fetch', mockApi(lecturer)); mount('/khong-ton-tai');
  await waitFor(() => expect(screen.getByRole('link', { name: 'Về trang chủ' })).toHaveAttribute('href', '/giang-day'));
});
it('không có email hỗ trợ thì bỏ câu liên hệ', () => {
  vi.stubEnv('VITE_SUPPORT_EMAIL', ''); vi.stubGlobal('fetch', mockApi()); mount('/login');
  expect(screen.queryByText(/Quên mật khẩu/)).not.toBeInTheDocument();
  expect(screen.queryByText(/email hỗ trợ/)).not.toBeInTheDocument();
});
it('email hỗ trợ lấy từ cấu hình', () => {
  vi.stubEnv('VITE_SUPPORT_EMAIL', 'support@example.test'); vi.stubGlobal('fetch', mockApi()); mount('/login');
  expect(screen.getByRole('link', { name: 'support@example.test' })).toHaveAttribute('href', 'mailto:support@example.test');
});
