export interface Question {
  id: string; lesson_id: string | null; kind: 'mcq' | 'short'; stem: string; options: string[] | null;
}
export interface LecturerQuestion extends Question {
  answer_key: string; explanation: string; origin: 'lecturer' | 'ai'; status: 'draft' | 'approved' | 'published' | 'retired'; supersedes_id: string | null;
}
export interface StudentQuestion extends Question { my_attempts: number; my_last_correct: boolean | null }
export interface QuestionBody {
  kind: 'mcq' | 'short'; stem: string; options: string[] | null; answer_key: string; explanation: string; lesson_id: string | null;
}
export interface AttemptResult { attempt_id: string; is_correct: boolean | null; answer_key: string; explanation: string; submitted_at: string }
