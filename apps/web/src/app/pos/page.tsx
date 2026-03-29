'use client';

import React, { useState } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Card from '@/components/ui/Card';

interface CartItem {
  id: string;
  name: string;
  price: number;
  photo?: string;
}

interface PaymentLine {
  method: 'especes' | 'carte' | 'cheque';
  amount: number;
}

export default function POSPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [cart, setCart] = useState<CartItem[]>([]);
  const [showPayment, setShowPayment] = useState(false);
  const [payments, setPayments] = useState<PaymentLine[]>([]);
  const [cashGiven, setCashGiven] = useState('');
  const [clientSearch, setClientSearch] = useState('');

  // Scanned product placeholder
  const [scannedProduct, setScannedProduct] = useState<CartItem | null>(null);

  const total = cart.reduce((sum, item) => sum + item.price, 0);
  const totalPaid = payments.reduce((sum, p) => sum + p.amount, 0);
  const remaining = total - totalPaid;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    // Simulate finding a product
    const product: CartItem = {
      id: Date.now().toString(),
      name: `Produit ${searchQuery}`,
      price: 29.90,
    };
    setScannedProduct(product);
    setSearchQuery('');
  };

  const addToCart = (product: CartItem) => {
    setCart((prev) => [...prev, { ...product, id: Date.now().toString() }]);
    setScannedProduct(null);
  };

  const removeFromCart = (id: string) => {
    setCart((prev) => prev.filter((item) => item.id !== id));
  };

  const addPayment = (method: PaymentLine['method']) => {
    setPayments((prev) => [...prev, { method, amount: 0 }]);
  };

  const updatePaymentAmount = (index: number, amount: number) => {
    setPayments((prev) =>
      prev.map((p, i) => (i === index ? { ...p, amount } : p))
    );
  };

  const removePayment = (index: number) => {
    setPayments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleValidate = () => {
    // TODO: Call API to create transaction
    setCart([]);
    setPayments([]);
    setCashGiven('');
    setClientSearch('');
    setShowPayment(false);
  };

  const methodLabels: Record<string, string> = {
    especes: 'Especes',
    carte: 'Carte (CB)',
    cheque: 'Cheque',
  };

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-black">Caisse</h1>
          <p className="text-gray-500 mt-1">Point de vente</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left panel: Search / Scan */}
          <div className="space-y-4">
            <Card title="Recherche produit">
              <form onSubmit={handleSearch} className="flex gap-3">
                <div className="flex-1">
                  <Input
                    placeholder="Scanner code-barres ou rechercher..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    icon={
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="11" cy="11" r="8" />
                        <line x1="21" y1="21" x2="16.65" y2="16.65" />
                      </svg>
                    }
                  />
                </div>
                <Button type="submit">Rechercher</Button>
              </form>

              {/* Scanned product */}
              {scannedProduct && (
                <div className="mt-4 p-4 bg-pink-50 rounded-lg flex items-center gap-4">
                  <div className="w-14 h-14 bg-gray-200 rounded-lg flex items-center justify-center shrink-0">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" strokeWidth="2">
                      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <polyline points="21 15 16 10 5 21" />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-black">{scannedProduct.name}</p>
                    <p className="text-teal font-bold">{scannedProduct.price.toFixed(2)}&nbsp;&euro;</p>
                  </div>
                  <Button onClick={() => addToCart(scannedProduct)}>
                    Ajouter
                  </Button>
                </div>
              )}
            </Card>
          </div>

          {/* Right panel: Cart */}
          <div>
            <Card title="Panier">
              {cart.length === 0 ? (
                <p className="text-gray-400 text-center py-8">
                  Aucun article dans le panier
                </p>
              ) : (
                <div className="space-y-3 mb-4">
                  {cart.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div>
                        <p className="font-medium text-black">{item.name}</p>
                        <p className="text-sm text-teal font-bold">
                          {item.price.toFixed(2)}&nbsp;&euro;
                        </p>
                      </div>
                      <button
                        onClick={() => removeFromCart(item.id)}
                        className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors"
                        title="Retirer"
                      >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="3 6 5 6 21 6" />
                          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Total */}
              <div className="border-t border-gray-200 pt-4 mt-4">
                <div className="flex items-center justify-between">
                  <span className="text-lg font-bold text-black">Total TTC</span>
                  <span className="text-2xl font-bold text-teal">
                    {total.toFixed(2)}&nbsp;&euro;
                  </span>
                </div>
              </div>

              {/* Encaisser button */}
              <Button
                size="lg"
                className="w-full mt-6"
                disabled={cart.length === 0}
                onClick={() => {
                  setPayments([]);
                  setCashGiven('');
                  setShowPayment(true);
                }}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                  <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
                  <line x1="1" y1="10" x2="23" y2="10" />
                </svg>
                Encaisser
              </Button>
            </Card>
          </div>
        </div>
      </main>

      {/* Payment Modal */}
      <Modal
        open={showPayment}
        onClose={() => setShowPayment(false)}
        title="Encaissement"
        actions={
          <Button
            size="lg"
            disabled={remaining > 0.01}
            onClick={handleValidate}
          >
            Valider le paiement
          </Button>
        }
      >
        <div className="space-y-5">
          {/* Total reminder */}
          <div className="text-center p-4 bg-teal-50 rounded-lg">
            <p className="text-sm text-gray-500">Total a encaisser</p>
            <p className="text-3xl font-bold text-teal">{total.toFixed(2)}&nbsp;&euro;</p>
          </div>

          {/* Payment method buttons */}
          <div>
            <p className="text-sm font-medium text-black mb-2">Ajouter un moyen de paiement</p>
            <div className="flex gap-3">
              <Button variant="outline" size="sm" onClick={() => addPayment('especes')}>
                Especes
              </Button>
              <Button variant="outline" size="sm" onClick={() => addPayment('carte')}>
                Carte (CB)
              </Button>
              <Button variant="outline" size="sm" onClick={() => addPayment('cheque')}>
                Cheque
              </Button>
            </div>
          </div>

          {/* Payment lines */}
          {payments.map((payment, index) => (
            <div key={index} className="p-4 bg-gray-50 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-medium">{methodLabels[payment.method]}</span>
                <button
                  onClick={() => removePayment(index)}
                  className="min-h-[44px] min-w-[44px] flex items-center justify-center text-gray-400 hover:text-red-600"
                >
                  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="4" y1="4" x2="16" y2="16" />
                    <line x1="16" y1="4" x2="4" y2="16" />
                  </svg>
                </button>
              </div>
              <Input
                type="number"
                placeholder="Montant"
                value={payment.amount || ''}
                onChange={(e) =>
                  updatePaymentAmount(index, parseFloat(e.target.value) || 0)
                }
              />
              {payment.method === 'especes' && (
                <div className="space-y-2">
                  <Input
                    label="Montant donne"
                    type="number"
                    placeholder="0.00"
                    value={cashGiven}
                    onChange={(e) => setCashGiven(e.target.value)}
                  />
                  {parseFloat(cashGiven) > 0 && (
                    <p className="text-sm">
                      Monnaie a rendre:{' '}
                      <span className="font-bold text-teal">
                        {(parseFloat(cashGiven) - payment.amount).toFixed(2)}&nbsp;&euro;
                      </span>
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* Remaining */}
          {payments.length > 0 && (
            <div className="flex items-center justify-between p-3 bg-pink-50 rounded-lg">
              <span className="text-sm font-medium">Reste a payer</span>
              <span className={`font-bold ${remaining <= 0.01 ? 'text-green-600' : 'text-red-600'}`}>
                {Math.max(0, remaining).toFixed(2)}&nbsp;&euro;
              </span>
            </div>
          )}

          {/* Client search */}
          <div>
            <Input
              label="Client (optionnel)"
              placeholder="Rechercher un client..."
              value={clientSearch}
              onChange={(e) => setClientSearch(e.target.value)}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              }
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
