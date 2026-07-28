'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import Input from '@/components/ui/Input';
import TransactionDetailModal from '@/components/pos/TransactionDetailModal';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

type Tab = 'synthese' | 'achats' | 'fidelite' | 'gouts' | 'shopper' | 'comms' | 'rgpd' | 'audit';

interface PSProduct {
  id?: string;
  product_id?: string;
  name?: string;
  brand?: string | null;
  size?: string | null;
  color?: string | null;
  sale_price?: number | null;
  price_cents?: number | null;
  score?: number | null;
  photo_url?: string | null;
}

interface PSLive {
  recommendation_set_id?: string;
  message?: string;
  products?: PSProduct[];
  algo_version?: string;
  fallback_used?: boolean;
}

interface PSMessage {
  id: string;
  subject: string | null;
  message: string;
  product_ids: string[];
  products: PSProduct[];
  channel: string;
  status: string;
  backend: string | null;
  created_at: string | null;
}

interface ClientFull {
  client: {
    id: string;
    first_name: string;
    last_name: string;
    email: string | null;
    phone: string | null;
    notes: string | null;
    birth_date: string | null;
    email_optin: boolean;
    sms_optin: boolean;
    rfm_segment: string | null;
    avoir_balance: number;
    deletion_pending: boolean;
    created_at: string | null;
  };
  loyalty: {
    membership_number: string;
    points: number;
    mode: string | null;
    subscribed_at: string | null;
    expires_at: string | null;
    ledger: { id: string; type: string; points: number; description: string | null; created_at: string | null }[];
  } | null;
  taste_profile: {
    favorite_categories: { name: string; count: number; share: number }[];
    favorite_brands: string[];
    favorite_colors: string[];
    size_profile: { haut?: string; bas?: string };
    lifetime_value: number;
    last_visit: string | null;
    days_since_last_visit: number | null;
  };
  qualification: {
    profiling_consent: boolean;
    gender_profile: string | null;
    age_band: string | null;
    season_bias: string | null;
    price_ceiling_cents: number | null;
    price_sensitivity: number | null;
    trend_affinity: number | null;
  };
  transactions: {
    id: string;
    transaction_number: number;
    transaction_type: string;
    total_ttc: number;
    created_at: string | null;
    item_count: number;
    payment_methods: string[];
    is_gift?: boolean;
  }[];
  consents: {
    purpose: string;
    granted: boolean;
    source: string | null;
    policy_version: string | null;
    recorded_at: string | null;
  }[];
  coupons: {
    code: string;
    discount_type: string;
    discount_value: number;
    source: string | null;
    valid_until: string | null;
  }[];
  communications: {
    id: string;
    channel: string;
    kind: string;
    subject: string | null;
    status: string;
    backend: string | null;
    to_address: string | null;
    created_at: string | null;
  }[];
  personal_shopper?: {
    last_message: PSMessage | null;
    sent_count: number;
  };
  audit: {
    id: string;
    action: string;
    entity: string;
    data: unknown;
    user_id: string | null;
    created_at: string | null;
  }[];
  // Sections du payload qui ont planté côté serveur. Tableau vide quand
  // la fiche s'est chargée intégralement.
  errors?: { section: string; error_type: string; message: string }[];
}

const CONSENT_LABELS: Record<string, string> = {
  email_marketing: 'Newsletter',
  sms_marketing: 'SMS',
  profiling: 'Profilage Personal Shopper',
  trend_alerts: 'Alertes nouveautés tendance',
  email_open_tracking: "Suivi d'ouverture des e-mails",
  // data_sharing (B2B) volontairement absent — fonctionnalité jamais activée.
};

const GENDER_LABELS: Record<string, string> = {
  femme: 'Femme',
  homme: 'Homme',
  mixte: 'Mixte',
};

const SEASON_LABELS: Record<string, string> = {
  winter: 'Hiver',
  summer: 'Été',
  all: 'Toute saison',
};

const COMM_KIND_LABELS: Record<string, string> = {
  anniversary: 'Anniversaire',
  new_arrivals: 'Nouveautés',
  trend_alert: 'Alerte tendance',
  magic_link: 'Connexion',
  consent_confirmation: 'Confirmation consentement',
  manual: 'Manuel',
};

const COMM_STATUS_LABELS: Record<string, string> = {
  sent: 'Envoyé',
  simulated: 'Simulé',
  failed: 'Échec',
  skipped: 'Ignoré',
};


