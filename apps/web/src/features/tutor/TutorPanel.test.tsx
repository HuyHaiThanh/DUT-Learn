import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { TutorPanel } from './TutorPanel';
import type { Answer, Citation } from './api';

const citation: Citation = { id: 'cite1', ordinal: 1, material_id: 'm1', material_title: 'Giáo trình C', version_id: 'v1', page_index: 1, page_label: 'ii', excerpt: 'Một đoạn nguồn.' };
const answer: Answer = { session_id: 's1', message_id: 'a1', status: 'ok', answer: 'Giải thích [1]. [9]\n```c\n#include <stdio.h>\na[i] = x < y && y > 0; // [1]\n```\n`[1]` a[1]', citations: [citation], limitation: null };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function Path() { const location = useLocation(); return <output data-testid="path">{location.pathname + location.search}</output>; }
function setup(options: { ask?: () => Promise<Response>; open?: () => Promise<Response>; sessions?: unknown[]; messages?: unknown[] } = {}) {
  let messageNumber = 0;
  const fetchMock = vi.fn(async (path: string, init?: RequestInit): Promise<Response> => {
    void init;
    if (path.includes('/messages')) return response(options.messages ?? []);
    if (path.includes('/tutor/sessions?')) return response(options.sessions ?? []);
    if (path === '/api/tutor/ask') return options.ask ? options.ask() : response({ ...answer, message_id: `a${++messageNumber}` });
    if (path.includes('/citations/')) return options.open ? options.open() : response({ version_id: 'v1', page_index: 1, char_start: 4, char_end: 20 });
    throw new Error(`Unexpected ${path}`);
  });
  vi.stubGlobal('fetch', fetchMock);
  const view = render(<MemoryRouter initialEntries={['/doc/v1']}><Path /><TutorPanel context={{ class_id: 'c1', material_id: 'm1' }} pageIndex={2} /></MemoryRouter>);
  return { fetchMock, ...view };
}
async function ready() { await waitFor(() => expect(screen.queryByText('Đang tải lịch sử…')).not.toBeInTheDocument()); }
function type(value = 'Giải thích vòng lặp?') { fireEvent.change(screen.getByLabelText('Câu hỏi cho trợ giảng'), { target: { value } }); }
function submit() { fireEvent.click(screen.getByRole('button', { name: 'Hỏi' })); }
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

it('nút và Ctrl+Enter gửi đúng dữ liệu, Enter xuống dòng, giữ session và mode', async () => {
  const { fetchMock } = setup(); await ready(); type();
  fireEvent.keyDown(screen.getByLabelText('Câu hỏi cho trợ giảng'), { key: 'Enter' });
  expect(fetchMock.mock.calls.filter(([path]) => path === '/api/tutor/ask')).toHaveLength(0);
  submit();
  await screen.findByText('Trợ giảng đã trả lời.');
  let requests = fetchMock.mock.calls.filter(([path]) => path === '/api/tutor/ask');
  expect(JSON.parse(requests[0][1]!.body as string)).toEqual({ class_id: 'c1', material_id: 'm1', page_index: 2, question: 'Giải thích vòng lặp?', mode: 'answer', session_id: null });
  expect(new Headers(requests[0][1]!.headers).get('X-DUT-CSRF')).toBe('1');
  type('Hướng dẫn vòng lặp');
  fireEvent.click(screen.getByRole('button', { name: 'Gợi ý từng bước' }));
  fireEvent.keyDown(screen.getByLabelText('Câu hỏi cho trợ giảng'), { key: 'Enter', ctrlKey: true });
  await waitFor(() => expect(fetchMock.mock.calls.filter(([path]) => path === '/api/tutor/ask')).toHaveLength(2));
  requests = fetchMock.mock.calls.filter(([path]) => path === '/api/tutor/ask');
  expect(JSON.parse(requests[1][1]!.body as string)).toMatchObject({ mode: 'hint', session_id: 's1' });
});

