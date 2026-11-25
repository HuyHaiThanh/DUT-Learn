import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { Assignments } from '@/pages/class/Assignments';
import type { ClassOutletContext } from '@/pages/class/ClassLayout';
import { date, localDate, type Assignment, type Grade, type Version } from './shared';

const item: Assignment = { id: 'a1', title: 'Con trỏ', instructions: 'Viết chương trình', criteria: 'Đúng kết quả', due_at: null, lesson_id: null, status: 'published', submission_count: 1, my_versions: 0, my_grade_published: false };
const version: Version = { id: 'v1', version_id: 'v1', version_no: 1, content: 'int main() {\n  return 0;\n}', submitted_at: '2026-11-12T16:59:00Z', is_late: false, grade: null };
const grade: Grade = { revision_id: 'g1', revision_no: 1, status: 'draft', grade: 8.25, comment: 'Nhận xét nháp', criteria_snapshot: 'Đúng kết quả', published_at: null };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function setup({ role = 'student', detail = true, assignment = item, versions = [] as Version[], revisions = () => [grade], write = async () => response({}) }:
  { role?: 'student' | 'lecturer'; detail?: boolean; assignment?: Assignment; versions?: Version[]; revisions?: () => Grade[]; write?: (path: string, init: RequestInit) => Promise<Response> } = {}) {
  const mock = vi.fn(async (path: string, init: RequestInit = {}) => {
    if (init?.method) return write(path, init);
    if (path === '/api/classes/c1/assignments') return response([assignment]);
    if (path === '/api/assignments/a1') return response(assignment);
    if (path === '/api/assignments/a1/submissions/me') return response(versions);
    if (path === '/api/assignments/a1/submissions') return response([{ student: { id: 's1', full_name: 'Nguyễn An', email: 'an@example.test' }, versions: [version], latest_grade: grade }]);
    if (path === '/api/submission-versions/v1') return response({ ...version, revisions: revisions() });
    throw new Error(`Unexpected ${path}`);
  });
  vi.stubGlobal('fetch', mock);
  const classroom: ClassOutletContext['classroom'] = { id: 'c1', course_id: 'course1', code: 'L1', course_code: 'CS1', course_name: 'Lập trình', term: '2026.1', content_version: 0, status: 'open', role, lessons: [{ id: 'l1', title: 'Con trỏ', position: 0, is_published: true }] };
  const context = { classroom, me: { id: 'u1', full_name: 'Test', email: 'test@example.test', system_role: 'user', classes: [] } } satisfies ClassOutletContext;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/lop/c1/bai-tap${detail ? '/a1' : ''}`]}><Routes><Route path="/lop/:classId" element={<Outlet context={context} />}><Route path="bai-tap/*" element={<Assignments />} /></Route></Routes></MemoryRouter></QueryClientProvider>);
  return mock;
}
afterEach(() => vi.unstubAllGlobals());

it('shows one criteria heading and puts draft/publish actions together without nesting the confirmation form', async () => {
  setup({ role: 'lecturer' });
  fireEvent.click(await screen.findByRole('button', { name: 'Nguyễn An' }));
  await screen.findByLabelText('Điểm');
  expect(screen.getAllByRole('heading', { name: 'Tiêu chí chấm' })).toHaveLength(1);
  const save = screen.getByRole<HTMLButtonElement>('button', { name: 'Lưu nháp' });
  const publish = screen.getByRole('button', { name: 'Công bố điểm' });
  expect(save.parentElement).toBe(publish.parentElement);
  expect(save.form).toBe(screen.getByLabelText('Điểm').closest('form'));
  expect(publish.closest('form')).toBeNull();
  expect(screen.getByLabelText('Phiên bản bài nộp')).toBeInTheDocument();
});

it('enables publishing after saving 8.50 as numeric 8.5', async () => {
  let saved = grade;
  setup({ role: 'lecturer', revisions: () => [saved], write: async () => {
    saved = { ...grade, grade: 8.5 };
    return response(saved);
  } });
  fireEvent.click(await screen.findByRole('button', { name: 'Nguyễn An' }));
  fireEvent.change(await screen.findByLabelText('Điểm'), { target: { value: '8.50' } });
  expect(screen.getByRole('button', { name: 'Công bố điểm' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Lưu nháp' }));
  await screen.findByText('Đã lưu nháp.');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Công bố điểm' })).toBeEnabled());
  fireEvent.change(screen.getByLabelText('Điểm'), { target: { value: '' } });
  expect(screen.getByRole('button', { name: 'Công bố điểm' })).toBeDisabled();
});

it('creates an assignment with the exact body and Vietnam due date', async () => {
  const mock = setup({ role: 'lecturer', detail: false });
  fireEvent.click(screen.getByRole('button', { name: 'Tạo bài tập' }));
  const dialog = screen.getByRole('dialog');
  fireEvent.change(within(dialog).getByLabelText('Tiêu đề'), { target: { value: 'Bài mới' } });
  fireEvent.change(within(dialog).getByLabelText('Hướng dẫn'), { target: { value: 'Làm bài' } });
  fireEvent.change(within(dialog).getByLabelText('Tiêu chí chấm'), { target: { value: 'Đúng' } });
  fireEvent.change(within(dialog).getByLabelText('Hạn nộp'), { target: { value: '2026-11-12T23:59' } });
  fireEvent.change(within(dialog).getByLabelText('Bài học'), { target: { value: 'l1' } });
  fireEvent.submit(within(dialog).getByRole('form', { name: 'Tạo bài tập' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const [path, init] = mock.mock.calls.find(([, init]) => init?.method === 'POST')!;
  expect(path).toBe('/api/classes/c1/assignments');
  expect(JSON.parse(String(init?.body))).toEqual({ title: 'Bài mới', instructions: 'Làm bài', criteria: 'Đúng', due_at: '2026-11-12T16:59:00.000Z', lesson_id: 'l1' });
  expect(new Headers(init?.headers).get('X-DUT-CSRF')).toBe('1');
});

it('keeps the payload and key after network failure, changes key on editing', async () => {
  const mock = setup({ write: async () => { throw new TypeError('Failed to fetch'); } });
  const input = await screen.findByLabelText('Bài làm');
  fireEvent.change(input, { target: { value: 'Answer' } });
  fireEvent.click(screen.getByRole('button', { name: 'Nộp bài' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Nộp bài' }));
  await waitFor(() => expect(mock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(2));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Nộp bài' })).toBeEnabled());
  fireEvent.change(input, { target: { value: 'Changed' } });
  fireEvent.click(screen.getByRole('button', { name: 'Nộp bài' }));
  await waitFor(() => expect(mock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(3));
  const bodies = mock.mock.calls.filter(([, init]) => init?.method === 'POST').map(([, init]) => JSON.parse(String(init?.body)));
  expect(bodies[0]).toEqual(bodies[1]);
  expect(bodies[0].idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
  expect(bodies[2].idempotency_key).not.toBe(bodies[0].idempotency_key);
  expect(bodies[2].content).toBe('Changed');
});

it('shows only published feedback for each student version', async () => {
  const write = vi.fn(async () => response({}));
  setup({ write, versions: [version, { ...version, id: 'v2', version_id: 'v2', version_no: 2, grade: { revision_id: 'r2', grade: 9.5, comment: 'Đã công bố nhận xét', published_at: '2026-11-13T00:00:00Z' } }] });
  expect(await screen.findByText('Điểm: 9,5/10')).toBeInTheDocument();
  await waitFor(() => expect(write).toHaveBeenCalledWith('/api/events', expect.objectContaining({ body: JSON.stringify({ class_id: 'c1', type: 'feedback_viewed', ref_id: 'r2' }) })));
  expect(screen.getByText('Đã công bố nhận xét')).toBeInTheDocument();
  expect(screen.queryByText('Nhận xét nháp')).not.toBeInTheDocument();
  expect(screen.getAllByText('23:59, 12/11/2026')).toHaveLength(2);
  expect(screen.getByRole('button', { name: 'Nộp lại' })).toBeInTheDocument();
});

it('requires confirmation before publishing a grade and allows cancellation', async () => {
  const mock = setup({ role: 'lecturer' });
  fireEvent.click(await screen.findByRole('button', { name: 'Nguyễn An' }));
  fireEvent.click(await screen.findByRole('button', { name: 'Công bố điểm' }));
  let dialog = screen.getByRole('dialog');
  expect(dialog).toHaveTextContent('Sinh viên sẽ thấy điểm và nhận xét này. Sau khi công bố, muốn sửa phải tạo bản chấm mới.');
  expect(mock.mock.calls.some(([, init]) => init?.method)).toBe(false);
  fireEvent.click(within(dialog).getByRole('button', { name: 'Hủy' }));
  expect(mock.mock.calls.some(([, init]) => init?.method)).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Công bố điểm' }));
  dialog = screen.getByRole('dialog');
  fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận' }));
  await waitFor(() => expect(mock.mock.calls.some(([path, init]) => path === '/api/grade-revisions/g1/publish' && init?.method === 'POST')).toBe(true));
});

it('hides submission controls when closed', async () => {
  setup({ assignment: { ...item, status: 'closed' } });
  expect(await screen.findByText('Bài tập đã đóng nộp.')).toBeInTheDocument();
  expect(screen.queryByLabelText('Bài làm')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Nộp bài|Nộp lại/ })).not.toBeInTheDocument();
});

it('formats date and editor values in Asia/Ho_Chi_Minh', () => {
  expect(date('2026-11-12T16:59:00Z')).toBe('23:59, 12/11/2026');
  expect(localDate('2026-11-12T16:59:00Z')).toBe('2026-11-12T23:59');
});

it.each(['8,5', '8.5'])('sends decimal input %s as a number and displays Vietnamese scores', async input => {
  const mock = setup({ role: 'lecturer' });
  expect(await screen.findByText('Nháp: 8,25')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Nguyễn An' }));
  fireEvent.change(await screen.findByLabelText('Điểm'), { target: { value: input } });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu nháp' }));
  await waitFor(() => expect(mock).toHaveBeenCalledWith('/api/submission-versions/v1/grades', expect.objectContaining({ body: JSON.stringify({ grade: 8.5, comment: grade.comment }) })));
});

it('renders fenced student submission code without fence markers', async () => {
  setup({ versions: [{ ...version, content: 'Lời giải\n```c\nint *p = &a;\n```\nKết thúc' }] });
  await screen.findByText('Lời giải');
  expect(document.querySelector('.submission-content pre code')).toHaveTextContent('int *p = &a;');
  expect(document.querySelector('.submission-content')).not.toHaveTextContent('```');
  expect(screen.getByText('Kết thúc')).toBeInTheDocument();
});

