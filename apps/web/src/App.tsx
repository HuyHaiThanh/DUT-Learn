import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, NavLink, Navigate, Outlet, Route, Routes, useNavigate, useOutletContext } from 'react-router-dom';
import { apiFetch } from '@/api/client';
import type { Me } from '@/api/types';
import { homePath, isUnauthorized, useMe } from '@/features/auth';
import { Brand } from '@/components/Brand';
import { Chevron } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Login } from '@/pages/Login';
import { Classes } from '@/pages/Classes';
import { LoginRedirect, RetryError } from '@/components/feedback';

function Shell() {
  const me = useMe();
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const navigate = useNavigate();
  const logout = useMutation({
    mutationFn: () => apiFetch('/auth/logout', { method: 'POST' }),
    onSuccess: async () => { await client.cancelQueries(); client.clear(); navigate('/login', { replace: true }); },
    onError: async error => { if (isUnauthorized(error)) { await client.cancelQueries(); client.clear(); navigate('/login', { replace: true }); } },
  });
  if (isUnauthorized(me.error)) return <LoginRedirect />;
  if (me.isError) return <main className="standalone-page"><h1>Không thể tải tài khoản</h1><RetryError retry={() => void me.refetch()} /></main>;
  if (me.isPending) return <main className="standalone-page"><p role="status" className="state-panel">Đang tải tài khoản…</p></main>;
  const user = me.data;
  const student = user.classes.some(c => c.role === 'student');
  const lecturer = user.classes.some(c => c.role === 'lecturer');
  const initials = user.full_name.trim().split(/\s+/).filter((_, i, names) => i === 0 || i === names.length - 1).map(name => name[0]).join('');
  return <div className="app-shell">
    <a href="#main-content" className="skip-link">Bỏ qua đến nội dung chính</a>
    <header className="topbar"><Link to={homePath(user)} className="brand-link"><Brand /></Link>
      <button type="button" className="mobile-toggle" aria-label="Menu" aria-expanded={open} aria-controls="main-nav" onClick={() => setOpen(!open)}><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6h16M4 12h16M4 18h16" /></svg></button>
      <nav id="main-nav" className="main-nav" data-open={open} aria-label="Điều hướng chính" onKeyDown={e => { if (e.key === 'Escape') { setOpen(false); document.querySelector<HTMLButtonElement>('.mobile-toggle')?.focus(); } }}>
        {student && <NavLink className="nav-link" to="/hoc" onClick={() => setOpen(false)}>Học tập</NavLink>}
        {lecturer && <NavLink className="nav-link" to="/giang-day" onClick={() => setOpen(false)}>Giảng dạy</NavLink>}
        {user.system_role === 'admin' && <NavLink className="nav-link" to="/quan-tri" onClick={() => setOpen(false)}>Quản trị</NavLink>}
      </nav>
      <div className="user-menu"><DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" className="user-trigger" aria-haspopup="menu"><span className="user-initials" aria-hidden="true">{initials}</span><span className="user-name">{user.full_name}</span><Chevron down /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><p className="break-all px-3 py-2 text-sm text-muted-foreground">{user.email}</p><DropdownMenuItem disabled={logout.isPending} onSelect={() => logout.mutate()}>{logout.isPending ? 'Đang đăng xuất…' : 'Đăng xuất'}</DropdownMenuItem></DropdownMenuContent></DropdownMenu></div>
    </header>
    <main id="main-content" tabIndex={-1} className="page-content">{logout.isError && !isUnauthorized(logout.error) && <p role="alert" className="form-error">Không thể đăng xuất. Vui lòng thử lại từ menu người dùng.</p>}<Outlet context={user} /></main>
  </div>;
}
function HomeRedirect() { return <Navigate to={homePath(useOutletContext<Me>())} replace />; }
function Admin() {
  const me = useOutletContext<Me>();
  if (me.system_role !== 'admin') return <div className="state-panel"><p role="alert">Bạn không có quyền quản trị.</p><Link to={homePath(me)}>Về trang chủ</Link></div>;
  return <><div className="page-heading"><h1>Quản trị</h1></div><div className="list-panel">{[
    ['Người dùng', 'Quản lý tài khoản sinh viên và giảng viên.'],
    ['Môn học', 'Quản lý mã môn và tên môn học.'],
    ['Lớp học & ghi danh', 'Quản lý lớp học và phân công thành viên.'],
  ].map(([label, description]) => <section key={label} className="admin-row"><div><h2 className="row-title">{label}</h2><p className="metadata">{description}</p></div><span className="coming-soon">Sắp có</span></section>)}</div></>;
}
function ClassPlaceholder() {
  const me = useOutletContext<Me>();
  return <div className="state-panel"><h1>Trang lớp đang được xây dựng</h1><p>Danh sách bài học sẽ được bổ sung ở giai đoạn tiếp theo.</p><Link to={homePath(me)}>Quay lại danh sách lớp</Link></div>;
}
function NotFound() {
  const me = useMe();
  return <main className="standalone-page"><Brand /><div className="state-panel"><p className="metadata">404</p><h1>Không tìm thấy trang</h1><p>Đường dẫn này không tồn tại hoặc đã được thay đổi.</p><Button asChild><Link to={me.data ? homePath(me.data) : '/'}>Về trang chủ</Link></Button></div></main>;
}
export function App() {
  return <Routes><Route path="/login" element={<Login />} /><Route element={<Shell />}><Route index element={<HomeRedirect />} /><Route path="/hoc" element={<Classes role="student" />} /><Route path="/giang-day" element={<Classes role="lecturer" />} /><Route path="/quan-tri" element={<Admin />} /><Route path="/lop/:classId" element={<ClassPlaceholder />} /></Route><Route path="*" element={<NotFound />} /></Routes>;
}
