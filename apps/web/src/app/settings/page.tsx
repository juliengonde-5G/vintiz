'use client';

import React, { useState, useEffect } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import ScoringWeightsPanel from '@/components/settings/ScoringWeightsPanel';
import { api } from '@/lib/api';

interface Category {
  id: string;
  name: string;
  gender: string;
}

interface Zone {
  zone_id: string;
  zone_name: string;
  description: string;
  capacity: number;
  product_count: number;
  occupancy_percent: number;
  product_types?: string[];
  color_code?: string;
}

const ALL_PRODUCT_TYPES = ['Robes', 'Hauts', 'Pantalons', 'Jupes', 'Vestes', 'Manteaux', 'Accessoires', 'Chaussures', 'Sacs', 'Bijoux', 'Enfant'];

interface HardwareConfig {
  receipt_printer: { enabled: boolean; model: string; host: string; port: number; width_chars: number; cut_paper: boolean };
  cash_drawer: { enabled: boolean; model: string; kick_on_cash: boolean; kick_pin: number; on_time_ms: number; off_time_ms: number };
  label_printer: { enabled: boolean; model: string; host: string; port: number; label_width_mm: number; label_height_mm: number };
  barcode_scanner: { enabled: boolean; model: string; mode: string; suffix: string; min_length: number };
  payment_terminal: { enabled: boolean; model: string; mode: string };
}

interface CompatibilityItem {
  category: string;
  label: string;
  model: string;
  connection: string;
  supported: boolean;
  notes: string;
}

interface SumUpConfig {
  environment: string;
  api_key_set: boolean;
  merchant_code_set: boolean;
  merchant_code_masked: string;
  sandbox_auto_delay_sec: number;
  api_base: string;
}

interface SandboxCheckout {
  checkout_id: string;
  checkout_reference: string;
  amount: number;
  currency: string;
  description: string;
  status: string;
  created_at: number;
  updated_at: number;
  auto_approve_in: number | null;
  manual_override: boolean;
}

interface SandboxEvent {
  timestamp: number;
  iso_time: string;
  kind: string;
  checkout_id: string;
  status: string;
  payload: Record<string, unknown>;
}

interface SandboxSnapshot {
  config: SumUpConfig;
  checkouts: SandboxCheckout[];
  events: SandboxEvent[];
}

