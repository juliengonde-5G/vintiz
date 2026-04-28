# Vintiz — UX Design Brief

> Public : équipe design (Claude Design ou autre) qui produira des wireframes,
> mockups haute fidélité, refontes ou nouvelles fonctionnalités.
>
> Ce document décrit le **contexte d'usage**, les **parcours**, les **états**,
> les **contraintes** et les **objectifs UX** de chaque écran.
>
> La charte graphique (palette, fonts, logos) est dans
> [`DESIGN_SYSTEM.md`](./DESIGN_SYSTEM.md). Ce document UX la **complète**
> sans la dupliquer.

---

## 1. Identité du produit

**Vintiz** est un logiciel tout-en-un pour une boutique de seconde main
premium à Vernon (Normandie). C'est un outil de **vendeuse experte** :
elle connaît ses clients, ses pièces, son stock, et l'app doit la rendre
plus rapide, pas la contraindre.

**Ton** : chaleureux, élégant, sans jargon technique. La couleur dominante
est le **teal `#008678`** (couleur signature) sur un fond `cream #FFF3ED`,
avec des accents `pink #FFC5DF` pour la fidélité.

**Référence retail** : Aesop, Muji, Sézane (clarté, espace blanc, photos
soignées). À l'opposé : Cdiscount, Amazon, GoogleAdSense (encombrement,
spam visuel).

---

## 2. Personas

### P1 — Hélène, la manager (45 ans, propriétaire)

- Profil : ancienne directrice de boutique mode, autodidacte digital
- Usage : matin (Cahier du jour), soir (clôture, rapports), tout le mois
  (objectifs, IA marketing)
- Frustrations : "Je n'ai pas le temps d'apprendre 15 logiciels"
- Besoins : vue d'ensemble en un coup d'œil, IA qui propose des actions
  concrètes (pas des graphes vides)
- **À optimiser** : Dashboard, Cahier du jour, Personas IA, Rapports

### P2 — Margaux, la vendeuse (28 ans, temps partiel)

- Profil : passionnée mode, peu d'expérience caisse
- Usage : caisse iPad toute la journée (vente, encaissement, ticket)
- Frustrations : "Je perds 30 sec à chaque client à chercher un produit"
- Besoins : douchette qui marche, modal courte et claire, jamais d'erreur
  qui bloque la vente
- **À optimiser** : POS, recherche produit, modal de paiement, ticket

### P3 — Sophie, la cliente fidèle (35 ans, cadre)

- Profil : achète 2-3 fois par mois, sensible à l'attention
- Usage : site web (avant la visite), espace client, Personal Shopper IA
- Frustrations : "On me redemande toujours mes infos"
- Besoins : reconnaissance, propositions pertinentes, pas de friction RGPD
- **À optimiser** : site public, espace client, Personal Shopper

---

## 3. Inventaire des écrans (état avril 2026)

### Back-office (`apps/web` — Hélène + Margaux)

| Route | Titre | Persona principal |
|---|---|---|
| `/login` | Connexion | toutes |
| `/dashboard` | Vue d'ensemble | Hélène |
| `/dashboard/cahier-du-jour` | **Cahier de Travail** | Hélène |
| `/pos` | Caisse | Margaux |
| `/pos/close` | Clôture caisse | Margaux + Hélène |
| `/inventory` | Liste inventaire | Hélène |
| `/inventory/[id]` | Fiche produit | Hélène |
| `/inventory/new` | Créer produit | Hélène |
| `/clients` | Liste clients | Hélène |
| `/ia` | Compagnon IA (5 outils) | Hélène |
| `/zones` | Plan boutique | Hélène |
| `/admin` | Transactions admin | Hélène |
| `/newsletter` | Inscrits newsletter | Hélène |
| `/seo` | Healthcheck SEO | dev |
| `/settings` | Paramètres + Materiel + Paiement + Cahier | Hélène |
| `/reports` | Rapports CA | Hélène |

### Site public (`apps/site` — Sophie)

