import { useId, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useOutletContext, useParams } from 'react-router-dom';
import { ApiError, apiFetch } from '@/api/client';
import type { Lesson, LessonCreate, LessonUpdate } from '@/api/types';
import { isUnauthorized } from '@/features/auth';
import { LoginRedirect } from '@/components/feedback';
import { StatusPill } from '@/components/StatusPill';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { ClassOutletContext } from './class/ClassLayout';
import { LecturerMaterials, MaterialError, MaterialLinks, useMaterials } from '@/features/materials';

function LessonError({ error, id }: { error: Error | null; id?: string }) {
  if (!error) return null;
  if (isUnauthorized(error)) return <LoginRedirect />;
  return <p id={id} role="alert" className="form-error">{error instanceof ApiError ? error.message : 'Không thể kết nối máy chủ. Vui lòng thử lại.'}</p>;
}

function TitleDialog({ classId, lesson, disabled }: { classId: string; lesson?: Lesson; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const id = useId();
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (data: LessonCreate) => apiFetch<Lesson>(lesson ? `/lessons/${lesson.id}` : `/classes/${classId}/lessons`, { method: lesson ? 'PATCH' : 'POST', body: JSON.stringify(data) }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['class', classId] }); setOpen(false); },
  });
  const label = lesson ? 'Đổi tên bài học' : 'Thêm bài học';
  return <Dialog title={label} description="Tiêu đề từ 1 đến 200 ký tự." open={open} pending={mutation.isPending}
    onOpenChange={next => { setOpen(next); if (next) { setTitle(lesson?.title ?? ''); mutation.reset(); } }}
    trigger={<Button variant={lesson ? 'outline' : 'default'} disabled={disabled} aria-label={lesson ? `Đổi tên: ${lesson.title}` : undefined}>{lesson ? 'Đổi tên' : label}</Button>}>
    <form className="admin-form" aria-label={label} onSubmit={e => { e.preventDefault(); if (!mutation.isPending && title.trim()) mutation.mutate({ title: title.trim() }); }}>
      <div className="form-field"><Label htmlFor={id}>Tiêu đề</Label><Input id={id} value={title} onChange={e => setTitle(e.target.value)} maxLength={200} required disabled={mutation.isPending} aria-invalid={mutation.isError} aria-describedby={mutation.isError ? `${id}-error` : undefined} /></div>
      <LessonError id={`${id}-error`} error={mutation.error} />
      <Button type="submit" disabled={mutation.isPending || !title.trim()}>{mutation.isPending ? 'Đang lưu…' : 'Lưu bài học'}</Button>
    </form>
  </Dialog>;
}

function PublishDialog({ classId, lesson, disabled }: { classId: string; lesson: Lesson; disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const label = lesson.is_published ? 'Ẩn bài học' : 'Công bố bài học';
  const mutation = useMutation({
    mutationFn: () => apiFetch<Lesson>(`/lessons/${lesson.id}`, { method: 'PATCH', body: JSON.stringify({ is_published: !lesson.is_published } satisfies LessonUpdate) }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['class', classId] }); setOpen(false); },
  });
  return <Dialog title={label} description={`${label} “${lesson.title}”? ${lesson.is_published ? 'Sinh viên sẽ không còn thấy bài học này.' : 'Sinh viên trong lớp sẽ thấy bài học này.'}`} open={open} pending={mutation.isPending} focusCancel
    onOpenChange={next => { setOpen(next); if (next) mutation.reset(); }}
    trigger={<Button variant="outline" disabled={disabled} aria-label={`${label}: ${lesson.title}`} aria-pressed={lesson.is_published}>{lesson.is_published ? 'Ẩn' : 'Công bố'}</Button>}>
    <div className="admin-form"><LessonError error={mutation.error} /><Button disabled={mutation.isPending} onClick={() => { if (!mutation.isPending) mutation.mutate(); }}>{mutation.isPending ? 'Đang lưu…' : 'Xác nhận'}</Button></div>
  </Dialog>;
}

export function ClassPage() {
  const { classId = '' } = useParams();
  const { classroom: data } = useOutletContext<ClassOutletContext>();
  const client = useQueryClient();
  const materials = useMaterials(classId);
  const move = useMutation({
    mutationFn: async ({ lessons, index, step }: { lessons: Lesson[]; index: number; step: number }) => {
      const ordered = [...lessons];
      [ordered[index], ordered[index + step]] = [ordered[index + step], ordered[index]];
      // Normalize positions as well, so tied/gapped positions can still be reordered.
      for (const [position, lesson] of ordered.entries()) {
        if (lesson.position !== position) await apiFetch<Lesson>(`/lessons/${lesson.id}`, { method: 'PATCH', body: JSON.stringify({ position } satisfies LessonUpdate) });
      }
    },
    onSettled: () => client.invalidateQueries({ queryKey: ['class', classId] }),
  });
  const lecturer = data.role === 'lecturer';
  const lessons = data.lessons.filter(l => lecturer || l.is_published);
  return <div className="lesson-page">
    <section aria-labelledby="lessons-heading" aria-busy={move.isPending}>
      <div className="admin-heading"><h2 id="lessons-heading" className="section-title">Bài học</h2>{lecturer && <TitleDialog classId={classId} disabled={move.isPending} />}</div>
      <LessonError error={move.error} />
      <MaterialError error={materials.error} />
      {materials.isError && <Button variant="outline" onClick={() => void materials.refetch()}>Thử tải lại học liệu</Button>}
      {lessons.length ? <ul className="list-panel lesson-list">{lessons.map((lesson, index) => <li className="lesson-row" key={lesson.id}>
        <div className="class-copy"><h3 className="row-title">{lesson.title}</h3>{lecturer && <StatusPill tone={lesson.is_published ? 'ok' : 'neutral'} icon={lesson.is_published ? 'check' : 'clipboard'}>{lesson.is_published ? 'Đã công bố' : 'Nháp'}</StatusPill>}{materials.isPending ? <p role="status" className="state-panel loading-state"><span className="spinner" aria-hidden="true" />Đang tải học liệu…</p> : materials.data && <MaterialLinks materials={materials.data.filter(m => m.lesson_id === lesson.id && m.active_version_id)} />}</div>
        {lecturer && <div className="lesson-actions">
          <TitleDialog classId={classId} lesson={lesson} disabled={move.isPending} /><PublishDialog classId={classId} lesson={lesson} disabled={move.isPending} />
          {([-1, 1] as const).map(step => <Button key={step} variant="outline" disabled={move.isPending || (step === -1 ? index === 0 : index === lessons.length - 1)} aria-label={`${step === -1 ? 'Đưa lên' : 'Đưa xuống'}: ${lesson.title}`} onClick={() => { if (!move.isPending) move.mutate({ lessons, index, step }); }}><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={step === -1 ? 'm6 14 6-6 6 6' : 'm6 10 6 6 6-6'} /></svg></Button>)}
        </div>}
      </li>)}</ul> : <div className="state-panel">{lecturer ? 'Chưa có bài học. Chọn “Thêm bài học” để bắt đầu.' : 'Giảng viên chưa công bố bài học nào.'}</div>}
    </section>
    {!lecturer && !!materials.data?.some(m => m.lesson_id === null) && <section aria-label="Học liệu chung của lớp"><h2 className="section-title">Học liệu chung của lớp</h2><MaterialLinks materials={materials.data.filter(m => m.lesson_id === null)} /></section>}
    {lecturer && <LecturerMaterials classId={classId} lessons={lessons} />}
  </div>;
}
