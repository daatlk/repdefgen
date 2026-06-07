// Typed API wrappers for the RepDefGen FastAPI backend

export interface BlockSummary {
  name: string;
  field_count: number;
  aggregate_name: string | null;
  parent_name: string | null;
}

export interface SessionCreatedResponse {
  session_id: string;
  report_name: string;
  report_title: string;
  blocks: BlockSummary[];
}

export interface MessageResponse {
  message: string;
}

export interface FilesResponse {
  files: Record<string, string>; // filename -> content
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function createSession(rdlFile: File): Promise<SessionCreatedResponse> {
  const form = new FormData();
  form.append('rdl_file', rdlFile);
  return request<SessionCreatedResponse>('/api/sessions', { method: 'POST', body: form });
}

export async function proposeFieldList(
  sessionId: string,
  luName: string,
  module: string,
  description: string,
): Promise<MessageResponse> {
  return request<MessageResponse>(`/api/sessions/${sessionId}/field-list`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lu_name: luName, module, description }),
  });
}

export async function correctFieldList(
  sessionId: string,
  text: string,
): Promise<MessageResponse> {
  return request<MessageResponse>(`/api/sessions/${sessionId}/field-list/correct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
}

export async function generateFiles(sessionId: string): Promise<FilesResponse> {
  return request<FilesResponse>(`/api/sessions/${sessionId}/generate`, { method: 'POST' });
}

export async function applyCorrection(
  sessionId: string,
  text: string,
): Promise<FilesResponse> {
  return request<FilesResponse>(`/api/sessions/${sessionId}/correct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
}

export function downloadUrl(sessionId: string, filename: string): string {
  return `/api/sessions/${sessionId}/download/${encodeURIComponent(filename)}`;
}
