/**
 * WebUSB driver for the MUNBYN 047P receipt printer.
 *
 * Used on the cashier tablet (Lenovo Idea Tab Pro Gen 2, Chrome Android)
 * when the boutique runs the POS over USB-OTG instead of Wi-Fi. The
 * printer accepts the same ESC/POS payload as the network path; only the
 * transport differs.
 *
 * Pairing flow:
 *   1. Operator clicks "Coupler le périphérique USB" in /settings.
 *   2. ``requestMunbynDevice()`` opens the browser's USB picker filtered
 *      on USB class 7 (printer).
 *   3. Chrome remembers the grant per-origin; on next reload
 *      ``findPairedDevice()`` returns it without re-prompting.
 *
 * Printing flow (each job):
 *   1. ``sendEscposBytes(bytes)`` opens the device, picks the first
 *      bulk-OUT endpoint on interface 0 and writes the payload.
 *   2. The device is released immediately so the OS lets us reclaim it
 *      between jobs.
 *
 * Notes
 * - Requires a secure context (HTTPS or localhost). The PWA is served
 *   over HTTPS in production so this is satisfied.
 * - The TS DOM lib doesn't ship WebUSB types yet; we declare the
 *   minimum surface we use rather than adding @types/w3c-web-usb.
 */

// ---------------------------------------------------------------------------
// Minimal WebUSB typings — only what we actually call.
// ---------------------------------------------------------------------------
type UsbEndpointDirection = 'in' | 'out';
type UsbTransferType = 'bulk' | 'interrupt' | 'isochronous' | 'control';

interface USBEndpoint {
  endpointNumber: number;
  direction: UsbEndpointDirection;
  type: UsbTransferType;
  packetSize: number;
}

interface USBAlternateInterface {
  endpoints: USBEndpoint[];
}

interface USBInterface {
  interfaceNumber: number;
  claimed: boolean;
  alternate: USBAlternateInterface;
}

interface USBConfiguration {
  configurationValue: number;
  interfaces: USBInterface[];
}

interface USBOutTransferResult {
  bytesWritten: number;
  status: string;
}

interface USBDevice {
  vendorId: number;
  productId: number;
  productName?: string;
  manufacturerName?: string;
  serialNumber?: string;
  opened: boolean;
  configuration: USBConfiguration | null;
  open(): Promise<void>;
  close(): Promise<void>;
  selectConfiguration(value: number): Promise<void>;
  claimInterface(n: number): Promise<void>;
  releaseInterface(n: number): Promise<void>;
  transferOut(endpointNumber: number, data: BufferSource): Promise<USBOutTransferResult>;
}

interface USBDeviceFilter {
  vendorId?: number;
  productId?: number;
  classCode?: number;
  subclassCode?: number;
  protocolCode?: number;
  serialNumber?: string;
}

interface USBOptions {
  filters: USBDeviceFilter[];
}

interface USB {
  requestDevice(options: USBOptions): Promise<USBDevice>;
  getDevices(): Promise<USBDevice[]>;
}

declare global {
  interface Navigator {
    usb?: USB;
  }
}

// ---------------------------------------------------------------------------
// Public types & helpers
// ---------------------------------------------------------------------------

export interface PairedPrinter {
  vendorId: number;
  productId: number;
  serialNumber?: string;
  productLabel: string;
}

export function isWebUsbSupported(): boolean {
  return typeof navigator !== 'undefined' && Boolean(navigator.usb);
}

/**
 * Prompt the user to pick a USB printer. Filters on USB class 7 (the
 * "Printer" base class) so the chooser only shows compatible peripherals
 * — the operator doesn't have to sort through mice and keyboards.
 *
 * Returns the paired device's identifying fingerprint, which the caller
 * should persist via PUT /hardware/config so subsequent sessions can
 * reconnect silently.
 */
export async function requestMunbynDevice(): Promise<PairedPrinter> {
  if (!navigator.usb) {
    throw new Error('WebUSB indisponible — utilisez Chrome Android sur HTTPS');
  }
  const device = await navigator.usb.requestDevice({
    filters: [{ classCode: 7 }],
  });
  return summarisePrinter(device);
}

/**
 * Locate a previously paired printer by USB IDs without re-prompting.
 *
 * Chrome retains the per-origin grant across page reloads, so once the
 * operator has paired the MUNBYN once we can pick it back up silently.
 */
export async function findPairedDevice(
  target: { vendorId: number; productId: number; serialNumber?: string | null },
): Promise<USBDevice | null> {
  if (!navigator.usb) return null;
  const devices = await navigator.usb.getDevices();
  for (const d of devices) {
    if (d.vendorId !== target.vendorId) continue;
    if (d.productId !== target.productId) continue;
    if (target.serialNumber && d.serialNumber !== target.serialNumber) continue;
    return d;
  }
  return null;
}

/**
 * Send raw ESC/POS bytes to a paired MUNBYN.
 *
 * Opens the device, selects configuration 1, claims the first interface
 * that exposes a bulk-OUT endpoint and writes the payload in chunks of
 * the endpoint's packet size. Always closes the interface afterwards so
 * other tabs (or a reload) can reclaim it.
 */
export async function sendEscposBytes(
  device: USBDevice,
  payload: Uint8Array,
): Promise<void> {
  if (!device.opened) await device.open();
  if (!device.configuration) await device.selectConfiguration(1);
  const iface = device.configuration!.interfaces.find((it) =>
    it.alternate.endpoints.some(
      (e) => e.direction === 'out' && e.type === 'bulk',
    ),
  );
  if (!iface) {
    throw new Error('Interface bulk-OUT introuvable sur ce périphérique');
  }
  const endpoint = iface.alternate.endpoints.find(
    (e) => e.direction === 'out' && e.type === 'bulk',
  )!;

  if (!iface.claimed) await device.claimInterface(iface.interfaceNumber);
  try {
    // Some MUNBYN units stall on payloads larger than 4 KiB; chunk
    // defensively even though the spec allows arbitrary sizes.
    const chunkSize = Math.max(endpoint.packetSize * 16, 4096);
    for (let offset = 0; offset < payload.byteLength; offset += chunkSize) {
      const slice = payload.slice(offset, offset + chunkSize);
      await device.transferOut(endpoint.endpointNumber, slice);
    }
  } finally {
    try { await device.releaseInterface(iface.interfaceNumber); } catch { /* device may have detached */ }
  }
}

function summarisePrinter(device: USBDevice): PairedPrinter {
  const label = [
    device.manufacturerName,
    device.productName,
  ].filter(Boolean).join(' ').trim();
  return {
    vendorId: device.vendorId,
    productId: device.productId,
    serialNumber: device.serialNumber || undefined,
    productLabel: label || 'Imprimante ESC/POS',
  };
}
