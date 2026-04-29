# Vintiz — Design System v3 « Sauge Néo » (2026-04)

Charte graphique officielle. Toute évolution visuelle doit respecter ce
document.

## 1. Identité « Sauge Néo »

Refonte 2026-04 — direction retenue après exploration de 4 variantes.
Palette **Néo** (off-white frais, teal vif, magenta éditorial) appliquée au
traitement **Sauge** (typographie Fraunces + Manrope, mises en page de
documentation).

Le rose pastel v2 est remplacé par un **magenta éditorial** réservé aux
moments de célébration (anniversaire fidélité, offre exclusive). La couleur
primaire identitaire reste le **teal**, plus vif qu'en v2. Fraunces apporte
une chaleur de magazine indépendant ; Manrope structure les UIs denses du
backend.

Cible primaire : **Sophie**, 35-55, cadre, fidèle, mobile-first.
Cible secondaire récupérée : **18-30**, énergie contemporaine sans virer Vinted.
Le backend boutique est nettement plus utilitaire que le front (Linear-like).

## 2. Palette

| Rôle | Token Tailwind | Hex | Usage |
|---|---|---|---|
| Fond principal | `vz-bg` | `#F6F5F1` | Off-white frais, légèrement froid |
| Fond secondaire | `vz-bg-alt` | `#ECEAE3` | Sidebar backend, sections alternées |
| Surface | `vz-surface` | `#FFFFFF` | Cards, modales, inputs |
| Texte principal | `vz-ink` | `#0E0E0C` | Quasi-noir froid |
| Texte secondaire | `vz-ink-soft` | `#4A4A47` | Léges, paragraphes long |
| Texte mute | `vz-ink-mute` | `#8B8B86` | Méta, labels, hints |
| Bordures | `vz-line` | `#D5D3CC` | Séparateurs, inputs |
| Primaire | `vz-teal` | `#0B7A6A` | **CTA, liens, accent fidélité** |
| Primaire pressé | `vz-teal-deep` | `#054238` | Hover/active teal |
| Tag teal | `vz-teal-soft` | `#CDE5DF` | Backgrounds chips/badges teal |
| Accent | `vz-accent` | `#E84E8B` | **Magenta éditorial — célébration uniquement** |
| Accent doux | `vz-accent-soft` | `#FFD5E5` | Background offre encartée |
| Tier rare | `vz-gold` | `#8E7B57` | Tier fidélité haut de gamme (rare) |

### Mode sombre (backend uniquement)

Activé via `[data-theme="dark"]` ou `.dark` sur `<html>` ou conteneur.

| Token | Hex sombre |
|---|---|
| `vz-bg` | `#0F100E` |
| `vz-bg-alt` | `#171814` |
| `vz-surface` | `#1A1B17` |
| `vz-ink` | `#F0EFEA` |
| `vz-ink-soft` | `#A5A49E` |
| `vz-ink-mute` | `#65645F` |
| `vz-line` | `#262722` |
| `vz-teal` | `#1FA790` (versionnage clair pour contraste) |
| `vz-accent` | `#FF6FA0` |

### Règles d'application

- **CTA primaire** : `bg-vz-teal text-white hover:bg-vz-teal-deep`
- **CTA secondaire** : `bg-vz-surface text-vz-ink border border-vz-ink`
- **CTA tertiaire** (mute) : `bg-transparent text-vz-ink-soft hover:bg-vz-bg-alt`
- **Chips/badges teal** : `bg-vz-teal-soft text-vz-teal-deep`
- **Badges fidélité (anniversaire, célébration)** : `bg-vz-accent-soft text-vz-accent`
- **Offre encartée** (anniversaire, promo) : `bg-vz-accent-soft border border-dashed border-vz-accent`
- **Fond de page** : `bg-vz-bg`
- **Sidebar backend** : `bg-vz-bg-alt`

## 3. Typographie

| Rôle | Famille | Variable CSS | Classe Tailwind | Source |
|---|---|---|---|---|
| Titres / display | **Fraunces** | `--vz-font-display` | `font-display` | Google Fonts |
| Corps de texte | **Manrope** | `--vz-font-body` | `font-body` (et `font-sans`) | Google Fonts |
| Numéros / codes | **JetBrains Mono** | `--vz-font-mono` | `font-mono` | Google Fonts |

### Chargement

Variable CSS importée en tête de `apps/{web,site}/src/app/globals.css` via
`@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,450;9..144,500&family=Manrope:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap')`.

### Échelle (mobile / desktop)

| Rôle | Tailwind preset | Mobile | Desktop |
|---|---|---|---|
| Hero display | `text-vz-hero` | 38px | 64px (weight 450, letter-spacing -0.015em) |
| H1 | `text-vz-h1` | 28px | 40px (weight 500, letter-spacing -0.01em) |
| H2 | `text-vz-h2` | 22px | 28px (weight 500) |
| Body | `text-vz-body` (ou base) | 14px | 16px (line-height 1.55) |
| Caption | `text-vz-meta` | 11px (letter-spacing 0.12em, uppercase, `text-vz-ink-mute`) | — |
| Mono | `font-mono` | 11–13px |

### Règles d'application

