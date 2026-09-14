# Cahier des charges — Caisse « Frip & Co Street »

**Entité :** Frip & Co (groupe Solidarité Textiles)
**Boutique :** Frip & Co Street — boutique éphémère, centre-ville de Rouen, ouverture semaine 38 (septembre 2026), fermeture janvier 2027
**Version :** 1.2 — 14/09/2026 — validée pour lancement PR0 — à valider avant tout développement
**Source :** monorepo Vintiz (FastAPI + PostgreSQL + Next.js 14, Docker), déjà déployé sur le serveur cible

---

## 1. Objectif

Disposer en quelques jours d'une caisse simple, isolée et conforme, réutilisant exclusivement les modules existants et fonctionnels de Vintiz. Aucune fonctionnalité nouvelle n'est inventée : on **extrait, on débranche, on simplifie**.

Le résultat est une application indépendante (`fripco-street`) avec sa propre base, son propre conteneur et son propre sous-domaine sur le serveur Vintiz existant.

## 2. Périmètre

### 2.1 Inclus

| Module | Origine Vintiz | Adaptation |
|---|---|---|
| Vente | Écran de vente / panier | Saisie manuelle : libellé libre + prix TTC. Pas de catalogue, pas de recherche article, pas de stock. |
| Encaissement CB | Module paiement | **Nouveau terminal SumUp piloté par l'API SumUp dès l'ouverture** : la caisse déclenche le paiement sur le terminal, reçoit le statut et enregistre automatiquement la référence transaction. Aucune saisie manuelle du montant sur le TPE. Terminal : **SumUp Solo** (compatible API cloud, confirmé). Clé API marchand fournie par Julien. |
| Caisse espèces | Module espèces | Fond de caisse, rendu monnaie, mouvements entrées/sorties, clôture journalière. |
| Fidélité | Comptes clients | Réduit à la **collecte de coordonnées** (nom, prénom, e-mail, consentement newsletter). Aucun point, aucune remise, aucune règle. |
| Ticket client | Génération ticket | Envoi par **e-mail via Brevo** (instance déjà en place). Pas d'impression. |
| Newsletter | — | Synchronisation des contacts consentants vers une **liste Brevo dédiée** « Frip & Co Street ». Les campagnes se font dans Brevo, pas dans l'outil. |
| Export comptable | Export existant | Journal des ventes + journal de caisse exportables (CSV) pour Pennylane / Talenz Alteis. |

### 2.2 Exclus (explicitement)

- Lecteur code-barres, imprimante Zebra, tout matériel hors TPE SumUp
- Gestion de stock, intake, catalogue, photos, prix suggérés
- Personal Shopper 360, IA vision, embeddings, dashboards analytiques
- SMS (suspendu — architecture à laisser ouverte, aucun code)
- Multi-boutique, multi-utilisateur, rôles/permissions avancés
- Toute correspondance de données avec Vintiz Vernon (systèmes totalement isolés)

## 3. Contraintes

### 3.1 Conformité NF525 — auto-attestation (art. 286 I-3° bis CGI, BOI-TVA-DECLA-30-10-30)

Même régime que Vernon : attestation individuelle de l'éditeur (Frip & Co). Le logiciel doit donc **démontrer** les quatre conditions, et le code extrait de Vintiz doit être vérifié sur ces points, pas supposé conforme :

