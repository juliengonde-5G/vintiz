# Audit & stratégie — Site vitrine Vintiz (juin 2026)

**Objet (#9)** : unifier l'articulation du site, traiter les redondances,
vérifier les traductions EN, tester les liens (notamment vers l'espace client),
et établir une stratégie de pages compatible **SEO Google + SOO/SGE** (moteurs
de réponse IA).

> ⚠️ Document d'**état des lieux + plan**. Aucune modification de structure
> n'est faite avant ta validation de l'arborescence cible (§3) et de la
> décision `/dev` (§2).

---

## 1. Inventaire des pages

### Pages publiques FR (indexables)
| Route | Metadata | JSON-LD | EN ? |
|---|---|---|---|
| `/` (accueil) | ✅ (layout) | ClothingStore + WebSite | `/en` ✅ |
| `/produits` | ✅ | ItemList | `/en/produits`\* |
| `/produits/[slug]` | ✅ | ❌ (pas de `Product`) | ❌ |
| `/produits/made-in-france` | ✅ | — | (= `/en/produits`) |
| `/produits/marque/[brand]` | ✅ | — | ❌ |
| `/capsules` + `/capsules/[slug]` | ✅ | — | ❌ |
| `/journal` + `/journal/[slug]` | ✅ | Blog / BlogPosting | ❌ |
| `/a-propos` | ✅ | AboutPage | `/en/a-propos` ✅ |
| `/personal-shopper` | ✅ | Service | `/en/personal-shopper` ✅ |
| `/contact` | ✅ | ContactPage | `/en/contact` ✅ |

\* `/en/produits` pointe en réalité vers la sélection *made-in-france* (marques
iconiques FR), pas le catalogue complet.

### Pages légales (noindex, volontaire)
`/cgv`, `/mentions-legales`, `/confidentialite`, `/desinscription` — OK noindex.

### Espace client (noindex + robots disallow) — OK
`/account` + `/account/{login,fidelite,shopper,selection,offres,historique,rgpd,onboarding}`.

### ⚠️ Pages `/dev` (noindex) — la question centrale
`/dev`, `/dev/notre-boutique`, `/dev/contact` : **maquette parallèle** (route
group avec `DevHeader`/`DevFooter`, police serif, `robots:index=false`).
Doublonnent l'accueil, à-propos et contact, avec un **design plus abouti**
(images plein écran, témoignages clients 4,7★).

---

## 2. Redondances identifiées

| Doublon | Prod | /dev | Constat |
|---|---|---|---|
| Accueil | `/` (newsletter only, **sans PublicHeader**) | `/dev` (hero + concept + carrousel) | /dev plus riche |
| Boutique/À-propos | `/a-propos` (éditorial + JSON-LD) | `/dev/notre-boutique` (photos + avis) | contenus complémentaires |
| Contact | `/contact` (form + ContactPage JSON-LD + horaires) | `/dev/contact` (form simple, sans API) | prod plus complet |

**Le vrai problème** : il existe **deux chartes** en parallèle (production
`PublicHeader` + police Lexend/Poppins ; maquette `DevHeader` + serif). L'accueil
`/` de prod est un **holding page** (newsletter), alors que `/dev` ressemble à
l'accueil final voulu.

---

## 3. Arborescence cible proposée (à valider)

**Principe** : une seule charte (PublicHeader/PublicFooter), `/dev` résorbé.

```
/                      Accueil complet (reprendre le design /dev) + PublicHeader
/produits             Catalogue (filtres catégorie + marque)
/produits/[slug]      Fiche produit (+ JSON-LD Product/Offer + breadcrumb)
/produits/marque/...  Pages marque (SEO longue traîne "Sandro occasion Vernon")
/capsules             Sélections éditoriales
/journal              Journal (SEO contenu)
/a-propos             Histoire + ESS (fusionner les meilleurs éléments de
                      /dev/notre-boutique : photos boutique + avis clients)
/personal-shopper     Service PS (générateur de visites)
/contact              Contact (form API + horaires + plan)
+ miroir /en/* pour TOUTES les pages ci-dessus
+ legal noindex inchangé
```

**Décision `/dev` requise** (tu as choisi « audit d'abord ») :
- **Option A (recommandée)** : *promouvoir* le design `/dev` vers les pages prod
  (`/`, `/a-propos`, `/contact`), puis **supprimer `/dev`**. Une seule charte,
  meilleur rendu, zéro doublon.
- **Option B** : garder la prod actuelle, **supprimer `/dev`** (brouillon).
- Dans les deux cas : **`/dev` disparaît** à terme (aujourd'hui c'est de la
  dette : 3 pages noindex dupliquées).

---

## 4. Traductions EN (objectif : tout traduire)

**Existant** : `/en`, `/en/produits`, `/en/a-propos`, `/en/personal-shopper`,
`/en/contact` (hreflang bidirectionnel OK).

**Manquant (à créer)** :
- `/en/capsules` + `/en/capsules/[slug]`
- `/en/journal` + `/en/journal/[slug]`
- `/en/produits/marque/[brand]`
- `/en/produits` = vrai catalogue (aujourd'hui limité made-in-france)
- Nav EN (`PublicHeader`) : ajouter **Capsules** + **Journal** (absents)
- Footer EN : ajouter Capsules/Journal

**Volume** : ~6 routes EN + contenus éditoriaux (journal/capsules) à traduire.
C'est le **gros poste** de #9 → je propose de le faire en **PR dédiée par lot**
(d'abord nav + pages statiques EN ; puis contenus éditoriaux).

---

## 5. Liens & espace client

- Tous les liens publics vers `/account*` pointent vers des routes **valides**
  (`/account/login`, `/account`) — pas de lien cassé détecté.
- `/account/login` utilise l'ancien `Navbar` (incohérent avec PublicHeader) —
  cosmétique, à harmoniser.
- **Footer EN** : `/capsules` et `/journal` absents (FR : journal présent,
  capsules absent) → à compléter.

---

## 6. Stratégie SEO Google + SOO/SGE

### Acquis ✅
- `sitemap.ts` + `robots.ts` propres ; legal/account/dev noindex.
- JSON-LD : ClothingStore, WebSite+SearchAction, AboutPage, ContactPage,
  Service, Blog/BlogPosting, ItemList.
- hreflang bidirectionnel sur les pages cœur. CookieBanner + Consent Mode v2.

### À ajouter (impact SEO/SGE fort)
1. **Schema `Product` + `Offer`** sur `/produits/[slug]` (prix, dispo, marque,
   état/`itemCondition: UsedCondition`) → éligibilité résultats riches + SGE.
2. **`BreadcrumbList`** sur produits / journal / capsules (+ fil d'Ariane
   visuel) → meilleure compréhension de la hiérarchie par Google & les LLM.
3. **`FAQPage`** sur `/personal-shopper` et `/a-propos` (questions/réponses
   factuelles) → très favorable aux **réponses génératives (SGE/IA)**.
4. **Maillage interne** : fiche produit → page marque + catégorie + « pièces
   similaires » (aujourd'hui aucune sortie depuis la fiche).
5. **Accueil `/`** : monter `PublicHeader` + contenu indexable (aujourd'hui
   quasi vide = faible pour le SEO de la home).
6. **SGE/SOO** : contenu **factuel et structuré** (adresse, horaires, marques,
   ESS, « 10 min de Giverny ») déjà présent — le renforcer en JSON-LD +
   paragraphes courts « réponse directe » (les LLM citent ce qui est
   explicite et structuré).
7. **Contenu éditorial** (`/journal`, `/capsules`) = actif SEO longue traîne :
   prioriser quelques articles « authentifier un sac Polène », « Sézane
   d'occasion », ciblant l'intention d'achat locale (Vernon/Normandie).

---

## 7. Plan d'exécution proposé (PRs séquencées, après ta validation)

| Lot | Contenu | Dépend de |
|---|---|---|
| **S1** | Décision `/dev` (A/B) → unifier la charte, supprimer les doublons | ta validation §3 |
| **S2** | SEO technique : `Product`/`Offer` + `BreadcrumbList` + `FAQPage` + maillage fiche produit | — |
| **S3** | EN — nav/footer + pages statiques (`/en/capsules`, `/en/journal`, `/en/produits` complet, marque) | S1 |
| **S4** | EN — traduction des contenus éditoriaux (journal/capsules) | S3 |

---

## 8. Questions ouvertes (pour toi)
1. **`/dev`** : Option A (promouvoir le design /dev en prod) ou B (garder prod,
   supprimer /dev) ?
2. **Accueil** : veux-tu une vraie home riche (design /dev) dès maintenant, ou
   garder le holding newsletter jusqu'à l'ouverture ?
3. **EN éditorial** : traduire *tout* le journal/capsules (volumineux) ou les
   pages structurelles d'abord + éditorial au fil de l'eau ?
