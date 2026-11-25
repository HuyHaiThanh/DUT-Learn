import { useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ApiError, apiFetch } from '@/api/client';
import type { Lesson } from '@/api/types';
import { isUnauthorized } from '@/features/auth';
import { LoginRedirect } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Icon } from '@/components/icons';

export type VersionStatus = 'uploaded' | 'processing' | 'ready' | 'failed' | 'published' | 'superseded' | 'revoked';
export type Version = { id: string; version_no: number; status: VersionStatus; error: string | null };
export type Quality = { page_count: number; chunk_count: { text: number; code: number }; empty_pages: number; glued_tokens_before: number; glued_tokens_after: number };
export type Material = { id: string; title: string; lesson_id: string | null; kind: 'pdf' | 'text'; visibility?: 'students' | 'lecturers'; active_version_id: string | null; page_count?: number | null; versions?: Version[]; quality_report?: Quality | null; source_note?: string | null; license_note?: string | null };

const statusLabels: Record<VersionStatus, string> = { uploaded: 'Đã tải lên', processing: 'Đang xử lý', ready: 'Sẵn sàng', failed: 'Xử lý lỗi', published: 'Đã công bố', superseded: 'Đã thay thế', revoked: 'Đã thu hồi' };

export function useMaterials(classId: string) {
  return useQuery({ queryKey: ['materials', classId], queryFn: () => apiFetch<Material[]>(`/classes/${classId}/materials`), retry: false,
    refetchInterval: query => query.state.data?.some(m => m.versions?.some(v => v.status === 'uploaded' || v.status === 'processing')) ? 3000 : false });
}

export function MaterialError({ error }: { error: Error | null }) {
  if (!error) return null;
  if (isUnauthorized(error)) return <LoginRedirect />;
  return <p role="alert" className="form-error">{error instanceof ApiError ? error.message : 'Không thể kết nối máy chủ. Vui lòng thử lại.'}</p>;
}

export function MaterialLinks({ materials }: { materials: Material[] }) {
  if (!materials.length) return <p className="metadata">Chưa có học liệu</p>;
  return <ul className="material-links">{materials.map(material => <li key={material.id}>{material.active_version_id && <Link to={`/doc/${material.active_version_id}?page=1`}>
    <span className="feature-icon icon-sky"><Icon name="book" /></span><span className="material-link-copy">{material.title}<span className="metadata">{material.kind === 'pdf' ? 'PDF' : 'Văn bản'}{material.page_count != null ? ` · ${material.page_count} trang` : ''}</span></span><span className="material-read">Đọc</span>
  </Link>}</li>)}</ul>;
}

