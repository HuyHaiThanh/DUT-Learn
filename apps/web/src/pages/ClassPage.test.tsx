import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from '@/App';
import type { ClassDetail, Lesson, Me } from '@/api/types';
import type { Material } from '@/features/materials';

const published: Lesson = { id: 'l1', title: 'Mảng một chiều', position: 2, is_published: true };
const draft: Lesson = { id: 'l2', title: 'Con trỏ', position: 2, is_published: false };
const classroom: ClassDetail = { id: 'c1', course_id: 'course', course_code: 'KTLT', course_name: 'Kỹ thuật lập trình', role: 'student', code: 'KTLT-01', term: '2026-2027.1', status: 'open', content_version: 0, lessons: [published] };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function setup(options: { path?: string; lecturer?: boolean; lessons?: Lesson[]; materials?: Material[]; status?: number; write?: (path: string, init: RequestInit) => Response | Promise<Response>; read?: () => Promise<Response> } = {}) {
  const role = options.lecturer ? 'lecturer' : 'student';
  const me: Me = { id: 'u1', email: 'u@example.test', full_name: 'Nguyễn An', system_role: 'user', classes: [{ class_id: 'c1', role }] };
  const mock = vi.fn(async (path: string, init: RequestInit = {}) => {
    if (path === '/api/auth/me') return response(me);
    if (path === '/api/classes/c1/materials') return response(options.materials ?? []);
    if (path === '/api/classes/c1' && !init?.method) return options.read?.() ?? (options.status ? response({ error: { message: 'Lỗi tải lớp' } }, options.status) : response({ ...classroom, role, lessons: options.lessons ?? classroom.lessons }));
    if (init?.method) return options.write?.(path, init) ?? response(published);
    throw new Error(`Unexpected ${path}`);
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[options.path ?? '/lop/c1']}><App /></MemoryRouter></QueryClientProvider>);
  return { mock, client };
}
afterEach(() => vi.unstubAllGlobals());

it('SV thấy học liệu theo bài và học liệu chung, liên kết tới đúng bản công bố', async () => {
  setup({ materials: [
    { id: 'm1', title: 'Giáo trình mảng', lesson_id: 'l1', kind: 'pdf', active_version_id: 'v1', page_count: 12 },
    { id: 'm2', title: 'Tài liệu tham khảo', lesson_id: null, kind: 'text', active_version_id: 'v2', page_count: 2 },
  ] });
  expect(await screen.findByRole('link', { name: /Giáo trình mảng/ })).toHaveAttribute('href', '/doc/v1?page=1');
  expect(screen.getByRole('link', { name: /Tài liệu tham khảo/ })).toHaveAttribute('href', '/doc/v2?page=1');
  expect(screen.getByRole('heading', { name: 'Học liệu chung của lớp' })).toBeInTheDocument();
  expect(screen.queryByText('Chưa có học liệu')).not.toBeInTheDocument();
});

