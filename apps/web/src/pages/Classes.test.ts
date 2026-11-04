import { describe, expect, it } from 'vitest';
import { formatTerm, greetingName } from './Classes';

describe('formatTerm', () => {
  it('formats academic terms', () => expect(formatTerm('2026-2027.1')).toBe('Học kỳ 1, 2026–2027'));
  it('keeps unknown formats', () => expect(formatTerm('HK hè')).toBe('HK hè'));
});

describe('greetingName', () => {
  it('uses the given name', () => expect(greetingName('Nguyễn Văn Huy')).toBe('Huy'));
  it('falls back to the full name', () => expect(greetingName('Sinh viên 1')).toBe('Sinh viên 1'));
});
