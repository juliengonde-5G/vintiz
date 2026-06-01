import PublicHeader from "@/components/PublicHeader";
import PublicFooter from "@/components/PublicFooter";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Politique de confidentialité",
  description:
    "Politique de confidentialité, traitement des données et gestion des cookies de la boutique Vintiz (Vernon, Normandie). Conformité RGPD.",
  robots: { index: false, follow: true },
};

export default function ConfidentialitePage() {
  return (
    <>
      <PublicHeader />
      <section className="pt-12 pb-20 px-6 bg-vz-bg min-h-screen">
        <div className="max-w-3xl mx-auto">
          <h1 className="font-display text-3xl text-black mb-8">
            Politique de confidentialité
          </h1>
          <p className="text-xs text-black/50 mb-8">
            Dernière mise à jour : avril 2026 — version v1.0-2026-04
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Responsable du traitement
          </h2>
          <p className="text-black/70 leading-relaxed">
            Le responsable de traitement est <strong>Vintiz</strong> — 6 rue
            Saint-Jacques, 27200 Vernon, France (responsable unique). La
            fonction de Délégué à la Protection des Données (DPO) est assurée
            par notre partenaire Solidarité Textiles&nbsp;; vous pouvez le
            contacter à <strong>dpo@solidarite-textiles.fr</strong>.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Données collectées
          </h2>
          <p className="text-black/70 leading-relaxed">
            Selon votre interaction avec Vintiz, nous collectons les données
            suivantes&nbsp;:
          </p>
          <ul className="list-disc pl-6 mt-2 space-y-2 text-black/70">
            <li>
              <strong>Newsletter</strong> — adresse e-mail, date, heure et adresse
              IP du consentement (preuve RGPD).
            </li>
            <li>
              <strong>Carte de fidélité</strong> (souscription en boutique) —
              prénom, nom, e-mail, téléphone, achats, points de fidélité, niveau
              de carte, et solde d&apos;avoir éventuel.
            </li>
            <li>
              <strong>Personal Shopper IA</strong> (sur demande) — préférences de
              style, tailles, marques, dérivées de votre historique d&apos;achats
              afin de vous proposer des sélections personnalisées.
            </li>
            <li>
              <strong>Encaissement</strong> — chaque vente est enregistrée
              conformément à la norme NF525 (loi anti-fraude TVA), avec montant,
              articles, méthode de paiement et chaînage cryptographique.
            </li>
          </ul>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Finalités et bases légales
          </h2>
          <ul className="list-disc pl-6 mt-2 space-y-2 text-black/70">
            <li>
              <strong>Newsletter</strong> — consentement explicite (RGPD art.
              6.1.a). Retirable à tout moment via le lien de désinscription.
            </li>
            <li>
              <strong>Programme fidélité, avoirs, historique d&apos;achats</strong>
              {" "}— exécution de la relation commerciale (RGPD art. 6.1.b).
            </li>
            <li>
              <strong>Personal Shopper IA et profilage</strong> — consentement
              explicite (RGPD art. 6.1.a + art. 22). Vos préférences de style,
              tailles, couleurs et historique d&apos;achats alimentent un
              modèle d&apos;embeddings (sous-traitant&nbsp;: Anthropic Ireland
              pour Claude Haiku 4.5). Durée de conservation 36 mois maximum
              après le dernier achat. Retrait via le toggle Personal Shopper
              dans votre{" "}
              <Link href="/account/rgpd" className="text-vz-teal underline">
                espace de gestion des données
              </Link>
              .
            </li>
            <li>
              <strong>Alertes nouveautés tendance par email</strong> —
              consentement explicite séparé du profilage. Un produit
              fraîchement arrivé en boutique et compatible avec votre profil
              déclenche au maximum un email tous les 7 jours. Retrait 1-clic
              dans chaque email ou via la page espace client RGPD.
            </li>
            <li>
              <strong>Souscription carte fidélité au POS</strong> — l&apos;équipe
              boutique enregistre nom, prénom, code postal et email avec votre
              consentement explicite (newsletter et profilage cochés
              séparément). Le n° de carte (V######) est généré automatiquement.
            </li>
            <li>
              <strong>Comptabilité fiscale</strong> — obligation légale (CGI,
              décret 2016-1138 NF525) imposant la conservation 6 ans des
              transactions.
            </li>
          </ul>

          <h2 className="font-display text-xl text-black mt-8 mb-3">Cookies</h2>
          <p className="text-black/70 leading-relaxed">
            Ce site utilise uniquement des cookies fonctionnels nécessaires à
            son fonctionnement. Avec votre accord explicite (bandeau de
            consentement), des cookies de mesure d&apos;audience anonyme (Google
            Analytics 4 avec IP anonymisée et Consent Mode v2) peuvent être
            déposés. Aucun cookie publicitaire n&apos;est déposé.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Vos droits
          </h2>
          <p className="text-black/70 leading-relaxed">
            Conformément au RGPD et à la loi Informatique et Libertés, vous
            disposez des droits suivants&nbsp;:
          </p>
          <ul className="list-disc pl-6 mt-2 space-y-2 text-black/70">
            <li>
              <strong>Accès et portabilité</strong> (art. 15 + 20) — visualiser
              et télécharger l&apos;ensemble de vos données au format JSON depuis{" "}
              <Link href="/account/rgpd" className="text-vz-teal underline">
                /account/rgpd
              </Link>
              .
            </li>
            <li>
              <strong>Rectification</strong> (art. 16) — demande à
              dpo@solidarite-textiles.fr ou directement en boutique.
            </li>
            <li>
              <strong>Effacement / droit à l&apos;oubli</strong> (art. 17) —
              demande en self-service depuis{" "}
              <Link href="/account/rgpd" className="text-vz-teal underline">
                /account/rgpd
              </Link>
              . La suppression effective intervient sous 30 jours pour permettre
              une éventuelle annulation. Les transactions soumises à
              l&apos;obligation NF525 (6 ans) sont conservées mais anonymisées
              (votre identité est dissociée du paiement).
            </li>
            <li>
              <strong>Limitation et opposition</strong> (art. 18 + 21) —
              dpo@solidarite-textiles.fr.
            </li>
            <li>
              <strong>Réclamation</strong> auprès de la CNIL (www.cnil.fr).
            </li>
          </ul>
          <p className="text-black/70 leading-relaxed mt-3">
            Nous répondons à toute demande sous un délai maximum de 30 jours.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Conservation
          </h2>
          <ul className="list-disc pl-6 mt-2 space-y-2 text-black/70">
            <li>
              <strong>Newsletter</strong> — jusqu&apos;à désinscription, et au
              plus tard 3 ans sans interaction (standard CNIL prospection).
            </li>
            <li>
              <strong>Compte client / carte de fidélité</strong> — pendant la
              durée de la relation commerciale, puis 5 ans après la dernière
              transaction.
            </li>
            <li>
              <strong>Données de transaction (NF525)</strong> — 6 ans, obligation
              légale (article L102 B du Livre des procédures fiscales).
            </li>
            <li>
              <strong>Mesure d&apos;audience</strong> — 14 mois.
            </li>
          </ul>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Destinataires et sous-traitants
          </h2>
          <p className="text-black/70 leading-relaxed">
            Vos données ne sont transmises à aucun tiers commercial. Les
            sous-traitants techniques utilisés sont&nbsp;:
          </p>
          <ul className="list-disc pl-6 mt-2 space-y-2 text-black/70">
            <li>
              <strong>Scaleway</strong> (hébergement, France) — base de données
              et application.
            </li>
            <li>
              <strong>Anthropic</strong> (API Claude, AWS Europe) — analyse
              automatisée des fiches produits et rédaction des recommandations
              Personal Shopper. Les données envoyées sont strictement
              fonctionnelles (description du panier ou du produit) et ne sont
              pas conservées par Anthropic après inférence.
            </li>
            <li>
              <strong>SumUp</strong> (paiement CB) — informations de paiement
              traitées directement par SumUp&nbsp;; Vintiz n&apos;a accès qu&apos;à
              un identifiant de transaction non nominatif.
            </li>
            <li>
              <strong>Brevo (Sendinblue)</strong> — envoi des newsletters, des
              emails et SMS transactionnels et marketing (adresse e-mail /
              numéro de téléphone uniquement). Sous-traitant établi dans
              l&apos;Union européenne.
            </li>
            <li>
              <strong>Twilio</strong> (fournisseur SMS de secours) — uniquement
              pour l&apos;envoi de votre code de connexion ou de votre ticket par
              SMS lorsque vous nous le demandez.
            </li>
          </ul>
          <p className="text-black/70 leading-relaxed mt-2">
            Le QR code de votre carte de fidélité est généré localement (dans
            votre navigateur ou sur nos serveurs)&nbsp;: votre numéro de carte
            n&apos;est transmis à aucun service tiers.
          </p>
          <p className="text-black/70 leading-relaxed mt-2">
            Aucun transfert hors Union européenne n&apos;est effectué pour les
            données de profil&nbsp;; l&apos;API Claude est utilisée via une
            instance européenne.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">Sécurité</h2>
          <p className="text-black/70 leading-relaxed">
            Les données sont stockées dans une base de données PostgreSQL
            sauvegardée quotidiennement (sauvegardes chiffrées). Les accès
            administratifs sont protégés par authentification forte
            (mot de passe + PIN cashier 4 chiffres). Toute modification de
            donnée sensible est journalisée dans un registre d&apos;audit
            inaltérable. Les transactions de caisse sont chaînées par hash
            SHA-256 conformément à la norme NF525.
          </p>

          <h2
            id="personal-shopper"
            className="font-display text-xl text-black mt-8 mb-3 scroll-mt-24"
          >
            Profilage, Personal Shopper IA et décisions automatisées
          </h2>
          <p className="text-black/70 leading-relaxed">
            Le Personal Shopper IA et les recommandations de produits utilisent
            un traitement automatisé pour suggérer des articles susceptibles de
            vous plaire. Aucune décision automatisée produisant un effet juridique
            ou affectant significativement votre situation n&apos;est prise sur la
            base de ce profilage&nbsp;: il s&apos;agit uniquement de suggestions,
            qu&apos;une employée valide systématiquement avant tout envoi
            personnalisé. Vous pouvez à tout moment retirer votre consentement
            au profilage depuis votre{" "}
            <Link href="/account/rgpd" className="text-vz-teal underline">
              espace de gestion des données
            </Link>
            .
          </p>

          <p className="text-black/70 leading-relaxed mt-4">
            <strong>Conformité AI Act (UE 2024/1689, art. 50)</strong>
            &nbsp;— le Personal Shopper IA est un système d&apos;intelligence
            artificielle à risque limité au sens du règlement européen. À ce
            titre&nbsp;:
          </p>
          <ul className="mt-3 space-y-2 text-black/70 leading-relaxed list-disc list-inside">
            <li>
              vous êtes informée de manière permanente, dans l&apos;interface
              de votre espace client, que vous interagissez avec une IA&nbsp;;
            </li>
            <li>
              chaque recommandation produite par l&apos;IA est marquée comme
              telle (badge visible «&nbsp;IA&nbsp;» et marquage HTML
              <code className="text-xs bg-black/5 px-1 py-0.5 rounded mx-1">
                data-ai-generated=&quot;true&quot;
              </code>
              lisible par les outils d&apos;assistance et de transparence)&nbsp;;
            </li>
            <li>
              vous pouvez à tout moment demander l&apos;intervention d&apos;un
              humain Vintiz pour réviser une recommandation, en écrivant à
              {" "}
              <a
                href="mailto:dpo@solidarite-textiles.fr"
                className="text-vz-teal underline"
              >
                dpo@solidarite-textiles.fr
              </a>
              .
            </li>
          </ul>
          <p className="text-black/70 leading-relaxed mt-4">
            Le modèle utilisé est Claude Haiku 4.5 (Anthropic Ireland Limited,
            hébergement AWS Union européenne). Les données envoyées au modèle
            sont strictement nécessaires à la recommandation et ne sont pas
            conservées par Anthropic après inférence.
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Modification de cette politique
          </h2>
          <p className="text-black/70 leading-relaxed">
            Cette politique est versionnée. Chaque modification fait
            l&apos;objet d&apos;une nouvelle version (visible en haut de cette
            page) et, lorsqu&apos;elle est substantielle, vous est notifiée par
            e-mail si vous êtes inscrit·e à la newsletter ou détenteur d&apos;une
            carte fidélité.
          </p>
        </div>
      </section>
      <PublicFooter />
    </>
  );
}
