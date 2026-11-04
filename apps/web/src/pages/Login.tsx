import { useEffect, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import { apiFetch, ApiError } from '@/api/client';
import type { Me } from '@/api/types';
import { homePath } from '@/features/auth';
import { Brand } from '@/components/Brand';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export function Login() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [lockedUntil, setLockedUntil] = useState(0);
  const [remainingMinutes, setRemainingMinutes] = useState(0);
  const supportEmail = import.meta.env.VITE_SUPPORT_EMAIL?.trim();
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
    onError: error => {
      if (error instanceof ApiError && error.status === 429) {
        const seconds = error.details?.retry_after_seconds;
        const retrySeconds = typeof seconds === 'number' && Number.isFinite(seconds) && seconds >= 0 ? seconds : 900;
        setLockedUntil(Date.now() + retrySeconds * 1000);
        setRemainingMinutes(Math.ceil(retrySeconds / 60));
      }
    },
  });
  useEffect(() => {
    if (!lockedUntil) return;
    const update = () => setRemainingMinutes(Math.max(0, Math.ceil((lockedUntil - Date.now()) / 60000)));
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [lockedUntil]);
  let message = 'Không thể đăng nhập. Kiểm tra kết nối và thử lại.';
  if (login.error instanceof ApiError) {
    if (login.error.status === 401) {
      message = 'Email hoặc mật khẩu không đúng.';
      const attempts = login.error.details?.attempts_remaining;
      if (typeof attempts === 'number' && Number.isInteger(attempts) && attempts >= 0 && attempts <= 3) {
        message += attempts === 0 ? ' Lần sai tiếp theo sẽ tạm khóa đăng nhập 15 phút.' : ` Bạn còn ${attempts} lần thử trước khi bị tạm khóa 15 phút.`;
      }
    } else if (login.error.status === 429) {
      message = remainingMinutes > 0 ? `Bạn đã thử quá nhiều lần. Thử lại sau ${remainingMinutes} phút.` : 'Bạn có thể thử đăng nhập lại.';
    }
  }
  const invalidCredentials = login.error instanceof ApiError && login.error.status === 401;
  const blocked = login.isPending || remainingMinutes > 0;
  return <div className="login-layout">
    <main className="login-form-side" id="main-content">
      <Brand />
      <div className="login-content">
        <h1>Đăng nhập</h1>
        <p className="login-intro">Học liệu và trợ giảng theo lớp học phần, Khoa Công nghệ Thông tin.</p>
        <form className="login-form" aria-busy={login.isPending} onSubmit={e => {
          e.preventDefault();
          if (blocked || lockedUntil > Date.now()) return;
          const data = new FormData(e.currentTarget);
          login.mutate({ email: String(data.get('email') ?? ''), password: String(data.get('password') ?? '') });
        }}>
          <div className="form-field"><Label htmlFor="email">Email</Label><Input id="email" name="email" type="email" autoComplete="username" required disabled={login.isPending} aria-invalid={invalidCredentials || undefined} aria-describedby={login.isError ? 'login-error' : undefined} /></div>
          <div className="form-field"><Label htmlFor="password">Mật khẩu</Label><Input id="password" name="password" type="password" autoComplete="current-password" required disabled={login.isPending} aria-invalid={invalidCredentials || undefined} aria-describedby={login.isError ? 'login-error' : undefined} />
            {login.isError && <p id="login-error" role="alert" aria-atomic="true" className="form-error">{message}</p>}
          </div>
          <Button type="submit" disabled={blocked}>{login.isPending ? 'Đang đăng nhập…' : 'Đăng nhập'}</Button>
        </form>
        <p className="login-help">Tài khoản do quản trị viên cấp cho sinh viên và giảng viên tham gia thử nghiệm.{supportEmail && <> Quên mật khẩu hoặc chưa có tài khoản: liên hệ <a href={`mailto:${supportEmail}`}>{supportEmail}</a>.</>}</p>
      </div>
      <p className="login-footer">Đồ án tốt nghiệp · Trường Đại học Bách khoa, Đại học Đà Nẵng<br />Phiên bản thử nghiệm, chưa phải hệ thống chính thức của trường.</p>
    </main>
    <div className="login-visual" aria-hidden="true">
      <div className="login-illustration">
        <div className="document-preview">
          <p className="document-chapter">Chương VII. Kiểu con trỏ</p>
          <p className="document-title">7.2 Khai báo và sử dụng con trỏ</p>
          <p>Con trỏ là một biến dùng để lưu địa chỉ của một biến khác trong bộ nhớ.</p>
          <p><mark>Toán tử * đặt trước tên con trỏ cho phép truy cập giá trị tại địa chỉ mà con trỏ giữ.</mark></p>
          <pre>{'int *p = &a;\n*p = 10;'}</pre>
        </div>
        <div className="illustration-chat">
          <div className="illustration-question">Vì sao *p = 10 đổi được a?</div>
          <div className="illustration-answer">Vì *p chính là ô nhớ của a <span className="citation-number">1</span></div>
          <div className="illustration-source"><b>1</b><span>Giáo trình, mục 7.2</span><span>tr. 133</span></div>
        </div>
      </div>
    </div>
  </div>;
}
