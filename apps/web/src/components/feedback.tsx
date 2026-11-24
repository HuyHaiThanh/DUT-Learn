import { Link, Navigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { homePath, useMe } from '@/features/auth';

export function RetryError({ retry, homeTo }: { retry: () => void; homeTo?: string }) {
  const { data: me } = useMe();
  return <div role="alert" className="state-panel">
    <p>Không thể kết nối máy chủ. Vui lòng thử lại.</p>
    <div className="mt-3 flex flex-wrap items-center gap-4"><Button variant="outline" onClick={retry}>Thử lại</Button><Link to={homeTo ?? (me ? homePath(me) : '/')}>{me ? 'Về trang học tập' : 'Về trang chủ'}</Link></div>
  </div>;
}

export function LoginRedirect() {
  const location = useLocation();
  return <Navigate to="/login" replace state={{ from: location.pathname + location.search + location.hash }} />;
}
