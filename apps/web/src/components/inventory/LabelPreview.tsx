'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';

interface LabelPreviewProps {
  productId: string;
  /** Auto-fetch when this changes; bump it to force a refresh. */
  refreshKey?: number;
}

/**
 * Renders the PNG preview of the product label (same render the Raspberry Pi
 * prints, served by GET /api/labels/preview/{id}).
 *
 * The blob URL is revoked on unmount / refresh so we don't leak memory
 * when the operator hops between products.
 */
export default function LabelPreview({ productId, refreshKey = 0 }: LabelPreviewProps) {
  const [url, setUrl] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    let objectUrl = '';

    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await api.get(`/api/labels/preview/${productId}`);
        if (cancelled) return;
        if (!res.ok) {
          const body = await res.json().catch(() => ({} as Record<string, unknown>));
          setError((body.detail as string) || 'Aperçu indisponible');
          setUrl('');
          return;
        }
        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setUrl(objectUrl);
      } catch {
        if (!cancelled) {
          setError('Aperçu indisponible');
          setUrl('');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [productId, refreshKey]);

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-vz-teal" />
      </div>
    );
  }
  if (error || !url) {
    return <p className="text-red-600 py-4 text-center text-sm">{error || 'Aperçu indisponible'}</p>;
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={url}
      alt="Aperçu étiquette"
      className="mx-auto border border-vz-line rounded-lg max-w-full bg-white"
    />
  );
}
