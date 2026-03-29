'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

export default function CashClosePage() {
  const router = useRouter();
  const [openingAmount, setOpeningAmount] = useState('');
  const [closingAmount, setClosingAmount] = useState('');

  // Placeholder: expected amount would come from the API
  const expectedAmount = 0;
  const opening = parseFloat(openingAmount) || 0;
  const closing = parseFloat(closingAmount) || 0;
  const difference = closing - (opening + expectedAmount);

  const handleClose = () => {
    // TODO: Call API to generate Z report and close day
    alert('Cloture de caisse effectuee');
    router.push('/dashboard');
  };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
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
          <p className="text-gray-500 mt-1">Bilan de la journee</p>
        </div>

        <div className="max-w-xl mx-auto space-y-6">
          <Card title="Fond de caisse">
            <div className="space-y-5">
              <Input
                label="Montant d'ouverture"
                type="number"
                placeholder="0.00"
                value={openingAmount}
                onChange={(e) => setOpeningAmount(e.target.value)}
              />

              <div>
                <label className="block text-sm font-medium text-black mb-1.5">
                  Montant attendu (calcule)
                </label>
                <div className="min-h-[44px] px-4 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-black font-medium">
                  {(opening + expectedAmount).toFixed(2)}&nbsp;&euro;
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
                  difference === 0
                    ? 'text-green-600'
                    : difference > 0
                    ? 'text-blue-600'
                    : 'text-red-600'
                }`}
              >
                {difference >= 0 ? '+' : ''}
                {difference.toFixed(2)}&nbsp;&euro;
              </p>
              {difference !== 0 && closingAmount && (
                <p className="text-sm text-gray-500 mt-2">
                  {difference > 0 ? 'Excedent de caisse' : 'Deficit de caisse'}
                </p>
              )}
            </div>
          </Card>

          <div className="flex justify-end">
            <Button size="lg" onClick={handleClose}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              Generer Z et cloture
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
