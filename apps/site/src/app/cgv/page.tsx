import PublicHeader from "@/components/PublicHeader";
import PublicFooter from "@/components/PublicFooter";
import LegalDraftNotice from "@/components/LegalDraftNotice";
import { LEGAL_INFO, isPlaceholder, legalValue } from "@/data/legal-info";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Conditions générales de vente",
  description:
    "Conditions générales de vente de la boutique Vintiz, Vernon (27200) — seconde main premium, programme fidélité, retours et avoirs.",
  robots: { index: false, follow: true },
};

export default function CGVPage() {
  return (
    <>
      <PublicHeader />
      <section className="pt-12 pb-20 px-6 bg-vz-bg min-h-screen">
        <div className="max-w-3xl mx-auto">
          <h1 className="font-display text-3xl text-black mb-8">
            Conditions Générales de Vente
          </h1>
          <p className="text-xs text-black/50 mb-8">
            Dernière mise à jour : avril 2026
          </p>

          <LegalDraftNotice />

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 1 — Objet
          </h2>
          <p className="text-black/70 leading-relaxed">
            Les présentes conditions générales de vente s&apos;appliquent à
            toutes les ventes effectuées en boutique Vintiz, 6 rue
            Saint-Jacques, 27200 Vernon.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 2 — Produits
          </h2>
          <p className="text-black/70 leading-relaxed">
            Vintiz propose des vêtements et accessoires de seconde main. Chaque
            article est unique et vendu en l&apos;état. L&apos;état du produit
            est indiqué sur l&apos;étiquette (excellent, très bon, bon,
            correct). Les articles sont vérifiés avant mise en vente.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 3 — Prix
          </h2>
          <p className="text-black/70 leading-relaxed">
            Les prix sont affichés en euros TTC (TVA 20 % incluse). Les prix
            peuvent être modifiés à tout moment&nbsp;; le prix applicable est
            celui en vigueur au moment de l&apos;encaissement.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 4 — Paiement
          </h2>
          <p className="text-black/70 leading-relaxed">
            Les modes de paiement acceptés sont&nbsp;: <strong>espèces</strong>,{" "}
            <strong>carte bancaire</strong> (terminal SumUp Solo),{" "}
            <strong>chèque</strong> à l&apos;ordre de Vintiz, et{" "}
            <strong>avoir client</strong> (store credit) lorsque vous en
            disposez. Le paiement peut être <strong>fractionné</strong> entre
            plusieurs méthodes (paiement mixte). Il est exigible au moment de
            l&apos;encaissement.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 5 — Échanges et remboursements
          </h2>
          <p className="text-black/70 leading-relaxed">
            Compte tenu de la nature des produits (articles de seconde main
            uniques), les ventes sont en principe fermes et définitives. Vintiz
            accepte toutefois, dans les cas suivants, un retour&nbsp;:
          </p>
          <ul className="list-disc pl-6 mt-2 space-y-2 text-black/70">
            <li>
              <strong>Défaut caché</strong> non signalé lors de la vente —
              signalement à effectuer dans les 7 jours suivant l&apos;achat,
              sur présentation du ticket.
            </li>
            <li>
              <strong>Geste commercial</strong> à la discrétion de la
              responsable de magasin.
            </li>
          </ul>
          <p className="text-black/70 leading-relaxed mt-3">
            Le remboursement peut, au choix de la cliente, prendre la forme
            d&apos;un règlement par le moyen initial (espèces, virement carte)
            ou d&apos;un <strong>avoir</strong> utilisable sans limite de durée
            sur tout achat ultérieur. Un ticket de retour est systématiquement
            remis et le retour est tracé conformément à la norme NF525.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 6 — Garanties légales
          </h2>
          <p className="text-black/70 leading-relaxed">
            Indépendamment des retours commerciaux ci-dessus, le consommateur
            bénéficie des garanties légales d&apos;ordre public&nbsp;:
          </p>
          <ul className="list-disc pl-6 mt-2 space-y-2 text-black/70">
            <li>
              la <strong>garantie légale de conformité</strong> (art. L217-3 et
              suivants du Code de la consommation), qui s&apos;applique aux
              biens d&apos;occasion&nbsp;; l&apos;état d&apos;usage de chaque
              pièce, décrit sur l&apos;étiquette et accepté à l&apos;achat, ne
              constitue pas un défaut de conformité&nbsp;;
            </li>
            <li>
              la <strong>garantie contre les vices cachés</strong>
              {" "}(art. 1641 et suivants du Code civil).
            </li>
          </ul>
          <p className="text-black/70 leading-relaxed mt-3">
            Pour mettre en œuvre ces garanties, contactez-nous à
            contact@vintiz.fr ou présentez-vous en boutique avec votre ticket.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 7 — Programme fidélité
          </h2>
          <p className="text-black/70 leading-relaxed">
            Le programme de fidélité Vintiz est <strong>100 % digital</strong>{" "}
            (carte virtuelle Apple Wallet / Google Wallet, n° de carte au format
            <code className="font-mono mx-1">V######</code>). Selon
            l&apos;opération en cours, l&apos;adhésion peut être gratuite,
            payante ou offerte au-delà d&apos;un montant d&apos;achat — les
            conditions actives sont affichées en boutique au moment de la
            souscription. Mécanique unique&nbsp;:{" "}
            <strong>1 € dépensé = 1 point</strong>. Tous les{" "}
            <strong>100 points</strong>, un bon d&apos;achat de 8 € est généré
            automatiquement (durée de validité affichée en boutique et dans
            votre espace client, par défaut 6 mois). Les points expirent au
            bout de <strong>24 mois sans activité</strong>. Vintiz se réserve le droit
            de modifier les conditions du programme avec préavis affiché en
            boutique et envoyé par email aux membres opt-in.
          </p>
          <p className="text-black/70 leading-relaxed mt-3">
            Le programme inclut un{" "}
            <strong>Personal Shopper</strong> (sélection IA de pièces
            disponibles en boutique en fonction de l&apos;historique d&apos;achat
            et des goûts déclarés) et des{" "}
            <strong>alertes de nouveautés tendance</strong> par email. Ces
            services sont strictement réservés aux membres et nécessitent un
            consentement explicite « profilage » et « alertes nouveautés », tous
            deux désactivables à tout moment dans l&apos;espace client. Aucune
            vente n&apos;est réalisée en ligne&nbsp;: ces outils ont vocation à
            préparer une visite en boutique à Vernon.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 8 — Avoir (store credit)
          </h2>
          <p className="text-black/70 leading-relaxed">
            Un avoir vous est remis lorsque vous demandez le remboursement
            d&apos;un article éligible et choisissez ce mode (au lieu d&apos;un
            règlement immédiat). Le solde de votre avoir est consultable à tout
            moment depuis votre{" "}
            <Link href="/account" className="text-vz-teal underline">
              espace personnel
            </Link>
            . Il est utilisable lors de tout achat futur, en boutique
            uniquement, par une employée Vintiz qui vous identifie via votre
            adresse e-mail. L&apos;avoir n&apos;est pas convertible en espèces.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 9 — Données personnelles
          </h2>
          <p className="text-black/70 leading-relaxed">
            Le traitement de vos données personnelles est encadré par notre{" "}
            <Link href="/confidentialite" className="text-vz-teal underline">
              politique de confidentialité
            </Link>
            . Vous pouvez, à tout moment, télécharger vos données ou demander
            leur suppression depuis votre{" "}
            <Link href="/account" className="text-vz-teal underline">
              espace personnel
            </Link>
            .
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 10 — Litiges et médiation
          </h2>
          <p className="text-black/70 leading-relaxed">
            Les présentes CGV sont soumises au droit français. En cas de litige,
            une solution amiable sera recherchée en premier lieu (contact&nbsp;:
            contact@vintiz.fr). À défaut, le tribunal compétent sera celui de
            Vernon.
          </p>
          <p className="text-black/70 leading-relaxed mt-3">
            Conformément à l&apos;article L612-1 du Code de la consommation, vous
            pouvez recourir gratuitement au médiateur de la consommation désigné
            par {LEGAL_INFO.tradeName} en vue de la résolution amiable de tout
            litige&nbsp;: <strong>{legalValue(LEGAL_INFO.mediator.name)}</strong>
            {!isPlaceholder(LEGAL_INFO.mediator.url) && (
              <>
                {" "}(
                <a href={LEGAL_INFO.mediator.url} className="text-vz-teal underline" target="_blank" rel="noopener noreferrer">
                  {LEGAL_INFO.mediator.url}
                </a>
                )
              </>
            )}
            . Le recours à la médiation est possible après une réclamation
            écrite préalable restée sans réponse satisfaisante.
          </p>
        </div>
      </section>
      <PublicFooter />
    </>
  );
}
