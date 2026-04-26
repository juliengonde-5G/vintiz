'use client';

/**
 * Connectivity hook (P1-005).
 *
 * Single source of truth for the POS UI to know whether it can reach
 * the API. Combines:
 *
 *  - `navigator.onLine` (instant signal, but fallible: returns true if
 *    Wi-Fi is up but the captive portal blocks traffic).
 *  - A periodic ping of `/api/health` (definitive but slower).
 *
 * The hook returns the latest decision plus a `recheck()` function the
 * caller can wire to a "Sync now" button.
 */

import { useCallback, useEffect, useState } from 'react';

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const PING_INTERVAL_MS = 15_000;
const PING_TIMEOUT_MS = 4_000;

async function pingHealth(): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PING_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_URL}/api/health`, {
      signal: controller.signal,
      cache: 'no-store',
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export function useConnectivity(): {
  online: boolean;
  lastCheck: number | null;
  recheck: () => Promise<boolean>;
} {
  const [online, setOnline] = useState<boolean>(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine,
  );
  const [lastCheck, setLastCheck] = useState<number | null>(null);

  const recheck = useCallback(async () => {
    const result = await pingHealth();
    setOnline(result);
    setLastCheck(Date.now());
    return result;
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const onOnline = () => {
      setOnline(true);
      // Validate via a real ping — the OS may flip to "online" before the
      // network actually carries traffic.
      void recheck();
    };
    const onOffline = () => setOnline(false);

    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);

    // First check on mount.
    void recheck();

    const interval = setInterval(() => {
      void recheck();
    }, PING_INTERVAL_MS);

    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      clearInterval(interval);
    };
  }, [recheck]);

  return { online, lastCheck, recheck };
}
