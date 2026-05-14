/**
 * Single source of truth for "envoyer ce ticket à la MUNBYN".
 *
 * Used by:
 *   - /pos (vente validée, modale legacy + wizard ReceiptPreviewCard)
 *   - /dashboard (réimpression d'un ticket déjà encaissé)
 *
 * Reads the printer ``connection`` mode from /api/hardware/config and
 * branches to the right transport :
 *   - network → POST /api/pos/transactions/{id}/print (backend opens TCP)
 *   - usb     → GET  /api/pos/transactions/{id}/escpos?kick_drawer=true
 *               + WebUSB transferOut to the paired MUNBYN
 *
 * Centralising this avoids the bug we just shipped where the dashboard
 * fell back to ``window.print()`` (tablet's PDF dialog) instead of the
 * thermal printer.
 */

import { api } from '@/lib/api';

export interface PrintTicketResult {
  ok: boolean;
  message: string;
  /** Which transport was actually used. */
  transport: 'network' | 'usb' | 'none';
}

interface PrinterConfig {
  mode: 'network' | 'usb';
  usbVendor: number | null;
  usbProduct: number | null;
  usbSerial: string | null;
}

async function readPrinterConfig(): Promise<PrinterConfig> {
  try {
    const cfgRes = await api.get('/api/hardware/config');
    if (cfgRes.ok) {
      const cfg = await cfgRes.json();
      if (cfg?.receipt_printer?.connection === 'usb') {
        return {
          mode: 'usb',
          usbVendor: cfg.receipt_printer.usb_vendor_id ?? null,
          usbProduct: cfg.receipt_printer.usb_product_id ?? null,
          usbSerial: cfg.receipt_printer.usb_serial_number ?? null,
        };
      }
    }
  } catch {
    // Fall through to default network mode below.
  }
  return { mode: 'network', usbVendor: null, usbProduct: null, usbSerial: null };
}

async function getUsbDevice(cfg: PrinterConfig) {
  const { findPairedDevice, isWebUsbSupported } = await import('@/lib/webusb-printer');
  if (!isWebUsbSupported()) {
    throw new Error('WebUSB indisponible — utilisez Chrome Android sur HTTPS');
  }
  if (!cfg.usbVendor || !cfg.usbProduct) {
    throw new Error('Aucune imprimante USB couplée — voir Paramètres > Matériel');
  }
  const device = await findPairedDevice({
    vendorId: cfg.usbVendor,
    productId: cfg.usbProduct,
    serialNumber: cfg.usbSerial,
  });
  if (!device) {
    throw new Error('Imprimante USB introuvable — rebranchez puis recouplez');
  }
  return device;
}

/**
 * Open the cash drawer without printing anything.
 *
 * Used by:
 *   - The "Test tiroir" button in /settings > Materiel
 *   - The auto-kick on cash sale validation (POS encaissement)
 *
 * Branches on the configured ``connection`` mode the same way
 * ``printTransactionTicket`` does — without this, the drawer kick
 * fails silently in USB mode (legacy network endpoint opens a TCP
 * socket that doesn't exist on the tablet).
 */
export async function kickDrawer(): Promise<PrintTicketResult> {
  const cfg = await readPrinterConfig();

  if (cfg.mode === 'usb') {
    try {
      const device = await getUsbDevice(cfg);
      const bytesRes = await api.get('/api/hardware/drawer/kick-escpos');
      if (!bytesRes.ok) {
        const body = await bytesRes.json().catch(() => ({} as Record<string, unknown>));
        return {
          ok: false,
          transport: 'usb',
          message: (body.detail as string) || 'Impossible de générer la commande tiroir',
        };
      }
      const bytes = new Uint8Array(await bytesRes.arrayBuffer());
      const { sendEscposBytes } = await import('@/lib/webusb-printer');
      await sendEscposBytes(device, bytes);
      return { ok: true, transport: 'usb', message: 'Tiroir ouvert (USB)' };
    } catch (err) {
      return {
        ok: false,
        transport: 'usb',
        message: err instanceof Error ? err.message : 'Erreur USB',
      };
    }
  }

  // Network path
  try {
    const res = await api.post('/api/hardware/drawer/kick', {});
    if (res.ok) {
      return { ok: true, transport: 'network', message: 'Tiroir ouvert' };
    }
    const body = await res.json().catch(() => ({} as Record<string, unknown>));
    return {
      ok: false,
      transport: 'network',
      message: (body.detail as string) || 'Tiroir injoignable',
    };
  } catch {
    return { ok: false, transport: 'network', message: 'Tiroir injoignable' };
  }
}

