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
 *   even when the cashier abandons before commit — drives the « CB
 *   échouées » view of the /admin/transactions page.
 *
 * The hook returns a stable `runCardCheckout` ready to be passed to
 * `<MultiStepPaymentWizard onCardCheckout={...} />`. It does NOT manage the
 * cart or commit the transaction; the parent owns those.
 */

/** SumUp identifiers captured at PAID time, persisted on the Payment row so
 * a later card refund can be issued through the SumUp API. */
export interface SumUpPaymentDetails {
  attempt_id?: string;
  sumup_checkout_id?: string;
  sumup_transaction_id?: string;
  sumup_transaction_code?: string;
  sumup_auth_code?: string;
  sumup_card_brand?: string;
  sumup_card_last4?: string;
  sumup_environment?: string;
}

export interface CardCheckoutOutcome {
  status: PaymentStatus;
  detail?: string;
  checkout_id?: string;
  attempt_id?: string;
  sumup?: SumUpPaymentDetails;
}

function extractSumUpDetails(
  data: Record<string, unknown>,
  checkoutId?: string,
): SumUpPaymentDetails {
  return {
    attempt_id: data.attempt_id as string | undefined,
    sumup_checkout_id: (data.checkout_id as string) || checkoutId,
    sumup_transaction_id: data.sumup_transaction_id as string | undefined,
    sumup_transaction_code: data.sumup_transaction_code as string | undefined,
    sumup_auth_code: data.sumup_auth_code as string | undefined,
    sumup_card_brand: data.sumup_card_brand as string | undefined,
    sumup_card_last4: data.sumup_card_last4 as string | undefined,
    sumup_environment: data.environment as string | undefined,
  };
}

/** Flatten the Solo return into the fields the payment-attempts log accepts,
 * so a settled CB attempt (succeeded or failed) records the terminal outcome
 * — transaction reference + masked card — not only the checkout id. */
