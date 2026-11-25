import { Link, NavLink, Outlet, useOutletContext } from 'react-router-dom';
import type { Me } from '@/api/types';
import { homePath } from '@/features/auth';
import { PageBand } from '@/components/PageBand';

export function AdminLayout() {
  const me = useOutletContext<Me>();
  if (me.system_role !== 'admin') return <div className="state-panel"><p role="alert">Bạn không có quyền quản trị.</p><Link to={homePath(me)}>Về trang chủ</Link></div>;
  return <div className="admin-page"><PageBand title="Quản trị" meta="Quản lý tài khoản, học phần và thành viên lớp.">
    <nav className="admin-nav" aria-label="Quản trị"><NavLink to="/quan-tri/nguoi-dung">Người dùng</NavLink><NavLink to="/quan-tri/hoc-phan">Học phần</NavLink><NavLink to="/quan-tri/lop-hoc-phan">Lớp học phần</NavLink></nav>
    </PageBand><div className="page-body"><Outlet /></div>
  </div>;
}
