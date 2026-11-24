import { useEffect, useId, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiFetch } from '@/api/client';
import { isUnauthorized } from '@/features/auth';
import { LoginRedirect } from '@/components/feedback';
import { sendEvent } from '@/features/events';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { AnswerText, CitationButton } from './AnswerText';
import type { Answer, Citation, Context, Message } from './api';
import './tutor.css';

type Question = { question: string; mode: 'answer' | 'hint'; page_index: number };
function errorText(error: unknown) {
  if (!(error instanceof ApiError)) return 'Không kết nối được máy chủ.';
  return ({ 409: 'Học liệu vừa được thay đổi, hãy hỏi lại.', 429: 'Trợ giảng đang bận, vui lòng thử lại sau ít phút.', 503: 'Trợ giảng tạm thời không sẵn sàng.', 504: 'Trợ giảng phản hồi quá lâu, hãy thử lại.' } as Record<number, string>)[error.status] ?? 'Không thể gửi câu hỏi. Hãy thử lại.';
}

export function TutorPanel({ context, pageIndex }: { context: Context; pageIndex: number }) {
  const navigate = useNavigate();
  const id = useId();
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<'answer' | 'hint'>('answer');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<'loading' | 'ready' | 'error'>('loading');
  const [historyAttempt, setHistoryAttempt] = useState(0);
  const [pending, setPending] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [failure, setFailure] = useState<{ text: string; request: Question } | null>(null);
  const [notice, setNotice] = useState('');
  const [unauthorized, setUnauthorized] = useState(false);
  const request = useRef<AbortController | null>(null);
  const historyRequest = useRef<AbortController | null>(null);
  const sourceRequest = useRef<AbortController | null>(null);
  const messageList = useRef<HTMLDivElement | null>(null);
  const historyLoading = useRef(true);
  const generation = useRef(0);
  const length = Array.from(question).length;

  useEffect(() => {
    const list = messageList.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages, pending]);

  useEffect(() => {
    const controller = new AbortController();
    historyRequest.current = controller;
    historyLoading.current = true;
    async function load() {
      try {
        const sessions = await apiFetch<{ id: string; material_id: string | null; created_at: string }[]>(`/tutor/sessions?class_id=${context.class_id}`, { signal: controller.signal, cache: 'no-store' });
        if (controller.signal.aborted) return;
        const session = sessions.filter(s => s.material_id === context.material_id).sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
        const rows = session ? await apiFetch<Message[]>(`/tutor/sessions/${session.id}/messages`, { signal: controller.signal, cache: 'no-store' }) : [];
        if (!controller.signal.aborted) { setSessionId(session?.id ?? null); setMessages(rows); setHistory('ready'); historyLoading.current = false; }
      } catch (error) {
        if (!controller.signal.aborted) { setUnauthorized(isUnauthorized(error)); setHistory('error'); historyLoading.current = false; }
      }
    }
    void load();
    return () => { controller.abort(); request.current?.abort(); sourceRequest.current?.abort(); };
  }, [context.class_id, context.material_id, historyAttempt]);

  useEffect(() => {
    if (!pending) return;
    const start = Date.now();
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [pending]);

  async function send(payload: Question, retry = false) {
    if (request.current || historyLoading.current || history !== 'ready' || !payload.question.trim() || Array.from(payload.question).length > 2000) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(true); setSeconds(0); setFailure(null); setNotice('');
    if (!retry) setMessages(rows => [...rows, { id: crypto.randomUUID(), role: 'user', content: payload.question, status: 'ok', citations: [] }]);
    try {
      const result = await apiFetch<Answer>('/tutor/ask', { method: 'POST', signal: controller.signal, body: JSON.stringify({ ...context, ...payload, session_id: sessionId }) });
      if (controller.signal.aborted) return;
      setSessionId(result.session_id);
      setMessages(rows => [...rows, { id: result.message_id, role: 'assistant', content: result.answer, status: result.status, citations: result.citations, limitation: result.limitation, model: result.model }]);
      setQuestion(current => current === payload.question ? '' : current);
      setNotice('Trợ giảng đã trả lời.');
    } catch (error) {
      if (!controller.signal.aborted) { setUnauthorized(isUnauthorized(error)); setFailure({ text: errorText(error), request: payload }); }
    } finally {
      if (request.current === controller) { request.current = null; setPending(false); }
    }
  }

  async function open(citation: Citation) {
    sourceRequest.current?.abort();
    const controller = new AbortController(); sourceRequest.current = controller;
    const currentGeneration = generation.current;
    setNotice('Đang mở nguồn…');
    try {
      const source = await apiFetch<{ version_id: string; page_index: number; char_start: number; char_end: number }>(`/citations/${citation.id}/open`, { signal: controller.signal, cache: 'no-store' });
      if (!controller.signal.aborted && currentGeneration === generation.current) { void sendEvent(context.class_id, 'citation_opened', citation.id); setNotice(''); navigate(`/doc/${source.version_id}?page=${source.page_index + 1}&hl=${source.char_start}-${source.char_end}`); }
    } catch (error) {
      if (!controller.signal.aborted) { setUnauthorized(isUnauthorized(error)); setNotice(error instanceof ApiError && error.status === 410 ? 'Nguồn này đã bị thu hồi hoặc thay thế.' : 'Không kết nối được máy chủ.'); }
    }
  }

  function newSession() {
    generation.current++; historyRequest.current?.abort(); sourceRequest.current?.abort();
    historyLoading.current = false; setHistory('ready'); setSessionId(null); setMessages([]); setFailure(null); setNotice('Đã bắt đầu cuộc hỏi đáp mới.');
  }
  if (unauthorized) return <LoginRedirect />;
  return <section className="tutor-panel" aria-labelledby={`${id}-title`}>
    <header><h2 id={`${id}-title`}>Trợ giảng</h2><Button variant="outline" disabled={pending} onClick={newSession}>Cuộc hỏi đáp mới</Button>
      <div className="tutor-modes" role="group" aria-label="Chế độ trả lời">{(['answer', 'hint'] as const).map(value => <Button key={value} variant={mode === value ? 'default' : 'outline'} aria-pressed={mode === value} onClick={() => setMode(value)}>{value === 'answer' ? 'Trả lời' : 'Gợi ý từng bước'}</Button>)}</div>
    </header>
    <div ref={messageList} className="tutor-messages" aria-label="Luồng hỏi đáp">
      {history === 'loading' && <p role="status">Đang tải lịch sử…</p>}
      {history === 'error' && <div role="alert">Không tải được lịch sử. <Button variant="outline" onClick={() => { setHistory('loading'); setHistoryAttempt(n => n + 1); }}>Thử lại lịch sử</Button></div>}
      {history === 'ready' && messages.length === 0 && <p className="metadata">Hỏi về học liệu đang đọc. Hãy mở nguồn để kiểm tra câu trả lời.</p>}
      {messages.map(message => <article key={message.id} className={`tutor-message ${message.role === 'user' ? 'tutor-question' : ''}`}>
        <p className="metadata">{message.role === 'user' ? 'Bạn' : 'Trợ giảng'}</p>
        {message.status === 'source_withdrawn' ? <p className="tutor-neutral">{message.notice ?? 'Nguồn này đã bị thu hồi hoặc thay thế.'}</p> : <>
          <div className={message.status === 'insufficient_evidence' ? 'tutor-neutral' : undefined}><AnswerText text={message.content ?? message.notice ?? ''} citations={message.citations} open={open} /></div>
          {message.role === 'assistant' && ['ok', 'insufficient_evidence'].includes(message.status) && message.model && <p className="tutor-model">Mô hình: {message.model}</p>}
          {message.limitation && <p className="metadata">{message.limitation}</p>}
          {message.citations.length > 0 && <ol className="tutor-sources" aria-label="Nguồn trích dẫn">{message.citations.map(citation => <li key={citation.id}><CitationButton citation={citation} open={open} /> <span>{citation.material_title} · tr. {citation.page_label ?? citation.page_index + 1}</span><p>{citation.excerpt}</p></li>)}</ol>}
        </>}
      </article>)}
    </div>
    <div className="tutor-status" aria-live="polite">{pending ? <>Trợ giảng đang đọc học liệu…{seconds >= 3 && ` Đã chờ ${seconds} giây.`}</> : notice}</div>
    {pending && <Button variant="outline" onClick={() => { request.current?.abort(); request.current = null; setPending(false); setNotice('Đã hủy chờ kết quả.'); }}>Hủy chờ</Button>}
    {failure && <div role="alert" className="tutor-error"><p>{failure.text}</p><Button variant="outline" disabled={pending} onClick={() => void send(failure.request, true)}>Thử lại</Button></div>}
    <form onSubmit={e => { e.preventDefault(); void send({ question, mode, page_index: pageIndex }); }}>
      <Label htmlFor={`${id}-question`}>Câu hỏi cho trợ giảng</Label>
      <textarea id={`${id}-question`} rows={3} value={question} aria-describedby={`${id}-hint ${id}-count`} aria-invalid={length > 2000} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send({ question, mode, page_index: pageIndex }); } }} />
      <p id={`${id}-count`} className={length > 2000 ? 'form-error' : 'metadata'}>{length}/2000 ký tự</p>
      <p id={`${id}-hint`} className="metadata">Mỗi câu hỏi được trả lời độc lập — hãy hỏi đầy đủ ý.</p>
      <div className="tutor-submit"><span className="metadata">Ctrl+Enter để gửi</span><Button type="submit" disabled={pending || history !== 'ready' || !question.trim() || length > 2000}>Hỏi</Button></div>
    </form>
  </section>;
}
