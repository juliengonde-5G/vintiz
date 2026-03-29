# Changelog Vintiz V2

## [0.2.0] - 2026-03-29
### Added
- Frontend PWA back-office (Next.js 14 + Tailwind)
  - Design system Vintiz (Button, Card, Input, Badge, Modal, DataTable)
  - Sidebar navigation avec icones
  - Page login avec auth JWT
  - Dashboard KPIs (CA, stock, transactions, panier moyen)
  - Inventaire : liste produits, creation avec photo, filtres
  - Caisse : scan/saisie, panier, paiement multi-mode, cloture Z
- Module POS backend complet
  - Service encaissement avec TVA 20%
  - Multi-paiement (especes, CB, cheque) avec rendu monnaie
  - Gestion tiroir-caisse (ouverture, cloture, cadrage)
- Conformite fiscale NF525
  - Hash chain SHA-256 sur transactions
  - Generation Z reports immutables
  - Verification integrite chaine
  - Service tickets de caisse
- CRM backend
  - CRUD clients (nom, prenom, tel, email, commune)
  - Systeme de fidelite (activation, solde)
  - Historique achats par client
- Reporting backend
  - Rapports quotidiens, hebdomadaires, mensuels
  - Valorisation du stock
- Script seed data (admin, categories, grille tarifaire, zones boutique)

## [0.1.0] - 2026-03-29
### Added
- Structure monorepo (apps/api, apps/web, apps/site)
- Assets de marque organises (logos, lettrages, etiquettes)
- Page "Ouverture Prochaine" (landing page vintiz.fr)
- Scaffold API FastAPI (modeles, schemas, auth, inventaire)
- Infrastructure Docker (PostgreSQL, Redis, API, Web, Site)
- Documentation architecture
