# Manuel Utilisateur — Vintiz V1
## Boutique de seconde main premium — Vernon, Normandie

**Version** : 1.0 — Mai 2026
**Public** : Équipes boutique (manager, vendeur, caissier)
**Format** : Ce document est destiné à être mis en forme par l'équipe communication.

---

> **Comment lire ce manuel**
> Chaque section correspond à un écran de l'application. Les étapes sont numérotées. Les encadrés `→` indiquent ce qui se passe à l'écran. Les encadrés `⚠` signalent un point d'attention.

---

## Sommaire

1. [Présentation générale](#1-présentation-générale)
2. [Connexion et navigation](#2-connexion-et-navigation)
3. [Tableau de bord](#3-tableau-de-bord)
4. [Cahier du jour](#4-cahier-du-jour)
5. [Caisse — vendre un article](#5-caisse--vendre-un-article)
6. [Caisse — moyens de paiement](#6-caisse--moyens-de-paiement)
7. [Caisse — gestion de la caisse](#7-caisse--gestion-de-la-caisse)
8. [Inventaire — gérer les produits](#8-inventaire--gérer-les-produits)
9. [Inventaire — étiquettes](#9-inventaire--étiquettes)
10. [Clients et fidélité](#10-clients-et-fidélité)
11. [Compagnon IA](#11-compagnon-ia)
12. [Rapports](#12-rapports)
13. [Newsletter](#13-newsletter)
14. [Paramètres](#14-paramètres)
15. [Site vitrine et espace client](#15-site-vitrine-et-espace-client)
16. [Dépannage](#16-dépannage)

---

## 1. Présentation générale

Vintiz est une application de gestion complète pour la boutique de seconde main. Elle se compose de trois espaces :

| Espace | Adresse | Pour qui |
|---|---|---|
| **Back-office** | app.vintiz.fr | Manager, vendeurs, caissiers |
| **Site vitrine** | vintiz.fr | Clients de la boutique |
| **Espace client** | vintiz.fr/account | Clients inscrits |

Ce manuel couvre principalement le **back-office** (app.vintiz.fr), qui est l'outil de travail quotidien des équipes.

### Ce que fait Vintiz

- **Caisse** : enregistrement des ventes, paiements espèces / CB / chèque
- **Inventaire** : fiches produits, photos, étiquettes, suivi du cycle de vie
- **Clients** : base de données, programme de fidélité, personal shopper IA
- **IA** : analyse de photos, recommandations de mise en rayon, tendances mode
- **Rapports** : chiffre d'affaires, performances, segments clients
- **Matériel** : imprimante ticket, imprimante étiquettes, tiroir-caisse, TPE

---

## 2. Connexion et navigation

### Se connecter

1. Ouvrir le navigateur sur la tablette ou l'ordinateur.
2. Aller sur **app.vintiz.fr**.
3. Saisir les identifiants :
   - **Identifiant** : votre email ou `admin`
   - **Mot de passe** : fourni par le manager
4. Appuyer sur **Se connecter**.

→ La page d'accueil est le **Tableau de bord**.

> **Premier accès** : les identifiants par défaut sont `admin` / `vintiz2026`. Le manager doit les modifier dès la première connexion dans Paramètres > Utilisateurs.

### La barre de navigation (sidebar)

La barre de navigation est visible à gauche de l'écran (sur tablette, appuyez sur l'icône ☰ pour l'ouvrir).

| Rubrique | Ce que vous y trouvez |
|---|---|
| **Tableau de bord** | Vue du jour : CA, transactions, météo |
| **Cahier du jour** | Objectifs, performance par heure, zoning |
| **Rapports** | Statistiques semaine et mois |
| **Caisse** | Interface de vente |
| **Inventaire** | Liste et gestion des produits |
| **Espaces** | Plan des zones de la boutique |
| **Clients** | Base de données clients |
| **Newsletter** | Gestion des abonnés |
| **Compagnon IA** | Outils d'intelligence artificielle |
| **Admin** | Gestion avancée (manager uniquement) |
| **Paramètres** | Configuration de la boutique et du matériel |

> **Rôle collaborateur** : les onglets Admin, Paramètres et SEO ne sont pas visibles pour les vendeurs. Seul le manager y a accès.

### Se déconnecter

Cliquer sur votre nom en bas de la sidebar, puis **Se déconnecter**.

---

## 3. Tableau de bord

Le tableau de bord est la page d'accueil. Il se met à jour automatiquement toutes les 60 secondes.

### Ce que vous voyez

**4 indicateurs du jour** (en haut de page) :
- **CA du jour** : chiffre d'affaires depuis l'ouverture
- **Articles en stock** : nombre de produits disponibles
- **Transactions aujourd'hui** : nombre de ventes de la journée
- **Panier moyen** : montant moyen par vente

**Message du Compagnon IA** (bandeau teal) : 3 recommandations prioritaires pour la journée (mise en avant d'articles, tendances, actions commerciales). Cliquer sur une recommandation pour accéder à l'écran correspondant.

**Bande objectif du jour** : progression du CA par rapport à l'objectif mensuel. La barre verte avance au fil de la journée.

**10 derniers tickets** : liste des ventes récentes. Cliquer sur un ticket pour ouvrir le détail.

**Météo Vernon** : prévisions sur 5 jours (données OpenWeatherMap).

**Actions rapides** :
- **Nouvelle vente** → ouvre la caisse
- **Ajouter un produit** → ouvre le formulaire de saisie

### Réimprimer un ticket depuis le tableau de bord

1. Cliquer sur le ticket dans la liste des 10 derniers tickets.
2. La modale s'ouvre avec le détail complet (articles, montants, paiements).
3. Cliquer sur **Réimprimer (MUNBYN)** pour envoyer à l'imprimante thermique.
4. Ou **Version A4 / PDF** pour obtenir un document imprimable.
5. Boutons **Email** / **SMS** pour renvoyer le ticket au client.

---

## 4. Cahier du jour

Le cahier du jour est le tableau de pilotage quotidien du manager.

**Accès** : menu latéral > **Cahier du jour**

### Lecture des indicateurs

**En-tête** :
- Date du jour, météo du matin
- **Message du jour** : note libre (ex. "Très calme, mise en avant robes"). Cliquer sur *Modifier* pour le saisir.
- **Opération en cours** : promotion ou événement du moment

**Bloc objectif** :
- **CA budget mois** : objectif mensuel fixé en paramètres
- **Objectif du jour** : part de l'objectif mensuel attendue aujourd'hui (calculée selon le poids historique du jour de la semaine)
- **N-1** : chiffre du même jour l'an dernier
- Barre de progression : avancement par rapport à l'objectif du jour

**Performances en temps réel** :
- % d'atteinte de l'objectif
- Delta vs N-1 (en vert si en hausse, en rouge si en baisse)
- Panier moyen, taux CRM, taux fidélité

**Courbe horaire** : CA cumulé heure par heure + objectif théorique. Permet de voir si la journée est en avance ou en retard.

**Zoning** : performance par zone de la boutique (CA réalisé vs objectif, comparaison N-1).

**CRM & Fidélité** : nombre de fiches créées, nouvelles adhésions fidélité, tickets avec fidélité utilisée.

### Saisir l'objectif mensuel

Le manager fixe l'objectif mensuel une fois par mois :

1. Aller dans **Paramètres > Cahier**.
2. Saisir le montant de l'objectif mensuel (ex. `12 000`).
3. Enregistrer.

→ L'application répartit automatiquement l'objectif par jour selon le profil historique de la boutique (le samedi pèse plus que le lundi, etc.).

### Signer le cahier

En bas de la page, deux boutons de signature :
- **Signature Manager** : apposer la validation du responsable
- **Signature Équipe** : validation de l'équipe du jour

Ces signatures horodatent la clôture journalière.

---

## 5. Caisse — vendre un article

La caisse est l'écran principal de vente. Elle est optimisée pour une tablette en format paysage.

**Accès** : menu latéral > **Caisse**

### Ouvrir la caisse

À la première ouverture de la journée, une fenêtre demande le **fond de caisse** :

1. Saisir le montant du fond initial (billets + pièces comptés dans le tiroir).
2. Appuyer sur **Ouvrir la caisse**.

→ La caisse est prête. Le fond de caisse est enregistré pour le rapport Z de fermeture.

> Si la caisse est déjà ouverte par un autre utilisateur, vous accédez directement à l'écran de vente.

### Identifier le caissier (PIN)

Si les PINs sont activés :

1. Une fenêtre s'affiche demandant votre code PIN à 4 chiffres.
2. Saisir votre PIN sur le pavé numérique.
3. → Votre nom apparaît en haut de l'écran.

> Le manager configure les PINs dans **Paramètres > Utilisateurs**.

### Ajouter un article au panier

**Méthode 1 — Douchette (recommandé)**

1. Appuyer dans le champ de recherche (il se sélectionne automatiquement).
2. Scanner le code-barres de l'article avec la douchette Inateck.
3. → L'article apparaît immédiatement dans le panier.

**Méthode 2 — Recherche manuelle**

1. Taper le nom, la référence ou le code-barres dans le champ de recherche.
2. → Une liste de résultats apparaît.
3. Cliquer sur l'article souhaité pour l'ajouter au panier.

**Méthode 3 — Article libre (hors stock)**

Pour un article non référencé en base :

1. Taper le nom et le montant dans le champ.
2. Sélectionner **Article manuel**.
3. → L'article s'ajoute au panier avec le montant saisi.

### Modifier un article dans le panier

Pour chaque article du panier, vous pouvez :

- **Augmenter/diminuer la quantité** avec les boutons + et −
- **Appliquer une remise** : appuyer sur le chip `-%` pour révéler les boutons de remise (5 %, 10 %, 15 %, 20 %, 30 %)
- **Supprimer** l'article avec l'icône corbeille

> Les remises sont appliquées à l'article, pas au panier entier.

### Identifier un client

1. Appuyer sur **Identifier un client**.
2. Saisir email, téléphone ou numéro de carte fidélité.
3. → Le panneau client s'affiche à droite avec son solde de points et ses suggestions personnalisées.

Si le client n'est pas encore dans la base :

1. Appuyer sur **Nouveau client**.
2. Saisir prénom, nom, email, téléphone.
3. Cocher les cases de consentement email/SMS.
4. → Le client est créé et une carte de fidélité lui est attribuée.

### Utiliser les points de fidélité

Quand un client est identifié et qu'il a des points :

1. Le panneau fidélité s'affiche avec le solde de points.
2. Activer le toggle **Utiliser mes points**.
3. → Le montant déduit (max 50 % du panier) est calculé automatiquement.
4. Continuer vers l'encaissement.

---

## 6. Caisse — moyens de paiement

Une fois les articles ajoutés et le client identifié (optionnel), appuyer sur **Encaisser**.

### L'assistant de paiement

L'assistant s'ouvre en 3 étapes :

**Étape 1 — Choisir le mode de paiement**

- **Espèces**
- **CB (carte bancaire)** — via le TPE SumUp
- **Chèque**
- **Chèque CDC** (Chèque Emploi-Service)
- **Avoir** (avoir en compte du client)
- **Paiement mixte** — combiner plusieurs modes

**Étape 2 — Saisir le montant**

- Pour les espèces : saisir le montant remis par le client sur le pavé numérique. Le **rendu monnaie** s'affiche automatiquement.
- Pour la CB : confirmer le montant et suivre les instructions du TPE.
- Pour le chèque : saisir le montant et le nom du tireur.

**Étape 3 — Confirmer**

Appuyer sur **Valider la vente**.

→ La vente est enregistrée. En paiement espèces, le tiroir-caisse s'ouvre automatiquement.

### Paiement CB (SumUp)

1. Sélectionner **CB**.
2. Confirmer le montant.
3. → Le TPE SumUp sonne et affiche le montant à payer.
4. Le client présente sa carte (contact ou sans contact).
5. → Le résultat s'affiche : **Accepté** (vert) ou **Refusé** (rouge).
6. En cas de refus, vous pouvez proposer un autre mode de paiement.

> Si le TPE ne se déclenche pas automatiquement, appuyer sur **Envoyer vers le TPE** ou lancer le paiement manuellement sur le terminal.

### Paiement mixte

Exemple : 10 € en espèces + 5 € en CB

1. Sélectionner **Mixte**.
2. Ajouter chaque ligne de paiement :
   - Choisir le mode, saisir le montant, appuyer sur **Ajouter**.
3. Quand le total atteint le montant de la vente, confirmer.

### Après la vente — le ticket

Une fenêtre propose :

- **Imprimer (MUNBYN)** : envoie le ticket à l'imprimante thermique
- **Version A4 / PDF** : ouvre une version imprimable dans le navigateur
- **Fermer** : clôturer sans ticket
- **Envoyer par email** / **Envoyer par SMS** : envoyer le ticket au client

> Le ticket porte un numéro de ticket permanent (`#xxx`) issu d'une séquence sécurisée. Ce numéro ne change jamais, même sur une réimpression.

### Effectuer un remboursement

1. Ouvrir le ticket depuis le **Tableau de bord** ou les **Rapports**.
2. Appuyer sur **Rembourser**.
3. Sélectionner les articles à rembourser et le montant.
4. Choisir le mode de remboursement (espèces, avoir en compte…).
5. Confirmer.

→ Un nouveau ticket de remboursement est créé.

---

## 7. Caisse — gestion de la caisse

### Fermer la caisse (Rapport Z)

En fin de journée ou de service :

1. Appuyer sur l'icône de fermeture de caisse (en haut à droite de la caisse).
2. Compter physiquement le contenu du tiroir.
3. Saisir le montant compté sur le pavé numérique.
4. → L'application affiche l'écart entre le montant attendu et le montant compté.
5. Appuyer sur **Clôturer la caisse**.

→ Le **Rapport Z** est généré. Il récapitule :
- CA par mode de paiement (espèces, CB, chèque…)
- Fond initial et fond final
- Écart de caisse
- Nombre de transactions

Le rapport Z peut être imprimé ou consulté dans **Rapports > Rapports Z**.

### Ouvrir le tiroir-caisse manuellement

Pour ouvrir le tiroir sans effectuer de vente :

1. Aller dans **Paramètres > Matériel**.
2. Cliquer sur **Test tiroir** (bouton de test).

> Le tiroir ne peut s'ouvrir que si l'imprimante MUNBYN est connectée (elle transmet le signal RJ-12).

---

## 8. Inventaire — gérer les produits

**Accès** : menu latéral > **Inventaire**

### La liste des produits

La liste affiche tous les produits avec leurs statuts :

**Filtres disponibles** :
- **Recherche** : nom, référence, code-barres
- **Catégorie** : filtrer par type de vêtement
- **Statut** : voir seulement les articles en stock, en rayon, vendus…
- **Emplacement** : Stock (réserve) / Magasin (en rayon)

**Statuts des articles** :

| Statut | Signification |
|---|---|
| Réceptionné | Arrivé mais pas encore trié |
| Trié | Trié, pas encore étiqueté |
| Étiqueté | Étiqueté, prêt pour le rayon |
| En rayon | Visible et disponible à la vente |
| Démarqué | Prix réduit une première fois |
| Démarqué − | Deuxième démarque (réduction plus importante) |
| Vendu | Article vendu |
| Retourné | Retourné par le client |
| Retour tri | Retourné en zone de tri |
| Donné | Donné (fin de vie) |

### Ajouter un nouveau produit

1. Appuyer sur **+ Nouveau produit** (bouton en haut à droite).
2. **Étape 1 — Photo** :
   - Prendre une photo de l'article ou en importer une.
   - Appuyer sur **Analyser avec l'IA** : Claude Vision remplit automatiquement type, couleur, matière, marque estimée, état et description.
   - Vérifier et corriger les informations si nécessaire.
3. **Étape 2 — Informations** :
   - Nom de l'article (ex. "Robe fleurie Zara")
   - Catégorie (choisir dans la liste)
   - Taille, couleur, marque
   - État (Très bon état / Bon état / Correct)
   - Prix d'achat et prix de vente
4. **Étape 3 — Emplacement** :
   - Choisir la zone de rangement dans la boutique
   - La date de mise en rayon est renseignée automatiquement
5. **Étape 4 — Validation** :
   - Vérifier le récapitulatif
   - Appuyer sur **Créer le produit**

→ Un code-barres unique (`VTZ-AAAA-XXXXX`) est généré automatiquement.

> **Photo vitrine** : à chaque nouvelle photo, une version détourée (fond supprimé, logo Vintiz) est générée automatiquement pour le site vitrine. Vous pouvez la régénérer depuis la fiche produit.

### Modifier un produit

1. Cliquer sur l'article dans la liste.
2. La fiche s'ouvre avec toutes les informations.
3. Cliquer sur **Modifier** à côté du champ à changer.
4. Enregistrer.

Modifications rapides possibles directement dans la liste (sans ouvrir la fiche) :
- Prix de vente
- Zone
- Statut

### Faire évoluer le statut d'un article

1. Ouvrir la fiche produit.
2. Appuyer sur **Transition → [nouveau statut]**.
3. Confirmer.

Exemples de transitions courantes :
- Réceptionné → Trié → Étiqueté → En rayon
- En rayon → Démarqué (à partir d'un nombre de semaines configurable)
- En rayon → Retour tri

### Importer des produits en masse

Pour un lot d'articles similaires (ex. vide-grenier) :

1. Appuyer sur **Importer CSV**.
2. Télécharger le modèle CSV.
3. Remplir le fichier avec les articles.
4. Importer le fichier.
5. Vérifier la prévisualisation (**Mode simulation** disponible).
6. Confirmer l'import.

---

## 9. Inventaire — étiquettes

Chaque article Vintiz reçoit **deux étiquettes** imprimées sur la Zebra ZD421d (format 52 × 25 mm) :

- **Étiquette 1 — Info produit** : nom + taille, code-barres, numéro de semaine de mise en rayon
- **Étiquette 2 — Prix** : logo VINTIZ, prix de vente en euros

### Imprimer l'étiquette d'un article

**Depuis la fiche produit** :

1. Ouvrir la fiche de l'article.
2. Appuyer sur **Imprimer l'étiquette**.
3. → Les deux étiquettes sont envoyées à l'imprimante Zebra.

**Depuis la liste d'inventaire** :

1. Cocher un ou plusieurs articles dans la liste.
2. La barre d'impression en bas de page apparaît.
3. Choisir le nombre de copies.
4. Appuyer sur **Imprimer les étiquettes**.

### Prévisualiser une étiquette

Avant d'imprimer, vous pouvez voir l'aperçu de l'étiquette :

1. Ouvrir la fiche produit.
2. Appuyer sur **Aperçu étiquette**.
3. → Une image PNG de l'étiquette s'affiche.

### Vérifier si l'imprimante est disponible

1. Aller dans **Paramètres > Matériel**.
2. La section **Imprimante étiquettes (Zebra)** affiche le statut **En ligne** ou **Hors ligne**.
3. Si hors ligne, vérifier que l'imprimante est allumée et sur le même réseau Wi-Fi.

---

## 10. Clients et fidélité

**Accès** : menu latéral > **Clients**

### La liste des clients

La liste affiche tous les clients enregistrés. Recherche par nom, email ou téléphone.

Pour chaque client, un badge indique :
- **Carte fidélité active** (numéro `V######`)
- **Nombre de points**

### Créer un compte client

**Depuis la caisse** (recommandé pendant la vente) :

1. Dans la caisse, appuyer sur **Identifier un client**.
2. Saisir l'email du client pour vérifier s'il existe déjà.
3. Si nouveau : appuyer sur **Nouveau client**.
4. Remplir prénom, nom, email, téléphone.
5. Cocher les consentements (email marketing, SMS).
6. Appuyer sur **Créer**.

**Depuis la liste Clients** :

1. Appuyer sur **+ Nouveau client**.
2. Remplir le formulaire.
3. Enregistrer.

### La carte de fidélité

Chaque client reçoit une carte virtuelle numérotée `V######`.

**Fonctionnement** :
- **1 € dépensé = 1 point**
- **1 point = 0,10 € de réduction**
- **Maximum utilisable** : 50 % du panier lors d'une vente
- Les points expirent après **24 mois sans achat**

**Niveaux de fidélité** :
- **Bronze** : 0 à 499 points
- **Silver** : 500 à 999 points
- **Gold** : 1 000 points et plus

**Wallet numérique** : chaque client peut ajouter sa carte de fidélité à son Apple Wallet ou Google Wallet depuis son espace client sur vintiz.fr.

### La fiche client (manager)

1. Cliquer sur le nom du client dans la liste.
2. La fiche s'ouvre avec 6 onglets :
   - **Synthèse** : informations personnelles, solde fidélité, historique
   - **Achats** : liste de toutes les transactions
   - **Fidélité** : détail des points gagnés et utilisés
   - **Goûts** : profil style généré par l'IA
   - **RGPD** : consentements enregistrés
   - **Audit** : journal des modifications

### Personal Shopper IA

Le Personal Shopper analyse les achats passés du client et propose des articles du stock susceptibles de lui plaire.

**Depuis la caisse** (pendant la vente) :

Quand un client est identifié, le panneau latéral affiche automatiquement :
- Son solde de points et le montant maximum qu'il peut utiliser
- 3 suggestions d'articles complémentaires (ex. si le client achète une robe → suggestions de chaussures ou d'accessoires)
- Ses coupons actifs

**Depuis la fiche client** :

1. Onglet **Goûts** : voir le profil style du client
2. Appuyer sur **Lancer le Personal Shopper** : liste d'articles recommandés

### Gérer les avoirs

Un avoir est un crédit en euros sur le compte du client (ex. suite à un remboursement).

- L'avoir apparaît dans la fiche client et dans le panneau fidélité à la caisse.
- Il est utilisable comme moyen de paiement lors d'une prochaine vente.
- Le solde n'expire pas.

### RGPD — droits des clients

Les clients ont le droit :
- **D'accéder à leurs données** : via leur espace client sur vintiz.fr/account/rgpd
- **De demander la suppression** : via leur espace client (délai 30 jours)
- **De se désabonner** : lien de désinscription dans chaque email

En tant que vendeur, si un client vous demande de supprimer ses données :
1. Ouvrir la fiche client.
2. Onglet **RGPD**.
3. Appuyer sur **Demande de suppression**.

---

## 11. Compagnon IA

**Accès** : menu latéral > **Compagnon IA**

Le Compagnon IA est l'assistant intelligent de Vintiz. Il analyse le stock, les tendances et les performances pour proposer des actions concrètes.

### Recommandations du jour

La page d'accueil du Compagnon affiche les **priorités du jour** :

- Articles à mettre en avant (fort potentiel de vente)
- Produits à démarquer (trop longtemps en rayon)
- Suggestions de vitrine
- Alertes de performance

### Analyse photo (IA Vision)

Pour analyser un article à l'aide de la photo :

1. Dans le formulaire de création d'article, appuyer sur **Analyser avec l'IA**.
2. L'IA Claude Vision identifie :
   - Type de vêtement
   - Couleur et motifs
   - Matière estimée
   - Marque (si visible)
   - État de l'article
   - Style et saison
   - Estimation de gamme de prix
3. Les champs sont remplis automatiquement.
4. Vérifier et corriger si nécessaire.

> L'analyse IA est une aide, pas un oracle. Toujours vérifier les informations, notamment le prix de vente.

### Tendances mode

1. Dans le Compagnon IA, ouvrir l'onglet **Tendances**.
2. → Liste des tendances actuelles (social media, Vinted, retail) avec les articles du stock qui y correspondent.
3. Ces articles sont à mettre en avant en vitrine ou en rayon.

### Checklist hebdomadaire

Chaque semaine, l'IA génère une checklist d'actions pour la boutique :
- Produits à remettre en avant
- Articles à démarquer
- Suggestions de merchandising
- Indicateurs de performance à surveiller

**Accès** : Compagnon IA > onglet **Checklist**.

### Mapping boutique

Le mapping affiche l'occupation et la performance de chaque zone :

- Pourcentage de remplissage
- CA généré par zone
- Score de tendance moyen
- Suggestion de réorganisation

**Accès** : Compagnon IA > onglet **Zones**.

### Suggestions de prix

Pour un article, l'IA peut suggérer un prix de vente optimisé basé sur :
- Le prix de marché des articles similaires
- L'ancienneté en rayon
- Le niveau de demande

**Accès** : Depuis la fiche produit > **Suggestion de prix IA**.

---

## 12. Rapports

**Accès** : menu latéral > **Rapports**

### Rapports journaliers / hebdomadaires / mensuels

Trois onglets : **Journalier**, **Hebdomadaire**, **Mensuel**.

Pour chaque période, vous trouvez :
- **CA total** : chiffre d'affaires brut
- **CA net** (après remboursements)
- **Nombre de transactions**
- **Panier moyen**
- **Top produits** : articles les plus vendus

### KPIs Retail (indicateurs métier)

| Indicateur | Définition |
|---|---|
| **Sell-through** | % du stock vendu sur la période |
| **GMROI** | Retour sur investissement en achat-vente |
| **Days on Hand** | Nombre de jours de stock restant |
| **AIT** | Durée moyenne de présence d'un article avant vente |
| **CA/m²/mois** | Chiffre d'affaires par mètre carré |

### Segmentation clients (RFM)

La segmentation RFM classe les clients selon leur **Récence**, **Fréquence** et **Montant** d'achats.

| Segment | Description | Action recommandée |
|---|---|---|
| **Champions** | Achètent souvent et récemment | Choyer, inviter aux événements |
| **Fidèles** | Achètent régulièrement | Fidéliser, proposer nouveautés |
| **Nouvelles** | Achat récent, 1 fois | Convertir en fidèles |
| **Prometteuses** | Potentiel fort | Relancer |
| **À ne pas perdre** | Anciens bons clients | Réactiver en urgence |
| **À risque** | Achats moins fréquents | Relance personnalisée |
| **En sommeil** | Inactifs depuis longtemps | Campagne de réveil |
| **Perdues** | Plus d'activité | Offre exceptionnelle ou abandon |

### Rapports Z (fermetures de caisse)

Toutes les fermetures de caisse sont conservées :

1. **Rapports > Rapports Z**.
2. Sélectionner la date.
3. Consulter ou imprimer le rapport.

---

## 13. Newsletter

**Accès** : menu latéral > **Newsletter**

### La liste des abonnés

Affiche tous les clients inscrits à la newsletter, avec :
- Email
- Date d'inscription et d'accord
- Source (boutique, site, POS)
- Statut (Actif / Désabonné)

### Filtres

- **Tous** : liste complète
- **Actifs** : abonnés qui reçoivent les emails
- **Désabonnés** : clients qui ont retiré leur consentement

> Ne jamais envoyer de communications aux clients dont le statut est **Désabonné** — obligation légale RGPD.

### Rechercher un abonné

Saisir l'email dans la barre de recherche.

### Exporter la liste

1. Appuyer sur **Exporter CSV**.
2. → Un fichier `.csv` se télécharge avec les adresses actives.
3. Ce fichier peut être importé dans l'outil d'emailing (Brevo).

> L'export ne contient que les abonnés actifs ayant donné leur consentement.

### Supprimer un abonné (RGPD)

Sur demande d'un client :

1. Trouver son email dans la liste.
2. Appuyer sur l'icône de suppression.
3. Confirmer.

→ L'adresse est supprimée définitivement de la base de données.

---

## 14. Paramètres

**Accès** : menu latéral > **Paramètres** (manager uniquement)

### Informations boutique

- Nom, adresse, téléphone, email
- Horaires d'ouverture
- Logo (affiché sur les tickets et le site)
- Texte du ticket (message de fin de ticket, conditions de retour)

### Paiement

- Activation/désactivation des modes de paiement
- Configuration SumUp (clé API, identifiant marchand, identifiant TPE)
- TVA par défaut

### Matériel

#### Imprimante ticket (MUNBYN 047P)

- **Adresse IP** : IP de l'imprimante sur le réseau Wi-Fi de la boutique
- **Port** : 9100 (valeur par défaut, ne pas modifier)
- **Connexion** : Réseau (standard) ou USB (tablette Android)
- **Bouton Test** : imprime un ticket de test pour vérifier la connexion

> Pour trouver l'IP de l'imprimante : imprimer la page de configuration de la MUNBYN (maintenir le bouton d'alimentation 3 secondes jusqu'au ticket de config).

#### Tiroir-caisse (Safescan SD-4141)

- **Kick automatique** : ouverture automatique à chaque vente espèces
- **Bouton Test tiroir** : ouvre le tiroir manuellement

#### Imprimante étiquettes (Zebra ZD421d)

- **Adresse IP** : IP de l'imprimante Zebra sur le réseau local
- **Port** : 9100
- **Mode de connexion** : Réseau local / Cloud Weblink / Bluetooth
- **Bouton Test** : imprime une étiquette de test

> Mode Cloud : à utiliser si l'application est hébergée sur internet et que l'imprimante est dans la boutique. Nécessite un compte Zebra Data Services.

#### Douchette (Inateck)

La douchette fonctionne en mode USB HID (émulation clavier). Aucune configuration requise — elle se comporte comme un clavier qui tape le code-barres puis appuie sur Entrée.

> Si la douchette scanne mal les codes Vintiz (les tirets arrivent comme `=`) : c'est normal sur une tablette Android configurée en AZERTY. L'application corrige automatiquement.

#### TPE SumUp Solo

- **Identifiant lecteur** : récupéré depuis le compte SumUp (optionnel — sans cet ID, le paiement s'initialise depuis l'appli SumUp sur le TPE)

### Catégories

Gérer les catégories de produits :

- Ajouter, renommer ou désactiver des catégories
- Les catégories sont utilisées dans l'inventaire et le filtrage

> Deux catégories ne peuvent pas avoir le même nom (insensible à la casse).

### Zones

Le plan de la boutique est divisé en zones configurables :

| Champ | Description |
|---|---|
| Nom | Nom affiché (ex. "Rayon femme", "Vitrine") |
| Description | Détail de la zone |
| Capacité | Nombre maximum d'articles |
| Types de produits | Catégories autorisées dans cette zone |
| Objectif CA mensuel | Objectif financier par zone |

### Utilisateurs

- Liste des comptes manager et vendeur
- Créer, modifier, désactiver un utilisateur
- Réinitialiser un mot de passe
- Attribuer / révoquer un PIN caissier

### Système

- Informations de version
- Journaux d'audit (qui a fait quoi et quand)
- Export fiscal (format NF525 pour le contrôleur fiscal)

---

## 15. Site vitrine et espace client

### Le site vitrine (vintiz.fr)

Le site vitrine est public et accessible à tous. Il présente :
- La boutique et son histoire
- Le catalogue de produits disponibles
- Le Personal Shopper en accès libre
- Les articles de blog et capsules éditoriales
- Les informations de contact et les CGV

Les produits apparaissent automatiquement sur le site quand ils passent au statut **En rayon** dans l'inventaire.

### L'espace client (vintiz.fr/account)

Les clients inscrits peuvent se connecter à leur espace personnel avec un **lien magique** envoyé par email (pas de mot de passe à retenir).

Dans leur espace, ils trouvent :
- **Ma fidélité** : solde de points, numéro de carte, niveau (Bronze/Silver/Gold), historique des gains
- **Mon Personal Shopper** : sélection personnalisée d'articles correspondant à leur style
- **Mes offres** : coupons de réduction actifs
- **Mon historique** : toutes leurs commandes et achats en boutique
- **Mon espace RGPD** : gérer les consentements, demander l'export ou la suppression de données

### La carte de fidélité numérique

Les clients peuvent ajouter leur carte fidélité Vintiz à leur portefeuille numérique :
- **Apple Wallet** (iPhone)
- **Google Wallet** (Android)

→ La carte s'affiche sur l'écran de verrouillage du téléphone. Le code-barres est lisible directement par la douchette en caisse.

---

## 16. Dépannage

### L'application ne se charge pas

1. Vérifier la connexion Wi-Fi de la tablette.
2. Rafraîchir la page (tirer vers le bas ou appuyer sur F5).
3. Vider le cache du navigateur.
4. Si le problème persiste : contacter le support.

### La douchette ne fonctionne pas

1. Vérifier que le câble USB est bien branché.
2. Cliquer dans le champ de recherche avant de scanner.
3. Scanner un code-barres test (retrouvés dans `docs/test_barcodes/`).
4. Si les tirets apparaissent comme `=` : l'application corrige automatiquement — ce n'est pas une erreur.

### "Aucune correspondance trouvée" après scan

1. Vérifier que l'article est bien dans la base (chercher par nom dans l'inventaire).
2. S'assurer que l'article n'est pas en statut "Vendu" ou "Retourné" (exclus de la recherche caisse).
3. Si l'article existe mais ne s'affiche pas, ouvrir sa fiche et vérifier son statut.

### L'imprimante ticket ne répond pas

1. Vérifier que la MUNBYN est allumée (voyant bleu).
2. Vérifier qu'elle est connectée au Wi-Fi de la boutique.
3. Aller dans **Paramètres > Matériel > Imprimante ticket** et noter l'IP configurée.
4. Vérifier que l'IP correspond bien à l'imprimante (imprimer la page de config MUNBYN).
5. Appuyer sur **Test impression** dans les paramètres.
6. Si le test échoue : redémarrer l'imprimante.

### L'imprimante ticket imprime des caractères bizarres en tête de ticket

1. Désactiver l'option **Logo sur les tickets** dans **Paramètres > Matériel**.
2. Si le problème vient des accents (é, à, ç…) : ils sont automatiquement remplacés par leur équivalent sans accent (limitation du firmware — les tickets restent lisibles).

### Le tiroir-caisse ne s'ouvre pas

1. Vérifier que le câble RJ-12 est bien branché entre le tiroir et l'imprimante MUNBYN.
2. L'imprimante doit être allumée et connectée.
3. Aller dans **Paramètres > Matériel > Test tiroir**.
4. Si le test échoue : redémarrer l'imprimante.
5. S'assurer que l'option **Kick automatique** est activée dans les paramètres du tiroir.

### L'imprimante étiquettes (Zebra) ne répond pas

1. Vérifier que la Zebra ZD421d est allumée (voyant vert).
2. Vérifier qu'elle est sur le même réseau Wi-Fi que l'application.
3. Aller dans **Paramètres > Matériel > Imprimante étiquettes** et appuyer sur **Test étiquette**.
4. Si hors ligne : redémarrer la Zebra (interrupteur arrière).
5. En cas d'échec persistant : contacter le support pour vérifier la configuration réseau.

### Le TPE SumUp ne se déclenche pas

1. Vérifier que le TPE Solo est allumé et connecté au Wi-Fi.
2. Vérifier que l'option **SumUp** est activée dans **Paramètres > Paiement**.
3. Si le paiement ne se lance pas automatiquement : lancer manuellement depuis le TPE.
4. En cas d'erreur CB persistante : contacter SumUp au 0 800 980 003.

### Erreur 401 — Non autorisé

La session a expiré. Se reconnecter avec ses identifiants.

### La météo n'affiche pas les prévisions

La clé API OpenWeatherMap n'est pas configurée ou a expiré. Contacter le manager pour la mettre à jour dans les variables d'environnement (`OPENWEATHER_API_KEY`).

### Un article a été vendu par erreur

1. Ouvrir le ticket depuis le **Tableau de bord**.
2. Appuyer sur **Rembourser**.
3. Sélectionner l'article concerné.
4. Choisir le mode de remboursement.
5. L'article repasse automatiquement au statut **Retourné**.

### La liste des catégories affiche des doublons

Cela ne devrait plus arriver depuis la mise à jour V1 (les doublons ont été fusionnés et un contrôle empêche les doublons futurs). Si vous en observez à nouveau, contacter le support.

---

## Annexe A — Raccourcis et gestes utiles

| Action | Geste / Raccourci |
|---|---|
| Scanner un article | Pointer la douchette sur le code-barres, appuyer sur la gâchette |
| Chercher un article | Taper dans le champ de recherche |
| Ajouter une remise | Appuyer sur `-%` dans le panier |
| Ouvrir le menu (mobile) | Taper sur l'icône ☰ en haut à gauche |
| Fermer une modale | Appuyer en dehors de la fenêtre ou sur la croix × |
| Rafraîchir la page | Tirer l'écran vers le bas (pull-to-refresh) |

---

## Annexe B — Glossaire

| Terme | Définition |
|---|---|
| **Back-office** | Interface d'administration de la boutique (app.vintiz.fr) |
| **CA** | Chiffre d'affaires |
| **Caissier / Cashier** | Personne qui effectue les ventes à la caisse |
| **Code-barres** | Identifiant unique d'un article (format `VTZ-AAAA-XXXXX`) |
| **Douchette** | Lecteur de codes-barres USB (Inateck) |
| **ESC/POS** | Protocole d'impression des tickets thermiques (MUNBYN) |
| **Fond de caisse** | Monnaie présente dans le tiroir à l'ouverture de la journée |
| **GMROI** | Gross Margin Return on Investment — rentabilité du stock |
| **Magic link** | Lien de connexion sans mot de passe envoyé par email |
| **MUNBYN** | Imprimante thermique pour tickets de caisse (port réseau 9100) |
| **Avoir** | Crédit en euros sur le compte d'un client |
| **Personal Shopper** | Sélection personnalisée d'articles basée sur les goûts du client |
| **POS** | Point of Sale — caisse enregistreuse |
| **Rapport Z** | Rapport de clôture de caisse (total des ventes de la journée) |
| **RFM** | Récence, Fréquence, Montant — méthode de segmentation clients |
| **RGPD** | Règlement Général sur la Protection des Données |
| **Sell-through** | Pourcentage de stock vendu sur une période |
| **SumUp Solo** | Terminal de paiement CB (TPE) |
| **TPE** | Terminal de Paiement Électronique |
| **Trend Score** | Score de tendance d'un article (de 0 à 100) |
| **VTZ** | Préfixe des codes-barres Vintiz (ex. VTZ-2026-00142) |
| **Zebra ZD421d** | Imprimante d'étiquettes thermiques (25 × 52 mm) |
| **ZPL** | Zebra Programming Language — langage d'impression des étiquettes |

---

## Annexe C — Contacts et support

| Besoin | Contact |
|---|---|
| Problème applicatif / bug | Signaler via l'interface ou contacter le développeur |
| Problème SumUp (CB) | 0 800 980 003 (gratuit) ou support.sumup.com |
| Perte de mot de passe | Contacter le manager |
| Question RGPD client | dpo@solidarite-textiles.fr |
| Problème imprimante réseau | Vérifier IP + redémarrer l'imprimante |

---

*Document généré le 25 mai 2026 — Vintiz V1*
*Ce document est à usage interne. Il sera mis en forme par l'équipe communication avant diffusion.*
