export type ClassRole = 'lecturer' | 'student';
export interface Me {
  id: string;
  email: string;
  full_name: string;
  system_role: 'admin' | 'user';
  classes: { class_id: string; role: ClassRole }[];
}
// GET /classes: class columns from CONTRACT_V0 section 3.
export interface ClassSummary {
  id: string;
  course_id: string;
  code: string;
  term: string;
  status: 'open' | 'closed';
}
