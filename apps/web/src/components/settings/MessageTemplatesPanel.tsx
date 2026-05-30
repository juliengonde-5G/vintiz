'use client';

import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

interface MessageTemplate {
  id: string;
  key: string;
  channel: string;
  label: string;
  description: string | null;
  subject: string | null;
  body_html: string | null;
  body_text: string | null;
  is_active: boolean;
}

/**
 * Éditeur des templates de messages automatiques (emails / SMS).
 * Variables {var} disponibles listées dans la description de chaque template.
 * Un template désactivé fait retomber l'envoi sur le texte par défaut du code.
 */
export default function MessageTemplatesPanel() {
  const [items, setItems] = useState<MessageTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [flash, setFlash] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/admin/message-templates');
      if (res.ok) {
        setItems(await res.json());
      } else if (res.status === 403) {
        setError('Accès réservé aux administrateurs.');
      } else {
        setError('Impossible de charger les templates.');
      }
    } catch {
      setError('Erreur réseau.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const patch = (id: string, field: keyof MessageTemplate, value: string | boolean) => {
    setItems((prev) => prev.map((t) => (t.id === id ? { ...t, [field]: value } : t)));
  };

  const save = async (t: MessageTemplate) => {
    setSavingId(t.id);
    setFlash('');
    setError('');
    try {
      const res = await api.put(`/api/admin/message-templates/${t.id}`, {
        subject: t.subject,
        body_html: t.body_html,
        body_text: t.body_text,
        is_active: t.is_active,
      });
      if (res.ok) {
        setFlash(`Template « ${t.label} » enregistré.`);
      } else {
        setError("Échec de l'enregistrement.");
      }
    } catch {
      setError('Erreur réseau.');
    }
    setSavingId(null);
  };

  if (loading) return <p className="text-gray-500">Chargement…</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-600">
        Personnalisez les messages automatiques envoyés aux clients. Les
        variables entre accolades (ex. <code>{'{prenom}'}</code>) sont
        remplacées à l&apos;envoi. Un template désactivé revient au texte par
        défaut.
      </p>
      {flash && <div className="p-3 bg-vz-teal/10 text-vz-teal rounded-lg text-sm">{flash}</div>}

      {items.map((t) => (
        <div key={t.id} className="border border-gray-200 rounded-xl p-4 space-y-3 bg-white">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-medium text-black">
                {t.label}{' '}
                <span className="text-xs text-gray-400">
                  ({t.channel === 'sms' ? 'SMS' : 'Email'})
                </span>
              </h3>
              {t.description && (
                <p className="text-xs text-gray-500 mt-0.5">{t.description}</p>
              )}
            </div>
            <label className="flex items-center gap-2 text-xs text-gray-600">
              <input
                type="checkbox"
                checked={t.is_active}
                onChange={(e) => patch(t.id, 'is_active', e.target.checked)}
              />
              Actif
            </label>
          </div>

          {t.channel !== 'sms' && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Objet</label>
              <input
                type="text"
                value={t.subject ?? ''}
                onChange={(e) => patch(t.id, 'subject', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
              />
            </div>
          )}

          {t.channel !== 'sms' && (
            <div>
              <label className="block text-xs text-gray-500 mb-1">Corps (HTML)</label>
              <textarea
                value={t.body_html ?? ''}
                onChange={(e) => patch(t.id, 'body_html', e.target.value)}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
              />
            </div>
          )}

          <div>
            <label className="block text-xs text-gray-500 mb-1">
              {t.channel === 'sms' ? 'Message SMS' : 'Corps (texte brut)'}
            </label>
            <textarea
              value={t.body_text ?? ''}
              onChange={(e) => patch(t.id, 'body_text', e.target.value)}
              rows={t.channel === 'sms' ? 3 : 2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
            />
          </div>

          <button
            type="button"
            onClick={() => save(t)}
            disabled={savingId === t.id}
            className="px-4 py-2 bg-vz-teal text-white rounded-lg text-sm font-medium hover:bg-vz-teal-deep disabled:opacity-50"
          >
            {savingId === t.id ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
      ))}
    </div>
  );
}
