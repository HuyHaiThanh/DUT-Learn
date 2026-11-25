import { expect, it } from 'vitest';
import { reflowPageText } from './pageText';

it('joins only single prose line breaks and keeps paragraph breaks', () => {
  expect(reflowPageText('Trong trường hợp\nn=0 là điều kiện dừng.\n\nĐoạn văn thứ hai\ncòn tiếp.')).toBe('Trong trường hợp n=0 là điều kiện dừng.\n\nĐoạn văn thứ hai còn tiếp.');
});

it('preserves every offset in UTF-16 and Unicode code points, including a citation across the join', () => {
  const original = '😀 Đoạn đầu\ntrường hợp\nn=0 là điều kiện dừng.\n\nĐoạn cuối';
  const displayed = reflowPageText(original);
  const raw = Array.from(original);
  const chars = Array.from(displayed);
  expect(displayed.length).toBe(original.length);
  expect(chars).toHaveLength(raw.length);
  raw.forEach((char, offset) => {
    expect(char === '\n' ? ['\n', ' '] : [char]).toContain(chars[offset]);
  });
  const start = raw.indexOf('t');
  const end = start + Array.from('trường hợp\nn=0').length;
  expect(chars.slice(start, end).join('')).toBe('trường hợp n=0');
  expect(chars.slice(end).join('')).toBe(raw.slice(end).join(''));
});

it.each([' thụt dòng', '\tthụt dòng', '- Mục', '• Mục', '* Mục', '1. Mục', '12) Mục'])('keeps a break before %j', next => {
  const text = `Dòng văn bản\n${next}`;
  expect(reflowPageText(text)).toBe(text);
});

it.each(['int x = 3; ghi chú', 'mở { khối', 'đóng } khối', '#include <stdio.h>', 'Khai báo:', 'Khai báo:  ', 'return 0;', 'if (x) {', '}'])('keeps breaks beside code or a label: %j', line => {
  const text = `Dòng trước\n${line}\nDòng sau`;
  expect(reflowPageText(text)).toBe(text);
});

it.each(['', '\n', 'Đoạn trước\n\nĐoạn sau', 'Đoạn trước\n  \nĐoạn sau', 'Đoạn cuối\n'])('preserves blank lines and boundaries: %j', text => {
  expect(reflowPageText(text)).toBe(text);
});
