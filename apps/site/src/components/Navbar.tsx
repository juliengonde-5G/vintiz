'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useState } from 'react';
import { usePathname } from 'next/navigation';

const links = [
  { href: '/', label: 'Accueil' },
  { href: '/boutique', label: 'La Boutique' },
  { href: '/concept', label: 'Notre Concept' },
  { href: '/contact', label: 'Contact' },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-vintiz-bg/90 backdrop-blur-md border-b border-vintiz-pink/20">
      <nav className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          <Image src="/logo-rose.png" alt="Vintiz" width={36} height={36} />
          <span className="font-serif text-xl tracking-[0.2em] text-vintiz-black">VINTIZ</span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`text-sm font-medium transition-colors ${
                pathname === l.href
                  ? 'text-vintiz-teal'
                  : 'text-vintiz-black/60 hover:text-vintiz-teal'
              }`}
            >
              {l.label}
            </Link>
          ))}
          <Link
            href="/espace-client"
            className="text-sm font-medium px-4 py-2 rounded-lg border border-vintiz-teal text-vintiz-teal hover:bg-vintiz-teal hover:text-white transition-colors"
          >
            Espace Client
          </Link>
        </div>

        {/* Mobile burger */}
        <button
          onClick={() => setOpen(!open)}
          className="md:hidden min-h-[44px] min-w-[44px] flex items-center justify-center"
          aria-label="Menu"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
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
      </nav>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden bg-vintiz-bg border-t border-vintiz-pink/20 px-6 py-4 space-y-3">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className={`block py-2 text-base font-medium ${
                pathname === l.href ? 'text-vintiz-teal' : 'text-vintiz-black/60'
              }`}
            >
              {l.label}
            </Link>
          ))}
          <Link
            href="/espace-client"
            onClick={() => setOpen(false)}
            className="block py-2 text-base font-medium text-vintiz-teal"
          >
            Espace Client
          </Link>
        </div>
      )}
    </header>
  );
}
