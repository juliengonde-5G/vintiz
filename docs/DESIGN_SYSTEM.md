# Vintiz — Design System v2 (2026-04)

Charte graphique officielle. Toute évolution visuelle doit respecter ce
document.

## 1. Palette

| Usage | Token | Hex | Commentaire |
|---|---|---|---|
| Signature / CTA / liens | `teal` | `#008678` | Vert-teal profond, couleur maîtresse |
| Accent / fidélité / badges | `pink` | `#FFC5DF` | Rose pastel |
| Texte / structure | `black` | `#000000` | Pur noir |
| Fond chaud / surfaces | `cream` | `#FFF3ED` | Crème rosé, sert de `background` |
| Fond clair / cartes | `white` | `#FFFFFF` | — |

Les scales Tailwind (50 → 900 pour `teal`, 50 → 700 pour `pink`) sont définies
dans `apps/web/tailwind.config.ts` et `apps/site/tailwind.config.ts`.

### Règles d'application

- **Actions principales** (boutons CTA, Encaisser, Se connecter…) : fond `teal` + texte blanc
- **Actions secondaires** : bordure `teal`, texte `teal`, fond blanc
- **Accents doux** (labels fidélité, tags) : fond `pink-100` ou `pink-200`, texte `pink-700`
- **Fonds d'écran** : `cream` sur le site public et le back-office
- **Messages d'erreur** : `red-500 / red-600` (hors charte mais essentiel UX)

## 2. Typographie

| Rôle | Famille | Poids usuels | Source |
|---|---|---|---|
| Titres / display | **Lexend Mega** | 400, 500, 600, 700 | Google Fonts |
| Corps de texte | **Poppins** | 300, 400, 500, 600, 700 | Google Fonts |

### Chargement

Via `next/font/google` dans `apps/{web,site}/src/app/layout.tsx` — variables
CSS injectées sur `<html>` :

- `--font-display` → titres (classe Tailwind `font-display`)
- `--font-body` → texte (classe Tailwind `font-sans`, appliquée sur `<body>`)

Aucun appel externe à `fonts.googleapis.com` en runtime : les fichiers sont
self-hosted par Next via l'optimiseur de polices.

### Règles d'application

- H1 / hero : `font-display` + `tracking-wider` + `uppercase`
- H2 / H3 : `font-display` (cas par cas l'uppercase)
- Paragraphes, labels, boutons : `font-sans` (Poppins)
- **Ne pas** utiliser Playfair / Inter / Georgia / system-ui — ces familles
  ne font plus partie de la charte.

## 3. Logos

Les fichiers sont dans `assets/branding/` (source) et copiés dans les
dossiers publics des apps pour servir via le CDN.

| Fichier (public) | Usage |
|---|---|
| `logo-teal.png` | Monogramme VL teal sur fond transparent — **logo par défaut** (navbar, login, sidebar, landing, favicon) |
| `logo-rose.png` | Monogramme VL rose sur fond transparent — fond sombre (footer noir) |
| `lettrage-noir.png` | Mot « VINTIZ » en noir — factures, emails, ticket secondaire |
| `lettrage-rose.png` | Mot « VINTIZ » en rose — supports roses |
| `receipt-logo.png` | Version ticket de caisse (impression thermique, forcée en pur noir via CSS filter) |

### Règles d'application

- **Fond clair / crème / blanc** → `logo-teal.png`
- **Fond teal** (carte, footer teal) → `logo-rose.png` inversé ou monogramme blanc
- **Fond noir** (footer sombre) → `logo-rose.png`
- **Fond rose** (bannières, badges) → monogramme noir
- Toujours conserver un **quiet zone** d'au moins 1× la hauteur du logo autour
- **Ne jamais déformer** (pas de stretch, pas de rotation, pas d'ombre)
- **Taille minimale** affichée : 24 px de hauteur

## 4. Moodboard (inspiration)

- Retail premium rose pastel / arches / miroirs
- Mobilier rose poudré, touches teal profond
- Dressing visible type Muji / Aesop avec mise en scène individuelle de chaque pièce
- Éclairage chaud, bois clair, détails dorés interdits (reste en noir/blanc/teal/rose)

## 5. Check-list pour toute nouvelle page / composant

- [ ] Fond : `bg-cream` (ou `bg-background`) pour les pages, `bg-white` pour les cartes
- [ ] Titres : `font-display` + couleurs `text-black` ou `text-teal`
- [ ] Texte : `font-sans` (hérité du `<body>`)
- [ ] Boutons primaires : `bg-teal text-white`
- [ ] Boutons secondaires : `border border-teal text-teal bg-white`
- [ ] Accents fidélité / tags : `bg-pink-100 text-pink-700`
- [ ] Logo dans le header de la page → `/logo-teal.png`
- [ ] Touch target mini 44 px (`min-h-[44px]` / `min-w-[44px]`)

## 6. Historique

| Version | Date | Résumé |
|---|---|---|
| v1 | 2026-03 | Palette provisoire (teal `#2A8B8B`, pink `#E8B4D0`, bg `#FFF5F8`, fonts Inter/Playfair) |
| **v2** | **2026-04** | Charte définitive (teal `#008678`, pink `#FFC5DF`, cream `#FFF3ED`, Lexend Mega + Poppins, monogramme VL officiel) |
