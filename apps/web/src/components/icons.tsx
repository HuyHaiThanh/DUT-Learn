export function Chevron({ down = false }: { down?: boolean }) {
  return <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={down ? 'M6 9l6 6 6-6' : 'M9 6l6 6-6 6'} /></svg>;
}

const paths = {
  book: 'M4 3h15v18H4a2 2 0 0 1 0-4h15M4 3v14',
  clipboard: 'M9 4H6a2 2 0 0 0-2 2v14h16V6a2 2 0 0 0-2-2h-3M9 2h6v5H9zM8 12h8M8 16h5',
  check: 'm5 12 4 4L19 6',
  clock: 'M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  lock: 'M7 10V7a5 5 0 0 1 10 0v3M5 10h14v11H5z',
  alert: 'M12 3 2 21h20L12 3zM12 9v5M12 17h.01',
  shield: 'm12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6zM8 12l3 3 5-6',
  close: 'm6 6 12 12M6 18 18 6',
  info: 'M12 11v6M12 7h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  history: 'M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v6l4 2',
  message: 'M4 3h16v14H9l-5 4z',
  menu: 'M4 6h16M4 12h16M4 18h16',
} as const;
export type IconName = keyof typeof paths;
export function Icon({ name }: { name: IconName }) {
  return <svg className="icon" aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]} /></svg>;
}
