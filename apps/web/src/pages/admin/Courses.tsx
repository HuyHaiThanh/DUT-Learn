import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { adminKeys, createCourse, useAdminClasses, useAdminCourses } from '@/api/admin';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Empty, Field, MutationError, QueryState, Table } from './shared';

export function Courses() {
  const courses = useAdminCourses();
  const classes = useAdminClasses();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState('');
  const create = useMutation({ mutationFn: createCourse, onSuccess: async course => {
    setOpen(false); setNotice(`Đã tạo học phần ${course.name}.`);
    await client.invalidateQueries({ queryKey: adminKeys.courses });
  } });
  return <section aria-labelledby="admin-courses-heading"><div className="admin-heading"><h2 id="admin-courses-heading" className="section-title">Học phần</h2>
    <Dialog title="Thêm học phần" description="Nhập mã và tên học phần." trigger={<Button>Thêm học phần</Button>} open={open} onOpenChange={value => { setOpen(value); create.reset(); }} pending={create.isPending}>
      <form className="admin-form" aria-label="Thêm học phần" onSubmit={e => {
        e.preventDefault(); if (create.isPending) return;
        const data = new FormData(e.currentTarget);
        create.mutate({ code: String(data.get('code')), name: String(data.get('name')) });
      }}><fieldset disabled={create.isPending}><Field label="Mã" name="code" maxLength={100} required /><Field label="Tên học phần" name="name" maxLength={200} required /></fieldset>
        <MutationError error={create.error} conflict="Mã học phần đã tồn tại." /><Button type="submit" disabled={create.isPending}>{create.isPending ? 'Đang gửi…' : 'Tạo học phần'}</Button></form>
    </Dialog></div>{notice && <p role="status" className="admin-success">{notice}</p>}
    <QueryState queries={[courses, classes]}>{courses.data?.length ? <Table label="Danh sách học phần" headers={['Mã', 'Tên học phần', 'Số lớp']}>{courses.data.map(course => <tr key={course.id}><td>{course.code}</td><td className="admin-name">{course.name}</td><td>{classes.data?.filter(c => c.course_id === course.id).length ?? 0}</td></tr>)}</Table> : <Empty>Chưa có học phần. Chọn “Thêm học phần” để bắt đầu.</Empty>}</QueryState>
  </section>;
}
