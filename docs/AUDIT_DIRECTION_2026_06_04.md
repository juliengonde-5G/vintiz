# Audit complet VINTIZ - Direction metier & technique

Date d'audit : 04/06/2026  
Perimetre : lecture statique du depot local `vintiz`, sans navigation externe.  
Limite de verification : les tests n'ont pas pu etre executes localement car les dependances Python ne sont pas installees dans l'environnement courant (`ModuleNotFoundError: fastapi`).

## A. Resume executif

### Niveau global de maturite

VINTIZ presente une maturite fonctionnelle elevee pour une boutique de seconde main : POS, CRM, inventaire, etiquettes, fidelite, avoirs, remboursement, rapports Z, export fiscal, sauvegardes, SEO et communication sont presents dans le code. Le socle est ambitieux et coherent avec un outil unique d'exploitation boutique.

Le niveau de maturite operationnelle est toutefois a qualifier : **bon sur la couverture fonctionnelle, moyen sur le controle interne, la securite des donnees client et la gouvernance de livraison**. Les risques les plus forts ne viennent pas d'une absence de modules, mais de quelques flux critiques encore insuffisamment verrouilles cote serveur.

### Principaux risques

| Risque | Niveau | Synthese |
|---|---:|---|
| Donnees client accessibles/modifiables par simple email sur routes publiques | Critique | Plusieurs endpoints `/api/crm/account/*` n'exigent pas le JWT magic-link et retournent achats, coupons, consents ou export RGPD sur simple email. |
| POS accepte prix/remises/quantites insuffisamment bornes cote serveur | Critique | `CartItem` accepte `unit_price`, `discount_percent`, `quantity` sans contraintes fortes ; `PosService` fait confiance a ces valeurs. |
| Calcul TVA de vente non branche sur le service multi-taux | Majeure | `tva_service.py` existe, mais `PosService` recalcule toujours en dur a 20 %. |
| Route caisse courante cassee | Majeure | `/api/pos/drawer/current` importe `app.models.payment` et `app.models.transaction`, modules absents. |
| CI/deploiement permissifs | Majeure | Lint, typecheck et tests peuvent echouer sans bloquer ; deploy ne depend pas du CI. |
| Roles trop grossiers | Majeure | Seulement `manager` / `collaborateur`, alors que remboursements, ouverture/fermeture caisse, mouvements cash, exports et donnees client demandent des permissions distinctes. |

### Points forts

- Modele metier riche : produits seconde main, articles permanents, lots, zones, photos, labels, POS, fidelite, avoirs, personal shopper, rapports et exports.
- Chaude piste fiscale : hash-chain transactions/Z reports, export DGFiP, FEC quotidien, verrouillage comptable apres cloture.
- Bonnes briques RGPD : ledger de consentement append-only, suppression differee, anonymisation des transactions, newsletter opt-in, webhook Brevo protege.
- Auth manager avec JWT, rate-limit login et refus de boot prod si `SECRET_KEY` insecure.
- Documentation abondante et scripts de deploiement/sauvegarde/reset go-live.

### Niveau d'urgence

**Urgence elevee avant generalisation ou exploitation multi-utilisateur.** Les corrections prioritaires concernent la confidentialite client, la validation serveur du panier POS, la CI bloquante et la route de caisse courante.

## B. Audit metier

### Adequation fonctionnelle

L'application couvre bien les besoins d'une boutique premium de seconde main :

- Inventaire article par article avec code-barres, photos, statut, zone, genre, score et cycle de vie : `apps/api/app/models/product.py`.
- Encaissement multi-moyens, avoirs, bons, SumUp, tickets, remboursements : `apps/api/app/models/pos.py` et `apps/api/app/api/pos/router.py`.
- CRM, fidelite, segmentation, personal shopper et communications : `apps/api/app/api/crm/router.py`, `apps/api/app/api/crm/account.py`.
- Pilotage : reporting, cahier, KPIs retail/ESS, RFM, SEO, social posts.
- Materiel boutique : imprimantes ticket/etiquette, tiroir, scanner, SumUp.

### Manques ou incoherences metier

1. **Controle manager insuffisant sur operations sensibles.** Les routes POS de vente, remboursement, ouverture/fermeture tiroir et consultation Z reports utilisent `get_current_user`, pas `manager_only` : `apps/api/app/api/pos/router.py:164`, `:648`, `:727`, `:894`, `:2047`. Pour une boutique seule, cela peut etre acceptable ; pour une equipe, cela limite la prevention fraude.

