import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Link, MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { Reader } from './Reader';

const pdf = vi.hoisted(() => {
  const cancel = vi.fn();
  const render = vi.fn(() => ({ promise: Promise.resolve(), cancel }));
  const getPage = vi.fn(async () => ({ getViewport: () => ({ width: 600, height: 800 }), render }));
  const documents: { getPage: typeof getPage; destroy: ReturnType<typeof vi.fn> }[] = [];
  const getDocument = vi.fn(() => {
    const document = { getPage, destroy: vi.fn(async () => {}) }; documents.push(document);
    return { promise: Promise.resolve(document), destroy: document.destroy };
  });
  return { getDocument, getPage, render, cancel, documents };
});
vi.mock('pdfjs-dist', () => ({ getDocument: pdf.getDocument, GlobalWorkerOptions: {} }));
vi.mock('pdfjs-dist/build/pdf.worker.min.mjs?url', () => ({ default: 'worker.js' }));
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); pdf.documents.length = 0; });

it.each([360, 760])('defaults to text at %spx, permits PDF and clears the PDF loading status after rendering', async width => {
  vi.stubGlobal('innerWidth', width);
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  let finishRender!: () => void;
  pdf.render.mockImplementationOnce(() => ({ promise: new Promise<void>(resolve => { finishRender = resolve; }), cancel: pdf.cancel }));
  const fetchMock = vi.fn(async (path: string) => {
    if (path === '/api/auth/me') return new Response(JSON.stringify({ id: 'u1', system_role: 'user', classes: [] }));
    if (path === '/api/classes') return new Response('[]');
    if (path.endsWith('/file')) return new Response(new Uint8Array([1, 2]));
    return new Response(JSON.stringify({ page_index: 0, page_label: '1', text: 'Trong trường hợp\nn=0 là điều kiện dừng.', chunks: [] }), { headers: { 'X-Page-Count': '3', 'X-Material-Kind': 'pdf' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/doc/v1']}><Routes><Route path="/doc/:versionId" element={<Reader />} /></Routes></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole('button', { name: 'Văn bản' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('region', { name: 'Văn bản trang' })).toHaveTextContent('Trong trường hợp n=0 là điều kiện dừng.');
  expect(fetchMock.mock.calls.some(([path]) => path.endsWith('/file'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'PDF' }));
  await waitFor(() => expect(finishRender).toBeDefined());
  expect(screen.getByText('Đang vẽ trang PDF…')).toBeInTheDocument();
  expect(screen.getByRole('img', { name: 'Trang PDF 1' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Phóng to' })).not.toBeInTheDocument();
  await act(async () => { finishRender(); });
  expect(screen.queryByText('Đang vẽ trang PDF…')).not.toBeInTheDocument();
  expect(document.querySelector('.pdf-viewport')).toHaveAttribute('aria-busy', 'false');
  act(() => { window.innerWidth = 1280; window.dispatchEvent(new Event('resize')); });
  expect(screen.getByRole('button', { name: 'PDF' })).toHaveAttribute('aria-pressed', 'true');
  expect(screen.getByRole('button', { name: 'Phóng to' })).toBeInTheDocument();
});

it('giữ PDF qua hai lần chuyển trang, zoom, resize; đổi version và unmount thì destroy', async () => {
  let resize!: ResizeObserverCallback;
  vi.stubGlobal('ResizeObserver', class { constructor(callback: ResizeObserverCallback) { resize = callback; } observe() {} disconnect() {} });
  let resolvePage!: (value: Response) => void;
  const pageResponse = () => new Response(JSON.stringify({ page_index: 0, page_label: '1', text: 'PDF text', chunks: [] }), { headers: { 'X-Page-Count': '3', 'X-Material-Kind': 'pdf' } });
  const fetchMock = vi.fn(async (path: string) => {
    if (path === '/api/auth/me') return new Response(JSON.stringify({ id: 'u1', system_role: 'user', classes: [] }));
    if (path.endsWith('/file')) return new Response(new Uint8Array([1, 2]));
    if (path === '/api/classes') return new Response('[]');
    if (path.includes('/pages/1/')) return new Promise<Response>(resolve => { resolvePage = resolve; });
    return pageResponse();
  });
  vi.stubGlobal('fetch', fetchMock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/doc/v1']}><Link to="/doc/v2">Đổi phiên bản</Link><Routes><Route path="/doc/:versionId" element={<Reader />} /></Routes></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(pdf.render).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }));
  await waitFor(() => expect(resolvePage).toBeDefined());
  expect(screen.getByRole('img', { name: 'Trang PDF 2' })).toBeInTheDocument();
  await act(async () => { resolvePage(pageResponse()); });
  await waitFor(() => expect(screen.getByLabelText('Trang')).toHaveValue(2));
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }));
  await waitFor(() => expect(screen.getByLabelText('Trang')).toHaveValue(3));
  await waitFor(() => expect(pdf.getPage).toHaveBeenCalledWith(3));
  fireEvent.click(screen.getByRole('button', { name: 'Phóng to' }));
  await act(async () => { resize([{ contentRect: { width: 500 } }] as ResizeObserverEntry[], {} as ResizeObserver); });
  expect(pdf.getDocument).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls.filter(([path]) => path.endsWith('/file'))).toHaveLength(1);
  expect(fetchMock).toHaveBeenCalledWith('/api/material-versions/v1/file', expect.objectContaining({ cache: 'no-store', credentials: 'include' }));
  expect(pdf.cancel).toHaveBeenCalled();
  for (let i = 0; i < 8; i++) fireEvent.click(screen.getByRole('button', { name: 'Thu nhỏ' }));
  expect(screen.getByRole('button', { name: 'Thu nhỏ' })).toBeDisabled();
  expect(screen.getByLabelText('Mức phóng to')).toHaveTextContent('50%');
  for (let i = 0; i < 8; i++) fireEvent.click(screen.getByRole('button', { name: 'Phóng to' }));
  expect(screen.getByRole('button', { name: 'Phóng to' })).toBeDisabled();
  fireEvent.click(screen.getByRole('link', { name: 'Đổi phiên bản' }));
  await waitFor(() => expect(pdf.getDocument).toHaveBeenCalledTimes(2));
  expect(fetchMock.mock.calls.filter(([path]) => path.endsWith('/file'))).toHaveLength(2);
  expect(pdf.documents[0].destroy).toHaveBeenCalledTimes(1);
  view.unmount();
  expect(pdf.documents[1].destroy).toHaveBeenCalledTimes(1);
});

function Path() { const location = useLocation(); return <output data-testid="path">{location.pathname + location.search}</output>; }

it.each(['PDF', 'Văn bản'])('citation switches to text, focuses and scrolls the source, then restores %s and the prior page', async previousMode => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  const scrollIntoView = vi.fn();
  const originalScroll = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = scrollIntoView;
  const citation = { id: 'cite1', ordinal: 1, material_id: 'm1', material_title: 'Giáo trình C', version_id: 'v1', page_index: 2, page_label: '3', excerpt: 'Nguồn kiểm chứng' };
  const response = (value: unknown) => new Response(JSON.stringify(value));
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/auth/me') return response({ id: 'u1', system_role: 'user', classes: [] });
    if (path === '/api/classes') return response([{ id: 'c1', code: 'KTLT-01', course_name: 'Kỹ thuật lập trình' }]);
    if (path.endsWith('/materials')) return response([{ id: 'm1', title: 'Giáo trình C', active_version_id: 'v1' }]);
    if (path.endsWith('/file')) return new Response(new Uint8Array([1, 2]));
    if (path.includes('/tutor/sessions?')) return response([{ id: 's1', material_id: 'm1', created_at: '2026-11-25' }]);
    if (path.endsWith('/messages')) return response([{ id: 'a1', role: 'assistant', status: 'ok', content: 'Kiểm chứng [1]', citations: [citation] }]);
    if (path === '/api/citations/cite1/open') return response({ version_id: 'v1', page_index: 2, char_start: 0, char_end: 5 });
    if (path.includes('/pages/')) return new Response(JSON.stringify({ text: 'Nguồn kiểm chứng', page_label: '3', chunks: [] }), { headers: { 'X-Page-Count': '3', 'X-Material-Kind': 'pdf' } });
    return response({});
  }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  try {
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/doc/v1?page=1']}><Path /><Routes><Route path="/doc/:versionId" element={<Reader />} /></Routes></MemoryRouter></QueryClientProvider>);
    const chip = (await screen.findAllByRole('button', { name: 'Nguồn 1, trang 3' }))[0];
    fireEvent.click(screen.getByRole('button', { name: previousMode }));
    fireEvent.click(screen.getByRole('tab', { name: 'Trợ giảng' }));
    fireEvent.click(chip);
    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/doc/v1?page=3&hl=0-5'));
    expect(screen.getByRole('button', { name: 'Văn bản' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('tab', { name: 'Tài liệu' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('region', { name: 'Đang xem nguồn' })).toHaveTextContent('Đang xem nguồn 1 · trang 3');
    await waitFor(() => expect(screen.getByRole('region', { name: 'Đang xem nguồn' })).toHaveFocus());
    expect(document.querySelector('mark')).toHaveTextContent('Nguồn');
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center', behavior: 'auto' });
    expect(screen.queryByRole('button', { name: 'Phóng to' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Về câu trả lời' }));
    expect(screen.getByRole('tab', { name: 'Trợ giảng' })).toHaveAttribute('aria-selected', 'true');
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Trợ giảng' }), { key: 'ArrowLeft' });
    expect(screen.getByRole('tab', { name: 'Tài liệu' })).toHaveFocus();
    expect(screen.getByLabelText('Trang')).toHaveValue(3);
    fireEvent.click(screen.getByRole('button', { name: 'Về chỗ đang đọc' }));
    await waitFor(() => expect(screen.getByLabelText('Trang')).toHaveValue(1));
    await waitFor(() => expect(screen.getByRole('button', { name: previousMode })).toHaveAttribute('aria-pressed', 'true'));
    expect(screen.queryByRole('region', { name: 'Đang xem nguồn' })).not.toBeInTheDocument();
  } finally { Element.prototype.scrollIntoView = originalScroll; }
});
