/** Thin REST client for the backend (relative URLs go through the Vite proxy). */



async function request<T>(method: string, path: string, body?: unknown): Promise<T> {

  const res = await fetch(`/api${path}`, {

    method,

    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,

    body: body !== undefined ? JSON.stringify(body) : undefined,

  });

  if (!res.ok) {

    let detail = res.statusText;

    try {

      detail = (await res.json()).detail ?? detail;

    } catch {

      /* ignore */

    }

    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));

  }

  return res.json() as Promise<T>;

}



export const api = {

  get: <T = any>(path: string) => request<T>('GET', path),

  post: <T = any>(path: string, body: unknown = {}) => request<T>('POST', path, body),

};



export function qs(params: Record<string, string | number | undefined | null>) {

  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '');

  return entries.length ? '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString() : '';

}



export const fmtTime = (t: number | null | undefined) => {

  if (t === null || t === undefined) return '—';

  const m = Math.floor(t / 60);

  const s = t - m * 60;

  return `${String(m).padStart(2, '0')}:${s.toFixed(1).padStart(4, '0')}`;

};



export const shortHash = (h?: string | null, n = 10) => (h ? `${h.slice(0, n)}…` : '—');



export const pct = (v: number | null | undefined, digits = 1) =>

  v === null || v === undefined || Number.isNaN(v) ? '—' : `${(v * 100).toFixed(digits)}%`;
