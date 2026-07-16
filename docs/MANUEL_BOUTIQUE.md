# Manuel Vintiz — Guide manager / vendeur

> Dernière mise à jour : avril 2026
> Public : équipe boutique Vintiz Vernon (manager + vendeurs)

Ce document explique comment utiliser Vintiz au quotidien. Pour la doc
technique, voir [`CLAUDE.md`](../CLAUDE.md).

## 1. Vue d'ensemble

Vintiz, c'est **trois espaces** :

| Espace | URL | Pour qui | Rôle |
|---|---|---|---|
| **Caisse / iPad** | `app.vintiz.fr` | vendeur en boutique | Vente, encaissement, ticket |
| **Back-office** | `app.vintiz.fr` | manager + vendeurs | Inventaire, CRM, IA, rapports, paramètres |
| **Site public** | `vintiz.fr` | clients | Vitrine, newsletter, espace client |

Il n'existe aucun identifiant par défaut. Chaque membre de l'équipe utilise un
compte nominatif créé par le manager (Settings > Sécurité).

## 2. Premier démarrage de la journée

### A. Allumer le matériel

1. iPad caisse — Safari, page d'accueil épinglée sur `app.vintiz.fr`
2. Imprimante MUNBYN ticket (Wi-Fi) — voyant Wi-Fi vert fixe
3. Tiroir-caisse Safescan — branché sur l'imprimante (RJ-12)
4. Douchette Inateck — branchée en USB sur l'iPad (ou dongle)
5. TPE SumUp Solo — allumé et connecté au Wi-Fi
6. (Optionnel) Imprimante étiquettes SATO CT4-LX — pour générer/réimprimer
   des étiquettes produits

### B. Se connecter

1. Ouvrir Safari sur l'iPad → `app.vintiz.fr`
2. Se connecter avec son compte nominatif
3. Le **Dashboard** s'affiche : météo Vernon, KPIs du jour, derniers tickets

### C. Ouvrir la caisse

1. Aller sur **Caisse** (`/pos`)
2. Bouton **Ouvrir la caisse** → saisir le fond initial (ex : 100 €)
3. Confirmer — le tiroir s'ouvre, la caisse est prête

> Le fond initial sert au calcul de l'écart en clôture. Il est conseillé
> de toujours redémarrer avec le même montant.

### D. Cahier de Travail (manager)

Dashboard > **Cahier du jour** (`/dashboard/cahier-du-jour`)

- Affiche l'objectif CA du jour (calculé automatiquement à partir de
  l'objectif mensuel + poids historique des jours)
- Comparatif N-1, progression cumul mois, reste à faire
- Champs libres : **message du jour** (ex : "Live Insta 18h"), **opération
  en cours** (ex : "-20 % sur les robes")
- **Signatures** manager + équipe en fin de journée (clôture symbolique)

## 3. Vendre un article

### Mode 1 : Scanner le code-barres (recommandé)

1. Sur la page Caisse, le **champ recherche** est auto-focus
2. Scanner le code-barres avec la douchette Inateck
3. L'article s'ajoute automatiquement au panier

### Mode 2 : Recherche manuelle

1. Taper 2-3 lettres du nom dans le champ de recherche
2. Cliquer sur le résultat → ajout au panier

### Mode 3 : Article hors-stock (non répertorié)

1. Bouton **Article manuel** → saisir nom + prix
2. Ajouté au panier comme "manuel"
3. (Optionnel) Compléter ensuite la fiche depuis Inventaire pour le ré-utiliser

### Remises

- Cliquer sur le chip **`-%`** d'un article → choix 5/10/15/20/30 %
- Remise calculée automatiquement, total mis à jour

### Fidélité

- Si une cliente membre est rattachée, son solde et ses bons actifs apparaissent.
- 1 € payé sur un article **hors promotion, solde ou remise** rapporte 1 point.
- Chaque tranche de 100 points génère automatiquement un chèque cadeau de 5 €, valable 6 mois.
- Le bon est affecté au panier comme moyen de paiement. Les retours annulent les points correspondants.

