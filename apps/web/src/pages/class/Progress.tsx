import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { apiFetch } from '@/api/client';
import { LoginRedirect, RetryError } from '@/components/feedback';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { isUnauthorized } from '@/features/auth';
import { formatDateTime as date } from '@/lib/datetime';
import type { ProgressData, StudentProgress } from '@/features/progress/api';
import type { ClassOutletContext } from './ClassLayout';
import '@/features/progress/progress.css';

const note = 'Các số liệu chỉ phản ánh hoạt động đã được ghi nhận trên DUTLearn, không phải đánh giá năng lực.';
function Metric({ label, value, total }: { label: string; value: number; total?: number }) {
  return <div className="progress-metric"><div><span>{label}</span><span>{value}{total !== undefined && ` / ${total}`}</span></div>{total !== undefined && <div className="progress-track" aria-hidden="true"><div style={{ width: `${total > 0 ? Math.min(100, value / total * 100) : 0}%` }} /></div>}</div>;
}
function StudentView({ data }: { data: ProgressData }) {
  const { activity: a, results: r } = data;
  return <>{!a.last_activity_at && r.assignments_submitted === 0 && r.practice_attempted === 0 && <p>Chưa có hoạt động nào được ghi nhận.</p>}<div className="progress-blocks">
    <section className="progress-block"><h3>Hoạt động học</h3><Metric label="Học liệu đã mở" value={a.materials_opened} total={a.materials_available} /><Metric label="Câu hỏi đã hỏi" value={a.questions_asked} /><Metric label="Trích dẫn đã mở" value={a.citations_opened} /></section>
    <section className="progress-block"><h3>Kết quả</h3><Metric label="Bài đã nộp" value={r.assignments_submitted} total={r.assignments_available} /><Metric label="Luyện tập đã làm" value={r.practice_attempted} total={r.practice_available} /><Metric label="Trắc nghiệm đúng (lần gần nhất)" value={r.practice_mcq_correct_last} total={r.practice_mcq_attempted} /><ul className="progress-grades">{r.grades.map(g => <li key={g.assignment_id}>{g.title}: {g.grade.toLocaleString('vi-VN', { maximumFractionDigits: 2 })}/10 · {date(g.published_at)}</li>)}</ul></section>
  </div></>;
}
function LecturerView({ rows }: { rows: StudentProgress[] }) {
  const [filter, setFilter] = useState('');
  const sorted = [...rows].sort((a, b) => a.full_name.localeCompare(b.full_name, 'vi')).filter(s => s.full_name.toLocaleLowerCase('vi').includes(filter.trim().toLocaleLowerCase('vi')));
  if (!rows.length) return <p>Lớp chưa có sinh viên.</p>;
  return <><div className="progress-filter"><Label htmlFor="progress-name">Lọc tên</Label><Input id="progress-name" value={filter} onChange={e => setFilter(e.target.value)} /></div><div className="progress-table-frame" role="region" aria-label="Tiến độ sinh viên" tabIndex={0}><table className="progress-table"><thead><tr>{['Họ tên', 'Học liệu đã mở', 'Câu hỏi đã hỏi', 'Bài đã nộp', 'Luyện tập đã làm', 'Trắc nghiệm đúng (lần gần nhất)', 'Hoạt động gần nhất'].map(h => <th scope="col" key={h}>{h}</th>)}</tr></thead><tbody>{sorted.map(s => <tr key={s.user_id}><th scope="row">{s.full_name}</th><td>{s.activity.materials_opened} / {s.activity.materials_available}</td><td>{s.activity.questions_asked}</td><td>{s.results.assignments_submitted} / {s.results.assignments_available}</td><td>{s.results.practice_attempted} / {s.results.practice_available}</td><td>{s.results.practice_mcq_correct_last} / {s.results.practice_mcq_attempted}</td><td>{s.last_activity_at ? date(s.last_activity_at) : 'Chưa có'}</td></tr>)}</tbody></table></div></>;
}
export function Progress() {
  const { classroom } = useOutletContext<ClassOutletContext>();
  const lecturer = classroom.role === 'lecturer';
  const query = useQuery({ queryKey: ['progress', classroom.id, classroom.role], queryFn: () => apiFetch<ProgressData | StudentProgress[]>(`/classes/${classroom.id}/progress${lecturer ? '' : '/me'}`, { cache: 'no-store' }), retry: false });
  if (isUnauthorized(query.error)) return <LoginRedirect />;
  return <section className="progress-page"><h2 className="section-title">Tiến độ</h2>{query.isPending ? <p role="status">Đang tải tiến độ…</p> : query.isError ? <RetryError retry={() => void query.refetch()} /> : Array.isArray(query.data) ? <LecturerView rows={query.data} /> : <StudentView data={query.data} />}<p className="progress-note">{note}</p></section>;
}
