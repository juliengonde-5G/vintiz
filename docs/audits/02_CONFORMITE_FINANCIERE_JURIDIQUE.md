# Audit Conformité Financière & Juridique — Vintiz

> **Auteur** : Claude (audit externe complémentaire)
> **Date** : 2026-05-08
> **Périmètre** :
> 1. Conformité réglementaire FR (NF525, TVA biens d'occasion, gestion espèces, SumUp/PCI-DSS, RGPD)
> 2. Comparaison marché POS retail / 2nde main FR
> 3. Audit juridique — boutique + personal shopper IA
> **Méthode** : scan code monorepo (`apps/api`, `apps/web`, `apps/site`) + recherche réglementaire à jour 2026 + benchmark concurrents

---

## Synthèse exécutive

Vintiz démontre une **conformité substantielle** — la chaîne NF525 (hash SHA-256), Z reports verrouillés, export DGFiP, RGPD (export Article 20 + droit à l'oubli + DPO désigné), 3 modes SumUp avec stockage zéro PAN/CVV → tout cela est en place et tient la route à l'audit code.

Mais **5 trous critiques (P0)** doivent être bouchés **avant l'ouverture publique** de la boutique :

1. **Attestation éditeur NF525 non signée** — modèle prêt (`docs/COMPLIANCE_NF525.md`), à signer par Julien Gondé
2. **TVA — régime normal confirmé** (décision Vintiz, pas le régime de la marge) mais **calcul non auditable dans le code** : aucune colonne `tva_rate` sur `Transaction` ou `TransactionItem` → impossible de justifier le taux appliqué (20 %) lors d'un contrôle fiscal. Footer TVA absent des tickets (mention HT/TVA/TTC obligatoire en régime normal). Modèle = **achat ferme uniquement**, pas de dépôt-vente → pas de chantier de ce côté.
3. **Plafond paiement espèces 1000 € non validé** — un client peut payer 5000 € en espèces, contrevenant à la loi
4. **Profilage Personal Shopper sans consentement explicite préalable** — `Consent.purpose="profiling"` existe mais aucun écran de demande à l'inscription
5. **AIPD (analyse d'impact RGPD) absente** — obligatoire pour le profilage IA selon délibération CNIL 2018-327, **et** AI Act art. 50 (transparence chatbot) applicable au 02/08/2026

**Effort total P0** : 3-4 semaines (parallélisable).

**Risque financier non traité** :
- Amende NF525 : **7 500 € par logiciel** non conforme (CGI art. 1770 duodecies)
- Amende paiement espèces > plafond : **5 % des sommes payées indûment** (CGI art. 1840 J), solidaire client + Vintiz
- Sanction CNIL profilage non conforme : jusqu'à **4 % du CA mondial** ou 20 M€

---

## Partie 1 — Audit code : conformité technique

### Axe 1 — NF525 (Loi de finances 2016 art. 88, CGI art. 286 I-3°bis)

L'application doit garantir 4 propriétés cardinales (**ISCA**) : Inaltérabilité, Sécurisation, Conservation 6 ans, Archivage.

| Propriété | Implémentation | Statut |
|---|---|---|
| **Inaltérabilité** | Chaîne SHA-256 `apps/api/app/services/fiscal.py:35-48` — hash transaction = `SHA256(tx_number ‖ total_ttc ‖ created_at ‖ previous_hash)`, genesis = `"0"` | ✓ |
| **Vérification chaîne** | `verify_chain_integrity()` `fiscal.py:61-89` | ✓ |
| **Tests régression** | `apps/api/tests/test_nf525_chain.py` (199 lignes) — falsification montant/date/insertion détectées + chaîne 100 tx | ✓ |
| **Sécurisation** | Audit listeners SQLAlchemy `before/after_flush` `apps/api/app/services/audit.py:17-236`, redaction `pin_hash` / `password_hash`, `cashier_id` traceable obligatoire | ✓ |
| **Conservation 6 ans** | Aucune purge auto sur `Transaction` / `ZReport` ; RGPD `hard_delete()` anonymise `client_id` mais conserve la transaction (`apps/api/app/services/rgpd.py:237-286`) | ✓ |
| **Z reports verrouillés** | Génération + lock + PDF SHA-256 byte-identique idempotent `fiscal.py:95-269`, modèle `apps/api/app/models/pos.py:224-236` (`is_locked`, `locked_at`, `locked_by_user_id`, `pdf_content`, `pdf_sha256`) | ✓ |
| **Export DGFiP** | `GET /api/admin/fiscal-export?from=&to=&format=xml\|json` `apps/api/app/services/fiscal_export.py:44-241` — métadonnées + chaîne hash + items + payments | ✓ |

**P0 — Attestation éditeur non signée**

`docs/COMPLIANCE_NF525.md:103-131` contient le modèle d'attestation, mais il n'est pas imprimé/signé. Depuis la **loi n° 2026-103 du 19 février 2026** (BOFiP 25/03/2026), l'attestation éditeur est juridiquement valide en alternative au certificat d'organisme accrédité (AFNOR/INFOCERT/LNE). Elle doit :

- être signée par le représentant légal (Julien Gondé)
- préciser la version exacte du logiciel (Git tag conseillé)
- être conservée dans le dossier fiscal physique 6 ans
- être renouvelée à chaque release modifiant `FiscalService`, `Transaction`, `ZReport`

**P1 — Test "tampering DB direct" manquant**

Les tests couvrent les altérations via API. Ils ne couvrent pas le scénario contrôle fiscal "modification DB directe" (UPDATE raw SQL). À ajouter :

```python
# apps/api/tests/test_nf525_chain.py
async def test_chain_integrity_after_db_tampering():
    # 1. Crée 10 transactions
    # 2. UPDATE direct table transactions SET total_ttc = … WHERE id = 5
    # 3. Vérifie verify_chain_integrity() détecte le break + broken_at == 5
```

---

### Axe 2 — TVA et régime fiscal

> **Régime confirmé** : **régime normal de TVA à 20 %** sur prix de vente HT (pas le régime de la marge sur biens d'occasion). Décision Julien Gondé / Vintiz, hors scope de cet audit. Le régime de la marge (CGI art. 297 A) est donc **hors sujet** pour Vintiz — ce qui suit s'évalue uniquement à l'aune du régime normal.

| Aspect | Statut | Verdict |
|---|---|---|
| Régime TVA | Régime normal 20 % HT confirmé | ✓ (décision actée) |
| Calcul TVA dans transactions | Colonnes `total_ht`, `total_tva`, `total_ttc` présentes (`apps/api/app/models/pos.py:93-95`) | ⚠ taux non stocké |
| Taux TVA stocké par ligne | **AUCUNE colonne** `tva_rate` sur `Transaction` ni sur `TransactionItem` | ✗ **P0** |
| Calcul auditable | Hardcodé 20 % côté front ou service ? À tracer | ⚠ |
| Footer TVA sur tickets | Mention HT/TVA/TTC visible obligatoire en régime normal — à vérifier dans le générateur `escpos_service.py` | ⚠ **P1** |
| Factures B2B (mention TVA) | Implémentées migration `0035` — `is_invoice`, `invoice_number`, `client_siret`, templates configurables | ✓ |
| N° TVA intracommunautaire | À publier sur tickets et factures | ⚠ |
| Seuils franchise en base | Si Vintiz reste sous 85 000 € HT/an (biens) → franchise possible. Si dépasse 93 500 € (seuil majoré 2026) → assujettissement obligatoire. Aucune logique CA HT annuel dans le code | ⚠ **P2** |
| Droit à déduction TVA amont | Régime normal → Vintiz **récupère la TVA** sur ses achats taxés (équipements, fournitures, abonnements logiciels) — aucune trace de gestion comptable de la TVA déductible dans `apps/api/` (normal, c'est l'EC qui gère via Sage/équivalent) | ✓ hors scope POS |

**P0 — Stocker le taux TVA par ligne de transaction**

En régime normal, le taux appliqué (20 %) doit être justifiable lors d'un contrôle DGFiP. Aujourd'hui le calcul est probablement hardcodé côté code → **non auditable a posteriori si le taux change** (ex. taux réduit 5,5 % ou 10 % qui pourrait s'appliquer à certaines catégories — chaussures enfant, livres si Vintiz en vend, etc.).

Action :

```python
# Migration 0036_add_tva_rate_to_transaction_items.py
# ALTER TABLE transaction_items ADD COLUMN tva_rate NUMERIC(4,2) NOT NULL DEFAULT 20.00;
# ALTER TABLE products ADD COLUMN tva_rate NUMERIC(4,2) NOT NULL DEFAULT 20.00;

# apps/api/app/services/tva_service.py (à créer, simple)
def compute_line_totals(unit_price_ttc: Decimal, qty: int, discount_pct: Decimal, tva_rate: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Retourne (line_ht, line_tva, line_ttc) pour une ligne au régime normal."""
    line_ttc = (unit_price_ttc * qty) * (1 - discount_pct / 100)
    line_ht = line_ttc / (1 + tva_rate / 100)
    line_tva = line_ttc - line_ht
    return line_ht, line_tva, line_ttc
```

**Note** : la majorité des produits Vintiz sont des vêtements adultes → 20 %. Mais en régime normal il faut garder l'option ouverte pour catégories à taux différent (livres 5,5 %, chaussures bébé/enfant ≤ certains seuils 5,5 %, etc.). Préférer un default 20 % par produit, override possible.

**P1 — Footer TVA sur tickets (régime normal)**

En régime normal, la TVA **doit apparaître séparément** sur le ticket (contrairement au régime marge où elle ne doit **pas** apparaître). Mention à ajouter au footer :

```
                          HT       TVA 20%    TTC
Total :                  XX,XX €   XX,XX €   XX,XX €
N° TVA intracommunautaire : FR XX XXX XXX XXX
```

Pour les factures B2B (déjà existantes), s'assurer que la ventilation HT/TVA/TTC + N° TVA intracom est imprimée (à vérifier dans le template configurable de migration `0035`).

**Note SCIC / association ESS Solidarité Textiles** : en régime normal, le statut TVA du fournisseur (Solidarité Textiles) n'a pas d'impact direct sur le calcul de la TVA collectée par Vintiz (qui taxe à 20 % sur la totalité du prix de vente HT). Mais si Solidarité Textiles facture HT (non-redevable / franchise), Vintiz **n'a pas de TVA déductible** sur ces achats — la TVA collectée est intégralement due au Trésor. À documenter avec l'EC pour optimisation (ou non) du modèle de relations Vintiz / Solidarité Textiles.

**Comparaison vs concurrents 2nde main FR** : la plupart des concurrents 2nde main FR (Hiboutik, Seconde, Rezomatic, AC LOG) appliquent par défaut le régime de la marge — c'est le régime fiscalement le plus favorable pour la 2nde main pure (pas de TVA sur la totalité du prix, juste sur la marge). Vintiz fait le **choix inverse** (régime normal). Implications :

- ✗ Vintiz collecte **plus de TVA** que ses concurrents en régime marge → prix de vente plus élevé à marge équivalente, ou marge plus faible à prix équivalent
- ✓ Vintiz **récupère la TVA** sur ses achats taxés (équipements, abonnements), ce qui est impossible en régime marge
- ✓ Comptabilité simplifiée : pas de calcul de marge bénéficiaire au coup par coup, pas de régularisation annuelle stock 31/12 (CGI art. 297 A § II)
- ✓ Facturation B2B avec TVA visible → clients pros peuvent récupérer la TVA, ce qui rend Vintiz **plus attractif sur le segment B2B** (entreprises, costumiers, stylistes pros) que ses concurrents en régime marge

→ choix défendable, surtout si Vintiz vise le segment B2B / pros. À expliciter dans la communication interne et au comptable.

---

### Axe 3 — Gestion des espèces

| Aspect | Implémentation | Statut |
|---|---|---|
| Ouverture caisse + fond initial | `CashDrawer.opening_amount`, `opening_breakdown` JSONB `apps/api/app/models/pos.py:156-193` | ✓ |
| Fermeture caisse + écart | `closing_amount`, `expected_amount`, `closing_note`, `allowed_discrepancy` | ✓ |
| Calcul `expected` | `apps/api/app/services/cash_drawer.py:15-47` — `opening + Σ(cash payments)` | ✓ |
| Z reports journaliers | Voir Axe 1 | ✓ |
| Cash movements (dépôts, prélèvements) | Migration `0035` — table `cash_movements` | ✓ |
| **Plafond paiement espèces 1000 €** | **Aucun contrôle** sur `Payment.method=cash`, `amount` non borné | ✗ **P0** |

**P0 — Loi Sapin / décret 2015-741** : paiement espèces particulier > 1000 € **interdit** (15 000 € pour non-résident fiscal). Sanction : amende **5 % des sommes payées indûment**, **solidaire** entre client et commerçant, minimum 150 €.

Action :

```python
# apps/api/app/services/cash_payment_validator.py (à créer)
def validate_cash_payment(amount_eur: Decimal, customer_is_tourist: bool = False) -> tuple[bool, str | None]:
    cap = Decimal("15000") if customer_is_tourist else Decimal("1000")
    if amount_eur > cap:
        return False, f"Paiement espèces limité à {cap} € (loi anti-blanchiment)."
    return True, None
```

À brancher dans `POST /api/pos/transactions` avant commit, avec audit log si un manager force l'override (cas exceptionnel).

**P2 — Reporting espèces > 10 000 €/mois cumulé** : la banque déclenche automatiquement une COSI TRACFIN (art. L.561-15-1 CMF). Anticiper avec un module de reporting mensuel + dossier permanent à fournir à la banque sur demande.

---

### Axe 4 — SumUp & PCI-DSS

| Aspect | Implémentation | Statut |
|---|---|---|
| Stockage PAN / CVV | **Aucun stockage** — checkout opaque côté SumUp `apps/api/app/services/sumup_service.py:237-318` | ✓ |
| `PaymentAttempt` table | Migration `0035` — `method`, `amount`, `status`, `cashier_id`, `drawer_id`, `transaction_id`, `sumup_checkout_id` (pas de PAN ni token) `apps/api/app/models/payment_attempt.py:39-65` | ✓ |
| Modes prod / sandbox / simulation | Documentés `CLAUDE.md:125-134`, fallback auto sur sandbox sans clé | ✓ |
| Idempotence paiement | `Transaction.client_uuid` UUID unique généré côté POS, replay offline safe `apps/api/app/models/pos.py:66-72` | ✓ |
| Logs d'erreur SumUp | `error_detail = resp.text[:300]` — réponse API SumUp brute persistée `sumup_service.py:304-318` | ⚠ **P1** |

**P1 — Redaction des erreurs SumUp**

Si SumUp retourne une erreur contenant un fragment de PAN ou un token, il est persisté tel quel. Action :

```python
# Dans sumup_service.py, helper _redact_sumup_error()
def _redact_sumup_error(text: str) -> str:
    # Strip card-like 13-19 digit sequences
    text = re.sub(r"\b\d{13,19}\b", "<PAN_REDACTED>", text)
    # Strip CVV 3-4 digits in known contexts
    text = re.sub(r'(?i)(cvv|cvc|cvv2)\D*\d{3,4}', r"\1<REDACTED>", text)
    return text[:300]
```

**Cadrage SAQ PCI-DSS** : avec SumUp Solo en TPE standalone (le PAN ne transite jamais par les serveurs Vintiz), Vintiz reste en **SAQ B-IT** (~40 contrôles, ~3-5 k€/an), pas SAQ D (lourd, ~330 contrôles, 15-80 k€/an). À documenter par un **diagramme de flux carte** validé par SumUp (exigence PCI-DSS req. 1).

---

### Axe 5 — RGPD : boutique + personal shopper (profilage)

| Aspect | Implémentation | Statut |
|---|---|---|
| Consentement profilage explicite | `ConsentPurpose.profiling` existe `apps/api/app/models/client.py:29` mais **aucun écran d'activation initiale** | ✗ **P0** |
| Information utilisateur (art. 13/14) | Page `/confidentialite` existe — à enrichir d'une section Personal Shopper détaillée | ⚠ **P1** |
| Opt-in / opt-out | `POST /api/crm/account/personal-shopper/toggle` + `_enforce_gating()` `personal_shopper.py:318-347` | ✓ |
| Droit à l'effacement | `request_deletion()` + `purge_pending_deletions()` cron daily, fenêtre 30j `apps/api/app/services/rgpd.py:220-305` | ✓ |
| Export Article 20 | `export_client_data()` JSON (consents + loyalty + avoir + purchases) `rgpd.py:134-214` | ✓ |
| DPO désigné | `dpo@solidarite-textiles.fr` `CLAUDE.md:484` | ✓ |
| Newsletter double opt-in | Token signé désinscription 1-clic | ✓ |
| Cookies Google Consent Mode v2 | `apps/site/src/components/Analytics.tsx` — defaults `denied`, GA4 chargé post-grant | ✓ |
| Banner consentement cookies UI | À vérifier (composant `CookieConsent` / `ConsentBanner`) | ⚠ |
| Hashage email en audit logs | Email persisté **en clair** dans `audit.py:37-45` `_SENSITIVE_FIELDS` | ⚠ **P1** |
| Rétention embeddings (taste profile) | Pas de `expires_at`, pas de TTL ; non supprimé dans `hard_delete()` | ⚠ **P2** |
| Vérification âge | `Client.birth_date` facultatif, pas de check < 16 ans | ⚠ **P2** |
| **AIPD documentée** | **Absente** | ✗ **P0** |

**P0 — Pas de consentement explicite préalable au profilage**

Le `Consent(purpose="profiling")` existe en base mais aucun parcours UI ne le demande au moment de la collecte. Or :

- **Article 6-1-a RGPD** : consentement explicite, préalable, spécifique
- **Article 13 RGPD** : information claire au moment de la collecte
- **WP251 (lignes directrices G29/EDPB)** : profilage = traitement à risque renforcé
- **CJUE C-252/21 (Meta vs Bundeskartellamt, juillet 2023)** : « exécution du contrat » non recevable pour profilage publicitaire

**Action P0** :

1. **Écran `personal-shopper-consent`** côté `apps/site` :
   - Affiche : « Pour vous recommander des articles précis, nous analysons vos achats et préférences via une IA (Claude Haiku d'Anthropic). Vos données sont chiffrées, jamais revendues. Vous pouvez désactiver le service à tout moment. [Lire la politique complète](/confidentialite#personal-shopper). »
   - Boutons : « J'accepte » et « Continuer sans Personal Shopper » — **opt-in, pas opt-out**
   - Enregistre `Consent(purpose="profiling", granted=True/False, source="site_personal_shopper_consent", policy_version=…)`
2. **Endpoint backend** : `POST /api/crm/account/personal-shopper/init-consent` — bloque l'accès au PS tant que le consent n'est pas posé
3. **Existing membres** sans consent profiling → re-prompt à la prochaine connexion

**P0 — AIPD obligatoire**

Selon la délibération CNIL 2018-327, l'AIPD est obligatoire dès que ≥ 2 critères du CEPD sont cochés. Pour le Personal Shopper, on en coche typiquement **5** :

1. ✓ Évaluation / scoring (le profilage)
2. ✓ Données collectées à grande échelle (clients récurrents)
3. ✓ Croisement de données (achats physiques + e-com + IA)
4. ✓ Usage innovant / nouvelle technologie (LLM)
5. ✓ Décision automatisée affectant l'usager (si tarification dynamique ou priorisation accès stock)

→ AIPD **obligatoire**. Outil gratuit CNIL : **PIA** (logiciel). À transmettre à la CNIL si risques résiduels élevés non maîtrisés.

**P1 — Politique de confidentialité incomplète sur le PS**

Section à ajouter dans `apps/site/src/app/confidentialite/page.tsx` :

```
# Personal Shopper — finalité, données, droits

## Pourquoi nous utilisons vos données
Pour vous recommander des articles d'occasion premium qui correspondent à votre style, nous croisons :
- Votre historique d'achats (3 derniers en priorité)
- Vos préférences (tailles, couleurs, catégories)
- Le moment de votre visite et la météo (contexte uniquement)
- Vos clics sur les recommandations précédentes (boucle de feedback)

## Quelle IA ?
Nous utilisons Claude Haiku 4.5 (Anthropic, hébergeur AWS UE-Irlande). Anthropic ne réutilise pas vos données pour entraîner ses modèles (engagement contractuel API-Anthropic).

## Combien de temps ?
- Profil de goûts (embeddings) : tant que vous êtes membre, supprimé après 24 mois sans activité
- Logs de scoring : 6 mois
- Historique d'achats : 10 ans (obligation comptable Code de commerce L.123-22)

## Vos droits
- Accès : `/account/rgpd` > Export
- Effacement : `/account/rgpd` > Demander suppression (fenêtre annulation 30 j)
- Opposition : `/account/shopper` > Désactiver Personal Shopper (revoke immédiat)
- Intervention humaine : écrire à dpo@solidarite-textiles.fr

## Décision contestée ?
Notre responsable Vintiz peut réviser substantiellement toute recommandation contestée sous 30 jours.
```

**P1 — Hashage email dans audit_logs**

`apps/api/app/services/audit.py:76-100` — la fonction `_redact()` masque `pin_hash` / `password_hash` mais conserve `email`, `phone`, `first_name`, `last_name` en clair. Pour 6 ans de rétention NF525, c'est une surface d'attaque inutile. Reco :

```python
# Option balanced : hash partiel non-réversible mais traçable
if field == "email":
    return hashlib.sha256(value.lower().encode()).hexdigest()[:12] if value else None
```

**P2 — Rétention embeddings**

`CustomerTasteProfile` (pgvector) n'a ni `expires_at` ni TTL. Non supprimé par `hard_delete()`. À ajouter dans le cron quotidien :

```python
# apps/api/app/services/embedding_retention.py
async def cleanup_expired_embeddings():
    # 1. Clients avec deletion_requested_at → DELETE FROM customer_taste_profile
    # 2. Clients inactifs > 24 mois → idem
    # 3. Audit log de la suppression
```

**P2 — AI Act art. 50 — transparence chatbot (au 02/08/2026)**

Le règlement (UE) 2024/1689 (AI Act) impose pour les systèmes à risque limité (chatbot) un disclaimer permanent. Action UI : ajouter dans `apps/site/src/app/account/shopper/` :

```
"Vous discutez avec une IA Personal Shopper Vintiz."
```

Déclencheur : avant la première interaction, pas en réponse à la première interaction. Et marquage machine-readable des sorties (art. 50-2).

---

## Partie 2 — Mémo réglementaire (référentiel)

### NF525 — état au 8 mai 2026

- Texte : Article 88 LF 2016 → CGI art. 286 I-3°bis ; doctrine BOI-TVA-DECLA-30-10-30 (dernière maj BOFiP **25/03/2026**)
- Loi n° 2026-103 du **19/02/2026** : **rétabli l'attestation éditeur** comme alternative au certificat AFNOR/INFOCERT/LNE
- Tolérance prolongée jusqu'au **31/08/2026** (BOFiP ACTU-2025-00160)
- Régime cible au 01/09/2026 : certificat accrédité **OU** attestation éditeur conforme au modèle BOFiP
- Sanction : amende **7 500 € / logiciel** (CGI art. 1770 duodecies) + 60 j pour régulariser
- Périmètre : tout assujetti TVA réalisant des ventes B2C avec logiciel de caisse — Vintiz est dedans

### TVA biens d'occasion — régime de la marge

- CGI art. 297 A à G + BOI-TVA-SECT-90-20-20
- Conditions cumulatives : assujetti-revendeur, bien d'occasion, acheté à non-assujetti
- Calcul : (prix vente TTC − prix achat TTC) × (1/1,20) au taux normal 20 %
- Méthode coup par coup OU globale par période + régularisation stock 31/12
- Aucun droit à déduction TVA amont (TVA rémanente)
- Mention obligatoire : « Régime particulier — Biens d'occasion / Article 297 A du CGI et directive 2006/112/CE »
- TVA **non séparée** sur facture régime marge

**Seuils franchise en base 2026** (BOI-BAREME-000036, réforme 25 000 € **suspendue/reportée**) :
- biens : 85 000 € (base) / 93 500 € (majoré)
- services : 37 500 € (base) / 41 250 € (majoré)

### Espèces

- Plafond résident → pro : **1 000 €** (CMF art. D112-3)
- Plafond non-résident fiscal → pro : **15 000 €**
- Sanction : **5 % des sommes** payées indûment (CGI art. 1840 J), solidaire payeur/bénéficiaire, min 150 €
- Livre de caisse : conservation 6 ans LPF L.102 B (10 ans recommandé)
- COSI TRACFIN : déclaration banque automatique > 10 000 €/mois (CMF art. L.561-15-1)

### PCI-DSS v4.0.1 (en vigueur 31/03/2025)

- Vintiz = **Level 4** marchand (< 1 M tx/an)
- Avec SumUp Solo standalone : **SAQ B-IT** (~40 contrôles, 3-5 k€/an)
- Si jamais le PAN transite par les serveurs Vintiz → escalade en **SAQ D** (~330 contrôles, 15-80 k€/an) ⚠
- Diagramme de flux carte exigé (req. 1)
- Logs ≥ 1 an dont 3 mois immédiat dispo (req. 10)
- TLS 1.2 mini, MFA admin, registre TPE physique
- Soumission annuelle SAQ signé à SumUp

### RGPD profilage + AI Act

- **Article 22 RGPD** : recommandation pure « hors art. 22 » mais profilage sous-jacent reste dans le RGPD
- Base légale recommandée : **consentement explicite** (art. 6-1-a) opt-in granulaire
- **Article 50 AI Act** (applicable au **02/08/2026**) : chatbot = obligation de transparence + marquage machine-readable des sorties
- Durées CNIL recommandées : profil comportemental 13 mois, logs scoring 6 mois, compte inactif 2 ans, données comptables 10 ans
- AIPD obligatoire dès ≥ 2 critères CEPD (Vintiz en coche 4-5)

---

## Partie 3 — Comparaison marché POS retail / 2nde main FR

### Tableau synthétique

| Acteur | NF525 (mai 2026) | 1 pièce = 1 SKU | TVA marge native | Dépôt-vente | Personal Shopper IA | Prix HT/mois | 2nde main |
|---|---|---|---|---|---|---|---|
| **Lightspeed Retail** (X-Series) | Oui (cert. INFOCERT) | Oui | Add-on | Tiers | Reco moteur règles | 89-289 € | Limité |
| **Shopify POS Pro** | Oui (cert. 26/03/2026, app *Comply*) | Faible (variantes ≠ pièce unique) | Non native | Apps tierces | Shopify Magic, Sidekick | 89 € + abo | Limité |
| **Hiboutik** (FR-CH) | **Oui** dès la version gratuite | Oui | **Oui** (app dédiée) | Paramétrable | Non | **Gratuit** ou 9,90 € Premium | Bon (friperies solidaires) |
| **Cashpad** (FR) | Oui | Faible (resto-centric) | Limité | Non | Non | 52 € Lite / 109 € | Limité |
| **Tactill** (FR) | Oui | Oui | Limité | Non | Non | 52 €+ (pack iPad ~1189 €) | Limité |
| **Square POS** | **À vérifier** — pas de cert. INFOCERT publié | Oui | Limité | Non | Square AI (en cours) | Gratuit (commission) | Très limité |
| **Seconde** (FR) | Oui (annoncé) | **Oui — natif** | **Oui** (calcul auto déposant/btq/TVA) | **Cœur métier** | Non | ~45-89 € | **Excellent** |
| **Rezomatic / TGM Commerce** (FR) | Oui (depuis 2017) | Oui | **Oui** | **Oui** (contrat numérique signé) | Non | Sur devis | **Excellent** |
| **Ginkoia** (Orisha, FR) | Oui | Oui | Oui | Oui (SMS auto déposant) | Non | 200+ € | Bon |
| **AC LOG dépôt-vente** | Oui | Oui | Oui | Oui | Non | Sur devis | Bon |
| **Vintiz** (auto-hébergé) | À démontrer (attestation OU certif.) | **Oui — natif** | **N/A — choix régime normal** (TVA visible HT/TVA/TTC) | **Hors modèle** (achat ferme uniquement) | **Personal Shopper IA propriétaire** | Internalisé | **Cœur métier** |
| **Vinted Pro** | N/A (marketplace) | N/A | N/A | N/A | Algos Vinted | Commission | Plateforme |

### Lectures clés

- **Verticale dépôt-vente FR (Seconde, Rezomatic, e-inventaire, AC LOG, Ginkoia)** = segment le plus mature techniquement (1 pièce = 1 SKU + TVA marge + contrat dépôt-vente). Aucun n'a d'IA conversationnelle. **Hors scope Vintiz** (modèle achat ferme).
- **Shopify POS Pro** vient d'obtenir NF525 (26/03/2026) mais sa logique « variantes produits » est mal adaptée à la pièce unique — chaque pièce devrait être un SKU distinct, pas une variante d'un produit-modèle.
- **Hiboutik** = bon plan FR (NF525 dans la version gratuite, app TVA marge native). Manque ergonomie moderne et IA.
- **Square** = à éviter dans un audit FR tant que le certificat NF525 n'est pas vérifiable au registre INFOCERT (risque amende 7 500 €).

### Différenciation Vintiz

| Force vs marché | Position |
|---|---|
| Pièce unique native | ✓ aligné avec verticales 2nde main, pas avec généralistes |
| Personal Shopper IA propriétaire (Claude Haiku + embeddings) | ✓ **unique sur le marché FR 2nde main** au 05/2026 |
| Auto-hébergement | + souveraineté / − coût et conformité à supporter en interne |
| Régime TVA | choix **régime normal** assumé (vs régime marge dominant chez les concurrents 2nde main) — facilite B2B et déduction TVA amont, alourdit le prix de vente toutes choses égales par ailleurs |
| Modèle d'achat | **achat ferme uniquement** — pas de dépôt-vente. Décision stratégique : Vintiz porte le stock, gère le sourcing (Solidarité Textiles + lots), garde la main sur la curation et la marge |

**Synthèse positionnement** : Vintiz se distingue par 2 choix structurants assumés — (1) **régime normal de TVA** vs régime de la marge dominant chez les concurrents 2nde main, (2) **achat ferme uniquement** sans dépôt-vente. Combinés au Personal Shopper IA propriétaire, ces choix construisent un positionnement **boutique premium curée à stock propriétaire**, plus proche du modèle Imparfaite ou Once Again que des verticales dépôt-vente FR (Seconde, Rezomatic, Ginkoia). Pas de gap fonctionnel à combler côté dépôt-vente — c'est un choix de modèle, pas un retard.

---

## Partie 4 — Volet juridique (rôle « responsable juridique »)

> Ce volet adopte la posture d'un responsable juridique interne. Vintiz **assume** d'utiliser les données clients pour rendre la gestion de clientèle plus précise et le personal shopper plus pertinent — l'enjeu n'est pas de masquer cet usage, mais de l'**encadrer correctement**.

### Volet 1 — Boutique (POS, fidélité, espace client)

#### Risques juridiques identifiés

| Risque | Probabilité | Sévérité | Action |
|---|---|---|---|
| Contrôle DGFiP sans certif NF525 valide | Moyenne | **Très élevée** (7 500 € + reconstitution recettes) | P0 — signer attestation éditeur |
| TVA marge non appliquée → redressement | Élevée | Élevée | P0 — confirmer régime + implémenter |
| Paiement espèces > 1 000 € accepté | Moyenne | Élevée (5 % du montant solidaire) | P0 — validation applicative |
| Logs avec PII en clair (data leak) | Faible | Très élevée (CNIL) | P1 — hashage email |
| Cookies sans banner visible | Faible | Moyenne | P1 — vérifier UI |

#### Plan juridique boutique

1. **Avant ouverture (P0, 3-4 semaines)** :
   - Attestation éditeur NF525 signée + scan archivé + Git tag de release lié
   - Avis comptable confirmant le régime TVA (marge probable) — devis EC à demander
   - Implémentation validation espèces 1 000 €
   - CGV et politique de confidentialité revues par avocat (1 demi-journée, ~800-1 200 € HT)
   - Mentions légales site complètes (éditeur, hébergeur, DPO)
   - Registre des traitements RGPD (art. 30) à formaliser
2. **Phase 2 (juin 2026, P1)** :
   - Hashage email audit logs
   - Banner cookies vérifiable
   - Footer TVA tickets + mention 297 A si régime marge
3. **Phase 3 (juillet 2026, P2)** :
   - Politique de rétention embeddings
   - Test régression tampering DB
   - Doc rotation `SECRET_KEY`

### Volet 2 — Personal Shopper (ouvert sur les clients)

#### Position assumée

Vintiz utilise les données clients (historique d'achats, préférences, clics, contexte météo) pour :
- **rendre la gestion de clientèle plus précise** : segmentation RFM, tier fidélité, cohortes, alertes anniversaire
- **proposer un personal shopper plus pertinent** : embeddings pgvector + Claude Haiku, taste profile cliente, recommandations narratives

Cet usage est **légitime et précieux** pour la cliente. Le travail de mise en conformité ne consiste pas à le restreindre, mais à :
1. l'**informer** clairement
2. obtenir son **consentement explicite** opt-in
3. lui donner les **moyens de contrôle** (opposition, intervention humaine, suppression)
4. **documenter** dans une AIPD le bénéfice/risque

#### Risques juridiques spécifiques au Personal Shopper

| Risque | Probabilité | Sévérité | Action |
|---|---|---|---|
| Profilage sans consentement explicite | Élevée actuellement | Très élevée (CNIL : 4 % CA mondial / 20 M€) | P0 — écran consent dédié |
| AIPD absente (déli. CNIL 2018-327) | Certaine | Élevée | P0 — produire AIPD avec outil PIA gratuit |
| Information art. 13/14 incomplète | Élevée | Moyenne | P1 — section dédiée /confidentialite |
| AI Act art. 50 non respecté au 02/08/2026 | Certaine si rien fait | Moyenne (selon décret applicatif FR) | P2 — disclaimer permanent |
| Décision sans intervention humaine substantielle | Faible (effet limité actuellement) | Moyenne | P2 — procédure documentée |
| Rétention indéfinie embeddings | Élevée | Moyenne | P2 — TTL + cleanup cron |

#### Plan juridique Personal Shopper

1. **Avant ouverture (P0, 1-2 semaines)** :
   - Écran de consentement explicite « personal-shopper-consent » (UI + endpoint backend + enregistrement Consent ledger)
   - AIPD rédigée (outil **PIA logiciel CNIL**, gratuit) — couvrir : finalité, base légale, données collectées, durées de conservation, mesures de sécurité, droits, risques résiduels
   - Section « Personal Shopper » détaillée dans `/confidentialite` (cf. modèle Partie 1 §5)
   - Procédure d'intervention humaine documentée + email DPO actif
2. **Phase 2 (juin 2026, P1)** :
   - Test régression sur révocation consent (le PS doit immédiatement cesser)
   - Audit log de toutes les recommandations PS pour traçabilité
3. **Avant 02/08/2026 (P2)** :
   - Disclaimer permanent dans l'UI shopper « Vous discutez avec une IA Personal Shopper Vintiz »
   - Marquage machine-readable des sorties (art. 50-2 AI Act)
   - Mention IA dans toutes les communications email automatiques générées par Claude

#### Mention type CGU à insérer

```
Article X — Personal Shopper IA
Vintiz vous propose, sur consentement explicite, un service de
recommandation personnalisée appelé Personal Shopper, alimenté par
une intelligence artificielle (Claude Haiku, hébergée par Anthropic
au sein de l'Union européenne). Pour vous proposer des articles
adaptés à votre style et à votre budget, nous analysons votre
historique d'achats, vos préférences déclarées (tailles, couleurs,
catégories, marques), vos interactions avec les recommandations
précédentes et un contexte de visite (saison, météo locale, moment
de la journée).

Vous pouvez à tout moment :
- désactiver le service depuis votre espace client (effet immédiat)
- demander l'accès à vos données ou leur portabilité (article 20 RGPD)
- demander la suppression complète de votre profil (article 17 RGPD)
- demander l'intervention humaine d'un responsable Vintiz pour
  contester une recommandation (dpo@solidarite-textiles.fr)

La conservation des données de profilage est limitée à la durée
de votre adhésion au programme de fidélité, et au maximum à 24 mois
sans activité.
```

---

## Partie 5 — Plan d'action consolidé

### Vague P0 — Avant ouverture publique (3-4 semaines)

| # | Action | Effort | Owner |
|---|---|---|---|
| 1 | Signer attestation éditeur NF525 (modèle prêt) | 1 j (humain) | Julien Gondé |
| 2 | Régime TVA normal — ajouter `tva_rate` sur `Product` + `TransactionItem`, créer `tva_service.compute_line_totals()`, footer ticket HT/TVA/TTC + N° TVA intracom, valider avec l'EC les options de taux par catégorie | 1-2 sem | EC + dev |
| 3 | `cash_payment_validator.py` + intégration POS + audit log override | 1 sem | dev |
| 4 | Écran consentement explicite Personal Shopper + endpoint init-consent + re-prompt membres existants | 1-2 sem | UX + dev |
| 5 | AIPD via outil PIA CNIL — finalité, base légale, données, durées, risques | 1 sem | DPO + Julien |
| 6 | Revue avocat : CGV + politique confidentialité + mentions légales | 1 demi-j | avocat externe (~800-1 200 € HT) |

### Vague P1 — Phase 2 (juin 2026)

| # | Action | Effort |
|---|---|---|
| 7 | Hashage email/phone dans `audit.py:_redact()` | 3-5 j |
| 8 | Footer TVA tickets HT/TVA/TTC + N° TVA intracom (régime normal) | 2 j |
| 9 | Section Personal Shopper enrichie dans `/confidentialite` | 1 j |
| 10 | Banner cookies vérifié visible + accessible | 1 j |
| 11 | Redaction `_redact_sumup_error()` avant persistance | 1 j |
| 12 | Test `test_chain_integrity_after_db_tampering()` | 1 j |
| 13 | Procédure d'intervention humaine PS documentée + audit log reco | 2 j |

### Vague P2 — Phase 3 (juillet–août 2026)

| # | Action | Effort | Deadline |
|---|---|---|---|
| 14 | Disclaimer permanent UI shopper + marquage machine-readable sorties (AI Act art. 50) | 2 j | **avant 02/08/2026** |
| 15 | TTL + cleanup cron embeddings + suppression dans `hard_delete()` | 3 j | juillet |
| 16 | Module reporting espèces > 10 000 €/mois (anticipation COSI) | 2 j | juillet |
| 17 | Documentation rotation `SECRET_KEY` | 1 h | juillet |
| 18 | Diagramme de flux carte PCI-DSS validé par SumUp | 1 j | juillet |
| 19 | Soumission SAQ B-IT signé à SumUp | 1 j | annuel |
| 20 | Décision NF525 long terme : rester sur attestation éditeur OU lancer certification accréditée (12-25 k€, 6-9 mois) | décision | sept-2026 |

### Effort total

- **P0** : 25-30 j-personne (parallèle, ~3-4 semaines calendaire)
- **P1** : 12-15 j-dev
- **P2** : 12 j-dev + décision stratégique certif

### Risque financier évité

- NF525 : amende 7 500 € + reconstitution recettes
- TVA marge non appliquée : redressement N-3 + intérêts + majoration 40 %
- Espèces > 1000 € : 5 % solidaire (50 € sur 1000 € exemple)
- Profilage non conforme : sanction CNIL jusqu'à 4 % CA mondial / 20 M€
- AI Act art. 50 non respecté au 02/08/2026 : sanctions à venir, plafond 15 M€ ou 3 % CA mondial

---

## Annexe — Calendrier réglementaire 2026-2027

| Date | Évènement | Impact Vintiz |
|---|---|---|
| 21/02/2026 | Loi n° 2026-103 — rétablissement attestation éditeur NF525 (BOFiP 25/03/2026) | Voie B disponible immédiatement |
| **02/08/2026** | **AI Act art. 50 transparence chatbot applicable** | Disclaimer + marquage sorties **obligatoires** |
| 31/08/2026 | Fin tolérance NF525 (BOFiP ACTU-2025-00160) | Régime cible au 01/09/2026 |
| 31/12/2026 | Régularisation annuelle stock TVA marge (CGI art. 297 A § II) | Si régime marge : module dédié |
| 02/08/2027 | AI Act application haut risque produit complète | Hors scope Personal Shopper actuel |

---

## Annexe — Sources réglementaires consolidées

- BOI-TVA-DECLA-30-10-30 (BOFiP) — version 25/03/2026
- BOFiP ACTU-2025-00160 (prorogation au 31/08/2026)
- BOFiP ACTU-2025-00075 (suppression attestation éditeur, LF 2025)
- CGI Article 297 A — régime particulier biens d'occasion
- CGI Article 1840 J — sanctions paiement espèces
- CGI Article 1770 duodecies — sanctions logiciel de caisse
- BOI-TVA-SECT-90-20-20 — assujettis-revendeurs
- BOI-BAREME-000036 — seuils franchise TVA
- BOI-CF-INF-10-40-20 — sanctions livre de caisse
- CMF Article L.561-15-1 — COSI TRACFIN
- CMF Article D.112-3 — plafond espèces 1 000 €
- LPF Article L.102 B — conservation 6 ans
- Règlement (UE) 2024/1689 (AI Act) — articles 4, 50
- RGPD articles 6, 13, 14, 17, 20, 22, 30, 35
- CNIL — délibération 2018-327 (liste AIPD obligatoire)
- WP251 — lignes directrices G29/EDPB sur le profilage
- CJUE C-252/21 — Meta vs Bundeskartellamt (juillet 2023)
- Loi n° 2026-103 du 19/02/2026 — rétablissement attestation éditeur NF525
- PCI-DSS v4.0.1 — en vigueur 31/03/2025
