import { useQuery } from '@tanstack/react-query';
import { useOutletContext } from 'react-router-dom';
import { apiFetch } from '@/api/client';
import type { ClassRole, ClassSummary, Me } from '@/api/types';
import { isUnauthorized } from '@/features/auth';
import { Card } from '@/components/ui/card';
import { LoginRedirect, RetryError } from '@/components/feedback';
export function Classes({ role }: { role: ClassRole }) {
  const me = useOutletContext<Me>();
  const classes = useQuery({ queryKey: ['classes', me.id], queryFn: () => apiFetch<ClassSummary[]>('/classes'), retry: false });
  if (isUnauthorized(classes.error)) return <LoginRedirect />;
  const rows = classes.data?.filter(c => me.classes.some(m => m.class_id === c.id && m.role === role) && (role === 'lecturer' || c.status === 'open')) ?? [];
  return <><p className="text-sm font-semibold uppercase tracking-widest text-primary">{role === 'student' ? 'Không gian học tập' : 'Không gian giảng dạy'}</p><h1 className="mt-2 text-4xl">{role === 'student' ? 'Lớp học của tôi' : 'Lớp phụ trách'}</h1><p className="mt-3 text-muted-foreground">{role === 'student' ? 'Tiếp tục hành trình học tập từ những học liệu của lớp.' : 'Các lớp học bạn đang phụ trách giảng dạy.'}</p>
    <section className="mt-8" aria-label="Danh sách lớp" aria-busy={classes.isFetching}>
      {classes.isPending ? <p role="status">Đang tải danh sách lớp…</p> : classes.isError ? <RetryError retry={() => void classes.refetch()} /> : rows.length ? <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">{rows.map(c => <Card key={c.id}><p className="text-sm text-muted-foreground">Học kỳ {c.term}</p><h2 className="mt-2 break-all text-2xl">{c.code}</h2><p className="mt-6 inline-block rounded-md bg-secondary px-3 py-1 text-sm text-secondary-foreground">{c.status === 'open' ? 'Đang mở' : 'Đã đóng'}</p></Card>)}</div> : <Card className="py-12 text-center"><h2 className="text-2xl">{role === 'student' ? 'Bạn chưa được ghi danh lớp nào' : 'Bạn chưa được phân công lớp nào'}</h2><p className="mt-3 text-muted-foreground">Vui lòng liên hệ giảng viên hoặc quản trị viên để được hỗ trợ.</p></Card>}
    </section>
  </>;
}