2. **Remises/prix libres sans regle serveur.** Le panier peut envoyer un prix unitaire different du prix catalogue et une remise arbitraire : `CartItem` dans `apps/api/app/api/pos/router.py:41-50`, puis utilisation directe dans `apps/api/app/services/pos.py:117-119`. Il manque une politique : prix catalogue par defaut, remise maximum collaborateur, override manager avec motif.

3. **Gestion client publique trop permissive.** Les pages espace client stockent l'email localement et appellent les routes par `?email=` : `apps/site/src/app/account/page.tsx:60-114`. Cela rend le parcours simple, mais ce n'est pas une preuve d'identite.

4. **Pilotage commercial riche mais tres disperse.** Les modules existent, mais certains fichiers concentrent beaucoup trop de flux : `apps/api/app/api/pos/router.py` fait 2854 lignes, `apps/web/src/app/pos/page.tsx` 3615 lignes. L'ergonomie fonctionnelle risque de devenir couteuse a maintenir.

## C. Audit technique

### Architecture

Architecture monorepo claire : API FastAPI async, deux apps Next.js, Docker prod, Caddy, Redis, PostgreSQL. Le decoupage par domaines est visible, mais plusieurs routers sont devenus monolithiques (`pos`, `admin`, `crm`) et melangent schemas, orchestration, appels externes, email, fiscalite et materiel.

### Dette et maintenabilite

- **Fichiers trop volumineux** : `pos/router.py` 2854 lignes, `admin/router.py` 2583, `crm/router.py` 1585, `web/pos/page.tsx` 3615. Cela augmente les risques de regression et complique les revues.
- **Schema cree au boot** : `Base.metadata.create_all` est encore appele dans `apps/api/app/main.py:50-51`, alors que les migrations Alembic existent. Cela brouille la separation schema prod/migrations.
- **Migrations non rejouables sur base vierge en CI** : la CI note elle-meme que `alembic upgrade head` est indicatif : `.github/workflows/ci.yml:55-60`.
- **CI non bloquante** : `ruff`, `pytest`, `tsc` utilisent `|| true` ou fallback echo : `.github/workflows/ci.yml:52-63`, `:110-114`, `:141-145`.
- **Deploy de production sans dependance CI** : `.github/workflows/deploy.yml:26-28` contient `needs: []`.
- **Route cassee probable** : `/drawer/current` importe des modules inexistants `app.models.payment` et `app.models.transaction` : `apps/api/app/api/pos/router.py:828-830`. Le scan confirme que ces fichiers n'existent pas.

### Securite logicielle

- Positif : `SECRET_KEY` insecure refuse le boot prod : `apps/api/app/core/config.py:108-138`; rate-limit login : `apps/api/app/api/auth/router.py:46-79`; erreurs masquees en prod : `apps/api/app/main.py:126-150`.
- A renforcer : JWT manager stocke en `localStorage` : `apps/web/src/lib/api.ts:28-42`, login admin `apps/web/src/app/login/page.tsx:39-43`. Le token client magic-link est aussi en `localStorage` avec commentaire de migration future vers cookie HttpOnly : `apps/site/src/app/account/login/page.tsx:134-138`.
- Secrets UI en clair sur disque : `data/app_config.json` stocke SumUp/Brevo/SMTP : `apps/api/app/services/app_config.py:57-83`, sauvegarde par dump DB et fichiers persistants a documenter/durcir.

## D. Audit comptable

### Fiabilite encaissements

Points forts :

- `Transaction`, `TransactionItem`, `Payment`, `CashDrawer`, `ZReport` sont modelises : `apps/api/app/models/pos.py`.
- Idempotence vente et remboursement via `client_uuid` : `apps/api/app/services/pos.py:66-77`, `apps/api/app/services/refund.py:140-154`.
- Numerotation transaction via sequence PostgreSQL : `apps/api/app/services/pos.py:159-173`, `apps/api/app/services/refund.py:201-213`.
- Plafond especes avec override manager motive : `apps/api/app/api/pos/router.py:174-246`.
- Remboursement lie a la vente d'origine, avec controle de quantite restante : `apps/api/app/services/refund.py:156-193`.
- FEC quotidien et lignes equilibrees : `apps/api/app/services/accounting_service.py:523-578`.

### Risques comptables

1. **Base comptable depend d'un panier serveur insuffisamment valide.** Si un utilisateur authentifie envoie `unit_price=0.01`, `discount_percent=100` ou quantite negative, le flux comptable peut enregistrer une operation incoherente. Le service TVA sait refuser ces cas (`apps/api/app/services/tva_service.py:101-114`), mais il n'est pas appele par le POS.

