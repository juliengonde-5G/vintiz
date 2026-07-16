const TOKEN_KEY = "vintiz_account_token";

/** Fetch a private customer-space resource with the magic-link JWT. */
export function accountFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem(TOKEN_KEY);
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}

/** Download a protected binary resource without putting the JWT in the URL. */
export async function downloadAccountFile(
  url: string,
  filename: string,
): Promise<void> {
  const response = await accountFetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Download failed (${response.status})`);

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

/** Resolve a protected Google Wallet URL, then navigate without exposing JWT. */
export async function openAccountWalletUrl(url: string): Promise<void> {
  const response = await accountFetch(url, {
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Wallet redirect failed (${response.status})`);
  const payload = (await response.json()) as { save_url?: string };
  if (!payload.save_url) throw new Error("Google Wallet URL missing");
  window.location.assign(payload.save_url);
}
