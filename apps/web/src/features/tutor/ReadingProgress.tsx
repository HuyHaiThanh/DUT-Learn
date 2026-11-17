import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/api/client';
import { isUnauthorized } from '@/features/auth';
import { LoginRedirect } from '@/components/feedback';
import { ContinueReading } from '@/components/ContinueReading';
import type { Context, Position } from './api';

export function useReadingPosition(context: Context | null | undefined, versionId: string, pageIndex: number, readable: boolean) {
  const client = useQueryClient();
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (!context || !readable) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void apiFetch<void>('/reading-position', { method: 'PUT', signal: controller.signal, body: JSON.stringify({ material_id: context.material_id, version_id: versionId, page_index: pageIndex }) })
        .then(() => { if (!controller.signal.aborted) { setError(null); void client.invalidateQueries({ queryKey: ['continue-reading'] }); } })
        .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason); });
    }, 1000);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [context, versionId, pageIndex, readable, client]);
  return error;
}

export function ContinueReadingSection({ userId }: { userId: string }) {
  const position = useQuery({ queryKey: ['continue-reading', userId], queryFn: ({ signal }) => apiFetch<Position | null>('/me/continue', { signal, cache: 'no-store' }), retry: false, staleTime: 0 });
  if (isUnauthorized(position.error)) return <LoginRedirect />;
  if (position.isError) return <p role="status">Không tải được vị trí đọc gần nhất. <button onClick={() => void position.refetch()}>Thử lại vị trí đọc</button></p>;
  if (!position.data) return null;
  const data = position.data;
  return <ContinueReading to={`/doc/${data.version_id}?page=${data.page_index + 1}`} title={data.material_title} courseName={data.course_name} pageLabel={data.page_label} lastOpenedLabel={new Date(data.updated_at).toLocaleString('vi-VN')} />;
}
