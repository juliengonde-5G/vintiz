import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "À propos",
  description:
    "Vintiz, boutique seconde main premium à Vernon. Notre histoire, notre sélection, notre partenariat avec Solidarité Textiles pour une mode circulaire et solidaire.",
  alternates: {
    canonical: `${SITE_URL}/a-propos`,
    languages: {
      "fr-FR": `${SITE_URL}/a-propos`,
      "en-US": `${SITE_URL}/en/a-propos`,
    },
  },
  openGraph: {
    title: "À propos | Vintiz",
    description:
      "Notre histoire, notre sélection et notre partenariat avec Solidarité Textiles.",
    url: `${SITE_URL}/a-propos`,
    type: "website",
    locale: "fr_FR",
  },
};

const aboutJsonLd = {
  "@context": "https://schema.org",
  "@type": "AboutPage",
  name: "À propos de Vintiz",
  url: `${SITE_URL}/a-propos`,
  mainEntity: {
    "@type": "Organization",
    name: "Vintiz",
    url: SITE_URL,
    logo: `${SITE_URL}/logo-teal.png`,
    description:
      "Boutique seconde main premium à Vernon (Normandie). Marques sélectionnées, pièces uniques, mode responsable. Partenaire de Solidarité Textiles.",
    sameAs: [
      "https://www.instagram.com/vintiz.fr/",
      "https://www.facebook.com/vintiz.fr",
      "https://www.tiktok.com/@vintiz.fr",
    ],
  },
};

