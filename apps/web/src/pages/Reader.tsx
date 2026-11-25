import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ApiError } from '@/api/client';
import { homePath, isUnauthorized, useMe } from '@/features/auth';
import { LoginRedirect } from '@/components/feedback';
import { Icon } from '@/components/icons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { TutorPanel } from '@/features/tutor/TutorPanel';
import { readerContext } from '@/features/tutor/api';
import { useReadingPosition } from '@/features/tutor/ReadingProgress';
import { sendEvent } from '@/features/events';
import { reflowPageText } from '@/features/tutor/pageText';
import './reader.css';

type PageText = { page_index: number; page_label: string; text: string; chunks: { id: string; ordinal: number; kind: string; char_start: number; char_end: number }[] };
type ReaderPage = PageText & { count: number; kind: string };

async function loadPage(versionId: string, page: number, signal: AbortSignal): Promise<ReaderPage> {
  const response = await fetch(`/api/material-versions/${versionId}/pages/${page - 1}/text`, { credentials: 'include', cache: 'no-store', signal });
  if (!response.ok) throw new ApiError(response.status, 'read_failed', 'Không thể tải trang tài liệu.');
  return { ...await response.json() as PageText, count: Number(response.headers.get('X-Page-Count')), kind: response.headers.get('X-Material-Kind') ?? 'text' };
}

export function HighlightedText({ text, highlight }: { text: string; highlight: string | null }) {
  const match = /^(\d+)-(\d+)$/.exec(highlight ?? '');
  const chars = Array.from(text); // Python offsets count Unicode code points, not UTF-16 units.
  const start = match ? Number(match[1]) : -1;
  const end = match ? Number(match[2]) : -1;
  if (start < 0 || end <= start || end > chars.length) return <>{text}</>;
  return <>{chars.slice(0, start).join('')}<mark>{chars.slice(start, end).join('')}</mark>{chars.slice(end).join('')}</>;
}

