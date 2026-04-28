'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { api } from '@/lib/api';

type Tab = 'synthese' | 'achats' | 'fidelite' | 'gouts' | 'rgpd' | 'audit';

interface ClientFull {
  client: {
    id: string;
    first_name: string;
    last_name: string;
    email: string | null;
    phone: string | null;
    notes: string | null;
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
  transactions: {
    id: string;
    transaction_number: number;
    transaction_type: string;
    total_ttc: number;
    created_at: string | null;
    item_count: number;
    payment_methods: string[];
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
  audit: {
    id: string;
    action: string;
    entity: string;
    data: unknown;
    user_id: string | null;
    created_at: string | null;
  }[];
}

const CONSENT_LABELS: Record<string, string> = {
  email_marketing: 'Newsletter',
  sms_marketing: 'SMS',
  profiling: 'Profilage Personal Shopper',
  trend_alerts: 'Alertes nouveautés tendance',
  data_sharing: 'Partage B2B',
};

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + ' €';
}

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

  useEffect(() => {
    if (!id) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

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
          <Link href="/clients" className="text-teal underline">← Retour</Link>
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
          <div className="flex flex-wrap gap-2">
            {c.rfm_segment && (
              <Badge variant="default">RFM · {c.rfm_segment}</Badge>
            )}
            {data.loyalty ? (
              <Badge variant="sold">Membre · {data.loyalty.points} pts</Badge>
            ) : (
              <Badge variant="default">Non membre</Badge>
            )}
            {c.deletion_pending && <Badge variant="default">Suppression en cours</Badge>}
          </div>
        </header>

        <nav className="border-b border-gray-200 mb-6 flex flex-wrap gap-1">
          {([
            ['synthese', 'Synthèse'],
            ['achats', `Achats (${data.transactions.length})`],
            ['fidelite', 'Fidélité'],
            ['gouts', 'Goûts'],
            ['rgpd', 'RGPD'],
            ['audit', `Audit (${data.audit.length})`],
          ] as [Tab, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={
                'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ' +
                (tab === key
                  ? 'border-teal text-teal'
                  : 'border-transparent text-gray-500 hover:text-black')
              }
            >
              {label}
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
                      <span className="text-teal font-medium">
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
                    <tr key={t.id} className="border-t border-gray-100">
                      <td className="p-2 font-mono">{t.transaction_number}</td>
                      <td className="p-2 text-gray-600">{formatDate(t.created_at)}</td>
                      <td className="p-2">
                        <Badge variant={t.transaction_type === 'refund' ? 'default' : 'sold'}>
                          {t.transaction_type === 'refund' ? 'Retour' : 'Vente'}
                        </Badge>
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
                          <span className={'font-medium ' + (tx.points >= 0 ? 'text-teal' : 'text-red-600')}>
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