- **Hero / H1** : `font-display font-[450] tracking-[-0.015em]`
- **H2 / titres section** : `font-display font-medium`
- **Caption / labels** : `font-body uppercase tracking-[0.12em] text-[11px] text-vz-ink-mute`
- **Numéros (CA, points fidélité, codes promo)** : `font-display` pour les gros chiffres, `font-mono` pour les codes
- **Paragraphes** : `font-body` (hérité du `<body>`)
- **Ne pas** utiliser Lexend Mega / Poppins / Inter / Playfair / Georgia / system-ui — ces familles ne font plus partie de la charte.

## 4. Radius & ombres

| Token | Valeur | Usage |
|---|---|---|
| `rounded-vz` | 8px | Boutons, inputs, chips |
| `rounded-vz-lg` | 16px | Cards, modales |
| `rounded-full` | 999px | Badges, tags pill |
| `shadow-vz-soft` | `0 1px 0 rgba(14,14,12,.04), 0 16px 40px -20px rgba(14,14,12,.16)` | Cartes élevées |

## 5. Composants shadcn

| Composant | Variantes | Tokens clés |
|---|---|---|
| `Button` | `primary` (teal), `secondary` (border ink), `outline` (border line), `ghost`, `danger` | `bg-vz-teal`, `border-vz-ink`, `text-vz-ink-soft` |
| `Card` | `default`, `elevated` (shadow), `bordered`, `teal`, `accent` (offre encartée) | `bg-vz-surface`, `border-vz-line`, `shadow-vz-soft`, `border-dashed border-vz-accent` |
| `Badge` | `default`, `loyalty` (rose accent), `tag` (teal soft), `zone` (transparent), `stock`, `display`, `sold`, `returned` | `bg-vz-accent-soft text-vz-accent`, `bg-vz-teal-soft text-vz-teal-deep` |
| `Input` | — | `rounded-vz`, `border-vz-line`, `bg-vz-surface`, label en caption uppercase |

## 6. Logos

Les fichiers sont dans `apps/{web,site}/public/`.

| Fichier (public) | Usage |
|---|---|
| `logo-teal.png` | Monogramme VZ teal `#0B7A6A` — **logo par défaut** (navbar, login, sidebar, landing, favicon) |
| `logo-rose.png` | Monogramme VZ rose magenta `#E84E8B` — fond sombre (footer noir) — **à régénérer dans la nouvelle teinte (était `#FFC5DF` en v2)** |
| `lettrage-noir.png` | Mot « VINTIZ » en noir — factures, emails, ticket secondaire |
| `lettrage-rose.png` | Mot « VINTIZ » en rose magenta — supports célébration |
| `receipt-logo.png` | Version ticket de caisse (impression thermique, forcée en pur noir via CSS filter) |

### Règles d'application

- **Fond clair / off-white / blanc** → `logo-teal.png`
- **Fond teal** (carte, footer teal) → monogramme blanc ou `logo-rose.png` selon le ton
- **Fond noir** (footer sombre) → `logo-rose.png`
- Toujours conserver un **quiet zone** d'au moins 1× la hauteur du logo autour
- **Ne jamais déformer** (pas de stretch, pas de rotation, pas d'ombre)
- **Taille minimale** affichée : 24 px de hauteur

## 7. Check-list pour toute nouvelle page / composant

- [ ] Fond : `bg-vz-bg` pour les pages, `bg-vz-surface` pour les cartes
- [ ] Titres hero : `font-display font-[450] tracking-[-0.015em] text-vz-ink`
- [ ] Texte : `font-body` (hérité du `<body>`)
- [ ] CTA primaire : `bg-vz-teal text-white`
- [ ] CTA secondaire : `bg-vz-surface text-vz-ink border border-vz-ink`
- [ ] Caption / eyebrow : `text-[11px] uppercase tracking-[0.12em] text-vz-ink-mute`
- [ ] Accent magenta réservé aux **célébrations** (anniversaire, offre exclusive, encart)
- [ ] Logo dans le header → `/logo-teal.png`
- [ ] Touch target mini 44 px (`min-h-[44px]` / `min-w-[44px]`)
- [ ] Mode sombre testé pour les écrans backend (`data-theme="dark"`)

## 8. Pages référence (prototypes)

Direction visuelle figée par les prototypes du `design-package/handoff/` :

| Page | Référence prototype |
|---|---|
| `apps/site/src/app/page.tsx` (landing publique) | `LandingSauge` |
| `apps/site/src/app/account/page.tsx` (espace client) | `AccountSauge` |
| `apps/web/src/app/dashboard/cahier-du-jour/page.tsx` (cahier de travail) | `CahierSauge` |
| `apps/web/src/app/ia/page.tsx` (compagnon IA) | `IaSauge` |

## 9. Historique

| Version | Date | Résumé |
|---|---|---|
| v1 | 2026-03 | Palette provisoire (teal `#2A8B8B`, pink `#E8B4D0`, bg `#FFF5F8`, fonts Inter/Playfair) |
| v2 | 2026-04 | Charte (teal `#008678`, pink `#FFC5DF`, cream `#FFF3ED`, Lexend Mega + Poppins, monogramme VL) |
| **v3** | **2026-04** | **Sauge Néo** — palette off-white `#F6F5F1` + teal `#0B7A6A` + magenta éditorial `#E84E8B`, Fraunces + Manrope + JetBrains Mono, monogramme VZ |