### Encaissement

| Mode | Geste |
|---|---|
| **Espèces** | Saisir montant donné (numpad tactile), rendu monnaie auto. **Tiroir s'ouvre tout seul** |
| **CB SumUp** | Bouton "Carte (CB)" → le TPE Solo sonne et présente le montant. Le client paie. Statut polled toutes les secondes |
| **Chèque** | Saisir le montant, validation libre |
| **Mixte** | Empiler plusieurs lignes (ex : 50 € en CB + 30 € en espèces) |

### Ticket de caisse

Après validation, une modal *Vente validée* propose 3 boutons :

1. **Fermer sans ticket** — pas d'impression (le client n'en veut pas)
2. **Imprimer (MUNBYN)** — impression directe sur l'imprimante ESC/POS,
   ouvre le tiroir si configuré
3. **Imprimer (AirPrint)** — fallback via la dialogue d'impression iPad

> **Si rien ne sort de l'imprimante**, vérifier dans `/settings > Materiel`
> que l'IP et le port (par défaut 9100) sont corrects. Bouton "Imprimer un
> ticket de test" pour valider sans faire de vente.

### Renvoyer un ticket par email / SMS

Dashboard → cliquer sur la transaction → modal détail → boutons
**Renvoyer par email** / **Renvoyer par SMS**.

## 4. Fermer la caisse

1. Sur la page Caisse, bouton **Fermer la caisse**
2. Saisir le **montant compté physiquement** dans le tiroir
3. L'app calcule l'écart attendu vs réel
4. Validation → **Rapport Z** s'affiche : totaux par méthode, nb transactions,
   écart, numéro Z incrémental

> En cas d'écart inattendu, garder la fenêtre ouverte le temps de re-compter
> (le rapport peut être réimprimé).

## 5. Gérer l'inventaire

### Ajouter un article

`/inventory > Nouveau produit`

1. Photo (recommandé : photo nette, fond uni)
2. **Bouton "Analyse IA"** → Claude Vision détecte type, couleur, marque,
   taille, état, saison, gamme de prix estimée
3. Compléter / corriger les champs
4. Choisir une **zone** (Petits Prix 1/2, Extra 1/2, Tendance, Hommes, Chaussures F/H…)
5. Sauvegarder → un code-barres unique est généré + l'étiquette est imprimable

### Étiquette produit

Sur la fiche produit :

- Bouton **Télécharger étiquette** → PNG 50 × 30 mm avec nom + prix + barcode
- Bouton **Imprimer SATO** (si imprimante étiquettes configurée) → impression
  directe sur la SATO CT4-LX

### Score produit (IA)

Chaque article a un score sur 6 dimensions :

1. Tendance (correspondance moodboard saison)
2. Marque (premium / mid / mass)
3. État (neuf / très bon / bon)
4. Couleur (popularité couleur de la saison)
5. Mise en rayon (fraîcheur stock)
6. Photo (qualité visuelle)

Le score est recalculé automatiquement le **1er mercredi de chaque mois**.

## 6. CRM clients

### Ajouter un client en caisse

1. Pendant une vente, panneau **Client** → bouton "Nouveau client"
2. Nom, prénom, email (obligatoire pour la fidélité), téléphone
3. Création + carte fidélité Bronze automatique

### Carte fidélité

- Carte digitale unique au format `V######`, sans conversion directe des points.
- Gain : 1 point par euro éligible, hors promotion, solde et remise.
- Récompense : un chèque cadeau de 5 € à chaque tranche de 100 points.
- Le bon se cumule avec d'autres bons fidélité et s'utilise comme moyen de paiement au POS.

### Personal Shopper IA

`/clients > [Client] > Bouton "Personal Shopper IA"`

→ Claude génère une sélection personnalisée basée sur l'historique d'achats,
les marques préférées, les couleurs déjà choisies. Idéal pour préparer une
visite en boutique ou un email ciblé.

## 7. IA Booster

Onglet `/ia` (renommé "Compagnon IA") — 5 outils :

### Mapping Boutique

