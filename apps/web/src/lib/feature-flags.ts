/**
 * Feature flag helpers — read from the browser's environment + localStorage.
 *
 * Build-time flags come from ``NEXT_PUBLIC_ENABLE_*`` env vars; runtime
 * overrides via ``localStorage[ff.<name>]`` are handy on the Lenovo caisse
 * to opt the till into the new POS wizard without redeploying. Falls back
 * to the build-time value when the override is missing or "auto".
 *
 * Usage:
 *   if (isPosWizardEnabled()) renderNewWizard();
 */

const STORAGE_PREFIX = 'ff.';

function readBuildFlag(envKey: string): boolean {
  const raw = (process.env[envKey] || '').toString().toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'on';
}

function readOverride(name: string): 'on' | 'off' | 'auto' {
  if (typeof window === 'undefined') return 'auto';
  const raw = (window.localStorage.getItem(STORAGE_PREFIX + name) || '')
    .toLowerCase();
  if (raw === '1' || raw === 'true' || raw === 'on') return 'on';
  if (raw === '0' || raw === 'false' || raw === 'off') return 'off';
  return 'auto';
}

export function isFeatureEnabled(name: string, envKey: string): boolean {
  const override = readOverride(name);
  if (override === 'on') return true;
  if (override === 'off') return false;
  return readBuildFlag(envKey);
}

/**
 * Set a runtime override for the current device. Pass ``null`` to revert to
 * the build-time default.
 */
export function setFeatureOverride(
  name: string,
  state: boolean | null,
): void {
  if (typeof window === 'undefined') return;
  const key = STORAGE_PREFIX + name;
  if (state === null) {
    window.localStorage.removeItem(key);
  } else {
    window.localStorage.setItem(key, state ? '1' : '0');
  }
}

/**
 * The new SumUp-style POS wizard (PR 4-6 of the routine refactor). False by
 * default — the legacy inline payment UI keeps running until the manager
 * opts a device in. Enable on the Lenovo dock first, then iPad / Galaxy.
 */
export function isPosWizardEnabled(): boolean {
  return isFeatureEnabled(
    'pos_wizard',
    'NEXT_PUBLIC_ENABLE_NEW_POS_WIZARD',
  );
}
