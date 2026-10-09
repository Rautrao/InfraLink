const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:4000/api/v1';
export class ApiError extends Error { constructor(public status: number, message: string, public code?: string, public details?: unknown) { super(message); } }
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  const headers = new Headers(init.headers);
  if (init.body && !(typeof FormData !== 'undefined' && init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${API_BASE}${path.startsWith('/') ? path : `/${path}`}`, { ...init, headers });
  const data = await response.json().catch(() => null);
  if (!response.ok) { const error = data?.error; throw new ApiError(response.status, error?.message ?? response.statusText, error?.code, error?.details); }
  return data as T;
}
