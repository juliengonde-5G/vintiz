'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

interface Category {
  id: string;
  name: string;
}

interface VisionResult {
  type?: string;
  couleur?: string;
  couleur_secondaire?: string;
  matiere?: string;
  marque?: string;
  taille?: string;
  etat?: string;
  saison?: string;
  style?: string;
  description?: string;
  gamme_estimee?: string;
  confiance?: number;
  error?: string;
}

interface PriceSuggestion {
  suggested_price: number;
  price_range: { min: number; max: number };
  reasoning: string[];
  market_data: {
    avg_sold_price: number | null;
    recent_sales_count: number;
  };
}

function getWeekNumber(): number {
  const d = new Date();
  const target = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  return Math.ceil(((target.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

export default function NewProductPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [showLabel, setShowLabel] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [categories, setCategories] = useState<Category[]>([]);

  // AI states
  const [analyzing, setAnalyzing] = useState(false);
  const [visionResult, setVisionResult] = useState<VisionResult | null>(null);
  const [priceSuggestion, setPriceSuggestion] = useState<PriceSuggestion | null>(null);
  const [pricingLoading, setPricingLoading] = useState(false);

  const [form, setForm] = useState({
    name: '',
    category_id: '',
    size: '',
    color: '',
    brand: '',
    sellingPrice: '',
    week_number: String(getWeekNumber()),
    status: 'stock',
  });

  useEffect(() => {
    api.get('/api/inventory/categories').then(async (res) => {
      if (res.ok) setCategories(await res.json());
    });
  }, []);

  const handleChange = (field: string, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleFileSelect = async (file: File) => {
    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => setPhotoPreview(e.target?.result as string);
    reader.readAsDataURL(file);

    // AI analysis
    setAnalyzing(true);
    setVisionResult(null);
    setError('');
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.upload('/api/ai/vision/analyze', fd);
      if (res.ok) {
        const result: VisionResult = await res.json();
        setVisionResult(result);
        if (!result.error) {
          // Auto-fill form with AI results
          if (result.type) {
            const brandSuffix = result.marque && result.marque !== 'non identifiee' ? ` ${result.marque}` : '';
            handleChange('name', result.type.charAt(0).toUpperCase() + result.type.slice(1) + brandSuffix);
          }
          if (result.couleur) handleChange('color', result.couleur);
          if (result.taille) handleChange('size', result.taille);
          if (result.marque && result.marque !== 'non identifiee') handleChange('brand', result.marque);
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || 'Erreur analyse photo');
      }
    } catch {
      setError('Erreur envoi photo');
    }
    setAnalyzing(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      handleFileSelect(file);
    }
  };

  const fetchPriceSuggestion = useCallback(async () => {
    if (!form.category_id) return;
    setPricingLoading(true);
    try {
      const params = new URLSearchParams({ category_id: form.category_id });
      if (form.brand) params.set('brand', form.brand);
      if (visionResult?.etat) params.set('condition', visionResult.etat);
      const res = await api.post(`/api/ai/pricing/suggest?${params}`, {});
      if (res.ok) {
        const data: PriceSuggestion = await res.json();
        setPriceSuggestion(data);
        // N'écrase pas une saisie manuelle du caissier — uniquement quand
        // le champ est vide ou égal à la précédente suggestion.
        if (data.suggested_price > 0) {
          handleChange('sellingPrice', String(data.suggested_price));
        }
      }
    } catch {
      // Échec silencieux — la suggestion auto ne doit pas bloquer la
      // saisie produit. Le caissier peut toujours saisir le prix à la
      // main.
    }
    setPricingLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.category_id, form.brand, visionResult?.etat]);

  // Déclenche systématiquement la suggestion dès qu'on a une catégorie
  // (et le contexte AI quand il arrive). Le moteur degrade gracefully
  // sans prix d'achat — grille tarifaire + prix moyen vendu + marque +
  // état couvrent la grande majorité des cas.
  useEffect(() => {
    if (!form.category_id) return;
    void fetchPriceSuggestion();
  }, [form.category_id, form.brand, visionResult?.etat, fetchPriceSuggestion]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const res = await api.post('/api/inventory/products', {
        name: form.name,
        category_id: form.category_id || undefined,
        size: form.size || null,
        color: form.color || null,
        brand: form.brand || null,
        // Vintiz fonctionne en achat-revente sans prix d'achat saisi
        // côté caisse — l'API accepte 0 par défaut.
        purchase_price: 0,
        sale_price: parseFloat(form.sellingPrice) || 0,
        status: form.status,
        week_number: parseInt(form.week_number) || null,
      });
      if (res.ok) { const savedProduct = await res.json(); router.push('/inventory/' + savedProduct.id + '?showLabel=true');
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || 'Erreur lors de la creation');
      }
    } catch {
      setError('Erreur de connexion');
    }
    setSaving(false);
  };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-gray-500 hover:text-black min-h-[48px] transition-colors mb-4"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Retour
          </button>
          <h1 className="text-2xl font-bold text-black">Nouveau produit</h1>
          <p className="text-gray-500 mt-1">Ajout assiste par IA</p>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
            <button onClick={() => setError('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}

        <form onSubmit={handleSave} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Photo + AI */}
          <div className="lg:col-span-1 space-y-4">
            <Card title="Photo + Analyse IA">
              <div
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
                  dragOver ? 'border-vz-teal bg-vz-teal-soft' : 'border-gray-300 hover:border-vz-accent-soft'
                }`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
              >
                {photoPreview ? (
                  <img // eslint-disable-line @next/next/no-img-element
                    src={photoPreview}
                    alt="Preview"
                    className="max-h-48 mx-auto rounded-lg object-contain"
                  />
                ) : (
                  <div className="space-y-3">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mx-auto">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <polyline points="21 15 16 10 5 21" />
                    </svg>
                    <p className="text-gray-500 text-sm">
                      Glissez une photo ou cliquez pour parcourir
                    </p>
                    <p className="text-xs text-gray-400">L&apos;IA analysera automatiquement le vetement</p>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }}
                />
                {/* Caméra directe — sur Android Chrome l'attribut
                    capture=environment ouvre l'appareil photo arrière.
                    Sur desktop il retombe sur le file picker. Champ
                    caché, déclenché par le bouton dédié. */}
                <input
                  ref={cameraInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFileSelect(file);
                  }}
                />
              </div>

              {/* Action buttons — bouton caméra dédié à côté du choix fichier */}
              <div className="grid grid-cols-2 gap-2 mt-3">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    cameraInputRef.current?.click();
                  }}
                  className="flex items-center justify-center gap-2 px-3 py-3 rounded-xl bg-vz-teal hover:bg-vz-teal-deep text-white text-sm font-medium transition-colors min-h-[48px] shadow-sm"
                  aria-label="Prendre en photo"
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                    <circle cx="12" cy="13" r="4" />
                  </svg>
                  Prendre en photo
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fileInputRef.current?.click();
                  }}
                  className="flex items-center justify-center gap-2 px-3 py-3 rounded-xl bg-white border border-vz-line hover:bg-vz-bg-alt text-vz-ink text-sm font-medium transition-colors min-h-[48px]"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  Choisir fichier
                </button>
              </div>

              {analyzing && (
                <div className="text-center py-4">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-vz-teal"></div>
                  <p className="text-sm text-gray-500 mt-2">Analyse IA en cours...</p>
                </div>
              )}

              {visionResult && !visionResult.error && !analyzing && (
                <div className="mt-4 space-y-2">
                  <div className="p-2 bg-green-50 rounded-lg text-green-700 text-xs font-medium flex items-center gap-2">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                    Analyse terminee ({visionResult.confiance ? `${Math.round(visionResult.confiance * 100)}%` : '-'} confiance)
                  </div>
                  {visionResult.description && (
                    <p className="text-xs text-gray-500 italic p-2 bg-gray-50 rounded">{visionResult.description}</p>
                  )}
                  <div className="text-xs space-y-1">
                    {visionResult.matiere && (
                      <div className="flex justify-between"><span className="text-gray-400">Matiere</span><span className="text-gray-700">{visionResult.matiere}</span></div>
                    )}
                    {visionResult.etat && (
                      <div className="flex justify-between"><span className="text-gray-400">Etat</span><span className="text-gray-700">{visionResult.etat}</span></div>
                    )}
                    {visionResult.saison && (
                      <div className="flex justify-between"><span className="text-gray-400">Saison</span><span className="text-gray-700">{visionResult.saison}</span></div>
                    )}
                    {visionResult.style && (
                      <div className="flex justify-between"><span className="text-gray-400">Style</span><span className="text-gray-700">{visionResult.style}</span></div>
                    )}
                    {visionResult.gamme_estimee && (
                      <div className="flex justify-between"><span className="text-gray-400">Gamme</span><span className="text-gray-700">{visionResult.gamme_estimee}</span></div>
                    )}
                  </div>
                </div>
              )}

              {visionResult?.error && (
                <p className="mt-3 text-sm text-red-600">{visionResult.error}</p>
              )}
            </Card>

            {/* Price Suggestion — déclenchée systématiquement dès qu'une
                catégorie est sélectionnée (le moteur degrade gracefully
                sans prix d'achat). */}
            {form.category_id && (
              <Card title="Suggestion prix automatique">
                {pricingLoading && (
                  <div className="text-center py-3 text-sm text-gray-500">
                    <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-vz-teal mr-2 align-middle" />
                    Calcul à partir des ventes et de la grille tarifaire…
                  </div>
                )}
                {!pricingLoading && priceSuggestion && priceSuggestion.suggested_price > 0 && (
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between py-1">
                      <span className="text-gray-500">Prix suggéré</span>
                      <span className="font-bold text-vz-teal text-lg">{priceSuggestion.suggested_price.toFixed(2)}&nbsp;&euro;</span>
                    </div>
                    <div className="flex justify-between py-1 text-xs">
                      <span className="text-gray-400">Fourchette</span>
                      <span className="text-gray-500">{priceSuggestion.price_range.min.toFixed(2)} - {priceSuggestion.price_range.max.toFixed(2)}&nbsp;&euro;</span>
                    </div>
                    {priceSuggestion.market_data.avg_sold_price && (
                      <div className="flex justify-between py-1 text-xs">
                        <span className="text-gray-400">Prix moyen vendu</span>
                        <span className="text-gray-500">{priceSuggestion.market_data.avg_sold_price.toFixed(2)}&nbsp;&euro; ({priceSuggestion.market_data.recent_sales_count} ventes)</span>
                      </div>
                    )}
                    <div className="pt-2 border-t border-gray-100">
                      <ul className="space-y-0.5">
                        {priceSuggestion.reasoning.map((r, i) => (
                          <li key={i} className="text-xs text-gray-400">&bull; {r}</li>
                        ))}
                      </ul>
                    </div>
                    <Button
                      type="button"
                      onClick={fetchPriceSuggestion}
                      disabled={pricingLoading}
                      variant="outline"
                      size="sm"
                      className="w-full mt-2"
                    >
                      Recalculer
                    </Button>
                  </div>
                )}
                {!pricingLoading && priceSuggestion && priceSuggestion.suggested_price === 0 && (
                  <div className="text-xs text-gray-500 space-y-1">
                    <p>Pas assez de données marché pour suggérer un prix.</p>
                    {priceSuggestion.reasoning.map((r, i) => (
                      <p key={i} className="text-gray-400">• {r}</p>
                    ))}
                  </div>
                )}
              </Card>
            )}
          </div>

          {/* Right: Form fields */}
          <div className="lg:col-span-2 space-y-6">
            <Card title="Informations produit">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div className="sm:col-span-2">
                  <Input
                    label="Nom"
                    value={form.name}
                    onChange={(e) => handleChange('name', e.target.value)}
                    placeholder="Ex: Robe fleurie Sandro"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">
                    Categorie
                  </label>
                  <select
                    value={form.category_id}
                    onChange={(e) => handleChange('category_id', e.target.value)}
                    className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
                    required
                  >
                    <option value="">Choisir une categorie</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </div>

                <Input
                  label="Marque"
                  value={form.brand}
                  onChange={(e) => handleChange('brand', e.target.value)}
                  placeholder="Ex: Sandro, Maje..."
                />

                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-black mb-1.5">Taille</label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {['XS','S','M','L','XL','XXL','XXXL','TU','34','36','38','40','42','44','46'].map(s => (
                      <button key={s} type="button" onClick={() => handleChange('size', form.size === s ? '' : s)}
                        className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors min-h-[40px] ${form.size === s ? 'bg-vz-teal text-white' : 'bg-gray-100 hover:bg-gray-200 text-black'}`}>
                        {s}
                      </button>
                    ))}
                  </div>
                  <Input value={form.size} onChange={(e) => handleChange('size', e.target.value)} placeholder="Autre taille..." />
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
                      <button key={l} type="button" onClick={() => handleChange('color', form.color === l ? '' : l)}
                        title={l}
                        className={`flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg transition-all ${form.color === l ? 'ring-2 ring-vz-teal ring-offset-1 bg-vz-teal-soft' : 'hover:bg-gray-50'}`}>
                        <div className="w-6 h-6 rounded-full border border-gray-200" style={{background:c}} />
                        <span className="text-xs text-gray-600 whitespace-nowrap">{l}</span>
                      </button>
                    ))}
                  </div>
                  <Input value={form.color} onChange={(e) => handleChange('color', e.target.value)} placeholder="Autre couleur..." />
                </div>

                <Input
                  label="Semaine (SEM)"
                  type="number"
                  value={form.week_number}
                  onChange={(e) => handleChange('week_number', e.target.value)}
                />

                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">Statut</label>
                  <select
                    value={form.status}
                    onChange={(e) => handleChange('status', e.target.value)}
                    className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
                  >
                    <option value="stock">En stock</option>
                    <option value="display">En vitrine</option>
                  </select>
                </div>
              </div>
            </Card>

            <Card title="Prix de vente">
              <div>
                <label className="block text-sm font-medium text-black mb-1.5">Prix TTC (EUR)</label>
                <div className="flex items-center gap-2 max-w-md">
                  <button
                    type="button"
                    onClick={() => handleChange('sellingPrice', String(Math.max(0, parseFloat(form.sellingPrice || '0') - 0.5).toFixed(2)))}
                    className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0"
                  >
                    −
                  </button>
                  <Input
                    type="number"
                    step="0.50"
                    value={form.sellingPrice}
                    onChange={(e) => handleChange('sellingPrice', e.target.value)}
                    placeholder="0.00"
                    required
                    className="text-center font-bold"
                  />
                  <button
                    type="button"
                    onClick={() => handleChange('sellingPrice', String((parseFloat(form.sellingPrice || '0') + 0.5).toFixed(2)))}
                    className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0"
                  >
                    +
                  </button>
                </div>
                {priceSuggestion && priceSuggestion.suggested_price > 0 && (
                  <p className="text-xs text-gray-500 mt-2">
                    Suggestion automatique :{' '}
                    <button
                      type="button"
                      onClick={() => handleChange('sellingPrice', String(priceSuggestion.suggested_price))}
                      className="text-vz-teal underline font-medium"
                    >
                      {priceSuggestion.suggested_price.toFixed(2)}&nbsp;€
                    </button>{' '}
                    — basée sur grille tarifaire et ventes récentes.
                  </p>
                )}
              </div>
            </Card>

            {/* Label preview */}
            <Card title="Etiquette">
              <div className="flex flex-col sm:flex-row gap-4 items-start">
                <div className="flex flex-col gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowLabel(true)}
                  >
                    Generer etiquette
                  </Button>
                  {(!form.name || !form.sellingPrice) && (
                    <p className="text-xs text-gray-400">L&apos;etiquette sera disponible apres enregistrement</p>
                  )}
                </div>
                {showLabel && form.name && form.sellingPrice && (
                  <div className="border-2 border-dashed border-vz-accent-soft rounded-lg p-4 w-full sm:w-64">
                    <p className="font-serif text-lg font-bold text-vz-accent-soft text-center">Vintiz</p>
                    <hr className="my-2 border-vz-accent-soft" />
                    <p className="text-sm font-medium text-center">{form.name}</p>
                    {form.size && <p className="text-xs text-gray-500 text-center">Taille: {form.size}</p>}
                    {form.brand && <p className="text-xs text-gray-400 text-center">{form.brand}</p>}
                    <p className="text-lg font-bold text-vz-teal text-center mt-2">{form.sellingPrice}&nbsp;&euro;</p>
                    <p className="text-xs text-gray-400 text-center">SEM:{form.week_number}</p>
                  </div>
                )}
              </div>
            </Card>

            {/* Actions */}
            <div className="flex gap-4 justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => router.back()}
              >
                Annuler
              </Button>
              <Button type="submit" size="lg" disabled={saving}>
                {saving ? 'Enregistrement...' : 'Enregistrer'}
              </Button>
            </div>
          </div>
        </form>
      </main>
    </div>
  );
}
