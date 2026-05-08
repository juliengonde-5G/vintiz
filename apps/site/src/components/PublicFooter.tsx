import Image from "next/image";
import Link from "next/link";

/**
 * Footer pour les pages publiques (hors landing `/`).
 * Symétrique de PublicHeader — n'est *pas* monté dans le layout global
 * pour préserver l'apparence de la landing provisoire.
 */
export default function PublicFooter() {
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
          <p className="text-sm text-white/70 leading-relaxed">
            Boutique seconde main premium à Vernon, Normandie.
            <br />
            Marques sélectionnées, pièces uniques, mode responsable.
          </p>
        </div>

        <div className="space-y-3 text-sm text-white/80">
          <h3 className="font-display text-base text-white">Boutique</h3>
          <p>
            6 rue Saint-Jacques
            <br />
            27200 Vernon — Normandie
          </p>
          <p>
            <a
              href="mailto:contact@vintiz.fr"
              className="hover:text-vz-accent-soft transition-colors"
            >
              contact@vintiz.fr
            </a>
          </p>
          <p className="text-white/60 text-xs pt-1">
            Mardi à samedi · 10h30 – 19h
          </p>
        </div>

        <div className="space-y-3 text-sm text-white/80">
          <h3 className="font-display text-base text-white">Vintiz</h3>
          <ul className="space-y-1.5">
            <li>
              <Link
                href="/produits"
                className="hover:text-vz-accent-soft transition-colors"
              >
                Boutique
              </Link>
            </li>
            <li>
              <Link
                href="/a-propos"
                className="hover:text-vz-accent-soft transition-colors"
              >
                À propos
              </Link>
            </li>
            <li>
              <Link
                href="/personal-shopper"
                className="hover:text-vz-accent-soft transition-colors"
              >
                Personal Shopper IA
              </Link>
            </li>
            <li>
              <Link
                href="/contact"
                className="hover:text-vz-accent-soft transition-colors"
              >
                Contact
              </Link>
            </li>
            <li>
              <Link
                href="/account"
                className="hover:text-vz-accent-soft transition-colors"
              >
                Espace client
              </Link>
            </li>
          </ul>

          <h3 className="font-display text-base text-white pt-3">Légal</h3>
          <ul className="space-y-1.5">
            <li>
              <Link
                href="/mentions-legales"
                className="hover:text-vz-accent-soft transition-colors"
              >
                Mentions légales
              </Link>
            </li>
            <li>
              <Link
                href="/cgv"
                className="hover:text-vz-accent-soft transition-colors"
              >
                CGV
              </Link>
            </li>
            <li>
              <Link
                href="/confidentialite"
                className="hover:text-vz-accent-soft transition-colors"
              >
                Confidentialité
              </Link>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-white/10 py-4 text-center text-xs text-white/40">
        &copy; 2026 Vintiz — Vernon, Normandie
      </div>
    </footer>
  );
}
