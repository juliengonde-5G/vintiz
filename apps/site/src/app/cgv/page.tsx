import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
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
      <Navbar />
      <section className="pt-28 pb-20 px-6 bg-cream min-h-screen">
        <div className="max-w-3xl mx-auto">
          <h1 className="font-display text-3xl text-black mb-8">
            Conditions Générales de Vente
          </h1>
          <p className="text-xs text-black/50 mb-8">
            Dernière mise à jour : avril 2026
          </p>

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
            Article 6 — Programme fidélité
          </h2>
          <p className="text-black/70 leading-relaxed">
            Le programme de fidélité Vintiz est gratuit et accessible sur simple
            demande à la caisse. Il permet de cumuler{" "}
            <strong>1 point par euro dépensé</strong>. 1 point équivaut à 0,10 €
            de remise (soit 50 points = 5 €), utilisable jusqu&apos;à 50 % du
            panier. Trois niveaux structurent le programme&nbsp;: Bronze,
            Argent, Or — avec avantages croissants. Les points sont valables 12
            mois après la dernière transaction. Vintiz se réserve le droit de
            modifier les conditions du programme avec préavis.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 7 — Avoir (store credit)
          </h2>
          <p className="text-black/70 leading-relaxed">
            Un avoir vous est remis lorsque vous demandez le remboursement
            d&apos;un article éligible et choisissez ce mode (au lieu d&apos;un
            règlement immédiat). Le solde de votre avoir est consultable à tout
            moment depuis votre{" "}
            <Link href="/account/data" className="text-teal underline">
              espace personnel
            </Link>
            . Il est utilisable lors de tout achat futur, en boutique
            uniquement, par une employée Vintiz qui vous identifie via votre
            adresse e-mail. L&apos;avoir n&apos;est pas convertible en espèces.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 8 — Données personnelles
          </h2>
          <p className="text-black/70 leading-relaxed">
            Le traitement de vos données personnelles est encadré par notre{" "}
            <Link href="/confidentialite" className="text-teal underline">
              politique de confidentialité
            </Link>
            . Vous pouvez, à tout moment, télécharger vos données ou demander
            leur suppression depuis votre{" "}
            <Link href="/account/data" className="text-teal underline">
              espace personnel
            </Link>
            .
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Article 9 — Litiges
          </h2>
          <p className="text-black/70 leading-relaxed">
            Les présentes CGV sont soumises au droit français. En cas de litige,
            une solution amiable sera recherchée en premier lieu (contact&nbsp;:
            contact@vintiz.fr). À défaut, le tribunal compétent sera celui de
            Vernon. Conformément à la réglementation, vous pouvez recourir à
            une procédure de médiation conventionnelle ou à tout autre mode de
            résolution amiable des différends.
          </p>
        </div>
      </section>
      <Footer />
    </>
  );
}
