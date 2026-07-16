# Dossier de préparation NF525 — Vintiz POS

> **Statut au 15 juillet 2026 : préparation technique renforcée, non certifiée.**
> **Version fiscale candidate : 1.1.1** — signature fiscale v2, révision DB 0072.
> Ce document ne constitue ni un certificat NF525, ni une attestation éditeur.

## 1. Position réglementaire

Le 3° bis du I de l'article 286 du CGI impose aux logiciels de caisse concernés
quatre qualités : inaltérabilité, sécurisation, conservation et archivage des
données de règlement.

La doctrine administrative publiée le 25 mars 2026 admet de nouveau deux modes
de preuve : certificat d'un organisme accrédité ou attestation individuelle de
l'éditeur. Elle précise toutefois qu'un logiciel développé en interne par
l'assujetti pour ses propres besoins doit être certifié par un organisme
accrédité, sauf activité réelle d'édition de logiciels ou de systèmes de caisse.

Pour Vintiz, boutique utilisatrice et détentrice du code source, la position
prudente retenue est donc : **certification externe obligatoire avant de
revendiquer la conformité**, sauf avis juridique documenté établissant que
l'exception d'activité réelle d'édition est applicable.

Sources officielles :

- [BOI-TVA-DECLA-30-10-30 du 25 mars 2026](https://bofip.impots.gouv.fr/bofip/10691-PGP.html/identifiant%3DBOI-TVA-DECLA-30-10-30-20260325)
- [Article 286 du CGI](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000051203262)
- [Information Bercy sur les logiciels de caisse](https://www.economie.gouv.fr/entreprises/gerer-son-entreprise-au-quotidien/gerer-sa-comptabilite-et-ses-demarches/ce-quil-faut-savoir-sur-la-certification-des-logiciels-de-caisse)

## 2. Périmètre fiscal candidat

Le périmètre à présenter au certificateur comprend :

- création des ventes, paiements et remboursements sous `/api/pos` ;
- paiements CB SumUp et rapprochement des tentatives ;
- tickets, factures, lignes et moyens de paiement ;
- tiroirs de caisse et clôtures Z ;
- clôtures mensuelles et annuelles ;
- export fiscal et archives JSON gzip ;
- migration 0072 et triggers PostgreSQL d'inaltérabilité ;
- clé `FISCAL_SIGNING_KEY` et sa procédure de conservation.

Les fonctions CRM, inventaire et IA sont hors périmètre sauf lorsqu'elles
fournissent une donnée figée dans une vente (remise, coupon, article, client ou
moyen de paiement).

## 3. Couverture technique

### 3.1 Inaltérabilité et corrections

Chaque vente ou remboursement reçoit une signature HMAC-SHA256 v2 calculée par
`FiscalService`. Le payload canonique contient notamment :

- numéro, type, date, opérateur, cashier, référence idempotente et vente
  d'origine en cas de remboursement ;
- totaux HT, TVA et TTC, données de facture et modèle de ticket ;
- chaque ligne : article, libellé figé, quantité, prix, remise, total,
  caractère promotionnel et taux de TVA ;
- chaque paiement : méthode, montant appliqué, montant remis en espèces et
  références SumUp masquées ;
- le hash précédent et la version de signature.

La clé HMAC fiscale est indépendante de la clé JWT. En production, l'API refuse
de démarrer sans `FISCAL_SIGNING_KEY` stable d'au moins 32 caractères.

La migration 0072 installe des triggers PostgreSQL qui interdisent :

- modification ou suppression du cœur d'une transaction signée ;
- ajout, modification ou suppression de ses lignes et paiements ;
- modification ou suppression des totaux et hashes Z ;
- modification des périodes de tiroir déjà clôturées ;
- modification ou suppression d'une clôture fiscale périodique.

Les corrections se font par une nouvelle transaction de remboursement liée à
la vente d'origine, jamais par réécriture de la vente.

### 3.2 Sécurisation des encaissements

- Les écritures vente/remboursement sont sérialisées par verrou transactionnel
  PostgreSQL ; le numéro est alloué par `MAX+1` sous ce verrou, sans numéro
  consommé lors d'un rollback.
- Une vente CB n'est créée que si SumUp confirme de nouveau `PAID`, avec le même
  checkout, le même montant et la même référence `client_uuid` que la tentative
  serveur verrouillée.
- Les informations CB envoyées par le navigateur sont remplacées par la réponse
  SumUp. Une clé SumUp de test est refusée en environnement de production.
- Un remboursement CB local est annulé en base si le remboursement SumUp n'est
  pas confirmé.
- Les secrets, PAN et CVV sont expurgés des diagnostics de paiement.

### 3.3 Clôtures et compteurs

- Clôture journalière : rapport Z à la fermeture du tiroir ; une garde à 23 h 59
  ferme et scelle toute caisse oubliée, en signalant l'absence de comptage.
- Clôture mensuelle : le 1er à 00 h 15, sur le mois civil précédent.
- Clôture annuelle : le 1er janvier à 00 h 30, sur l'année précédente.

Les clôtures périodiques enregistrent un grand total de période et un total
perpétuel (ventes, remboursements, net et nombre de transactions). Elles sont
chaînées et signées ; le total perpétuel ne revient jamais à zéro dans une même
installation.

### 3.4 Conservation et archivage

Les transactions élémentaires, lignes, paiements, Z et clôtures sont conservés
sans purge fiscale. Une suppression RGPD dissocie ou anonymise l'identité du
client sans supprimer l'écriture de caisse.

`POST /api/admin/fiscal-closures` crée manuellement une clôture ; les crons
mensuel et annuel utilisent le même service. Chaque clôture embarque :

- un snapshot complet JSON en format ouvert, accompagné d'une notice française ;
- les transactions, lignes, paiements et Z de la période ;
- les contrôles d'intégrité des chaînes ;
- les grands totaux et le total perpétuel ;
- un SHA-256 de l'archive gzip et un manifest HMAC chaîné ;
- la version logicielle et les bornes de numérotation.

Endpoints manager :

```text
GET  /api/admin/fiscal-closures
GET  /api/admin/fiscal-closures/integrity
POST /api/admin/fiscal-closures
GET  /api/admin/fiscal-closures/{id}/archive
GET  /api/admin/fiscal-export?from=YYYY-MM-DD&to=YYYY-MM-DD&format=json|xml
```

Les données et preuves doivent être conservées au moins six ans. L'archive
applicative ne remplace pas une sauvegarde : l'exploitant doit dupliquer chaque
archive annuelle sur un support externe protégé, tester sa lecture et conserver
la clé fiscale selon une procédure d'accès restreint.

## 4. Déploiement et gestion des versions

- La production applique Alembic avant le démarrage de l'API.
- L'API refuse une base dont `alembic_version` n'est pas `0072`.
- `/api/admin/create-tables` est désactivé en production.
- Une base réellement vide est initialisée uniquement par
  `scripts/bootstrap_database.py --confirm-empty`, sans compte par défaut ni
  données de démonstration, puis migrée vers la révision courante.
- `/api/health` expose la version applicative, la révision DB attendue, la
  version de signature et le SHA de build.

Toute évolution touchant le payload signé, les triggers, la numérotation, les
clôtures, les remboursements ou l'archivage est une évolution fiscale majeure.
Elle impose une revue avec l'organisme certificateur avant déploiement et peut
nécessiter un nouveau certificat.

## 5. Vérifications avant candidature

1. Exécuter la suite Python, le lint, les migrations sur base vide et les deux
   builds Next.js sans tolérance d'erreur.
2. Réaliser un jeu d'essai documenté : espèces avec rendu, CB, paiement mixte,
   coupon fidélité, facture, remboursement partiel et total, caisse oubliée.
3. Prouver qu'une altération SQL d'une vente, ligne, paiement, Z ou clôture est
   refusée par PostgreSQL et/ou détectée par les contrôles de chaîne.
4. Télécharger une archive annuelle, vérifier son SHA-256, la décompresser sur
   un poste sans Vintiz et rapprocher ses totaux du Z et de la comptabilité.
5. Tester une restauration complète de sauvegarde et conserver le procès-verbal.
6. Figer la candidate dans un tag Git, produire la nomenclature des composants
   et transmettre le dossier à un organisme accrédité.

## 6. Réserves bloquantes avant toute mention « conforme NF525 »

- certificat externe non obtenu à ce jour ;
- exploitation réelle des clés, sauvegardes et archives externes à éprouver ;
- recette terrain SumUp/TPE/imprimantes à signer par la responsable boutique ;
- procédures d'incident, restauration et changement de clé à faire valider par
  le certificateur.

La mention correcte jusqu'à levée de ces réserves est :
**« version candidate à la certification NF525 »**.
