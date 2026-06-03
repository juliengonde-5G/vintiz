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

  const focusInput = useCallback(() => {
    // Defer so it survives re-renders / DOM updates after a scan.
    requestAnimationFrame(() => inputRef.current?.focus());
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

  // Déplacer une pièce réserve→rayon (achalandage manuel, hors proposition).
  // Statut → displayed ; la zone d'origine est conservée (l'IA / l'opérateur
  // affinent ensuite). Marche pour TOUT le stock, pas seulement la proposition.
  const moveToFloor = useCallback(async (p: FreeProduct) => {
    if (executing) return;
    setExecuting(true);
    try {
      const res = await api.post('/api/inventory/movements/execute', {
        barcode: p.barcode,
        to_status: 'displayed',
        reason: 'Achalandage manuel (recherche libre)',
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setToast({ kind: 'error', text: (data && data.detail) || 'Mouvement refusé.' });
        return;
      }
      const result = data as ExecuteResult;
      setDone((prev) => ({ ...prev, [result.product_id]: result }));
      setToast({ kind: 'success', text: `${result.name} → rayon ✓` });
      // Retire la pièce déplacée des résultats pour éviter un double envoi.
      setFreeResults((prev) => prev.filter((x) => x.id !== p.id));
    } catch {
      setToast({ kind: 'error', text: 'Erreur réseau pendant le mouvement.' });
    } finally {
      setExecuting(false);
    }
  }, [executing]);

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

  const resolveRestock = (
    barcode: string,
  ): { item: PlanItem; zone: RestockZone } | null => {
    if (!restock) return null;
    for (const zone of restock.zones) {
      const item = zone.candidates.find((it) => it.barcode === barcode);
      if (item) return { item, zone };
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

    let body: Record<string, unknown> | null = null;
    let productId: string | null = null;

    if (tab === 'amenagement') {
      const match = resolveWeekly(barcode);
      if (!match) {
        setToast({ kind: 'warn', text: `Code ${barcode} hors proposition.` });
        return;
      }
      productId = match.item.product_id;
      body = {
        barcode,
        to_zone_id: match.item.to_zone_id,
        reason: 'Aménagement hebdo',
      };
    } else {
      const match = resolveRestock(barcode);
      if (!match) {
        // Hors proposition : on ne bloque plus. En achalandage, toute pièce
        // scannée part en rayon (réserve→rayon), proposition ou pas — c'est
        // ce que veut l'opérateur qui vide la réserve.
        body = {
          barcode,
          to_status: 'displayed',
          reason: 'Achalandage réserve→rayon (hors proposition)',
        };
      } else {
        productId = match.item.product_id;
        body = {
          barcode,
          to_status: 'displayed',
          to_zone_id: match.zone.zone_id,
          reason: 'Achalandage réserve→rayon',
        };
      }
    }

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
      setDone((prev) => ({ ...prev, [productId as string]: result }));
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
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium min-h-[48px] transition-colors ${
                tab === t.key ? 'bg-white text-vz-teal shadow-sm' : 'text-gray-500 hover:text-black'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Scan bar */}
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
            <span>
              {totalProposed} pièce(s) proposée(s)
            </span>
            <span className="text-vz-teal font-medium">{doneCount} fait(s) ✓</span>
            {executing && <span className="text-gray-400">Exécution…</span>}
          </div>
          {toast && (
            <div className={`mt-3 px-3 py-2 rounded-lg border text-sm ${toastCls}`}>
              {toast.text}
            </div>
          )}
          <p className="mt-2 text-xs text-gray-400">
            Astuce : une pièce scannée hors proposition part quand même en
            rayon (réserve→rayon). Pour chercher par nom, utilisez la recherche
            ci-dessous.
          </p>
        </Card>

        {/* Recherche libre — déplacer TOUT le stock réserve→rayon, même hors
            proposition. Même moteur de recherche que le POS. */}
        <Card className="mb-4">
          <label className="block text-sm font-medium text-black mb-1.5">
            Recherche libre (tout le stock) — envoyer en rayon
          </label>
          <div className="relative">
            <input
              value={freeQuery}
              onChange={(e) => setFreeQuery(e.target.value)}
              placeholder="Nom, marque ou code-barres…"
              className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
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
          {freeLoading && <p className="mt-2 text-xs text-gray-400">Recherche…</p>}
          {freeResults.length > 0 && (
            <ul className="mt-3 divide-y divide-gray-100 max-h-72 overflow-y-auto">
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
                      onClick={() => moveToFloor(p)}
                      disabled={executing || onFloor}
                      title={onFloor ? 'Déjà en rayon' : 'Envoyer en rayon'}
                    >
                      {onFloor ? 'En rayon' : '→ Rayon'}
                    </Button>
                  </li>
                );
              })}
            </ul>
          )}
          {freeQuery && !freeLoading && freeResults.length === 0 && (
            <p className="mt-2 text-xs text-gray-400">Aucun article trouvé.</p>
          )}
        </Card>

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
          <RestockView plan={restock} done={done} />
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
}: {
  plan: RestockPlan | null;
  done: Record<string, ExecuteResult>;
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