export default function SettingsPage() {
  const [tab, setTab] = useState<'store' | 'payment' | 'cahier' | 'categories' | 'zones' | 'hardware' | 'scoring' | 'system'>('store');
  const [hardware, setHardware] = useState<HardwareConfig | null>(null);
  const [compatibility, setCompatibility] = useState<CompatibilityItem[]>([]);
  const [hwSaving, setHwSaving] = useState(false);

  // Cahier de Travail state
  const now = new Date();
  const [cahierYear, setCahierYear] = useState(now.getFullYear());
  const [cahierMonth, setCahierMonth] = useState(now.getMonth() + 1);
  const [cahierTarget, setCahierTarget] = useState('');
  const [cahierNotes, setCahierNotes] = useState('');
  const [cahierWeights, setCahierWeights] = useState<{
    weights: number[];
    weekdays: string[];
    source: string;
    sample_size_weeks: number;
    computed_at: string;
  } | null>(null);
  const [cahierLoading, setCahierLoading] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  // SumUp sandbox state
  const [sandbox, setSandbox] = useState<SandboxSnapshot | null>(null);
  const [sandboxTestAmount, setSandboxTestAmount] = useState('12.50');

  // New category form
  const [newCatName, setNewCatName] = useState('');
  const [newCatGender, setNewCatGender] = useState('femme');

  // Zone edit modal
  const [showZoneModal, setShowZoneModal] = useState(false);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);
  const [zoneForm, setZoneForm] = useState({ name: '', description: '', capacity: 20, product_types: [] as string[], color_code: '#1A7A6A' });

  useEffect(() => {
    if (tab === 'categories') loadCategories();
    if (tab === 'zones') loadZones();
    if (tab === 'hardware') loadHardware();
    if (tab === 'cahier') loadCahierData();
  }, [tab]);

  // ── SumUp sandbox: auto-refresh snapshot every 2s while payment tab is open ──
  useEffect(() => {
    if (tab !== 'payment') return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const res = await api.get('/api/pos/payments/cb/sandbox/state?limit=40');
        if (!cancelled && res.ok) setSandbox(await res.json());
      } catch { /* silent */ }
    };
    refresh();
    const handle = setInterval(refresh, 2000);
    return () => { cancelled = true; clearInterval(handle); };
  }, [tab]);

  const runSandboxTest = async () => {
    setError('');
    const amount = parseFloat(sandboxTestAmount);
    if (isNaN(amount) || amount <= 0) {
      setError('Montant invalide');
      return;
    }
    try {
      const res = await api.post('/api/pos/payments/cb/sandbox/test', {
        amount,
        description: 'Test sandbox depuis Parametres',
      });
      if (!res.ok) setError('Erreur lors du test sandbox');
    } catch { setError('Erreur de connexion'); }
  };

  const approveSandbox = async (checkoutId: string) => {
    try { await api.post(`/api/pos/payments/cb/sandbox/${checkoutId}/approve`, {}); }
    catch { setError('Erreur approbation'); }
  };

  const declineSandbox = async (checkoutId: string) => {
    try { await api.post(`/api/pos/payments/cb/sandbox/${checkoutId}/decline`, {}); }
    catch { setError('Erreur refus'); }
  };

  const clearSandbox = async () => {
    try { await api.post('/api/pos/payments/cb/sandbox/clear', {}); }
    catch { setError('Erreur reset'); }
  };

  const loadHardware = async () => {
    setLoading(true);
    try {
      const [cfgRes, compatRes] = await Promise.all([
        api.get('/api/hardware/config'),
        api.get('/api/hardware/compatibility'),
      ]);
      if (cfgRes.ok) setHardware(await cfgRes.json());
      if (compatRes.ok) {
        const data = await compatRes.json();
        setCompatibility(data.items || []);
      }
    } catch {
      setError('Erreur de chargement du materiel');
    }
    setLoading(false);
  };

  const saveHardware = async () => {
    if (!hardware) return;
    setHwSaving(true);
    setError('');
    try {
      const res = await api.put('/api/hardware/config', hardware);
      if (res.ok) {
        setHardware(await res.json());
        setMessage('Configuration materiel sauvegardee');
        setTimeout(() => setMessage(''), 3000);
      } else {
        setError('Erreur lors de la sauvegarde');
      }
    } catch {
      setError('Erreur de connexion');
    }
    setHwSaving(false);
  };

  const testReceiptPrinter = async () => {
    setError(''); setMessage('');
    try {
      const res = await api.post('/api/hardware/receipt/test', {});
      if (res.ok) setMessage('Ticket de test envoye a l\'imprimante MUNBYN');
      else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Echec du test imprimante');
      }
    } catch { setError('Erreur de connexion'); }
  };

  const kickDrawer = async () => {
    setError(''); setMessage('');
    try {
      const res = await api.post('/api/hardware/drawer/kick', {});
      if (res.ok) setMessage('Impulsion envoyee au tiroir-caisse');
      else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Echec ouverture tiroir');
      }
    } catch { setError('Erreur de connexion'); }
  };

  const testLabelPrinter = async () => {
    setError(''); setMessage('');
    try {
      const res = await api.post('/api/hardware/label/test', {});
      if (res.ok) setMessage('Etiquette de test envoyee a la SATO CT4-LX');
      else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Echec du test SATO');
      }
    } catch { setError('Erreur de connexion'); }
  };

  const loadCategories = async () => {
    setLoading(true);
    const res = await api.get('/api/inventory/categories');
    if (res.ok) setCategories(await res.json());
    setLoading(false);
  };

  const loadZones = async () => {
    setLoading(true);
    const res = await api.get('/api/admin/zones');
    if (res.ok) {
      const data = await res.json();
      setZones(data.zones || data || []);
    }
    setLoading(false);
  };

  const openZoneModal = (zone?: Zone) => {
    if (zone) {
      setEditingZone(zone);
      setZoneForm({ name: zone.zone_name, description: zone.description || '', capacity: zone.capacity, product_types: zone.product_types || [], color_code: zone.color_code || '#1A7A6A' });
    } else {
      setEditingZone(null);
      setZoneForm({ name: '', description: '', capacity: 20, product_types: [], color_code: '#1A7A6A' });
    }
    setShowZoneModal(true);
  };

  const saveZone = async () => {
    setLoading(true);
    setError('');
    try {
      const body = { name: zoneForm.name, description: zoneForm.description, capacity: zoneForm.capacity, product_types: zoneForm.product_types, color_code: zoneForm.color_code };
      const res = editingZone
        ? await api.put(`/api/admin/zones/${editingZone.zone_id}`, body)
        : await api.post('/api/admin/zones', body);
      if (res.ok) {
        setShowZoneModal(false);
        await loadZones();
        setMessage(editingZone ? 'Zone modifiée' : 'Zone créée');
        setTimeout(() => setMessage(''), 3000);
      } else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Erreur lors de la sauvegarde');
      }
    } catch { setError('Erreur de connexion'); }
    setLoading(false);
  };

  const toggleProductType = (t: string) => {
    setZoneForm(f => ({ ...f, product_types: f.product_types.includes(t) ? f.product_types.filter(x => x !== t) : [...f.product_types, t] }));
  };

  const addCategory = async () => {
    if (!newCatName.trim()) return;
    setError('');
    const res = await api.post('/api/inventory/categories', {
      name: newCatName.trim(),
      gender: newCatGender,
    });
    if (res.ok) {
      setNewCatName('');
      await loadCategories();
      setMessage('Categorie ajoutee');
      setTimeout(() => setMessage(''), 3000);
    } else {
      setError('Erreur lors de l\'ajout');
    }
  };

  const runSeed = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.post('/api/admin/seed', {});
      if (res.ok) {
        const data = await res.json();
        setMessage(data.messages?.join('\n') || 'Seed termine');
      } else {
        setError('Erreur lors du seed');
      }
    } catch {
      setError('Erreur de connexion');
    }
    setLoading(false);
  };

  const runReset = async () => {
    if (!confirm('Supprimer toutes les donnees (produits, clients, transactions, zones) ? Cette action est irreversible.')) return;
    setLoading(true);
    setError('');
    try {
      const res = await api.post('/api/admin/reset-data', {});
      if (res.ok) {
        const data = await res.json();
        const deleted = Object.entries(data.deleted || {}).map(([k, v]) => `${v} ${k}`).join(', ');
        setMessage(`Donnees supprimees : ${deleted || 'rien a supprimer'}`);
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || 'Erreur lors du reset');
      }
    } catch (e) {
      setError('Erreur de connexion: ' + (e instanceof Error ? e.message : String(e)));
    }
    setLoading(false);
  };

  const runTestData = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.post('/api/admin/test-data', {});
      if (res.ok) {
        const data = await res.json();
        if (data.status === 'skip') {
          setMessage(data.message);
        } else {
          const s = data.summary;
          setMessage(
            `Donnees de test generees :\n${s.products} produits, ${s.clients} clients, ${s.loyalty_accounts} comptes fidelite, ${s.transactions} transactions (${s.revenue} EUR)`
          );
        }
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || err.message || 'Erreur lors de la generation');
      }
    } catch (e) {
      setError('Erreur de connexion: ' + (e instanceof Error ? e.message : String(e)));
    }
    setLoading(false);
  };

  const loadCahierData = async () => {
    setCahierLoading(true);
    try {
      const [targetRes, weightsRes] = await Promise.all([
        api.get(`/api/cahier/monthly-target/${cahierYear}/${cahierMonth}`),
        api.get('/api/cahier/weekday-weights'),
      ]);
      if (targetRes.ok) {
        const t = await targetRes.json();
        setCahierTarget(t.target_eur != null ? String(t.target_eur) : '');
        setCahierNotes(t.notes || '');
      }
      if (weightsRes.ok) {
        setCahierWeights(await weightsRes.json());
      }
    } finally {
      setCahierLoading(false);
    }
  };

  const saveCahierTarget = async () => {
    const value = parseFloat(cahierTarget);
    if (!Number.isFinite(value) || value < 0) {
      setError("Montant invalide");
      return;
    }
    setCahierLoading(true);
    const res = await api.put('/api/cahier/monthly-target', {
      year: cahierYear,
      month: cahierMonth,
      target_eur: value,
      notes: cahierNotes || null,
    });
    if (res.ok) {
      setMessage(`Objectif ${cahierMonth}/${cahierYear} enregistre : ${value.toLocaleString('fr-FR')} €`);
      setTimeout(() => setMessage(''), 3000);
    } else {
      setError('Erreur enregistrement objectif');
    }
    setCahierLoading(false);
  };

  const recomputeWeights = async () => {
    setCahierLoading(true);
    const res = await api.get('/api/cahier/weekday-weights?recompute=1');
    if (res.ok) {
      setCahierWeights(await res.json());
      setMessage('Poids recalcules');
      setTimeout(() => setMessage(''), 3000);
    }
    setCahierLoading(false);
  };

  const initZones = async () => {
    setLoading(true);
    const res = await api.post('/api/ai/mapping/init-zones', {});
    if (res.ok) {
      await loadZones();
      setMessage('Zones initialisees');
      setTimeout(() => setMessage(''), 3000);
    }
    setLoading(false);
  };

  const tabs = [
    { key: 'store' as const, label: 'Boutique' },
    { key: 'payment' as const, label: 'Paiement' },
    { key: 'cahier' as const, label: 'Cahier de travail' },
    { key: 'categories' as const, label: 'Categories' },
    { key: 'zones' as const, label: 'Zones' },
    { key: 'hardware' as const, label: 'Materiel' },
    { key: 'scoring' as const, label: 'Scoring IA' },
    { key: 'system' as const, label: 'Systeme' },
  ];

  // Zones tab now redirects to dedicated /zones page (plan 2D + dashboards per zone).
  useEffect(() => {
    if (tab === 'zones' && typeof window !== 'undefined') {
      window.location.href = '/zones';
    }
  }, [tab]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-black">Parametres</h1>
          <p className="text-gray-500 mt-1">Configuration de la boutique</p>
        </div>

        {message && (
          <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm whitespace-pre-wrap">
            {message}
            <button onClick={() => setMessage('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
            <button onClick={() => setError('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-6 overflow-x-auto">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 rounded-lg min-h-[44px] whitespace-nowrap transition-colors ${
                tab === t.key
                  ? 'bg-teal text-white font-medium'
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* STORE TAB */}
        {tab === 'store' && (
          <div className="space-y-6">
            <Card title="Informations boutique">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <p className="text-sm text-gray-500 mb-1">Nom</p>
                  <p className="font-medium text-black">Vintiz</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">Type</p>
                  <p className="font-medium text-black">Boutique seconde main premium</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">Adresse</p>
                  <p className="font-medium text-black">6 rue Saint-Jacques, 27200 Vernon</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">Surface</p>
                  <p className="font-medium text-black">98 m&sup2;</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">Horaires</p>
                  <p className="font-medium text-black">Mar-Sam : 10h-19h</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">TVA</p>
                  <p className="font-medium text-black">20% (regime standard)</p>
                </div>
              </div>
            </Card>

            <Card title="Terminal de paiement">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <p className="text-sm text-gray-500 mb-1">TPE</p>
                  <p className="font-medium text-black">SumUp</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">Moyens de paiement</p>
                  <p className="font-medium text-black">CB, Especes, Cheque, Virement</p>
                </div>
              </div>
              <div className="mt-4">
                <Button variant="outline" onClick={() => setTab('payment')}>
                  Configurer / tester le sandbox SumUp
                </Button>
              </div>
            </Card>

            <Card title="Domaines">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
                <div>
                  <p className="text-sm text-gray-500 mb-1">Site vitrine</p>
                  <p className="font-medium text-teal">vintiz.fr</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">Back-office</p>
                  <p className="font-medium text-teal">app.vintiz.fr</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">API</p>
                  <p className="font-medium text-teal">api.vintiz.fr</p>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* PAYMENT TAB */}
        {tab === 'payment' && (
          <div className="space-y-6">
            <Card title="Configuration SumUp">
              {!sandbox ? (
                <p className="text-sm text-gray-500">Chargement...</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 text-sm">
                  <div>
                    <p className="text-gray-500 mb-1">Environnement</p>
                    <p className="font-medium text-black">
                      <span
                        className={`inline-block px-2 py-1 rounded ${
                          sandbox.config.environment === 'production'
                            ? 'bg-green-100 text-green-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {sandbox.config.environment.toUpperCase()}
                      </span>
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Base API</p>
                    <p className="font-mono text-black text-xs">{sandbox.config.api_base}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Cle API</p>
                    <p className="font-medium text-black">
                      {sandbox.config.api_key_set ? 'Definie' : 'Non definie (mode simulation)'}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Merchant code</p>
                    <p className="font-mono text-black">
                      {sandbox.config.merchant_code_set ? sandbox.config.merchant_code_masked : '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 mb-1">Delai auto PAID (sandbox)</p>
                    <p className="font-medium text-black">{sandbox.config.sandbox_auto_delay_sec} s</p>
                  </div>
                </div>
              )}
              <p className="text-xs text-gray-500 mt-4">
                Variables d&apos;environnement : <code className="font-mono">SUMUP_ENVIRONMENT</code>,{' '}
                <code className="font-mono">SUMUP_API_KEY</code>,{' '}
                <code className="font-mono">SUMUP_MERCHANT_CODE</code>,{' '}
                <code className="font-mono">SUMUP_SANDBOX_AUTO_DELAY_SEC</code>.
              </p>
            </Card>

            <Card title="Simulation de paiement">
              <p className="text-sm text-gray-500 mb-4">
                Cree un checkout sandbox. Le flux reproduit ce qui se passe depuis la caisse
                lorsque vous cliquez sur CB : envoi du montant et de la reference, puis polling
                du statut toutes les 3 secondes jusqu&apos;a PAID ou FAILED.
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <Input
                    type="number"
                    value={sandboxTestAmount}
                    onChange={(e) => setSandboxTestAmount(e.target.value)}
                    placeholder="Montant EUR"
                  />
                </div>
                <Button onClick={runSandboxTest}>Lancer un paiement test</Button>
                <Button variant="outline" onClick={clearSandbox}>Vider le journal</Button>
              </div>
            </Card>

            <Card title="Checkouts actifs">
              {!sandbox || sandbox.checkouts.length === 0 ? (
                <p className="text-sm text-gray-400">Aucun checkout en cours.</p>
              ) : (
                <div className="space-y-2">
                  {sandbox.checkouts.map((c) => (
                    <div
                      key={c.checkout_id}
                      className="flex items-center justify-between border border-gray-200 rounded-lg p-3"
                    >
                      <div className="text-sm">
                        <div className="font-mono text-black">{c.checkout_id}</div>
                        <div className="text-gray-500">
                          {c.amount.toFixed(2)} {c.currency} — {c.description}
                        </div>
                        <div className="mt-1">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                              c.status === 'PAID'
                                ? 'bg-green-100 text-green-800'
                                : c.status === 'FAILED' || c.status === 'CANCELLED'
                                ? 'bg-red-100 text-red-800'
                                : 'bg-amber-100 text-amber-800'
                            }`}
                          >
                            {c.status}
                          </span>
                          {c.auto_approve_in != null && c.status === 'PENDING' && (
                            <span className="text-xs text-gray-500 ml-2">
                              auto-PAID dans {c.auto_approve_in}s
                            </span>
                          )}
                        </div>
                      </div>
                      {c.status === 'PENDING' && (
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            onClick={() => approveSandbox(c.checkout_id)}
                          >
                            Approuver
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => declineSandbox(c.checkout_id)}
                          >
                            Refuser
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card title="Journal des evenements (live)">
              <p className="text-xs text-gray-500 mb-3">
                Rafraichi toutes les 2 secondes. Utile pour verifier que la caisse transmet bien
                les bonnes informations (montant, reference, description, polling).
              </p>
              {!sandbox || sandbox.events.length === 0 ? (
                <p className="text-sm text-gray-400">Aucun evenement.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-gray-200 text-gray-500">
                        <th className="py-2 pr-2">Heure</th>
                        <th className="py-2 pr-2">Type</th>
                        <th className="py-2 pr-2">Checkout</th>
                        <th className="py-2 pr-2">Statut</th>
                        <th className="py-2">Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sandbox.events.map((e, i) => (
                        <tr key={i} className="border-b border-gray-100">
                          <td className="py-2 pr-2 font-mono text-gray-500">{e.iso_time}</td>
                          <td className="py-2 pr-2 font-medium text-black">{e.kind}</td>
                          <td className="py-2 pr-2 font-mono">{e.checkout_id}</td>
                          <td className="py-2 pr-2">{e.status}</td>
                          <td className="py-2 font-mono text-gray-600">
                            {Object.keys(e.payload).length > 0
                              ? JSON.stringify(e.payload)
                              : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        )}

        {/* CATEGORIES TAB */}
        {tab === 'categories' && (
          <div className="space-y-6">
            <Card title="Ajouter une categorie">
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <Input
                    placeholder="Nom de la categorie"
                    value={newCatName}
                    onChange={(e) => setNewCatName(e.target.value)}
                  />
                </div>
                <select
                  value={newCatGender}
                  onChange={(e) => setNewCatGender(e.target.value)}
                  className="min-h-[44px] px-4 py-2 rounded-lg border border-gray-300 bg-white text-black"
                >
                  <option value="femme">Femme</option>
                  <option value="homme">Homme</option>
                  <option value="enfant">Enfant</option>
                  <option value="mixte">Mixte</option>
                </select>
                <Button onClick={addCategory}>Ajouter</Button>
              </div>
            </Card>

            <Card title="Categories existantes">
              {loading ? (
                <p className="text-gray-400 text-center py-4">Chargement...</p>
              ) : categories.length === 0 ? (
                <p className="text-gray-400 text-center py-4">Aucune categorie. Lancez le seed dans Systeme.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="pb-2 text-sm font-semibold text-gray-600">Nom</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600">Genre</th>
                      </tr>
                    </thead>
                    <tbody>
                      {categories.map((c) => (
                        <tr key={c.id} className="border-b border-gray-50">
                          <td className="py-2 text-sm text-black">{c.name}</td>
                          <td className="py-2">
                            <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                              c.gender === 'femme' ? 'bg-pink-100 text-pink-700' :
                              c.gender === 'homme' ? 'bg-blue-100 text-blue-700' :
                              c.gender === 'enfant' ? 'bg-purple-100 text-purple-700' :
                              'bg-gray-100 text-gray-700'
                            }`}>
                              {c.gender}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        )}

        {/* ZONES TAB */}
        {tab === 'zones' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-black">Zones de la boutique</h2>
              <div className="flex gap-2">
                {zones.length === 0 && <Button onClick={initZones} disabled={loading}>Initialiser les zones</Button>}
                <Button onClick={() => openZoneModal()} variant="secondary">+ Ajouter une zone</Button>
              </div>
            </div>

            {loading ? (
              <Card><p className="text-gray-400 text-center py-4">Chargement...</p></Card>
            ) : zones.length === 0 ? (
              <Card><p className="text-gray-400 text-center py-4">Aucune zone configuree. Cliquez &quot;Initialiser les zones&quot; ou &quot;Ajouter une zone&quot;.</p></Card>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {zones.map((z) => (
                  <Card key={z.zone_id}>
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: z.color_code || '#1A7A6A' }} />
                        <h3 className="font-semibold text-black">{z.zone_name}</h3>
                      </div>
                      <button onClick={() => openZoneModal(z)} className="text-xs text-teal hover:underline min-h-[32px] px-2">Modifier</button>
                    </div>
                    <p className="text-xs text-gray-400 mb-3">{z.description}</p>
                    {z.product_types && z.product_types.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-3">
                        {z.product_types.map(t => <span key={t} className="text-xs px-2 py-0.5 bg-teal-50 text-teal-700 rounded-full">{t}</span>)}
                      </div>
                    )}
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Capacité</span>
                        <span className="text-black font-medium">{z.product_count} / {z.capacity}</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div className={`h-2 rounded-full ${z.occupancy_percent > 80 ? 'bg-red-400' : z.occupancy_percent > 50 ? 'bg-yellow-400' : 'bg-green-400'}`}
                          style={{ width: `${Math.min(100, z.occupancy_percent)}%` }} />
                      </div>
                      <p className="text-xs text-gray-400 text-right">{z.occupancy_percent}% occupé</p>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {/* Zone Edit Modal */}
            {showZoneModal && (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
                  <h3 className="text-lg font-bold text-black mb-4">{editingZone ? 'Modifier la zone' : 'Nouvelle zone'}</h3>
                  <div className="space-y-4">
                    <Input label="Nom de la zone" value={zoneForm.name} onChange={e => setZoneForm(f => ({...f, name: e.target.value}))} placeholder="Ex: Vitrine gauche" />
                    <Input label="Description" value={zoneForm.description} onChange={e => setZoneForm(f => ({...f, description: e.target.value}))} placeholder="Ex: Rails mur gauche entrée" />
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Capacité max (articles)</label>
                      <input type="number" min={1} max={500} value={zoneForm.capacity} onChange={e => setZoneForm(f => ({...f, capacity: parseInt(e.target.value) || 20}))}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-2">Types de produits acceptés</label>
                      <div className="flex flex-wrap gap-2">
                        {ALL_PRODUCT_TYPES.map(t => (
                          <button key={t} type="button" onClick={() => toggleProductType(t)}
                            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${zoneForm.product_types.includes(t) ? 'bg-teal text-white border-teal' : 'bg-white text-gray-600 border-gray-300 hover:border-teal'}`}>
                            {t}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <label className="text-sm font-medium text-black">Couleur</label>
                      <input type="color" value={zoneForm.color_code} onChange={e => setZoneForm(f => ({...f, color_code: e.target.value}))} className="w-10 h-10 rounded cursor-pointer border border-gray-300" />
                      <span className="text-sm text-gray-500">{zoneForm.color_code}</span>
                    </div>
                  </div>
                  <div className="flex gap-3 mt-6">
                    <Button variant="outline" onClick={() => setShowZoneModal(false)} className="flex-1">Annuler</Button>
                    <Button onClick={saveZone} disabled={loading || !zoneForm.name} className="flex-1">{loading ? 'Sauvegarde...' : 'Sauvegarder'}</Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* HARDWARE TAB */}
        {tab === 'hardware' && (
          <div className="space-y-6">
            <Card title="Compatibilite materielle">
              <p className="text-sm text-gray-500 mb-4">
                Peripheriques supportes nativement par Vintiz. Configurez les adresses IP ci-dessous, puis lancez un test.
              </p>
              {loading && compatibility.length === 0 ? (
                <p className="text-gray-400 text-center py-4">Chargement...</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="pb-2 text-sm font-semibold text-gray-600">Peripherique</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600">Modele</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600">Connexion</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600">Statut</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compatibility.map((it) => (
                        <tr key={it.category} className="border-b border-gray-50">
                          <td className="py-2 text-sm text-black font-medium">{it.label}</td>
                          <td className="py-2 text-sm text-gray-700">{it.model}</td>
                          <td className="py-2 text-xs text-gray-500">{it.connection}</td>
                          <td className="py-2">
                            <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                              Compatible
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            {hardware && (
              <>
                <Card title="Imprimante de recus — MUNBYN 047P-WiFi">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="rp-enabled"
                        checked={hardware.receipt_printer.enabled}
                        onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, enabled: e.target.checked } })}
                        className="w-5 h-5 accent-teal"
                      />
                      <label htmlFor="rp-enabled" className="text-sm font-medium text-black">Activer l&apos;imprimante de recus</label>
                    </div>
                    <Input
                      label="Adresse IP"
                      value={hardware.receipt_printer.host}
                      onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, host: e.target.value } })}
                      placeholder="192.168.1.50"
                    />
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Port TCP</label>
                      <input
                        type="number"
                        value={hardware.receipt_printer.port}
                        onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, port: parseInt(e.target.value) || 9100 } })}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Largeur papier (caracteres)</label>
                      <input
                        type="number"
                        value={hardware.receipt_printer.width_chars}
                        onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, width_chars: parseInt(e.target.value) || 42 } })}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal"
                      />
                      <p className="text-xs text-gray-400 mt-1">42 pour du 80 mm (Font A)</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        id="rp-cut"
                        checked={hardware.receipt_printer.cut_paper}
                        onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, cut_paper: e.target.checked } })}
                        className="w-5 h-5 accent-teal"
                      />
                      <label htmlFor="rp-cut" className="text-sm text-black">Coupe automatique du papier</label>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <Button onClick={testReceiptPrinter} variant="secondary">Imprimer un ticket de test</Button>
                  </div>
                </Card>

                <Card title="Tiroir-caisse — Safescan SD-4141">
                  <p className="text-xs text-gray-500 mb-4">Connecte en RJ-12 a l&apos;imprimante de recus ci-dessus. Ouverture via commande ESC/POS.</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="cd-enabled"
                        checked={hardware.cash_drawer.enabled}
                        onChange={(e) => setHardware({ ...hardware, cash_drawer: { ...hardware.cash_drawer, enabled: e.target.checked } })}
                        className="w-5 h-5 accent-teal"
                      />
                      <label htmlFor="cd-enabled" className="text-sm font-medium text-black">Activer le tiroir-caisse</label>
                    </div>
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="cd-auto"
                        checked={hardware.cash_drawer.kick_on_cash}
                        onChange={(e) => setHardware({ ...hardware, cash_drawer: { ...hardware.cash_drawer, kick_on_cash: e.target.checked } })}
                        className="w-5 h-5 accent-teal"
                      />
                      <label htmlFor="cd-auto" className="text-sm text-black">Ouverture automatique a l&apos;encaissement especes</label>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Broche (kick pin)</label>
                      <select
                        value={hardware.cash_drawer.kick_pin}
                        onChange={(e) => setHardware({ ...hardware, cash_drawer: { ...hardware.cash_drawer, kick_pin: parseInt(e.target.value) } })}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black"
                      >
                        <option value={0}>Pin 2 (standard)</option>
                        <option value={1}>Pin 5</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <Button onClick={kickDrawer} variant="secondary">Ouvrir le tiroir (test)</Button>
                  </div>
                </Card>

                <Card title="Imprimante d&apos;etiquettes — SATO CT4-LX">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="lp-enabled"
                        checked={hardware.label_printer.enabled}
                        onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, enabled: e.target.checked } })}
                        className="w-5 h-5 accent-teal"
                      />
                      <label htmlFor="lp-enabled" className="text-sm font-medium text-black">Activer l&apos;imprimante SATO</label>
                    </div>
                    <Input
                      label="Adresse IP"
                      value={hardware.label_printer.host}
                      onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, host: e.target.value } })}
                      placeholder="192.168.1.51"
                    />
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Port TCP</label>
                      <input
                        type="number"
                        value={hardware.label_printer.port}
                        onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, port: parseInt(e.target.value) || 9100 } })}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Largeur etiquette (mm)</label>
                      <input
                        type="number"
                        value={hardware.label_printer.label_width_mm}
                        onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, label_width_mm: parseInt(e.target.value) || 50 } })}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Hauteur etiquette (mm)</label>
                      <input
                        type="number"
                        value={hardware.label_printer.label_height_mm}
                        onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, label_height_mm: parseInt(e.target.value) || 30 } })}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <Button onClick={testLabelPrinter} variant="secondary">Imprimer une etiquette de test</Button>
                  </div>
                </Card>

                <Card title="Douchette code-barres — Inateck BCST-35">
                  <p className="text-xs text-gray-500 mb-4">Fonctionne en mode clavier HID : branchez le dongle USB ou appairez en Bluetooth. Le scan remplit le champ recherche du POS et ajoute l&apos;article au panier.</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="bs-enabled"
                        checked={hardware.barcode_scanner.enabled}
                        onChange={(e) => setHardware({ ...hardware, barcode_scanner: { ...hardware.barcode_scanner, enabled: e.target.checked } })}
                        className="w-5 h-5 accent-teal"
                      />
                      <label htmlFor="bs-enabled" className="text-sm font-medium text-black">Activer le champ de scan automatique au POS</label>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Longueur minimale</label>
                      <input
                        type="number"
                        value={hardware.barcode_scanner.min_length}
                        onChange={(e) => setHardware({ ...hardware, barcode_scanner: { ...hardware.barcode_scanner, min_length: parseInt(e.target.value) || 4 } })}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal"
                      />
                    </div>
                  </div>
                </Card>

                <Card title="Terminal de paiement — SumUp">
                  <p className="text-sm text-gray-500">
                    Deja integre via l&apos;API SumUp. Configurez <code className="font-mono bg-gray-100 px-1 rounded">SUMUP_API_KEY</code> et <code className="font-mono bg-gray-100 px-1 rounded">SUMUP_MERCHANT_CODE</code> dans le fichier <code className="font-mono bg-gray-100 px-1 rounded">.env</code> du backend.
                  </p>
                </Card>

                <div className="flex justify-end gap-3">
                  <Button onClick={saveHardware} disabled={hwSaving}>
                    {hwSaving ? 'Sauvegarde...' : 'Sauvegarder la configuration'}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}

        {/* CAHIER TAB */}
        {tab === 'cahier' && (
          <div className="space-y-6">
            <Card title="Objectif mensuel de CA">
              <p className="text-sm text-gray-500 mb-4">
                Saisissez l&apos;objectif de chiffre d&apos;affaires du mois. Il est
                automatiquement reparti sur chaque journee selon le poids
                historique des jours de la semaine.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-500 mb-1">Annee</label>
                  <Input
                    type="number"
                    value={cahierYear}
                    onChange={(e) => setCahierYear(parseInt(e.target.value) || now.getFullYear())}
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-500 mb-1">Mois</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                    value={cahierMonth}
                    onChange={(e) => setCahierMonth(parseInt(e.target.value))}
                  >
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                      <option key={m} value={m}>
                        {new Date(2000, m - 1, 1).toLocaleDateString('fr-FR', { month: 'long' })}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-500 mb-1">Objectif CA (€)</label>
                  <Input
                    type="number"
                    value={cahierTarget}
                    onChange={(e) => setCahierTarget(e.target.value)}
                    placeholder="ex : 8000"
                  />
                </div>
              </div>
              <div className="mt-4">
                <label className="block text-sm text-gray-500 mb-1">Notes (optionnel)</label>
                <Input
                  type="text"
                  value={cahierNotes}
                  onChange={(e) => setCahierNotes(e.target.value)}
                  placeholder="ex : boost printemps"
                />
              </div>
              <div className="mt-4 flex gap-2">
                <Button onClick={saveCahierTarget} disabled={cahierLoading}>
                  {cahierLoading ? 'Enregistrement...' : 'Enregistrer'}
                </Button>
                <Button variant="outline" onClick={loadCahierData} disabled={cahierLoading}>
                  Recharger
                </Button>
              </div>
            </Card>

            <Card title="Distribution des ventes par jour de la semaine">
              <p className="text-sm text-gray-500 mb-4">
                Poids calcules automatiquement a partir des 12 dernieres semaines
                de ventes. En cas de donnees insuffisantes, un profil par defaut
                retail mode est applique.
              </p>
              {cahierWeights && (
                <>
                  <div className="flex items-end gap-2 h-32 mb-4">
                    {cahierWeights.weights.map((w, i) => (
                      <div key={i} className="flex-1 flex flex-col items-center">
                        <div className="flex-1 w-full flex items-end">
                          <div
                            className="w-full bg-teal rounded-t"
                            style={{ height: `${Math.max(4, w * 300)}%` }}
                            title={`${(w * 100).toFixed(1)}%`}
                          />
                        </div>
                        <div className="text-[10px] text-gray-500 mt-1 capitalize">
                          {cahierWeights.weekdays[i].slice(0, 3)}
                        </div>
                        <div className="text-[10px] font-medium text-black">
                          {(w * 100).toFixed(0)}%
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between items-center text-xs text-gray-500">
                    <span>
                      Source :{' '}
                      <span className={cahierWeights.source === 'historical' ? 'text-teal font-medium' : 'text-amber-600 font-medium'}>
                        {cahierWeights.source === 'historical'
                          ? `${cahierWeights.sample_size_weeks} semaines historiques`
                          : 'Profil par defaut (pas assez de donnees)'}
                      </span>
                    </span>
                    <Button variant="outline" onClick={recomputeWeights} disabled={cahierLoading}>
                      Recalculer
                    </Button>
                  </div>
                </>
              )}
            </Card>

            <Card title="Apercu des objectifs du mois">
              <p className="text-sm text-gray-500 mb-3">
                Somme des objectifs journaliers = objectif mensuel. Samedi
                concentre le plus gros de l&apos;objectif, lundi le moins.
              </p>
              {cahierWeights && cahierTarget && (() => {
                const monthlyTarget = parseFloat(cahierTarget) || 0;
                const daysInMonth = new Date(cahierYear, cahierMonth, 0).getDate();
                const occurrences = [0, 0, 0, 0, 0, 0, 0];
                for (let d = 1; d <= daysInMonth; d++) {
                  const jsWd = new Date(cahierYear, cahierMonth - 1, d).getDay();
                  const wd = (jsWd + 6) % 7; // convert JS Sunday=0 to Monday=0
                  occurrences[wd]++;
                }
                const totalWeight = cahierWeights.weights.reduce(
                  (acc, w, i) => acc + w * occurrences[i],
                  0,
                ) || 1;
                return (
                  <div className="grid grid-cols-7 gap-2 text-xs">
                    {cahierWeights.weekdays.map((label, i) => {
                      const dailyTarget = monthlyTarget * cahierWeights.weights[i] / totalWeight;
                      return (
                        <div key={i} className="text-center">
                          <div className="text-gray-500 capitalize">{label.slice(0, 3)}</div>
                          <div className="text-teal font-bold font-mono">{dailyTarget.toFixed(0)} €</div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
            </Card>
          </div>
        )}

        {/* SCORING IA TAB */}
        {tab === 'scoring' && (
          <ScoringWeightsPanel />
        )}

        {/* SYSTEM TAB */}
        {tab === 'system' && (
          <div className="space-y-6">
            <Card title="Initialisation">
              <p className="text-sm text-gray-500 mb-4">
                Initialise les donnees de base : categories, grilles de prix, fournisseur par defaut, zones boutique.
              </p>
              <Button onClick={runSeed} disabled={loading}>
                {loading ? 'Initialisation...' : 'Lancer le seed'}
              </Button>
            </Card>

            <Card title="Donnees de test">
              <p className="text-sm text-gray-500 mb-4">
                Genere des produits, clients, comptes fidelite et transactions realistes pour tester l&apos;application.
                Necessite d&apos;avoir lance le seed au prealable.
              </p>
              <div className="flex gap-3">
                <Button onClick={runTestData} disabled={loading} variant="secondary">
                  {loading ? 'Generation...' : 'Generer les donnees de test'}
                </Button>
              </div>
            </Card>

            <Card title="Reinitialisation">
              <p className="text-sm text-gray-500 mb-4">
                Supprime toutes les donnees (produits, clients, transactions, zones) pour repartir a zero.
                Les categories et grilles de prix sont conservees.
              </p>
              <Button onClick={runReset} disabled={loading} variant="outline">
                {loading ? 'Suppression...' : 'Reinitialiser les donnees'}
              </Button>
            </Card>

            <Card title="Informations systeme">
              <div className="space-y-3 text-sm">
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Version</span>
                  <span className="font-mono text-black">v2.0.0</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Backend</span>
                  <span className="font-mono text-black">Python 3.11 + FastAPI</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Frontend</span>
                  <span className="font-mono text-black">Next.js 14 (PWA)</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Base de donnees</span>
                  <span className="font-mono text-black">PostgreSQL 16</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">IA</span>
                  <span className="font-mono text-black">Claude Vision (Anthropic)</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Conformite</span>
                  <span className="font-mono text-black">NF525 (SHA-256 hash chain)</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-gray-500">Hebergement</span>
                  <span className="font-mono text-black">Scaleway VPS</span>
                </div>
              </div>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
