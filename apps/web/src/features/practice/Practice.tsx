import { useId, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, apiFetch } from '@/api/client';
import type { Lesson } from '@/api/types';
import { LoginRedirect, RetryError } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { isUnauthorized } from '@/features/auth';
import type { AttemptResult, LecturerQuestion, QuestionBody, StudentQuestion } from './types';
import './practice.css';

function PracticeError({ error }: { error: Error | null }) {
  if (!error) return null;
  if (isUnauthorized(error)) return <LoginRedirect />;
  return <p role="alert" className="form-error">{error instanceof ApiError ? error.message : 'Không thể kết nối máy chủ. Vui lòng thử lại.'}</p>;
}

function QuestionDialog({ classId, lessons, question }: { classId: string; lessons: Lesson[]; question?: LecturerQuestion }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<'mcq' | 'short'>('mcq');
  const [stem, setStem] = useState('');
  const [options, setOptions] = useState(['', '']);
  const [answer, setAnswer] = useState('0');
  const [sample, setSample] = useState('');
  const [explanation, setExplanation] = useState('');
  const [lesson, setLesson] = useState('');
  const id = useId();
  const client = useQueryClient();
  const title = question ? 'Sửa' : 'Thêm câu hỏi';
  const mutation = useMutation({
    mutationFn: (body: QuestionBody) => apiFetch<LecturerQuestion>(question ? `/practice/${question.id}` : `/classes/${classId}/practice`, { method: question ? 'PATCH' : 'POST', body: JSON.stringify(body) }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['practice', classId] }); setOpen(false); },
  });
  function changeOpen(next: boolean) {
    setOpen(next);
    if (next) {
      setKind(question?.kind ?? 'mcq'); setStem(question?.stem ?? ''); setOptions(question?.options ?? ['', '']);
      setAnswer(question?.kind === 'mcq' ? question.answer_key : '0'); setSample(question?.kind === 'short' ? question.answer_key : '');
      setExplanation(question?.explanation ?? ''); setLesson(question?.lesson_id ?? ''); mutation.reset();
    }
  }
  const validOptions = options.every(o => o.trim()) && new Set(options.map(o => o.trim())).size === options.length;
  return <Dialog title={title} description={question?.status === 'published' ? 'Câu đang dùng sẽ được thay bằng phiên bản mới; các lần làm cũ giữ nguyên đề cũ.' : 'Soạn câu luyện tập.'} trigger={<Button variant={question ? 'outline' : 'default'}>{title}</Button>} open={open} onOpenChange={changeOpen} pending={mutation.isPending}>
    <form className="admin-form practice-form" aria-label={title} onSubmit={e => { e.preventDefault(); if (!mutation.isPending) mutation.mutate({ kind, stem, options: kind === 'mcq' ? options : null, answer_key: kind === 'mcq' ? answer : sample, explanation, lesson_id: lesson || null }); }}>
      <fieldset disabled={mutation.isPending}>
        <div className="form-field"><Label htmlFor={`${id}-kind`}>Loại</Label><select id={`${id}-kind`} value={kind} onChange={e => setKind(e.target.value as 'mcq' | 'short')}><option value="mcq">Trắc nghiệm</option><option value="short">Tự luận ngắn</option></select></div>
        <div className="form-field"><Label htmlFor={`${id}-stem`}>Đề bài</Label><textarea id={`${id}-stem`} required maxLength={5000} value={stem} onChange={e => setStem(e.target.value)} /></div>
        <div className="form-field"><Label htmlFor={`${id}-lesson`}>Bài học (tùy chọn)</Label><select id={`${id}-lesson`} value={lesson} onChange={e => setLesson(e.target.value)}><option value="">Không chọn bài học</option>{lessons.map(l => <option key={l.id} value={l.id}>{l.title}</option>)}</select></div>
        {kind === 'mcq' ? <fieldset><legend>Đáp án đúng</legend>{options.map((option, i) => <div className="practice-option" key={i}>
          <input type="radio" name={`${id}-answer`} aria-label={`Đáp án đúng ${i + 1}`} checked={answer === String(i)} onChange={() => setAnswer(String(i))} />
          <div className="form-field"><Label htmlFor={`${id}-option-${i}`}>Phương án {i + 1}</Label><Input id={`${id}-option-${i}`} required maxLength={1000} value={option} onChange={e => setOptions(options.map((v, n) => n === i ? e.target.value : v))} /></div>
          <Button type="button" variant="outline" aria-label={`Bớt phương án ${i + 1}`} disabled={options.length <= 2} onClick={() => { setOptions(options.filter((_, n) => n !== i)); setAnswer(Number(answer) === i ? '0' : String(Number(answer) > i ? Number(answer) - 1 : Number(answer))); }}>Bớt</Button>
        </div>)}<Button type="button" variant="outline" disabled={options.length >= 6} onClick={() => setOptions([...options, ''])}>Thêm phương án</Button></fieldset> : <div className="form-field"><Label htmlFor={`${id}-sample`}>Đáp án mẫu</Label><textarea id={`${id}-sample`} required maxLength={5000} value={sample} onChange={e => setSample(e.target.value)} /></div>}
        <div className="form-field"><Label htmlFor={`${id}-explanation`}>Giải thích</Label><textarea id={`${id}-explanation`} maxLength={5000} value={explanation} onChange={e => setExplanation(e.target.value)} /></div>
      </fieldset>
      <PracticeError error={mutation.error} /><Button type="submit" disabled={mutation.isPending || !stem.trim() || (kind === 'mcq' ? !validOptions : !sample.trim())}>{mutation.isPending ? 'Đang lưu…' : 'Lưu câu hỏi'}</Button>
    </form>
  </Dialog>;
}

