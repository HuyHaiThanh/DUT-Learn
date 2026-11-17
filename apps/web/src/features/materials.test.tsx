import { act, fireEvent, render, renderHook, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { LecturerMaterials, MaterialLinks, useMaterials, type Material, type VersionStatus } from './materials';

const report = { page_count: 2, chunk_count: { text: 3, code: 1 }, empty_pages: 0, glued_tokens_before: 4, glued_tokens_after: 1 };
const material = (status: VersionStatus, id: string = status): Material => ({ id, title: `Tài liệu ${id}`, lesson_id: null, kind: 'pdf', visibility: 'students', active_version_id: status === 'published' ? `v-${id}` : null, versions: [{ id: `v-${id}`, version_no: 1, status, error: status === 'failed' ? 'PDF không có văn bản' : null }], quality_report: report });
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function setup(items: Material[], write?: (path: string, init: RequestInit) => Response | Promise<Response>) {
  const mock = vi.fn(async (path: string, init: RequestInit = {}) => {
    if (init.method) return write?.(path, init) ?? response({});
    if (path === '/api/classes/c1/materials') return response(items);
    if (path.startsWith('/api/material-versions/')) return response({ quality_report: { ...report, empty_pages: [] } });
    throw new Error(`Unexpected ${path}`);
  });
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><LecturerMaterials classId="c1" lessons={[{ id: 'l1', title: 'Con trỏ', position: 0, is_published: true }]} /></MemoryRouter></QueryClientProvider>);
  return { mock, client };
}
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

