# Procès-verbal de recette — Vintiz 1.1.1

> Version candidate NF525 — ce document ne constitue pas un certificat.

## 1. Identification

| Élément | Valeur constatée |
|---|---|
| Date du contrôle automatisé | 16/07/2026 10:38 (Europe/Paris) |
| Environnement | Production — `https://api.vintiz.fr` |
| Version applicative | 1.1.1 |
| Build Git | `6081ec0` |
| Révision base | 0072 |
| Signature fiscale | v2 |
| Script | `scripts/smoke_prod.sh` |

## 2. Résultat automatisé

Commande exécutée depuis une machine extérieure au VPS :

```bash
VINTIZ_EXPECTED_BUILD_SHA=6081ec0 \
  bash scripts/smoke_prod.sh https://api.vintiz.fr
```

Résultat : **30 OK, 0 KO, 1 contrôle manager non exécuté faute de jeton**.

Les contrôles réussis couvrent :

- disponibilité HTTPS de l'API ;
- version, build, révision DB et version de signature fiscale ;
- présence des routes POS, CRM, rapports et clôtures fiscales dans OpenAPI ;
- protection JWT des données clientes (`401` sans jeton) ;
- fonctionnement public du magic-link anti-énumération ;
- disponibilité de la sélection éditoriale anonyme.

## 3. Complément automatisé avec jeton manager

À exécuter sans enregistrer le jeton dans un fichier ou dans Git :

```bash
read -rs VINTIZ_API_TOKEN
export VINTIZ_API_TOKEN
bash scripts/smoke_prod.sh https://api.vintiz.fr
unset VINTIZ_API_TOKEN
```

Résultat attendu : aucun contrôle ignoré, aucun échec. Joindre la sortie au
dossier de recette en masquant le jeton.

## 4. Recette terrain boutique

Chaque cas doit être réalisé avec des produits de recette identifiés, puis
rapproché du ticket, de la fiche transaction et du rapport Z. Ne jamais altérer
directement la base de production.

| ID | Cas | Résultat attendu | Preuve à conserver | Statut |
|---|---|---|---|---|
| POS-01 | Ouverture de caisse par un opérateur identifié | Fond initial et caissier tracés | Capture caisse + heure | ☐ |
| POS-02 | Vente espèces avec rendu | Encaissé, rendu et total fiscal distincts ; ticket correct | N° transaction + ticket | ☐ |
| POS-03 | Vente CB SumUp | Vente créée uniquement après statut SumUp `PAID` et montant identique | N° transaction + référence SumUp | ☐ |
| POS-04 | CB refusée ou annulée | Aucune vente fiscale créée | Capture erreur + journal SumUp | ☐ |
| POS-05 | Paiement mixte espèces/CB | Somme des moyens égale au TTC ; rendu cohérent | Ticket + références | ☐ |
| POS-06 | Facture client professionnel | Numéro unique et mentions client présentes | PDF ou impression | ☐ |
| FID-01 | Vente de 100 € intégralement éligible | +100 points et chèque cadeau de 5 € généré | Compte fidélité + code masqué | ☐ |
| FID-02 | Article soldé, promotion ou remise | Aucun point sur la ligne exclue | Détail vente + mouvement points | ☐ |
| FID-03 | Paiement par chèque cadeau fidélité | Débit de 5 € maximum, bon désactivé atomiquement | Ticket + état coupon | ☐ |
| FID-04 | Tentative de réutilisation du même bon | Refus sans modifier la vente | Capture du refus | ☐ |
| REF-01 | Remboursement partiel | Avoir/remboursement lié à l'original et points repris au prorata | Deux n° de transaction | ☐ |
| REF-02 | Remboursement CB échoué chez SumUp | Aucun remboursement local validé | Référence SumUp + journal | ☐ |
| NF-01 | Fermeture caisse et rapport Z | Totaux ventes/remboursements/moyens cohérents | Rapport Z signé | ☐ |
| NF-02 | Contrôle d'intégrité | Chaînes transactions, Z et clôtures déclarées valides | Réponse endpoint + date | ☐ |
| NF-03 | Export fiscal de la journée | Export lisible, bornes et totaux rapprochés du Z | JSON/XML archivé | ☐ |
| NF-04 | Archive périodique sur environnement de recette | SHA-256 vérifié après téléchargement et décompression | Archive + hash + manifest | ☐ |
| OPS-01 | Ticket réseau ou WebUSB | Impression complète et ouverture tiroir si configurée | Ticket papier signé | ☐ |
| OPS-02 | Étiquette Zebra | ZPL/impression et code-barres lisible | Étiquette signée | ☐ |
| IA-01 | Personal Shopper avec membre consentant | Recommandations en stock, genre/taille respectés | Capture + IDs produits | ☐ |
| IA-02 | Personal Shopper sans consentement | Accès bloqué et CTA de consentement | Capture | ☐ |

## 5. Tests hors production obligatoires

Sur une restauration isolée de la base :

1. tenter de modifier puis supprimer une vente signée, une ligne, un paiement,
   un Z et une clôture ; les triggers doivent refuser l'opération ;
2. altérer une copie d'archive et vérifier que le contrôle SHA-256 échoue ;
3. restaurer une sauvegarde complète et contrôler les chaînes fiscales ;
4. mesurer le temps de restauration et consigner l'opérateur, la date et le
   support utilisé.

## 6. Signatures

| Rôle | Nom | Date | Signature | Réserves |
|---|---|---|---|---|
| Responsable boutique |  |  |  |  |
| Responsable sécurité/technique |  |  |  |  |
| Référent comptable |  |  |  |  |

Toute anomalie doit référencer l'ID du cas, le numéro de transaction concerné,
l'heure, le caissier, le comportement attendu et le comportement constaté.
