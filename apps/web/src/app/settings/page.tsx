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
}

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
    const res = await api.get('/api/ai/mapping/zones');
    if (res.ok) setZones(await res.json());
    setLoading(false);
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
      <main className="md:ml-64 p-6 md:p-8">
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
              {zones.length === 0 && (
                <Button onClick={initZones} disabled={loading}>Initialiser les zones</Button>
              )}
            </div>

            {loading ? (
              <Card><p className="text-gray-400 text-center py-4">Chargement...</p></Card>
            ) : zones.length === 0 ? (
              <Card><p className="text-gray-400 text-center py-4">Aucune zone configuree</p></Card>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {zones.map((z) => (
                  <Card key={z.zone_id}>
                    <h3 className="font-semibold text-black mb-1">{z.zone_name}</h3>
                    <p className="text-xs text-gray-400 mb-3">{z.description}</p>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Capacite</span>
                        <span className="text-black">{z.capacity}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Produits</span>
                        <span className="text-black">{z.product_count}</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            z.occupancy_percent > 80 ? 'bg-red-400' :
                            z.occupancy_percent > 50 ? 'bg-yellow-400' : 'bg-green-400'
                          }`}
                          style={{ width: `${Math.min(100, z.occupancy_percent)}%` }}
                        />
                      </div>
                    </div>
                  </Card>
                ))}
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
