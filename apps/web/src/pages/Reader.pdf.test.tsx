import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
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

it('giữ PDF qua hai lần chuyển trang, zoom, resize; đổi version và unmount thì destroy', async () => {
  let resize!: ResizeObserverCallback;
  vi.stubGlobal('ResizeObserver', class { constructor(callback: ResizeObserverCallback) { resize = callback; } observe() {} disconnect() {} });
  let resolvePage!: (value: Response) => void;
  const pageResponse = () => new Response(JSON.stringify({ page_index: 0, page_label: '1', text: 'PDF text', chunks: [] }), { headers: { 'X-Page-Count': '3', 'X-Material-Kind': 'pdf' } });
  const fetchMock = vi.fn(async (path: string) => {
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
  fireEvent.click(screen.getByRole('link', { name: 'Đổi phiên bản' }));
  await waitFor(() => expect(pdf.getDocument).toHaveBeenCalledTimes(2));
  expect(fetchMock.mock.calls.filter(([path]) => path.endsWith('/file'))).toHaveLength(2);
  expect(pdf.documents[0].destroy).toHaveBeenCalledTimes(1);
  view.unmount();
  expect(pdf.documents[1].destroy).toHaveBeenCalledTimes(1);
});
