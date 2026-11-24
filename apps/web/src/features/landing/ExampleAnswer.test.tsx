import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ExampleAnswer } from './ExampleAnswer';
import { example } from './example';

it('mở nguồn nguyên văn, focus panel rồi trở về đúng nút; không gọi mạng', () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch');
  render(<ExampleAnswer />);
  const chip = screen.getByRole('button', { name: 'Nguồn 1, trang 110' });
  fireEvent.click(chip);
  const panel = screen.getByRole('region', { name: 'Nguồn' });
  expect(panel).toHaveFocus();
  expect(within(panel).getByRole('heading', { name: /tr. 110/ })).toBeInTheDocument();
  expect(panel.querySelector('mark')?.textContent).toBe(example.sources[0].highlight);
  expect(chip).toHaveAccessibleDescription('đang mở');
  fireEvent.click(screen.getByRole('button', { name: 'Về câu trả lời' }));
  expect(chip).toHaveFocus();
  fireEvent.click(screen.getAllByRole('button', { name: 'Mở đoạn này' })[1]);
  expect(panel).toHaveFocus();
  expect(panel.querySelector('mark')?.textContent).toBe(example.sources[1].highlight);
  fireEvent.click(screen.getByRole('button', { name: 'Về câu trả lời' }));
  expect(screen.getAllByRole('button', { name: 'Mở đoạn này' })[1]).toHaveFocus();
  expect(fetchMock).not.toHaveBeenCalled(); fetchMock.mockRestore();
});
it('phím mũi tên đổi tab và roving tabindex, hiện từ chối', () => {
  render(<ExampleAnswer />);
  const tabs = screen.getAllByRole('tab');
  fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
  expect(tabs[1]).toHaveFocus();
  expect(tabs[1]).toHaveAttribute('tabindex', '0');
  expect(tabs[0]).toHaveAttribute('tabindex', '-1');
  expect(screen.getByRole('heading', { name: 'Không đủ căn cứ trong học liệu' })).toBeVisible();
  expect(screen.getByText(example.refusal)).toBeVisible();
  fireEvent.keyDown(tabs[1], { key: 'ArrowLeft' });
  expect(tabs[0]).toHaveFocus();
});
it('mọi đoạn highlight xuất hiện nguyên văn trong nguồn', () => {
  for (const source of example.sources) expect(source.text).toContain(source.highlight);
});
