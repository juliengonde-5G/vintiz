# Vintiz Design Package

Charte graphique exportable de la boutique Vintiz Vernon (charte v2 — 2026-04).
Dossier autoporteur : tokens, polices, logos et composants React standalone
réutilisables hors monorepo (autres apps, prototypes, Claude Artifacts).

## Contenu

```
design-package/
├── README.md                          # ce fichier
├── package.json                       # @vintiz/design-package, peerDeps react + tailwind
├── tokens/
│   ├── colors.json                    # palette teal / pink / cream + variantes
│   ├── typography.json                # Lexend Mega + Poppins + scale
│   ├── spacing.json                   # échelle Tailwind utilisée
│   ├── radii.json                     # rounded-xl / 2xl / full
│   └── tailwind.config.preset.js      # preset importable
├── fonts/
│   └── google-fonts.css               # @import drop-in (sans next/font)
├── logos/
│   ├── logo-teal.png                  # monogramme VL — usage par défaut
│   ├── logo-rose.png                  # monogramme rose — fonds sombres
│   ├── lettrage-noir.png              # mot « VINTIZ » noir
│   └── lettrage-rose.png              # mot « VINTIZ » rose
├── components/
│   ├── WalletCard.tsx                 # carte fidélité virtuelle
│   ├── AccountNav.tsx                 # side nav espace client (drawer mobile)
│   ├── OfferTile.tsx                  # tuile coupon
│   ├── HistoryItem.tsx                # ligne d'historique transaction
│   └── ReceiptFooter.tsx              # footer fidélité ticket de caisse
└── examples/
    └── account-overview.html          # preview HTML autonome
```

## Charte couleurs

| Token | Hex | Usage |
|---|---|---|
| `teal` | `#008678` | Couleur signature : CTA, liens, en-têtes carte |
| `pink` | `#FFC5DF` | Accent : badges, fidélité, célébrations |
| `cream` | `#FFF3ED` | Fond chaud par défaut |
| `black` | `#000000` | Texte structurel |
| `white` | `#FFFFFF` | Cartes, surfaces |

Les nuances `teal-50…700` et `pink-50…700` sont disponibles pour les états
hover, désactivés et fonds subtils — voir `tokens/colors.json`.

## Typographie

- **Lexend Mega** (display) — titres, hero, n° de carte. Poids 400-700.
- **Poppins** (body) — corps de texte, UI, labels. Poids 300-700.

Les deux sont chargées en CSS variables `--font-display` et `--font-body`
(via `next/font` ou `@import` Google Fonts).

## Utilisation dans une app Next.js + Tailwind

```ts
// tailwind.config.ts
import type { Config } from "tailwindcss";
// @ts-expect-error preset is plain JS
import vintizPreset from "@vintiz/design-package/tokens/tailwind.config.preset.js";

const config: Config = {
  presets: [vintizPreset],
  content: ["./src/**/*.{ts,tsx}"],
};
export default config;
```

```tsx
// app/layout.tsx — chargement des fontes côté Next.js
import { Lexend_Mega, Poppins } from "next/font/google";

const lexend = Lexend_Mega({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-display",
});
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-body",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${lexend.variable} ${poppins.variable}`}>
      <body>{children}</body>
    </html>
  );
}
```

## Utilisation dans un projet sans next/font

Inclure `fonts/google-fonts.css` dans le HTML :

```html
<link rel="stylesheet" href="./design-package/fonts/google-fonts.css" />
```

Le fichier déclare les variables `--font-display` et `--font-body` sur `:root`,
consommées par le preset Tailwind.

## Composants React

Tous les composants sont en React 18+ TypeScript, dépendent uniquement de
Tailwind CSS et n'utilisent pas de routeur (pour `AccountNav`, le composant
`linkAs` permet d'injecter le `Link` du framework hôte).

```tsx
import { WalletCard } from "@vintiz/design-package/components/WalletCard";
import { OfferTile } from "@vintiz/design-package/components/OfferTile";
import { ReceiptFooter } from "@vintiz/design-package/components/ReceiptFooter";

<WalletCard holderName="Alice Martin" membershipNumber="V482931" points={120} />

<OfferTile
  code="ANNIV-AB12CD"
  discountType="amount"
  discountValue={10}
  validUntil="2026-12-31"
  source="anniversary"
/>

<ReceiptFooter
  variant="member"
  totalTtc={42.0}
  firstName="Alice"
  lastName="Martin"
  membershipNumber="V482931"
  pointsBalance={162}
  pointsEarned={42}
/>
```

## Preview HTML

Le fichier `examples/account-overview.html` est un fichier HTML statique qui
charge Tailwind via CDN et reproduit la mise en page de l'espace client. Ouvrir
dans un navigateur pour vérifier le rendu sans avoir à installer le projet :

```bash
open design-package/examples/account-overview.html
```

## Génération automatisée

Le script `scripts/export_design_package.sh` à la racine du monorepo
synchronise ce dossier depuis les sources (logos `apps/site/public/*.png`,
extraits du `tailwind.config.ts` du site). Lancer après une modification de la
charte pour propager les changements.

```bash
./scripts/export_design_package.sh
```

## Liens utiles

- Charte complète : `docs/DESIGN_SYSTEM.md`
- Source d'origine du Tailwind config : `apps/site/tailwind.config.ts`
- Composants intégrés (avec deps Next.js) : `apps/site/src/components/`
