import Link from 'next/link';
import Image from 'next/image';

export default function Navbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-cream/90 backdrop-blur-md border-b border-pink/20">
      <nav className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2" aria-label="Retour à l'accueil Vintiz">
          <Image src="/logo-teal.png" alt="Vintiz" width={44} height={44} className="h-10 w-auto" />
        </Link>
        <Link
          href="/"
          className="text-sm font-medium text-teal hover:text-teal-600 transition-colors"
        >
          ← Accueil
        </Link>
      </nav>
    </header>
  );
}