| Route | Titre |
|---|---|
| `/` | Landing |
| `/espace-client` | Login email + carte fidélité + historique |
| `/personal-shopper` | Sélection IA |
| `/desinscription` | Unsub newsletter (RGPD) |
| `/cgv` `/mentions-legales` `/confidentialite` | Légales |

---

## 4. Contraintes physiques

| Contrainte | Implication |
|---|---|
| **iPad 10" 1024 × 768** | POS doit tenir sur 1 écran sans scroll vertical sur la zone principale |
| **Tactile** | Touch targets ≥ 44 × 44 px partout |
| **Une main** (l'autre tient un article) | Boutons critiques accessibles au pouce — bas droit de l'écran |
| **Pas de clavier physique** | Numpad tactile pour les montants, recherche en mode "progressive" |
| **Lumière variable** (vitrine, fond) | Contrastes WCAG AA mini |
| **Bruit ambiant** | Pas d'audio de feedback (pas de "ding") sauf MUNBYN beep optionnel |
| **Douchette USB HID** | Le champ recherche POS doit être **auto-focus** au chargement et au retour de modal |
| **Imprimante MUNBYN** offline possible | Toujours proposer un fallback "Fermer sans ticket" |
| **iPad lock screen** après 5 min | Reconnexion JWT silencieuse, pas de perte de panier |
| **Wi-Fi flaky** | Indicateur de connectivité subtil mais visible (badge offline en haut-droite) |

---

## 5. Heuristiques Vintiz

À appliquer systématiquement quand on conçoit un nouvel écran ou une
modification.

### H1 — Une seule action principale par écran

Chaque écran a **un objectif clair** (vendre, encaisser, valider, signer).
Une seule CTA primaire `bg-teal text-white`. Les actions secondaires sont
en outline `border-teal text-teal`.

### H2 — Pas de scroll caché

Sur iPad, les éléments critiques (panier, total, encaisser) sont **toujours
visibles**. On scrolle dans des sous-zones, pas dans la page entière.

### H3 — État vide explicite

Pas de page blanche. Toujours :
- Un titre court (`Aucun produit pour l'instant`)
- Une explication d'1 ligne (`Ajoutez votre premier article via le bouton ci-dessous`)
- Une CTA pour sortir de l'état vide

### H4 — Erreur = solution + action

Pas de `Error: 500`. Toujours :
- "Impossible de charger les produits"
- "Vérifiez votre connexion Wi-Fi"
- Bouton "Réessayer"

### H5 — Loading = squelette, pas spinner

Skeleton loaders gris clair animés sur les cards / tableaux. Pas de spinner
centré sur fond crème — c'est trop "interface technique".

### H6 — La fidélité doit briller

Tout ce qui touche à la fidélité (points, tier Bronze/Silver/Gold, Personal
Shopper) utilise du **`pink-100` / `pink-700`**. C'est un moment chaleureux,
pas une transaction froide.

### H7 — IA visible mais discrète

Les fonctions IA (analyse photo, mapping, recommandations) sont **dans un
panneau dédié**, pas mélangées aux fonctions standard. Leur badge est subtil
(`✨` ou `Compagnon IA`), pas un gros "POWERED BY AI".

### H8 — Une vente prend 30 secondes ou moins

Du scan au "Imprimer le ticket", le parcours doit pouvoir se faire en 4
gestes max : scan, ajouter, encaisser, imprimer. Tout ce qui rallonge
(remise, fidélité, client) est optionnel et accessible en 1 tap.

### H9 — Le ticket de caisse est la signature

C'est ce que le client emporte chez lui. Logo VINTIZ noir sur thermique, mise
en page sobre, avec le numéro de téléphone et l'adresse en pied. Pas de QR
code "follow us" qui prend 1/3 du ticket.

### H10 — Mobile-first sur le site public, iPad-first sur le back-office

Site `vintiz.fr` : toujours penser smartphone d'abord (Sophie regarde sur son
téléphone dans le métro). Back-office : iPad d'abord, puis ordinateur.