/**
 * Print a transaction's receipt on the configured MUNBYN.
 *
 * Returns a structured result instead of throwing so callers can show
 * a non-blocking toast without try/catch boilerplate.
 */
export async function printTransactionTicket(
  transactionId: string,
  options: { kickDrawer?: boolean } = {},
): Promise<PrintTicketResult> {
  const kickDrawer = options.kickDrawer ?? true;

  let mode: 'network' | 'usb' = 'network';
  let usbVendor: number | null = null;
  let usbProduct: number | null = null;
  let usbSerial: string | null = null;
  try {
    const cfgRes = await api.get('/api/hardware/config');
    if (cfgRes.ok) {
      const cfg = await cfgRes.json();
      if (cfg?.receipt_printer?.connection === 'usb') {
        mode = 'usb';
        usbVendor = cfg.receipt_printer.usb_vendor_id ?? null;
        usbProduct = cfg.receipt_printer.usb_product_id ?? null;
        usbSerial = cfg.receipt_printer.usb_serial_number ?? null;
      }
    }
  } catch {
    // Network failure reading config — fall back to network mode and
    // let the backend surface the real error.
  }

  if (mode === 'usb') {
    const { findPairedDevice, sendEscposBytes, isWebUsbSupported } =
      await import('@/lib/webusb-printer');
    if (!isWebUsbSupported()) {
      return {
        ok: false,
        transport: 'usb',
        message: 'WebUSB indisponible — utilisez Chrome Android sur HTTPS',
      };
    }
    if (!usbVendor || !usbProduct) {
      return {
        ok: false,
        transport: 'usb',
        message: 'Aucune imprimante USB couplée — voir Paramètres > Matériel',
      };
    }
    const device = await findPairedDevice({
      vendorId: usbVendor,
      productId: usbProduct,
      serialNumber: usbSerial,
    });
    if (!device) {
      return {
        ok: false,
        transport: 'usb',
        message: 'Imprimante USB introuvable — rebranchez puis recouplez',
      };
    }
    const qs = kickDrawer ? '?kick_drawer=true' : '';
    const bytesRes = await api.get(
      `/api/pos/transactions/${transactionId}/escpos${qs}`,
    );
    if (!bytesRes.ok) {
      const body = await bytesRes.json().catch(() => ({} as Record<string, unknown>));
      return {
        ok: false,
        transport: 'usb',
        message: (body.detail as string) || 'Impossible de générer le ticket',
      };
    }
    try {
      const bytes = new Uint8Array(await bytesRes.arrayBuffer());
      await sendEscposBytes(device, bytes);
      return {
        ok: true,
        transport: 'usb',
        message: 'Ticket envoyé à la MUNBYN (USB)',
      };
    } catch (err) {
      return {
        ok: false,
        transport: 'usb',
        message: err instanceof Error ? err.message : 'Erreur USB',
      };
    }
  }

  // Network path
  try {
    const res = await api.post(`/api/pos/transactions/${transactionId}/print`, {});
    if (res.ok) {
      return {
        ok: true,
        transport: 'network',
        message: 'Ticket imprimé sur la MUNBYN',
      };
    }
    const body = await res.json().catch(() => ({} as Record<string, unknown>));
    return {
      ok: false,
      transport: 'network',
      message: (body.detail as string) || "Échec de l'impression",
    };
  } catch {
    return {
      ok: false,
      transport: 'network',
      message: 'Imprimante injoignable',
    };
  }
}
