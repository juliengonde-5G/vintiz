"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AccountShell from "@/components/account/AccountShell";
import { mediaUrl } from "@/lib/media";
import { formatPriceCents } from "@/lib/format";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface SelectionItem {
  id: string;
  name: string;
  brand: string | null;
  size: string | null;
  color: string | null;
  price_cents: number;
  photo_url: string | null;
  score: number | null;
}

interface SelectionPayload {
  ps_member: boolean;
  items: SelectionItem[];
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
  const [data, setData] = useState<SelectionPayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let email = "";
    try {
      email = window.localStorage.getItem("vintiz_account_email") || "";
    } catch {
      /* private mode */
    }
    const qs = email ? `?email=${encodeURIComponent(email)}` : "";
    fetch(`${API_URL}/api/crm/account/selection${qs}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (cancelled || !d) return;
        setData(d as SelectionPayload);
      })
      .catch(() => undefined)
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const items = data?.items ?? [];

  // #7 — réservée aux non-membres PS : un membre avec profilage actif a déjà
  // son feed personnalisé, on le renvoie vers /account/shopper.
  if (!loading && data?.ps_member) {
    return (
      <AccountShell
        title="Sélection du moment"
        intro="Vous avez activé votre Personal Shopper."
      >
        <div className="bg-vz-surface rounded-vz-lg border border-vz-line p-6 max-w-2xl">
          <p className="text-vz-ink-soft">
            Votre Personal Shopper vous propose déjà une sélection personnalisée,
            calibrée sur vos goûts.
          </p>
          <Link
            href="/account/shopper"
            className="inline-block mt-4 bg-vz-teal text-white px-5 py-2.5 rounded-lg font-medium hover:bg-vz-teal-deep"
          >
            Voir ma sélection personnalisée
          </Link>
        </div>
      </AccountShell>
    );
  }

  return (
    <AccountShell
      title="Sélection du moment"
      intro="Nos pièces les mieux notées du moment, une par catégorie. Activez votre Personal Shopper pour une sélection sur-mesure."
    >
      {loading && <p className="text-vz-ink-mute">Chargement…</p>}

      {!loading && items.length === 0 ? (
        <div className="bg-vz-surface rounded-vz-lg border border-vz-line p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-vz-teal">
            Sélection en cours
          </p>
          <p className="text-vz-ink-soft mt-2">
            Aucune pièce à afficher pour le moment. Passez à Vernon pour
            découvrir les nouveautés en boutique.
          </p>
          <p className="text-sm text-vz-ink-mute mt-3 font-mono">
            6 rue Saint-Jacques · 27200 Vernon
          </p>
        </div>
      ) : (
        !loading && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
              {items.map((it, i) => (
                <article key={it.id} className="bg-vz-surface rounded-vz-lg border border-vz-line overflow-hidden">
                  <div
                    className="aspect-[4/5] flex items-end p-3"
                    style={{
                      background: it.photo_url
                        ? `url(${mediaUrl(it.photo_url)}) center/cover`
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
                    <p className="mt-3 font-display text-lg text-vz-teal">{formatPriceCents(it.price_cents)}</p>
                  </div>
                </article>
              ))}
            </div>
            <div className="mt-8 bg-vz-teal-soft/30 border border-vz-teal/20 rounded-vz-lg p-5 max-w-2xl">
              <p className="text-vz-ink-soft">
                Envie d&apos;une sélection vraiment faite pour vous ?
              </p>
              <Link
                href="/account/shopper"
                className="inline-block mt-3 bg-vz-teal text-white px-5 py-2.5 rounded-lg font-medium hover:bg-vz-teal-deep"
              >
                Activer mon Personal Shopper
              </Link>
            </div>
          </>
        )
      )}
    </AccountShell>
  );
}