function QuestionActions({ classId, question, lessons }: { classId: string; question: LecturerQuestion; lessons: Lesson[] }) {
  const [open, setOpen] = useState(false);
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: (action: 'approve' | 'publish' | 'retire') => apiFetch<LecturerQuestion>(`/practice/${question.id}/${action}`, { method: 'POST' }),
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['practice', classId] }); setOpen(false); },
  });
  if (question.status === 'retired') return null;
  return <div><div className="practice-actions" aria-busy={mutation.isPending}>
    <QuestionDialog classId={classId} lessons={lessons} question={question} />
    {question.origin === 'ai' && question.status === 'draft' && <Button variant="outline" disabled={mutation.isPending} onClick={() => mutation.mutate('approve')}>Duyệt</Button>}
    {((question.origin === 'lecturer' && question.status === 'draft') || question.status === 'approved') && <Button disabled={mutation.isPending} onClick={() => mutation.mutate('publish')}>Công bố</Button>}
    {question.status === 'published' && <Dialog title="Ngừng dùng" description="Ngừng dùng câu luyện tập này?" open={open} onOpenChange={setOpen} pending={mutation.isPending} focusCancel trigger={<Button variant="outline" disabled={mutation.isPending}>Ngừng dùng</Button>}>
      <PracticeError error={mutation.error} /><Button disabled={mutation.isPending} onClick={() => mutation.mutate('retire')}>Xác nhận</Button>
    </Dialog>}
  </div><PracticeError error={mutation.error} /></div>;
}

export function LecturerPractice({ classId, userId, lessons }: { classId: string; userId: string; lessons: Lesson[] }) {
  const query = useQuery({ queryKey: ['practice', classId, userId, 'lecturer'], queryFn: () => apiFetch<LecturerQuestion[]>(`/classes/${classId}/practice?include_retired=true`), retry: false });
  return <section className="practice-page"><div className="admin-heading"><h2 className="section-title">Luyện tập</h2><QuestionDialog classId={classId} lessons={lessons} /></div>
    {query.isPending ? <p role="status">Đang tải câu luyện tập…</p> : query.isError ? <><PracticeError error={query.error} /><RetryError retry={() => void query.refetch()} /></> : !query.data.length ? <p className="state-panel">Chưa có câu luyện tập. Chọn “Thêm câu hỏi”.</p> : (['draft', 'published', 'retired'] as const).map(status => <details key={status} open={status !== 'retired'}>
      <summary>{status === 'draft' ? 'Nháp' : status === 'published' ? 'Đang dùng' : 'Ngừng dùng'}</summary>
      {query.data.filter(q => q.status === status || (status === 'draft' && q.status === 'approved')).map(q => <article className="practice-card" key={q.id}>
        <h3 className="row-title practice-preview">{q.stem}</h3><div className="practice-labels"><span>{q.kind === 'mcq' ? 'Trắc nghiệm' : 'Tự luận ngắn'}</span><span className={`admin-badge${q.origin === 'ai' ? ' practice-ai' : ''}`}>{q.origin === 'ai' ? 'AI đề xuất' : 'GV soạn'}</span>{q.status === 'approved' && <span className="admin-badge">Đã duyệt</span>}</div>
        <QuestionActions classId={classId} question={q} lessons={lessons} />
      </article>)}
    </details>)}
  </section>;
}

