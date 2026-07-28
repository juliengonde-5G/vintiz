import PublicHeader from "@/components/PublicHeader";
import PublicFooter from "@/components/PublicFooter";
import MatomoOptOut from "@/components/MatomoOptOut";
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
            Dernière mise à jour : 16 juillet 2026 — version v1.1-2026-07
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
              <strong>Encaissement</strong> — chaque vente est enregistrée avec
              montant, articles, méthode de paiement et chaînage
              cryptographique, dans le cadre de la démarche de certification
              du logiciel de caisse. Vintiz ne revendique pas encore une
              certification NF525.
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
              modèle d&apos;embeddings. Claude Haiku 4.5, fourni par Anthropic,
              peut rédiger la recommandation. Le profil dérivé est supprimé
              dès le retrait du consentement et, à défaut, après 24 mois
              d&apos;inactivité. Retrait via le toggle Personal Shopper dans
              votre{" "}
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

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Cookies et mesure d&apos;audience
          </h2>
          <p className="text-black/70 leading-relaxed">
            Ce site utilise uniquement des cookies fonctionnels nécessaires à
            son fonctionnement. Notre mesure d&apos;audience s&apos;appuie sur{" "}
            <strong>Matomo en mode «&nbsp;sans cookie&nbsp;»</strong> (IP
            anonymisée, pas de suivi entre sites, données non partagées)&nbsp;:
            conforme aux critères d&apos;exemption de la CNIL, elle{" "}
            <strong>ne nécessite pas votre consentement</strong> et ne dépose
            aucun cookie. Aucun cookie publicitaire tiers n&apos;est déposé. Le
            cas échéant, un outil complémentaire soumis à consentement (Google
            Analytics&nbsp;4) ne serait activé qu&apos;après votre accord via le
            bandeau, révocable à tout moment depuis le lien «&nbsp;Gérer les
            cookies&nbsp;» en pied de page.
          </p>
          <p className="text-black/70 leading-relaxed mt-3">
            Vous pouvez à tout moment vous opposer à cette mesure d&apos;audience
            anonyme&nbsp;:
          </p>
          <MatomoOptOut />

          <h2 className="font-display text-xl text-black mt-8 mb-3">
            Pixels de suivi dans les e-mails
          </h2>
          <p className="text-black/70 leading-relaxed">
            Nos e-mails marketing peuvent contenir un pixel mesurant leur
            ouverture. Conformément à la recommandation de la CNIL, ce suivi
            individuel n&apos;est réalisé qu&apos;avec votre consentement
            spécifique&nbsp;: vous pouvez l&apos;accorder ou le retirer à tout
            moment depuis{" "}
            <Link href="/account/rgpd" className="text-vz-teal underline">
              /account/rgpd
            </Link>{" "}
            (consentement «&nbsp;Suivi d&apos;ouverture des e-mails&nbsp;»),
            indépendamment de votre inscription à la newsletter. À défaut de
            consentement, la mesure reste strictement anonyme et agrégée.
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
              <strong>Profil Personal Shopper</strong> — jusqu&apos;au retrait du
              consentement ou, à défaut, 24 mois sans activité. La preuve du
              retrait reste conservée dans le registre de consentement.
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
              <strong>Anthropic</strong> (API commerciale Claude) — analyse
              automatisée des fiches produits et rédaction des recommandations
              Personal Shopper. Seules les données nécessaires à la demande
              sont transmises. Anthropic indique que les entrées et sorties de
              son API commerciale ne servent pas, par défaut, à entraîner ses
              modèles et sont supprimées sous 30 jours dans le régime standard,
              sous réserve des exceptions prévues par ses conditions.
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
            L&apos;utilisation de l&apos;API Claude peut entraîner un traitement dans
            plusieurs régions et un stockage aux États-Unis par défaut. Elle
            implique donc un transfert de données hors de l&apos;Espace économique
            européen, à encadrer par les garanties contractuelles applicables.
            Les détails à jour sont disponibles dans le{" "}
            <a
              href="https://privacy.claude.com/en/articles/7996890-where-are-your-servers-located-do-you-host-your-models-on-eu-servers"
              className="text-vz-teal underline"
              rel="noreferrer"
              target="_blank"
            >
              centre de confidentialité Anthropic
            </a>
            .
          </p>

          <h2 className="font-display text-xl text-black mt-8 mb-3">Sécurité</h2>
          <p className="text-black/70 leading-relaxed">
            Les données sont stockées dans une base PostgreSQL sauvegardée
            quotidiennement. Les accès administratifs utilisent des comptes
            nominatifs authentifiés ; le PIN caisse identifie l&apos;opérateur et
            ne constitue pas un second facteur. Les opérations sensibles sont
            journalisées. Les écritures fiscales sont chaînées, signées et
            protégées contre la modification dans la version candidate à la
            certification NF525.
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
            Le modèle utilisé est Claude Haiku 4.5 via l&apos;API commerciale
            d&apos;Anthropic. Les données envoyées sont limitées à ce qui est
            nécessaire à la recommandation. Dans le régime standard annoncé
            par Anthropic, les entrées et sorties sont supprimées sous 30 jours,
            sauf exception contractuelle, légale ou liée à la sécurité.
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
