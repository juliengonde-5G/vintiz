'use client';

import React, { useEffect, useRef } from 'react';

interface ClientResult {
  id: string;
  first_name: string;
  last_name: string;
  phone?: string;
  email?: string;
  has_loyalty: boolean;
}

interface ClientSelectionScreenProps {
  open: boolean;
  onClose: () => void;
  search: string;
  onSearchChange: (value: string) => void;
  results: ClientResult[];
  onSelect: (client: ClientResult) => void;
  onCreateNew: () => void;
}

/**
 * Fullscreen client picker — Odoo 17 POS pattern. Replaces the inline
 * dropdown from the ticket header. Search box at top, results grid in
 * the centre, "+ Nouveau" affordance always visible.
 */
export default function ClientSelectionScreen({
  open,
  onClose,
  search,
  onSearchChange,
  results,
  onSelect,
  onCreateNew,
}: ClientSelectionScreenProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      // Focus the search on open for keyboard / scanner workflow.
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[55] bg-vz-bg flex flex-col">
      {/* Header bar */}
      <header className="flex-shrink-0 h-14 bg-vz-teal-deep text-white flex items-center px-3 gap-3 shadow-lg">
        <button
          onClick={onClose}
          className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-white/10 transition-colors min-h-[44px]"
          aria-label="Fermer"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          <span className="text-sm font-medium">Retour</span>
        </button>
        <div className="h-7 w-px bg-white/15" />
        <h1 className="font-display text-lg">Sélectionner une cliente</h1>
        <div className="flex-1" />
        <button
          onClick={onCreateNew}
          className="px-4 py-2 rounded-lg bg-vz-accent text-white text-sm font-medium hover:opacity-90 transition-opacity min-h-[40px] flex items-center gap-2"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Nouvelle cliente
        </button>
      </header>

      {/* Search bar */}
      <div className="flex-shrink-0 px-6 py-4 bg-white border-b border-vz-line">
        <div className="relative max-w-2xl mx-auto">
          <svg
            className="absolute left-4 top-1/2 -translate-y-1/2 text-vz-ink-mute"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            type="search"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Nom, prénom, téléphone, email, V######…"
            className="w-full pl-12 pr-10 py-3.5 text-base rounded-xl border border-vz-line bg-vz-bg-alt text-vz-ink focus:outline-none focus:ring-2 focus:ring-vz-teal focus:border-vz-teal"
          />
          {search && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-vz-ink-mute hover:text-vz-ink p-2"
              aria-label="Effacer"
            >
              ×
            </button>
          )}
        </div>
      </div>

      {/* Results grid */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        <div className="max-w-5xl mx-auto">
          {results.length === 0 ? (
            <div className="flex flex-col items-center justify-center text-vz-ink-mute py-20">
              <svg
                width="64"
                height="64"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1"
                className="mb-4 opacity-40"
              >
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              <p className="text-base">
                {search
                  ? 'Aucune cliente correspondante'
                  : 'Recherchez par nom, téléphone ou V######'}
              </p>
              {!search && (
                <p className="text-sm opacity-70 mt-1">
                  Ou créez une nouvelle cliente avec le bouton en haut à droite.
                </p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {results.map((c) => (
                <button
                  key={c.id}
                  onClick={() => onSelect(c)}
                  className="text-left p-4 bg-white rounded-xl border border-vz-line hover:border-vz-teal hover:shadow-md active:bg-vz-teal-soft transition-all flex items-center gap-3 min-h-[80px]"
                >
                  <div className="w-12 h-12 rounded-full bg-vz-teal flex-shrink-0 flex items-center justify-center text-white font-bold text-lg">
                    {(c.first_name?.[0] ?? '?').toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-base font-semibold text-vz-ink truncate">
                      {c.first_name} {c.last_name}
                    </p>
                    {c.phone && (
                      <p className="text-xs text-vz-ink-mute truncate">{c.phone}</p>
                    )}
                    {c.email && (
                      <p className="text-xs text-vz-ink-mute truncate">{c.email}</p>
                    )}
                  </div>
                  {c.has_loyalty && (
                    <span className="flex-shrink-0 text-[10px] px-2 py-1 rounded-full bg-vz-accent-soft text-vz-accent font-semibold uppercase tracking-wider">
                      Fidélité
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
