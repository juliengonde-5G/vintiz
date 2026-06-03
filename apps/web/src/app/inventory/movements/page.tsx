'use client';

/**
 * Mouvements de stock — module piloté par la douchette.
 *
 * « Le moteur propose, je scanne le code-barres, je fais le mouvement. »
 *
 * Deux onglets :
 *  - Aménagement (hebdomadaire) → flux HORIZONTAL (zone ↔ zone), proposé par
 *    Vintiz IA. GET /api/inventory/movements/weekly-plan.
 *  - Achalandage (réserve → rayon) → flux VERTICAL, au fil des ventes.
 *    GET /api/inventory/movements/restock-plan.
 *
 * À chaque scan (USB HID → Entrée), on cherche la pièce proposée dans l'onglet
 * courant et on déclenche POST /api/inventory/movements/execute. La pièce passe
 * en « Fait ✓ ».
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';
import { looksLikeScannerMojibake, SCANNER_MOJIBAKE_MESSAGE } from '@/lib/barcode';

type Tab = 'amenagement' | 'achalandage';

interface PlanItem {
  product_id: string;
  barcode: string;
  name: string;
  brand: string | null;
  size: string | null;
  color: string | null;
  trend_score: number | null;
  score_bucket: string;
}

interface WeeklyItem extends PlanItem {
  to_zone_id: string;
  to_zone_name: string;
  rationale: string;
}

interface WeeklyZone {
  from_zone_id: string | null;
  from_zone_name: string;
  n_moves: number;
  items: WeeklyItem[];
}

interface WeeklyPlan {
  generated_at: string;
  total_moves: number;
  zones: WeeklyZone[];
}

interface RestockZone {
  zone_id: string;
  zone_name: string;
  capacity: number | null;
  current: number;
  occupancy_pct: number | null;
  deficit: number;
  recent_sales: number;
  candidates: PlanItem[];
}

interface RestockPlan {
  generated_at: string;
  period_days: number;
  stock_available: number;
  zones: RestockZone[];
}

interface ExecuteResult {
  product_id: string;
  barcode: string;
  name: string;
  status: string;
  zone_id: string | null;
  move_type: string | null;
  recorded: boolean;
}

type Toast =
  | { kind: 'success'; text: string }
  | { kind: 'warn'; text: string }
  | { kind: 'error'; text: string };

// Résultat du moteur de recherche POS (même endpoint /products/search).
interface FreeProduct {
  id: string;
  barcode: string;
  name: string;
  sale_price: number;
  status: string;
  category: string | null;
  photo_url: string | null;
}

const BUCKET_STYLE: Record<string, { label: string; cls: string }> = {
  hot: { label: 'Tendance forte', cls: 'bg-vz-accent-soft text-vz-accent' },
  warm: { label: 'Tendance', cls: 'bg-vz-teal-soft text-vz-teal-deep' },
  slow: { label: 'Lent', cls: 'bg-amber-100 text-amber-700' },
  cold: { label: 'Dormant', cls: 'bg-gray-100 text-gray-500' },
  unknown: { label: 'Non noté', cls: 'bg-gray-100 text-gray-500' },
};

function BucketBadge({ bucket }: { bucket: string }) {
  const cfg = BUCKET_STYLE[bucket] ?? BUCKET_STYLE.unknown;
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] font-medium ${cfg.cls}`}>
      {cfg.label}
    </span>
  );
}

function describe(item: PlanItem): string {
  return [item.brand, item.size, item.color].filter(Boolean).join(' · ');
}

export default function StockMovementsPage() {
  const [tab, setTab] = useState<Tab>('amenagement');

  const [weekly, setWeekly] = useState<WeeklyPlan | null>(null);
  const [restock, setRestock] = useState<RestockPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Barcodes already executed this session (per tab is overkill — a piece is
  // either moved or not, key by product_id).
  const [done, setDone] = useState<Record<string, ExecuteResult>>({});
  const [toast, setToast] = useState<Toast | null>(null);
  const [executing, setExecuting] = useState(false);

  const [scanValue, setScanValue] = useState('');
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Recherche libre (tout le stock) — même moteur que le POS. Permet de
  // déplacer N'IMPORTE quelle pièce réserve→rayon sans qu'elle soit dans la
  // proposition IA. Indépendant de la douchette/proposition.
  const [freeQuery, setFreeQuery] = useState('');
  const [freeResults, setFreeResults] = useState<FreeProduct[]>([]);
  const [freeLoading, setFreeLoading] = useState(false);
  const freeDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Placement (achalandage) : produit sélectionné → confirmation de zone.
  // Le moteur IA propose une zone, l'opérateur confirme ou modifie.
  const [zones, setZones] = useState<{ id: string; name: string }[]>([]);
  const [placement, setPlacement] = useState<{
    product: FreeProduct;
    suggestion: {
      primary_zone_id: string | null;
      primary_zone_name: string | null;
      alternative_zone_id: string | null;
      alternative_zone_name: string | null;
      rationale: string | null;
    } | null;
    chosenZoneId: string;
    loadingSuggestion: boolean;
  } | null>(null);

  const focusInput = useCallback(() => {
    // Defer so it survives re-renders / DOM updates after a scan.
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  // Charge la liste des zones une fois (pour le sélecteur de placement).
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await api.get('/api/admin/zones');
        if (res.ok && active) {
          const data = await res.json();
          const list = Array.isArray(data) ? data : (data.zones || []);
          setZones(list.map((z: { id: string; name: string }) => ({ id: z.id, name: z.name })));
        }
      } catch { /* silent */ }
    })();
    return () => { active = false; };
  }, []);

  const loadWeekly = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/inventory/movements/weekly-plan');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setWeekly(await res.json());
    } catch {
      setError("Impossible de charger le plan d'aménagement.");
      setWeekly(null);
    } finally {
      setLoading(false);
      focusInput();
    }
  }, [focusInput]);

  const loadRestock = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/inventory/movements/restock-plan?period_days=14');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRestock(await res.json());
    } catch {
      setError("Impossible de charger le plan d'achalandage.");
      setRestock(null);
    } finally {
      setLoading(false);
      focusInput();
    }
  }, [focusInput]);

  // (Re)load the active tab's plan.
  const reload = useCallback(() => {
    if (tab === 'amenagement') loadWeekly();
    else loadRestock();
  }, [tab, loadWeekly, loadRestock]);

  useEffect(() => {
    reload();
  }, [reload]);

  // Auto-dismiss toast.
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  // Recherche libre debounced — même endpoint que le POS.
  useEffect(() => {
    if (freeDebounceRef.current) clearTimeout(freeDebounceRef.current);
    const q = freeQuery.trim();
    if (!q) { setFreeResults([]); return; }
    setFreeLoading(true);
    freeDebounceRef.current = setTimeout(async () => {
      try {
        const res = await api.get(`/api/inventory/products/search?q=${encodeURIComponent(q)}`);
        if (res.ok) setFreeResults(await res.json());
      } catch { /* silent */ } finally { setFreeLoading(false); }
    }, 300);
    return () => { if (freeDebounceRef.current) clearTimeout(freeDebounceRef.current); };
  }, [freeQuery]);

  // Sélectionner une pièce pour la placer en rayon. On ouvre le panneau de
  // placement et on demande à l'IA une zone suggérée (que l'opérateur pourra
  // confirmer ou modifier). C'est le flux unifié : peu importe que la pièce
  // vienne de la recherche, du flash code-barres ou d'une proposition IA.
  const selectForPlacement = useCallback(async (p: FreeProduct, preferredZoneId?: string) => {
    setError('');
    setPlacement({
      product: p,
      suggestion: null,
      chosenZoneId: preferredZoneId || '',
      loadingSuggestion: true,
    });
    try {
      const res = await api.get(`/api/inventory/products/${p.id}/suggest-zone`);
      const sug = res.ok ? await res.json() : null;
      setPlacement((prev) =>
        prev && prev.product.id === p.id
          ? {
              ...prev,
              suggestion: sug,
              // Zone pré-cochée : la zone proposée par l'achalandage (déficit)
              // si fournie, sinon la suggestion merchandising. L'opérateur reste
              // libre de la changer.
              chosenZoneId: preferredZoneId || (sug && sug.primary_zone_id) || '',
              loadingSuggestion: false,
            }
          : prev,
      );
    } catch {
      setPlacement((prev) =>
        prev && prev.product.id === p.id ? { ...prev, loadingSuggestion: false } : prev,
      );
    }
  }, []);

  // Confirmer le placement : exécute le mouvement réserve→rayon avec la zone
  // choisie (suggérée ou modifiée par l'opérateur).
  const confirmPlacement = useCallback(async () => {
    if (!placement || executing) return;
    const { product, chosenZoneId } = placement;
    setExecuting(true);
    try {
      const body: Record<string, unknown> = {
        barcode: product.barcode,
        to_status: 'displayed',
        reason: 'Achalandage réserve→rayon (placement confirmé)',
      };
      if (chosenZoneId) body.to_zone_id = chosenZoneId;
      const res = await api.post('/api/inventory/movements/execute', body);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setToast({ kind: 'error', text: (data && data.detail) || 'Mouvement refusé.' });
        return;
      }
      const result = data as ExecuteResult;
      setDone((prev) => ({ ...prev, [result.product_id]: result }));
      const zoneName = zones.find((z) => z.id === chosenZoneId)?.name;
      setToast({ kind: 'success', text: `${result.name} → ${zoneName || 'rayon'} ✓` });
      setFreeResults((prev) => prev.filter((x) => x.id !== product.id));
      setPlacement(null);
      setScanValue('');
      focusInput();
    } catch {
      setToast({ kind: 'error', text: 'Erreur réseau pendant le mouvement.' });
    } finally {
      setExecuting(false);
    }
  }, [placement, executing, zones, focusInput]);

  // Resolve the scanned barcode against the CURRENT tab's proposals.
  const resolveWeekly = (
    barcode: string,
  ): { item: WeeklyItem } | null => {
    if (!weekly) return null;
    for (const zone of weekly.zones) {
      const item = zone.items.find((it) => it.barcode === barcode);
      if (item) return { item };
    }
    return null;
  };

  const handleScan = async () => {
    const barcode = scanValue.trim();
    setScanValue('');
    focusInput();
    if (!barcode || executing) return;

    // Garde-fou mojibake : « &é"'(-è_çà » = douchette en QWERTY sur tablette
    // AZERTY. On n'envoie rien à l'API (aucun produit ne matchera).
    if (looksLikeScannerMojibake(barcode)) {
      setToast({ kind: 'error', text: SCANNER_MOJIBAKE_MESSAGE });
      return;
    }

    // ── Achalandage : le scan SÉLECTIONNE la pièce (n'importe laquelle) puis
    // ouvre le panneau de placement (zone suggérée à confirmer/modifier).
    if (tab === 'achalandage') {
      try {
        const res = await api.get(
          `/api/inventory/products/by-barcode/${encodeURIComponent(barcode)}`,
        );
        if (!res.ok) {
          setToast({ kind: 'warn', text: `Aucun article pour le code ${barcode}.` });
          return;
        }
        const p = await res.json();
        await selectForPlacement({
          id: p.id, barcode: p.barcode, name: p.name,
          sale_price: p.sale_price, status: p.status,
          category: p.category ?? null, photo_url: p.photo_url ?? null,
        });
      } catch {
        setToast({ kind: 'error', text: 'Erreur réseau pendant la lecture du code.' });
      }
      return;
    }

    // ── Aménagement (zone↔zone) : exécution directe contre la proposition,
    // car la zone cible vient du plan hebdo (pas de choix d'implantation).
    const match = resolveWeekly(barcode);
    if (!match) {
      setToast({ kind: 'warn', text: `Code ${barcode} hors proposition.` });
      return;
    }
    const productId = match.item.product_id;
    const body = {
      barcode,
      to_zone_id: match.item.to_zone_id,
      reason: 'Aménagement hebdo',
    };

    setExecuting(true);
    try {
      const res = await api.post('/api/inventory/movements/execute', body);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setToast({
          kind: 'error',
          text: (data && data.detail) || 'Mouvement refusé.',
        });
        return;
      }
      const result = data as ExecuteResult;
      setDone((prev) => ({ ...prev, [productId]: result }));
      setToast({ kind: 'success', text: `${result.name} déplacé ✓` });
    } catch {
      setToast({ kind: 'error', text: 'Erreur réseau pendant le mouvement.' });
    } finally {
      setExecuting(false);
      focusInput();
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleScan();
    }
  };

  // Achalandage : Entrée dans le moteur unifié = flash code-barres. On résout
  // la référence (exact match), sinon on prend l'unique résultat de recherche.
  const onAchalandageEnter = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const q = freeQuery.trim();
    if (!q || executing) return;
    if (looksLikeScannerMojibake(q)) {
      setToast({ kind: 'error', text: SCANNER_MOJIBAKE_MESSAGE });
      return;
    }
    try {
      const res = await api.get(`/api/inventory/products/by-barcode/${encodeURIComponent(q)}`);
      if (res.ok) {
        const p = await res.json();
        setFreeQuery('');
        setFreeResults([]);
        await selectForPlacement({
          id: p.id, barcode: p.barcode, name: p.name, sale_price: p.sale_price,
          status: p.status, category: p.category ?? null, photo_url: p.photo_url ?? null,
        });
        return;
      }
    } catch { /* fall through to search results */ }
    // Pas un code-barres exact : si la recherche a 1 seul résultat, on le prend.
    if (freeResults.length === 1) {
      await selectForPlacement(freeResults[0]);
    }
  };

  const doneCount = Object.keys(done).length;

  const plan = tab === 'amenagement' ? weekly : restock;
  const totalProposed =
    tab === 'amenagement'
      ? weekly?.zones.reduce((n, z) => n + z.items.length, 0) ?? 0
      : restock?.zones.reduce((n, z) => n + z.candidates.length, 0) ?? 0;

  const toastCls =
    toast?.kind === 'success'
      ? 'bg-vz-teal-soft text-vz-teal-deep border-vz-teal/40'
      : toast?.kind === 'warn'
        ? 'bg-amber-50 text-amber-700 border-amber-300'
        : 'bg-red-50 text-red-700 border-red-300';

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 max-w-5xl">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-1">
            <Link href="/inventory" className="text-sm text-vz-teal hover:text-vz-teal-deep">
              ← Inventaire
            </Link>
            <span className="text-gray-300">/</span>
            <h1 className="text-2xl font-bold text-black font-display">Mouvements de stock</h1>
          </div>
          <p className="text-gray-500">
            Le moteur propose, vous scannez le code-barres, le mouvement est exécuté
            et historisé.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg mb-4 w-fit">
          {([
            { key: 'amenagement', label: 'Aménagement (hebdo)' },
            { key: 'achalandage', label: 'Achalandage (réserve → rayon)' },
          ] as { key: Tab; label: string }[]).map((t) => (
            <button
              key={t.key}
              onClick={() => {
                setTab(t.key);
                setPlacement(null);
                setFreeQuery('');
                setFreeResults([]);
              }}
              className={`px-4 py-2 rounded-lg text-sm font-medium min-h-[48px] transition-colors ${
                tab === t.key ? 'bg-white text-vz-teal shadow-sm' : 'text-gray-500 hover:text-black'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* AMÉNAGEMENT — douchette : scan contre la proposition hebdo (zone↔zone) */}
        {tab === 'amenagement' && (
          <Card className="mb-4">
            <div className="flex flex-col sm:flex-row sm:items-end gap-3">
              <div className="flex-1">
                <label className="block text-sm font-medium text-black mb-1.5">
                  Scanner le code-barres
                </label>
                <input
                  ref={inputRef}
                  autoFocus
                  value={scanValue}
                  onChange={(e) => setScanValue(e.target.value)}
                  onKeyDown={onKeyDown}
                  onBlur={focusInput}
                  placeholder="Douchette ou saisie manuelle puis Entrée…"
                  className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black font-mono focus:outline-none focus:ring-2 focus:ring-vz-teal"
                />
              </div>
              <Button variant="outline" onClick={reload} disabled={loading}>
                {loading ? 'Chargement…' : 'Régénérer la proposition'}
              </Button>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-gray-500">
              <span>{totalProposed} pièce(s) proposée(s)</span>
              <span className="text-vz-teal font-medium">{doneCount} fait(s) ✓</span>
              {executing && <span className="text-gray-400">Exécution…</span>}
            </div>
          </Card>
        )}

        {/* ACHALANDAGE — moteur UNIQUE : recherche (toutes références) OU flash
            code-barres. L'IA propose une zone, l'opérateur confirme ou modifie. */}
        {tab === 'achalandage' && (
          <Card className="mb-4">
            <label className="block text-sm font-medium text-black mb-1.5">
              Rechercher ou flasher une référence
            </label>
            <div className="flex gap-3">
              <div className="relative flex-1">
                <input
                  ref={inputRef}
                  autoFocus
                  value={freeQuery}
                  onChange={(e) => setFreeQuery(e.target.value)}
                  onKeyDown={onAchalandageEnter}
                  placeholder="Nom, marque ou code-barres — ou flashez puis Entrée"
                  className="w-full min-h-[48px] px-4 py-2.5 pr-9 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                />
                {freeQuery && (
                  <button
                    type="button"
                    onClick={() => { setFreeQuery(''); setFreeResults([]); }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    aria-label="Effacer"
                  >
                    ✕
                  </button>
                )}
              </div>
              <Button variant="outline" onClick={reload} disabled={loading}>
                {loading ? '…' : 'Régénérer'}
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-gray-500">
              <span>{totalProposed} proposée(s) par l&apos;IA</span>
              <span className="text-vz-teal font-medium">{doneCount} placée(s) ✓</span>
            </div>

            {/* Résultats de recherche (masqués quand un placement est en cours) */}
            {!placement && freeLoading && <p className="mt-2 text-xs text-gray-400">Recherche…</p>}
            {!placement && freeResults.length > 0 && (
              <ul className="mt-3 divide-y divide-gray-100 max-h-64 overflow-y-auto">
                {freeResults.map((p) => {
                  const onFloor = ['display', 'displayed', 'discounted', 'deep_discounted'].includes(p.status);
                  return (
                    <li key={p.id} className="flex items-center justify-between gap-3 py-2">
                      <div className="min-w-0">
                        <p className="text-sm text-black truncate">{p.name}</p>
                        <p className="text-xs text-gray-400 font-mono truncate">
                          {p.barcode}{p.category ? ` · ${p.category}` : ''} · {p.status}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        onClick={() => selectForPlacement(p)}
                        disabled={onFloor}
                        title={onFloor ? 'Déjà en rayon' : 'Choisir et placer en rayon'}
                      >
                        {onFloor ? 'En rayon' : 'Placer'}
                      </Button>
                    </li>
                  );
                })}
              </ul>
            )}
            {!placement && freeQuery && !freeLoading && freeResults.length === 0 && (
              <p className="mt-2 text-xs text-gray-400">Aucun article trouvé.</p>
            )}

            {/* Panneau de placement : zone suggérée par l'IA, modifiable */}
            {placement && (
              <div className="mt-4 p-4 rounded-lg border-2 border-vz-teal bg-vz-teal-soft/30">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-black truncate">{placement.product.name}</p>
                    <p className="text-xs text-gray-500 font-mono truncate">
                      {placement.product.barcode}
                      {placement.product.category ? ` · ${placement.product.category}` : ''}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setPlacement(null); focusInput(); }}
                    className="text-gray-400 hover:text-gray-600 text-sm flex-shrink-0"
                  >
                    Annuler
                  </button>
                </div>
                <div className="mt-3">
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Zone d&apos;implantation
                    {placement.loadingSuggestion && <span className="text-gray-400 font-normal"> (suggestion IA…)</span>}
                  </label>
                  <select
                    value={placement.chosenZoneId}
                    onChange={(e) => setPlacement((prev) => (prev ? { ...prev, chosenZoneId: e.target.value } : prev))}
                    className="w-full min-h-[48px] px-3 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                  >
                    <option value="">— Rayon (sans zone précise) —</option>
                    {zones.map((z) => (
                      <option key={z.id} value={z.id}>{z.name}</option>
                    ))}
                  </select>
                  {placement.suggestion?.primary_zone_name && (
                    <p className="mt-1.5 text-xs text-vz-teal-deep">
                      💡 Suggéré : <strong>{placement.suggestion.primary_zone_name}</strong>
                      {placement.suggestion.rationale ? ` — ${placement.suggestion.rationale}` : ''}
                    </p>
                  )}
                  {placement.suggestion?.alternative_zone_id && placement.suggestion.alternative_zone_id !== placement.chosenZoneId && (
                    <button
                      type="button"
                      onClick={() => setPlacement((prev) => (prev && prev.suggestion?.alternative_zone_id ? { ...prev, chosenZoneId: prev.suggestion.alternative_zone_id } : prev))}
                      className="mt-1 text-xs text-gray-500 underline"
                    >
                      Alternative : {placement.suggestion.alternative_zone_name}
                    </button>
                  )}
                </div>
                <div className="mt-3 flex gap-2">
                  <Button onClick={confirmPlacement} disabled={executing}>
                    {executing ? 'Placement…' : 'Confirmer le placement →'}
                  </Button>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Toast partagé (les deux onglets) */}
        {toast && (
          <div className={`mb-4 px-3 py-2 rounded-lg border text-sm ${toastCls}`}>
            {toast.text}
          </div>
        )}

        {error && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
        )}

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-vz-teal" />
          </div>
        ) : tab === 'amenagement' ? (
          <WeeklyView plan={weekly} done={done} />
        ) : (
          <RestockView
            plan={restock}
            done={done}
            onPick={(item, zoneId) => selectForPlacement(
              {
                id: item.product_id, barcode: item.barcode, name: item.name,
                sale_price: 0, status: 'stock', category: null, photo_url: null,
              },
              zoneId,
            )}
          />
        )}

        {!loading && plan && totalProposed === 0 && (
          <Card>
            <p className="text-gray-400 text-center py-6">
              Aucun mouvement proposé cette semaine.
            </p>
          </Card>
        )}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Aménagement (horizontal) — group by source zone
// ---------------------------------------------------------------------------

function WeeklyView({
  plan,
  done,
}: {
  plan: WeeklyPlan | null;
  done: Record<string, ExecuteResult>;
}) {
  if (!plan || plan.zones.length === 0) return null;
  return (
    <div className="space-y-4">
      {plan.zones.map((zone) => (
        <Card
          key={zone.from_zone_id ?? 'none'}
          title={`De la zone ${zone.from_zone_name}, déplacez :`}
          subtitle={`${zone.n_moves} pièce(s)`}
        >
          <ul className="divide-y divide-gray-100">
            {zone.items.map((item) => {
              const isDone = !!done[item.product_id];
              return (
                <li
                  key={item.product_id}
                  className={`py-3 flex flex-wrap items-start justify-between gap-3 ${
                    isDone ? 'opacity-50' : ''
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p
                        className={`text-sm font-medium text-vz-ink ${
                          isDone ? 'line-through' : ''
                        }`}
                      >
                        {item.name}
                      </p>
                      <BucketBadge bucket={item.score_bucket} />
                      {isDone && <span className="text-vz-teal text-sm">✓</span>}
                    </div>
                    <p className="text-xs text-gray-500">{describe(item)}</p>
                    <p className="text-[11px] font-mono text-gray-400 mt-0.5">{item.barcode}</p>
                    {item.rationale && (
                      <p className="text-xs text-gray-400 mt-1 italic">{item.rationale}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-[11px] uppercase tracking-wide text-gray-400">Vers</p>
                    <p className="text-sm font-medium text-vz-teal">{item.to_zone_name}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </Card>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Achalandage (vertical) — per deficient zone, candidates to bring up
// ---------------------------------------------------------------------------

function RestockView({
  plan,
  done,
  onPick,
}: {
  plan: RestockPlan | null;
  done: Record<string, ExecuteResult>;
  onPick: (item: PlanItem, zoneId: string, zoneName: string) => void;
}) {
  if (!plan || plan.zones.length === 0) return null;
  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500">
        {plan.stock_available} pièce(s) disponible(s) en réserve · ventes sur{' '}
        {plan.period_days} jours
      </p>
      {plan.zones.map((zone) => (
        <Card
          key={zone.zone_id}
          title={zone.zone_name}
          subtitle={`${zone.current}${zone.capacity != null ? ` / ${zone.capacity}` : ''} en rayon${
            zone.occupancy_pct != null ? ` · ${zone.occupancy_pct}% occupé` : ''
          }`}
        >
          <div className="flex flex-wrap gap-4 mb-3 text-xs">
            <span className="text-gray-500">
              Déficit&nbsp;: <strong className="text-amber-600">{zone.deficit}</strong>
            </span>
            <span className="text-gray-500">
              Ventes récentes&nbsp;: <strong className="text-vz-ink">{zone.recent_sales}</strong>
            </span>
          </div>
          {zone.candidates.length === 0 ? (
            <p className="text-sm text-gray-400">Aucune pièce candidate en réserve.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {zone.candidates.map((item) => {
                const isDone = !!done[item.product_id];
                return (
                  <li
                    key={item.product_id}
                    className={`py-3 flex flex-wrap items-center justify-between gap-3 ${
                      isDone ? 'opacity-50' : ''
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p
                          className={`text-sm font-medium text-vz-ink ${
                            isDone ? 'line-through' : ''
                          }`}
                        >
                          {item.name}
                        </p>
                        <BucketBadge bucket={item.score_bucket} />
                        {isDone && <span className="text-vz-teal text-sm">✓</span>}
                      </div>
                      <p className="text-xs text-gray-500">{describe(item)}</p>
                      <p className="text-[11px] font-mono text-gray-400 mt-0.5">{item.barcode}</p>
                    </div>
                    {!isDone && (
                      <Button
                        variant="outline"
                        onClick={() => onPick(item, zone.zone_id, zone.zone_name)}
                        title={`Placer en ${zone.zone_name}`}
                      >
                        Placer
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      ))}
    </div>
  );
}
