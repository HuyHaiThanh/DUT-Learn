import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, expect, it, vi } from 'vitest';
import { Home } from './Home';

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Home /></QueryClientProvider>);
}
afterEach(() => vi.unstubAllGlobals());
it('hiển thị kết nối và dịch vụ AI chưa sẵn sàng', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', db: true, llm: false }) });
  vi.stubGlobal('fetch', fetchMock);
  mount();
  expect(await screen.findByText('Đã kết nối')).toBeInTheDocument();
  expect(screen.getByText('Chưa sẵn sàng')).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith('/api/health', expect.any(Object));
});
it('hiển thị lỗi kết nối và cho phép thử lại', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
  mount();
  expect(await screen.findByRole('alert')).toHaveTextContent('Không thể kết nối');
  expect(screen.getByRole('button', { name: 'Kiểm tra lại' })).toBeEnabled();
});
