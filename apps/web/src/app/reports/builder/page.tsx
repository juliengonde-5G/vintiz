'use client';

/**
 * Rapports sur-mesure — constructeur de tableaux de bord embarqué.
 *
 * L'utilisateur compose une page d'indicateurs : pour chaque widget il choisit
 * un jeu de données (ventes / stock / clients), une mesure, une dimension
 * (dont le temps), un format graphique et une plage de temps. Le backend agit
 * en requêteur (POST /reports/custom/query). Les rapports sont sauvegardables.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import ChartWidget, { ChartType, QueryResult } from '@/components/reports/ChartWidget';
import { api } from '@/lib/api';

interface CatalogMeasure { key: string; label: string; format: string }
interface CatalogDimension { key: string; label: string; time: boolean }
interface CatalogDataset { key: string; label: string; has_time: boolean; dimensions: CatalogDimension[]; measures: CatalogMeasure[] }
interface Catalog { datasets: CatalogDataset[]; granularities: string[]; chart_types: string[] }

interface Widget {
  id: string;
  title: string;
  chart_type: ChartType;
  dataset: string;
  measure: string;
  dimension: string | null;
  granularity: string;
}

interface SavedReport { id: string; name: string; description: string | null; layout: Widget[]; updated_at: string | null }

const RANGE_OPTIONS: { label: string; days: number | null }[] = [
  { label: '7 jours', days: 7 },
  { label: '30 jours', days: 30 },
  { label: '90 jours', days: 90 },
  { label: '12 mois', days: 365 },
  { label: 'Tout', days: null },
];

const CHART_LABELS: Record<string, string> = {
  kpi: 'Indicateur', bar: 'Barres', line: 'Courbe', pie: 'Camembert', table: 'Tableau',
};

function uid() { return Math.random().toString(36).slice(2, 9); }

function WidgetCard({ widget, rangeDays, onRemove }: { widget: Widget; rangeDays: number | null; onRemove: () => void }) {
  const [data, setData] = useState<QueryResult | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError('');
    api.post('/api/reports/custom/query', {
      dataset: widget.dataset,
      measure: widget.measure,
      dimension: widget.dimension,
      granularity: widget.granularity,
      range_days: rangeDays,
    }).then(async (res) => {
      if (cancelled) return;
      if (res.ok) setData(await res.json());
      else { const e = await res.json().catch(() => ({})); setError(e.detail || 'Erreur'); }
    }).catch(() => { if (!cancelled) setError('Erreur réseau'); });
    return () => { cancelled = true; };
  }, [widget.dataset, widget.measure, widget.dimension, widget.granularity, rangeDays]);

  return (
    <Card className="relative" title={widget.title}>
      <button onClick={onRemove} aria-label="Retirer"
        className="absolute top-3 right-3 text-vz-ink-mute hover:text-red-500 text-lg leading-none">×</button>
      {error ? <p className="text-sm text-red-600 py-4">{error}</p> : <ChartWidget type={widget.chart_type} data={data} />}
    </Card>
  );
}

export default function ReportBuilderPage() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [rangeDays, setRangeDays] = useState<number | null>(30);
  const [reportId, setReportId] = useState<string | null>(null);
  const [reportName, setReportName] = useState('Nouveau rapport');
  const [saved, setSaved] = useState<SavedReport[]>([]);
  const [toast, setToast] = useState<{ msg: string; kind: 'success' | 'error' } | null>(null);

  // Add-widget form state
  const [fDataset, setFDataset] = useState('');
  const [fMeasure, setFMeasure] = useState('');
  const [fDimension, setFDimension] = useState('');
  const [fGranularity, setFGranularity] = useState('month');
  const [fChart, setFChart] = useState<ChartType>('bar');
  const [fTitle, setFTitle] = useState('');

  const notify = useCallback((msg: string, kind: 'success' | 'error' = 'success') => {
    setToast({ msg, kind }); setTimeout(() => setToast(null), 3500);
  }, []);

  const loadSaved = useCallback(async () => {
    try { const r = await api.get('/api/reports/custom/reports'); if (r.ok) setSaved((await r.json()).reports || []); } catch { /* */ }
  }, []);

  useEffect(() => {
    api.get('/api/reports/custom/catalog').then(async (r) => { if (r.ok) setCatalog(await r.json()); }).catch(() => {});
    loadSaved();
  }, [loadSaved]);

  const currentDataset = useMemo(
    () => catalog?.datasets.find((d) => d.key === fDataset) || null,
    [catalog, fDataset],
  );
  const dimIsTime = currentDataset?.dimensions.find((d) => d.key === fDimension)?.time;

  // Keep the form coherent when the dataset changes.
  useEffect(() => {
    if (!currentDataset) return;
    if (!currentDataset.measures.find((m) => m.key === fMeasure)) setFMeasure(currentDataset.measures[0]?.key || '');
    if (fDimension && !currentDataset.dimensions.find((d) => d.key === fDimension)) setFDimension('');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fDataset]);

  const addWidget = () => {
    if (!fDataset || !fMeasure) { notify('Choisissez un jeu de données et une mesure.', 'error'); return; }
    const measureLabel = currentDataset?.measures.find((m) => m.key === fMeasure)?.label || fMeasure;
    const dimLabel = fDimension ? currentDataset?.dimensions.find((d) => d.key === fDimension)?.label : null;
    const title = fTitle.trim() || (dimLabel ? `${measureLabel} par ${dimLabel.toLowerCase()}` : measureLabel);
    setWidgets((w) => [...w, {
      id: uid(), title, chart_type: fChart, dataset: fDataset, measure: fMeasure,
      dimension: fDimension || null, granularity: fGranularity,
    }]);
    setFTitle('');
  };

  const saveReport = async () => {
    const body = { name: reportName.trim() || 'Rapport', layout: widgets };
    try {
      const res = reportId
        ? await api.put(`/api/reports/custom/reports/${reportId}`, body)
        : await api.post('/api/reports/custom/reports', body);
      if (res.ok) { const r = await res.json(); setReportId(r.id); notify('Rapport enregistré'); loadSaved(); }
      else notify('Échec de l\'enregistrement', 'error');
    } catch { notify('Erreur réseau', 'error'); }
  };

  const loadReport = (r: SavedReport) => {
    setReportId(r.id); setReportName(r.name); setWidgets(r.layout || []);
  };

  const newReport = () => { setReportId(null); setReportName('Nouveau rapport'); setWidgets([]); };

  const deleteReport = async (id: string) => {
    if (!confirm('Supprimer ce rapport ?')) return;
    try { const res = await api.delete(`/api/reports/custom/reports/${id}`); if (res.ok) { if (id === reportId) newReport(); loadSaved(); notify('Rapport supprimé'); } } catch { notify('Erreur réseau', 'error'); }
  };

  return (
    <div className="min-h-screen bg-vz-bg">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-10 md:p-8">
        <div className="max-w-6xl mx-auto space-y-6">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <h1 className="text-2xl font-bold text-vz-ink">Rapports sur-mesure</h1>
              <p className="text-sm text-vz-ink-mute">Composez vos tableaux de bord à partir de vos données.</p>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {RANGE_OPTIONS.map((o) => (
                <button key={o.label} onClick={() => setRangeDays(o.days)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium ${rangeDays === o.days ? 'bg-vz-teal text-white' : 'bg-vz-surface border border-vz-line text-vz-ink-soft hover:bg-vz-bg-alt'}`}>
                  {o.label}
                </button>
              ))}
            </div>
          </div>

          {toast && (
            <div role="status" className={`px-4 py-3 rounded-xl text-sm font-medium ${toast.kind === 'success' ? 'bg-vz-teal text-white' : 'bg-red-600 text-white'}`}>
              {toast.msg}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
            {/* Canvas */}
            <div className="space-y-4 order-2 lg:order-1">
              <div className="flex items-center gap-2 flex-wrap">
                <input value={reportName} onChange={(e) => setReportName(e.target.value)}
                  className="flex-1 min-w-[180px] px-3 py-2 rounded-lg border border-vz-line text-sm font-medium bg-vz-surface focus:outline-none focus:ring-2 focus:ring-vz-teal" />
                <Button onClick={saveReport}>{reportId ? 'Mettre à jour' : 'Enregistrer'}</Button>
                {reportId && <Button variant="outline" onClick={newReport}>Nouveau</Button>}
              </div>

              {widgets.length === 0 ? (
                <Card><p className="text-sm text-vz-ink-mute py-8 text-center">Ajoutez un indicateur depuis le panneau de droite pour commencer.</p></Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {widgets.map((w) => (
                    <WidgetCard key={w.id} widget={w} rangeDays={rangeDays}
                      onRemove={() => setWidgets((ws) => ws.filter((x) => x.id !== w.id))} />
                  ))}
                </div>
              )}
            </div>

            {/* Builder + saved reports */}
            <div className="space-y-4 order-1 lg:order-2">
              <Card title="Ajouter un indicateur">
                {!catalog ? <p className="text-sm text-vz-ink-mute">Chargement…</p> : (
                  <div className="space-y-3">
                    <Field label="Jeu de données">
                      <Select value={fDataset} onChange={setFDataset}
                        options={[{ v: '', l: '— choisir —' }, ...catalog.datasets.map((d) => ({ v: d.key, l: d.label }))]} />
                    </Field>
                    {currentDataset && (
                      <>
                        <Field label="Mesure">
                          <Select value={fMeasure} onChange={setFMeasure}
                            options={currentDataset.measures.map((m) => ({ v: m.key, l: m.label }))} />
                        </Field>
                        <Field label="Dimension (regrouper par)">
                          <Select value={fDimension} onChange={setFDimension}
                            options={[{ v: '', l: 'Total (aucun)' }, ...currentDataset.dimensions.map((d) => ({ v: d.key, l: d.label }))]} />
                        </Field>
                        {dimIsTime && (
                          <Field label="Granularité">
                            <Select value={fGranularity} onChange={setFGranularity}
                              options={catalog.granularities.map((g) => ({ v: g, l: g }))} />
                          </Field>
                        )}
                        <Field label="Format">
                          <Select value={fChart} onChange={(v) => setFChart(v as ChartType)}
                            options={catalog.chart_types.map((c) => ({ v: c, l: CHART_LABELS[c] || c }))} />
                        </Field>
                        <Field label="Titre (optionnel)">
                          <input value={fTitle} onChange={(e) => setFTitle(e.target.value)} placeholder="Auto"
                            className="w-full px-2 py-1.5 rounded-lg border border-vz-line text-sm focus:outline-none focus:ring-2 focus:ring-vz-teal" />
                        </Field>
                        <Button className="w-full" onClick={addWidget}>+ Ajouter au rapport</Button>
                      </>
                    )}
                  </div>
                )}
              </Card>

              <Card title="Mes rapports">
                {saved.length === 0 ? (
                  <p className="text-sm text-vz-ink-mute">Aucun rapport enregistré.</p>
                ) : (
                  <ul className="space-y-1.5">
                    {saved.map((r) => (
                      <li key={r.id} className="flex items-center justify-between gap-2">
                        <button onClick={() => loadReport(r)}
                          className={`text-sm text-left truncate hover:text-vz-teal ${r.id === reportId ? 'text-vz-teal font-medium' : 'text-vz-ink-soft'}`}>
                          {r.name}
                        </button>
                        <button onClick={() => deleteReport(r.id)} className="text-vz-ink-mute hover:text-red-500 text-xs">Suppr.</button>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="block text-xs font-medium text-vz-ink-soft mb-1">{label}</span>
      {children}
    </label>
  );
}

function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { v: string; l: string }[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="w-full px-2 py-1.5 rounded-lg border border-vz-line text-sm bg-vz-surface focus:outline-none focus:ring-2 focus:ring-vz-teal">
      {options.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
    </select>
  );
}
