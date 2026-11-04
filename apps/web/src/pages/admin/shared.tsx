import { useId, type ReactNode } from 'react';
import type { UseQueryResult } from '@tanstack/react-query';
import { ApiError } from '@/api/client';
import { LoginRedirect, RetryError } from '@/components/feedback';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export function QueryState({ queries, children }: { queries: UseQueryResult<unknown, Error>[]; children: ReactNode }) {
  if (queries.some(q => q.error instanceof ApiError && q.error.status === 401)) return <LoginRedirect />;
  if (queries.some(q => q.error instanceof ApiError && q.error.status === 403)) return <p role="alert" className="state-panel">Bạn không có quyền quản trị.</p>;
  if (queries.some(q => q.isError)) return <RetryError homeTo="/quan-tri" retry={() => { queries.forEach(q => { void q.refetch(); }); }} />;
  if (queries.some(q => q.isPending)) return <p role="status" className="state-panel">Đang tải dữ liệu…</p>;
  return children;
}
export function MutationError({ error, conflict }: { error: Error | null; conflict: string }) {
  if (!error) return null;
  if (error instanceof ApiError && error.status === 401) return <LoginRedirect />;
  const message = error instanceof ApiError
    ? error.status === 409 ? conflict : error.status === 403 ? 'Bạn không có quyền quản trị.' : error.message
    : 'Không thể kết nối máy chủ. Vui lòng thử lại.';
  return <p role="alert" className="form-error">{message}</p>;
}
export function Field({ label, ...props }: React.ComponentProps<typeof Input> & { label: string }) {
  const id = useId();
  return <div className="form-field"><Label htmlFor={id}>{label}</Label><Input id={id} {...props} /></div>;
}
export function SelectField({ label, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }) {
  const id = useId();
  return <div className="form-field"><Label htmlFor={id}>{label}</Label><select id={id} className="admin-select" {...props}>{children}</select></div>;
}
export function Table({ label, headers, children }: { label: string; headers: string[]; children: ReactNode }) {
  return <div className="admin-table-scroll" role="region" aria-label={label} tabIndex={0}><table className="admin-table"><caption className="sr-only">{label}</caption><thead><tr>{headers.map(h => <th scope="col" key={h}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>;
}
export function Empty({ children }: { children: ReactNode }) { return <div className="state-panel"><p>{children}</p></div>; }
// Client-side filtering is case-insensitive, preserves Vietnamese accents.
export const matches = (name: string, email: string, search: string) => `${name} ${email}`.normalize('NFC').toLocaleLowerCase('vi').includes(search.trim().normalize('NFC').toLocaleLowerCase('vi'));
