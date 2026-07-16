import PublicHeader from "@/components/PublicHeader";
import PublicFooter from "@/components/PublicFooter";
import LegalDraftNotice from "@/components/LegalDraftNotice";
import { LEGAL_INFO, isPlaceholder, legalValue } from "@/data/legal-info";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Mentions légales",
  description: "Mentions légales de la boutique Vintiz, Vernon (27200).",
  robots: { index: false, follow: true },
};

export default function MentionsLegalesPage() {
  return (
    <>
      <PublicHeader />
      <section className="pt-12 pb-20 px-6 bg-vz-bg min-h-screen">
        <div className="max-w-3xl mx-auto prose prose-sm">
          <h1 className="font-serif text-3xl text-vz-ink mb-8">Mentions légales</h1>

          <LegalDraftNotice />

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">Éditeur du site</h2>
          <p className="text-vz-ink/70 leading-relaxed">
            {LEGAL_INFO.tradeName}<br />
            6 rue Saint-Jacques<br />
            27200 Vernon<br />
            France<br />
            Téléphone : {legalValue(LEGAL_INFO.phone)}<br />
            E-mail : {LEGAL_INFO.email}
          </p>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">
            Identité de l&apos;entreprise
          </h2>
          {/* Mentions obligatoires (LCEN art. 6-III, C. com. art. R123-237).
              Valeurs centralisées dans data/legal-info.ts (point unique). */}
          <p className="text-vz-ink/70 leading-relaxed">
            Forme juridique : {legalValue(LEGAL_INFO.legalForm)}<br />
            Capital social : {legalValue(LEGAL_INFO.capital)}<br />
            SIREN / SIRET : {legalValue(LEGAL_INFO.siret)}<br />
            RCS : {legalValue(LEGAL_INFO.rcs)}<br />
            N° TVA intracommunautaire : {legalValue(LEGAL_INFO.vatNumber)}<br />
            Directeur / responsable de la publication :{" "}
            {legalValue(LEGAL_INFO.publicationDirector)}
          </p>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">Hébergement</h2>
          <p className="text-vz-ink/70 leading-relaxed">
            Scaleway SAS<br />
            8 rue de la Ville l&apos;Évêque<br />
            75008 Paris, France<br />
            Téléphone : +33 (0)1 84 13 00 00
          </p>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">
            Données personnelles &amp; DPO
          </h2>
          <p className="text-vz-ink/70 leading-relaxed">
            Le responsable de traitement des données collectées sur ce site est
            <strong> Vintiz</strong> (responsable unique), immatriculé à Vernon.
            La fonction de Délégué à la Protection des Données (DPO) est assurée
            par notre partenaire Solidarité Textiles. Vous pouvez exercer vos
            droits d&apos;accès, rectification, suppression et portabilité
            directement depuis votre espace client (rubrique
            <em> Confidentialité &amp; RGPD</em>) ou par email auprès du DPO&nbsp;:
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
              <strong>Anthropic</strong> — API commerciale Claude
              (Personal Shopper, alertes tendance, audit RGPD). Données
              transmises&nbsp;: attributs de produits, contexte de recommandation
              et requêtes de recherche. Le traitement peut impliquer un
              transfert vers les États-Unis&nbsp;; voir la politique de
              confidentialité.
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

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">
            Marques citées
          </h2>
          <p className="text-vz-ink/70 leading-relaxed">
            Vintiz est une boutique indépendante de vêtements de seconde main.
            Les marques citées sur ce site (Sandro, Maje, Sézane, Polène, IRO,
            Isabel Marant, Ba&amp;sh, Vanessa Bruno, The Kooples, etc.)
            appartiennent à leurs propriétaires respectifs. Leur citation a pour
            seul objet de décrire des articles authentiques d&apos;occasion
            proposés à la revente&nbsp;; elle n&apos;implique aucun partenariat,
            parrainage ni affiliation avec ces marques.
          </p>

          <h2 className="font-serif text-xl text-vz-ink mt-8 mb-3">
            Médiation de la consommation
          </h2>
          <p className="text-vz-ink/70 leading-relaxed">
            Conformément à l&apos;article L612-1 du Code de la consommation, le
            consommateur peut recourir gratuitement à un médiateur de la
            consommation en vue de la résolution amiable d&apos;un litige.
            Médiateur désigné par {LEGAL_INFO.tradeName}&nbsp;:{" "}
            <strong>{legalValue(LEGAL_INFO.mediator.name)}</strong>
            {!isPlaceholder(LEGAL_INFO.mediator.address) && (
              <> — {LEGAL_INFO.mediator.address}</>
            )}
            {!isPlaceholder(LEGAL_INFO.mediator.url) && (
              <>
                {" "}(
                <a
                  href={LEGAL_INFO.mediator.url}
                  className="text-vz-teal underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {LEGAL_INFO.mediator.url}
                </a>
                )
              </>
            )}
            .
          </p>
        </div>
      </section>
      <PublicFooter />
    </>
  );
}