2. **TVA multi-taux annoncee mais non appliquee en caisse.** `Product.tva_rate` existe (`apps/api/app/models/product.py:107-114`) et `TransactionItem.tva_rate` aussi (`apps/api/app/models/pos.py:168-174`), mais `PosService.create_transaction` calcule `total_ht = total_ttc / 1.20` et ne renseigne pas `TransactionItem.tva_rate` depuis le produit : `apps/api/app/services/pos.py:150-152`, `:216-228`.

3. **Cloture Z et hash-chain bases sur `created_at`, pas transaction_number.** La verification trie par `created_at` : `apps/api/app/services/fiscal.py:67-80`. Sous concurrence ou corrections horodatage, l'ordre peut diverger de la sequence fiscale. Le hash devrait etre ordonne par `transaction_number`.

4. **Rapport Z non automatiquement verrouille dans le flux de fermeture.** `lock_z_report` existe : `apps/api/app/services/fiscal.py:207-269`, mais `close_drawer` cree le Z report et lance la compta sans appeler ce verrouillage : `apps/api/app/api/pos/router.py:753-793`.

## E. Audit juridique et donnees

### RGPD et donnees personnelles

Points forts :

- Ledger de consentement : `apps/api/app/models/client.py:156-180`.
- Export et suppression/anonymisation RGPD : `apps/api/app/services/rgpd.py:148-228`, `:251-313`.
- Magic-link anti-enumeration pour demande de code : `apps/api/app/services/magic_link.py:124-160`.
- Webhook Brevo refuse si token absent : `apps/api/app/api/brevo/router.py:31-40`.

### Risques juridiques

1. **Acces public aux donnees client par email.** `lookup_client` retourne nom, email, telephone, avoir, fidelite et transactions recentes sans authentification : `apps/api/app/api/crm/router.py:40-114`. `public_account_data_export` retourne l'export RGPD complet par email et le commentaire annonce une future correction : `apps/api/app/api/crm/account.py:297-315`.

2. **Modification publique de droits et preferences par email.** Demande suppression, annulation suppression, consentements, personal shopper, historique cadeau, onboarding et fidelite self-service utilisent l'email sans dependance `get_current_client` : `apps/api/app/api/crm/account.py:317-395`, `:593-668`, `:671-725`.

3. **Principe de minimisation/logs.** L'audit hashe email/telephone mais conserve prenom/nom en clair dans audit logs : `apps/api/app/services/audit.py:99-106`. Cela peut etre justifie, mais doit etre explicite dans registre de traitement et duree de conservation.

4. **Exports CSV/backup sensibles.** Les exports manager sont utiles, mais doivent etre gouvernes : `apps/api/app/api/admin/database.py:123-137` et `apps/api/app/services/database_backup.py:185-237`.

## F. Liste priorisee des anomalies

| # | Criticite | Nature | Impact | Preuve code | Recommandation | Effort |
|---:|---|---|---|---|---|---|
| 1 | Critique | Juridique / securite | Divulgation et modification de donnees client par simple connaissance d'email | `crm/router.py:40-114`, `crm/account.py:297-315`, `:475-630` | Exiger JWT client `get_current_client`; verifier que `sub` correspond au client demande ; garder endpoint email uniquement pour demander un magic-link | Moyen |
| 2 | Critique | Comptable / fraude | Prix, remise ou quantite manipules alimentent tickets, hash, FEC | `pos/router.py:41-50`, `services/pos.py:117-119`, `:154-157` | Contraintes Pydantic (`quantity > 0`, remise 0-100), prix catalogue serveur, override manager audite | Moyen |
| 3 | Majeure | Comptable / fiscal | TVA erronee si multi-taux ou produit hors 20 % | `services/pos.py:150-152`, `models/product.py:107-114`, `tva_service.py:76-138` | Brancher `compute_line_totals` et `aggregate_totals`; figer `TransactionItem.tva_rate` | Moyen |
| 4 | Majeure | Technique / caisse | Etat tiroir courant peut retourner 500 | `pos/router.py:828-830` | Remplacer par imports depuis `app.models.pos`; ajouter test endpoint | Faible |
| 5 | Majeure | DevOps | Erreurs lint/tests/typecheck non bloquantes et deploy independant CI | `.github/workflows/ci.yml:52-63`, `:110-145`, `deploy.yml:26-28` | Supprimer `|| true`, faire rejouer migrations sur DB vierge, `deploy.needs` sur CI ou workflow_run | Moyen |
| 6 | Majeure | Controle interne | Collaborateur peut ouvrir/fermer caisse, rembourser, voir Z sans autorisation fine | `pos/router.py:648`, `:727`, `:894`, `:2047` | Ajouter roles/permissions : cashier, manager, compta, admin ; double validation remboursements/overrides | Moyen |
| 7 | Majeure | Fiscal | Ordre hash-chain base sur `created_at` | `services/fiscal.py:52-57`, `:67-80` | Ordonner par `transaction_number`; inclure plus de champs immuables dans le hash | Moyen |
| 8 | Moyenne | Juridique | Tokens JWT en localStorage exposables par XSS | `web/lib/api.ts:28-42`, `site/account/login/page.tsx:134-138` | Cookies HttpOnly/SameSite ou BFF Next.js ; CSP stricte | Moyen |
| 9 | Moyenne | Technique | Fichiers monolithiques difficiles a maintenir | `wc -l`: POS API 2854, POS page 3615 | Extraire sous-routers/services/hooks par domaine : paiement, drawer, refund, receipt, hardware | Eleve |
| 10 | Moyenne | Ops | Secrets UI persistants en JSON clair | `services/app_config.py:57-83`, `services/hardware_config.py:89-93` | Permissions 600, chiffrement applicatif/KMS, exclusion logs, procedure backup/restauration securisee | Moyen |
| 11 | Moyenne | Documentation | Documentation SumUp contradictoire avec prod-only | `AGENTS.md:60`, `docs/DEPLOIEMENT.md:84-100` | Mettre docs deploy a jour : plus de sandbox/simulation prod ; supprimer endpoints sandbox obsoletes | Faible |
| 12 | Mineure | Qualite | Tests locaux non executables sans dependances installees | Execution locale `python3 -m pytest ...` -> `fastapi` manquant | Fournir bootstrap dev fiable (`pip install -e "apps/api[dev]"` ou uv/venv) et README a jour | Faible |

