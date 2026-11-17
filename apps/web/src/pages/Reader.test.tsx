import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { HighlightedText, Reader } from './Reader';

function Location() { return <output data-testid="location">{useLocation().search}</output>; }
function setup(entry = '/doc/v1?page=1', fail?: number) {
  const mock = vi.fn(async () => new Response(JSON.stringify(fail ? {} : { page_index: 0, page_label: 'i', text: 'A😀 Nội dung trang', chunks: [] }), { status: fail ?? 200, headers: { 'X-Page-Count': '3', 'X-Material-Kind': 'text' } }));
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[entry]}><Location /><Routes><Route path="/doc/:versionId" element={<Reader />} /></Routes></MemoryRouter></QueryClientProvider>);
  return { mock, client };
}
afterEach(() => vi.unstubAllGlobals());

it('đọc trang từ URL, tô sáng theo code point và không hiện khung trợ giảng', async () => {
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

it('phím trong ô trang không điều hướng; phóng to có giới hạn', async () => {
  setup();
  const input = await screen.findByLabelText('Trang');
  fireEvent.keyDown(input, { key: 'ArrowRight' });
  expect(screen.getByTestId('location')).toHaveTextContent('?page=1');
  fireEvent.click(screen.getByRole('button', { name: 'Phóng to' }));
  expect(screen.getByLabelText('Mức phóng to')).toHaveTextContent('125%');
  for (let i = 0; i < 8; i++) fireEvent.click(screen.getByRole('button', { name: 'Thu nhỏ' }));
  expect(screen.getByRole('button', { name: 'Thu nhỏ' })).toBeDisabled();
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
