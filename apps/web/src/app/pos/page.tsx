'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Card from '@/components/ui/Card';
import { api } from '@/lib/api';

interface SearchProduct {
  id: string;
  barcode: string;
  name: string;
  sale_price: number;
  status: string;
  category: string | null;
}

interface CartItem {
  product_id: string | null;
  name: string;
  price: number;
  quantity: number;
  discount: number; // percent
  isManual: boolean;
}

interface PaymentLine {
  method: 'especes' | 'carte' | 'cheque';
  amount: number;
}

interface ClientResult {
  id: string;
  first_name: string;
  last_name: string;
  phone?: string;
  email?: string;
  has_loyalty: boolean;
}

interface ClientDetail {
  id: string;
  first_name: string;
  last_name: string;
  phone?: string;
  email?: string;
  notes?: string;
  loyalty: { points: number; tier: string } | null;
  purchases: { id: string; transaction_number: number; total_ttc: number; created_at: string }[];
}

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
}

function tierLabel(tier: string): string {
  if (tier === 'gold') return 'Or';
  if (tier === 'silver') return 'Argent';
  return 'Bronze';
}

function tierColor(tier: string): string {
  if (tier === 'gold') return 'bg-yellow-100 text-yellow-700';
  if (tier === 'silver') return 'bg-gray-100 text-gray-600';
  return 'bg-orange-100 text-orange-700';
}

