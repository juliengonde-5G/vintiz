'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Badge from '@/components/ui/Badge';
import PhotoGallery from '@/components/inventory/PhotoGallery';
import { api } from '@/lib/api';

interface ProductDetail {
  id: string;
  barcode: string;
  name: string;
  brand: string | null;
  category: { id: string; name: string } | null;
  size: string | null;
  color: string | null;
  purchase_price: number;
  sale_price: number;
  status: string;
  week_number: number | null;
  shelf_date: string | null;
  description: string | null;
  photo_url: string | null;
  trend_score: number | null;
  zone_id: string | null;
}

interface ScoreDetail {
  total_score: number;
  score_age: number;
  score_prix: number;
  score_condition: number;
  score_brand: number;
  score_category: number;
  score_photos: number;
  action: string;
  action_color: string;
  days_on_shelf: number | null;
}

interface Transaction {
  id: string;
  transaction_number: number;
  total_ttc: number;
  created_at: string;
}

const statusOptions = [
  { value: 'stock', label: 'En stock' },
  { value: 'display', label: 'En vitrine' },
  { value: 'sold', label: 'Vendu' },
  { value: 'returned', label: 'Retourné' },
];

const statusVariants: Record<string, 'stock' | 'display' | 'sold' | 'returned'> = {
  stock: 'stock', display: 'display', sold: 'sold', returned: 'returned',
};