it('SV chỉ thấy bài công bố, chưa có học liệu và link về đúng vai trò', async () => {
  setup({ lessons: [published, draft] });
  expect(await screen.findByRole('heading', { name: classroom.course_name })).toBeInTheDocument();
  expect(screen.getByText('KTLT-01 · Học kỳ 1, 2026–2027')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: published.title })).toBeInTheDocument();
  expect(screen.queryByText(draft.title)).not.toBeInTheDocument();
  expect(await screen.findByText('Chưa có học liệu')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Thêm bài học' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Quay lại danh sách lớp' })).toHaveAttribute('href', '/hoc');
});
it('SV có trạng thái rỗng', async () => {
  setup({ lessons: [] });
  expect(await screen.findByText('Giảng viên chưa công bố bài học nào.')).toBeInTheDocument();
});
it('GV thấy nhãn, mở thêm bài, focus và Escape trả focus', async () => {
  setup({ lecturer: true, lessons: [published, draft] });
  expect(await screen.findByText('Nháp')).toBeInTheDocument();
  expect(screen.getByText('Đã công bố')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Quay lại danh sách lớp' })).toHaveAttribute('href', '/giang-day');
  const trigger = screen.getByRole('button', { name: 'Thêm bài học' });
  trigger.focus(); fireEvent.click(trigger);
  expect(screen.getByRole('dialog')).toHaveTextContent('Thêm bài học');
  expect(screen.getByLabelText('Tiêu đề')).toHaveFocus();
  fireEvent.keyDown(screen.getByLabelText('Tiêu đề'), { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  await waitFor(() => expect(trigger).toHaveFocus());
});
it('thêm bài gửi tiêu đề trim, CSRF và tải lại lớp', async () => {
  const { mock } = setup({ lecturer: true });
  fireEvent.click(await screen.findByRole('button', { name: 'Thêm bài học' }));
  fireEvent.change(screen.getByLabelText('Tiêu đề'), { target: { value: '  Bài mới  ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu bài học' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const [path, init] = mock.mock.calls.find(([, init]) => init?.method === 'POST')!;
  expect(path).toBe('/api/classes/c1/lessons');
  expect(JSON.parse(String(init?.body))).toEqual({ title: 'Bài mới' });
  expect(new Headers(init?.headers).get('X-DUT-CSRF')).toBe('1');
  expect(mock.mock.calls.filter(([path]) => path === '/api/classes/c1')).toHaveLength(2);
});
it.each([403, 404, 409, 422])('đổi tên giữ dữ liệu và lỗi %s tại hộp thoại', async status => {
  setup({ lecturer: true, write: () => response({ error: { message: `Lỗi ${status}` } }, status) });
  fireEvent.click(await screen.findByRole('button', { name: `Đổi tên: ${published.title}` }));
  expect(screen.getByLabelText('Tiêu đề')).toHaveValue(published.title);
  fireEvent.change(screen.getByLabelText('Tiêu đề'), { target: { value: 'Tên mới' } });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu bài học' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(`Lỗi ${status}`);
  expect(screen.getByLabelText('Tiêu đề')).toHaveValue('Tên mới');
});
it.each([true, false])('công bố/ẩn=%s chỉ gửi khi xác nhận', async isPublished => {
  const lesson = { ...published, is_published: isPublished };
  const { mock } = setup({ lecturer: true, lessons: [lesson] });
  fireEvent.click(await screen.findByRole('button', { name: `${isPublished ? 'Ẩn bài học' : 'Công bố bài học'}: ${lesson.title}` }));
  expect(mock.mock.calls.some(([, init]) => init?.method)).toBe(false);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Hủy' })).toHaveFocus());
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const [path, init] = mock.mock.calls.find(([, init]) => init?.method === 'PATCH')!;
  expect(path).toBe('/api/lessons/l1');
  expect(JSON.parse(String(init?.body))).toEqual({ is_published: !isPublished });
});
it('đổi thứ tự xử lý position trùng và vô hiệu hai biên', async () => {
  const { mock } = setup({ lecturer: true, lessons: [published, draft] });
  expect(await screen.findByRole('button', { name: `Đưa lên: ${published.title}` })).toBeDisabled();
  expect(screen.getByRole('button', { name: `Đưa xuống: ${draft.title}` })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: `Đưa lên: ${draft.title}` }));
  await waitFor(() => expect(mock.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(2));
  const writes = mock.mock.calls.filter(([, init]) => init?.method === 'PATCH');
  expect(writes.map(([path, init]) => [path, JSON.parse(String(init?.body))])).toEqual([
    ['/api/lessons/l2', { position: 0 }], ['/api/lessons/l1', { position: 1 }],
  ]);
});
it('đang gửi chặn đóng và gửi lặp', async () => {
  let resolve!: (value: Response) => void;
  const { mock } = setup({ lecturer: true, write: () => new Promise<Response>(r => { resolve = r; }) });
  fireEvent.click(await screen.findByRole('button', { name: 'Thêm bài học' }));
  fireEvent.change(screen.getByLabelText('Tiêu đề'), { target: { value: 'Mới' } });
  const form = screen.getByRole('form', { name: 'Thêm bài học' });
  fireEvent.submit(form);
  expect(await screen.findByRole('button', { name: 'Đang lưu…' })).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  fireEvent.submit(form);
  expect(mock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  await act(async () => resolve(response(published)));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
});
it('404 có thông báo và link về', async () => {
  setup({ status: 404 });
  expect(await screen.findByRole('alert')).toHaveTextContent('Không tìm thấy lớp hoặc bạn không có quyền xem.');
  expect(screen.getByRole('link', { name: 'Quay lại danh sách lớp' })).toHaveAttribute('href', '/hoc');
});
it('đang tải và lỗi mạng có thể thử lại', async () => {
  let resolve!: (value: Response) => void;
  setup({ read: () => new Promise<Response>(r => { resolve = r; }) });
  expect(await screen.findByText('Đang tải lớp…')).toHaveAttribute('role', 'status');
  await act(async () => resolve(response({}, 500)));
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể kết nối máy chủ');
  fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
  await act(async () => resolve(response(classroom)));
  expect(await screen.findByRole('heading', { name: classroom.course_name })).toBeInTheDocument();
});
it('401 chuyển đăng nhập', async () => {
  setup({ status: 401 });
  expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument();
  expect(screen.getByLabelText('Email')).toBeInTheDocument();
});

it.each([
  ['/lop/c1', 'Bài học'],
  ['/lop/c1/bai-tap', 'Bài tập'],
  ['/lop/c1/bai-tap/new', 'Bài tập'],
  ['/lop/c1/luyen-tap', 'Luyện tập'],
  ['/lop/c1/luyen-tap/new', 'Luyện tập'],
  ['/lop/c1/tien-do', 'Tiến độ'],
])('class navigation selects the current section at %s', async (path, active) => {
  const { mock } = setup({ path });
  const nav = await screen.findByRole('navigation', { name: 'Nội dung lớp' });
  const links = within(nav).getAllByRole('link');
  expect(links).toHaveLength(4);
  expect(links.map(link => [link.textContent, link.getAttribute('href')])).toEqual([
    ['Bài học', '/lop/c1'], ['Bài tập', '/lop/c1/bai-tap'],
    ['Luyện tập', '/lop/c1/luyen-tap'], ['Tiến độ', '/lop/c1/tien-do'],
  ]);
  for (const link of links) {
    if (link.textContent === active) expect(link).toHaveAttribute('aria-current', 'page');
    else expect(link).not.toHaveAttribute('aria-current');
  }
  expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
  expect(mock.mock.calls.filter(([url]) => url === '/api/classes/c1')).toHaveLength(1);
  if (active !== 'Bài học') {
    expect(screen.getByRole('heading', { level: 2, name: active })).toBeInTheDocument();
    expect(screen.getByText('Mục này đang được xây dựng.')).toBeInTheDocument();
    expect(mock.mock.calls.some(([url]) => url.endsWith('/materials'))).toBe(false);
  }
});
it('switching class sections retains the layout and cached class', async () => {
  const { mock } = setup();
  const nav = await screen.findByRole('navigation', { name: 'Nội dung lớp' });
  fireEvent.click(within(nav).getByRole('link', { name: 'Bài tập' }));
  expect(await screen.findByRole('heading', { level: 2, name: 'Bài tập' })).toBeInTheDocument();
  expect(within(nav).getByRole('link', { name: 'Bài tập' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(classroom.course_name);
  expect(mock.mock.calls.filter(([url]) => url === '/api/classes/c1')).toHaveLength(1);
});
it.each(['bai-tap', 'luyen-tap', 'tien-do'])('layout handles 404 before rendering %s', async section => {
  const { mock } = setup({ path: `/lop/c1/${section}`, status: 404 });
  expect(await screen.findByRole('alert')).toHaveTextContent('Không tìm thấy lớp hoặc bạn không có quyền xem.');
  expect(screen.queryByRole('navigation', { name: 'Nội dung lớp' })).not.toBeInTheDocument();
  expect(screen.queryByText('Mục này đang được xây dựng.')).not.toBeInTheDocument();
  expect(mock.mock.calls.some(([url]) => url.endsWith('/materials'))).toBe(false);
});