it('GV thấy đủ trạng thái, báo cáo và lỗi theo từng phiên bản', async () => {
  setup((['uploaded', 'processing', 'ready', 'failed', 'published', 'superseded', 'revoked'] as const).map(s => material(s)));
  expect(await screen.findByRole('heading', { name: 'Tài liệu ready' })).toBeInTheDocument();
  for (const label of ['Đã tải lên', 'Đang xử lý', 'Sẵn sàng', 'Xử lý lỗi', 'Đã công bố', 'Đã thay thế', 'Đã thu hồi']) expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  expect(screen.getByRole('alert')).toHaveTextContent('PDF không có văn bản');
  expect(screen.getByText('4 (văn bản: 3, mã: 1)')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Xử lý lại: Tài liệu failed, phiên bản 1' })).toBeInTheDocument();
  expect(screen.getAllByText('Đang công bố: phiên bản 1')).toHaveLength(1);
});

it('thu hồi chỉ gửi sau xác nhận, thông báo hậu quả và focus Hủy', async () => {
  const { mock } = setup([material('published')]);
  fireEvent.click(await screen.findByRole('button', { name: 'Thu hồi: Tài liệu published, phiên bản 1' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('sinh viên sẽ không đọc/trích dẫn được nữa');
  expect(mock.mock.calls.some(([, init]) => init?.method)).toBe(false);
  await waitFor(() => expect(screen.getByRole('button', { name: 'Hủy' })).toHaveFocus());
  fireEvent.click(screen.getByRole('button', { name: 'Hủy' }));
  expect(mock.mock.calls.some(([, init]) => init?.method)).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Thu hồi: Tài liệu published, phiên bản 1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const [path, init] = mock.mock.calls.find(([, init]) => init?.method)!;
  expect(path).toBe('/api/material-versions/v-published/revoke');
  expect(new Headers(init?.headers).get('X-DUT-CSRF')).toBe('1');
});

it('công bố tải báo cáo đúng phiên bản và chờ xác nhận', async () => {
  const { mock } = setup([material('ready')]);
  fireEvent.click(await screen.findByRole('button', { name: 'Công bố: Tài liệu ready, phiên bản 1' }));
  const dialog = screen.getByRole('dialog');
  expect(await within(dialog).findByText('4 (văn bản: 3, mã: 1)')).toBeInTheDocument();
  expect(mock.mock.calls.some(([, init]) => init?.method)).toBe(false);
  fireEvent.click(within(dialog).getByRole('button', { name: 'Xác nhận' }));
  await waitFor(() => expect(mock).toHaveBeenCalledWith('/api/material-versions/v-ready/publish', expect.objectContaining({ method: 'POST' })));
});

it('tải học liệu gửi multipart đầy đủ, không tự đặt Content-Type', async () => {
  const { mock } = setup([]);
  fireEvent.click(screen.getByRole('button', { name: 'Tải học liệu' }));
  fireEvent.change(screen.getByLabelText('Tiêu đề'), { target: { value: 'Con trỏ' } });
  fireEvent.change(screen.getByLabelText('Tệp học liệu'), { target: { files: [new File(['PDF'], 'lesson.pdf', { type: 'application/pdf' })] } });
  fireEvent.change(screen.getByLabelText('Bài học'), { target: { value: 'l1' } });
  fireEvent.change(screen.getByLabelText('Hiển thị cho'), { target: { value: 'lecturers' } });
  fireEvent.change(screen.getByLabelText('Ghi nguồn'), { target: { value: 'VOER' } });
  fireEvent.change(screen.getByLabelText('Giấy phép'), { target: { value: 'CC BY' } });
  fireEvent.submit(screen.getByRole('form', { name: 'Tải học liệu' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  const [path, init] = mock.mock.calls.find(([, init]) => init?.method === 'POST')!;
  expect(path).toBe('/api/classes/c1/materials');
  const form = init?.body as FormData;
  expect(['title', 'lesson_id', 'visibility', 'source_note', 'license_note'].map(k => form.get(k))).toEqual(['Con trỏ', 'l1', 'lecturers', 'VOER', 'CC BY']);
  expect(form.get('file')).toBeInstanceOf(File);
  expect(new Headers(init?.headers).has('Content-Type')).toBe(false);
});

it('sửa hiển thị/bài học và xử lý lỗi API giữ hộp thoại', async () => {
  const { mock } = setup([material('ready')], () => response({ error: { message: 'Không thể lưu' } }, 409));
  fireEvent.click(await screen.findByRole('button', { name: 'Sửa học liệu: Tài liệu ready' }));
  fireEvent.change(screen.getByLabelText('Hiển thị cho'), { target: { value: 'lecturers' } });
  fireEvent.change(screen.getByLabelText('Bài học'), { target: { value: 'l1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Lưu thay đổi' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể lưu');
  const [, init] = mock.mock.calls.find(([, init]) => init?.method === 'PATCH')!;
  expect(JSON.parse(String(init?.body))).toEqual({ title: 'Tài liệu ready', visibility: 'lecturers', lesson_id: 'l1' });
  expect(screen.getByLabelText('Bài học')).toHaveValue('l1');
});

it('SV mở đúng bản active từ học liệu của bài học', () => {
  render(<MemoryRouter><MaterialLinks materials={[material('published')]} /></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Tài liệu published/ })).toHaveAttribute('href', '/doc/v-published?page=1');
});

it.each(['ready', 'failed'] as const)('poll mỗi 3 giây khi đang xử lý, dừng khi %s', async finalStatus => {
  vi.useFakeTimers();
  let status: VersionStatus = 'processing';
  const mock = vi.fn(async () => response([material(status)]));
  vi.stubGlobal('fetch', mock);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const { unmount } = renderHook(() => useMaterials('c1'), { wrapper });
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(mock).toHaveBeenCalledTimes(1);
  status = finalStatus;
  await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
  expect(mock).toHaveBeenCalledTimes(2);
  await act(async () => { await vi.advanceTimersByTimeAsync(9000); });
  expect(mock).toHaveBeenCalledTimes(2);
  unmount(); client.clear();
});

it('tải phiên bản mới chỉ gửi tệp tới học liệu tương ứng', async () => {
  const { mock } = setup([material('published')]);
  fireEvent.click(await screen.findByRole('button', { name: 'Tải phiên bản mới: Tài liệu published' }));
  expect(screen.queryByLabelText('Tiêu đề')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Tệp học liệu'), { target: { files: [new File(['PDF'], 'new.pdf')] } });
  fireEvent.submit(screen.getByRole('form', { name: 'Tải phiên bản mới' }));
  await waitFor(() => expect(mock).toHaveBeenCalledWith('/api/materials/published/versions', expect.objectContaining({ method: 'POST' })));
});

it('xử lý lại phiên bản failed gọi API sau xác nhận', async () => {
  const { mock } = setup([material('failed')]);
  fireEvent.click(await screen.findByRole('button', { name: 'Xử lý lại: Tài liệu failed, phiên bản 1' }));
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận' }));
  await waitFor(() => expect(mock).toHaveBeenCalledWith('/api/material-versions/v-failed/reprocess', expect.objectContaining({ method: 'POST' })));
});
