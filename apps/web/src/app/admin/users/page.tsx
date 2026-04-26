'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';

interface CashierRow {
  id: string;
  username: string;
  role: string;
  is_active: boolean;
  has_pin: boolean;
}

const PIN_LENGTH = 4;

export default function AdminUsersPage() {
  const [users, setUsers] = useState<CashierRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState<CashierRow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/pos/cashier/list');
      if (res.ok) {
        setUsers(await res.json());
        setError('');
      } else if (res.status === 403) {
        setError('Accès réservé aux managers.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex h-screen overflow-hidden bg-cream">
      <Sidebar />
      <main className="flex-1 overflow-y-auto md:ml-64 p-4 md:p-8">
        <header className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-black font-display">
              Utilisateurs &amp; PIN cashier
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Gérez les codes PIN à 4 chiffres utilisés au POS pour identifier
              le cashier sur chaque transaction (NF525).
            </p>
          </div>
        </header>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        <Card>
          {loading ? (
            <div className="p-8 text-center text-gray-400">Chargement…</div>
          ) : users.length === 0 ? (
            <div className="p-8 text-center text-gray-400">Aucun utilisateur</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="py-3 px-4 font-semibold text-gray-600">Utilisateur</th>
                    <th className="py-3 px-4 font-semibold text-gray-600">Rôle</th>
                    <th className="py-3 px-4 font-semibold text-gray-600">Statut</th>
                    <th className="py-3 px-4 font-semibold text-gray-600">PIN</th>
                    <th className="py-3 px-4 font-semibold text-gray-600 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4 font-medium text-black">{u.username}</td>
                      <td className="py-3 px-4 text-gray-600">
                        {u.role === 'manager' ? 'Manager' : 'Collaborateur'}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                          u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                        }`}>
                          {u.is_active ? 'Actif' : 'Désactivé'}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        {u.has_pin ? (
                          <span className="inline-flex items-center gap-1 text-teal text-xs font-medium">
                            <span className="w-2 h-2 rounded-full bg-teal" /> Configuré
                          </span>
                        ) : (
                          <span className="text-gray-400 text-xs">Aucun</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Button
                          variant="secondary"
                          onClick={() => setEditing(u)}
                        >
                          {u.has_pin ? 'Changer / Retirer' : 'Définir PIN'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </main>

      {editing && (
        <PinEditModal
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load(); }}
        />
      )}
    </div>
  );
}


interface PinEditModalProps {
  user: CashierRow;
  onClose: () => void;
  onSaved: () => void;
}

function PinEditModal({ user, onClose, onSaved }: PinEditModalProps) {
  const [pin, setPin] = useState('');
  const [confirmPin, setConfirmPin] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const validFormat = /^\d{4}$/.test(pin);
  const matches = pin && pin === confirmPin;
  const canSave = validFormat && matches && !busy;

  const setPinDigit = (val: string, target: 'pin' | 'confirm') => {
    const cleaned = val.replace(/\D/g, '').slice(0, PIN_LENGTH);
    if (target === 'pin') setPin(cleaned);
    else setConfirmPin(cleaned);
    setMsg('');
  };

  const save = async () => {
    setBusy(true);
    setMsg('');
    try {
      const res = await api.post('/api/pos/cashier/set-pin', {
        user_id: user.id,
        pin,
      });
      if (res.ok) {
        onSaved();
      } else if (res.status === 403) {
        setMsg('Réservé aux managers.');
      } else {
        const err = await res.json().catch(() => null);
        setMsg(err?.detail || 'Erreur lors de l\'enregistrement.');
      }
    } catch {
      setMsg('Erreur réseau.');
    }
    setBusy(false);
  };

  const clear = async () => {
    if (!user.has_pin) return;
    if (!confirm(`Retirer le PIN de ${user.username} ? Cet utilisateur ne pourra plus s'identifier au POS tant qu'un nouveau PIN n'est pas défini.`)) return;
    setBusy(true);
    setMsg('');
    try {
      const res = await api.post('/api/pos/cashier/clear-pin', { user_id: user.id });
      if (res.ok) {
        onSaved();
      } else if (res.status === 403) {
        setMsg('Réservé aux managers.');
      } else {
        setMsg('Erreur lors de la suppression.');
      }
    } catch {
      setMsg('Erreur réseau.');
    }
    setBusy(false);
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title={`PIN de ${user.username}`}
      actions={
        <>
          {user.has_pin && (
            <Button variant="secondary" onClick={clear} disabled={busy}>
              Retirer le PIN
            </Button>
          )}
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            Annuler
          </Button>
          <Button onClick={save} disabled={!canSave}>
            {user.has_pin ? 'Changer le PIN' : 'Définir le PIN'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-gray-500">
          Saisissez un code à 4 chiffres. Il sera demandé à {user.username} à
          l&apos;ouverture de session POS.
        </p>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Nouveau PIN
          </label>
          <input
            type="password"
            inputMode="numeric"
            pattern="\d*"
            maxLength={PIN_LENGTH}
            autoComplete="new-password"
            value={pin}
            onChange={(e) => setPinDigit(e.target.value, 'pin')}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-2xl text-center tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-teal"
            placeholder="••••"
          />
          {pin && !validFormat && (
            <p className="mt-1 text-xs text-red-600">
              Le PIN doit contenir exactement 4 chiffres.
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Confirmer le PIN
          </label>
          <input
            type="password"
            inputMode="numeric"
            pattern="\d*"
            maxLength={PIN_LENGTH}
            autoComplete="new-password"
            value={confirmPin}
            onChange={(e) => setPinDigit(e.target.value, 'confirm')}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-2xl text-center tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-teal"
            placeholder="••••"
          />
          {confirmPin && pin !== confirmPin && (
            <p className="mt-1 text-xs text-red-600">
              Les deux PINs ne correspondent pas.
            </p>
          )}
        </div>

        {msg && <div className="p-2 bg-red-50 text-red-700 rounded text-sm">{msg}</div>}
      </div>
    </Modal>
  );
}
