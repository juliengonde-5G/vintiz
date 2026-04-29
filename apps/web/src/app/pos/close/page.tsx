'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { api } from '@/lib/api';

interface DrawerState {
  id: string;
  opening_amount: number;
  expected_amount: number;
  opened_at: string;
}

interface ZReport {
  total_sales: number;
  total_transactions: number;
  total_cash: number;
  total_card: number;
  total_cheque: number;
  opening_amount: number;
  closing_amount: number;
  difference: number;
}

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
}

function SkeletonBlock({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-gray-200 rounded-lg ${className}`} />
  );
}

export default function CashClosePage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [drawer, setDrawer] = useState<DrawerState | null>(null);
  const [openingInput, setOpeningInput] = useState('');
  const [closingAmount, setClosingAmount] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [zReport, setZReport] = useState<ZReport | null>(null);

  const fetchDrawer = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/pos/drawer/current');
      if (res.ok) {
        const data = await res.json();
        if (data && data.id) {
          setDrawer(data);
        } else {
          setDrawer(null);
        }
      } else if (res.status === 404) {
        setDrawer(null);
      } else {
        throw new Error('Erreur lors du chargement');
      }
      setError('');
    } catch {
      setError('Impossible de verifier l\'etat de la caisse.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDrawer();
  }, [fetchDrawer]);

  const closing = parseFloat(closingAmount) || 0;
  const expectedAmount = drawer ? drawer.expected_amount : 0;
  const difference = closing - expectedAmount;

  const handleOpen = async () => {
    const amount = parseFloat(openingInput);
    if (isNaN(amount) || amount < 0) {
      setError('Veuillez saisir un montant valide.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const res = await api.post('/api/pos/drawer/open', { opening_amount: amount });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || err?.message || 'Erreur lors de l\'ouverture');
      }
      setOpeningInput('');
      await fetchDrawer();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = async () => {
    if (!closingAmount) {
      setError('Veuillez saisir le montant de cloture.');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const res = await api.post('/api/pos/drawer/close', {
        closing_amount: closing,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || err?.message || 'Erreur lors de la cloture');
      }
      const data = await res.json();
      setZReport(data);
      setDrawer(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-gray-500 hover:text-black min-h-[44px] transition-colors mb-4"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Retour
          </button>
          <h1 className="text-2xl font-bold text-black">Cloture de caisse</h1>
          <p className="text-gray-500 mt-1">Gestion du tiroir-caisse</p>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg max-w-xl mx-auto">
            {error}
          </div>
        )}

        <div className="max-w-xl mx-auto space-y-6">
          {loading ? (
            <Card>
              <div className="space-y-4">
                <SkeletonBlock className="h-6 w-48" />
                <SkeletonBlock className="h-12 w-full" />
                <SkeletonBlock className="h-12 w-full" />
              </div>
            </Card>
          ) : zReport ? (
            /* Z Report Summary */
            <>
              <Card title="Rapport Z - Cloture effectuee">
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-vz-teal-soft rounded-lg">
                      <p className="text-xs text-gray-500">Total ventes</p>
                      <p className="text-lg font-bold text-vz-teal">{formatCurrency(zReport.total_sales)}</p>
                    </div>
                    <div className="p-3 bg-vz-teal-soft rounded-lg">
                      <p className="text-xs text-gray-500">Nb transactions</p>
                      <p className="text-lg font-bold text-vz-teal">{zReport.total_transactions}</p>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-xs text-gray-500">Total especes</p>
                      <p className="text-lg font-bold text-black">{formatCurrency(zReport.total_cash)}</p>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-xs text-gray-500">Total carte</p>
                      <p className="text-lg font-bold text-black">{formatCurrency(zReport.total_card)}</p>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-xs text-gray-500">Total cheque</p>
                      <p className="text-lg font-bold text-black">{formatCurrency(zReport.total_cheque)}</p>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                      <p className="text-xs text-gray-500">Fond d&apos;ouverture</p>
                      <p className="text-lg font-bold text-black">{formatCurrency(zReport.opening_amount)}</p>
                    </div>
                  </div>
                  <div className="border-t border-gray-200 pt-4">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-black">Ecart</span>
                      <span
                        className={`text-xl font-bold ${
                          zReport.difference === 0
                            ? 'text-green-600'
                            : 'text-red-600'
                        }`}
                      >
                        {zReport.difference >= 0 ? '+' : ''}
                        {formatCurrency(zReport.difference)}
                      </span>
                    </div>
                  </div>
                </div>
              </Card>
              <div className="flex justify-end">
                <Button size="lg" onClick={() => router.push('/dashboard')}>
                  Retour au tableau de bord
                </Button>
              </div>
            </>
          ) : !drawer ? (
            /* No drawer open - show open form */
            <Card title="Ouvrir la caisse">
              <div className="space-y-5">
                <p className="text-gray-500">
                  Aucun tiroir-caisse n&apos;est ouvert. Saisissez le fond de caisse pour commencer.
                </p>
                <Input
                  label="Montant d'ouverture"
                  type="number"
                  placeholder="0.00"
                  value={openingInput}
                  onChange={(e) => setOpeningInput(e.target.value)}
                />
                <div className="flex justify-end">
                  <Button size="lg" onClick={handleOpen} disabled={submitting}>
                    {submitting ? 'Ouverture...' : 'Ouvrir la caisse'}
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            /* Drawer open - show close form */
            <>
              <Card title="Fond de caisse">
                <div className="space-y-5">
                  <div>
                    <label className="block text-sm font-medium text-black mb-1.5">
                      Montant d&apos;ouverture
                    </label>
                    <div className="min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-black font-medium">
                      {formatCurrency(drawer.opening_amount)}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-black mb-1.5">
                      Montant attendu (calcule)
                    </label>
                    <div className="min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-black font-medium">
                      {formatCurrency(expectedAmount)}
                    </div>
                  </div>

                  <Input
                    label="Montant de cloture (comptage reel)"
                    type="number"
                    placeholder="0.00"
                    value={closingAmount}
                    onChange={(e) => setClosingAmount(e.target.value)}
                  />
                </div>
              </Card>

              <Card title="Ecart">
                <div className="text-center py-4">
                  <p className="text-sm text-gray-500 mb-2">Difference</p>
                  <p
                    className={`text-3xl font-bold ${
                      !closingAmount
                        ? 'text-gray-400'
                        : difference === 0
                        ? 'text-green-600'
                        : 'text-red-600'
                    }`}
                  >
                    {closingAmount ? (
                      <>
                        {difference >= 0 ? '+' : ''}
                        {formatCurrency(difference)}
                      </>
                    ) : (
                      '--'
                    )}
                  </p>
                  {closingAmount && difference !== 0 && (
                    <p className="text-sm text-gray-500 mt-2">
                      {difference > 0 ? 'Excedent de caisse' : 'Deficit de caisse'}
                    </p>
                  )}
                </div>
              </Card>

              <div className="flex justify-end">
                <Button size="lg" onClick={handleClose} disabled={submitting}>
                  {submitting ? 'Cloture en cours...' : (
                    <>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                        <line x1="16" y1="13" x2="8" y2="13" />
                        <line x1="16" y1="17" x2="8" y2="17" />
                      </svg>
                      Cloturer
                    </>
                  )}
                </Button>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
