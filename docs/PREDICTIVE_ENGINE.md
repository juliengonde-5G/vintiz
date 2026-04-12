# Moteur Prédictif Vintiz — Documentation technique

## Vue d'ensemble

Le moteur prédictif de Vintiz combine plusieurs composantes pour optimiser en continu les performances de la boutique :

1. **Scoring produit** : évaluation objective de chaque article
2. **Checklist hebdomadaire IA** : recommandations actionnables chaque lundi
3. **Tendances mode** : veille automatique des tendances du marché
4. **Personal Shopper** : recommandations personnalisées par client
5. **Météo + corrélation ventes** : adaptation aux conditions locales
6. **Personas IA** : analyses stratégiques (marketing, juridique)

---

## 1. Scoring produit

### Fichier : `apps/api/app/services/scoring_service.py`

### Formule de calcul

Le score total est calculé sur 100 points, avec 6 composantes pondérées :

| Composante | Poids | Score max | Description |
|---|---|---|---|
| Âge en rayon | 30% | 30 pts | Ancienneté depuis `shelf_date` |
| Prix relatif | 20% | 20 pts | Rapport au prix moyen de la catégorie |
| État | 20% | 20 pts | Condition physique de l'article |
| Marque | 15% | 15 pts | Tier de la marque |
| Tendance catégorie | 10% | 10 pts | Popularité de la catégorie |
| Photos | 5% | 5 pts | Qualité visuelle |

### Détail par composante

#### 1.1 Âge en rayon (30%)

```python
if days_on_shelf <= 7:    score = 30   # Nouvelle arrivée — très attractif
elif days_on_shelf <= 21:  score = 25   # Récent
elif days_on_shelf <= 42:  score = 18   # Quelques semaines
elif days_on_shelf <= 84:  score = 10   # 2 mois — attention requise
else:                      score = 3    # Vieux stock — action urgente
```

#### 1.2 Prix relatif à la catégorie (20%)

```python
ratio = sale_price / category_avg_price

if ratio <= 0.70:   score = 20   # Très compétitif (promotion)
elif ratio <= 0.90: score = 18   # Sous le marché
elif ratio <= 1.10: score = 15   # Prix marché
elif ratio <= 1.30: score = 10   # Au-dessus du marché
elif ratio <= 1.50: score = 5    # Cher pour la catégorie
else:               score = 1    # Sur-évalué
```

#### 1.3 État (20%)

| Valeur en base | Score |
|---|---|
| `neuf_etiquette` | 20 |
| `neuf` | 18 |
| `Excellent` / `tres_bon` | 15 |
| `Très bon état` / `bon` | 12 |
| `Bon état` / `Correct` | 10 |
| `correct` | 5 |

#### 1.4 Tier marque (15%)

```python
TIER_1 = {"Sandro", "Maje", "Isabel Marant", "Ba&sh", ...}  # score: 15
TIER_2 = {"Zara", "H&M", "Mango", "COS", ...}               # score: 10
TIER_3 = autre marque connue                                  # score: 7
no_brand = None                                               # score: 5
```

#### 1.5 Tendance catégorie (10%)

Basé sur le score tendance moyen des produits vendus dans cette catégorie ces 30 derniers jours. Valeur de 0 à 10 points.

#### 1.6 Photos (5%)

```python
if photo_url:   score = 5   # Photo présente
else:           score = 0   # Pas de photo
```

### Score total et recommandation

```python
total = age*0.30 + prix*0.20 + etat*0.20 + marque*0.15 + tendance*0.10 + photos*0.05

# Recommandation automatique
if total >= 75:   action = "Mettre en vitrine"     # vert
elif total >= 50: action = "Conserver en rayon"     # bleu  
elif total >= 30: action = "Proposer remise"        # orange
else:             action = "Retirer / démarquer"    # rouge
```

### API

```
GET /api/inventory/products/{id}/score
```

**Réponse** :
```json
{
  "total_score": 72.5,
  "score_age": 25.0,
  "score_prix": 15.0,
  "score_condition": 15.0,
  "score_brand": 15.0,
  "score_category": 10.0,
  "score_photos": 0.0,
  "days_on_shelf": 14,
  "action": "Mettre en vitrine",
  "action_color": "green"
}
```

---

## 2. Checklist hebdomadaire IA

### Fichier : `apps/api/app/api/ai/router.py` — `GET /api/ai/weekly-checklist`

### Déclenchement

- **Manuel** : via le bouton "Actualiser" dans l'interface `/ia-booster`
- **Automatique recommandé** : cron chaque lundi à 07h00

### Logique de génération

```
1. Récupère les 50 produits avec le score tendance le plus bas (EN_STOCK ou EN_VITRINE)
2. Calcule le prix moyen par catégorie
3. Identifie les produits sur-évalués (prix > 1.5x moyenne catégorie)
4. Génère 4 items de checklist :
   - Mise en avant (produits score 30-60 à exposer)
   - Réduction prix (produits sur-évalués)
   - Vitrine de la semaine (recommendation générale)
   - Anticipation commande (vérification niveaux stock)
5. Si ANTHROPIC_API_KEY configuré : enrichit avec un résumé Claude (max 100 mots)
```

### Format de réponse

```json
{
  "week": 15,
  "year": 2026,
  "generated_at": "2026-04-13T07:00:00Z",
  "ai_summary": "Cette semaine, priorité aux blazers et robes d'été...",
  "checklist": [
    {
      "type": "mise_en_avant",
      "priority": "haute",
      "title": "Mettre en avant 3 produits à fort potentiel",
      "description": "Ces produits ont un score tendance modéré mais...",
      "products": [...]
    },
    {
      "type": "reduction_prix",
      "priority": "moyenne",
      "title": "Réduire le prix de 2 produits sur-évalués",
      "products": [{"id": "...", "sale_price": 45, "suggested_price": 33, ...}]
    },
    ...
  ]
}
```

