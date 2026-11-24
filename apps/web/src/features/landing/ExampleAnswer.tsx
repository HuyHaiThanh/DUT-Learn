import { useLayoutEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { example, type ExampleSource } from './example';

export function ExampleAnswer() {
  const [tab, setTab] = useState(0);
  const [source, setSource] = useState<ExampleSource | null>(null);
  const panel = useRef<HTMLElement>(null);
  const origin = useRef<HTMLButtonElement | null>(null);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  useLayoutEffect(() => { if (source) panel.current?.focus(); }, [source]);
  function open(value: ExampleSource, trigger: HTMLButtonElement) {
    origin.current = trigger;
    setSource(value);
    panel.current?.focus();
  }
  return <section className="landing-example" aria-labelledby="landing-example-title">
    <h2 id="landing-example-title" tabIndex={-1}>Thử kiểm chứng một câu trả lời</h2>
    <p className="landing-note">Ví dụ dựng sẵn: câu hỏi và câu trả lời được ghi lại nguyên văn từ hệ thống ngày 22/11/2026 (mô hình Qwen2.5-7B-Instruct chạy cục bộ), trên giáo trình của học phần thí điểm. Trang này không gọi trợ giảng.</p>
    <div className="landing-tabs" role="tablist" aria-label="Ví dụ câu hỏi">{['Câu hỏi trong giáo trình', 'Câu hỏi ngoài giáo trình'].map((label, index) => <button key={label} ref={node => { tabs.current[index] = node; }} type="button" role="tab" id={`landing-tab-${index}`} aria-controls={`landing-panel-${index}`} aria-selected={tab === index} tabIndex={tab === index ? 0 : -1} onClick={() => setTab(index)} onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
      event.preventDefault(); const next = 1 - index; setTab(next); tabs.current[next]?.focus();
    }}>{label}</button>)}</div>
    <div role="tabpanel" id="landing-panel-0" aria-labelledby="landing-tab-0" hidden={tab !== 0}>
      <div className="landing-example-grid"><div>
        <p className="landing-question">{example.question}</p>
        <div className="landing-answer">{example.answer.split(/(\[1\]|\[2\])/).map((part, index) => {
          const citation = /^\[(\d)\]$/.exec(part);
          if (!citation) return part;
          const value = example.sources[Number(citation[1]) - 1];
          return <button key={index} type="button" className="landing-citation" data-active={source?.id === value.id} aria-label={`Nguồn ${value.id}, trang ${value.page}`} aria-describedby={source?.id === value.id ? 'landing-source-open' : undefined} onClick={event => open(value, event.currentTarget)}>{value.id} · tr.{value.page}</button>;
        })}</div>
        <ol className="landing-sources">{example.sources.map(value => <li key={value.id}><span>{example.material} · tr. {value.page}</span> <Button variant="outline" onClick={event => open(value, event.currentTarget)}>Mở đoạn này</Button></li>)}</ol>
      </div><section ref={panel} tabIndex={-1} className="landing-source" aria-labelledby="landing-source-title">
        <h3 id="landing-source-title">Nguồn</h3>
        {source ? <><span id="landing-source-open" className="sr-only">đang mở</span><h4>{example.material} · tr. {source.page}</h4><p className="landing-source-text">{source.text.slice(0, source.text.indexOf(source.highlight))}<mark>{source.highlight}</mark>{source.text.slice(source.text.indexOf(source.highlight) + source.highlight.length)}</p><Button variant="outline" onClick={() => origin.current?.focus()}>Về câu trả lời</Button></> : <p>Bấm vào số trích dẫn để mở đúng đoạn trong giáo trình.</p>}
      </section></div>
    </div>
    <div role="tabpanel" id="landing-panel-1" aria-labelledby="landing-tab-1" hidden={tab !== 1}>
      <p className="landing-question">{example.refusalQuestion}</p>
      <div className="landing-warning"><h3><svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3 2 21h20L12 3Z" /><path d="M12 9v5m0 3v1" /></svg>Không đủ căn cứ trong học liệu</h3><p>{example.refusal}</p></div>
      <p className="landing-note">Giáo trình thí điểm là giáo trình C; câu hỏi về Java không có căn cứ nên trợ giảng không trả lời.</p>
    </div>
  </section>;
}
