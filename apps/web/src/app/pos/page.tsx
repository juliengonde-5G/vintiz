'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import Button from '@/components/ui/Button';
import NumPad from '@/components/ui/NumPad';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import Card from '@/components/ui/Card';
import CashierPinModal from '@/components/cashier/CashierPinModal';
import CashDrawerCloseModal from '@/components/pos/CashDrawerCloseModal';
import CashDrawerOpenModal from '@/components/pos/CashDrawerOpenModal';
import CashMovementButton from '@/components/pos/CashMovementButton';
import ClientCompanion from '@/components/pos/ClientCompanion';
import ClientSelectionScreen from '@/components/pos/ClientSelectionScreen';
import InvoiceClientForm, {
  type InvoiceFields,
  isInvoiceFormValid,
} from '@/components/pos/InvoiceClientForm';
import LoyaltyCustomerCard, { type CustomerBrief } from '@/components/pos/LoyaltyCustomerCard';
import MultiStepPaymentWizard from '@/components/pos/MultiStepPaymentWizard';
import ReceiptPreviewCard from '@/components/pos/ReceiptPreviewCard';
import { usePosPayment } from '@/hooks/usePosPayment';
import { api } from '@/lib/api';
import { useConnectivity } from '@/lib/connectivity';
import { isPosWizardEnabled } from '@/lib/feature-flags';
import { formatCurrency } from '@/lib/format';
import { isIOS } from '@/lib/platform';
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
  loyalty: { points: number; membership_number: string } | null;
  avoir_balance?: number;
  purchases: { id: string; transaction_number: number; total_ttc: number; created_at: string }[];
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
  const [showClientSelect, setShowClientSelect] = useState(false);
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
  const [cbStatus, setCbStatus] = useState<'idle' | 'pending' | 'paid' | 'failed' | 'timeout'>('idle');
  const cbPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cbTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const CB_POLL_MAX_MS = 90_000; // 90s — past this the cashier confirms manually

  // Loyalty redemption
  const [redeemPoints, setRedeemPoints] = useState(false);

  // Loyalty subscription (PR1)
  const [showSubscribeModal, setShowSubscribeModal] = useState(false);
  const [subscribeForm, setSubscribeForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    postal_code: '',
    accept_terms: false,
    optin_newsletter: false,
    optin_profiling: false,
  });
  const [subscribeBusy, setSubscribeBusy] = useState(false);
  const [subscribeError, setSubscribeError] = useState('');
  const [subscribeSuccess, setSubscribeSuccess] = useState<{
    membership_number: string;
    client_id: string;
  } | null>(null);
  const [subscribeDuplicate, setSubscribeDuplicate] = useState<{
    membership_number: string;
    client_id: string;
  } | null>(null);

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

  // ─── PR 6/6 — New SumUp-style wizard, gated by env flag + localStorage
  // Falls back to the legacy inline payment modal when disabled (default).
  const [wizardEnabled] = useState<boolean>(() => isPosWizardEnabled());
  const [invoiceFields, setInvoiceFields] = useState<InvoiceFields>({
    is_invoice: false,
    client_company_name: '',
    client_siret: '',
    client_billing_address: '',
  });
  const [showWizardReceipt, setShowWizardReceipt] = useState(false);
  const [wizardTxNumber, setWizardTxNumber] = useState<number | null>(null);
  const [wizardInvoiceNumber, setWizardInvoiceNumber] = useState<number | null>(
    null,
  );
  const posPayment = usePosPayment({
    cashierId: cashier?.id ?? null,
    drawerId: drawer?.drawer_id ?? null,
  });

  // Which cart item has its discount strip expanded (compact layout: hide by
  // default to fit more items on iPad 1024x768).
  const [discountOpenIdx, setDiscountOpenIdx] = useState<number | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clientDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Computed — memoised so unrelated state changes (modals, focus, etc.)
  // don't re-run the cart reduce on every render.
  const cartTotal = useMemo(
    () => cart.reduce((sum, item) => {
      const linePrice = item.price * item.quantity;
      const afterDiscount = linePrice * (1 - item.discount / 100);
      return sum + afterDiscount;
    }, 0),
    [cart],
  );

  // Loyalty discount: 1 point = 0.10 EUR, max 50% of cart
  const loyaltyPoints = selectedClient?.loyalty?.points || 0;
  const loyaltyDiscount = redeemPoints ? Math.min(loyaltyPoints * 0.10, cartTotal * 0.5) : 0;
  // ``cartTotalAfterLoyalty`` is the amount the cashier needs to collect.
  // Coupon discount (P4-008) stacks on top of loyalty.
  const cartTotalAfterLoyalty = Math.max(0, cartTotal - loyaltyDiscount - couponDiscount);

  const totalPaid = useMemo(
    () => payments.reduce((sum, p) => sum + p.amount, 0),
    [payments],
  );
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

  const submitSubscription = async () => {
    setSubscribeError('');
    setSubscribeBusy(true);
    setSubscribeDuplicate(null);
    try {
      const res = await api.post('/api/pos/loyalty/subscribe', subscribeForm);
      if (res.ok) {
        const data = await res.json();
        setSubscribeSuccess({
          membership_number: data.membership_number,
          client_id: data.client_id,
        });
        // Refresh client detail if a client was selected.
        if (selectedClient && selectedClient.id === data.client_id) {
          const detailRes = await api.get(`/api/crm/clients/${data.client_id}`);
          if (detailRes.ok) setSelectedClient(await detailRes.json());
        }
      } else if (res.status === 409) {
        const err = await res.json();
        const detail = err.detail || {};
        setSubscribeDuplicate({
          membership_number: detail.existing_membership_number,
          client_id: detail.client_id,
        });
      } else {
        const err = await res.json().catch(() => ({}));
        setSubscribeError(err.detail || 'Erreur de souscription');
      }
    } catch {
      setSubscribeError('Erreur reseau');
    }
    setSubscribeBusy(false);
  };

  const closeSubscribeModal = () => {
    setShowSubscribeModal(false);
    setSubscribeForm({
      first_name: '',
      last_name: '',
      email: '',
      postal_code: '',
      accept_terms: false,
      optin_newsletter: false,
      optin_profiling: false,
    });
    setSubscribeError('');
    setSubscribeSuccess(null);
    setSubscribeDuplicate(null);
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

  // Browser-print fallback: opens a print-sized window and triggers the
  // browser's print dialog. On iPad this hits AirPrint and the thermal
  // printer fires the cash-drawer kick (RJ11) on print. On Android Chrome
  // it just dumps a PDF — we only expose this button on iOS now (M1
  // hardware migration). The logo is forced to pure black via CSS filter
  // so it reads cleanly on 80 mm thermal paper.
  const printReceipt = useCallback((text: string) => {
    const w = window.open('', '_blank', 'width=400,height=700');
    if (!w) {
      setPrintMsg(
        "Impossible d'ouvrir la fenêtre d'impression. " +
        (isIOS()
          ? "Autorisez les pop-ups pour ce site dans les réglages Safari."
          : "Autorisez les pop-ups pour ce site dans les réglages Chrome."),
      );
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
  const stopCbPolling = useCallback(() => {
    if (cbPollingRef.current) {
      clearInterval(cbPollingRef.current);
      cbPollingRef.current = null;
    }
    if (cbTimeoutRef.current) {
      clearTimeout(cbTimeoutRef.current);
      cbTimeoutRef.current = null;
    }
  }, []);

  // Cleanup on unmount: never leak an interval/timeout if the cashier
  // navigates away mid-payment.
  useEffect(() => () => stopCbPolling(), [stopCbPolling]);

  const initiateCBPayment = async (amount: number) => {
    stopCbPolling();
    setCbStatus('pending');
    try {
      const res = await api.post('/api/pos/payments/cb/initiate', {
        amount: parseFloat(amount.toFixed(2)),
        description: `Vente Vintiz #${Date.now()}`,
      });
      if (res.ok) {
        const data = await res.json();
        setCbCheckoutId(data.checkout_id);
        // Poll every 3s for status, hard-stop at CB_POLL_MAX_MS so we never
        // leak the interval if the TPE never replies (network drop, etc.).
        cbPollingRef.current = setInterval(async () => {
          try {
            const statusRes = await api.get(`/api/pos/payments/cb/${data.checkout_id}/status`);
            if (statusRes.ok) {
              const s = await statusRes.json();
              if (s.status === 'PAID') {
                stopCbPolling();
                setCbStatus('paid');
              } else if (s.status === 'FAILED') {
                stopCbPolling();
                setCbStatus('failed');
              }
            }
          } catch { /* keep polling */ }
        }, 3000);
        cbTimeoutRef.current = setTimeout(() => {
          stopCbPolling();
          setCbStatus(prev => (prev === 'pending' ? 'timeout' : prev));
        }, CB_POLL_MAX_MS);
      } else {
        setCbStatus('failed');
      }
    } catch {
      setCbStatus('failed');
    }
  };

  const cancelCBPayment = async () => {
    stopCbPolling();
    if (cbCheckoutId) {
      await api.delete(`/api/pos/payments/cb/${cbCheckoutId}`).catch(() => {});
    }
    setCbCheckoutId(null);
    setCbStatus('idle');
    // Remove the carte payment line
    setPayments(prev => prev.filter(p => p.method !== 'carte'));
  };

  // Cashier-confirmed payment after the 90s timeout. We require an explicit
  // last-status poll so we don't mark a checkout PAID when SumUp says it
  // FAILED — the audit's confirmCBManually used to validate the sale blind.
  const confirmCBManually = async () => {
    stopCbPolling();
    if (!cbCheckoutId) {
      setCbStatus('paid');
      return;
    }
    try {
      const res = await api.get(`/api/pos/payments/cb/${cbCheckoutId}/status`);
      if (res.ok) {
        const s = await res.json();
        if (s.status === 'PAID') {
          setCbStatus('paid');
          return;
        }
        if (s.status === 'FAILED' || s.status === 'CANCELLED') {
          setCbStatus('failed');
          return;
        }
      }
    } catch { /* fall through — still let the cashier confirm */ }
    // Last resort — surface a confirm dialog instead of validating blind.
    if (window.confirm(
      'SumUp ne confirme pas le paiement.\n\n' +
      'Confirme manuellement UNIQUEMENT si tu vois "Paiement accepté" sur le TPE.\n' +
      'Sinon, annule et redemande le paiement.',
    )) {
      setCbStatus('paid');
    }
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

  /**
   * PR 6/6 wizard commit path.
   *
   * Reuses the cart + tender mapping done in ``onCommit`` (wizard sets
   * ``payments`` synchronously via ``setPayments`` before awaiting this).
   * Differences vs. the legacy ``handleValidate``:
   *  - injects the invoice block (``is_invoice``, SIRET, raison sociale,
   *    adresse) so the API allocates a FACT-AAAA-NNNNNN number
   *  - reuses ``posPayment.clientUuid`` for idempotence (rotated only on
   *    success)
   *  - opens the new ``ReceiptPreviewCard`` instead of the legacy modal
   */
  const handleValidateWizard = async (): Promise<void> => {
    setSubmitting(true);
    setError('');
    try {
      const tenders = payments;
      const body: Record<string, unknown> = {
        items: cart.map((item) => ({
          product_id: item.product_id || undefined,
          name: item.isManual ? item.name : undefined,
          quantity: item.quantity,
          unit_price: item.price,
          discount_percent: item.discount,
        })),
        payments: tenders.map((p) => ({ method: p.method, amount: p.amount })),
        redeem_loyalty_discount: redeemPoints ? loyaltyDiscount : 0,
        client_uuid: posPayment.clientUuid,
      };
      if (selectedClient) body.client_id = selectedClient.id;
      if (cashier) body.cashier_id = cashier.id;
      if (couponApplied) body.coupon_code = couponApplied.code;
      if (invoiceFields.is_invoice) {
        body.is_invoice = true;
        body.client_company_name = invoiceFields.client_company_name.trim();
        body.client_siret = invoiceFields.client_siret.replace(/\s+/g, '');
        body.client_billing_address = invoiceFields.client_billing_address.trim();
      }

      const res = await api.post('/api/pos/transactions', body);
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || 'Erreur lors de la création');
      }
      const transaction = await res.json();
      setReceiptTxId(transaction.id);
      setWizardTxNumber(transaction.transaction_number);
      setWizardInvoiceNumber(transaction.invoice_number ?? null);

      try {
        const receiptRes = await api.get(
          `/api/pos/transactions/${transaction.id}/receipt`,
        );
        if (receiptRes.ok) {
          const rd = await receiptRes.json();
          setReceiptText(rd.receipt_text || rd.text || 'Transaction validée.');
        } else {
          setReceiptText(
            `Transaction #${transaction.transaction_number} validée.\nTotal: ${formatCurrency(transaction.total_ttc)}`,
          );
        }
      } catch {
        setReceiptText(
          `Transaction #${transaction.transaction_number} validée.`,
        );
      }

      // Rotate the idempotence key for the next sale + open the success card.
      posPayment.rotateUuid();
      setShowPayment(false);
      setShowWizardReceipt(true);
      if (tenders.some((p) => p.method === 'especes')) {
        kickDrawer();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue');
    }
    setSubmitting(false);
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
    setCbCheckoutId(null);
    setCbStatus('idle');
    setRedeemPoints(false);
    setNumpadTarget(null);
    stopCbPolling();
  };

  const methodLabels: Record<string, string> = {
    especes: 'Especes',
    carte: 'Carte (CB)',
    cheque: 'Cheque',
    avoir: 'Avoir client',
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-vz-bg-alt">
      {/* ─── ODOO 17 TOP BAR ────────────────────────────────────────
           Replaces the back-office Sidebar + 3 inline info strips
           (connectivity, cashier, drawer). The POS goes fullscreen,
           Odoo-style. Exit via the brand link → /dashboard. */}
      <header className="flex-shrink-0 h-14 bg-vz-teal-deep text-white flex items-center px-3 gap-3 shadow-lg z-30">
        <a
          href="/dashboard"
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/10 transition-colors min-h-[44px]"
          title="Retour back-office"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          <span className="font-display font-bold text-sm tracking-wider">VINTIZ</span>
          <span className="text-[10px] uppercase tracking-[0.18em] opacity-70 px-1.5 py-0.5 rounded bg-white/10">Caisse</span>
        </a>

        <div className="h-7 w-px bg-white/15 hidden md:block" />

        {/* Date / heure session */}
        <div className="hidden md:flex flex-col leading-tight text-xs">
          <span className="opacity-70 capitalize">{new Date().toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'short' })}</span>
          <span className="font-mono font-medium">{new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</span>
        </div>

        <div className="h-7 w-px bg-white/15 hidden md:block" />

        {/* Cashier badge */}
        <div className="flex items-center gap-2">
          <div className={`w-9 h-9 rounded-full flex items-center justify-center text-white font-bold text-sm ${cashier ? 'bg-vz-accent' : 'bg-white/20'}`}>
            {cashier ? cashier.username.slice(0, 1).toUpperCase() : '?'}
          </div>
          <div className="hidden sm:flex flex-col leading-tight">
            <span className="text-[10px] opacity-70 uppercase tracking-wider">Cashier</span>
            <span className="text-xs font-medium truncate max-w-[120px]">{cashier?.username ?? 'Non identifié'}</span>
          </div>
          {cashier ? (
            <div className="flex gap-0.5">
              <button
                onClick={switchCashier}
                className="text-xs min-w-[44px] min-h-[40px] px-2 rounded-lg hover:bg-white/10 transition-colors flex items-center justify-center"
                title="Relève (changer de cashier)"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="23 4 23 10 17 10" />
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
                </svg>
              </button>
              <button
                onClick={logoutCashier}
                className="text-xs min-w-[44px] min-h-[40px] px-2 rounded-lg hover:bg-red-500/30 transition-colors flex items-center justify-center"
                title="Déconnexion"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </button>
            </div>
          ) : (
            <button
              onClick={() => { setCashierModalDismissible(false); setShowCashierModal(true); }}
              className="text-xs px-3 py-2 rounded-lg bg-vz-accent hover:opacity-90 transition-opacity min-h-[40px] font-medium"
            >
              S&apos;identifier
            </button>
          )}
        </div>

        <div className="h-7 w-px bg-white/15 hidden lg:block" />

        {/* Drawer status */}
        {drawer !== null && (
          <div className="hidden lg:flex items-center gap-2">
            <span className={`inline-block w-2.5 h-2.5 rounded-full ${drawer.open ? 'bg-green-400' : 'bg-amber-400'}`} title={drawer.open ? 'Caisse ouverte' : 'Caisse fermée'} />
            <div className="flex flex-col leading-tight">
              <span className="text-[10px] opacity-70 uppercase tracking-wider">Tiroir</span>
              <span className="text-xs font-medium font-mono">
                {drawer.open ? `${drawer.opening_amount?.toFixed(2)} €` : 'Fermé'}
              </span>
            </div>
            {drawer.open ? (
              <div className="flex gap-0.5">
                <button
                  onClick={kickDrawer}
                  title="Ouvrir le tiroir-caisse"
                  className="text-xs min-h-[40px] px-3 rounded-lg bg-white/10 hover:bg-white/20 transition-colors flex items-center gap-1.5"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="10" width="18" height="10" rx="1" />
                    <path d="M3 10V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4" />
                    <line x1="10" y1="15" x2="14" y2="15" />
                  </svg>
                  Tiroir
                </button>
                {wizardEnabled && (
                  <CashMovementButton
                    onSubmit={async (payload) => {
                      await api.post('/api/pos/cash-movements', {
                        ...payload,
                        cashier_id: cashier?.id ?? undefined,
                      });
                    }}
                  />
                )}
                <button
                  onClick={() => { setDrawerAmount(0); setShowDrawerClose(true); }}
                  className="text-xs min-h-[40px] px-3 rounded-lg bg-red-500/30 hover:bg-red-500/50 transition-colors font-medium"
                  title="Clôturer la caisse"
                >
                  Clôturer
                </button>
              </div>
            ) : (
              <button
                onClick={() => { setDrawerAmount(0); setShowDrawerOpen(true); }}
                className="text-xs px-3 py-2 rounded-lg bg-vz-accent hover:opacity-90 transition-opacity min-h-[40px] font-medium"
              >
                Initialiser
              </button>
            )}
          </div>
        )}

        <div className="flex-1" />

        {/* Online status + queue */}
        <div className="flex items-center gap-2">
          <span
            className={`inline-block w-2.5 h-2.5 rounded-full ${online ? 'bg-green-400' : 'bg-red-500 animate-pulse'}`}
            title={online ? 'En ligne' : 'Hors-ligne'}
          />
          <span className="hidden md:inline text-xs">
            {online ? 'En ligne' : 'Hors-ligne'}
            {pendingCount > 0 && ` · ${pendingCount} en attente`}
          </span>
          {pendingCount > 0 && (
            <button
              onClick={drainPending}
              disabled={draining || !online}
              className="text-xs min-h-[40px] px-3 rounded-lg bg-white/10 hover:bg-white/20 transition-colors disabled:opacity-40 font-medium"
              title={online ? 'Synchroniser maintenant' : 'Synchronisation impossible hors-ligne'}
            >
              {draining ? 'Sync…' : 'Sync'}
            </button>
          )}
          {!online && (
            <button
              onClick={() => recheck()}
              className="text-xs min-w-[40px] min-h-[40px] rounded-lg bg-white/10 hover:bg-white/20 transition-colors"
              title="Re-tester la connexion"
            >
              ↻
            </button>
          )}
        </div>
      </header>

      {/* ── Main POS area ─────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT PANEL: Order / Cart ──────────────────────────────
             Width is responsive — 42% suits an iPad 10.9" (1024-1180 css
             px), but the Lenovo Idea Tab Pro 13" caisse renders at
             ≥1280 px in landscape and benefits from a wider cart column
             (more lines visible without scrolling). xl: ≥1280, 2xl:
             ≥1536 for very wide docked setups. */}
        <div className="w-[42%] xl:w-[48%] 2xl:w-[50%] flex flex-col bg-white border-r border-vz-line shadow-sm">

          {offlineMsg && (
            <div className="px-3 py-1.5 text-xs bg-vz-teal-soft text-vz-teal-deep border-b border-vz-teal-soft flex items-center justify-between">
              <span>{offlineMsg}</span>
              <button
                onClick={() => setOfflineMsg('')}
                className="text-xs font-bold hover:text-vz-teal-deep"
              >
                ×
              </button>
            </div>
          )}

          {/* Header (Odoo 17 style — "Order" panel) */}
          <div className="px-4 py-3 border-b border-vz-line flex items-center justify-between flex-shrink-0">
            <div>
              <h1 className="font-display text-lg text-vz-ink leading-tight">Ticket</h1>
              <p className="text-xs text-vz-ink-mute">{cart.length} article{cart.length > 1 ? 's' : ''}</p>
            </div>
            {/* Client section */}
            {selectedClient ? (
              <button
                onClick={() => setShowClientPopup(true)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-xl bg-vz-teal-soft hover:bg-vz-teal-soft/70 transition-colors max-w-[240px] group"
                title="Voir la fiche cliente"
              >
                <div className="w-9 h-9 rounded-full bg-vz-teal flex-shrink-0 flex items-center justify-center text-white font-bold text-sm">
                  {(selectedClient.first_name?.[0] ?? '?').toUpperCase()}
                </div>
                <div className="text-left min-w-0 flex-1">
                  <p className="text-xs font-semibold text-vz-ink truncate">
                    {selectedClient.first_name} {selectedClient.last_name}
                  </p>
                  {selectedClient.loyalty && (
                    <p className="text-[10px] text-vz-teal-deep">{selectedClient.loyalty.points} pts · {selectedClient.loyalty.membership_number}</p>
                  )}
                </div>
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedClient(null);
                    setCustomerBrief(null);
                    setClientSearch('');
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      e.stopPropagation();
                      setSelectedClient(null);
                      setCustomerBrief(null);
                      setClientSearch('');
                    }
                  }}
                  className="w-7 h-7 flex items-center justify-center rounded-lg text-vz-ink-mute hover:bg-red-50 hover:text-red-500 transition-colors text-base flex-shrink-0"
                  title="Retirer la cliente"
                >
                  ×
                </span>
              </button>
            ) : (
              <button
                onClick={() => {
                  setClientSearch('');
                  setShowClientSelect(true);
                }}
                className="flex items-center gap-2 px-3 py-2 rounded-xl border border-vz-line bg-white hover:bg-vz-bg-alt hover:border-vz-teal transition-colors text-sm text-vz-ink-soft hover:text-vz-ink min-h-[44px]"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                Ajouter cliente
              </button>
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

          {/* PR4 — Companion caisse: cart-aware up-sells (loyalty, suggestions, coupons, alerts) */}
          {selectedClient && (
            <div className="px-3 pt-2">
              <ClientCompanion
                clientId={selectedClient.id}
                cartTotalCents={Math.round(cartTotal * 100)}
                cartProductIds={cart
                  .map((item) => item.product_id)
                  .filter((id): id is string => Boolean(id))}
                onAddSuggestion={addPickToCart}
                onApplyCoupon={(code) => {
                  setCouponCode(code);
                }}
              />
            </div>
          )}

          {/* "Proposer la carte" CTA for non-identified clients with a non-empty cart */}
          {!selectedClient && cart.length > 0 && (
            <div className="px-3 pt-2">
              <div className="bg-vz-accent-soft border border-vz-accent/40 rounded-xl p-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-xs uppercase tracking-[0.18em] text-vz-accent font-semibold">
                    Carte fidélité
                  </p>
                  <p className="text-sm text-vz-ink mt-0.5">
                    Cette cliente <strong>gagnerait {Math.floor(cartTotal)} pts</strong> en adhérant.
                    Adhésion en quelques secondes.
                  </p>
                </div>
                <button
                  onClick={() => setShowSubscribeModal(true)}
                  className="px-3 py-2 rounded-lg bg-vz-accent text-white text-sm font-medium hover:opacity-90 transition-opacity whitespace-nowrap"
                >
                  Proposer la carte
                </button>
              </div>
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
                          <span className="text-xs font-bold text-vz-teal ml-auto">{formatCurrency(afterDiscount)}</span>
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
                                ? 'bg-vz-teal/10 text-vz-teal'
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
              <div className="flex items-center justify-between p-2 bg-vz-accent-soft border border-vz-accent-soft rounded-lg">
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
                <span className="text-2xl font-bold text-vz-teal">{formatCurrency(cartTotalAfterLoyalty)}</span>
              </div>
            </div>
            {cart.some(i => i.discount > 0) && (
              <p className="text-xs text-red-500 text-right -mt-1">
                Remises : -{formatCurrency(cart.reduce((s, i) => s + i.price * i.quantity * i.discount / 100, 0))}
              </p>
            )}

            {/* B2B invoice toggle (PR 6/6) — only visible with the new wizard. */}
            {wizardEnabled && cart.length > 0 && (
              <div className="mb-3">
                <InvoiceClientForm
                  value={invoiceFields}
                  onChange={setInvoiceFields}
                  compact
                />
              </div>
            )}

            <button
              disabled={
                cart.length === 0 ||
                (wizardEnabled && !isInvoiceFormValid(invoiceFields))
              }
              onClick={() => {
                setPayments([]);
                setCashGiven('');
                setError('');
                setCbCheckoutId(null);
                setCbStatus('idle');
                setNumpadTarget(null);
                stopCbPolling();
                setShowPayment(true);
              }}
              className={`w-full py-4 rounded-xl font-bold text-lg tracking-wide transition-colors flex items-center justify-center gap-3 ${
                cart.length === 0 ||
                (wizardEnabled && !isInvoiceFormValid(invoiceFields))
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-vz-teal text-white hover:bg-vz-teal-deep active:bg-vz-teal-deep shadow-lg'
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
                className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-black text-sm focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
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
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-vz-teal" />
              </div>
            ) : searchQuery.trim() && searchResults.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-3"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <p className="text-sm">Aucun produit trouvé</p>
              </div>
            ) : searchResults.length > 0 ? (
              // Odoo 17 product grid — bigger tiles with photo placeholder header.
              // Touch targets ≥ 140px to be comfortable on iPad / Lenovo M11.
              <div className="grid grid-cols-2 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3">
                {searchResults.map(product => (
                  <button
                    key={product.id}
                    onClick={() => addProductToCart(product)}
                    className="text-left bg-white rounded-xl border border-vz-line hover:border-vz-teal hover:shadow-lg active:scale-[0.98] active:bg-vz-teal-soft transition-all overflow-hidden min-h-[180px] flex flex-col group"
                  >
                    {/* Photo placeholder header — Odoo POS style with status corner */}
                    <div className="aspect-[4/3] bg-gradient-to-br from-vz-bg-alt to-vz-bg flex items-center justify-center relative">
                      <svg
                        width="36" height="36"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        className="text-vz-ink-mute opacity-60"
                      >
                        <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                      </svg>
                      <span className={`absolute top-1.5 right-1.5 text-[9px] px-1.5 py-0.5 rounded-full font-semibold ${
                        product.status === 'display'
                          ? 'bg-vz-teal-soft text-vz-teal-deep'
                          : 'bg-white text-vz-ink-mute border border-vz-line'
                      }`}>
                        {product.status === 'display' ? 'Vitrine' : 'Stock'}
                      </span>
                    </div>
                    {/* Title + price block */}
                    <div className="p-2.5 flex-1 flex flex-col">
                      <p className="text-sm font-medium text-vz-ink group-hover:text-vz-teal-deep leading-tight line-clamp-2 mb-1">
                        {product.name}
                      </p>
                      <p className="text-[10px] text-vz-ink-mute font-mono truncate">
                        {product.barcode}{product.category ? ` · ${product.category}` : ''}
                      </p>
                      <span className="mt-auto pt-1.5 text-lg font-bold text-vz-teal">
                        {formatCurrency(product.sale_price)}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-vz-ink-mute">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="mb-4 opacity-40">
                  <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                <p className="text-base">Scannez ou tapez le nom d&apos;un article</p>
                <p className="text-sm opacity-70 mt-1">Les résultats apparaissent ici</p>
              </div>
            )}
          </div>
        </div>

      </div>

      {/* ── Client Selection Fullscreen (Odoo 17 pattern) ──────── */}
      <ClientSelectionScreen
        open={showClientSelect}
        onClose={() => setShowClientSelect(false)}
        search={clientSearch}
        onSearchChange={setClientSearch}
        results={clientResults}
        onSelect={(c) => {
          setShowClientSelect(false);
          void selectClient(c);
        }}
        onCreateNew={() => {
          setShowClientSelect(false);
          setShowSubscribeModal(true);
        }}
      />

      {/* ── Client Popup Modal ──────────────────────────────────── */}
      <Modal
        open={showClientPopup}
        onClose={() => setShowClientPopup(false)}
        title="Fiche client"
      >
        {selectedClient && (
          <div className="space-y-4">
            <div className="text-center p-4 bg-vz-accent-soft rounded-lg">
              <p className="text-xl font-bold text-black">{selectedClient.first_name} {selectedClient.last_name}</p>
              {selectedClient.phone && <p className="text-sm text-gray-500 mt-1">{selectedClient.phone}</p>}
              {selectedClient.email && <p className="text-sm text-gray-500">{selectedClient.email}</p>}
              {selectedClient.notes && <p className="text-xs text-gray-400 mt-1">{selectedClient.notes}</p>}
            </div>

            {/* Loyalty */}
            {selectedClient.loyalty ? (
              <div className="p-4 bg-purple-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-purple-800">Carte fidelite</h4>
                  <span className="text-xs px-2 py-1 rounded-full font-medium bg-vz-teal-soft text-vz-teal-deep">
                    {selectedClient.loyalty.membership_number}
                  </span>
                </div>
                <p className="text-2xl font-bold text-purple-700">{selectedClient.loyalty.points} <span className="text-sm font-normal">points</span></p>
              </div>
            ) : (
              <button
                onClick={() => setShowSubscribeModal(true)}
                className="w-full p-4 bg-purple-50 hover:bg-purple-100 rounded-lg text-purple-700 font-medium transition-colors min-h-[48px]"
              >
                Souscrire la carte fidelite
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

      {/* ── Payment Screen (legacy fullscreen, gated by !wizardEnabled) ──
           Odoo 17 POS pattern : plein écran, panneau gauche = récap
           panier + lignes de paiement + reste à payer, panneau droit =
           méthodes + statut CB + numpad. Validation barre du bas. */}
      {showPayment && !wizardEnabled && (
        <div className="fixed inset-0 z-[55] bg-vz-bg flex flex-col">
          {/* Header */}
          <header className="flex-shrink-0 h-14 bg-vz-teal-deep text-white flex items-center px-3 gap-3 shadow-lg">
            <button
              onClick={() => setShowPayment(false)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors min-h-[44px]"
              aria-label="Retour au ticket"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              <span className="text-sm font-medium">Retour au ticket</span>
            </button>
            <div className="h-7 w-px bg-white/15" />
            <h1 className="font-display text-lg">Encaissement</h1>
            {selectedClient && (
              <span className="hidden md:inline text-xs opacity-70 px-2 py-1 rounded bg-white/10">
                {selectedClient.first_name} {selectedClient.last_name}
                {selectedClient.loyalty && ` · ${selectedClient.loyalty.points} pts`}
              </span>
            )}
            <div className="flex-1" />
            <div className="flex flex-col items-end leading-tight">
              <span className="text-[10px] opacity-70 uppercase tracking-wider">Total TTC</span>
              <span className="font-display text-2xl font-bold">{formatCurrency(cartTotalAfterLoyalty)}</span>
            </div>
          </header>

          {/* Body : 2 colonnes */}
          <div className="flex flex-1 overflow-hidden">
            {/* LEFT : récap commande + lignes de paiement + reste */}
            <div className="flex-1 flex flex-col bg-vz-bg overflow-y-auto p-4 md:p-6 gap-4">
              {error && (
                <div className="p-3 bg-red-50 text-red-700 rounded-xl text-sm flex items-start justify-between gap-3">
                  <span className="flex-1">{error}</span>
                  <button onClick={() => setError('')} className="font-bold">×</button>
                </div>
              )}

              {/* Loyalty redemption toggle */}
              {selectedClient?.loyalty && loyaltyPoints > 0 && (
                <div className="p-3 bg-vz-accent-soft rounded-xl flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-vz-ink">Utiliser les points fidélité</p>
                    <p className="text-xs text-vz-ink-soft">{loyaltyPoints} pts = {(loyaltyPoints * 0.10).toFixed(2)} €</p>
                  </div>
                  <button
                    onClick={() => setRedeemPoints(prev => !prev)}
                    className={`relative inline-flex h-7 w-12 items-center rounded-full transition-colors ${redeemPoints ? 'bg-vz-accent' : 'bg-vz-line'}`}
                    aria-label="Activer fidélité"
                  >
                    <span className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${redeemPoints ? 'translate-x-6' : 'translate-x-1'}`} />
                  </button>
                </div>
              )}

              {/* Récap commande */}
              <section className="bg-white rounded-2xl border border-vz-line p-4">
                <header className="flex items-center justify-between mb-3">
                  <h2 className="font-display text-base text-vz-ink">Récap commande</h2>
                  <span className="text-xs text-vz-ink-mute">{cart.length} article{cart.length > 1 ? 's' : ''}</span>
                </header>
                <ul className="space-y-1.5 max-h-[40vh] overflow-y-auto pr-1">
                  {cart.map((item, idx) => {
                    const linePrice = item.price * item.quantity;
                    const afterDiscount = linePrice * (1 - item.discount / 100);
                    return (
                      <li key={idx} className="flex items-center justify-between text-sm border-b border-vz-line/40 last:border-0 pb-1.5 last:pb-0">
                        <div className="min-w-0 flex-1 pr-3">
                          <p className="font-medium text-vz-ink truncate">{item.name}</p>
                          <p className="text-[11px] text-vz-ink-mute">
                            {item.quantity} × {formatCurrency(item.price)}
                            {item.discount > 0 && <span className="ml-1.5 text-vz-accent font-semibold">−{item.discount}%</span>}
                          </p>
                        </div>
                        <span className="font-mono font-medium text-vz-ink">{formatCurrency(afterDiscount)}</span>
                      </li>
                    );
                  })}
                </ul>
                {(loyaltyDiscount > 0 || couponDiscount > 0) && (
                  <div className="mt-2 pt-2 border-t border-vz-line space-y-1 text-xs">
                    {couponDiscount > 0 && (
                      <div className="flex justify-between text-vz-accent">
                        <span>Coupon {couponApplied?.code}</span>
                        <span>−{formatCurrency(couponDiscount)}</span>
                      </div>
                    )}
                    {loyaltyDiscount > 0 && (
                      <div className="flex justify-between text-vz-accent">
                        <span>Fidélité ({redeemPoints ? loyaltyPoints : 0} pts)</span>
                        <span>−{formatCurrency(loyaltyDiscount)}</span>
                      </div>
                    )}
                  </div>
                )}
                <div className="mt-3 pt-3 border-t border-vz-line flex items-baseline justify-between">
                  <span className="text-sm font-semibold text-vz-ink-soft">Total TTC</span>
                  <span className="font-display text-2xl font-bold text-vz-teal">{formatCurrency(cartTotalAfterLoyalty)}</span>
                </div>
              </section>

              {/* Lignes de paiement */}
              {payments.length > 0 && (
                <section className="bg-white rounded-2xl border border-vz-line p-4">
                  <h2 className="font-display text-base text-vz-ink mb-3">Lignes de paiement</h2>
                  <div className="space-y-2">
                    {payments.map((payment, index) => (
                      <div key={index} className="flex items-center gap-3 p-2.5 bg-vz-bg-alt rounded-xl">
                        <span className="flex-1 font-medium text-vz-ink text-sm">{methodLabels[payment.method]}</span>
                        {payment.method !== 'carte' ? (
                          <button
                            type="button"
                            onClick={() => setNumpadTarget({ type: payment.method === 'especes' ? 'cash' : 'payment', index })}
                            className={`px-4 py-2 rounded-lg font-bold text-base font-mono transition-colors min-h-[44px] ${
                              numpadTarget?.index === index
                                ? 'bg-vz-teal text-white shadow-md'
                                : 'bg-white border border-vz-line text-vz-ink hover:bg-vz-bg-alt'
                            }`}
                          >
                            {payment.amount.toFixed(2)} €
                          </button>
                        ) : (
                          <span className="text-sm font-mono font-semibold text-vz-ink px-3">{payment.amount.toFixed(2)} € CB</span>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            removePayment(index);
                            if (payment.method === 'carte') cancelCBPayment();
                            if (numpadTarget?.index === index) setNumpadTarget(null);
                          }}
                          className="w-10 h-10 flex items-center justify-center text-vz-ink-mute hover:text-red-600 rounded-lg hover:bg-red-50 transition-colors"
                          aria-label="Retirer cette ligne"
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                        </button>
                      </div>
                    ))}
                  </div>

                  {/* Reste à payer */}
                  <div className={`mt-3 p-3 rounded-xl flex items-center justify-between ${remaining <= 0.01 ? 'bg-green-50 border border-green-200' : 'bg-vz-accent-soft border border-vz-accent/30'}`}>
                    <span className="text-sm font-semibold">
                      {remaining <= 0.01 ? 'Solde atteint' : 'Reste à payer'}
                    </span>
                    <span className={`font-mono text-xl font-bold ${remaining <= 0.01 ? 'text-green-600' : 'text-vz-accent'}`}>
                      {formatCurrency(Math.max(0, remaining))}
                    </span>
                  </div>

                  {/* Monnaie à rendre */}
                  {numpadTarget?.type === 'cash' && parseFloat(cashGiven) > 0 && payments[numpadTarget.index] && (
                    <div className="mt-2 flex items-center justify-between p-3 bg-green-50 rounded-xl border border-green-200">
                      <span className="text-sm font-semibold text-green-800">Monnaie à rendre</span>
                      <span className="font-mono text-xl font-bold text-green-700">
                        {formatCurrency(Math.max(0, parseFloat(cashGiven) - payments[numpadTarget.index].amount))}
                      </span>
                    </div>
                  )}
                </section>
              )}
            </div>

            {/* RIGHT : méthodes + CB status + numpad */}
            <div className="w-[420px] xl:w-[460px] 2xl:w-[500px] flex flex-col bg-white border-l border-vz-line overflow-y-auto p-4 md:p-5 gap-4">
              {/* Méthodes */}
              <section>
                <h2 className="font-display text-base text-vz-ink mb-2">Moyen de paiement</h2>
                <p className="text-xs text-vz-ink-mute mb-3">Cumulables — paiement mixte possible.</p>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => addPayment('especes')}
                    className="flex flex-col items-center justify-center gap-2 p-4 bg-vz-bg-alt rounded-xl border border-vz-line hover:border-vz-teal hover:bg-white hover:shadow-md active:scale-95 transition-all min-h-[88px] text-vz-ink"
                  >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-vz-teal">
                      <rect x="1" y="4" width="22" height="16" rx="2"/>
                      <line x1="1" y1="10" x2="23" y2="10"/>
                    </svg>
                    <span className="text-sm font-semibold">Espèces</span>
                  </button>
                  <button
                    onClick={() => addPayment('carte')}
                    disabled={cbStatus === 'pending' || cbStatus === 'paid'}
                    className="flex flex-col items-center justify-center gap-2 p-4 bg-vz-bg-alt rounded-xl border border-vz-line hover:border-vz-teal hover:bg-white hover:shadow-md active:scale-95 transition-all min-h-[88px] text-vz-ink disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-vz-teal">
                      <rect x="2" y="5" width="20" height="14" rx="2"/>
                      <line x1="2" y1="10" x2="22" y2="10"/>
                    </svg>
                    <span className="text-sm font-semibold">Carte CB</span>
                  </button>
                  <button
                    onClick={() => addPayment('cheque')}
                    className="flex flex-col items-center justify-center gap-2 p-4 bg-vz-bg-alt rounded-xl border border-vz-line hover:border-vz-teal hover:bg-white hover:shadow-md active:scale-95 transition-all min-h-[88px] text-vz-ink"
                  >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-vz-teal">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span className="text-sm font-semibold">Chèque</span>
                  </button>
                  <button
                    onClick={() => addPayment('avoir')}
                    disabled={!((selectedClient?.avoir_balance || 0) > 0) || payments.some(p => p.method === 'avoir')}
                    title={selectedClient?.avoir_balance ? `Solde avoir : ${formatCurrency(selectedClient.avoir_balance)}` : 'Pas d\'avoir disponible'}
                    className="flex flex-col items-center justify-center gap-2 p-4 bg-vz-bg-alt rounded-xl border border-vz-line hover:border-vz-accent hover:bg-white hover:shadow-md active:scale-95 transition-all min-h-[88px] text-vz-ink disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-vz-accent">
                      <polyline points="20 12 20 22 4 22 4 12"/>
                      <rect x="2" y="7" width="20" height="5"/>
                      <line x1="12" y1="22" x2="12" y2="7"/>
                      <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"/>
                    </svg>
                    <span className="text-sm font-semibold">
                      Avoir{selectedClient?.avoir_balance ? ` (${formatCurrency(selectedClient.avoir_balance)})` : ''}
                    </span>
                  </button>
                </div>
              </section>

              {/* CB Status display */}
              {cbStatus !== 'idle' && (
                <section className={`p-4 rounded-xl border-2 ${
                  cbStatus === 'paid' ? 'border-green-400 bg-green-50' :
                  cbStatus === 'failed' ? 'border-red-400 bg-red-50' :
                  cbStatus === 'timeout' ? 'border-amber-400 bg-amber-50' :
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
                    {cbStatus === 'timeout' && (
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2" className="shrink-0"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                    )}
                    <div>
                      <p className={`font-semibold text-sm ${
                        cbStatus === 'paid' ? 'text-green-700' :
                        cbStatus === 'failed' ? 'text-red-700' :
                        cbStatus === 'timeout' ? 'text-amber-700' :
                        'text-blue-700'
                      }`}>
                        {cbStatus === 'pending' ? 'En attente de confirmation TPE…' :
                         cbStatus === 'paid' ? 'Paiement CB confirmé' :
                         cbStatus === 'timeout' ? 'TPE pas de réponse — vérifie l\'écran du Solo' :
                         'Paiement CB échoué'}
                      </p>
                      {cbStatus === 'pending' && (
                        <p className="text-xs text-blue-500">Présentez la carte sur le lecteur</p>
                      )}
                      {cbStatus === 'timeout' && (
                        <p className="text-xs text-amber-700">
                          Confirme uniquement si le TPE indique &laquo;&nbsp;Paiement accepté&nbsp;&raquo;.
                        </p>
                      )}
                    </div>
                  </div>
                  {cbStatus === 'pending' && (
                    <div className="flex gap-2">
                      <button
                        onClick={confirmCBManually}
                        className="flex-1 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors min-h-[44px]"
                      >
                        Confirmer manuellement
                      </button>
                      <button
                        onClick={cancelCBPayment}
                        className="px-4 py-2.5 bg-white text-red-600 border border-red-300 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors min-h-[44px]"
                      >
                        Annuler
                      </button>
                    </div>
                  )}
                  {cbStatus === 'timeout' && (
                    <div className="flex gap-2">
                      <button
                        onClick={confirmCBManually}
                        className="flex-1 py-2.5 bg-amber-600 text-white text-sm font-medium rounded-lg hover:bg-amber-700 transition-colors min-h-[44px]"
                      >
                        Le TPE dit accepté — confirmer
                      </button>
                      <button
                        onClick={cancelCBPayment}
                        className="px-4 py-2.5 bg-white text-red-700 border border-red-300 text-sm font-medium rounded-lg hover:bg-red-50 transition-colors min-h-[44px]"
                      >
                        Annuler
                      </button>
                    </div>
                  )}
                  {cbStatus === 'failed' && (
                    <button
                      onClick={cancelCBPayment}
                      className="w-full py-2.5 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 min-h-[44px]"
                    >
                      Réessayer
                    </button>
                  )}
                </section>
              )}

              {/* Numpad for active payment */}
              {numpadTarget && (
                <section className="border-t border-vz-line pt-3">
                  <p className="text-xs font-semibold text-vz-ink-mute uppercase tracking-wider mb-2">
                    {numpadTarget.type === 'cash' ? 'Montant remis par le client' : 'Montant à encaisser'}
                  </p>
                  <NumPad
                    value={numpadTarget.type === 'cash' ? parseFloat(cashGiven) || 0 : payments[numpadTarget.index]?.amount || 0}
                    onChange={handleNumpadChange}
                    presets={getNumpadPresets()}
                  />
                </section>
              )}
            </div>
          </div>

          {/* Bottom action bar — Odoo 17 style big Validate button */}
          <footer className="flex-shrink-0 bg-white border-t border-vz-line px-4 md:px-6 py-3 flex items-center gap-3 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
            <button
              onClick={() => setShowPayment(false)}
              className="px-5 py-3 rounded-xl text-sm font-medium text-vz-ink-soft bg-vz-bg-alt hover:bg-vz-line transition-colors min-h-[52px]"
            >
              Annuler
            </button>
            <button
              disabled={remaining > 0.01 || submitting}
              onClick={handleValidate}
              className={`flex-1 py-3 rounded-xl text-lg font-bold transition-colors min-h-[52px] flex items-center justify-center gap-3 ${
                remaining > 0.01 || submitting
                  ? 'bg-vz-line text-vz-ink-mute cursor-not-allowed'
                  : 'bg-vz-teal text-white hover:bg-vz-teal-deep active:bg-vz-teal-deep shadow-lg'
              }`}
            >
              {submitting ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Traitement…
                </>
              ) : (
                <>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  Valider — {formatCurrency(cartTotalAfterLoyalty)}
                </>
              )}
            </button>
          </footer>
        </div>
      )}

      {/* ── New SumUp-style wizard (PR 6/6) — gated by feature flag ─── */}
      {wizardEnabled && (
        <MultiStepPaymentWizard
          open={showPayment}
          totalTtc={cartTotalAfterLoyalty}
          hasClient={!!selectedClient}
          avoirBalance={selectedClient?.avoir_balance ?? undefined}
          onClose={() => {
            posPayment.cancel();
            setShowPayment(false);
          }}
          onCardCheckout={posPayment.runCardCheckout}
          onCommit={async (tenders) => {
            // Map wizard tenders (cash | card | cheque | avoir) to the legacy
            // ``payments`` shape (especes | carte | cheque | avoir).
            const methodMap: Record<string, string> = {
              cash: 'especes',
              card: 'carte',
              cheque: 'cheque',
              avoir: 'avoir',
            };
            const mapped = tenders.map((t) => ({
              method: methodMap[t.method] || t.method,
              amount: t.amount,
            }));
            // Force CB to "paid" so handleValidate doesn't bail on the legacy
            // guard — the wizard already drove the SumUp checkout via the hook.
            if (mapped.some((m) => m.method === 'carte')) {
              setCbStatus('paid');
            }
            setPayments(mapped);
            // Wait one tick so React flushes the payments state before commit
            await new Promise((r) => setTimeout(r, 0));
            await handleValidateWizard();
          }}
        />
      )}

      {/* ── New ReceiptPreviewCard (wizard mode, replaces legacy modal) */}
      {wizardEnabled && showWizardReceipt && (
        <Modal
          open={showWizardReceipt}
          onClose={() => {
            setShowWizardReceipt(false);
            handleReceiptClose();
          }}
          title="Vente validée"
        >
          <ReceiptPreviewCard
            ticketNumber={wizardTxNumber ?? 0}
            totalTtc={cartTotalAfterLoyalty}
            isInvoice={invoiceFields.is_invoice}
            invoiceNumber={wizardInvoiceNumber}
            receiptText={receiptText}
            clientEmail={selectedClient?.email}
            clientPhone={selectedClient?.phone}
            onPrintEscpos={printReceiptOnPrinter}
            onPrintAirprint={() => {
              printReceipt(receiptText);
              setShowWizardReceipt(false);
              handleReceiptClose();
            }}
            onResend={async (channel) => {
              if (!receiptTxId) return;
              await api.post(`/api/pos/transactions/${receiptTxId}/resend`, {
                channel,
              });
            }}
            onDownloadInvoicePdf={async () => {
              if (!receiptTxId) return;
              const res = await api.get(
                `/api/pos/transactions/${receiptTxId}/invoice.pdf`,
              );
              if (!res.ok) return;
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `FACT-${new Date().getFullYear()}-${String(
                wizardInvoiceNumber ?? wizardTxNumber ?? 0,
              ).padStart(6, '0')}.pdf`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
              URL.revokeObjectURL(url);
            }}
            onNewSale={() => {
              setShowWizardReceipt(false);
              handleReceiptClose();
              setInvoiceFields({
                is_invoice: false,
                client_company_name: '',
                client_siret: '',
                client_billing_address: '',
              });
            }}
          />
        </Modal>
      )}

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
            {/* AirPrint fallback — visible on iOS only. On Android Chrome the
                browser print path doesn't drive the thermal printer (no RJ11
                kick), so the button would just dump a PDF. The MUNBYN ESC/POS
                path above is the canonical receipt route on the Lenovo Idea
                Tab Pro 13" caisse. */}
            {isIOS() && (
              <Button onClick={() => { printReceipt(receiptText); handleReceiptClose(); }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1.5"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                Imprimer (AirPrint)
              </Button>
            )}
          </div>
        }
      >
        <div className="bg-gray-50 p-4 rounded-lg">
          <pre className="whitespace-pre-wrap text-sm font-mono text-black">{receiptText}</pre>
        </div>
        {printMsg && (
          <p className="mt-3 text-sm text-vz-teal">{printMsg}</p>
        )}
      </Modal>

      {/* ── Open Drawer Modal (legacy) ────────────────────────── */}
      {!wizardEnabled && (
        <Modal open={showDrawerOpen} onClose={() => setShowDrawerOpen(false)} title="Initialiser la caisse"
          actions={<Button size="lg" onClick={handleOpenDrawer} disabled={drawerSubmitting}>{drawerSubmitting ? 'En cours...' : 'Ouvrir la caisse'}</Button>}>
          <div className="space-y-3">
            <p className="text-sm text-gray-500">Saisissez le fonds de caisse initial (monnaie disponible).</p>
            <NumPad value={drawerAmount} onChange={setDrawerAmount} presets={[50, 100, 150, 200]} />
          </div>
        </Modal>
      )}

      {/* ── Close Drawer Modal (legacy) ───────────────────────── */}
      {!wizardEnabled && (
        <Modal open={showDrawerClose} onClose={() => setShowDrawerClose(false)} title="Clôturer la caisse"
          actions={<Button size="lg" onClick={handleCloseDrawer} disabled={drawerSubmitting}>{drawerSubmitting ? 'En cours...' : 'Générer le rapport Z'}</Button>}>
          <div className="space-y-3">
            <p className="text-sm text-gray-500">Comptez les espèces en caisse et saisissez le montant total.</p>
            <NumPad value={drawerAmount} onChange={setDrawerAmount} presets={[]} />
          </div>
        </Modal>
      )}

      {/* ── New drawer modals (PR 6/6 — denomination grid + 3-phase close) */}
      {wizardEnabled && (
        <>
          <CashDrawerOpenModal
            open={showDrawerOpen}
            onClose={() => setShowDrawerOpen(false)}
            onSubmit={async ({ opening_amount, opening_breakdown }) => {
              setDrawerSubmitting(true);
              try {
                const res = await api.post('/api/pos/drawer/open', {
                  opening_amount,
                  opening_breakdown: opening_breakdown ?? undefined,
                  cashier_id: cashier?.id,
                });
                if (res.ok) {
                  const data = await res.json();
                  setDrawer({
                    open: true,
                    drawer_id: data.drawer_id,
                    opening_amount: data.opening_amount,
                  });
                  setShowDrawerOpen(false);
                }
              } finally {
                setDrawerSubmitting(false);
              }
            }}
          />
          <CashDrawerCloseModal
            open={showDrawerClose}
            onClose={() => setShowDrawerClose(false)}
            expectedAmount={drawer?.opening_amount ?? null}
            defaultAllowedDiscrepancy={2}
            onSubmit={async ({
              closing_amount,
              closing_breakdown,
              closing_note,
              allowed_discrepancy_override,
            }) => {
              setDrawerSubmitting(true);
              try {
                const res = await api.post('/api/pos/drawer/close', {
                  closing_amount,
                  closing_breakdown: closing_breakdown ?? undefined,
                  closing_note: closing_note ?? undefined,
                  allowed_discrepancy_override:
                    allowed_discrepancy_override ?? undefined,
                  cashier_id: cashier?.id,
                });
                if (res.ok) {
                  const data = await res.json();
                  setZReport(data);
                  setDrawer({ open: false });
                  setShowDrawerClose(false);
                  return { z_report_number: data.z_report_number };
                }
              } finally {
                setDrawerSubmitting(false);
              }
              return undefined;
            }}
          />
        </>
      )}

      {/* ── Z Report Modal ───────────────────────────────────────── */}
      <Modal open={!!zReport} onClose={() => setZReport(null)} title="Rapport Z — Clôture de caisse"
        actions={<Button onClick={() => setZReport(null)}>Fermer</Button>}>
        {zReport && (
          <div className="space-y-3">
            <div className="p-4 bg-vz-teal-soft rounded-xl text-center">
              <p className="text-xs text-gray-500 mb-1">Rapport Z n°{zReport.z_report_number}</p>
              <p className="text-3xl font-bold text-vz-teal">{formatCurrency(zReport.total_net)}</p>
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

      {/* Loyalty subscription modal (PR1) */}
      <Modal open={showSubscribeModal} onClose={closeSubscribeModal} title="Souscription fidelite">
        {subscribeSuccess ? (
          <div className="space-y-4">
            <div className="p-4 bg-vz-teal-soft rounded-lg">
              <p className="text-sm text-gray-600">Carte creee :</p>
              <p className="text-3xl font-bold text-vz-teal mt-1 tracking-wider">
                {subscribeSuccess.membership_number}
              </p>
            </div>
            <p className="text-sm text-gray-500">
              Imprimez le QR ou envoyez la carte au wallet du client depuis la fiche cliente.
            </p>
            <Button onClick={closeSubscribeModal} className="w-full">Fermer</Button>
          </div>
        ) : subscribeDuplicate ? (
          <div className="space-y-4">
            <div className="p-4 bg-orange-50 rounded-lg">
              <p className="text-sm text-orange-700 font-medium">
                Cet email a deja une carte de fidelite : {subscribeDuplicate.membership_number}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Identifiez la cliente existante au lieu d&apos;en creer une nouvelle.
              </p>
            </div>
            <Button onClick={closeSubscribeModal} className="w-full">Compris</Button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Prenom</label>
                <Input
                  value={subscribeForm.first_name}
                  onChange={(e) => setSubscribeForm({ ...subscribeForm, first_name: e.target.value })}
                  placeholder="Alice"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nom</label>
                <Input
                  value={subscribeForm.last_name}
                  onChange={(e) => setSubscribeForm({ ...subscribeForm, last_name: e.target.value })}
                  placeholder="Martin"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Email</label>
              <Input
                type="email"
                value={subscribeForm.email}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, email: e.target.value })}
                placeholder="alice@email.fr"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Code postal</label>
              <Input
                value={subscribeForm.postal_code}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, postal_code: e.target.value })}
                placeholder="27200"
              />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={subscribeForm.accept_terms}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, accept_terms: e.target.checked })}
              />
              <span>J&apos;accepte les conditions du programme fidelite Vintiz (1 € = 1 pt, peremption 24 mois).</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={subscribeForm.optin_newsletter}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, optin_newsletter: e.target.checked })}
              />
              <span>J&apos;accepte de recevoir la newsletter Vintiz.</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={subscribeForm.optin_profiling}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, optin_profiling: e.target.checked })}
              />
              <span>J&apos;accepte le profilage Personal Shopper (recommandations personnalisees).</span>
            </label>
            {subscribeError && (
              <p className="text-sm text-red-600">{subscribeError}</p>
            )}
            <div className="flex gap-2 pt-2">
              <Button variant="outline" onClick={closeSubscribeModal} className="flex-1">
                Annuler
              </Button>
              <Button
                onClick={submitSubscription}
                disabled={
                  subscribeBusy ||
                  !subscribeForm.first_name ||
                  !subscribeForm.last_name ||
                  !subscribeForm.email ||
                  !subscribeForm.accept_terms
                }
                className="flex-1"
              >
                {subscribeBusy ? '...' : 'Creer la carte'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
