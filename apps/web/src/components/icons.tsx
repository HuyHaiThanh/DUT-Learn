export function Chevron({ down = false }: { down?: boolean }) {
  return <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={down ? 'M6 9l6 6 6-6' : 'M9 6l6 6-6 6'} /></svg>;
}
