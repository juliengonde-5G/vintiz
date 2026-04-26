# Benchmark IA 2026-05 — Claude vs alternatives

> **Date** : mai 2026
> **Branche** : `claude/structure-shop-app-3pbeo`
> **Statut** : infrastructure prête, exécution à programmer
> **Objectif** : valider que Claude reste le bon choix pour les 7 cas
> d'usage Vintiz, ou identifier un meilleur rapport pertinence/coût/latence.

---

## §1 — Méthodologie

### 7 prompts testés
| Prompt | Usage Vintiz | Modèle Claude actuel |
|---|---|---|
| `vision_intake` | Extraction 15 attributs depuis photo | claude-sonnet-4-20250514 |
| `personal_shopper` | Reco narrative cliente | claude-haiku-4-5 |
| `store_mapping` | Reco placement zone + démarque | claude-sonnet-4-20250514 |
| `window_display` | Sélection vitrine semaine | claude-haiku-4-5 |
| `pricing_decision` | Décision démarque pièce limite | claude-haiku-4-5 |
| `social_posts` | 4 posts RS / semaine | claude-haiku-4-5 |
| `review_reply` | Réponse avis Google | claude-haiku-4-5 |

### 4 modèles concurrents
| Provider | Modèle | Pourquoi le tester |
|---|---|---|
| **Anthropic Haiku** | claude-haiku-4-5 | Référence — texte rapide |
| **Anthropic Sonnet** | claude-sonnet-4-20250514 | Référence — vision + raisonnement |
| **Mistral Large 2** | mistral-large-latest | RGPD friendly (cloud français) |
| **GPT-4.1 mini** | gpt-4.1-mini | Rapport coût/perf |
| **Gemini 2.5 Flash** | gemini-2.5-flash | Contexte long, multimodal |

### 20 cas par prompt
Inputs réels anonymisés tirés de la base seed Vernon
(produits + clientes + transactions + zones + avis Google).

### Métriques mesurées par appel
- **Latence** p50, p95
- **Tokens** in / out
- **Coût USD** (tarification publique octobre 2025, à actualiser)
- **Validité format** : JSON valide ? schéma respecté ?
- **Score qualité subjective** (rubrique L5.2 — humain)

---

## §2 — Rubrique de notation qualité

Notée 0-5 par 2 humains à l'aveugle (Camille manager + Léa employée).

### Pour `personal_shopper`
- **Personnalisation** : utilise les données cliente fournies ?
- **Pertinence boutique** : mentionne des produits réels du contexte ?
- **Ton** : chaleureux + professionnel sans excès ?
- **Concision** : 4-6 phrases, pas plus ?

### Pour `vision_intake`
- **Couverture** : 15 champs présents ?
- **Précision marque** : correctement détectée si visible ?
- **Précision état** : cohérent avec photo ?
- **Honnêteté** : utilise null au lieu d'halluciner ?

### Pour `store_mapping`
- **Actionable** : recommandations concrètes vs vagues ?
- **Justification** : chaque reco a une raison ?
- **Faisabilité** : mouvement physique réaliste ?
- **Diversité** : pas la même reco répétée ?

### Pour `window_display`
- **Cohérence thème** : palette + style alignés ?
- **Saisonnalité** : adapté à la période ?
- **Faisabilité** : produits réellement en stock ?
- **Diversité** : mix de styles dans les 6 pièces ?

### Pour `pricing_decision`
- **Précision décision** : action argumentée vs arbitraire ?
- **Conservatisme** : ne démarque pas ce qui peut encore vendre ?
- **Cohérence règles** : aligné avec markdown_engine ?

### Pour `social_posts`
- **Structure** : 4 catégories obligatoires (PRODUIT_STAR / VALEURS / TEMOIGNAGE / ACTU) ?
- **Hashtags** : ≤ 8 et pertinents ?
- **Ton** : aligné avec brand voice Vintiz ?
- **Engageant** : appelle à l'action ?

### Pour `review_reply`
- **Personnalisation** : mentionne 1 détail spécifique de l'avis ?
- **Ton adapté** : chaleureux 5★, dialogique 3-4★, sincère 1-2★ ?
- **Longueur** : 3-5 phrases ?
- **Pas de générique** : évite les formules toutes faites ?