- Plan 2D des 11 zones (cf. `plan.jpg`, Lot N°2 ~184 m² utiles dont ~99 m² magasin)
  avec heatmap d'occupation (vert / jaune / rouge)
- Cliquer une zone → détail : produits présents, valeur, score moyen, photo
- Bouton **Recommandations IA** : Claude propose des réagencements
  (ex : "déplacer la robe Sandro de Petits Prix 2 vers Tendance")

### Checklist Semaine

Tous les lundis, IA génère 5–8 actions concrètes pour la semaine :
mises en avant, baisse de prix sur articles stagnants, focus vitrine, etc.

### Tendances Mode

Snapshot à jour des tendances Vinted / Pinterest / Instagram retail pour la
saison en cours. Utile pour prioriser les achats fournisseurs.

### Personas

- **Marketing** — rapport mensuel : performance, opportunités, plan d'action
- **Juridique** — audit RGPD : conformité collecte, durée conservation,
  droits clients

### Analyse photo

Upload d'une photo article → détection automatique pour pré-remplir la fiche
produit. Utilisable aussi depuis `/inventory > Nouveau produit`.

## 8. Newsletter (RGPD)

`/newsletter`

- **Liste** des inscrits avec recherche + filtres consentement
- **Export CSV** pour Brevo / Mailchimp / autre outil d'emailing
- **Suppression RGPD** sur demande client (clic sur la corbeille → confirmation)

L'inscription se fait depuis le site public : double consentement (case à
cocher + lien email de confirmation prévu en S2). La désinscription 1-clic
est disponible via le lien en pied de chaque newsletter.

## 9. Paramètres

`/settings`

| Onglet | Contenu |
|---|---|
| **Boutique** | Nom, adresse, horaires, infos légales |
| **Paiement** | SumUp env / sandbox / simulation, log d'événements live, approve manuel |
| **Cahier** | Objectif CA mensuel, poids historiques des jours |
| **Catégories** | Femme / Homme / Enfant — types de produits |
| **Zones** | 11 zones boutique (plan.jpg) : nom, capacité, types autorisés, photo, position 2D |
| **Materiel** | Imprimante ticket / tiroir / imprimante étiquette / douchette / TPE — IP, ports, tests |
| **Système** | Initialisation seed, infos versions |

### Onglet Materiel — détail

- **Imprimante reçus** (MUNBYN) : IP + port + largeur + cut paper. Test
  d'impression en 1 clic
- **Tiroir-caisse** (Safescan) : kick on cash (auto à chaque vente espèces),
  pin (0 ou 1), durée d'impulsion. Test "Kicker tiroir"
- **Imprimante étiquettes** (SATO) : IP + port + dimensions étiquette + DPI.
  Test SATO
- **Douchette** : longueur min, suffix, mode (USB HID standard)
- **TPE SumUp** : reader ID si push direct

> Tous les paramètres sont sauvegardés dans `apps/api/data/hardware.json`.
> Pas besoin de redéployer pour changer une IP.

## 10. Rapports

`/reports`

### Rapports historiques
- CA jour / semaine / mois / personnalisé
- Panier moyen, taux de transformation, top vendeurs
- Évolution N-1
- Export CSV pour comptabilité

### KPIs retail (P4-001)
- **Sell-through rate** : articles vendus / (vendus + en vitrine) sur la fenêtre
- **GMROI** (gross margin return on inventory) : approximation
  net_revenue / coût d'inventaire en vitrine
- **Days on Hand** : jours moyens passés sur la surface de vente
- **AIT** (average items per ticket) : panier moyen en nombre d'articles
- **CA / m² / mois** : revenu mensualisé rapporté à la surface (Lot N°2 ~98,70 m²
  zone magasin, éditable dans `Settings > KPIs config`)
- Top et bottom catégories
- % de variation vs période précédente

### Rapport ESS — Solidarité Textiles (P4-002)
- Pièces reçues / vendues / données / retournées au tri
- Taux de réemploi
- Tonnage estimé (poids moyen 0,5 kg/pièce, éditable)
- CA reversé à Solidarité Textiles (pourcentage configurable)

