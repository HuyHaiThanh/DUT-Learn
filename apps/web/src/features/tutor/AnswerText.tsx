import type { ReactNode } from 'react';
import type { Citation } from './api';

export function CitationButton({ citation, open }: { citation: Citation; open: (citation: Citation) => void }) {
  return <button type="button" className="tutor-citation" aria-label={`Mở nguồn ${citation.ordinal}: ${citation.material_title}, trang ${citation.page_label ?? citation.page_index + 1}`} onClick={() => open(citation)}>[{citation.ordinal}]</button>;
}

/** Only parse citation markers outside fenced and inline code; React escapes all text. */
export function AnswerText({ text, citations, open }: { text: string; citations: Citation[]; open: (citation: Citation) => void }) {
  function inline(value: string): ReactNode[] {
    return value.split(/(`[^`\n]*`)/g).map((part, i) => {
      if (part.startsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
      const nodes: ReactNode[] = [];
      let cursor = 0;
      let lastCitationEnd = -1;
      for (const match of part.matchAll(/\[(\d+)\]/g)) {
        const start = match.index;
        const citation = citations.find(c => c.ordinal === Number(match[1]));
        const arraySyntax = /[A-Za-z_\])]/.test(part[start - 1] ?? '') && lastCitationEnd !== start;
        nodes.push(part.slice(cursor, start));
        if (citation && !arraySyntax) {
          nodes.push(<CitationButton key={start} citation={citation} open={open} />);
          lastCitationEnd = start + match[0].length;
        } else nodes.push(match[0]);
        cursor = start + match[0].length;
      }
      nodes.push(part.slice(cursor));
      return <span key={i}>{nodes}</span>;
    });
  }
  const blocks: ReactNode[] = [];
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*```/.test(line)) {
      const start = i;
      const code: string[] = [];
      while (++i < lines.length && !/^\s*```\s*$/.test(lines[i])) code.push(lines[i]);
      blocks.push(<pre key={start}><code>{code.join('\n')}</code></pre>);
    } else if (/^\s*(?:[-*]|\d+\.)\s+/.test(line)) {
      blocks.push(<ul key={i}><li>{inline(line.replace(/^\s*(?:[-*]|\d+\.)\s+/, ''))}</li></ul>);
    } else blocks.push(<div className="tutor-line" key={i}>{inline(line)}</div>);
  }
  return <div className="tutor-answer">{blocks}</div>;
}
