import { useQuery } from '@tanstack/react-query';
import { Link, NavLink, Outlet, useOutletContext, useParams } from 'react-router-dom';
import { ApiError, apiFetch } from '@/api/client';
import type { ClassDetail, Me } from '@/api/types';
import { homePath, isUnauthorized } from '@/features/auth';
import { LoginRedirect, RetryError } from '@/components/feedback';
import { formatTerm } from '../Classes';
import { PageBand } from '@/components/PageBand';

export interface ClassOutletContext { classroom: ClassDetail; me: Me }

export function ClassLayout() {
  const { classId = '' } = useParams();
  const me = useOutletContext<Me>();
  const classroom = useQuery({ queryKey: ['class', classId], queryFn: () => apiFetch<ClassDetail>(`/classes/${classId}`), retry: false });
  if (isUnauthorized(classroom.error)) return <LoginRedirect />;
  const back = classroom.data ? classroom.data.role === 'lecturer' ? '/giang-day' : '/hoc' : me.classes.find(c => c.class_id === classId)?.role === 'lecturer' ? '/giang-day' : homePath(me);
  const backLink = <Link to={back} aria-label="Quay lại danh sách lớp">← Lớp của tôi</Link>;
  if (classroom.error instanceof ApiError && classroom.error.status === 404) return <div className="state-panel"><p role="alert">Không tìm thấy lớp hoặc bạn không có quyền xem.</p>{backLink}</div>;
  if (classroom.isError) return <RetryError homeTo={back} retry={() => void classroom.refetch()} />;
  if (classroom.isPending) return <p role="status" className="state-panel"><span className="spinner" aria-hidden="true" />Đang tải lớp…</p>;
  const data = classroom.data;
  return <div className="lesson-page" aria-busy={classroom.isFetching}>
    <PageBand eyebrow={backLink} title={data.course_name} meta={`${data.code} · ${formatTerm(data.term)}`}>
    <nav aria-label="Nội dung lớp" className="class-tabs">
      <NavLink className="nav-link shrink-0 whitespace-nowrap" to={`/lop/${classId}`} end>Bài học</NavLink>
      <NavLink className="nav-link shrink-0 whitespace-nowrap" to={`/lop/${classId}/bai-tap`}>Bài tập</NavLink>
      <NavLink className="nav-link shrink-0 whitespace-nowrap" to={`/lop/${classId}/luyen-tap`}>Luyện tập</NavLink>
      <NavLink className="nav-link shrink-0 whitespace-nowrap" to={`/lop/${classId}/tien-do`}>Tiến độ</NavLink>
    </nav>
    </PageBand><div className="page-body"><Outlet context={{ classroom: data, me } satisfies ClassOutletContext} /></div>
  </div>;
}
