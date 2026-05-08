import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Page introuvable",
  description:
    "Cette page n'existe pas ou a été déplacée. Retour à l'accueil Vintiz, votre boutique seconde main premium à Vernon.",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <main className="min-h-screen flex flex-col">
      <section className="flex-1 flex items-center justify-center px-6 py-16 bg-vz-bg">
        <div className="max-w-2xl mx-auto text-center">
          <Image
            src="/logo-teal.png"
            alt="Vintiz"
            width={140}
            height={140}
            priority
            className="mx-auto mb-6 h-24 w-auto sm:h-28"
          />

          <p className="text-xs uppercase tracking-[0.12em] text-vz-teal font-medium mb-3">
            Erreur 404
          </p>

          <h1 className="font-display font-[450] text-4xl sm:text-5xl text-vz-ink mb-6 leading-tight tracking-[-0.015em]">
            Cette pépite a déjà
            <br />
            <em className="text-vz-teal not-italic">trouvé preneuse.</em>
          </h1>

          <p className="text-lg text-vz-ink-soft max-w-lg mx-auto mb-10 leading-relaxed">
            La page que vous cherchiez n&apos;existe pas ou a été déplacée. Pas
            de panique — d&apos;autres pièces uniques vous attendent.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center mb-10">
            <Link
              href="/"
              className="px-6 py-3 bg-vz-teal text-white font-medium rounded-lg hover:bg-vz-teal-deep transition-colors"
            >
              Retour à l&apos;accueil
            </Link>
            <Link
              href="/#newsletter"
              className="px-6 py-3 border border-vz-teal/30 text-vz-teal font-medium rounded-lg hover:bg-vz-teal hover:text-white transition-colors"
            >
              Être prévenue de l&apos;ouverture
            </Link>
          </div>

          <p className="text-xs uppercase tracking-[0.12em] text-vz-ink/50">
            Vintiz — 6 rue Saint-Jacques, 27200 Vernon
          </p>
        </div>
      </section>
    </main>
  );
}
