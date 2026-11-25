import { StatusPill } from '@/components/StatusPill';
import { formatTerm } from '@/pages/Classes';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { adminKeys, createClass, useAdminClasses, useAdminCourses, type ClassCreate } from '@/api/admin';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Empty, Field, MutationError, QueryState, SelectField, Table } from './shared';

export function AdminClasses() {
  const courses = useAdminCourses();
  const classes = useAdminClasses();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState('');
  const [term, setTerm] = useState('');
  const [courseId, setCourseId] = useState('');
  const create = useMutation({ mutationFn: createClass, onSuccess: async classroom => {
    setOpen(false); setNotice(`Đã tạo lớp ${classroom.code}.`);
    await client.invalidateQueries({ queryKey: adminKeys.classes });
  } });
  const rows = classes.data?.filter(c => (!term || c.term === term) && (!courseId || c.course_id === courseId)) ?? [];
  return <section aria-labelledby="admin-classes-heading"><div className="admin-heading"><h2 id="admin-classes-heading" className="section-title">Lớp học phần</h2>
    <Dialog title="Thêm lớp học phần" description="Chọn học phần và nhập thông tin lớp." trigger={<Button>Thêm lớp học phần</Button>} open={open} onOpenChange={value => { setOpen(value); create.reset(); }} pending={create.isPending}>
      <QueryState queries={[courses]}>{courses.data?.length ? <form className="admin-form" aria-label="Thêm lớp học phần" onSubmit={e => {
        e.preventDefault(); if (create.isPending) return;
        const data = new FormData(e.currentTarget);
        create.mutate({ course_id: String(data.get('course_id')), code: String(data.get('code')), term: String(data.get('term')), status: data.get('status') as ClassCreate['status'] });
      }}><fieldset disabled={create.isPending}>
        <SelectField label="Học phần" name="course_id" required defaultValue=""><option value="" disabled>Chọn học phần</option>{courses.data.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</SelectField>
        <Field label="Mã lớp" name="code" required maxLength={100} /><Field label="Học kỳ" name="term" placeholder="2026-2027.1" maxLength={100} required />
        <SelectField label="Trạng thái" name="status" defaultValue="open"><option value="open">Đang mở</option><option value="closed">Đã đóng</option></SelectField>
      </fieldset><MutationError error={create.error} conflict="Lớp học phần đã tồn tại trong học kỳ này." /><Button type="submit" disabled={create.isPending}>{create.isPending ? 'Đang gửi…' : 'Tạo lớp học phần'}</Button></form> : <p className="admin-dialog-note"><Link to="/quan-tri/hoc-phan">Tạo học phần trước</Link> để thêm lớp học phần.</p>}</QueryState>
    </Dialog></div>{notice && <p role="status" className="admin-success">{notice}</p>}
    <QueryState queries={[courses, classes]}><div className="admin-toolbar">
      <SelectField label="Lọc theo học kỳ" value={term} onChange={e => setTerm(e.target.value)}><option value="">Tất cả học kỳ</option>{[...new Set(classes.data?.map(c => c.term))].map(t => <option key={t} value={t}>{formatTerm(t)}</option>)}</SelectField>
      <SelectField label="Lọc theo học phần" value={courseId} onChange={e => setCourseId(e.target.value)}><option value="">Tất cả học phần</option>{courses.data?.map(c => <option key={c.id} value={c.id}>{c.code} · {c.name}</option>)}</SelectField>
    </div>{rows.length ? <Table label="Danh sách lớp học phần" headers={['Mã lớp', 'Học phần', 'Học kỳ', 'Trạng thái', 'Thành viên']}>{rows.map(c => {
      const course = courses.data?.find(course => course.id === c.course_id);
      return <tr key={c.id}><td className="admin-name">{c.code}</td><td>{course ? <>{course.name}<span className="metadata">{course.code}</span></> : c.course_id}</td><td>{formatTerm(c.term)}</td><td><StatusPill tone={c.status === 'open' ? 'ok' : 'neutral'} icon={c.status === 'open' ? 'check' : 'lock'}>{c.status === 'open' ? 'Đang mở' : 'Đã đóng'}</StatusPill></td><td><Link to={`/quan-tri/lop-hoc-phan/${encodeURIComponent(c.id)}`}>Quản lý thành viên<span className="sr-only"> lớp {c.code}</span></Link></td></tr>;
    })}</Table> : <Empty>{term || courseId ? 'Không có lớp khớp bộ lọc. Chọn tất cả học kỳ và học phần để xem lại.' : <>Chưa có lớp học phần. {courses.data?.length ? 'Chọn “Thêm lớp học phần” để bắt đầu.' : <Link to="/quan-tri/hoc-phan">Tạo học phần trước</Link>}</>}</Empty>}</QueryState>
  </section>;
}
