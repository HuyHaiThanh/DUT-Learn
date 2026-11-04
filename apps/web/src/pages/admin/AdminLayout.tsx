import { Link, NavLink, Outlet, useOutletContext } from 'react-router-dom';
import type { Me } from '@/api/types';
import { homePath } from '@/features/auth';

export function AdminLayout() {
  const me = useOutletContext<Me>();
  if (me.system_role !== 'admin') return <div className="state-panel"><p role="alert">Bạn không có quyền quản trị.</p><Link to={homePath(me)}>Về trang chủ</Link></div>;
  return <div className="admin-page"><div className="page-heading"><h1>Quản trị</h1><p>Quản lý tài khoản, học phần và thành viên lớp.</p></div>
    <nav className="admin-nav" aria-label="Quản trị"><NavLink to="/quan-tri/nguoi-dung">Người dùng</NavLink><NavLink to="/quan-tri/hoc-phan">Học phần</NavLink><NavLink to="/quan-tri/lop-hoc-phan">Lớp học phần</NavLink></nav>
    <Outlet />
  </div>;
}
