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
          <p className="text-xs text-black/50 mb-8">Dernière mise à jour : avril 2026</p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Responsable du traitement
          </h2>
          <p className="text-black/70 leading-relaxed">
            Vintiz — 6 rue Saint-Jacques, 27200 Vernon, France. Contact :
            dpo@solidarite-textiles.fr.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Données collectées
          </h2>
          <p className="text-black/70 leading-relaxed">
            Sur ce site vitrine, seules les adresses e-mail déposées via le formulaire
            d&apos;inscription à la newsletter sont collectées. Lors de votre inscription,
            nous enregistrons également la date et l&apos;heure du consentement ainsi que
            l&apos;adresse IP ayant servi à le donner — à des fins exclusives de preuve du
            consentement conformément au RGPD. Aucune autre donnée personnelle
            n&apos;est collectée.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Finalité et base légale
          </h2>
          <p className="text-black/70 leading-relaxed">
            Finalité : vous informer de l&apos;ouverture de la boutique, des ventes privées
            et des nouveautés. Base légale : votre <strong>consentement explicite</strong>{" "}
            (RGPD art. 6.1.a), matérialisé par la case à cocher du formulaire. Vous
            pouvez retirer ce consentement à tout moment sans motif via le lien de
            désinscription présent dans chaque e-mail que nous vous envoyons, ou en
            écrivant à dpo@solidarite-textiles.fr.
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
            et de portabilité de vos données. Pour exercer ces droits, écrivez à
            dpo@solidarite-textiles.fr. Nous répondons sous un délai maximum de 30 jours.
            Vous pouvez également introduire une réclamation auprès de la CNIL
            (www.cnil.fr).
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">Conservation</h2>
          <p className="text-black/70 leading-relaxed">
            Les adresses e-mail newsletter sont conservées jusqu&apos;à votre désinscription,
            et au plus tard pendant <strong>3 ans sans interaction</strong> avec nos e-mails
            (standard CNIL pour la prospection). Passé ce délai, elles sont
            automatiquement supprimées. Les données de mesure d&apos;audience sont
            conservées 14 mois.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Destinataires et sous-traitants
          </h2>
          <p className="text-black/70 leading-relaxed">
            Vos données ne sont transmises à aucun tiers commercial. Elles sont stockées
            sur nos serveurs hébergés en France et ne font l&apos;objet d&apos;aucun transfert
            hors Union européenne. Seul le personnel autorisé de Vintiz peut y accéder.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">Sécurité</h2>
          <p className="text-black/70 leading-relaxed">
            Les données sont stockées dans une base de données PostgreSQL sauvegardée
            quotidiennement (sauvegardes chiffrées). Les accès administratifs sont
            protégés par authentification forte et journalisation.
          </p>
        </div>
      </section>
      <Footer />
    </>
  );
}
