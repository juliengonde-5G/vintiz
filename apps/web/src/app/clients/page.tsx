'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from '@/components/layout/Sidebar';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import DataTable from '@/components/ui/DataTable';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/format';

interface Client {
  id: string;
  first_name: string;
  last_name: string;
  phone?: string;
  email?: string;
  city?: string;
  email_optin?: boolean;
  sms_optin?: boolean;
  loyalty_active?: boolean;
  loyalty_points?: number;
  membership_number?: string | null;
}

interface Transaction {
  id: string;
  date: string;
  total: number;
  items_count: number;
}

interface TopClient {
  rank: number;
  client_id: string;
  membership_number: string | null;
  loyalty_active: boolean;
  loyalty_points: number;
  first_name: string;
  last_name: string;
  revenue: number;
  transactions_count: number;
}

const TOP_PERIODS = [
  { value: 'day', label: 'Jour' },
  { value: 'week', label: 'Semaine' },
  { value: 'month', label: 'Mois' },
  { value: 'year', label: 'Année' },
] as const;
type TopPeriod = (typeof TOP_PERIODS)[number]['value'];

const TOP_LIMITS = [10, 20, 50, 100];

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

// Le début de période renvoyé par l'API est déjà en heure boutique
// (Europe/Paris). On formate la partie calendaire de l'ISO telle quelle :
// passer par new Date() la reconvertirait dans le fuseau du navigateur et
// afficherait la veille (ex. « 31/12 » pour un 1er janvier 00:00 Paris).
function formatIsoDay(isoStr: string): string {
  const [y, m, d] = isoStr.slice(0, 10).split('-');
  return d && m && y ? `${d}/${m}/${y}` : isoStr;
}

