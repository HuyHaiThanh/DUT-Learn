import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { HighlightedText, Reader } from './Reader';

function Location() { return <output data-testid="location">{useLocation().search}</output>; }
function setup(entry = '/doc/v1?page=1', fail?: number, withContext = false, text = 'A😀 Nội dung trang') {
  const mock = vi.fn(async (path: string) => {
    if (path === '/api/auth/me') return new Response(JSON.stringify({ id: 'u1', system_role: 'user', classes: [] }));
    if (path === '/api/classes') return new Response(JSON.stringify(withContext ? [{ id: 'c1' }] : []));
    if (path === '/api/classes/c1/materials') return new Response(JSON.stringify([{ id: 'm1', title: 'Giáo trình C', active_version_id: 'v1' }]));
    if (path.includes('/tutor/sessions')) return new Response('[]');
    if (path === '/api/events' || path === '/api/reading-position') return new Response('{}');
    return new Response(JSON.stringify(fail ? {} : { page_index: 0, page_label: 'i', text, chunks: [] }), { status: fail ?? 200, headers: { 'X-Page-Count': '3', 'X-Material-Kind': 'text' } });
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[entry]}><Location /><Routes><Route path="/doc/:versionId" element={<Reader />} /></Routes></MemoryRouter></QueryClientProvider>);
  return { mock, client };
}
afterEach(() => vi.unstubAllGlobals());

it('reflows the display while keeping source highlight offsets from the raw page', async () => {
  setup('/doc/v1?page=1&hl=12-15', undefined, false, '😀 Trong câu\nvăn này.\n\nĐoạn mới');
  await screen.findByRole('region', { name: 'Văn bản trang' });
  expect(document.querySelector('.reader-text')).toHaveTextContent('😀 Trong câu văn này.');
  expect(document.querySelector('mark')).toHaveTextContent('văn');
});

it('links to the class and shows the material title from existing lists', async () => {
  const { mock } = setup('/doc/v1?page=1', undefined, true);
  expect(await screen.findByRole('heading', { level: 1, name: 'Giáo trình C' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Về lớp' })).toHaveAttribute('href', '/lop/c1');
  expect(mock).toHaveBeenCalledWith('/api/classes/c1/materials', expect.anything());
});

it('links to the learning home when reader context is unavailable', async () => {
  setup('/doc/v1?page=1', 404);
  await screen.findByRole('alert');
  await waitFor(() => expect(screen.getByRole('link', { name: 'Về lớp' })).toHaveAttribute('href', '/hoc'));
});

it('đọc trang từ URL, tô sáng theo code point và không hiện trợ giảng khi chưa có ngữ cảnh', async () => {
  const { mock } = setup('/doc/v1?page=2&hl=3-6');
  expect(await screen.findByLabelText('Trang')).toHaveValue(2);
  expect(document.querySelector('mark')).toHaveTextContent('Nội');
  expect(mock).toHaveBeenCalledWith('/api/material-versions/v1/pages/1/text', expect.objectContaining({ cache: 'no-store', credentials: 'include' }));
  expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
  expect(document.querySelector('.reader-assistant')).toBeNull();
});

it('nút, ô trang, phím mũi tên và lịch sử thay đổi URL, bỏ highlight khi chuyển trang', async () => {
  setup('/doc/v1?page=1&hl=0-1');
  expect(await screen.findByRole('button', { name: 'Trang trước' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }));
  await waitFor(() => expect(screen.getByLabelText('Trang')).toHaveValue(2));
  expect(screen.getByTestId('location')).toHaveTextContent('?page=2');
  expect(document.querySelector('mark')).toBeNull();
  fireEvent.keyDown(window, { key: 'ArrowRight' });
  await waitFor(() => expect(screen.getByLabelText('Trang')).toHaveValue(3));
  expect(screen.getByRole('button', { name: 'Trang sau' })).toBeDisabled();
  fireEvent.keyDown(window, { key: 'ArrowLeft' });
  await waitFor(() => expect(screen.getByLabelText('Trang')).toHaveValue(2));
  fireEvent.change(screen.getByLabelText('Trang'), { target: { value: '1' } });
  fireEvent.submit(screen.getByLabelText('Trang').closest('form')!);
  await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('?page=1'));
});

it('phím trong ô trang không điều hướng; văn bản không có điều khiển PDF', async () => {
  setup();
  const input = await screen.findByLabelText('Trang');
  fireEvent.keyDown(input, { key: 'ArrowRight' });
  expect(screen.getByTestId('location')).toHaveTextContent('?page=1');
  expect(screen.queryByRole('button', { name: 'Phóng to' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Thu nhỏ' })).not.toBeInTheDocument();
});

it.each([403, 404, 410])('không còn quyền %s có thông báo rõ và không lộ văn bản', async status => {
  setup('/doc/v1?page=1', status);
  expect(await screen.findByRole('alert')).toHaveTextContent('Tài liệu không tồn tại hoặc đã bị thu hồi.');
  expect(screen.queryByText('A😀 Nội dung trang')).not.toBeInTheDocument();
});

it('thu hồi sau khi đã đọc: lỗi refetch gỡ nội dung trang cũ', async () => {
  const { client, mock } = setup();
  expect(await screen.findByText('A😀 Nội dung trang')).toBeInTheDocument();
  mock.mockImplementation(async () => new Response('{}', { status: 404 }));
  await act(async () => { await client.invalidateQueries({ queryKey: ['reader'] }); });
  expect(await screen.findByRole('alert')).toHaveTextContent('đã bị thu hồi');
  expect(screen.queryByText('A😀 Nội dung trang')).not.toBeInTheDocument();
});

it.each(['-1-3', '3-2', '0-999', 'bad'])('highlight không hợp lệ %s hiển thị văn bản an toàn', highlight => {
  const { container } = render(<HighlightedText text="<script>😀</script>" highlight={highlight} />);
  expect(container.textContent).toBe('<script>😀</script>');
  expect(container.querySelector('mark,script')).toBeNull();
});
