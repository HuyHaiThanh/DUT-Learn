import { useId, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiFetch } from '@/api/client';
import type { Lesson } from '@/api/types';
import { LoginRedirect } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { isUnauthorized } from '@/features/auth';

export type Assignment = { id: string; title: string; instructions: string; criteria: string; due_at: string | null; lesson_id: string | null; status: 'draft' | 'published' | 'closed'; submission_count: number; my_versions: number; my_grade_published: boolean };
export type Grade = { revision_id: string; revision_no: number; status: 'draft' | 'published'; grade: number | null; comment: string; criteria_snapshot: string; published_at: string | null };
export type Version = { id: string; version_id: string; version_no: number; content: string; submitted_at: string; is_late: boolean; grade: Pick<Grade, 'grade' | 'comment' | 'published_at'> | null };
export type Student = { student: { id: string; full_name: string; email: string }; versions: Pick<Version, 'id' | 'version_no' | 'submitted_at' | 'is_late'>[]; latest_grade: Grade | null };
export const labels = { draft: 'Nháp', published: 'Đang mở nộp', closed: 'Đã đóng' };
export const request = <T,>(path: string, body?: unknown, method = 'POST') => apiFetch<T>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
export function date(value: string | null) {
  if (!value) return 'Không có hạn nộp';
  const parts = new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric', hourCycle: 'h23' }).formatToParts(new Date(value));
  const part = (name: string) => parts.find(p => p.type === name)?.value;
  return `${part('hour')}:${part('minute')}, ${part('day')}/${part('month')}/${part('year')}`;
}
export function localDate(value: string | null) {
  return value ? new Date(new Date(value).getTime() + 7 * 3600000).toISOString().slice(0, 16) : '';
}
export function ErrorMessage({ error, retry }: { error: Error | null; retry?: () => void }) {
  if (!error) return null;
  if (isUnauthorized(error)) return <LoginRedirect />;
  return <div><p role="alert" className="form-error">{error instanceof ApiError ? error.message : 'Không thể kết nối máy chủ. Vui lòng thử lại.'}</p>{retry && <Button variant="outline" onClick={retry}>Thử lại</Button>}</div>;
}
export function useRefresh() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: ['assignments'] });
}
export function Confirm({ label, description, action, disabled = false }: { label: string; description: string; action: () => Promise<unknown>; disabled?: boolean }) {
  const [open, setOpen] = useState(false);
  const refresh = useRefresh();
  const mutation = useMutation({ mutationFn: action, onSuccess: async () => { await refresh(); setOpen(false); } });
  return <><Dialog title={label} description={description} trigger={<Button variant="outline" disabled={disabled}>{label}</Button>} open={open} onOpenChange={next => { setOpen(next); mutation.reset(); }} pending={mutation.isPending} focusCancel>
    <ErrorMessage error={mutation.error} /><Button disabled={mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? 'Đang gửi…' : 'Xác nhận'}</Button>
  </Dialog>{mutation.isSuccess && <p role="status">Đã lưu thay đổi.</p>}</>;
}
export function AssignmentEditor({ classId, lessons, item }: { classId: string; lessons: Lesson[]; item?: Assignment }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const refresh = useRefresh();
  const label = item ? 'Sửa' : 'Tạo bài tập';
  const mutation = useMutation({ mutationFn: (form: FormData) => request(item ? `/assignments/${item.id}` : `/classes/${classId}/assignments`, {
    title: form.get('title'), instructions: form.get('instructions'), criteria: form.get('criteria'),
    due_at: form.get('due_at') ? new Date(`${form.get('due_at')}+07:00`).toISOString() : null, lesson_id: form.get('lesson_id') || null,
  }, item ? 'PATCH' : 'POST'), onSuccess: async () => { await refresh(); setOpen(false); } });
  return <><Dialog title={label} description={item?.title ?? 'Bài tập'} open={open} onOpenChange={next => { setOpen(next); mutation.reset(); }} pending={mutation.isPending} trigger={<Button>{label}</Button>}>
    <form aria-label={label} className="admin-form" onSubmit={e => { e.preventDefault(); if (!mutation.isPending) mutation.mutate(new FormData(e.currentTarget)); }}>
      <fieldset disabled={mutation.isPending} className="assignment-fields">
        <Label htmlFor={`${id}-title`}>Tiêu đề</Label><Input id={`${id}-title`} name="title" defaultValue={item?.title} required minLength={1} maxLength={200} />
        <Label htmlFor={`${id}-instructions`}>Hướng dẫn</Label><textarea id={`${id}-instructions`} name="instructions" defaultValue={item?.instructions} maxLength={20000} />
        <Label htmlFor={`${id}-criteria`}>Tiêu chí chấm</Label><textarea id={`${id}-criteria`} name="criteria" defaultValue={item?.criteria} maxLength={5000} />
        <Label htmlFor={`${id}-due`}>Hạn nộp</Label><Input id={`${id}-due`} name="due_at" type="datetime-local" defaultValue={localDate(item?.due_at ?? null)} />
        <Label htmlFor={`${id}-lesson`}>Bài học</Label><select id={`${id}-lesson`} name="lesson_id" defaultValue={item?.lesson_id ?? ''}><option value="">Không chọn bài học</option>{lessons.map(l => <option key={l.id} value={l.id}>{l.title}</option>)}</select>
      </fieldset><ErrorMessage error={mutation.error} /><Button type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'Đang gửi…' : item ? 'Lưu thay đổi' : 'Tạo bài tập'}</Button>
    </form>
  </Dialog>{mutation.isSuccess && <p role="status">Đã lưu bài tập.</p>}</>;
}
