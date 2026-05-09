import type { Metadata } from "next";
import Link from "next/link";
import PublicFooter from "@/components/PublicFooter";
import PublicHeader from "@/components/PublicHeader";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://vintiz.fr";

export const metadata: Metadata = {
  title: "Personal Shopper IA",
  description:
    "Le Personal Shopper IA Vintiz : une sélection sur-mesure de pièces seconde main premium à Vernon, dictée par vos goûts. Réservation, retrait, désactivation libre.",
  alternates: {
    canonical: `${SITE_URL}/personal-shopper`,
    languages: {
      "fr-FR": `${SITE_URL}/personal-shopper`,
      "en-US": `${SITE_URL}/en/personal-shopper`,
    },
  },
  openGraph: {
    title: "Personal Shopper IA | Vintiz Vernon",
    description:
      "Une sélection sur-mesure de pièces seconde main premium à Vernon, dictée par vos goûts.",
    url: `${SITE_URL}/personal-shopper`,
    type: "website",
    locale: "fr_FR",
  },
};

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Personal Shopper IA Vintiz",
  serviceType: "Personal Shopping",
  description:
    "Service de recommandation personnalisée de pièces seconde main premium, alimenté par une IA conversationnelle (Claude Haiku, hébergée en Union européenne). Disponible aux membres du programme de fidélité Vintiz, sur consentement explicite.",
  provider: {
    "@type": "ClothingStore",
    name: "Vintiz",
    url: SITE_URL,
    address: {
      "@type": "PostalAddress",
      streetAddress: "6 rue Saint-Jacques",
      addressLocality: "Vernon",
      postalCode: "27200",
      addressRegion: "Normandie",
      addressCountry: "FR",
    },
  },
  areaServed: [
    { "@type": "City", name: "Vernon" },
    { "@type": "AdministrativeArea", name: "Normandie" },
  ],
  offers: {
    "@type": "Offer",
    priceCurrency: "EUR",
    price: "0",
    description: "Service inclus pour les membres du programme de fidélité.",
  },
  url: `${SITE_URL}/personal-shopper`,
};

