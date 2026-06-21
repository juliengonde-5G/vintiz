'use client';

/**
 * Assistant d'installation boutique (chaîne d'installation — phase 1).
 *
 * Guide le paramétrage d'une nouvelle boutique : identité & localisation,
 * fiscalité (TVA), organisation (zonage), matériel, utilisateurs, puis
 * finalisation. Réutilise les endpoints existants (shop-info, features) et
 * l'état d'installation (/admin/installation). Voir docs/MULTI_STORE.md.
 */

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface ChecklistItem { key: string; label: string; done: boolean }
interface InstallState { installed: boolean; installed_at: string; completed_steps: string[]; checklist: ChecklistItem[]; all_done: boolean }

export default function SetupPage() {
  const [state, setState] = useState<InstallState | null>(null);
  const [shop, setShop] = useState<Record<string, string>>({});
  const [zoning, setZoning] = useState(true);
  const [saving, setSaving] = useState('');
  const [toast, setToast] = useState<{ msg: string; kind: 'success' | 'error' } | null>(null);

  const notify = useCallback((msg: string, kind: 'success' | 'error' = 'success') => {
    setToast({ msg, kind }); setTimeout(() => setToast(null), 3500);
  }, []);

  const refresh = useCallback(async () => {
    const [iRes, sRes, fRes] = await Promise.all([
      api.get('/api/admin/installation'),
      api.get('/api/admin/shop-info'),
      api.get('/api/admin/features'),
    ]);
    if (iRes.ok) setState(await iRes.json());
    if (sRes.ok) setShop(await sRes.json());
    if (fRes.ok) setZoning((await fRes.json()).zoning_enabled !== false);
  }, []);

  useEffect(() => { refresh().catch(() => {}); }, [refresh]);

  const completeStep = async (key: string, extra?: Record<string, unknown>) => {
    setSaving(key);
    try {
      const res = await api.put('/api/admin/installation', { complete_step: key, ...extra });
      if (res.ok) { setState(await res.json()); notify('Étape validée'); }
      else notify('Échec', 'error');
    } catch { notify('Erreur réseau', 'error'); }
    setSaving('');
  };

  const saveIdentity = async () => {
    setSaving('identity');
    try {
      const res = await api.put('/api/admin/shop-info', {
        name: shop.name || '', address_line1: shop.address_line1 || '',
        postal_code: shop.postal_code || '', city: shop.city || '', hours: shop.hours || '',
      });
      if (res.ok) { await refresh(); notify('Identité enregistrée'); }
      else notify('Échec', 'error');
    } catch { notify('Erreur réseau', 'error'); }
    setSaving('');
  };

  const saveFiscal = async () => {
    setSaving('fiscal');
    try {
      const res = await api.put('/api/admin/shop-info', { vat_rate_percent: Number(shop.vat_rate_percent) || 20 });
      if (res.ok) { await completeStep('fiscal'); }
      else notify('Échec', 'error');
    } catch { notify('Erreur réseau', 'error'); }
    setSaving('');
  };

  const saveZoning = async (next: boolean) => {
    setSaving('zoning');
    setZoning(next);
    try {
      await api.put('/api/admin/features', { zoning_enabled: next });
      await completeStep('zoning');
    } catch { notify('Erreur réseau', 'error'); }
    setSaving('');
  };

  const finalize = async () => {
    setSaving('finalize');
    try {
      const res = await api.put('/api/admin/installation', { installed: true });
      if (res.ok) { setState(await res.json()); notify('Boutique installée 🎉'); }
      else notify('Échec', 'error');
    } catch { notify('Erreur réseau', 'error'); }
    setSaving('');
  };

  const doneSet = new Set((state?.checklist || []).filter((c) => c.done).map((c) => c.key));

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-10 md:p-8">
        <div className="max-w-3xl mx-auto space-y-5">
          <div>
            <h1 className="text-2xl font-bold text-vz-ink">Installation de la boutique</h1>
            <p className="text-sm text-vz-ink-mute">Paramétrez votre boutique étape par étape.</p>
          </div>

          {toast && (
            <div role="status" className={`px-4 py-3 rounded-xl text-sm font-medium ${toast.kind === 'success' ? 'bg-vz-teal text-white' : 'bg-red-600 text-white'}`}>
              {toast.msg}
            </div>
          )}

          {state?.installed && (
            <div className="p-4 rounded-xl bg-vz-teal-soft/50 border border-vz-teal-soft">
              <p className="text-sm font-medium text-vz-teal-deep">✓ Boutique installée{state.installed_at ? ` le ${new Date(state.installed_at).toLocaleDateString('fr-FR')}` : ''}.</p>
              <p className="text-xs text-vz-ink-soft mt-1">Vous pouvez continuer à ajuster les réglages ci-dessous à tout moment.</p>
            </div>
          )}

          {/* Progress checklist */}
          <Card title="Progression">
            <ul className="space-y-1.5">
              {(state?.checklist || []).map((c) => (
                <li key={c.key} className="flex items-center gap-2 text-sm">
                  <span className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-xs ${c.done ? 'bg-vz-teal text-white' : 'bg-vz-bg-alt text-vz-ink-mute'}`}>
                    {c.done ? '✓' : '•'}
                  </span>
                  <span className={c.done ? 'text-vz-ink' : 'text-vz-ink-mute'}>{c.label}</span>
                </li>
              ))}
            </ul>
          </Card>

          {/* Step 1 — Identity */}
          <Card title="1 · Identité & localisation">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input label="Nom de la boutique" value={shop.name || ''} onChange={(e) => setShop({ ...shop, name: e.target.value })} />
              <Input label="Horaires" value={shop.hours || ''} onChange={(e) => setShop({ ...shop, hours: e.target.value })} placeholder="Mar-Sam : 10h-19h" />
              <Input label="Adresse" value={shop.address_line1 || ''} onChange={(e) => setShop({ ...shop, address_line1: e.target.value })} />
              <div className="grid grid-cols-2 gap-2">
                <Input label="Code postal" value={shop.postal_code || ''} onChange={(e) => setShop({ ...shop, postal_code: e.target.value })} />
                <Input label="Ville" value={shop.city || ''} onChange={(e) => setShop({ ...shop, city: e.target.value })} />
              </div>
            </div>
            <div className="mt-3"><Button onClick={saveIdentity} disabled={saving === 'identity'}>Enregistrer</Button></div>
          </Card>

          {/* Step 2 — Fiscal */}
          <Card title="2 · Fiscalité (TVA)">
            <div className="flex items-end gap-3 flex-wrap">
              <Input label="Taux de TVA par défaut (%)" type="number" className="w-40"
                value={shop.vat_rate_percent ?? '20'} onChange={(e) => setShop({ ...shop, vat_rate_percent: e.target.value })} />
              <Button onClick={saveFiscal} disabled={saving === 'fiscal'}>{doneSet.has('fiscal') ? 'Mettre à jour' : 'Valider'}</Button>
            </div>
            <p className="text-xs text-vz-ink-mute mt-2">Le taux peut être affiné par produit (taux réduits) dans l&apos;inventaire.</p>
          </Card>

          {/* Step 3 — Zoning */}
          <Card title="3 · Organisation boutique (zonage)">
            <div className="flex items-start justify-between gap-4">
              <p className="text-sm text-vz-ink-soft max-w-prose">
                Activez la gestion des zones (placement produit, plan 2D, optimisation IA, KPI par zone)
                ou laissez désactivé pour une boutique sans zonage.
              </p>
              <button type="button" role="switch" aria-checked={zoning} disabled={saving === 'zoning'}
                onClick={() => saveZoning(!zoning)}
                className={`relative inline-flex h-7 w-12 flex-shrink-0 items-center rounded-full transition-colors ${zoning ? 'bg-vz-teal' : 'bg-gray-300'}`}>
                <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${zoning ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
          </Card>

          {/* Step 4 — Hardware */}
          <Card title="4 · Matériel">
            <p className="text-sm text-vz-ink-soft">Encaissement (SumUp), imprimante ticket, imprimante étiquettes &amp; format, tiroir-caisse, douchette.</p>
            <div className="flex items-center gap-3 mt-3">
              <Link href="/settings?tab=hardware"><Button variant="outline">Configurer le matériel</Button></Link>
              <Button onClick={() => completeStep('hardware')} disabled={saving === 'hardware'}>
                {doneSet.has('hardware') ? 'Validé ✓' : 'Marquer comme fait'}
              </Button>
            </div>
          </Card>

          {/* Step 5 — Users */}
          <Card title="5 · Utilisateurs & droits">
            <p className="text-sm text-vz-ink-soft">Créez les comptes manager / collaborateur et leurs PIN de caisse.</p>
            <div className="flex items-center gap-3 mt-3">
              <Link href="/admin/users"><Button variant="outline">Gérer les utilisateurs</Button></Link>
              <Button onClick={() => completeStep('users')} disabled={saving === 'users'}>
                {doneSet.has('users') ? 'Validé ✓' : 'Marquer comme fait'}
              </Button>
            </div>
          </Card>

          {/* Finalize */}
          <Card title="Finalisation">
            <p className="text-sm text-vz-ink-soft mb-3">
              {state?.all_done ? 'Toutes les étapes sont prêtes.' : 'Vous pouvez finaliser même si certaines étapes restent à compléter.'}
            </p>
            <Button onClick={finalize} disabled={saving === 'finalize'}>
              {state?.installed ? 'Boutique installée ✓' : 'Marquer la boutique comme installée'}
            </Button>
          </Card>
        </div>
      </main>
    </div>
  );
}
