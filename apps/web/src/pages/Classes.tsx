import { useQuery } from '@tanstack/react-query';
import { Link, useOutletContext } from 'react-router-dom';
import { apiFetch } from '@/api/client';
import type { ClassRole, ClassSummary, Me } from '@/api/types';
import { homePath, isUnauthorized } from '@/features/auth';
import { Chevron } from '@/components/icons';
import { LoginRedirect, RetryError } from '@/components/feedback';

/** "2026-2027.1" → "Học kỳ 1, 2026–2027"; giữ nguyên nếu không đúng dạng. */
export function formatTerm(term: string): string {
  const m = /^(\d{4})-(\d{4})\.(\d)$/.exec(term);
  return m ? `Học kỳ ${m[3]}, ${m[1]}–${m[2]}` : term;
}

/** Tên gọi tiếng Việt là từ cuối; nếu từ cuối không phải chữ (vd. "Sinh viên 1") thì dùng cả họ tên. */
export function greetingName(fullName: string): string {
  const words = fullName.trim().split(/\s+/);
  const last = words.at(-1) ?? '';
  return /^\p{L}+$/u.test(last) && words.length > 1 ? last : fullName.trim();
}

export function Classes({ role }: { role: ClassRole }) {
  const me = useOutletContext<Me>();
  const classes = useQuery({ queryKey: ['classes', me.id], queryFn: () => apiFetch<ClassSummary[]>('/classes'), retry: false });
  if (isUnauthorized(classes.error)) return <LoginRedirect />;
  const rows = classes.data?.filter(c => c.role === role && c.status === 'open' && me.classes.some(m => m.class_id === c.id && m.role === role)) ?? [];
  const terms = [...new Set(rows.map(c => c.term))];
  const givenName = greetingName(me.full_name);
  return <>
    <div className="page-heading"><h1>{role === 'student' ? `Chào ${givenName}` : 'Lớp phụ trách'}</h1>
      {terms.length > 0 && <p>{terms.map(formatTerm).join(' · ')}</p>}
    </div>
    <section aria-labelledby="classes-heading" aria-busy={classes.isFetching}>
      <h2 id="classes-heading" className="section-title">{role === 'student' ? 'Lớp đang học' : 'Lớp đang giảng dạy'}</h2>
      {classes.isPending ? <div className="state-panel" role="status">Đang tải danh sách lớp…</div> : classes.isError ? <RetryError homeTo={homePath(me)} retry={() => void classes.refetch()} /> : rows.length ? <div className="list-panel">{rows.map(c => <Link className="class-row" key={c.id} to={`/lop/${encodeURIComponent(c.id)}`}>
        <span className="class-copy"><span className="row-title">{c.course_name}</span><span className="metadata">{c.code} · {formatTerm(c.term)}{role === 'lecturer' && ' · vai trò giảng viên'}</span></span><Chevron />
      </Link>)}</div> : <div className="state-panel"><h3>{role === 'student' ? 'Bạn chưa được ghi danh lớp nào' : 'Bạn chưa được phân công lớp nào'}</h3><p>Vui lòng liên hệ giảng viên hoặc quản trị viên để được hỗ trợ.</p></div>}
      {role === 'student' && <p className="class-note">Đợt thử nghiệm chỉ gồm học phần Kỹ thuật lập trình. Không thấy lớp của bạn? Liên hệ giảng viên phụ trách để được ghi danh.</p>}
    </section>
  </>;
}
