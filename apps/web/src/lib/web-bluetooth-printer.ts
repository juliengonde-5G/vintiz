/**
 * Web Bluetooth (BLE) driver for the Zebra ZD421d label printer.
 *
 * Used on the cashier tablet (Chrome Android) when the boutique runs the
 * label printer over Bluetooth Low Energy instead of network/cloud. The
 * cloud API can't reach a BLE printer, so the tablet fetches the raw ZPL
 * from the backend and writes it here, directly to the printer over BLE.
 *
 * Transport: Zebra's "BLE Parser Service" — a GATT service that accepts
 * ZPL the same way the Bluetooth Classic SPP serial port would. We write
 * to the "To Printer Data" characteristic in small chunks (BLE caps each
 * write, and Zebra's AppNote recommends a short delay between writes on
 * Android).
 *
 * Limits:
 * - BLE only (Web Bluetooth can't use Bluetooth Classic).
 * - Chrome Android / desktop Chrome — NOT iPad/Safari.
 * - Requires a secure context (HTTPS), satisfied by the prod PWA.
 * - requestDevice() must run inside a user gesture (button click).
 */

// Zebra BLE Parser Service UUIDs (lowercase — Web Bluetooth requires it).
const ZEBRA_PARSER_SERVICE = '38eb4a80-c570-11e3-9507-0002a5d5c51b';
// "To Printer Data" — the characteristic we write ZPL to.
const ZEBRA_WRITE_CHARACTERISTIC = '38eb4a82-c570-11e3-9507-0002a5d5c51b';

// BLE link layer caps each write; 200 bytes is safe on stacks that don't
// negotiate a larger MTU. A short delay between writes avoids dropping
// chunks on Android (per Zebra's BLE AppNote).
const CHUNK_SIZE = 200;
const INTER_CHUNK_DELAY_MS = 20;

// ---------------------------------------------------------------------------
// Minimal Web Bluetooth typings — only what we call (the TS DOM lib doesn't
// ship them, mirroring the approach in webusb-printer.ts).
// ---------------------------------------------------------------------------
interface BluetoothRemoteGATTCharacteristic {
  writeValue(value: BufferSource): Promise<void>;
  writeValueWithoutResponse?(value: BufferSource): Promise<void>;
}
interface BluetoothRemoteGATTService {
  getCharacteristic(uuid: string): Promise<BluetoothRemoteGATTCharacteristic>;
}
interface BluetoothRemoteGATTServer {
  connected: boolean;
  connect(): Promise<BluetoothRemoteGATTServer>;
  disconnect(): void;
  getPrimaryService(uuid: string): Promise<BluetoothRemoteGATTService>;
}
interface BluetoothDevice {
  id: string;
  name?: string;
  gatt?: BluetoothRemoteGATTServer;
}
interface RequestDeviceOptions {
  filters?: Array<{ services?: string[]; namePrefix?: string; name?: string }>;
  optionalServices?: string[];
  acceptAllDevices?: boolean;
}
interface Bluetooth {
  requestDevice(options: RequestDeviceOptions): Promise<BluetoothDevice>;
  getDevices?(): Promise<BluetoothDevice[]>;
}
declare global {
  interface Navigator {
    bluetooth?: Bluetooth;
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface PairedBtPrinter {
  id: string;
  name: string;
}

export function isWebBluetoothSupported(): boolean {
  return typeof navigator !== 'undefined' && Boolean(navigator.bluetooth);
}

/**
 * Prompt the operator to pick a Zebra printer over BLE. Filters on the
 * Zebra Parser Service so the chooser only shows compatible printers.
 * Must be called from a user gesture (button click).
 */
export async function requestZebraDevice(): Promise<{ device: BluetoothDevice; info: PairedBtPrinter }> {
  if (!navigator.bluetooth) {
    throw new Error('Web Bluetooth indisponible — utilisez Chrome Android sur HTTPS');
  }
  const device = await navigator.bluetooth.requestDevice({
    filters: [{ services: [ZEBRA_PARSER_SERVICE] }],
    optionalServices: [ZEBRA_PARSER_SERVICE],
  });
  return { device, info: { id: device.id, name: device.name || 'Zebra' } };
}

/**
 * Find a previously paired Zebra without prompting.
 *
 * Chrome retains BLE grants per-origin and exposes them via getDevices()
 * (where supported), so we can reconnect silently. Falls back to null when
 * unavailable — the caller then re-prompts via requestZebraDevice().
 */
export async function findPairedZebra(
  target: { name?: string | null },
): Promise<BluetoothDevice | null> {
  if (!navigator.bluetooth?.getDevices) return null;
  try {
    const devices = await navigator.bluetooth.getDevices();
    if (target.name) {
      const match = devices.find((d) => d.name === target.name);
      if (match) return match;
    }
    return devices[0] ?? null;
  } catch {
    return null;
  }
}

/**
 * Write a ZPL job to a paired Zebra over BLE.
 *
 * Connects GATT, resolves the Parser Service + write characteristic, and
 * streams the ZPL in chunks. Disconnects afterwards so the printer is free
 * for the next job / another device.
 */
export async function sendZpl(device: BluetoothDevice, zpl: string): Promise<void> {
  if (!device.gatt) {
    throw new Error('GATT indisponible sur ce périphérique Bluetooth');
  }
  const server = device.gatt.connected ? device.gatt : await device.gatt.connect();
  try {
    const service = await server.getPrimaryService(ZEBRA_PARSER_SERVICE);
    const characteristic = await service.getCharacteristic(ZEBRA_WRITE_CHARACTERISTIC);
    const bytes = new TextEncoder().encode(zpl);
    for (let offset = 0; offset < bytes.byteLength; offset += CHUNK_SIZE) {
      const slice = bytes.slice(offset, offset + CHUNK_SIZE);
      if (characteristic.writeValueWithoutResponse) {
        await characteristic.writeValueWithoutResponse(slice);
      } else {
        await characteristic.writeValue(slice);
      }
      await new Promise((resolve) => setTimeout(resolve, INTER_CHUNK_DELAY_MS));
    }
  } finally {
    try { server.disconnect(); } catch { /* already disconnected */ }
  }
}
