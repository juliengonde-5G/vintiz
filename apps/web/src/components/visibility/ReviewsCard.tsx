'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface GoogleReview {
  id: string;
  author: string | null;
  rating: number;
  text: string | null;
  occurred_at: string | null;
  fetched_at: string | null;
  reply_text: string | null;
  replied_at: string | null;
}

function ratingDots(rating: number): string {
  return '★'.repeat(Math.max(0, Math.min(5, rating))) +
         '☆'.repeat(Math.max(0, 5 - rating));
}

function formatDate(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });
}

export default function ReviewsCard() {
  const [reviews, setReviews] = useState<GoogleReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [working, setWorking] = useState<string | null>(null);

  // New review form
  const [newAuthor, setNewAuthor] = useState('');
  const [newRating, setNewRating] = useState<number>(5);
  const [newText, setNewText] = useState('');
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/seo/reviews');
      if (res.ok) {
        const data = (await res.json()) as GoogleReview[];
        setReviews(data);
        setDrafts(
          data.reduce<Record<string, string>>((acc, r) => {
            if (r.reply_text) acc[r.id] = r.reply_text;
            return acc;
          }, {}),
        );
        setError('');
      } else {
        setError('Erreur de chargement.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const submitNew = async () => {
    if (!newText.trim() || newRating < 1 || newRating > 5) return;
    setWorking('new');
    try {
      const res = await api.post('/api/seo/reviews', {
        author: newAuthor.trim() || null,
        rating: newRating,
        text: newText.trim(),
      });
      if (res.ok) {
        setNewAuthor('');
        setNewText('');
        setNewRating(5);
        setShowForm(false);
        await load();
      }
    } catch { /* silent */ }
    setWorking(null);
  };

  const suggest = async (id: string) => {
    setWorking(id);
    try {
      const res = await api.post(`/api/seo/reviews/${id}/suggest-reply`, {});
      if (res.ok) {
        const data = await res.json();
        setDrafts((prev) => ({ ...prev, [id]: data.draft }));
      }
    } catch { /* silent */ }
    setWorking(null);
  };

  const saveReply = async (id: string) => {
    const text = (drafts[id] || '').trim();
    if (!text) return;
    setWorking(id);
    try {
      const res = await api.put(`/api/seo/reviews/${id}/reply`, { reply_text: text });
      if (res.ok) await load();
    } catch { /* silent */ }
    setWorking(null);
  };

  const avgRating =
    reviews.length > 0
      ? reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length
      : null;

  return (
    <Card title="Avis Google">
      <div className="flex justify-between items-center mb-3">
        <p className="text-sm">
          {reviews.length > 0 ? (
            <>
              <strong>{avgRating?.toFixed(1)}/5</strong> sur {reviews.length} avis ·{' '}
              <span className="text-yellow-500">{ratingDots(Math.round(avgRating || 0))}</span>
            </>
          ) : (
            <span className="text-gray-500">Aucun avis enregistré.</span>
          )}
        </p>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? 'Annuler' : 'Ajouter un avis'}
        </Button>
      </div>

      {showForm && (
        <div className="mb-4 p-3 bg-vz-bg rounded-lg space-y-2">
          <input
            type="text"
            placeholder="Auteur (optionnel)"
            value={newAuthor}
            onChange={(e) => setNewAuthor(e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded text-sm"
          />
          <div className="flex items-center gap-2">
            <span className="text-sm">Note :</span>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setNewRating(n)}
                className={`w-8 h-8 rounded ${
                  n <= newRating ? 'bg-yellow-400 text-white' : 'bg-white border border-gray-200 text-gray-400'
                }`}
              >
                ★
              </button>
            ))}
          </div>
          <textarea
            placeholder="Texte de l'avis…"
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 border border-gray-200 rounded text-sm"
          />
          <Button
            size="sm"
            onClick={submitNew}
            disabled={working === 'new' || !newText.trim()}
          >
            {working === 'new' ? '…' : 'Enregistrer'}
          </Button>
        </div>
      )}

      {error && (
        <div className="p-2 bg-red-50 text-red-700 rounded text-sm mb-3">{error}</div>
      )}

      {loading ? (
        <p className="text-sm text-gray-400 text-center py-6">Chargement…</p>
      ) : reviews.length === 0 ? null : (
        <ul className="space-y-3">
          {reviews.map((r) => (
            <li key={r.id} className="p-3 border border-gray-200 rounded-lg">
              <div className="flex items-baseline justify-between gap-2 mb-1">
                <p className="text-sm font-medium">
                  {r.author || 'Anonyme'}{' '}
                  <span className="text-yellow-500 text-base ml-1">
                    {ratingDots(r.rating)}
                  </span>
                </p>
                <p className="text-xs text-gray-400">{formatDate(r.occurred_at)}</p>
              </div>
              {r.text && (
                <p className="text-sm text-gray-700 mb-2">{r.text}</p>
              )}

              <div className="mt-2 space-y-2">
                <div className="flex items-center gap-2">
                  <textarea
                    value={drafts[r.id] ?? ''}
                    onChange={(e) =>
                      setDrafts((prev) => ({ ...prev, [r.id]: e.target.value }))
                    }
                    rows={3}
                    placeholder={
                      r.reply_text
                        ? 'Réponse enregistrée'
                        : 'Brouillon de réponse — cliquez sur "Suggérer" pour pré-remplir'
                    }
                    className="flex-1 px-3 py-2 border border-gray-200 rounded text-sm"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => suggest(r.id)}
                    disabled={working === r.id}
                  >
                    Suggérer (Claude)
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => saveReply(r.id)}
                    disabled={working === r.id || !(drafts[r.id] || '').trim()}
                  >
                    {r.reply_text ? 'Mettre à jour' : 'Enregistrer'}
                  </Button>
                </div>
                {r.replied_at && (
                  <p className="text-xs text-gray-400 text-right">
                    Réponse enregistrée le {formatDate(r.replied_at)}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
