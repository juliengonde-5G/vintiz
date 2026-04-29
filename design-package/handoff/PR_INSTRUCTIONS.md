# PR : Migration Charte v2 → v3 « Sauge Néo »

## Branche

```bash
git checkout -b design/charte-v3-sauge-neo
```

## Étapes

### 1. Tokens design (`design-package/`)

```bash
# Remplacer les tokens v2
cp handoff/tokens-sauge-neo.json design-package/tokens/colors.json
cp handoff/tailwind.preset.ts design-package/tailwind.preset.ts
```

Mettre à jour `design-package/tokens/typography.json` :
- Display : `Fraunces` (fallback `Cormorant Garamond`)
- Body : `Manrope` (fallback `Söhne`, `system-ui`)
- Mono : `JetBrains Mono`

### 2. Variables CSS (`apps/web/app/globals.css` et `apps/site/app/globals.css`)

En tête de chaque fichier :
```css
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,450;9..144,500&family=Manrope:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

Puis copier le contenu de `handoff/tokens.css` (variables `:root` + `[data-theme="dark"]`).

Supprimer les variables v2 (Lexend Mega, anciens tokens teal/rose).

### 3. Tailwind configs

Dans `apps/web/tailwind.config.ts` et `apps/site/tailwind.config.ts` :
```ts
import vintizPreset from '../../design-package/tailwind.preset';

export default {
  presets: [vintizPreset],
  content: [...],
  // ... reste de la config
} satisfies Config;
```

### 4. Components shadcn

Composants à revoir dans `apps/web/components/ui/` et `apps/site/components/ui/` :
- `button.tsx` — variantes `default` (teal), `secondary`, `outline`, `ghost`, `destructive`
- `card.tsx` — radius `vz-lg`, shadow `vz-soft`, border `line`
- `badge.tsx` — ajouter variantes `loyalty` (rose), `tag` (teal soft), `zone` (transparent)
- `input.tsx` — radius `vz`, border `line`
- `tabs.tsx` — underline style avec border-bottom `ink` actif

### 5. Pages à mettre à jour

| Page | Référence prototype |
|---|---|
| `apps/site/app/page.tsx` | `prototypes/page-frontend.jsx` → `LandingSauge` |
| `apps/site/app/account/page.tsx` | `prototypes/page-frontend.jsx` → `AccountSauge` |
| `apps/web/app/dashboard/cahier-du-jour/page.tsx` | `prototypes/page-backend.jsx` → `CahierSauge` |
| `apps/web/app/ia/page.tsx` | `prototypes/page-backend.jsx` → `IaSauge` |

### 6. Recherche & remplacement

```bash
# Couleurs v2 à débusquer
rg -i "lexend|poppins|#006A5A|#F4C9D6|rose-50[0-9]|pink-[0-9]" apps/ design-package/

# Préfixes Tailwind à migrer
# bg-rose-*  → bg-vz-accent (uniquement pour célébration), sinon supprimer
# text-pink-* → text-vz-accent
# bg-teal-600 → bg-vz-teal
# font-lexend → font-display
```

### 7. Documentation

Mettre à jour `docs/DESIGN_SYSTEM.md` :
- Section 1 (Identité) : remplacer description v2 par v3 « Sauge Néo »
- Section 2 (Couleurs) : table avec les 13 tokens
- Section 3 (Typographie) : Fraunces + Manrope + JetBrains Mono
- Section 4 (Composants) : noter les nouvelles variantes Badge

Mettre à jour `docs/UX_DESIGN.md` :
- Mentionner que le rose pastel v2 est remplacé par un magenta éditorial réservé aux moments de célébration

### 8. Logos

```bash
# Régénérer le logo rose dans la nouvelle teinte magenta
# (ou demander au designer un export en #E84E8B)
# Conserver design-package/logos/logo-teal.png et lettrage-noir.png tels quels
```

### 9. Tests visuels

```bash
pnpm --filter @vintiz/web dev
pnpm --filter @vintiz/site dev
# Vérifier sur les 4 pages référencées + dark mode backend
```

### 10. Commit & PR

```bash
git add -A
git commit -m "design: migrate to charte v3 (Sauge Néo)

- New palette: off-white #F6F5F1 / teal #0B7A6A / magenta #E84E8B
- New typography: Fraunces (display) + Manrope (body) + JetBrains Mono
- Replaces v2 (Lexend Mega + Poppins + teal #006A5A + rose pastel)
- Logo VZ + lettrage VINTIZ conservés
- Magenta réservé aux célébrations (anniversaire fidélité, exclu)

Refs: design exploration https://claude.site/.../vintiz-charte-v3"

git push -u origin design/charte-v3-sauge-neo
gh pr create --title "Charte v3 · Sauge Néo" --body-file handoff/README.md
```

## Checklist QA

- [ ] Lighthouse > 90 sur les 4 pages
- [ ] Mode sombre backend OK (Cahier + IA)
- [ ] Contraste AAA sur teal `#0B7A6A` sur `#F6F5F1` (ratio 5.5+)
- [ ] Contraste AA sur accent `#E84E8B` sur `#FFD5E5` (badges)
- [ ] Mobile 375px : landing + account fonctionnent
- [ ] Tablette 1024×768 : Cahier + IA OK
- [ ] Print Ticket caisse 80mm pas cassé (faire un dump)
- [ ] Pas de `font-lexend` ni `bg-pink-*` qui traîne
- [ ] Le composant `AccountNav.tsx` (existant dans `design-package/components/`) utilise les nouveaux tokens
