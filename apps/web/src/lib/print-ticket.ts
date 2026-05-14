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
