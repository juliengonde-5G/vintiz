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
import InlineResendButtons from '@/components/pos/InlineResendButtons';
import ClientCompanion from '@/components/pos/ClientCompanion';
import ClientSelectionScreen from '@/components/pos/ClientSelectionScreen';
import InvoiceClientForm, {
  type InvoiceFields,
  isInvoiceFormValid,
} from '@/components/pos/InvoiceClientForm';
import LoyaltyCustomerCard, { type CustomerBrief } from '@/components/pos/LoyaltyCustomerCard';
import MultiStepPaymentWizard from '@/components/pos/MultiStepPaymentWizard';
import ReceiptPreviewCard from '@/components/pos/ReceiptPreviewCard';
import { usePosPayment, type SumUpPaymentDetails } from '@/hooks/usePosPayment';
import { api } from '@/lib/api';
import { useConnectivity } from '@/lib/connectivity';
import { isPosWizardEnabled } from '@/lib/feature-flags';
import { formatCurrency, mediaUrl } from '@/lib/format';
import { useLandscapeLock } from '@/lib/orientation';
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
  photo_url?: string | null;
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
  method: 'especes' | 'carte' | 'cheque' | 'cheque_cdc' | 'avoir' | 'voucher';
  amount: number;
  // Bon cadeau d'ouverture affecté comme règlement : code + libellé du bon.
  voucher_code?: string;
  label?: string;
}

// Bons cadeau d'ouverture (zone Événementiel)
interface VoucherType {
  key: string;
  label: string;
  discount_type: string;
  discount_value: number;
  free_item_label: string | null;
  valid_until?: string;
  active?: boolean;
  // true = immediate voucher (utilisable sur l'achat en cours) — pas de
  // règle « 1 par personne » ni « pas le jour même ». false = bon
  // « prochain achat » (cadré par les 2 règles).
  immediate?: boolean;
}

