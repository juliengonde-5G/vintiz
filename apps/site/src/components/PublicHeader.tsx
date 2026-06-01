"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const NAV_FR = [
  { href: "/produits", label: "Boutique" },
  { href: "/capsules", label: "Capsules" },
  { href: "/journal", label: "Journal" },
  { href: "/a-propos", label: "À propos" },
  { href: "/personal-shopper", label: "Personal Shopper" },
  { href: "/contact", label: "Contact" },
];

const NAV_EN = [
  { href: "/en/produits", label: "Shop" },
  { href: "/en/capsules", label: "Capsules" },
  { href: "/en/journal", label: "Journal" },
  { href: "/en/a-propos", label: "About" },
  { href: "/en/personal-shopper", label: "AI Personal Shopper" },
  { href: "/en/contact", label: "Visit us" },
];

const EN_TO_FR: Record<string, string> = {
  "/en": "/",
  "/en/produits": "/produits",
  "/en/capsules": "/capsules",
  "/en/journal": "/journal",
  "/en/personal-shopper": "/personal-shopper",
  "/en/a-propos": "/a-propos",
  "/en/contact": "/contact",
};

const FR_TO_EN: Record<string, string> = {
  "/": "/en",
  "/produits": "/en/produits",
  "/produits/made-in-france": "/en/produits",
  "/capsules": "/en/capsules",
  "/journal": "/en/journal",
  "/personal-shopper": "/en/personal-shopper",
  "/a-propos": "/en/a-propos",
  "/contact": "/en/contact",
};

/**
 * Routes dynamiques à slug partagé FR↔EN (capsules, journal, marque). Le
 * slug est identique dans les deux langues, donc le toggle de langue
 * préserve simplement le slug en changeant le préfixe.
 */
const SHARED_SLUG_PREFIXES = [
  { fr: "/capsules/", en: "/en/capsules/" },
  { fr: "/journal/", en: "/en/journal/" },
  { fr: "/produits/marque/", en: "/en/produits/marque/" },
];

function resolveSwitchHref(pathname: string, isEn: boolean): string {
  // Routes statiques d'abord (mapping explicite).
  const direct = isEn ? EN_TO_FR[pathname] : FR_TO_EN[pathname];
  if (direct) return direct;

  // Routes dynamiques à slug partagé.
  for (const { fr, en } of SHARED_SLUG_PREFIXES) {
    const from = isEn ? en : fr;
    const to = isEn ? fr : en;
    if (pathname.startsWith(from) && pathname.length > from.length) {
      return to + pathname.slice(from.length);
    }
  }

  return isEn ? "/" : "/en/personal-shopper";
}

/**
 * Header de navigation pour les pages publiques (hors landing `/`).
 * Volontairement *non* monté dans `app/layout.tsx` pour ne pas modifier
 * l'apparence de la landing provisoire — chaque page concernée l'importe.
 */
export default function PublicHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isEn = pathname?.startsWith("/en") ?? false;
  const NAV = isEn ? NAV_EN : NAV_FR;
  const switchHref = resolveSwitchHref(pathname ?? "", isEn);
  const switchLabel = isEn ? "FR" : "EN";

  return (
    <header className="sticky top-0 z-50 bg-vz-bg/95 backdrop-blur-md border-b border-black/5">
      <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
        <Link href="/" aria-label="Accueil Vintiz" className="shrink-0">
          <Image
            src="/logo-teal.png"
            alt="Vintiz"
            width={80}
            height={80}
            className="h-12 w-auto sm:h-14"
          />
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`text-sm font-medium transition-colors ${
                  active ? "text-vz-teal" : "text-vz-ink hover:text-vz-teal"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <Link
            href={switchHref}
            aria-label={isEn ? "Lire en français" : "Read in English"}
            className="hidden sm:inline-flex items-center rounded-full border border-black/10 px-3 py-1.5 text-xs font-medium text-vz-ink-soft hover:border-vz-teal/40 hover:text-vz-teal transition-colors"
          >
            {switchLabel}
          </Link>
          <Link
            href="/account/login"
            className="hidden sm:inline-flex items-center rounded-full bg-vz-teal text-white px-5 py-2 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
          >
            {isEn ? "My account" : "Mon espace"}
          </Link>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Fermer le menu" : "Ouvrir le menu"}
            aria-expanded={open}
            className="md:hidden p-2 text-vz-ink hover:text-vz-teal"
          >
            <svg
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {open ? (
                <>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </>
              ) : (
                <>
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </>
              )}
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <div className="md:hidden border-t border-black/5 bg-vz-bg">
          <nav className="px-6 py-4 flex flex-col gap-3">
            {NAV.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={`text-base font-medium py-2 ${
                    active ? "text-vz-teal" : "text-vz-ink"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
            <Link
              href="/account/login"
              onClick={() => setOpen(false)}
              className="mt-2 inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-5 py-2.5 text-sm font-medium"
            >
              {isEn ? "My account" : "Mon espace"}
            </Link>
            <Link
              href={switchHref}
              onClick={() => setOpen(false)}
              className="mt-1 inline-flex items-center justify-center rounded-full border border-black/10 px-4 py-2 text-xs font-medium text-vz-ink-soft"
            >
              {isEn ? "Lire en français" : "Read in English"}
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
