# Conformité — Pixels de suivi & traceurs (juillet 2026)

Réponse à la question : **« Sommes-nous soumis à la réglementation sur les
pixels de suivi ? Si oui, impact et plan d'action. »**

> TL;DR — **Oui, nous sommes soumis** (art. 82 Loi Informatique & Libertés /
> directive ePrivacy). Deux périmètres : **le site web** (Google Analytics 4)
> et **les e-mails marketing** (pixel d'ouverture Brevo). Le web est
> globalement conforme *tel que codé* (consentement préalable), avec 2 lacunes
> mineures. Les **e-mails** sont le vrai point d'attention : la recommandation
> CNIL 2026 assimile le pixel d'ouverture à un cookie et son délai de mise en
> conformité (**14 juillet 2026**) est **dépassé**.

## 1. Ce qui s'applique à nous

- **Art. 82 LIL / ePrivacy** : tout dépôt/lecture d'information sur le terminal
  de l'utilisateur (cookie **ou pixel**) exige un **consentement préalable**,
  sauf exception (strictement nécessaire, ou mesure d'audience « exemptée »).
- **Recommandation CNIL sur les pixels dans les e-mails (2026)** : le pixel qui
  mesure l'ouverture d'un e-mail **marketing** est un traceur soumis au même
  régime que les cookies → **consentement spécifique**, distinct du
  consentement à recevoir les e-mails. Délai d'information des bases existantes
  expiré le **14/07/2026** ; la CNIL a annoncé des contrôles ensuite.
- **Mesure d'audience** : depuis le 01/01/2026, la CNIL a remplacé sa liste
  d'outils exemptés par une **auto-évaluation** (grille 5 objectifs / 14
  critères). **GA4 n'a jamais été exempté** et ne peut pas l'être (la CNIL avait
  mis en demeure d'arrêter GA en 2022). Concrètement : **GA4 impose toujours un
  consentement** (pas d'exemption possible).

## 2. Ce que fait réellement Vintiz aujourd'hui

### a) Site web (`apps/site`) — 1 seul traceur : Google Analytics 4

- **Double verrou** : GA4 ne se charge (i) que si `NEXT_PUBLIC_GA_ID` est posé,
  (ii) **qu'après clic sur « Tout accepter »** dans le bandeau cookies
  (`components/Analytics.tsx`, `components/CookieBanner.tsx`).
- **Consent Mode v2** initialisé à `denied` par défaut (`layout.tsx`) : aucun
  stockage tant que le choix n'est pas fait. IP anonymisée (`anonymize_ip`).
- **Aucun pixel publicitaire / social** (pas de Meta Pixel, TikTok, Hotjar,
  Matomo…). Vérifié sur tout le code.
- État actuel : `NEXT_PUBLIC_GA_ID` **vide** dans les fichiers d'env → GA4 **ne
  tourne pas** en l'état ; c'est un interrupteur à activer en prod.
- **Politique de confidentialité** (`/confidentialite`) à jour, mentionne GA4
  (IP anonymisée, Consent Mode v2, rétention 14 mois), « aucun cookie
  publicitaire ». Cohérent avec le code.

**Verdict web : conforme *tel que codé*.** Le consentement précède le dépôt.

**2 lacunes CNIL à corriger :**
1. **Pas de retrait du consentement** aussi simple que son recueil : une fois
   le choix stocké (`localStorage vintiz_cookie_consent`), aucune UI ne permet
   de revenir dessus (il faut vider le localStorage). La CNIL exige un retrait
   aussi facile que l'acceptation.
2. **GA4 = risque résiduel** : même consenti, GA4 reste l'outil que la CNIL a
   sanctionné (transferts hors UE). Risque juridique non nul.

### b) E-mails (Brevo) — pixel d'ouverture activé par défaut

- Vintiz envoie ses e-mails via **Brevo** (`services/email_gateway.py`,
  `POST /v3/smtp/email`). **Brevo insère par défaut un pixel d'ouverture + des
  liens réécrits** sur tous les envois vers des contacts en France, y compris
  transactionnels. Notre payload ne désactive pas ce suivi → **défaut Brevo
  actif**.
- E-mails **marketing** concernés : alertes tendance (quotidien 11h), digest
  nouvelles pièces (**désactivé ce jour**, cf. `jobs.py`), anniversaires,
  nouveautés. → pixel d'ouverture **soumis à consentement**.
- E-mails **transactionnels / de service** (ticket de caisse, magic-link,
  RGPD…) : messages de service → **hors champ marketing** (le suivi
  individuel y reste néanmoins déconseillé).

**Verdict e-mail : NON conforme en l'état** (suivi d'ouverture individuel sans
consentement spécifique), et le délai CNIL est dépassé.

## 3. Impact

- **Juridique** : exposition à un contrôle/sanction CNIL sur le volet e-mail
  (délai dépassé). Sur le web, exposition faible mais réelle (retrait +
  GA4). Sanctions cookies/pixels déjà prononcées par la CNIL (amendes).
- **Opérationnel** : perte de la mesure d'ouverture *individuelle* si on
  bascule en suivi **anonyme** (on garde les taux d'ouverture agrégés).
- **Métier** : le Personal Shopper / segmentation ne dépendent **pas** du pixel
  d'ouverture e-mail (ils s'appuient sur les achats et les embeddings), donc
  peu d'impact fonctionnel à désactiver le suivi individuel.

## 4. Plan d'action

### Volet e-mail (priorité 1 — délai dépassé)

1. **Activer le « suivi anonyme » dans Brevo** (compte → paramètres de suivi) :
   opens/clics restent mesurés **en agrégé**, non rattachés au contact. C'est la
   voie la plus rapide pour sortir du champ « traceur soumis à consentement »
   sur le suivi individuel. *(Action ops — pas de code.)*
2. **OU** recueillir un **consentement spécifique « suivi d'ouverture des
   e-mails »**, distinct de l'opt-in marketing, tracé dans les consentements
   RGPD existants (`Client` consents). *(Nécessite : nouveau purpose de consent
   + UI espace client + case dédiée.)*
3. **Ne pas tracker les e-mails transactionnels** (ticket, magic-link) : privilégier
   le suivi anonyme côté compte Brevo (Brevo n'expose pas de désactivation par
   message en SMTP transactionnel).
4. Mettre à jour la **politique de confidentialité** : section « pixels e-mail »
   (base légale, finalité, anonymisation/consentement, retrait).

### Volet web (priorité 2)

5. **Ajouter un mécanisme de retrait** du consentement cookies : lien
   « Gérer les cookies » en pied de page qui rouvre le bandeau et permet de
   repasser à `denied` (réémettre l'événement `vintiz:consent`). *(Petit dev
   front, `CookieBanner.tsx` + footer.)*
6. **Décision GA4** : soit le maintenir strictement gated (statu quo, acceptable
   tant que consenti), soit **migrer vers une solution exemptable** (Matomo
   auto-hébergé sans cookie, Piwik PRO) pour pouvoir mesurer **sans bandeau** et
   supprimer le risque GA4. *(Décision manager + ops.)*
7. Conserver Consent Mode v2 à `denied` par défaut (déjà en place).

### Suivi

8. Journaliser la décision (ce document) et re-vérifier après la mise en
   conformité e-mail.

## 4bis. Développements réalisés dans ce lot

Suite à validation manager, les développements suivants ont été implémentés
(le reste étant des actions ops/compte) :

**Migration GA4 → Matomo (mesure exemptée).**
- Nouveau composant `apps/site/src/components/Analytics.tsx` : Matomo
  **cookieless** (`disableCookies`) chargé **sans consentement** (exempté), avec
  suivi des changements de route SPA. GA4 conservé en **legacy**, toujours gated
  par consentement, désactivé tant que `NEXT_PUBLIC_GA_ID` est vide.
- Variables : `NEXT_PUBLIC_MATOMO_URL`, `NEXT_PUBLIC_MATOMO_SITE_ID`
  (`.env.example`, `.env.production.template`).
- ⚠️ **Action ops** : l'instance Matomo doit être réglée en audience exemptée
  (anonymisation IP, pas de cross-site, pas de partage) pour bénéficier de
  l'exemption de consentement.

**Retrait du consentement cookies.**
- Lien « Gérer les cookies » ajouté au footer (`PublicFooter.tsx`), visible
  uniquement si GA4 configuré (sinon rien à gérer). Il rouvre le bandeau
  (`CookieBanner.tsx`), qui affiche le choix courant et permet de **refuser /
  retirer** à tout moment (bascule Consent Mode → `denied`).

**Consentement au pixel d'ouverture des e-mails.**
- Nouveau purpose RGPD `email_open_tracking` (`ConsentPurpose`), migration
  Alembic `0075`, label FR (espace client + back-office), copie ajoutée à la
  politique de confidentialité. Il apparaît automatiquement dans l'espace
  client `/account/rgpd` (activer/désactiver).
- À l'envoi, les e-mails **marketing** (nouvelles pièces, alertes tendance,
  anniversaires) positionnent `track_opens` selon ce consentement ; sans
  consentement, l'e-mail part avec un marqueur d'audit `no-open-tracking`.
- ⚠️ **Limite fournisseur** : l'API transactionnelle Brevo ne permet pas de
  désactiver le pixel **par message**. La coupure effective du suivi individuel
  repose donc sur le réglage **« suivi anonyme »** du compte Brevo (action ops).
  Le consentement per-client est néanmoins tracé et prêt pour un pixel
  first-party / des campagnes Brevo (contrôle par envoi).

## 5. Note

Ce document est un état des lieux à date. Le volet e-mail (point 1) est une
action **ops/compte Brevo** ne nécessitant pas de déploiement. Les points 2, 5
et 6 nécessitent un développement à cadrer si le manager les retient. Le DPO
(`dpo@solidarite-textiles.fr`) doit valider le choix suivi anonyme vs
consentement spécifique.

---

### Sources réglementaires

- CNIL — pixels de suivi dans les e-mails (recommandation 2026, délai
  14/07/2026).
- CNIL — mesure d'audience, auto-évaluation (grille 5 objectifs / 14 critères,
  en vigueur 01/01/2026) ; GA4 non exempté (mise en demeure GA, 2022).
- Brevo — « About email tracking pixels and the CNIL recommendation » :
  pixel activé par défaut (France), option de **suivi anonyme** disponible.
