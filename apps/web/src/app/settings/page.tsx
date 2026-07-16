'use client';

import React, { useState, useEffect } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Modal from '@/components/ui/Modal';
import CashManagementSettingsPanel from '@/components/settings/CashManagementSettingsPanel';
import FeaturesPanel from '@/components/settings/FeaturesPanel';
import PosQuickAddPanel from '@/components/settings/PosQuickAddPanel';
import MessageTemplatesPanel from '@/components/settings/MessageTemplatesPanel';
import ReceiptInvoiceStudio from '@/components/settings/ReceiptInvoiceStudio';
import ScoringWeightsPanel from '@/components/settings/ScoringWeightsPanel';
import SumUpTerminalsPanel from '@/components/settings/SumUpTerminalsPanel';
import SumUpExchangeLogPanel from '@/components/settings/SumUpExchangeLogPanel';
import { api } from '@/lib/api';

interface Category {
  id: string;
  name: string;
  gender: string;
  is_active: boolean;
}

interface Zone {
  zone_id: string;
  zone_name: string;
  description: string;
  capacity: number;
  product_count: number;
  occupancy_percent: number;
  product_types?: string[];
  color_code?: string;
}

interface HardwareConfig {
  receipt_printer: {
    enabled: boolean;
    model: string;
    host: string;
    port: number;
    width_chars: number;
    cut_paper: boolean;
    connection?: 'network' | 'usb';
    usb_vendor_id?: number | null;
    usb_product_id?: number | null;
    usb_serial_number?: string | null;
    usb_product_label?: string | null;
  };
  cash_drawer: { enabled: boolean; model: string; kick_on_cash: boolean; kick_pin: number; on_time_ms: number; off_time_ms: number };
  label_printer: {
    enabled: boolean; model: string; host: string; port: number;
    label_width_mm: number; label_height_mm: number;
    /** Clé du profil sélectionné (25x52_double | 40x60_single). */
    label_profile?: string;
    connection?: 'network' | 'cloud' | 'bluetooth';
    cloud_api_key?: string;
    cloud_tenant?: string;
    cloud_serial?: string;
    cloud_endpoint?: string;
    cloud_api_key_set?: boolean;
    cloud_api_key_hint?: string;
    bt_device_name?: string;
  };
  barcode_scanner: { enabled: boolean; model: string; mode: string; suffix: string; min_length: number };
  payment_terminal: { enabled: boolean; model: string; mode: string };
}

interface CompatibilityItem {
  category: string;
  label: string;
  model: string;
  connection: string;
  supported: boolean;
  notes: string;
}

