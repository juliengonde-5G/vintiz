'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

interface Product {
  id: string;
  name: string;
  price: number;
  barcode?: string;
  photo?: string;
  stock_quantity?: number;
}

interface CartItem {
  product_id: string;
  name: string;
  price: number;
  quantity: number;
}

interface PaymentLine {
  method: 'especes' | 'carte' | 'cheque';
  amount: number;
}

interface Client {
  id: string;
  first_name: string;
  last_name: string;
  phone?: string;
}

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
}

export default function POSPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Product[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [showPayment, setShowPayment] = useState(false);
  const [showReceipt, setShowReceipt] = useState(false);
  const [receiptText, setReceiptText] = useState('');
  const [payments, setPayments] = useState<PaymentLine[]>([]);
  const [cashGiven, setCashGiven] = useState('');
  const [clientSearch, setClientSearch] = useState('');
  const [clientResults, setClientResults] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clientDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const total = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  const totalPaid = payments.reduce((sum, p) => sum + p.amount, 0);
  const remaining = total - totalPaid;

  // Product search with debounce
  const searchProducts = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    try {
      const isBarcode = /^\d{8,}$/.test(query.trim());
      const param = isBarcode ? `barcode=${encodeURIComponent(query.trim())}` : `search=${encodeURIComponent(query.trim())}`;
      const res = await api.get(`/api/inventory/products?${param}`);
      if (res.ok) {
        const json = await res.json();
        setSearchResults(Array.isArray(json) ? json : json.results || json.data || []);
      }
    } catch {
      // silent
    } finally {
      setSearchLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    debounceRef.current = setTimeout(() => {
      searchProducts(searchQuery);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchQuery, searchProducts]);

  // Client search with debounce
  useEffect(() => {
    if (clientDebounceRef.current) clearTimeout(clientDebounceRef.current);
    if (!clientSearch.trim()) {
      setClientResults([]);
      return;
    }
    clientDebounceRef.current = setTimeout(async () => {
      try {
        const res = await api.get(`/api/crm/clients?search=${encodeURIComponent(clientSearch.trim())}`);
        if (res.ok) {
          const json = await res.json();
          setClientResults(Array.isArray(json) ? json : json.results || json.data || []);
        }
      } catch {
        // silent
      }
    }, 300);
    return () => {
      if (clientDebounceRef.current) clearTimeout(clientDebounceRef.current);
    };
  }, [clientSearch]);

  const addToCart = (product: Product) => {
    setCart((prev) => {
      const existing = prev.find((item) => item.product_id === product.id);
      if (existing) {
        return prev.map((item) =>
          item.product_id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [
        ...prev,
        { product_id: product.id, name: product.name, price: product.price, quantity: 1 },
      ];
    });
    setSearchQuery('');
    setSearchResults([]);
  };

  const updateQuantity = (productId: string, delta: number) => {
    setCart((prev) =>
      prev
        .map((item) =>
          item.product_id === productId
            ? { ...item, quantity: item.quantity + delta }
            : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  const removeFromCart = (productId: string) => {
    setCart((prev) => prev.filter((item) => item.product_id !== productId));
  };

  const addPayment = (method: PaymentLine['method']) => {
    const autoAmount = Math.max(0, parseFloat((total - totalPaid).toFixed(2)));
    setPayments((prev) => [...prev, { method, amount: autoAmount }]);
  };

  const updatePaymentAmount = (index: number, amount: number) => {
    setPayments((prev) =>
      prev.map((p, i) => (i === index ? { ...p, amount } : p))
    );
  };

  const removePayment = (index: number) => {
    setPayments((prev) => prev.filter((_, i) => i !== index));
  };

  const handleValidate = async () => {
    setSubmitting(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        items: cart.map((item) => ({
          product_id: item.product_id,
          quantity: item.quantity,
          unit_price: item.price,
        })),
        payments: payments.map((p) => ({
          method: p.method,
          amount: p.amount,
        })),
      };
      if (selectedClient) {
        body.client_id = selectedClient.id;
      }
      const res = await api.post('/api/pos/transactions', body);
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || err?.message || 'Erreur lors de la creation');
      }
      const transaction = await res.json();
      // Fetch receipt
      try {
        const receiptRes = await api.get(`/api/pos/transactions/${transaction.id}/receipt`);
        if (receiptRes.ok) {
          const receiptData = await receiptRes.json();
          setReceiptText(typeof receiptData === 'string' ? receiptData : receiptData.text || receiptData.receipt || JSON.stringify(receiptData, null, 2));
        } else {
          setReceiptText('Transaction validee avec succes.');
        }
      } catch {
        setReceiptText('Transaction validee avec succes.');
      }
      setShowPayment(false);
      setShowReceipt(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReceiptClose = () => {
    setShowReceipt(false);
    setReceiptText('');
    setCart([]);
    setPayments([]);
    setCashGiven('');
    setClientSearch('');
    setClientResults([]);
    setSelectedClient(null);
    setError('');
  };

  const methodLabels: Record<string, string> = {
    especes: 'Especes',
    carte: 'Carte (CB)',
    cheque: 'Cheque',
  };

  // Find the first especes payment for change calculation
  const cashPaymentIndex = payments.findIndex((p) => p.method === 'especes');

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-black">Caisse</h1>
          <p className="text-gray-500 mt-1">Point de vente</p>
        </div>

        {error && !showPayment && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left panel: Search */}
          <div className="space-y-4">
            <Card title="Recherche produit">
              <div className="relative">
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

                {/* Search Results Dropdown */}
                {(searchResults.length > 0 || searchLoading) && searchQuery.trim() && (
                  <div className="absolute z-10 left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-80 overflow-y-auto">
                    {searchLoading ? (
                      <div className="p-4 text-center text-gray-400">Recherche...</div>
                    ) : (
                      searchResults.map((product) => (
                        <button
                          key={product.id}
                          onClick={() => addToCart(product)}
                          className="w-full text-left p-3 hover:bg-pink-50 transition-colors flex items-center justify-between border-b border-gray-50 last:border-0 min-h-[44px]"
                        >
                          <div>
                            <p className="font-medium text-black">{product.name}</p>
                            {product.barcode && (
                              <p className="text-xs text-gray-400">{product.barcode}</p>
                            )}
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-teal">{formatCurrency(product.price)}</p>
                            {product.stock_quantity !== undefined && (
                              <p className="text-xs text-gray-400">Stock: {product.stock_quantity}</p>
                            )}
                          </div>
                        </button>
                      ))
                    )}
                    {!searchLoading && searchResults.length === 0 && (
                      <div className="p-4 text-center text-gray-400">Aucun produit trouve</div>
                    )}
                  </div>
                )}
              </div>
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
                      key={item.product_id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div className="flex-1">
                        <p className="font-medium text-black">{item.name}</p>
                        <p className="text-sm text-teal font-bold">
                          {formatCurrency(item.price)} x {item.quantity} = {formatCurrency(item.price * item.quantity)}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => updateQuantity(item.product_id, -1)}
                          className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-gray-200 text-gray-600 transition-colors"
                          title="Moins"
                        >
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <line x1="5" y1="12" x2="19" y2="12" />
                          </svg>
                        </button>
                        <span className="min-w-[28px] text-center font-bold text-black">{item.quantity}</span>
                        <button
                          onClick={() => updateQuantity(item.product_id, 1)}
                          className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-gray-200 text-gray-600 transition-colors"
                          title="Plus"
                        >
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <line x1="12" y1="5" x2="12" y2="19" />
                            <line x1="5" y1="12" x2="19" y2="12" />
                          </svg>
                        </button>
                        <button
                          onClick={() => removeFromCart(item.product_id)}
                          className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600 transition-colors"
                          title="Retirer"
                        >
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Total */}
              <div className="border-t border-gray-200 pt-4 mt-4">
                <div className="flex items-center justify-between">
                  <span className="text-lg font-bold text-black">Total TTC</span>
                  <span className="text-2xl font-bold text-teal">
                    {formatCurrency(total)}
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
                  setError('');
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
            disabled={remaining > 0.01 || submitting}
            onClick={handleValidate}
          >
            {submitting ? 'Traitement...' : 'Valider le paiement'}
          </Button>
        }
      >
        <div className="space-y-5">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
          )}

          {/* Total reminder */}
          <div className="text-center p-4 bg-teal-50 rounded-lg">
            <p className="text-sm text-gray-500">Total a encaisser</p>
            <p className="text-3xl font-bold text-teal">{formatCurrency(total)}</p>
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
              {payment.method === 'especes' && index === cashPaymentIndex && (
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
                        {formatCurrency(Math.max(0, parseFloat(cashGiven) - payment.amount))}
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
                {formatCurrency(Math.max(0, remaining))}
              </span>
            </div>
          )}

          {/* Client search */}
          <div>
            <Input
              label="Client (optionnel)"
              placeholder="Rechercher un client..."
              value={selectedClient ? `${selectedClient.first_name} ${selectedClient.last_name}` : clientSearch}
              onChange={(e) => {
                setClientSearch(e.target.value);
                setSelectedClient(null);
              }}
              icon={
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              }
            />
            {selectedClient && (
              <button
                onClick={() => {
                  setSelectedClient(null);
                  setClientSearch('');
                }}
                className="text-xs text-red-500 mt-1 hover:underline"
              >
                Retirer le client
              </button>
            )}
            {clientResults.length > 0 && !selectedClient && (
              <div className="mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-40 overflow-y-auto">
                {clientResults.map((client) => (
                  <button
                    key={client.id}
                    onClick={() => {
                      setSelectedClient(client);
                      setClientResults([]);
                      setClientSearch('');
                    }}
                    className="w-full text-left p-3 hover:bg-pink-50 transition-colors border-b border-gray-50 last:border-0 min-h-[44px]"
                  >
                    <p className="font-medium text-black">
                      {client.first_name} {client.last_name}
                    </p>
                    {client.phone && (
                      <p className="text-xs text-gray-400">{client.phone}</p>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </Modal>

      {/* Receipt Modal */}
      <Modal
        open={showReceipt}
        onClose={handleReceiptClose}
        title="Ticket de caisse"
        actions={
          <Button onClick={handleReceiptClose}>Fermer</Button>
        }
      >
        <div className="bg-gray-50 p-4 rounded-lg">
          <pre className="whitespace-pre-wrap text-sm font-mono text-black">{receiptText}</pre>
        </div>
      </Modal>
    </div>
  );
}
