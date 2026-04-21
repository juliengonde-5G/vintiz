import Link from "next/link";
import Image from "next/image";

export default function DevFooter() {
  return (
    <footer className="bg-cream border-t border-black/5">
      <div className="max-w-6xl mx-auto px-6 py-10 grid gap-8 md:grid-cols-3 items-center">
        <div className="space-y-3 text-sm text-black/80">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-teal/10 text-teal">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 16.92V21a1 1 0 0 1-1.09 1 19.86 19.86 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.86 19.86 0 0 1 3.22 4.09 1 1 0 0 1 4.21 3h4.09a1 1 0 0 1 1 .75 12.11 12.11 0 0 0 .66 2.67 1 1 0 0 1-.23 1l-1.73 1.73a16 16 0 0 0 6 6l1.73-1.73a1 1 0 0 1 1-.23 12.11 12.11 0 0 0 2.67.66 1 1 0 0 1 .75 1z" />
              </svg>
            </span>
            02 58 65 66 46
          </div>
          <div className="flex items-start gap-2">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-teal/10 text-teal shrink-0">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
            </span>
            <span>
              6 Rue St Jacques,
              <br />27200 Vernon
            </span>
          </div>
        </div>

        <div className="flex flex-col items-center gap-4">
          <Image src="/logo-teal.png" alt="Vintiz" width={88} height={88} className="h-16 w-auto" />
          <div className="flex items-center gap-3">
            <a href="https://www.facebook.com/vintiz.vernon" aria-label="Facebook Vintiz" className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-teal text-white hover:bg-teal-600 transition-colors">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" /></svg>
            </a>
            <a href="https://www.instagram.com/vintiz.vernon/" aria-label="Instagram Vintiz" className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-teal text-white hover:bg-teal-600 transition-colors">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
                <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
              </svg>
            </a>
          </div>
        </div>

        <ul className="text-sm text-black/80 space-y-2 md:text-right">
          <li><Link href="/dev/notre-boutique" className="hover:text-teal underline underline-offset-4">Notre boutique</Link></li>
          <li><Link href="/dev/nos-produits" className="hover:text-teal underline underline-offset-4">Nos produits</Link></li>
          <li><Link href="/dev/contact" className="hover:text-teal underline underline-offset-4">Nous contacter</Link></li>
          <li><Link href="/mentions-legales" className="hover:text-teal underline underline-offset-4">Mentions légales</Link></li>
        </ul>
      </div>

      <div className="border-t border-black/5 py-4 text-center text-xs text-black/40">
        &copy; 2026 Vintiz — Mockup dev preview
      </div>
    </footer>
  );
}
