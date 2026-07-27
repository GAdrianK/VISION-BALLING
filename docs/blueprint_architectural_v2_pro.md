# BLUEPRINT ARCHITECTURAL : PLATFORME FOOTBALL IQ ASSISTANT (V2 PRO)
## Système Hybride de Big Data : RAG Sémantique & Event Data Quantitatif

**Auteur :** Ingénierie Logicielle & Analyse Tactique Élite  
**Date de publication :** Juin 2026

---

## 1. Vision Stratégique & Concept Hybride

Pour passer d'un prototype de RAG de 20 matchs à une infrastructure industrielle capable d'absorber des dizaines de milliers de matchs (multi-championnats, plusieurs saisons), la dépendance exclusive aux textes bruts doit être supprimée.

Le **Modèle Hybride Parfait** sépare et fait converger deux types de données :
* **Le Quantitatif (L'Événementiel / Event Data) :** Données atomiques structurées (coordonnées X/Y, passes, tirs, pressions, xG, xA). Stocké dans une base relationnelle pour des agrégations instantanées à l'échelle de la saison.
* **Le Qualitatif (Le Contextuel / Textual Data) :** Comptes-rendus, notes de scouts, consignes tactiques du coach. Stocké sous forme de vecteurs condensés pour l'extraction de philosophie de jeu.

---

## 2. Architecture Globale du Système

```
                           [ FLUX DE DONNÉES EN ENTRÉE ]
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
         [ RAPPORTS TEXTUELS (.md) ]               [ EVENT DATA BRUT (JSON/Scraping) ]
                    │                                         │
                    ▼                                         ▼
         (LLM Chunking & Parsing)                  (Data Processing & Analytics)
                    │                                         │
                    ▼                                         ▼
       ┌─────────────────────────┐               ┌─────────────────────────┐
       │   BASE VECTORIELLE      │               │    BASE RELATIONNELLE   │
       │       (Qdrant)          │               │      (PostgreSQL)       │
       ├─────────────────────────┤               ├─────────────────────────┤
       │ Résumés tactiques macro │               │ Stats froides cumulées  │
       │ Profils de jeu textuels │               │ Métriques (xA, xG, PPDA)│
       └─────────────────────────┘               └─────────────────────────┘
                    │                                         │
                    └────────────────────┬────────────────────┘
                                         ▼
                            [ ENGINE DE RECHERCHE HYBRIDE ]
                                         │
                                         ▼
                             [ LLM ORCHESTRATEUR (Gemini) ]
                                         │
                                         ▼
                            [ RAPPORT TACTIQUE GLOBAL PRO ]
```

---

## 3. Les Deux Pipelines d'Ingestion (ETL Automatisé)

### A. Pipeline Quantitatif : Scraper de Données (FBref / Opta)
Le système n'attend plus de saisie manuelle. Un worker asynchrone (ex: via FastAPI + Celery) tourne en tâche de fond après chaque journée de championnat.
1. **Extraction :** Un script basé sur Playwright ou Scrapy extrait les tableaux de statistiques du match (ex: fiches de matchs de FBref).
2. **Transformation :** Normalisation des métriques complexes (Conversion des temps de jeu, standardisation des noms de joueurs).
3. **Chargement :** Insertion immédiate dans une base relationnelle indexée.

### B. Pipeline Qualitatif : Le RAG Hiérarchique (Génération de fiches)
Pour éviter de saturer la mémoire sémantique, chaque compte-rendu textuel brut subit une réduction de dimension logique assurée par l'IA avant son indexation :

```python
# Exemple conceptuel du worker d'ingestion qualitatif
def ingest_match_narrative(raw_text: str):
    prompt = "Analyse ce compte-rendu brut et génère une fiche tactique standardisée au format JSON."
    # Gemini condense le match en 1 chunk ultra-dense
    structured_summary = gemini_client.generate(prompt + raw_text, response_schema=MatchSummarySchema)
    
    # Stockage du chunk unique et qualitatif dans Qdrant
    qdrant_client.upsert(
        collection_name="psg_season_summaries",
        points=[PointStruct(id=match_id, vector=get_embedding(structured_summary), payload=structured_summary)]
    )
```

---

## 4. Modélisation des Bases de Données

Pour garantir des performances optimales sur 500 matchs et 1 000 joueurs, les structures de données sont réparties de manière étanche.

### Table Relationnelle (PostgreSQL) : `player_match_stats`
Cette table stocke la performance chiffrée pure. Chaque ligne représente le match d'un joueur.

| Colonne | Type | Description / Rôle |
| :--- | :--- | :--- |
| `match_id` | VARCHAR(50) (PK) | Identifiant unique de la rencontre |
| `player_name` | VARCHAR(100) (PK) | Nom du joueur (ex: "Ousmane Dembélé") |
| `minutes_played` | INT | Temps de jeu effectif |
| `goals` | INT | Buts marqués |
| `expected_goals` | FLOAT | Qualité des tirs pris par le joueur ($xG$) |
| `expected_assists` | FLOAT | Qualité des passes clés délivrées ($xA$) |
| `key_passes` | INT | Passes leading directly to a shot |
| `progressive_dribbles` | INT | Dribbles moving the block forward by more than 10 meters |
| `defensive_pressures` | INT | High-intensity pressing actions |

### Collection Vectorielle (Qdrant) : `tactical_context`
Cette collection stocke l'ambiance et la philosophie. Elle ne contient qu'un seul vecteur par match.
* **Vecteur (1536 dim) :** Représentation sémantique du style de jeu global du match.
* **Payload (Métadonnées) :**
```json
{
  "match_id": "2025_01_22_psg_mancity",
  "opposition": "Manchester City",
  "tactical_setup": "Bloc haut, contre-pressing agressif",
  "weaknesses_exposed": "Espace dans le dos des latéraux lors des transitions rapides",
  "individual_notes": "Dembélé a totalement dicté le tempo en zone 14, Barcola a fixé la ligne de 4."
}
```

---

## 5. Le Moteur de Requête Hybride (L'Intelligence Logique)

Quand l'utilisateur pose une question à grande échelle (*« Fais-moi le bilan de la saison de Dembélé »*), le point d'accès du backend (`/api/trends`) exécute une routine en deux temps, appelée **Récupération Composée**.

### Étape 1 : L'extraction mathématique (SQL)
L'orchestrateur demande d'abord à la base PostgreSQL de compiler et calculer instantanément les moyennes de la saison complète sur l'ensemble des 50 matchs.
```sql
SELECT 
    player_name,
    SUM(goals) as total_goals,
    SUM(key_passes) as total_key_passes,
    AVG(expected_assists) as avg_xA,
    SUM(progressive_dribbles) as total_dribbles
FROM player_match_stats
WHERE player_name = 'Ousmane Dembélé' AND season = '24-25'
GROUP BY player_name;
```

### Étape 2 : L'extraction contextuelle (Qdrant)
En parallèle, le moteur interroge Qdrant pour récupérer les fiches des 15 matchs les plus intenses ou complexes de la saison pour comprendre le style de Dembélé lors des grands rendez-vous.

### Étape 3 : La fusion dans Gemini
Le prompt final envoyé à `gemini-flash-latest` réunit les deux mondes. L'IA n'a plus besoin d'essayer de deviner les statistiques : elles lui sont servies sur un plateau d'argent par le SQL, pendant que le RAG lui donne les arguments tactiques narratifs.

---

## 6. Feu de Route de Déploiement Long Terme

* **Mois 1 - 2 : Migration de la Base de Données (Phase Fondations)**
  Mise en place de l'instance PostgreSQL en parallèle de Qdrant. Création du modèle objet relationnel avec SQLAlchemy. Développement du système de Singleton unifié pour gérer la connexion simultanée aux deux bases sans créer de verrous de threads.
* **Mois 3 - 5 : Automatisation complète de l'ETL (Phase Data Pipeline)**
  Développement des scripts de web scraping asynchrones (Playwright) pour extraire de manière hebdomadaire les statistiques froides depuis les bases publiques (FBref). Intégration de la routine de résumé automatique des matchs par Gemini avant l'indexation vectorielle.
* **Mois 6 - 8 : Refonte du Moteur de Requête Hybride (Phase Intelligence)**
  Développement du routeur sémantique dans `trend_engine.py`. Capacité du serveur à traduire une question utilisateur en une requête SQL combinée à un scan vectoriel Qdrant. Phase d'optimisation des temps de réponse sous la barre des 800 millisecondes.
* **Mois 9 - 12 : Frontend Analytics & Dashboarding (Phase Déploiement)**
  Ajout de l'interface visuelle complète : graphiques en radar pour comparer l'impact des attaquants (Buts vs xA vs Pressing), courbes d'évolution de la forme de l'équipe et fiches de scouting automatisées exportables en un clic.

---

> [!TIP]
> **Règle d'or pour le futur :** La donnée textuelle doit servir à expliquer le **pourquoi**, la donnée statistique doit servir à prouver le **quoi**. En maintenant cette séparation stricte dans ton code, ton application pourra absorber 10 ans d'histoire du football sans jamais perdre une seule seconde d'analyse.