interface ClientVoucher {
  code: string;
  label: string;
  discount_type: string;
  discount_value: number;
  free_item_label: string | null;
  requires_item: boolean;
  value_for_cart: number;
  valid_until: string | null;
  // false pour un bon d'ouverture émis le jour même : utilisable dès le
  // lendemain seulement. Le bouton « Affecter » est désactivé et un badge
  // « disponible demain » est affiché à la place du montant.
  available_today?: boolean;
  available_from?: string | null;
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


/** Pull the SumUp identifiers out of a /cb/{id}/status response so they can
 * be persisted on the Payment row (enables API-driven card refunds). */
function extractCbDetails(
  s: Record<string, unknown>,
  checkoutId?: string,
): SumUpPaymentDetails {
  return {
    sumup_checkout_id: (s.checkout_id as string) || checkoutId,
    sumup_transaction_id: s.sumup_transaction_id as string | undefined,
    sumup_transaction_code: s.sumup_transaction_code as string | undefined,
    sumup_auth_code: s.sumup_auth_code as string | undefined,
    sumup_card_brand: s.sumup_card_brand as string | undefined,
    sumup_card_last4: s.sumup_card_last4 as string | undefined,
    sumup_environment: s.environment as string | undefined,
  };
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

  // Bons cadeau d'ouverture (zone Événementiel) : catalogue + bons de la cliente.
  const [voucherCatalog, setVoucherCatalog] = useState<VoucherType[]>([]);
  const [clientVouchers, setClientVouchers] = useState<ClientVoucher[]>([]);
  const [showEventModal, setShowEventModal] = useState(false);
  const [eventBusy, setEventBusy] = useState(false);
  const [eventToast, setEventToast] = useState('');
  // Compagnon caisse — modale plein écran déclenchée par le bouton dans
  // le ticket (cf. ClientCompanion). Sort le panneau du flux ticket pour
  // garder Encaisser visible.
  const [showCompanionModal, setShowCompanionModal] = useState(false);
  // Sélection des bons cochés dans la modale Événementiel (validation via
  // bouton "Valider" plutôt que sur clic direct). Permet de cocher
  // plusieurs bons immédiats à la fois pour la même cliente sans
  // confirmation à chaque clic.
  const [eventSelected, setEventSelected] = useState<string[]>([]);

  // Manual article
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [manualName, setManualName] = useState('');
  const [manualPrice, setManualPrice] = useState('');

  // Reusable bags quick-add (configurable in Settings > Caisse).
  // Each bag is a manual line: unlimited quantity, no stock impact, price
  // editable per sale at the till. One quick-add button per bag.
  const [bags, setBags] = useState<{ label: string; price_eur: number }[]>([
    { label: 'Sac boutique Vintiz', price_eur: 0.25 },
  ]);
  const [priceEditIdx, setPriceEditIdx] = useState<number | null>(null);

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
  // Transient toast for drawer kick outcomes (espèces auto-kick + manual
  // "Tiroir" button on the top bar). Without this the operator sees no
  // feedback when the WebUSB call fails (device unplugged, permission
  // revoked) — looks like the button is "KO".
  const [drawerToast, setDrawerToast] = useState<{ msg: string; ok: boolean } | null>(null);

  // SumUp Solo connectivity check — probed at startup so the cashier
  // sees a banner when the TPE is offline or misconfigured BEFORE
  // they try a CB sale that would otherwise hang for 30s on the
  // wizard.
  const [sumupStatus, setSumupStatus] = useState<{
    ready: boolean;
    online: boolean;
    paired: boolean;
    configured: boolean;
    message: string;
    status: string;
    state?: string | null;
    battery_level?: number | null;
    is_sandbox?: boolean;
    environment?: string;
  } | null>(null);

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

  // SumUp identifiers captured when a card payment reaches PAID — merged onto
  // the carte payment line so the API persists them on the Payment row (lets a
  // later refund be issued through the SumUp API instead of manually).
  const [cbDetails, setCbDetails] = useState<SumUpPaymentDetails | null>(null);

  // CB slip (ticket carte) — after a CB attempt the merchant copy prints
  // automatically and we offer the client copy via this prompt.
  const [cbClientPrompt, setCbClientPrompt] = useState<import('@/lib/print-ticket').CbTicketData | null>(null);
  const [cbTicketBusy, setCbTicketBusy] = useState(false);

  // Which cart item has its discount strip expanded (compact layout: hide by
  // default to fit more items on Lenovo landscape).
  const [discountOpenIdx, setDiscountOpenIdx] = useState<number | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clientDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Search input ref — the USB-HID scanner needs the search field focused
  // to deliver the barcode. We refocus after every cart add so the cashier
  // can scan a second item without tapping the field again.
  const searchInputRef = useRef<HTMLInputElement>(null);
  const refocusSearch = useCallback(() => {
    // Don't fight a modal — only refocus when no overlay is open.
    if (showPayment || showClientSelect || showClientPopup || showSubscribeModal) return;
    if (showDrawerOpen || showDrawerClose || showCashierModal || showReceipt) return;
    if (showWizardReceipt || showManualEntry) return;
    if (showCompanionModal || showEventModal) return;
    requestAnimationFrame(() => {
      searchInputRef.current?.focus();
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    showPayment, showClientSelect, showClientPopup, showSubscribeModal,
    showDrawerOpen, showDrawerClose, showCashierModal, showReceipt,
    showWizardReceipt, showManualEntry,
    showCompanionModal, showEventModal,
  ]);

  // Landscape lock for the Lenovo Idea Tab Pro Gen 2 (TB39OFU) when running
  // as a PWA. Silently ignored in regular tab mode (Chrome non-installé).
  useLandscapeLock();

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

  // Cash under-payment guard : when an espèces line is present, the cash
  // physically received (``cashGiven``) must cover the cash amount due. Blocks
  // validation otherwise so a cashier can't close a ticket with too little cash.
  const cashLine = payments.find((p) => p.method === 'especes');
  const cashShort = !!cashLine && (parseFloat(cashGiven || '0') + 1e-6) < cashLine.amount;

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

  // POS quick-add config — list of reusable bags (Sac Kraft, Grand Sac Kraft…).
  // The API resolves the legacy single-bag fields into a list, so we get a
  // non-empty array whatever the persisted shape.
  useEffect(() => {
    api.get('/api/admin/pos-config').then(async (res) => {
      if (!res.ok) return;
      const cfg = await res.json();
      const list = Array.isArray(cfg.bags)
        ? cfg.bags
            .map((b: { label?: unknown; price_eur?: unknown }) => ({
              label: String(b?.label ?? '').trim(),
              price_eur:
                typeof b?.price_eur === 'number'
                  ? b.price_eur
                  : parseFloat(String(b?.price_eur ?? '0')) || 0,
            }))
            .filter((b: { label: string }) => b.label)
        : [];
      if (list.length > 0) setBags(list);
      else if (cfg.bag_label) {
        // Fallback : config very old without ``bags`` and the resolver didn't
        // run (defensive — shouldn't happen with the current API).
        const price =
          typeof cfg.bag_default_price_eur === 'number'
            ? cfg.bag_default_price_eur
            : 0.25;
        setBags([{ label: String(cfg.bag_label), price_eur: price }]);
      }
    }).catch(() => {});
  }, []);

  // ── SumUp connectivity check (cloud + reader status) ─────────────
  // Probe at mount so the cashier sees a yellow banner when the TPE
  // is offline before they try a CB sale that would otherwise hang
  // through the wizard. Re-probed every 60 s so a transient Wi-Fi
  // drop on the Solo clears on its own without a page reload.
  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      try {
        const res = await api.get('/api/pos/payments/cb/ping');
        if (cancelled || !res.ok) return;
        const data = await res.json();
        if (!cancelled) setSumupStatus(data);
      } catch {
        /* silent — sumupStatus stays null, no banner shown */
      }
    };
    probe();
    const id = setInterval(probe, 60_000);
    return () => { cancelled = true; clearInterval(id); };
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
    setError('');
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
        setShowDrawerClose(false);
      } else {
        // Avant le fix : on swallow-ait silencieusement → bouton "Générer
        // le rapport Z" qui ne faisait rien à l'écran. On surface la
        // raison HTTP (caisse déjà fermée, montant invalide, drawer
        // introuvable…) pour que le manager puisse réagir.
        const err = await res.json().catch(() => null);
        const detail = err?.detail || err?.message || `Erreur HTTP ${res.status}`;
        setError(`Clôture refusée : ${detail}`);
        setDrawerToast({ msg: `Clôture refusée : ${detail}`, ok: false });
        setTimeout(() => setDrawerToast(null), 6000);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'erreur réseau';
      setError(`Clôture impossible (${msg}). Vérifiez la connexion API.`);
      setDrawerToast({ msg: `Clôture impossible (${msg})`, ok: false });
      setTimeout(() => setDrawerToast(null), 6000);
    }
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

  // ── Bons cadeau d'ouverture (zone Événementiel) ─────────────────
  // Catalogue chargé une fois (boutons de la zone Événementiel).
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const res = await api.get('/api/pos/event-vouchers/catalog');
        if (res.ok && active) setVoucherCatalog((await res.json()).vouchers || []);
      } catch { /* silent */ }
    })();
    return () => { active = false; };
  }, []);

  // Bons actifs de la cliente — rafraîchis à l'identification et quand le panier
  // change (la valeur affectable d'un % / d'un foulard dépend du panier).
  useEffect(() => {
    if (!selectedClient) { setClientVouchers([]); return; }
    const clientId = selectedClient.id;
    const t = setTimeout(async () => {
      try {
        const ids = cart.filter((i) => i.product_id).map((i) => i.product_id).join(',');
        const cents = Math.round(cartTotal * 100);
        const res = await api.get(
          `/api/pos/clients/${clientId}/vouchers?cart_total_cents=${cents}&items=${encodeURIComponent(ids)}`,
        );
        if (res.ok) setClientVouchers((await res.json()).vouchers || []);
      } catch { /* silent */ }
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClient, cart, cartTotal]);

  // Émettre les bons cochés via le bouton « Valider » de la modale
  // Événementiel. Les émissions tournent en séquence (l'API est
  // best-effort par bon : un échec n'interrompt pas les autres) puis on
  // recharge la liste des bons actifs de la cliente.
  const issueSelectedVouchers = async () => {
    if (!selectedClient || eventBusy || eventSelected.length === 0) return;
    setEventBusy(true);
    const results: { key: string; label: string; ok: boolean; detail?: string }[] = [];
    for (const typeKey of eventSelected) {
      const label = voucherCatalog.find((v) => v.key === typeKey)?.label || typeKey;
      try {
        const res = await api.post('/api/pos/event-vouchers/issue', {
          client_id: selectedClient.id,
          type_key: typeKey,
        });
        const data = await res.json().catch(() => null);
        if (res.ok) {
          results.push({ key: typeKey, label, ok: true });
        } else {
          results.push({ key: typeKey, label, ok: false, detail: data?.detail });
        }
      } catch {
        results.push({ key: typeKey, label, ok: false, detail: 'Erreur réseau' });
      }
    }
    // Recharger la liste des bons actifs de la cliente.
    try {
      const ids = cart.filter((i) => i.product_id).map((i) => i.product_id).join(',');
      const cents = Math.round(cartTotal * 100);
      const vres = await api.get(
        `/api/pos/clients/${selectedClient.id}/vouchers?cart_total_cents=${cents}&items=${encodeURIComponent(ids)}`,
      );
      if (vres.ok) setClientVouchers((await vres.json()).vouchers || []);
    } catch { /* silent */ }
    setEventBusy(false);
    const okKeys = new Set(results.filter((r) => r.ok).map((r) => r.key));
    const okCount = okKeys.size;
    const koResults = results.filter((r) => !r.ok);
    if (koResults.length === 0) {
      setEventToast(
        `${okCount} bon${okCount > 1 ? 's' : ''} crédité${okCount > 1 ? 's' : ''} sur le compte de ${selectedClient.first_name}.`,
      );
      setEventSelected([]);
      setShowEventModal(false);
    } else {
      const detail = koResults
        .map((r) => `${r.label} : ${r.detail || 'refusé'}`)
        .join(' · ');
      setEventToast(
        okCount > 0
          ? `${okCount} OK, ${koResults.length} refusé${koResults.length > 1 ? 's' : ''} (${detail})`
          : `Émission refusée : ${detail}`,
      );
      // Garder la modale ouverte mais retirer les bons déjà crédités
      // de la sélection (évite un double crédit si on re-valide).
      setEventSelected((prev) => prev.filter((k) => !okKeys.has(k)));
    }
    setTimeout(() => setEventToast(''), 4500);
  };

  const toggleEventSelected = (typeKey: string) => {
    setEventSelected((prev) =>
      prev.includes(typeKey) ? prev.filter((k) => k !== typeKey) : [...prev, typeKey],
    );
  };

  // Affecter un bon de la cliente comme moyen de paiement (ligne de règlement).
  const addVoucherPayment = (v: ClientVoucher) => {
    if (payments.some((p) => p.voucher_code === v.code)) return;
    const remainingNow = Math.max(0, parseFloat((cartTotalAfterLoyalty - totalPaid).toFixed(2)));
    const amount = Math.min(v.value_for_cart || 0, remainingNow);
    if (amount <= 0) {
      setError(
        v.requires_item
          ? `Ajoutez un ${v.free_item_label || 'article éligible'} au panier pour utiliser ce bon.`
          : 'Le panier est déjà couvert — rien à affecter pour ce bon.',
      );
      return;
    }
    setPayments((prev) => [
      ...prev,
      { method: 'voucher', amount: parseFloat(amount.toFixed(2)), voucher_code: v.code, label: v.label },
    ]);
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
        // Toujours sélectionner la cliente qui vient d'être créée — la
        // caissière vient de la saisir, elle s'attend à la voir épinglée
        // sur le ticket en cours (et à profiter immédiatement du
        // ClientCompanion + des bons cadeau).
        try {
          const detailRes = await api.get(`/api/crm/clients/${data.client_id}`);
          if (detailRes.ok) setSelectedClient(await detailRes.json());
        } catch {
          /* best-effort — on garde la cliente non-épinglée si l'appel échoue */
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
    // Keep the search input focused so the USB-HID scanner can immediately
    // pick up the next barcode (Lenovo Idea Tab Pro Gen 2 + Inateck BCST-35).
    refocusSearch();
  };

  // Barcode scanner (Inateck BCST-60 / 160B USB HID): types the code fast then
  // sends Enter. We hit the dedicated by-barcode endpoint first (exact
  // match, bypasses the status filter — works for freshly created
  // products whose lifecycle stage isn't ``stock`` yet) and fall back
  // to the fuzzy search only on 404 so partial scans still work.
  const handleBarcodeScan = useCallback(async (rawCode: string) => {
    const code = rawCode.trim();
    if (!code) return;
    try {
      const exactRes = await api.get(
        `/api/inventory/products/by-barcode/${encodeURIComponent(code)}`,
      );
      if (exactRes.ok) {
        addProductToCart(await exactRes.json());
        return;
      }
      if (exactRes.status !== 404) {
        setError(`Erreur lecture code-barres ${code}`);
        return;
      }
      // Fallback: fuzzy search (legacy behaviour, useful when the
      // operator types a partial barcode by hand).
      const res = await api.get(
        `/api/inventory/products/search?q=${encodeURIComponent(code)}`,
      );
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

  // Kick le tiroir-caisse via la MUNBYN ESC/POS (impulsion ESC p m sur
  // le port 9100). Remplace l'ancien fallback AirPrint qui ouvrait une
  // pop-up window.print() — celle-ci ne pilotait pas la MUNBYN sur
  // Android (Lenovo Idea Tab Pro Gen 2 Chrome), elle générait juste un
  // PDF. Désormais le tiroir est piloté côté API uniquement.
  const kickDrawer = useCallback(() => {
    // Route through the shared helper so the kick works in both USB and
    // network modes. Surface the outcome as a transient toast — the
    // previous "best-effort silent" wrapper hid genuine failures and
    // looked broken from the cashier's POV when nothing happened on
    // click (device unplugged, permission revoked, etc.).
    //
    // Errors are also pushed to the console so the cashier can copy/paste
    // them when calling support — the toast is intentionally short, the
    // console keeps the full diagnostic.
    void (async () => {
      const { kickDrawer: kick } = await import('@/lib/print-ticket');
      const result = await kick();
      if (!result.ok) {
        console.warn('[POS] Drawer kick failed:', result);
      }
      setDrawerToast({ msg: result.message, ok: result.ok });
      // Failures stay longer (6 s) so the cashier has time to read the
      // remediation tip ("vérifie l'IP MUNBYN", "rebranche la douchette"…).
      setTimeout(() => setDrawerToast(null), result.ok ? 3500 : 6000);
    })();
  }, []);

  const addBag = (bag: { label: string; price_eur: number }) => {
    setCart(prev => {
      const existing = prev.find(i => i.name === bag.label && i.isManual);
      if (existing) {
        return prev.map(i => i.name === bag.label && i.isManual
          ? { ...i, quantity: i.quantity + 1 } : i);
      }
      return [...prev, {
        product_id: null,
        name: bag.label,
        price: bag.price_eur,
        quantity: 1,
        discount: 0,
        isManual: true,
      }];
    });
    // Le scanner USB-HID doit pouvoir saisir l'article suivant sans
    // qu'on doive retaper sur le champ de recherche.
    refocusSearch();
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
    refocusSearch();
  };

  const updateDiscount = (index: number, discount: number) => {
    setCart(prev => prev.map((item, i) =>
      i === index ? { ...item, discount: Math.max(0, Math.min(30, discount)) } : item
    ));
  };

  // Inline price edit — only for manual lines (bag, custom article). Real
  // catalog products keep their tagged sale_price.
  const updatePrice = (index: number, value: number) => {
    setCart(prev => prev.map((item, i) =>
      i === index ? { ...item, price: Math.max(0, value) } : item
    ));
  };

  const removeFromCart = (index: number) => {
    setCart(prev => prev.filter((_, i) => i !== index));
    refocusSearch();
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
    setCbDetails(null);
    try {
      const res = await api.post('/api/pos/payments/cb/initiate', {
        amount: parseFloat(amount.toFixed(2)),
        description: `Vente Vintiz #${Date.now()}`,
        // Reconciliation key so the SumUp transaction can be looked up later.
        foreign_transaction_id: generateClientUuid(),
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
                setCbDetails(extractCbDetails(s, data.checkout_id));
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
    setCbDetails(null);
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
          setCbDetails(extractCbDetails(s, cbCheckoutId));
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
        payments: tenders.map((p) => ({
          method: p.method,
          amount: p.amount,
          ...(p.method === 'carte' && cbDetails ? cbDetails : {}),
          ...(p.method === 'voucher' && p.voucher_code ? { voucher_code: p.voucher_code } : {}),
        })),
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
      // Cash must cover the cash amount due before the ticket can close.
      if (cashShort) {
        setError('Montant en espèces reçu insuffisant pour couvrir le ticket.');
        setSubmitting(false);
        return;
      }
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
        payments: payments.map(p => ({
          method: p.method,
          amount: p.amount,
          ...(p.method === 'carte' && cbDetails ? cbDetails : {}),
          ...(p.method === 'voucher' && p.voucher_code ? { voucher_code: p.voucher_code } : {}),
        })),
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
    const { printTransactionTicket } = await import('@/lib/print-ticket');
    const result = await printTransactionTicket(receiptTxId, { kickDrawer: true });
    setPrintMsg(result.message);
    setPrinting(false);
  };

  const resendReceipt = async (channel: 'email' | 'sms', to?: string) => {
    if (!receiptTxId) return;
    const res = await api.post(`/api/pos/transactions/${receiptTxId}/resend`, {
      channel,
      ...(to ? { to } : {}),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(body.detail || "Échec de l'envoi");
    }
    return body as { simulated?: boolean; message?: string };
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
    cheque_cdc: 'Cheque CDC',
    avoir: 'Avoir client',
    voucher: 'Bon cadeau',
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

      {/* SumUp connectivity banner — silent when ready, yellow warning
          when the TPE is unreachable or misconfigured. Lets the cashier
          either fix the issue or skip CB and encash cash/cheque
          without waiting 30 s for a wizard timeout. */}
      {sumupStatus?.is_sandbox && (
        <div className="flex-shrink-0 px-3 py-2 bg-orange-100 border-b border-orange-300 text-orange-900 text-sm flex items-center gap-2 font-medium">
          <span className="inline-block w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
          <strong>MODE TEST SumUp</strong>
          <span className="opacity-80">— clé sup_sk_test_… utilisée. Ne pas encaisser de vrais paiements.</span>
        </div>
      )}
      {sumupStatus && !sumupStatus.ready && (
        <div className="flex-shrink-0 px-3 py-2 bg-yellow-50 border-b border-yellow-200 text-yellow-900 text-sm flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <strong>TPE SumUp&nbsp;:</strong>
          <span className="flex-1">{sumupStatus.message}</span>
          <a href="/settings" className="underline text-yellow-900 hover:text-yellow-950">
            Configurer
          </a>
        </div>
      )}

      {/* ── Main POS area ─────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* ── LEFT PANEL: Order / Cart ──────────────────────────────
             Width is responsive — la Lenovo Idea Tab Pro Gen 2 13" rend
             à ≥1280 px en paysage et bénéficie d'une colonne ticket large
             (plus de lignes visibles sans scroll). xl: ≥1280, 2xl: ≥1536
             pour les setups dock très larges. */}
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
            {/* Zone Événementiel — distribution des bons cadeau d'ouverture */}
            <button
              onClick={() => setShowEventModal(true)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-vz-accent/40 bg-vz-accent-soft text-vz-ink hover:bg-vz-accent-soft/70 transition-colors text-sm min-h-[44px]"
              title="Bons cadeau d'ouverture"
            >
              <span aria-hidden>🎟</span>
              <span className="hidden sm:inline">Événementiel</span>
            </button>
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

          {/* Bons cadeau sur le compte — affichés dès l'identification cliente */}
          {selectedClient && clientVouchers.length > 0 && (
            <div className="px-3 pt-2">
              <div className="rounded-xl border border-vz-accent/40 bg-vz-accent-soft px-3 py-2 text-xs text-vz-ink flex items-center gap-2">
                <span aria-hidden>🎟</span>
                <span>
                  <strong>{clientVouchers.length} bon{clientVouchers.length > 1 ? 's' : ''} d&apos;achat</strong> sur ce compte — à affecter au paiement.
                </span>
              </div>
            </div>
          )}

          {/* PR4 — Companion caisse : bouton compact dans le ticket, ouvre une
              modale plein écran. Avant : le panneau s'inlinait sous la
              fiche cliente, ce qui empilait des sections et faisait
              disparaître le bouton Encaisser en bas. Maintenant le panneau
              est isolé dans une modale (comme la souscription fidélité) ;
              le ticket et l'Encaisser restent toujours visibles. */}
          {selectedClient && (
            <div className="px-3 pt-2">
              <button
                type="button"
                onClick={() => setShowCompanionModal(true)}
                className="w-full flex items-center justify-between gap-2 rounded-lg border border-vz-teal/30 bg-vz-teal-soft/40 px-3 py-2 text-xs font-medium text-vz-teal-deep hover:bg-vz-teal-soft transition-colors"
                aria-label="Ouvrir le compagnon caisse"
              >
                <span className="flex items-center gap-1.5">
                  <span aria-hidden>💡</span>
                  Compagnon caisse
                  <span className="text-vz-ink-mute font-normal">
                    — suggestions, coupons, alertes
                  </span>
                </span>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                >
                  <polyline points="9 6 15 12 9 18" />
                </svg>
              </button>
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
                          {item.isManual ? (
                            priceEditIdx === idx ? (
                              <input
                                type="number"
                                step="0.05"
                                min="0"
                                autoFocus
                                defaultValue={item.price.toFixed(2)}
                                onBlur={(e) => { updatePrice(idx, parseFloat(e.target.value) || 0); setPriceEditIdx(null); }}
                                onKeyDown={(e) => { if (e.key === 'Enter') { updatePrice(idx, parseFloat((e.target as HTMLInputElement).value) || 0); setPriceEditIdx(null); } }}
                                className="w-16 text-xs px-1.5 py-0.5 rounded border border-vz-teal focus:outline-none focus:ring-1 focus:ring-vz-teal"
                              />
                            ) : (
                              <button
                                onClick={() => setPriceEditIdx(idx)}
                                title="Modifier le prix"
                                className="text-xs px-1.5 py-0.5 rounded border border-dashed border-gray-300 text-gray-600 hover:border-vz-teal hover:text-vz-teal"
                              >
                                {formatCurrency(item.price)} ✎
                              </button>
                            )
                          ) : (
                            <span className="text-xs text-gray-500">{formatCurrency(item.price)}</span>
                          )}
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

          {/* Footer: Total + Pay button — la zone récap (loyalty, coupon,
              invoice form) peut grossir; on lui donne un ``max-h`` avec
              overflow interne pour que le bouton Encaisser reste *toujours*
              visible en bas du panneau (demande prio cashier). */}
          <div className="flex-shrink-0 border-t border-gray-200 bg-white px-4 pt-3 pb-3 flex flex-col max-h-[60%]">
            <div className="overflow-y-auto space-y-3 mb-3">
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
            </div>

            {/* Encaisser — pinned button, hors-flux scrollable, toujours visible */}
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
              className={`flex-shrink-0 w-full py-4 rounded-xl font-bold text-lg tracking-wide transition-colors flex items-center justify-center gap-3 ${
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
                ref={searchInputRef}
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
            {/* Quick action buttons — un bouton par sac configuré + manuel */}
            <div className="flex flex-wrap gap-2 mt-2">
              {bags.map((bag) => (
                <button
                  key={bag.label}
                  onClick={() => addBag(bag)}
                  title={`${bag.label} — prix modifiable au panier`}
                  className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-xs text-black transition-colors"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/></svg>
                  {bag.label} {formatCurrency(bag.price_eur)}
                </button>
              ))}
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
                    {/* Photo thumbnail — falls back to the silhouette icon
                        when the product has no photo on file. The cashier
                        can confirm visually before adding to the cart. */}
                    <div className="aspect-[4/3] bg-gradient-to-br from-vz-bg-alt to-vz-bg flex items-center justify-center relative overflow-hidden">
                      {product.photo_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={mediaUrl(product.photo_url)}
                          alt={product.name}
                          className="w-full h-full object-cover"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                        />
                      ) : (
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
                      )}
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
      {/* ── Compagnon caisse — modale ouverte depuis le ticket. */}
      <Modal
        open={showCompanionModal}
        onClose={() => setShowCompanionModal(false)}
        title="Compagnon caisse"
        actions={
          <Button onClick={() => setShowCompanionModal(false)}>Fermer</Button>
        }
      >
        {selectedClient ? (
          <ClientCompanion
            clientId={selectedClient.id}
            cartTotalCents={Math.round(cartTotal * 100)}
            cartProductIds={cart
              .map((item) => item.product_id)
              .filter((id): id is string => Boolean(id))}
            onAddSuggestion={(pid) => {
              addPickToCart(pid);
              setShowCompanionModal(false);
            }}
            onApplyCoupon={(code) => {
              setCouponCode(code);
              setShowCompanionModal(false);
            }}
          />
        ) : (
          <p className="text-sm text-vz-ink-mute">
            Identifiez d&apos;abord une cliente.
          </p>
        )}
      </Modal>

      {/* ── Zone Événementiel — bons cadeau d'ouverture ──────────────
           Un bouton par type de bon (catalogue). Sur clic → le bon est
           crédité sur la fiche de la cliente identifiée ; affiché ensuite à
           l'identification + affectable comme moyen de paiement. */}
      <Modal
        open={showEventModal}
        onClose={() => {
          setShowEventModal(false);
          setEventSelected([]);
        }}
        title="Bons cadeau d'ouverture"
        actions={
          <div className="flex items-center gap-2 w-full justify-end">
            <Button
              variant="outline"
              onClick={() => {
                setShowEventModal(false);
                setEventSelected([]);
              }}
              disabled={eventBusy}
            >
              Annuler
            </Button>
            <Button
              onClick={issueSelectedVouchers}
              disabled={
                !selectedClient || eventBusy || eventSelected.length === 0
              }
            >
              {eventBusy
                ? '...'
                : `Valider${eventSelected.length > 0 ? ` (${eventSelected.length})` : ''}`}
            </Button>
          </div>
        }
      >
        {selectedClient ? (
          <p className="text-xs text-vz-ink-mute mb-4">
            Sur le compte de{' '}
            <strong>{selectedClient.first_name} {selectedClient.last_name}</strong>
            {clientVouchers.length > 0 ? ` · ${clientVouchers.length} bon(s) déjà crédité(s)` : ''}.
            Cochez les bons à créditer puis cliquez sur Valider.
          </p>
        ) : (
          <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2 mb-4">
            Sélectionnez d&apos;abord une cliente (ou créez sa fiche) pour lui attribuer un bon.
          </p>
        )}
        <div className="grid grid-cols-2 gap-2">
          {voucherCatalog
            .filter((v) => v.active !== false)
            .map((v) => {
              const checked = eventSelected.includes(v.key);
              return (
                <button
                  key={v.key}
                  type="button"
                  onClick={() => toggleEventSelected(v.key)}
                  disabled={!selectedClient || eventBusy}
                  className={`flex flex-col items-center justify-center gap-1 p-4 rounded-xl border-2 transition-all min-h-[84px] text-vz-ink disabled:opacity-40 disabled:cursor-not-allowed ${
                    checked
                      ? 'border-vz-teal bg-vz-teal-soft shadow-md'
                      : 'border-vz-line bg-vz-bg-alt hover:border-vz-teal hover:bg-white hover:shadow-md'
                  }`}
                >
                  <span className="font-display text-xl text-vz-teal">{v.label}</span>
                  <span className="text-[10px] text-vz-ink-mute">
                    {v.immediate
                      ? 'applicable immédiatement'
                      : 'utilisable au prochain achat'}
                  </span>
                  {checked && (
                    <span className="text-[10px] text-vz-teal-deep font-semibold">✓ sélectionné</span>
                  )}
                </button>
              );
            })}
        </div>
        {eventToast && (
          <p className="mt-4 text-sm text-vz-teal-deep bg-vz-teal-soft rounded-lg px-3 py-2">
            {eventToast}
          </p>
        )}
      </Modal>

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

                  {/* Monnaie à rendre / montant reçu insuffisant */}
                  {cashLine && cashShort && (
                    <div className="mt-2 flex items-center justify-between p-3 bg-red-50 rounded-xl border border-red-200">
                      <span className="text-sm font-semibold text-red-800">Montant reçu insuffisant</span>
                      <span className="font-mono text-lg font-bold text-red-700">
                        Manque {formatCurrency(cashLine.amount - (parseFloat(cashGiven) || 0))}
                      </span>
                    </div>
                  )}
                  {numpadTarget?.type === 'cash' && parseFloat(cashGiven) > 0 && payments[numpadTarget.index] && !cashShort && (
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
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-vz-teal">
                      <rect x="2" y="6" width="20" height="12" rx="2"/>
                      <circle cx="12" cy="12" r="2.5"/>
                      <path d="M6 12h.01M18 12h.01"/>
                    </svg>
                    <span className="text-sm font-semibold">Espèces</span>
                  </button>
                  <button
                    onClick={() => addPayment('carte')}
                    disabled={cbStatus === 'pending' || cbStatus === 'paid'}
                    className="flex flex-col items-center justify-center gap-2 p-4 bg-vz-bg-alt rounded-xl border border-vz-line hover:border-vz-teal hover:bg-white hover:shadow-md active:scale-95 transition-all min-h-[88px] text-vz-ink disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-vz-teal">
                      <rect x="2" y="5" width="20" height="14" rx="2"/>
                      <line x1="2" y1="10" x2="22" y2="10"/>
                      <line x1="6" y1="15" x2="10" y2="15"/>
                    </svg>
                    <span className="text-sm font-semibold">Carte CB</span>
                  </button>
                  <button
                    onClick={() => addPayment('cheque_cdc')}
                    title="Chèque cadeau Le Club des Commerçants"
                    className="flex flex-col items-center justify-center gap-2 p-4 bg-vz-bg-alt rounded-xl border border-vz-line hover:border-vz-teal hover:bg-white hover:shadow-md active:scale-95 transition-all min-h-[88px] text-vz-ink"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src="/payment/cdc-logo.svg" alt="" aria-hidden="true" className="h-7 w-7 object-contain" />
                    <span className="text-sm font-semibold">Chèque CDC</span>
                  </button>
                  <button
                    onClick={() => addPayment('avoir')}
                    disabled={!((selectedClient?.avoir_balance || 0) > 0) || payments.some(p => p.method === 'avoir')}
                    title={selectedClient?.avoir_balance ? `Solde avoir : ${formatCurrency(selectedClient.avoir_balance)}` : 'Pas d\'avoir disponible'}
                    className="flex flex-col items-center justify-center gap-2 p-4 bg-vz-bg-alt rounded-xl border border-vz-line hover:border-vz-accent hover:bg-white hover:shadow-md active:scale-95 transition-all min-h-[88px] text-vz-ink disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-vz-accent">
                      <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/>
                      <path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/>
                      <path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/>
                    </svg>
                    <span className="text-sm font-semibold">
                      Avoir{selectedClient?.avoir_balance ? ` (${formatCurrency(selectedClient.avoir_balance)})` : ''}
                    </span>
                  </button>
                </div>
              </section>

              {/* Bons cadeau de la cliente — affecter comme moyen de paiement */}
              {selectedClient && clientVouchers.length > 0 && (
                <section>
                  <h2 className="font-display text-base text-vz-ink mb-2">Bons cadeau</h2>
                  <div className="space-y-2">
                    {clientVouchers.map((v) => {
                      const used = payments.some((p) => p.voucher_code === v.code);
                      // Bon d'ouverture émis aujourd'hui : utilisable
                      // seulement à partir de demain.
                      const blockedSameDay = v.available_today === false;
                      const disabled = used || blockedSameDay;
                      return (
                        <div
                          key={v.code}
                          className={`flex items-center justify-between gap-2 p-3 rounded-xl border ${
                            blockedSameDay
                              ? 'border-amber-300 bg-amber-50'
                              : 'border-vz-accent/40 bg-vz-accent-soft'
                          }`}
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-vz-ink truncate">🎟 {v.label}</p>
                            <p className="text-[11px] text-vz-ink-mute font-mono truncate">
                              {v.code}
                              {v.valid_until ? ` · exp. ${new Date(v.valid_until).toLocaleDateString('fr-FR')}` : ''}
                            </p>
                            {blockedSameDay && (
                              <p className="text-[11px] text-amber-700 font-medium mt-0.5">
                                ⏳ Utilisable dès demain (jour d&apos;émission)
                              </p>
                            )}
                          </div>
                          <button
                            onClick={() => addVoucherPayment(v)}
                            disabled={disabled}
                            title={
                              blockedSameDay
                                ? "Ce bon ne peut pas être utilisé le jour de son émission."
                                : undefined
                            }
                            className="px-3 py-2 rounded-lg bg-vz-teal text-white text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-vz-teal-deep transition-colors whitespace-nowrap"
                          >
                            {used
                              ? 'Affecté ✓'
                              : blockedSameDay
                                ? 'Indisponible'
                                : v.value_for_cart > 0
                                  ? `Affecter ${formatCurrency(v.value_for_cart)}`
                                  : v.requires_item
                                    ? `+ ${v.free_item_label || 'article'}`
                                    : 'Affecter'}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

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
              disabled={remaining > 0.01 || cashShort || submitting}
              onClick={handleValidate}
              className={`flex-1 py-3 rounded-xl text-lg font-bold transition-colors min-h-[52px] flex items-center justify-center gap-3 ${
                remaining > 0.01 || cashShort || submitting
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
          // Disable the card tile when SumUp is unconfigured or the Solo
          // pinged offline — otherwise the cashier waits through the polling
          // banner only to see it fail.
          cardDisabled={!!sumupStatus && (!sumupStatus.configured || !sumupStatus.ready)}
          cardDisabledReason={
            sumupStatus && !sumupStatus.configured
              ? 'SumUp non configuré'
              : 'TPE hors ligne'
          }
          onCardCheckout={async (amount, onStatus) => {
            const outcome = await posPayment.runCardCheckout(amount, onStatus);
            if (outcome.status === 'paid' && outcome.sumup) {
              setCbDetails(outcome.sumup);
            }
            // Ticket CB : on récupère le retour Solo et on édite la copie
            // commerçant automatiquement (succès OU échec), puis on propose
            // la copie client. Les abandons/annulations cashier ne génèrent
            // pas de ticket CB (rien ne s'est passé sur le TPE).
            if (outcome.status === 'paid' || outcome.status === 'failed' || outcome.status === 'timeout') {
              const cbData = {
                amount,
                status: outcome.status,
                card_brand: outcome.sumup?.sumup_card_brand ?? null,
                card_last4: outcome.sumup?.sumup_card_last4 ?? null,
                auth_code: outcome.sumup?.sumup_auth_code ?? null,
                transaction_code: outcome.sumup?.sumup_transaction_code ?? null,
                transaction_id: outcome.sumup?.sumup_transaction_id ?? null,
                declined_reason: outcome.detail ?? null,
              };
              void (async () => {
                const { printCbTicket } = await import('@/lib/print-ticket');
                const r = await printCbTicket(cbData, 'merchant');
                setDrawerToast({
                  msg: r.ok ? 'Ticket CB commerçant imprimé' : `Ticket CB : ${r.message}`,
                  ok: r.ok,
                });
                setTimeout(() => setDrawerToast(null), 3500);
              })();
              setCbClientPrompt(cbData);
            }
            return outcome;
          }}
          onCommit={async (tenders) => {
            // Map wizard tenders (cash | card | cheque | avoir) to the legacy
            // ``payments`` shape (especes | carte | cheque | avoir).
            const methodMap: Record<string, string> = {
              cash: 'especes',
              card: 'carte',
              cheque: 'cheque',
              cheque_cdc: 'cheque_cdc',
              avoir: 'avoir',
            };
            const mapped: PaymentLine[] = tenders.map((t) => ({
              method: (methodMap[t.method] || t.method) as PaymentLine['method'],
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
            onResend={resendReceipt}
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

      {/* ── Receipt Modal (legacy non-wizard flow) ─────────────── */}
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
          </div>
        }
      >
        <div className="bg-gray-50 p-4 rounded-lg">
          <pre className="whitespace-pre-wrap text-sm font-mono text-black">{receiptText}</pre>
        </div>
        {printMsg && (
          <p className="mt-3 text-sm text-vz-teal">{printMsg}</p>
        )}
        {/* Email / SMS ad-hoc — walk-in customers without a CRM record
            can still get their receipt by typing the destination here. */}
        {receiptTxId && (
          <InlineResendButtons
            clientEmail={selectedClient?.email ?? null}
            clientPhone={selectedClient?.phone ?? null}
            onResend={resendReceipt}
          />
        )}
      </Modal>

      {/* ── Open Drawer (legacy fullscreen, Odoo 17 style) ────── */}
      {!wizardEnabled && showDrawerOpen && (
        <div className="fixed inset-0 z-[58] bg-vz-bg flex flex-col">
          <header className="flex-shrink-0 h-14 bg-vz-teal-deep text-white flex items-center px-3 gap-3 shadow-lg">
            <button
              onClick={() => setShowDrawerOpen(false)}
              disabled={drawerSubmitting}
              className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors min-h-[44px] disabled:opacity-50"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              <span className="text-sm font-medium">Annuler</span>
            </button>
            <div className="h-7 w-px bg-white/15" />
            <h1 className="font-display text-lg">Ouverture de caisse</h1>
            <div className="flex-1" />
            <div className="flex flex-col items-end leading-tight">
              <span className="text-[10px] opacity-70 uppercase tracking-wider">Fond de caisse</span>
              <span className="font-display text-2xl font-bold font-mono">{formatCurrency(drawerAmount)}</span>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto bg-vz-bg p-5 md:p-8">
            <div className="max-w-md mx-auto space-y-5">
              <p className="text-sm text-vz-ink-soft text-center">
                Saisissez le fonds de caisse initial (monnaie disponible).
              </p>
              <NumPad value={drawerAmount} onChange={setDrawerAmount} presets={[50, 100, 150, 200]} />
            </div>
          </div>

          <footer className="flex-shrink-0 bg-white border-t border-vz-line px-4 md:px-6 py-3 flex items-center gap-3 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
            <button
              onClick={() => setShowDrawerOpen(false)}
              disabled={drawerSubmitting}
              className="px-5 py-3 rounded-xl text-sm font-medium text-vz-ink-soft bg-vz-bg-alt hover:bg-vz-line transition-colors min-h-[52px] disabled:opacity-50"
            >
              Annuler
            </button>
            <button
              onClick={handleOpenDrawer}
              disabled={drawerSubmitting || drawerAmount <= 0}
              className={`flex-1 py-3 rounded-xl text-lg font-bold transition-colors min-h-[52px] flex items-center justify-center gap-3 ${
                drawerSubmitting || drawerAmount <= 0
                  ? 'bg-vz-line text-vz-ink-mute cursor-not-allowed'
                  : 'bg-vz-teal text-white hover:bg-vz-teal-deep shadow-lg'
              }`}
            >
              {drawerSubmitting ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Ouverture…
                </>
              ) : (
                <>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="10" width="18" height="10" rx="1" />
                    <path d="M3 10V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4" />
                    <line x1="10" y1="15" x2="14" y2="15" />
                  </svg>
                  Ouvrir la caisse — {formatCurrency(drawerAmount)}
                </>
              )}
            </button>
          </footer>
        </div>
      )}

      {/* ── Close Drawer (legacy fullscreen, Odoo 17 style) ───── */}
      {!wizardEnabled && showDrawerClose && (
        <div className="fixed inset-0 z-[58] bg-vz-bg flex flex-col">
          <header className="flex-shrink-0 h-14 bg-vz-teal-deep text-white flex items-center px-3 gap-3 shadow-lg">
            <button
              onClick={() => setShowDrawerClose(false)}
              disabled={drawerSubmitting}
              className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors min-h-[44px] disabled:opacity-50"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              <span className="text-sm font-medium">Annuler</span>
            </button>
            <div className="h-7 w-px bg-white/15" />
            <h1 className="font-display text-lg">Clôture de caisse</h1>
            <div className="flex-1" />
            <div className="flex flex-col items-end leading-tight">
              <span className="text-[10px] opacity-70 uppercase tracking-wider">Compté</span>
              <span className="font-display text-2xl font-bold font-mono">{formatCurrency(drawerAmount)}</span>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto bg-vz-bg p-5 md:p-8">
            <div className="max-w-md mx-auto space-y-5">
              <p className="text-sm text-vz-ink-soft text-center">
                Comptez les espèces en caisse et saisissez le total compté.
                Le rapport Z (NF525) sera généré à la validation.
              </p>
              <NumPad value={drawerAmount} onChange={setDrawerAmount} presets={[]} />
              {drawer?.opening_amount != null && (
                <div className="p-3 bg-vz-bg-alt rounded-xl flex items-center justify-between">
                  <span className="text-xs uppercase tracking-wider text-vz-ink-mute">Fond ouverture</span>
                  <span className="font-mono text-base font-semibold text-vz-ink tabular-nums">
                    {formatCurrency(drawer.opening_amount)}
                  </span>
                </div>
              )}
            </div>
          </div>

          <footer className="flex-shrink-0 bg-white border-t border-vz-line px-4 md:px-6 py-3 flex items-center gap-3 shadow-[0_-2px_8px_rgba(0,0,0,0.04)]">
            <button
              onClick={() => setShowDrawerClose(false)}
              disabled={drawerSubmitting}
              className="px-5 py-3 rounded-xl text-sm font-medium text-vz-ink-soft bg-vz-bg-alt hover:bg-vz-line transition-colors min-h-[52px] disabled:opacity-50"
            >
              Annuler
            </button>
            <button
              onClick={handleCloseDrawer}
              disabled={drawerSubmitting || drawerAmount <= 0}
              className={`flex-1 py-3 rounded-xl text-lg font-bold transition-colors min-h-[52px] flex items-center justify-center gap-3 ${
                drawerSubmitting || drawerAmount <= 0
                  ? 'bg-vz-line text-vz-ink-mute cursor-not-allowed'
                  : 'bg-vz-teal text-white hover:bg-vz-teal-deep shadow-lg'
              }`}
            >
              {drawerSubmitting ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Clôture…
                </>
              ) : (
                <>
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  Générer le rapport Z — {formatCurrency(drawerAmount)}
                </>
              )}
            </button>
          </footer>
        </div>
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
                // Avant : on retournait undefined sans rien dire au
                // manager → bouton « Clôturer » qui semble bloqué. On
                // remonte maintenant l'erreur via le toast global + on
                // throw pour que le wizard ré-affiche la phase Décompte.
                const err = await res.json().catch(() => null);
                const detail = err?.detail || err?.message || `HTTP ${res.status}`;
                setDrawerToast({ msg: `Clôture refusée : ${detail}`, ok: false });
                setTimeout(() => setDrawerToast(null), 6000);
                throw new Error(String(detail));
              } catch (e) {
                if (!(e instanceof Error)) {
                  setDrawerToast({ msg: 'Clôture impossible (réseau)', ok: false });
                  setTimeout(() => setDrawerToast(null), 6000);
                }
                throw e;
              } finally {
                setDrawerSubmitting(false);
              }
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
          /* Wrapped in a <form> so:
             - Tab navigation respects HTML tabIndex order (prénom → nom →
               email → code postal → CGU → newsletter → profilage → Valider)
             - The Enter key submits the form (saisie clavier rapide)
             - Le bouton Annuler porte ``type="button"`` pour ne pas valider
               par erreur. */
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              if (
                !subscribeBusy &&
                subscribeForm.first_name &&
                subscribeForm.last_name &&
                subscribeForm.email &&
                subscribeForm.accept_terms
              ) {
                void submitSubscription();
              }
            }}
          >
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Prenom</label>
                <Input
                  autoFocus
                  tabIndex={1}
                  autoComplete="given-name"
                  value={subscribeForm.first_name}
                  onChange={(e) => setSubscribeForm({ ...subscribeForm, first_name: e.target.value })}
                  placeholder="Alice"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nom</label>
                <Input
                  tabIndex={2}
                  autoComplete="family-name"
                  value={subscribeForm.last_name}
                  onChange={(e) => setSubscribeForm({ ...subscribeForm, last_name: e.target.value })}
                  placeholder="Martin"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Email</label>
              <Input
                tabIndex={3}
                type="email"
                autoComplete="email"
                value={subscribeForm.email}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, email: e.target.value })}
                placeholder="alice@email.fr"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Code postal</label>
              <Input
                tabIndex={4}
                autoComplete="postal-code"
                value={subscribeForm.postal_code}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, postal_code: e.target.value })}
                placeholder="27200"
              />
            </div>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                tabIndex={5}
                className="mt-1"
                checked={subscribeForm.accept_terms}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, accept_terms: e.target.checked })}
              />
              <span>J&apos;accepte les conditions du programme fidelite Vintiz (1 € = 1 pt, peremption 24 mois).</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                tabIndex={6}
                className="mt-1"
                checked={subscribeForm.optin_newsletter}
                onChange={(e) => setSubscribeForm({ ...subscribeForm, optin_newsletter: e.target.checked })}
              />
              <span>J&apos;accepte de recevoir la newsletter Vintiz.</span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                tabIndex={7}
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
              <Button
                variant="outline"
                type="button"
                onClick={closeSubscribeModal}
                className="flex-1"
                tabIndex={9}
              >
                Annuler
              </Button>
              <Button
                type="submit"
                tabIndex={8}
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
          </form>
        )}
      </Modal>

      {drawerToast && (
        <div
          role="status"
          aria-live="assertive"
          className={`fixed top-6 left-1/2 -translate-x-1/2 z-[9999] px-5 py-3.5 rounded-2xl shadow-2xl text-base font-semibold max-w-xl min-w-[280px] text-center flex items-center justify-center gap-2 border-2 ${
            drawerToast.ok
              ? 'bg-green-600 text-white border-green-400'
              : 'bg-red-600 text-white border-red-400'
          }`}
          onClick={() => setDrawerToast(null)}
        >
          <span aria-hidden>{drawerToast.ok ? '✓' : '⚠'}</span>
          <span>{drawerToast.msg}</span>
        </div>
      )}

      {/* Ticket CB — copie client proposée après la copie commerçant auto. */}
      {cbClientPrompt && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl">
            <h3 className="font-display text-lg font-semibold text-vz-ink">
              Ticket carte bancaire
            </h3>
            <p className="mt-1 text-sm text-vz-ink-soft">
              {cbClientPrompt.status === 'paid'
                ? 'Paiement CB accepté.'
                : 'Transaction CB refusée.'}{' '}
              La copie commerçant a été imprimée automatiquement. Imprimer la
              copie client ?
            </p>
            <div className="mt-5 flex flex-col gap-2">
              <Button
                disabled={cbTicketBusy}
                onClick={async () => {
                  setCbTicketBusy(true);
                  const { printCbTicket } = await import('@/lib/print-ticket');
                  const r = await printCbTicket(cbClientPrompt, 'client');
                  setDrawerToast({
                    msg: r.ok ? 'Ticket CB client imprimé' : `Ticket CB : ${r.message}`,
                    ok: r.ok,
                  });
                  setTimeout(() => setDrawerToast(null), 3500);
                  setCbTicketBusy(false);
                  setCbClientPrompt(null);
                }}
              >
                {cbTicketBusy ? 'Impression…' : 'Imprimer le ticket client'}
              </Button>
              <Button
                variant="outline"
                disabled={cbTicketBusy}
                onClick={() => setCbClientPrompt(null)}
              >
                Pas de ticket client
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
