'use client';

import React, { useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface ImportSummary {
  dry_run: boolean;
  total_rows: number;
  imported: number;
  skipped_existing_barcode: number;
  errors: { line: number; message: string }[];
  created_ids: string[];
}

export default function InventoryImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [summary, setSummary] = useState<ImportSummary | null>(null);

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    setError('');
    setSummary(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.upload(
        `/api/inventory/products/import-csv?dry_run=${dryRun}`,
        formData,
      );
      const body = await res.json().catch(() => null);
      if (res.ok && body) {
        setSummary(body as ImportSummary);
      } else {
        setError(body?.detail || `HTTP ${res.status}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur réseau.');
    }
    setBusy(false);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-cream">
      <Sidebar />
      <main className="flex-1 overflow-y-auto md:ml-64 p-4 md:p-8">
        <header className="mb-6">
          <h1 className="text-2xl font-bold text-black font-display">
            Import produits CSV
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Importez en masse depuis le tracker du centre de tri ou un export
            Excel. Lancez d&apos;abord en mode <strong>Dry-run</strong> pour
            valider sans toucher au stock.
          </p>
        </header>

        <Card title="Fichier CSV">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Sélectionner un fichier .csv
              </label>
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  setSummary(null);
                  setError('');
                }}
                className="block w-full text-sm text-gray-700 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-teal file:text-white hover:file:bg-teal-700"
              />
              {file && (
                <p className="text-xs text-gray-500 mt-1">
                  {file.name} — {(file.size / 1024).toFixed(1)} ko
                </p>
              )}
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
                className="rounded border-gray-300"
              />
              Dry-run (valider sans persister)
            </label>

            <Button onClick={submit} disabled={!file || busy}>
              {busy ? 'Import en cours…' : dryRun ? 'Valider (dry-run)' : 'Importer'}
            </Button>

            <details className="text-xs text-gray-500">
              <summary className="cursor-pointer">Format attendu</summary>
              <pre className="mt-2 bg-gray-50 p-3 rounded overflow-x-auto">
{`name,sale_price,category_name,barcode,brand,color,size,condition,purchase_price,week_number,status
Robe noire,49.00,Robes,,Sandro,noir,38,bon,5,18,received`}
              </pre>
              <ul className="mt-2 list-disc pl-5 space-y-1">
                <li><strong>Obligatoire</strong> : name, sale_price + (category_id OU category_name)</li>
                <li>category_name doit déjà exister (les catégories ne sont jamais auto-créées)</li>
                <li>barcode optionnel — auto-généré si vide ; ligne ignorée si déjà en base</li>
                <li>Décimales acceptées avec virgule (49,90)</li>
                <li>5 Mo max</li>
              </ul>
            </details>
          </div>

          {error && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 rounded text-sm">
              {error}
            </div>
          )}

          {summary && (
            <div className="mt-4 space-y-3">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div className="p-3 bg-gray-50 rounded">
                  <p className="text-xs text-gray-500">Lignes lues</p>
                  <p className="text-xl font-bold">{summary.total_rows}</p>
                </div>
                <div className="p-3 bg-green-50 rounded">
                  <p className="text-xs text-green-700">
                    {summary.dry_run ? 'Importables' : 'Importées'}
                  </p>
                  <p className="text-xl font-bold text-green-700">{summary.imported}</p>
                </div>
                <div className="p-3 bg-amber-50 rounded">
                  <p className="text-xs text-amber-700">Doublons (skip)</p>
                  <p className="text-xl font-bold text-amber-700">
                    {summary.skipped_existing_barcode}
                  </p>
                </div>
                <div className="p-3 bg-red-50 rounded">
                  <p className="text-xs text-red-700">Erreurs</p>
                  <p className="text-xl font-bold text-red-700">{summary.errors.length}</p>
                </div>
              </div>

              {summary.errors.length > 0 && (
                <div className="border border-red-200 rounded-lg overflow-hidden">
                  <p className="px-3 py-2 bg-red-50 text-sm font-medium text-red-700">
                    Erreurs détaillées
                  </p>
                  <ul className="divide-y divide-gray-100 text-sm">
                    {summary.errors.map((err, i) => (
                      <li key={i} className="px-3 py-2 flex gap-3">
                        <span className="font-mono text-gray-500">L{err.line}</span>
                        <span className="text-red-700">{err.message}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {summary.dry_run && summary.errors.length === 0 && summary.imported > 0 && (
                <div className="p-3 bg-teal-50 text-teal-800 rounded text-sm">
                  Tout est OK. Décochez « Dry-run » et relancez pour importer
                  réellement.
                </div>
              )}
            </div>
          )}
        </Card>
      </main>
    </div>
  );
}
