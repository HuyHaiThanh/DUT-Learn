import { useLayoutEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { example, type ExampleSource } from './example';

export function ExampleAnswer() {
  const [source, setSource] = useState<ExampleSource | null>(null);
  const panel = useRef<HTMLElement>(null);
  const origin = useRef<HTMLButtonElement | null>(null);
  useLayoutEffect(() => { if (source) panel.current?.focus(); }, [source]);
  function open(value: ExampleSource, trigger: HTMLButtonElement) {
    origin.current = trigger;
    setSource(value);
    panel.current?.focus();
  }
  return <article className="landing-example" aria-labelledby="landing-example-title">
    <h3 id="landing-example-title">Một câu trả lời từ giáo trình</h3>
    <p className="landing-question">{example.question}</p>
    <div className="landing-answer">{example.answer.split(/(\[1\]|\[2\])/).map((part, index) => {
      const citation = /^\[(\d)\]$/.exec(part);
      if (!citation) return part;
      const value = example.sources[Number(citation[1]) - 1];
      return <button key={index} type="button" className="landing-citation" data-active={source?.id === value.id} aria-label={`Nguồn ${value.id}, trang ${value.page}`} aria-controls="landing-source" aria-expanded={source?.id === value.id} aria-describedby={source?.id === value.id ? 'landing-source-open' : undefined} onClick={event => open(value, event.currentTarget)}>{value.id} · tr.{value.page}</button>;
    })}</div>
    <section id="landing-source" ref={panel} tabIndex={-1} className="landing-source" aria-labelledby="landing-source-title" hidden={!source}>
      <h4 id="landing-source-title">Nguồn</h4>
      {source && <>
        <span id="landing-source-open" className="sr-only">đang mở</span>
        <p className="landing-source-heading">{example.material} · tr. {source.page}</p>
        <p className="landing-source-text">{source.text.slice(0, source.text.indexOf(source.highlight))}<mark>{source.highlight}</mark>{source.text.slice(source.text.indexOf(source.highlight) + source.highlight.length)}</p>
        <Button variant="outline" onClick={() => { setSource(null); origin.current?.focus(); }}>Về câu trả lời</Button>
      </>}
    </section>
    <p className="landing-note landing-recording">Ví dụ dựng sẵn: câu hỏi và câu trả lời được ghi lại nguyên văn từ hệ thống ngày 22/11/2026 (mô hình {example.model} chạy cục bộ), trên giáo trình của học phần thí điểm. Trang này không gọi trợ giảng.</p>
  </article>;
}
