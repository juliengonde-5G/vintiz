'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import SectionHeader from '@/components/ui/SectionHeader';
import { api } from '@/lib/api';

type Report = {
  generated_at?: string;
  report?: any;
  [k: string]: any;
};

export default function MarketingReportPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post('/api/ai/persona/marketing', {});
      if (!res.ok) throw new Error('report failed');
      setReport(await res.json());
    } catch {
      setError('Le rapport n\u2019a pas pu etre genere. Verifie la cle ANTHROPIC_API_KEY.');
    } finally {
      setLoading(false);
    }
  };

  const r = report?.report || report;

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8 max-w-5xl">
        <Link href="/ia" className="inline-flex items-center gap-2 text-sm text-vz-teal hover:text-vz-teal-deep mb-4">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          Retour au compagnon IA
        </Link>

        <div className="rounded-3xl bg-vz-teal p-6 md:p-8 text-white shadow-vz-soft mb-6 relative overflow-hidden">
          <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/10 blur-2xl" />
          <div className="relative z-10 flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-[11px] tracking-[0.22em] uppercase font-medium opacity-90">
                Persona · Manager marketing
              </p>
              <h1 className="text-3xl md:text-4xl font-display font-semibold mt-1">
                Rapport marketing
              </h1>
              <p className="text-sm opacity-90 mt-1 max-w-xl">
                Une analyse strategique de la boutique : positionnement, audiences,
                actions prioritaires et KPI a suivre — produite par Claude, affinee par
                les donnees Vintiz.
              </p>
            </div>
            <Button onClick={generate} disabled={loading} variant="secondary">
              {loading ? 'Analyse en cours…' : report ? 'Regenerer' : 'Generer le rapport'}
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-vz-accent-soft bg-vz-accent-soft text-vz-accent px-4 py-3 text-sm">
            {error}
          </div>
        )}

        {!report && !loading && (
          <Card variant="gradient">
            <p className="text-sm text-gray-700">
              Clique sur <strong>Generer le rapport</strong> pour obtenir une analyse
              fraiche : le persona manager marketing evaluera la position actuelle de la
              boutique, proposera 3 a 5 actions prioritaires, et formulera des cibles
              chiffrees pour les 30 prochains jours.
            </p>
          </Card>
        )}

        {loading && (
          <Card>
            <div className="flex items-center gap-3 text-sm text-gray-600">
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" />
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" style={{ animationDelay: '150ms' }} />
              <span className="h-2 w-2 bg-vz-teal rounded-full animate-pulse" style={{ animationDelay: '300ms' }} />
              <span>Le manager marketing IA reflechit…</span>
            </div>
          </Card>
        )}

        {r && (
          <div className="space-y-6 animate-slide-up">
            {r.resume_executif && (
              <Card title="Resume executif" icon={<span>📋</span>}>
                <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-line">{r.resume_executif}</p>
              </Card>
            )}

            {r.positionnement && (
              <Card title="Positionnement" icon={<span>🎯</span>}>
                <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-line">{r.positionnement}</p>
              </Card>
            )}

            {Array.isArray(r.audiences_cibles) && r.audiences_cibles.length > 0 && (
              <Card title="Audiences cibles" icon={<span>👥</span>}>
                <ul className="space-y-2">
                  {r.audiences_cibles.map((a: any, i: number) => (
                    <li key={i} className="rounded-xl bg-vz-bg px-4 py-3">
                      <p className="font-medium text-black">{a.segment || a.nom || `Segment ${i + 1}`}</p>
                      {a.description && <p className="text-sm text-gray-600 mt-0.5">{a.description}</p>}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {Array.isArray(r.actions_prioritaires) && r.actions_prioritaires.length > 0 && (
              <Card title="Actions prioritaires" icon={<span>🚀</span>}>
                <ol className="space-y-3">
                  {r.actions_prioritaires.map((a: any, i: number) => (
                    <li key={i} className="flex items-start gap-3 rounded-xl bg-white border border-vz-teal-soft px-4 py-3">
                      <span className="h-7 w-7 rounded-full bg-vz-teal text-white flex items-center justify-center text-sm font-semibold flex-shrink-0">
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <p className="font-medium text-black">{a.action || a.titre || a.name}</p>
                        {a.impact && <p className="text-sm text-gray-600 mt-0.5">Impact estime : {a.impact}</p>}
                        {a.priorite && (
                          <span className="inline-block mt-1 text-[10px] font-semibold tracking-wider px-2 py-0.5 rounded-full bg-vz-accent-soft text-vz-accent uppercase">
                            {a.priorite}
                          </span>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </Card>
            )}

            {r.kpi_cibles && (
              <Card title="KPI cibles" icon={<span>📊</span>}>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {Object.entries(r.kpi_cibles).map(([k, v]) => (
                    <div key={k} className="rounded-xl bg-vz-bg px-4 py-3">
                      <p className="text-[11px] uppercase tracking-wider text-gray-500">
                        {k.replace(/_/g, ' ')}
                      </p>
                      <p className="font-display font-semibold text-lg text-black mt-0.5">
                        {typeof v === 'number' ? v.toLocaleString('fr-FR') : String(v)}
                      </p>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            <p className="text-xs text-gray-400 text-center">
              {report?.generated_at ? `Genere le ${report.generated_at}` : 'Rapport genere par Claude'}
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