---

## 6. Parcours clés (à ne jamais casser)

### P-VENTE (Margaux, 30 secondes)

```
[Caisse en attente, recherche auto-focus]
   ↓ scan code-barres
[Article ajouté au panier]
   ↓ tap "Encaisser"
[Modal paiement — espèces / CB / chèque]
   ↓ tap "Espèces" + saisir 50 €
[Rendu monnaie affiché — tiroir s'ouvre]
   ↓ tap "Valider"
[Modal "Vente validée" — Imprimer / Fermer sans ticket]
   ↓ tap "Imprimer (MUNBYN)"
[Modal se ferme, retour à Caisse en attente]
```

**À préserver** : aucun écran intermédiaire entre le scan et le panier ;
modal paiement avec numpad sans scroll ; tiroir s'ouvre à la validation
(pas avant) ; ticket imprimable mais jamais imposé.

### P-FIDELITE (Margaux, +15 secondes)

```
[Vente en cours, panier rempli]
   ↓ tap "Client"
[Modal recherche client — par nom / email / téléphone]
   ↓ taper "Sophie"
[Liste résultats — tap sur la bonne]
[Panneau client visible : points, tier]
   ↓ toggle "Utiliser les points"
[Total mis à jour avec remise fidélité]
```

### P-CAHIER (Hélène, 2 minutes le matin)

```
[Login → Dashboard]
   ↓ tap "Cahier du jour"
[Page Cahier — date du jour]
   ↓ lecture : objectif CA jour, météo, message du jour
   ↓ scroll : KPI cumul mois, comparatif N-1
   ↓ saisie "Opération en cours" si besoin
[Tap "Signer (manager)" en fin de journée]
```

### P-NOUVEAU-PRODUIT (Hélène, 1 minute)

```
[Inventaire → Nouveau produit]
   ↓ tap "Photo" + capture iPad
[IA analyse → 80 % des champs pré-remplis]
   ↓ correction taille + zone
   ↓ tap "Sauvegarder"
[Fiche produit + barcode + bouton "Imprimer étiquette SATO"]
```

---

## 7. Composants critiques

### POS — Cart Item

- Hauteur compacte (≤ 64 px) pour afficher 5-6 items sans scroll
- Strip remise **masquée par défaut**, ouverte via chip `-%`
- Boutons `+ / −` quantité tactiles (44 px chacun)
- Croix suppression à droite, confirmation seulement si quantité > 1

### POS — Numpad

- 4 × 4 grille tactile, 1 / 2 / 3 / .
- Boutons "rapides" : 5 € / 10 € / 20 € / 50 € / 100 €
- Affichage en grand du montant en haut

### Modal de paiement (iPad)

- Pas de scroll sur le contenu principal
- 3 onglets espèces / CB / chèque, plus possibilité d'empiler (paiement mixte)
- Total + reste à payer toujours visibles en haut

### Modal "Vente validée"

- 3 boutons côte à côte (responsive : empilage en mobile)
- L'ordre d'importance suit l'usage réel : Fermer sans ticket → MUNBYN → AirPrint
- Ticket aperçu monospace en arrière-plan (`pre`, `whitespace-pre-wrap`)

### Cahier du Jour — Header

- Bandeau date + jour + météo + message du jour
- Hero KPI : objectif CA jour + reste à faire
- Couleur du chiffre : teal si en avance, gris sinon, rouge si très en retard

### Compagnon IA — Cards

- Chaque outil IA dans une carte indépendante (Mapping, Checklist, Tendances,
  Personas, Photo)
- Header card avec **icône emoji** + titre + 1 ligne de description
- Bouton CTA spécifique à chaque outil

### Sidebar (back-office)

- Largeur 256 px desktop, drawer mobile
- 4 groupes (Pilotage, Commerce, Intelligence, Configuration)
- Icônes outline sans fill (sauf actif → fill teal)
- Logo en haut, profil utilisateur en bas

