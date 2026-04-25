import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Conditions générales de vente",
  description: "Conditions générales de vente de la boutique Vintiz, Vernon (27200).",
  robots: { index: false, follow: true },
};

export default function CGVPage() {
  return (
    <>
      <Navbar />
      <section className="pt-28 pb-20 px-6 bg-vintiz-bg min-h-screen">
        <div className="max-w-3xl mx-auto prose prose-sm">
          <h1 className="font-serif text-3xl text-vintiz-black mb-8">Conditions Generales de Vente</h1>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Article 1 - Objet</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Les presentes conditions generales de vente s&apos;appliquent a toutes les ventes effectuees en boutique Vintiz, 6 rue Saint-Jacques, 27200 Vernon.
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Article 2 - Produits</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Vintiz propose des vetements et accessoires de seconde main. Chaque article est unique et vendu en l&apos;etat. L&apos;etat du produit est indique sur l&apos;etiquette. Les articles sont verifies avant mise en vente.
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Article 3 - Prix</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Les prix sont affiches en euros TTC (TVA 20% incluse). Les prix peuvent etre modifies a tout moment. Le prix applicable est celui en vigueur au moment de l&apos;achat.
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Article 4 - Paiement</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Les modes de paiement acceptes sont : especes, carte bancaire (via terminal SumUp), cheque et virement. Le paiement est exigible au moment de l&apos;achat.
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Article 5 - Echanges et remboursements</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Compte tenu de la nature des produits (articles de seconde main uniques), les ventes sont fermes et definitives. Aucun echange ni remboursement ne sera accepte, sauf defaut cache non signale lors de la vente. Dans ce cas, le client dispose de 7 jours pour signaler le defaut. Un avoir ou un echange sera alors propose.
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Article 6 - Programme fidelite</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Le programme de fidelite Vintiz permet de cumuler 1 point par euro depense. Les points sont convertibles en bons d&apos;achat selon le bareme en vigueur (100 points = 5&euro;). Les points sont valables 12 mois. Vintiz se reserve le droit de modifier les conditions du programme.
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Article 7 - Litiges</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Les presentes CGV sont soumises au droit francais. En cas de litige, une solution amiable sera recherchee. A defaut, le tribunal competent sera celui de Vernon.
          </p>
        </div>
      </section>
      <Footer />
    </>
  );
}
