import type { ReactNode } from 'react';
import { Icon, type IconName } from './icons';

export function StatusPill({ children, tone = 'neutral', icon = 'info' }: { children: ReactNode; tone?: 'neutral' | 'ok' | 'warn' | 'bad' | 'sky' | 'ai'; icon?: IconName }) {
  return <span className={`status-pill pill-${tone}`}><Icon name={icon} />{children}</span>;
}
