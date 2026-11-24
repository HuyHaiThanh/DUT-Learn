import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom';
import { ApiError } from '@/api/client';
import { homePath, isUnauthorized, useMe } from '@/features/auth';
import { LoginRedirect } from '@/components/feedback';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { TutorPanel } from '@/features/tutor/TutorPanel';
import { readerContext } from '@/features/tutor/api';
import { useReadingPosition } from '@/features/tutor/ReadingProgress';
import { sendEvent } from '@/features/events';

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
  return <div ref={container} className="pdf-viewport" aria-busy={loading}>{loading && <p role="status">Đang vẽ trang PDF…</p>}<canvas ref={canvas} aria-label={`Trang PDF ${page}`} role="img" /></div>;
}

/** T13 supplies the side panel and the mobile tab; no visible empty slot in T10. */
export function ReaderLayout({ children, assistant, citationLocation }: { children: ReactNode; assistant?: ReactNode; citationLocation?: string }) {
  const [tab, setTab] = useState<'document' | 'assistant'>('document');
  useEffect(() => { if (citationLocation) setTab('document'); }, [citationLocation]);
  return <div className={`reader-layout${assistant ? ' has-assistant' : ''}`}>
    {assistant && <div className="reader-mobile-tabs" role="tablist" aria-label="Chế độ xem"><button role="tab" aria-selected={tab === 'document'} onClick={() => setTab('document')}>Tài liệu</button><button role="tab" aria-selected={tab === 'assistant'} onClick={() => setTab('assistant')}>Trợ giảng</button></div>}
    <div className="reader-document" data-mobile-hidden={tab !== 'document'}>{children}</div>
    {assistant && <aside className="reader-assistant" data-mobile-hidden={tab !== 'assistant'}>{assistant}</aside>}
  </div>;
}

export function Reader() {
  const { data: me } = useMe();
  const { versionId = '' } = useParams();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const requested = Number(params.get('page') ?? 1);
  const page = Number.isSafeInteger(requested) && requested > 0 ? requested : 1;
  const [zoom, setZoom] = useState(1);
  const [pdfError, setPdfError] = useState<Error | null>(null);
  const query = useQuery({ queryKey: ['reader', versionId, page], queryFn: ({ signal }) => loadPage(versionId, page, signal), retry: false, gcTime: 0, staleTime: 0 });
  const error = query.error ?? pdfError;
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
      if ((target instanceof Element && target.closest('input, textarea, select, [contenteditable="true"]')) || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || error) return;
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
  if (isUnauthorized(error) || isUnauthorized(context.error) || isUnauthorized(positionError)) return <LoginRedirect />;
  if (error) return <div className="state-panel"><p role="alert">{error instanceof ApiError && [403, 404, 410].includes(error.status) ? 'Tài liệu không tồn tại hoặc đã bị thu hồi.' : 'Không thể tải tài liệu. Vui lòng thử lại.'}</p><Button onClick={() => { setPdfError(null); void query.refetch(); }}>Thử lại</Button><Link to={backTo}>Về lớp</Link></div>;
  if (query.isPending && knownCount === 0) return <p role="status">Đang tải tài liệu…</p>;
  const data = query.data;
  return <div className="reader-page"><Link to={backTo}>Về lớp</Link><h1>{context.data?.material_title || 'Trình đọc học liệu'}</h1>
    <div className="reader-toolbar" aria-label="Điều khiển tài liệu">
      <Button variant="outline" disabled={page <= 1} onClick={() => navigate(page - 1)}>Trang trước</Button>
      <form key={page} onSubmit={e => { e.preventDefault(); const value = Number(new FormData(e.currentTarget).get('page')); if (Number.isInteger(value)) navigate(value); }}><label htmlFor="reader-page-number">Trang</label><Input id="reader-page-number" name="page" type="number" min={1} max={count} defaultValue={page} required /><span>/ {count}</span><Button variant="outline" type="submit">Đến trang</Button></form>
      <Button variant="outline" disabled={page >= count} onClick={() => navigate(page + 1)}>Trang sau</Button>
      <div className="reader-zoom"><Button variant="outline" aria-label="Thu nhỏ" disabled={zoom <= 0.5} onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}>−</Button><output aria-label="Mức phóng to">{Math.round(zoom * 100)}%</output><Button variant="outline" aria-label="Phóng to" disabled={zoom >= 2} onClick={() => setZoom(z => Math.min(2, z + 0.25))}>+</Button></div>
    </div>
    {data && context.isError && <p role="alert">Không tải được ngữ cảnh trợ giảng. <Button variant="outline" onClick={() => void context.refetch()}>Thử lại trợ giảng</Button></p>}
    {positionError != null && !isUnauthorized(positionError) && <p role="status">Chưa lưu được vị trí đọc gần nhất.</p>}
    <ReaderLayout citationLocation={params.has('hl') ? location.key : undefined} assistant={context.data && (data || knownCount > 0) ? <TutorPanel key={context.data.material_id} context={context.data} pageIndex={page - 1} /> : undefined}>
      {(data?.kind ?? (knownPage.versionId === versionId ? knownPage.kind : null)) === 'pdf' && <PdfPage key={versionId} versionId={versionId} page={page} zoom={zoom} onError={setPdfError} />}
      {!data ? <p role="status">Đang tải tài liệu…</p> : <>
        <section className="reader-text-panel" aria-label={data.kind === 'pdf' ? 'Đoạn được trích' : 'Văn bản trang'}>{data.kind === 'pdf' && <h2>Đoạn được trích</h2>}<p className="metadata">Trang {data.page_label}</p><pre className="reader-text" style={{ fontSize: `${18 * (data.kind === 'pdf' ? 1 : zoom)}px` }}><HighlightedText text={data.text} highlight={params.get('hl')} /></pre></section>
      </>}
    </ReaderLayout>
  </div>;
}
