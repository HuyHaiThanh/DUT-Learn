import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { ContinueReading } from './ContinueReading';

afterEach(() => vi.unstubAllGlobals());
it('hiển thị props và đường đọc tiếp mà không gọi API', () => {
  const fetchMock = vi.fn();
  vi.stubGlobal('fetch', fetchMock);
  render(<MemoryRouter><ContinueReading to="/lop/c1/tai-lieu/m1" courseName="Kỹ thuật lập trình" title="Giáo trình Lập trình căn bản, chương VII" pageLabel="133" pageCount={199} lastOpenedLabel="21:40 hôm qua" questionCount={2} /></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Tiếp tục đọc/ })).toHaveAttribute('href', '/lop/c1/tai-lieu/m1');
  expect(screen.getByText('Kỹ thuật lập trình · Bạn dừng ở trang 133')).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});
