import type { Metadata } from "next";
import type { ReactNode } from "react";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Mon espace",
  description:
    "Espace personnel Vintiz — fidélité, Personal Shopper IA, sélection, offres, historique, RGPD.",
  robots: { index: false, follow: false, nocache: true },
  alternates: { canonical: `${SITE_URL}/account` },
};

/**
 * Espace client layout — does NOT render Navbar/Footer because the
 * legacy login/data/onboarding pages already include them. New pages
 * (PR3 zones) wrap their content in <AccountShell>.
 *
 * SEO: zone connectée → noindex sur tout /account/* (corrige KO-01 audit
 * SEO 2026-05). robots.ts ajoute aussi un Disallow ceinture+bretelles.
 */
export default function AccountLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
