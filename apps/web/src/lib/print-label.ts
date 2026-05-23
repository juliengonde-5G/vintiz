/**
 * Single source of truth for "imprimer une étiquette produit".
 *
 * The API runs off-site and can't reach a printer on the boutique LAN, so a
 * print action no longer talks to a printer — it enqueues a job. The in-store
 * Raspberry Pi agent polls the queue and prints on its CUPS printer. These
 * helpers therefore POST to the enqueue endpoints and report "queued", not
 * "printed".
 */

import { api } from '@/lib/api';

export interface PrintLabelResult {
  ok: boolean;
  message: string;
}

/** Queue one product label for the Raspberry Pi agent to print. */
export async function printProductLabel(productId: string, copies = 1): Promise<PrintLabelResult> {
  try {
    const res = await api.post(
      `/api/labels/print/${productId}${copies > 1 ? `?copies=${copies}` : ''}`,
      {},
    );
    if (res.ok) return { ok: true, message: 'Étiquette ajoutée à la file (Raspberry Pi)' };
    const body = await res.json().catch(() => ({} as Record<string, unknown>));
    return { ok: false, message: (body.detail as string) || "Échec de la mise en file" };
  } catch {
    return { ok: false, message: 'Serveur Vintiz injoignable' };
  }
}

/** Queue a test label (used by /settings). */
export async function printTestLabel(): Promise<PrintLabelResult> {
  try {
    const res = await api.post('/api/hardware/label/test', {});
    if (res.ok) return { ok: true, message: 'Étiquette de test ajoutée à la file' };
    const body = await res.json().catch(() => ({} as Record<string, unknown>));
    return { ok: false, message: (body.detail as string) || 'Échec du test' };
  } catch {
    return { ok: false, message: 'Serveur Vintiz injoignable' };
  }
}