1. **Inaltérabilité** — toute vente enregistrée est immuable ; une annulation est une écriture inverse horodatée, jamais une suppression ou une modification. Chaînage cryptographique (hash de l'enregistrement précédent) sur les tickets et les clôtures.
2. **Sécurisation** — journal des événements techniques (JET) : connexion, ouverture/clôture de caisse, annulation, export, correction. Accès authentifié.
3. **Conservation** — clôtures journalières, mensuelles et annuelles avec totaux cumulés (grand total perpétuel).
4. **Archivage** — archive fiscale exportable, datée, signée, lisible hors application.

Livrable associé : le document d'auto-attestation daté et signé par Julien Gondé (Président de Frip & Co), avec la description technique des mécanismes, avant la première vente.

### 3.2 Simplicité d'exploitation

- Un seul utilisateur, un seul compte, une seule caisse.
- Utilisable sur tablette ou ordinateur du magasin, interface tactile.
- Aucune formation : un vendeur doit encaisser en trois gestes (montant → mode de paiement → e-mail ou passer).

### 3.3 Sécurité et données

- HTTPS via le reverse-proxy existant, hébergement sur le domaine **fripco.fr** (proposition : `street.fripco.fr`).
- Base PostgreSQL séparée, sauvegarde quotidienne (réutiliser le mécanisme de backup du serveur).
- RGPD : consentement newsletter explicite et horodaté, mention d'information sur l'écran de saisie, suppression sur demande.
- Aucune clé Brevo ou SumUp dans le code : variables d'environnement. Accès API Brevo et SumUp fournis par Julien.

### 3.4 Isolation par rapport à Vintiz Vernon

- Conteneurs, réseau Docker, base, secrets et domaine distincts.
- Interdiction de toute dépendance runtime vers les services Vintiz (le code est copié, pas appelé).
- Les instructions serveur (chemins, proxy, ports, backup, `.env`) sont à lire dans le `CLAUDE.md` du repo Vintiz — c'est la source de vérité pour l'infrastructure.

## 4. Fonctionnel détaillé

### 4.1 Vente
- Écran unique : ligne = libellé (facultatif, défaut « Article ») + prix TTC ; plusieurs lignes par ticket ; remise globale en € ou % (traçée).
- TVA : taux normal 20 % appliqué sur l'intégralité du prix TTC (pas de régime de la marge). Taux paramétrable en admin, HT/TVA/TTC affichés sur le ticket.
- Mode de paiement : CB SumUp (paiement poussé sur le terminal via API, statut en retour, réessai/annulation gérés) / Espèces / Mixte.
- Annulation d'un ticket = ticket d'annulation référencé.

### 4.2 Caisse espèces
- Ouverture avec fond de caisse ; mouvements manuels motivés ; clôture avec comptage théorique/réel et écart.
- Impossible de vendre caisse fermée.

### 4.3 Client / fidélité
- Champ e-mail optionnel au moment du paiement ; si renseigné : création ou rattachement du contact, envoi du ticket, case « recevoir les actualités et événements » (non pré-cochée).
- Push vers la liste Brevo à chaque consentement ; retrait à chaque désinscription Brevo (webhook) ou demande.

### 4.4 Administration
- Paramètres : nom boutique, adresse, SIRET, TVA, domaine, clés Brevo et SumUp, identifiant du terminal.
- Consultation des tickets et clôtures, exports CSV et archive fiscale.

## 5. Organisation du développement

### 5.1 Principe
Développement en **PR successives, cumulatives**, chacune validée par Julien avant la suivante. Chaque PR est déployable en l'état (feature flag si besoin) et livre ses tests verts.

### 5.2 Plan de PR

| PR | Contenu | Critère de validation |
|---|---|---|
| **PR0** | Audit du repo Vintiz : cartographie des modules vente / paiement / espèces / clients / tickets / export ; liste des dépendances à couper ; vérification point par point NF525 sur le code existant ; rapport écrit. | Julien valide la liste des modules extraits et les écarts NF525 identifiés. |
| **PR1** | Squelette `fripco-street` : monorepo allégé, Docker Compose, base, migration initiale, auth mono-utilisateur, déploiement sur le serveur (sous-domaine, proxy, backup). | Page de connexion accessible en HTTPS en prod. |
| **PR2** | Vente + espèces + tickets (hash chaîné, annulation, JET, clôture journalière) + **intégration API SumUp** (push paiement, statut, référence). | Scénario complet vente CB réelle + vente espèces → clôture en prod, tests d'immuabilité verts. |
| **PR3** | Client/fidélité + e-mail ticket Brevo + liste newsletter + consentement. | Ticket reçu, contact visible dans Brevo. |
| **PR4** | Exports comptables, archive fiscale, clôtures mensuelle/annuelle, document d'auto-attestation. | Export importable ; attestation signée. |

Ouverture possible après PR2 + attestation provisoire, PR3 dans la foulée. Si l'API SumUp bloque en PR2 (terminal incompatible, délai d'activation), repli temporaire : enregistrement manuel de la référence, avec réintégration API en priorité absolue après ouverture.

