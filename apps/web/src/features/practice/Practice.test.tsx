import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { LecturerPractice, StudentPractice } from './Practice';
import type { LecturerQuestion, StudentQuestion } from './types';

const student: StudentQuestion = { id: 'q1', kind: 'mcq', stem: '1 + 1?', options: ['1', '2'], lesson_id: null, my_attempts: 0, my_last_correct: null };
const lecturer: LecturerQuestion = { ...student, answer_key: '1', explanation: 'Một cộng một bằng hai.', origin: 'lecturer', status: 'draft', supersedes_id: null };
const result = { attempt_id: 'a1', is_correct: true, answer_key: '1', explanation: 'Một cộng một bằng hai.', submitted_at: '2026-11-24T12:00:00Z' };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function setup(role: 'student' | 'lecturer', items: StudentQuestion[] | LecturerQuestion[], write?: (path: string, init: RequestInit) => Response | Promise<Response>) {
  const mock = vi.fn(async (path: string, init: RequestInit = {}) => init.method ? write?.(path, init) ?? response(lecturer) : response(items));
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter>{role === 'lecturer' ? <LecturerPractice classId="c1" userId="u1" lessons={[{ id: 'l1', title: 'Bài một', position: 0, is_published: true }]} /> : <StudentPractice classId="c1" userId="u1" />}</MemoryRouter></QueryClientProvider>);
  return mock;
}
afterEach(() => vi.unstubAllGlobals());

it('renders C options and backticks as code without revealing answers', async () => {
  setup('student', [{ ...student, stem: 'Giá trị của `p`?', options: ['int *p = &a;', 'Dùng `p` để đọc'] }]);
  const option = await screen.findByRole('radio', { name: 'int *p = &a;' });
  expect(option.closest('label')?.querySelector('code')).toHaveTextContent('int *p = &a;');
  // jsdom treats <code> as block when computing accessible names and inserts spaces around it.
  expect(screen.getByRole('group', { name: /^Giá trị của\s*p\s*\?$/ }).querySelector('legend code')).toHaveTextContent('p');
  expect(screen.getByRole('radio', { name: /^Dùng\s*p\s*để đọc$/ }).closest('label')?.querySelector('code')).toHaveTextContent('p');
  expect(screen.queryByText('Đáp án đúng')).not.toBeInTheDocument();
  expect(screen.queryByText('Giải thích')).not.toBeInTheDocument();
});

it.each(['mcq', 'short'] as const)('renders backticks in %s stems while preserving unmarked seeded code', async kind => {
  setup('student', [{ ...student, kind, stem: 'Xét `int x = 3;` và int *p = &x;', options: kind === 'mcq' ? student.options : null }]);
  const stem = (await screen.findByText('int x = 3;')).closest('.practice-stem')!;
  expect(stem.querySelector('code')).toHaveTextContent('int x = 3;');
  expect(stem).toHaveTextContent('và int *p = &x;');
  expect(stem.querySelectorAll('code')).toHaveLength(1);
  expect(screen.queryByText('Đáp án đúng')).not.toBeInTheDocument();
});

it('renders backticks in the lecturer question preview', async () => {
  setup('lecturer', [{ ...lecturer, stem: 'Giá trị của `x`?' }]);
  const title = await screen.findByRole('heading', { name: /^Giá trị của\s*x\s*\?$/ });
  expect(title.querySelector('code')).toHaveTextContent('x');
});

it('GV tạo trắc nghiệm gửi đúng chỉ số đáp án và các trường', async () => {
  const mock = setup('lecturer', []);
  await screen.findByText('Chưa có câu luyện tập. Chọn “Thêm câu hỏi”.');
  fireEvent.click(screen.getByRole('button', { name: 'Thêm câu hỏi' }));
  fireEvent.change(screen.getByLabelText('Đề bài'), { target: { value: '1 + 1?' } });
  fireEvent.change(screen.getByLabelText('Phương án 1'), { target: { value: '1' } });
  fireEvent.change(screen.getByLabelText('Phương án 2'), { target: { value: '2' } });
  fireEvent.click(screen.getByRole('radio', { name: 'Đáp án đúng 2' }));
  fireEvent.change(screen.getByLabelText('Bài học (tùy chọn)'), { target: { value: 'l1' } });
  fireEvent.change(screen.getByLabelText('Giải thích'), { target: { value: result.explanation } });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu câu hỏi' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const [path, init] = mock.mock.calls.find(([, init]) => init?.method)!;
  expect(path).toBe('/api/classes/c1/practice');
  expect(JSON.parse(String(init?.body))).toEqual({ kind: 'mcq', stem: '1 + 1?', options: ['1', '2'], answer_key: '1', explanation: result.explanation, lesson_id: 'l1' });
  expect(new Headers(init?.headers).get('X-DUT-CSRF')).toBe('1');
});