### Segmentation RFM (P4-007)
9 segments calculés mensuellement (1er du mois, 04:00) :
- Champions, Fidèles, Nouvelles, Prometteuses, À ne pas perdre, À risque,
  En sommeil, Perdues, Régulières
- Bouton "Recalculer maintenant" pour rafraîchir à la demande
- Visualisation barres + clic pour voir la liste des clientes par segment

## 11. Communication automatique (Phase 4)

### Email anniversaire (P4-008)
Cron quotidien 09:00. Pour chaque cliente dont c'est l'anniversaire et qui
a opt-in email : crée un coupon `ANNIV-XXXXXX` -10% valable 7 jours et
envoie l'email. Idempotent — relancer le jour-même n'envoie pas en double.
Trigger manuel : `Settings > Outils > Anniversaires`.

### Email nouvelles arrivées (P4-009)
Cron hebdo vendredi 10:00. Digest des 5 dernières pièces sur la vitrine
envoyé aux clientes opt-in email. Personnalisé via Personal Shopper si
profil de goût présent, sinon plus récents génériques.

### Réservation 48h (P4-005)
`/reservations` — Camille pose un hold pour une cliente sur un article
spécifique. La cliente le voit sur son espace `vintiz.fr/account/data`.
Au POS, un bandeau alerte si l'article est tenu pour quelqu'un d'autre,
ou confirme en vert si c'est la bonne cliente. La réservation est
encaissée automatiquement à la validation de la vente. Cron horaire
expire automatiquement les holds dépassés.

### Wallet pass (P4-004)
Carte fidélité dématérialisée avec QR membership stable. Affichée sur
l'espace client `/account/data`. La signature Apple `.pkpass` et Google
Wallet JWT sont en attente d'activation côté ops (cert + service account).

## 12. Site public

`vintiz.fr` — landing avec :

- Hero produits + concept
- Newsletter (RGPD)
- Espace client (login email — magic-link prévu)
- Personal Shopper IA accessible aux clients fidélisés
- Mentions légales / CGV / Confidentialité / Désinscription

## 13. Dépannage rapide

| Problème | Vérifier |
|---|---|
| L'app ne charge pas | Wi-Fi iPad, voyant Caddy/Internet sur la box |
| L'imprimante MUNBYN n'imprime pas | `/settings > Materiel > Imprimer ticket test`. Si KO : IP, voyant Wi-Fi MUNBYN |
| Le tiroir ne s'ouvre pas en espèces | Settings : "kick on cash" activé, pin correct (0 ou 1). Sinon Safari → autoriser les pop-ups pour `app.vintiz.fr` |
| Le TPE SumUp ne sonne pas | Settings > Paiement : `SUMUP_READER_ID` défini, env "production", clé API valide |
| Douchette ne fonctionne pas | Champ recherche bien auto-focus ? Cliquer dans le champ. Tester sur un éditeur de texte pour valider la connexion USB |
| 401 quand on charge une page | Token expiré → se reconnecter |
| Météo bloquée | Clé OpenWeather expirée — voir Settings > Système |
| Compte verrouillé après 10 essais ratés | Attendre 5 min ou contacter dev (voir AUDIT_2026_04 §3-S3) |

## 13. Bonnes pratiques

- **Toujours scanner** plutôt que chercher manuellement (rapide, anti-erreur)
- **Saisir l'email client** dès que possible (fidélité + relances)
- **Photographier les nouveautés** avec une lumière constante pour que l'IA
  Vision détecte mieux la couleur
- **Clôturer la caisse chaque soir** même si CA = 0 (rapport Z numéroté)
- **Vérifier le cahier du jour le matin** pour avoir l'objectif et les
  recommandations IA en tête

## 14. Aide

- Bug ou question : équipe dev / Julien
- Documentation technique : [`CLAUDE.md`](../CLAUDE.md)
- Audit sécurité : [`docs/AUDIT_2026_04.md`](./AUDIT_2026_04.md)

— Vintiz, Vernon, Normandie.
