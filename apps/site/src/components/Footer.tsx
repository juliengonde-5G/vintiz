import Link from 'next/link';
import Image from 'next/image';

export default function Footer() {
  return (
    <footer className="bg-black text-white">
      <div className="max-w-4xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Image src="/logo-rose.png" alt="" width={44} height={44} className="h-8 w-auto" />
          <p className="text-xs text-white/40">&copy; 2026 Vintiz — Vernon, Normandie</p>
        </div>
        <div className="flex gap-5 text-xs text-white/40">
          <Link href="/mentions-legales" className="hover:text-vz-accent-soft transition-colors">Mentions légales</Link>
          <Link href="/cgv" className="hover:text-vz-accent-soft transition-colors">CGV</Link>
          <Link href="/confidentialite" className="hover:text-vz-accent-soft transition-colors">Confidentialité</Link>
        </div>
      </div>
    </footer>
  );
}
