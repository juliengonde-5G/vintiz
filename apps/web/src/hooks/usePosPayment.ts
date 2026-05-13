'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { api } from '@/lib/api';
import { generateClientUuid } from '@/lib/offline-queue';
import type { PaymentStatus } from '@/components/pos/PaymentStatusBanner';

/**
 * usePosPayment — centralizes the side-effects the new wizard relies on:
 *
 * - **client_uuid idempotence** (Sprint 1) : a fresh UUID per checkout
 *   session, regenerated only after a successful commit. A network retry
 *   replays the same UUID so the API short-circuits.
 * - **SumUp polling** with 90s timeout (Sprint 2) : poll the `/cb/{id}/status`
 *   endpoint while the payment is pending; bubble the status changes up
 *   to the wizard via the `onStatus` callback. Auto-cancels on timeout.
 * - **Visibility pause** (Sprint 4) : when the page is backgrounded the
 *   poller stops to save battery on the Lenovo tablette; resumes on
 *   visibility change. The 90 s timer keeps running so the cashier
 *   doesn't see a "wedged" state on return.
 * - **Payment-attempt logging** : every CB attempt is logged to
 *   `/api/pos/payment-attempts` (pending → succeeded / failed / timeout),
 *   even when the cashier abandons before commit — drives the
 *   /admin/payment-attempts debug surface.
 *
 * The hook returns a stable `runCardCheckout` ready to be passed to
 * `<MultiStepPaymentWizard onCardCheckout={...} />`. It does NOT manage the
 * cart or commit the transaction; the parent owns those.
 */

export interface CardCheckoutOutcome {
  status: PaymentStatus;
  detail?: string;
  checkout_id?: string;
  attempt_id?: string;
}

interface UsePosPaymentOptions {
  /** Cashier currently identified at the POS — logged on every attempt. */
  cashierId?: string | null;
  /** Drawer ID for the open session — logged on every attempt. */
  drawerId?: string | null;
  /** Polling interval (ms) — defaults to 1500. */
  pollIntervalMs?: number;
  /** Hard timeout for a CB checkout (ms) — defaults to 90 s. */
  timeoutMs?: number;
}

const POLL_DEFAULT_MS = 1500;
const TIMEOUT_DEFAULT_MS = 90_000;

