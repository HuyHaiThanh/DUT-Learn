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
