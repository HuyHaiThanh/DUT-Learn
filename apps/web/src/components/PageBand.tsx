import type { ReactNode } from 'react';

export function PageBand({ eyebrow, title, meta, actions, aside, children }: { eyebrow?: ReactNode; title: string; meta?: ReactNode; actions?: ReactNode; aside?: ReactNode; children?: ReactNode }) {
  return <header className="page-band"><div className="band-inner">
    <div className={`band-heading${aside ? ' has-aside' : ''}`}><div>{eyebrow && <div className="band-eyebrow">{eyebrow}</div>}<h1>{title}</h1>{meta && <p className="band-meta">{meta}</p>}{actions && <div className="band-actions">{actions}</div>}</div>{aside}</div>
    {children}
  </div></header>;
}
