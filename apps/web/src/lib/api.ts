const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Default per-request timeout (ms). Long enough for AI endpoints, short
// enough to surface a clear error rather than spinning forever.
const DEFAULT_TIMEOUT_MS = 30_000;

function handleUnauthorized() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  // Avoid redirect loops if the login page itself returns 401
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
}

async function fetchAPI(endpoint: string, options?: RequestInit & { timeoutMs?: number }) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const controller = new AbortController();
  const timeoutMs = options?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      signal: options?.signal ?? controller.signal,
      headers: { ...headers, ...options?.headers },
    });

    if (res.status === 401) {
      handleUnauthorized();
    }

    return res;
  } catch (err) {
    // Convert AbortError → friendly error so callers can show a message
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error(`La requête a expiré après ${Math.round(timeoutMs / 1000)}s`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

async function uploadAPI(endpoint: string, formData: FormData) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const controller = new AbortController();
  // Uploads can be larger — give them more time
  const timer = setTimeout(() => controller.abort(), 60_000);

  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers,
      body: formData,
      signal: controller.signal,
    });

    if (res.status === 401) {
      handleUnauthorized();
    }

    return res;
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new Error('Le téléversement a expiré');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  get: (url: string) => fetchAPI(url),
  post: (url: string, data: unknown) =>
    fetchAPI(url, { method: 'POST', body: JSON.stringify(data) }),
  put: (url: string, data: unknown) =>
    fetchAPI(url, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (url: string) => fetchAPI(url, { method: 'DELETE' }),
  upload: (url: string, formData: FormData) => uploadAPI(url, formData),
};
