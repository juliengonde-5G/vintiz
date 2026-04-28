/**
 * Vintiz espace client side navigation (charte v2).
 *
 * Standalone version of `apps/site/src/components/account/AccountNav.tsx`
 * — drop your own `Link` (Next.js, react-router…) via the `linkAs`
 * prop. Drawer mobile + sidebar desktop responsive.
 */

import { useState, type ComponentType, type ReactNode } from "react";

const ZONES = [
  { href: "/account", label: "Mon espace", icon: "👤" },
  { href: "/account/fidelite", label: "Ma fidélité", icon: "💳" },
  { href: "/account/shopper", label: "Personal Shopper", icon: "✨" },
  { href: "/account/selection", label: "Sélection du moment", icon: "🛍️" },
  { href: "/account/offres", label: "Offres", icon: "🎁" },
  { href: "/account/historique", label: "Historique", icon: "📜" },
  { href: "/account/rgpd", label: "Confidentialité", icon: "🔒" },
] as const;

interface LinkProps {
  href: string;
  className?: string;
  onClick?: () => void;
  children: ReactNode;
}

interface AccountNavProps {
  currentPath: string;
  email: string | null;
  onLogout: () => void;
  /** Pluggable link component (Next Link, react-router Link, plain <a>). */
  linkAs?: ComponentType<LinkProps>;
}

const DefaultLink: ComponentType<LinkProps> = (props) => <a {...props} />;

export function AccountNav({
  currentPath,
  email,
  onLogout,
  linkAs,
}: AccountNavProps) {
  const Link = linkAs ?? DefaultLink;
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/account" ? currentPath === "/account" : currentPath.startsWith(href);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-20 left-3 z-30 bg-white rounded-full shadow-md px-3 py-2 text-sm font-medium text-black"
        aria-label="Ouvrir le menu de l'espace client"
      >
        ☰ Menu
      </button>

      {open && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/40" onClick={() => setOpen(false)}>
          <aside
            className="absolute left-0 top-0 h-full w-72 bg-cream shadow-xl p-6 overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <NavInner
              email={email}
              isActive={isActive}
              onLogout={onLogout}
              Link={Link}
              onClick={() => setOpen(false)}
            />
          </aside>
        </div>
      )}

      <aside className="hidden md:block w-64 shrink-0">
        <NavInner email={email} isActive={isActive} onLogout={onLogout} Link={Link} />
      </aside>
    </>
  );
}

function NavInner({
  email,
  isActive,
  onLogout,
  Link,
  onClick,
}: {
  email: string | null;
  isActive: (href: string) => boolean;
  onLogout: () => void;
  Link: ComponentType<LinkProps>;
  onClick?: () => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">Connectée</p>
        <p className="text-sm font-medium text-black truncate">{email ?? "Visiteur"}</p>
      </div>
      <nav className="space-y-1">
        {ZONES.map((zone) => {
          const active = isActive(zone.href);
          return (
            <Link
              key={zone.href}
              href={zone.href}
              onClick={onClick}
              className={
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors " +
                (active ? "bg-teal text-white" : "text-black hover:bg-pink/30")
              }
            >
              <span aria-hidden>{zone.icon}</span>
              <span>{zone.label}</span>
            </Link>
          );
        })}
      </nav>
      <button
        type="button"
        onClick={onLogout}
        className="text-xs text-gray-500 underline"
      >
        Se déconnecter
      </button>
    </div>
  );
}
