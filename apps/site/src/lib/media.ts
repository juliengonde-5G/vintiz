/**
 * Resolve a stored media path to a browser-loadable URL.
 *
 * Uploaded product photos are persisted by the API and served from the API
 * origin at ``/uploads/...``. The public site runs on a different origin, so a
 * raw ``<img src="/uploads/...">`` would 404 against the site origin. This
 * prefixes the API base for those paths only and leaves Next public assets and
 * absolute / data / blob URLs untouched.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function mediaUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (url.startsWith("/uploads/")) return `${API_BASE}${url}`;
  return url;
}
