'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Modal from '@/components/ui/Modal';
import { api } from '@/lib/api';

interface UserRow {
  id: string;
  username: string;
  email: string;
  role: 'manager' | 'collaborateur';
  is_active: boolean;
  has_pin: boolean;
}

const PIN_LENGTH = 4;
const ROLE_LABEL: Record<UserRow['role'], string> = {
  manager: 'Admin',
  collaborateur: 'Collaborateur',
};
const ROLE_BADGE: Record<UserRow['role'], string> = {
  manager: 'bg-vz-teal/10 text-vz-teal',
  collaborateur: 'bg-vz-accent-soft/10 text-vz-accent',
};

interface CreateDraft {
  username: string;
  email: string;
  password: string;
  role: UserRow['role'];
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  // Edit modal (role / email / active)
  const [editing, setEditing] = useState<UserRow | null>(null);

  // Create modal
  const [creating, setCreating] = useState(false);
  const [createDraft, setCreateDraft] = useState<CreateDraft>({
    username: '', email: '', password: '', role: 'collaborateur',
  });

  // PIN modal (existant)
  const [pinUser, setPinUser] = useState<UserRow | null>(null);
  const [pinDraft, setPinDraft] = useState('');
  const [pinSaving, setPinSaving] = useState(false);

  // Reset password output
  const [resetResult, setResetResult] = useState<{ user: string; password: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/admin/users');
      if (res.ok) {
        const data = await res.json();
        setUsers(data || []);
        setError('');
      } else if (res.status === 403) {
        setError('Accès réservé aux administrateurs.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const flash = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(''), 3000);
  };

  const createUser = async () => {
    setError('');
    if (createDraft.password.length < 8) {
      setError('Mot de passe trop court (8 char. min)');
      return;
    }
    try {
      const res = await api.post('/api/admin/users', createDraft);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'Création échouée');
        return;
      }
      setCreating(false);
      setCreateDraft({ username: '', email: '', password: '', role: 'collaborateur' });
      flash('Utilisateur créé');
      load();
    } catch (e: any) {
      setError(e?.message || 'Erreur réseau');
    }
  };

  const saveEdit = async () => {
    if (!editing) return;
    try {
      const res = await api.put(`/api/admin/users/${editing.id}`, {
        email: editing.email,
        role: editing.role,
        is_active: editing.is_active,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'Modification échouée');
        return;
      }
      setEditing(null);
      flash('Utilisateur mis à jour');
      load();
    } catch (e: any) {
      setError(e?.message || 'Erreur réseau');
    }
  };