function ScoreBar({ value, max = 20, label }: { value: number; max?: number; label: string }) {
  const pct = Math.round((value / max) * 100);
  const color = pct >= 70 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-gray-600 w-36 shrink-0">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-sm font-medium text-gray-700 w-12 text-right">{value}/{max}</span>
    </div>
  );
}

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const productId = params.id as string;

  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [score, setScore] = useState<ScoreDetail | null>(null);
  const [transactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  // Edit state
  const [editing, setEditing] = useState<Partial<ProductDetail>>({});
  const [isEditing, setIsEditing] = useState(false);

  // Label modal
  const [showLabel, setShowLabel] = useState(false);
  const [labelUrl, setLabelUrl] = useState('');
  const [labelLoading, setLabelLoading] = useState(false);
  const [satoSending, setSatoSending] = useState(false);
  const [satoMsg, setSatoMsg] = useState('');

  const fetchProduct = useCallback(async () => {
    setLoading(true);
    try {
      const [prodRes, scoreRes] = await Promise.all([
        api.get(`/api/inventory/products/${productId}`),
        api.get(`/api/inventory/products/${productId}/score`),
      ]);
      if (prodRes.ok) {
        const p = await prodRes.json();
        setProduct(p);
        setEditing(p);
      } else {
        setError('Produit introuvable');
      }
      if (scoreRes.ok) setScore(await scoreRes.json());
    } catch {
      setError('Erreur de connexion');
    }
    setLoading(false);
  }, [productId]);

  useEffect(() => {
    fetchProduct();
  }, [fetchProduct]);

  // Auto-open label if redirected from creation
  useEffect(() => {
    if (searchParams.get('showLabel') === 'true' && product) {
      handleGenerateLabel();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.id]);

  const handleSave = async () => {
    if (!product) return;
    setSaving(true);
    try {
      const res = await api.put(`/api/inventory/products/${product.id}`, {
        name: editing.name,
        brand: editing.brand,
        size: editing.size,
        color: editing.color,
        purchase_price: Number(editing.purchase_price),
        sale_price: Number(editing.sale_price),
        status: editing.status,
        shelf_date: editing.shelf_date || null,
        description: editing.description,
      });
      if (res.ok) {
        const updated = await res.json();
        setProduct(updated);
        setIsEditing(false);
        setSaveMsg('Sauvegardé');
        setTimeout(() => setSaveMsg(''), 3000);
      }
    } catch { setError('Erreur de sauvegarde'); }
    setSaving(false);
  };

  const handleGenerateLabel = async () => {
    setLabelLoading(true);
    setShowLabel(true);
    setSatoMsg('');
    try {
      const res = await api.get(`/api/inventory/products/${productId}/label`);
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        setLabelUrl(url);
      }
    } catch { /* show error in modal */ }
    setLabelLoading(false);
  };

  const handlePrintSato = async () => {
    setSatoSending(true);
    setSatoMsg('');
    try {
      const res = await api.post(`/api/inventory/products/${productId}/print-label?quantity=1`, {});
      if (res.ok) {
        setSatoMsg('Etiquette envoyee a la SATO CT4-LX');
      } else {
        const e = await res.json().catch(() => ({}));
        setSatoMsg(e.detail || 'Echec de l\'impression SATO');
      }
    } catch {
      setSatoMsg('Erreur de connexion SATO');
    }
    setSatoSending(false);
  };

  const scoreColor = (s: number) => s >= 70 ? 'text-green-600' : s >= 40 ? 'text-yellow-600' : 'text-red-600';
  const actionBg = (c: string) => c === 'green' ? 'bg-green-50 text-green-700 border-green-200' : c === 'yellow' ? 'bg-yellow-50 text-yellow-700 border-yellow-200' : c === 'orange' ? 'bg-orange-50 text-orange-700 border-orange-200' : 'bg-red-50 text-red-700 border-red-200';

  if (loading) return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-teal" />
      </main>
    </div>
  );

  if (error || !product) return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-8">
        <p className="text-red-600">{error || 'Produit introuvable'}</p>
        <button onClick={() => router.back()} className="mt-4 text-teal underline">Retour</button>
      </main>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <button onClick={() => router.push('/inventory')} className="min-h-[44px] flex items-center gap-2 text-gray-500 hover:text-black transition-colors">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
              </svg>
              Inventaire
            </button>
            <span className="text-gray-300">/</span>
            <h1 className="text-xl font-bold text-black truncate max-w-xs">{product.name}</h1>
          </div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={handleGenerateLabel}>
              🏷 Générer étiquette
            </Button>
            {!isEditing ? (
              <Button onClick={() => setIsEditing(true)}>Modifier</Button>
            ) : (
              <>
                <Button variant="outline" onClick={() => { setIsEditing(false); setEditing(product); }}>Annuler</Button>
                <Button onClick={handleSave} disabled={saving}>{saving ? 'Sauvegarde...' : 'Sauvegarder'}</Button>
              </>
            )}
          </div>
        </div>

        {saveMsg && <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm">{saveMsg}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Product Info */}
          <div className="lg:col-span-2 space-y-6">
            <Card title="Informations produit">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {isEditing ? (
                  <>
                    <div className="sm:col-span-2">
                      <Input label="Nom" value={editing.name || ''} onChange={e => setEditing(p => ({...p, name: e.target.value}))} />
                    </div>
                    <Input label="Marque" value={editing.brand || ''} onChange={e => setEditing(p => ({...p, brand: e.target.value}))} />
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-black mb-1.5">Taille</label>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {['XS','S','M','L','XL','XXL','XXXL','TU','34','36','38','40','42','44','46'].map(s => (
                          <button key={s} type="button" onClick={() => setEditing(p => ({...p, size: p.size === s ? '' : s}))}
                            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors min-h-[40px] ${editing.size === s ? 'bg-teal text-white' : 'bg-gray-100 hover:bg-gray-200 text-black'}`}>
                            {s}
                          </button>
                        ))}
                      </div>
                      <Input value={editing.size || ''} onChange={e => setEditing(p => ({...p, size: e.target.value}))} placeholder="Autre taille..." />
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-black mb-1.5">Couleur</label>
                      <div className="flex flex-wrap gap-2 mb-2">
                        {[
                          {l:'Noir',c:'#1a1a1a'},{l:'Blanc',c:'#f0f0f0'},{l:'Gris',c:'#9ca3af'},
                          {l:'Beige',c:'#d4b896'},{l:'Camel',c:'#c19a6b'},{l:'Marine',c:'#1e3a5f'},
                          {l:'Rose',c:'#f4a7b9'},{l:'Rouge',c:'#dc2626'},{l:'Bordeaux',c:'#7c1d2a'},
                          {l:'Bleu',c:'#2563eb'},{l:'Vert',c:'#16a34a'},{l:'Kaki',c:'#5d6b3b'},
                          {l:'Marron',c:'#92400e'},{l:'Jaune',c:'#fbbf24'},{l:'Orange',c:'#ea580c'},
                          {l:'Violet',c:'#7c3aed'},{l:'Multicolore',c:'linear-gradient(135deg,#f43f5e,#3b82f6,#22c55e)'},
                        ].map(({l,c}) => (
                          <button key={l} type="button" onClick={() => setEditing(p => ({...p, color: p.color === l ? '' : l}))}
                            title={l}
                            className={`flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg transition-all ${editing.color === l ? 'ring-2 ring-teal ring-offset-1 bg-teal-50' : 'hover:bg-gray-50'}`}>
                            <div className="w-6 h-6 rounded-full border border-gray-200" style={{background:c}} />
                            <span className="text-xs text-gray-600 whitespace-nowrap">{l}</span>
                          </button>
                        ))}
                      </div>
                      <Input value={editing.color || ''} onChange={e => setEditing(p => ({...p, color: e.target.value}))} placeholder="Autre couleur..." />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Statut</label>
                      <select value={editing.status || 'stock'} onChange={e => setEditing(p => ({...p, status: e.target.value}))}
                        className="w-full min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-teal">
                        {statusOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Prix d&apos;achat (€)</label>
                      <div className="flex items-center gap-2">
                        <button type="button" onClick={() => setEditing(p => ({...p, purchase_price: Math.max(0, (p.purchase_price||0) - 1)}))}
                          className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0">−</button>
                        <Input type="number" step="0.01" value={String(editing.purchase_price || 0)} onChange={e => setEditing(p => ({...p, purchase_price: parseFloat(e.target.value)}))} className="text-center font-bold" />
                        <button type="button" onClick={() => setEditing(p => ({...p, purchase_price: (p.purchase_price||0) + 1}))}
                          className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0">+</button>
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Prix de vente (€)</label>
                      <div className="flex items-center gap-2">
                        <button type="button" onClick={() => setEditing(p => ({...p, sale_price: Math.max(0, (p.sale_price||0) - 0.5)}))}
                          className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0">−</button>
                        <Input type="number" step="0.50" value={String(editing.sale_price || 0)} onChange={e => setEditing(p => ({...p, sale_price: parseFloat(e.target.value)}))} className="text-center font-bold" />
                        <button type="button" onClick={() => setEditing(p => ({...p, sale_price: (p.sale_price||0) + 0.5}))}
                          className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0">+</button>
                      </div>
                    </div>
                    <Input label="Date de mise en rayon" type="date" value={editing.shelf_date ? editing.shelf_date.split('T')[0] : ''} onChange={e => setEditing(p => ({...p, shelf_date: e.target.value}))} />
                  </>
                ) : (
                  <>
                    <div><p className="text-xs text-gray-500 mb-0.5">Nom</p><p className="text-sm font-medium text-black">{product.name}</p></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Marque</p><p className="text-sm text-gray-700">{product.brand || '—'}</p></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Catégorie</p><p className="text-sm text-gray-700">{product.category?.name || '—'}</p></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Taille</p><p className="text-sm text-gray-700">{product.size || '—'}</p></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Couleur</p><p className="text-sm text-gray-700">{product.color || '—'}</p></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Statut</p><Badge variant={statusVariants[product.status] || 'stock'}>{statusOptions.find(o => o.value === product.status)?.label || product.status}</Badge></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Prix d&apos;achat</p><p className="text-sm text-gray-700">{product.purchase_price?.toFixed(2)} €</p></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Prix de vente</p><p className="text-sm font-bold text-teal">{product.sale_price?.toFixed(2)} €</p></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Code-barres</p><p className="text-xs font-mono text-gray-500">{product.barcode}</p></div>
                    <div><p className="text-xs text-gray-500 mb-0.5">Semaine</p><p className="text-sm text-gray-700">{product.week_number ? `SEM ${product.week_number}` : '—'}</p></div>
                    <div className="sm:col-span-2"><p className="text-xs text-gray-500 mb-0.5">Date de mise en rayon</p><p className="text-sm text-gray-700">{product.shelf_date ? new Date(product.shelf_date).toLocaleDateString('fr-FR', {day: '2-digit', month: 'long', year: 'numeric'}) : '— Non renseignée'}</p></div>
                  </>
                )}
              </div>
            </Card>

            {/* Score Detail */}
            {score && (
              <Card title="Score produit">
                <div className="flex items-start gap-6 mb-6">
                  <div className="text-center">
                    <div className={`text-5xl font-bold ${scoreColor(score.total_score)}`}>{Math.round(score.total_score)}</div>
                    <div className="text-xs text-gray-500 mt-1">/ 100</div>
                  </div>
                  <div className="flex-1">
                    <div className={`inline-block px-3 py-1.5 rounded-lg border text-sm font-medium ${actionBg(score.action_color)}`}>
                      {score.action}
                    </div>
                    {score.days_on_shelf !== null && (
                      <p className="text-xs text-gray-500 mt-2">En rayon depuis {score.days_on_shelf} jour{score.days_on_shelf > 1 ? 's' : ''}</p>
                    )}
                  </div>
                </div>

                <div className="space-y-3">
                  <ScoreBar value={score.score_age} label="Fraîcheur (ancienneté)" />
                  <ScoreBar value={score.score_prix} label="Compétitivité prix" />
                  <ScoreBar value={score.score_condition} label="État / Condition" />
                  <ScoreBar value={score.score_brand} label="Notoriété marque" />
                  <ScoreBar value={score.score_category} label="Tendance catégorie" />
                  <ScoreBar value={score.score_photos} label="Photos disponibles" />
                </div>

                <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 font-medium mb-1">Formule de calcul :</p>
                  <p className="text-xs text-gray-400">Score = Fraîcheur×30% + Prix×20% + Condition×20% + Marque×15% + Tendance×10% + Photos×5%</p>
                </div>
              </Card>
            )}
          </div>

          {/* Right: Photo + History */}
          <div className="space-y-6">
            <Card title="Photos">
              <PhotoGallery
                productId={product.id}
                onChange={() => fetchProduct()}
              />
            </Card>

            <Card title="Transactions">
              {transactions.length === 0 ? (
                <p className="text-sm text-gray-400">Aucune vente enregistrée</p>
              ) : (
                <div className="space-y-2">
                  {transactions.map(tx => (
                    <div key={tx.id} className="flex justify-between text-sm p-2 bg-gray-50 rounded">
                      <span className="text-gray-600">#{tx.transaction_number}</span>
                      <span className="text-gray-500">{new Date(tx.created_at).toLocaleDateString('fr-FR')}</span>
                      <span className="font-medium text-teal">{tx.total_ttc.toFixed(2)} €</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>

        {/* Label Modal */}
        <Modal open={showLabel} onClose={() => { setShowLabel(false); setLabelUrl(''); }} title="Étiquette produit">
          <div className="text-center space-y-4">
            {labelLoading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-teal" />
              </div>
            ) : labelUrl ? (
              <>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={labelUrl} alt="Étiquette" className="mx-auto border rounded-lg max-w-full" />
                <div className="flex justify-center gap-3 flex-wrap">
                  <a href={labelUrl} download={`etiquette-${product.barcode}.png`}>
                    <Button variant="outline">⬇ Télécharger</Button>
                  </a>
                  <Button onClick={() => {
                    const win = window.open(labelUrl, '_blank');
                    win?.print();
                  }}>🖨 Imprimer</Button>
                  <Button onClick={handlePrintSato} disabled={satoSending} variant="secondary">
                    {satoSending ? 'Envoi...' : 'Imprimer sur SATO'}
                  </Button>
                </div>
                {satoMsg && <p className="text-sm text-teal mt-2">{satoMsg}</p>}
              </>
            ) : (
              <p className="text-red-600 py-4">Erreur lors de la génération de l&apos;étiquette. Vérifiez la connexion API.</p>
            )}
          </div>
        </Modal>
      </main>
    </div>
  );
}
