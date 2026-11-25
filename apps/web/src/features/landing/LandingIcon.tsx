const paths = {
  book: 'M12 5C8 2 4 3 2 4v16c3-2 6-2 10 0 4-2 7-2 10 0V4c-2-1-6-2-10 1Zm0 0v15',
  source: 'M14 3H5v18h14V8Zm0 0v5h5M8 12h8M8 16h5',
  alert: 'M12 3 2 21h20L12 3Zm0 6v5m0 3v1',
  shield: 'M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6l-9-4ZM8 12l3 3 5-6',
  model: 'M4 5h16v12H4V5Zm4 16h8m-4-4v4M8 9h8m-8 4h5',
  history: 'M6 10V7a6 6 0 0 1 12 0v3M4 10h16v12H4V10Zm8 4v4',
};

export function LandingIcon({ name }: { name: keyof typeof paths }) {
  return <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name]} /></svg>;
}