function sumupAttemptFields(
  sumup: SumUpPaymentDetails,
  checkoutId?: string,
): Record<string, unknown> {
  return {
    sumup_checkout_id: sumup.sumup_checkout_id || checkoutId,
    sumup_transaction_id: sumup.sumup_transaction_id,
    sumup_transaction_code: sumup.sumup_transaction_code,
    sumup_auth_code: sumup.sumup_auth_code,
    sumup_card_brand: sumup.sumup_card_brand,
    sumup_card_last4: sumup.sumup_card_last4,
  };
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

      // 1. Initiate the checkout. The backend is now authoritative: it
      //    creates the PaymentAttempt and returns its id, plus a `diagnostic`
      //    when the checkout fell through to link mode (no reader resolved →
      //    the Solo terminal will NOT ring). We only *update* that attempt
      //    through the lifecycle, and fall back to creating one ourselves if
      //    an older backend didn't return an id.
      let checkoutId: string | undefined;
      let attemptId: string | undefined;
      let diagnostic: string | undefined;
      try {
        const res = await api.post('/api/pos/payments/cb/initiate', {
          amount,
          description: 'Vente Vintiz',
          // Idempotence / reconciliation key — ties this checkout to the
          // sale's client_uuid so a retried initiate references the same
          // intended payment and the SumUp txn can be looked up later.
          foreign_transaction_id: clientUuidRef.current,
          // Attribute the server-side attempt to the cashier + drawer.
          cashier_id: cashierId || undefined,
          drawer_id: drawerId || undefined,
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
        attemptId = data.attempt_id; // authoritative id created server-side
        diagnostic = data.diagnostic; // link-mode warning ("le TPE ne sonnera pas"), if any
        const initialStatus = (data.status || 'PENDING').toUpperCase();
        if (initialStatus === 'FAILED') {
          const detail = data.error_detail || 'Refusé par SumUp';
          // The backend already recorded the failed attempt when it returned
          // an id — only log it ourselves as a fallback for older backends.
          if (!attemptId) {
            attemptId = await logAttempt({
              method: 'card',
              amount,
              status: 'failed',
              error_detail: detail,
              sumup_checkout_id: checkoutId,
            });
          }
          onStatus('failed', detail);
          return {
            status: 'failed',
            detail,
            checkout_id: checkoutId,
            attempt_id: attemptId,
          };
        }
        if (!attemptId) {
          attemptId = await logAttempt({
            method: 'card',
            amount,
            status: 'pending',
            sumup_checkout_id: checkoutId,
          });
        }
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

      // Surface the link-mode diagnostic under the spinner so the cashier
      // understands why the TPE stays silent instead of waiting it out.
      onStatus('pending', diagnostic);

      // 2. Poll until completion or timeout
      const startedAt = Date.now();
      while (!cancelledRef.current) {
        if (Date.now() - startedAt > timeoutMs) {
          // One final status read before giving up. A backgrounded tab pauses
          // polling but the timer keeps running, so the card may have been
          // PAID while we weren't looking — don't cancel a real payment.
          try {
            if (checkoutId) {
              const finalRes = await api.get(
                `/api/pos/payments/cb/${checkoutId}/status`,
              );
              if (finalRes.ok) {
                const finalData = await finalRes.json();
                if ((finalData.status || '').toUpperCase() === 'PAID') {
                  const sumup = extractSumUpDetails(finalData, checkoutId);
                  attemptId = await logAttempt(
                    {
                      method: 'card',
                      amount,
                      status: 'succeeded',
                      ...sumupAttemptFields(sumup, checkoutId),
                    },
                    attemptId,
                  );
                  onStatus('paid');
                  return {
                    status: 'paid',
                    checkout_id: checkoutId,
                    attempt_id: attemptId,
                    sumup: { ...sumup, attempt_id: attemptId },
                  };
                }
              }
            }
          } catch {
            /* fall through to the timeout/cancel path */
          }
          // Second canal de confirmation, indépendant du polling checkout :
          // on interroge SumUp par la référence de la vente
          // (foreign_transaction_id = client_uuid). Rattrape un paiement abouti
          // dont la confirmation TPE a été perdue → évite un double encaissement.
          try {
            const recRes = await api.get(
              `/api/pos/payments/cb/recover?foreign_transaction_id=${encodeURIComponent(
                clientUuidRef.current,
              )}`,
            );
            if (recRes.ok) {
              const rec = await recRes.json();
              if ((rec.status || '').toUpperCase() === 'PAID') {
                const sumup = extractSumUpDetails(rec, checkoutId);
                attemptId = await logAttempt(
                  {
                    method: 'card',
                    amount,
                    status: 'succeeded',
                    ...sumupAttemptFields(sumup, checkoutId),
                  },
                  attemptId,
                );
                onStatus('paid');
                return {
                  status: 'paid',
                  checkout_id: checkoutId,
                  attempt_id: attemptId,
                  sumup: { ...sumup, attempt_id: attemptId },
                };
              }
            }
          } catch {
            /* réseau toujours coupé — on retombe sur le timeout prudent */
          }
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
          const timeoutMsg =
            'Pas de réponse du TPE après 90 s. Si la carte a été débitée, '
            + 'vérifiez le reçu du TPE ou le journal CB AVANT de relancer '
            + '(le paiement est rattaché à cette vente).';
          onStatus('timeout', timeoutMsg);
          return {
            status: 'timeout',
            detail: timeoutMsg,
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
              const sumup = extractSumUpDetails(data, checkoutId);
              attemptId = await logAttempt(
                {
                  method: 'card',
                  amount,
                  status: 'succeeded',
                  ...sumupAttemptFields(sumup, checkoutId),
                },
                attemptId,
              );
              onStatus('paid');
              return {
                status: 'paid',
                checkout_id: checkoutId,
                attempt_id: attemptId,
                sumup: { ...sumup, attempt_id: attemptId },
              };
            }
            if (raw === 'FAILED') {
              const detail = data.error_detail || 'Carte refusée';
              const sumup = extractSumUpDetails(data, checkoutId);
              attemptId = await logAttempt(
                {
                  method: 'card',
                  amount,
                  status: 'failed',
                  error_detail: detail,
                  ...sumupAttemptFields(sumup, checkoutId),
                },
                attemptId,
              );
              onStatus('failed', detail);
              return {
                status: 'failed',
                detail,
                checkout_id: checkoutId,
                attempt_id: attemptId,
                sumup: { ...sumup, attempt_id: attemptId },
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
    [logAttempt, pollIntervalMs, timeoutMs, cashierId, drawerId],
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