---

## 8. États à toujours prévoir

Pour chaque nouveau composant ou écran, prévoir :

| État | Maquette |
|---|---|
| **Empty** | "Pas encore de [...]." + CTA |
| **Loading** | Skeleton (jamais spinner sur fond crème) |
| **Success** | Toast `bg-teal text-white` 3s en bas-droite |
| **Error** | Card rouge claire avec message + bouton "Réessayer" |
| **Disabled** | `opacity-40 cursor-not-allowed` + tooltip "Pourquoi" |
| **Hover desktop** | `hover:bg-teal/5` ou `hover:shadow-md` |
| **Active touch** | `active:scale-[0.98]` (feedback tactile rapide) |
| **Focus clavier** | `focus:ring-2 focus:ring-teal` (a11y) |
| **Offline** | Badge top-right `Hors-ligne — synchro reprendra` |

---

## 9. Accessibilité

- Contraste : teal `#008678` sur cream `#FFF3ED` → **6.4:1** ✅ AAA
  pour le texte large, AA pour le texte normal
- Toujours `aria-label` sur les boutons à icône seule
- Modal : focus trap + Esc + restitution focus à la fermeture
  (en cours d'implémentation, cf. AUDIT §5)
- Tables : `role="table"`, `<th scope="col">`
- Forms : `<label for=>` toujours, jamais juste `placeholder`
- Skip-link "Aller au contenu" en haut de chaque page
- Boutons jamais sur du `<div onClick>` — toujours `<button>`

---

## 10. Animations

Sobre. Tout doit être ≤ 200 ms et signifier quelque chose.

| Action | Animation | Durée |
|---|---|---|
| Modal open | fade + scale-95 → 100 | 150 ms ease-out |
| Modal close | fade out + scale-100 → 95 | 100 ms ease-in |
| Toast | slide from bottom + fade | 200 ms ease-out |
| Button tap | scale 1 → 0.98 → 1 | 100 ms |
| Skeleton shimmer | gradient sweep | 1.5 s loop |
| Sidebar mobile | slide from left | 200 ms ease-out |
| Bouton CB en attente | pulse `opacity 1 → 0.7 → 1` | 1.5 s loop |
| Tiroir kické | flash teal sur le bouton | 200 ms |

**À éviter** : confetti, gros bounce, parallax sur scroll, transitions de
page longues. Vintiz n'est pas une app fitness, c'est un outil de travail.

---

## 11. Photographie produit (charte vente)

- Fond uni `cream` ou blanc cassé
- Article suspendu ou posé bien à plat (jamais froissé)
- Lumière naturelle ou LED 5000K
- Cadrage : article centré, marge 10 % autour
- Format : 4:5 portrait pour le site, 1:1 carré pour la grille admin
- Pas de mannequin, pas de mise en scène théâtrale

L'IA Vision Claude détecte mieux quand la photo est **propre et nette**.
Photos floues = analyse moins fiable.

---

## 12. Tone of voice (textes UI)

- Adresse au "tu" en interne, "vous" sur le site public
- Verbes à l'impératif courts pour les CTA : "Encaisser", "Imprimer",
  "Renvoyer", "Sauvegarder"
- Pas de jargon technique exposé : "synchronisation" plutôt que "sync DB",
  "clôture caisse" plutôt que "close drawer transaction"
- Pas de point en fin de bouton ("Encaisser", pas "Encaisser.")
- Erreurs : factuelles + actionnables, jamais "Oups, une erreur s'est
  produite 🙃"

Exemples bons / mauvais :

| ❌ Mauvais | ✅ Bon |
|---|---|
| "Erreur 500 - Internal Server Error" | "Impossible d'imprimer. Vérifiez la connexion de l'imprimante." |
| "Loading..." | "Chargement des produits..." (ou skeleton) |
| "Êtes-vous sûr de vouloir continuer ?" | "Supprimer ce client ?" |
| "Submit" / "OK" | "Sauvegarder" / "Confirmer" |
| "Powered by AI 🤖" | (rien — c'est dans le titre `Compagnon IA`) |

---

## 13. Roadmap UX (à designer)

### Livré Phase 4 (avril 2026)

- ✅ **Mobile back-office (partiel)** — strip KPI sticky compact sur le
  dashboard mobile (CA / tickets / panier) en plus du grid responsive
  existant. Reste à faire : bottom-nav iOS-style.
- ✅ **Cards retail KPIs / ESS / RFM** sur `/reports` (P4-001 / 002 / 007).
- ✅ **Badges IA POS** sous chaque ligne du panier (P4-010) — vélocité,
  stale, marque, score.
- ✅ **Wallet preview card** sur l'espace client public `/account/fidelite`
  (P4-004) — preview seulement, signing Apple/Google reste à plugger.
- ✅ **Espace client refondu en 6 zones** (avril 2026) — `/account`
  (dashboard), `/fidelite`, `/shopper`, `/selection`, `/offres`,
  `/historique`, `/rgpd`. Chrome partagé `AccountShell` + side nav
  responsive (drawer mobile + sidebar desktop). Magic-link OTP email,
  fin du `?email=` dans les URLs.
- ✅ **POS Companion** — panneau latéral cart-aware (debounce 300 ms)
  affichant loyalty + 3 suggestions complémentaires + coupons +
  alertes RFM. Visible dès qu'un client est identifié au POS.
- ✅ **Fiche client admin** `/clients/[id]` — 6 onglets (Synthèse /
  Achats / Fidélité / Goûts / RGPD / Audit) chargés en 1 requête.

### Backlog encore à designer (post-Phase 4)

1. **Refonte Dashboard** — actuellement un peu chargé, besoin d'un hero
   plus visuel (météo + KPI principal + CTA "Voir le cahier")
2. **POS — mode "rush"** — un layout encore plus minimaliste pendant les
   pics (ouvre une modal verrouillée, juste scan + encaisser)
3. **Personal Shopper côté client** — page dédiée magnifique
   (carrousel de pièces, ajout à une wishlist, RDV en boutique)
4. **Nouveau onboarding inventaire** — wizard 3 étapes (photo → IA →
   confirmation) au lieu du formulaire long actuel
5. **Bottom-nav iOS-style mobile** (4 icônes : Dashboard, Caisse,
   Inventaire, Plus) — finir le travail commencé avec le sticky bar.
6. **Vue plan boutique heatmap** — animer les zones (saturation = vente
   récente)
7. **Notification system** — toast persistants empilés + centre de
   notifications (cloche en sidebar). Les emails transactionnels Brevo
   (P4-003) couvrent déjà le canal email.
8. **Add to Wallet bouton réel** — une fois la signature `.pkpass` /
   Google JWT plugée côté ops, remplacer la preview card par un vrai CTA.

---

## 14. Livrables attendus du design

Pour chaque écran ou flow, fournir :

1. **Mockup haute fidélité** Figma — desktop 1280, iPad 1024, mobile 375
2. **États** (empty / loading / error / success / disabled)
3. **Spécifications** — tokens utilisés, marges, transitions
4. **Composants réutilisables** — listés et liés au design system v2
5. **Notes a11y** — focus order, aria-label, contrastes vérifiés

Code rendu : Tailwind + composants existants dans
`apps/web/src/components/ui/` (Button, Card, Input, Modal, NumPad). Si un
nouveau composant est nécessaire, le proposer dans la même structure.

---

## 15. Références

- [Design System v2](./DESIGN_SYSTEM.md) — tokens, palette, typo
- [CLAUDE.md](../CLAUDE.md) — endpoints API, structure data
- [Manuel Boutique](./MANUEL_BOUTIQUE.md) — usage réel
- [Audit avril 2026](./AUDIT_2026_04.md) — points UX déjà identifiés à corriger

— Vintiz, Vernon, Normandie.
