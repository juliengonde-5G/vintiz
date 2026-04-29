"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/dev", label: "Accueil" },
  { href: "/dev/notre-boutique", label: "Notre boutique" },
  { href: "/dev/contact", label: "Nous contacter" },
];

export default function DevHeader() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-50 bg-vz-bg/95 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
        <Link href="/dev" aria-label="Accueil Vintiz" className="shrink-0">
          <Image src="/logo-teal.png" alt="Vintiz" width={80} height={80} className="h-14 w-auto" />
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`text-sm font-medium transition-colors ${
                  active ? "text-vz-teal" : "text-black hover:text-vz-teal"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3">
          <Link
            href="/account/login"
            className="hidden sm:inline-flex items-center rounded-full bg-vz-accent-soft px-5 py-2 text-sm font-medium text-black hover:bg-vz-accent transition-colors"
          >
            Mon compte
          </Link>
          <button
            aria-label="Rechercher"
            className="p-2 text-black/70 hover:text-vz-teal transition-colors"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  );
}
