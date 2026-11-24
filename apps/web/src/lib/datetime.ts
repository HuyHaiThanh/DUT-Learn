export function formatDateTime(iso: string) {
  const parts = new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric', hourCycle: 'h23' }).formatToParts(new Date(iso));
  const part = (name: string) => parts.find(p => p.type === name)?.value;
  return `${part('hour')}:${part('minute')}, ${part('day')}/${part('month')}/${part('year')}`;
}
