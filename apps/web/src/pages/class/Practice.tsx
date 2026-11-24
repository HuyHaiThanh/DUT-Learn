import { useOutletContext, useParams } from 'react-router-dom';
import type { ClassOutletContext } from './ClassLayout';
import { LecturerPractice, StudentPractice } from '@/features/practice/Practice';

export function Practice() {
  const { classId = '' } = useParams();
  const { classroom, me } = useOutletContext<ClassOutletContext>();
  return classroom.role === 'lecturer' ? <LecturerPractice key={`${classId}-${me.id}`} classId={classId} userId={me.id} lessons={classroom.lessons} /> : <StudentPractice key={`${classId}-${me.id}`} classId={classId} userId={me.id} />;
}