function formatDate(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' });
}

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;
  const [data, setData] = useState<ClientFull | null>(null);
  const [tab, setTab] = useState<Tab>('synthese');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openTxId, setOpenTxId] = useState<string | null>(null);

  // --- Personal Shopper tab state ---
  const [psLive, setPsLive] = useState<PSLive | null>(null);
  const [psGated, setPsGated] = useState<string | null>(null);
  const [psLoading, setPsLoading] = useState(false);
  const [psMessages, setPsMessages] = useState<PSMessage[] | null>(null);
  const [psDraft, setPsDraft] = useState('');
  const [psChannel, setPsChannel] = useState<'email' | 'sms' | 'none'>('email');
  const [psSending, setPsSending] = useState(false);
  const [psResult, setPsResult] = useState<{ msg: string; kind: 'success' | 'error' } | null>(null);

  // --- Communication viewer (voir le mail envoyé) ---
  const [openComm, setOpenComm] = useState<{ id: string; subject: string | null; channel: string; kind: string; status: string; to_address: string | null; body_html: string | null; detail: string | null; created_at: string | null } | null>(null);
  const [commLoading, setCommLoading] = useState(false);

  // --- Édition de la fiche client (coordonnées) ---
  const [showEdit, setShowEdit] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editErr, setEditErr] = useState('');
  const [editForm, setEditForm] = useState({
    first_name: '', last_name: '', email: '', phone: '',
    birth_date: '', notes: '', email_optin: false, sms_optin: false,
  });

  const openEdit = () => {
    if (!data) return;
    const c = data.client;
    setEditErr('');
    setEditForm({
      first_name: c.first_name || '',
      last_name: c.last_name || '',
      email: c.email || '',
      phone: c.phone || '',
      birth_date: c.birth_date || '',
      notes: c.notes || '',
      email_optin: c.email_optin,
      sms_optin: c.sms_optin,
    });
    setShowEdit(true);
  };

  const saveEdit = async () => {
    if (!editForm.first_name.trim() || !editForm.last_name.trim()) {
      setEditErr('Le prénom et le nom sont requis.');
      return;
    }
    setSavingEdit(true);
    setEditErr('');
    try {
      const res = await api.put(`/api/crm/clients/${id}`, {
        first_name: editForm.first_name.trim(),
        last_name: editForm.last_name.trim(),
        email: editForm.email.trim() || null,
        phone: editForm.phone.trim() || null,
        birth_date: editForm.birth_date,
        notes: editForm.notes,
        email_optin: editForm.email_optin,
        sms_optin: editForm.sms_optin,
      });
      if (res.ok) {
        setShowEdit(false);
        await load();
      } else {
        const e = await res.json().catch(() => ({}));
        setEditErr(e.detail || 'Erreur lors de l’enregistrement.');
      }
    } catch {
      setEditErr('Erreur de connexion — la fiche n’a pas été enregistrée.');
    }
    setSavingEdit(false);
  };

  const openCommunication = async (commId: string) => {
    setCommLoading(true);
    setOpenComm(null);
    try {
      const res = await api.get(`/api/crm/communications/${commId}`);
      if (res.ok) setOpenComm(await res.json());
    } catch { /* silent */ }
    setCommLoading(false);
  };

  useEffect(() => {
    if (!id) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const loadShopper = async () => {
    if (!id || psLive || psGated || psLoading) return;
    setPsLoading(true);
    setPsGated(null);
    try {
      const [liveRes, histRes] = await Promise.all([
        api.get(`/api/crm/clients/${id}/personal-shopper-v2`),
        api.get(`/api/crm/clients/${id}/personal-shopper/messages`),
      ]);
      if (liveRes.ok) {
        const live: PSLive = await liveRes.json();
        setPsLive(live);
        setPsDraft(live.message || '');
      } else if (liveRes.status === 403) {
        const e = await liveRes.json().catch(() => ({}));
        setPsGated(e.detail || 'Personal Shopper réservé aux membres ayant consenti au profilage.');
      } else {
        setPsGated('Sélection indisponible pour le moment.');
      }
      if (histRes.ok) setPsMessages((await histRes.json()).messages || []);
    } catch {
      setPsGated('Erreur de chargement de la sélection.');
    }
    setPsLoading(false);
  };

  useEffect(() => {
    if (tab === 'shopper') void loadShopper();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const sendShopperSelection = async () => {
    if (!id || !psLive) return;
    setPsSending(true);
    setPsResult(null);
    try {
      const res = await api.post(`/api/crm/clients/${id}/personal-shopper/send`, {
        message: psDraft,
        product_ids: (psLive.products || []).map((p) => p.product_id || p.id).filter(Boolean),
        products: (psLive.products || []).map((p) => ({
          id: p.product_id || p.id,
          name: p.name,
          brand: p.brand,
          sale_price: p.sale_price,
          photo_url: p.photo_url,
        })),
        channel: psChannel,
        algo_version: psLive.algo_version,
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        const st = data.message?.status;
        setPsResult({
          msg: st === 'simulated'
            ? 'Sélection enregistrée (envoi simulé — aucun provider configuré).'
            : psChannel === 'none' ? 'Sélection enregistrée.' : 'Sélection envoyée au client.',
          kind: 'success',
        });
        // Refresh history + bump the synthèse badge without a full reload.
        const histRes = await api.get(`/api/crm/clients/${id}/personal-shopper/messages`);
        if (histRes.ok) setPsMessages((await histRes.json()).messages || []);
        if (data.message) {
          setData((prev) => prev ? {
            ...prev,
            personal_shopper: {
              last_message: data.message,
              sent_count: (prev.personal_shopper?.sent_count ?? 0) + 1,
            },
          } : prev);
        }
      } else {
        setPsResult({ msg: data.message?.status === 'failed' && psChannel === 'email'
          ? 'Échec : la cliente n\'a pas d\'email.' : (data.detail || 'Échec de l\'envoi.'), kind: 'error' });
      }
    } catch {
      setPsResult({ msg: 'Erreur réseau.', kind: 'error' });
    }
    setPsSending(false);
  };

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/api/crm/clients/${id}/full`);
      if (res.ok) {
        setData(await res.json());
      } else if (res.status === 404) {
        setError('Cliente introuvable.');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Sidebar />
        <main className="md:ml-64 p-8">
          <p className="text-gray-500">Chargement…</p>
        </main>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-background">
        <Sidebar />
        <main className="md:ml-64 p-8">
          <p className="text-red-700 mb-4">{error || 'Indisponible.'}</p>
          <Link href="/clients" className="text-vz-teal underline">← Retour</Link>
        </main>
      </div>
    );
  }

  const c = data.client;

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="mb-6 flex items-center gap-3">
          <button onClick={() => router.back()} className="text-sm text-gray-500 underline">
            ← Retour
          </button>
        </div>
        <header className="mb-6 flex flex-col md:flex-row md:items-end md:justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold text-black">
              {c.first_name} {c.last_name}
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              {c.email || 'Sans email'} · {c.phone || 'Sans téléphone'}
              {data.loyalty && ` · ${data.loyalty.membership_number}`}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {c.rfm_segment && (
              <Badge variant="default">RFM · {c.rfm_segment}</Badge>
            )}
            {data.loyalty ? (
              <Badge variant="sold">Membre · {data.loyalty.points} pts</Badge>
            ) : (
              <Badge variant="default">Non membre</Badge>
            )}
            {c.deletion_pending && <Badge variant="default">Suppression en cours</Badge>}
            <Button variant="secondary" onClick={openEdit}>Modifier la fiche</Button>
          </div>
        </header>

        {/* Bandeau partial-fail : si une section du payload a planté côté
            serveur, l'API renvoie la fiche quand même avec un tableau
            ``errors`` ; on l'affiche pour que le manager sache ce qui
            manque sans rester sur un 500 aveugle. */}
        {data.errors && data.errors.length > 0 && (
          <div className="mb-6 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-sm">
            <strong>Fiche chargée partiellement.</strong>{' '}
            {data.errors.length} section{data.errors.length > 1 ? 's' : ''} en
            erreur : {data.errors.map((e) => e.section).join(', ')}. Détail
            (à transmettre au support) :
            <pre className="mt-1 font-mono text-[11px] whitespace-pre-wrap">
              {data.errors.map((e) => `${e.section}: ${e.error_type} — ${e.message}`).join('\n')}
            </pre>
          </div>
        )}

        <nav className="border-b border-gray-200 mb-6 flex flex-wrap gap-1">
          {([
            ['synthese', 'Synthèse'],
            ['achats', `Achats (${data.transactions.length})`],
            ['fidelite', 'Fidélité'],
            ['gouts', 'Goûts'],
            ['shopper', (data.personal_shopper?.sent_count ?? 0) > 0
              ? `Personal Shopper · ${data.personal_shopper?.sent_count}`
              : 'Personal Shopper'],
            ['comms', `Communications (${data.communications.length})`],
            ['rgpd', 'RGPD'],
            ['audit', `Audit (${data.audit.length})`],
          ] as [Tab, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={
                'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors relative ' +
                (tab === key
                  ? 'border-vz-teal text-vz-teal'
                  : 'border-transparent text-gray-500 hover:text-black')
              }
            >
              {label}
              {key === 'shopper' && (data.personal_shopper?.sent_count ?? 0) > 0 && (
                <span className="ml-1 inline-block w-1.5 h-1.5 rounded-full bg-vz-accent align-middle" />
              )}
            </button>
          ))}
        </nav>

        {tab === 'synthese' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card title="Coordonnées">
              <Row label="Email" value={c.email || '—'} />
              <Row label="Téléphone" value={c.phone || '—'} />
              <Row label="Newsletter" value={c.email_optin ? 'Opt-in' : 'Refus'} />
              <Row label="SMS" value={c.sms_optin ? 'Opt-in' : 'Refus'} />
              <Row label="Notes" value={c.notes || '—'} />
              <Row label="Cliente créée le" value={formatDate(c.created_at)} />
            </Card>
            <Card title="Indicateurs">
              <Row label="Avoir disponible" value={formatCurrency(c.avoir_balance)} />
              <Row label="Lifetime value" value={formatCurrency(data.taste_profile.lifetime_value || 0)} />
              <Row label="Dernière visite" value={formatDate(data.taste_profile.last_visit)} />
              <Row
                label="Jours depuis"
                value={
                  data.taste_profile.days_since_last_visit !== null
                    ? `${data.taste_profile.days_since_last_visit} j`
                    : '—'
                }
              />
              <Row label="Segment RFM" value={c.rfm_segment || '—'} />
            </Card>
            {data.coupons.length > 0 && (
              <Card title="Coupons actifs">
                <ul className="space-y-2 text-sm">
                  {data.coupons.map((cp) => (
                    <li key={cp.code} className="flex items-center justify-between gap-3">
                      <span className="font-mono">{cp.code}</span>
                      <span className="text-vz-teal font-medium">
                        {cp.discount_type === 'amount'
                          ? `-${cp.discount_value} €`
                          : `-${cp.discount_value} %`}
                      </span>
                      <span className="text-xs text-gray-500">
                        jusqu&apos;au {formatDate(cp.valid_until)}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            {data.personal_shopper?.last_message && (
              <Card title="Personal Shopper" className="md:col-span-2 border-l-4 border-vz-accent">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <p className="text-sm text-vz-ink">
                      Dernière sélection {data.personal_shopper.last_message.channel === 'none' ? 'préparée' : 'envoyée'} le{' '}
                      <strong>{formatDate(data.personal_shopper.last_message.created_at)}</strong>
                      {' '}· {data.personal_shopper.last_message.product_ids.length} pièce(s)
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {data.personal_shopper.sent_count} sélection(s) au total.
                    </p>
                  </div>
                  <Button variant="outline" onClick={() => setTab('shopper')}>
                    Voir la sélection
                  </Button>
                </div>
              </Card>
            )}
          </div>
        )}

        {tab === 'shopper' && (
          <div className="space-y-4">
            {psResult && (
              <div role="status" className={`px-4 py-3 rounded-xl text-sm font-medium ${psResult.kind === 'success' ? 'bg-vz-teal text-white' : 'bg-red-600 text-white'}`}>
                {psResult.msg}
              </div>
            )}

            <Card title="Sélection proposée par le Personal Shopper">
              {psLoading ? (
                <p className="text-sm text-gray-500 py-4">Calcul de la sélection…</p>
              ) : psGated ? (
                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200">
                  <p className="text-sm text-amber-800 font-medium">Personal Shopper indisponible</p>
                  <p className="text-xs text-amber-700 mt-1">{psGated}</p>
                  <p className="text-xs text-amber-700 mt-1">
                    Conditions : cliente membre fidélité + consentement au profilage (onglet RGPD).
                  </p>
                </div>
              ) : psLive ? (
                <div className="space-y-4">
                  {psLive.message && (
                    <div className="p-3 rounded-xl bg-vz-teal-soft/40 border border-vz-teal-soft">
                      <p className="text-[11px] uppercase tracking-wide text-vz-ink-mute mb-1">Message du Personal Shopper</p>
                      <p className="text-sm text-vz-ink whitespace-pre-line">{psLive.message}</p>
                      {psLive.fallback_used && (
                        <p className="text-[11px] text-vz-ink-mute mt-1">(message généré sans IA — repli déterministe)</p>
                      )}
                    </div>
                  )}
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {(psLive.products || []).map((p) => (
                      <div key={(p.product_id || p.id) as string} className="rounded-xl border border-vz-line overflow-hidden bg-vz-surface">
                        <div className="aspect-square bg-vz-bg-alt flex items-center justify-center overflow-hidden">
                          {p.photo_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={p.photo_url} alt={p.name || ''} className="w-full h-full object-cover" />
                          ) : (
                            <span className="text-3xl">🧥</span>
                          )}
                        </div>
                        <div className="p-2">
                          <p className="text-xs font-medium text-vz-ink truncate">{p.name}</p>
                          <p className="text-[11px] text-vz-ink-mute truncate">{p.brand || '—'}{p.size ? ` · ${p.size}` : ''}</p>
                          <p className="text-sm font-bold text-vz-teal mt-0.5">
                            {p.sale_price != null ? `${Number(p.sale_price).toFixed(2)} €` : '—'}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                  {(psLive.products || []).length === 0 && (
                    <p className="text-sm text-gray-500">Aucune pièce ne correspond actuellement au profil.</p>
                  )}

                  {/* Send the selection to the client */}
                  <div className="pt-2 border-t border-vz-line">
                    <label className="block text-sm font-medium text-vz-ink mb-1.5">Message à envoyer</label>
                    <textarea
                      value={psDraft}
                      onChange={(e) => setPsDraft(e.target.value)}
                      rows={4}
                      className="w-full px-3 py-2 rounded-lg border border-vz-line text-sm focus:outline-none focus:ring-2 focus:ring-vz-teal"
                    />
                    <div className="flex flex-wrap items-center gap-2 mt-2">
                      <select
                        value={psChannel}
                        onChange={(e) => setPsChannel(e.target.value as 'email' | 'sms' | 'none')}
                        className="px-3 py-2 rounded-lg border border-vz-line text-sm bg-vz-surface"
                      >
                        <option value="email">Par email</option>
                        <option value="sms">Par SMS</option>
                        <option value="none">Enregistrer (présentée en boutique)</option>
                      </select>
                      <Button onClick={sendShopperSelection} disabled={psSending || (psLive.products || []).length === 0}>
                        {psSending ? 'Envoi…' : psChannel === 'none' ? 'Enregistrer la sélection' : 'Envoyer au client'}
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-500 py-4">Indisponible.</p>
              )}
            </Card>

            {/* History of sent selections */}
            <Card title={`Historique des sélections${psMessages ? ` (${psMessages.length})` : ''}`}>
              {!psMessages ? (
                <p className="text-sm text-gray-400 py-2">…</p>
              ) : psMessages.length === 0 ? (
                <p className="text-sm text-gray-400 py-2">Aucune sélection envoyée pour le moment.</p>
              ) : (
                <ul className="divide-y divide-vz-line">
                  {psMessages.map((m) => (
                    <li key={m.id} className="py-3">
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <span className="text-sm text-vz-ink">
                          {formatDate(m.created_at)} · {m.channel === 'none' ? 'En boutique' : m.channel.toUpperCase()}
                          {' · '}{m.product_ids.length} pièce(s)
                        </span>
                        <Badge variant={m.status === 'sent' ? 'sold' : 'default'}>
                          {m.status === 'sent' ? 'Envoyé' : m.status === 'simulated' ? 'Simulé' : m.status === 'saved' ? 'Enregistré' : m.status}
                        </Badge>
                      </div>
                      {m.message && <p className="text-xs text-gray-500 mt-1 line-clamp-2 whitespace-pre-line">{m.message}</p>}
                      {m.products && m.products.length > 0 && (
                        <p className="text-[11px] text-vz-ink-mute mt-1">
                          {m.products.map((p) => p.name).filter(Boolean).join(' · ')}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        )}

        {tab === 'achats' && (
          <Card title="Transactions">
            {data.transactions.length === 0 ? (
              <p className="text-gray-500">Aucune transaction.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-xs text-gray-500">
                  <tr>
                    <th className="text-left p-2">N°</th>
                    <th className="text-left p-2">Date</th>
                    <th className="text-left p-2">Type</th>
                    <th className="text-right p-2">Total</th>
                    <th className="text-right p-2">Articles</th>
                    <th className="text-left p-2">Paiements</th>
                  </tr>
                </thead>
                <tbody>
                  {data.transactions.map((t) => (
                    <tr
                      key={t.id}
                      onClick={() => setOpenTxId(t.id)}
                      className="border-t border-gray-100 cursor-pointer hover:bg-gray-50"
                      title="Voir le détail de l'achat"
                    >
                      <td className="p-2 font-mono text-vz-teal underline">{t.transaction_number}</td>
                      <td className="p-2 text-gray-600">{formatDate(t.created_at)}</td>
                      <td className="p-2">
                        <Badge variant={t.transaction_type === 'refund' ? 'default' : 'sold'}>
                          {t.transaction_type === 'refund' ? 'Retour' : 'Vente'}
                        </Badge>
                        {t.is_gift && (
                          <span className="ml-1 inline-block rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-700">
                            Cadeau · hors-profil
                          </span>
                        )}
                      </td>
                      <td className="p-2 text-right font-medium">{formatCurrency(t.total_ttc)}</td>
                      <td className="p-2 text-right text-gray-600">{t.item_count}</td>
                      <td className="p-2 text-xs text-gray-500">{t.payment_methods.join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        )}

        {tab === 'fidelite' && (
          <div className="space-y-4">
            {data.loyalty ? (
              <>
                <Card title="Carte">
                  <Row label="N° de carte" value={data.loyalty.membership_number} />
                  <Row label="Solde" value={`${data.loyalty.points} points`} />
                  <Row label="Mode souscription" value={data.loyalty.mode || '—'} />
                  <Row label="Adhésion" value={formatDate(data.loyalty.subscribed_at)} />
                  <Row label="Validité" value={formatDate(data.loyalty.expires_at)} />
                </Card>
                <Card title="Mouvements">
                  {data.loyalty.ledger.length === 0 ? (
                    <p className="text-gray-500">Aucun mouvement.</p>
                  ) : (
                    <ul className="text-sm divide-y divide-gray-100">
                      {data.loyalty.ledger.map((tx) => (
                        <li key={tx.id} className="flex items-center justify-between py-2">
                          <span className="text-gray-600 text-xs uppercase tracking-wider">
                            {tx.type}
                          </span>
                          <span className="flex-1 px-3 truncate">{tx.description || '—'}</span>
                          <span className={'font-medium ' + (tx.points >= 0 ? 'text-vz-teal' : 'text-red-600')}>
                            {tx.points >= 0 ? '+' : ''}{tx.points} pts
                          </span>
                          <span className="text-xs text-gray-500 ml-3 shrink-0">
                            {formatDate(tx.created_at)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </>
            ) : (
              <Card title="Carte fidélité"><p className="text-gray-500">Cliente non enrôlée.</p></Card>
            )}
          </div>
        )}

        {tab === 'gouts' && (
          <div className="space-y-4">
          <Card title="Qualification — Personal Shopper">
            {!data.qualification.profiling_consent ? (
              <p className="text-sm text-gray-500">
                Profilage non consenti — les signaux calculés (saison, budget,
                affinité tendance) ne sont pas calculés. Genre/âge déclarés à
                l&apos;onboarding restent visibles.
              </p>
            ) : null}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-1">
              <QualStat label="Genre déclaré" value={GENDER_LABELS[data.qualification.gender_profile || ''] || '—'} />
              <QualStat label="Tranche d'âge" value={data.qualification.age_band || '—'} />
              <QualStat label="Saison" value={SEASON_LABELS[data.qualification.season_bias || ''] || '—'} />
              <QualStat
                label="Budget habituel"
                value={
                  data.qualification.price_ceiling_cents
                    ? formatCurrency(data.qualification.price_ceiling_cents / 100)
                    : '—'
                }
              />
            </div>
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>Affinité tendance</span>
                <span>
                  {data.qualification.trend_affinity !== null
                    ? `${Math.round(data.qualification.trend_affinity * 100)}%`
                    : '—'}
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full bg-vz-teal"
                  style={{ width: `${Math.round((data.qualification.trend_affinity || 0) * 100)}%` }}
                />
              </div>
            </div>
            <p className="mt-3 text-xs text-gray-500">
              Achats exclus du profil (cadeaux) :{' '}
              {data.transactions.filter((t) => t.is_gift).length}
            </p>
          </Card>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card title="Catégories favorites">
              {data.taste_profile.favorite_categories.length === 0 ? (
                <p className="text-gray-500">Pas assez d&apos;achats.</p>
              ) : (
                <ul className="text-sm space-y-1">
                  {data.taste_profile.favorite_categories.map((cat) => (
                    <li key={cat.name} className="flex items-center justify-between">
                      <span className="capitalize">{cat.name}</span>
                      <span className="text-gray-500">
                        {cat.count} achats ({Math.round(cat.share * 100)}%)
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Marques préférées">
              {data.taste_profile.favorite_brands.length === 0 ? (
                <p className="text-gray-500">—</p>
              ) : (
                <p className="text-sm">{data.taste_profile.favorite_brands.join(' · ')}</p>
              )}
            </Card>
            <Card title="Couleurs préférées">
              {data.taste_profile.favorite_colors.length === 0 ? (
                <p className="text-gray-500">—</p>
              ) : (
                <p className="text-sm">{data.taste_profile.favorite_colors.join(' · ')}</p>
              )}
            </Card>
            <Card title="Profil de tailles">
              <Row label="Haut" value={data.taste_profile.size_profile.haut || '—'} />
              <Row label="Bas" value={data.taste_profile.size_profile.bas || '—'} />
            </Card>
          </div>
          </div>
        )}

        {tab === 'comms' && (
          <Card title="Communications envoyées">
            {data.communications.length === 0 ? (
              <p className="text-gray-500">Aucune communication envoyée.</p>
            ) : (
              <>
                <p className="text-xs text-gray-400 mb-2">Cliquez sur une ligne pour voir le message envoyé.</p>
                <table className="w-full text-sm">
                  <thead className="text-xs text-gray-500">
                    <tr>
                      <th className="text-left p-2">Date</th>
                      <th className="text-left p-2">Canal</th>
                      <th className="text-left p-2">Type</th>
                      <th className="text-left p-2">Objet</th>
                      <th className="text-left p-2">Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.communications.map((c) => (
                      <tr key={c.id}
                        onClick={() => openCommunication(c.id)}
                        className="border-t border-gray-100 cursor-pointer hover:bg-vz-bg-alt transition-colors">
                        <td className="p-2 text-gray-600">{formatDate(c.created_at)}</td>
                        <td className="p-2">{c.channel === 'sms' ? '📱 SMS' : '✉️ Email'}</td>
                        <td className="p-2">{COMM_KIND_LABELS[c.kind] || c.kind}</td>
                        <td className="p-2 text-gray-600">{c.subject || '—'}</td>
                        <td className="p-2">
                          <Badge variant={c.status === 'failed' ? 'default' : 'sold'}>
                            {COMM_STATUS_LABELS[c.status] || c.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </Card>
        )}

        {tab === 'rgpd' && (
          <Card title="Consentements (état courant)">
            <ul className="text-sm divide-y divide-gray-100">
              {data.consents.map((c) => (
                <li key={c.purpose} className="flex items-center justify-between py-2">
                  <div>
                    <p className="font-medium">{CONSENT_LABELS[c.purpose] ?? c.purpose}</p>
                    <p className="text-xs text-gray-500">
                      {c.granted ? 'Activé' : 'Désactivé'}
                      {c.recorded_at && ` · ${formatDate(c.recorded_at)}`}
                      {c.source && ` · source ${c.source}`}
                    </p>
                  </div>
                  <Badge variant={c.granted ? 'sold' : 'default'}>
                    {c.granted ? 'Oui' : 'Non'}
                  </Badge>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {tab === 'audit' && (
          <Card title="Journal audit (50 dernières entrées)">
            {data.audit.length === 0 ? (
              <p className="text-gray-500">Aucun événement.</p>
            ) : (
              <ul className="text-xs font-mono divide-y divide-gray-100">
                {data.audit.map((row) => (
                  <li key={row.id} className="py-1.5">
                    <span className="text-gray-500">{formatDate(row.created_at)}</span>
                    {' · '}
                    <strong>{row.action}</strong>
                    {' '}{row.entity}
                    {row.data ? <span className="text-gray-500"> · {JSON.stringify(row.data)}</span> : null}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        )}

        <div className="mt-8 flex flex-wrap gap-2">
          <Button onClick={load} variant="outline" size="sm">
            Recharger
          </Button>
        </div>
      </main>

      <TransactionDetailModal
        transactionId={openTxId}
        onClose={() => setOpenTxId(null)}
        allowLink={false}
      />

      {/* Édition de la fiche client (coordonnées) */}
      <Modal
        open={showEdit}
        onClose={() => setShowEdit(false)}
        title="Modifier la fiche client"
        actions={
          <>
            <Button variant="ghost" onClick={() => setShowEdit(false)} disabled={savingEdit}>
              Annuler
            </Button>
            <Button onClick={saveEdit} disabled={savingEdit}>
              {savingEdit ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          {editErr && (
            <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {editErr}
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Prénom"
              value={editForm.first_name}
              onChange={(e) => setEditForm((f) => ({ ...f, first_name: e.target.value }))}
            />
            <Input
              label="Nom"
              value={editForm.last_name}
              onChange={(e) => setEditForm((f) => ({ ...f, last_name: e.target.value }))}
            />
            <Input
              label="Email"
              type="email"
              value={editForm.email}
              onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
            />
            <Input
              label="Téléphone"
              value={editForm.phone}
              onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
            />
            <Input
              label="Date de naissance"
              type="date"
              value={editForm.birth_date}
              onChange={(e) => setEditForm((f) => ({ ...f, birth_date: e.target.value }))}
            />
          </div>
          <div>
            <label className="block text-[11px] uppercase tracking-[0.12em] font-medium text-vz-ink-mute mb-1.5">
              Notes
            </label>
            <textarea
              className="w-full px-4 py-2.5 rounded-vz border border-vz-line bg-vz-surface text-vz-ink placeholder-vz-ink-mute transition-colors focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
              rows={3}
              value={editForm.notes}
              onChange={(e) => setEditForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>
          <div className="flex flex-wrap gap-4 pt-1">
            <label className="flex items-center gap-2 text-sm text-vz-ink">
              <input
                type="checkbox"
                checked={editForm.email_optin}
                onChange={(e) => setEditForm((f) => ({ ...f, email_optin: e.target.checked }))}
              />
              Newsletter (email)
            </label>
            <label className="flex items-center gap-2 text-sm text-vz-ink">
              <input
                type="checkbox"
                checked={editForm.sms_optin}
                onChange={(e) => setEditForm((f) => ({ ...f, sms_optin: e.target.checked }))}
              />
              SMS marketing
            </label>
          </div>
        </div>
      </Modal>

      {/* Visionneuse du mail/SMS envoyé */}
      {(commLoading || openComm) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => { setOpenComm(null); }}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3 p-4 border-b border-vz-line">
              <div>
                <p className="text-sm font-semibold text-vz-ink">{openComm?.subject || 'Message'}</p>
                <p className="text-xs text-vz-ink-mute">
                  {openComm ? `${COMM_KIND_LABELS[openComm.kind] || openComm.kind} · ${openComm.channel === 'sms' ? 'SMS' : 'Email'}` : ''}
                  {openComm?.to_address ? ` · ${openComm.to_address}` : ''}
                  {openComm?.created_at ? ` · ${formatDate(openComm.created_at)}` : ''}
                </p>
              </div>
              <button onClick={() => setOpenComm(null)} aria-label="Fermer"
                className="text-vz-ink-mute hover:text-vz-ink text-xl leading-none">×</button>
            </div>
            <div className="flex-1 overflow-auto">
              {commLoading ? (
                <p className="text-sm text-gray-500 p-6 text-center">Chargement…</p>
              ) : openComm?.body_html ? (
                <iframe
                  title="Aperçu du message"
                  sandbox=""
                  srcDoc={openComm.body_html}
                  className="w-full h-[60vh] border-0 bg-white"
                />
              ) : (
                <div className="p-6">
                  <p className="text-sm text-gray-600">
                    {openComm?.channel === 'sms'
                      ? 'SMS — le contenu détaillé n\'est pas archivé pour ce message.'
                      : 'Le contenu HTML de ce message n\'a pas été archivé (message antérieur ou type sans aperçu).'}
                  </p>
                  {openComm?.detail && <p className="text-xs text-gray-400 mt-2">{openComm.detail}</p>}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm py-1">
      <span className="text-gray-500">{label}</span>
      <span className="text-black font-medium">{value}</span>
    </div>
  );
}

function QualStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
      <div className="text-[11px] uppercase tracking-wider text-gray-500">{label}</div>
      <div className="mt-1 text-sm font-medium text-black">{value}</div>
    </div>
  );
}
