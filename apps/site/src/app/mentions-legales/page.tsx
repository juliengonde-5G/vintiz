import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mentions légales",
  description: "Mentions légales de la boutique Vintiz, Vernon (27200).",
  robots: { index: false, follow: true },
};

export default function MentionsLegalesPage() {
  return (
    <>
      <Navbar />
      <section className="pt-28 pb-20 px-6 bg-vz-bg min-h-screen">
        <div className="max-w-3xl mx-auto prose prose-sm">
          <h1 className="font-serif text-3xl text-vz-ink mb-8">Mentions légales</h1>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">Éditeur du site</h2>
          <p className="text-vz-ink/70 leading-relaxed">
            Vintiz<br />
            6 rue Saint-Jacques<br />
            27200 Vernon<br />
            France
          </p>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">Hébergement</h2>
          <p className="text-vz-ink/70 leading-relaxed">
            Scaleway SAS<br />
            8 rue de la Ville l&apos;Évêque<br />
            75008 Paris, France
          </p>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">
            Données personnelles &amp; DPO
          </h2>
          <p className="text-vz-ink/70 leading-relaxed">
            Le responsable de traitement des données collectées sur ce site est
            Vintiz, immatriculé à Vernon. Vous pouvez exercer vos droits
            d&apos;accès, rectification, suppression et portabilité directement
            depuis votre espace client (rubrique <em>Confidentialité &amp;
            RGPD</em>) ou par email auprès du Délégué à la Protection des
            Données&nbsp;:
            {" "}
            <a
              href="mailto:dpo@solidarite-textiles.fr"
              className="text-vz-teal underline"
            >
              dpo@solidarite-textiles.fr
            </a>
            .
          </p>
          <p className="text-vz-ink/70 leading-relaxed mt-3">
            Sous-traitants principaux&nbsp;:
          </p>
          <ul className="list-disc pl-6 text-vz-ink/70 leading-relaxed">
            <li>
              <strong>Anthropic Ireland Ltd.</strong> — service Claude
              (Personal Shopper, alertes tendance, audit RGPD). Données
              transmises&nbsp;: embeddings de texte, requêtes de recherche.
            </li>
            <li>
              <strong>Brevo (Sendinblue)</strong> — envoi des emails
              transactionnels et marketing.
            </li>
            <li>
              <strong>SumUp</strong> — encaissement carte bancaire.
            </li>
            <li>
              <strong>Scaleway SAS</strong> — hébergement applicatif et base
              de données.
            </li>
          </ul>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">Cookies</h2>
          <p className="text-vz-ink/70 leading-relaxed">
            Ce site utilise des cookies techniques strictement nécessaires à
            son fonctionnement et, sous réserve de votre consentement explicite
            (bandeau de consentement), des cookies de mesure d&apos;audience
            anonyme (Google Analytics 4 avec IP anonymisée et Consent Mode v2).
            Aucun cookie publicitaire n&apos;est déposé.
          </p>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">
            Propriété intellectuelle
          </h2>
          <p className="text-vz-ink/70 leading-relaxed">
            L&apos;ensemble du contenu de ce site (textes, images, logo) est la
            propriété exclusive de Vintiz. Toute reproduction est interdite
            sans autorisation préalable.
          </p>
        </div>
      </section>
      <Footer />
    </>
  );
}
