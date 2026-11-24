import { apiFetch } from '@/api/client';

export async function sendEvent(classId: string, type: 'material_opened' | 'citation_opened' | 'feedback_viewed', refId: string): Promise<void> {
  try { await apiFetch<void>('/events', { method: 'POST', body: JSON.stringify({ class_id: classId, type, ref_id: refId }) }); }
  catch { /* Event collection must never interrupt learning. */ }
}
