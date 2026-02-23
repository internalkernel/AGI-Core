const BASE = window.location.origin;

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('openclaw_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders(), ...init?.headers },
  });
  if (res.status === 401) {
    localStorage.removeItem('openclaw_token');
    localStorage.removeItem('openclaw_user');
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw new Error('Not authenticated');
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'POST', body: JSON.stringify(body) });
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'PUT', body: JSON.stringify(body) });
}

export function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
}

export function apiDelete<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: 'DELETE' });
}

/**
 * Build an authenticated WebSocket URL with the JWT token as a query param.
 */
export function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = localStorage.getItem('openclaw_token') || '';
  const sep = path.includes('?') ? '&' : '?';
  return `${proto}//${window.location.host}${path}${sep}token=${encodeURIComponent(token)}`;
}
