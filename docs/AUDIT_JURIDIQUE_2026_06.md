# Audit juridique — Site Vintiz (juin 2026)

**Posture** : agent juridique. Vérification de conformité et d'exhaustivité des
mentions légales obligatoires d'un site e-commerce / vitrine français (boutique
physique, seconde main premium, Vernon, partenariat Solidarité Textiles / ESS).

**Périmètre** : CGV, mentions légales, politique de confidentialité (RGPD),
consentement / cookies, citation des marques.

> ⚠️ Cet audit est une revue de conformité technique du code et des contenus
> publiés. Il ne se substitue pas à la validation d'un avocat. Les champs
> dépendant de l'immatriculation réelle (SIRET, RCS, capital, forme juridique)
> doivent être renseignés par l'exploitant — ils sont signalés `À RENSEIGNER`.

---

## 0. Synthèse — niveau de conformité

| Domaine | État | Criticité des manques |
|---|---|---|
| Mentions légales (LCEN art. 6-III) | 🔴 Incomplet | **Haute** — identité légale manquante |
| CGV | 🟡 Présent, à compléter | Moyenne — médiateur + garanties légales |
| Politique de confidentialité (RGPD) | 🟡 À valider | Haute — transfert Anthropic hors EEE |
| Cookies / consentement | 🟢 Conforme | Bandeau + Consent Mode v2 présents |
| Citation des marques | 🟡 À encadrer | Moyenne — disclaimer d'indépendance absent |
| Cohérence inter-pages | 🟡 | 1 incohérence (durée du bon : 60 j vs 6 mois) |

---

## 1. Mentions légales — 🔴 INCOMPLET (priorité haute)

Fichier : `apps/site/src/app/mentions-legales/page.tsx`.

**Présent** : nom commercial (Vintiz), adresse boutique, hébergeur (Scaleway —
nom + adresse ✓), DPO + sous-traitants, cookies, propriété intellectuelle.

**Manquant (obligatoire — LCEN art. 6-III + C. com. art. R123-237)** :
- **Forme juridique** (SARL, SAS, EI, micro-entreprise…) — `À RENSEIGNER`
- **Capital social** (si société) — `À RENSEIGNER`
- **N° SIRET / SIREN** — `À RENSEIGNER`
- **N° RCS + ville du greffe** (ou RM si artisan) — `À RENSEIGNER`
- **N° TVA intracommunautaire** (si assujetti) — `À RENSEIGNER`
- **Directeur / responsable de la publication** (nom) — `À RENSEIGNER`
- **Téléphone** de contact (recommandé fortement, quasi obligatoire e-commerce)
- **Téléphone de l'hébergeur** (Scaleway) — recommandé
- **Médiateur de la consommation** (peut figurer ici ou en CGV — voir §2)

**Correction apportée** : ajout d'un bloc « Identité de l'entreprise » avec
placeholders explicites `À COMPLÉTER` + téléphone + médiateur, pour que
l'exploitant n'ait qu'à remplir les valeurs réelles (pas de fausse donnée
inventée).

---

## 2. CGV — 🟡 présent, à compléter

Fichier : `apps/site/src/app/cgv/page.tsx` (9 articles).

**Bien couvert** : objet, produits (état/unicité), prix TTC, paiement, retours
(défaut caché 7 j + geste commercial), avoir, fidélité, données, litiges + droit
applicable + tribunal de Vernon.

**Manques / corrections** :
1. **Médiateur de la consommation NON nommé** (art. L612-1 C. conso —
   *obligatoire* pour un pro vendant à des consommateurs). L'art. 9 évoque « une
   procédure de médiation conventionnelle » sans **nom + URL + adresse** du
   médiateur. → bloc médiateur ajouté avec placeholder `À RENSEIGNER` + rappel
   **plateforme RLL** (la plateforme RLL européenne a fermé le 20/07/2025 — ne
   plus la citer ; renvoyer au médiateur national).