### 5.3 Architecture d'agents (Claude Code)

| Agent | Modèle | Rôle |
|---|---|---|
| **Orchestrateur / architecte** | Fable 5.1 | Lit le CLAUDE.md, planifie, arbitre, rédige les PR descriptions, revue finale. Seul agent qui touche l'infra. |
| **Extracteur** | Sonnet 5 | Copie et allège les modules Vintiz, coupe les dépendances (stock, barcode, printer, IA). |
| **Développeur** | Sonnet 5 | Implémente les adaptations (saisie libre, Brevo, exports). |
| **Testeur** | Haiku 4.5 | Écrit et exécute les tests unitaires/e2e (Playwright), rapporte les échecs. |
| **Persona « vendeur »** | Haiku 4.5 | Rejoue à chaque PR le parcours réel en boutique (encaissement en 3 gestes, caisse fermée, erreur de saisie, client sans e-mail) et bloque si la promesse utilisateur n'est pas tenue. |
| **Persona « comptable Talenz »** | Sonnet 5 | Vérifie exports, TVA, cohérence clôtures/journal. |
| **Debug & sécurité** | Fable 5.1 | À chaque PR : secrets, injection, auth, isolation Vintiz, dépendances vulnérables, NF525 (inaltérabilité, JET). Veto bloquant. |

Règle : Fable n'écrit pas de code de production sauf infra/déploiement ; les modèles plus légers codent, Fable revoit.

## 6. Critères d'acceptation globaux

- Une vente CB, une vente espèces, une annulation, une clôture : chacune tracée, immuable, exportable.
- Ticket e-mail reçu en < 1 min avec les mentions légales.
- Aucun appel réseau vers Vintiz Vernon (vérifié par test).
- Sauvegarde restaurable testée une fois avant ouverture.
- Auto-attestation NF525 signée par Julien Gondé, Président de Frip & Co, avant la première vente.

## 7. Livrables

1. Rapport d'audit PR0
2. Repo `fripco-street` déployé
3. Tests automatisés verts par PR
4. Document d'auto-attestation NF525
5. Guide d'utilisation d'une page (vendeur) + procédure de clôture

## 8. Calendrier indicatif

- J0 (lundi 14/09) : validation CDC → lancement PR0
- J1 : PR0 validée → PR1
- J2–J3 : PR2
- J4 : PR3 + attestation → **ouverture**
- Semaine suivante : PR4

## 9. Points ouverts à trancher

1. **Sous-domaine** : `street.fripco.fr` sauf avis contraire.
2. **Liste Brevo** : liste dédiée « Frip & Co Street » (recommandation), ou rattachement à la liste Frip & Co existante.

---

# Brief Claude Code (à coller tel quel une fois le CDC validé)

```
Tu travailles dans le monorepo Vintiz. Lis d'abord CLAUDE.md et le fichier CDC_Caisse_FripCo_Street.md à la racine.

Mission : créer l'application isolée `fripco-street` (caisse boutique éphémère Rouen) en extrayant uniquement les modules existants de Vintiz décrits au §2.1 du CDC. Aucune fonctionnalité nouvelle. Aucune dépendance runtime vers Vintiz.

Mode : orchestrateur (toi) + sous-agents selon §5.3 du CDC. Tu délègues le code aux agents Sonnet/Haiku et tu revois. Tu lances l'agent debug & sécurité sur chaque PR avant de la proposer.

Livraison : une PR à la fois selon le plan §5.2. Tu t'arrêtes après chaque PR et attends ma validation. Chaque PR est cumulative, déployable et livre ses tests verts.

Première étape maintenant : PR0 — audit. Produis un rapport listant (a) les modules à extraire avec leurs fichiers, (b) les dépendances à couper, (c) les écarts NF525 constatés dans le code existant, (d) les questions bloquantes. Ne modifie aucun fichier avant ma validation.

Si un point est imprécis, tu me poses la question plutôt que de supposer.
```
