'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';
import { mediaUrl } from '@/lib/format';
import { downscaleImage } from '@/lib/image-resize';

interface Photo {
  id: string;
  url: string;
  processed_url: string | null;
  processing_status: string | null;
  order_index: number;
  is_primary: boolean;
  ai_confidence: number | null;
}

interface PhotoGalleryProps {
  productId: string;
  /** Called when the photo set changes so parent can refresh photo_url. */
  onChange?: () => void;
}

export default function PhotoGallery({ productId, onChange }: PhotoGalleryProps) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [error, setError] = useState('');
  const [lightbox, setLightbox] = useState<{ url: string; label: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get(`/api/inventory/products/${productId}/photos`);
      if (res.ok) {
        setPhotos(await res.json());
        setError('');
      } else {
        setError('Erreur de chargement des photos.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setLoading(false);
  }, [productId]);

  useEffect(() => { load(); }, [load]);

  const notify = () => { onChange?.(); };

  const addPhoto = async () => {
    if (!newUrl.trim()) return;
    setBusy(true);
    setError('');
    try {
      const res = await api.post(
        `/api/inventory/products/${productId}/photos`,
        { url: newUrl.trim() },
      );
      if (res.ok) {
        setNewUrl('');
        await load();
        notify();
      } else {
        const err = await res.json().catch(() => null);
        setError(err?.detail || 'Erreur ajout photo.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setBusy(false);
  };

  const uploadFile = async (rawFile: File) => {
    setBusy(true);
    setError('');
    try {
      const file = await downscaleImage(rawFile);
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.upload(
        `/api/inventory/products/${productId}/photos/upload`,
        formData,
      );
      if (res.ok) {
        await load();
        notify();
      } else {
        const err = await res.json().catch(() => null);
        setError(err?.detail || 'Erreur upload.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setBusy(false);
  };

  const setPrimary = async (photoId: string) => {
    setBusy(true);
    try {
      const res = await api.post(
        `/api/inventory/products/${productId}/photos/${photoId}/primary`,
        {},
      );
      if (res.ok) {
        await load();
        notify();
      }
    } catch { /* silent */ }
    setBusy(false);
  };

  const deletePhoto = async (photoId: string) => {
    if (!confirm('Supprimer cette photo ?')) return;
    setBusy(true);
    try {
      const res = await api.delete(
        `/api/inventory/products/${productId}/photos/${photoId}`,
      );
      if (res.ok || res.status === 204) {
        await load();
        notify();
      }
    } catch { /* silent */ }
    setBusy(false);
  };

  const regenerateStorefront = async (photoId: string) => {
    setBusy(true);
    setError('');
    try {
      const res = await api.post(
        `/api/inventory/products/${productId}/photos/${photoId}/storefront`,
        {},
      );
      if (res.ok) {
        await load();
        notify();
      } else {
        const err = await res.json().catch(() => null);
        setError(err?.detail || 'Génération de la photo vitrine impossible.');
      }
    } catch {
      setError('Erreur réseau.');
    }
    setBusy(false);
  };

  const move = async (idx: number, direction: 'up' | 'down') => {
    const target = direction === 'up' ? idx - 1 : idx + 1;
    if (target < 0 || target >= photos.length) return;
    const reordered = [...photos];
    [reordered[idx], reordered[target]] = [reordered[target], reordered[idx]];
    setBusy(true);
    try {
      const res = await api.post(
        `/api/inventory/products/${productId}/photos/reorder`,
        { ordered_ids: reordered.map(p => p.id) },
      );
      if (res.ok) {
        await load();
        notify();
      }
    } catch { /* silent */ }
    setBusy(false);
  };

  return (
    <div className="space-y-3">
      {error && (
        <div className="p-2 bg-red-50 text-red-700 rounded text-sm">{error}</div>
      )}

      {loading ? (
        <div className="text-center text-gray-400 py-6 text-sm">Chargement…</div>
      ) : photos.length === 0 ? (
        <div className="text-center text-gray-400 py-6 text-sm">
          Aucune photo. Ajoutez-en une ci-dessous.
        </div>
      ) : (
        <div className="space-y-3">
          {photos.map((photo, idx) => {
            const failed = photo.processing_status === 'failed';
            return (
            <div
              key={photo.id}
              className={`p-3 border rounded-xl ${
                photo.is_primary
                  ? 'border-vz-teal bg-vz-teal-soft/30'
                  : 'border-gray-200 bg-white'
              }`}
            >
              {/* Before / after — original shot vs detoured storefront copy.
                  Both enlarge on click so the manager can inspect the cut-out. */}
              <div className="grid grid-cols-2 gap-3">
                <figure className="min-w-0">
                  <figcaption className="mb-1 flex items-center justify-between">
                    <span className="text-[11px] font-medium uppercase tracking-wide text-vz-ink-mute">
                      Originale
                    </span>
                    {photo.is_primary && (
                      <span className="rounded-full bg-vz-teal px-2 py-0.5 text-[10px] font-medium text-white">
                        Principale
                      </span>
                    )}
                  </figcaption>
                  <button
                    type="button"
                    onClick={() => setLightbox({ url: mediaUrl(photo.url), label: 'Photo originale' })}
                    className="group block w-full overflow-hidden rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-vz-teal"
                    title="Agrandir la photo originale"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={mediaUrl(photo.url)}
                      alt={`Photo ${idx + 1}`}
                      className="aspect-square w-full object-cover transition-transform group-hover:scale-105"
                    />
                  </button>
                </figure>

                <figure className="min-w-0">
                  <figcaption className="mb-1 flex items-center justify-between">
                    <span className="text-[11px] font-medium uppercase tracking-wide text-vz-ink-mute">
                      Vitrine
                    </span>
                    {photo.processed_url && (
                      <span className="rounded-full bg-vz-teal-soft px-2 py-0.5 text-[10px] font-medium text-vz-teal-deep">
                        Détourée
                      </span>
                    )}
                  </figcaption>
                  {photo.processed_url ? (
                    <button
                      type="button"
                      onClick={() => setLightbox({ url: mediaUrl(photo.processed_url!), label: 'Photo vitrine (fond détouré)' })}
                      className="group block w-full overflow-hidden rounded-lg border border-vz-teal/40 bg-[length:16px_16px] bg-[linear-gradient(45deg,#0000000a_25%,transparent_25%,transparent_75%,#0000000a_75%),linear-gradient(45deg,#0000000a_25%,#fff_25%,#fff_75%,#0000000a_75%)] focus:outline-none focus:ring-2 focus:ring-vz-teal"
                      title="Agrandir la photo vitrine"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={mediaUrl(photo.processed_url)}
                        alt={`Photo vitrine ${idx + 1}`}
                        className="aspect-square w-full object-contain transition-transform group-hover:scale-105"
                      />
                    </button>
                  ) : (
                    <div className={`flex aspect-square w-full flex-col items-center justify-center gap-1 rounded-lg border border-dashed px-2 text-center text-[11px] ${
                      failed ? 'border-vz-accent/40 text-vz-accent' : 'border-gray-200 text-gray-400'
                    }`}>
                      <span>{failed ? 'Détourage échoué' : 'Pas de photo vitrine'}</span>
                    </div>
                  )}
                </figure>
              </div>

              {/* Source URL + actions */}
              <p className="mt-2 truncate text-[11px] text-gray-400" title={photo.url}>{photo.url}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => regenerateStorefront(photo.id)}
                  disabled={busy}
                  className="rounded-lg bg-vz-teal-soft px-2.5 py-1 text-xs font-medium text-vz-teal hover:bg-vz-teal-soft/70 disabled:opacity-40"
                >
                  {photo.processed_url ? 'Régénérer la vitrine' : 'Générer la vitrine'}
                </button>
                {!photo.is_primary && (
                  <button
                    type="button"
                    onClick={() => setPrimary(photo.id)}
                    disabled={busy}
                    className="rounded-lg border border-gray-200 px-2.5 py-1 text-xs hover:bg-gray-50 disabled:opacity-40"
                  >
                    Définir principale
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => move(idx, 'up')}
                  disabled={busy || idx === 0}
                  className="rounded-lg border border-gray-200 px-2 py-1 text-xs hover:bg-gray-50 disabled:opacity-30"
                  title="Monter"
                >
                  ▲
                </button>
                <button
                  type="button"
                  onClick={() => move(idx, 'down')}
                  disabled={busy || idx === photos.length - 1}
                  className="rounded-lg border border-gray-200 px-2 py-1 text-xs hover:bg-gray-50 disabled:opacity-30"
                  title="Descendre"
                >
                  ▼
                </button>
                <button
                  type="button"
                  onClick={() => deletePhoto(photo.id)}
                  disabled={busy}
                  className="ml-auto rounded-lg bg-red-50 px-2.5 py-1 text-xs text-red-600 hover:bg-red-100 disabled:opacity-40"
                >
                  Supprimer
                </button>
              </div>
            </div>
            );
          })}
        </div>
      )}

      <div className="space-y-2 pt-2 border-t border-gray-100">
        <label className="block text-sm font-medium text-black">
          Téléverser depuis l&apos;appareil
        </label>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) {
              uploadFile(file);
              e.target.value = '';
            }
          }}
          className="block w-full text-sm text-gray-700 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-vz-teal file:text-white hover:file:bg-vz-teal-deep disabled:opacity-50"
        />
        <p className="text-xs text-gray-400">
          JPG / PNG / WEBP. Les photos sont automatiquement optimisées avant
          envoi. Stockage local pour l&apos;instant ; bascule Scaleway prévue.
        </p>
      </div>

      <div className="space-y-2 pt-2 border-t border-gray-100">
        <label className="block text-sm font-medium text-black">
          Ou ajouter par URL
        </label>
        <div className="flex gap-2">
          <input
            type="url"
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            placeholder="https://…"
            className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-vz-teal"
            disabled={busy}
          />
          <button
            type="button"
            onClick={addPhoto}
            disabled={busy || !newUrl.trim()}
            className="px-4 py-2 bg-vz-teal text-white text-sm font-medium rounded-lg hover:bg-vz-teal-deep disabled:opacity-50"
          >
            Ajouter
          </button>
        </div>
      </div>

      {lightbox && (
        <div
          role="dialog"
          aria-modal="true"
          onClick={() => setLightbox(null)}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 p-4"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={lightbox.url}
            alt={lightbox.label}
            onClick={(e) => e.stopPropagation()}
            className="max-h-[80vh] max-w-[90vw] rounded-lg bg-white object-contain shadow-2xl"
          />
          <div className="mt-3 flex items-center gap-3 text-sm text-white">
            <span>{lightbox.label}</span>
            <button
              type="button"
              onClick={() => setLightbox(null)}
              className="rounded-lg bg-white/15 px-3 py-1 hover:bg-white/25"
            >
              Fermer
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
