'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { api } from '@/lib/api';

interface SocialPost {
  id: string;
  category: 'PRODUIT_STAR' | 'VALEURS' | 'TEMOIGNAGE' | 'ACTU_LOCALE';
  platform: 'instagram' | 'tiktok' | 'both';
  caption: string;
  hashtags: string[];
  best_time: string | null;
  media_brief: string | null;
  used_llm: boolean;
  accepted_at: string | null;
}

interface CurrentPosts {
  iso_week: string;
  posts: SocialPost[];
}

const CATEGORY_LABELS: Record<SocialPost['category'], string> = {
  PRODUIT_STAR: 'Produit star',
  VALEURS: 'Valeurs',
  TEMOIGNAGE: 'Témoignage',
  ACTU_LOCALE: 'Actu locale',
};

const PLATFORM_BADGE: Record<SocialPost['platform'], string> = {
  instagram: '📸 Instagram',
  tiktok: '🎬 TikTok',
  both: '📸 + 🎬 Les deux',
};

export default function SocialPostsCard() {
  const [data, setData] = useState<CurrentPosts | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [acting, setActing] = useState<string | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/api/seo/social-posts/current');
      if (res.ok) {
        setData(await res.json());
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

  const regenerate = async () => {
    setBusy(true);
    try {
      const res = await api.post('/api/seo/social-posts/regenerate', {});
      if (res.ok) await load();
    } catch { /* silent */ }
    setBusy(false);
  };

  const accept = async (postId: string) => {
    setActing(postId);
    try {
      const res = await api.post(`/api/seo/social-posts/${postId}/accept`, {});
      if (res.ok) await load();
    } catch { /* silent */ }
    setActing(null);
  };

  return (
    <Card title="Calendrier éditorial (semaine courante)">
      <div className="flex justify-between items-center mb-3">
        <p className="text-xs text-gray-500">
          {data?.iso_week || '—'} · génération automatique chaque lundi 07:00
        </p>
        <Button size="sm" variant="secondary" onClick={regenerate} disabled={busy}>
          {busy ? 'Génération…' : 'Régénérer'}
        </Button>
      </div>

      {error && <div className="p-2 bg-red-50 text-red-700 rounded text-sm mb-3">{error}</div>}

      {loading ? (
        <p className="text-sm text-gray-400 text-center py-6">Chargement…</p>
      ) : !data || data.posts.length === 0 ? (
        <div className="text-center text-sm text-gray-500 py-6 space-y-3">
          <p>Aucune proposition pour la semaine.</p>
          <Button onClick={regenerate} disabled={busy}>
            Générer maintenant
          </Button>
        </div>
      ) : (
        <ul className="space-y-3">
          {data.posts.map((post) => (
            <li
              key={post.id}
              className={`p-3 border rounded-lg ${
                post.accepted_at ? 'border-teal/50 bg-teal/5' : 'border-gray-200 bg-white'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-2">
                <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-pink-100 text-pink-800">
                  {CATEGORY_LABELS[post.category]}
                </span>
                <span className="text-xs text-gray-500">
                  {PLATFORM_BADGE[post.platform]} · {post.best_time || '—'}
                </span>
              </div>
              <p className="text-sm whitespace-pre-line">{post.caption}</p>
              {post.hashtags.length > 0 && (
                <p className="text-xs text-teal mt-1">
                  {post.hashtags.join(' ')}
                </p>
              )}
              {post.media_brief && (
                <p className="text-xs text-gray-500 mt-2 italic">
                  📷 {post.media_brief}
                </p>
              )}
              <div className="mt-2 flex justify-end">
                <Button
                  size="sm"
                  onClick={() => accept(post.id)}
                  disabled={acting === post.id || !!post.accepted_at}
                >
                  {post.accepted_at ? 'Validé ✓' : acting === post.id ? '…' : 'Valider'}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {data && data.posts.length > 0 && (
        <p className="mt-3 text-xs text-gray-400">
          {data.posts.every(p => p.used_llm)
            ? 'Posts générés par Claude Haiku.'
            : 'Posts générés par template déterministe (clé Anthropic absente / fallback).'}
        </p>
      )}
    </Card>
  );
}
