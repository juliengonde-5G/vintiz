"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const ZONES = [
  { href: "/account", label: "Mon espace", icon: "👤" },
  { href: "/account/fidelite", label: "Ma fidélité", icon: "💳" },
  { href: "/account/shopper", label: "Personal Shopper", icon: "✨" },
  { href: "/account/selection", label: "Sélection du moment", icon: "🛍️" },
  { href: "/account/offres", label: "Offres", icon: "🎁" },
  { href: "/account/historique", label: "Historique", icon: "📜" },
  { href: "/account/rgpd", label: "Confidentialité", icon: "🔒" },
];

export default function AccountNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      setEmail(window.localStorage.getItem("vintiz_account_email"));
    } catch {
      setEmail(null);
    }
  }, []);

  const logout = () => {
    try {
      window.localStorage.removeItem("vintiz_account_token");
      window.localStorage.removeItem("vintiz_account_email");
    } catch {
      /* private mode */
    }
    router.push("/account/login");
  };

  const isActive = (href: string) => {
    if (href === "/account") return pathname === "/account";
    return pathname?.startsWith(href);
  };

  return (
    <>
      {/* Mobile drawer trigger */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-20 left-3 z-30 bg-white rounded-full shadow-md px-3 py-2 text-sm font-medium text-black"
        aria-label="Ouvrir le menu de l'espace client"
      >
        ☰ Menu
      </button>

      {/* Mobile drawer */}
      {open && (
        <div className="md:hidden fixed inset-0 z-40 bg-black/40" onClick={() => setOpen(false)}>
          <aside
            className="absolute left-0 top-0 h-full w-72 bg-vz-bg shadow-xl p-6 overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <NavInner zones={ZONES} email={email} isActive={isActive} onLogout={logout} onClick={() => setOpen(false)} />
          </aside>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className="hidden md:block w-64 shrink-0">
        <NavInner zones={ZONES} email={email} isActive={isActive} onLogout={logout} />
      </aside>
    </>
  );
}

function NavInner({
  zones,
  email,
  isActive,
  onLogout,
  onClick,
}: {
  zones: typeof ZONES;
  email: string | null;
  isActive: (href: string) => boolean;
  onLogout: () => void;
  onClick?: () => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-wider text-gray-500 mb-1">Connectée</p>
        <p className="text-sm font-medium text-black truncate">{email ?? "Visiteur"}</p>
      </div>
      <nav className="space-y-1">
        {zones.map((zone) => {
          const active = isActive(zone.href);
          return (
            <Link
              key={zone.href}
              href={zone.href}
              onClick={onClick}
              className={
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors " +
                (active
                  ? "bg-vz-teal text-white"
                  : "text-black hover:bg-vz-accent-soft/30")
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