function PdfPage({ versionId, page, zoom, onError }: { versionId: string; page: number; zoom: number; onError: (error: Error) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver(entries => setWidth(Math.max(100, entries[0].contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const [document, setDocument] = useState<{ versionId: string; pdf: import('pdfjs-dist').PDFDocumentProxy } | null>(null);
  const errorHandler = useRef(onError);
  errorHandler.current = onError;
  useEffect(() => {
    const controller = new AbortController();
    let disposed = false;
    let task: import('pdfjs-dist').PDFDocumentLoadingTask | undefined;
    async function load() {
      setLoading(true);
      try {
        const pdfjs = await import('pdfjs-dist');
        const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
        if (disposed) return;
        pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
        const response = await fetch(`/api/material-versions/${versionId}/file`, { credentials: 'include', cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new ApiError(response.status, 'read_failed', 'Không thể tải PDF.');
        const bytes = new Uint8Array(await response.arrayBuffer());
        if (disposed) return;
        task = pdfjs.getDocument({ data: bytes });
        const pdf = await task.promise;
        if (!disposed) setDocument({ versionId, pdf });
      } catch (error) { if (!disposed) errorHandler.current(error instanceof Error ? error : new Error('Không thể hiển thị PDF.')); }
    }
    void load();
    return () => {
      disposed = true; controller.abort();
      // pdf.js 6 releases the document and worker through its loading task.
      void task?.destroy();
    };
  }, [versionId]);
  useEffect(() => {
    if (!document || document.versionId !== versionId) return;
    let disposed = false;
    let render: import('pdfjs-dist').RenderTask | undefined;
    async function draw() {
      setLoading(true);
      try {
        const pdfPage = await document!.pdf.getPage(page);
        if (disposed || !canvas.current) return;
        const base = pdfPage.getViewport({ scale: 1 });
        const viewport = pdfPage.getViewport({ scale: width / base.width * zoom });
        const pixelRatio = window.devicePixelRatio || 1;
        canvas.current.width = viewport.width * pixelRatio;
        canvas.current.height = viewport.height * pixelRatio;
        canvas.current.style.width = `${viewport.width}px`;
        canvas.current.style.height = `${viewport.height}px`;
        render = pdfPage.render({ canvas: canvas.current, viewport, transform: pixelRatio === 1 ? undefined : [pixelRatio, 0, 0, pixelRatio, 0, 0] });
        await render.promise;
        if (!disposed) setLoading(false);
      } catch (error) { if (!disposed) errorHandler.current(error instanceof Error ? error : new Error('Không thể hiển thị PDF.')); }
    }
    void draw();
    return () => { disposed = true; render?.cancel(); };
  }, [document, versionId, page, zoom, width]);
  return <div ref={container} className="pdf-viewport" aria-busy={loading}>{loading && <p className="loading-state" role="status"><span className="spinner" aria-hidden="true" />Đang vẽ trang PDF…</p>}<canvas ref={canvas} aria-label={`Trang PDF ${page}`} role="img" /></div>;
}

/** Keep reading and conversation in independent, keyboard accessible panes. */
export function ReaderLayout({ children, assistant, tab, setTab }: { children: ReactNode; assistant?: ReactNode; tab: 'document' | 'assistant'; setTab: (tab: 'document' | 'assistant') => void }) {
  function select(next: 'document' | 'assistant') { setTab(next); document.getElementById(`reader-tab-${next}`)?.focus(); }
  return <div className={`reader-layout${assistant ? ' has-assistant' : ''}`}>
    {assistant && <div className="reader-mobile-tabs" role="tablist" aria-label="Chế độ xem" onKeyDown={e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); e.stopPropagation(); select(tab === 'document' ? 'assistant' : 'document'); } }}>
      {(['document', 'assistant'] as const).map(value => <button key={value} id={`reader-tab-${value}`} role="tab" aria-controls={`reader-pane-${value}`} tabIndex={tab === value ? 0 : -1} aria-selected={tab === value} onClick={() => setTab(value)}>{value === 'document' ? 'Tài liệu' : 'Trợ giảng'}</button>)}
    </div>}
    <div id="reader-pane-document" role={assistant ? 'tabpanel' : undefined} aria-labelledby={assistant ? 'reader-tab-document' : undefined} className="reader-document" data-mobile-hidden={tab !== 'document'}>{children}</div>
    {assistant && <aside id="reader-pane-assistant" role="tabpanel" aria-labelledby="reader-tab-assistant" className="reader-assistant" data-mobile-hidden={tab !== 'assistant'}>{assistant}</aside>}
  </div>;
}

type SourceState = { ordinal?: number; returnTo: string; returnMode: 'pdf' | 'text' };

export function Reader() {
  const { data: me } = useMe();
  const { versionId = '' } = useParams();
  const location = useLocation();
  const routeNavigate = useNavigate();
  const [tab, setTab] = useState<'document' | 'assistant'>('document');
  const [narrow, setNarrow] = useState(() => window.innerWidth <= 760);
  useEffect(() => {
    const resize = () => setNarrow(window.innerWidth <= 760);
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);
  const [mode, setMode] = useState<'pdf' | 'text'>(() => location.search.includes('hl=') || window.innerWidth <= 760 ? 'text' : 'pdf');
  const source = (location.state as { source?: SourceState } | null)?.source;
  const sourceBar = useRef<HTMLDivElement>(null);
  const textPanel = useRef<HTMLElement>(null);
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get('page') ?? 1);
  const page = Number.isSafeInteger(requested) && requested > 0 ? requested : 1;
  const [zoom, setZoom] = useState(1);
  const [pdfError, setPdfError] = useState<Error | null>(null);
  const query = useQuery({ queryKey: ['reader', versionId, page], queryFn: ({ signal }) => loadPage(versionId, page, signal), retry: false, gcTime: 0, staleTime: 0 });
  const error = query.error ?? (mode === 'pdf' ? pdfError : null);
  const context = useQuery({ queryKey: ['reader-context', versionId], queryFn: ({ signal }) => readerContext(versionId, signal), retry: false, gcTime: 0 });
  const backTo = context.data ? `/lop/${context.data.class_id}` : me ? homePath(me) : '/';
  const openedMaterials = useRef(new Set<string>());
  useEffect(() => {
    if (!context.data?.class_id || !context.data.material_id || openedMaterials.current.has(context.data.material_id)) return;
    openedMaterials.current.add(context.data.material_id);
    void sendEvent(context.data.class_id, 'material_opened', context.data.material_id);
  }, [context.data]);
  const positionError = useReadingPosition(context.data, versionId, page - 1, !!query.data && !error && !query.isFetching);
  // Keep PDF mounted and retain navigation while the next page text loads.
  const [knownPage, setKnownPage] = useState({ versionId: '', count: 0, kind: '' });
  const knownCount = knownPage.versionId === versionId ? knownPage.count : 0;
  useEffect(() => { if (query.data) setKnownPage({ versionId, count: query.data.count, kind: query.data.kind }); }, [query.data, versionId]);
  const count = query.data?.count ?? knownCount;
  function navigate(next: number) {
    if (next < 1 || next > count || next === page) return;
    const search = new URLSearchParams(params);
    search.set('page', String(next)); search.delete('hl');
    setPdfError(null); setParams(search);
  }
  useEffect(() => {
    function keydown(e: KeyboardEvent) {
      const target = e.target;
      if ((target instanceof Element && target.closest('input, textarea, select, [role=tablist], [contenteditable="true"]')) || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || error) return;
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const next = page + (e.key === 'ArrowLeft' ? -1 : 1);
        if (next < 1 || next > count) return;
        e.preventDefault();
        const search = new URLSearchParams(params); search.set('page', String(next)); search.delete('hl'); setParams(search);
      }
    }
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  }, [count, page, params, setParams, error]);
  const highlight = params.get('hl');
  useEffect(() => {
    if (highlight) { setMode('text'); setTab('document'); }
    else {
      const restored = (location.state as { readerMode?: 'pdf' | 'text' } | null)?.readerMode;
      if (restored) setMode(restored);
    }
  }, [location.key, location.state, highlight]);
  useEffect(() => {
    if (!highlight || !query.data || mode !== 'text') return;
    const frame = requestAnimationFrame(() => {
      sourceBar.current?.focus({ preventScroll: true });
      textPanel.current?.querySelector('mark')?.scrollIntoView?.({ block: 'center', behavior: 'auto' });
    });
    return () => cancelAnimationFrame(frame);
  }, [highlight, query.data, mode, location.key]);
  function closeSource() { const search = new URLSearchParams(params); search.delete('hl'); setParams(search, { state: null }); }
  function returnToReading() {
    if (source) routeNavigate(source.returnTo, { state: { readerMode: source.returnMode } });
    else closeSource();
  }
  if (isUnauthorized(error) || isUnauthorized(context.error) || isUnauthorized(positionError)) return <LoginRedirect />;
  if (error) return <div className="state-panel"><p role="alert">{error instanceof ApiError && [403, 404, 410].includes(error.status) ? 'Tài liệu không tồn tại hoặc đã bị thu hồi.' : 'Không thể tải tài liệu. Vui lòng thử lại.'}</p><Button onClick={() => { setPdfError(null); void query.refetch(); }}>Thử lại</Button><Link to={backTo}>Về lớp</Link></div>;
  if (query.isPending && knownCount === 0) return <p className="state-panel loading-state" role="status"><span className="spinner" aria-hidden="true" />Đang tải tài liệu…</p>;
  const data = query.data;
  const isPdf = (data?.kind ?? (knownPage.versionId === versionId ? knownPage.kind : null)) === 'pdf';
  const viewMode = isPdf ? mode : 'text';
  return <div className="reader-page">
    <header className="reader-topbar">
      <Link className="reader-back" to={backTo} aria-label="Về lớp">D</Link>
      <div className="reader-title"><p>{context.data?.course_name}</p><h1>{context.data?.material_title || 'Trình đọc học liệu'}</h1></div>
      <div className="reader-toolbar" aria-label="Điều khiển tài liệu">
        <div className="reader-view-modes" role="group" aria-label="Định dạng tài liệu"><button disabled={!isPdf} aria-pressed={viewMode === 'pdf'} onClick={() => setMode('pdf')}>PDF</button><button aria-pressed={viewMode === 'text'} onClick={() => setMode('text')}>Văn bản</button></div>
        <div className="reader-pagination"><button aria-label="Trang trước" disabled={page <= 1} onClick={() => navigate(page - 1)}>‹</button>
          <form key={`${versionId}-${page}`} onSubmit={e => { e.preventDefault(); const value = Number(new FormData(e.currentTarget).get('page')); if (Number.isInteger(value)) navigate(value); }}><label className="sr-only" htmlFor="reader-page-number">Trang</label><Input id="reader-page-number" name="page" type="number" min={1} max={count} defaultValue={page} required /><span>/ {count}</span></form>
          <button aria-label="Trang sau" disabled={page >= count} onClick={() => navigate(page + 1)}>›</button>
        </div>
        {viewMode === 'pdf' && !narrow && <div className="reader-zoom"><button aria-label="Thu nhỏ" disabled={zoom <= 0.5} onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}>−</button><output aria-label="Mức phóng to">{Math.round(zoom * 100)}%</output><button aria-label="Phóng to" disabled={zoom >= 2} onClick={() => setZoom(z => Math.min(2, z + 0.25))}>+</button></div>}
      </div>
    </header>
    {data && context.isError && <p role="alert" className="reader-notice">Không tải được ngữ cảnh trợ giảng. <Button variant="outline" onClick={() => void context.refetch()}>Thử lại trợ giảng</Button></p>}
    {positionError != null && !isUnauthorized(positionError) && <p role="status" className="reader-notice">Chưa lưu được vị trí đọc gần nhất.</p>}
    <ReaderLayout tab={tab} setTab={setTab} assistant={context.data && (data || knownCount > 0) ? <TutorPanel key={context.data.material_id} context={context.data} pageIndex={page - 1} readingMode={viewMode} /> : undefined}>
      {highlight && <div ref={sourceBar} tabIndex={-1} className="reader-source-bar" role="region" aria-label="Đang xem nguồn"><strong><Icon name="book" />Đang xem nguồn{source?.ordinal ? ` ${source.ordinal}` : ''} · trang {page}</strong><div><button onClick={returnToReading}><Icon name="history" />Về chỗ đang đọc</button><button className="source-answer-back" onClick={() => { setTab('assistant'); requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('.tutor-panel textarea')?.focus({ preventScroll: true })); }}>Về câu trả lời</button><button aria-label="Đóng nguồn" onClick={closeSource}><Icon name="close" /></button></div></div>}
      {viewMode === 'pdf' && <PdfPage key={versionId} versionId={versionId} page={page} zoom={zoom} onError={setPdfError} />}
      {viewMode === 'text' && (!data ? <p className="state-panel loading-state" role="status"><span className="spinner" aria-hidden="true" />Đang tải tài liệu…</p> : <section ref={textPanel} key={`${location.key}-${highlight}`} className={`reader-text-panel${highlight ? ' source-open' : ''}`} aria-label="Văn bản trang"><p className="metadata">Trang {data.page_label}</p><div className="reader-text"><HighlightedText text={reflowPageText(data.text)} highlight={highlight} /></div></section>)}
    </ReaderLayout>
  </div>;
}