export default function AboutPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(aboutJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        {/* HERO */}
        <section className="max-w-5xl mx-auto px-6 py-16 lg:py-24 text-center">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-4">
            À propos
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl lg:text-6xl text-vz-ink leading-tight tracking-[-0.015em]">
            Une seconde main
            <br />
            <em className="text-vz-teal not-italic">qui a du sens.</em>
          </h1>
          <p className="mt-8 text-lg sm:text-xl text-vz-ink-soft max-w-2xl mx-auto leading-relaxed">
            Vintiz est née d&apos;une idée simple : proposer une seconde main
            premium à Vernon, où chaque pièce est choisie pour sa qualité, son
            style, et sa capacité à durer plusieurs vies.
          </p>
        </section>

        {/* NOTRE CONCEPT */}
        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-6xl mx-auto px-6 py-16 lg:py-20 grid lg:grid-cols-2 gap-12 lg:gap-16 items-start">
            <div>
              <h2 className="font-display text-3xl sm:text-4xl text-vz-teal leading-tight">
                Notre concept
              </h2>
              <p className="mt-2 text-sm uppercase tracking-[0.14em] text-vz-ink-mute">
                Premium curé, jamais en vrac
              </p>
            </div>
            <div className="space-y-5 text-vz-ink-soft text-lg leading-relaxed">
              <p>
                Vintiz, c&apos;est l&apos;envie de consommer autrement sans
                renoncer au plaisir de s&apos;habiller avec style. Chaque pièce
                est sélectionnée à la main pour son état, sa marque, sa coupe.
                Pas de tri au kilo — uniquement des coups de cœur prêts à être
                portés.
              </p>
              <p>
                Nos marques de prédilection : Sandro, Maje, Sézane, Ba&amp;sh,
                IRO, Polène, The Kooples, Vanessa Bruno, Isabel Marant — et
                quelques pépites confidentielles à découvrir en boutique.
              </p>
              <p>
                Tous les articles sont vendus en achat ferme : pas de dépôt,
                pas d&apos;intermédiaire. Le prix affiché est juste, le stock
                est réel, et la pièce vous attend rue Saint-Jacques.
              </p>
            </div>
          </div>
        </section>

        {/* MODE QUI A DU SENS — IMPACT */}
        <section className="max-w-6xl mx-auto px-6 py-16 lg:py-20 grid lg:grid-cols-3 gap-8">
          <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
            <div className="w-12 h-12 rounded-full bg-vz-teal/10 text-vz-teal flex items-center justify-center mb-5">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 2v6M5.34 6.34l4.24 4.24M2 12h6M5.34 17.66l4.24-4.24M12 22v-6M18.66 17.66l-4.24-4.24M22 12h-6M18.66 6.34l-4.24 4.24" />
              </svg>
            </div>
            <h3 className="font-display text-xl text-vz-ink mb-3">
              Une sélection rigoureuse
            </h3>
            <p className="text-vz-ink-soft leading-relaxed">
              Chaque pièce passe entre nos mains avant de rejoindre les
              portants. État, marque, taille, prix — rien n&apos;est laissé au
              hasard.
            </p>
          </div>

          <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
            <div className="w-12 h-12 rounded-full bg-vz-teal/10 text-vz-teal flex items-center justify-center mb-5">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            </div>
            <h3 className="font-display text-xl text-vz-ink mb-3">
              Personal Shopper IA
            </h3>
            <p className="text-vz-ink-soft leading-relaxed">
              Notre IA conversationnelle analyse vos préférences et vous
              propose une sélection sur-mesure dans nos pièces disponibles.
              Boucle d&apos;apprentissage continue, désactivable à tout moment.
            </p>
            <Link
              href="/personal-shopper"
              className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-vz-teal hover:underline"
            >
              En savoir plus
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </Link>
          </div>

          <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
            <div className="w-12 h-12 rounded-full bg-vz-teal/10 text-vz-teal flex items-center justify-center mb-5">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M20 12V8H6a2 2 0 0 1-2-2c0-1.1.9-2 2-2h12v4M4 6v12c0 1.1.9 2 2 2h14v-4" />
                <path d="M18 12a2 2 0 0 0-2 2c0 1.1.9 2 2 2h4v-4z" />
              </svg>
            </div>
            <h3 className="font-display text-xl text-vz-ink mb-3">
              Carte fidélité
            </h3>
            <p className="text-vz-ink-soft leading-relaxed">
              1 € dépensé = 1 point. Trois tiers (Bronze, Silver, Gold) avec
              avantages progressifs. Carte virtuelle Apple Wallet et Google
              Wallet pour ne jamais l&apos;oublier.
            </p>
          </div>
        </section>

        {/* SOLIDARITÉ TEXTILES — partenariat ESS */}
        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-6xl mx-auto px-6 py-16 lg:py-20 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
                Notre partenaire
              </p>
              <h2 className="font-display text-3xl sm:text-4xl text-vz-teal leading-tight">
                Solidarité Textiles,
                <br />
                la mode qui crée du lien.
              </h2>
              <div className="mt-6 space-y-4 text-vz-ink-soft text-lg leading-relaxed">
                <p>
                  Nos vêtements, chaussures et accessoires sont triés par notre
                  partenaire <strong>Solidarité Textiles</strong>, centre de
                  tri textile situé en Normandie.
                </p>
                <p>
                  Les pièces sont collectées dans des bornes réparties sur la
                  Métropole Rouen Normandie, puis triées manuellement par des
                  salariés en parcours d&apos;insertion. Vintiz reprend ensuite
                  la sélection premium pour vous la proposer en boutique.
                </p>
                <p>
                  C&apos;est ce qui nous permet de garantir : une économie
                  circulaire réelle, des emplois locaux soutenus, et une
                  traçabilité complète de chaque pièce.
                </p>
              </div>
              <a
                href="https://solidaritetextiles.com"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-8 inline-flex items-center gap-2 rounded-full border border-vz-teal/40 px-6 py-3 text-sm font-medium text-vz-teal hover:bg-vz-teal hover:text-white transition-colors"
              >
                Découvrir Solidarité Textiles
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </a>
            </div>

            <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
              <h3 className="font-display text-xl text-vz-ink mb-5">
                Notre engagement, en clair
              </h3>
              <ul className="space-y-4 text-vz-ink leading-relaxed">
                <li className="flex gap-3">
                  <span className="text-vz-teal text-xl leading-tight">→</span>
                  <span>
                    <strong>Achat ferme</strong>. Nous achetons le stock, vous
                    n&apos;avez pas à patienter pour récupérer un dépôt.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="text-vz-teal text-xl leading-tight">→</span>
                  <span>
                    <strong>Sourcing tracé</strong> via Solidarité Textiles —
                    insertion par le travail.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="text-vz-teal text-xl leading-tight">→</span>
                  <span>
                    <strong>Pièces non-revendables</strong> redirigées vers nos
                    partenaires (recyclage / dons), jamais jetées.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="text-vz-teal text-xl leading-tight">→</span>
                  <span>
                    <strong>Rapport d&apos;impact annuel</strong> : kilos
                    revalorisés, taux de réemploi, reversement Solidarité
                    Textiles. Publié publiquement à partir de 2027.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="max-w-4xl mx-auto px-6 py-20 text-center">
          <h2 className="font-display text-3xl sm:text-4xl text-vz-ink leading-tight">
            Envie d&apos;un avant-goût ?
          </h2>
          <p className="mt-5 text-lg text-vz-ink-soft leading-relaxed">
            Découvrez notre Personal Shopper IA, ou venez nous voir directement
            au 6 rue Saint-Jacques.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/personal-shopper"
              className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-7 py-3 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
            >
              Découvrir le Personal Shopper
            </Link>
            <Link
              href="/contact"
              className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-7 py-3 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
            >
              Nous rendre visite
            </Link>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