---

## §3 — Scoring global

Pour chaque (prompt × modèle), un score composite [0, 100] :
```
qualité_norm = avg(score_qualité) / 5 × 100   [0..100]
latency_score = max(0, 100 - latency_p50_ms / 50)   [0..100]
cost_score = max(0, 100 - cost_per_call_eur × 1000)   [0..100]

score_global = 0.6 × qualité_norm + 0.2 × latency_score + 0.2 × cost_score
```

Le modèle **gagnant par prompt** = celui avec le score_global le plus élevé.

---

## §4 — Exécution

```bash
# Variables nécessaires :
export ANTHROPIC_API_KEY=sk-ant-...
export MISTRAL_API_KEY=...        # optionnel
export OPENAI_API_KEY=...         # optionnel
export GEMINI_API_KEY=...         # optionnel

# Lancement complet :
python scripts/ai_benchmark.py

# Subset :
python scripts/ai_benchmark.py --prompts personal_shopper,vision_intake
python scripts/ai_benchmark.py --providers anthropic_haiku,mistral_large
```

Sortie : `scripts/output/ai_benchmark_results.json`.

---

## §5 — Résultats

> **Statut** : à compléter après exécution. Le script produit
> automatiquement les agrégats latence / coût / token. Le score qualité
> humain doit être saisi manuellement dans une feuille Excel partagée
> entre Camille et Léa.

### Tableau récapitulatif (template à remplir)

| Prompt | Modèle | n_ok / 20 | p50 ms | p95 ms | Avg cost $ | Qualité 0-5 | Score global |
|---|---|---|---|---|---|---|---|
| personal_shopper | anthropic_haiku | — | — | — | — | — | — |
| personal_shopper | mistral_large | — | — | — | — | — | — |
| personal_shopper | gpt-4.1-mini | — | — | — | — | — | — |
| personal_shopper | gemini_flash | — | — | — | — | — | — |
| ... | ... | ... | ... | ... | ... | ... | ... |

---

## §6 — Recommandation finale

> **À compléter** après scoring complet. Format attendu :
>
> - **Conserver** Claude pour : (liste des prompts où Claude reste gagnant)
> - **Basculer** sur (autre provider) pour : (liste des prompts où le challenger gagne)
> - **Plan de migration** : 2 prompts max à la fois pour rollback facile
>   via `PUT /api/admin/ai-routing`

### Décision-type

Si Claude gagne sur 6 prompts sur 7 :
- Garder Claude tel quel
- Documenter le 7ème comme "à surveiller à 6 mois"

Si un challenger (Mistral / GPT / Gemini) gagne nettement sur 2-3 prompts :
- Basculer ces prompts via `ai_router` (clé `app_settings.ai_routing`)
- Conserver Claude pour les autres
- Re-tester dans 6 mois (modèles évoluent)

---

## §7 — Infrastructure mise en place

### Service `apps/api/app/services/ai_router.py`
- Lit la table de routage depuis `app_settings.ai_routing`
- `call_with_routing(prompt_name, user_message, ...)` route vers le provider configuré
- Fallback automatique sur Anthropic puis sur fallback déterministe service
- Log de chaque appel (provider, model, latency, tokens, cost)

### Endpoints admin
- `GET /api/admin/ai-routing` — voir routage courant
- `PUT /api/admin/ai-routing` — modifier routage par prompt

### Garde-fous
- Conservation des **fallbacks déterministes** dans chaque service
  (déjà en place pour PS et Vision)
- **Quota mensuel** par provider configurable (clé
  `app_settings.ai_quota_monthly_eur`) avec coupure automatique +
  bascule fallback (TODO — à implémenter quand utile)

### Migration progressive
1. Run `scripts/ai_benchmark.py` avec toutes les clés posées
2. Saisir les scores qualité humains dans un Google Sheets dédié
3. Mettre à jour ce document `§5 Résultats`
4. Décider la nouvelle table de routage
5. `PUT /api/admin/ai-routing` avec la table validée
6. Surveiller events log + métriques business 2 semaines avant nouvelle bascule

---

**Fin du document** — à mettre à jour après chaque run de benchmark.