function MaterialEditor({ classId, lessons, material, replace = false }: { classId: string; lessons: Lesson[]; material?: Material; replace?: boolean }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [lesson, setLesson] = useState('');
  const [visibility, setVisibility] = useState('students');
  const id = useId();
  const client = useQueryClient();
  const edit = !!material && !replace;
  const label = replace ? 'Tải phiên bản mới' : edit ? 'Sửa học liệu' : 'Tải học liệu';
  const mutation = useMutation({
    mutationFn: (form: FormData) => edit ? apiFetch(`/materials/${material.id}`, { method: 'PATCH', body: JSON.stringify({ title: title.trim(), lesson_id: lesson || null, visibility }) })
      : apiFetch(replace ? `/materials/${material!.id}/versions` : `/classes/${classId}/materials`, { method: 'POST', body: form }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['materials', classId] }); setOpen(false); },
  });
  return <Dialog title={label} description={material ? material.title : 'PDF, TXT hoặc MD mã hóa UTF-8, tối đa 50 MB.'} open={open} pending={mutation.isPending}
    onOpenChange={next => { setOpen(next); if (next) { mutation.reset(); setTitle(material?.title ?? ''); setLesson(material?.lesson_id ?? ''); setVisibility(material?.visibility ?? 'students'); } }}
    trigger={<Button variant={material ? 'outline' : 'default'} aria-label={material ? `${label}: ${material.title}` : undefined}>{label}</Button>}>
    <form className="admin-form" aria-label={label} onSubmit={e => { e.preventDefault(); if (!mutation.isPending) mutation.mutate(new FormData(e.currentTarget)); }}>
      <fieldset disabled={mutation.isPending} className="material-fields">
        {!edit && <div className="form-field"><Label htmlFor={`${id}-file`}>Tệp học liệu</Label><Input id={`${id}-file`} name="file" type="file" accept={replace ? material?.kind === 'pdf' ? '.pdf' : '.txt,.md' : '.pdf,.txt,.md'} required /></div>}
        {!replace && <>
          <div className="form-field"><Label htmlFor={`${id}-title`}>Tiêu đề</Label><Input id={`${id}-title`} name="title" value={title} onChange={e => setTitle(e.target.value)} maxLength={200} required /></div>
          <div className="form-field"><Label htmlFor={`${id}-lesson`}>Bài học</Label><select id={`${id}-lesson`} name="lesson_id" value={lesson} onChange={e => setLesson(e.target.value)}><option value="">Học liệu chung của lớp</option>{lessons.map(l => <option key={l.id} value={l.id}>{l.title}</option>)}</select></div>
          <div className="form-field"><Label htmlFor={`${id}-visibility`}>Hiển thị cho</Label><select id={`${id}-visibility`} name="visibility" value={visibility} onChange={e => setVisibility(e.target.value)}><option value="students">Sinh viên</option><option value="lecturers">Chỉ giảng viên</option></select></div>
          {!edit && <><div className="form-field"><Label htmlFor={`${id}-source`}>Ghi nguồn</Label><Input id={`${id}-source`} name="source_note" /></div><div className="form-field"><Label htmlFor={`${id}-license`}>Giấy phép</Label><Input id={`${id}-license`} name="license_note" /></div></>}
        </>}
      </fieldset>
      <MaterialError error={mutation.error} />
      <Button type="submit" disabled={mutation.isPending || (!replace && !title.trim())}>{mutation.isPending ? 'Đang lưu…' : edit ? 'Lưu thay đổi' : 'Tải lên'}</Button>
    </form>
  </Dialog>;
}

function QualityReport({ report }: { report: Quality | null | undefined }) {
  if (!report) return <p className="metadata">Chưa có báo cáo chất lượng.</p>;
  return <div className="quality-report"><h4>Báo cáo chất lượng</h4><dl>
    <dt>Số trang</dt><dd>{report.page_count}</dd><dt>Số đoạn</dt><dd>{report.chunk_count.text + report.chunk_count.code} (văn bản: {report.chunk_count.text}, mã: {report.chunk_count.code})</dd>
    <dt>Trang trống / ít chữ</dt><dd>{report.empty_pages}</dd><dt>Chữ dính trước / sau</dt><dd>{report.glued_tokens_before} / {report.glued_tokens_after}</dd>
  </dl><p className="metadata">Chữ dính là số token nghi ngờ do bộ trích xuất phát hiện.{report.glued_tokens_before > 0 && ` Sau xử lý còn ${Math.round(report.glued_tokens_after / report.glued_tokens_before * 100)}% so với trước.`}</p></div>;
}

function VersionAction({ classId, material, version, action }: { classId: string; material: Material; version: Version; action: 'publish' | 'revoke' | 'reprocess' }) {
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const label = action === 'publish' ? 'Công bố' : action === 'revoke' ? 'Thu hồi' : 'Xử lý lại';
  const detail = useQuery({ queryKey: ['material-version', version.id], queryFn: () => apiFetch<{ quality_report: Omit<Quality, 'empty_pages'> & { empty_pages: number[] } | null }>(`/material-versions/${version.id}`), enabled: open && action === 'publish', retry: false });
  const mutation = useMutation({ mutationFn: () => apiFetch(`/material-versions/${version.id}/${action}`, { method: 'POST' }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['materials', classId] }); setOpen(false); },
    onError: () => { void client.invalidateQueries({ queryKey: ['materials', classId] }); },
  });
  return <Dialog title={`${label} học liệu`} description={`${material.title} · phiên bản ${version.version_no}. ${action === 'revoke' ? 'Sau khi thu hồi, sinh viên sẽ không đọc/trích dẫn được nữa.' : action === 'publish' ? 'Sinh viên được cấp quyền sẽ đọc được phiên bản này; bản công bố cũ sẽ được thay thế.' : 'Thử xử lý lại tệp đã tải lên.'}`}
    open={open} pending={mutation.isPending} focusCancel onOpenChange={next => { setOpen(next); if (next) mutation.reset(); }}
    trigger={<Button variant="outline" aria-label={`${label}: ${material.title}, phiên bản ${version.version_no}`}>{label}</Button>}>
    {action === 'publish' && <>{detail.isFetching && <p role="status" className="state-panel loading-state"><span className="spinner" aria-hidden="true" />Đang tải báo cáo chất lượng…</p>}<MaterialError error={detail.error} /><QualityReport report={detail.data?.quality_report ? { ...detail.data.quality_report, empty_pages: detail.data.quality_report.empty_pages.length } : null} /></>}
    <div className="admin-form"><MaterialError error={mutation.error} /><Button disabled={mutation.isPending || (action === 'publish' && !detail.isSuccess)} onClick={() => { if (!mutation.isPending) mutation.mutate(); }}>{mutation.isPending ? 'Đang lưu…' : 'Xác nhận'}</Button></div>
  </Dialog>;
}

