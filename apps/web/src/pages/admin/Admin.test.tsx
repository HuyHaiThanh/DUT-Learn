import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { App } from '@/App';
import type { AdminUser, Course, AdminClass, Member } from '@/api/admin';

const thao: AdminUser = { id: 'u1', full_name: 'Nguyễn Thị Phương Thảo', email: 'nguyen.thi.phuong.thao.102220108@sv1.dut.udn.vn', system_role: 'user', is_active: true };
const duc: AdminUser = { ...thao, id: 'u2', full_name: 'Trần Văn Đức', email: 'duc@example.test', is_active: false };
const course: Course = { id: 'course1', code: '1022201', name: 'Lập trình hướng đối tượng và thiết kế phần mềm ứng dụng nâng cao' };
const classroom: AdminClass = { id: 'c1', course_id: course.id, code: '1022201.2610.24.11A', term: '2026-2027 HK1', status: 'open', content_version: 0 };
const member: Member = { id: 'm1', class_id: classroom.id, user_id: duc.id, role: 'student' };
function response(body: unknown, status = 200) { return status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status }); }
function error(status: number) { return response({ error: { code: status === 409 ? 'conflict' : 'request_failed', message: 'Yêu cầu thất bại.', request_id: 'req1' } }, status); }
function setup(options: { role?: 'user' | 'admin'; users?: AdminUser[]; courses?: Course[]; classes?: AdminClass[]; members?: Member[]; write?: (path: string, init: RequestInit) => Response | Promise<Response>; read?: (path: string) => Response | undefined } = {}, path = '/quan-tri/nguoi-dung') {
  const mock = vi.fn(async (path: string, init: RequestInit = {}) => {
    if (path === '/api/auth/me') return response({ ...thao, system_role: options.role ?? 'admin', classes: [] });
    if (init.method && init.method !== 'GET') return options.write?.(path, init) ?? response({}, 201);
    const override = options.read?.(path); if (override) return override;
    if (path === '/api/admin/users') return response(options.users ?? [thao, duc]);
    if (path === '/api/admin/courses') return response(options.courses ?? [course]);
    if (path === '/api/admin/classes') return response(options.classes ?? [classroom]);
    if (path.endsWith('/members')) return response(options.members ?? [member]);
    throw new Error(`Unexpected request ${path}`);
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
  return { mock, client };
}
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
function fillUser() {
  change('Họ tên', thao.full_name); change('Email', thao.email); change('Mật khẩu tạm', 'x');
}
function writes(mock: ReturnType<typeof setup>['mock'], method: string): [string, RequestInit][] {
  return mock.mock.calls.flatMap(([path, init]) => init?.method === method ? [[path, init] as [string, RequestInit]] : []);
}
afterEach(() => vi.unstubAllGlobals());

it.each(['/quan-tri/nguoi-dung', '/quan-tri/hoc-phan', '/quan-tri/lop-hoc-phan', '/quan-tri/lop-hoc-phan/c1'])('chặn người không phải admin: %s', async path => {
  const { mock } = setup({ role: 'user' }, path);
  expect(await screen.findByRole('alert')).toHaveTextContent('Bạn không có quyền quản trị.');
  expect(mock.mock.calls.some(([path]) => path.startsWith('/api/admin/'))).toBe(false);
});
it('tạo người dùng gửi body, CSRF, tải lại và không hiển thị mật khẩu', async () => {
  const { mock } = setup({ write: () => response(thao, 201) });
  await screen.findByText(thao.email);
  fireEvent.click(screen.getByRole('button', { name: 'Thêm người dùng' })); fillUser();
  expect(screen.getByLabelText('Email')).toHaveAttribute('autocomplete', 'off');
  expect(screen.getByLabelText('Mật khẩu tạm')).toHaveAttribute('autocomplete', 'new-password');
  fireEvent.click(screen.getByRole('button', { name: 'Hiện mật khẩu' }));
  expect(screen.getByLabelText('Mật khẩu tạm')).toHaveAttribute('type', 'text');
  fireEvent.click(screen.getByRole('button', { name: 'Tạo người dùng' }));
  expect(await screen.findByRole('status')).toHaveTextContent(`Đã tạo tài khoản cho ${thao.full_name}.`);
  const [path, init] = writes(mock, 'POST')[0];
  expect(path).toBe('/api/admin/users'); expect(JSON.parse(String(init.body))).toEqual({ full_name: thao.full_name, email: thao.email, password: 'x', system_role: 'user' });
  expect(new Headers(init.headers).get('X-DUT-CSRF')).toBe('1');
  await waitFor(() => expect(mock.mock.calls.filter(([p]) => p === '/api/admin/users')).toHaveLength(3));
  expect(screen.queryByLabelText('Mật khẩu tạm')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Thêm người dùng' }));
  expect(screen.getByLabelText('Mật khẩu tạm')).toHaveValue('');
});
it('409 giữ dữ liệu tạo người dùng', async () => {
  setup({ write: () => error(409) }); await screen.findByText(thao.email);
  fireEvent.click(screen.getByRole('button', { name: 'Thêm người dùng' })); fillUser();
  fireEvent.click(screen.getByRole('button', { name: 'Tạo người dùng' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Email này đã có tài khoản.');
  expect(screen.getByLabelText('Họ tên')).toHaveValue(thao.full_name); expect(screen.getByLabelText('Email')).toHaveValue(thao.email); expect(screen.getByLabelText('Mật khẩu tạm')).toHaveValue('x');
});
it('lọc tên có dấu không phân biệt hoa thường và có phân biệt dấu', async () => {
  setup(); await screen.findByText(thao.email);
  change('Tìm theo tên hoặc email', 'THẢO');
  const table = screen.getByRole('region', { name: 'Danh sách người dùng' });
  expect(within(table).getByText(thao.full_name)).toBeInTheDocument(); expect(within(table).queryByText(duc.full_name)).not.toBeInTheDocument();
  change('Tìm theo tên hoặc email', 'TRAN'); expect(screen.queryByText(duc.full_name)).not.toBeInTheDocument();
  expect(screen.getByText(/Lọc trong 2 người dùng đã tải/)).toBeInTheDocument();
});
it('tạo học phần và đếm số lớp; 409 giữ tên và mã', async () => {
  let conflict = true;
  const { mock } = setup({ write: () => conflict ? error(409) : response(course, 201) }, '/quan-tri/hoc-phan');
  await screen.findByText(course.name);
  expect(within(screen.getByRole('table')).getByText('1')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Thêm học phần' }));
  change('Mã', course.code); change('Tên học phần', course.name);
  fireEvent.click(screen.getByRole('button', { name: 'Tạo học phần' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Mã học phần đã tồn tại.');
  expect(screen.getByLabelText('Tên học phần')).toHaveValue(course.name);
  conflict = false; fireEvent.click(screen.getByRole('button', { name: 'Tạo học phần' }));
  expect(await screen.findByRole('status')).toHaveTextContent(`Đã tạo học phần ${course.name}.`);
  expect(JSON.parse(String(writes(mock, 'POST')[1][1].body))).toEqual({ code: course.code, name: course.name });
  await waitFor(() => expect(mock.mock.calls.filter(([p, init]) => p === '/api/admin/courses' && !init?.method)).toHaveLength(2));
});
it('tạo lớp gửi đúng course_id và trạng thái mặc định', async () => {
  const { mock } = setup({ write: () => response(classroom, 201) }, '/quan-tri/lop-hoc-phan');
  await screen.findByText(classroom.code); fireEvent.click(screen.getByRole('button', { name: 'Thêm lớp học phần' }));
  change('Học phần', course.id); change('Mã lớp', classroom.code); change('Học kỳ', classroom.term);
  fireEvent.click(screen.getByRole('button', { name: 'Tạo lớp học phần' }));
  expect(await screen.findByRole('status')).toHaveTextContent(`Đã tạo lớp ${classroom.code}.`);
  expect(JSON.parse(String(writes(mock, 'POST')[0][1].body))).toEqual({ course_id: course.id, code: classroom.code, term: classroom.term, status: 'open' });
  await waitFor(() => expect(mock.mock.calls.filter(([p, init]) => p === '/api/admin/classes' && !init?.method)).toHaveLength(2));
});
it('chưa có học phần hướng dẫn tạo trước trong hộp thoại', async () => {
  setup({ courses: [], classes: [] }, '/quan-tri/lop-hoc-phan');
  await screen.findByText(/Chưa có lớp học phần/); fireEvent.click(screen.getByRole('button', { name: 'Thêm lớp học phần' }));
  expect(within(screen.getByRole('dialog')).getByRole('link', { name: 'Tạo học phần trước' })).toHaveAttribute('href', '/quan-tri/hoc-phan');
  expect(screen.queryByRole('button', { name: 'Tạo lớp học phần' })).not.toBeInTheDocument();
});
it('lọc lớp theo học kỳ và học phần, tên dài và link thành viên', async () => {
  setup({ classes: [classroom, { ...classroom, id: 'c2', code: 'KHAC', term: '2027', status: 'closed' }] }, '/quan-tri/lop-hoc-phan');
  await screen.findByText(classroom.code);
  expect(screen.getByRole('link', { name: `Quản lý thành viên lớp ${classroom.code}` })).toHaveAttribute('href', '/quan-tri/lop-hoc-phan/c1');
  change('Lọc theo học kỳ', '2027'); expect(screen.queryByText(classroom.code)).not.toBeInTheDocument(); expect(screen.getByText('Đã đóng')).toBeInTheDocument();
  change('Lọc theo học phần', course.id); expect(screen.getByText('KHAC')).toBeInTheDocument();
});
it.each([false, true])('ghi danh ẩn thành viên hiện có và xử lý conflict=%s', async conflict => {
  let enrolled = false;
  const { mock } = setup({ write: () => { if (conflict) return error(409); enrolled = true; return response({ ...member, user_id: thao.id }, 201); }, read: path => path.endsWith('/members') && enrolled ? response([member, { ...member, id: 'm2', user_id: thao.id }]) : undefined }, '/quan-tri/lop-hoc-phan/c1');
  await screen.findByRole('heading', { name: 'Sinh viên (1)' });
  const select = screen.getByLabelText('Người dùng để ghi danh');
  expect(within(select).queryByRole('option', { name: new RegExp(duc.full_name) })).not.toBeInTheDocument();
  change('Tìm người dùng theo tên hoặc email', 'THẢO'); change('Người dùng để ghi danh', thao.id); change('Vai trò trong lớp', 'lecturer');
  fireEvent.click(screen.getByRole('button', { name: 'Ghi danh' }));
  await waitFor(() => expect(writes(mock, 'POST')).toHaveLength(1));
  expect(JSON.parse(String(writes(mock, 'POST')[0][1].body))).toEqual({ user_id: thao.id, role: 'lecturer' });
  expect(writes(mock, 'POST')[0][0]).toBe('/api/admin/classes/c1/members');
  if (conflict) { expect(await screen.findByRole('alert')).toHaveTextContent('Người dùng này đã là thành viên lớp.'); expect(select).toHaveValue(thao.id); }
  else { expect(await screen.findByRole('status')).toHaveTextContent(`Đã ghi danh ${thao.full_name} vào lớp ${classroom.code}.`); await waitFor(() => expect(within(select).queryByRole('option', { name: new RegExp(thao.full_name) })).not.toBeInTheDocument()); }
});
it('gỡ chỉ gọi DELETE khi xác nhận; hủy không gửi', async () => {
  let removed = false;
  const { mock } = setup({ write: () => { removed = true; return response(null, 204); }, read: path => path.endsWith('/members') && removed ? response([]) : undefined }, '/quan-tri/lop-hoc-phan/c1');
  const trigger = await screen.findByRole('button', { name: `Gỡ khỏi lớp: ${duc.full_name}` });
  fireEvent.click(trigger); expect(screen.getByRole('dialog')).toHaveTextContent(`Gỡ ${duc.full_name} khỏi lớp ${classroom.code}? Người này sẽ không còn xem được học liệu của lớp.`);
  expect(writes(mock, 'DELETE')).toHaveLength(0); await waitFor(() => expect(screen.getByRole('button', { name: 'Hủy' })).toHaveFocus()); fireEvent.click(screen.getByRole('button', { name: 'Hủy' })); expect(writes(mock, 'DELETE')).toHaveLength(0);
  fireEvent.click(trigger); fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gỡ' }));
  expect(await screen.findByRole('status')).toHaveTextContent(`Đã gỡ ${duc.full_name} khỏi lớp.`);
  expect(writes(mock, 'DELETE')[0][0]).toBe('/api/admin/classes/c1/members/u2');
  expect(new Headers(writes(mock, 'DELETE')[0][1].headers).get('X-DUT-CSRF')).toBe('1');
  expect(await screen.findByRole('heading', { name: 'Sinh viên (0)' })).toBeInTheDocument();
});
it('lớp trả 404 có đường về danh sách', async () => {
  setup({ read: path => path.endsWith('/members') ? error(404) : undefined }, '/quan-tri/lop-hoc-phan/c1');
  expect(await screen.findByRole('alert')).toHaveTextContent('Không tìm thấy lớp học phần.');
  expect(screen.getByRole('link', { name: 'Về danh sách lớp học phần' })).toHaveAttribute('href', '/quan-tri/lop-hoc-phan');
});
it('hiện user_id rút gọn khi không tra được người dùng', async () => {
  setup({ members: [{ ...member, user_id: 'unknown-user-id' }] }, '/quan-tri/lop-hoc-phan/c1');
  expect(await screen.findByText('Không tìm thấy người dùng')).toBeInTheDocument(); expect(screen.getByText('unknown-…')).toBeInTheDocument();
});
it('lỗi tải có thử lại danh sách', async () => {
  let failed = true;
  setup({ read: path => path === '/api/admin/users' && failed ? error(500) : undefined });
  await screen.findByRole('alert'); failed = false; fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
  await screen.findByText(thao.email);
});
it('403 từ API thông báo không có quyền', async () => {
  setup({ read: path => path === '/api/admin/users' ? error(403) : undefined });
  expect(await screen.findByRole('alert')).toHaveTextContent('Bạn không có quyền quản trị.'); expect(screen.queryByText(thao.email)).not.toBeInTheDocument();
});
it('401 từ API chuyển đăng nhập', async () => {
  setup({ read: path => path === '/api/admin/users' ? error(401) : undefined });
  expect(await screen.findByRole('button', { name: 'Đăng nhập' })).toBeInTheDocument();
});
it.each(['/quan-tri/nguoi-dung', '/quan-tri/hoc-phan', '/quan-tri/lop-hoc-phan', '/quan-tri/lop-hoc-phan/c1'])('có thông báo tải dữ liệu: %s', async path => {
  const mock = vi.fn(async (url: string) => url === '/api/auth/me'
    ? response({ ...thao, system_role: 'admin', classes: [] }) : new Promise<Response>(() => {}));
  vi.stubGlobal('fetch', mock);
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('Đang tải dữ liệu…')).toHaveAttribute('role', 'status');
});
it('lớp không có trong danh sách có thông báo và link về', async () => {
  setup({ classes: [], members: [] }, '/quan-tri/lop-hoc-phan/c1');
  expect(await screen.findByRole('alert')).toHaveTextContent('Không tìm thấy lớp học phần.');
  expect(screen.getByRole('link', { name: 'Về danh sách lớp học phần' })).toBeInTheDocument();
});
it('lỗi 422 giữ form và cho gửi lại', async () => {
  setup({ write: () => error(422) }); await screen.findByText(thao.email);
  fireEvent.click(screen.getByRole('button', { name: 'Thêm người dùng' })); fillUser();
  fireEvent.click(screen.getByRole('button', { name: 'Tạo người dùng' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Yêu cầu thất bại.');
  expect(screen.getByLabelText('Họ tên')).toHaveValue(thao.full_name);
  expect(screen.getByRole('button', { name: 'Tạo người dùng' })).toBeEnabled();
});
it('gỡ đang gửi không đóng được; lỗi giữ hộp thoại để thử lại', async () => {
  let resolve!: (response: Response) => void;
  const { mock } = setup({ write: () => new Promise<Response>(r => { resolve = r; }) }, '/quan-tri/lop-hoc-phan/c1');
  fireEvent.click(await screen.findByRole('button', { name: `Gỡ khỏi lớp: ${duc.full_name}` }));
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gỡ' }));
  expect(await screen.findByRole('button', { name: 'Đang gửi…' })).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  expect(screen.getByRole('dialog')).toBeInTheDocument(); expect(screen.getByRole('button', { name: 'Hủy' })).toBeDisabled();
  expect(writes(mock, 'DELETE')).toHaveLength(1);
  await act(async () => resolve(error(404)));
  expect(await screen.findByRole('alert')).toHaveTextContent('Yêu cầu thất bại.');
  expect(screen.getByRole('button', { name: 'Xác nhận gỡ' })).toBeEnabled();
});
it('focus ô đầu, Esc đóng và trả focus; đang gửi chặn đóng và gửi lặp', async () => {
  let resolve!: (response: Response) => void;
  const { mock } = setup({ write: () => new Promise<Response>(r => { resolve = r; }) });
  await screen.findByText(thao.email); const trigger = screen.getByRole('button', { name: 'Thêm người dùng' });
  trigger.focus(); fireEvent.click(trigger); expect(screen.getByLabelText('Họ tên')).toHaveFocus();
  fireEvent.keyDown(screen.getByLabelText('Họ tên'), { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument()); await waitFor(() => expect(trigger).toHaveFocus());
  fireEvent.click(trigger); fillUser(); const form = screen.getByRole('form', { name: 'Thêm người dùng' }); fireEvent.submit(form);
  expect(await screen.findByRole('button', { name: 'Đang gửi…' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Hủy' })).toBeDisabled();
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' }); expect(screen.getByRole('dialog')).toBeInTheDocument();
  fireEvent.submit(form); expect(writes(mock, 'POST')).toHaveLength(1);
  await act(async () => resolve(response(thao, 201))); await screen.findByRole('status');
});
