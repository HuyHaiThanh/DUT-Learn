import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { date, ErrorMessage, request, useRefresh, type Assignment, type Version } from './shared';

export function StudentDetail({ item }: { item: Assignment }) {
  const [draft, setDraft] = useState(() => ({ content: '', key: crypto.randomUUID() }));
  const refresh = useRefresh();
  const query = useQuery({ queryKey: ['assignments', item.id, 'me'], queryFn: () => apiFetch<Version[]>(`/assignments/${item.id}/submissions/me`), retry: false });
  const mutation = useMutation({ mutationFn: () => request(`/assignments/${item.id}/submissions`, { content: draft.content, idempotency_key: draft.key }),
    onSuccess: async () => { setDraft({ content: '', key: crypto.randomUUID() }); await refresh(); } });
  return <>
    {query.isPending && <p role="status">Đang tải…</p>}<ErrorMessage error={query.error} retry={() => void query.refetch()} />
    {item.status === 'closed' ? <p className="state-panel">Bài tập đã đóng nộp.</p> : query.isSuccess && <form className="admin-form" onSubmit={e => { e.preventDefault(); if (!mutation.isPending) mutation.mutate(); }}>
      <Label htmlFor="submission-content">Bài làm</Label><textarea id="submission-content" value={draft.content} maxLength={20000} required disabled={mutation.isPending} onChange={e => { setDraft({ content: e.target.value, key: crypto.randomUUID() }); mutation.reset(); }} />
      <p className="metadata">{draft.content.length}/20.000</p><ErrorMessage error={mutation.error} />
      <Button type="submit" disabled={mutation.isPending || !draft.content.length}>{mutation.isPending ? 'Đang gửi…' : query.data.length ? 'Nộp lại' : 'Nộp bài'}</Button>
    </form>}
    {mutation.isSuccess && <p role="status">Đã nộp bài.</p>}
    <h3 className="row-title">Các lần nộp</h3><ul className="list-panel">{query.data?.map(v => <li key={v.version_id}><h4>Lần {v.version_no}</h4><p>{date(v.submitted_at)} {v.is_late && <span className="admin-badge">Nộp muộn</span>}</p><pre className="assignment-content">{v.content}</pre>{v.grade && <><p>{v.grade.grade === null ? 'Nhận xét' : `${v.grade.grade}/10`}</p><p className="assignment-content">{v.grade.comment}</p></>}</li>)}</ul>
  </>;
}
