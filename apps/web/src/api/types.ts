export type ClassRole = 'lecturer' | 'student';
export interface Me {
  id: string;
  email: string;
  full_name: string;
  system_role: 'admin' | 'user';
  classes: { class_id: string; role: ClassRole }[];
}
// GET /classes: CONTRACT_V0 section 5.
export interface ClassSummary {
  id: string;
  course_id: string;
  course_code: string;
  course_name: string;
  role: ClassRole;
  content_version: number;
  code: string;
  term: string;
  status: 'open' | 'closed';
}

export interface Lesson {
  id: string;
  title: string;
  position: number;
  is_published: boolean;
}
export interface ClassDetail extends ClassSummary {
  lessons: Lesson[];
}
export interface LessonCreate { title: string; position?: number }
export interface LessonUpdate { title?: string; position?: number; is_published?: boolean }
