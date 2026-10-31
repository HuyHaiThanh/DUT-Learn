export interface Health { status: 'ok'; db: boolean; llm: boolean }

export async function getHealth(): Promise<Health> {
  const response = await fetch('/api/health', { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error('Không thể kết nối máy chủ. Vui lòng thử lại.');
  return response.json() as Promise<Health>;
}
