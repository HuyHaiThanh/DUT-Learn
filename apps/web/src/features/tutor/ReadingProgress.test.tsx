import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { Reader } from '@/pages/Reader';
import { ContinueReadingSection } from './ReadingProgress';
import { readerContext } from './api';

function response(data: unknown, headers?: Record<string, string>) { return new Response(JSON.stringify(data), { headers }); }
function Path() { const l = useLocation(); return <output data-testid="path">{l.pathname + l.search}</output>; }
function mount(element: React.ReactNode, reader = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/doc/v1']}><Path />{reader ? <Routes><Route path="/doc/:versionId" element={element} /></Routes> : element}</MemoryRouter></QueryClientProvider>);
  return client;
}
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it.each([null, { material_id: 'm1', version_id: 'v1', page_index: 2, page_label: 'iii', material_title: 'Giáo trình C', course_name: 'KTLT', updated_at: '2026-11-17T10:00:00Z' }])('ContinueReading hiện/ẩn theo API %#', async position => {
  const mock = vi.fn(async () => response(position)); vi.stubGlobal('fetch', mock);
  mount(<ContinueReadingSection userId="u1" />);
  await waitFor(() => expect(mock).toHaveBeenCalledOnce());
  await act(async () => {});
  if (position) {
    const link = await screen.findByRole('link', { name: /Tiếp tục đọc/ });
    expect(link).toHaveAttribute('href', '/doc/v1?page=3');
    expect(link).toHaveTextContent('Giáo trình C · tr. iii');
    expect(link).not.toHaveTextContent('câu hỏi với trợ giảng');
  } else expect(screen.queryByRole('link')).not.toBeInTheDocument();
});

function readerApi() {
  let revoked = false;
  const mock = vi.fn(async (path: string, init?: RequestInit) => {
    void init;
    if (path === '/api/auth/me') return response({ id: 'u1', system_role: 'user', classes: [] });
    if (path === '/api/classes') return response([{ id: 'c1' }]);
    if (path === '/api/classes/c1/materials') return response([{ id: 'm1', title: 'Giáo trình C', active_version_id: 'v1' }]);
    if (path.includes('/pages/')) return revoked ? new Response('{}', { status: 404 }) : response({ page_index: path.includes('/1/text') ? 1 : 0, page_label: 'i', text: 'Nội dung nguồn', chunks: [] }, { 'X-Page-Count': '3', 'X-Material-Kind': 'text' });
    if (path.includes('/tutor/sessions?')) return response([]);
    if (path === '/api/reading-position') return new Response(null, { status: 204 });
    if (path === '/api/tutor/ask') return response({ session_id: 's1', message_id: 'a1', status: 'ok', answer: 'Đây là câu trả lời [1]', limitation: null, citations: [{ id: 'cite1', ordinal: 1, material_id: 'm1', material_title: 'Giáo trình', version_id: 'v1', page_index: 1, page_label: 'ii', excerpt: 'nguồn' }] });
    if (path.includes('/citations/')) return response({ version_id: 'v1', page_index: 1, char_start: 0, char_end: 3 });
    throw new Error(`Unexpected ${path}`);
  });
  vi.stubGlobal('fetch', mock);
  return { mock, revoke: () => { revoked = true; } };
}

it('PUT debounce 1 giây, hủy trang cũ khi chuyển nhanh và không lưu khi lỗi', async () => {
  const { mock, revoke } = readerApi();
  const client = mount(<Reader />, true);
  await screen.findByRole('heading', { name: 'Trợ giảng' });
  await waitFor(() => expect(screen.queryByText('Đang tải lịch sử…')).not.toBeInTheDocument());
  vi.useFakeTimers();
  await act(async () => { vi.advanceTimersByTime(500); });
  expect(mock.mock.calls.filter(([path]) => path === '/api/reading-position')).toHaveLength(0);
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }));
  await act(async () => { await vi.advanceTimersByTimeAsync(0); });
  await act(async () => { vi.advanceTimersByTime(999); });
  expect(mock.mock.calls.filter(([path]) => path === '/api/reading-position')).toHaveLength(0);
  await act(async () => { vi.advanceTimersByTime(1); });
  const calls = mock.mock.calls.filter(([path]) => path === '/api/reading-position');
  expect(calls).toHaveLength(1);
  expect(JSON.parse(calls[0][1]!.body as string)).toEqual({ material_id: 'm1', version_id: 'v1', page_index: 1 });
  expect(new Headers(calls[0][1]!.headers).get('X-DUT-CSRF')).toBe('1');
  revoke();
  await act(async () => { await client.invalidateQueries({ queryKey: ['reader'] }); vi.advanceTimersByTime(0); });
  await act(async () => { vi.advanceTimersByTime(2000); });
  expect(mock.mock.calls.filter(([path]) => path === '/api/reading-position')).toHaveLength(1);
  expect(screen.queryByRole('heading', { name: 'Trợ giảng' })).not.toBeInTheDocument();
});

it('tab di động đổi chế độ và trích dẫn cùng tài liệu giữ luồng hỏi đáp, tô sáng đúng trang', async () => {
  vi.stubGlobal('innerWidth', 360);
  readerApi(); mount(<Reader />, true);
  await screen.findByRole('heading', { name: 'Trợ giảng' });
  await waitFor(() => expect(screen.queryByText('Đang tải lịch sử…')).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole('tab', { name: 'Trợ giảng' }));
  expect(document.querySelector('.reader-document')).toHaveAttribute('data-mobile-hidden', 'true');
  fireEvent.change(screen.getByLabelText('Câu hỏi cho trợ giảng'), { target: { value: 'Một câu hỏi?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Hỏi' }));
  const source = await screen.findAllByRole('button', { name: /Mở nguồn 1:/ });
  fireEvent.click(source[0]);
  await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/doc/v1?page=2&hl=0-3'));
  await waitFor(() => expect(document.querySelector('mark')).toHaveTextContent('Nội'));
  expect(screen.getByRole('tab', { name: 'Tài liệu' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByText('Một câu hỏi?')).toBeInTheDocument();
  expect(screen.queryByText('Trợ giảng đã trả lời.')).not.toBeInTheDocument(); // Opening clears only the status.
  fireEvent.click(screen.getByRole('tab', { name: 'Trợ giảng' }));
  expect(document.querySelector('.reader-assistant')).toHaveAttribute('data-mobile-hidden', 'false');
  expect(screen.getByLabelText('Luồng hỏi đáp')).toHaveTextContent('Đây là câu trả lời [1]');
  fireEvent.click(screen.getByRole('tab', { name: 'Tài liệu' }));
  expect(document.querySelector('.reader-assistant')).toHaveAttribute('data-mobile-hidden', 'true');
  expect(document.querySelector('.reader-document')).toHaveAttribute('data-mobile-hidden', 'false');
});

it('ngữ cảnh reader tìm cả version của giảng viên qua API hiện có', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => response(path === '/api/classes' ? [{ id: 'c1' }] : [{ id: 'm1', title: 'Giáo trình C', active_version_id: null, versions: [{ id: 'draft' }] }])));
  expect(await readerContext('draft', new AbortController().signal)).toEqual({ class_id: 'c1', material_id: 'm1', material_title: 'Giáo trình C' });
});
