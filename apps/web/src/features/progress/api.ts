export type ProgressData = {
  activity: { materials_opened: number; materials_available: number; questions_asked: number; citations_opened: number; last_activity_at: string | null };
  results: { assignments_submitted: number; assignments_available: number; grades: { assignment_id: string; title: string; grade: number; published_at: string }[]; practice_attempted: number; practice_available: number; practice_mcq_correct_last: number; practice_mcq_attempted: number };
};
export type StudentProgress = ProgressData & { user_id: string; full_name: string; last_activity_at: string | null };
