'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import CahierForecastPanel from '@/components/dashboard/CahierForecastPanel';
import { api } from '@/lib/api';

interface CahierPayload {
  date: string;
  is_past: boolean;
  weekday: string;
  header: {
    weather: { icon?: string; temp?: number; description?: string } | null;
    message_du_jour: string | null;
    operation_en_cours: string | null;
  };
  objectifs_valeur: {
    ca_budget_mois: number | null;
    ca_objectif_jour: number | null;
    ca_n1_jour: number;
    ca_n1_source: string;
    prog_ca_cumul_mois: number;
    reste_a_faire_mois: number | null;
  };
  performance: {
    obj: number | null;
    ca: number;
    ca_n1: number;
    prog_vs_obj_pct: number | null;
    delta_vs_n1_pct: number | null;
    tx_crm_pct: number;
    loyalty_pct: number;
    tk: number;
    iv: number;
    pm: number;
    prod: number;
  };
  zoning: {
    zone_id: string;
    zone_name: string;
    color_code: string;
    obj_jour: number;
    ca: number;
    ca_n1: number;
    delta_pct: number | null;
    units: number;
  }[];
  crm_loyalty: {
    fiches_creees: number;
    adhesions_fidelite: number;
    reprints: number;
    tickets_fidelo: number;
  };
  progression_horaire: { hour: number; ca_cumul: number }[];
  progression_cible_horaire: { hour: number; ca_target: number }[];
}

const CURRENCY = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });

const todayISO = () => new Date().toISOString().slice(0, 10);

const N1_SOURCE_LABELS: Record<string, string> = {
  same_date_last_year: 'Compare a la meme date N-1',
  same_weekday_last_week: 'Historique insuffisant — meme jour semaine passee',
  rolling_4_weeks_avg: 'Moyenne 4 dernieres occurrences',
  unavailable: 'Aucun historique comparable',
};

