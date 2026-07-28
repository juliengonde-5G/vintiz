"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { OPEN_CONSENT_EVENT } from "@/components/CookieBanner";

// GA4 (soumis à consentement) configuré ? Si non, seule la mesure Matomo
// cookieless exemptée tourne → rien à gérer, on masque le lien.
const HAS_CONSENT_TRACKER = Boolean(process.env.NEXT_PUBLIC_GA_ID);

/**
 * Footer pour les pages publiques (hors landing `/`).
 * Symétrique de PublicHeader — n'est *pas* monté dans le layout global
 * pour préserver l'apparence de la landing provisoire.
 *
 * Bilingue : bascule FR ↔ EN en fonction du pathname (préfixe `/en`).
 */
export default function PublicFooter() {
  const pathname = usePathname();
  const isEn = pathname?.startsWith("/en") ?? false;

  const t = isEn
    ? {
        tagline: (
          <>
            Premium second-hand boutique in Vernon, Normandy.
            <br />
            Curated brands, one-of-a-kind pieces, responsible fashion.
          </>
        ),
        boutiqueHeading: "Boutique",
        addressLine: (
          <>
            6 rue Saint-Jacques
            <br />
            27200 Vernon — Normandy, France
          </>
        ),
        hours: "Tuesday to Saturday · 10:30 AM – 7:00 PM",
        sectionHeading: "Vintiz",
        nav: [
          { href: "/en/produits", label: "Shop" },
          { href: "/en/capsules", label: "Capsules" },
          { href: "/en/a-propos", label: "About" },
          { href: "/en/personal-shopper", label: "AI Personal Shopper" },
          { href: "/en/contact", label: "Visit us" },
          { href: "/account", label: "Account" },
        ],
        legalHeading: "Legal",
        legal: [
          { href: "/mentions-legales", label: "Legal notice" },
          { href: "/cgv", label: "Terms" },
          { href: "/confidentialite", label: "Privacy" },
        ],
        manageCookies: "Manage cookies",
        copyright: "© 2026 Vintiz — Vernon, Normandy",
      }
    : {
        tagline: (
          <>
            Boutique seconde main premium à Vernon, Normandie.
            <br />
            Marques sélectionnées, pièces uniques, mode responsable.
          </>
        ),
        boutiqueHeading: "Boutique",
        addressLine: (
          <>
            6 rue Saint-Jacques
            <br />
            27200 Vernon — Normandie
          </>
        ),
        hours: "Mardi à samedi · 10h30 – 19h",
        sectionHeading: "Vintiz",
        nav: [
          { href: "/produits", label: "Boutique" },
          { href: "/a-propos", label: "À propos" },
          { href: "/personal-shopper", label: "Personal Shopper IA" },
          { href: "/contact", label: "Contact" },
          { href: "/account", label: "Espace client" },
        ],
        legalHeading: "Légal",
        legal: [
          { href: "/mentions-legales", label: "Mentions légales" },
          { href: "/cgv", label: "CGV" },
          { href: "/confidentialite", label: "Confidentialité" },
        ],
        manageCookies: "Gérer les cookies",
        copyright: "© 2026 Vintiz — Vernon, Normandie",
      };

  return (
    <footer className="bg-black text-white mt-16">
      <div className="max-w-6xl mx-auto px-6 py-12 grid gap-10 md:grid-cols-3">
        <div className="space-y-3">
          <Image
            src="/logo-rose.png"
            alt="Vintiz"
            width={88}
            height={88}
            className="h-10 w-auto"
          />
          <p className="text-sm text-white/70 leading-relaxed">{t.tagline}</p>
        </div>

        <div className="space-y-3 text-sm text-white/80">
          <h3 className="font-display text-base text-white">
            {t.boutiqueHeading}
          </h3>
          <p>{t.addressLine}</p>
          <p>
            <a
              href="mailto:contact@vintiz.fr"
              className="hover:text-vz-accent-soft transition-colors"
            >
              contact@vintiz.fr
            </a>
          </p>
          <p className="text-white/60 text-xs pt-1">{t.hours}</p>
        </div>

        <div className="space-y-3 text-sm text-white/80">
          <h3 className="font-display text-base text-white">
            {t.sectionHeading}
          </h3>
          <ul className="space-y-1.5">
            {t.nav.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="hover:text-vz-accent-soft transition-colors"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>

          <h3 className="font-display text-base text-white pt-3">
            {t.legalHeading}
          </h3>
          <ul className="space-y-1.5">
            {t.legal.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="hover:text-vz-accent-soft transition-colors"
                >
                  {item.label}
                </Link>
              </li>
            ))}
            {HAS_CONSENT_TRACKER && (
              <li>
                <button
                  type="button"
                  onClick={() =>
                    window.dispatchEvent(new CustomEvent(OPEN_CONSENT_EVENT))
                  }
                  className="hover:text-vz-accent-soft transition-colors text-left"
                >
                  {t.manageCookies}
                </button>
              </li>
            )}
          </ul>
        </div>
      </div>

      <div className="border-t border-white/10 py-4 text-center text-xs text-white/40">
        {t.copyright}
      </div>
    </footer>
  );
}
