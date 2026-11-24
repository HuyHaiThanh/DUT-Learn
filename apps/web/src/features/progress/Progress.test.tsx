import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';
import { StrictMode } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { Progress } from '@/pages/class/Progress';
import { Reader } from '@/pages/Reader';
import { TutorPanel } from '@/features/tutor/TutorPanel';
import { sendEvent } from '@/features/events';
import type { ProgressData, StudentProgress } from './api';

const data: ProgressData = {
  activity: { materials_opened: 3, materials_available: 5, questions_asked: 12, citations_opened: 4, last_activity_at: '2026-11-12T16:59:00Z' },
  results: { assignments_submitted: 1, assignments_available: 2, grades: [{ assignment_id: 'a1', title: 'Bài tập mảng', grade: 8.5, published_at: '2026-11-12T16:59:00Z' }], practice_attempted: 4, practice_available: 6, practice_mcq_correct_last: 3, practice_mcq_attempted: 3 },
};
function setup(body: ProgressData | StudentProgress[], lecturer = false, fail = false) {
  const mock = vi.fn(async () => new Response(JSON.stringify(body), { status: fail ? 503 : 200 }));
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/progress']}><Routes><Route element={<Outlet context={{ classroom: { id: 'c1', role: lecturer ? 'lecturer' : 'student' } }} />}><Route path="/progress" element={<Progress />} /></Route></Routes></MemoryRouter></QueryClientProvider>);
  return mock;
}
afterEach(() => vi.unstubAllGlobals());

it('shows student counts, separate sections, grades and the exact note', async () => {
  const mock = setup(data);
  expect(await screen.findByRole('heading', { name: 'Hoạt động học' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'Kết quả' })).toBeInTheDocument();
  for (const [label, value] of [['Học liệu đã mở', '3 / 5'], ['Bài đã nộp', '1 / 2'], ['Luyện tập đã làm', '4 / 6'], ['Trắc nghiệm đúng (lần gần nhất)', '3 / 3']]) {
    expect(screen.getByText(label).parentElement).toHaveTextContent(value);
  }
  expect(screen.getByText(/Bài tập mảng: 8,5\/10/)).toBeInTheDocument();
  expect(screen.getByText('Các số liệu chỉ phản ánh hoạt động đã được ghi nhận trên DUTLearn, không phải đánh giá năng lực.')).toBeInTheDocument();
  expect(document.querySelectorAll('.progress-track[aria-hidden="true"]')).toHaveLength(4);
  expect(mock).toHaveBeenCalledWith('/api/classes/c1/progress/me', expect.anything());
});

it('shows students alphabetically and filters names without ranks', async () => {
  setup(['Trần Bình', 'Nguyễn An'].map((full_name, index) => ({ ...data, full_name, user_id: String(index), last_activity_at: null })), true);
  const table = await screen.findByRole('table');
  const rows = within(table).getAllByRole('row');
  expect(rows[1]).toHaveTextContent('Nguyễn An');
  expect(rows[2]).toHaveTextContent('Trần Bình');
  expect(rows[1]).toHaveTextContent('Chưa có');
  fireEvent.change(screen.getByLabelText('Lọc tên'), { target: { value: 'bình' } });
  expect(within(table).getAllByRole('row')).toHaveLength(2);
  expect(screen.queryByText('Nguyễn An')).not.toBeInTheDocument();
});

it('shows the lecturer empty state', async () => {
  setup([], true);
  expect(await screen.findByText('Lớp chưa có sinh viên.')).toBeInTheDocument();
});

it('shows the student empty state', async () => {
  setup({ activity: { ...data.activity, materials_opened: 0, questions_asked: 0, citations_opened: 0, last_activity_at: null }, results: { ...data.results, assignments_submitted: 0, practice_attempted: 0, grades: [] } });
  expect(await screen.findByText('Chưa có hoạt động nào được ghi nhận.')).toBeInTheDocument();
});

