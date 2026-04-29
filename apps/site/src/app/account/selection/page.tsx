"use client";

import { useEffect, useState } from "react";
import AccountShell from "@/components/account/AccountShell";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CurationItem {
  id: string;
  name: string;
  barcode: string;
  brand: string | null;
  size: string | null;
  color: string | null;
  sale_price: number;
  photo_url: string | null;
  reason: string;
}

interface CurationPayload {
  items: CurationItem[];
  curator_note: string;
  updated_at: string;
}

const FALLBACK_GRADIENTS = [
  "linear-gradient(140deg, #cdd6c8, #8aa092)",
  "linear-gradient(140deg, #e8d4c2, #c2937a)",
  "linear-gradient(140deg, #ddd9c8, #8e7b57)",
  "linear-gradient(140deg, #cde5df, #0b7a6a)",
  "linear-gradient(140deg, #ffd5e5, #e84e8b)",
  "linear-gradient(140deg, #d8cbb6, #b9a486)",
];

export default function AccountSelectionPage() {
  const [data, setData] = useState<CurationPayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/api/crm/curation/current`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (cancelled || !d) return;
        setData(d as CurationPayload);
      })
      .catch(() => undefined)
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const items = data?.items ?? [];

  return (
    <AccountShell
      title="Sélection du moment"
      intro="Les coups de cœur de l'équipe boutique cette semaine, choisis pour l'ambiance et la saison."
    >
      {loading && <p className="text-vz-ink-mute">Chargement…</p>}

      {!loading && data?.curator_note && (
        <blockquote className="border-l-2 border-vz-teal pl-4 mb-8 max-w-2xl">
          <p className="font-display text-lg italic text-vz-ink-soft leading-relaxed">
            « {data.curator_note} »
          </p>
          {data.updated_at && (
            <footer className="mt-2 font-mono text-[11px] uppercase tracking-[0.18em] text-vz-ink-mute">
              — Curation mise à jour le {new Date(data.updated_at).toLocaleDateString("fr-FR")}
            </footer>
          )}
        </blockquote>
      )}

      {!loading && items.length === 0 ? (
        <div className="bg-vz-surface rounded-vz-lg border border-vz-line p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-vz-teal">
            Curation en cours
          </p>
          <p className="text-vz-ink-soft mt-2">
            La sélection est mise à jour chaque semaine par l&apos;équipe boutique. Passez à Vernon pour découvrir les pièces choisies en vitrine.
          </p>
          <p className="text-sm text-vz-ink-mute mt-3 font-mono">
            6 rue Saint-Jacques · 27200 Vernon
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
          {items.map((it, i) => (
            <article key={it.id} className="bg-vz-surface rounded-vz-lg border border-vz-line overflow-hidden">
              <div
                className="aspect-[4/5] flex items-end p-3"
                style={{
                  background: it.photo_url
                    ? `url(${it.photo_url}) center/cover`
                    : FALLBACK_GRADIENTS[i % FALLBACK_GRADIENTS.length],
                }}
              >
                <span className="font-mono text-[10px] tracking-[0.2em] uppercase text-white/90 bg-black/30 px-2 py-0.5 rounded">
                  N° {String(i + 1).padStart(2, "0")}
                </span>
              </div>
              <div className="p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-vz-ink-mute">
                  {it.brand || "Sans marque"}
                </p>
                <p className="mt-1 font-display text-base text-vz-ink leading-tight">
                  <em className="not-italic">{it.name}</em>
                  {it.size && <span className="text-vz-ink-soft text-sm">, T. {it.size}</span>}
                </p>
                {it.reason && (
                  <p className="mt-2 text-xs text-vz-ink-soft italic leading-relaxed">« {it.reason} »</p>
                )}
                <p className="mt-3 font-display text-lg text-vz-teal">{it.sale_price.toFixed(0)} €</p>
              </div>
            </article>
          ))}
        </div>
      )}
    </AccountShell>
  );
}
