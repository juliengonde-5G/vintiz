'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import { api } from '@/lib/api';

interface ApproLine {
  category: string;
  gender: string;
  quality_hint: string;
  action: string;
  demand_share: number | null;
  stock_count: number;
  brands: string | null;
  rationale: string;
}

interface ApproBrief {
  generated_at: string;
  cold_start: boolean;
  dominant_gender: string;
  n_members_profiled: number;
  period_days: number;
  signals: {
    cohort_size: number;
    top_brands: string[];
    gender_skew: Record<string, number>;
  };
  lines: ApproLine[];
}

const ACTION_STYLE: Record<string, string> = {
  demander: 'bg-vz-teal text-white',
  renforcer: 'bg-vz-teal-soft text-vz-teal-deep',
  reduire: 'bg-amber-100 text-amber-800',
  maintenir: 'bg-gray-100 text-gray-600',
};
const ACTION_LABEL: Record<string, string> = {
  demander: 'Demander un carton',
  renforcer: 'Renforcer',
  reduire: 'Réduire',
  maintenir: 'Maintenir',
};

export default function BriefApproPage() {
  const [brief, setBrief] = useState<ApproBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/appro-brief');
      if (!res.ok) throw new Error('Brief indisponible');
      setBrief(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur inconnue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="flex min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="flex-1 ml-64 p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-display text-vz-ink">Brief d&apos;appro</h1>
            <p className="text-sm text-vz-ink-soft mt-1">
              La demande des membres pilote les cartons à faire rentrer.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/ia"
              className="px-3 py-2 text-sm border border-vz-line rounded-lg hover:bg-vz-surface"
            >
              ← Compagnon
            </Link>
            <button
              onClick={load}
              disabled={loading}
              className="px-3 py-2 text-sm bg-vz-teal text-white rounded-lg hover:bg-vz-teal-deep disabled:opacity-50"
            >
              {loading ? 'Calcul…' : 'Rafraîchir'}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        {loading && !brief && (
          <p className="text-vz-ink-soft text-sm">Chargement…</p>
        )}

        {brief && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs text-vz-ink-soft mb-4">
              {brief.cold_start && (
                <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200">
                  Pré-lancement — signal déclaratif
                </span>
              )}
              <span>
                Audience dominante : <strong>{brief.dominant_gender}</strong>
              </span>
              <span>· {brief.n_members_profiled} membres profilés</span>
              <span>· cohorte fidèle {brief.signals?.cohort_size ?? 0}</span>
              <span>· {brief.period_days} j</span>
            </div>

            {brief.lines.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {brief.lines.map((line, i) => (
                  <div
                    key={i}
                    className="rounded-xl border border-vz-line bg-vz-surface p-4"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-medium text-vz-ink capitalize">
                        {line.category} · {line.gender}
                      </p>
                      <span
                        className={`text-[11px] px-2 py-0.5 rounded-full whitespace-nowrap ${
                          ACTION_STYLE[line.action] || 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {ACTION_LABEL[line.action] || line.action}
                      </span>
                    </div>
                    <p className="text-xs text-vz-ink-mute mt-1">{line.rationale}</p>
                    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-vz-ink-soft mt-2">
                      {line.demand_share != null && (
                        <span>Demande {Math.round(line.demand_share * 100)}%</span>
                      )}
                      <span>Stock {line.stock_count}</span>
                      <span>Qualité {line.quality_hint}</span>
                      {line.brands && (
                        <span className="truncate">Marques : {line.brands}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-vz-ink-soft text-sm">
                Aucun signal de demande pour l&apos;instant.
              </p>
            )}

            <p className="text-[11px] text-vz-ink-mute mt-4">
              Recommandations au niveau carton (catégorie × genre × qualité). La
              connexion au centre d&apos;appro est une 2ᵉ étape.
            </p>
          </>
        )}
      </main>
    </div>
  );
}
