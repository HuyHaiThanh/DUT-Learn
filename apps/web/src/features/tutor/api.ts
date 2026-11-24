import { apiFetch } from '@/api/client';
import type { ClassSummary } from '@/api/types';

export interface Citation {
  id: string; ordinal: number; material_id: string; material_title: string;
  version_id: string; page_index: number; page_label: string | null; excerpt: string;
}
export interface Message {
  id: string; role: string; content: string | null; status: string;
  model?: string | null; citations: Citation[]; notice?: string | null; limitation?: string | null;
}
export interface Answer {
  session_id: string; message_id: string; status: string; answer: string;
  model: string; citations: Citation[]; limitation: string | null;
}
export interface Context { class_id: string; material_id: string }
export interface Position extends Context {
  version_id: string; page_index: number; page_label: string; material_title: string;
  course_name: string; updated_at: string;
}

/** Page text has no material metadata; resolve it through the existing authorized lists. */
export async function readerContext(versionId: string, signal: AbortSignal): Promise<Context | null> {
  const classes = await apiFetch<ClassSummary[]>('/classes', { signal, cache: 'no-store' });
  const lists = await Promise.all(classes.map(async classroom => {
    const materials = await apiFetch<{ id: string; active_version_id: string | null; versions?: { id: string }[] }[]>(`/classes/${classroom.id}/materials`, { signal, cache: 'no-store' });
    const material = materials.find(m => m.active_version_id === versionId || m.versions?.some(v => v.id === versionId));
    return material ? { class_id: classroom.id, material_id: material.id } : null;
  }));
  return lists.find(Boolean) ?? null;
}