export function usePosPayment(options: UsePosPaymentOptions = {}) {
  const {
    cashierId,
    drawerId,
    pollIntervalMs = POLL_DEFAULT_MS,
    timeoutMs = TIMEOUT_DEFAULT_MS,
  } = options;

  /** Idempotence key for the *next* commit. Regenerated after success. */
  const clientUuidRef = useRef<string>(generateClientUuid());
  const [clientUuid, setClientUuid] = useState<string>(clientUuidRef.current);

  /** Cancellation flag — flipped when the wizard closes mid-poll. */
  const cancelledRef = useRef<boolean>(false);

  /** Pause poller while the tab is backgrounded. */
  const visibleRef = useRef<boolean>(
    typeof document === 'undefined' ? true : !document.hidden,
  );

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const handler = (): void => {
      visibleRef.current = !document.hidden;
    };
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, []);

  const rotateUuid = useCallback((): string => {
    const next = generateClientUuid();
    clientUuidRef.current = next;
    setClientUuid(next);
    return next;
  }, []);

  const cancel = useCallback((): void => {
    cancelledRef.current = true;
  }, []);

  const logAttempt = useCallback(
    async (
      payload: Record<string, unknown>,
      attemptId?: string,
    ): Promise<string | undefined> => {
      try {
        const res = await api.post('/api/pos/payment-attempts', {
          ...payload,
          attempt_id: attemptId,
          cashier_id: cashierId || undefined,
          drawer_id: drawerId || undefined,
        });
        if (res.ok) {
          const data = await res.json();
          return data.id;
        }
      } catch {
        /* don't break the checkout because the audit log failed */
      }
      return attemptId;
    },
    [cashierId, drawerId],
  );

  /**
   * Run a CB checkout end-to-end. The wizard awaits this promise; the
   * `onStatus` callback fires every time the status flips so the banner
   * can update without polling on the React tree.
   */
  const runCardCheckout = useCallback(
    async (
      amount: number,
      onStatus: (status: PaymentStatus, detail?: string) => void,
    ): Promise<CardCheckoutOutcome> => {
      cancelledRef.current = false;

      // 1. Initiate the checkout
      let checkoutId: string | undefined;
      let attemptId: string | undefined;
      try {
        const res = await api.post('/api/pos/payments/cb/initiate', {
          amount,
          description: 'Vente Vintiz',
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          const detail = err?.detail || 'Initiation refusée';
          attemptId = await logAttempt({
            method: 'card',
            amount,
            status: 'failed',
            error_detail: detail,
          });
          onStatus('failed', detail);
          return { status: 'failed', detail, attempt_id: attemptId };
        }
        const data = await res.json();
        checkoutId = data.checkout_id;
        const initialStatus = (data.status || 'PENDING').toUpperCase();
        if (initialStatus === 'FAILED') {
          attemptId = await logAttempt({
            method: 'card',
            amount,
            status: 'failed',
            error_detail: data.error_detail || 'Refusé par SumUp',
            sumup_checkout_id: checkoutId,
          });
          onStatus('failed', data.error_detail || 'Refusé par SumUp');
          return {
            status: 'failed',
            detail: data.error_detail,
            checkout_id: checkoutId,
            attempt_id: attemptId,
          };
        }
        attemptId = await logAttempt({
          method: 'card',
          amount,
          status: 'pending',
          sumup_checkout_id: checkoutId,
        });
      } catch (err) {
        const detail = err instanceof Error ? err.message : 'Erreur réseau';
        attemptId = await logAttempt({
          method: 'card',
          amount,
          status: 'failed',
          error_detail: detail,
        });
        onStatus('failed', detail);
        return { status: 'failed', detail, attempt_id: attemptId };
      }

      onStatus('pending');

      // 2. Poll until completion or timeout
      const startedAt = Date.now();
      while (!cancelledRef.current) {
        if (Date.now() - startedAt > timeoutMs) {
          // Hard timeout — try to cancel server-side and report to caller.
          try {
            if (checkoutId) {
              await api.delete(`/api/pos/payments/cb/${checkoutId}`);
            }
          } catch {
            /* best-effort cancel */
          }
          attemptId = await logAttempt(
            {
              method: 'card',
              amount,
              status: 'failed',
              error_detail: 'timeout',
              sumup_checkout_id: checkoutId,
            },
            attemptId,
          );
          onStatus('timeout', 'Pas de réponse du TPE après 90 s.');
          return {
            status: 'timeout',
            detail: 'Pas de réponse du TPE après 90 s.',
            checkout_id: checkoutId,
            attempt_id: attemptId,
          };
        }

        if (!visibleRef.current) {
          // Tab backgrounded — sleep without polling.
          await sleep(pollIntervalMs);
          continue;
        }

        try {
          const res = await api.get(
            `/api/pos/payments/cb/${checkoutId}/status`,
          );
          if (res.ok) {
            const data = await res.json();
            const raw = (data.status || 'PENDING').toUpperCase();
            if (raw === 'PAID') {
              attemptId = await logAttempt(
                {
                  method: 'card',
                  amount,
                  status: 'succeeded',
                  sumup_checkout_id: checkoutId,
                },
                attemptId,
              );
              onStatus('paid');
              return {
                status: 'paid',
                checkout_id: checkoutId,
                attempt_id: attemptId,
              };
            }
            if (raw === 'FAILED') {
              const detail = data.error_detail || 'Carte refusée';
              attemptId = await logAttempt(
                {
                  method: 'card',
                  amount,
                  status: 'failed',
                  error_detail: detail,
                  sumup_checkout_id: checkoutId,
                },
                attemptId,
              );
              onStatus('failed', detail);
              return {
                status: 'failed',
                detail,
                checkout_id: checkoutId,
                attempt_id: attemptId,
              };
            }
            if (raw === 'CANCELLED') {
              attemptId = await logAttempt(
                {
                  method: 'card',
                  amount,
                  status: 'cancelled',
                  cancelled_reason: 'sumup_side',
                  sumup_checkout_id: checkoutId,
                },
                attemptId,
              );
              onStatus('cancelled');
              return {
                status: 'cancelled',
                checkout_id: checkoutId,
                attempt_id: attemptId,
              };
            }
          }
        } catch {
          /* transient error, keep polling until timeout */
        }
        await sleep(pollIntervalMs);
      }

      // Wizard cancelled mid-poll
      try {
        if (checkoutId) {
          await api.delete(`/api/pos/payments/cb/${checkoutId}`);
        }
      } catch {
        /* best-effort */
      }
      attemptId = await logAttempt(
        {
          method: 'card',
          amount,
          status: 'cancelled',
          cancelled_reason: 'cashier_cancelled',
          sumup_checkout_id: checkoutId,
        },
        attemptId,
      );
      onStatus('cancelled');
      return {
        status: 'cancelled',
        checkout_id: checkoutId,
        attempt_id: attemptId,
      };
    },
    [logAttempt, pollIntervalMs, timeoutMs],
  );

  return {
    clientUuid,
    rotateUuid,
    runCardCheckout,
    cancel,
  };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
