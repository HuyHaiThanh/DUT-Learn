import { expect, it } from 'vitest';
import { formatDateTime, formatShortDateTime } from './datetime';

it('formats UTC timestamps in Asia/Ho_Chi_Minh', () => {
  expect(formatDateTime('2026-11-12T16:59:00Z')).toBe('23:59, 12/11/2026');
  expect(formatDateTime('2026-11-12T17:00:00Z')).toBe('00:00, 13/11/2026');
});

it('formats dashboard deadlines as day/month and Vietnam time', () => {
  expect(formatShortDateTime('2026-11-12T16:59:00Z')).toBe('12/11, 23:59');
  expect(formatShortDateTime('2026-11-12T17:00:00Z')).toBe('13/11, 00:00');
});
