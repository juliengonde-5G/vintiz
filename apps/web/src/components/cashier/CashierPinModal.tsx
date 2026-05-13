'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface Cashier {
  id: string;
  username: string;
  role: string;
}

interface CashierPinModalProps {
  open: boolean;
  onAuthenticated: (cashier: Cashier) => void;
  onCancel?: () => void;
  /** When true, the user can dismiss the modal (shift change). When false
   *  (initial session), the modal is mandatory. */
  dismissible?: boolean;
}

const PIN_LENGTH = 4;

export default function CashierPinModal({
  open,
  onAuthenticated,
  onCancel,
  dismissible = false,
}: CashierPinModalProps) {
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setPin('');
      setError('');
      setSubmitting(false);
    }
  }, [open]);

  const submit = async (fullPin: string) => {
    setSubmitting(true);
    setError('');
    try {
      const res = await api.post('/api/pos/cashier/login', { pin: fullPin });
      if (res.ok) {
        const cashier: Cashier = await res.json();
        onAuthenticated(cashier);
      } else if (res.status === 401) {
        setError('PIN incorrect');
        setPin('');
      } else if (res.status === 400) {
        setError('PIN invalide (4 chiffres requis)');
        setPin('');
      } else {
        setError('Erreur de connexion');
        setPin('');
      }
    } catch {
      setError('Erreur réseau');
      setPin('');
    }
    setSubmitting(false);
  };

  const press = (digit: string) => {
    if (submitting || pin.length >= PIN_LENGTH) return;
    const next = pin + digit;
    setPin(next);
    setError('');
    if (next.length === PIN_LENGTH) {
      submit(next);
    }
  };

  const back = () => {
    if (submitting) return;
    setPin(pin.slice(0, -1));
    setError('');
  };

  if (!open) return null;

  // Odoo 17-style fullscreen login. Dark teal gradient, large PIN dots,
  // big touch-friendly keypad. Replaces the previous centered modal card —
  // matches the cashier login screen that ships with Odoo POS.
  return (
    <div className="fixed inset-0 z-[60] bg-gradient-to-br from-vz-teal-deep via-[#0a3c33] to-vz-teal flex flex-col">
      {/* Header */}
      <header className="flex-shrink-0 flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3 text-white">
          <img
            src="/logo-teal.png"
            alt="Vintiz"
            className="h-9 w-auto brightness-0 invert"
            draggable={false}
          />
          <div className="leading-tight">
            <p className="font-display font-bold text-lg tracking-wide">VINTIZ</p>
            <p className="text-[10px] uppercase tracking-[0.22em] opacity-70">Caisse</p>
          </div>
        </div>
        {dismissible && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="text-white/70 hover:text-white text-sm px-4 py-2 rounded-lg hover:bg-white/10 transition-colors min-h-[44px]"
          >
            Annuler
          </button>
        )}
      </header>

      {/* Centered content */}
      <div className="flex-1 flex items-center justify-center px-6 pb-12">
        <div className="w-full max-w-md text-center">
          {/* Avatar circle */}
          <div className="mx-auto w-24 h-24 rounded-full bg-white/10 border-2 border-white/20 flex items-center justify-center mb-6 backdrop-blur-sm">
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-white"
            >
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>

          <h1 className="font-display text-3xl text-white mb-2">Identification</h1>
          <p className="text-white/70 text-sm mb-8">
            Saisissez votre PIN à {PIN_LENGTH} chiffres
          </p>

          {/* PIN dots */}
          <div className="flex justify-center gap-4 mb-6">
            {Array.from({ length: PIN_LENGTH }).map((_, i) => (
              <div
                key={i}
                className={`w-5 h-5 rounded-full transition-all ${
                  i < pin.length
                    ? 'bg-vz-accent scale-110 shadow-lg shadow-vz-accent/50'
                    : 'bg-white/10 border-2 border-white/30'
                }`}
              />
            ))}
          </div>

          {/* Status */}
          <div className="h-7 mb-6">
            {submitting && (
              <span className="text-sm text-white/70">Vérification…</span>
            )}
            {!submitting && error && (
              <span className="text-sm text-vz-accent font-medium px-3 py-1 rounded-full bg-vz-accent/10 inline-block">
                {error}
              </span>
            )}
          </div>

          {/* Numeric keypad — large Odoo-style buttons */}
          <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto">
            {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => press(d)}
                disabled={submitting}
                className="aspect-square rounded-2xl text-3xl font-bold bg-white/5 hover:bg-white/15 active:bg-white/25 active:scale-95 border border-white/10 text-white transition-all shadow-lg disabled:opacity-30 disabled:cursor-not-allowed min-h-[72px]"
              >
                {d}
              </button>
            ))}
            <div />
            <button
              type="button"
              onClick={() => press('0')}
              disabled={submitting}
              className="aspect-square rounded-2xl text-3xl font-bold bg-white/5 hover:bg-white/15 active:bg-white/25 active:scale-95 border border-white/10 text-white transition-all shadow-lg disabled:opacity-30 disabled:cursor-not-allowed min-h-[72px]"
            >
              0
            </button>
            <button
              type="button"
              onClick={back}
              disabled={submitting || pin.length === 0}
              className="aspect-square rounded-2xl text-2xl font-bold bg-vz-accent/20 hover:bg-vz-accent/40 active:scale-95 border border-vz-accent/30 text-white transition-all shadow-lg disabled:opacity-20 disabled:cursor-not-allowed min-h-[72px] flex items-center justify-center"
              aria-label="Effacer"
            >
              ⌫
            </button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="flex-shrink-0 text-center pb-6">
        <p className="text-white/40 text-[11px] tracking-wider">
          Vintiz Vernon · Caisse iPad / Lenovo
        </p>
      </footer>
    </div>
  );
}
