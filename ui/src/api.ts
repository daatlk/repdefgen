// Typed API wrappers for the RepDefGen FastAPI backend

const TOKEN_KEY = 'repdefgen_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export async function login(password: string): Promise<void> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? 'Invalid password');
  }
  const data = await res.json() as { token: string };
  setToken(data.token);
}

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

export interface FieldDef {
  name: string;
  data_type: string;
  hidden: boolean;
  source?: string | null;
  note?: string | null;
}

export interface BlockDef {
  name: string;
  parent: string | null;
  aggregate: string | null;
  fields: FieldDef[];
}

export interface ParameterDef {
  name: string;
  data_type: string;
}

export interface FieldListData {
  blocks: BlockDef[];
  parameters: ParameterDef[];
}

export interface FieldListResponse {
  message: string;
  field_list: FieldListData;
}

export interface FilesResponse {
  files: Record<string, string>; // filename -> content
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const existingHeaders = init?.headers instanceof Headers
    ? Object.fromEntries(init.headers.entries())
    : (init?.headers as Record<string, string> | undefined) ?? {};
  const headers: Record<string, string> = { ...existingHeaders };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    window.location.reload();
    throw new Error('Session expired — please log in again');
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = (body as { detail?: string }).detail ?? detail;
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
): Promise<FieldListResponse> {
  return request<FieldListResponse>(`/api/sessions/${sessionId}/field-list`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lu_name: luName, module, description }),
  });
}

export async function correctFieldList(
  sessionId: string,
  text: string,
  fieldList: FieldListData,
): Promise<FieldListResponse> {
  return request<FieldListResponse>(`/api/sessions/${sessionId}/field-list/correct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, field_list: fieldList }),
  });
}

export async function generateFiles(
  sessionId: string,
  fieldList: FieldListData,
): Promise<FilesResponse> {
  return request<FilesResponse>(`/api/sessions/${sessionId}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ field_list: fieldList }),
  });
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
