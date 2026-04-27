'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Button from '@/components/ui/Button';
import NumPad from '@/components/ui/NumPad';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Card from '@/components/ui/Card';
import CashierPinModal from '@/components/cashier/CashierPinModal';
import LoyaltyCustomerCard, { type CustomerBrief } from '@/components/pos/LoyaltyCustomerCard';
import { api } from '@/lib/api';
import { useConnectivity } from '@/lib/connectivity';
import {
  count as queueCount,
  drain as drainQueue,
  enqueue as enqueueOffline,
  generateClientUuid,
  type Submitter,
} from '@/lib/offline-queue';

interface Cashier {
  id: string;
  username: string;
  role: string;
}

const CASHIER_STORAGE_KEY = 'vintiz_pos_cashier';

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
  method: 'especes' | 'carte' | 'cheque' | 'avoir';
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
  avoir_balance?: number;
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

  // P4-010 — per-product insights (badges) cached by product_id.
  const [insights, setInsights] = useState<Record<string, { icon: string; label: string; severity: string }[]>>({});

  // P4-008 redemption — coupon entered by the cashier.
  const [couponCode, setCouponCode] = useState('');
  const [couponDiscount, setCouponDiscount] = useState(0);
  const [couponApplied, setCouponApplied] = useState<{ code: string; source: string } | null>(null);
  const [couponError, setCouponError] = useState('');
  const [couponBusy, setCouponBusy] = useState(false);

  // Client
  const [clientSearch, setClientSearch] = useState('');
  const [clientResults, setClientResults] = useState<ClientResult[]>([]);
  const [selectedClient, setSelectedClient] = useState<ClientDetail | null>(null);
  const [showClientPopup, setShowClientPopup] = useState(false);
  const [customerBrief, setCustomerBrief] = useState<CustomerBrief | null>(null);

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

  // Numpad (touch)
  const [numpadTarget, setNumpadTarget] = useState<{ type: 'cash' | 'payment'; index: number } | null>(null);

  // Offline POS (P1-005)
  const { online, recheck } = useConnectivity();
  const [pendingCount, setPendingCount] = useState(0);
  const [draining, setDraining] = useState(false);
  const [offlineMsg, setOfflineMsg] = useState('');

  // Cash drawer
  const [drawer, setDrawer] = useState<{ open: boolean; drawer_id?: string; opening_amount?: number } | null>(null);
  const [showDrawerOpen, setShowDrawerOpen] = useState(false);
  const [showDrawerClose, setShowDrawerClose] = useState(false);
  const [drawerAmount, setDrawerAmount] = useState(0);
  const [zReport, setZReport] = useState<{ z_report_number: number; total_sales: number; total_refunds: number; total_net: number; transaction_count: number; difference: number } | null>(null);
  const [drawerSubmitting, setDrawerSubmitting] = useState(false);

  // Cashier identification (NF525 — P1-002)
  const [cashier, setCashier] = useState<Cashier | null>(null);
  const [showCashierModal, setShowCashierModal] = useState(false);
  const [cashierModalDismissible, setCashierModalDismissible] = useState(false);

  // General
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Which cart item has its discount strip expanded (compact layout: hide by
  // default to fit more items on iPad 1024x768).
  const [discountOpenIdx, setDiscountOpenIdx] = useState<number | null>(null);
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
  // ``cartTotalAfterLoyalty`` is the amount the cashier needs to collect.
  // Coupon discount (P4-008) stacks on top of loyalty.
  const cartTotalAfterLoyalty = Math.max(0, cartTotal - loyaltyDiscount - couponDiscount);

  const totalPaid = payments.reduce((sum, p) => sum + p.amount, 0);
  const remaining = cartTotalAfterLoyalty - totalPaid;

  // ── Cashier identification ──────────────────────────────────────
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = sessionStorage.getItem(CASHIER_STORAGE_KEY);
    if (stored) {
      try {
        setCashier(JSON.parse(stored) as Cashier);
        return;
      } catch {
        sessionStorage.removeItem(CASHIER_STORAGE_KEY);
      }
    }
    setCashierModalDismissible(false);
    setShowCashierModal(true);
  }, []);

  const handleCashierAuthenticated = (next: Cashier) => {
    setCashier(next);
    sessionStorage.setItem(CASHIER_STORAGE_KEY, JSON.stringify(next));
    setShowCashierModal(false);
  };

  const switchCashier = () => {
    setCashierModalDismissible(true);
    setShowCashierModal(true);
  };

  const logoutCashier = () => {
    sessionStorage.removeItem(CASHIER_STORAGE_KEY);
    setCashier(null);
    setCashierModalDismissible(false);
    setShowCashierModal(true);
  };

  // ── Cash drawer ─────────────────────────────────────────────────
  useEffect(() => {
    api.get('/api/pos/drawer/current').then(async (res) => {
      if (res.ok) setDrawer(await res.json());
    }).catch(() => {});
  }, []);

  const handleOpenDrawer = async () => {
    setDrawerSubmitting(true);
    try {
      const res = await api.post('/api/pos/drawer/open', {
        opening_amount: drawerAmount,
        cashier_id: cashier?.id,
      });
      if (res.ok) {
        const data = await res.json();
        setDrawer({ open: true, drawer_id: data.drawer_id, opening_amount: data.opening_amount });
        setShowDrawerOpen(false);
        setDrawerAmount(0);
      }
    } catch { /* silent */ }
    setDrawerSubmitting(false);
  };

  const handleCloseDrawer = async () => {
    setDrawerSubmitting(true);
    try {
      const res = await api.post('/api/pos/drawer/close', {
        closing_amount: drawerAmount,
        cashier_id: cashier?.id,
      });
      if (res.ok) {
        const data = await res.json();
        setZReport(data);
        setDrawer({ open: false });
        setDrawerAmount(0);
      }
    } catch { /* silent */ }
    setDrawerSubmitting(false);
  };

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
      // L2.3 — load enriched brief in parallel for upsell context.
      const briefRes = await api.get(`/api/crm/clients/${client.id}/brief`);
      if (briefRes.ok) setCustomerBrief(await briefRes.json());
    } catch { /* silent */ }
  };

  // L2.3 — Tap a Personal Shopper pick from the loyalty card → add to cart.
  const addPickToCart = async (productId: string) => {
    try {
      const res = await api.get(`/api/inventory/products/${productId}`);
      if (!res.ok) return;
      const product = await res.json();
      addProductToCart({
        id: product.id,
        name: product.name,
        sale_price: product.sale_price,
        barcode: product.barcode,
        photo_url: product.photo_url,
        category: product.category,
        brand: product.brand,
        size: product.size,
        color: product.color,
      } as any);
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

  // Barcode scanner (Inateck BCST-60 / 160B USB HID): types the code fast then
  // sends Enter. We resolve the code → product and add it to the cart.
  const handleBarcodeScan = useCallback(async (rawCode: string) => {
    const code = rawCode.trim();
    if (!code) return;
    try {
      const res = await api.get(`/api/inventory/products/search?q=${encodeURIComponent(code)}`);
      if (!res.ok) { setError(`Produit introuvable pour ${code}`); return; }
      const data: SearchProduct[] = await res.json();
      const exact = data.find(p => p.barcode === code);
      const hit = exact || (data.length === 1 ? data[0] : null);
      if (!hit) { setError(`Aucune correspondance pour ${code}`); return; }
      addProductToCart(hit);
    } catch {
      setError(`Erreur lecture code-barres ${code}`);
    }
  }, []);

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;
    const exact = searchResults.find(p => p.barcode === q);
    if (exact) { addProductToCart(exact); return; }
    if (searchResults.length === 1) { addProductToCart(searchResults[0]); return; }
    handleBarcodeScan(q);
  };

  // Open the receipt in a print-sized window and trigger the browser print
  // dialog (AirPrint on iPad). Most thermal printers fire the cash-drawer
  // kick pulse (RJ11) when a ticket prints — no extra trigger needed.
  // The logo (public/receipt-logo.png) is rendered at the top of the ticket,
  // forced to pure black via grayscale+contrast filters so it reads cleanly
  // on 80 mm thermal paper.
  const printReceipt = useCallback((text: string) => {
    const w = window.open('', '_blank', 'width=400,height=700');
    if (!w) {
      alert("Impossible d'ouvrir la fenêtre d'impression. Autorisez les pop-ups pour ce site.");
      return;
    }
    const safe = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const logoUrl = `${window.location.origin}/receipt-logo.png`;
    w.document.write(`<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Ticket Vintiz</title>
<style>
  @page { size: 80mm auto; margin: 0; }
  body { margin: 0; padding: 4mm 3mm; }
  .logo { display: block; margin: 0 auto 3mm; width: 28mm; height: auto;
          filter: grayscale(1) contrast(10) brightness(0.9);
          -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  pre { font-family: 'Courier New', Consolas, monospace; font-size: 12px;
        line-height: 1.35; white-space: pre-wrap; word-break: break-word; margin: 0; }
  @media print { body { padding: 0 2mm; } }
</style></head>
<body>
<img class="logo" src="${logoUrl}" alt="Vintiz" onerror="this.style.display='none'">
<pre>${safe}</pre>
<script>
  // Wait for the logo image to load (or fail) before triggering print, so it
  // is rendered on the first print job instead of being blank on first run.
  (function() {
    var img = document.querySelector('.logo');
    var go = function() { window.focus(); window.print(); };
    if (!img || img.complete) { go(); }
    else { img.addEventListener('load', go); img.addEventListener('error', go); }
  })();
</script>
</body></html>`);
    w.document.close();
  }, []);

  // Kick the cash drawer without printing a visible ticket. We send a
  // near-empty print job to the same thermal printer — the printer fires
  // its RJ11 kick pulse as soon as the print starts, so the drawer opens.
  // On iPad AirPrint the pop-up window auto-closes after 800 ms.
  const kickDrawer = useCallback(() => {
    const w = window.open('', '_blank', 'width=200,height=60');
    if (!w) return; // silently skip — the Imprimer button will still work
    w.document.write(`<!doctype html>
<html><head><meta charset="utf-8"><title>.</title>
<style>@page { size: 80mm 5mm; margin: 0; } body { margin: 0; }</style></head>
<body>
<script>
  window.onload = function() {
    try { window.print(); } catch (e) {}
    setTimeout(function(){ try { window.close(); } catch (e) {} }, 800);
  };
</script>
</body></html>`);
    w.document.close();
  }, []);

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
    const remainingBeforeLine = Math.max(0, parseFloat((cartTotalAfterLoyalty - totalPaid).toFixed(2)));
    let autoAmount = remainingBeforeLine;
    if (method === 'avoir') {
      const balance = selectedClient?.avoir_balance || 0;
      autoAmount = Math.min(remainingBeforeLine, balance);
    }
    const newIndex = payments.length;
    setPayments(prev => [...prev, { method, amount: autoAmount }]);
    if (method === 'carte') {
      initiateCBPayment(autoAmount);
    } else if (method === 'especes') {
      setCashGiven('');
      setNumpadTarget({ type: 'cash', index: newIndex });
    } else {
      // chèque + avoir → numpad d'édition (avoir capé côté validateurs).
      setNumpadTarget({ type: 'payment', index: newIndex });
    }
  };

  const handleNumpadChange = (v: number) => {
    if (!numpadTarget) return;
    if (numpadTarget.type === 'cash') {
      setCashGiven(v > 0 ? v.toString() : '');
    } else {
      updatePaymentAmount(numpadTarget.index, v);
    }
  };

  const getNumpadPresets = (): number[] => {
    if (!numpadTarget) return [];
    if (numpadTarget.type === 'cash') {
      const exact = parseFloat((payments[numpadTarget.index]?.amount || cartTotalAfterLoyalty).toFixed(2));
      const presets: number[] = [exact];
      for (const bill of [5, 10, 20, 50, 100]) {
        const rounded = Math.ceil(exact / bill) * bill;
        if (rounded > exact && !presets.some(p => p === rounded) && presets.length < 5) presets.push(rounded);
      }
      return presets;
    }
    const others = payments.reduce((s, p, i) => i === numpadTarget.index ? s : s + p.amount, 0);
    return [parseFloat(Math.max(0, cartTotalAfterLoyalty - others).toFixed(2))];
  };

  const updatePaymentAmount = (index: number, amount: number) => {
    setPayments(prev => prev.map((p, i) => (i === index ? { ...p, amount } : p)));
  };

  const removePayment = (index: number) => {
    setPayments(prev => prev.filter((_, i) => i !== index));
  };

  // ── Offline replay (P1-005) ───────────────────────────────────
  // Refresh the badge count whenever the page is shown so cashiers see
  // a stale queue from a previous session.
  useEffect(() => {
    queueCount().then(setPendingCount).catch(() => {});
  }, []);

  const submitter: Submitter = useCallback(async (payload) => {
    const res = await api.post('/api/pos/transactions', payload);
    const bodyText = await res.text().catch(() => '');
    return { ok: res.ok, status: res.status, bodyText };
  }, []);

  const drainPending = useCallback(async () => {
    if (draining) return;
    setDraining(true);
    setOfflineMsg('');
    try {
      const outcome = await drainQueue(submitter);
      setPendingCount(await queueCount());
      if (outcome.failed.length > 0) {
        setOfflineMsg(
          `${outcome.succeeded.length}/${outcome.attempted} synchronisées. ${outcome.failed.length} échec(s) — refaire manuellement.`,
        );
      } else if (outcome.succeeded.length > 0) {
        setOfflineMsg(`${outcome.succeeded.length} vente(s) synchronisée(s).`);
      }
    } catch (err) {
      setOfflineMsg(
        err instanceof Error ? err.message : 'Erreur de synchronisation.',
      );
    }
    setDraining(false);
  }, [draining, submitter]);

  // Auto-drain whenever connectivity flips back on AND there's a backlog.
  useEffect(() => {
    if (online && pendingCount > 0 && !draining) {
      void drainPending();
    }
  }, [online, pendingCount, draining, drainPending]);

  // P4-010 — fetch insights for each product in the cart that we
  // haven't already loaded. Cheap call (< 5 small queries server-side).
  useEffect(() => {
    const ids = Array.from(
      new Set(
        cart
          .filter((i) => !i.isManual && i.product_id)
          .map((i) => i.product_id as string),
      ),
    ).filter((id) => !(id in insights));
    if (ids.length === 0) return;
    let cancelled = false;
    (async () => {
      const fresh: Record<string, { icon: string; label: string; severity: string }[]> = {};
      for (const id of ids) {
        try {
          const res = await api.get(`/api/inventory/products/${id}/insights`);
          if (!res.ok) continue;
          const data = await res.json();
          fresh[id] = data.insights || [];
        } catch { /* silent */ }
      }
      if (!cancelled && Object.keys(fresh).length) {
        setInsights((prev) => ({ ...prev, ...fresh }));
      }
    })();
    return () => { cancelled = true; };
  }, [cart, insights]);

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
      const clientUuid = generateClientUuid();
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
        client_uuid: clientUuid,
      };
      if (selectedClient) body.client_id = selectedClient.id;
      if (cashier) body.cashier_id = cashier.id;
      if (couponApplied) body.coupon_code = couponApplied.code;

      // Offline path (P1-005): no card transactions allowed without
      // network (the SumUp Solo TPE itself needs Wi-Fi). Cash / cheque /
      // avoir queue locally and replay on reconnect.
      if (!online) {
        if (payments.some(p => p.method === 'carte')) {
          setError('Mode hors-ligne : seules les ventes espèces / chèque / avoir sont acceptées. Le TPE CB nécessite le réseau.');
          setSubmitting(false);
          return;
        }
        await enqueueOffline(body);
        setPendingCount(await queueCount());
        setReceiptTxId(null);
        setReceiptText(
          `Vente enregistrée hors-ligne.\nElle sera synchronisée à la reconnexion.\nTotal: ${formatCurrency(cartTotalAfterLoyalty)}`,
        );
        setShowPayment(false);
        setShowReceipt(true);
        if (payments.some(p => p.method === 'especes')) {
          kickDrawer();
        }
        setSubmitting(false);
        return;
      }

      let res: Response;
      try {
        res = await api.post('/api/pos/transactions', body);
      } catch (netErr) {
        // Network failure mid-submit — enqueue and keep going so the
        // cashier isn't blocked. The drain will retry on reconnect.
        await enqueueOffline(body);
        setPendingCount(await queueCount());
        setReceiptTxId(null);
        setReceiptText(
          `Réseau coupé pendant la vente — bufferisée.\nElle sera synchronisée à la reconnexion.\nTotal: ${formatCurrency(cartTotalAfterLoyalty)}`,
        );
        setShowPayment(false);
        setShowReceipt(true);
        if (payments.some(p => p.method === 'especes')) {
          kickDrawer();
        }
        setSubmitting(false);
        // Trigger an immediate connectivity recheck so the banner updates.
        void recheck();
        void netErr;
        return;
      }

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

      // Cash payment → fire the drawer kick immediately so the cashier can
      // make change without an extra click. Card / cheque do not open the
      // drawer automatically; the Imprimer button will, when used.
      if (payments.some(p => p.method === 'especes')) {
        kickDrawer();
      }
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
    setCustomerBrief(null);
    setClientSearch('');
    setError('');
    setCouponCode(''); setCouponDiscount(0); setCouponApplied(null); setCouponError('');
    setHolders({});
    setCbCheckoutId(null);
    setCbStatus('idle');
    setRedeemPoints(false);
    setNumpadTarget(null);
    if (cbPollingRef) { clearInterval(cbPollingRef); setCbPollingRef(null); }
  };

  const methodLabels: Record<string, string> = {
    especes: 'Especes',
    carte: 'Carte (CB)',
    cheque: 'Cheque',
    avoir: 'Avoir client',
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
      <Sidebar />

      {/* ── Main POS area ─────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden md:ml-64">

        {/* ── LEFT PANEL: Order / Cart ────────────────────────────── */}
        <div className="w-[42%] flex flex-col bg-white border-r border-gray-200 shadow-sm">

          {/* Connectivity strip (P1-005) — visible only when offline or with backlog */}
          {(!online || pendingCount > 0) && (
            <div
              className={`flex items-center justify-between px-3 py-1.5 flex-shrink-0 text-xs ${
                online
                  ? 'bg-amber-50 border-b border-amber-200'
                  : 'bg-red-50 border-b border-red-200'
              }`}
            >
              <span className={`font-medium ${online ? 'text-amber-800' : 'text-red-700'}`}>
                {online ? (
                  <>📡 En ligne — {pendingCount} vente(s) en attente de synchronisation</>
                ) : (
                  <>⚠️ Mode hors-ligne — les ventes espèces / chèque / avoir sont bufferisées</>
                )}
              </span>
              <div className="flex items-center gap-1.5">
                {pendingCount > 0 && (
                  <button
                    onClick={drainPending}
                    disabled={draining || !online}
                    className="text-xs px-2 py-1 rounded bg-white border border-gray-200 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                    title={online ? 'Synchroniser maintenant' : 'Synchronisation impossible hors-ligne'}
                  >
                    {draining ? 'Sync…' : 'Synchroniser'}
                  </button>
                )}
                <button
                  onClick={() => recheck()}
                  className="text-xs px-2 py-1 rounded bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
                  title="Re-tester la connexion"
                >
                  ↻
                </button>
              </div>
            </div>
          )}
          {offlineMsg && (
            <div className="px-3 py-1.5 text-xs bg-teal-50 text-teal-800 border-b border-teal-100 flex items-center justify-between">
              <span>{offlineMsg}</span>
              <button
                onClick={() => setOfflineMsg('')}
                className="text-xs font-bold hover:text-teal-900"
              >
                ×
              </button>
            </div>
          )}

          {/* Cashier identification strip */}
          <div className="flex items-center justify-between px-3 py-1.5 flex-shrink-0 text-xs bg-teal-50 border-b border-teal-100">
            <span className="font-medium text-teal-800">
              {cashier
                ? <>Cashier : <strong>{cashier.username}</strong></>
                : 'Aucun cashier identifié'}
            </span>
            <div className="flex items-center gap-1.5">
              {cashier && (
                <>
                  <button
                    onClick={switchCashier}
                    className="text-xs px-2 py-1 rounded bg-white border border-teal-200 text-teal hover:bg-teal-100 transition-colors"
                    title="Changer de cashier (relève)"
                  >
                    Changer
                  </button>
                  <button
                    onClick={logoutCashier}
                    className="text-xs px-2 py-1 rounded bg-white border border-gray-200 text-gray-500 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors"
                    title="Déconnecter le cashier"
                  >
                    Déconnexion
                  </button>
                </>
              )}
              {!cashier && (
                <button
                  onClick={() => { setCashierModalDismissible(false); setShowCashierModal(true); }}
                  className="text-xs px-2 py-1 rounded bg-teal text-white hover:bg-teal-700 transition-colors"
                >
                  S&apos;identifier
                </button>
              )}
            </div>
          </div>

          {/* Cash drawer status strip */}
          {drawer !== null && (
            <div className={`flex items-center justify-between px-3 py-1.5 flex-shrink-0 text-xs ${drawer.open ? 'bg-green-50 border-b border-green-100' : 'bg-amber-50 border-b border-amber-200'}`}>
              <span className={`font-medium ${drawer.open ? 'text-green-700' : 'text-amber-700'}`}>
                {drawer.open
                  ? `Caisse ouverte — fonds: ${drawer.opening_amount?.toFixed(2)} €`
                  : 'Caisse non initialisée'}
              </span>
              {drawer.open ? (
                <div className="flex items-center gap-1.5">
                  <button onClick={kickDrawer}
                    title="Ouvrir le tiroir-caisse manuellement"
                    className="text-xs px-2 py-1 rounded bg-teal text-white hover:bg-teal-700 transition-colors flex items-center gap-1">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="10" width="18" height="10" rx="1"/><path d="M3 10V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4"/><line x1="10" y1="15" x2="14" y2="15"/></svg>
                    Ouvrir tiroir
                  </button>
                  <button onClick={() => { setDrawerAmount(0); setShowDrawerClose(true); }}
                    className="text-xs px-2 py-1 rounded bg-white border border-gray-200 text-gray-600 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors">
                    Clôturer
                  </button>
                </div>
              ) : (
                <button onClick={() => { setDrawerAmount(0); setShowDrawerOpen(true); }}
                  className="text-xs px-2 py-1 rounded bg-teal text-white hover:bg-teal-700 transition-colors">
                  Initialiser
                </button>
              )}
            </div>
          )}

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
                  <button onClick={() => { setSelectedClient(null); setCustomerBrief(null); setClientSearch(''); }}
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

          {/* L2.3 — Loyalty customer card with PS picks for upsell */}
          {customerBrief && (
            <div className="px-3 pt-2">
              <LoyaltyCustomerCard
                brief={customerBrief}
                onTapPick={addPickToCart}
                onClose={() => setCustomerBrief(null)}
              />
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
                  <div key={idx} className="p-2 bg-gray-50 rounded-xl border border-gray-100">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-black truncate">
                          {item.name}
                          {item.isManual && <span className="ml-1 text-xs text-gray-400">(man.)</span>}
                        </p>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="text-xs text-gray-500">{formatCurrency(item.price)}</span>
                          <button
                            onClick={() => setDiscountOpenIdx(discountOpenIdx === idx ? null : idx)}
                            className={`text-xs px-1.5 py-0.5 rounded-full font-medium transition-colors ${
                              item.discount > 0
                                ? 'bg-red-500 text-white'
                                : 'bg-white border border-gray-200 text-gray-400 hover:border-red-300 hover:text-red-500'
                            }`}
                            title="Remise"
                          >
                            {item.discount > 0 ? `-${item.discount}%` : '-%'}
                          </button>
                          <span className="text-xs font-bold text-teal ml-auto">{formatCurrency(afterDiscount)}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-0.5 flex-shrink-0">
                        <button onClick={() => updateQuantity(idx, -1)}
                          className="w-8 h-8 flex items-center justify-center rounded-lg bg-white border border-gray-200 hover:bg-gray-100 text-gray-500">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        </button>
                        <span className="w-6 text-center text-sm font-bold text-black">{item.quantity}</span>
                        <button onClick={() => updateQuantity(idx, 1)}
                          className="w-8 h-8 flex items-center justify-center rounded-lg bg-white border border-gray-200 hover:bg-gray-100 text-gray-500">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                        </button>
                        <button onClick={() => removeFromCart(idx)}
                          className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-red-50 text-gray-300 hover:text-red-500 ml-1">
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        </button>
                      </div>
                    </div>
                    {/* Discount strip: only when expanded or a discount is already set */}
                    {(discountOpenIdx === idx || item.discount > 0) && (
                      <div className="flex items-center gap-1 mt-1.5">
                        {[0, 5, 10, 15, 20, 30].map(d => (
                          <button key={d} onClick={() => { updateDiscount(idx, d); if (d === 0) setDiscountOpenIdx(null); }}
                            className={`px-2 py-1 text-xs rounded-full transition-colors min-w-[34px] ${
                              item.discount === d ? 'bg-red-500 text-white' : 'bg-white border border-gray-200 text-gray-500 hover:border-red-300'
                            }`}>
                            {d === 0 ? '0%' : `-${d}%`}
                          </button>
                        ))}
                      </div>
                    )}
                    {/* P4-010 — AI insight badges (vendue 3× cette semaine, etc.) */}
                    {item.product_id && insights[item.product_id]?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {insights[item.product_id].map((b, i) => (
                          <span
                            key={i}
                            className={`text-[10px] px-2 py-0.5 rounded-full ${
                              b.severity === 'good'
                                ? 'bg-teal/10 text-teal'
                                : b.severity === 'warn'
                                  ? 'bg-orange-50 text-orange-700'
                                  : 'bg-gray-100 text-gray-600'
                            }`}
                          >
                            {b.icon} {b.label}
                          </span>
                        ))}
                      </div>
                    )}
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

            {/* P4-008 — Coupon code (anniversaire, win-back, etc.) */}
            {couponApplied ? (
              <div className="flex items-center justify-between p-2 bg-pink-50 border border-pink rounded-lg">
                <p className="text-xs font-medium text-black">
                  🎟 Code <strong>{couponApplied.code}</strong> — −{formatCurrency(couponDiscount)}
                </p>
                <button
                  onClick={() => { setCouponApplied(null); setCouponDiscount(0); setCouponCode(''); setCouponError(''); }}
                  className="text-xs text-gray-500 hover:text-black"
                >
                  Retirer
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={couponCode}
                  onChange={(e) => { setCouponCode(e.target.value.toUpperCase()); setCouponError(''); }}
                  placeholder="Code promo"
                  className="flex-1 px-2 py-1.5 text-xs border border-gray-200 rounded uppercase tracking-wider"
                />
                <button
                  disabled={!couponCode || couponBusy || cart.length === 0}
                  onClick={async () => {
                    setCouponBusy(true); setCouponError('');
                    try {
                      const body: Record<string, unknown> = {
                        code: couponCode,
                        cart_total: cartTotal - loyaltyDiscount,
                      };
                      if (selectedClient) body.client_id = selectedClient.id;
                      const res = await api.post('/api/pos/coupons/validate', body);
                      const data = await res.json();
                      if (!res.ok) {
                        setCouponError(data?.detail || 'Code refusé.');
                      } else {
                        setCouponDiscount(data.discount_amount);
                        setCouponApplied({ code: data.code, source: data.source });
                      }
                    } catch {
                      setCouponError('Erreur réseau.');
                    }
                    setCouponBusy(false);
                  }}
                  className="px-3 py-1.5 text-xs bg-black text-white rounded disabled:opacity-30"
                >
                  {couponBusy ? '…' : 'OK'}
                </button>
              </div>
            )}
            {couponError && (
              <p className="text-xs text-red-500 -mt-1">{couponError}</p>
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
                setNumpadTarget(null);
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
                onKeyDown={handleSearchKeyDown}
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
            <p className="text-sm font-medium text-black mb-2">
              Moyen de paiement{' '}
              <span className="text-xs font-normal text-gray-500">
                (cumulables — paiement mixte)
              </span>
            </p>
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
              {(selectedClient?.avoir_balance || 0) > 0 && !payments.some(p => p.method === 'avoir') && (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => addPayment('avoir')}
                  title={`Solde avoir : ${formatCurrency(selectedClient?.avoir_balance || 0)}`}
                >
                  Avoir ({formatCurrency(selectedClient?.avoir_balance || 0)})
                </Button>
              )}
            </div>
            {selectedClient?.avoir_balance != null && selectedClient.avoir_balance > 0 && (
              <p className="text-xs text-gray-500 mt-1">
                {selectedClient.first_name} dispose d&apos;un avoir de{' '}
                <strong>{formatCurrency(selectedClient.avoir_balance)}</strong>.
              </p>
            )}
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
            <div key={index} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
              <span className="flex-1 font-semibold text-black text-sm">{methodLabels[payment.method]}</span>
              {payment.method !== 'carte' ? (
                <button
                  type="button"
                  onClick={() => setNumpadTarget({ type: payment.method === 'especes' ? 'cash' : 'payment', index })}
                  className={`px-4 py-2.5 rounded-xl font-bold text-base transition-colors min-h-[44px] ${
                    numpadTarget?.index === index
                      ? 'bg-teal text-white'
                      : 'bg-white border border-gray-200 text-black hover:bg-gray-100'
                  }`}
                >
                  {payment.amount.toFixed(2)} €
                </button>
              ) : (
                <span className="text-sm font-medium text-gray-500">{payment.amount.toFixed(2)} € CB</span>
              )}
              <button
                type="button"
                onClick={() => {
                  removePayment(index);
                  if (payment.method === 'carte') cancelCBPayment();
                  if (numpadTarget?.index === index) setNumpadTarget(null);
                }}
                className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-red-600 rounded-xl hover:bg-red-50"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          ))}

          {/* Numpad for active payment */}
          {numpadTarget && (
            <div className="space-y-2 border-t border-gray-100 pt-3">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                {numpadTarget.type === 'cash' ? 'Montant remis par le client' : 'Montant à encaisser'}
              </p>
              <NumPad
                value={numpadTarget.type === 'cash' ? parseFloat(cashGiven) || 0 : payments[numpadTarget.index]?.amount || 0}
                onChange={handleNumpadChange}
                presets={getNumpadPresets()}
              />
              {numpadTarget.type === 'cash' && parseFloat(cashGiven) > 0 && payments[numpadTarget.index] && (
                <div className="flex items-center justify-between p-3 bg-green-50 rounded-xl border border-green-200">
                  <span className="text-sm font-semibold text-green-800">Monnaie à rendre</span>
                  <span className="text-xl font-bold text-green-700">
                    {formatCurrency(Math.max(0, parseFloat(cashGiven) - payments[numpadTarget.index].amount))}
                  </span>
                </div>
              )}
            </div>
          )}


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
        title="Vente validée"
        actions={
          <div className="flex gap-2 flex-wrap justify-end w-full">
            <Button variant="outline" onClick={handleReceiptClose}>
              Fermer sans ticket
            </Button>
            <Button onClick={printReceiptOnPrinter} disabled={printing || !receiptTxId} variant="secondary">
              {printing ? 'Impression...' : 'Imprimer (MUNBYN)'}
            </Button>
            <Button onClick={() => { printReceipt(receiptText); handleReceiptClose(); }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1.5"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
              Imprimer (AirPrint)
            </Button>
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

      {/* ── Open Drawer Modal ───────────────────────────────────── */}
      <Modal open={showDrawerOpen} onClose={() => setShowDrawerOpen(false)} title="Initialiser la caisse"
        actions={<Button size="lg" onClick={handleOpenDrawer} disabled={drawerSubmitting}>{drawerSubmitting ? 'En cours...' : 'Ouvrir la caisse'}</Button>}>
        <div className="space-y-3">
          <p className="text-sm text-gray-500">Saisissez le fonds de caisse initial (monnaie disponible).</p>
          <NumPad value={drawerAmount} onChange={setDrawerAmount} presets={[50, 100, 150, 200]} />
        </div>
      </Modal>

      {/* ── Close Drawer Modal ──────────────────────────────────── */}
      <Modal open={showDrawerClose} onClose={() => setShowDrawerClose(false)} title="Clôturer la caisse"
        actions={<Button size="lg" onClick={handleCloseDrawer} disabled={drawerSubmitting}>{drawerSubmitting ? 'En cours...' : 'Générer le rapport Z'}</Button>}>
        <div className="space-y-3">
          <p className="text-sm text-gray-500">Comptez les espèces en caisse et saisissez le montant total.</p>
          <NumPad value={drawerAmount} onChange={setDrawerAmount} presets={[]} />
        </div>
      </Modal>

      {/* ── Z Report Modal ───────────────────────────────────────── */}
      <Modal open={!!zReport} onClose={() => setZReport(null)} title="Rapport Z — Clôture de caisse"
        actions={<Button onClick={() => setZReport(null)}>Fermer</Button>}>
        {zReport && (
          <div className="space-y-3">
            <div className="p-4 bg-teal-50 rounded-xl text-center">
              <p className="text-xs text-gray-500 mb-1">Rapport Z n°{zReport.z_report_number}</p>
              <p className="text-3xl font-bold text-teal">{formatCurrency(zReport.total_net)}</p>
              <p className="text-sm text-gray-500 mt-1">Chiffre d&apos;affaires net</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">Ventes</p><p className="font-bold text-black">{formatCurrency(zReport.total_sales)}</p></div>
              <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">Remboursements</p><p className="font-bold text-black">{formatCurrency(zReport.total_refunds)}</p></div>
              <div className="p-3 bg-gray-50 rounded-lg"><p className="text-xs text-gray-500">Transactions</p><p className="font-bold text-black">{zReport.transaction_count}</p></div>
              <div className={`p-3 rounded-lg ${Math.abs(zReport.difference) < 0.01 ? 'bg-green-50' : 'bg-amber-50'}`}>
                <p className="text-xs text-gray-500">Écart caisse</p>
                <p className={`font-bold ${Math.abs(zReport.difference) < 0.01 ? 'text-green-700' : 'text-amber-700'}`}>
                  {zReport.difference >= 0 ? '+' : ''}{formatCurrency(zReport.difference)}
                </p>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Cashier PIN modal — required at session start, dismissible during shift change */}
      <CashierPinModal
        open={showCashierModal}
        dismissible={cashierModalDismissible}
        onAuthenticated={handleCashierAuthenticated}
        onCancel={() => setShowCashierModal(false)}
      />
    </div>
  );
}
