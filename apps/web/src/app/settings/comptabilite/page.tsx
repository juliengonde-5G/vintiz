'use client';

import React, { useEffect, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface AccountingConfig {
  account_sales: string;
  account_tva: string;
  tva_rate: number;
  account_cash: string;
  account_card: string;
  account_cheque: string;
  account_cheque_cdc: string;
  account_avoir: string;
  account_transfer: string;
  label_sales: string;
  label_tva: string;
  label_cash: string;
  label_card: string;
  label_cheque: string;
  label_cheque_cdc: string;
  label_avoir: string;
  label_transfer: string;
  pennylane_enabled: boolean;
  pennylane_api_key_hint: string | null;
  pennylane_api_key_set: boolean;
  pennylane_journal_code: string;
  pennylane_api_url: string;
  discrepancy_alert_threshold: number;
  discrepancy_alert_email: string | null;
  daily_report_email: string;
  daily_report_enabled: boolean;
  fec_monthly_enabled: boolean;
}

const FIELD_LABEL: Record<string, string> = {
  account_sales: 'Ventes (707xxx)',
  account_tva: 'TVA collectée (44571)',
  account_cash: 'Caisse — Espèces (531xxx)',
  account_card: 'CB SumUp (512xxx)',
  account_cheque: 'Chèques (511xxx)',
  account_cheque_cdc: 'Club des Commerçants (511xxx)',
  account_avoir: 'Avoirs clients (419xxx)',
  account_transfer: 'Virements (512xxx)',
};

export default function ComptabilitePage() {
  const [cfg, setCfg] = useState<AccountingConfig | null>(null);
  const [form, setForm] = useState<Partial<AccountingConfig & { pennylane_api_key?: string }>>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ connected: boolean } | null>(null);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  useEffect(() => {
    api.get('/api/accounting/config').then(r => r.json()).then((data: AccountingConfig) => {
      setCfg(data);
      setForm({
        ...data,
        pennylane_api_key: '',
      });
    });
  }, []);

  const patch = (key: string, value: unknown) => {
    setForm(prev => ({ ...prev, [key]: value }));
    setMsg('');
    setErr('');
  };

  const save = async () => {
    setSaving(true);
    setMsg('');
    setErr('');
    try {
      const payload: Record<string, unknown> = { ...form };
      if (!payload.pennylane_api_key) delete payload.pennylane_api_key;
      await api.put('/api/accounting/config', payload).then(r => r.json());
      const updated: AccountingConfig = await api.get('/api/accounting/config').then(r => r.json());
      setCfg(updated);
      setForm({ ...updated, pennylane_api_key: '' });
      setMsg('Configuration enregistrée.');
    } catch {
      setErr('Erreur lors de la sauvegarde.');
    } finally {
      setSaving(false);
    }
  };

  const testPennylane = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await api.post('/api/accounting/pennylane/test', {}).then(r => r.json());
      setTestResult(result);
    } catch {
      setTestResult({ connected: false });
    } finally {
      setTesting(false);
    }
  };

  if (!cfg) {
    return (
      <div className="flex h-screen bg-vz-bg">
        <Sidebar />
        <main className="flex-1 flex items-center justify-center">
          <p className="text-vz-ink-mute">Chargement…</p>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-vz-bg overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
          <div>
            <h1 className="text-2xl font-display font-semibold text-vz-ink">Paramétrage comptable</h1>
            <p className="text-vz-ink-soft mt-1">Plan de comptes PCG — compatible Pennylane et FEC DGFiP.</p>
          </div>

          {msg && <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg px-4 py-3 text-sm">{msg}</div>}
          {err && <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg px-4 py-3 text-sm">{err}</div>}

          {/* Plan de comptes — Recettes */}
          <Card>
            <h2 className="font-semibold text-vz-ink mb-4">Comptes de recettes</h2>
            <div className="space-y-3">
              {(['account_sales', 'account_tva'] as const).map(key => (
                <div key={key} className="grid grid-cols-2 gap-3 items-center">
                  <label className="text-sm text-vz-ink-soft">{FIELD_LABEL[key]}</label>
                  <div className="flex gap-2">
                    <Input
                      value={(form as any)[key] || ''}
                      onChange={e => patch(key, e.target.value)}
                      placeholder="ex: 707100"
                      className="font-mono text-sm"
                    />
                    <Input
                      value={(form as any)[key.replace('account_', 'label_')] || ''}
                      onChange={e => patch(key.replace('account_', 'label_'), e.target.value)}
                      placeholder="Libellé"
                      className="text-sm"
                    />
                  </div>
                </div>
              ))}
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">Taux TVA (%)</label>
                <Input
                  type="number"
                  value={form.tva_rate ?? 20}
                  onChange={e => patch('tva_rate', parseFloat(e.target.value))}
                  className="font-mono text-sm w-32"
                />
              </div>
            </div>
          </Card>

          {/* Plan de comptes — Encaissements */}
          <Card>
            <h2 className="font-semibold text-vz-ink mb-4">Comptes d'encaissement par mode de paiement</h2>
            <p className="text-xs text-vz-ink-mute mb-4">Chaque mode de paiement correspond à un compte PCG distinct. Format : N° compte · Libellé.</p>
            <div className="space-y-3">
              {(['account_cash', 'account_card', 'account_cheque', 'account_cheque_cdc', 'account_avoir', 'account_transfer'] as const).map(key => (
                <div key={key} className="grid grid-cols-2 gap-3 items-center">
                  <label className="text-sm text-vz-ink-soft">{FIELD_LABEL[key]}</label>
                  <div className="flex gap-2">
                    <Input
                      value={(form as any)[key] || ''}
                      onChange={e => patch(key, e.target.value)}
                      placeholder="ex: 531000"
                      className="font-mono text-sm"
                    />
                    <Input
                      value={(form as any)[key.replace('account_', 'label_')] || ''}
                      onChange={e => patch(key.replace('account_', 'label_'), e.target.value)}
                      placeholder="Libellé"
                      className="text-sm"
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Pennylane */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-vz-ink">Pennylane</h2>
              <label className="flex items-center gap-2 cursor-pointer">
                <div
                  onClick={() => patch('pennylane_enabled', !form.pennylane_enabled)}
                  className={`relative w-10 h-6 rounded-full transition-colors ${form.pennylane_enabled ? 'bg-vz-teal' : 'bg-gray-200'}`}
                >
                  <span className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${form.pennylane_enabled ? 'left-5' : 'left-1'}`} />
                </div>
                <span className="text-sm text-vz-ink-soft">Activé</span>
              </label>
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">Clé API Bearer</label>
                <div>
                  <Input
                    type="password"
                    value={form.pennylane_api_key || ''}
                    onChange={e => patch('pennylane_api_key', e.target.value)}
                    placeholder={cfg.pennylane_api_key_set ? `Configurée (${cfg.pennylane_api_key_hint})` : 'Nouvelle clé API…'}
                  />
                  <p className="text-xs text-vz-ink-mute mt-1">Laisser vide pour conserver la clé existante.</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">Code journal</label>
                <Input
                  value={form.pennylane_journal_code || ''}
                  onChange={e => patch('pennylane_journal_code', e.target.value)}
                  placeholder="VTE"
                  className="font-mono text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">URL API</label>
                <Input
                  value={form.pennylane_api_url || ''}
                  onChange={e => patch('pennylane_api_url', e.target.value)}
                  placeholder="https://app.pennylane.com/api/external/v1"
                  className="font-mono text-sm"
                />
              </div>
              {cfg.pennylane_api_key_set && (
                <div className="flex items-center gap-3 pt-2">
                  <Button variant="secondary" size="sm" onClick={testPennylane} disabled={testing}>
                    {testing ? 'Test en cours…' : 'Tester la connexion'}
                  </Button>
                  {testResult !== null && (
                    <span className={`text-sm font-medium ${testResult.connected ? 'text-green-600' : 'text-red-600'}`}>
                      {testResult.connected ? '✓ Connecté' : '✗ Échec de connexion'}
                    </span>
                  )}
                </div>
              )}
            </div>
          </Card>

          {/* Alertes & Email */}
          <Card>
            <h2 className="font-semibold text-vz-ink mb-4">Alertes et rapports</h2>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">Seuil alerte écart caisse (€)</label>
                <Input
                  type="number"
                  value={form.discrepancy_alert_threshold ?? 5}
                  onChange={e => patch('discrepancy_alert_threshold', parseFloat(e.target.value))}
                  className="font-mono text-sm w-32"
                />
              </div>
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">Email alerte écart</label>
                <Input
                  value={form.discrepancy_alert_email || ''}
                  onChange={e => patch('discrepancy_alert_email', e.target.value)}
                  placeholder="comptable@domaine.fr"
                />
              </div>
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">Email rapport quotidien</label>
                <Input
                  value={form.daily_report_email || ''}
                  onChange={e => patch('daily_report_email', e.target.value)}
                  placeholder="vernon@vintiz.fr"
                />
              </div>
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">Rapport quotidien actif</label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.daily_report_enabled ?? true}
                    onChange={e => patch('daily_report_enabled', e.target.checked)}
                    className="w-4 h-4 accent-vz-teal"
                  />
                  <span className="text-sm text-vz-ink-soft">Envoyer à chaque clôture</span>
                </label>
              </div>
              <div className="grid grid-cols-2 gap-3 items-center">
                <label className="text-sm text-vz-ink-soft">FEC mensuel</label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.fec_monthly_enabled ?? true}
                    onChange={e => patch('fec_monthly_enabled', e.target.checked)}
                    className="w-4 h-4 accent-vz-teal"
                  />
                  <span className="text-sm text-vz-ink-soft">Activer le FEC mensuel d'audit</span>
                </label>
              </div>
            </div>
          </Card>

          <div className="flex justify-end gap-3 pb-8">
            <Button variant="secondary" onClick={() => { setForm({ ...cfg, pennylane_api_key: '' }); setMsg(''); setErr(''); }}>
              Annuler
            </Button>
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
