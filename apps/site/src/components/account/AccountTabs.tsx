"use client";

import { ReactNode } from "react";

interface Tab {
  key: string;
  label: string;
}

interface AccountTabsProps {
  tabs: Tab[];
  active: string;
  onChange: (key: string) => void;
  children: ReactNode;
}

/**
 * Underline-style tabs (Sauge Néo direction). Active tab gets a 1-px ink
 * border-bottom + Manrope 500 weight. Used inside the espace client to
 * navigate Récompenses / Offres / Historique without leaving the page.
 */
export default function AccountTabs({ tabs, active, onChange, children }: AccountTabsProps) {
  return (
    <div>
      <div className="border-b border-vz-line flex gap-0 overflow-x-auto" role="tablist">
        {tabs.map((t) => {
          const isActive = active === t.key;
          return (
            <button
              key={t.key}
              role="tab"
              aria-selected={isActive}
              onClick={() => onChange(t.key)}
              className={`px-4 py-3 text-sm transition-colors border-b-2 -mb-px whitespace-nowrap ${
                isActive
                  ? "border-vz-ink text-vz-ink font-medium"
                  : "border-transparent text-vz-ink-mute hover:text-vz-ink"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>
      <div className="pt-6">{children}</div>
    </div>
  );
}