it('renders fenced submission code in lecturer grading', async () => {
  setup({ role: 'lecturer', write: async () => response({}) });
  // The test API returns the selected submission through the same authorized endpoint.
  const original = globalThis.fetch;
  vi.stubGlobal('fetch', vi.fn(async (path: RequestInfo | URL, init?: RequestInit) => String(path) === '/api/submission-versions/v1'
    ? response({ ...version, content: '```c\nreturn 0;\n```', revisions: [grade] }) : original(path, init)));
  fireEvent.click(await screen.findByRole('button', { name: 'Nguyễn An' }));
  await screen.findByLabelText('Điểm');
  expect(document.querySelector('.assignment-grading pre code')).toHaveTextContent('return 0;');
  expect(document.querySelector('.assignment-grading pre')).not.toHaveTextContent('```');
});

it('assignment status pills include an icon and visible words', async () => {
  setup({ detail: false, assignment: { ...item, due_at: '2099-11-30T16:59:00Z', my_grade_published: true } });
  const open = await screen.findByText('Đang mở nộp');
  expect(open.closest('.status-pill')?.querySelector('svg')).not.toBeNull();
  expect(screen.getByText('Chưa nộp').closest('.status-pill')).toBeInTheDocument();
  expect(screen.getByText('Đã công bố điểm').closest('.status-pill')).toBeInTheDocument();
  expect(screen.getByText('Hạn nộp: 23:59, 30/11/2099')).toBeInTheDocument();
});

