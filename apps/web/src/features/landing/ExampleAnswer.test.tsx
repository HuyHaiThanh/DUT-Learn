import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { ExampleAnswer } from './ExampleAnswer';
import { example } from './example';

it('opens the verbatim source, focuses it and returns to each citation without network calls', () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch');
  try {
    render(<ExampleAnswer />);
    expect(screen.queryByRole('region', { name: 'Nguồn' })).not.toBeInTheDocument();
    for (const source of example.sources) {
      const chip = screen.getByRole('button', { name: `Nguồn ${source.id}, trang ${source.page}` });
      expect(chip).toHaveAttribute('aria-expanded', 'false');
      chip.focus();
      fireEvent.click(chip);
      const panel = screen.getByRole('region', { name: 'Nguồn' });
      expect(panel).toHaveFocus();
      expect(within(panel).getByText(`${example.material} · tr. ${source.page}`)).toBeVisible();
      expect(panel.querySelector('mark')?.textContent).toBe(source.highlight);
      expect(within(panel).getByText((_, node) => node?.className === 'landing-source-text')).toHaveTextContent(source.text.replace(/\s+/g, ' '));
      expect(chip).toHaveAccessibleDescription('đang mở');
      expect(chip).toHaveAttribute('aria-expanded', 'true');
      fireEvent.click(within(panel).getByRole('button', { name: 'Về câu trả lời' }));
      expect(chip).toHaveFocus();
      expect(chip).toHaveAttribute('aria-expanded', 'false');
      expect(screen.queryByRole('region', { name: 'Nguồn' })).not.toBeInTheDocument();
    }
    expect(fetchMock).not.toHaveBeenCalled();
  } finally { fetchMock.mockRestore(); }
});

it('shows only the recorded in-material example and its provenance, without tabs', () => {
  render(<ExampleAnswer />);
  expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
  expect(screen.queryByRole('tab')).not.toBeInTheDocument();
  expect(screen.queryByRole('tabpanel')).not.toBeInTheDocument();
  expect(screen.getByText(example.question)).toBeVisible();
  expect(screen.queryByText(example.refusalQuestion)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Nguồn 1, trang 110' })).toHaveTextContent('1 · tr.110');
  expect(screen.getByText(/ngày 22\/11\/2026/)).toHaveTextContent(example.model);
  expect(screen.getByText(/Trang này không gọi trợ giảng/)).toBeVisible();
});

it('keeps every highlighted excerpt verbatim in its source', () => {
  for (const source of example.sources) expect(source.text).toContain(source.highlight);
});
