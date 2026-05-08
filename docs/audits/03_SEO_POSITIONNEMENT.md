# Audit SEO & Positionnement — vintiz.fr

> **Auteur** : Claude (audit externe complémentaire)
> **Date** : 2026-05-08
> **Périmètre** :
> 1. SEO technique du site live `https://vintiz.fr` (mobile-first)
> 2. Positionnement vs concurrents 2nde main (national + zone Vernon + 30 min)
> 3. Lecture par 2 personas clients : Julie (P-CLI-FID) et Léa (P-CLI-DEC)
> 4. Recommandations architecture site / pages personnelles / personal shopper
> **Méthode** : fetch live HTML 16 routes, analyse Next.js / JSON-LD / OG / mobile, étude concurrentielle sourcée (35+ sources), grille mots-clés 30 entrées

---

## Synthèse exécutive

`vintiz.fr` est une **landing « coming soon » techniquement très propre** (Next.js 14, JSON-LD `ClothingStore` solide, GA4 Consent Mode v2 conforme, HTML 21 ko, scripts async, TTFB < 100 ms). Score SEO actuel estimé : **65 / 100**.

Mais **3 trous bloquants** empêchent l'activation commerciale :

1. **`/account` est public et indexable** (`KO-01`) — métadonnées héritées de la home, canonical pointant vers `/`, robots `index, follow` → pollution d'index probable + risque de fuite de contenu privé
2. **NAP incomplet** (`KO-02`) — pas de téléphone, pas d'email, pas de page `/contact` → SEO local cassé, fiche Google Business Profile non matchable
3. **Aucune page publique pour Personal Shopper** (`KO-03`) — opportunité majeure manquée sur les keywords « personal shopper Vernon/Normandie », faible concurrence + fort intent

À côté, **3 opportunités stratégiques majeures** sortent de l'étude concurrentielle :

- **Personal Shopper IA conversationnel adossé à un stock seconde main premium** = position **unique sur le marché FR au 05/2026**. Younzee (seul concurrent IA FR) n'a pas de stock physique. Vestiaire Collective fait de l'IA d'authentification, pas conversationnelle.
- **Zone Vexin Normand / Andelys / Giverny est une vraie zone blanche** sur le segment premium 2nde main → Giverny attire ~600 000 visiteurs/an CSP+ sans aucune offre 2nde main premium.
- **La Fripe (8 rue Carnot) liquidée fin 2024** → vide concurrentiel sur l'axe commerçant historique de Vernon.

**Effort 4 actions P0** : ~1,5-2 j-dev → score SEO passe à ~85/100, prêt pour ouverture boutique + activation GBP.

---

## Partie 1 — SEO technique de vintiz.fr

### 1.1 Inventaire des pages

16 routes testées, **5 publiques actives** :

| URL | HTTP | Indexable | Statut |
|---|---|---|---|
| `/` | 200 | `index, follow` | OK |
| `/account` | 200 | `index, follow` | **KO-01** zone privée indexable |
| `/mentions-legales` | 200 | `noindex, follow` | OK |
| `/cgv` | 200 | `noindex, follow` | OK |
| `/confidentialite` | 200 | `noindex, follow` | OK |
| `/sitemap.xml` | 200 | n/a | partiellement OK (voir 1.5) |
| `/robots.txt` | 200 | n/a | OK avec un manque (voir 1.5) |
| `/contact`, `/produits`, `/articles`, `/catalogue`, `/boutique`, `/personal-shopper`, `/services`, `/a-propos`, `/rendez-vous` | 404 | — | **toutes absentes** |

**Constat** : site en mode pré-ouverture. **Aucune page commerciale** (catalogue, fiche produit, page service Personal Shopper, contact) n'existe encore. Ce qui définit le périmètre : les 4 actions P0 ci-dessous sont prioritaires **avant l'ouverture**, pas des polishes.

### 1.2 Homepage `/` — détail technique

| Élément | Valeur | Statut |
|---|---|---|
| `<title>` | `Vintiz | Boutique seconde main premium à Vernon (27)` (53 char) | ✓ |
| `<meta name="description">` | 199 char — dépasse la limite Google ~155 → **truncature SERP** | ⚠ W-01 |
| `<link rel="canonical">` | `https://vintiz.fr` (présent **2× dans le head**) | ⚠ W-06 |
| `<meta name="robots">` | `index, follow` | ✓ |
| Open Graph | titre + description + url + locale + image présents | ⚠ W-02 (image = logo carré 512×512) |
| Twitter Card | `summary_large_image` mais image carrée → fallback `summary` côté X | ⚠ W-02 |
| JSON-LD | `ClothingStore` complet (adresse, geo, horaires, sameAs Insta/FB/TikTok) | ✓ avec manques (voir 1.4) |
| `<H1>` | « Votre nouvelle destination Slow Fashion premium. » — **ne contient pas « Vintiz » ni « Vernon »** | ⚠ W-03 |
| Body content | ~70 mots — **thin content** | ⚠ W-04 |
| Mobile viewport | `width=device-width, initial-scale=1` | ✓ |
| Touch targets | bouton newsletter `px-6 py-3`, sociaux `w-11 h-11` (44×44 px) | ✓ |
| Theme color | `#F6F5F1` (charte Sauge Néo) | ✓ |
| Performance | HTML 21,6 ko, 9 chunks JS async, 1 CSS, 6 fonts woff2 préchargées | ✓ avec ⚠ W-11 (6 fonts = 120-180 ko) |
| Accessibilité | `lang="fr"`, `aria-label` sociaux, `sr-only` pour label email | ✓ |
| GA4 | `G-6F4339T75H` avec Consent Mode v2 (defaults `denied`, conforme CNIL) | ✓ |
| Search Console verif | `<meta name="google-site-verification">` **absent** | ⚠ W-08 |