export default function SettingsPage() {
  const [tab, setTab] = useState<'store' | 'caisse' | 'tickets' | 'communication' | 'templates' | 'cahier' | 'fidelite' | 'categories' | 'zones' | 'hardware' | 'scoring' | 'system'>('store');
  const [hardware, setHardware] = useState<HardwareConfig | null>(null);
  const [compatibility, setCompatibility] = useState<CompatibilityItem[]>([]);
  const [labelProfiles, setLabelProfiles] = useState<{
    key: string; name: string; label_width_mm: number; label_height_mm: number; ticket_count: number;
  }[]>([]);
  const [hwSaving, setHwSaving] = useState(false);

  // Cahier de Travail state
  const now = new Date();
  const [cahierYear, setCahierYear] = useState(now.getFullYear());
  const [cahierMonth, setCahierMonth] = useState(now.getMonth() + 1);
  const [cahierTarget, setCahierTarget] = useState('');
  const [cahierNotes, setCahierNotes] = useState('');
  const [cahierWeights, setCahierWeights] = useState<{
    weights: number[];
    weekdays: string[];
    source: string;
    sample_size_weeks: number;
    computed_at: string;
  } | null>(null);
  const [cahierLoading, setCahierLoading] = useState(false);
  // Annual grid: 12 mois remplissables + simulation d'augmentation
  // (en €/mois ou en %). Le tableau remplace le picker mois-par-mois :
  // on voit l'année d'un coup et on propage une variation sur tous les
  // mois en 1 clic.
  const [yearGridTargets, setYearGridTargets] = useState<string[]>(
    Array(12).fill(''),
  );
  const [yearGridSaving, setYearGridSaving] = useState(false);
  const [increaseValue, setIncreaseValue] = useState('');
  const [increaseUnit, setIncreaseUnit] = useState<'eur' | 'pct'>('pct');
  const [categories, setCategories] = useState<Category[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  // New category form
  const [newCatName, setNewCatName] = useState('');
  const [newCatGender, setNewCatGender] = useState('femme');
  // Feedback shown INLINE inside the categories tab, right by the form — the
  // global banner sits at the top of the page, off-screen when the manager is
  // scrolled down to the form, which read as "il ne se passe rien".
  const [catFeedback, setCatFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  // Inline category edit
  const [editingCatId, setEditingCatId] = useState<string | null>(null);
  const [editCatName, setEditCatName] = useState('');
  const [editCatGender, setEditCatGender] = useState('femme');

  // Zone edit modal
  const [showZoneModal, setShowZoneModal] = useState(false);
  const [editingZone, setEditingZone] = useState<Zone | null>(null);
  const [zoneForm, setZoneForm] = useState({ name: '', description: '', capacity: 20, product_types: [] as string[], color_code: '#1A7A6A' });

  // Loyalty subscription config (PR1)
  const [loyaltyMode, setLoyaltyMode] = useState<'free' | 'paid' | 'first_purchase'>('free');
  const [loyaltyPriceEuros, setLoyaltyPriceEuros] = useState('5');
  const [loyaltyThresholdEuros, setLoyaltyThresholdEuros] = useState('30');
  const [loyaltySaving, setLoyaltySaving] = useState(false);
  const [loyaltyWindowEnabled, setLoyaltyWindowEnabled] = useState(false);
  const [loyaltyWindowStart, setLoyaltyWindowStart] = useState('');
  const [loyaltyWindowEnd, setLoyaltyWindowEnd] = useState('');

  // Shop info (editable boutique metadata)
  const [shopInfo, setShopInfo] = useState<{
    name: string; tagline: string;
    address_line1: string; address_line2: string; postal_code: string; city: string; country: string;
    phone: string; email: string; website: string;
    hours: string; surface_m2: number; vat_rate_percent: number;
    siret: string; rcs: string; ape: string;
    legal_form: string; capital_social: string; tva_intracom: string;
    iban: string; bic: string;
  } | null>(null);
  const [shopSaving, setShopSaving] = useState(false);

  // Hardware compatibility test status (per category)
  type HwTestStatus = 'idle' | 'running' | 'success' | 'error';
  const [hwTests, setHwTests] = useState<Record<string, { status: HwTestStatus; message?: string }>>({});

  // Email gateway config (Communication tab)
  const [emailForm, setEmailForm] = useState<{
    provider: string; brevo_api_key: string;
    smtp_host: string; smtp_port: string; smtp_user: string; smtp_password: string; smtp_from: string;
    from_address: string; from_name: string;
  }>({
    provider: '', brevo_api_key: '',
    smtp_host: '', smtp_port: '587', smtp_user: '', smtp_password: '', smtp_from: '',
    from_address: 'noreply@vintiz.fr', from_name: 'Vintiz Vernon',
  });
  const [emailPersisted, setEmailPersisted] = useState<{
    provider: string; brevo_api_key_masked: string;
    smtp_host: string; smtp_port: string; smtp_user: string; smtp_password_masked: string;
    smtp_from: string; from_address: string; from_name: string;
  } | null>(null);
  const [emailLive, setEmailLive] = useState<{ provider: string; configured: boolean; host?: string; port?: string } | null>(null);
  const [emailSaving, setEmailSaving] = useState(false);
  const [emailTestTo, setEmailTestTo] = useState('');
  const [emailTestResult, setEmailTestResult] = useState<{ ok: boolean; status: string; backend: string; detail?: string } | null>(null);
  const [emailTesting, setEmailTesting] = useState(false);

  // SMS gateway — partage la même BREVO_API_KEY que l'email, donc pas de
  // formulaire dédié. Juste un statut « live » + un envoi de test pour
  // diagnostiquer un Brevo qui rejette (sender non enregistré, crédit
  // épuisé, compte sous validation…).
  const [smsLive, setSmsLive] = useState<{ provider: string; configured: boolean; from?: string } | null>(null);
  const [smsAccount, setSmsAccount] = useState<{
    ok: boolean; error?: string; account_email?: string; company?: string;
    sms_credits?: number | null; email_plan_type?: string | null;
    can_send_transactional_sms?: boolean; plan_types?: string[];
  } | null>(null);
  const [smsTestTo, setSmsTestTo] = useState('');
  const [smsTestResult, setSmsTestResult] = useState<{
    ok: boolean; status: string; backend: string; detail?: string; simulated?: boolean;
  } | null>(null);
  const [smsTesting, setSmsTesting] = useState(false);

  useEffect(() => {
    if (tab === 'store') loadShopInfo();
    if (tab === 'communication') {
      loadEmailConfig();
      loadSmsConfig();
    }
    if (tab === 'categories') loadCategories();
    if (tab === 'zones') { loadZones(); loadCategories(); }
    if (tab === 'hardware') loadHardware();
    if (tab === 'cahier') loadCahierData();
    if (tab === 'fidelite') loadLoyaltyConfig();
  }, [tab]);

  const loadShopInfo = async () => {
    try {
      const res = await api.get('/api/admin/shop-info');
      if (res.ok) setShopInfo(await res.json());
    } catch {
      setError('Erreur de chargement de la boutique');
    }
  };

  const saveShopInfo = async () => {
    if (!shopInfo) return;
    setShopSaving(true);
    setError('');
    try {
      const res = await api.put('/api/admin/shop-info', shopInfo);
      if (res.ok) {
        setShopInfo(await res.json());
        setMessage('Informations boutique enregistrées');
        setTimeout(() => setMessage(''), 3000);
      } else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Erreur enregistrement boutique');
      }
    } catch { setError('Erreur de connexion'); }
    setShopSaving(false);
  };

  // ── SMS gateway config (Brevo, partage BREVO_API_KEY avec l'email) ──────
  const loadSmsConfig = async () => {
    try {
      const res = await api.get('/api/admin/sms-config');
      if (res.ok) {
        const data = await res.json();
        setSmsLive(data.live);
        setSmsAccount(data.account ?? null);
      }
    } catch { /* silent — état affiché en « inconnu » */ }
  };

  const sendSmsTest = async () => {
    setSmsTesting(true);
    setSmsTestResult(null);
    try {
      const res = await api.post('/api/admin/sms-config/test', {
        to: smsTestTo.trim(),
      });
      const data = await res.json();
      setSmsTestResult({
        ok: !!data.ok,
        status: data.status || 'unknown',
        backend: data.backend || 'unknown',
        detail: data.detail,
        simulated: !!data.simulated,
      });
    } catch (e: any) {
      setSmsTestResult({ ok: false, status: 'failed', backend: 'error', detail: e?.message || 'Erreur réseau' });
    }
    setSmsTesting(false);
  };

  // ── Email gateway config ─────────────────────────────────────────────────
  const loadEmailConfig = async () => {
    try {
      const res = await api.get('/api/admin/email-config');
      if (res.ok) {
        const data = await res.json();
        setEmailLive(data.live);
        setEmailPersisted(data.persisted);
        setEmailForm({
          provider: data.persisted.provider || '',
          // Never echo back the secret — leave empty so user explicitly retypes to change
          brevo_api_key: '',
          smtp_host: data.persisted.smtp_host || '',
          smtp_port: data.persisted.smtp_port || '587',
          smtp_user: data.persisted.smtp_user || '',
          smtp_password: '',
          smtp_from: data.persisted.smtp_from || '',
          from_address: data.persisted.from_address || 'noreply@vintiz.fr',
          from_name: data.persisted.from_name || 'Vintiz Vernon',
        });
      }
    } catch {
      setError('Erreur de chargement de la passerelle email');
    }
  };

  const saveEmailConfig = async () => {
    setEmailSaving(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        provider: emailForm.provider,
        smtp_host: emailForm.smtp_host,
        smtp_port: emailForm.smtp_port,
        smtp_user: emailForm.smtp_user,
        smtp_from: emailForm.smtp_from,
        from_address: emailForm.from_address,
        from_name: emailForm.from_name,
      };
      if (emailForm.brevo_api_key.trim()) body.brevo_api_key = emailForm.brevo_api_key.trim();
      if (emailForm.smtp_password.trim()) body.smtp_password = emailForm.smtp_password.trim();
      const res = await api.put('/api/admin/email-config', body);
      if (res.ok) {
        const data = await res.json();
        setEmailLive(data.live);
        setEmailPersisted(data.persisted);
        setEmailForm((f) => ({ ...f, brevo_api_key: '', smtp_password: '' }));
        setMessage('Configuration email enregistrée');
        setTimeout(() => setMessage(''), 3000);
      } else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Erreur enregistrement email');
      }
    } catch { setError('Erreur de connexion'); }
    setEmailSaving(false);
  };

  const sendEmailTest = async () => {
    setEmailTesting(true);
    setEmailTestResult(null);
    try {
      const res = await api.post('/api/admin/email-config/test', {
        to: emailTestTo.trim() || undefined,
      });
      const data = await res.json();
      setEmailTestResult({
        ok: !!data.ok,
        status: data.status || 'unknown',
        backend: data.backend || 'unknown',
        detail: data.detail,
      });
    } catch (e: any) {
      setEmailTestResult({ ok: false, status: 'failed', backend: 'error', detail: e?.message || 'Erreur réseau' });
    }
    setEmailTesting(false);
  };

  // ── Hardware compatibility tests (inline per row) ─────────────────────────
  const runHwTest = async (category: string) => {
    setHwTests((s) => ({ ...s, [category]: { status: 'running' } }));
    try {
      if (category === 'payment_terminal') {
        // Mode prod uniquement : on ne crée pas de checkout test (cela
        // débiterait une vraie carte). On vérifie juste que l'API key
        // et le merchant code sont configurés.
        const cfg = await api.get('/api/pos/payments/cb/config');
        if (!cfg.ok) {
          setHwTests((s) => ({ ...s, [category]: { status: 'error', message: 'Impossible de lire la config SumUp' } }));
          return;
        }
        const data = await cfg.json();
        if (!data.api_key_set || !data.merchant_code_set) {
          setHwTests((s) => ({ ...s, [category]: { status: 'error', message: 'SumUp non configuré — clé API ou merchant code manquant.' } }));
        } else {
          const reader = data.reader_id_set ? `, reader ${data.reader_id_masked}` : '';
          setHwTests((s) => ({ ...s, [category]: { status: 'success', message: `SumUp prêt (${data.merchant_code_masked}${reader})` } }));
        }
        return;
      }
      if (category === 'cash_drawer') {
        // Route through the shared helper so USB mode works too.
        const { kickDrawer: kick } = await import('@/lib/print-ticket');
        const result = await kick();
        setHwTests((s) => ({
          ...s,
          [category]: result.ok
            ? { status: 'success', message: result.message }
            : { status: 'error', message: result.message },
        }));
        return;
      }
      if (category === 'barcode_scanner') {
        // No backend test — focus the search field at /pos
        setHwTests((s) => ({ ...s, [category]: { status: 'success', message: 'Allez sur /pos et scannez un produit pour valider la douchette' } }));
        return;
      }
      let endpoint = '';
      if (category === 'receipt_printer') endpoint = '/api/hardware/receipt/test';
      else if (category === 'label_printer') endpoint = '/api/hardware/label/test';
      const res = await api.post(endpoint, {});
      if (res.ok) {
        setHwTests((s) => ({ ...s, [category]: { status: 'success', message: 'Test envoyé ✓' } }));
      } else {
        const e = await res.json().catch(() => ({}));
        setHwTests((s) => ({ ...s, [category]: { status: 'error', message: e.detail || `HTTP ${res.status}` } }));
      }
    } catch (e: any) {
      setHwTests((s) => ({ ...s, [category]: { status: 'error', message: e?.message || 'Erreur réseau' } }));
    }
  };

  const loadLoyaltyConfig = async () => {
    try {
      const res = await api.get('/api/admin/loyalty/config');
      if (res.ok) {
        const data = await res.json();
        setLoyaltyMode((data.mode as typeof loyaltyMode) || 'free');
        setLoyaltyPriceEuros(((data.price_cents || 0) / 100).toFixed(2));
        setLoyaltyThresholdEuros(((data.first_purchase_threshold_cents || 0) / 100).toFixed(0));
        setLoyaltyWindowEnabled(Boolean(data.window_start) && Boolean(data.window_end));
        setLoyaltyWindowStart(data.window_start || '');
        setLoyaltyWindowEnd(data.window_end || '');
      }
    } catch {
      setError('Erreur de chargement de la configuration fidelite');
    }
  };

  const saveLoyaltyConfig = async () => {
    setLoyaltySaving(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        mode: loyaltyMode,
        price_cents: Math.round(parseFloat(loyaltyPriceEuros || '0') * 100),
        first_purchase_threshold_cents: Math.round(parseFloat(loyaltyThresholdEuros || '0') * 100),
        window_start: loyaltyWindowEnabled ? loyaltyWindowStart || null : null,
        window_end: loyaltyWindowEnabled ? loyaltyWindowEnd || null : null,
      };
      const res = await api.put('/api/admin/loyalty/config', body);
      if (res.ok) {
        setMessage('Configuration fidelite enregistree');
        setTimeout(() => setMessage(''), 3000);
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || 'Erreur enregistrement');
      }
    } catch {
      setError('Erreur reseau');
    }
    setLoyaltySaving(false);
  };

  const loadHardware = async () => {
    setLoading(true);
    try {
      const [cfgRes, compatRes, profilesRes] = await Promise.all([
        api.get('/api/hardware/config'),
        api.get('/api/hardware/compatibility'),
        api.get('/api/labels/profiles'),
      ]);
      if (cfgRes.ok) setHardware(await cfgRes.json());
      if (compatRes.ok) {
        const data = await compatRes.json();
        setCompatibility(data.items || []);
      }
      if (profilesRes.ok) {
        const data = await profilesRes.json();
        setLabelProfiles(data.profiles || []);
      }
    } catch {
      setError('Erreur de chargement du materiel');
    }
    setLoading(false);
  };

  const saveHardware = async () => {
    if (!hardware) return;
    setHwSaving(true);
    setError('');
    try {
      const res = await api.put('/api/hardware/config', hardware);
      if (res.ok) {
        setHardware(await res.json());
        setMessage('Configuration materiel sauvegardee');
        setTimeout(() => setMessage(''), 3000);
      } else {
        setError('Erreur lors de la sauvegarde');
      }
    } catch {
      setError('Erreur de connexion');
    }
    setHwSaving(false);
  };

  const testReceiptPrinter = async () => {
    setError(''); setMessage('');
    if (!hardware) return;
    const mode = hardware.receipt_printer.connection || 'network';
    if (mode === 'usb') {
      // USB path : récupère les bytes ESC/POS bruts depuis le backend
      // et les pousse à la MUNBYN via WebUSB (Chrome Android tablette).
      try {
        const { findPairedDevice, sendEscposBytes, isWebUsbSupported } =
          await import('@/lib/webusb-printer');
        if (!isWebUsbSupported()) {
          setError('WebUSB indisponible — utilisez Chrome Android sur HTTPS.');
          return;
        }
        const vendorId = hardware.receipt_printer.usb_vendor_id;
        const productId = hardware.receipt_printer.usb_product_id;
        if (!vendorId || !productId) {
          setError('Aucun périphérique USB couplé — cliquez d\'abord sur "Coupler le périphérique USB".');
          return;
        }
        const device = await findPairedDevice({
          vendorId, productId,
          serialNumber: hardware.receipt_printer.usb_serial_number,
        });
        if (!device) {
          setError('Périphérique USB introuvable — rebranchez la MUNBYN puis recouplez.');
          return;
        }
        const res = await api.get('/api/hardware/receipt/test-escpos');
        if (!res.ok) {
          const e = await res.json().catch(() => ({}));
          setError(e.detail || 'Impossible de générer le ticket de test');
          return;
        }
        const bytes = new Uint8Array(await res.arrayBuffer());
        await sendEscposBytes(device, bytes);
        setMessage('Ticket de test envoyé à la MUNBYN via USB');
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(`Échec USB : ${msg}`);
      }
      return;
    }
    // Network path (legacy / fixed station). Test the IP currently typed in
    // the form; the backend falls back to the persisted config when omitted.
    const host = hardware.receipt_printer.host?.trim();
    const port = hardware.receipt_printer.port || 9100;
    if (!host) {
      setError("Renseignez d'abord l'adresse IP de l'imprimante ticket.");
      return;
    }
    try {
      const res = await api.post('/api/hardware/receipt/test', { host, port });
      if (res.ok) setMessage(`Ticket de test envoyé à ${host}:${port}`);
      else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Échec du test imprimante');
      }
    } catch { setError('Erreur de connexion'); }
  };

  const pairUsbReceiptPrinter = async () => {
    setError(''); setMessage('');
    if (!hardware) return;
    try {
      const { requestMunbynDevice, isWebUsbSupported } = await import('@/lib/webusb-printer');
      if (!isWebUsbSupported()) {
        setError('WebUSB indisponible — utilisez Chrome Android sur HTTPS.');
        return;
      }
      const printer = await requestMunbynDevice();
      const next = {
        ...hardware,
        receipt_printer: {
          ...hardware.receipt_printer,
          connection: 'usb' as const,
          usb_vendor_id: printer.vendorId,
          usb_product_id: printer.productId,
          usb_serial_number: printer.serialNumber ?? null,
          usb_product_label: printer.productLabel,
        },
      };
      setHardware(next);
      // Persist immediately so a reload picks it up.
      await api.put('/api/hardware/config', { receipt_printer: next.receipt_printer });
      setMessage(`Périphérique couplé : ${printer.productLabel}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Échec du couplage USB : ${msg}`);
    }
  };

  const unpairUsbReceiptPrinter = async () => {
    if (!hardware) return;
    const next = {
      ...hardware,
      receipt_printer: {
        ...hardware.receipt_printer,
        usb_vendor_id: null,
        usb_product_id: null,
        usb_serial_number: null,
        usb_product_label: null,
      },
    };
    setHardware(next);
    await api.put('/api/hardware/config', { receipt_printer: next.receipt_printer });
    setMessage('Périphérique USB découplé');
  };

  const kickDrawer = async () => {
    setError(''); setMessage('');
    const { kickDrawer: kick } = await import('@/lib/print-ticket');
    const result = await kick();
    if (result.ok) setMessage(result.message);
    else setError(result.message);
  };

  const pairBluetoothPrinter = async () => {
    setError(''); setMessage('');
    if (!hardware) return;
    try {
      const { requestZebraDevice, isWebBluetoothSupported } = await import('@/lib/web-bluetooth-printer');
      if (!isWebBluetoothSupported()) {
        setError('Web Bluetooth indisponible — utilisez Chrome Android sur HTTPS.');
        return;
      }
      const { info } = await requestZebraDevice();
      const next = {
        ...hardware,
        label_printer: {
          ...hardware.label_printer,
          connection: 'bluetooth' as const,
          bt_device_name: info.name,
        },
      };
      setHardware(next);
      await api.put('/api/hardware/config', { label_printer: next.label_printer });
      setMessage(`Imprimante Bluetooth couplée : ${info.name}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Échec du couplage Bluetooth : ${msg}`);
    }
  };

  const testLabelPrinter = async () => {
    if (!hardware) return;
    setError(''); setMessage('');
    const conn = hardware.label_printer.connection || 'network';

    if (conn === 'bluetooth') {
      // BLE path: fetch the test ZPL and write it to the Zebra over Web
      // Bluetooth (Chrome Android tablet). The server can't reach a BLE
      // printer, so this never touches the network print endpoint.
      setHwTests((s) => ({ ...s, label_printer: { status: 'running' } }));
      try {
        const { isWebBluetoothSupported, findPairedZebra, requestZebraDevice, sendZpl } =
          await import('@/lib/web-bluetooth-printer');
        if (!isWebBluetoothSupported()) {
          setHwTests((s) => ({ ...s, label_printer: { status: 'error', message: 'Web Bluetooth indisponible — Chrome Android requis.' } }));
          return;
        }
        let device = await findPairedZebra({ name: hardware.label_printer.bt_device_name });
        if (!device) {
          const paired = await requestZebraDevice();
          device = paired.device;
        }
        const res = await api.get('/api/hardware/label/test-zpl');
        if (!res.ok) {
          const e = await res.json().catch(() => ({}));
          setHwTests((s) => ({ ...s, label_printer: { status: 'error', message: e.detail || 'ZPL de test indisponible' } }));
          return;
        }
        const zpl = await res.text();
        await sendZpl(device, zpl);
        setHwTests((s) => ({ ...s, label_printer: { status: 'success', message: 'Étiquette de test envoyée (Bluetooth)' } }));
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setHwTests((s) => ({ ...s, label_printer: { status: 'error', message: `Échec Bluetooth : ${msg}` } }));
      }
      return;
    }

    const isCloud = conn === 'cloud';
    const host = hardware.label_printer.host?.trim();
    const port = hardware.label_printer.port || 9100;
    if (!isCloud && !host) {
      setHwTests((s) => ({ ...s, label_printer: { status: 'error', message: "Renseignez d'abord l'adresse IP de l'imprimante." } }));
      return;
    }
    // Network mode tests the IP typed in the form (no save needed). Cloud
    // mode uses the persisted Zebra Data Services credentials, so save the
    // form first — the test endpoint reads the stored config in that mode.
    setHwTests((s) => ({ ...s, label_printer: { status: 'running' } }));
    try {
      const res = await api.post('/api/hardware/label/test', isCloud ? {} : { host, port });
      if (res.ok) {
        setHwTests((s) => ({ ...s, label_printer: { status: 'success', message: isCloud ? 'Étiquette de test envoyée via le cloud Zebra (Weblink)' : `Étiquette de test envoyée à ${host}:${port}` } }));
      } else {
        const e = await res.json().catch(() => ({}));
        setHwTests((s) => ({ ...s, label_printer: { status: 'error', message: e.detail || `Échec du test (HTTP ${res.status})` } }));
      }
    } catch {
      setHwTests((s) => ({ ...s, label_printer: { status: 'error', message: 'Erreur de connexion au serveur Vintiz' } }));
    }
  };

  // Success feedback near the category form, auto-cleared after 3s.
  const flashCatSuccess = (text: string) => {
    setCatFeedback({ type: 'success', text });
    setTimeout(() => setCatFeedback((f) => (f?.text === text ? null : f)), 3000);
  };

  const loadCategories = async () => {
    setLoading(true);
    // include_inactive so the management screen can show + re-enable disabled ones.
    // Cache-bust (&_=…) : sans ça, Safari (iPad) resservait la liste GET en
    // cache juste après un ajout → la catégorie n'apparaissait qu'après un F5.
    try {
      const res = await api.get(`/api/inventory/categories?include_inactive=true&_=${Date.now()}`);
      if (res.ok) setCategories(await res.json());
      else setCatFeedback({ type: 'error', text: 'Erreur lors du chargement des catégories' });
    } catch {
      setCatFeedback({ type: 'error', text: 'Erreur de connexion lors du chargement des catégories' });
    }
    setLoading(false);
  };

  const startEditCat = (c: Category) => {
    setEditingCatId(c.id);
    setEditCatName(c.name);
    setEditCatGender(c.gender);
  };

  const saveCat = async (id: string) => {
    if (!editCatName.trim()) { setCatFeedback({ type: 'error', text: 'Le nom de la catégorie est requis' }); return; }
    setCatFeedback(null);
    try {
      const res = await api.put(`/api/inventory/categories/${id}`, {
        name: editCatName.trim(),
        gender: editCatGender,
      });
      if (res.ok) {
        setEditingCatId(null);
        await loadCategories();
        flashCatSuccess('Catégorie modifiée');
      } else {
        const e = await res.json().catch(() => ({}));
        setCatFeedback({ type: 'error', text: e.detail || 'Erreur lors de la modification' });
      }
    } catch {
      setCatFeedback({ type: 'error', text: 'Erreur de connexion — la modification a échoué' });
    }
  };

  const toggleCatActive = async (c: Category) => {
    setCatFeedback(null);
    try {
      const res = await api.put(`/api/inventory/categories/${c.id}`, { is_active: !c.is_active });
      if (res.ok) {
        await loadCategories();
        flashCatSuccess(c.is_active ? 'Catégorie désactivée' : 'Catégorie activée');
      } else {
        setCatFeedback({ type: 'error', text: 'Erreur lors du changement de statut' });
      }
    } catch {
      setCatFeedback({ type: 'error', text: 'Erreur de connexion — le statut n’a pas changé' });
    }
  };

  const loadZones = async () => {
    setLoading(true);
    const res = await api.get('/api/admin/zones');
    if (res.ok) {
      const data = await res.json();
      setZones(data.zones || data || []);
    }
    setLoading(false);
  };

  const openZoneModal = (zone?: Zone) => {
    if (zone) {
      setEditingZone(zone);
      setZoneForm({ name: zone.zone_name, description: zone.description || '', capacity: zone.capacity, product_types: zone.product_types || [], color_code: zone.color_code || '#1A7A6A' });
    } else {
      setEditingZone(null);
      setZoneForm({ name: '', description: '', capacity: 20, product_types: [], color_code: '#1A7A6A' });
    }
    setShowZoneModal(true);
  };

  const saveZone = async () => {
    setLoading(true);
    setError('');
    try {
      const body = { name: zoneForm.name, description: zoneForm.description, capacity: zoneForm.capacity, product_types: zoneForm.product_types, color_code: zoneForm.color_code };
      const res = editingZone
        ? await api.put(`/api/admin/zones/${editingZone.zone_id}`, body)
        : await api.post('/api/admin/zones', body);
      if (res.ok) {
        setShowZoneModal(false);
        await loadZones();
        setMessage(editingZone ? 'Zone modifiée' : 'Zone créée');
        setTimeout(() => setMessage(''), 3000);
      } else {
        const e = await res.json().catch(() => ({}));
        setError(e.detail || 'Erreur lors de la sauvegarde');
      }
    } catch { setError('Erreur de connexion'); }
    setLoading(false);
  };

  const toggleProductType = (t: string) => {
    setZoneForm(f => ({ ...f, product_types: f.product_types.includes(t) ? f.product_types.filter(x => x !== t) : [...f.product_types, t] }));
  };

  const addCategory = async () => {
    if (!newCatName.trim()) { setCatFeedback({ type: 'error', text: 'Le nom de la catégorie est requis' }); return; }
    setCatFeedback(null);
    const added = newCatName.trim();
    try {
      const res = await api.post('/api/inventory/categories', {
        name: added,
        gender: newCatGender,
      });
      if (res.ok) {
        const created: Category = await res.json();
        setNewCatName('');
        // Une catégorie est unique par (nom + genre) : même nom, genre
        // différent = deux catégories distinctes. Si l'API renvoie une ligne
        // déjà présente, c'est qu'elle existait (idempotent) — on le dit
        // clairement plutôt que d'annoncer une création trompeuse.
        const alreadyListed = categories.some((c) => c.id === created.id);
        // Merge optimiste : la nouvelle ligne s'affiche tout de suite, sans
        // attendre (et sans dépendre d') un GET potentiellement en cache.
        setCategories((prev) =>
          [...prev.filter((c) => c.id !== created.id), created].sort((a, b) =>
            a.name.localeCompare(b.name, 'fr') || a.gender.localeCompare(b.gender),
          ),
        );
        await loadCategories();
        flashCatSuccess(
          alreadyListed
            ? `« ${created.name} » (${created.gender}) existe déjà`
            : `Catégorie « ${created.name} » (${created.gender}) ajoutée`,
        );
      } else {
        const e = await res.json().catch(() => ({}));
        setCatFeedback({ type: 'error', text: e.detail || "Erreur lors de l'ajout de la catégorie" });
      }
    } catch {
      setCatFeedback({ type: 'error', text: 'Erreur de connexion — la catégorie n’a pas pu être créée' });
    }
  };

  const loadCahierData = async () => {
    setCahierLoading(true);
    try {
      const [targetRes, weightsRes, yearRes] = await Promise.all([
        api.get(`/api/cahier/monthly-target/${cahierYear}/${cahierMonth}`),
        api.get('/api/cahier/weekday-weights'),
        api.get(`/api/cahier/monthly-targets/year/${cahierYear}`),
      ]);
      if (targetRes.ok) {
        const t = await targetRes.json();
        setCahierTarget(t.target_eur != null ? String(t.target_eur) : '');
        setCahierNotes(t.notes || '');
      }
      if (weightsRes.ok) {
        setCahierWeights(await weightsRes.json());
      }
      if (yearRes.ok) {
        const y = await yearRes.json();
        setYearGridTargets(
          (y.months as { target_eur: number | null }[]).map((m) =>
            m.target_eur != null ? String(m.target_eur) : '',
          ),
        );
      }
    } finally {
      setCahierLoading(false);
    }
  };

  const applyIncreaseToGrid = () => {
    const v = parseFloat(increaseValue);
    if (!Number.isFinite(v)) return;
    setYearGridTargets((prev) =>
      prev.map((cur) => {
        const base = parseFloat(cur);
        if (!Number.isFinite(base) || base <= 0) return cur;
        const next = increaseUnit === 'pct' ? base * (1 + v / 100) : base + v;
        return String(Math.max(0, Math.round(next)));
      }),
    );
  };

  const saveYearGrid = async () => {
    setYearGridSaving(true);
    try {
      const res = await api.put('/api/cahier/monthly-targets/bulk', {
        year: cahierYear,
        months: yearGridTargets.map((s, i) => ({
          month: i + 1,
          target_eur: s.trim() === '' ? null : parseFloat(s),
        })),
      });
      if (res.ok) {
        const body = await res.json().catch(() => null);
        const saved = body?.saved ?? 0;
        setMessage(`Tableau annuel enregistré (${saved} mois).`);
        setTimeout(() => setMessage(''), 3000);
        await loadCahierData();
      } else {
        setError('Erreur lors de l\'enregistrement du tableau.');
      }
    } catch {
      setError('Erreur réseau lors de l\'enregistrement.');
    }
    setYearGridSaving(false);
  };

  const saveCahierTarget = async () => {
    const value = parseFloat(cahierTarget);
    if (!Number.isFinite(value) || value < 0) {
      setError("Montant invalide");
      return;
    }
    setCahierLoading(true);
    const res = await api.put('/api/cahier/monthly-target', {
      year: cahierYear,
      month: cahierMonth,
      target_eur: value,
      notes: cahierNotes || null,
    });
    if (res.ok) {
      setMessage(`Objectif ${cahierMonth}/${cahierYear} enregistre : ${value.toLocaleString('fr-FR')} €`);
      setTimeout(() => setMessage(''), 3000);
    } else {
      setError('Erreur enregistrement objectif');
    }
    setCahierLoading(false);
  };

  const recomputeWeights = async () => {
    setCahierLoading(true);
    const res = await api.get('/api/cahier/weekday-weights?recompute=1');
    if (res.ok) {
      setCahierWeights(await res.json());
      setMessage('Poids recalcules');
      setTimeout(() => setMessage(''), 3000);
    }
    setCahierLoading(false);
  };

  const initZones = async () => {
    setLoading(true);
    const res = await api.post('/api/ai/mapping/init-zones', {});
    if (res.ok) {
      await loadZones();
      setMessage('Zones initialisees');
      setTimeout(() => setMessage(''), 3000);
    }
    setLoading(false);
  };

  const tabs = [
    { key: 'store' as const, label: 'Boutique' },
    { key: 'caisse' as const, label: 'Caisse' },
    { key: 'tickets' as const, label: 'Tickets & Factures' },
    { key: 'communication' as const, label: 'Communication' },
    { key: 'templates' as const, label: 'Modeles de messages' },
    { key: 'cahier' as const, label: 'Cahier de travail' },
    { key: 'fidelite' as const, label: 'Fidelite' },
    { key: 'categories' as const, label: 'Categories' },
    { key: 'zones' as const, label: 'Zones' },
    { key: 'hardware' as const, label: 'Materiel' },
    { key: 'scoring' as const, label: 'Scoring IA' },
    { key: 'system' as const, label: 'Systeme' },
  ];

  // Zones tab now redirects to dedicated /zones page (plan 2D + dashboards per zone).
  useEffect(() => {
    if (tab === 'zones' && typeof window !== 'undefined') {
      window.location.href = '/zones';
    }
  }, [tab]);

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-3 pt-16 pb-6 sm:px-4 md:px-6 md:pt-6 lg:p-8 max-w-5xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-display font-semibold text-black">Paramètres</h1>
          <p className="text-vz-ink-mute mt-1">Configuration de la boutique</p>
        </div>

        {message && (
          <div className="mb-4 p-3 bg-green-50 text-green-700 rounded-lg text-sm whitespace-pre-wrap">
            {message}
            <button onClick={() => setMessage('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}
        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            {error}
            <button onClick={() => setError('')} className="ml-2 font-bold">&times;</button>
          </div>
        )}

        {/* Tabs — scrollable, sticky. On mobile it pins below the floating
            hamburger (top-16) so the first tab isn't hidden behind it; on
            desktop there's no hamburger so it pins flush to the top. */}
        <div className="sticky top-16 md:top-0 z-10 -mx-3 sm:-mx-4 md:-mx-6 lg:-mx-8 bg-vz-bg/95 backdrop-blur-sm border-b border-vz-line mb-5">
          <div
            className="flex gap-2 px-3 sm:px-4 md:px-6 lg:px-8 py-2 overflow-x-auto"
            style={{ scrollbarWidth: 'thin' }}
          >
            {tabs.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-3 sm:px-4 py-2 rounded-lg min-h-[40px] whitespace-nowrap text-sm transition-colors ${
                  tab === t.key
                    ? 'bg-vz-teal text-white font-medium'
                    : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* STORE TAB */}
        {tab === 'store' && (
          <div className="space-y-6">
            <Card title="Informations boutique">
              {!shopInfo ? (
                <p className="text-sm text-gray-400">Chargement…</p>
              ) : (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Input
                      label="Nom"
                      value={shopInfo.name}
                      onChange={(e) => setShopInfo({ ...shopInfo, name: e.target.value })}
                    />
                    <Input
                      label="Slogan / type"
                      value={shopInfo.tagline}
                      onChange={(e) => setShopInfo({ ...shopInfo, tagline: e.target.value })}
                    />
                    <Input
                      label="Adresse"
                      value={shopInfo.address_line1}
                      onChange={(e) => setShopInfo({ ...shopInfo, address_line1: e.target.value })}
                    />
                    <Input
                      label="Complément (optionnel)"
                      value={shopInfo.address_line2}
                      onChange={(e) => setShopInfo({ ...shopInfo, address_line2: e.target.value })}
                    />
                    <Input
                      label="Code postal"
                      value={shopInfo.postal_code}
                      onChange={(e) => setShopInfo({ ...shopInfo, postal_code: e.target.value })}
                    />
                    <Input
                      label="Ville"
                      value={shopInfo.city}
                      onChange={(e) => setShopInfo({ ...shopInfo, city: e.target.value })}
                    />
                    <Input
                      label="Téléphone"
                      value={shopInfo.phone}
                      onChange={(e) => setShopInfo({ ...shopInfo, phone: e.target.value })}
                      placeholder="+33 …"
                    />
                    <Input
                      label="Email contact"
                      type="email"
                      value={shopInfo.email}
                      onChange={(e) => setShopInfo({ ...shopInfo, email: e.target.value })}
                    />
                    <Input
                      label="Site web"
                      value={shopInfo.website}
                      onChange={(e) => setShopInfo({ ...shopInfo, website: e.target.value })}
                      placeholder="vintiz.fr"
                    />
                    <Input
                      label="Horaires"
                      value={shopInfo.hours}
                      onChange={(e) => setShopInfo({ ...shopInfo, hours: e.target.value })}
                      placeholder="Mar-Sam : 10h-19h"
                    />
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Surface (m²)</label>
                      <input
                        type="number"
                        value={shopInfo.surface_m2}
                        onChange={(e) => setShopInfo({ ...shopInfo, surface_m2: parseFloat(e.target.value) || 0 })}
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">TVA (%)</label>
                      <input
                        type="number"
                        step="0.1"
                        value={shopInfo.vat_rate_percent}
                        onChange={(e) => setShopInfo({ ...shopInfo, vat_rate_percent: parseFloat(e.target.value) || 0 })}
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                      />
                    </div>
                    <Input
                      label="SIRET"
                      value={shopInfo.siret}
                      onChange={(e) => setShopInfo({ ...shopInfo, siret: e.target.value })}
                    />
                    <Input
                      label="RCS"
                      value={shopInfo.rcs}
                      onChange={(e) => setShopInfo({ ...shopInfo, rcs: e.target.value })}
                    />
                    <Input
                      label="Code APE"
                      value={shopInfo.ape}
                      onChange={(e) => setShopInfo({ ...shopInfo, ape: e.target.value })}
                    />
                    <Input
                      label="Forme juridique"
                      value={shopInfo.legal_form}
                      onChange={(e) => setShopInfo({ ...shopInfo, legal_form: e.target.value })}
                      placeholder="SARL, Association loi 1901…"
                    />
                    <Input
                      label="Capital social"
                      value={shopInfo.capital_social}
                      onChange={(e) => setShopInfo({ ...shopInfo, capital_social: e.target.value })}
                      placeholder="10 000 €"
                    />
                    <Input
                      label="TVA intracommunautaire"
                      value={shopInfo.tva_intracom}
                      onChange={(e) => setShopInfo({ ...shopInfo, tva_intracom: e.target.value })}
                      placeholder="FR..."
                    />
                    <Input
                      label="IBAN (facture)"
                      value={shopInfo.iban}
                      onChange={(e) => setShopInfo({ ...shopInfo, iban: e.target.value })}
                    />
                    <Input
                      label="BIC"
                      value={shopInfo.bic}
                      onChange={(e) => setShopInfo({ ...shopInfo, bic: e.target.value })}
                    />
                  </div>
                  <p className="text-xs text-vz-ink-mute mt-2">
                    Ces informations vendeur alimentent l&apos;émetteur et le bloc
                    règlement des factures (onglet « Tickets &amp; Factures »).
                  </p>
                  <div className="flex justify-end mt-5">
                    <Button onClick={saveShopInfo} disabled={shopSaving}>
                      {shopSaving ? 'Enregistrement…' : 'Enregistrer la boutique'}
                    </Button>
                  </div>
                </>
              )}
            </Card>

            <FeaturesPanel />

            <Card title="Terminal de paiement">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                <div>
                  <p className="text-sm text-gray-500 mb-1">TPE</p>
                  <p className="font-medium text-black">SumUp</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">Moyens de paiement</p>
                  <p className="font-medium text-black">CB, Especes, Cheque, Virement</p>
                </div>
              </div>
              <p className="mt-3 text-xs text-vz-ink-mute">
                Les identifiants SumUp (clé API, merchant code) sont fournis par
                les variables d&apos;environnement / l&apos;ops. La gestion des
                terminaux (TPE Solo) se fait dans l&apos;onglet « Caisse ».
              </p>
              <div className="mt-4">
                <Button variant="outline" onClick={() => setTab('caisse')}>
                  Gérer les terminaux
                </Button>
              </div>
            </Card>

            <Card title="Domaines">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
                <div>
                  <p className="text-sm text-gray-500 mb-1">Site vitrine</p>
                  <p className="font-medium text-vz-teal">vintiz.fr</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">Back-office</p>
                  <p className="font-medium text-vz-teal">app.vintiz.fr</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 mb-1">API</p>
                  <p className="font-medium text-vz-teal">api.vintiz.fr</p>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* CAISSE TAB — Multi-terminaux SumUp + article sac + routine caisse */}
        {tab === 'caisse' && (
          <div className="space-y-6">
            <SumUpTerminalsPanel />
            <PosQuickAddPanel />
            <CashManagementSettingsPanel />
          </div>
        )}

        {/* TICKETS & FACTURES TAB — studio mise en forme ticket + facture PDF */}
        {tab === 'tickets' && (
          <div className="space-y-6">
            <ReceiptInvoiceStudio />
          </div>
        )}

        {/* COMMUNICATION TAB — Email gateway (Brevo / SMTP / simulation) */}
        {tab === 'templates' && <MessageTemplatesPanel />}

        {tab === 'communication' && (
          <div className="space-y-6">
            <Card title="Passerelle email — magic-link OTP, anniversaires, nouvelles arrivées">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm mb-5 p-3 rounded-lg bg-vz-bg/60 border border-vz-line">
                <div>
                  <p className="text-vz-ink-mute text-xs uppercase tracking-wider">Backend actif</p>
                  <p className="font-medium text-black mt-1">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                      emailLive?.provider === 'brevo' ? 'bg-green-100 text-green-800' :
                      emailLive?.provider === 'smtp' ? 'bg-blue-100 text-blue-800' :
                      'bg-amber-100 text-amber-800'
                    }`}>
                      {emailLive ? emailLive.provider.toUpperCase() : '—'}
                    </span>
                  </p>
                </div>
                <div>
                  <p className="text-vz-ink-mute text-xs uppercase tracking-wider">Clé Brevo</p>
                  <p className="font-medium text-black mt-1">
                    {emailPersisted?.brevo_api_key_masked ? '✓ ' + emailPersisted.brevo_api_key_masked : '— Non définie'}
                  </p>
                </div>
                <div>
                  <p className="text-vz-ink-mute text-xs uppercase tracking-wider">SMTP</p>
                  <p className="font-medium text-black mt-1">
                    {emailPersisted?.smtp_host ? `${emailPersisted.smtp_host}:${emailPersisted.smtp_port}` : '— Non défini'}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">Provider forcé</label>
                  <select
                    value={emailForm.provider}
                    onChange={(e) => setEmailForm({ ...emailForm, provider: e.target.value })}
                    className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black"
                  >
                    <option value="">Auto-détection (Brevo si clé, sinon SMTP, sinon simulation)</option>
                    <option value="brevo">Brevo (production)</option>
                    <option value="smtp">SMTP standard</option>
                    <option value="simulation">Simulation (dev/test)</option>
                  </select>
                  <p className="text-xs text-gray-400 mt-1">Sans clé Brevo ni SMTP, les emails sont simulés (logués mais pas envoyés).</p>
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-black mb-1.5">
                    Clé API Brevo
                    {emailPersisted?.brevo_api_key_masked && (
                      <span className="ml-2 text-xs text-vz-ink-mute font-mono">actuelle : {emailPersisted.brevo_api_key_masked}</span>
                    )}
                  </label>
                  <input
                    type="password"
                    value={emailForm.brevo_api_key}
                    onChange={(e) => setEmailForm({ ...emailForm, brevo_api_key: e.target.value })}
                    placeholder={emailPersisted?.brevo_api_key_masked ? 'Laisser vide pour conserver' : 'xkeysib-…'}
                    autoComplete="off"
                    className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black font-mono focus:outline-none focus:ring-2 focus:ring-vz-teal"
                  />
                </div>

                <div className="sm:col-span-2 border-t border-vz-line pt-4 mt-2">
                  <p className="text-xs uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-3">
                    Fallback SMTP (utilisé si Brevo non configuré)
                  </p>
                </div>
                <Input
                  label="Hôte SMTP"
                  value={emailForm.smtp_host}
                  onChange={(e) => setEmailForm({ ...emailForm, smtp_host: e.target.value })}
                  placeholder="smtp.gmail.com"
                />
                <Input
                  label="Port SMTP"
                  value={emailForm.smtp_port}
                  onChange={(e) => setEmailForm({ ...emailForm, smtp_port: e.target.value })}
                  placeholder="587"
                />
                <Input
                  label="Utilisateur SMTP"
                  value={emailForm.smtp_user}
                  onChange={(e) => setEmailForm({ ...emailForm, smtp_user: e.target.value })}
                  placeholder="contact@domaine.fr"
                />
                <div>
                  <label className="block text-sm font-medium text-black mb-1.5">
                    Mot de passe SMTP
                    {emailPersisted?.smtp_password_masked && (
                      <span className="ml-2 text-xs text-vz-ink-mute font-mono">actuel : {emailPersisted.smtp_password_masked}</span>
                    )}
                  </label>
                  <input
                    type="password"
                    value={emailForm.smtp_password}
                    onChange={(e) => setEmailForm({ ...emailForm, smtp_password: e.target.value })}
                    placeholder={emailPersisted?.smtp_password_masked ? 'Laisser vide pour conserver' : '••••••••'}
                    autoComplete="off"
                    className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black font-mono focus:outline-none focus:ring-2 focus:ring-vz-teal"
                  />
                </div>

                <div className="sm:col-span-2 border-t border-vz-line pt-4 mt-2">
                  <p className="text-xs uppercase tracking-[0.18em] text-vz-ink-mute font-medium mb-3">
                    Identité de l'expéditeur
                  </p>
                </div>
                <Input
                  label="Adresse expéditeur"
                  value={emailForm.from_address}
                  onChange={(e) => setEmailForm({ ...emailForm, from_address: e.target.value })}
                  placeholder="noreply@vintiz.fr"
                />
                <Input
                  label="Nom expéditeur"
                  value={emailForm.from_name}
                  onChange={(e) => setEmailForm({ ...emailForm, from_name: e.target.value })}
                  placeholder="Vintiz Vernon"
                />
              </div>

              <div className="flex justify-end items-center mt-5 flex-wrap gap-3">
                <p className="text-xs text-gray-500 mr-auto">
                  Champs vides = conserver la valeur actuelle. Les valeurs persistées priment sur les variables d&apos;environnement.
                </p>
                <Button onClick={saveEmailConfig} disabled={emailSaving}>
                  {emailSaving ? 'Enregistrement…' : 'Enregistrer'}
                </Button>
              </div>
            </Card>

            <Card title="Test d'envoi end-to-end">
              <p className="text-sm text-gray-500 mb-4">
                Envoie un email réel pour vérifier que la passerelle est bien câblée.
                Si vous laissez le champ vide, l&apos;email sera envoyé à l&apos;adresse de votre compte admin.
              </p>
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <Input
                    type="email"
                    value={emailTestTo}
                    onChange={(e) => setEmailTestTo(e.target.value)}
                    placeholder="adresse@destinataire.fr (optionnel)"
                  />
                </div>
                <Button onClick={sendEmailTest} disabled={emailTesting}>
                  {emailTesting ? 'Envoi…' : 'Envoyer un email de test'}
                </Button>
              </div>
              {emailTestResult && (
                <div className={`mt-4 p-3 rounded-lg text-sm border ${
                  emailTestResult.ok && emailTestResult.status === 'sent'
                    ? 'bg-green-50 text-green-800 border-green-200'
                    : emailTestResult.status === 'simulated'
                      ? 'bg-amber-50 text-amber-800 border-amber-200'
                      : 'bg-red-50 text-red-700 border-red-200'
                }`}>
                  <p className="font-medium">
                    {emailTestResult.status === 'sent' && '✓ Email envoyé via ' + emailTestResult.backend.toUpperCase()}
                    {emailTestResult.status === 'simulated' && '⚠ Email SIMULÉ — backend non configuré, aucun envoi réel'}
                    {emailTestResult.status === 'failed' && '✕ Échec d\'envoi'}
                  </p>
                  {emailTestResult.detail && (
                    <p className="text-xs mt-1 font-mono">{emailTestResult.detail}</p>
                  )}
                </div>
              )}
            </Card>

            <Card title="Passerelle SMS (Brevo)">
              <p className="text-sm text-gray-500 mb-4">
                Le SMS partage la même clé API Brevo que l&apos;email — pas de
                secret dédié à poser. Sender ID affiché sur le téléphone du
                client (alphanumérique, max 11 caractères) :{' '}
                <code className="font-mono bg-gray-100 px-1 rounded">
                  {smsLive?.from || 'Vintiz'}
                </code>
                .
              </p>
              <div className="mb-4 p-3 rounded-lg border border-vz-line bg-vz-bg/40 text-sm">
                <p className="font-medium">
                  Provider actif :{' '}
                  <span className={smsLive?.configured ? 'text-vz-teal' : 'text-amber-700'}>
                    {smsLive ? smsLive.provider.toUpperCase() : 'inconnu'}
                  </span>
                </p>
                {smsLive && !smsLive.configured && (
                  <p className="text-xs text-amber-700 mt-1">
                    Aucun provider configuré — les SMS sont simulés (logs uniquement).
                    Renseigne la clé BREVO_API_KEY dans le bloc Email ci-dessus pour activer.
                  </p>
                )}
                {/* Sonde compte Brevo : ce que la CLÉ voit réellement. Si le
                    solde ici est 0 / le compte différent de celui du
                    navigateur → la clé pointe vers un autre compte Brevo. */}
                {smsAccount && smsAccount.ok && (
                  <div className="mt-2 pt-2 border-t border-vz-line/60 text-xs space-y-0.5">
                    <p>
                      Compte vu par la clé :{' '}
                      <span className="font-mono">{smsAccount.company || smsAccount.account_email || '—'}</span>
                      {smsAccount.account_email && smsAccount.company && (
                        <span className="text-vz-ink-mute"> ({smsAccount.account_email})</span>
                      )}
                      {smsAccount.email_plan_type && (
                        <span className="ml-2 text-vz-ink-mute">
                          · Plan Brevo : <strong className="uppercase">{smsAccount.email_plan_type}</strong>
                        </span>
                      )}
                    </p>
                    <p>
                      Crédits SMS vus par la clé :{' '}
                      <span className={`font-semibold ${(smsAccount.sms_credits ?? 0) > 0 ? 'text-vz-teal' : 'text-red-600'}`}>
                        {smsAccount.sms_credits ?? 'aucun bucket SMS'}
                      </span>
                    </p>
                    {/* 3 cas distincts : crédits=0 → autre compte ; crédits>0 +
                        plan Free → limitation plan ; crédits>0 + plan payant → tout OK. */}
                    {(smsAccount.sms_credits ?? 0) === 0 && (
                      <p className="text-red-600">
                        ⚠ La clé voit 0 crédit SMS. Si Brevo affiche des crédits dans le
                        navigateur, c&apos;est que cette clé API appartient à un <strong>autre
                        compte/portefeuille</strong> : régénère une clé dans le compte
                        « {smsAccount.company || 'celui qui a les crédits'} » et colle-la dans
                        le bloc Email ci-dessus.
                      </p>
                    )}
                    {(smsAccount.sms_credits ?? 0) > 0 && smsAccount.email_plan_type === 'free' && (
                      <p className="text-red-600">
                        ⚠ Crédits SMS visibles ({smsAccount.sms_credits}) mais le plan Brevo
                        est <strong>FREE</strong> : l&apos;API SMS transactionnelle est
                        <strong> désactivée sur l&apos;offre Free</strong> (Brevo l&apos;autorise
                        uniquement via l&apos;UI campagne marketing). Solutions :{' '}
                        <strong>(a)</strong> passer en plan Starter+ chez Brevo,{' '}
                        <strong>(b)</strong> basculer la passerelle SMS sur Twilio (legacy fallback).
                      </p>
                    )}
                    {(smsAccount.sms_credits ?? 0) > 0 &&
                      smsAccount.email_plan_type &&
                      smsAccount.email_plan_type !== 'free' &&
                      smsAccount.can_send_transactional_sms === false && (
                      <p className="text-amber-700">
                        Crédits visibles et plan payant — mais l&apos;API SMS transactionnel
                        semble bloquée. Demande au support Brevo l&apos;activation
                        transactionnelle du compte.
                      </p>
                    )}
                  </div>
                )}
                {smsAccount && !smsAccount.ok && (
                  <p className="mt-2 text-xs text-red-600">
                    Sonde compte Brevo en échec : {smsAccount.error}
                  </p>
                )}
              </div>
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <Input
                    type="tel"
                    value={smsTestTo}
                    onChange={(e) => setSmsTestTo(e.target.value)}
                    placeholder="06 12 34 56 78 ou +33612345678"
                  />
                </div>
                <Button onClick={sendSmsTest} disabled={smsTesting || !smsTestTo.trim()}>
                  {smsTesting ? 'Envoi…' : 'Envoyer un SMS de test'}
                </Button>
              </div>
              {smsTestResult && (
                <div className={`mt-4 p-3 rounded-lg text-sm border ${
                  smsTestResult.ok && smsTestResult.status === 'sent'
                    ? 'bg-green-50 text-green-800 border-green-200'
                    : smsTestResult.simulated || smsTestResult.status === 'simulated'
                      ? 'bg-amber-50 text-amber-800 border-amber-200'
                      : 'bg-red-50 text-red-700 border-red-200'
                }`}>
                  <p className="font-medium">
                    {smsTestResult.status === 'sent' && '✓ SMS envoyé via ' + smsTestResult.backend.toUpperCase()}
                    {(smsTestResult.simulated || smsTestResult.status === 'simulated') && '⚠ SMS SIMULÉ — backend non configuré, aucun envoi réel'}
                    {smsTestResult.status === 'failed' && '✕ Échec d\'envoi'}
                  </p>
                  {smsTestResult.detail && (
                    <p className="text-xs mt-1 font-mono break-all">{smsTestResult.detail}</p>
                  )}
                  {smsTestResult.detail && smsTestResult.detail.includes('Brevo') && (
                    <div className="mt-2 text-xs space-y-1">
                      <p className="font-medium">Pistes Brevo :</p>
                      <ul className="list-disc list-inside pl-1">
                        <li><strong>Sender invalid / not registered</strong> → enregistre le sender « {smsLive?.from || 'Vintiz'} » dans Brevo &gt; SMS &gt; Sender</li>
                        <li><strong>402 / insufficient credit</strong> → recharge le crédit SMS dans Brevo</li>
                        <li><strong>403 / permission_denied</strong> → demande à Brevo l&apos;activation transactionnelle SMS pour le compte</li>
                        <li><strong>400 / invalid recipient</strong> → vérifie le format E.164 (+33612345678)</li>
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </Card>
          </div>
        )}

        {/* CATEGORIES TAB */}
        {tab === 'categories' && (
          <div className="space-y-6">
            <Card title="Ajouter une categorie">
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <Input
                    placeholder="Nom de la categorie"
                    value={newCatName}
                    onChange={(e) => setNewCatName(e.target.value)}
                  />
                </div>
                <select
                  value={newCatGender}
                  onChange={(e) => setNewCatGender(e.target.value)}
                  className="min-h-[48px] px-4 py-2 rounded-lg border border-gray-300 bg-white text-black"
                >
                  <option value="femme">Femme</option>
                  <option value="homme">Homme</option>
                  <option value="enfant">Enfant</option>
                  <option value="mixte">Mixte</option>
                </select>
                <Button onClick={addCategory}>Ajouter</Button>
              </div>
              {catFeedback && (
                <div
                  role="status"
                  className={`mt-3 p-3 rounded-lg text-sm flex items-start justify-between gap-2 ${
                    catFeedback.type === 'success'
                      ? 'bg-green-50 text-green-700'
                      : 'bg-red-50 text-red-700'
                  }`}
                >
                  <span>{catFeedback.text}</span>
                  <button
                    onClick={() => setCatFeedback(null)}
                    className="font-bold shrink-0"
                    aria-label="Fermer"
                  >
                    &times;
                  </button>
                </div>
              )}
            </Card>

            <Card title="Categories existantes">
              {loading ? (
                <p className="text-gray-400 text-center py-4">Chargement...</p>
              ) : categories.length === 0 ? (
                <p className="text-gray-400 text-center py-4">Aucune categorie. Lancez le seed dans Systeme.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="pb-2 text-sm font-semibold text-gray-600">Nom</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600">Genre</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600">Statut</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {categories.map((c) => {
                        const editing = editingCatId === c.id;
                        return (
                        <tr key={c.id} className={`border-b border-gray-50 ${c.is_active ? '' : 'opacity-60'}`}>
                          <td className="py-2 text-sm text-black">
                            {editing ? (
                              <Input value={editCatName} onChange={(e) => setEditCatName(e.target.value)} />
                            ) : c.name}
                          </td>
                          <td className="py-2">
                            {editing ? (
                              <select value={editCatGender} onChange={(e) => setEditCatGender(e.target.value)}
                                className="min-h-[40px] px-3 py-1.5 rounded-lg border border-gray-300 bg-white text-sm">
                                <option value="femme">Femme</option>
                                <option value="homme">Homme</option>
                                <option value="enfant">Enfant</option>
                                <option value="mixte">Mixte</option>
                              </select>
                            ) : (
                              <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                                c.gender === 'femme' ? 'bg-vz-accent-soft text-vz-accent' :
                                c.gender === 'homme' ? 'bg-blue-100 text-blue-700' :
                                c.gender === 'enfant' ? 'bg-purple-100 text-purple-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>
                                {c.gender}
                              </span>
                            )}
                          </td>
                          <td className="py-2">
                            <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${c.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-500'}`}>
                              {c.is_active ? 'Active' : 'Désactivée'}
                            </span>
                          </td>
                          <td className="py-2">
                            <div className="flex justify-end gap-3 text-sm">
                              {editing ? (
                                <>
                                  <button onClick={() => saveCat(c.id)} className="text-vz-teal font-medium hover:underline">Enregistrer</button>
                                  <button onClick={() => setEditingCatId(null)} className="text-gray-400 hover:underline">Annuler</button>
                                </>
                              ) : (
                                <>
                                  <button onClick={() => startEditCat(c)} className="text-vz-teal hover:underline">Modifier</button>
                                  <button onClick={() => toggleCatActive(c)} className={c.is_active ? 'text-amber-600 hover:underline' : 'text-green-600 hover:underline'}>
                                    {c.is_active ? 'Désactiver' : 'Activer'}
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        )}

        {/* ZONES TAB */}
        {tab === 'zones' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-black">Zones de la boutique</h2>
              <div className="flex gap-2">
                {zones.length === 0 && <Button onClick={initZones} disabled={loading}>Initialiser les zones</Button>}
                <Button onClick={() => openZoneModal()} variant="secondary">+ Ajouter une zone</Button>
              </div>
            </div>

            {loading ? (
              <Card><p className="text-gray-400 text-center py-4">Chargement...</p></Card>
            ) : zones.length === 0 ? (
              <Card><p className="text-gray-400 text-center py-4">Aucune zone configuree. Cliquez &quot;Initialiser les zones&quot; ou &quot;Ajouter une zone&quot;.</p></Card>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {zones.map((z) => (
                  <Card key={z.zone_id}>
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: z.color_code || '#1A7A6A' }} />
                        <h3 className="font-semibold text-black">{z.zone_name}</h3>
                      </div>
                      <button onClick={() => openZoneModal(z)} className="text-xs text-vz-teal hover:underline min-h-[32px] px-2">Modifier</button>
                    </div>
                    <p className="text-xs text-gray-400 mb-3">{z.description}</p>
                    {z.product_types && z.product_types.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-3">
                        {z.product_types.map(t => <span key={t} className="text-xs px-2 py-0.5 bg-vz-teal-soft text-vz-teal-deep rounded-full">{t}</span>)}
                      </div>
                    )}
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Capacité</span>
                        <span className="text-black font-medium">{z.product_count} / {z.capacity}</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div className={`h-2 rounded-full ${z.occupancy_percent > 80 ? 'bg-red-400' : z.occupancy_percent > 50 ? 'bg-yellow-400' : 'bg-green-400'}`}
                          style={{ width: `${Math.min(100, z.occupancy_percent)}%` }} />
                      </div>
                      <p className="text-xs text-gray-400 text-right">{z.occupancy_percent}% occupé</p>
                    </div>
                  </Card>
                ))}
              </div>
            )}

            {/* Zone Edit Modal */}
            {showZoneModal && (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
                  <h3 className="text-lg font-bold text-black mb-4">{editingZone ? 'Modifier la zone' : 'Nouvelle zone'}</h3>
                  <div className="space-y-4">
                    <Input label="Nom de la zone" value={zoneForm.name} onChange={e => setZoneForm(f => ({...f, name: e.target.value}))} placeholder="Ex: Vitrine gauche" />
                    <Input label="Description" value={zoneForm.description} onChange={e => setZoneForm(f => ({...f, description: e.target.value}))} placeholder="Ex: Rails mur gauche entrée" />
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Capacité max (articles)</label>
                      <input type="number" min={1} max={500} value={zoneForm.capacity} onChange={e => setZoneForm(f => ({...f, capacity: parseInt(e.target.value) || 20}))}
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-2">Catégories à affecter (préférence)</label>
                      <p className="text-[11px] text-gray-400 mb-2">Les produits de ces catégories seront orientés vers cette zone par le moteur d&apos;affectation.</p>
                      <div className="flex flex-wrap gap-2">
                        {Array.from(new Set([...categories.map(c => c.name), ...zoneForm.product_types])).map(t => (
                          <button key={t} type="button" onClick={() => toggleProductType(t)}
                            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${zoneForm.product_types.includes(t) ? 'bg-vz-teal text-white border-vz-teal' : 'bg-white text-gray-600 border-gray-300 hover:border-vz-teal'}`}>
                            {t}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <label className="text-sm font-medium text-black">Couleur</label>
                      <input type="color" value={zoneForm.color_code} onChange={e => setZoneForm(f => ({...f, color_code: e.target.value}))} className="w-10 h-10 rounded cursor-pointer border border-gray-300" />
                      <span className="text-sm text-gray-500">{zoneForm.color_code}</span>
                    </div>
                  </div>
                  <div className="flex gap-3 mt-6">
                    <Button variant="outline" onClick={() => setShowZoneModal(false)} className="flex-1">Annuler</Button>
                    <Button onClick={saveZone} disabled={loading || !zoneForm.name} className="flex-1">{loading ? 'Sauvegarde...' : 'Sauvegarder'}</Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* HARDWARE TAB */}
        {tab === 'hardware' && (
          <div className="space-y-6">
            <Card title="Compatibilite materielle">
              <p className="text-sm text-gray-500 mb-4">
                Peripheriques supportes nativement par Vintiz. Configurez les adresses IP ci-dessous, puis lancez un test.
              </p>
              {loading && compatibility.length === 0 ? (
                <p className="text-gray-400 text-center py-4">Chargement...</p>
              ) : (
                <div className="overflow-x-auto -mx-4 sm:mx-0 px-4 sm:px-0">
                  <table className="w-full text-left min-w-[640px]">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="pb-2 text-sm font-semibold text-gray-600">Peripherique</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600">Modele</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600 hidden sm:table-cell">Connexion</th>
                        <th className="pb-2 text-sm font-semibold text-gray-600 text-right">Test</th>
                      </tr>
                    </thead>
                    <tbody>
                      {compatibility.map((it) => {
                        const test = hwTests[it.category] || { status: 'idle' as const };
                        return (
                          <tr key={it.category} className="border-b border-gray-50">
                            <td className="py-3 text-sm text-black font-medium">{it.label}</td>
                            <td className="py-3 text-sm text-gray-700">{it.model}</td>
                            <td className="py-3 text-xs text-gray-500 hidden sm:table-cell">{it.connection}</td>
                            <td className="py-3 text-right">
                              <div className="inline-flex items-center gap-2 flex-wrap justify-end">
                                {test.status === 'success' && (
                                  <span className="text-xs text-green-700">✓ {test.message || 'OK'}</span>
                                )}
                                {test.status === 'error' && (
                                  <span className="text-xs text-red-600 max-w-[180px] truncate" title={test.message}>✕ {test.message}</span>
                                )}
                                <Button
                                  variant="outline"
                                  onClick={() => runHwTest(it.category)}
                                  disabled={test.status === 'running'}
                                >
                                  {test.status === 'running' ? 'Test…' : 'Tester'}
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            {hardware && (
              <>
                <Card title="Imprimante de reçus — MUNBYN 047P">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="rp-enabled"
                        checked={hardware.receipt_printer.enabled}
                        onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, enabled: e.target.checked } })}
                        className="w-5 h-5 accent-vz-teal"
                      />
                      <label htmlFor="rp-enabled" className="text-sm font-medium text-black">Activer l&apos;imprimante de reçus</label>
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-black mb-1.5">Mode de connexion</label>
                      <div className="flex gap-2 flex-wrap">
                        {(['network', 'usb'] as const).map((mode) => {
                          const active = (hardware.receipt_printer.connection || 'network') === mode;
                          return (
                            <button
                              key={mode}
                              type="button"
                              onClick={() => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, connection: mode } })}
                              className={`px-4 py-2 rounded-lg min-h-[44px] text-sm font-medium transition-colors ${
                                active
                                  ? 'bg-vz-teal text-white'
                                  : 'bg-white text-vz-ink-soft border border-vz-line hover:bg-vz-bg-alt'
                              }`}
                            >
                              {mode === 'network' ? 'Réseau (Wi-Fi)' : 'USB (tablette)'}
                            </button>
                          );
                        })}
                      </div>
                      <p className="text-xs text-vz-ink-mute mt-1">
                        {(hardware.receipt_printer.connection || 'network') === 'network'
                          ? 'Station fixe — ESC/POS sur TCP 9100.'
                          : 'Tablette caissier (Lenovo Idea Tab Pro) — WebUSB sur câble OTG.'}
                      </p>
                    </div>

                    {(hardware.receipt_printer.connection || 'network') === 'network' && (
                      <>
                        <Input
                          label="Adresse IP"
                          value={hardware.receipt_printer.host}
                          onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, host: e.target.value } })}
                          placeholder="192.168.1.50"
                        />
                        <div>
                          <label className="block text-sm font-medium text-black mb-1.5">Port TCP</label>
                          <input
                            type="number"
                            value={hardware.receipt_printer.port}
                            onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, port: parseInt(e.target.value) || 9100 } })}
                            className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                          />
                        </div>
                      </>
                    )}

                    {(hardware.receipt_printer.connection || 'network') === 'usb' && (
                      <div className="sm:col-span-2 p-3 rounded-lg bg-vz-bg-alt border border-vz-line">
                        {hardware.receipt_printer.usb_vendor_id && hardware.receipt_printer.usb_product_id ? (
                          <div className="flex flex-wrap items-center gap-3">
                            <span className="inline-flex items-center gap-1.5 text-sm text-vz-ink">
                              <span className="w-2 h-2 rounded-full bg-green-500" />
                              Couplé : <strong className="font-mono">{hardware.receipt_printer.usb_product_label || 'Imprimante ESC/POS'}</strong>
                            </span>
                            <span className="text-xs text-vz-ink-mute">
                              VID {hardware.receipt_printer.usb_vendor_id?.toString(16).padStart(4, '0')} ·
                              PID {hardware.receipt_printer.usb_product_id?.toString(16).padStart(4, '0')}
                            </span>
                            <span className="flex-1" />
                            <button type="button" onClick={pairUsbReceiptPrinter} className="text-xs text-vz-teal underline">
                              Re-coupler
                            </button>
                            <button type="button" onClick={unpairUsbReceiptPrinter} className="text-xs text-red-600 underline">
                              Découpler
                            </button>
                          </div>
                        ) : (
                          <div className="flex flex-wrap items-center gap-3">
                            <span className="inline-flex items-center gap-1.5 text-sm text-vz-ink-soft">
                              <span className="w-2 h-2 rounded-full bg-gray-300" />
                              Aucun périphérique couplé
                            </span>
                            <span className="flex-1" />
                            <Button onClick={pairUsbReceiptPrinter} variant="secondary" size="sm">
                              Coupler le périphérique USB
                            </Button>
                          </div>
                        )}
                        <p className="text-xs text-vz-ink-mute mt-2">
                          Sur la tablette Android : autoriser l&apos;accès USB lors du couplage. Le navigateur retient la permission jusqu&apos;à débranchement.
                        </p>
                      </div>
                    )}

                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Largeur papier (caractères)</label>
                      <input
                        type="number"
                        value={hardware.receipt_printer.width_chars}
                        onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, width_chars: parseInt(e.target.value) || 42 } })}
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                      />
                      <p className="text-xs text-gray-400 mt-1">42 pour du 80 mm (Font A)</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        id="rp-cut"
                        checked={hardware.receipt_printer.cut_paper}
                        onChange={(e) => setHardware({ ...hardware, receipt_printer: { ...hardware.receipt_printer, cut_paper: e.target.checked } })}
                        className="w-5 h-5 accent-vz-teal"
                      />
                      <label htmlFor="rp-cut" className="text-sm text-black">Coupe automatique du papier</label>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <Button onClick={testReceiptPrinter} variant="secondary">Imprimer un ticket de test</Button>
                  </div>
                </Card>

                <Card title="Tiroir-caisse — Safescan SD-4141">
                  <p className="text-xs text-gray-500 mb-4">Connecte en RJ-12 a l&apos;imprimante de recus ci-dessus. Ouverture via commande ESC/POS.</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="cd-enabled"
                        checked={hardware.cash_drawer.enabled}
                        onChange={(e) => setHardware({ ...hardware, cash_drawer: { ...hardware.cash_drawer, enabled: e.target.checked } })}
                        className="w-5 h-5 accent-vz-teal"
                      />
                      <label htmlFor="cd-enabled" className="text-sm font-medium text-black">Activer le tiroir-caisse</label>
                    </div>
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="cd-auto"
                        checked={hardware.cash_drawer.kick_on_cash}
                        onChange={(e) => setHardware({ ...hardware, cash_drawer: { ...hardware.cash_drawer, kick_on_cash: e.target.checked } })}
                        className="w-5 h-5 accent-vz-teal"
                      />
                      <label htmlFor="cd-auto" className="text-sm text-black">Ouverture automatique a l&apos;encaissement especes</label>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Broche (kick pin)</label>
                      <select
                        value={hardware.cash_drawer.kick_pin}
                        onChange={(e) => setHardware({ ...hardware, cash_drawer: { ...hardware.cash_drawer, kick_pin: parseInt(e.target.value) } })}
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black"
                      >
                        <option value={0}>Pin 2 (standard)</option>
                        <option value={1}>Pin 5</option>
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-4">
                    <Button onClick={kickDrawer} variant="secondary">Ouvrir le tiroir (test)</Button>
                  </div>
                </Card>

                <Card title="Imprimante d&apos;étiquettes — Zebra ZD421d">
                  <p className="text-xs text-vz-ink-mute mb-3">
                    Format Vintiz 80×120 mm, thermique direct 203 dpi. Deux modes : <strong>réseau local</strong> (ZPL en TCP 9100, l&apos;API doit joindre l&apos;imprimante) ou <strong>cloud</strong> (Weblink + SendFileToPrinter : l&apos;imprimante se connecte à Zebra Data Services, idéal si l&apos;API tourne hors site).
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="lp-enabled"
                        checked={hardware.label_printer.enabled}
                        onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, enabled: e.target.checked } })}
                        className="w-5 h-5 accent-vz-teal"
                      />
                      <label htmlFor="lp-enabled" className="text-sm font-medium text-black">Activer l&apos;imprimante Zebra</label>
                    </div>
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-black mb-1.5">Mode de connexion</label>
                      <select
                        value={hardware.label_printer.connection || 'network'}
                        onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, connection: e.target.value as 'network' | 'cloud' | 'bluetooth' } })}
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                      >
                        <option value="network">Réseau local (TCP 9100)</option>
                        <option value="cloud">Cloud Zebra (Weblink + SendFileToPrinter)</option>
                        <option value="bluetooth">Bluetooth (tablette, Web Bluetooth)</option>
                      </select>
                    </div>
                    {(hardware.label_printer.connection || 'network') === 'network' && (
                      <>
                        <Input
                          label="Adresse IP"
                          value={hardware.label_printer.host}
                          onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, host: e.target.value } })}
                          placeholder="192.168.1.100"
                        />
                        <div>
                          <label className="block text-sm font-medium text-black mb-1.5">Port TCP</label>
                          <input
                            type="number"
                            value={hardware.label_printer.port}
                            onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, port: parseInt(e.target.value) || 9100 } })}
                            className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                          />
                        </div>
                      </>
                    )}
                    {hardware.label_printer.connection === 'cloud' && (
                      <>
                        <Input
                          label="Clé API Zebra Data Services"
                          type="password"
                          value={hardware.label_printer.cloud_api_key || ''}
                          onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, cloud_api_key: e.target.value } })}
                          placeholder={hardware.label_printer.cloud_api_key_set ? `•••• ${hardware.label_printer.cloud_api_key_hint || ''}` : 'clé API'}
                        />
                        <Input
                          label="Tenant"
                          value={hardware.label_printer.cloud_tenant || ''}
                          onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, cloud_tenant: e.target.value } })}
                          placeholder="n° de tenant"
                        />
                        <Input
                          label="N° de série imprimante"
                          value={hardware.label_printer.cloud_serial || ''}
                          onChange={(e) => setHardware({ ...hardware, label_printer: { ...hardware.label_printer, cloud_serial: e.target.value } })}
                          placeholder="ex. D2J123456789"
                        />
                        <div className="sm:col-span-2 text-xs text-vz-ink-mute">
                          L&apos;imprimante doit d&apos;abord être enrôlée auprès de Zebra Data Services (Weblink). Laissez la clé API vide pour conserver celle déjà enregistrée. Enregistrez avant de tester.
                        </div>
                      </>
                    )}
                    {hardware.label_printer.connection === 'bluetooth' && (
                      <div className="sm:col-span-2">
                        {hardware.label_printer.bt_device_name ? (
                          <div className="flex items-center gap-3 flex-wrap">
                            <span className="text-sm text-vz-ink">Imprimante couplée : <strong>{hardware.label_printer.bt_device_name}</strong></span>
                            <button type="button" onClick={pairBluetoothPrinter} className="text-xs text-vz-teal underline">
                              Coupler une autre
                            </button>
                          </div>
                        ) : (
                          <Button onClick={pairBluetoothPrinter} variant="secondary" size="sm">
                            Coupler l&apos;imprimante Bluetooth
                          </Button>
                        )}
                        <p className="text-xs text-vz-ink-mute mt-2">
                          Web Bluetooth (BLE) depuis la tablette — Chrome Android requis (pas iPad/Safari). L&apos;impression se fait depuis la tablette, pas le serveur. L&apos;imprimante doit avoir l&apos;option Bluetooth LE.
                        </p>
                      </div>
                    )}
                    <div className="sm:col-span-2">
                      <label className="block text-sm font-medium text-black mb-1.5">
                        Format d&apos;étiquette
                      </label>
                      <select
                        value={hardware.label_printer.label_profile || '60x40_single'}
                        onChange={(e) => {
                          const next = labelProfiles.find((p) => p.key === e.target.value);
                          setHardware({
                            ...hardware,
                            label_printer: {
                              ...hardware.label_printer,
                              label_profile: e.target.value,
                              // Synchronise les dimensions persistées (compat
                              // avec consommateurs qui lisent encore width/height).
                              label_width_mm: next?.label_width_mm ?? hardware.label_printer.label_width_mm,
                              label_height_mm: next?.label_height_mm ?? hardware.label_printer.label_height_mm,
                            },
                          });
                        }}
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                      >
                        {labelProfiles.map((p) => (
                          <option key={p.key} value={p.key}>
                            {p.name} ({p.ticket_count === 1 ? '1 ticket' : `${p.ticket_count} tickets`})
                          </option>
                        ))}
                      </select>
                      <p className="text-xs text-vz-ink-mute mt-1.5">
                        Le format détermine les dimensions du rouleau ET la disposition
                        (deux étiquettes 25×52, ou une seule 40×60 combinant les deux).
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 mt-4">
                    <Button
                      onClick={testLabelPrinter}
                      variant="secondary"
                      disabled={hwTests.label_printer?.status === 'running'}
                    >
                      {hwTests.label_printer?.status === 'running' ? 'Envoi en cours…' : 'Imprimer une étiquette de test'}
                    </Button>
                    {hwTests.label_printer && hwTests.label_printer.status !== 'running' && (
                      <span
                        className={`text-sm ${hwTests.label_printer.status === 'success' ? 'text-vz-teal' : 'text-red-600'}`}
                      >
                        {hwTests.label_printer.status === 'success' ? '✓ ' : '✕ '}
                        {hwTests.label_printer.message}
                      </span>
                    )}
                  </div>
                </Card>

                <Card title="Douchette code-barres — Inateck BCST-35">
                  <p className="text-xs text-gray-500 mb-4">Fonctionne en mode clavier HID : branchez le dongle USB ou appairez en Bluetooth. Le scan remplit le champ recherche du POS et ajoute l&apos;article au panier.</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="flex items-center gap-3 sm:col-span-2">
                      <input
                        type="checkbox"
                        id="bs-enabled"
                        checked={hardware.barcode_scanner.enabled}
                        onChange={(e) => setHardware({ ...hardware, barcode_scanner: { ...hardware.barcode_scanner, enabled: e.target.checked } })}
                        className="w-5 h-5 accent-vz-teal"
                      />
                      <label htmlFor="bs-enabled" className="text-sm font-medium text-black">Activer le champ de scan automatique au POS</label>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-black mb-1.5">Longueur minimale</label>
                      <input
                        type="number"
                        value={hardware.barcode_scanner.min_length}
                        onChange={(e) => setHardware({ ...hardware, barcode_scanner: { ...hardware.barcode_scanner, min_length: parseInt(e.target.value) || 4 } })}
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-lg border border-gray-300 bg-white text-black focus:outline-none focus:ring-2 focus:ring-vz-teal"
                      />
                    </div>
                  </div>
                </Card>

                <Card title="Terminal de paiement — SumUp">
                  <p className="text-sm text-gray-500 mb-3">
                    Les identifiants SumUp (clé API, merchant code) sont fournis
                    par les variables d&apos;environnement / l&apos;ops. La
                    gestion des terminaux (TPE Solo, reader ID) se fait dans
                    l&apos;onglet&nbsp;
                    <button
                      type="button"
                      onClick={() => setTab('caisse')}
                      className="text-vz-teal underline font-medium"
                    >
                      Caisse
                    </button>
                    .
                  </p>
                  <Button variant="outline" onClick={() => setTab('caisse')}>
                    Gérer les terminaux
                  </Button>
                </Card>

                <div className="flex justify-end gap-3">
                  <Button onClick={saveHardware} disabled={hwSaving}>
                    {hwSaving ? 'Sauvegarde...' : 'Sauvegarder la configuration'}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}

        {/* CAHIER TAB */}
        {tab === 'cahier' && (
          <div className="space-y-6">
            <Card title="Objectifs mensuels — tableau annuel">
              <p className="text-sm text-gray-500 mb-4">
                Saisissez les 12 objectifs de l&apos;année d&apos;un coup. Chaque
                objectif est ensuite réparti sur les jours d&apos;ouverture du
                mois (Obj du jour = Obj mensuel ÷ jours d&apos;ouverture).
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm text-gray-500 mb-1">Année</label>
                  <Input
                    type="number"
                    value={cahierYear}
                    onChange={(e) => setCahierYear(parseInt(e.target.value) || now.getFullYear())}
                  />
                </div>
                <div className="sm:col-span-2 flex items-end gap-2">
                  <Button variant="outline" onClick={loadCahierData} disabled={cahierLoading}>
                    {cahierLoading ? 'Chargement…' : 'Recharger l’année'}
                  </Button>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200 text-gray-500 text-xs uppercase tracking-wider">
                      <th className="text-left py-2 px-2 font-medium">Mois</th>
                      <th className="text-left py-2 px-2 font-medium">Objectif CA (€)</th>
                      <th className="text-left py-2 px-2 font-medium hidden sm:table-cell">
                        Aperçu — Obj du jour (moy.)
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
                      const v = parseFloat(yearGridTargets[m - 1]);
                      const daysInMonth = new Date(cahierYear, m, 0).getDate();
                      // Approx opening days = days with weight > 0 (default 6 if weights absent)
                      let openingDays = 0;
                      if (cahierWeights) {
                        for (let d = 1; d <= daysInMonth; d++) {
                          const jsWd = new Date(cahierYear, m - 1, d).getDay();
                          const wd = (jsWd + 6) % 7;
                          if ((cahierWeights.weights[wd] || 0) > 0) openingDays++;
                        }
                      } else {
                        openingDays = Math.round((daysInMonth * 6) / 7);
                      }
                      const objJour =
                        Number.isFinite(v) && v > 0 && openingDays > 0
                          ? v / openingDays
                          : 0;
                      return (
                        <tr key={m} className="border-b border-gray-100">
                          <td className="py-2 px-2 capitalize text-black font-medium">
                            {new Date(2000, m - 1, 1).toLocaleDateString('fr-FR', { month: 'long' })}
                          </td>
                          <td className="py-2 px-2">
                            <Input
                              type="number"
                              value={yearGridTargets[m - 1]}
                              onChange={(e) => {
                                const next = [...yearGridTargets];
                                next[m - 1] = e.target.value;
                                setYearGridTargets(next);
                              }}
                              placeholder="—"
                            />
                          </td>
                          <td className="py-2 px-2 hidden sm:table-cell text-vz-teal font-mono">
                            {objJour > 0 ? `${objJour.toFixed(0)} €/jour ouvert` : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mt-5 p-3 bg-vz-bg-alt rounded-lg">
                <p className="text-sm font-medium text-black mb-2">
                  Augmentation rapide
                </p>
                <p className="text-xs text-gray-500 mb-3">
                  Applique la variation à tous les mois remplis (cellules
                  vides ignorées). Pratique pour planifier une croissance N+1.
                </p>
                <div className="flex flex-wrap items-end gap-2">
                  <div className="flex-1 min-w-[120px]">
                    <label className="block text-xs text-gray-500 mb-1">Valeur</label>
                    <Input
                      type="number"
                      value={increaseValue}
                      onChange={(e) => setIncreaseValue(e.target.value)}
                      placeholder={increaseUnit === 'pct' ? '+5' : '+500'}
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Unité</label>
                    <div className="inline-flex rounded-lg border border-gray-200 overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setIncreaseUnit('pct')}
                        className={`px-3 py-2 text-sm ${
                          increaseUnit === 'pct'
                            ? 'bg-vz-teal text-white'
                            : 'bg-white text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        %
                      </button>
                      <button
                        type="button"
                        onClick={() => setIncreaseUnit('eur')}
                        className={`px-3 py-2 text-sm ${
                          increaseUnit === 'eur'
                            ? 'bg-vz-teal text-white'
                            : 'bg-white text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        €
                      </button>
                    </div>
                  </div>
                  <Button variant="outline" onClick={applyIncreaseToGrid}>
                    Appliquer
                  </Button>
                </div>
              </div>

              <div className="mt-4 flex gap-2 justify-end">
                <Button onClick={saveYearGrid} disabled={yearGridSaving}>
                  {yearGridSaving ? 'Enregistrement…' : 'Enregistrer le tableau'}
                </Button>
              </div>
            </Card>

            <Card title="Objectif mensuel — saisie ponctuelle">
              <p className="text-sm text-gray-500 mb-4">
                Ancienne saisie mois-par-mois (gardée pour les ajustements
                ciblés avec notes).
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm text-gray-500 mb-1">Année</label>
                  <Input
                    type="number"
                    value={cahierYear}
                    onChange={(e) => setCahierYear(parseInt(e.target.value) || now.getFullYear())}
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-500 mb-1">Mois</label>
                  <select
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
                    value={cahierMonth}
                    onChange={(e) => setCahierMonth(parseInt(e.target.value))}
                  >
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                      <option key={m} value={m}>
                        {new Date(2000, m - 1, 1).toLocaleDateString('fr-FR', { month: 'long' })}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-500 mb-1">Objectif CA (€)</label>
                  <Input
                    type="number"
                    value={cahierTarget}
                    onChange={(e) => setCahierTarget(e.target.value)}
                    placeholder="ex : 8000"
                  />
                </div>
              </div>
              <div className="mt-4">
                <label className="block text-sm text-gray-500 mb-1">Notes (optionnel)</label>
                <Input
                  type="text"
                  value={cahierNotes}
                  onChange={(e) => setCahierNotes(e.target.value)}
                  placeholder="ex : boost printemps"
                />
              </div>
              <div className="mt-4 flex gap-2">
                <Button onClick={saveCahierTarget} disabled={cahierLoading}>
                  {cahierLoading ? 'Enregistrement...' : 'Enregistrer'}
                </Button>
                <Button variant="outline" onClick={loadCahierData} disabled={cahierLoading}>
                  Recharger
                </Button>
              </div>
            </Card>

            <Card title="Distribution des ventes par jour de la semaine">
              <p className="text-sm text-gray-500 mb-4">
                Poids calcules automatiquement a partir des 12 dernieres semaines
                de ventes. En cas de donnees insuffisantes, un profil par defaut
                retail mode est applique.
              </p>
              {cahierWeights && (
                <>
                  <div className="flex items-end gap-2 h-32 mb-4">
                    {cahierWeights.weights.map((w, i) => (
                      <div key={i} className="flex-1 flex flex-col items-center">
                        <div className="flex-1 w-full flex items-end">
                          <div
                            className="w-full bg-vz-teal rounded-t"
                            style={{ height: `${Math.max(4, w * 300)}%` }}
                            title={`${(w * 100).toFixed(1)}%`}
                          />
                        </div>
                        <div className="text-[10px] text-gray-500 mt-1 capitalize">
                          {cahierWeights.weekdays[i].slice(0, 3)}
                        </div>
                        <div className="text-[10px] font-medium text-black">
                          {(w * 100).toFixed(0)}%
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between items-center text-xs text-gray-500">
                    <span>
                      Source :{' '}
                      <span className={cahierWeights.source === 'historical' ? 'text-vz-teal font-medium' : 'text-amber-600 font-medium'}>
                        {cahierWeights.source === 'historical'
                          ? `${cahierWeights.sample_size_weeks} semaines historiques`
                          : 'Profil par defaut (pas assez de donnees)'}
                      </span>
                    </span>
                    <Button variant="outline" onClick={recomputeWeights} disabled={cahierLoading}>
                      Recalculer
                    </Button>
                  </div>
                </>
              )}
            </Card>

            <Card title="Aperçu des objectifs du mois">
              <p className="text-sm text-gray-500 mb-3">
                Objectif quotidien = Objectif mensuel ÷ nombre de jours
                d&apos;ouverture du mois. Les jours fermés (poids 0) sont
                exclus.
              </p>
              {cahierWeights && cahierTarget && (() => {
                const monthlyTarget = parseFloat(cahierTarget) || 0;
                const daysInMonth = new Date(cahierYear, cahierMonth, 0).getDate();
                let openingDays = 0;
                for (let d = 1; d <= daysInMonth; d++) {
                  const jsWd = new Date(cahierYear, cahierMonth - 1, d).getDay();
                  const wd = (jsWd + 6) % 7;
                  if ((cahierWeights.weights[wd] || 0) > 0) openingDays++;
                }
                const dailyTarget = openingDays > 0 ? monthlyTarget / openingDays : 0;
                return (
                  <div className="grid grid-cols-7 gap-2 text-xs">
                    {cahierWeights.weekdays.map((label, i) => {
                      const isOpen = (cahierWeights.weights[i] || 0) > 0;
                      return (
                        <div key={i} className="text-center">
                          <div className="text-gray-500 capitalize">{label.slice(0, 3)}</div>
                          <div className={`font-bold font-mono ${isOpen ? 'text-vz-teal' : 'text-gray-300'}`}>
                            {isOpen ? `${dailyTarget.toFixed(0)} €` : 'fermé'}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
              <p className="mt-3 text-xs text-gray-400">
                Jours d&apos;ouverture du mois sélectionné :{' '}
                {(() => {
                  if (!cahierWeights) return '—';
                  const daysInMonth = new Date(cahierYear, cahierMonth, 0).getDate();
                  let openingDays = 0;
                  for (let d = 1; d <= daysInMonth; d++) {
                    const jsWd = new Date(cahierYear, cahierMonth - 1, d).getDay();
                    const wd = (jsWd + 6) % 7;
                    if ((cahierWeights.weights[wd] || 0) > 0) openingDays++;
                  }
                  return `${openingDays} jours`;
                })()}
              </p>
            </Card>
          </div>
        )}

        {/* FIDELITE TAB */}
        {tab === 'fidelite' && (
          <div className="space-y-6">
            <Card title="Programme fidelite — souscription">
              <p className="text-sm text-gray-500 mb-4">
                Choisissez comment les nouveaux membres adherent a la carte de fidelite Vintiz.
                Le bouton &laquo;&nbsp;Souscription fidelite&nbsp;&raquo; au POS suivra cette regle.
              </p>
              <div className="space-y-3">
                <label className="flex items-start gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    name="loyalty-mode"
                    className="mt-1"
                    checked={loyaltyMode === 'free'}
                    onChange={() => setLoyaltyMode('free')}
                  />
                  <div>
                    <div className="font-medium text-black">Adhesion gratuite</div>
                    <div className="text-sm text-gray-500">Toute cliente peut adherer immediatement, sans frais.</div>
                  </div>
                </label>
                <label className="flex items-start gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    name="loyalty-mode"
                    className="mt-1"
                    checked={loyaltyMode === 'paid'}
                    onChange={() => setLoyaltyMode('paid')}
                  />
                  <div className="flex-1">
                    <div className="font-medium text-black">Adhesion payante</div>
                    <div className="text-sm text-gray-500 mb-2">La carte est facturee a la souscription.</div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">Prix carte (€)</span>
                      <Input
                        type="number"
                        step="0.50"
                        min="0"
                        value={loyaltyPriceEuros}
                        onChange={(e) => setLoyaltyPriceEuros(e.target.value)}
                        disabled={loyaltyMode !== 'paid'}
                        className="max-w-[120px]"
                      />
                    </div>
                  </div>
                </label>
                <label className="flex items-start gap-3 p-3 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50">
                  <input
                    type="radio"
                    name="loyalty-mode"
                    className="mt-1"
                    checked={loyaltyMode === 'first_purchase'}
                    onChange={() => setLoyaltyMode('first_purchase')}
                  />
                  <div className="flex-1">
                    <div className="font-medium text-black">Offerte au 1er achat</div>
                    <div className="text-sm text-gray-500 mb-2">Souscription gratuite a partir d&apos;un panier minimum.</div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">Seuil panier (€)</span>
                      <Input
                        type="number"
                        step="1"
                        min="0"
                        value={loyaltyThresholdEuros}
                        onChange={(e) => setLoyaltyThresholdEuros(e.target.value)}
                        disabled={loyaltyMode !== 'first_purchase'}
                        className="max-w-[120px]"
                      />
                    </div>
                  </div>
                </label>
              </div>
              {/* Time window — outside it, the configured mode reverts to "free" */}
              <div className="mt-5 p-3 border border-vz-line rounded-lg bg-vz-bg/50">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={loyaltyWindowEnabled}
                    onChange={(e) => setLoyaltyWindowEnabled(e.target.checked)}
                    className="w-5 h-5 accent-vz-teal"
                  />
                  <div>
                    <div className="font-medium text-black">Limiter cette configuration à une plage temporelle</div>
                    <div className="text-xs text-gray-500">
                      En dehors de la plage, on revient au mode &laquo;&nbsp;adhésion gratuite&nbsp;&raquo; (configuration par défaut).
                    </div>
                  </div>
                </label>
                {loyaltyWindowEnabled && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Du</label>
                      <input
                        type="date"
                        value={loyaltyWindowStart}
                        onChange={(e) => setLoyaltyWindowStart(e.target.value)}
                        className="w-full min-h-[48px] px-3 py-2 rounded-lg border border-gray-300 bg-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Au</label>
                      <input
                        type="date"
                        value={loyaltyWindowEnd}
                        onChange={(e) => setLoyaltyWindowEnd(e.target.value)}
                        className="w-full min-h-[48px] px-3 py-2 rounded-lg border border-gray-300 bg-white"
                      />
                    </div>
                  </div>
                )}
              </div>
              <div className="mt-4 flex items-center gap-3 flex-wrap">
                <Button onClick={saveLoyaltyConfig} disabled={loyaltySaving}>
                  {loyaltySaving ? 'Enregistrement...' : 'Enregistrer'}
                </Button>
                <span className="text-xs text-gray-500">
                  Mécanique : 1 € hors promotion, solde ou remise = 1 pt · 100 pts = chèque cadeau de 5 € · péremption 24 mois sans activité.
                </span>
              </div>
            </Card>
          </div>
        )}

        {/* SCORING IA TAB */}
        {tab === 'scoring' && (
          <ScoringWeightsPanel />
        )}

        {/* SYSTEM TAB */}
        {tab === 'system' && (
          <div className="space-y-6">
            <SumUpExchangeLogPanel />
            <Card title="Informations systeme">
              <div className="space-y-3 text-sm">
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Version</span>
                  <span className="font-mono text-black">v2.0.0</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Backend</span>
                  <span className="font-mono text-black">Python 3.11 + FastAPI</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Frontend</span>
                  <span className="font-mono text-black">Next.js 15 (PWA)</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Base de donnees</span>
                  <span className="font-mono text-black">PostgreSQL 16</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">IA</span>
                  <span className="font-mono text-black">Claude Vision (Anthropic)</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-gray-500">Conformite</span>
                  <span className="font-mono text-black">NF525 (SHA-256 hash chain)</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-gray-500">Hebergement</span>
                  <span className="font-mono text-black">Scaleway VPS</span>
                </div>
              </div>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