function QuestionStem({ text }: { text: string }) {
  return <div className="practice-stem">{text.split(/(```[\s\S]*?```|`[^`\n]+`)/g).map((part, i) => part.startsWith('```') ? <pre key={i}><code>{part.slice(3, -3).replace(/^[a-zA-Z0-9+#.-]*\n/, '')}</code></pre> : part.startsWith('`') ? <code key={i}>{part.slice(1, -1)}</code> : <span key={i}>{part}</span>)}</div>;
}

function StudentCard({ question }: { question: StudentQuestion }) {
  const [response, setResponse] = useState('');
  const [count, setCount] = useState(question.my_attempts);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [locked, setLocked] = useState(false);
  const submission = useRef<{ response: string; idempotency_key: string } | null>(null);
  const baseline = useRef(question.my_attempts);
  const pending = useRef(false);
  const id = useId();
  const mutation = useMutation({
    mutationFn: (body: { response: string; idempotency_key: string }) => apiFetch<AttemptResult>(`/practice/${question.id}/attempts`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: data => { setResult(data); setCount(n => Math.max(n, question.my_attempts, baseline.current + 1)); },
    onSettled: () => { pending.current = false; },
  });
  function submit() {
    if (pending.current || result || !response.trim()) return;
    pending.current = true;
    if (!submission.current) { baseline.current = Math.max(count, question.my_attempts); submission.current = { response, idempotency_key: crypto.randomUUID() }; }
    setLocked(true); mutation.mutate(submission.current);
  }
  function restart() { submission.current = null; setResponse(''); setResult(null); setLocked(false); mutation.reset(); }
  return <article className="practice-card">
    <p className="metadata">{question.kind === 'mcq' ? 'Trắc nghiệm' : 'Tự luận ngắn'}</p>{question.kind === 'short' && <QuestionStem text={question.stem} />}<p className="metadata" aria-live="polite">Đã làm {Math.max(count, question.my_attempts)} lần</p>
    <form onSubmit={e => { e.preventDefault(); submit(); }} aria-label="Trả lời câu luyện tập">
      {question.kind === 'mcq' ? <fieldset disabled={locked || mutation.isPending}><legend><QuestionStem text={question.stem} /></legend>{question.options?.map((option, i) => <label className="practice-radio" key={i}><input type="radio" name={id} checked={response === String(i)} onChange={() => setResponse(String(i))} /><span>{option}</span></label>)}</fieldset> : <div className="form-field"><Label htmlFor={id}>Câu trả lời</Label><textarea id={id} required maxLength={5000} disabled={locked || mutation.isPending} value={response} onChange={e => setResponse(e.target.value)} /></div>}
      {!result && <Button type="submit" disabled={mutation.isPending || !response.trim()}>{mutation.isPending ? 'Đang nộp…' : 'Nộp'}</Button>}
    </form>
    <PracticeError error={mutation.error} />
    {result && <div className="practice-result" role="status">
      <p className={`row-title${result.is_correct === null ? '' : result.is_correct ? ' practice-correct' : ' practice-incorrect'}`}>{result.is_correct === null ? 'Đã ghi nhận câu trả lời' : <><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d={result.is_correct ? 'm5 12 4 4L19 6' : 'm6 6 12 12M6 18 18 6'} /></svg>{result.is_correct ? 'Đúng' : 'Sai'}</>}</p>
      <p>{question.kind === 'mcq' ? 'Đáp án đúng' : 'Đáp án mẫu'}</p><QuestionStem text={question.kind === 'mcq' ? question.options?.[Number(result.answer_key)] ?? result.answer_key : result.answer_key} />
      <p>Giải thích</p><QuestionStem text={result.explanation} />
      {question.kind === 'short' && <p>Câu tự luận không chấm tự động; hãy tự đối chiếu với đáp án mẫu.</p>}
    </div>}
    {(result || mutation.isError) && <Button variant="outline" disabled={mutation.isPending} onClick={restart}>Làm lại</Button>}
  </article>;
}

export function StudentPractice({ classId, userId }: { classId: string; userId: string }) {
  const query = useQuery({ queryKey: ['practice', classId, userId, 'student'], queryFn: () => apiFetch<StudentQuestion[]>(`/classes/${classId}/practice`), retry: false });
  return <section className="practice-page"><h2 className="section-title">Luyện tập</h2>
    {query.isPending ? <p role="status">Đang tải câu luyện tập…</p> : query.isError ? <><PracticeError error={query.error} /><RetryError retry={() => void query.refetch()} /></> : query.data.length ? query.data.map(q => <StudentCard key={q.id} question={q} />) : <p className="state-panel">Giảng viên chưa công bố câu luyện tập nào.</p>}
  </section>;
}
