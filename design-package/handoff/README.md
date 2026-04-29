# Handoff: Vintiz — Charte v3 « Sauge Néo »

## Overview

Refonte de la charte graphique Vintiz pour les 3 espaces de l'app (site public `vintiz.fr`, espace client `/account`, backend boutique). Direction retenue après exploration de 4 variantes : **Sauge Néo** — palette Néo (off-white frais, teal vif, rose magenta) appliquée au traitement Sauge (typographie Fraunces + Manrope, mises en page de documentation).

## About the Design Files

Les fichiers livrés dans ce bundle sont des **références de design créées en HTML** — des prototypes qui montrent l'apparence et le comportement visés. Ce ne sont pas des fichiers de production à copier-coller dans le repo.

La mission est de **recréer cette charte dans l'environnement existant du repo `juliengonde-5G/vintiz`** (Next.js + Tailwind + shadcn/ui d'après la lecture des `.tsx` du `design-package`), en respectant les patterns établis (App Router, components shadcn, Tailwind tokens, `cn()` helper).

La charte v2 (Lexend Mega + Poppins, teal #006A5A + rose pastel #F4C9D6) est **remplacée**. Le logo VZ + le lettrage VINTIZ sont **conservés**.

## Fidelity

**Hi-fi.** Couleurs exactes (hex), typographie finale (Fraunces + Manrope + JetBrains Mono), spacing et border-radius définis. Les mockups (3 directions × landing/account/cahier/IA) montrent l'intention pixel-near. Implémentation pixel-perfect attendue, mais avec les composants shadcn existants — ne pas dupliquer la structure DOM exacte des HTML, ré-exprimer les tokens dans Tailwind.

## Direction « Sauge Néo » — ADN

Le rose de la v2 revient, mais transformé : ce n'est plus un rose pastel féminin de remplissage, c'est un **magenta éditorial** qui signe (anniversaire fidélité, célébration, offre exclusive). La couleur primaire identitaire reste le **teal**, plus vif qu'en v2. La typographie Fraunces apporte une chaleur de magazine indépendant ; Manrope structure les UIs denses du backend.

- Cible primaire conservée : **Sophie**, 35-55, cadre, fidèle, mobile-first.
- Cible secondaire récupérée : **18-30**, énergie contemporaine sans virer Vinted.
- Backend boutique nettement plus utilitaire que le front (Linear-like).

## Design Tokens

### Couleurs

| Rôle | Hex | Usage |
|---|---|---|
| `bg` | `#F6F5F1` | Fond principal — off-white frais, légèrement froid |
| `bg-alt` | `#ECEAE3` | Fond secondaire (sidebar backend, sections alternées) |
| `surface` | `#FFFFFF` | Cards, modales, inputs |
| `ink` | `#0E0E0C` | Texte principal — quasi-noir froid |
| `ink-soft` | `#4A4A47` | Texte secondaire |
| `ink-mute` | `#8B8B86` | Méta, labels, hints |
| `line` | `#D5D3CC` | Bordures, séparateurs |
| `teal` | `#0B7A6A` | **Couleur primaire** — CTA, liens, accent fidélité |
| `teal-deep` | `#054238` | Hover/pressed teal |
| `teal-soft` | `#CDE5DF` | Backgrounds de chips/badges teal |
| `accent` | `#E84E8B` | **Magenta éditorial** — célébration, anniversaire, exclusivités |
| `accent-soft` | `#FFD5E5` | Background accent (offre encartée) |
| `gold` | `#8E7B57` | Tier fidélité haut de gamme (rare) |

### Mode sombre (backend uniquement)

| Rôle | Hex |
|---|---|
| `bg` | `#0F100E` |
| `bg-alt` | `#171814` |
| `surface` | `#1A1B17` |
| `ink` | `#F0EFEA` |
| `ink-soft` | `#A5A49E` |
| `ink-mute` | `#65645F` |
| `line` | `#262722` |
| `teal` | `#1FA790` (versionnage clair pour contraste) |
| `accent` | `#FF6FA0` |

### Typographie

```
Display    Fraunces, opsz 9-144, weights 400/450/500
Body       Manrope, weights 300/400/500/600/700
Mono       JetBrains Mono, weights 400/500
```

Stack complète :
```css
--font-display: "Fraunces", "Söhne Breit", "Cormorant Garamond", serif;
--font-body: "Manrope", "Söhne", system-ui, sans-serif;
--font-mono: "JetBrains Mono", ui-monospace, monospace;
```

Échelle (mobile / desktop) :
- Hero display: 38px / 64px, weight 450, letter-spacing -0.015em
- H1: 28px / 40px, weight 500
- H2: 22px / 28px, weight 500
- Body: 14px / 16px, line-height 1.55
- Caption / label: 11px, letter-spacing 0.12em, uppercase, color `ink-mute`
- Mono (numéros, codes, références): 11–13px

### Radius
- `sm`: 8px (boutons, inputs, chips)
- `lg`: 16px (cards, modales)
- `pill`: 999px (badges, tags)

### Shadow
- `shadow-soft`: `0 1px 0 rgba(14,14,12,0.04), 0 16px 40px -20px rgba(14,14,12,0.16)`

### Spacing
Échelle Tailwind standard (4px). Unités principales utilisées : 4 / 8 / 12 / 16 / 20 / 24 / 32 / 48 / 64.

## Files in this bundle

```
handoff/
├── README.md                          ← ce fichier
├── tokens.css                         ← variables CSS prêtes à l'emploi
├── tailwind.preset.ts                 ← preset Tailwind à étendre
├── tokens-sauge-neo.json              ← tokens design (W3C format)
├── prototypes/
│   ├── Vintiz Charte v3.html          ← les 4 directions + 3 onglets
│   ├── tokens.js                      ← définitions JS des 4 directions
│   ├── styles-base.css
│   ├── styles-screens.css
│   ├── page-charte.jsx
│   ├── page-frontend.jsx
│   ├── page-backend.jsx
│   ├── app.jsx
│   └── assets/                        ← logos VZ
└── PR_INSTRUCTIONS.md                 ← steps pour la PR
```

## Screens à recréer

### 1. Landing publique — `apps/site/app/page.tsx` (vintiz.fr)
- Hero : eyebrow `meta mono` + titre Fraunces 64px + lede Manrope + CTA teal pill
- Bandeau de stats sur séparateurs verticaux (3 chiffres clés)
- Grille de pièces en `surface` + bordures `line`
- Référence : `prototypes/page-frontend.jsx` → `LandingSauge`

### 2. Espace client — `apps/site/app/account/page.tsx`
- Card fidélité `surface` avec gros chiffre teal Fraunces 40px
- Tabs `Récompenses / Offres / Historique`
- Offre encartée en `accent-soft` avec border dashed `accent`, code en mono
- Référence : `prototypes/page-frontend.jsx` → `AccountSauge`

### 3. Cahier de Travail — `apps/web/app/dashboard/cahier-du-jour/page.tsx`
- Sidebar 200px `bg-alt`, items 11px Manrope avec icône 14px
- Hero CA jour : grand chiffre Fraunces teal + progress bar 4px
- 3 KPI cards en grid
- Sections avec titre Fraunces 14px + body 12px
- Mode sombre via `data-theme="dark"`
- Référence : `prototypes/page-backend.jsx` → `CahierSauge`

### 4. Compagnon IA — `apps/web/app/ia/page.tsx`
- Hero card avec icône 18px teal + titre Fraunces 22px (italique pour le focus mot)
- 3 cards d'actions IA en grid
- CTA mute (`btn-mute`) + primary teal
- Référence : `prototypes/page-backend.jsx` → `IaSauge`

## Components à mettre à jour (shadcn)

| Composant | Changements |
|---|---|
| `Button` | variant `default` → bg teal, variant `secondary` → border ink + bg surface, font-medium 500 |
| `Card` | radius lg (16px), shadow-soft, border line |
| `Badge` | 3 variantes : `loyalty` (rose accent-soft + accent), `tag` (teal-soft + teal-deep), `zone` (transparent + line) |
| `Input` | radius sm, border line, bg surface, label en caption uppercase |
| `Tabs` | underline style, font Manrope, active = ink + border ink |

## Assets

- `assets/logo-teal.png` — logo VZ teal (existe déjà : `design-package/logos/logo-teal.png`)
- `assets/logo-rose.png` — logo VZ rose, à régénérer en `#E84E8B` (ou utiliser SVG monochrome avec `currentColor`)
- Garder le lettrage VINTIZ (`design-package/logos/lettrage-noir.png`)

## Migration de la v2

Fichiers du repo à mettre à jour :
- `apps/web/tailwind.config.ts` — étendre avec `tailwind.preset.ts`
- `apps/site/tailwind.config.ts` — idem
- `apps/web/app/globals.css` — importer `tokens.css`
- `apps/site/app/globals.css` — idem
- `design-package/tokens/colors.json` — remplacer par `tokens-sauge-neo.json`
- `design-package/tokens/typography.json` — Fraunces + Manrope
- `docs/DESIGN_SYSTEM.md` — réécrire la section Charte avec les nouveaux tokens
- Components qui utilisaient `bg-rose-*` ou `text-pink-*` v2 → migrer vers `bg-accent` (le rose magenta n'apparaît plus que pour les célébrations)

Voir `PR_INSTRUCTIONS.md` pour les commandes git suggérées.
