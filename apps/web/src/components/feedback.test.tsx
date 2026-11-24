import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { RetryError } from './feedback';

it.each([
  ['user', [], '/hoc'],
  ['user', [{ class_id: 'c1', role: 'lecturer' }], '/giang-day'],
  ['admin', [], '/quan-tri'],
])('uses the authenticated home for %s', (system_role, classes, target) => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  client.setQueryData(['me'], { id: 'u1', system_role, classes });
  render(<QueryClientProvider client={client}><MemoryRouter><RetryError retry={vi.fn()} /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByRole('link', { name: 'Về trang học tập' })).toHaveAttribute('href', target);
});

it('keeps an explicit home target', () => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  client.setQueryData(['me'], { id: 'u1', system_role: 'user', classes: [] });
  render(<QueryClientProvider client={client}><MemoryRouter><RetryError retry={vi.fn()} homeTo="/lop/c1" /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByRole('link', { name: 'Về trang học tập' })).toHaveAttribute('href', '/lop/c1');
});

it('uses the public home without a session', () => {
  const client = new QueryClient({ defaultOptions: { queries: { staleTime: Infinity } } });
  client.setQueryData(['me'], null);
  render(<QueryClientProvider client={client}><MemoryRouter><RetryError retry={vi.fn()} /></MemoryRouter></QueryClientProvider>);
  expect(screen.getByRole('link', { name: 'Về trang chủ' })).toHaveAttribute('href', '/');
});