### 1.3 `/account` — espace client : KO-01 critique

`/account` répond 200 avec **les mêmes title/description/canonical/robots que la home** :

```
<title>Vintiz | Boutique seconde main premium à Vernon (27)</title>
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://vintiz.fr">
```

Conséquences :
- Google va crawler `/account` (autorisé), trouver le canonical vers `/` → signal incohérent
- Le shell SSR rend les liens `/account/fidelite`, `/account/shopper`, `/account/selection`, `/account/offres`, `/account/historique`, `/account/rgpd` → potentiellement crawlables
- **Risque** : indexation de pages privées + dilution du signal home

**Action P0** :

```tsx
// apps/site/src/app/account/layout.tsx
export const metadata = {
  title: 'Mon espace | Vintiz',
  description: 'Espace personnel Vintiz — fidélité, personal shopper, historique.',
  robots: { index: false, follow: false },
  alternates: { canonical: 'https://vintiz.fr/account' },
};
```

Ajouter dans `apps/site/src/app/robots.ts` :
```ts
disallow: ['/api/', '/account', '/account/']
```

### 1.4 JSON-LD `ClothingStore` — bonifications

Présent et bien rempli mais **dupliqué sur les 5 pages** (home + 4 légales). Manques :

```json
{
  "telephone": "+33 …",                  // P0 - manquant
  "email": "bonjour@vintiz.fr",           // P0 - manquant
  "currenciesAccepted": "EUR",            // P1
  "paymentAccepted": "Cash, Credit Card", // P1
  "contactPoint": {                       // P1
    "@type": "ContactPoint",
    "contactType": "customer service",
    "telephone": "+33 …",
    "email": "bonjour@vintiz.fr",
    "areaServed": "FR",
    "availableLanguage": ["French"]
  }
}
```

**Reco architecturale** : limiter `ClothingStore` à la home, mettre un simple `Organization` sur les autres pages. Évite la répétition artificielle de l'entité business.

### 1.5 Sitemap & robots.txt

**Sitemap** (4 URLs) :
```
/                  lastmod=2026-05-08T08:22:22.763Z  priority=1.0
/mentions-legales  lastmod=…  priority=0.2  (mais noindex)
/cgv               lastmod=…  priority=0.2  (mais noindex)
/confidentialite   lastmod=…  priority=0.2  (mais noindex)
```

⚠ W-05 : 3 URLs `noindex` figurent dans le sitemap → signal contradictoire à Google.
⚠ `lastmod` synthétique identique à la milliseconde → Google peut l'ignorer.

**Robots.txt** :
```
User-Agent: *
Allow: /
Disallow: /api/
Sitemap: https://vintiz.fr/sitemap.xml
```