---

## 3. Tendances mode

### Fichier : `apps/api/app/api/ai/router.py` — `GET /api/ai/trends`

### Sources couvertes

| Canal | Données | Fréquence cible |
|---|---|---|
| Réseaux sociaux | Top items, couleurs phares | Hebdomadaire |
| Vinted | Top catégories, évolution prix | Hebdomadaire |
| Retail | Tendances grandes enseignes | Mensuelle |

### Génération IA

Si `ANTHROPIC_API_KEY` est configuré : appel Claude haiku avec prompt contextuel (saison courante, localisation Normandie). Sinon : fallback sur données statiques printemps/été 2026.

---

## 4. Personal Shopper IA

### Fichiers :
- Backend : `apps/api/app/api/crm/router.py` — `GET /api/crm/clients/personal-shopper?email=...`
- Frontend : `apps/site/src/app/espace-client/page.tsx`

### Algorithme de recommandation

```
1. Chargement de l'historique d'achats du client (50 dernières transactions)
2. Analyse des préférences :
   - Marques préférées (top 3 par fréquence)
   - Taille la plus achetée (mode statistique)
   - Catégories préférées (top 3)
3. Scoring des produits EN_STOCK / EN_VITRINE :
   - +30 pts si marque préférée #1
   - +20 pts si marque préférée #2
   - +10 pts si marque préférée #3
   - +8 pts si taille correspond
   - +15/10/5 pts si catégorie préférée #1/2/3
   - +score_tendance × 0.1 pts (bonus qualité)
4. Sélection des 8 meilleurs matches (min score > 0)
5. Si Claude configuré : narrative personnalisée en 2-3 phrases
```

### Format de réponse

```json
{
  "client": {"first_name": "Sophie", "last_name": "Martin"},
  "profile": {
    "preferred_brands": ["Sandro", "Maje", "Ba&sh"],
    "preferred_size": "S",
    "preferred_categories": ["Robe", "Haut femme"]
  },
  "narrative": "Sophie, j'ai sélectionné ces pièces pour toi...",
  "recommendations": [
    {
      "id": "uuid",
      "name": "Robe Sandro — Blanc cassé",
      "brand": "Sandro",
      "size": "S",
      "sale_price": 45.0,
      "category": "Robe",
      "trend_score": 82
    }
  ],
  "generated_at": "2026-04-12T10:00:00Z"
}
```

---

## 5. Intégration météo

### Fichier : `apps/api/app/services/weather_service.py`

### Configuration

```
Ville : Vernon (Normandie)
Coordonnées : lat=49.0937, lon=1.4833
API : OpenWeatherMap (OPENWEATHER_API_KEY)
```

### Endpoints

```
GET /api/admin/weather
```

**Réponse** :
```json
{
  "current": {
    "temp": 17.3,
    "feels_like": 15.8,
    "humidity": 68,
    "description": "nuageux",
    "icon": "04d",
    "wind_speed": 4.2
  },
  "forecast": [
    {"date": "2026-04-13", "temp_min": 12, "temp_max": 19, "description": "ensoleillé", "icon": "01d"}
  ],
  "city": "Vernon"
}
```

### Corrélation météo / ventes (prévue)

L'objectif est d'enrichir les rapports avec une corrélation entre conditions météo et CA journalier, permettant d'anticiper les journées fortes selon la météo prévue.

---

## 6. Personas IA

### Persona Marketing

**Endpoint** : `POST /api/ai/persona/marketing`

Collecte les métriques boutique (stock, score moyen, CA 30j, nb clients) et génère un rapport structuré par un "responsable marketing fictif" avec :
- Analyse de situation
- Points forts / points faibles
- 4 recommandations priorisées
- KPI cibles

### Persona Juridique (RGPD/CNIL)

**Endpoint** : `POST /api/ai/persona/juridique`

Analyse les outils marketing en place et génère un audit de conformité RGPD avec :
- Score de conformité (0-100)
- Points à corriger (classés par urgence)
- Actions prioritaires
- Textes de consentement opt-in prêts à l'emploi
- Liste des mentions légales requises

---

## 7. Automation mensuelle (scoring)

### Endpoint : `POST /api/admin/scoring/monthly-update`

Prévu pour être déclenché le **1er mercredi de chaque mois à 06h00** (APScheduler ou cron Vercel).

Actions effectuées :
1. Recalcul du score tendance pour tous les produits EN_STOCK/EN_VITRINE
2. Mise à jour de `Product.trend_score` en base
3. Retour du nombre de produits mis à jour

```bash
# Test manuel
curl -X POST http://localhost:8000/api/admin/scoring/monthly-update \
  -H "Authorization: Bearer TOKEN"
```

---

## 8. Paramètres de configuration du moteur

| Variable | Valeur | Impact |
|---|---|---|
| `ANTHROPIC_API_KEY` | requis pour IA | Sans clé : données statiques |
| `OPENWEATHER_API_KEY` | requis météo | Sans clé : widget indisponible |
| `STALE_WEEKS` | 4 (défaut) | Seuil produits "stale" |
| TVA | 20% | Calcul fiscal intégré |
| Points fidélité | 1pt = 0,10€ | Valeur point fidélité |
| Loyalty tier seuils | Bronze<100, Silver<200, Gold≥200 | Niveaux fidélité |
