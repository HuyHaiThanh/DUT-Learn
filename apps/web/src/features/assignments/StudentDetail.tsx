import { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { apiFetch } from '@/api/client';
import { sendEvent } from '@/features/events';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { date, ErrorMessage, request, useRefresh, type Assignment, type Version } from './shared';

export function StudentDetail({ item }: { item: Assignment }) {
  const [draft, setDraft] = useState(() => ({ content: '', key: crypto.randomUUID() }));
  const refresh = useRefresh();
  const query = useQuery({ queryKey: ['assignments', item.id, 'me'], queryFn: () => apiFetch<Version[]>(`/assignments/${item.id}/submissions/me`), retry: false });
  const mutation = useMutation({ mutationFn: () => request(`/assignments/${item.id}/submissions`, { content: draft.content, idempotency_key: draft.key }),
    onSuccess: async () => { setDraft({ content: '', key: crypto.randomUUID() }); await refresh(); } });
  const { classId = '' } = useParams();
  const feedback = query.data?.flatMap(v => v.grade ? [v.grade.revision_id] : []).join(',') ?? '';
  // The server dedupes repeats, so re-sending after a refetch is harmless.
  useEffect(() => { if (classId) for (const id of feedback.split(',').filter(Boolean)) void sendEvent(classId, 'feedback_viewed', id); }, [classId, feedback]);
  return <div className="assignment-blocks">
    {query.isPending && <p role="status">Đang tải…</p>}<ErrorMessage error={query.error} retry={() => void query.refetch()} />
    {item.status === 'closed' ? <p className="state-panel">Bài tập đã đóng nộp.</p> : query.isSuccess && <section><form className="admin-form" onSubmit={e => { e.preventDefault(); if (!mutation.isPending) mutation.mutate(); }}>
      {/* The label doubles as the section heading so the page does not say "Bài làm" twice. */}
      <Label htmlFor="submission-content" className="section-title">Bài làm</Label><textarea id="submission-content" value={draft.content} maxLength={20000} required disabled={mutation.isPending} onChange={e => { setDraft({ content: e.target.value, key: crypto.randomUUID() }); mutation.reset(); }} />
      <p className="metadata">{draft.content.length}/20.000</p><ErrorMessage error={mutation.error} />
      <div className="assignment-actions"><Button type="submit" disabled={mutation.isPending || !draft.content.length}>{mutation.isPending ? 'Đang gửi…' : query.data.length ? 'Nộp lại' : 'Nộp bài'}</Button>{mutation.isSuccess && <p role="status">Đã nộp bài.</p>}</div>
    </form></section>}
    <section><h3 className="section-title">Các lần nộp</h3><ul className="submission-list">{query.data?.map(v => <li className="submission-card" key={v.version_id}><h4 className="row-title">Lần {v.version_no} · <time dateTime={v.submitted_at}>{date(v.submitted_at)}</time>{v.is_late && <> · <span className="admin-badge">Nộp muộn</span></>}</h4><pre className="assignment-content">{v.content}</pre>{v.grade && <section className="assignment-feedback">{v.grade.grade !== null && <h5 className="row-title">Điểm: {v.grade.grade.toLocaleString('vi-VN')}/10</h5>}<h5 className="row-title">Nhận xét</h5><p className="assignment-content">{v.grade.comment}</p></section>}</li>)}</ul></section>
  </div>;
}