⚠ W-10 : pas de `Disallow: /account` (combiné à KO-01, c'est doublement problématique).

### 1.6 Page 404

- `<title>` par défaut Next.js : `404: This page could not be found.`
- Double meta robots (`noindex` du composant 404 + `index, follow` du layout parent) → ambigu
- Aucun branding charte, pas de lien retour, pas de CTA newsletter

⚠ W-09 : créer `app/not-found.tsx` Vintiz-branded.

### 1.7 Score audit technique

| Domaine | Score |
|---|---|
| Performance | 95/100 (HTML léger, CDN Vercel, async scripts) |
| Mobile-friendliness | 90/100 (viewport, touch targets ≥ 44 px, Tailwind responsive) |
| On-page SEO | 60/100 (title OK, description trop longue, H1 sans keyword, thin content) |
| SEO local | 50/100 (JSON-LD ✓, geo meta ✓, mais NAP incomplet, pas de GBP) |
| Indexabilité | 55/100 (KO-01 `/account`, sitemap incohérent) |
| **Total estimé** | **65/100** |

---

## Partie 2 — Lecture mobile-first

L'utilisateur a explicitement demandé **vigilance sur la consultation smartphone**. C'est cohérent avec les personas : Julie consulte « 2×/mois iPhone » (P-CLI-FID), Léa cherche des « pièces uniques pour Insta » (P-CLI-DEC), donc 100 % mobile.

### 2.1 État mobile actuel

| Critère | Statut | Détail |
|---|---|---|
| Viewport meta | ✓ | `width=device-width, initial-scale=1` |
| Tailwind responsive | ✓ | classes `sm:`, `lg:` observées (`text-4xl sm:text-5xl lg:text-6xl`) |
| Touch targets ≥ 44×44 px | ✓ | bouton newsletter `px-6 py-3`, sociaux `w-11 h-11` |
| Lisibilité body | ⚠ | tailles non auditées finement, à valider sur device réel |
| Performance mobile | ✓ | HTML 21 ko, 1 CSS, scripts async — devrait passer Core Web Vitals |
| Image LCP | ✓ | logo hero `fetchPriority="high"` |
| Tap delay | ✓ | Next.js + viewport correct → pas de 300ms delay |
| Web App Manifest | ⚠ | non vérifié — à ajouter pour PWA + add-to-home iPhone |
| Apple Touch Icon | ⚠ | non vérifié — à ajouter pour qualité affichage iOS Safari |

### 2.2 Recommandations mobile spécifiques

| # | Action | Impact |
|---|---|---|
| 1 | Ajouter `apple-touch-icon-180.png` dans `<head>` (fallback iOS si web app installée) | UX iOS premium |
| 2 | Ajouter `manifest.json` (theme_color, icons 192/512, display standalone) | PWA add-to-home |
| 3 | Tester et corriger CLS (Cumulative Layout Shift) sur la home en chargement 3G | Core Web Vitals |
| 4 | Page `/personal-shopper` à concevoir mobile-first dès la maquette (carousel, sticky CTA, formulaire conversation IA) | conversion mobile |
| 5 | Catalogue produit : viser une grille 2 colonnes mobile (iPhone) avec lazy-load images WebP/AVIF | sell-through mobile |
| 6 | Drawer / bottom sheet pour les filtres au lieu de sidebars (qui marchent mal sur écrans <768 px) | UX |
| 7 | Sticky « Réserver / Demander » sur fiche produit | conversion |
| 8 | Wallet pass Apple Wallet déjà côté API (`/api/crm/clients/{id}/wallet`) → s'assurer que la carte fidélité Vintiz est ajoutable depuis le mobile en 1 clic | rétention |

### 2.3 Lecture mobile par persona

**Julie (Gold, 38 ans, Vernon, iPhone, 2×/mois)** :
- Pattern : reçoit une notif anniversaire / nouvelles arrivées le samedi matin → ouvre le site sur iPhone → consulte Personal Shopper → réserve 1-2 articles → vient récupérer en boutique
- Besoins UX mobile : connexion magic-link rapide, sélection PS visible en 2 clics, bouton « Réserver » sticky, push wallet pass Apple
- Frictions actuelles : pas de page commerciale, pas de personal shopper public → ne peut **rien faire** sur la home actuelle

**Léa (Bronze récente, 25 ans, Évreux, mobile-first, sensible Insta)** :
- Pattern : découverte via Insta/TikTok → atterrit sur vintiz.fr (probablement via lien bio Insta) → veut voir le catalogue, prix, ambiance
- Besoins UX mobile : feed visuel premier (gros carousel produits), possibilité de favoriser sans login, partage social facile, NAP clair pour passer à Vernon depuis Évreux (~30 min)
- Frictions actuelles : aucune offre visuelle, pas de NAP, pas d'horaires accessibles facilement, pas de catalogue → bounce probable

---

## Partie 3 — Personas appliqués au site

### 3.1 Julie — P-CLI-FID — Cliente fidèle Gold

**Profil** : 38 ans, Vernon, carte Gold, vient 2×/mois, panier moyen 65 €, pousse les copines à venir, sensible au matching style.

**Parcours actuel sur vintiz.fr** : ❌ impossible — site en mode coming soon, aucune page commerciale.

**Parcours cible** :

| Étape | Page | Besoin | Statut |
|---|---|---|---|
| 1. Notification reçue | email/SMS | « Nouvelles arrivées Sandro/Maje cette semaine » | ✓ backend P4-008/P4-009 |
| 2. Atterrissage iPhone | landing perso ? | accès direct à sa sélection PS | ✗ pas de page |
| 3. Connexion | `/account` | magic-link OTP 6 chiffres | ✓ backend OK, ✗ UI à finaliser |
| 4. Personal Shopper | `/account/shopper` | 5 recos narratives | ✓ backend, ✗ qualité UI à valider |
| 5. Réservation | fiche produit | hold 24-48h | ✓ backend P4-005 |
| 6. Visite boutique | mapping iPad caisse | retrait + upsell | ✓ POS |
| 7. Wallet pass | iPhone | carte fidélité virtuelle | ⚠ payload prêt, signing pas encore plugé |

**Gaps SEO/UX prioritaires Julie** :
- **G1** : sticky CTA « Mon espace » dès la home pour les cliquables connus
- **G2** : `/account` doit être `noindex` mais accessible directement via magic-link mail — pas un sujet SEO mais lien email à vérifier
- **G3** : page `/personal-shopper` publique pour exposer le service (Julie le connaît déjà, mais sa cousine non)
- **G4** : Wallet pass actif (signing Apple) → adoption iPhone immédiate

### 3.2 Léa — P-CLI-DEC — Cliente découverte

**Profil** : 25 ans, Évreux, Bronze récente, 1 visite, cherche pièces uniques pour Insta, sensible aux trends Vinted.

**Parcours actuel sur vintiz.fr** : ❌ aucune offre visuelle, pas de catalogue, bounce probable depuis Insta → site → 0 conversion.

**Parcours cible** :

| Étape | Page | Besoin | Statut |
|---|---|---|---|
| 1. Découverte Insta/TikTok | post/story Vintiz | accroche visuelle « pépite Sandro 35€ Vernon » | ✓ backend posts auto P4 |
| 2. Clic bio Insta | `/` ou `/produits` | feed produits chouette | ✗ catalogue absent |
| 3. Découverte ambiance | `/a-propos`, vitrine virtuelle | « qui c'est, qu'est-ce qu'ils proposent » | ✗ pas de page about |
| 4. Localisation | `/contact` ou footer | adresse, horaires, comment venir | ✗ NAP incomplet |
| 5. Personal Shopper teaser | `/personal-shopper` | « ils ont une IA qui te conseille ?? » | ✗ page absente |
| 6. Inscription | newsletter ou signup | RGPD double opt-in | ✓ backend, ✓ UI home |
| 7. Première visite Vernon | Maps + horaires | trajet Évreux → Vernon ~30 min | partiellement OK (JSON-LD) |

**Gaps SEO/UX prioritaires Léa** :
- **G5** : page `/produits` ou `/catalogue` minimale (10-15 pièces vitrine, photos premium, prix)
- **G6** : page `/a-propos` ou `/notre-histoire` (qui est Vintiz, lien Solidarité Textiles, ambiance)
- **G7** : page `/contact` avec NAP complet + Maps embed + horaires + photos boutique
- **G8** : page `/personal-shopper` pédagogique « Notre Personal Shopper IA »
- **G9** : feed Insta intégré sur la home (déjà partiellement avec sameAs, mais pas de mur Insta visuel)

---

## Partie 4 — Étude concurrentielle synthétique

### 4.1 Concurrents locaux — zone Vernon + 30 min

#### Vernon (cœur de zone)

| Acteur | Positionnement | Digital | Notes |
|---|---|---|---|
| **Anaïs luxury vintage** (55 rue d'Albuféra) | **Vintage premium** spécialité Chanel | Site anaisvintage.com + Facebook Anaisvintages | Concurrent direct le plus proche — orienté Chanel pur, peu d'e-com structuré, pas de SEO travaillé |
| Isabelle Friperie (8 rue Sainte-Geneviève) | Friperie traditionnelle | Pages Jaunes uniquement | Mainstream, peu visible |
| « Les vêtements de seconde main » (35 rue Carnot) | Friperie indépendante | Listing alternativi.fr | Mainstream |
| **La Fripe (8 rue Carnot)** | — | — | **LIQUIDÉE octobre 2024** → vide sur l'axe commerçant historique |
| Cash Express Vernon | Achat-revente multi-produits | cashexpress.fr + Facebook | Hors mode premium |
| **Gebetex Tri Normandie** | Grossiste B2B textile (centre de tri ECO TLC) | gebetextrinormandie.fr | Au kilo, mini 100 kg, **partenaire potentiel sourcing Vintiz** |
| Croix-Rouge Vernon | Vesti-boutique solidaire | eure.croix-rouge.fr | Ne pas concurrencer |

#### Évreux (~30 min)

| Acteur | Positionnement | Digital | Note Google |
|---|---|---|---|
| **Frip'Eure** (42 rue de La Harpe) | Friperie de marques **mainstream qualité** (5-30 €) | Facebook + Pages Jaunes + Mappy | **4,4/5** — concurrent dynamique mais pas premium |
| Lymea Frip / JANICK shop / Cartel Frip | Friperie / vintage | Présence faible | Mainstream |
| **Ressourcerie l'Abri** (392 rue de Cocherel) | Ressourcerie associative | Site associatif | Solidaire |
| Emmaüs Évreux | Communauté Emmaüs | emmaus-france.org + Facebook | Solidaire |
| Croix-Rouge Vesti-boutique Évreux | Solidaire | eure.croix-rouge.fr | Solidaire |

#### Mantes-la-Jolie / Vexin Normand / Andelys / Giverny

| Acteur | Notes |
|---|---|
| **Association Eco Solidaire (Mantes)** | Friperie associative + e-commerce — partenariats Le Relais / Croix-Rouge / Secours Populaire |
| Friperie Gisors (32 rue Frères Planquais) | Friperie multi très peu visible |
| Au Rythme des Marques (Gisors) | Boutique de marques (peut-être déstockage) |
| **Les Andelys / Étrépagny / Giverny** | **Aucune friperie / dépôt-vente premium identifié** → **zone blanche** |

**Lecture stratégique zone Vernon + 30 min** :

1. Une seule boutique premium positionnée à Vernon : Anaïs luxury vintage (Chanel pur, peu digital)
2. La rue Carnot a perdu La Fripe en 2024 → vide commerçant
3. **Giverny attire ~600 000 visiteurs/an, majoritairement CSP+ et internationaux, sans aucune offre 2nde main premium dans un rayon de 30 min** — opportunité majeure
4. Forte présence solidaire (Emmaüs, Croix-Rouge, Le Relais, Eco Solidaire) → opportunité de **partenariats** plutôt que concurrence frontale
5. Frip'Eure (Évreux) est le concurrent dynamique le plus proche, mais positionné mainstream (5-30 €) — Vintiz se distingue par le segment 50-300 €

### 4.2 Concurrents nationaux

| Acteur | Type | Force | Faiblesse | Apprentissage Vintiz |
|---|---|---|---|---|
| **Vinted** | C2C marketplace | 24,4 M visites/mois FR, leader incontesté | Pas de curation, pas d'authentification systématique | Présent sur Vinted Pro mais ne pas en dépendre |
| **Vinted Pro** | Boutiques pros sur Vinted | Visibilité instantanée, 0 % commission vendeur | Noyé parmi des milliers de pros | Canal multi mais pas central |
| **Vestiaire Collective** | Marketplace luxe | 1 Md€ GMV 2024, premier bénéfice 2026, pivot **« curatorial economy »** + IA | Luxe pur Hermès/Chanel, pas d'ancrage local | **Valide la thèse Vintiz curation + IA** mais Vintiz se positionne premium-accessible (Sandro/Maje/Sézane) |
| **Imparfaite** | Marketplace curée vintage premium | > 3 500 vendeurs pros, capsules « perles du mois », photos modèles, référencée Le Bon Marché | Pas de boutique physique, pas d'IA conversationnelle | **Benchmark central** : à répliquer en version locale (« Les pépites de Vernon ») |
| **Once Again** | Friperie en ligne + boutiques (Orléans, Compiègne, Ingré) | E-com solide + corner Gémo + grossiste B2B | Pas premium | Modèle omnichannel à étudier |
| **Vestiaire Collective IA** | IA d'authentification + recommandation | Géant international | Pas conversationnelle accessible | Vintiz peut être conversationnel, pas eux |
| **Younzee** | App **personal shopper IA française** + dressing virtuel | Première offre française IA mode | **Software only sur du neuf**, pas de stock 2nde main, pas de boutique | **Concurrent direct sur la brique IA** mais Vintiz se distingue par stock physique 2nde main |
| **Le Closet** | Location vêtements (modèle adjacent) | Abonnement 69,99 € / 6 pièces | Pas circularité longue | Brique « try-before-buy » via PS pourrait s'inspirer |
| **Beebs** | 2nde main enfant/famille (racheté Kiabi 2024) | 6 M articles, app native | Niche enfant uniquement | Hors cœur Vintiz mais coin enfant possible (Bonton, Bonpoint) |
| **Patatam** | 2nde main famille B2B | — | **Liquidation janvier 2024** | Leçon : unit economics solides obligatoires |
| **Ding Fring (Le Relais)** | 72 boutiques solidaires | Maillage national, 100 % insertion | Pas premium | **Partenaire potentiel** point de collecte Vintiz |

### 4.3 Personal Shopper IA — concurrence directe

**État du marché FR au 05/2026** :

| Acteur | Stock | IA conversationnelle | Boutique physique | Régionalisé |
|---|---|---|---|---|
| Younzee | ❌ neuf via partenaires | ✓ (avatar 3D + reco) | ❌ | ❌ |
| Vestiaire Collective | ✓ luxe seconde main | ⚠ authentification + reco partielle | ❌ | ❌ |
| Net-A-Porter | ✓ luxe neuf | ⚠ reco partielle | ❌ | ❌ |
| **Vintiz** | ✓ **2nde main premium curé** | ✓ **Claude Haiku conversationnel** | ✓ **Vernon** | ✓ **Normandie / Giverny** |

→ **Vintiz peut prendre une position de leader sur le sous-segment « Personal Shopper IA + 2nde main premium régionalisée »** — créneau libre.

---

## Partie 5 — Mots-clés SEO cibles

30 mots-clés segmentés en 4 catégories. Volume : F (<100/mois), M (100-1000), Fort (>1000). Difficulté : 1-10.

### 5.1 Locaux (priorité quick win — H1)

| # | Mot-clé | Volume | Difficulté | Priorité |
|---|---|---|---|---|
| 1 | friperie Vernon | M | 3 | **HAUTE** |
| 2 | ~~dépôt vente Vernon~~ | M | 3 | **EXCLU** — Vintiz fait achat ferme, pas de dépôt-vente. SEO trompeur. |
| 3 | ~~dépôt vente Eure~~ | M | 4 | **EXCLU** — idem |
| 4 | seconde main Vernon | F-M | 2 | **HAUTE** |
| 5 | seconde main premium Normandie | F | 2 | **HAUTE** |
| 6 | vintage Vernon | F | 2 | **HAUTE** |
| 7 | boutique femme Vernon | M | 4 | MOYENNE |
| 8 | friperie Évreux | M | 4 | MOYENNE |
| 9 | friperie Mantes-la-Jolie | M | 4 | MOYENNE |
| 10 | ~~dépôt vente Giverny~~ | F | 1 | **EXCLU** — idem |
| 11 | boutique seconde main Giverny | F | **1** | **HAUTE (zone blanche)** — remplace #10 |
| 12 | rachat vêtements de marque Vernon | F | 3 | **HAUTE** — capture l'intent vendeur (Vintiz rachète, pas dépôt) |
| 13 | vendre ses vêtements Vernon | F-M | 4 | **HAUTE** — idem, intent vendeur |

### 5.2 Transactionnels nationaux (H2)

| # | Mot-clé | Volume | Difficulté | Priorité |
|---|---|---|---|---|
| 11 | vêtements seconde main premium femme | M | 6 | **HAUTE** |
| 12 | robe Sandro occasion | M-Fort | 7 | MOYENNE |
| 13 | manteau Maje seconde main | M | 6 | MOYENNE |
| 14 | Sézane occasion authentique | M-Fort | 7 | MOYENNE |
| 15 | sac Polène d'occasion | M | 6 | MOYENNE |
| 16 | vintage femme luxe en ligne | M | 7 | MOYENNE |
| 17 | dressing premium occasion authentifié | F-M | 5 | **HAUTE** |
| 18 | dépôt vente luxe en ligne France | M | 8 | VEILLE |
| 19 | acheter vêtements occasion qualité | M | 6 | MOYENNE |
| 20 | seconde main mode éthique France | M | 6 | MOYENNE |

### 5.3 Informationnels / longue traîne (blog SEO H1-H2)

| # | Mot-clé | Volume | Difficulté | Priorité |
|---|---|---|---|---|
| 21 | comment vendre ses vêtements de marque | M | 5 | **HAUTE** |
| 22 | différence dépôt-vente et rachat ferme | F-M | 3 | **HAUTE** — angle pédagogique pour expliquer le modèle Vintiz |
| 23 | comment authentifier un sac de luxe | M | 6 | MOYENNE |
| 24 | quelle marque revendre en seconde main | F-M | 4 | **HAUTE** |
| 25 | est-ce rentable de vendre ses vêtements | M | 5 | **HAUTE** |

### 5.4 Personal Shopper IA (H3 stratégique)

| # | Mot-clé | Volume | Difficulté | Priorité |
|---|---|---|---|---|
| 26 | personal shopper en ligne | M | 6 | **HAUTE** |
| 27 | personal shopper IA | F-M (en croissance) | 4 | **HAUTE** (positionnement futur) |
| 28 | stylisme IA | F | 4 | MOYENNE |
| 29 | recommandation mode personnalisée | F-M | 5 | MOYENNE |
| 30 | conseiller en image en ligne seconde main | F | 3 | **HAUTE** (longue traîne unique) |

---

## Partie 6 — Architecture proposée

### 6.1 Site public (`apps/site`) — arborescence cible

```
/                                    home (refondue)
/contact                             P0 — NAP, formulaire, Maps embed, photos
/a-propos                            P1 — qui est Vintiz, ESS, Solidarité Textiles
/personal-shopper                    P0 — vitrine du service IA (publique, indexable)
/produits                            P1 — catalogue (10-15 pièces vitrine au lancement)
  /produits/[slug]                   P1 — fiche produit JSON-LD Product
  /produits?categorie=…              P2 — filtres SEO
/journal                             P2 — blog longue traîne (5 articles seed)
  /journal/comment-vendre-vetements-marque
  /journal/depot-vente-vs-vide-dressing
  /journal/comment-authentifier-sac-luxe
  /journal/quelle-marque-revendre-seconde-main
  /journal/rentabilite-vendre-vetements
/account                             noindex (espace connecté)
  /account/fidelite
  /account/shopper                   (UI Personal Shopper privée gated)
  /account/selection
  /account/offres
  /account/historique
  /account/rgpd
/cgv, /mentions-legales, /confidentialite   noindex (déjà OK)
/sitemap.xml, /robots.txt            mis à jour
```

### 6.2 Page `/personal-shopper` — spec détaillée

**Objectif** : capturer les keywords « personal shopper Vernon/Normandie » + « personal shopper IA » + « stylisme IA », et rediriger vers conversion (inscription espace client).

**Structure** :

```markdown
<title>Personal Shopper IA | Vintiz Vernon — Sélection seconde main personnalisée</title>
<meta description (155 char)>

H1 : Votre Personal Shopper IA chez Vintiz
Sous-titre : Une sélection sur-mesure de pièces seconde main premium, à Vernon et partout en Normandie.

[Hero visuel premium — boutique + capture conversation IA]

H2 : Comment ça marche
3 étapes : (1) Vos préférences (2) Notre IA croise votre style (3) Recommandations narratives

H2 : Ce que notre IA analyse
- Vos achats passés (avec votre accord)
- Vos préférences déclarées (tailles, couleurs, marques)
- Le contexte (météo, saison, occasion)
- Vos clics — boucle de feedback continue

H2 : Pourquoi c'est différent
- Stock physique premium curé à Vernon (Sandro, Maje, Sézane, Ba&sh, IRO…)
- IA conversationnelle Claude Haiku 4.5 (Anthropic, hébergement UE)
- Réservation 24-48h pour récupération en boutique
- Désactivation à tout moment, conformité RGPD complète

H2 : Confidentialité et contrôle
[Lien /confidentialite#personal-shopper]

H2 : Activer le Personal Shopper
CTA → /account (login magic-link)

JSON-LD Service:
{
  "@type": "Service",
  "name": "Personal Shopper IA Vintiz",
  "provider": { "@type":"ClothingStore","name":"Vintiz","url":"https://vintiz.fr" },
  "areaServed": { "@type":"City","name":"Vernon, Normandie" },
  "serviceType": "Personal Shopping",
  "offers": { "@type":"Offer","priceCurrency":"EUR","price":"0","description":"Service inclus pour les membres fidélité" }
}
```

### 6.3 Page `/contact` — spec détaillée

```
<title>Contact | Vintiz Vernon — 6 rue Saint-Jacques, 27200</title>
<meta description (155 char)>

H1 : Nous trouver et nous joindre

NAP en évidence :
  Vintiz
  6 rue Saint-Jacques
  27200 Vernon — Normandie
  Tél : +33 X XX XX XX XX
  Email : bonjour@vintiz.fr

Horaires : Mardi à Samedi 10h-19h
[Carte Google Maps embed]

H2 : Nous écrire
[Formulaire : nom, email, sujet (déposer/dénicher/PS/autre), message]

H2 : Suivez-nous
@vintiz.fr Insta · Vintiz Facebook · @vintiz.fr TikTok

H2 : Comment venir
- Depuis Évreux : ~30 min (D6155 / N13)
- Depuis Mantes-la-Jolie : ~25 min (A13)
- Depuis Giverny : ~10 min
- Parking : [détails]
- Train : Gare Vernon-Giverny (lignes Paris Saint-Lazare)

JSON-LD : enrichir ClothingStore avec telephone, email, contactPoint
```

### 6.4 Pages personnelles `/account` — refonte UX mobile

Les 6 zones existent déjà côté backend. Recommandations UX mobile :

| Zone | Optimisation mobile prio |
|---|---|
| `/account` (index) | Dashboard avec 4 cards : ma sélection PS, mes points, ma carte fidélité (wallet pass), mes offres |
| `/account/fidelite` | Wallet pass Apple/Google **bouton 1-clic** ; jauge points + tier next |
| `/account/shopper` | Conversation IA en mode chat mobile (input bottom sticky) ; cards reco swipeables ; bouton « Réserver 48h » sticky |
| `/account/selection` | Grille 2 colonnes mobile WebP/AVIF + favoris persistants |
| `/account/offres` | Coupons en cards avec gros code + bouton « Copier » |
| `/account/historique` | Liste paginée avec timeline + filtre type (achat/retour/avoir) |
| `/account/rgpd` | Consents togglables avec libellé clair ; bouton « Exporter mes données » + « Supprimer mon compte » (workflow 30j annulable) |

**Toutes ces pages doivent être `noindex`** (P0 KO-01).

### 6.5 Catalogue `/produits` — recommandations SEO

| Aspect | Recommandation |
|---|---|
| URL canonique | `/produits/[slug]` avec slug humain (`robe-sandro-noire-taille-38`) |
| JSON-LD `Product` | `name`, `image`, `brand`, `category`, `offers` (price, priceCurrency, availability), `condition` (`UsedCondition`) |
| Title | `[Nom produit] [Marque] [Taille] | Vintiz Seconde main Vernon` (60 char) |
| Description | « [Marque] [type] taille [size], couleur [c], état [état]. Authentifiée et sélectionnée par notre équipe à Vernon. » |
| Photos | min 4 angles, format WebP/AVIF via Next/Image, alt sémantique |
| Sticky mobile | bouton « Réserver 48h » + prix |
| `og:image` | photo principale 1200×630 |
| Maillage | « pièces similaires » (même marque OU même catégorie) |
| `noindex` | si stock épuisé, conserver la page mais `noindex, follow` |

---

## Partie 7 — Plan d'action consolidé

### Vague P0 — Avant ouverture publique (4 actions, ~2 j-dev)

| # | Action | Effort | Impact |
|---|---|---|---|
| 1 | **Créer `/contact`** + ajouter `telephone` + `email` + `contactPoint` dans JSON-LD | M (½ j) | Débloque SEO local + matching GBP |
| 2 | **Mettre `/account` et `/account/*` en `noindex`** + ajouter `Disallow: /account` dans `app/robots.ts` | S (1 h) | Corrige KO-01 |
| 3 | **Créer `/personal-shopper`** (page vitrine publique, 400-600 mots, H1 keyword, JSON-LD Service) | L (1 j) | Capture keywords personal shopper Vernon (faible concurrence) |
| 4 | **Raccourcir meta description home à ~155 char** + refondre H1 pour inclure « Vintiz » + « Vernon » | S (1 h) | CTR SERP + signal keyword principal |
| 5 | **Créer Google Business Profile** + valider GSC (DNS TXT ou via tag GA4) ; ajouter le lien GBP au `sameAs` | M (½ j) | Indispensable pack local Maps « friperie Vernon » |

### Vague P1 — Phase ouverture (juin 2026)

| # | Action | Effort |
|---|---|---|
| 6 | Créer image OG dédiée 1200×630 (façade ou ambiance) | M |
| 7 | Filtrer le sitemap : exclure les pages `noindex`, vraies dates `lastmod` | S |
| 8 | Ajouter 200-300 mots éditoriaux home (« Pourquoi Vintiz à Vernon ») | M |
| 9 | Créer page 404 personnalisée brandée Sauge Néo | S |
| 10 | Restreindre JSON-LD `ClothingStore` à la home, mettre `Organization` ailleurs | M |
| 11 | Créer page `/a-propos` (qui est Vintiz, lien Solidarité Textiles, ESS) | M |
| 12 | Créer page `/produits` avec 10-15 pièces vitrine au lancement | L |
| 13 | Audit fonts woff2 préchargées (sub-set, lazy familles secondaires) | M |
| 14 | Ajouter `apple-touch-icon` + `manifest.json` PWA | S |

### Vague P2 — Croissance (juillet-décembre 2026)

| # | Action | Effort |
|---|---|---|
| 15 | Blog `/journal` — 5 articles longue traîne (#21-25) sur 6 mois | XL (1 article = M) |
| 16 | Fiches produit SEO complètes avec JSON-LD `Product` | L |
| 17 | Catégories SEO « robe Sandro occasion », « manteau Sézane seconde main »… (pages dynamiques stock-driven) | L |
| 18 | Vinted Pro multi-canal (vitrine secondaire, sans dépendance) | M |
| 19 | Partenariats backlinks : Vernon Direct, Media Normandie, Office Tourisme Vernon, FashionNetwork, FashionUnited | XL |
| 20 | Capsules mensuelles « Les pépites de Vernon » (inspiration Imparfaite) | M récurrent |
| 21 | Schema `aggregateRating` dès les premiers avis Google Business | S |
| 22 | English-friendly site (i18n EN) pour cibler tourisme Giverny CSP+ international | XL |
| 23 | Partenariats hôtels Vernon-Giverny : corner Vintiz / co-marketing | XL |

### Vague H3-H4 — Stratégie 12-24 mois

| Horizon | Action |
|---|---|
| **H3 (6-18 mois)** | MVP Personal Shopper IA conversationnel public, capture keywords PS IA avant saturation, partenariats hôteliers Giverny |
| **H4 (12-24 mois)** | 2e point de vente (Rouen ou Évreux), partenariat Le Relais point de collecte, label Solidarité Textiles affiché, corners hôtels et concept stores |

---

## Partie 8 — Synthèse positionnement

### Forces actuelles Vintiz

- ✓ Site Next.js 14 techniquement très propre
- ✓ JSON-LD `ClothingStore` complet
- ✓ GA4 + Consent Mode v2 conformes
- ✓ Mobile-friendly (viewport, touch targets, Tailwind responsive)
- ✓ Backend mature : Personal Shopper IA fonctionnel, espace client RGPD complet, fidélité, wallet pass payload
- ✓ Marché FR du Personal Shopper IA + 2nde main premium est **vide** au 05/2026
- ✓ Zone Vernon-Giverny sans concurrent premium digital

### Faiblesses immédiates

- ✗ Site en mode coming soon — aucune page commerciale
- ✗ NAP incomplet (pas de tél, email, page contact)
- ✗ `/account` indexable par erreur
- ✗ Pas de page Personal Shopper publique
- ✗ Thin content home (~70 mots body)
- ✗ Pas de Google Business Profile

### 5 angles de différenciation à activer

1. **Premium curé vs friperie en vrac** — segment 50-300 € (Sandro/Maje/Sézane), inspiration Imparfaite (capsules mensuelles, photos modèles)
2. **Personal Shopper IA conversationnel adossé au stock** — unique sur le marché FR au 05/2026
3. **Boutique physique + digital + Vinted Pro multi-canal** — modèle Once Again revisité en premium
4. **Lien ESS / Solidarité Textiles + Le Relais** — narrative impact mesurable (kg sauvés, emplois insertion)
5. **Vernon = porte d'entrée Giverny** — capter le flux 600 000 visiteurs/an CSP+ avec offre English-friendly

### Score cible après vague P0

- Score SEO actuel estimé : **65/100**
- Après P0 (4 actions, ~2 j-dev) : **~85/100**, prêt pour ouverture publique

---

## Annexe — Sources principales (35+)

**Concurrents locaux** :
- pagesjaunes.fr/pros/56920755 (Anaïs Vicente Vintage)
- anaisvintage.com / facebook.com/Anaisvintages
- alternativi.fr/annuaire/friperie/vernon-27200
- gebetextrinormandie.fr
- societe.com/societe/la-fripe-912508843.html (liquidation)
- cashexpress.fr/magasin-vernon
- eure.croix-rouge.fr
- medianormandie.fr/2024/03/14/evreux-une-friperie-ouvre-rue-de-la-harpe (Frip'Eure)
- pagesjaunes.fr/pros/63065063 / 59500701
- emmaus-france.org/boutique/communaute-emmaus-elbeuf-evreux
- asso-ecosolidaire.fr/la-boutique-solidaire (Mantes)
- vexin-normand-tourisme.com (Au Rythme des Marques Gisors)
- vernon-direct.fr/en-mode-vintage

**Concurrents nationaux** :
- vinted.com/pro / vinteer.io/blog/guide-vendeur-pro-vinted-2026
- semrush.com/website/vinted.fr/overview
- meetandmatch.fr (Vestiaire Collective)
- fr.fashionnetwork.com (Vestiaire Collective rentable 2026)
- imparfaite.com / lebonmarche.com/en/marques/imparfaite
- onceagain.fr / france3-regions (Once Again Orléans)
- younzee.com/a-propos
- beebs.app / lsa-conso.fr (rachat Kiabi)
- lerelais.org (Ding Fring)
- la-mode-vintage.com / theparisianvintage.com
- ledressingdesalpilles.fr / closet2closet.eu / jaiio.fr / pretachanger.fr

**Marché & SEO** :
- iligo.fr/barometre-seconde-main-2026
- cm-cm.fr/post/vinted-le-relais-effet-rebond-6-chiffres-marche-textile-seconde-main
- ifmparis.fr/fr/actualites/marche-de-la-mode-2025-bilan-et-perspectives-2026
- repha.fr/seo-2026-donnees-cles
- semantisseo.com/blog/tendances-seo-2026
- blogdumoderateur.com/seo-2026-fin-chasse-mots-cles

**Personas Vintiz** : `AUDIT_VINTIZ_2026.md` §1.1
