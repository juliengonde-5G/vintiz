# Mise en place Matomo — mesure d'audience exemptée (accompagnement)

Guide opérationnel pour activer la mesure d'audience Vintiz **sans bandeau de
consentement**, en conformité avec les critères d'exemption de la CNIL. Le code
est déjà prêt (`apps/site/src/components/Analytics.tsx`) : il ne reste qu'à
provisionner l'instance et renseigner 2 variables.

> Contexte réglementaire : voir `docs/COMPLIANCE_TRACKING_PIXELS_2026.md`.
> GA4 n'est **jamais** exempté par la CNIL ; Matomo **cookieless** correctement
> configuré l'est → pas de consentement requis, pas de bandeau.

---

## 1. Choisir l'hébergement

| Option | Pour qui | Coût indicatif | Localisation données |
|---|---|---|---|
| **Matomo Cloud** (matomo.org) | Le plus simple, zéro serveur à gérer | ~19-29 €/mois | **UE** (choisir hébergement Allemagne) |
| **Matomo self-hosted** | Maîtrise totale, gratuit (logiciel) | Coût du VPS | Là où vous l'installez |

Recommandation Vintiz : **Matomo Cloud (région UE)** — pas de maintenance, et
l'hébergement UE simplifie la conformité (pas de transfert hors UE, contrairement
à GA4). Si vous préférez tout garder sur le VPS existant (déjà Caddy + Docker),
le self-hosted est viable — voir §5.

---

## 2. Régler l'instance en « mesure d'audience exemptée » (OBLIGATOIRE)

L'exemption de consentement CNIL n'est valable **que si** l'instance respecte la
grille. À faire dans l'admin Matomo (**Administration → Confidentialité**) :

- [ ] **Anonymiser les adresses IP** : masquer **au moins 2 octets** (idéalement
      3). *Confidentialité → Anonymiser les données → Anonymiser IP.*
- [ ] **Désactiver les cookies** : déjà fait **côté code** (`disableCookies` dans
      `Analytics.tsx`). Vérifier qu'aucun réglage serveur ne les réactive.
- [ ] **Pas de partage des données** : ne pas activer le partage avec d'autres
      sites / la « vue cross-site » ; désactiver toute intégration publicitaire.
- [ ] **Respecter Do Not Track** : laisser activé.
- [ ] **Ne pas activer** les fonctions qui sortent de la simple mesure : Heatmaps,
      Session Recording, A/B testing, Analytics comportemental individuel,
      User ID cross-device → **désactivés** (ils font retomber dans le régime du
      consentement).
- [ ] **Durée de conservation** : purge automatique des logs bruts (ex. 13-14
      mois max, cohérent avec la politique de confidentialité qui annonce
      « mesure d'audience : 14 mois »). *Administration → Confidentialité →
      Anonymiser progressivement / Supprimer les anciens rapports.*
- [ ] **Opt-out** : Matomo fournit un iframe/lien d'opposition ; l'ajouter à la
      page `/confidentialite` (voir §4, optionnel mais recommandé par la CNIL).

> Ces réglages correspondent aux 5 objectifs / 14 critères CNIL (grille de
> juillet 2025, en vigueur depuis le 01/01/2026). Sans eux, l'exemption tombe et
> il faudrait rebrancher le bandeau (le code GA4/bandeau reste dispo pour ce cas).

---

## 3. Renseigner les 2 variables et déployer

Dans le fichier d'environnement de prod (`.env` du site, cf.
`.env.production.template`) :

```env
NEXT_PUBLIC_MATOMO_URL=https://VOTRE-INSTANCE.matomo.cloud/   # slash final toléré
NEXT_PUBLIC_MATOMO_SITE_ID=1                                  # idSite du site Vintiz
```

- `NEXT_PUBLIC_MATOMO_URL` = l'URL de base de l'instance (Cloud :
  `https://vintiz.matomo.cloud/`, self-hosted : `https://analytics.vintiz.fr/`).
- `NEXT_PUBLIC_MATOMO_SITE_ID` = l'**idSite** affiché dans Matomo
  (*Administration → Sites web / Mesurés*) pour le domaine `vintiz.fr`.

Puis **rebuild + redéploiement** du site (`apps/site`). En prod Vintiz, un push
sur `main` déclenche la GitHub Action de déploiement.

> Laisser `NEXT_PUBLIC_GA_ID` **vide** : GA4 reste désactivé (recommandé). Tant
> qu'il est vide, aucun bandeau cookies ne s'affiche.

---

## 4. (Recommandé) Lien d'opposition sur la page confidentialité

La CNIL apprécie un moyen de s'opposer même pour la mesure exemptée. Matomo
génère un extrait `<iframe>` d'opt-out (*Administration → Confidentialité →
Fonctionnalité de désinscription des utilisateurs*). On peut l'ajouter à
`apps/site/src/app/confidentialite/page.tsx`, section « Cookies et mesure
d'audience ». Dis-moi si tu veux que je l'intègre (petit dev front, ~10 min).

---

## 5. Variante self-hosted (VPS existant)

Si tu héberges Matomo sur le VPS Vintiz (déjà Docker + Caddy) :

1. Ajouter un service `matomo` + une base (MySQL/MariaDB) au
   `docker/docker-compose.prod.yml`.
2. Exposer `analytics.vintiz.fr` via Caddy (HTTPS auto).
3. Faire l'assistant d'installation Matomo, créer le site `vintiz.fr` → idSite.
4. Appliquer **toute** la checklist §2.
5. Renseigner les variables §3 avec `https://analytics.vintiz.fr/`.

Je peux préparer ce bloc `docker-compose` + Caddyfile si tu choisis cette voie.

---

## 6. Vérification post-déploiement

- [ ] Ouvrir `vintiz.fr`, onglet réseau du navigateur : une requête
      `matomo.php` part vers l'instance, **aucun cookie `_pk_*`** n'est déposé
      (mode cookieless), **aucun bandeau** ne s'affiche (GA4 vide).
- [ ] Dans Matomo → *Visiteurs → en temps réel* : la visite remonte.
- [ ] Naviguer entre 2 pages : Matomo enregistre bien **2 pages vues** (le suivi
      de route SPA est géré par `Analytics.tsx`).
- [ ] Vérifier dans *Confidentialité* que l'IP affichée est bien tronquée.

---

## 7. Ce qu'il reste à décider (avec le DPO)

- Choix hébergement (Cloud UE vs self-hosted).
- Durée de conservation exacte (aligner avec la politique : 14 mois).
- Intégrer ou non l'iframe d'opt-out (§4).

Une fois l'instance créée et la checklist §2 cochée, l'activation se résume aux
2 variables (§3) — je peux t'accompagner pas à pas au moment du déploiement.
