import { StatusPill } from '@/components/StatusPill';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { adminKeys, createUser, useAdminUsers, type UserCreate } from '@/api/admin';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Empty, Field, matches, MutationError, QueryState, SelectField, Table } from './shared';

export function Users() {
  const users = useAdminUsers();
  const client = useQueryClient();
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);
  const [visible, setVisible] = useState(false);
  const [notice, setNotice] = useState('');
  const create = useMutation({ mutationFn: createUser, onSuccess: async user => {
    setOpen(false); setVisible(false); setNotice(`Đã tạo tài khoản cho ${user.full_name}.`);
    await client.invalidateQueries({ queryKey: adminKeys.users });
  } });
  const rows = users.data?.filter(u => matches(u.full_name, u.email, search)) ?? [];
  const add = <Dialog title="Thêm người dùng" description="Cấp tài khoản cho người dùng tham gia hệ thống." open={open} onOpenChange={value => { setOpen(value); setVisible(false); create.reset(); }} pending={create.isPending} trigger={<Button>Thêm người dùng</Button>}>
    <form className="admin-form" aria-label="Thêm người dùng" onSubmit={e => {
      e.preventDefault(); if (create.isPending) return;
      const data = new FormData(e.currentTarget);
      create.mutate({ full_name: String(data.get('full_name')), email: String(data.get('email')), password: String(data.get('password')), system_role: data.get('system_role') as UserCreate['system_role'] });
    }}><fieldset disabled={create.isPending}>
      <Field label="Họ tên" name="full_name" maxLength={200} required />
      <Field label="Email" name="email" type="email" autoComplete="off" required />
      <Field label="Mật khẩu tạm" name="password" type={visible ? 'text' : 'password'} autoComplete="new-password" required aria-describedby="password-help" />
      <Button type="button" variant="ghost" aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}</Button>
      <p id="password-help" className="metadata">Gửi mật khẩu tạm cho người dùng qua kênh riêng.</p>
      <SelectField label="Vai trò hệ thống" name="system_role" defaultValue="user"><option value="user">Người dùng</option><option value="admin">Quản trị viên</option></SelectField>
    </fieldset><MutationError error={create.error} conflict="Email này đã có tài khoản." /><Button type="submit" disabled={create.isPending}>{create.isPending ? 'Đang gửi…' : 'Tạo người dùng'}</Button></form>
  </Dialog>;
  return <section aria-labelledby="admin-users-heading"><div className="admin-heading"><h2 id="admin-users-heading" className="section-title">Người dùng</h2>{add}</div>
    {notice && <p role="status" className="admin-success">{notice}</p>}
    <QueryState queries={[users]}><div className="admin-toolbar"><Field label="Tìm theo tên hoặc email" type="search" value={search} onChange={e => setSearch(e.target.value)} /><p className="metadata">Lọc trong {users.data?.length ?? 0} người dùng đã tải<br />Không phân biệt hoa thường, có phân biệt dấu.</p></div>
      {rows.length ? <Table label="Danh sách người dùng" headers={['Họ tên', 'Email', 'Vai trò hệ thống', 'Trạng thái']}>{rows.map(u => <tr key={u.id}><td className="admin-name">{u.full_name}</td><td>{u.email}</td><td>{u.system_role === 'admin' ? 'Quản trị viên' : 'Người dùng'}</td><td><StatusPill tone={u.is_active ? 'ok' : 'neutral'} icon={u.is_active ? 'check' : 'lock'}>{u.is_active ? 'Đang hoạt động' : 'Đã khóa'}</StatusPill></td></tr>)}</Table> : <Empty>{search ? 'Không có người dùng khớp bộ lọc. Thử tên hoặc email khác.' : 'Chưa có người dùng. Chọn “Thêm người dùng” để tạo tài khoản.'}</Empty>}
    </QueryState></section>;
}