it.each([true, false])('SV chỉ thấy kết quả và giải thích sau nộp: %s', async correct => {
  const mock = setup('student', [student], () => response({ ...result, is_correct: correct }));
  await screen.findByText('1 + 1?');
  expect(screen.queryByText('Đáp án đúng')).not.toBeInTheDocument();
  expect(screen.queryByText(result.explanation)).not.toBeInTheDocument();
  expect(screen.getByRole('group', { name: '1 + 1?' })).toBeInTheDocument();
  fireEvent.click(screen.getByRole('radio', { name: '2' }));
  fireEvent.click(screen.getByRole('button', { name: 'Nộp' }));
  expect(await screen.findByText(correct ? 'Đúng' : 'Chưa đúng')).toBeInTheDocument();
  expect(screen.getByText(result.explanation)).toBeInTheDocument();
  expect(screen.getByText('Đã làm 1 lần')).toBeInTheDocument();
  expect(JSON.parse(String(mock.mock.calls.find(([, init]) => init?.method)?.[1]?.body)).response).toBe('1');
});

it('lỗi mạng giữ nguyên payload và key; Làm lại tạo key mới', async () => {
  let first = true;
  const mock = setup('student', [student], () => { if (first) { first = false; throw new TypeError('Failed to fetch'); } return response(result); });
  fireEvent.click(await screen.findByRole('radio', { name: '2' }));
  fireEvent.click(screen.getByRole('button', { name: 'Nộp' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể kết nối máy chủ. Vui lòng thử lại.');
  expect(screen.getByRole('radio', { name: '2' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Nộp' }));
  await screen.findByText('Đúng');
  const writes = () => mock.mock.calls.filter(([, init]) => init?.method).map(([, init]) => JSON.parse(String(init?.body)));
  expect(writes()[0]).toEqual(writes()[1]);
  fireEvent.click(screen.getByRole('button', { name: 'Làm lại' }));
  expect(screen.queryByText(result.explanation)).not.toBeInTheDocument();
  expect(screen.getByRole('radio', { name: '2' })).not.toBeChecked();
  fireEvent.click(screen.getByRole('radio', { name: '1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Nộp' }));
  await screen.findByText('Đã làm 2 lần');
  expect(writes()[2].idempotency_key).not.toBe(writes()[0].idempotency_key);
});

it('chỉ AI nháp có Duyệt, AI nháp không được Công bố', async () => {
  const mock = setup('lecturer', [lecturer, { ...lecturer, id: 'ai', stem: 'AI question', origin: 'ai' }]);
  const ai = (await screen.findByText('AI question')).closest('article')!;
  const human = screen.getByText('1 + 1?').closest('article')!;
  expect(within(human).queryByRole('button', { name: 'Duyệt' })).not.toBeInTheDocument();
  expect(within(ai).queryByRole('button', { name: 'Công bố' })).not.toBeInTheDocument();
  fireEvent.click(within(ai).getByRole('button', { name: 'Duyệt' }));
  await waitFor(() => expect(mock).toHaveBeenCalledWith('/api/practice/ai/approve', expect.objectContaining({ method: 'POST' })));
});

it('sửa câu đang dùng cảnh báo phiên bản và ngừng dùng cần xác nhận', async () => {
  const mock = setup('lecturer', [{ ...lecturer, status: 'published' }]);
  fireEvent.click(await screen.findByRole('button', { name: 'Sửa' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('Câu đang dùng sẽ được thay bằng phiên bản mới; các lần làm cũ giữ nguyên đề cũ.');
  fireEvent.click(screen.getByRole('button', { name: 'Hủy' }));
  fireEvent.click(screen.getByRole('button', { name: 'Ngừng dùng' }));
  expect(mock.mock.calls.filter(([, init]) => init?.method)).toHaveLength(0);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Hủy' })).toHaveFocus());
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
  await waitFor(() => expect(mock).toHaveBeenCalledWith('/api/practice/q1/retire', expect.objectContaining({ method: 'POST' })));
});

it('tự luận hiển thị đáp án mẫu và ghi chú không chấm tự động', async () => {
  setup('student', [{ ...student, kind: 'short', options: null }], () => response({ ...result, is_correct: null, answer_key: 'Đáp án mẫu của GV' }));
  fireEvent.change(await screen.findByLabelText('Câu trả lời'), { target: { value: 'Trả lời' } });
  fireEvent.click(screen.getByRole('button', { name: 'Nộp' }));
  await screen.findByText('Đã ghi nhận câu trả lời');
  expect(screen.getByText('Đáp án mẫu của GV')).toBeInTheDocument();
  expect(screen.getByText('Câu tự luận không chấm tự động; hãy tự đối chiếu với đáp án mẫu.')).toBeInTheDocument();
});
