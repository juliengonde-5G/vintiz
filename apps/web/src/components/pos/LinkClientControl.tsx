'use client';

import React, { useState } from 'react';

import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface ClientMatch {
  client_id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  membership_number: string | null;
}

function clientName(c: { first_name: string | null; last_name: string | null }): string {
  return [c.first_name, c.last_name].filter(Boolean).join(' ') || 'Cliente';
}

/**
 * Rattacher / détacher une cliente sur une transaction déjà réalisée.
 * POST /api/pos/transactions/{id}/client — la liaison ne touche pas la chaîne
 * NF525 (client_id hors hash). Réutilisé par la fiche client et l'admin.
 */
export default function LinkClientControl({
  transactionId,
  hasClient,
  onChanged,
}: {
  transactionId: string;
  hasClient: boolean;
  onChanged?: (detail: unknown) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [matches, setMatches] = useState<ClientMatch[]>([]);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const search = async () => {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setMsg('');
    setMatches([]);
    try {
      const res = await api.get(`/api/pos/clients/identify?q=${encodeURIComponent(q)}`);
      if (res.status === 404) {
        setMsg('Aucune cliente trouvée.');
        return;
      }
      if (!res.ok) throw new Error();
      const data = await res.json();
      setMatches(Array.isArray(data.matches) ? data.matches : [data]);
    } catch {
      setMsg('Recherche par email, téléphone ou n° de carte (V######).');
    } finally {
      setSearching(false);
    }
  };

  const apply = async (clientId: string | null) => {
    setBusy(true);
    setMsg('');
    try {
      const res = await api.post(`/api/pos/transactions/${transactionId}/client`, {
        client_id: clientId,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || 'Échec du rattachement');
      }
      const detail = await res.json();
      setOpen(false);
      setQuery('');
      setMatches([]);
      onChanged?.(detail);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Échec du rattachement');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <Button variant="outline" onClick={() => setOpen((v) => !v)}>
          {hasClient ? 'Changer la cliente' : 'Lier une cliente'}
        </Button>
        {hasClient && (
          <Button variant="outline" onClick={() => apply(null)} disabled={busy}>
            Détacher
          </Button>
        )}
      </div>

      {open && (
        <div className="space-y-2 rounded-lg border border-vz-line p-3">
          <div className="flex gap-2">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && search()}
              placeholder="Email, téléphone ou n° de carte (V######)"
              className="flex-1 px-3 py-2 rounded-lg border border-vz-line text-sm"
            />
            <Button onClick={search} disabled={searching}>
              {searching ? '…' : 'Chercher'}
            </Button>
          </div>
          {msg && <p className="text-xs text-red-600">{msg}</p>}
          {matches.map((m) => (
            <div
              key={m.client_id}
              className="flex items-center justify-between rounded border border-vz-line px-3 py-2"
            >
              <div className="text-sm">
                <span className="font-medium">{clientName(m)}</span>
                <span className="ml-2 text-xs text-gray-500">
                  {[m.email, m.phone, m.membership_number].filter(Boolean).join(' · ')}
                </span>
              </div>
              <Button onClick={() => apply(m.client_id)} disabled={busy}>
                Lier
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