2. **Garantie légale de conformité** (art. L217-3 s. C. conso) et **garantie des
   vices cachés** (art. 1641 C. civ.) — non mentionnées. Même pour de la seconde
   main « vendue en l'état », la garantie légale de conformité **s'applique**
   (24 mois ; le pro peut informer mais pas l'exclure pour un consommateur). →
   article « Garanties légales » ajouté.
3. **Incohérence durée du bon fidélité** : l'art. 6 indique « valable **60
   jours** » alors que le moteur a été passé à **6 mois** (PR #110/#112). →
   corrigé en « 6 mois » + formulation rendue cohérente avec le paramétrage
   admin (durée susceptible d'évoluer, affichée en boutique).
4. **Pas de droit de rétractation** : correct en l'état — vente **en boutique
   physique** uniquement (le droit de rétractation 14 j ne s'applique pas aux
   achats en magasin). À conserver tel quel **tant qu'il n'y a pas de vente en
   ligne** (cohérent avec « aucune vente en ligne »).

---

## 3. Politique de confidentialité (RGPD) — 🟡 à valider

Fichier : `apps/site/src/app/confidentialite/page.tsx`.

**Bien couvert** : responsable de traitement, **DPO** (`dpo@solidarite-textiles.fr`),
finalités, sous-traitants nommés, durées de conservation (profil 24 mois,
prospection 3 ans CNIL, comptabilité 10 ans), droits RGPD + **réclamation
CNIL**, base embeddings et suppression immédiate du profil dérivé au retrait
du consentement.

**Réserve majeure constatée le 16/07/2026** : la version publiée affirmait à
tort « Anthropic Ireland / AWS Europe », « aucun transfert hors UE » et une
absence de conservation après inférence. La documentation officielle
d'Anthropic indique au contraire un traitement possible dans plusieurs
régions, un stockage aux États-Unis par défaut et, pour l&apos;API standard, une
suppression des entrées/sorties sous 30 jours sauf exceptions. Les contenus ont
été corrigés ; il reste à conserver au dossier RGPD le DPA applicable et les
garanties du chapitre V (CCT et analyse de transfert si requise).

**Précisions recommandées** :
- **Bases légales** par finalité (exécution du contrat / intérêt légitime /
  consentement) — à expliciter finalité par finalité.
- **Transferts hors EEE** : vérifier et archiver le DPA Anthropic, les clauses
  contractuelles types et l&apos;analyse de transfert applicables avant de clôturer
  cette réserve.
- **qrserver.com** (génération des QR de carte fidélité, `api.qrserver.com`) :
  le payload de carte (n° V######) transite par un service tiers (Allemagne/UE) —
  à mentionner dans les sous-traitants, **ou** basculer la génération QR en
  interne (recommandé — supprime un tiers). *Voir reco technique §6.*
- **OpenWeather** (météo Vernon, contexte des recos) : pas de donnée perso
  transmise → mention non obligatoire, mais à vérifier.

**Corrections apportées** : suppression des allégations d'hébergement UE,
publication de la durée standard Anthropic (30 jours, sauf exceptions),
transparence sur le transfert vers les États-Unis, internalisation du QR et
suppression/anonymisation des signaux Personal Shopper lors du retrait du
consentement.

---

## 4. Cookies / consentement — 🟢 conforme

- **Bandeau** : `apps/site/src/components/CookieBanner.tsx` présent + monté dans
  `layout.tsx`.
- **Consent Mode v2** : `gtag('consent','default', …)` en **denied** par défaut
  (`layout.tsx`), `update` vers `granted/denied` piloté par le choix utilisateur
  (`components/Analytics.tsx`). GA4 chargé sous condition de consentement, IP
  anonymisée annoncée.
- **Conforme CNIL** : refus aussi simple que l'acceptation à vérifier
  visuellement sur le bandeau (le composant existe ; revue UX recommandée).

Aucune correction bloquante. ✓

---

## 5. Citation des marques — 🟡 à encadrer

Le site nomme des marques tierces comme arguments de sélection (Sandro, Maje,
Sézane, Polène, IRO, Isabel Marant…) sur `/produits`, `/capsules`, `/journal`,
`/personal-shopper`, pages EN.

**Cadre** : la revente de produits authentiques d'occasion et la citation des
marques pour **décrire** ce qui est vendu sont licites (épuisement des droits +
référence nécessaire), **à condition** de ne pas laisser croire à un lien
commercial / partenariat avec ces marques.

**Manque** : **aucun disclaimer d'indépendance**. → Risque d'allégation de
parasitisme / d'affiliation trompeuse.

**Correction apportée** : ajout d'une mention d'indépendance (footer + mentions
légales) : *« Vintiz est une boutique indépendante de seconde main. Les marques
citées appartiennent à leurs propriétaires respectifs ; leur citation décrit des
articles authentiques d'occasion et n'implique aucun partenariat ni
affiliation. »*

---

## 6. Recommandations techniques (hors texte légal)

1. **Internaliser la génération des QR** de carte fidélité (aujourd'hui via
   `api.qrserver.com`) → supprime un sous-traitant + évite la fuite du n° de
   carte vers un tiers. (Lib QR locale.)
2. **Cohérence des durées** : la durée du bon est désormais paramétrable
   (admin/operations). Le texte CGV doit rester générique (« durée affichée en
   boutique / dans votre espace ») pour ne pas re-diverger à chaque changement.
3. **Footer legal** : vérifier que CGV, Mentions légales, Confidentialité sont
   tous liés depuis le footer public (FR **et** EN).

---

## 7. Corrections appliquées dans cette PR

- `mentions-legales` : bloc identité entreprise (placeholders `À COMPLÉTER`) +
  téléphone + médiateur + disclaimer marques + `api.qrserver.com`.
- `cgv` : médiateur conso (placeholder) ; **article Garanties légales** ; durée
  du bon **60 j → 6 mois** + formulation générique ; rien d'autre retiré.
- `confidentialite` : phrase « traitements UE » + `api.qrserver.com`.
- Footer : lien disclaimer d'indépendance des marques.

Les éléments `À RENSEIGNER / À COMPLÉTER` nécessitent les **valeurs réelles**
d'immatriculation — laissés en placeholders explicites plutôt qu'inventés.
