import { useQuery } from '@tanstack/react-query';
import { apiFetch, ApiError } from '@/api/client';
import type { Me } from '@/api/types';

export function useMe() {
  return useQuery({ queryKey: ['me'], queryFn: () => apiFetch<Me>('/auth/me'), retry: false });
}
export function isUnauthorized(error: unknown) { return error instanceof ApiError && error.status === 401; }
export function homePath(me: Me) {
  if (me.system_role === 'admin') return '/quan-tri';
  return me.classes.some(c => c.role === 'lecturer') ? '/giang-day' : '/hoc';
}
