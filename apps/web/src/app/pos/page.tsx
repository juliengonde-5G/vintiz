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

  const handleReceiptClose = () => {
    setShowReceipt(false);
    setReceiptText('');
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
    <div className="flex h-screen overflow-hidden bg-gray-100">
      <Sidebar />

      {/* ── Main POS area ─────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden md:ml-64">

        {/* ── LEFT PANEL: Order / Cart ────────────────────────────── */}
        <div className="w-[42%] flex flex-col bg-white border-r border-gray-200 shadow-sm">

          {/* Header */}
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
            <div>
              <h1 className="text-base font-bold text-black">Commande</h1>
              <p className="text-xs text-gray-400">{cart.length} article{cart.length > 1 ? 's' : ''}</p>
            </div>
            {/* Client section */}
            {selectedClient ? (
              <div className="flex items-center gap-2">
                <div className="text-right">
                  <p className="text-sm font-semibold text-black">{selectedClient.first_name} {selectedClient.last_name}</p>
                  {selectedClient.loyalty && (
                    <p className="text-xs text-purple-600">{selectedClient.loyalty.points} pts fidélité</p>
                  )}
                </div>
                <div className="flex gap-1">
                  <button onClick={() => setShowClientPopup(true)}
                    className="w-8 h-8 flex items-center justify-center rounded-lg bg-teal-50 text-teal hover:bg-teal-100 text-xs">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                  </button>
                  <button onClick={() => { setSelectedClient(null); setClientSearch(''); }}
                    className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-red-50 text-gray-300 hover:text-red-500 text-xs">&times;</button>
                </div>
              </div>
            ) : (
              <div className="relative">
                <input
                  className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg w-44 focus:outline-none focus:ring-1 focus:ring-teal"
                  placeholder="Chercher client..."
                  value={clientSearch}
                  onChange={(e) => setClientSearch(e.target.value)}
                />
                {clientResults.length > 0 && (
                  <div className="absolute right-0 top-8 z-20 w-64 bg-white border border-gray-200 rounded-lg shadow-xl max-h-48 overflow-y-auto">
                    {clientResults.map(c => (
                      <button key={c.id} onClick={() => selectClient(c)}
                        className="w-full text-left px-3 py-2 hover:bg-pink-50 transition-colors border-b border-gray-50 last:border-0">
                        <p className="text-sm font-medium text-black">{c.first_name} {c.last_name}</p>
                        {c.phone && <p className="text-xs text-gray-400">{c.phone}</p>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {error && !showPayment && (
            <div className="mx-3 mt-2 p-2 bg-red-50 text-red-700 rounded-lg text-xs flex-shrink-0">
              {error}
              <button onClick={() => setError('')} className="ml-1 font-bold">&times;</button>
            </div>
          )}

          {/* Cart items - scrollable */}
          <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
            {cart.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-300">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-3">
                  <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
                  <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
                </svg>
                <p className="text-sm">Panier vide</p>
              </div>
            ) : (
              cart.map((item, idx) => {
                const linePrice = item.price * item.quantity;
                const afterDiscount = linePrice * (1 - item.discount / 100);
                return (
                  <div key={idx} className="p-2.5 bg-gray-50 rounded-xl border border-gray-100">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-black truncate">
                          {item.name}
                          {item.isManual && <span className="ml-1 text-xs text-gray-400">(man.)</span>}
                        </p>
                        <div className="flex items-center gap-1 mt-0.5">
                          <span className="text-xs text-gray-500">{formatCurrency(item.price)}</span>
                          {item.discount > 0 && <span className="text-xs text-red-500 font-medium">-{item.discount}%</span>}
                          <span className="text-xs font-bold text-teal ml-auto">{formatCurrency(afterDiscount)}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-0.5 flex-shrink-0">
                        <button onClick={() => updateQuantity(idx, -1)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg bg-white border border-gray-200 hover:bg-gray-100 text-gray-500">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        </button>
                        <span className="w-6 text-center text-sm font-bold text-black">{item.quantity}</span>
                        <button onClick={() => updateQuantity(idx, 1)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg bg-white border border-gray-200 hover:bg-gray-100 text-gray-500">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        </button>
                        <button onClick={() => removeFromCart(idx)}
                          className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-red-50 text-gray-300 hover:text-red-500 ml-1">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        </button>
                      </div>
                    </div>
                    {/* Discount row */}
                    <div className="flex items-center gap-1 mt-1.5">
                      {[0, 5, 10, 15, 20, 30].map(d => (
                        <button key={d} onClick={() => updateDiscount(idx, d)}
                          className={`px-2 py-0.5 text-xs rounded-full transition-colors ${
                            item.discount === d ? 'bg-red-500 text-white' : 'bg-white border border-gray-200 text-gray-500 hover:border-red-300'
                          }`}>
                          {d === 0 ? '—' : `-${d}%`}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer: Total + Pay button */}
          <div className="flex-shrink-0 border-t border-gray-200 bg-white px-4 py-3 space-y-3">
            {/* Loyalty redemption */}
            {selectedClient?.loyalty && loyaltyPoints > 0 && (
              <div className="flex items-center justify-between p-2 bg-purple-50 rounded-lg">
                <p className="text-xs font-medium text-purple-800">
                  Fidélité ({loyaltyPoints} pts = {(loyaltyPoints * 0.10).toFixed(2)} €)
                </p>
                <button onClick={() => setRedeemPoints(prev => !prev)}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${redeemPoints ? 'bg-purple-600' : 'bg-gray-300'}`}>
                  <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${redeemPoints ? 'translate-x-4' : 'translate-x-0.5'}`} />
                </button>
              </div>
            )}

            <div className="flex items-center justify-between">
              <span className="text-base font-bold text-black">Total TTC</span>
              <div className="text-right">
                {redeemPoints && loyaltyDiscount > 0 && (
                  <p className="text-xs text-gray-400 line-through">{formatCurrency(cartTotal)}</p>
                )}
                <span className="text-2xl font-bold text-teal">{formatCurrency(cartTotalAfterLoyalty)}</span>
              </div>
            </div>
            {cart.some(i => i.discount > 0) && (
              <p className="text-xs text-red-500 text-right -mt-1">
                Remises : -{formatCurrency(cart.reduce((s, i) => s + i.price * i.quantity * i.discount / 100, 0))}
              </p>
            )}

            <button
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
              className={`w-full py-4 rounded-xl font-bold text-lg tracking-wide transition-colors flex items-center justify-center gap-3 ${
                cart.length === 0
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-teal text-white hover:bg-teal-700 active:bg-teal-800 shadow-lg'
              }`}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
              Encaisser {cart.length > 0 ? formatCurrency(cartTotalAfterLoyalty) : ''}
            </button>
          </div>
        </div>

        {/* ── RIGHT PANEL: Product Search & Selection ─────────────── */}
        <div className="flex-1 flex flex-col bg-gray-50 overflow-hidden">
          {/* Search bar */}
          <div className="flex-shrink-0 px-4 py-3 bg-white border-b border-gray-200 shadow-sm">
            <div className="relative">
              <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input
                className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-black text-sm focus:outline-none focus:ring-2 focus:ring-teal focus:border-teal"
                placeholder="Scanner code-barres ou rechercher un article..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
              />
              {searchQuery && (
                <button onClick={() => { setSearchQuery(''); setSearchResults([]); }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              )}
            </div>
            {/* Quick action buttons */}
            <div className="flex gap-2 mt-2">
              <button onClick={addBag}
                className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-xs text-black transition-colors">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/></svg>
                Sac 0,25 €
              </button>
              <button onClick={() => setShowManualEntry(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-xs text-black transition-colors">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                Article manuel
              </button>
            </div>
          </div>

          {/* Product grid results */}
          <div className="flex-1 overflow-y-auto p-4">
            {searchLoading ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal" />
              </div>
            ) : searchQuery.trim() && searchResults.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-3"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <p className="text-sm">Aucun produit trouvé</p>
              </div>
            ) : searchResults.length > 0 ? (
              <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
                {searchResults.map(product => (
                  <button
                    key={product.id}
                    onClick={() => addProductToCart(product)}
                    className="text-left p-4 bg-white rounded-xl border-2 border-transparent hover:border-teal hover:shadow-md transition-all group"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="w-10 h-10 rounded-lg bg-pink-50 flex items-center justify-center text-teal flex-shrink-0">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>
                      </div>
                      <span className="text-lg font-bold text-teal">{formatCurrency(product.sale_price)}</span>
                    </div>
                    <p className="text-sm font-semibold text-black group-hover:text-teal leading-tight line-clamp-2">{product.name}</p>
                    <p className="text-xs text-gray-400 mt-1">{product.barcode}{product.category ? ` · ${product.category}` : ''}</p>
                    <div className="mt-2 flex items-center gap-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        product.status === 'display' ? 'bg-teal-50 text-teal' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {product.status === 'display' ? 'En vitrine' : 'En stock'}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-gray-300">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mb-4">
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                <p className="text-base text-gray-400">Scannez un article ou tapez son nom</p>
                <p className="text-sm text-gray-300 mt-1">Les résultats s&apos;afficheront ici</p>
              </div>
            )}
          </div>
        </div>

      </div>

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
        actions={<Button onClick={handleReceiptClose}>Fermer</Button>}
      >
        <div className="bg-gray-50 p-4 rounded-lg">
          <pre className="whitespace-pre-wrap text-sm font-mono text-black">{receiptText}</pre>
        </div>
      </Modal>
    </div>
  );
}