## G. Plan d'action

### Corrections immediates (0-3 jours)

1. Corriger `/api/pos/drawer/current` (imports POS).
2. Verrouiller les endpoints publics client : toutes les routes qui retournent ou modifient des donnees personnelles doivent exiger un JWT client magic-link.
3. Ajouter validation stricte du panier POS : quantite positive, remise bornee, prix catalogue serveur, paiement total non negatif, refus sur total nul sauf cas explicitement autorise.
4. Rendre la CI bloquante au minimum sur `pytest`, `ruff`, `tsc --noEmit`, et bloquer le deploy si CI rouge.

### Court terme (1-3 semaines)

1. Brancher le calcul TVA multi-taux dans `PosService` et `RefundService`.
2. Revoir les permissions : collaborateur caisse, manager, compta, admin technique.
3. Forcer motif + manager pour remise exceptionnelle, annulation, remboursement CB manuel, ouverture tiroir hors vente.
4. Appeler le verrouillage Z report dans le flux de fermeture ou documenter l'etape obligatoire.
5. Remplacer stockage client `localStorage email + token` par cookie HttpOnly ou appels API Next serveur.

### Refontes structurantes (1-2 mois)

1. Decouper `pos/router.py` en sous-domaines : transactions, drawer, payments, receipts, cashier, vouchers, SumUp, hardware.
2. Decouper `apps/web/src/app/pos/page.tsx` en etats/workflows testables.
3. Passer les migrations Alembic en source unique du schema ; retirer `create_all` du boot prod.
4. Mettre en place un registre RGPD complet : traitements, bases legales, durees, exports, sauvegardes, sous-traitants.
5. Ajouter tests E2E critiques : vente cash/CB, remboursement partiel, avoir, cloture Z, export FEC, espace client magic-link.

### Points a surveiller avant generalisation

- Attestation NF525 humaine a signer et archiver : `docs/COMPLIANCE_NF525.md:10-12`.
- Cohérence documentaire : `README`, `AGENTS.md`, `DEPLOIEMENT.md` divergent encore sur SumUp sandbox/prod-only.
- Sauvegardes : prouver restauration mensuelle, chiffrement stockage et restriction des telechargements backup.
- Audit d'acces : lister qui peut consulter/exporter clients, transactions, backups et FEC.

## Conclusion

VINTIZ est fonctionnellement tres avance pour une boutique de seconde main et possede deja des fondations serieuses de fiscalite et de pilotage. En revanche, l'application ne doit pas etre consideree comme mature au sens controle interne/RGPD tant que les routes publiques client, la validation serveur du POS et la CI bloquante ne sont pas corrigees.

Decision recommandee : **continuer l'exploitation boutique avec vigilance si usage restreint et equipe de confiance ; bloquer toute generalisation multi-boutique ou usage par equipe elargie avant correction des anomalies critiques #1 et #2.**