export default function ClientsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [error, setError] = useState('');

  // New client modal
  const [showNew, setShowNew] = useState(false);
  const [newForm, setNewForm] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
    city: '',
    email_optin: false,
    sms_optin: false,
  });
  const [newError, setNewError] = useState('');
  const [newSubmitting, setNewSubmitting] = useState(false);

  // Client detail modal
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [editForm, setEditForm] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
    city: '',
    email_optin: false,
    sms_optin: false,
  });
  const [editMode, setEditMode] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState('');
  const [clientTransactions, setClientTransactions] = useState<Transaction[]>([]);
  const [loadingTransactions, setLoadingTransactions] = useState(false);

  // Top Clients view (classement par CA sur une période calendaire)
  const [showTop, setShowTop] = useState(false);
  const [topPeriod, setTopPeriod] = useState<TopPeriod>('month');
  const [topLimit, setTopLimit] = useState(10);
  const [topRows, setTopRows] = useState<TopClient[]>([]);
  const [topStart, setTopStart] = useState('');
  const [topLoading, setTopLoading] = useState(false);
  const [topError, setTopError] = useState('');
  const [topExporting, setTopExporting] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchClients = useCallback(async (query?: string) => {
    setLoading(true);
    try {
      const params = query ? `?search=${encodeURIComponent(query)}` : '';
      const res = await api.get(`/api/crm/clients${params}`);
      if (res.ok) {
        const json = await res.json();
        setClients(Array.isArray(json) ? json : json.results || json.data || []);
      } else {
        throw new Error('Erreur');
      }
      setError('');
    } catch {
      setError('Impossible de charger les clients.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchClients(search);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search, fetchClients]);

  // Classement Top Clients — rechargé à chaque changement de période/limite
  useEffect(() => {
    if (!showTop) return;
    let cancelled = false;
    (async () => {
      setTopLoading(true);
      try {
        const res = await api.get(
          `/api/crm/clients/top?period=${topPeriod}&limit=${topLimit}`
        );
        if (!res.ok) throw new Error('Erreur');
        const json = await res.json();
        if (!cancelled) {
          setTopRows(json.results || []);
          setTopStart(json.start || '');
          setTopError('');
        }
      } catch {
        if (!cancelled) setTopError('Impossible de charger le classement des clients.');
      } finally {
        if (!cancelled) setTopLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showTop, topPeriod, topLimit]);

  const handleExportTopCsv = async () => {
    setTopExporting(true);
    try {
      const res = await api.get(
        `/api/crm/clients/top/export?period=${topPeriod}&limit=${topLimit}`
      );
      if (!res.ok) throw new Error('Erreur');
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `vintiz-top-clients-${topPeriod}-${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    } catch {
      setTopError('Export CSV impossible.');
    } finally {
      setTopExporting(false);
    }
  };

  const handleCreateClient = async () => {
    if (!newForm.first_name.trim() || !newForm.last_name.trim()) {
      setNewError('Le nom et le prenom sont obligatoires.');
      return;
    }
    setNewSubmitting(true);
    setNewError('');
    try {
      const res = await api.post('/api/crm/clients', newForm);
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || err?.message || 'Erreur lors de la creation');
      }
      setShowNew(false);
      setNewForm({ first_name: '', last_name: '', phone: '', email: '', city: '', email_optin: false, sms_optin: false });
      fetchClients(search);
    } catch (err) {
      setNewError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setNewSubmitting(false);
    }
  };

  const openDetail = async (client: Client) => {
    setSelectedClient(client);
    setEditForm({
      first_name: client.first_name,
      last_name: client.last_name,
      phone: client.phone || '',
      email: client.email || '',
      city: client.city || '',
      email_optin: client.email_optin || false,
      sms_optin: client.sms_optin || false,
    });
    setEditMode(false);
    setEditError('');
    setShowDetail(true);
    // Fetch transactions
    setLoadingTransactions(true);
    try {
      const res = await api.get(`/api/crm/clients/${client.id}/transactions`);
      if (res.ok) {
        const json = await res.json();
        setClientTransactions(Array.isArray(json) ? json : json.results || json.data || []);
      } else {
        setClientTransactions([]);
      }
    } catch {
      setClientTransactions([]);
    } finally {
      setLoadingTransactions(false);
    }
  };

  const handleUpdateClient = async () => {
    if (!selectedClient) return;
    setEditSubmitting(true);
    setEditError('');
    try {
      const res = await api.put(`/api/crm/clients/${selectedClient.id}`, editForm);
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || err?.message || 'Erreur lors de la modification');
      }
      const updated = await res.json();
      setSelectedClient(updated);
      setEditMode(false);
      fetchClients(search);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : 'Erreur inconnue');
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleActivateLoyalty = async () => {
    if (!selectedClient) return;
    try {
      const res = await api.post(`/api/crm/clients/${selectedClient.id}/loyalty/activate`, {});
      if (res.ok) {
        const updated = await res.json();
        setSelectedClient(updated);
        fetchClients(search);
      }
    } catch {
      // silent
    }
  };

  const columns = [
    {
      key: 'last_name',
      header: 'Nom',
      render: (_: unknown, row: Record<string, unknown>) =>
        `${row.first_name || ''} ${row.last_name || ''}`,
    },
    { key: 'phone', header: 'Telephone' },
    { key: 'email', header: 'Email' },
    { key: 'city', header: 'Ville' },
    {
      key: 'loyalty_active',
      header: 'Fidelite',
      render: (val: unknown) =>
        val ? (
          <Badge variant="sold">Active</Badge>
        ) : (
          <Badge variant="default">Inactive</Badge>
        ),
    },
  ];

  const tableData = clients.map((c) => ({
    ...c,
    id: c.id,
    first_name: c.first_name,
    last_name: c.last_name,
    phone: c.phone || '',
    email: c.email || '',
    city: c.city || '',
    loyalty_active: c.loyalty_active,
  }));

  const topColumns = [
    {
      key: 'rank',
      header: '#',
      className: 'w-14',
      render: (val: unknown) => {
        const rank = val as number;
        return rank <= 3 ? (
          <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-vz-teal-soft text-vz-teal font-bold text-sm">
            {rank}
          </span>
        ) : (
          <span className="font-mono text-gray-500 pl-2">{rank}</span>
        );
      },
    },
    {
      key: 'membership_number',
      header: 'N° fidélité',
      render: (val: unknown) =>
        val ? (
          <span className="font-mono text-black">{val as string}</span>
        ) : (
          <span className="text-gray-400">—</span>
        ),
    },
    { key: 'last_name', header: 'Nom' },
    { key: 'first_name', header: 'Prénom' },
    {
      key: 'loyalty_points',
      header: 'Points fidélité',
      render: (val: unknown, row: Record<string, unknown>) =>
        row.loyalty_active ? (
          <span className="font-bold text-vz-teal">{val as number}</span>
        ) : (
          <span className="text-gray-400">—</span>
        ),
    },
    {
      key: 'revenue',
      header: 'CA total',
      render: (val: unknown) => (
        <span className="font-bold text-black">{formatCurrency(val as number)}</span>
      ),
    },
  ];

  const topTableData = topRows.map((r) => ({ ...r, id: r.client_id }));

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 px-4 pt-16 pb-6 md:p-8">
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-black">
              {showTop ? 'Top Clients' : 'Clients'}
            </h1>
            <p className="text-gray-500 mt-1">
              {showTop
                ? 'Classement par chiffre d’affaires généré sur la période'
                : 'Gestion CRM et fidelite'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setShowTop((v) => !v)}>
              {showTop ? (
                <>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                    <line x1="19" y1="12" x2="5" y2="12" />
                    <polyline points="12 19 5 12 12 5" />
                  </svg>
                  Tous les clients
                </>
              ) : (
                <>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                    <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
                    <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
                    <path d="M4 22h16" />
                    <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
                    <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
                    <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
                  </svg>
                  Top Clients
                </>
              )}
            </Button>
            {!showTop && (
              <Button
                onClick={() => {
                  setNewForm({ first_name: '', last_name: '', phone: '', email: '', city: '', email_optin: false, sms_optin: false });
                  setNewError('');
                  setShowNew(true);
                }}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                Nouveau client
              </Button>
            )}
          </div>
        </div>

        {!showTop && error && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
        )}
        {showTop && topError && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg">{topError}</div>
        )}

        {!showTop && (
          <>
            {/* Search */}
            <Card className="mb-6">
              <Input
                placeholder="Rechercher un client (nom, telephone, email)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                icon={
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="11" cy="11" r="8" />
                    <line x1="21" y1="21" x2="16.65" y2="16.65" />
                  </svg>
                }
              />
            </Card>

            {/* Client Table */}
            {loading ? (
              <Card>
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="animate-pulse bg-gray-200 rounded-lg h-12 w-full" />
                  ))}
                </div>
              </Card>
            ) : (
              <DataTable
                columns={columns}
                data={tableData}
                emptyMessage="Aucun client trouve"
                actions={(row) => (
                  <div className="flex gap-1">
                    <a
                      href={`/clients/${(row as unknown as Client).id}`}
                      className="inline-flex items-center px-3 py-1 text-xs font-medium rounded-lg bg-vz-teal text-white hover:bg-vz-teal/90"
                    >
                      Fiche
                    </a>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => openDetail(row as unknown as Client)}
                    >
                      Aperçu
                    </Button>
                  </div>
                )}
              />
            )}
          </>
        )}

        {showTop && (
          <>
            {/* Filtres période + limite + export */}
            <Card className="mb-6">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs uppercase tracking-wide text-gray-500 font-medium">Période</span>
                    {TOP_PERIODS.map((p) => (
                      <button
                        key={p.value}
                        onClick={() => setTopPeriod(p.value)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                          topPeriod === p.value
                            ? 'bg-vz-teal text-white border-vz-teal'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-vz-teal hover:text-vz-teal'
                        }`}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs uppercase tracking-wide text-gray-500 font-medium">Afficher</span>
                    {TOP_LIMITS.map((n) => (
                      <button
                        key={n}
                        onClick={() => setTopLimit(n)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                          topLimit === n
                            ? 'bg-vz-teal text-white border-vz-teal'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-vz-teal hover:text-vz-teal'
                        }`}
                      >
                        Top {n}
                      </button>
                    ))}
                  </div>
                </div>
                <Button
                  variant="outline"
                  onClick={handleExportTopCsv}
                  disabled={topExporting || topLoading || topRows.length === 0}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="7 10 12 15 17 10" />
                    <line x1="12" y1="15" x2="12" y2="3" />
                  </svg>
                  {topExporting ? 'Export...' : 'Exporter CSV'}
                </Button>
              </div>
              {topStart && (
                <p className="text-xs text-gray-400 mt-3">
                  Ventes moins remboursements depuis le {formatIsoDay(topStart)} — les ventes
                  sans fiche client ne sont pas comptées.
                </p>
              )}
            </Card>

            {/* Top Clients Table */}
            {topLoading ? (
              <Card>
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="animate-pulse bg-gray-200 rounded-lg h-12 w-full" />
                  ))}
                </div>
              </Card>
            ) : (
              <DataTable
                columns={topColumns}
                data={topTableData}
                emptyMessage="Aucune vente cliente sur la période"
                actions={(row) => (
                  <a
                    href={`/clients/${(row as unknown as TopClient).client_id}`}
                    className="inline-flex items-center px-3 py-1 text-xs font-medium rounded-lg bg-vz-teal text-white hover:bg-vz-teal/90"
                  >
                    Fiche
                  </a>
                )}
              />
            )}
          </>
        )}
      </main>

      {/* New Client Modal */}
      <Modal
        open={showNew}
        onClose={() => setShowNew(false)}
        title="Nouveau client"
        actions={
          <Button onClick={handleCreateClient} disabled={newSubmitting}>
            {newSubmitting ? 'Creation...' : 'Creer'}
          </Button>
        }
      >
        <div className="space-y-4">
          {newError && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{newError}</div>
          )}
          <Input
            label="Prenom"
            placeholder="Prenom"
            value={newForm.first_name}
            onChange={(e) => setNewForm((f) => ({ ...f, first_name: e.target.value }))}
          />
          <Input
            label="Nom"
            placeholder="Nom"
            value={newForm.last_name}
            onChange={(e) => setNewForm((f) => ({ ...f, last_name: e.target.value }))}
          />
          <Input
            label="Telephone"
            placeholder="06 12 34 56 78"
            value={newForm.phone}
            onChange={(e) => setNewForm((f) => ({ ...f, phone: e.target.value }))}
          />
          <Input
            label="Email"
            type="email"
            placeholder="email@exemple.com"
            value={newForm.email}
            onChange={(e) => setNewForm((f) => ({ ...f, email: e.target.value }))}
          />
          <Input
            label="Ville"
            placeholder="Ville"
            value={newForm.city}
            onChange={(e) => setNewForm((f) => ({ ...f, city: e.target.value }))}
          />
          <div className="space-y-2 pt-2 border-t border-gray-100">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Consentement marketing (RGPD)</p>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={newForm.email_optin}
                onChange={(e) => setNewForm((f) => ({ ...f, email_optin: e.target.checked }))}
                className="w-4 h-4 rounded border-gray-300 text-vz-teal focus:ring-vz-teal"
              />
              <span className="text-sm text-gray-700">Accepte de recevoir des emails marketing</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={newForm.sms_optin}
                onChange={(e) => setNewForm((f) => ({ ...f, sms_optin: e.target.checked }))}
                className="w-4 h-4 rounded border-gray-300 text-vz-teal focus:ring-vz-teal"
              />
              <span className="text-sm text-gray-700">Accepte de recevoir des SMS</span>
            </label>
          </div>
        </div>
      </Modal>

      {/* Client Detail Modal */}
      <Modal
        open={showDetail}
        onClose={() => {
          setShowDetail(false);
          setEditMode(false);
        }}
        title={
          selectedClient
            ? `${selectedClient.first_name} ${selectedClient.last_name}`
            : 'Client'
        }
        actions={
          editMode ? (
            <>
              <Button variant="outline" onClick={() => setEditMode(false)}>
                Annuler
              </Button>
              <Button onClick={handleUpdateClient} disabled={editSubmitting}>
                {editSubmitting ? 'Enregistrement...' : 'Enregistrer'}
              </Button>
            </>
          ) : (
            <Button variant="outline" onClick={() => setEditMode(true)}>
              Modifier
            </Button>
          )
        }
      >
        {selectedClient && (
          <div className="space-y-6">
            {editError && (
              <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">{editError}</div>
            )}

            {/* Client Info */}
            {editMode ? (
              <div className="space-y-4">
                <Input
                  label="Prenom"
                  value={editForm.first_name}
                  onChange={(e) => setEditForm((f) => ({ ...f, first_name: e.target.value }))}
                />
                <Input
                  label="Nom"
                  value={editForm.last_name}
                  onChange={(e) => setEditForm((f) => ({ ...f, last_name: e.target.value }))}
                />
                <Input
                  label="Telephone"
                  value={editForm.phone}
                  onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                />
                <Input
                  label="Email"
                  type="email"
                  value={editForm.email}
                  onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                />
                <Input
                  label="Ville"
                  value={editForm.city}
                  onChange={(e) => setEditForm((f) => ({ ...f, city: e.target.value }))}
                />
                <div className="space-y-2 pt-2 border-t border-gray-100">
                  <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Consentement marketing (RGPD)</p>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editForm.email_optin}
                      onChange={(e) => setEditForm((f) => ({ ...f, email_optin: e.target.checked }))}
                      className="w-4 h-4 rounded border-gray-300 text-vz-teal focus:ring-vz-teal"
                    />
                    <span className="text-sm text-gray-700">Accepte de recevoir des emails marketing</span>
                  </label>
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editForm.sms_optin}
                      onChange={(e) => setEditForm((f) => ({ ...f, sms_optin: e.target.checked }))}
                      className="w-4 h-4 rounded border-gray-300 text-vz-teal focus:ring-vz-teal"
                    />
                    <span className="text-sm text-gray-700">Accepte de recevoir des SMS</span>
                  </label>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-sm text-gray-500">Telephone</span>
                  <span className="text-sm text-black">{selectedClient.phone || '-'}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-sm text-gray-500">Email</span>
                  <span className="text-sm text-black">{selectedClient.email || '-'}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-sm text-gray-500">Ville</span>
                  <span className="text-sm text-black">{selectedClient.city || '-'}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-sm text-gray-500">Emails marketing</span>
                  <span className={`text-sm font-medium ${selectedClient.email_optin ? 'text-vz-teal' : 'text-gray-400'}`}>
                    {selectedClient.email_optin ? 'Accepte' : 'Refuse'}
                  </span>
                </div>
                <div className="flex justify-between py-2 border-b border-gray-100">
                  <span className="text-sm text-gray-500">SMS marketing</span>
                  <span className={`text-sm font-medium ${selectedClient.sms_optin ? 'text-vz-teal' : 'text-gray-400'}`}>
                    {selectedClient.sms_optin ? 'Accepte' : 'Refuse'}
                  </span>
                </div>
              </div>
            )}

            {/* Loyalty */}
            <div>
              <h4 className="text-sm font-semibold text-black mb-3">Fidelite</h4>
              {selectedClient.loyalty_active ? (
                <div className="p-4 bg-vz-teal-soft rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Statut</span>
                    <Badge variant="sold">Active</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Points</span>
                    <span className="font-bold text-vz-teal">
                      {selectedClient.loyalty_points ?? 0}
                    </span>
                  </div>
                  {selectedClient.membership_number && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">N carte</span>
                      <span className="font-medium text-black">{selectedClient.membership_number}</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-4 bg-gray-50 rounded-lg flex items-center justify-between">
                  <span className="text-sm text-gray-500">Programme non active</span>
                  <Button size="sm" onClick={handleActivateLoyalty}>
                    Activer
                  </Button>
                </div>
              )}
            </div>

            {/* Purchase History */}
            <div>
              <h4 className="text-sm font-semibold text-black mb-3">Historique d&apos;achats</h4>
              {loadingTransactions ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="animate-pulse bg-gray-200 rounded-lg h-10 w-full" />
                  ))}
                </div>
              ) : clientTransactions.length > 0 ? (
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {clientTransactions.map((tx) => (
                    <div
                      key={tx.id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                    >
                      <div>
                        <p className="text-sm font-medium text-black">
                          {tx.items_count} article{tx.items_count > 1 ? 's' : ''}
                        </p>
                        <p className="text-xs text-gray-500">{formatDate(tx.date)}</p>
                      </div>
                      <p className="font-bold text-vz-teal">{formatCurrency(tx.total)}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400 text-center py-4">Aucun achat</p>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