export default function CahierDuJourPage() {
  const [data, setData] = useState<CahierPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedDate, setSelectedDate] = useState<string>(todayISO());
  const [messageDraft, setMessageDraft] = useState('');
  const [operationDraft, setOperationDraft] = useState('');
  const [editingText, setEditingText] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');

  useEffect(() => {
    const url = new URL(window.location.href);
    const q = url.searchParams.get('date');
    if (q) setSelectedDate(q);
  }, []);

  const fetchCahier = useCallback(async (d: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/api/cahier/${d}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(body.detail || 'Erreur de chargement');
        setData(null);
      } else {
        const payload: CahierPayload = await res.json();
        setData(payload);
        setMessageDraft(payload.header.message_du_jour || '');
        setOperationDraft(payload.header.operation_en_cours || '');
      }
    } catch {
      setError('Erreur reseau');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCahier(selectedDate);
  }, [fetchCahier, selectedDate]);

  // Poll every 60s only when viewing today and not editing
  useEffect(() => {
    if (selectedDate !== todayISO() || editingText) return;
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') fetchCahier(selectedDate);
    }, 60000);
    return () => clearInterval(id);
  }, [fetchCahier, selectedDate, editingText]);

  const navigateDay = (offset: number) => {
    const d = new Date(selectedDate + 'T00:00:00');
    d.setDate(d.getDate() + offset);
    const iso = d.toISOString().slice(0, 10);
    setSelectedDate(iso);
    const url = new URL(window.location.href);
    if (iso === todayISO()) url.searchParams.delete('date');
    else url.searchParams.set('date', iso);
    window.history.replaceState({}, '', url.toString());
  };

  const setDateDirect = (iso: string) => {
    setSelectedDate(iso);
    const url = new URL(window.location.href);
    if (iso === todayISO()) url.searchParams.delete('date');
    else url.searchParams.set('date', iso);
    window.history.replaceState({}, '', url.toString());
  };

  const saveTexts = async () => {
    setSaving(true);
    const res = await api.put('/api/cahier/daily-text', {
      date: selectedDate,
      message_du_jour: messageDraft,
      operation_en_cours: operationDraft,
    });
    setSaving(false);
    if (res.ok) {
      setEditingText(false);
      setToast('Textes enregistres');
      setTimeout(() => setToast(''), 2000);
      fetchCahier(selectedDate);
    } else {
      setError('Enregistrement impossible');
    }
  };

  const isPast = data?.is_past ?? false;
  const readOnly = isPast;

  const formattedDate = useMemo(() => {
    if (!data) return '';
    const d = new Date(data.date + 'T00:00:00');
    return d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  }, [data]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-4 md:p-8 cahier-main">
        <style jsx global>{`
          @media print {
            aside, .no-print, .cahier-main > .cahier-toolbar { display: none !important; }
            main.cahier-main { margin-left: 0 !important; padding: 0 !important; }
            body { background: white !important; }
            .cahier-page { box-shadow: none !important; break-inside: avoid; }
          }
        `}</style>

        {/* Toolbar (hidden when printing) */}
        <div className="cahier-toolbar mb-4 flex flex-wrap items-center gap-2 justify-between">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => navigateDay(-1)}>
              &laquo; Jour precedent
            </Button>
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setDateDirect(e.target.value)}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm min-h-[36px]"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigateDay(1)}
            >
              Jour suivant &raquo;
            </Button>
            {selectedDate !== todayISO() && (
              <Button variant="secondary" size="sm" onClick={() => setDateDirect(todayISO())}>
                Aujourd&apos;hui
              </Button>
            )}
          </div>
          <Button onClick={() => window.print()} variant="outline" size="sm">
            Imprimer
          </Button>
        </div>

        {toast && (
          <div className="mb-3 p-2 bg-vz-teal-soft text-vz-teal border border-vz-teal-soft rounded-lg text-sm">
            {toast}
          </div>
        )}
        {error && (
          <div className="mb-3 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        {loading && !data && <p className="text-gray-500">Chargement du cahier...</p>}

        {data && (
          <div className="cahier-page max-w-[900px] mx-auto bg-white rounded-2xl shadow-vz-soft p-6 md:p-8 space-y-6">
            {isPast && (
              <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-3 py-2">
                Archive — consultation uniquement
              </div>
            )}

            {/* L2.4 — Bandeau prévisionnel : saison + vacances + événements + opérations */}
            <CahierForecastPanel date={selectedDate} />

            {/* Header */}
            <section>
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <h1 className="text-2xl font-display font-bold text-black capitalize">
                    Cahier de travail
                  </h1>
                  <p className="text-sm text-gray-500 capitalize">{formattedDate}</p>
                </div>
                {data.header.weather && (
                  <div className="flex items-center gap-3 bg-vz-bg rounded-xl px-4 py-2">
                    {data.header.weather.icon && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={`https://openweathermap.org/img/wn/${data.header.weather.icon}@2x.png`}
                        alt={data.header.weather.description || ''}
                        className="h-10 w-10"
                      />
                    )}
                    <div>
                      <div className="font-bold text-lg leading-none">
                        {data.header.weather.temp != null ? `${Math.round(data.header.weather.temp)}°` : '—'}
                      </div>
                      <div className="text-xs text-gray-500 capitalize">
                        {data.header.weather.description}
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                <div className="border border-vz-teal-soft rounded-xl p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-vz-teal uppercase tracking-wider">
                      Message du jour
                    </span>
                    {!readOnly && !editingText && (
                      <button
                        onClick={() => setEditingText(true)}
                        className="text-xs text-vz-teal underline"
                      >
                        Modifier
                      </button>
                    )}
                  </div>
                  {editingText && !readOnly ? (
                    <textarea
                      className="w-full text-sm border border-gray-200 rounded-lg p-2 min-h-[60px]"
                      value={messageDraft}
                      onChange={(e) => setMessageDraft(e.target.value)}
                    />
                  ) : (
                    <p className="text-sm text-black whitespace-pre-wrap min-h-[24px]">
                      {data.header.message_du_jour || <span className="text-gray-400 italic">Aucun message</span>}
                    </p>
                  )}
                </div>

                <div className="border border-vz-accent-soft rounded-xl p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-black uppercase tracking-wider">
                      Operation en cours
                    </span>
                    {!readOnly && !editingText && (
                      <button
                        onClick={() => setEditingText(true)}
                        className="text-xs text-vz-teal underline"
                      >
                        Modifier
                      </button>
                    )}
                  </div>
                  {editingText && !readOnly ? (
                    <textarea
                      className="w-full text-sm border border-gray-200 rounded-lg p-2 min-h-[60px]"
                      value={operationDraft}
                      onChange={(e) => setOperationDraft(e.target.value)}
                    />
                  ) : (
                    <p className="text-sm text-black whitespace-pre-wrap min-h-[24px]">
                      {data.header.operation_en_cours || <span className="text-gray-400 italic">Aucune operation</span>}
                    </p>
                  )}
                </div>
              </div>
              {editingText && !readOnly && (
                <div className="flex gap-2 mt-2">
                  <Button onClick={saveTexts} disabled={saving} size="sm">
                    {saving ? 'Enregistrement...' : 'Enregistrer'}
                  </Button>
                  <Button
                    onClick={() => {
                      setEditingText(false);
                      setMessageDraft(data.header.message_du_jour || '');
                      setOperationDraft(data.header.operation_en_cours || '');
                    }}
                    variant="outline"
                    size="sm"
                  >
                    Annuler
                  </Button>
                </div>
              )}
            </section>

            {/* Objectifs valeur */}
            <section>
              <h2 className="text-sm font-display font-semibold text-black uppercase tracking-wider mb-3">
                Objectifs jour en valeur
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatBlock
                  label="CA budget"
                  value={CURRENCY(data.objectifs_valeur.ca_objectif_jour)}
                  hint={data.objectifs_valeur.ca_budget_mois != null ? `Mois : ${CURRENCY(data.objectifs_valeur.ca_budget_mois)}` : 'Non defini'}
                />
                <StatBlock
                  label="CA N-1"
                  value={CURRENCY(data.objectifs_valeur.ca_n1_jour)}
                  hint={N1_SOURCE_LABELS[data.objectifs_valeur.ca_n1_source] || ''}
                />
                <StatBlock
                  label="Prog. CA cumul mois"
                  value={CURRENCY(data.objectifs_valeur.prog_ca_cumul_mois)}
                  accent="teal"
                />
                <StatBlock
                  label="Reste a faire"
                  value={CURRENCY(data.objectifs_valeur.reste_a_faire_mois)}
                  accent="pink"
                />
              </div>
            </section>

            {/* Performance */}
            <section>
              <h2 className="text-sm font-display font-semibold text-black uppercase tracking-wider mb-3">
                Performance du jour
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-vz-bg text-xs uppercase text-gray-600">
                      <Th>OBJ</Th>
                      <Th>CA</Th>
                      <Th>CA N-1</Th>
                      <Th>PROG vs OBJ</Th>
                      <Th>DELTA N-1</Th>
                      <Th>TX CRM</Th>
                      <Th>GOLD</Th>
                      <Th>TK</Th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <Td>{CURRENCY(data.performance.obj)}</Td>
                      <Td accent>{CURRENCY(data.performance.ca)}</Td>
                      <Td>{CURRENCY(data.performance.ca_n1)}</Td>
                      <Td>{data.performance.prog_vs_obj_pct != null ? `${data.performance.prog_vs_obj_pct}%` : '—'}</Td>
                      <Td>
                        {data.performance.delta_vs_n1_pct != null ? (
                          <span className={data.performance.delta_vs_n1_pct >= 0 ? 'text-vz-teal font-semibold' : 'text-red-600 font-semibold'}>
                            {data.performance.delta_vs_n1_pct > 0 ? '+' : ''}{data.performance.delta_vs_n1_pct}%
                          </span>
                        ) : '—'}
                      </Td>
                      <Td>{data.performance.tx_crm_pct}%</Td>
                      <Td>{data.performance.loyalty_pct}%</Td>
                      <Td>{data.performance.tk}</Td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div className="mt-3 flex flex-wrap gap-4 text-sm text-gray-600">
                <span>IV : <strong className="text-black">{data.performance.iv}</strong></span>
                <span>PM : <strong className="text-black">{CURRENCY(data.performance.pm)}</strong></span>
                <span>PROD : <strong className="text-black">{CURRENCY(data.performance.prod)}</strong></span>
              </div>
            </section>

            {/* Progression horaire */}
            <section>
              <h2 className="text-sm font-display font-semibold text-black uppercase tracking-wider mb-3">
                Progression du jour
              </h2>
              <ProgressionChart
                real={data.progression_horaire}
                target={data.progression_cible_horaire}
              />
            </section>

            {/* Zoning */}
            <section>
              <h2 className="text-sm font-display font-semibold text-black uppercase tracking-wider mb-3">
                Zoning — performance par zone
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-vz-bg text-xs uppercase text-gray-600">
                      <Th align="left">Zone</Th>
                      <Th>OBJ</Th>
                      <Th>CA</Th>
                      <Th>CA N-1</Th>
                      <Th>DELTA</Th>
                      <Th>Unites</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.zoning.map((z) => (
                      <tr key={z.zone_id} className="border-b border-gray-100">
                        <Td align="left">
                          <span className="inline-flex items-center gap-2">
                            <span
                              className="h-3 w-3 rounded-full flex-shrink-0"
                              style={{ backgroundColor: z.color_code }}
                            />
                            <span className="font-medium">{z.zone_name}</span>
                          </span>
                        </Td>
                        <Td>{CURRENCY(z.obj_jour)}</Td>
                        <Td accent>{CURRENCY(z.ca)}</Td>
                        <Td>{CURRENCY(z.ca_n1)}</Td>
                        <Td>
                          {z.delta_pct != null ? (
                            <span className={z.delta_pct >= 0 ? 'text-vz-teal font-semibold' : 'text-red-600 font-semibold'}>
                              {z.delta_pct > 0 ? '+' : ''}{z.delta_pct}%
                            </span>
                          ) : '—'}
                        </Td>
                        <Td>{z.units}</Td>
                      </tr>
                    ))}
                    {data.zoning.length === 0 && (
                      <tr>
                        <td colSpan={6} className="p-3 text-gray-400 text-center">
                          Aucune zone configuree
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            {/* CRM Fidelite */}
            <section>
              <h2 className="text-sm font-display font-semibold text-black uppercase tracking-wider mb-3">
                Suivi CRM / Fidelite
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatBlock label="Fiches creees" value={String(data.crm_loyalty.fiches_creees)} />
                <StatBlock label="Adhesions fidelite" value={String(data.crm_loyalty.adhesions_fidelite)} accent="pink" />
                <StatBlock label="Reprints" value={String(data.crm_loyalty.reprints)} />
                <StatBlock label="Tickets fidelite" value={String(data.crm_loyalty.tickets_fidelo)} />
              </div>
            </section>

          </div>
        )}
      </main>
    </div>
  );
}

function StatBlock({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: 'teal' | 'pink' }) {
  const color = accent === 'teal' ? 'text-vz-teal' : accent === 'pink' ? 'text-vz-accent' : 'text-black';
  return (
    <div className="border border-gray-100 rounded-xl p-3 bg-white">
      <div className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</div>
      <div className={`text-lg font-display font-bold ${color} mt-1`}>{value}</div>
      {hint && <div className="text-[10px] text-gray-400 mt-1">{hint}</div>}
    </div>
  );
}

function Th({ children, align = 'right' }: { children: React.ReactNode; align?: 'left' | 'right' }) {
  const alignCls = align === 'left' ? 'text-left' : 'text-right';
  return (
    <th className={`px-2 py-2 font-semibold ${alignCls} border-b border-gray-200`}>
      {children}
    </th>
  );
}

function Td({ children, align = 'right', accent }: { children: React.ReactNode; align?: 'left' | 'right'; accent?: boolean }) {
  const alignCls = align === 'left' ? 'text-left' : 'text-right';
  return (
    <td className={`px-2 py-2 ${alignCls} ${accent ? 'font-bold text-vz-teal' : 'text-black'}`}>
      {children}
    </td>
  );
}

function ProgressionChart({
  real,
  target,
}: {
  real: { hour: number; ca_cumul: number }[];
  target: { hour: number; ca_target: number }[];
}) {
  const width = 800;
  const height = 160;
  const padX = 40;
  const padY = 20;

  const allVals = [...real.map((r) => r.ca_cumul), ...target.map((t) => t.ca_target), 0];
  const maxY = Math.max(1, ...allVals) * 1.1;
  const hours = real.map((r) => r.hour);
  const minH = Math.min(...hours);
  const maxH = Math.max(...hours);
  const spanH = maxH - minH || 1;

  const x = (h: number) => padX + ((h - minH) / spanH) * (width - 2 * padX);
  const y = (v: number) => height - padY - (v / maxY) * (height - 2 * padY);

  const path = (pts: { x: number; y: number }[]) =>
    pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');

  const realPts = real.map((r) => ({ x: x(r.hour), y: y(r.ca_cumul) }));
  const tgtPts = target.map((t) => ({ x: x(t.hour), y: y(t.ca_target) }));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" role="img" aria-label="Progression CA du jour">
      {/* Grid */}
      {[0, 0.25, 0.5, 0.75, 1].map((p) => (
        <line
          key={p}
          x1={padX}
          x2={width - padX}
          y1={padY + p * (height - 2 * padY)}
          y2={padY + p * (height - 2 * padY)}
          stroke="#eee"
        />
      ))}
      {/* Target */}
      <path d={path(tgtPts)} fill="none" stroke="#FFD5E5" strokeWidth={2} strokeDasharray="4 4" />
      {/* Real */}
      <path d={path(realPts)} fill="none" stroke="#0B7A6A" strokeWidth={2.5} />
      {/* Hours */}
      {hours.filter((_, i) => i % 2 === 0).map((h) => (
        <text key={h} x={x(h)} y={height - 4} fontSize="10" textAnchor="middle" fill="#888">
          {h}h
        </text>
      ))}
      {/* Max label */}
      <text x={width - padX} y={padY - 4} fontSize="10" textAnchor="end" fill="#888">
        {maxY.toFixed(0)} €
      </text>
    </svg>
  );
}
