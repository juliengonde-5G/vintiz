'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { api } from '@/lib/api';

interface Photo {
  id: string;
  url: string;
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

  const uploadFile = async (file: File) => {
    setBusy(true);
    setError('');
    try {
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
        <div className="space-y-2">
          {photos.map((photo, idx) => (
            <div
              key={photo.id}
              className={`flex items-center gap-3 p-2 border rounded-lg ${
                photo.is_primary
                  ? 'border-vz-teal bg-vz-teal-soft/40'
                  : 'border-gray-200 bg-white'
              }`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={photo.url}
                alt={`Photo ${idx + 1}`}
                className="w-16 h-16 object-cover rounded border border-gray-200"
              />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-gray-500 truncate">{photo.url}</p>
                {photo.is_primary && (
                  <span className="inline-block mt-1 px-2 py-0.5 text-xs font-medium rounded-full bg-vz-teal text-white">
                    Principale
                  </span>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <button
                  type="button"
                  onClick={() => move(idx, 'up')}
                  disabled={busy || idx === 0}
                  className="px-2 py-0.5 text-xs rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-30"
                  title="Monter"
                >
                  ▲
                </button>
                <button
                  type="button"
                  onClick={() => move(idx, 'down')}
                  disabled={busy || idx === photos.length - 1}
                  className="px-2 py-0.5 text-xs rounded border border-gray-200 hover:bg-gray-50 disabled:opacity-30"
                  title="Descendre"
                >
                  ▼
                </button>
              </div>
              <div className="flex flex-col gap-1">
                {!photo.is_primary && (
                  <button
                    type="button"
                    onClick={() => setPrimary(photo.id)}
                    disabled={busy}
                    className="px-2 py-1 text-xs rounded bg-vz-teal-soft text-vz-teal hover:bg-vz-teal-soft"
                  >
                    Principale
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => deletePhoto(photo.id)}
                  disabled={busy}
                  className="px-2 py-1 text-xs rounded bg-red-50 text-red-600 hover:bg-red-100"
                >
                  Supprimer
                </button>
              </div>
            </div>
          ))}
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
          JPG / PNG / WEBP, 5 Mo max. Stockage local pour l&apos;instant ;
          bascule Scaleway prévue.
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
    </div>
  );
}
