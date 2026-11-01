import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiFetch, ApiError } from '@/api/client';
import type { Me } from '@/api/types';
import { homePath } from '@/features/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';

export function Login() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const login = useMutation({
    mutationFn: async (credentials: { email: string; password: string }) => {
      await apiFetch('/auth/login', { method: 'POST', body: JSON.stringify(credentials) });
      await client.cancelQueries();
      client.clear();
      return client.fetchQuery({ queryKey: ['me'], queryFn: () => apiFetch<Me>('/auth/me') });
    },
    onSuccess: me => {
      const from: unknown = location.state?.from;
      const safePath = typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') && !from.startsWith('/login') && !from.includes('\\');
      navigate(safePath ? from : homePath(me), { replace: true });
    },
  });
  let message = 'Không thể đăng nhập. Kiểm tra kết nối và thử lại.';
  if (login.error instanceof ApiError) {
    if (login.error.code === 'invalid_credentials') message = 'Email hoặc mật khẩu không đúng. Vui lòng thử lại.';
    else if (login.error.code === 'too_many_attempts') message = 'Bạn đã thử quá nhiều lần. Vui lòng đợi 15 phút rồi thử lại.';
    else message = login.error.message;
  }
  return <main className="mx-auto grid min-h-dvh max-w-5xl items-center gap-10 px-5 py-12 md:grid-cols-2">
    <div><p className="mb-6 text-lg font-bold text-primary">DUTLearn</p><p className="mb-3 text-sm font-semibold uppercase tracking-widest text-primary-dark">Không gian học tập</p><h1 className="text-4xl leading-tight md:text-5xl">Học từ nguồn đúng.<br />Hiểu theo cách của bạn.</h1><p className="mt-5 max-w-sm text-muted-foreground">Học liệu môn học, bài tập và hướng dẫn — trong cùng một không gian của lớp.</p><div className="mt-8 h-1 w-20 rounded bg-highlight" /></div>
    <Card><h2 className="text-3xl">Chào mừng trở lại</h2><p className="mt-2 text-sm text-muted-foreground">Đăng nhập bằng tài khoản được cấp.</p>
      <form className="mt-7 grid gap-5" aria-busy={login.isPending} onSubmit={e => {
        e.preventDefault();
        if (login.isPending) return;
        const data = new FormData(e.currentTarget);
        login.mutate({ email: String(data.get('email') ?? ''), password: String(data.get('password') ?? '') });
      }}>
        <div className="grid gap-2"><Label htmlFor="email">Email</Label><Input id="email" name="email" type="email" autoComplete="username" required disabled={login.isPending} /></div>
        <div className="grid gap-2"><Label htmlFor="password">Mật khẩu</Label><Input id="password" name="password" type="password" autoComplete="current-password" required disabled={login.isPending} aria-describedby={login.isError ? 'login-error' : undefined} /></div>
        {login.isError && <p id="login-error" role="alert" className="rounded-lg border border-destructive p-3 text-sm">{message}</p>}
        <Button type="submit" disabled={login.isPending}>{login.isPending ? 'Đang đăng nhập…' : 'Đăng nhập'}</Button>
      </form>
    </Card>
  </main>;
}
