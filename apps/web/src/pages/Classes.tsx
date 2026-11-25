import { useQueries, useQuery } from '@tanstack/react-query';
import { Link, useOutletContext } from 'react-router-dom';
import { apiFetch } from '@/api/client';
import type { ClassRole, ClassSummary, Me } from '@/api/types';
import { homePath, isUnauthorized } from '@/features/auth';
import { Chevron, Icon } from '@/components/icons';
import { PageBand } from '@/components/PageBand';
import { StatusPill } from '@/components/StatusPill';
import { deadlineLabel, type Assignment } from '@/features/assignments/shared';
import { formatShortDateTime } from '@/lib/datetime';
import { LoginRedirect, RetryError } from '@/components/feedback';
import { ContinueReadingSection } from '@/features/tutor/ReadingProgress';

/** Format the known term convention, preserving other server labels. */
export function formatTerm(term: string): string {
  const m = /^(\d{4})-(\d{4})\.(\d)$/.exec(term);
  return m ? `Học kỳ ${m[3]}, ${m[1]}–${m[2]}` : term;
}

/** Use the final word only when it is a name rather than an account number. */
export function greetingName(fullName: string): string {
  const words = fullName.trim().split(/\s+/);
  const last = words.at(-1) ?? '';
  return /^\p{L}+$/u.test(last) && words.length > 1 ? last : fullName.trim();
}

export function Classes({ role }: { role: ClassRole }) {
  const me = useOutletContext<Me>();
  const classes = useQuery({ queryKey: ['classes', me.id], queryFn: () => apiFetch<ClassSummary[]>('/classes'), retry: false });
  const rows = classes.data?.filter(c => c.role === role && c.status === 'open' && me.classes.some(m => m.class_id === c.id && m.role === role)) ?? [];
  const assignments = useQueries({ queries: role === 'student' ? rows.map(c => ({ queryKey: ['assignments', c.id, 'list'], queryFn: () => apiFetch<Assignment[]>(`/classes/${c.id}/assignments`), retry: false as const })) : [] });
  if (isUnauthorized(classes.error)) return <LoginRedirect />;
  const memberships = me.classes.filter(m => m.role === role);
  const allClosed = memberships.length > 0 && memberships.every(m => !classes.data?.some(c => c.id === m.class_id && c.status === 'open'));
  const terms = [...new Set(rows.map(c => c.term))];
  const givenName = greetingName(me.full_name);
  return <>
    <PageBand title={role === 'student' ? `Chào ${givenName}` : 'Lớp phụ trách'} meta={terms.length > 0 ? terms.map(formatTerm).join(' · ') : undefined} aside={role === 'student' ? <ContinueReadingSection userId={me.id} /> : undefined} />
    <div className={`page-body${role === 'student' ? ' dashboard-grid' : ''}`}><div>
    {role === 'student' && !classes.isError && <section className="dashboard-tasks" aria-labelledby="tasks-heading"><h2 id="tasks-heading" className="section-title">Việc cần làm</h2>
      {assignments.some(q => isUnauthorized(q.error)) && <LoginRedirect />}
      {classes.isPending || assignments.some(q => q.isPending) ? <p className="state-panel" role="status"><span className="spinner" aria-hidden="true" />Đang tải bài tập…</p> : assignments.some(q => q.isError) ? <RetryError retry={() => { assignments.forEach(q => { if (q.isError) void q.refetch(); }); }} /> : assignments.some(q => q.data?.some(a => a.status === 'published' && !a.my_versions)) ? <div className="task-list">{assignments.flatMap((q, index) => (q.data ?? []).filter(a => a.status === 'published' && !a.my_versions).map(a => <Link className="task-row" key={a.id} to={`/lop/${rows[index].id}/bai-tap/${a.id}`}><span className="feature-icon icon-warn"><Icon name="clipboard" /></span><span><strong>{a.title}</strong><span className="metadata">{rows[index].course_name} · chưa nộp{a.due_at && ` · hạn ${formatShortDateTime(a.due_at)}`}</span></span>{a.due_at && <StatusPill tone={new Date(a.due_at).getTime() < Date.now() ? 'bad' : 'warn'} icon="clock">{deadlineLabel(a.due_at)}</StatusPill>}</Link>))}</div> : <p className="state-panel">Không có bài tập nào đang chờ nộp.</p>}
    </section>}
    <section aria-labelledby="classes-heading" aria-busy={classes.isFetching}>
      <h2 id="classes-heading" className="section-title">{role === 'student' ? 'Lớp đang học' : 'Lớp đang giảng dạy'}</h2>
      {classes.isPending ? <div className="state-panel" role="status"><span className="spinner" aria-hidden="true" />Đang tải danh sách lớp…</div> : classes.isError ? <RetryError homeTo={homePath(me)} retry={() => void classes.refetch()} /> : rows.length ? <div className="class-cards">{rows.map(c => <article className="class-card" key={c.id}><Link className="class-row" to={`/lop/${encodeURIComponent(c.id)}`}>
        <span className="feature-icon icon-sky"><Icon name="book" /></span><span className="class-copy"><span className="row-title">{c.course_name}</span><span className="metadata">{c.code} · {formatTerm(c.term)}{role === 'lecturer' && ' · vai trò giảng viên'}</span></span><span className="class-enter">Vào lớp <Chevron /></span>
      </Link>{role === 'lecturer' && <nav className="class-shortcuts" aria-label={`Liên kết nhanh ${c.code}`}>{[['', 'Bài học'], ['/bai-tap', 'Bài tập'], ['/luyen-tap', 'Luyện tập'], ['/tien-do', 'Tiến độ']].map(([path, label]) => <Link key={path} to={`/lop/${c.id}${path}`}>{label}</Link>)}</nav>}</article>)}</div> : <div className="state-panel"><h3>{allClosed ? 'Các lớp của bạn đã kết thúc.' : role === 'student' ? 'Bạn chưa được ghi danh lớp nào' : 'Bạn chưa được phân công lớp nào'}</h3><p>Vui lòng liên hệ giảng viên hoặc quản trị viên để được hỗ trợ.</p></div>}
      {role === 'student' && <p className="class-note">Đợt thử nghiệm chỉ gồm học phần Kỹ thuật lập trình. Không thấy lớp của bạn? Liên hệ giảng viên phụ trách để được ghi danh.</p>}
    </section>
    </div>{role === 'student' && <aside className="dashboard-aside"><section className="info-card"><h2>Trợ giảng của bạn</h2><ul className="tutor-principles"><li><Icon name="shield" />Chỉ trả lời từ học liệu giảng viên đã công bố</li><li><Icon name="book" />Bấm trích dẫn để mở đúng đoạn trong giáo trình</li><li><Icon name="alert" />Nói rõ khi học liệu không đủ căn cứ</li></ul></section>
      {assignments.some(q => q.data?.some(a => a.my_grade_published)) && <section className="info-card"><h2>Vừa có kết quả</h2>{assignments.flatMap((q, index) => (q.data ?? []).filter(a => a.my_grade_published).map(a => <Link className="result-link" key={a.id} to={`/lop/${rows[index].id}/bai-tap/${a.id}`}>{a.title} — Đã có điểm <Chevron /></Link>))}</section>}
    </aside>}</div>
  </>;
}
