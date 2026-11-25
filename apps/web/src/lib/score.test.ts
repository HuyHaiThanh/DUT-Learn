import { expect, it } from 'vitest';
import { formatScore, parseScore } from './score';

it.each([[8.5, '8,5'], [9, '9'], [10, '10'], [8.25, '8,25'], [0, '0']] as const)('formats %s as %s', (value, expected) => {
  expect(formatScore(value)).toBe(expected);
});
it.each(['8,5', '8.5', '8,50', '8.50'])('accepts decimal score %s', value => {
  expect(parseScore(value)).toBe(8.5);
});
it.each(['-1', '10,01', '11', '8,5.0', 'NaN', '8.555', ''])('rejects invalid score %s', value => {
  expect(parseScore(value)).toBeNull();
});
