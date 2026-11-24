import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Confirm, date, ErrorMessage, request, useRefresh, type Assignment, type Grade, type Student, type Version } from './shared';

function Grading({ item, versionId }: { item: Assignment; versionId: string }) {
  const refresh = useRefresh();
  const query = useQuery({ queryKey: ['assignments', item.id, 'version', versionId], queryFn: () => apiFetch<Version & { revisions: Grade[] }>(`/submission-versions/${versionId}`), retry: false });
  if (query.isPending) return <p role="status">Đang tải…</p>;
  if (query.isError) return <ErrorMessage error={query.error} retry={() => void query.refetch()} />;
  const version = query.data;
  return <GradeForm key={versionId} item={item} version={version} refresh={refresh} />;
}
function GradeForm({ item, version, refresh }: { item: Assignment; version: Version & { revisions: Grade[] }; refresh: () => Promise<unknown> }) {
  const latest = version.revisions.at(-1);
  const [grade, setGrade] = useState(latest?.grade == null ? '' : String(latest.grade));
  const [comment, setComment] = useState(latest?.comment ?? '');
  const changed = (grade === '' ? null : Number(grade)) !== (latest?.grade ?? null) || comment !== (latest?.comment ?? '');
  const mutation = useMutation({ mutationFn: () => request(`/submission-versions/${version.id}/grades`, { grade: grade === '' ? null : Number(grade), comment }), onSuccess: refresh });
  return <section className="assignment-grading"><div><h3 className="section-title">Bài nộp</h3><pre className="assignment-content">{version.content}</pre></div><div className="assignment-grading-details">
    <section><h3 className="section-title">Tiêu chí chấm</h3><p className="assignment-content">{item.criteria}</p></section>
    <section><h3 className="section-title">Chấm bài</h3>
    <form className="admin-form" onSubmit={e => { e.preventDefault(); if (!mutation.isPending) mutation.mutate(); }}>
      <Label htmlFor="grade-value">Điểm</Label><Input id="grade-value" type="number" min="0" max="10" step="0.25" value={grade} disabled={mutation.isPending} onChange={e => setGrade(e.target.value)} />
      <Label htmlFor="grade-comment">Nhận xét</Label><textarea id="grade-comment" maxLength={5000} value={comment} disabled={mutation.isPending} onChange={e => setComment(e.target.value)} />
      <ErrorMessage error={mutation.error} /><Button type="submit" disabled={mutation.isPending || (grade === '' && !comment.trim())}>{mutation.isPending ? 'Đang gửi…' : 'Lưu nháp'}</Button>
    </form>
    <Confirm label="Công bố điểm" description="Sinh viên sẽ thấy điểm và nhận xét này. Sau khi công bố, muốn sửa phải tạo bản chấm mới." disabled={!latest || latest.status !== 'draft' || changed || mutation.isPending} action={() => request(`/grade-revisions/${latest!.revision_id}/publish`)} />
    {mutation.isSuccess && <p role="status">Đã lưu nháp.</p>}
    </section><section><h3 className="section-title">Lịch sử bản chấm</h3><ul className="submission-list">{version.revisions.map(r => <li className="submission-card" key={r.revision_id}><p>Bản {r.revision_no} · {r.status === 'draft' ? 'Nháp' : 'Đã công bố'}: {r.grade ?? '—'}{r.published_at && ` · ${date(r.published_at)}`}</p><p className="assignment-content">{r.comment}</p><p className="assignment-content">Tiêu chí chấm: {r.criteria_snapshot}</p></li>)}</ul></section>
  </div></section>;
}
export function LecturerDetail({ item }: { item: Assignment }) {
  const [selected, setSelected] = useState<{ studentId: string; versionId: string } | null>(null);
  const query = useQuery({ queryKey: ['assignments', item.id, 'roster'], queryFn: () => apiFetch<Student[]>(`/assignments/${item.id}/submissions`), retry: false });
  const student = query.data?.find(s => s.student.id === selected?.studentId);
  return <>
    {query.isPending && <p role="status">Đang tải…</p>}<ErrorMessage error={query.error} retry={() => void query.refetch()} />
    {query.data && <div className="assignment-table" role="region" aria-label="Bài nộp của sinh viên" tabIndex={0}><table className="admin-table"><thead><tr><th>Họ tên</th><th>Lần nộp</th><th>Nộp lúc</th><th>Điểm</th></tr></thead><tbody>{query.data.map(s => {
      const last = s.versions.at(-1);
      return <tr key={s.student.id}><td><Button variant="outline" disabled={!last} onClick={() => setSelected({ studentId: s.student.id, versionId: last!.id })}>{s.student.full_name}</Button></td><td>{s.versions.length}</td><td>{last ? <>{date(last.submitted_at)} {last.is_late && <span className="admin-badge">Nộp muộn</span>}</> : 'Chưa nộp'}</td><td>{s.latest_grade ? `${s.latest_grade.status === 'draft' ? 'Nháp' : 'Đã công bố'}: ${s.latest_grade.grade ?? '—'}` : 'Chưa chấm'}</td></tr>;
    })}</tbody></table></div>}
    {student && selected && <section className="assignment-blocks"><h3 className="section-title">{student.student.full_name}</h3><div><Label htmlFor="submission-version">Phiên bản bài nộp</Label><select id="submission-version" value={selected.versionId} onChange={e => setSelected({ ...selected, versionId: e.target.value })}>{student.versions.map(v => <option key={v.id} value={v.id}>Lần {v.version_no}</option>)}</select></div><Grading key={selected.versionId} item={item} versionId={selected.versionId} /></section>}
  </>;
}
