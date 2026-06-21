'use client';

/**
 * Shared hook for the zoning feature toggle.
 *
 * Reads `features.zoning_enabled` from the back-office. Returns:
 *   null  — still loading (caller can show a spinner / render nothing yet)
 *   true  — zoning active (default)
 *   false — boutique sans zonage (hide every zone surface)
 *
 * Fetches once per mount (the toggle is rare); on error it falls back to
 * `true` so a transient API hiccup never hides core UI.
 */

import { useEffect, useState } from 'react';
import { api } from './api';

export function useZoningEnabled(): boolean | null {
  const [enabled, setEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.get('/api/admin/features')
      .then(async (res) => {
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          setEnabled(data.zoning_enabled !== false);
        } else {
          setEnabled(true);
        }
      })
      .catch(() => { if (!cancelled) setEnabled(true); });
    return () => { cancelled = true; };
  }, []);

  return enabled;
}
