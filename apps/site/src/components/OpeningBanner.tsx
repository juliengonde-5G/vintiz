"use client";

import { useEffect, useState } from "react";

// Bannière éphémère — affichée jusqu'à la fin du dimanche 7 juin 2026 (Europe/Paris).
// Auto-masquée après cette date sans intervention manuelle.
const VISIBLE_UNTIL = Date.parse("2026-06-08T00:00:00+02:00");

export default function OpeningBanner() {
  const [dismissed, setDismissed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      if (sessionStorage.getItem("vz-opening-banner-dismissed") === "1") {
        setDismissed(true);
      }
    } catch {
      /* sessionStorage may be unavailable in private mode */
    }
  }, []);

  if (!mounted || dismissed || Date.now() >= VISIBLE_UNTIL) return null;

  const close = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem("vz-opening-banner-dismissed", "1");
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="relative bg-vz-teal text-white">
      <div className="mx-auto flex max-w-6xl items-center justify-center gap-3 px-4 py-2.5 text-center text-sm font-medium tracking-wide">
        <span aria-hidden className="text-base">✦</span>
        <span>
          <strong className="font-semibold">Ouverture Exceptionnelle</strong>
          {" — Dimanche 7 juin"}
        </span>
        <button
          type="button"
          onClick={close}
          aria-label="Fermer la bannière"
          className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-white/80 transition hover:bg-white/10 hover:text-white"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>
    </div>
  );
}