export default function PersonalShopperPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceJsonLd) }}
      />
      <PublicHeader />
      <main className="bg-vz-bg">
        {/* HERO */}
        <section className="max-w-5xl mx-auto px-6 py-16 lg:py-24 text-center">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-4">
            Personal Shopper IA
          </p>
          <h1 className="font-display font-[450] text-4xl sm:text-5xl lg:text-6xl text-vz-ink leading-tight tracking-[-0.015em]">
            Votre styliste,
            <br />
            <em className="text-vz-teal not-italic">à toute heure.</em>
          </h1>
          <p className="mt-8 text-lg sm:text-xl text-vz-ink-soft max-w-2xl mx-auto leading-relaxed">
            Vintiz combine une sélection seconde main premium curée à la main
            et une IA conversationnelle qui apprend vos goûts pour vous
            recommander, en quelques secondes, les pièces faites pour vous.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/account/login"
              className="inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-8 py-3.5 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
            >
              Activer mon Personal Shopper
            </Link>
            <Link
              href="#comment-ca-marche"
              className="inline-flex items-center justify-center rounded-full border border-vz-teal/40 text-vz-teal px-8 py-3.5 text-sm font-medium hover:bg-vz-teal hover:text-white transition-colors"
            >
              Comment ça marche ?
            </Link>
          </div>
        </section>

        {/* COMMENT ÇA MARCHE */}
        <section
          id="comment-ca-marche"
          className="bg-vz-bg-alt border-y border-black/5"
        >
          <div className="max-w-6xl mx-auto px-6 py-16 lg:py-20">
            <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3 text-center">
              En 3 étapes
            </p>
            <h2 className="font-display text-3xl sm:text-4xl text-vz-ink mb-12 text-center leading-tight">
              Une sélection sur-mesure,
              <br />
              avant même votre prochaine visite.
            </h2>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <div className="font-display text-5xl text-vz-teal/30 mb-4">
                  01
                </div>
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  Vos préférences
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  Vous nous indiquez vos tailles, marques préférées, couleurs
                  qui vous vont, budget et le type de pièces recherchées. En 2
                  minutes, depuis votre espace client.
                </p>
              </div>

              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <div className="font-display text-5xl text-vz-teal/30 mb-4">
                  02
                </div>
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  Notre IA croise tout
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  Claude Haiku croise vos préférences, votre historique
                  d&apos;achats et le stock disponible en boutique. Pas une
                  liste anonyme — un brief stylistique narratif.
                </p>
              </div>

              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <div className="font-display text-5xl text-vz-teal/30 mb-4">
                  03
                </div>
                <h3 className="font-display text-xl text-vz-ink mb-3">
                  Vous réservez, vous récupérez
                </h3>
                <p className="text-vz-ink-soft leading-relaxed">
                  Réservation 24 à 48h. Vous venez essayer en boutique, vous
                  prenez ce que vous aimez, vous repartez. Aucun engagement.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* POURQUOI C'EST DIFFÉRENT */}
        <section className="max-w-6xl mx-auto px-6 py-16 lg:py-20">
          <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
            Pourquoi c&apos;est différent
          </p>
          <h2 className="font-display text-3xl sm:text-4xl text-vz-ink mb-12 leading-tight max-w-3xl">
            Pas un gadget IA. Pas une marketplace.
            <br />
            <span className="text-vz-teal">
              Une vraie boutique, un vrai stock, une vraie conversation.
            </span>
          </h2>

          <div className="grid md:grid-cols-2 gap-x-12 gap-y-10">
            <div>
              <h3 className="font-display text-xl text-vz-ink mb-3">
                Adossé à un stock réel
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Chaque recommandation correspond à une pièce physique présente
                à Vernon, immédiatement réservable. Pas de catalogue infini
                qui n&apos;existe nulle part — uniquement ce que vous pouvez
                vraiment essayer.
              </p>
            </div>

            <div>
              <h3 className="font-display text-xl text-vz-ink mb-3">
                Une vraie conversation
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Vous écrivez « robe pour un mariage à Giverny en juin, budget
                100 € » — l&apos;IA comprend, croise le stock, et vous propose
                3 à 5 pièces avec une justification courte pour chacune. Pas
                un dressing virtuel 3D abstrait.
              </p>
            </div>

            <div>
              <h3 className="font-display text-xl text-vz-ink mb-3">
                Disponible 24/7
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Le mardi à 14h ou le dimanche à 23h, votre Personal Shopper
                est là. Pas de file d&apos;attente, pas de rendez-vous à
                caler. Vous décidez du moment.
              </p>
            </div>

            <div>
              <h3 className="font-display text-xl text-vz-ink mb-3">
                Apprend de vos clics
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Plus vous interagissez, plus la sélection devient juste.
                Chaque clic, chaque réservation, chaque essai affine notre
                compréhension de votre style.
              </p>
            </div>

            <div>
              <h3 className="font-display text-xl text-vz-ink mb-3">
                Sans pression de vente
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                L&apos;IA recommande, elle ne pousse jamais à acheter. Vous
                réservez ce qui vous parle, vous laissez ce qui ne vous parle
                pas. Aucune pénalité, aucun jugement.
              </p>
            </div>

            <div>
              <h3 className="font-display text-xl text-vz-ink mb-3">
                Désactivable à tout moment
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Vous changez d&apos;avis ? Un clic dans votre espace client
                désactive immédiatement le service. Vos données de profilage
                sont alors supprimées, et nous repartons de zéro si vous
                réactivez plus tard.
              </p>
            </div>
          </div>
        </section>

        {/* CONFIDENTIALITÉ ET CONTRÔLE */}
        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-5xl mx-auto px-6 py-16 lg:py-20">
            <p className="text-xs uppercase tracking-[0.18em] text-vz-teal font-medium mb-3">
              Vos données, votre contrôle
            </p>
            <h2 className="font-display text-3xl sm:text-4xl text-vz-ink mb-8 leading-tight">
              Ce que nous utilisons,
              <br />
              <span className="text-vz-teal">et ce que vous pouvez retirer.</span>
            </h2>

            <div className="grid md:grid-cols-2 gap-8">
              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <h3 className="font-display text-lg text-vz-ink mb-4">
                  Nous analysons
                </h3>
                <ul className="space-y-2.5 text-vz-ink-soft">
                  <li className="flex gap-2">
                    <span className="text-vz-teal">•</span>
                    <span>
                      Votre historique d&apos;achats (3 derniers en priorité)
                    </span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vz-teal">•</span>
                    <span>
                      Vos préférences déclarées (tailles, couleurs, marques,
                      catégories)
                    </span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vz-teal">•</span>
                    <span>
                      Vos clics sur les recommandations précédentes (boucle
                      d&apos;apprentissage)
                    </span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vz-teal">•</span>
                    <span>
                      Le contexte de votre visite (saison, météo locale,
                      moment de la journée)
                    </span>
                  </li>
                </ul>
              </div>

              <div className="rounded-2xl bg-vz-surface border border-black/5 p-8">
                <h3 className="font-display text-lg text-vz-ink mb-4">
                  Vos droits, à tout moment
                </h3>
                <ul className="space-y-2.5 text-vz-ink-soft">
                  <li className="flex gap-2">
                    <span className="text-vz-teal">→</span>
                    <span>
                      <strong>Désactiver le service</strong> en un clic,
                      effet immédiat.
                    </span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vz-teal">→</span>
                    <span>
                      <strong>Exporter vos données</strong> au format JSON
                      (article 20 RGPD).
                    </span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vz-teal">→</span>
                    <span>
                      <strong>Demander la suppression</strong> de votre
                      profil (article 17 RGPD), avec fenêtre d&apos;annulation
                      de 30 jours.
                    </span>
                  </li>
                  <li className="flex gap-2">
                    <span className="text-vz-teal">→</span>
                    <span>
                      <strong>Demander l&apos;intervention</strong> d&apos;un
                      humain Vintiz pour contester ou commenter une
                      recommandation.
                    </span>
                  </li>
                </ul>
              </div>
            </div>

            <div className="mt-10 rounded-2xl bg-vz-teal-soft/30 border border-vz-teal/20 p-6 text-sm text-vz-ink-soft leading-relaxed">
              <p>
                <strong className="text-vz-ink">L&apos;IA utilisée :</strong>{" "}
                Claude Haiku 4.5 d&apos;Anthropic, hébergée en Union
                européenne. Anthropic ne réutilise pas vos données pour
                entraîner ses modèles (engagement contractuel API).
              </p>
              <p className="mt-3">
                <strong className="text-vz-ink">Conservation :</strong> profil
                de goûts conservé tant que vous êtes membre, supprimé au bout
                de 24 mois sans activité ; logs de scoring conservés 6 mois ;
                historique d&apos;achats conservé 10 ans (obligation
                comptable).
              </p>
              <p className="mt-3">
                <strong className="text-vz-ink">DPO :</strong>{" "}
                <a
                  href="mailto:dpo@solidarite-textiles.fr"
                  className="underline underline-offset-2 hover:text-vz-teal"
                >
                  dpo@solidarite-textiles.fr
                </a>
                .{" "}
                <Link
                  href="/confidentialite"
                  className="underline underline-offset-2 hover:text-vz-teal"
                >
                  Politique complète
                </Link>
                .
              </p>
            </div>
          </div>
        </section>

        {/* FAQ rapide */}
        <section className="max-w-4xl mx-auto px-6 py-16 lg:py-20">
          <h2 className="font-display text-3xl sm:text-4xl text-vz-ink mb-10 leading-tight text-center">
            Questions fréquentes
          </h2>

          <div className="space-y-6">
            <div>
              <h3 className="font-display text-lg text-vz-ink mb-2">
                Le Personal Shopper est-il payant ?
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Non. Le service est inclus gratuitement pour les membres du
                programme de fidélité Vintiz.
              </p>
            </div>

            <div>
              <h3 className="font-display text-lg text-vz-ink mb-2">
                Combien de pièces vais-je recevoir en recommandation ?
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Entre 3 et 5 pièces par session, sélectionnées dans le stock
                réel de la boutique. Si vous demandez à élargir, l&apos;IA
                propose plus de pièces — sans jamais sortir de votre budget.
              </p>
            </div>

            <div>
              <h3 className="font-display text-lg text-vz-ink mb-2">
                Et si une recommandation ne me convient pas ?
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Vous nous le dites en une phrase. L&apos;IA réajuste
                immédiatement. Et notre équipe peut intervenir manuellement
                pour vous proposer une alternative dans les 24h.
              </p>
            </div>

            <div>
              <h3 className="font-display text-lg text-vz-ink mb-2">
                Vous discutez vraiment avec une IA ?
              </h3>
              <p className="text-vz-ink-soft leading-relaxed">
                Oui — c&apos;est précisé en permanence dans l&apos;interface.
                Si vous préférez parler à un humain de Vintiz, c&apos;est
                possible à tout moment via le formulaire de{" "}
                <Link
                  href="/contact"
                  className="underline underline-offset-2 hover:text-vz-teal"
                >
                  contact
                </Link>
                .
              </p>
            </div>
          </div>
        </section>

        {/* CTA finale */}
        <section className="bg-vz-bg-alt border-y border-black/5">
          <div className="max-w-3xl mx-auto px-6 py-16 lg:py-20 text-center">
            <h2 className="font-display text-3xl sm:text-4xl text-vz-ink leading-tight">
              Prête à être guidée ?
            </h2>
            <p className="mt-5 text-lg text-vz-ink-soft leading-relaxed">
              Activez votre Personal Shopper en quelques clics et recevez vos
              premières recommandations sur-mesure.
            </p>
            <Link
              href="/account/login"
              className="mt-8 inline-flex items-center justify-center rounded-full bg-vz-teal text-white px-8 py-3.5 text-sm font-medium hover:bg-vz-teal-deep transition-colors"
            >
              Activer mon Personal Shopper
            </Link>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  );
}
