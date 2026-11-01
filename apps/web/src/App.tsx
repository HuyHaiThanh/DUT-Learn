import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, NavLink, Navigate, Outlet, Route, Routes, useNavigate, useOutletContext } from 'react-router-dom';
import { apiFetch } from '@/api/client';
import type { Me } from '@/api/types';
import { homePath, isUnauthorized, useMe } from '@/features/auth';
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
  if (me.isError) return <main className="m-auto max-w-lg p-6"><RetryError retry={() => void me.refetch()} /></main>;
  if (me.isPending) return <p role="status" className="p-8">Đang tải tài khoản…</p>;
  const user = me.data;
  const student = (user.system_role !== 'admin' && !user.classes.length) || user.classes.some(c => c.role === 'student');
  const lecturer = user.classes.some(c => c.role === 'lecturer');
  return <div className="app-shell">
    <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-card focus:p-3">Đến nội dung chính</a>
    <header className="topbar"><Link to="/" className="text-xl font-bold tracking-tight text-primary-dark">DUTLearn<span className="ml-3 hidden text-xs font-normal text-muted-foreground sm:inline">Không gian học tập</span></Link>
      <div className="flex min-w-0 items-center gap-2"><Button className="mobile-toggle" variant="outline" aria-expanded={open} aria-controls="main-nav" onClick={() => setOpen(!open)}>Menu</Button>
        <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" aria-label="Menu người dùng" className="max-w-44"><span className="truncate">{user.full_name}</span><span aria-hidden="true">▾</span></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><p className="break-all px-3 py-2 text-xs text-muted-foreground">{user.email}</p><DropdownMenuItem disabled={logout.isPending} onSelect={() => logout.mutate()}>{logout.isPending ? 'Đang đăng xuất…' : 'Đăng xuất'}</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
      </div>
    </header>
    <aside className="sidebar" data-open={open}><nav id="main-nav" aria-label="Điều hướng chính"><p className="px-4 py-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Không gian của bạn</p>{student && <NavLink className="nav-link" to="/hoc" onClick={() => setOpen(false)}>Học tập</NavLink>}{lecturer && <NavLink className="nav-link" to="/giang-day" onClick={() => setOpen(false)}>Giảng dạy</NavLink>}{user.system_role === 'admin' && <NavLink className="nav-link" to="/quan-tri" onClick={() => setOpen(false)}>Quản trị</NavLink>}</nav></aside>
    <main id="main-content" tabIndex={-1} className="min-w-0 p-5 md:p-10"><div className="mx-auto max-w-6xl">{logout.isError && !isUnauthorized(logout.error) && <p role="alert" className="mb-5">Không thể đăng xuất. Vui lòng thử lại từ menu người dùng.</p>}<Outlet context={user} /></div></main>
  </div>;
}
function HomeRedirect() { return <Navigate to={homePath(useOutletContext<Me>())} replace />; }
function Admin() {
  const me = useOutletContext<Me>();
  if (me.system_role !== 'admin') return <p role="alert">Bạn không có quyền quản trị.</p>;
  return <><p className="text-sm font-semibold text-primary">Quản trị hệ thống</p><h1 className="mt-2 text-4xl">Không gian quản trị</h1><p className="mt-3 text-muted-foreground">Các chức năng quản lý sẽ được bổ sung ở giai đoạn tiếp theo.</p><div className="mt-8 grid gap-4 sm:grid-cols-3">{['Người dùng', 'Môn học', 'Lớp học'].map(label => <section key={label} className="rounded-xl border border-border bg-card p-6"><h2 className="text-2xl">{label}</h2><p className="mt-3 text-sm text-muted-foreground">Chưa khả dụng</p></section>)}</div></>;
}
export function App() {
  return <Routes><Route path="/login" element={<Login />} /><Route element={<Shell />}><Route index element={<HomeRedirect />} /><Route path="/hoc" element={<Classes role="student" />} /><Route path="/giang-day" element={<Classes role="lecturer" />} /><Route path="/quan-tri" element={<Admin />} /></Route><Route path="*" element={<main className="mx-auto max-w-xl p-8"><p className="text-primary">404</p><h1 className="my-4 text-4xl">Không tìm thấy trang</h1><p className="mb-5">Đường dẫn này không tồn tại hoặc đã được thay đổi.</p><Button asChild><Link to="/">Về trang chủ</Link></Button></main>} /></Routes>;
}
