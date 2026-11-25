/** Reflow extracted prose without moving any server-provided character offset. */
export function reflowPageText(text: string): string {
  const lines = text.split('\n');
  const looksLikeCode = (line: string) => /[;{}#]/.test(line) || /[:;{}]\s*$/.test(line);
  return lines.map((line, index) => {
    if (index === lines.length - 1) return line;
    const next = lines[index + 1];
    const keepBreak = !line.trim() || !next.trim() || /^(?:\s|[-•*]|\d+[.)])/.test(next) || looksLikeCode(line) || looksLikeCode(next);
    return line + (keepBreak ? '\n' : ' ');
  }).join('');
}