  const resetPassword = async (u: UserRow) => {
    if (!confirm(`Réinitialiser le mot de passe de ${u.username} ?`)) return;
    try {
      const res = await api.post(`/api/admin/users/${u.id}/reset-password`, {});
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'Reset échoué');
        return;
      }
      const data = await res.json();
      setResetResult({ user: u.username, password: data.new_password });
    } catch (e: any) {
      setError(e?.message || 'Erreur réseau');
    }
  };

  const setPin = async () => {
    if (!pinUser) return;
    if (pinDraft.length !== PIN_LENGTH || !/^\d+$/.test(pinDraft)) {
      setError(`Le PIN doit faire exactement ${PIN_LENGTH} chiffres`);
      return;
    }
    setPinSaving(true);
    try {
      const res = await api.post('/api/pos/cashier/set-pin', {
        user_id: pinUser.id,
        pin: pinDraft,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'Erreur PIN');
        return;
      }
      setPinUser(null);
      setPinDraft('');
      flash('PIN mis à jour');
      load();
    } catch (e: any) {
      setError(e?.message || 'Erreur réseau');
    }
    setPinSaving(false);
  };

  const clearPin = async (u: UserRow) => {
    if (!confirm(`Retirer le PIN de ${u.username} ?`)) return;
    try {
      await api.post('/api/pos/cashier/clear-pin', { user_id: u.id });
      flash('PIN supprimé');
      load();
    } catch (e: any) {
      setError(e?.message || 'Erreur réseau');
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-vz-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto md:ml-64 p-4 md:p-8">
        <header className="mb-6 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-black font-display">Utilisateurs</h1>
            <p className="text-sm text-gray-500 mt-1">
              Gestion des comptes et rôles. Les administrateurs ont accès à toute l’application ;
              les collaborateurs voient Caisse, Inventaire, Espaces, Clients et Compagnon IA.
            </p>
          </div>
          <Button onClick={() => setCreating(true)}>+ Nouvel utilisateur</Button>
        </header>

        {message && <div className="p-3 mb-4 bg-green-50 text-green-700 rounded-lg text-sm">{message}</div>}
        {error && <div className="p-3 mb-4 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

        {resetResult && (
          <Card className="mb-4">
            <p className="text-sm">
              Nouveau mot de passe pour <strong>{resetResult.user}</strong> :
              <code className="ml-2 px-2 py-0.5 bg-gray-100 rounded font-mono">{resetResult.password}</code>
            </p>
            <p className="text-xs text-gray-500 mt-1">Communiquez-le à l’utilisateur, il ne sera plus affiché.</p>
            <Button size="sm" variant="outline" className="mt-2" onClick={() => setResetResult(null)}>Fermer</Button>
          </Card>
        )}

        <Card>
          {loading && <p className="text-sm text-gray-500">Chargement…</p>}
          {!loading && users.length === 0 && (
            <p className="text-sm text-gray-500">Aucun utilisateur.</p>
          )}
          {users.length > 0 && (
            <table className="w-full text-sm">
              <thead className="text-xs text-gray-500 uppercase">
                <tr>
                  <th className="text-left py-2">Username</th>
                  <th className="text-left">Email</th>
                  <th className="text-center">Rôle</th>
                  <th className="text-center">PIN POS</th>
                  <th className="text-center">Actif</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className={`border-t border-gray-100 ${u.is_active ? '' : 'opacity-50'}`}>
                    <td className="py-2 font-medium">{u.username}</td>
                    <td className="text-xs text-gray-500">{u.email}</td>
                    <td className="text-center">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${ROLE_BADGE[u.role]}`}>
                        {ROLE_LABEL[u.role]}
                      </span>
                    </td>
                    <td className="text-center text-xs">{u.has_pin ? '✓' : '—'}</td>
                    <td className="text-center text-xs">{u.is_active ? 'Actif' : 'Inactif'}</td>
                    <td className="text-right text-xs space-x-2">
                      <button className="text-vz-teal hover:underline" onClick={() => setEditing(u)}>Éditer</button>
                      <button className="text-vz-teal hover:underline" onClick={() => { setPinUser(u); setPinDraft(''); }}>
                        {u.has_pin ? 'Changer PIN' : 'Définir PIN'}
                      </button>
                      {u.has_pin && (
                        <button className="text-gray-500 hover:underline" onClick={() => clearPin(u)}>Retirer PIN</button>
                      )}
                      <button className="text-orange-600 hover:underline" onClick={() => resetPassword(u)}>Reset MDP</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </main>

      {/* Create modal */}
      {creating && (
        <Modal open onClose={() => setCreating(false)} title="Nouvel utilisateur">
          <div className="space-y-3 text-sm">
            <div>
              <label className="text-xs text-gray-500">Username</label>
              <input value={createDraft.username}
                onChange={(e) => setCreateDraft({ ...createDraft, username: e.target.value })}
                className="w-full px-3 py-2 border border-gray-200 rounded" />
            </div>
            <div>
              <label className="text-xs text-gray-500">Email</label>
              <input type="email" value={createDraft.email}
                onChange={(e) => setCreateDraft({ ...createDraft, email: e.target.value })}
                className="w-full px-3 py-2 border border-gray-200 rounded" />
            </div>
            <div>
              <label className="text-xs text-gray-500">Mot de passe (8 char. min)</label>
              <input type="password" value={createDraft.password}
                onChange={(e) => setCreateDraft({ ...createDraft, password: e.target.value })}
                className="w-full px-3 py-2 border border-gray-200 rounded" />
            </div>
            <div>
              <label className="text-xs text-gray-500">Rôle</label>
              <select value={createDraft.role}
                onChange={(e) => setCreateDraft({ ...createDraft, role: e.target.value as UserRow['role'] })}
                className="w-full px-3 py-2 border border-gray-200 rounded">
                <option value="collaborateur">Collaborateur</option>
                <option value="manager">Admin</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setCreating(false)}>Annuler</Button>
              <Button onClick={createUser}>Créer</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Edit modal */}
      {editing && (
        <Modal open onClose={() => setEditing(null)} title={`Éditer · ${editing.username}`}>
          <div className="space-y-3 text-sm">
            <div>
              <label className="text-xs text-gray-500">Email</label>
              <input value={editing.email}
                onChange={(e) => setEditing({ ...editing, email: e.target.value })}
                className="w-full px-3 py-2 border border-gray-200 rounded" />
            </div>
            <div>
              <label className="text-xs text-gray-500">Rôle</label>
              <select value={editing.role}
                onChange={(e) => setEditing({ ...editing, role: e.target.value as UserRow['role'] })}
                className="w-full px-3 py-2 border border-gray-200 rounded">
                <option value="collaborateur">Collaborateur</option>
                <option value="manager">Admin</option>
              </select>
            </div>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={editing.is_active}
                onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />
              <span>Compte actif</span>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setEditing(null)}>Annuler</Button>
              <Button onClick={saveEdit}>Enregistrer</Button>
            </div>
          </div>
        </Modal>
      )}

      {/* PIN modal */}
      {pinUser && (
        <Modal open onClose={() => setPinUser(null)} title={`PIN · ${pinUser.username}`}>
          <div className="space-y-3 text-sm">
            <p className="text-xs text-gray-500">
              {pinUser.has_pin ? 'Saisis un nouveau PIN à 4 chiffres' : 'Définis un PIN à 4 chiffres'}
            </p>
            <input
              type="password"
              inputMode="numeric"
              maxLength={PIN_LENGTH}
              value={pinDraft}
              onChange={(e) => setPinDraft(e.target.value.replace(/\D/g, '').slice(0, PIN_LENGTH))}
              className="w-full px-3 py-2 border border-gray-200 rounded text-center font-mono text-xl tracking-widest"
              placeholder="••••"
            />
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setPinUser(null)}>Annuler</Button>
              <Button onClick={setPin} disabled={pinSaving}>{pinSaving ? 'Enregistrement…' : 'Enregistrer'}</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
