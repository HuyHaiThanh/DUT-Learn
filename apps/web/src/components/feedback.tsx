import { Navigate, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';

export function RetryError({ retry }: { retry: () => void }) {
  return <div role="alert" className="rounded-xl border border-destructive bg-card p-5">
    <p>Không thể kết nối máy chủ. Vui lòng thử lại.</p>
    <Button variant="outline" className="mt-3" onClick={retry}>Thử lại</Button>
  </div>;
}

export function LoginRedirect() {
  const location = useLocation();
  return <Navigate to="/login" replace state={{ from: location.pathname + location.search + location.hash }} />;
}
