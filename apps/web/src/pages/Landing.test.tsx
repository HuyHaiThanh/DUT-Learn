import { fireEvent, render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import type { Me } from '@/api/types';
import { Landing } from './Landing';

function setup(me: Me | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(['me'], me);
  return render(<QueryClientProvider client={client}><MemoryRouter><Landing /></MemoryRouter></QueryClientProvider>);
}
afterEach(() => vi.unstubAllEnvs());

it('makes login the primary action for visitors and links to the workflow', () => {
  setup();
  const hero = screen.getByRole('region', { name: 'Học theo lớp, từ giáo trình đến bài tập' });
  const primary = within(hero).getByRole('link', { name: 'Đăng nhập' });
  expect(primary).toHaveClass('landing-primary');
  expect(primary).toHaveAttribute('href', '/login');
  expect(within(hero).getByRole('link', { name: 'Xem cách hoạt động' })).toHaveAttribute('href', '#cach-hoat-dong');
  expect(within(hero).queryByRole('button')).not.toBeInTheDocument();
  expect(screen.queryByText('Xem một câu trả lời mẫu')).not.toBeInTheDocument();
  expect(screen.queryByText('Học phần thí điểm')).not.toBeInTheDocument();
  const nav = screen.getByRole('navigation', { name: 'Điều hướng trang chủ' });
  expect(within(nav).getByRole('link', { name: 'Cách hoạt động' })).toHaveAttribute('href', '#cach-hoat-dong');
  expect(within(nav).getByRole('link', { name: 'Câu hỏi thường gặp' })).toHaveAttribute('href', '#hoi-dap');
});

it.each([
  ['student', 'user', '/hoc'],
  ['lecturer', 'user', '/giang-day'],
  ['student', 'admin', '/quan-tri'],
] as const)('uses homePath for a signed-in %s with system role %s', (role, systemRole, destination) => {
  setup({ id: 'u1', email: 'user@example.test', full_name: 'Nguyễn An', system_role: systemRole, classes: [{ class_id: 'c1', role }] });
  const hero = screen.getByRole('region', { name: 'Học theo lớp, từ giáo trình đến bài tập' });
  const primary = within(hero).getByRole('link', { name: 'Vào lớp học' });
  expect(primary).toHaveClass('landing-primary');
  expect(primary).toHaveAttribute('href', destination);
  expect(screen.queryByRole('link', { name: 'Đăng nhập' })).not.toBeInTheDocument();
});

it('presents five sections in order, four steps per role and the supplied accessible screenshot', () => {
  setup();
  expect(screen.getAllByRole('region').map(section => section.getAttribute('aria-labelledby'))).toEqual([
    'landing-title', 'landing-workflow-title', 'landing-tutor-title', 'landing-privacy-title', 'landing-faq-title',
  ]);
  for (const role of ['Sinh viên', 'Giảng viên']) {
    const column = screen.getByRole('article', { name: role });
    expect(within(column).getByRole('heading', { name: role })).toBeVisible();
    expect(within(column).getAllByRole('listitem')).toHaveLength(4);
  }
  expect(screen.getByText('Tiến độ chỉ ghi nhận hoạt động và kết quả thật, không dùng để đánh giá năng lực.')).toBeVisible();
  const image = screen.getByRole('img', { name: 'Ảnh chụp màn hình: trang giáo trình bên trái, trợ giảng trả lời kèm số trang nguồn bên phải' });
  expect(image).toHaveAttribute('src', '/landing/reader-tutor.webp');
  expect(image).toHaveAttribute('width', '1280');
  expect(image).toHaveAttribute('height', '800');
  expect(image.closest('a, button')).toBeNull();
  expect(screen.getByText('Ảnh chụp giao diện với dữ liệu minh họa · học phần Kỹ thuật lập trình')).toBeVisible();
});

it('keeps model disclosure, three native FAQ disclosures and attribution', () => {
  setup();
  const privacy = screen.getByRole('region', { name: 'Dữ liệu và quyền truy cập' });
  expect(within(privacy).getByText('Câu hỏi và các đoạn học liệu liên quan được gửi tới mô hình ngôn ngữ do hệ thống cấu hình; tên mô hình hiện dưới mỗi câu trả lời. Bản demo trực tuyến có thể dùng nhà cung cấp mô hình bên ngoài.')).toBeVisible();
  expect(within(privacy).getAllByRole('listitem')).toHaveLength(3);
  const faq = screen.getByRole('region', { name: 'Câu hỏi thường gặp' });
  expect(faq.querySelectorAll('details > summary')).toHaveLength(3);
  expect(within(faq).getByText('Làm sao có tài khoản?').tagName).toBe('SUMMARY');
  expect(within(faq).getByText('Trợ giảng có trả lời mọi câu hỏi?')).toBeVisible();
  expect(within(faq).getByText('Câu trả lời có luôn đúng?')).toBeVisible();
  expect(screen.queryByText('Câu hỏi của tôi được gửi đi đâu?')).not.toBeInTheDocument();
  expect(screen.queryByText(/mỗi ý đều có nguồn/i)).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'CC BY 3.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/3.0/');
});

it('shows the support email only when configured', () => {
  vi.stubEnv('VITE_SUPPORT_EMAIL', '  support@example.test  ');
  const view = setup();
  fireEvent.click(screen.getByText('Làm sao có tài khoản?'));
  expect(screen.getByRole('link', { name: 'support@example.test' })).toHaveAttribute('href', 'mailto:support@example.test');
  view.unmount();
  vi.stubEnv('VITE_SUPPORT_EMAIL', '');
  setup();
  expect(screen.queryByRole('link', { name: 'support@example.test' })).not.toBeInTheDocument();
});
