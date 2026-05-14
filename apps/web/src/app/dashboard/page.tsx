'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import InlineResendButtons from '@/components/pos/InlineResendButtons';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

type BriefingPriority = { title: string; body: string; action_url: string; type: string; priority: number };
type DashboardBriefing = { greeting: string; priorities: BriefingPriority[] } | null;

function BriefingWidget() {
  const [b, setB] = React.useState<DashboardBriefing>(null);
  React.useEffect(() => {
    api.get('/api/ai/briefing').then(async (res) => {
      if (res.ok) setB(await res.json());
    }).catch(() => {});
  }, []);
  if (!b) return null;
  return (
    <div className="rounded-2xl bg-vz-teal text-white p-5 md:p-6 shadow-vz-soft mb-8 relative overflow-hidden">
      <div className="absolute -right-8 -top-8 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-3 gap-3">
          <p className="text-sm font-medium opacity-90">{b.greeting}</p>
          <Link href="/ia" className="text-xs underline hover:opacity-80">Ouvrir le compagnon</Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {b.priorities.slice(0, 3).map((p, i) => (
            <Link key={i} href={p.action_url} className="rounded-xl bg-white/15 hover:bg-white/25 p-3 backdrop-blur-sm transition-colors block">
              <p className="text-xs font-semibold opacity-90 uppercase tracking-wider">{p.type.replace('_', ' ')}</p>
              <p className="font-display font-semibold text-sm mt-1 leading-snug">{p.title}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

interface DashboardData {
  today: { revenue: number; transaction_count: number; avg_basket: number };
  stock: { count: number; value: number };
  top_products_week: { name: string; quantity: number; revenue: number }[];
  recent_transactions: {
    id: string;
    transaction_number: number;
    total_ttc: number;
    type: string;
    created_at: string;
  }[];
}

interface WeatherData {
  current: {
    temp: number;
    feels_like: number;
    humidity: number;
    description: string;
    icon: string;
    wind_speed: number;
  };
  forecast: {
    date: string;
    temp_min: number;
    temp_max: number;
    description: string;
    icon: string;
  }[];
  city: string;
}

interface TransactionDetail {
  id: string;
  transaction_number: number;
  total_ttc: number;
  total_ht: number;
  tax_amount: number;
  type: string;
  created_at: string;
  client?: { id: string; first_name: string; last_name: string; email?: string; phone?: string } | null;
  items: { name: string; quantity: number; unit_price: number; discount_percent: number }[];
  payments: { method: string; amount: number }[];
}


function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, '0');
  const minutes = String(d.getMinutes()).padStart(2, '0');
  return `${day}/${month}/${year} ${hours}:${minutes}`;
}

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' });
}

function methodLabel(m: string): string {
  if (m === 'especes' || m === 'cash') return 'Espèces';
  if (m === 'carte' || m === 'card') return 'CB';
  if (m === 'cheque') return 'Chèque';
  return m;
}

function weatherIconUrl(icon: string): string {
  return `https://openweathermap.org/img/wn/${icon}@2x.png`;
}

function SkeletonBlock({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-200 rounded-lg ${className}`} />;
}

// ── Ticket Detail Modal ──────────────────────────────────────────────────────

function TicketModal({
  ticket,
  onClose,
}: {
  ticket: TransactionDetail;
  onClose: () => void;
}) {
  const [printing, setPrinting] = useState(false);
  const [printResult, setPrintResult] = useState('');

  // Resend (email/SMS) — ad-hoc recipient supported, see /lib/print-ticket
  // and ``InlineResendButtons`` for the shared UI.
  const handleResend = async (channel: 'email' | 'sms', to?: string) => {
    const res = await api.post(`/api/pos/transactions/${ticket.id}/resend`, {
      channel,
      ...(to ? { to } : {}),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || 'Erreur envoi');
    }
  };

  // Send the receipt to the MUNBYN (network or USB depending on the
  // configured connection mode). Replaces the old ``window.open`` +
  // ``win.print()`` path which used the tablet's PDF dialog rather
  // than the thermal printer.
  const handlePrint = async () => {
    setPrinting(true);
    setPrintResult('');
    const { printTransactionTicket } = await import('@/lib/print-ticket');
    const result = await printTransactionTicket(ticket.id, { kickDrawer: false });
    setPrintResult(result.message);
    setPrinting(false);
  };

  // Fallback: open a printable HTML version in a new tab (regular
  // printer / save as PDF). Kept as an escape hatch when the thermal
  // printer is unreachable.
  const handlePrintFallback = () => {
    const win = window.open('', '_blank', 'width=400,height=600');
    if (!win) return;
    win.document.write(`
      <html><head><title>Ticket #${ticket.transaction_number}</title>
      <style>
        body { font-family: monospace; font-size: 12px; margin: 20px; }
        h2 { text-align: center; font-size: 16px; }
        .sep { border-top: 1px dashed #999; margin: 8px 0; }
        .row { display: flex; justify-content: space-between; }
        .total { font-weight: bold; font-size: 14px; }
        .footer { text-align: center; font-size: 11px; color: #666; margin-top: 16px; }
      </style>
      </head><body>
      <h2>VINTIZ</h2>
      <p style="text-align:center">Vernon, Normandie</p>
      <div class="sep"></div>
      <div class="row"><span>Ticket #${ticket.transaction_number}</span><span>${formatDate(ticket.created_at)}</span></div>
      ${ticket.client ? `<div>Client : ${ticket.client.first_name} ${ticket.client.last_name}</div>` : ''}
      <div class="sep"></div>
      ${ticket.items.map(item => `
        <div class="row">
          <span>${item.name}${item.discount_percent > 0 ? ` (-${item.discount_percent}%)` : ''}</span>
          <span>${formatCurrency(item.unit_price * item.quantity * (1 - item.discount_percent / 100))}</span>
        </div>
      `).join('')}
      <div class="sep"></div>
      <div class="row total"><span>TOTAL TTC</span><span>${formatCurrency(ticket.total_ttc)}</span></div>
      <div class="row"><span>dont TVA</span><span>${formatCurrency(ticket.tax_amount)}</span></div>
      <div class="sep"></div>
      ${ticket.payments.map(p => `<div class="row"><span>${methodLabel(p.method)}</span><span>${formatCurrency(p.amount)}</span></div>`).join('')}
      <div class="footer">Merci de votre visite !<br>Boutique de seconde main premium</div>
      </body></html>
    `);
    win.document.close();
    win.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-bold text-black">Ticket #{ticket.transaction_number}</h2>
            <p className="text-sm text-gray-500">{formatDate(ticket.created_at)}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-black transition-colors p-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* Client */}
          {ticket.client && (
            <div className="flex items-center gap-3 p-3 bg-vz-teal-soft rounded-xl">
              <div className="w-9 h-9 rounded-full bg-vz-teal flex items-center justify-center text-white text-sm font-bold shrink-0">
                {ticket.client.first_name[0]}{ticket.client.last_name[0]}
              </div>
              <div>
                <p className="text-sm font-medium text-black">{ticket.client.first_name} {ticket.client.last_name}</p>
                {ticket.client.email && <p className="text-xs text-gray-500">{ticket.client.email}</p>}
                {ticket.client.phone && <p className="text-xs text-gray-500">{ticket.client.phone}</p>}
              </div>
            </div>
          )}

          {/* Items */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Articles</p>
            <div className="space-y-1">
              {ticket.items.map((item, i) => (
                <div key={i} className="flex justify-between text-sm">
                  <span className="text-gray-700">
                    {item.name}
                    {item.quantity > 1 && <span className="text-gray-400"> ×{item.quantity}</span>}
                    {item.discount_percent > 0 && (
                      <span className="ml-1 text-xs text-orange-500">-{item.discount_percent}%</span>
                    )}
                  </span>
                  <span className="font-medium text-black">
                    {formatCurrency(item.unit_price * item.quantity * (1 - item.discount_percent / 100))}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Totals */}
          <div className="border-t border-gray-100 pt-3 space-y-1">
            <div className="flex justify-between text-sm text-gray-500">
              <span>Total HT</span>
              <span>{formatCurrency(ticket.total_ht)}</span>
            </div>
            <div className="flex justify-between text-sm text-gray-500">
              <span>TVA (20%)</span>
              <span>{formatCurrency(ticket.tax_amount)}</span>
            </div>
            <div className="flex justify-between text-base font-bold text-black">
              <span>Total TTC</span>
              <span className="text-vz-teal">{formatCurrency(ticket.total_ttc)}</span>
            </div>
          </div>

          {/* Payments */}
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Paiements</p>
            {ticket.payments.map((p, i) => (
              <div key={i} className="flex justify-between text-sm">
                <span className="text-gray-600">{methodLabel(p.method)}</span>
                <span>{formatCurrency(p.amount)}</span>
              </div>
            ))}
          </div>

          {printResult && (
            <div className={`p-3 rounded-lg text-sm text-center ${
              printResult.toLowerCase().includes('échec') || printResult.toLowerCase().includes('erreur') || printResult.toLowerCase().includes('injoignable')
                ? 'bg-red-50 text-red-600'
                : 'bg-green-50 text-green-700'
            }`}>
              {printResult}
            </div>
          )}

          <InlineResendButtons
            clientEmail={ticket.client?.email ?? null}
            clientPhone={ticket.client?.phone ?? null}
            onResend={handleResend}
          />
        </div>

        {/* Actions */}
        <div className="px-6 pb-6 flex flex-wrap gap-3">
          <Button variant="secondary" size="sm" onClick={handlePrint} disabled={printing}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
              <polyline points="6 9 6 2 18 2 18 9" />
              <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
              <rect x="6" y="14" width="12" height="8" />
            </svg>
            {printing ? 'Impression…' : 'Réimprimer (MUNBYN)'}
          </Button>
          <Button variant="outline" size="sm" onClick={handlePrintFallback}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
              <rect x="4" y="3" width="16" height="18" rx="2" />
              <line x1="8" y1="8" x2="16" y2="8" />
              <line x1="8" y1="12" x2="16" y2="12" />
              <line x1="8" y1="16" x2="12" y2="16" />
            </svg>
            Version A4 / PDF
          </Button>
        </div>
      </div>
    </div>
  );
}

// ── Weather Widget ───────────────────────────────────────────────────────────

function WeatherWidget({ data }: { data: WeatherData }) {
  return (
    <Card title="Météo Vernon">
      <div className="flex items-center gap-4 mb-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={weatherIconUrl(data.current.icon)}
          alt={data.current.description}
          className="w-16 h-16"
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
        />
        <div>
          <p className="text-3xl font-bold text-black">{Math.round(data.current.temp)}°C</p>
          <p className="text-sm text-gray-500 capitalize">{data.current.description}</p>
          <p className="text-xs text-gray-400">Ressenti {Math.round(data.current.feels_like)}°C · Vent {data.current.wind_speed} m/s</p>
        </div>
      </div>
      {data.forecast && data.forecast.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {data.forecast.slice(0, 4).map((day, i) => (
            <div key={i} className="flex flex-col items-center min-w-[60px] p-2 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500 mb-1">{formatDateShort(day.date)}</p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={weatherIconUrl(day.icon)}
                alt={day.description}
                className="w-8 h-8"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
              <p className="text-xs font-medium text-black">{Math.round(day.temp_max)}°</p>
              <p className="text-xs text-gray-400">{Math.round(day.temp_min)}°</p>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── Cahier / Objectif widget ────────────────────────────────────────────────

interface CahierSummary {
  header: { message_du_jour: string | null };
  objectifs_valeur: {
    ca_objectif_jour: number | null;
    ca_n1_jour: number;
    reste_a_faire_mois: number | null;
  };
  performance: {
    ca: number;
    prog_vs_obj_pct: number | null;
    delta_vs_n1_pct: number | null;
  };
}

function CahierStrip() {
  const [summary, setSummary] = useState<CahierSummary | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);

  const today = new Date().toISOString().slice(0, 10);

  const load = useCallback(() => {
    api.get(`/api/cahier/${today}`).then(async (res) => {
      if (res.ok) {
        const payload = await res.json();
        setSummary(payload);
        setDraft(payload.header?.message_du_jour || '');
      }
    }).catch(() => {});
  }, [today]);

  useEffect(() => { load(); }, [load]);

  const saveMsg = async () => {
    setSaving(true);
    const res = await api.put('/api/cahier/daily-text', {
      date: today,
      message_du_jour: draft,
    });
    setSaving(false);
    if (res.ok) {
      setEditing(false);
      load();
    }
  };

  if (!summary) return null;

  const ca = summary.performance.ca;
  const obj = summary.objectifs_valeur.ca_objectif_jour;
  const progPct = summary.performance.prog_vs_obj_pct;
  const deltaN1 = summary.performance.delta_vs_n1_pct;

  return (
    <div className="mb-6 space-y-3">
      {/* Message du jour */}
      <div className="rounded-2xl border border-vz-teal-soft bg-white p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-vz-teal flex-shrink-0">
              Message du jour
            </span>
            {editing ? (
              <input
                autoFocus
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="flex-1 min-w-0 px-2 py-1 border border-gray-200 rounded text-sm"
                placeholder="ex : Tres calme, mise en avant robes"
              />
            ) : (
              <span className="text-sm text-black truncate">
                {summary.header.message_du_jour || <span className="text-gray-400 italic">Aucun message — cliquez pour ajouter</span>}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {editing ? (
              <>
                <Button size="sm" onClick={saveMsg} disabled={saving}>
                  {saving ? '...' : 'OK'}
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setEditing(false); setDraft(summary.header.message_du_jour || ''); }}>
                  Annuler
                </Button>
              </>
            ) : (
              <button onClick={() => setEditing(true)} className="text-xs text-vz-teal underline">
                Modifier
              </button>
            )}
            <Link href="/dashboard/cahier-du-jour" className="text-xs text-vz-teal underline">
              Voir le cahier
            </Link>
          </div>
        </div>
      </div>

      {/* Strip Objectif */}
      <div className="rounded-2xl bg-vz-teal text-white p-5 shadow-vz-soft">
        <div className="flex flex-wrap items-center gap-6">
          <div>
            <p className="text-xs uppercase tracking-wider opacity-80">CA du jour</p>
            <p className="font-display font-bold text-3xl">
              {ca.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })}
            </p>
          </div>
          <div className="flex-1 min-w-[160px]">
            {obj != null ? (
              <>
                <div className="flex justify-between text-xs opacity-90 mb-1">
                  <span>Objectif {obj.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })}</span>
                  <span>{progPct != null ? `${progPct}%` : '—'}</span>
                </div>
                <div className="h-2 bg-white/20 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-white transition-all"
                    style={{ width: `${Math.min(100, Math.max(0, progPct || 0))}%` }}
                  />
                </div>
              </>
            ) : (
              <Link href="/settings" className="text-sm underline">
                Definir un objectif mensuel
              </Link>
            )}
          </div>
          <div className="flex gap-2 flex-wrap">
            {deltaN1 != null && (
              <span className={`px-3 py-1.5 rounded-full text-xs font-semibold ${deltaN1 >= 0 ? 'bg-white/20' : 'bg-red-500/30'}`}>
                {deltaN1 >= 0 ? '+' : ''}{deltaN1}% vs N-1
              </span>
            )}
            {summary.objectifs_valeur.reste_a_faire_mois != null && (
              <span className="px-3 py-1.5 rounded-full text-xs font-semibold bg-white/20">
                Reste {summary.objectifs_valeur.reste_a_faire_mois.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })} ce mois
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(true);
  const [selectedTicket, setSelectedTicket] = useState<TransactionDetail | null>(null);
  const [ticketLoading, setTicketLoading] = useState(false);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await api.get('/api/reports/dashboard');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setError('');
    } catch (e) {
      console.error('dashboard fetch failed', e);
      setError('Impossible de charger le tableau de bord. Vérifiez votre connexion.');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchWeather = useCallback(async () => {
    setWeatherLoading(true);
    try {
      const res = await api.get('/api/admin/weather');
      if (res.ok) setWeather(await res.json());
    } catch (e) {
      // Weather is optional — still log so it shows up in browser devtools / Sentry
      console.warn('weather widget unavailable', e);
    } finally {
      setWeatherLoading(false);
    }
  }, []);

  const openTicket = async (id: string) => {
    setTicketLoading(true);
    try {
      const res = await api.get(`/api/pos/transactions/${id}`);
      if (res.ok) {
        setSelectedTicket(await res.json());
      } else {
        console.warn('ticket fetch returned', res.status);
      }
    } catch (e) {
      console.error('ticket fetch failed', e);
    } finally {
      setTicketLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    fetchWeather();

    // Pause polling when the tab is hidden so we don't burn the
    // OpenWeather quota and DB hits while the manager has the dashboard
    // open in a background tab. Resume + immediate refresh on focus.
    let interval: ReturnType<typeof setInterval> | null = null;
    const start = () => {
      if (interval !== null) return;
      interval = setInterval(fetchDashboard, 60000);
    };
    const stop = () => {
      if (interval === null) return;
      clearInterval(interval);
      interval = null;
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchDashboard();
        start();
      } else {
        stop();
      }
    };
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      start();
    }
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      stop();
    };
  }, [fetchDashboard, fetchWeather]);

  const kpis = data
    ? [
        {
          label: 'CA du jour',
          value: formatCurrency(data.today.revenue),
          icon: (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="1" x2="12" y2="23" />
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
          ),
        },
        {
          label: 'Articles en stock',
          value: String(data.stock.count),
          icon: (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
            </svg>
          ),
        },
        {
          label: "Transactions aujourd'hui",
          value: String(data.today.transaction_count),
          icon: (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
              <line x1="1" y1="10" x2="23" y2="10" />
            </svg>
          ),
        },
        {
          label: 'Panier moyen',
          value: formatCurrency(data.today.avg_basket),
          icon: (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2A8B8B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="9" cy="21" r="1" />
              <circle cx="20" cy="21" r="1" />
              <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
            </svg>
          ),
        },
      ]
    : [];

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        {/* P4-006 — Sticky compact KPI strip on mobile only. The full
            grid below stays the source of truth on desktop. */}
        {data && (
          <div className="md:hidden sticky top-0 z-30 -mx-4 mb-4 px-4 py-2 bg-white/90 backdrop-blur border-b border-gray-200 flex justify-between items-center text-sm">
            <span>
              <span className="text-gray-500 mr-1">CA</span>
              <strong className="text-vz-teal">{formatCurrency(data.today.revenue)}</strong>
            </span>
            <span>
              <span className="text-gray-500 mr-1">Tickets</span>
              <strong>{data.today.transaction_count}</strong>
            </span>
            <span>
              <span className="text-gray-500 mr-1">Panier</span>
              <strong>{formatCurrency(data.today.avg_basket)}</strong>
            </span>
          </div>
        )}

        <div className="mb-8">
          <h1 className="text-2xl font-bold text-black">Tableau de bord</h1>
          <p className="text-gray-500 mt-1">Bienvenue sur Vintiz</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        <BriefingWidget />

        <CahierStrip />

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
          {loading
            ? Array.from({ length: 4 }).map((_, i) => (
                <Card key={i} className="flex items-start gap-4">
                  <SkeletonBlock className="w-14 h-14 shrink-0" />
                  <div className="flex-1 space-y-2">
                    <SkeletonBlock className="h-4 w-24" />
                    <SkeletonBlock className="h-8 w-20" />
                  </div>
                </Card>
              ))
            : kpis.map((kpi) => (
                <Card key={kpi.label} className="flex items-start gap-4">
                  <div className="p-3 bg-vz-teal-soft rounded-lg shrink-0">{kpi.icon}</div>
                  <div>
                    <p className="text-sm text-gray-500">{kpi.label}</p>
                    <p className="text-2xl font-bold text-black mt-1">{kpi.value}</p>
                  </div>
                </Card>
              ))}
        </div>

        <div className="mb-8">
          {/* Recent Transactions — clickable, full width */}
          <div>
            <Card title="10 derniers tickets">
              {ticketLoading && (
                <div className="text-xs text-gray-400 mb-2 text-right">Chargement ticket...</div>
              )}
              {loading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <SkeletonBlock key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : data && data.recent_transactions && data.recent_transactions.length > 0 ? (
                <div className="space-y-2">
                  {data.recent_transactions.slice(0, 10).map((tx) => (
                    <button
                      key={tx.id}
                      onClick={() => openTicket(tx.id)}
                      className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-vz-teal-soft rounded-lg transition-colors cursor-pointer text-left group"
                    >
                      <div>
                        <p className="text-sm font-medium text-black group-hover:text-vz-teal transition-colors">
                          Ticket #{tx.transaction_number}
                        </p>
                        <p className="text-xs text-gray-500">{tx.created_at ? formatDate(tx.created_at) : ''}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <p className="font-bold text-vz-teal">{formatCurrency(tx.total_ttc)}</p>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-gray-400 group-hover:text-vz-teal transition-colors">
                          <polyline points="9 18 15 12 9 6" />
                        </svg>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400 text-center py-4">Aucune transaction</p>
              )}
            </Card>
          </div>
        </div>

        {/* Weather + Quick Actions row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Weather */}
          <div>
            {weatherLoading ? (
              <Card title="Météo Vernon">
                <div className="flex items-center gap-4">
                  <SkeletonBlock className="w-16 h-16 rounded-full" />
                  <div className="space-y-2 flex-1">
                    <SkeletonBlock className="h-8 w-20" />
                    <SkeletonBlock className="h-4 w-32" />
                  </div>
                </div>
              </Card>
            ) : weather ? (
              <WeatherWidget data={weather} />
            ) : (
              <Card title="Météo Vernon">
                <p className="text-gray-400 text-sm text-center py-4">
                  Météo indisponible (configurer OPENWEATHER_API_KEY)
                </p>
              </Card>
            )}
          </div>

          {/* Quick Actions */}
          <Card title="Actions rapides">
            <div className="flex flex-wrap gap-4">
              <Link href="/pos">
                <Button size="lg">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                    <circle cx="9" cy="21" r="1" />
                    <circle cx="20" cy="21" r="1" />
                    <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
                  </svg>
                  Nouvelle vente
                </Button>
              </Link>
              <Link href="/inventory/new">
                <Button variant="secondary" size="lg">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  Ajouter un produit
                </Button>
              </Link>
            </div>
          </Card>
        </div>
      </main>

      {/* Ticket Detail Modal */}
      {selectedTicket && (
        <TicketModal ticket={selectedTicket} onClose={() => setSelectedTicket(null)} />
      )}
    </div>
  );
}
