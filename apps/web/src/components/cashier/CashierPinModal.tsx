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

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/60"
        onClick={dismissible ? onCancel : undefined}
      />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <div className="text-center mb-6">
          <h2 className="text-xl font-bold text-black">
            Identification cashier
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            Saisissez votre PIN à 4 chiffres
          </p>
        </div>

        {/* PIN display: 4 dots */}
        <div className="flex justify-center gap-3 mb-4">
          {Array.from({ length: PIN_LENGTH }).map((_, i) => (
            <div
              key={i}
              className={`w-4 h-4 rounded-full border-2 transition-colors ${
                i < pin.length
                  ? 'bg-teal border-teal'
                  : 'bg-white border-gray-300'
              }`}
            />
          ))}
        </div>

        {/* Status line: error or loading */}
        <div className="h-6 text-center mb-4">
          {submitting && (
            <span className="text-sm text-gray-500">Vérification…</span>
          )}
          {!submitting && error && (
            <span className="text-sm text-red-600 font-medium">{error}</span>
          )}
        </div>

        {/* Numeric keypad */}
        <div className="grid grid-cols-3 gap-3">
          {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => press(d)}
              disabled={submitting}
              className="py-5 rounded-xl text-2xl font-bold bg-white border border-gray-200 text-black hover:bg-pink-50 hover:border-pink-200 active:scale-95 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {d}
            </button>
          ))}
          {/* Bottom row: blank | 0 | back */}
          <div />
          <button
            type="button"
            onClick={() => press('0')}
            disabled={submitting}
            className="py-5 rounded-xl text-2xl font-bold bg-white border border-gray-200 text-black hover:bg-pink-50 hover:border-pink-200 active:scale-95 transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            0
          </button>
          <button
            type="button"
            onClick={back}
            disabled={submitting || pin.length === 0}
            className="py-5 rounded-xl text-2xl font-bold bg-red-50 text-red-500 hover:bg-red-100 active:scale-95 transition-all shadow-sm disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Effacer"
          >
            ⌫
          </button>
        </div>

        {dismissible && onCancel && (
          <div className="mt-5 text-center">
            <button
              type="button"
              onClick={onCancel}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Annuler
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
