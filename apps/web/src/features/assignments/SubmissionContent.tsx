import { AnswerText } from '@/features/tutor/AnswerText';

export function SubmissionContent({ content }: { content: string }) {
  return <div className="submission-content"><AnswerText text={content} citations={[]} open={() => undefined} /></div>;
}
