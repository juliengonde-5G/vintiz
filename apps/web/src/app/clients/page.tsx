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

interface Client {
  id: string;
  first_name: string;
  last_name: string;
  phone?: string;
  email?: string;
  city?: string;
  loyalty_active?: boolean;
  loyalty_points?: number;
  loyalty_tier?: string;
}

interface Transaction {
  id: string;
  date: string;
  total: number;
  items_count: number;
}

function formatCurrency(value: number): string {
  return value.toFixed(2).replace('.', ',') + '\u00A0\u20AC';
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
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
  });
  const [editMode, setEditMode] = useState(false);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState('');
  const [clientTransactions, setClientTransactions] = useState<Transaction[]>([]);
  const [loadingTransactions, setLoadingTransactions] = useState(false);

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
      setNewForm({ first_name: '', last_name: '', phone: '', email: '', city: '' });
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

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="md:ml-64 p-6 md:p-8">
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-black">Clients</h1>
            <p className="text-gray-500 mt-1">Gestion CRM et fidelite</p>
          </div>
          <Button
            onClick={() => {
              setNewForm({ first_name: '', last_name: '', phone: '', email: '', city: '' });
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
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
        )}

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
              <Button
                size="sm"
                variant="outline"
                onClick={() => openDetail(row as unknown as Client)}
              >
                Voir
              </Button>
            )}
          />
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
              </div>
            )}

            {/* Loyalty */}
            <div>
              <h4 className="text-sm font-semibold text-black mb-3">Fidelite</h4>
              {selectedClient.loyalty_active ? (
                <div className="p-4 bg-teal-50 rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Statut</span>
                    <Badge variant="sold">Active</Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Points</span>
                    <span className="font-bold text-teal">
                      {selectedClient.loyalty_points ?? 0}
                    </span>
                  </div>
                  {selectedClient.loyalty_tier && (
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Niveau</span>
                      <span className="font-medium text-black">{selectedClient.loyalty_tier}</span>
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
                      <p className="font-bold text-teal">{formatCurrency(tx.total)}</p>
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
