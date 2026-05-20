'use client';

/**
 * Parcours d'entrée d'un nouveau produit — assistant guidé (mobile-first).
 *
 * Optimisé pour une tablette/téléphone Android en boutique :
 *   1. Photo      — capture caméra arrière en un tap (capture=environment)
 *   2. Analyse IA — déclenchée automatiquement sur la photo
 *   3. Identité   — nom / marque / catégorie (pré-remplis par l'IA)
 *   4. Détails    — couleur / taille (pré-remplis par l'IA)
 *   5. Prix       — suggestion IA, validée par l'utilisateur → crée la fiche
 *   6. Zone       — zone du magasin suggérée, validée (ou "garder en stock")
 *   7. Étiquette  — page de sortie + impression (réf. mise en stock/rayon)
 *
 * La fiche produit est créée à la validation du prix (étape 5) afin que les
 * étapes zone + étiquette disposent d'un identifiant réel.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';
import { mediaUrl } from '@/lib/format';

interface Category {
  id: string;
  name: string;
}

interface ZoneStat {
  zone_id: string;
  zone_name: string;
  product_count: number;
  capacity: number;
  occupancy_percent: number;
}

interface VisionResult {
  type?: string;
  couleur?: string;
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
  market_data: { avg_sold_price: number | null; recent_sales_count: number };
}

interface ZoneSuggestion {
  primary_zone_id: string | null;
  primary_zone_name: string | null;
  should_go_to_window: boolean;
  rationale: string;
}

interface CreatedProduct {
  id: string;
  barcode: string;
  name: string;
  status: string;
  sale_price: number;
  shelf_date: string | null;
  received_at: string | null;
  zone_name: string | null;
}

type Step = 'photo' | 'identity' | 'attributes' | 'price' | 'zone' | 'done';

const STEP_ORDER: Step[] = ['photo', 'identity', 'attributes', 'price', 'zone', 'done'];
const STEP_LABELS: Record<Step, string> = {
  photo: 'Photo',
  identity: 'Identité',
  attributes: 'Détails',
  price: 'Prix',
  zone: 'Emplacement',
  done: 'Étiquette',
};

const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', 'TU', '34', '36', '38', '40', '42', '44', '46'];
const COLORS = [
  { l: 'Noir', c: '#1a1a1a' }, { l: 'Blanc', c: '#f0f0f0' }, { l: 'Gris', c: '#9ca3af' },
  { l: 'Beige', c: '#d4b896' }, { l: 'Camel', c: '#c19a6b' }, { l: 'Marine', c: '#1e3a5f' },
  { l: 'Rose', c: '#f4a7b9' }, { l: 'Rouge', c: '#dc2626' }, { l: 'Bordeaux', c: '#7c1d2a' },
  { l: 'Bleu', c: '#2563eb' }, { l: 'Vert', c: '#16a34a' }, { l: 'Kaki', c: '#5d6b3b' },
  { l: 'Marron', c: '#92400e' }, { l: 'Jaune', c: '#fbbf24' }, { l: 'Orange', c: '#ea580c' },
  { l: 'Violet', c: '#7c3aed' }, { l: 'Multicolore', c: 'linear-gradient(135deg,#f43f5e,#3b82f6,#22c55e)' },
];

// Condition codes stored on the product (match the API / scoring vocabulary)
// with the label printed to the operator.
const CONDITIONS = [
  { code: 'neuf', label: 'Neuf' },
  { code: 'tres_bon', label: 'Très bon' },
  { code: 'bon', label: 'Bon' },
  { code: 'correct', label: 'Correct' },
];

// Map a free-form AI ``etat`` to one of our condition codes.
function normalizeCondition(etat?: string): string {
  if (!etat) return '';
  const e = etat.toLowerCase().replace(/[éè]/g, 'e').trim();
  if (e.includes('neuf') || e.includes('excellent')) return 'neuf';
  if (e.includes('tres bon') || e.includes('tres_bon')) return 'tres_bon';
  if (e.includes('correct')) return 'correct';
  if (e.includes('bon')) return 'bon';
  return '';
}

function getWeekNumber(): number {
  const d = new Date();
  const target = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = target.getUTCDay() || 7;
  target.setUTCDate(target.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(target.getUTCFullYear(), 0, 1));
  return Math.ceil(((target.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

function formatDate(s: string | null): string {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });
  } catch {
    return '—';
  }
}

export default function NewProductWizard() {
  const router = useRouter();
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  // Synchronous guard against a double-tap firing two POST /products before
  // React re-renders with ``saving=true`` (would create duplicate fiches).
  const submittingRef = useRef(false);

  const [step, setStep] = useState<Step>('photo');
  const [error, setError] = useState('');

  // Photo + AI
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [vision, setVision] = useState<VisionResult | null>(null);

  // Form
  const [categories, setCategories] = useState<Category[]>([]);
  const [form, setForm] = useState({ name: '', brand: '', category_id: '', color: '', size: '', condition: '' });
  const [price, setPrice] = useState('');
  // Surfaced on the exit screen so the operator knows the photo didn't attach.
  const [photoUploadFailed, setPhotoUploadFailed] = useState(false);

  // Pricing
  const [priceSuggestion, setPriceSuggestion] = useState<PriceSuggestion | null>(null);
  const [pricingLoading, setPricingLoading] = useState(false);

  // Created product + zone
  const [created, setCreated] = useState<CreatedProduct | null>(null);
  const [saving, setSaving] = useState(false);
  const [destination, setDestination] = useState<'rayon' | 'stock'>('rayon');
  const [zones, setZones] = useState<ZoneStat[]>([]);
  const [zoneSuggestion, setZoneSuggestion] = useState<ZoneSuggestion | null>(null);
  const [selectedZoneId, setSelectedZoneId] = useState('');

  // Label
  const [labelUrl, setLabelUrl] = useState('');
  const [labelLoading, setLabelLoading] = useState(false);
  const [printMsg, setPrintMsg] = useState('');
  const [printing, setPrinting] = useState(false);

  useEffect(() => {
    api.get('/api/inventory/categories').then(async (res) => {
      if (res.ok) setCategories(await res.json());
    }).catch(() => {});
  }, []);

  const set = (field: string, value: string) => setForm((p) => ({ ...p, [field]: value }));

  // --- Step 1-2: photo capture + auto AI analysis ---
  const handleFile = async (file: File) => {
    setPhotoFile(file);
    setError('');
    const reader = new FileReader();
    reader.onload = (e) => setPhotoPreview(e.target?.result as string);
    reader.readAsDataURL(file);

    setAnalyzing(true);
    setVision(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.upload('/api/ai/vision/analyze', fd);
      if (res.ok) {
        const result: VisionResult = await res.json();
        setVision(result);
        if (!result.error) {
          if (result.type) {
            const suffix = result.marque && result.marque !== 'non identifiee' ? ` ${result.marque}` : '';
            set('name', result.type.charAt(0).toUpperCase() + result.type.slice(1) + suffix);
          }
          if (result.couleur) set('color', result.couleur);
          if (result.taille) set('size', result.taille);
          if (result.marque && result.marque !== 'non identifiee') set('brand', result.marque);
          const cond = normalizeCondition(result.etat);
          if (cond) set('condition', cond);
        }
      } else {
        const e = await res.json().catch(() => ({}));
        setVision({ error: e.detail || 'Analyse indisponible' });
      }
    } catch {
      setVision({ error: 'Analyse indisponible — vous pouvez saisir les champs à la main.' });
    }
    setAnalyzing(false);
  };

  // --- Step 4: price suggestion ---
  const fetchPrice = useCallback(async () => {
    if (!form.category_id) return;
    setPricingLoading(true);
    try {
      const params = new URLSearchParams({ category_id: form.category_id });
      if (form.brand) params.set('brand', form.brand);
      if (vision?.etat) params.set('condition', vision.etat);
      const res = await api.post(`/api/ai/pricing/suggest?${params}`, {});
      if (res.ok) {
        const data: PriceSuggestion = await res.json();
        setPriceSuggestion(data);
        if (data.suggested_price > 0 && !price) setPrice(String(data.suggested_price));
      }
    } catch { /* graceful — manual price still possible */ }
    setPricingLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.category_id, form.brand, vision?.etat]);

  useEffect(() => {
    if (step === 'price') void fetchPrice();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  // --- Step 5: create the product (idempotent: PUT if already created) ---
  const createOrUpdate = async (): Promise<CreatedProduct | null> => {
    if (submittingRef.current) return null;  // ignore double-tap
    submittingRef.current = true;
    setSaving(true);
    setError('');
    try {
      const body = {
        name: form.name,
        category_id: form.category_id || undefined,
        brand: form.brand || null,
        color: form.color || null,
        size: form.size || null,
        condition: form.condition || null,
        purchase_price: 0,
        sale_price: parseFloat(price) || 0,
        status: 'stock',
        week_number: getWeekNumber(),
      };
      let res;
      if (created) {
        res = await api.put(`/api/inventory/products/${created.id}`, body);
      } else {
        res = await api.post('/api/inventory/products', body);
      }
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || 'Erreur lors de la création de la fiche');
        return null;
      }
      const product: CreatedProduct = await res.json();
      // Attach the captured photo once the product exists. Surface failures on
      // the exit screen so the operator isn't left thinking the photo saved.
      if (photoFile && !created) {
        await uploadPhoto(product.id);
      }
      setCreated(product);
      return product;
    } catch {
      setError('Erreur de connexion');
      return null;
    } finally {
      submittingRef.current = false;
      setSaving(false);
    }
  };

  const uploadPhoto = async (productId: string) => {
    if (!photoFile) return;
    try {
      const fd = new FormData();
      fd.append('file', photoFile);
      const res = await api.upload(`/api/inventory/products/${productId}/photos/upload`, fd);
      setPhotoUploadFailed(!res.ok);
    } catch {
      setPhotoUploadFailed(true);
    }
  };

  const validatePrice = async () => {
    const product = await createOrUpdate();
    if (!product) return;
    // Prepare the zone step.
    try {
      const [zres, sres] = await Promise.all([
        api.get('/api/ai/mapping/zones'),
        api.get(`/api/inventory/products/${product.id}/suggest-zone`),
      ]);
      if (zres.ok) setZones(await zres.json());
      if (sres.ok) {
        const sug: ZoneSuggestion = await sres.json();
        setZoneSuggestion(sug);
        if (sug.primary_zone_id) setSelectedZoneId(sug.primary_zone_id);
      }
    } catch { /* zone step still usable manually */ }
    setStep('zone');
  };

  // --- Step 6: validate destination (rayon + zone, or stock) ---
  const validateZone = async () => {
    if (!created) return;
    setSaving(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        status: destination === 'rayon' ? 'display' : 'stock',
      };
      if (destination === 'rayon' && selectedZoneId) body.zone_id = selectedZoneId;
      const res = await api.put(`/api/inventory/products/${created.id}`, body);
      if (res.ok) {
        const updated: CreatedProduct = await res.json();
        // The PUT response (ProductResponse) doesn't resolve the zone name —
        // backfill it from the zone list so the exit screen can show it.
        const zoneName = zones.find((z) => z.zone_id === selectedZoneId)?.zone_name ?? null;
        setCreated({ ...updated, zone_name: destination === 'rayon' ? zoneName : null });
      } else {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || "Erreur lors de l'affectation");
        setSaving(false);
        return;
      }
    } catch {
      setError('Erreur de connexion');
      setSaving(false);
      return;
    }
    setSaving(false);
    setStep('done');
    void loadLabel();
  };

  // --- Step 7: label ---
  const loadLabel = async () => {
    if (!created) return;
    setLabelLoading(true);
    setPrintMsg('');
    try {
      const res = await api.get(`/api/labels/preview/${created.id}`);
      if (res.ok) {
        const blob = await res.blob();
        setLabelUrl(URL.createObjectURL(blob));
      } else {
        const e = await res.json().catch(() => ({}));
        setPrintMsg(e.detail || 'Aperçu indisponible (Labelary injoignable)');
      }
    } catch {
      setPrintMsg('Aperçu indisponible');
    }
    setLabelLoading(false);
  };

  const printLabel = async () => {
    if (!created) return;
    setPrinting(true);
    setPrintMsg('');
    try {
      const res = await api.post(`/api/labels/print/${created.id}`, {});
      if (res.ok) setPrintMsg('Étiquette envoyée à l\'imprimante Zebra');
      else {
        const e = await res.json().catch(() => ({}));
        setPrintMsg(e.detail || 'Imprimante injoignable');
      }
    } catch {
      setPrintMsg('Imprimante injoignable');
    }
    setPrinting(false);
  };

  const resetForNext = () => {
    setStep('photo');
    setPhotoFile(null);
    setPhotoPreview(null);
    setPhotoUploadFailed(false);
    submittingRef.current = false;
    setVision(null);
    setForm({ name: '', brand: '', category_id: '', color: '', size: '', condition: '' });
    setPrice('');
    setPriceSuggestion(null);
    setCreated(null);
    setDestination('rayon');
    setZones([]);
    setZoneSuggestion(null);
    setSelectedZoneId('');
    setLabelUrl('');
    setPrintMsg('');
    setError('');
  };

  const stepIndex = STEP_ORDER.indexOf(step);
  const canIdentity = form.name.trim() && form.category_id;

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-10 md:p-8">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="mb-4">
            <button
              onClick={() => router.push('/inventory')}
              className="flex items-center gap-2 text-gray-500 hover:text-black min-h-[44px] transition-colors"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
              </svg>
              Inventaire
            </button>
            <h1 className="text-2xl font-bold text-black mt-2">Nouveau produit</h1>
          </div>

          {/* Step indicator */}
          <div className="flex items-center gap-1 mb-6">
            {STEP_ORDER.map((s, i) => (
              <React.Fragment key={s}>
                <div className="flex flex-col items-center gap-1 flex-1">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                      i < stepIndex ? 'bg-vz-teal text-white'
                        : i === stepIndex ? 'bg-vz-teal text-white ring-4 ring-vz-teal-soft'
                        : 'bg-gray-200 text-gray-400'
                    }`}
                  >
                    {i < stepIndex ? '✓' : i + 1}
                  </div>
                  <span className={`text-[10px] text-center ${i === stepIndex ? 'text-vz-teal font-medium' : 'text-gray-400'}`}>
                    {STEP_LABELS[s]}
                  </span>
                </div>
                {i < STEP_ORDER.length - 1 && (
                  <div className={`h-0.5 flex-1 -mt-4 ${i < stepIndex ? 'bg-vz-teal' : 'bg-gray-200'}`} />
                )}
              </React.Fragment>
            ))}
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm flex justify-between">
              <span>{error}</span>
              <button onClick={() => setError('')} className="font-bold">&times;</button>
            </div>
          )}

          {/* STEP 1 — PHOTO */}
          {step === 'photo' && (
            <Card>
              <div className="space-y-4">
                {photoPreview ? (
                  <img // eslint-disable-line @next/next/no-img-element
                    src={photoPreview}
                    alt="Aperçu"
                    className="w-full max-h-72 object-contain rounded-xl bg-gray-50"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => cameraInputRef.current?.click()}
                    className="w-full flex flex-col items-center justify-center gap-3 py-12 rounded-2xl bg-vz-teal text-white hover:bg-vz-teal-deep transition-colors shadow-sm"
                  >
                    <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                      <circle cx="12" cy="13" r="4" />
                    </svg>
                    <span className="text-lg font-semibold">Prendre la photo</span>
                    <span className="text-sm opacity-80">Caméra arrière — un seul tap</span>
                  </button>
                )}

                <input
                  ref={cameraInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />
                <input
                  ref={galleryInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />

                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => cameraInputRef.current?.click()}
                    className="min-h-[48px] flex items-center justify-center gap-2 rounded-xl border border-vz-line hover:bg-vz-bg-alt text-vz-ink text-sm font-medium"
                  >
                    {photoPreview ? 'Reprendre la photo' : 'Caméra'}
                  </button>
                  <button
                    type="button"
                    onClick={() => galleryInputRef.current?.click()}
                    className="min-h-[48px] flex items-center justify-center gap-2 rounded-xl border border-vz-line hover:bg-vz-bg-alt text-vz-ink text-sm font-medium"
                  >
                    Galerie
                  </button>
                </div>

                {analyzing && (
                  <div className="text-center py-3">
                    <div className="inline-block animate-spin rounded-full h-7 w-7 border-b-2 border-vz-teal" />
                    <p className="text-sm text-gray-500 mt-2">Analyse IA en cours…</p>
                  </div>
                )}

                {vision && !vision.error && !analyzing && (
                  <div className="p-3 bg-green-50 rounded-lg text-green-700 text-sm flex items-center gap-2">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12" /></svg>
                    Analyse terminée{vision.confiance ? ` — ${Math.round(vision.confiance * 100)}% de confiance` : ''}. Champs pré-remplis.
                  </div>
                )}
                {vision?.error && !analyzing && (
                  <div className="p-3 bg-amber-50 rounded-lg text-amber-700 text-sm">{vision.error}</div>
                )}

                <Button
                  size="lg"
                  className="w-full"
                  disabled={!photoFile || analyzing}
                  onClick={() => setStep('identity')}
                >
                  {analyzing ? 'Analyse…' : 'Continuer'}
                </Button>
              </div>
            </Card>
          )}

          {/* STEP 2 — IDENTITY (nom / marque / catégorie) */}
          {step === 'identity' && (
            <Card title="Étape 1 — Nom, marque, catégorie">
              <div className="space-y-4">
                <Input label="Nom du produit" value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="Ex : Robe fleurie Sandro" required />
                <Input label="Marque" value={form.brand} onChange={(e) => set('brand', e.target.value)} placeholder="Ex : Sandro, Maje…" />
                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">Catégorie</label>
                  <select
                    value={form.category_id}
                    onChange={(e) => set('category_id', e.target.value)}
                    className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
                    required
                  >
                    <option value="">Choisir une catégorie</option>
                    {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div className="flex gap-3 pt-2">
                  <Button variant="outline" onClick={() => setStep('photo')}>Précédent</Button>
                  <Button className="flex-1" disabled={!canIdentity} onClick={() => setStep('attributes')}>Continuer</Button>
                </div>
              </div>
            </Card>
          )}

          {/* STEP 3 — ATTRIBUTES (couleur / taille) */}
          {step === 'attributes' && (
            <Card title="Étape 2 — Couleur, taille">
              <div className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">Couleur</label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {COLORS.map(({ l, c }) => (
                      <button key={l} type="button" onClick={() => set('color', form.color === l ? '' : l)} title={l}
                        className={`flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg transition-all ${form.color === l ? 'ring-2 ring-vz-teal ring-offset-1 bg-vz-teal-soft' : 'hover:bg-gray-50'}`}>
                        <div className="w-6 h-6 rounded-full border border-gray-200" style={{ background: c }} />
                        <span className="text-xs text-gray-600 whitespace-nowrap">{l}</span>
                      </button>
                    ))}
                  </div>
                  <Input value={form.color} onChange={(e) => set('color', e.target.value)} placeholder="Autre couleur…" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">Taille</label>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {SIZES.map((s) => (
                      <button key={s} type="button" onClick={() => set('size', form.size === s ? '' : s)}
                        className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors min-h-[44px] ${form.size === s ? 'bg-vz-teal text-white' : 'bg-gray-100 hover:bg-gray-200 text-black'}`}>
                        {s}
                      </button>
                    ))}
                  </div>
                  <Input value={form.size} onChange={(e) => set('size', e.target.value)} placeholder="Autre taille…" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">État</label>
                  <div className="flex flex-wrap gap-2">
                    {CONDITIONS.map(({ code, label }) => (
                      <button key={code} type="button" onClick={() => set('condition', form.condition === code ? '' : code)}
                        className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors min-h-[44px] ${form.condition === code ? 'bg-vz-teal text-white' : 'bg-gray-100 hover:bg-gray-200 text-black'}`}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="flex gap-3 pt-2">
                  <Button variant="outline" onClick={() => setStep('identity')}>Précédent</Button>
                  <Button className="flex-1" onClick={() => setStep('price')}>Continuer</Button>
                </div>
              </div>
            </Card>
          )}

          {/* STEP 4 — PRICE */}
          {step === 'price' && (
            <Card title="Étape 3 — Prix de vente">
              <div className="space-y-4">
                {pricingLoading ? (
                  <div className="text-center py-3 text-sm text-gray-500">
                    <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-vz-teal mr-2 align-middle" />
                    Calcul du prix suggéré…
                  </div>
                ) : priceSuggestion && priceSuggestion.suggested_price > 0 ? (
                  <div className="p-3 rounded-xl bg-vz-teal-soft/40 border border-vz-teal-soft">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Prix suggéré par l&apos;IA</span>
                      <button type="button" onClick={() => setPrice(String(priceSuggestion.suggested_price))} className="text-2xl font-bold text-vz-teal hover:underline">
                        {priceSuggestion.suggested_price.toFixed(2)} €
                      </button>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">Fourchette {priceSuggestion.price_range.min.toFixed(2)} – {priceSuggestion.price_range.max.toFixed(2)} €</p>
                    {priceSuggestion.reasoning.length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {priceSuggestion.reasoning.map((r, i) => <li key={i} className="text-xs text-gray-400">• {r}</li>)}
                      </ul>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">Pas assez de données marché — saisissez le prix manuellement.</p>
                )}

                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">Prix TTC (à valider)</label>
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={() => setPrice(String(Math.max(0, (parseFloat(price || '0') - 0.5)).toFixed(2)))}
                      className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0">−</button>
                    <Input type="number" step="0.50" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="0.00" required className="text-center font-bold text-lg" />
                    <button type="button" onClick={() => setPrice(String((parseFloat(price || '0') + 0.5).toFixed(2)))}
                      className="w-12 h-12 flex items-center justify-center rounded-xl bg-gray-100 hover:bg-gray-200 text-black font-bold text-xl flex-shrink-0">+</button>
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <Button variant="outline" onClick={() => setStep('attributes')}>Précédent</Button>
                  <Button className="flex-1" disabled={saving || !(parseFloat(price) > 0)} onClick={validatePrice}>
                    {saving ? 'Création…' : 'Valider le prix'}
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* STEP 5 — ZONE */}
          {step === 'zone' && created && (
            <Card title="Étape 4 — Emplacement">
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-2">
                  <button type="button" onClick={() => setDestination('rayon')}
                    className={`min-h-[56px] rounded-xl border-2 px-3 font-medium transition-colors ${destination === 'rayon' ? 'border-vz-teal bg-vz-teal-soft text-vz-teal-deep' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}>
                    Mettre en rayon
                  </button>
                  <button type="button" onClick={() => setDestination('stock')}
                    className={`min-h-[56px] rounded-xl border-2 px-3 font-medium transition-colors ${destination === 'stock' ? 'border-amber-400 bg-amber-50 text-amber-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}>
                    Garder en stock
                  </button>
                </div>

                {destination === 'rayon' && (
                  <>
                    {zoneSuggestion?.rationale && (
                      <div className="p-3 rounded-xl bg-vz-teal-soft/40 border border-vz-teal-soft text-sm">
                        <p className="font-medium text-vz-teal-deep">
                          Zone suggérée : {zoneSuggestion.primary_zone_name || 'aucune'}
                          {zoneSuggestion.should_go_to_window && ' (vitrine recommandée)'}
                        </p>
                        <p className="text-xs text-gray-600 mt-1">{zoneSuggestion.rationale}</p>
                      </div>
                    )}
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Zone du magasin</label>
                      {zones.length === 0 ? (
                        <p className="text-sm text-gray-500">Aucune zone configurée. Le produit ira en rayon sans zone précise.</p>
                      ) : (
                        <select
                          value={selectedZoneId}
                          onChange={(e) => setSelectedZoneId(e.target.value)}
                          className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
                        >
                          <option value="">Sans zone précise</option>
                          {zones.map((z) => (
                            <option key={z.zone_id} value={z.zone_id}>
                              {z.zone_name} — {z.occupancy_percent}% occupée
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  </>
                )}

                {destination === 'stock' && (
                  <p className="text-sm text-gray-500">L&apos;article reste en réserve. Vous pourrez le mettre en rayon plus tard depuis l&apos;inventaire.</p>
                )}

                {destination === 'rayon' && zones.length > 0 && !selectedZoneId && (
                  <p className="text-xs text-amber-600">Choisissez une zone pour que l&apos;article soit localisable en boutique.</p>
                )}

                <div className="flex gap-3 pt-2">
                  <Button variant="outline" onClick={() => setStep('price')}>Précédent</Button>
                  <Button
                    className="flex-1"
                    disabled={saving || (destination === 'rayon' && zones.length > 0 && !selectedZoneId)}
                    onClick={validateZone}
                  >
                    {saving ? 'Validation…' : 'Valider et éditer l\'étiquette'}
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* STEP 6 — DONE / LABEL */}
          {step === 'done' && created && (
            <Card>
              <div className="space-y-4 text-center">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-green-100 text-green-600">
                  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg>
                </div>
                <div>
                  <h2 className="text-xl font-bold text-black">{created.name}</h2>
                  <p className="text-vz-teal font-bold text-lg">{Number(created.sale_price).toFixed(2)} €</p>
                </div>

                {photoUploadFailed && (
                  <div className="mx-auto max-w-xs p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 text-sm">
                    La photo n&apos;a pas pu être enregistrée.
                    <button
                      type="button"
                      onClick={async () => { setPhotoUploadFailed(false); await uploadPhoto(created.id); }}
                      className="ml-1 underline font-medium"
                    >
                      Réessayer
                    </button>
                  </div>
                )}

                {/* Référence de mise en stock / rayon */}
                <div className="text-left mx-auto max-w-xs text-sm space-y-1 bg-gray-50 rounded-xl p-3">
                  <div className="flex justify-between"><span className="text-gray-500">Référence</span><span className="font-mono text-gray-800">{created.barcode}</span></div>
                  {created.status === 'display' || created.status === 'displayed' ? (
                    <>
                      <div className="flex justify-between"><span className="text-gray-500">Localisation</span><span className="font-medium text-vz-teal">En rayon{created.zone_name ? ` — ${created.zone_name}` : ''}</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Mise en rayon</span><span className="text-gray-800">{formatDate(created.shelf_date)}</span></div>
                    </>
                  ) : (
                    <>
                      <div className="flex justify-between"><span className="text-gray-500">Localisation</span><span className="font-medium text-amber-600">En stock</span></div>
                      <div className="flex justify-between"><span className="text-gray-500">Entrée en stock</span><span className="text-gray-800">{formatDate(created.received_at)}</span></div>
                    </>
                  )}
                </div>

                {/* Label preview */}
                <div className="border-2 border-dashed border-vz-line rounded-xl p-3 min-h-[120px] flex items-center justify-center">
                  {labelLoading ? (
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-vz-teal" />
                  ) : labelUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={labelUrl} alt="Étiquette" className="max-h-64 mx-auto" />
                  ) : (
                    <p className="text-sm text-gray-400">{printMsg || 'Étiquette indisponible'}</p>
                  )}
                </div>
                {printMsg && labelUrl && <p className="text-sm text-vz-teal">{printMsg}</p>}

                <div className="flex flex-col sm:flex-row gap-2 justify-center">
                  <Button onClick={printLabel} disabled={printing}>
                    {printing ? 'Envoi…' : '🏷 Imprimer l\'étiquette'}
                  </Button>
                  {labelUrl && (
                    <a href={labelUrl} download={`etiquette-${created.barcode}.png`}>
                      <Button variant="outline" className="w-full">⬇ Télécharger</Button>
                    </a>
                  )}
                </div>

                <div className="flex flex-col sm:flex-row gap-2 justify-center pt-2 border-t border-gray-100">
                  <Button variant="outline" onClick={resetForNext}>+ Nouveau produit</Button>
                  <Button variant="outline" onClick={() => router.push(`/inventory/${created.id}`)}>Voir la fiche</Button>
                  <Button variant="outline" onClick={() => router.push('/inventory')}>Inventaire</Button>
                </div>
              </div>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}
