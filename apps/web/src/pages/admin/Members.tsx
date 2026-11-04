import { formatTerm } from '@/pages/Classes';
import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { adminKeys, enrollMember, removeMember, useAdminClasses, useAdminCourses, useAdminMembers, useAdminUsers, type AdminClass, type Member, type MemberCreate } from '@/api/admin';
import { ApiError } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Empty, Field, matches, MutationError, QueryState, SelectField, Table } from './shared';

function Remove({ member, name, classroom, onRemoved }: { member: Member; name: string; classroom: AdminClass; onRemoved: (name: string) => void }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const remove = useMutation({ mutationFn: () => removeMember(classroom.id, member.user_id), onSuccess: async () => {
    setOpen(false); onRemoved(name);
    await client.invalidateQueries({ queryKey: adminKeys.members(classroom.id) });
  } });
  return <Dialog title="Gỡ thành viên khỏi lớp" description={`Gỡ ${name} khỏi lớp ${classroom.code}? Người này sẽ không còn xem được học liệu của lớp.`} focusCancel trigger={<Button variant="outline" aria-label={`Gỡ khỏi lớp: ${name}`}>Gỡ khỏi lớp</Button>} open={open} onOpenChange={value => { setOpen(value); remove.reset(); }} pending={remove.isPending}>
    <div className="admin-form"><MutationError error={remove.error} conflict="Không thể gỡ thành viên. Vui lòng thử lại." /><Button type="button" onClick={() => { if (!remove.isPending) remove.mutate(); }} disabled={remove.isPending}>{remove.isPending ? 'Đang gửi…' : 'Xác nhận gỡ'}</Button></div>
  </Dialog>;
}

export function Members() {
  const { classId = '' } = useParams();
  // Remount local selection and mutation notices when navigating between classes.
  return <MemberPage key={classId} classId={classId} />;
}
function MemberPage({ classId }: { classId: string }) {
  const classes = useAdminClasses();
  const courses = useAdminCourses();
  const users = useAdminUsers();
  const members = useAdminMembers(classId);
  const client = useQueryClient();
  const [search, setSearch] = useState('');
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState<MemberCreate['role']>('student');
  const [notice, setNotice] = useState('');
  const classroom = classes.data?.find(c => c.id === classId);
  const enroll = useMutation({ mutationFn: (body: MemberCreate) => enrollMember(classId, body), onSuccess: async (_, body) => {
    const name = users.data?.find(u => u.id === body.user_id)?.full_name ?? body.user_id.slice(0, 8);
    setNotice(`Đã ghi danh ${name} vào lớp ${classroom?.code ?? classId}.`); setUserId(''); setSearch('');
    await client.invalidateQueries({ queryKey: adminKeys.members(classId) });
  } });
  const missing = members.error instanceof ApiError && members.error.status === 404;
  if (missing || (classes.isSuccess && !classroom)) return <div className="state-panel"><p role="alert">Không tìm thấy lớp học phần.</p><Link to="/quan-tri/lop-hoc-phan">Về danh sách lớp học phần</Link></div>;
  const course = courses.data?.find(c => c.id === classroom?.course_id);
  const candidates = users.data?.filter(u => !members.data?.some(m => m.user_id === u.id) && matches(u.full_name, u.email, search)) ?? [];
  const selected = candidates.some(u => u.id === userId) ? userId : '';
  return <QueryState queries={[classes, courses, users, members]}>{classroom && <section aria-labelledby="members-heading">
    <nav aria-label="Đường dẫn" className="metadata"><Link to="/quan-tri/lop-hoc-phan">Lớp học phần</Link> › {classroom.code}</nav>
    <div className="admin-heading"><div><h2 id="members-heading" className="row-title">{course?.name ?? 'Học phần'} · {classroom.code}</h2><p className="metadata">{formatTerm(classroom.term)}</p></div></div>
    <form className="admin-enroll" aria-label="Ghi danh" aria-busy={enroll.isPending} onSubmit={e => {
      e.preventDefault(); if (!selected || enroll.isPending) return;
      enroll.mutate({ user_id: selected, role });
    }}><h3 className="row-title">Ghi danh</h3><fieldset disabled={enroll.isPending}>
      <Field label="Tìm người dùng theo tên hoặc email" type="search" value={search} onChange={e => { setSearch(e.target.value); setUserId(''); }} />
      <SelectField label="Người dùng để ghi danh" value={selected} onChange={e => setUserId(e.target.value)} required><option value="">Chọn người dùng</option>{candidates.map(u => <option key={u.id} value={u.id}>{u.full_name} · {u.email}</option>)}</SelectField>
      {!candidates.length && <p className="metadata">Không có người dùng phù hợp chưa ghi danh. <Link to="/quan-tri/nguoi-dung">Thêm người dùng</Link> hoặc đổi từ khóa.</p>}
      <SelectField label="Vai trò trong lớp" value={role} onChange={e => setRole(e.target.value as MemberCreate['role'])}><option value="student">Sinh viên</option><option value="lecturer">Giảng viên</option></SelectField>
      <Button type="submit" disabled={!selected || enroll.isPending}>{enroll.isPending ? 'Đang gửi…' : 'Ghi danh'}</Button>
    </fieldset><MutationError error={enroll.error} conflict="Người dùng này đã là thành viên lớp." /><p className="metadata">Để đổi vai trò, gỡ thành viên rồi ghi danh lại với vai trò mới.</p></form>
    {notice && <p role="status" className="admin-success">{notice}</p>}
    {(['lecturer', 'student'] as const).map(group => {
      const rows = members.data?.filter(m => m.role === group) ?? [];
      const label = group === 'lecturer' ? 'Giảng viên' : 'Sinh viên';
      return <section className="admin-member-group" aria-label={label} key={group}><h3 className="section-title">{label} ({rows.length})</h3>{rows.length ? <Table label={`Danh sách ${label.toLocaleLowerCase('vi')}`} headers={['Họ tên', 'Email', 'Thao tác']}>{rows.map(m => {
        const user = users.data?.find(u => u.id === m.user_id);
        const name = user?.full_name ?? `${m.user_id.slice(0, 8)}…`;
        return <tr key={m.id}><td className="admin-name">{name}</td><td>{user?.email ?? 'Không tìm thấy người dùng'}</td><td><Remove member={m} name={name} classroom={classroom} onRemoved={name => setNotice(`Đã gỡ ${name} khỏi lớp.`)} /></td></tr>;
      })}</Table> : <Empty>Chưa có {label.toLocaleLowerCase('vi')}. Chọn người dùng và vai trò trong form Ghi danh phía trên để thêm.</Empty>}</section>;
    })}
  </section>}</QueryState>;
}
