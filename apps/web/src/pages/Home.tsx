import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../api/health';

export function Home() {
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth, retry: false });
  return <main>
    <p className="brand">DUTLearn</p>
    <h1>Trạng thái hệ thống</h1>
    <p>Nền tảng hỗ trợ học tập theo học liệu môn học.</p>
    <section aria-label="Kết nối dịch vụ" aria-live="polite" aria-busy={health.isFetching}>
      {health.isPending && <p>Đang kiểm tra kết nối…</p>}
      {health.isError && <p role="alert">Không thể kết nối máy chủ. Vui lòng thử lại.</p>}
      {health.data && !health.isError && <dl>
        <div><dt>Máy chủ</dt><dd>Đang hoạt động</dd></div>
        <div><dt>Cơ sở dữ liệu</dt><dd>{health.data.db ? 'Đã kết nối' : 'Chưa kết nối'}</dd></div>
        <div><dt>Trợ giảng AI</dt><dd>{health.data.llm ? 'Sẵn sàng' : 'Chưa sẵn sàng'}</dd></div>
      </dl>}
    </section>
    <button onClick={() => void health.refetch()} disabled={health.isFetching}>
      {health.isFetching ? 'Đang kiểm tra…' : 'Kiểm tra lại'}
    </button>
  </main>;
}