export default function POSPage() {
  // Search
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchProduct[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);

  // Cart
  const [cart, setCart] = useState<CartItem[]>([]);

  // Client
  const [clientSearch, setClientSearch] = useState('');
  const [clientResults, setClientResults] = useState<ClientResult[]>([]);
  const [selectedClient, setSelectedClient] = useState<ClientDetail | null>(null);
  const [showClientPopup, setShowClientPopup] = useState(false);

  // Manual article
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [manualName, setManualName] = useState('');
  const [manualPrice, setManualPrice] = useState('');

  // Payment
  const [showPayment, setShowPayment] = useState(false);
  const [payments, setPayments] = useState<PaymentLine[]>([]);
  const [cashGiven, setCashGiven] = useState('');

  // Receipt
  const [showReceipt, setShowReceipt] = useState(false);
  const [receiptText, setReceiptText] = useState('');
  const [receiptTxId, setReceiptTxId] = useState<string | null>(null);
  const [printing, setPrinting] = useState(false);
  const [printMsg, setPrintMsg] = useState('');

  // CB / SumUp
  const [cbCheckoutId, setCbCheckoutId] = useState<string | null>(null);
  const [cbStatus, setCbStatus] = useState<'idle' | 'pending' | 'paid' | 'failed'>('idle');
  const [cbPollingRef, setCbPollingRef] = useState<ReturnType<typeof setInterval> | null>(null);

  // Loyalty redemption
  const [redeemPoints, setRedeemPoints] = useState(false);

  // General
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clientDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Computed
  const cartTotal = cart.reduce((sum, item) => {
    const linePrice = item.price * item.quantity;
    const afterDiscount = linePrice * (1 - item.discount / 100);
    return sum + afterDiscount;
  }, 0);

  // Loyalty discount: 1 point = 0.10 EUR, max 50% of cart
  const loyaltyPoints = selectedClient?.loyalty?.points || 0;
  const loyaltyDiscount = redeemPoints ? Math.min(loyaltyPoints * 0.10, cartTotal * 0.5) : 0;
  const cartTotalAfterLoyalty = Math.max(0, cartTotal - loyaltyDiscount);

  const totalPaid = payments.reduce((sum, p) => sum + p.amount, 0);
  const remaining = cartTotalAfterLoyalty - totalPaid;

  // ── Product search ───────────────────────────────────────────────
  const searchProducts = useCallback(async (query: string) => {
    if (!query.trim()) { setSearchResults([]); return; }
    setSearchLoading(true);
    try {
      const res = await api.get(`/api/inventory/products/search?q=${encodeURIComponent(query.trim())}`);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(Array.isArray(data) ? data : []);
      }
    } catch { /* silent */ }
    setSearchLoading(false);
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!searchQuery.trim()) { setSearchResults([]); return; }
    debounceRef.current = setTimeout(() => searchProducts(searchQuery), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchQuery, searchProducts]);

  // ── Client search ────────────────────────────────────────────────
  useEffect(() => {
    if (clientDebounceRef.current) clearTimeout(clientDebounceRef.current);
    if (!clientSearch.trim()) { setClientResults([]); return; }
    clientDebounceRef.current = setTimeout(async () => {
      try {
        const res = await api.get(`/api/crm/clients?search=${encodeURIComponent(clientSearch.trim())}`);
        if (res.ok) setClientResults(await res.json());
      } catch { /* silent */ }
    }, 300);
    return () => { if (clientDebounceRef.current) clearTimeout(clientDebounceRef.current); };
  }, [clientSearch]);

  const selectClient = async (client: ClientResult) => {
    setClientResults([]);
    setClientSearch('');
    try {
      const res = await api.get(`/api/crm/clients/${client.id}`);
      if (res.ok) {
        const detail: ClientDetail = await res.json();
        setSelectedClient(detail);
        setShowClientPopup(true);
      }
    } catch { /* silent */ }
  };

  const activateLoyalty = async () => {
    if (!selectedClient) return;
    try {
      const res = await api.post(`/api/crm/clients/${selectedClient.id}/loyalty/activate`, {});
      if (res.ok) {
        // Refresh client detail
        const detailRes = await api.get(`/api/crm/clients/${selectedClient.id}`);
        if (detailRes.ok) setSelectedClient(await detailRes.json());
      }
    } catch { setError('Erreur activation fidelite'); }
  };

  // ── Cart operations ──────────────────────────────────────────────
  const addProductToCart = (product: SearchProduct) => {
    setCart(prev => {
      const existing = prev.find(i => i.product_id === product.id && !i.isManual);
      if (existing) {
        return prev.map(i => i.product_id === product.id && !i.isManual
          ? { ...i, quantity: i.quantity + 1 } : i);
      }
      return [...prev, {
        product_id: product.id,
        name: product.name,
        price: product.sale_price,
        quantity: 1,
        discount: 0,
        isManual: false,
      }];
    });
    setSearchQuery('');
    setSearchResults([]);
  };

  const addBag = () => {
    setCart(prev => {
      const existing = prev.find(i => i.name === 'Sac boutique Vintiz' && i.isManual);
      if (existing) {
        return prev.map(i => i.name === 'Sac boutique Vintiz' && i.isManual
          ? { ...i, quantity: i.quantity + 1 } : i);
      }
      return [...prev, {
        product_id: null,
        name: 'Sac boutique Vintiz',
        price: 0.25,
        quantity: 1,
        discount: 0,
        isManual: true,
      }];
    });
  };

  const addManualArticle = () => {
    const price = parseFloat(manualPrice);
    if (!manualName.trim() || isNaN(price) || price <= 0) return;
    setCart(prev => [...prev, {
      product_id: null,
      name: manualName.trim(),
      price,
      quantity: 1,
      discount: 0,
      isManual: true,
    }]);
    setManualName('');
    setManualPrice('');
    setShowManualEntry(false);
  };

  const updateQuantity = (index: number, delta: number) => {
    setCart(prev => prev.map((item, i) =>
      i === index ? { ...item, quantity: item.quantity + delta } : item
    ).filter(item => item.quantity > 0));
  };

  const updateDiscount = (index: number, discount: number) => {
    setCart(prev => prev.map((item, i) =>
      i === index ? { ...item, discount: Math.max(0, Math.min(30, discount)) } : item
    ));
  };

  const removeFromCart = (index: number) => {
    setCart(prev => prev.filter((_, i) => i !== index));
  };

  // ── CB / SumUp ───────────────────────────────────────────────────
  const initiateCBPayment = async (amount: number) => {
    setCbStatus('pending');
    try {
      const res = await api.post('/api/pos/payments/cb/initiate', {
        amount: parseFloat(amount.toFixed(2)),
        description: `Vente Vintiz #${Date.now()}`,
      });
      if (res.ok) {
        const data = await res.json();
        setCbCheckoutId(data.checkout_id);
        // Poll every 3 seconds for status
        const pollRef = setInterval(async () => {
          try {
            const statusRes = await api.get(`/api/pos/payments/cb/${data.checkout_id}/status`);
            if (statusRes.ok) {
              const s = await statusRes.json();
              if (s.status === 'PAID') {
                clearInterval(pollRef);
                setCbStatus('paid');
                setCbPollingRef(null);
              } else if (s.status === 'FAILED') {
                clearInterval(pollRef);
                setCbStatus('failed');
                setCbPollingRef(null);
              }
            }
          } catch { /* keep polling */ }
        }, 3000);
        setCbPollingRef(pollRef);
      } else {
        setCbStatus('failed');
      }
    } catch {
      setCbStatus('failed');
    }
  };

  const cancelCBPayment = async () => {
    if (cbPollingRef) { clearInterval(cbPollingRef); setCbPollingRef(null); }
    if (cbCheckoutId) {
      await api.delete(`/api/pos/payments/cb/${cbCheckoutId}`).catch(() => {});
    }
    setCbCheckoutId(null);
    setCbStatus('idle');
    // Remove the carte payment line
    setPayments(prev => prev.filter(p => p.method !== 'carte'));
  };

  const confirmCBManually = () => {
    if (cbPollingRef) { clearInterval(cbPollingRef); setCbPollingRef(null); }
    setCbStatus('paid');
  };

  // ── Payment ──────────────────────────────────────────────────────
  const addPayment = (method: PaymentLine['method']) => {
    const autoAmount = Math.max(0, parseFloat((cartTotalAfterLoyalty - totalPaid).toFixed(2)));
    setPayments(prev => [...prev, { method, amount: autoAmount }]);
    if (method === 'carte') {
      const amount = Math.max(0, cartTotalAfterLoyalty - totalPaid);
      initiateCBPayment(amount);
    }
  };

  const updatePaymentAmount = (index: number, amount: number) => {
    setPayments(prev => prev.map((p, i) => (i === index ? { ...p, amount } : p)));
  };

  const removePayment = (index: number) => {
    setPayments(prev => prev.filter((_, i) => i !== index));
  };

  const handleValidate = async () => {
    setSubmitting(true);
    setError('');
    try {
      // If CB was initiated, ensure it's confirmed
      if (payments.some(p => p.method === 'carte') && cbStatus !== 'paid') {
        setError('Le paiement CB n\'a pas encore été confirmé par le TPE.');
        setSubmitting(false);
        return;
      }
      const body: Record<string, unknown> = {
        items: cart.map(item => ({
          product_id: item.product_id || undefined,
          name: item.isManual ? item.name : undefined,
          quantity: item.quantity,
          unit_price: item.price,
          discount_percent: item.discount,
        })),
        payments: payments.map(p => ({ method: p.method, amount: p.amount })),
        redeem_loyalty_discount: redeemPoints ? loyaltyDiscount : 0,
      };
      if (selectedClient) body.client_id = selectedClient.id;

      const res = await api.post('/api/pos/transactions', body);
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || 'Erreur lors de la creation');
      }
      const transaction = await res.json();
      setReceiptTxId(transaction.id);

      // Fetch receipt
      try {
        const receiptRes = await api.get(`/api/pos/transactions/${transaction.id}/receipt`);
        if (receiptRes.ok) {
          const rd = await receiptRes.json();
          setReceiptText(rd.receipt_text || rd.text || 'Transaction validee.');
        } else {
          setReceiptText(`Transaction #${transaction.transaction_number} validee.\nTotal: ${formatCurrency(transaction.total_ttc)}`);
        }
      } catch {
        setReceiptText(`Transaction #${transaction.transaction_number} validee.`);
      }

      setShowPayment(false);
      setShowReceipt(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    }
    setSubmitting(false);
  };

  const printReceiptOnPrinter = async () => {
    if (!receiptTxId) return;
    setPrinting(true);
    setPrintMsg('');
    try {
      const res = await api.post(`/api/pos/transactions/${receiptTxId}/print`, {});
      if (res.ok) {
        setPrintMsg('Ticket imprime sur la MUNBYN');
      } else {
        const e = await res.json().catch(() => ({}));
        setPrintMsg(e.detail || 'Echec de l\'impression');
      }
    } catch {
      setPrintMsg('Erreur de connexion imprimante');
    }
    setPrinting(false);
  };

  const handleReceiptClose = () => {
    setShowReceipt(false);
    setReceiptText('');
    setReceiptTxId(null);
    setPrintMsg('');
    setCart([]);
    setPayments([]);
    setCashGiven('');
    setSelectedClient(null);
    setClientSearch('');
    setError('');
    setCbCheckoutId(null);
    setCbStatus('idle');
    setRedeemPoints(false);
    if (cbPollingRef) { clearInterval(cbPollingRef); setCbPollingRef(null); }
  };

  const methodLabels: Record<string, string> = {
    especes: 'Especes',
    carte: 'Carte (CB)',
    cheque: 'Cheque',
  };

  const cashPaymentIndex = payments.findIndex(p => p.method === 'especes');

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-black">Caisse</h1>
          <p className="text-gray-500 mt-1">Point de vente</p>
        </div>

        {error && !showPayment && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
            <button onClick={() => setError('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* ── Left: Search + Client ─────────────────────────────── */}
          <div className="lg:col-span-2 space-y-4">
            {/* Product search */}
            <Card title="Recherche produit">
              <div className="relative">
                <Input
                  placeholder="Scanner code-barres ou rechercher..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  icon={
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>
                  }
                />
                {(searchResults.length > 0 || searchLoading) && searchQuery.trim() && (
                  <div className="absolute z-10 left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-80 overflow-y-auto">
                    {searchLoading ? (
                      <div className="p-4 text-center text-gray-400">Recherche...</div>
                    ) : searchResults.length === 0 ? (
                      <div className="p-4 text-center text-gray-400">Aucun produit trouve</div>
                    ) : (
                      searchResults.map(product => (
                        <button
                          key={product.id}
                          onClick={() => addProductToCart(product)}
                          className="w-full text-left p-3 hover:bg-pink-50 transition-colors flex items-center justify-between border-b border-gray-50 last:border-0 min-h-[44px]"
                        >
                          <div>
                            <p className="font-medium text-black">{product.name}</p>
                            <p className="text-xs text-gray-400">{product.barcode}{product.category ? ` · ${product.category}` : ''}</p>
                          </div>
                          <p className="font-bold text-teal">{formatCurrency(product.sale_price)}</p>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* Quick buttons */}
              <div className="flex gap-2 mt-3">
                <button
                  onClick={addBag}
                  className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm text-black transition-colors min-h-[40px]"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/></svg>
                  Sac 0,25&nbsp;&euro;
                </button>
                <button
                  onClick={() => setShowManualEntry(true)}
                  className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm text-black transition-colors min-h-[40px]"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  Article manuel
                </button>
              </div>
            </Card>

            {/* Client search */}
            <Card title="Client">
              {selectedClient ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-black">{selectedClient.first_name} {selectedClient.last_name}</p>
                      {selectedClient.phone && <p className="text-xs text-gray-400">{selectedClient.phone}</p>}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setShowClientPopup(true)}
                        className="px-2 py-1 text-xs bg-teal-50 text-teal rounded-lg hover:bg-teal-100 min-h-[36px]"
                      >
                        Voir fiche
                      </button>
                      <button
                        onClick={() => { setSelectedClient(null); setClientSearch(''); }}
                        className="px-2 py-1 text-xs text-red-500 hover:bg-red-50 rounded-lg min-h-[36px]"
                      >
                        Retirer
                      </button>
                    </div>
                  </div>
                  {/* Loyalty badge */}
                  {selectedClient.loyalty ? (
                    <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>
                      <div>
                        <p className="text-sm font-medium text-purple-800">
                          Fidelite {tierLabel(selectedClient.loyalty.tier)}
                        </p>
                        <p className="text-xs text-purple-600">{selectedClient.loyalty.points} points</p>
                      </div>
                      <span className={`ml-auto text-xs px-2 py-1 rounded-full font-medium ${tierColor(selectedClient.loyalty.tier)}`}>
                        {tierLabel(selectedClient.loyalty.tier)}
                      </span>
                    </div>
                  ) : (
                    <button
                      onClick={activateLoyalty}
                      className="w-full p-3 bg-purple-50 hover:bg-purple-100 rounded-lg text-sm text-purple-700 font-medium transition-colors text-left min-h-[44px]"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="inline mr-2"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>
                      Proposer l&apos;adhesion fidelite
                    </button>
                  )}
                </div>
              ) : (
                <div className="relative">
                  <Input
                    placeholder="Rechercher un client (nom, tel, email)..."
                    value={clientSearch}
                    onChange={(e) => setClientSearch(e.target.value)}
                    icon={
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                    }
                  />
                  {clientResults.length > 0 && (
                    <div className="absolute z-10 left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                      {clientResults.map(c => (
                        <button
                          key={c.id}
                          onClick={() => selectClient(c)}
                          className="w-full text-left p-3 hover:bg-pink-50 transition-colors border-b border-gray-50 last:border-0 min-h-[44px]"
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium text-black">{c.first_name} {c.last_name}</p>
                              {c.phone && <p className="text-xs text-gray-400">{c.phone}</p>}
                            </div>
                            {c.has_loyalty && (
                              <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">Fidelite</span>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>

          {/* ── Right: Cart ───────────────────────────────────────── */}
          <div className="lg:col-span-3">
            <Card title="Panier">
              {cart.length === 0 ? (
                <p className="text-gray-400 text-center py-8">Aucun article dans le panier</p>
              ) : (
                <div className="space-y-3 mb-4">
                  {cart.map((item, idx) => {
                    const linePrice = item.price * item.quantity;
                    const afterDiscount = linePrice * (1 - item.discount / 100);
                    return (
                      <div key={idx} className="p-3 bg-gray-50 rounded-lg">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <p className="font-medium text-black">
                              {item.name}
                              {item.isManual && <span className="ml-2 text-xs text-gray-400">(manuel)</span>}
                            </p>
                            <p className="text-sm text-teal font-bold">
                              {formatCurrency(item.price)} x {item.quantity}
                              {item.discount > 0 && <span className="text-red-500 ml-1">-{item.discount}%</span>}
                              {' = '}
                              <span className={item.discount > 0 ? 'text-red-600' : ''}>{formatCurrency(afterDiscount)}</span>
                            </p>
                          </div>
                          <div className="flex items-center gap-1">
                            <button onClick={() => updateQuantity(idx, -1)} className="min-h-[40px] min-w-[40px] flex items-center justify-center rounded-lg hover:bg-gray-200 text-gray-600">
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </button>
                            <span className="min-w-[24px] text-center font-bold text-black text-sm">{item.quantity}</span>
                            <button onClick={() => updateQuantity(idx, 1)} className="min-h-[40px] min-w-[40px] flex items-center justify-center rounded-lg hover:bg-gray-200 text-gray-600">
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </button>
                            <button onClick={() => removeFromCart(idx)} className="min-h-[40px] min-w-[40px] flex items-center justify-center rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-600">
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
                            </button>
                          </div>
                        </div>
                        {/* Discount row */}
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs text-gray-400">Remise :</span>
                          <div className="flex gap-1">
                            {[0, 5, 10, 15, 20, 30].map(d => (
                              <button
                                key={d}
                                onClick={() => updateDiscount(idx, d)}
                                className={`px-2 py-0.5 text-xs rounded-full min-h-[28px] transition-colors ${
                                  item.discount === d
                                    ? 'bg-red-500 text-white'
                                    : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
                                }`}
                              >
                                {d === 0 ? 'Aucune' : `-${d}%`}
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Total */}
              <div className="border-t border-gray-200 pt-4 mt-4">
                <div className="flex items-center justify-between">
                  <span className="text-lg font-bold text-black">Total TTC</span>
                  <span className="text-2xl font-bold text-teal">{formatCurrency(cartTotal)}</span>
                </div>
                {cart.some(i => i.discount > 0) && (
                  <p className="text-xs text-red-500 text-right mt-1">
                    Dont remises : -{formatCurrency(cart.reduce((s, i) => s + i.price * i.quantity * i.discount / 100, 0))}
                  </p>
                )}
              </div>

              {/* Encaisser */}
              <Button
                size="lg"
                className="w-full mt-6"
                disabled={cart.length === 0}
                onClick={() => {
                  setPayments([]);
                  setCashGiven('');
                  setError('');
                  setCbCheckoutId(null);
                  setCbStatus('idle');
                  if (cbPollingRef) { clearInterval(cbPollingRef); setCbPollingRef(null); }
                  setShowPayment(true);
                }}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
                Encaisser {formatCurrency(cartTotal)}
              </Button>
            </Card>
          </div>
        </div>
      </main>

      {/* ── Client Popup Modal ──────────────────────────────────── */}
      <Modal
        open={showClientPopup}
        onClose={() => setShowClientPopup(false)}
        title="Fiche client"
      >
        {selectedClient && (
          <div className="space-y-4">
            <div className="text-center p-4 bg-pink-50 rounded-lg">
              <p className="text-xl font-bold text-black">{selectedClient.first_name} {selectedClient.last_name}</p>
              {selectedClient.phone && <p className="text-sm text-gray-500 mt-1">{selectedClient.phone}</p>}
              {selectedClient.email && <p className="text-sm text-gray-500">{selectedClient.email}</p>}
              {selectedClient.notes && <p className="text-xs text-gray-400 mt-1">{selectedClient.notes}</p>}
            </div>

            {/* Loyalty */}
            {selectedClient.loyalty ? (
              <div className="p-4 bg-purple-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-purple-800">Programme fidelite</h4>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${tierColor(selectedClient.loyalty.tier)}`}>
                    {tierLabel(selectedClient.loyalty.tier)}
                  </span>
                </div>
                <p className="text-2xl font-bold text-purple-700">{selectedClient.loyalty.points} <span className="text-sm font-normal">points</span></p>
              </div>
            ) : (
              <button
                onClick={activateLoyalty}
                className="w-full p-4 bg-purple-50 hover:bg-purple-100 rounded-lg text-purple-700 font-medium transition-colors min-h-[48px]"
              >
                Activer le programme fidelite
              </button>
            )}

            {/* Last visit */}
            <div className="p-4 bg-gray-50 rounded-lg">
              <h4 className="font-semibold text-black mb-2">Derniers achats</h4>
              {selectedClient.purchases.length === 0 ? (
                <p className="text-sm text-gray-400">Aucun achat enregistre</p>
              ) : (
                <div className="space-y-2">
                  {selectedClient.purchases.slice(0, 5).map(p => (
                    <div key={p.id} className="flex justify-between text-sm">
                      <span className="text-gray-500">
                        #{p.transaction_number} - {p.created_at ? new Date(p.created_at).toLocaleDateString('fr-FR') : '-'}
                      </span>
                      <span className="font-medium text-black">{formatCurrency(p.total_ttc)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* ── Manual Entry Modal ──────────────────────────────────── */}
      <Modal
        open={showManualEntry}
        onClose={() => setShowManualEntry(false)}
        title="Article manuel"
        actions={
          <Button onClick={addManualArticle} disabled={!manualName.trim() || !manualPrice}>
            Ajouter au panier
          </Button>
        }
      >
        <div className="space-y-4">
          <Input
            label="Designation"
            placeholder="Nom de l'article..."
            value={manualName}
            onChange={e => setManualName(e.target.value)}
          />
          <Input
            label="Prix TTC"
            type="number"
            step="0.01"
            placeholder="0,00"
            value={manualPrice}
            onChange={e => setManualPrice(e.target.value)}
          />
        </div>
      </Modal>

      {/* ── Payment Modal ───────────────────────────────────────── */}
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
          {error && <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

          {/* Loyalty redemption toggle */}
          {selectedClient?.loyalty && loyaltyPoints > 0 && (
            <div className="p-3 bg-purple-50 rounded-lg flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-purple-800">Utiliser les points fidélité</p>
                <p className="text-xs text-purple-600">{loyaltyPoints} pts disponibles = {(loyaltyPoints * 0.10).toFixed(2)} €</p>
              </div>
              <button
                onClick={() => setRedeemPoints(prev => !prev)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${redeemPoints ? 'bg-purple-600' : 'bg-gray-300'}`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${redeemPoints ? 'translate-x-6' : 'translate-x-1'}`} />
              </button>
            </div>
          )}

          {/* Total */}
          <div className="text-center p-4 bg-teal-50 rounded-lg">
            <p className="text-sm text-gray-500">Total a encaisser</p>
            {redeemPoints && loyaltyDiscount > 0 && (
              <p className="text-sm text-gray-400 line-through">{formatCurrency(cartTotal)}</p>
            )}
            <p className="text-3xl font-bold text-teal">{formatCurrency(cartTotalAfterLoyalty)}</p>
            {redeemPoints && loyaltyDiscount > 0 && (
              <p className="text-xs text-purple-600 mt-1">-{formatCurrency(loyaltyDiscount)} fidélité déduit</p>
            )}
            {selectedClient && (
              <p className="text-xs text-gray-500 mt-1">Client : {selectedClient.first_name} {selectedClient.last_name}</p>
            )}
          </div>

          {/* Payment methods */}
          <div>
            <p className="text-sm font-medium text-black mb-2">Moyen de paiement</p>
            <div className="flex gap-3 flex-wrap">
              <Button variant="outline" size="sm" onClick={() => addPayment('especes')}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5"><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
                Espèces
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => addPayment('carte')}
                disabled={cbStatus === 'pending' || cbStatus === 'paid'}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mr-1.5"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
                Carte (CB)
              </Button>
              <Button variant="outline" size="sm" onClick={() => addPayment('cheque')}>Chèque</Button>
            </div>
          </div>

          {/* CB Status display */}
          {cbStatus !== 'idle' && (
            <div className={`p-4 rounded-xl border-2 ${
              cbStatus === 'paid' ? 'border-green-400 bg-green-50' :
              cbStatus === 'failed' ? 'border-red-400 bg-red-50' :
              'border-blue-300 bg-blue-50'
            }`}>
              <div className="flex items-center gap-3 mb-3">
                {cbStatus === 'pending' && (
                  <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin shrink-0" />
                )}
                {cbStatus === 'paid' && (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" className="shrink-0"><polyline points="20 6 9 17 4 12"/></svg>
                )}
                {cbStatus === 'failed' && (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2" className="shrink-0"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                )}
                <div>
                  <p className={`font-semibold text-sm ${cbStatus === 'paid' ? 'text-green-700' : cbStatus === 'failed' ? 'text-red-700' : 'text-blue-700'}`}>
                    {cbStatus === 'pending' ? 'En attente de confirmation TPE...' :
                     cbStatus === 'paid' ? 'Paiement CB confirmé' :
                     'Paiement CB échoué'}
                  </p>
                  {cbStatus === 'pending' && (
                    <p className="text-xs text-blue-500">Présentez la carte sur le lecteur</p>
                  )}
                </div>
              </div>
              {cbStatus === 'pending' && (
                <div className="flex gap-2">
                  <button
                    onClick={confirmCBManually}
                    className="flex-1 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors min-h-[44px]"
                  >
                    Confirmer manuellement
                  </button>
                  <button
                    onClick={cancelCBPayment}
                    className="px-4 py-2 bg-white text-red-600 border border-red-300 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors min-h-[44px]"
                  >
                    Annuler
                  </button>
                </div>
              )}
              {cbStatus === 'failed' && (
                <button
                  onClick={cancelCBPayment}
                  className="w-full py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 min-h-[44px]"
                >
                  Réessayer
                </button>
              )}
            </div>
          )}

          {/* Payment lines */}
          {payments.map((payment, index) => (
            <div key={index} className="p-4 bg-gray-50 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-medium">{methodLabels[payment.method]}</span>
                <button onClick={() => {
                  removePayment(index);
                  if (payment.method === 'carte') cancelCBPayment();
                }} className="min-h-[44px] min-w-[44px] flex items-center justify-center text-gray-400 hover:text-red-600">
                  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><line x1="4" y1="4" x2="16" y2="16"/><line x1="16" y1="4" x2="4" y2="16"/></svg>
                </button>
              </div>
              {payment.method !== 'carte' && (
                <Input
                  type="number"
                  placeholder="Montant"
                  value={payment.amount || ''}
                  onChange={e => updatePaymentAmount(index, parseFloat(e.target.value) || 0)}
                />
              )}
              {payment.method === 'carte' && (
                <p className="text-sm text-gray-500">{formatCurrency(payment.amount)} via TPE</p>
              )}
              {payment.method === 'especes' && index === cashPaymentIndex && (
                <div className="space-y-2">
                  <Input
                    label="Montant donne"
                    type="number"
                    placeholder="0.00"
                    value={cashGiven}
                    onChange={e => setCashGiven(e.target.value)}
                  />
                  {parseFloat(cashGiven) > 0 && (
                    <p className="text-sm">
                      Monnaie a rendre :{' '}
                      <span className="font-bold text-teal">{formatCurrency(Math.max(0, parseFloat(cashGiven) - payment.amount))}</span>
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
        </div>
      </Modal>

      {/* ── Receipt Modal ───────────────────────────────────────── */}
      <Modal
        open={showReceipt}
        onClose={handleReceiptClose}
        title="Ticket de caisse"
        actions={
          <div className="flex gap-2">
            <Button onClick={printReceiptOnPrinter} disabled={printing || !receiptTxId} variant="secondary">
              {printing ? 'Impression...' : 'Imprimer (MUNBYN)'}
            </Button>
            <Button onClick={handleReceiptClose}>Fermer</Button>
          </div>
        }
      >
        <div className="bg-gray-50 p-4 rounded-lg">
          <pre className="whitespace-pre-wrap text-sm font-mono text-black">{receiptText}</pre>
        </div>
        {printMsg && (
          <p className="mt-3 text-sm text-teal">{printMsg}</p>
        )}
      </Modal>
    </div>
  );
}