export function LecturerMaterials({ classId, lessons }: { classId: string; lessons: Lesson[] }) {
  const query = useMaterials(classId);
  return <section aria-labelledby="materials-heading" className="materials-section" aria-busy={query.isFetching}>
    <div className="admin-heading"><h2 id="materials-heading" className="section-title">Học liệu</h2><MaterialEditor classId={classId} lessons={lessons} /></div>
    {query.isPending && <p role="status" className="state-panel loading-state"><span className="spinner" aria-hidden="true" />Đang tải học liệu…</p>}
    <MaterialError error={query.error} />{query.isError && <Button variant="outline" onClick={() => void query.refetch()}>Thử tải lại học liệu</Button>}
    {query.data && (query.data.length ? <ul className="list-panel material-list">{query.data.map(material => {
      const versions = material.versions ?? [];
      const latest = versions.reduce<Version | undefined>((current, v) => !current || v.version_no > current.version_no ? v : current, undefined);
      const active = versions.find(v => v.id === material.active_version_id);
      return <li key={material.id} className="material-row">
        <h3 className="row-title">{material.title}</h3><p className="metadata">{lessons.find(l => l.id === material.lesson_id)?.title ?? 'Học liệu chung của lớp'} · {material.visibility === 'students' ? 'Sinh viên' : 'Chỉ giảng viên'}</p>
        <p className="metadata">Đang công bố: {active ? `phiên bản ${active.version_no}` : 'Chưa có'}</p>
        {latest && <p>Bản mới nhất: {latest.version_no} · <span className={`material-status status-${latest.status}`}><Icon name={latest.status === 'revoked' ? 'lock' : latest.status === 'failed' ? 'alert' : ['ready', 'published'].includes(latest.status) ? 'check' : 'clock'} />{statusLabels[latest.status]}</span></p>}
        {latest?.status === 'ready' && <QualityReport report={material.quality_report} />}
        <div className="material-actions"><MaterialEditor classId={classId} lessons={lessons} material={material} /><MaterialEditor classId={classId} lessons={lessons} material={material} replace /></div>
        <ul className="version-list">{versions.map(version => <li key={version.id}><span>Phiên bản {version.version_no} · <span className={`material-status status-${version.status}`}><Icon name={version.status === 'revoked' ? 'lock' : version.status === 'failed' ? 'alert' : ['ready', 'published'].includes(version.status) ? 'check' : 'clock'} />{statusLabels[version.status]}</span></span>
          <div className="material-actions"><Link to={`/doc/${version.id}?page=1`}>Đọc phiên bản {version.version_no}</Link>
            {version.status === 'ready' && <VersionAction classId={classId} material={material} version={version} action="publish" />}
            {version.status === 'failed' && <VersionAction classId={classId} material={material} version={version} action="reprocess" />}
            {['ready', 'published', 'superseded'].includes(version.status) && <VersionAction classId={classId} material={material} version={version} action="revoke" />}
          </div>{version.status === 'failed' && <p role="alert" className="form-error">{version.error ?? 'Không thể xử lý tệp.'}</p>}</li>)}</ul>
      </li>;
    })}</ul> : <p className="state-panel">Chưa có học liệu. Chọn “Tải học liệu” để bắt đầu.</p>)}
  </section>;
}