it('retries a failed progress request', async () => {
  const mock = setup(data, false, true);
  fireEvent.click(await screen.findByRole('button', { name: 'Thử lại' }));
  await waitFor(() => expect(mock).toHaveBeenCalledTimes(2));
});

it('silently absorbs event errors with CSRF and all client event types', async () => {
  const mock = vi.fn(async () => { throw new Error('offline'); });
  vi.stubGlobal('fetch', mock);
  for (const type of ['material_opened', 'citation_opened', 'feedback_viewed'] as const) await expect(sendEvent('c1', type, 'ref')).resolves.toBeUndefined();
  const [path, init] = mock.mock.calls[0] as unknown as [string, RequestInit];
  expect(path).toBe('/api/events');
  expect(JSON.parse(String(init.body))).toEqual({ class_id: 'c1', type: 'material_opened', ref_id: 'ref' });
  expect(new Headers(init.headers).get('X-DUT-CSRF')).toBe('1');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it('records one material open across page changes and StrictMode effect replay', async () => {
  const mock = vi.fn(async (path: string) => {
    if (path === '/api/classes') return new Response(JSON.stringify([{ id: 'c1' }]));
    if (path === '/api/classes/c1/materials') return new Response(JSON.stringify([{ id: 'm1', active_version_id: 'v1' }]));
    if (path.includes('/tutor/sessions')) return new Response('[]');
    if (path === '/api/events' || path === '/api/reading-position') return new Response(null, { status: 204 });
    return new Response(JSON.stringify({ page_index: 0, page_label: '1', text: 'Synthetic page', chunks: [] }), { headers: { 'X-Page-Count': '3', 'X-Material-Kind': 'text' } });
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<StrictMode><QueryClientProvider client={client}><MemoryRouter initialEntries={['/doc/v1?page=1']}><Routes><Route path="/doc/:versionId" element={<Reader />} /></Routes></MemoryRouter></QueryClientProvider></StrictMode>);
  await waitFor(() => expect(mock.mock.calls.filter(([path]) => path === '/api/events')).toHaveLength(1));
  fireEvent.click(await screen.findByRole('button', { name: 'Trang sau' }));
  await waitFor(() => expect(screen.getByLabelText('Trang')).toHaveValue(2));
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }));
  await waitFor(() => expect(screen.getByLabelText('Trang')).toHaveValue(3));
  await act(async () => { await client.invalidateQueries({ queryKey: ['reader-context'] }); });
  expect(mock.mock.calls.filter(([path]) => path === '/api/events')).toHaveLength(1);
});

it.each([200, 410])('records a citation only after a successful open (%s)', async status => {
  const mock = vi.fn(async (path: string) => {
    if (path.includes('/tutor/sessions?')) return new Response(JSON.stringify([{ id: 's1', material_id: 'm1', created_at: '2026-11-12' }]));
    if (path.includes('/messages')) return new Response(JSON.stringify([{ id: 'msg', role: 'assistant', status: 'ok', content: 'Synthetic [1]', citations: [{ id: 'cite', ordinal: 1, material_id: 'm1', material_title: 'Synthetic', version_id: 'v1', page_index: 0, page_label: '1', excerpt: 'Synthetic' }] }]));
    if (path === '/api/citations/cite/open') return new Response(JSON.stringify({ version_id: 'v1', page_index: 0, char_start: 0, char_end: 4 }), { status });
    return new Response(null, { status: 204 });
  });
  vi.stubGlobal('fetch', mock);
  render(<MemoryRouter><TutorPanel context={{ class_id: 'c1', material_id: 'm1' }} pageIndex={0} /></MemoryRouter>);
  fireEvent.click((await screen.findAllByRole('button', { name: 'Mở nguồn 1: Synthetic, trang 1' }))[0]);
  if (status === 200) await waitFor(() => expect(mock.mock.calls.filter(([path]) => path === '/api/events')).toHaveLength(1));
  else {
    await screen.findByText('Nguồn này đã bị thu hồi hoặc thay thế.');
    expect(mock.mock.calls.filter(([path]) => path === '/api/events')).toHaveLength(0);
  }
});
