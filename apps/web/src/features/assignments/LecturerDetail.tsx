import { useId, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Confirm, date, ErrorMessage, request, useRefresh, type Assignment, type Grade, type Student, type Version } from './shared';
import { SubmissionContent } from './SubmissionContent';
import { formatScore, parseScore } from '@/lib/score';
import { StatusPill } from '@/components/StatusPill';

function Grading({ item, versionId }: { item: Assignment; versionId: string }) {
  const refresh = useRefresh();
  const query = useQuery({ queryKey: ['assignments', item.id, 'version', versionId], queryFn: () => apiFetch<Version & { revisions: Grade[] }>(`/submission-versions/${versionId}`), retry: false });
  if (query.isPending) return <p role="status" className="state-panel loading-state"><span className="spinner" aria-hidden="true" />Đang tải…</p>;
  if (query.isError) return <ErrorMessage error={query.error} retry={() => void query.refetch()} />;
  const version = query.data;
  return <GradeForm key={versionId} version={version} refresh={refresh} />;
}
function GradeForm({ version, refresh }: { version: Version & { revisions: Grade[] }; refresh: () => Promise<unknown> }) {
  const formId = useId();
  const latest = version.revisions.at(-1);
  const [grade, setGrade] = useState(latest?.grade == null ? '' : formatScore(latest.grade));
  const [comment, setComment] = useState(latest?.comment ?? '');
  const invalid = grade.trim() !== '' && parseScore(grade) === null;
  const changed = (grade.trim() === '' ? null : parseScore(grade)) !== (latest?.grade ?? null) || comment !== (latest?.comment ?? '');
  const mutation = useMutation({ mutationFn: () => request(`/submission-versions/${version.id}/grades`, { grade: grade.trim() === '' ? null : parseScore(grade), comment }), onSuccess: refresh });
  return <section className="assignment-grading"><div className="info-card"><h3 className="section-title">Bài nộp</h3><SubmissionContent content={version.content} /></div><div className="assignment-grading-details">
    <section><h3 className="section-title">Chấm bài</h3>
    <p className="metadata">Áp dụng tiêu chí ở phần trên.</p>
    <form id={formId} className="admin-form" onSubmit={e => { e.preventDefault(); if (!mutation.isPending && !invalid) mutation.mutate(); }}>
      <Label htmlFor="grade-value">Điểm</Label><Input id="grade-value" type="text" inputMode="decimal" value={grade} aria-invalid={invalid} aria-describedby={invalid ? 'grade-error' : undefined} disabled={mutation.isPending} onChange={e => setGrade(e.target.value)} />
      {invalid && <p id="grade-error" className="form-error">Nhập điểm từ 0 đến 10, tối đa hai chữ số thập phân.</p>}
      <Label htmlFor="grade-comment">Nhận xét</Label><textarea id="grade-comment" maxLength={5000} value={comment} disabled={mutation.isPending} onChange={e => setComment(e.target.value)} />
      <ErrorMessage error={mutation.error} />
    </form>
    <div className="assignment-grade-actions"><Button variant="outline" type="submit" form={formId} disabled={mutation.isPending || invalid || (grade.trim() === '' && !comment.trim())}>{mutation.isPending ? 'Đang gửi…' : 'Lưu nháp'}</Button>
    <Confirm primary label="Công bố điểm" description="Sinh viên sẽ thấy điểm và nhận xét này. Sau khi công bố, muốn sửa phải tạo bản chấm mới." disabled={!latest || latest.status !== 'draft' || changed || invalid || mutation.isPending} action={() => request(`/grade-revisions/${latest!.revision_id}/publish`)} />
    </div>
    {mutation.isSuccess && <p role="status">Đã lưu nháp.</p>}
    </section><section><h3 className="section-title">Lịch sử bản chấm</h3><ul className="submission-list">{version.revisions.map(r => <li className="submission-card" key={r.revision_id}><p>Bản {r.revision_no} · {r.status === 'draft' ? 'Nháp' : 'Đã công bố'}: {r.grade == null ? '—' : formatScore(r.grade)}{r.published_at && ` · ${date(r.published_at)}`}</p><p className="assignment-content">{r.comment}</p><p className="assignment-content">Tiêu chí chấm: {r.criteria_snapshot}</p></li>)}</ul></section>
  </div></section>;
}
export function LecturerDetail({ item }: { item: Assignment }) {
  const [selected, setSelected] = useState<{ studentId: string; versionId: string } | null>(null);
  const query = useQuery({ queryKey: ['assignments', item.id, 'roster'], queryFn: () => apiFetch<Student[]>(`/assignments/${item.id}/submissions`), retry: false });
  const student = query.data?.find(s => s.student.id === selected?.studentId);
  return <>
    {query.isPending && <p role="status" className="state-panel loading-state"><span className="spinner" aria-hidden="true" />Đang tải…</p>}<ErrorMessage error={query.error} retry={() => void query.refetch()} />
    {query.data && <div className="assignment-table" role="region" aria-label="Bài nộp của sinh viên" tabIndex={0}><table className="admin-table"><thead><tr><th>Họ tên</th><th>Lần nộp</th><th>Nộp lúc</th><th>Điểm</th></tr></thead><tbody>{query.data.map(s => {
      const last = s.versions.at(-1);
      return <tr key={s.student.id}><td><Button variant="ghost" className="student-link" disabled={!last} onClick={() => setSelected({ studentId: s.student.id, versionId: last!.id })}>{s.student.full_name}</Button></td><td>{s.versions.length}</td><td>{last ? <>{date(last.submitted_at)} {last.is_late && <StatusPill tone="warn" icon="clock">Nộp muộn</StatusPill>}</> : 'Chưa nộp'}</td><td>{s.latest_grade ? <StatusPill tone={s.latest_grade.status === 'published' ? 'ok' : 'neutral'} icon={s.latest_grade.status === 'published' ? 'check' : 'clipboard'}>{s.latest_grade.status === 'draft' ? 'Nháp' : 'Đã công bố'}: {s.latest_grade.grade == null ? '—' : formatScore(s.latest_grade.grade)}</StatusPill> : 'Chưa chấm'}</td></tr>;
    })}</tbody></table></div>}
    {student && selected && <section className="assignment-blocks"><h3 className="section-title">{student.student.full_name}</h3><div><Label htmlFor="submission-version">Phiên bản bài nộp</Label><select id="submission-version" value={selected.versionId} onChange={e => setSelected({ ...selected, versionId: e.target.value })}>{student.versions.map(v => <option key={v.id} value={v.id}>Lần {v.version_no}</option>)}</select></div><Grading key={selected.versionId} item={item} versionId={selected.versionId} /></section>}
  </>;
}
