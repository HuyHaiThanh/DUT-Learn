import { useQuery } from '@tanstack/react-query';
import { apiFetch } from './client';
import type { ClassRole, Me } from './types';

export interface AdminUser extends Omit<Me, 'classes'> { is_active: boolean }
export interface Course { id: string; code: string; name: string }
export interface AdminClass { id: string; course_id: string; code: string; term: string; status: 'open' | 'closed'; content_version: number }
export interface Member { id: string; class_id: string; user_id: string; role: ClassRole }
export type UserCreate = Pick<AdminUser, 'email' | 'full_name' | 'system_role'> & { password: string };
export type CourseCreate = Omit<Course, 'id'>;
export type ClassCreate = Omit<AdminClass, 'id' | 'content_version'>;
export type MemberCreate = Pick<Member, 'user_id' | 'role'>;

export const adminKeys = {
  users: ['admin', 'users'] as const,
  courses: ['admin', 'courses'] as const,
  classes: ['admin', 'classes'] as const,
  members: (classId: string) => ['admin', 'members', classId] as const,
};
export const useAdminUsers = () => useQuery({ queryKey: adminKeys.users, queryFn: () => apiFetch<AdminUser[]>('/admin/users'), retry: false });
export const useAdminCourses = () => useQuery({ queryKey: adminKeys.courses, queryFn: () => apiFetch<Course[]>('/admin/courses'), retry: false });
export const useAdminClasses = () => useQuery({ queryKey: adminKeys.classes, queryFn: () => apiFetch<AdminClass[]>('/admin/classes'), retry: false });
const membersPath = (classId: string) => `/admin/classes/${encodeURIComponent(classId)}/members`;
export const useAdminMembers = (classId: string) => useQuery({ queryKey: adminKeys.members(classId), queryFn: () => apiFetch<Member[]>(membersPath(classId)), retry: false });
const post = <T>(path: string, body: unknown) => apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) });
export const createUser = (body: UserCreate) => post<AdminUser>('/admin/users', body);
export const createCourse = (body: CourseCreate) => post<Course>('/admin/courses', body);
export const createClass = (body: ClassCreate) => post<AdminClass>('/admin/classes', body);
export const enrollMember = (classId: string, body: MemberCreate) => post<Member>(membersPath(classId), body);
export const removeMember = (classId: string, userId: string) => apiFetch<void>(`${membersPath(classId)}/${encodeURIComponent(userId)}`, { method: 'DELETE' });