it('khóa gửi trùng, hiện câu hỏi ngay, chờ 3 giây và hủy abort bỏ kết quả muộn', async () => {
  let resolve!: (value: Response) => void;
  const { fetchMock } = setup({ ask: () => new Promise(r => { resolve = r; }) });
  await ready(); vi.useFakeTimers(); type(); submit();
  expect(within(screen.getByLabelText('Luồng hỏi đáp')).getByText('Giải thích vòng lặp?')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Hỏi' })).toBeDisabled();
  expect(screen.getByText('Trợ giảng đang đọc học liệu…')).toHaveAttribute('aria-live', 'polite');
  fireEvent.keyDown(screen.getByLabelText('Câu hỏi cho trợ giảng'), { key: 'Enter', ctrlKey: true });
  expect(fetchMock.mock.calls.filter(([path]) => path === '/api/tutor/ask')).toHaveLength(1);
  await act(async () => { vi.advanceTimersByTime(3000); });
  expect(screen.getByText(/Đã chờ 3 giây/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Hủy chờ' }));
  const call = fetchMock.mock.calls.find(([path]) => path === '/api/tutor/ask')!;
  expect(call[1]!.signal!.aborted).toBe(true);
  await act(async () => { resolve(response(answer)); });
  expect(screen.queryByText('Trợ giảng đã trả lời.')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Câu hỏi cho trợ giảng')).toHaveValue('Giải thích vòng lặp?');
});

it.each(['v1', 'v2'])('trích dẫn mở %s đúng URL, chỉ marker hợp lệ ngoài code là nút', async versionId => {
  const { fetchMock, container } = setup({ open: async () => response({ version_id: versionId, page_index: 4, char_start: 2, char_end: 18 }) });
  await ready(); type(); submit();
  const buttons = await screen.findAllByRole('button', { name: 'Mở nguồn 1: Giáo trình C, trang ii' });
  expect(buttons).toHaveLength(2); // Inline marker + source list.
  expect(screen.queryByRole('button', { name: /Mở nguồn 9/ })).not.toBeInTheDocument();
  expect(container.querySelector('pre code')!.textContent).toContain('#include <stdio.h>\na[i] = x < y && y > 0; // [1]');
  expect(container.querySelector('pre code button')).toBeNull();
  expect(container.querySelector('script')).toBeNull();
  fireEvent.click(buttons[0]);
  await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent(`/doc/${versionId}?page=5&hl=2-18`));
  expect(fetchMock).toHaveBeenCalledWith('/api/citations/cite1/open', expect.objectContaining({ credentials: 'include', cache: 'no-store' }));
});

it('thiếu căn cứ là thông báo trung tính, limitation hiển thị và focus giữ ở ô hỏi', async () => {
  setup({ ask: async () => response({ ...answer, status: 'insufficient_evidence', answer: 'Chưa đủ căn cứ.', citations: [], limitation: 'Hãy kiểm tra với giảng viên.' }) });
  await ready(); type(); screen.getByLabelText('Câu hỏi cho trợ giảng').focus();
  fireEvent.keyDown(screen.getByLabelText('Câu hỏi cho trợ giảng'), { key: 'Enter', ctrlKey: true });
  expect(await screen.findByText('Chưa đủ căn cứ.')).toBeInTheDocument();
  expect(screen.getByText('Chưa đủ căn cứ.').closest('.tutor-neutral')).not.toBeNull();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(screen.getByText('Hãy kiểm tra với giảng viên.')).toBeInTheDocument();
  expect(screen.getByLabelText('Câu hỏi cho trợ giảng')).toHaveFocus();
});

it.each([
  [409, 'Học liệu vừa được thay đổi, hãy hỏi lại.'],
  [429, 'Trợ giảng đang bận, vui lòng thử lại sau ít phút.'],
  [503, 'Trợ giảng tạm thời không sẵn sàng.'],
  [504, 'Trợ giảng phản hồi quá lâu, hãy thử lại.'],
  [0, 'Không kết nối được máy chủ.'],
] as const)('lỗi %s giữ câu hỏi, retry đúng payload dù ô hỏi đã thay đổi', async (status, text) => {
  let count = 0;
  const { fetchMock } = setup({ ask: async () => { if (count++ > 0) return response(answer); if (!status) throw new TypeError('network'); return response({ error: { code: status === 409 ? 'source_changed' : 'error' } }, status); } });
  await ready(); type(); submit();
  expect(await screen.findByRole('alert')).toHaveTextContent(text);
  expect(screen.getByLabelText('Câu hỏi cho trợ giảng')).toHaveValue('Giải thích vòng lặp?');
  type('Câu hỏi khác'); fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
  await screen.findByText('Trợ giảng đã trả lời.');
  const calls = fetchMock.mock.calls.filter(([path]) => path === '/api/tutor/ask');
  expect(calls[0][1]!.body).toBe(calls[1][1]!.body);
  expect(screen.getByLabelText('Câu hỏi cho trợ giảng')).toHaveValue('Câu hỏi khác');
});

it('410 mở nguồn có thông báo tại chỗ', async () => {
  setup({ open: async () => response({}, 410) }); await ready(); type(); submit();
  fireEvent.click((await screen.findAllByRole('button', { name: /Mở nguồn 1:/ }))[0]);
  expect(await screen.findByText('Nguồn này đã bị thu hồi hoặc thay thế.')).toBeInTheDocument();
  expect(screen.getByTestId('path')).toHaveTextContent('/doc/v1');
});

it('lịch sử chọn session mới nhất đúng material, source_withdrawn ẩn nội dung và nguồn; session mới null', async () => {
  const { fetchMock } = setup({ sessions: [{ id: 'wrong', material_id: 'm2', created_at: '2026-11-18' }, { id: 'old', material_id: 'm1', created_at: '2026-11-01' }, { id: 'recent', material_id: 'm1', created_at: '2026-11-17' }], messages: [{ id: 'a0', role: 'assistant', content: 'Không được lộ', status: 'source_withdrawn', notice: 'Nguồn của câu trả lời đã bị thu hồi.', citations: [citation] }] });
  expect(await screen.findByText('Nguồn của câu trả lời đã bị thu hồi.')).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith('/api/tutor/sessions/recent/messages', expect.anything());
  expect(screen.queryByText('Không được lộ')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Mở nguồn/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Cuộc hỏi đáp mới' })); type(); submit();
  await screen.findByText('Trợ giảng đã trả lời.');
  const call = fetchMock.mock.calls.find(([path]) => path === '/api/tutor/ask')!;
  expect(JSON.parse(call[1]!.body as string).session_id).toBeNull();
});

it('chặn câu hỏi rỗng hoặc quá 2000 ký tự cả nút và Ctrl+Enter', async () => {
  const { fetchMock } = setup(); await ready();
  expect(screen.getByRole('button', { name: 'Hỏi' })).toBeDisabled();
  type('x'.repeat(2001));
  expect(screen.getByLabelText('Câu hỏi cho trợ giảng')).toHaveAttribute('aria-invalid', 'true');
  expect(screen.getByRole('button', { name: 'Hỏi' })).toBeDisabled();
  fireEvent.keyDown(screen.getByLabelText('Câu hỏi cho trợ giảng'), { key: 'Enter', ctrlKey: true });
  expect(fetchMock.mock.calls.filter(([path]) => path === '/api/tutor/ask')).toHaveLength(0);
});

it('401 khi hỏi chuyển tới login', async () => {
  setup({ ask: async () => response({}, 401) }); await ready(); type(); submit();
  await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/login'));
});

it('lịch sử đang tải có thể bắt đầu mới và bỏ kết quả lịch sử muộn', async () => {
  let resolve!: (value: Response) => void;
  vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(r => { resolve = r; })));
  render(<MemoryRouter><TutorPanel context={{ class_id: 'c1', material_id: 'm1' }} pageIndex={0} /></MemoryRouter>);
  fireEvent.click(screen.getByRole('button', { name: 'Cuộc hỏi đáp mới' }));
  await act(async () => { resolve(response([{ id: 'old', material_id: 'm1', created_at: '2026' }])); });
  expect(screen.queryByText('Đang tải lịch sử…')).not.toBeInTheDocument();
  expect(within(screen.getByRole('region', { name: 'Trợ giảng' })).getByLabelText('Câu hỏi cho trợ giảng')).toBeInTheDocument();
});
