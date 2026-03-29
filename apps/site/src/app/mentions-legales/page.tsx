import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mentions Legales | Vintiz",
};

export default function MentionsLegalesPage() {
  return (
    <>
      <Navbar />
      <section className="pt-28 pb-20 px-6 bg-vintiz-bg min-h-screen">
        <div className="max-w-3xl mx-auto prose prose-sm">
          <h1 className="font-serif text-3xl text-vintiz-black mb-8">Mentions Legales</h1>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Editeur du site</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Vintiz<br />
            6 rue Saint-Jacques<br />
            27200 Vernon<br />
            France
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Hebergement</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Scaleway SAS<br />
            8 rue de la Ville l&apos;Eveque<br />
            75008 Paris, France
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Donnees personnelles</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Les informations recueillies sur ce site sont destinees a Vintiz pour la gestion de la relation client et l&apos;envoi de newsletters. Conformement au RGPD, vous disposez d&apos;un droit d&apos;acces, de rectification et de suppression de vos donnees. Pour exercer ces droits, contactez-nous en boutique ou par le formulaire de contact.
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Cookies</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            Ce site utilise uniquement des cookies techniques strictement necessaires a son fonctionnement. Aucun cookie publicitaire ou de suivi n&apos;est utilise.
          </p>

          <h2 className="font-serif text-xl text-vintiz-black mt-8 mb-3">Propriete intellectuelle</h2>
          <p className="text-vintiz-black/70 leading-relaxed">
            L&apos;ensemble du contenu de ce site (textes, images, logo) est la propriete exclusive de Vintiz. Toute reproduction est interdite sans autorisation prealable.
          </p>
        </div>
      </section>
      <Footer />
    </>
  );
}
