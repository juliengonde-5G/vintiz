'use client';

import React, { useState } from 'react';

interface Props {
  clientEmail?: string | null;
  clientPhone?: string | null;
  /** Sends the receipt. ``to`` is the optional ad-hoc address (walk-in).
   *
   * May return a structured result so we can surface the simulated state
   * — i.e. when Twilio / Brevo are not configured the backend logs the
   * call but doesn't actually send anything. We MUST warn the operator
   * in that case so they don't think the customer received the receipt.
   */
  onResend: (
    channel: 'email' | 'sms',
    to?: string,
  ) => Promise<{ simulated?: boolean; message?: string } | void> | void;
}

/**
 * "Envoyer par email / SMS" buttons + ad-hoc input.
 *
 * Used by the POS legacy receipt modal and the wizard's
 * ``ReceiptPreviewCard``. Always shows both buttons :
 *   - if the client has an email/phone on file → one tap sends.
 *   - otherwise → unfolds an input for a walk-in customer who wants the
 *     receipt mailed without leaving a CRM trace.
 */
export default function InlineResendButtons({
  clientEmail,
  clientPhone,
  onResend,
}: Props) {
  const [emailDraft, setEmailDraft] = useState(clientEmail ?? '');
  const [phoneDraft, setPhoneDraft] = useState(clientPhone ?? '');
  const [showEmailInput, setShowEmailInput] = useState(false);
  const [showSmsInput, setShowSmsInput] = useState(false);
  const [sending, setSending] = useState<'email' | 'sms' | null>(null);
  type FeedbackTone = 'success' | 'error' | 'warning';
  const [feedback, setFeedback] = useState<{ msg: string; tone: FeedbackTone } | null>(null);

  const handleResend = async (channel: 'email' | 'sms', to?: string) => {
    setSending(channel);
    setFeedback(null);
    try {
      const result = await onResend(channel, to);
      // The backend tells us whether the send was real or just simulated
      // (Twilio/Brevo not configured). A simulated send is NOT a success
      // from the operator's POV — the customer never received anything.
      if (result && typeof result === 'object' && result.simulated) {
        setFeedback({
          msg:
            result.message ||
            (channel === 'email'
              ? '⚠ Email simulé — provider non configuré, le destinataire n\'a rien reçu.'
              : '⚠ SMS simulé — Twilio non configuré, le destinataire n\'a rien reçu.'),
          tone: 'warning',
        });
      } else {
        setFeedback({
          msg:
            (result && typeof result === 'object' && result.message) ||
            (channel === 'email'
              ? `Email envoyé à ${to || clientEmail}`
              : `SMS envoyé au ${to || clientPhone}`),
          tone: 'success',
        });
      }
      setShowEmailInput(false);
      setShowSmsInput(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Échec de l'envoi";
      setFeedback({ msg, tone: 'error' });
    } finally {
      setSending(null);
    }
  };

  const emailLooksValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailDraft.trim());
  const phoneLooksValid = /^\+?[\d\s().-]{6,}$/.test(phoneDraft.trim());

  return (
    <div className="mt-4 space-y-2">
      {feedback && (
        <div
          role="status"
          className={`rounded-xl px-3 py-2 text-sm ${
            feedback.tone === 'success'
              ? 'bg-green-50 text-green-700'
              : feedback.tone === 'warning'
                ? 'bg-yellow-50 text-yellow-800 border border-yellow-200'
                : 'bg-red-50 text-red-700'
          }`}
        >
          {feedback.msg}
        </div>
      )}

      {clientEmail && !showEmailInput ? (
        <button
          type="button"
          disabled={sending === 'email'}
          onClick={() => void handleResend('email')}
          className="w-full min-h-[44px] rounded-xl border border-vz-line bg-white px-4 py-2.5 text-sm font-medium text-vz-ink hover:bg-vz-bg-alt disabled:opacity-50"
        >
          {sending === 'email' ? 'Envoi…' : `Envoyer par email (${clientEmail})`}
        </button>
      ) : showEmailInput ? (
        <div className="flex gap-2">
          <input
            type="email"
            value={emailDraft}
            onChange={(e) => setEmailDraft(e.target.value)}
            placeholder="exemple@domaine.fr"
            className="flex-1 min-h-[44px] px-3 py-2 rounded-lg border border-vz-line bg-white text-vz-ink"
            autoFocus
          />
          <button
            type="button"
            disabled={!emailLooksValid || sending === 'email'}
            onClick={() => void handleResend('email', emailDraft.trim())}
            className="px-4 rounded-lg bg-vz-teal text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Envoyer
          </button>
          <button
            type="button"
            onClick={() => setShowEmailInput(false)}
            className="px-3 text-vz-ink-mute"
            aria-label="Annuler"
          >
            ✕
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowEmailInput(true)}
          className="w-full min-h-[44px] rounded-xl border border-vz-line bg-white px-4 py-2.5 text-sm font-medium text-vz-ink hover:bg-vz-bg-alt"
        >
          Envoyer par email…
        </button>
      )}

      {clientPhone && !showSmsInput ? (
        <button
          type="button"
          disabled={sending === 'sms'}
          onClick={() => void handleResend('sms')}
          className="w-full min-h-[44px] rounded-xl border border-vz-line bg-white px-4 py-2.5 text-sm font-medium text-vz-ink hover:bg-vz-bg-alt disabled:opacity-50"
        >
          {sending === 'sms' ? 'Envoi…' : `Envoyer par SMS (${clientPhone})`}
        </button>
      ) : showSmsInput ? (
        <div className="flex gap-2">
          <input
            type="tel"
            value={phoneDraft}
            onChange={(e) => setPhoneDraft(e.target.value)}
            placeholder="06 12 34 56 78"
            className="flex-1 min-h-[44px] px-3 py-2 rounded-lg border border-vz-line bg-white text-vz-ink"
            autoFocus
          />
          <button
            type="button"
            disabled={!phoneLooksValid || sending === 'sms'}
            onClick={() => void handleResend('sms', phoneDraft.trim())}
            className="px-4 rounded-lg bg-vz-teal text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Envoyer
          </button>
          <button
            type="button"
            onClick={() => setShowSmsInput(false)}
            className="px-3 text-vz-ink-mute"
            aria-label="Annuler"
          >
            ✕
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowSmsInput(true)}
          className="w-full min-h-[44px] rounded-xl border border-vz-line bg-white px-4 py-2.5 text-sm font-medium text-vz-ink hover:bg-vz-bg-alt"
        >
          Envoyer par SMS…
        </button>
      )}
    </div>
  );
}
