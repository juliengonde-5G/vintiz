'use client';

import React, { useState, useEffect } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
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

export default function SettingsPage() {
  const [tab, setTab] = useState<'store' | 'categories' | 'zones' | 'system'>('store');
  const [categories, setCategories] = useState<Category[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

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
  }, [tab]);

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
    { key: 'categories' as const, label: 'Categories' },
    { key: 'zones' as const, label: 'Zones' },
    { key: 'system' as const, label: 'Systeme' },
  ];

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
