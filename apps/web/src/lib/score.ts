export function formatScore(value: number): string {
  return value.toLocaleString('vi-VN', { maximumFractionDigits: 2 });
}

export function parseScore(value: string): number | null {
  if (!/^\d{1,2}(?:[.,]\d{1,2})?$/.test(value.trim())) return null;
  const score = Number(value.trim().replace(',', '.'));
  return score >= 0 && score <= 10 ? score : null;
}
