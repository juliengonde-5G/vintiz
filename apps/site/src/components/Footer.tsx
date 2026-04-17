import Link from 'next/link';
import Image from 'next/image';

export default function Footer() {
  return (
    <footer className="bg-vintiz-black text-white">
      <div className="max-w-6xl mx-auto px-6 py-16">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10">
          {/* Brand */}
          <div className="md:col-span-1">
            <div className="mb-4">
              <Image src="/logo-rose.png" alt="Vintiz" width={88} height={88} className="h-16 w-auto" />
            </div>
            <p className="text-sm text-white/60 leading-relaxed">
              Votre boutique de vetements de seconde main premium a Vernon.
            </p>
          </div>

          {/* Navigation */}
          <div>
            <h4 className="font-serif text-sm font-semibold mb-4 tracking-wider uppercase text-vintiz-pink">Navigation</h4>
            <ul className="space-y-2">
              <li><Link href="/" className="text-sm text-white/60 hover:text-vintiz-pink transition-colors">Accueil</Link></li>
              <li><Link href="/boutique" className="text-sm text-white/60 hover:text-vintiz-pink transition-colors">La Boutique</Link></li>
              <li><Link href="/concept" className="text-sm text-white/60 hover:text-vintiz-pink transition-colors">Notre Concept</Link></li>
              <li><Link href="/contact" className="text-sm text-white/60 hover:text-vintiz-pink transition-colors">Contact</Link></li>
            </ul>
          </div>

          {/* Informations */}
          <div>
            <h4 className="font-serif text-sm font-semibold mb-4 tracking-wider uppercase text-vintiz-pink">Informations</h4>
            <ul className="space-y-2 text-sm text-white/60">
              <li>6 rue Saint-Jacques</li>
              <li>27200 Vernon</li>
              <li className="pt-2">Mar-Sam : 10h - 19h</li>
              <li>Dimanche-Lundi : Ferme</li>
            </ul>
          </div>

          {/* Social */}
          <div>
            <h4 className="font-serif text-sm font-semibold mb-4 tracking-wider uppercase text-vintiz-pink">Suivez-nous</h4>
            <div className="flex gap-3">
              <a href="#" aria-label="Instagram" className="w-10 h-10 rounded-full border border-white/20 flex items-center justify-center text-white/40 hover:text-vintiz-pink hover:border-vintiz-pink transition-colors">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                  <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
                </svg>
              </a>
              <a href="#" aria-label="Facebook" className="w-10 h-10 rounded-full border border-white/20 flex items-center justify-center text-white/40 hover:text-vintiz-pink hover:border-vintiz-pink transition-colors">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
                </svg>
              </a>
              <a href="#" aria-label="TikTok" className="w-10 h-10 rounded-full border border-white/20 flex items-center justify-center text-white/40 hover:text-vintiz-pink hover:border-vintiz-pink transition-colors">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5" />
                </svg>
              </a>
            </div>
          </div>
        </div>

        <div className="mt-12 pt-8 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-white/30">&copy; 2026 Vintiz. Tous droits reserves.</p>
          <div className="flex gap-4 text-xs text-white/30">
            <Link href="/mentions-legales" className="hover:text-white/60 transition-colors">Mentions legales</Link>
            <Link href="/cgv" className="hover:text-white/60 transition-colors">CGV</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
