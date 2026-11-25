import { useQuery } from '@tanstack/react-query';
import { Link, useOutletContext, useParams } from 'react-router-dom';
import { apiFetch } from '@/api/client';
import { AssignmentEditor, Confirm, date, ErrorMessage, AssignmentStatus, deadlineLabel, request, type Assignment } from '@/features/assignments/shared';
import { Icon } from '@/components/icons';
import { StatusPill } from '@/components/StatusPill';
import { LecturerDetail } from '@/features/assignments/LecturerDetail';
import { StudentDetail } from '@/features/assignments/StudentDetail';
import type { ClassOutletContext } from './ClassLayout';
import '@/features/assignments/assignments.css';

export function Assignments() {
  const { classroom } = useOutletContext<ClassOutletContext>();
  const params = useParams();
  const assignmentId = params['*']?.split('/')[0];
  return <section className="assignments-section">{assignmentId ? <Detail key={assignmentId} id={assignmentId} classroom={classroom} /> : <List classroom={classroom} />}</section>;
}
function List({ classroom }: Pick<ClassOutletContext, 'classroom'>) {
  const lecturer = classroom.role === 'lecturer';
  const query = useQuery({ queryKey: ['assignments', classroom.id, 'list'], queryFn: () => apiFetch<Assignment[]>(`/classes/${classroom.id}/assignments`), retry: false });
  return <><div className="admin-heading"><h2 className="section-title">Bài tập</h2>{lecturer && <AssignmentEditor classId={classroom.id} lessons={classroom.lessons} />}</div>
    {query.isPending && <p role="status" className="state-panel loading-state"><span className="spinner" aria-hidden="true" />Đang tải…</p>}<ErrorMessage error={query.error} retry={() => void query.refetch()} />
    {query.data && (query.data.length ? <ul className="list-panel">{query.data.map(item => <li key={item.id}>
      <span className="feature-icon icon-warn"><Icon name="clipboard" /></span><h3 className="row-title"><Link to={`/lop/${classroom.id}/bai-tap/${item.id}`}>{item.title}</Link></h3><p className="metadata">Hạn nộp: {date(item.due_at)}</p><AssignmentStatus item={item} />
      {lecturer ? <><p>Số bài đã nộp: {item.submission_count}</p><div className="assignment-actions"><Confirm label={item.status === 'draft' ? 'Công bố' : item.status === 'published' ? 'Đóng nộp bài' : 'Mở lại'} description={item.title} action={() => request(`/assignments/${item.id}`, { status: item.status === 'published' ? 'closed' : 'published' }, 'PATCH')} /><Link to={`/lop/${classroom.id}/bai-tap/${item.id}`}>Xem bài nộp</Link></div></> : <><div className="assignment-actions">{item.due_at && <StatusPill tone={new Date(item.due_at).getTime() < Date.now() ? 'bad' : 'warn'} icon="clock">{deadlineLabel(item.due_at)}</StatusPill>}<StatusPill tone={item.my_versions ? 'ok' : 'warn'} icon={item.my_versions ? 'check' : 'clock'}>{item.my_versions ? `Đã nộp ${item.my_versions} lần` : 'Chưa nộp'}</StatusPill>{item.my_grade_published && <StatusPill tone="ok" icon="check">Đã công bố điểm</StatusPill>}</div></>}
    </li>)}</ul> : <p className="state-panel">{lecturer ? 'Chưa có bài tập. Chọn “Tạo bài tập” để bắt đầu.' : 'Giảng viên chưa giao bài tập nào.'}</p>)}
  </>;
}
function Detail({ id, classroom }: { id: string } & Pick<ClassOutletContext, 'classroom'>) {
  const query = useQuery({ queryKey: ['assignments', id, 'detail'], queryFn: () => apiFetch<Assignment>(`/assignments/${id}`), retry: false });
  if (query.isPending) return <p role="status" className="state-panel loading-state"><span className="spinner" aria-hidden="true" />Đang tải…</p>;
  if (query.isError) return <ErrorMessage error={query.error} retry={() => void query.refetch()} />;
  const item = query.data;
  return <><Link to={`/lop/${classroom.id}/bai-tap`}>Bài tập</Link><div className="admin-heading"><h2 className="section-title">{item.title}</h2>{classroom.role === 'lecturer' && <AssignmentEditor classId={classroom.id} lessons={classroom.lessons} item={item} />}</div>
    <section className="assignment-info"><p>Hạn nộp: {date(item.due_at)}</p><AssignmentStatus item={item} /><div className="assignment-info-grid"><section className="info-card"><h3 className="section-title">Hướng dẫn</h3><p className="assignment-content">{item.instructions}</p></section><section className="info-card"><h3 className="section-title">Tiêu chí chấm</h3><p className="assignment-content">{item.criteria}</p></section></div></section>
    {classroom.role === 'lecturer' ? <LecturerDetail item={item} /> : <StudentDetail item={item} />}
  </>;
}
