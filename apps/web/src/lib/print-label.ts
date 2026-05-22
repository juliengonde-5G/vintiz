/**
 * Single source of truth for "imprimer une étiquette produit sur la Zebra".
 *
 * Reads the label-printer ``connection`` mode from /api/hardware/config and
 * branches to the right transport:
 *   - network / cloud → POST /api/labels/print/{id} (the backend prints,
 *     either over TCP 9100 or via Zebra's SendFileToPrinter cloud API)
 *   - bluetooth       → GET  /api/labels/{id}/zpl + Web Bluetooth write to
 *     the Zebra (the server can't reach a BLE printer)
 *
 * Mirrors print-ticket.ts (receipt printer) so all label print buttons go
 * through one place and behave consistently across transports.
 */

import { api } from '@/lib/api';

export type LabelTransport = 'network' | 'cloud' | 'bluetooth' | 'none';

export interface PrintLabelResult {
  ok: boolean;
  message: string;
  transport: LabelTransport;
}

interface LabelConfig {
  mode: 'network' | 'cloud' | 'bluetooth';
  btName: string | null;
}

async function readLabelConfig(): Promise<LabelConfig> {
  try {
    const res = await api.get('/api/hardware/config');
    if (res.ok) {
      const cfg = await res.json();
      const conn = cfg?.label_printer?.connection;
      if (conn === 'bluetooth') {
        return { mode: 'bluetooth', btName: cfg.label_printer.bt_device_name ?? null };
      }
      if (conn === 'cloud') return { mode: 'cloud', btName: null };
    }
  } catch {
    // Network failure reading config — fall back to network and let the
    // backend surface the real error.
  }
  return { mode: 'network', btName: null };
}

/**
 * Send a ZPL string to the Zebra over Web Bluetooth.
 *
 * Must run inside a user gesture: when no paired device is found we call
 * requestZebraDevice(), which opens the browser's BLE chooser.
 */
async function sendZplOverBluetooth(zpl: string, cfg: LabelConfig): Promise<PrintLabelResult> {
  const { isWebBluetoothSupported, findPairedZebra, requestZebraDevice, sendZpl } =
    await import('@/lib/web-bluetooth-printer');
  if (!isWebBluetoothSupported()) {
    return { ok: false, transport: 'bluetooth', message: 'Web Bluetooth indisponible — utilisez Chrome Android sur HTTPS' };
  }
  try {
    let device = await findPairedZebra({ name: cfg.btName });
    if (!device) {
      const paired = await requestZebraDevice();
      device = paired.device;
    }
    await sendZpl(device, zpl);
    return { ok: true, transport: 'bluetooth', message: 'Étiquette envoyée (Bluetooth)' };
  } catch (err) {
    return { ok: false, transport: 'bluetooth', message: err instanceof Error ? err.message : 'Erreur Bluetooth' };
  }
}

async function fetchZpl(url: string): Promise<{ ok: true; zpl: string } | { ok: false; message: string }> {
  const res = await api.get(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({} as Record<string, unknown>));
    return { ok: false, message: (body.detail as string) || 'ZPL indisponible' };
  }
  return { ok: true, zpl: await res.text() };
}

/** Print one product label on the configured Zebra. */
export async function printProductLabel(productId: string, copies = 1): Promise<PrintLabelResult> {
  const cfg = await readLabelConfig();

  if (cfg.mode === 'bluetooth') {
    const qs = copies > 1 ? `?copies=${copies}` : '';
    const z = await fetchZpl(`/api/labels/${productId}/zpl${qs}`);
    if (!z.ok) return { ok: false, transport: 'bluetooth', message: z.message };
    return sendZplOverBluetooth(z.zpl, cfg);
  }

  try {
    const res = await api.post(`/api/labels/print/${productId}${copies > 1 ? `?copies=${copies}` : ''}`, {});
    if (res.ok) return { ok: true, transport: cfg.mode, message: 'Étiquette imprimée' };
    const body = await res.json().catch(() => ({} as Record<string, unknown>));
    return { ok: false, transport: cfg.mode, message: (body.detail as string) || "Échec de l'impression" };
  } catch {
    return { ok: false, transport: cfg.mode, message: 'Imprimante injoignable' };
  }
}

/** Print a test label on the configured Zebra (used by /settings). */
export async function printTestLabel(): Promise<PrintLabelResult> {
  const cfg = await readLabelConfig();

  if (cfg.mode === 'bluetooth') {
    const z = await fetchZpl('/api/hardware/label/test-zpl');
    if (!z.ok) return { ok: false, transport: 'bluetooth', message: z.message };
    return sendZplOverBluetooth(z.zpl, cfg);
  }

  try {
    const res = await api.post('/api/hardware/label/test', {});
    if (res.ok) return { ok: true, transport: cfg.mode, message: 'Étiquette de test envoyée' };
    const body = await res.json().catch(() => ({} as Record<string, unknown>));
    return { ok: false, transport: cfg.mode, message: (body.detail as string) || 'Échec du test' };
  } catch {
    return { ok: false, transport: cfg.mode, message: 'Imprimante injoignable' };
  }
}
