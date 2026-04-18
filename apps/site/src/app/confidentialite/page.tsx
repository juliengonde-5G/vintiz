import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Politique de confidentialité",
  description:
    "Politique de confidentialité et gestion des cookies de la boutique Vintiz (Vernon, Normandie). Conformité RGPD.",
  robots: { index: false, follow: true },
};

export default function ConfidentialitePage() {
  return (
    <>
      <Navbar />
      <section className="pt-28 pb-20 px-6 bg-cream min-h-screen">
        <div className="max-w-3xl mx-auto">
          <h1 className="font-display text-3xl text-black mb-8">
            Politique de confidentialité
          </h1>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Responsable du traitement
          </h2>
          <p className="text-black/70 leading-relaxed">
            Vintiz — 6 rue Saint-Jacques, 27200 Vernon, France. Contact : contact@vintiz.fr.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Données collectées
          </h2>
          <p className="text-black/70 leading-relaxed">
            Sur ce site vitrine, seules les adresses e-mail déposées via le formulaire
            d&apos;inscription à la newsletter sont collectées. Elles sont utilisées
            exclusivement pour vous informer de l&apos;ouverture de la boutique et de nos
            actualités. Vous pouvez vous désinscrire à tout moment.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">Cookies</h2>
          <p className="text-black/70 leading-relaxed">
            Ce site utilise uniquement des cookies fonctionnels nécessaires à son
            fonctionnement. Avec votre accord explicite (bandeau de consentement), des
            cookies de mesure d&apos;audience anonyme (Google Analytics 4 avec IP
            anonymisée et Consent Mode v2) peuvent être déposés afin de comprendre
            comment les visiteurs utilisent le site. Aucun cookie publicitaire n&apos;est
            déposé.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">Vos droits</h2>
          <p className="text-black/70 leading-relaxed">
            Conformément au RGPD et à la loi Informatique et Libertés, vous disposez
            d&apos;un droit d&apos;accès, de rectification, d&apos;effacement, de limitation, d&apos;opposition
            et de portabilité de vos données. Pour exercer ces droits, écrivez-nous à
            contact@vintiz.fr. Vous pouvez également introduire une réclamation auprès
            de la CNIL (www.cnil.fr).
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">Conservation</h2>
          <p className="text-black/70 leading-relaxed">
            Les adresses e-mail newsletter sont conservées jusqu&apos;à votre désinscription.
            Les données de mesure d&apos;audience sont conservées 14 mois.
          </p>
        </div>
      </section>
      <Footer />
    </>
  );
}
