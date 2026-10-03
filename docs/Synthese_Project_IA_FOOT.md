# ⚽ Dossier de Synthèse : Football IQ Assistant (MVP & V2 PRO)

> **Statut : historique / non normatif.** Cette synthèse conserve le contexte du prototype initial. L'état courant est décrit dans [`../README.md`](../README.md) et [`project_status.md`](project_status.md).

Ce dossier rassemble l'ensemble des concepts tactiques, des solutions d'ingénierie et des perspectives d'évolution du projet **Football IQ Assistant** pour vous préparer au mieux à votre entretien de recrutement.

Le PDF correspondant a été compilé avec succès et est disponible à l'emplacement suivant :  
👉 [Synthese_Projet_IA_FOOT.pdf](Synthese_Projet_IA_FOOT.pdf)

---

## 🎯 1. Fiche d'Identité du Projet

* **Nom du Projet** : Football IQ Assistant (Football Intelligence Core)
* **Description** : Assistant tactique de football d'élite s'appuyant sur un moteur de RAG (Retrieval-Augmented Generation) local et une architecture hybride.
* **Problématique Clé** : Aider les staffs techniques (entraîneurs, analystes) et vulgariser le jeu pour les passionnés en s'ancrant exclusivement dans un corpus de connaissances documentaires vérifiées (24 documents tactiques, 268 chunks) pour éliminer les hallucinations.
* **Stack Technique MVP** :
  * **Backend** : FastAPI (Python 3.10+), SQLite (stockage relationnel & parents).
  * **Vector Engine** : Qdrant (en mémoire `:memory:`) + fallback lexical BM25 (Rank-BM25).
  * **LLM Orchestrator** : Qwen 2.5 (72B via OpenRouter) et Gemini (Google GenAI) pour la génération structurée (`Structured Outputs` avec Pydantic).
  * **Reranking** : FlashRank (léger et ultra-rapide en local).
  * **Frontend** : SPA (Single Page Application) Vanilla Javascript, design premium responsive Dark Mode (Cyber Obsidian).

---

## 🏗️ 2. Architecture Technique Détaillée (MVP V1)

Le pipeline d'intelligence tactique sépare les données pour optimiser le contexte et la vitesse de recherche :

```
                           [ REQUÊTE UTILISATEUR ]
                                      │
                                      ▼
                      [ FASTAPI BACKEND /api/chat ]
                                      │
                                      ▼
               [ QUERYCLASSIFIER: CLASSIFICATION & EXTRACTION ]
                                      │
                                      ▼
                      [ RAGENGINE: HYBRID RETRIEVAL ]
                                      │
                ┌─────────────────────┴─────────────────────┐
                ▼                                           ▼
      [ QDRANT: SEMANTIC ]                        [ BM25: LEXICAL ]
                │                                           │
                └─────────────────────┬─────────────────────┘
                                      ▼
                        [ FUSION & PONDÉRATION ]
                                      │
                                      ▼
                           [ RERANKING: FLASHRANK ]
                                      │
                                      ▼
                      [ SQLITE: RÉSOLUTION PARENT ]
                                      │
                                      ▼
                        [ CONTEXTE TACTIQUE RÉSOLU ]
                                      │
                                      ▼
                      [ LLM ORCHESTRATOR: QWEN/GEMINI ]
                                      │
                                      ▼
                        [ STRUCTURED OUTPUT: PYDANTIC ]
                                      │
                                      ▼
                       [ RÉPONSE: COACH / ANALYSTE / FAN ]
```

### Les 5 Piliers du Pipeline MVP
1. **Ingestion & ETL Déterministe** : 
   * Découpage du corpus de documents Markdown via `MarkdownHeaderSplitter`.
   * En-tête YAML structuré (`topic`, `intent`, `phase`, `level`, `keywords`) lu à l'ingestion pour annoter les chunks.
2. **Stockage Hiérarchique (Parent-Enfant)** :
   * Les **chunks enfants** (courts et sémantiquement homogènes) sont indexés dans **Qdrant** pour une recherche vectorielle ultra-rapide.
   * Les **documents parents** (complets et structurés) sont conservés dans **SQLite**. Une fois le chunk enfant trouvé, le document parent complet est extrait pour donner au LLM un contexte global sans coupure.
3. **Moteur Hybride RAG** :
   * **Recherche Sémantique** : Vectorisation locale (via TF-IDF locale) ou en ligne (OpenAI Embeddings).
   * **Recherche Lexicale** : Algorithme BM25 customisé pour capturer les mots du terrain très spécifiques.
   * **Reranker Local** : FlashRank réduit les 20 candidats initiaux aux 3 plus pertinents pour préserver la fenêtre de contexte.
4. **Structured Outputs & Personas** :
   * FastAPI utilise les schémas Pydantic stricts pour structurer les réponses de l'API `/api/analyze` sous forme de fiches à 10 piliers tactiques.
   * Les prompts système dynamiques (`coach_prompt.txt`, `analyst_prompt.txt`, `fan_prompt.txt`) adaptent le ton et la structure (ex: le Coach donne des consignes et des exercices, l'Analyste est clinique et objectif, le Fan utilise du jargon vulgarisé).
5. **Ressources Offline Résilientes** :
   * Si la clé API est absente ou si le réseau échoue, le système bascule de manière transparente sur un **fallback local déterministe** : recherche TF-IDF locale + moteur de génération simulé reconstituant des exercices et consignes à partir des sources textuelles brutes du RAG.

---

## 🛠️ 3. Zoom Innovation : Le "Problem-Oriented Retrieval"

### Le Problème : Le Biais de Dominance Lexicale (TF-IDF/Vector Bias)
Dans un RAG traditionnel, si un utilisateur saisit :
> *« Je joue en 4-3-3 mais mon équipe perd trop de ballons à la relance. »*

Le moteur renvoie en premier la fiche descriptive de la formation (`formation_433.md`) au lieu de la fiche qui résout le problème de terrain (`sortie_balle.md`).
* **Pourquoi ?** Le terme sémantique `4-3-3` a un IDF très élevé (car rare globalement) et un TF élevé dans le document de formation. Le système traite tous les mots à l'horizontal sans comprendre que `4-3-3` est un **contexte secondaire**, tandis que la `perte à la relance` est le **problème principal**.

### La Solution Algorithmique Développée
Nous avons implémenté une recherche sémantique structurée et pondérée :
1. **Extraction de Structure Intermédiaire** : Le `QueryClassifier` utilise des regex et un lexique tactique pour extraire :
   * `System` : La formation mentionnée (`4-3-3`).
   * `Problem` : Le point de douleur (`pertes de balle`).
   * `Phase` : La phase de jeu (`relance`).
   * `Goal` : L'objectif (`corriger`/`améliorer`).
2. **Formule de Scoring Hybride** :
   $$S_{final} = 0.9 \cdot S_{problem\_phase} + 0.1 \cdot S_{system\_context}$$
   * Les mots-clés du problème et de la phase reçoivent un bonus fort (jusqu'à **+0.75**).
   * La formation ne reçoit qu'un léger bonus de contexte de **+0.10**.
3. **Pénalité Anti-Biais Tactique (Reinforcement Négatif)** :
   * Si la requête comporte un problème identifié, le moteur applique une **pénalité de -0.50** à tous les documents d'explication de formation pure (ceux commençant par `formation_`).
   * **Résultat** : La fiche opérationnelle (`sortie_balle.md`) remonte instantanément en tête de liste sémantique.

---

## 🚀 4. La Vision Future : L'Architecture V2 PRO

Pour faire passer le projet d'une dizaine de matchs à une plateforme industrielle capable d'absorber des milliers de rencontres de Ligue 1 et de Ligue des Champions, nous avons conçu l'architecture **V2 PRO (Système Hybride de Big Data)**.

### Le Concept : Séparer le Quantitatif et le Qualitatif
* **Le Quantitatif (L'Événementiel / Event Data)** : Stats brutes, coordonnées X/Y, passes, tirs, pressions, xG, xA cumulés. Stocké dans une base relationnelle (**PostgreSQL**).
* **Le Qualitatif (Le Contextuel / Textual Data)** : Rapports tactiques, notes de scouts, consignes de jeu. Stocké sous forme de vecteurs dans **Qdrant**.

### Le Pipeline d'Ingestion (ETL Automatique)
* Un worker asynchrone (FastAPI + Celery) tourne en tâche de fond après chaque journée.
* **Extraction** : Scraper asynchrone avec **Playwright** pour extraire les fiches de matchs de FBref.
* **Transformation & Chargement** : Normalisation des données dans PostgreSQL.
* **Résumé LLM** : Gemini condense le compte-rendu brut d'un match en une unique fiche tactique structurée JSON (pour éviter de polluer la mémoire sémantique avec 10 chunks par match) avant de l'envoyer dans Qdrant.

### Le Moteur de Requête Hybride (Récupération Composée)
Lorsqu'un utilisateur demande : *« Fais-moi le bilan de la saison d'Ousmane Dembélé »* :
1. Le routeur sémantique traduit la question en requête SQL SQLite/PostgreSQL pour compiler instantanément les moyennes froides (ex: passes clés, dribbles progressifs, minutes jouées).
2. En parallèle, il interroge Qdrant pour récupérer les notes qualitatives sur les matchs clés.
3. Les deux flux de données sont injectés dans le LLM (Gemini) qui produit une synthèse combinée : **les statistiques prouvent le *quoi*, le sémantique explique le *pourquoi*.**

---

## 🗺️ 5. Feu de Route de Déploiement (12 Mois)

* **Mois 1 - 2 : Migration de la Base de Données (Phase Fondations)**
  * Mise en place de PostgreSQL en parallèle de Qdrant.
  * Création des modèles SQLAlchemy.
  * Implémentation du pattern Singleton unifié pour la connexion simultanée sans verrous.
* **Mois 3 - 5 : Automatisation complète de l'ETL (Phase Data Pipeline)**
  * Développement des scrapers Playwright.
  * Routine LLM de résumé automatique des matchs avant indexation vectorielle.
* **Mois 6 - 8 : Refonte du Moteur de Requête Hybride (Phase Intelligence)**
  * Implémentation du compilateur Text-to-SQL combiné au scan vectoriel dans `trend_engine.py`.
  * Optimisation des performances pour descendre sous la barre des 800 ms.
* **Mois 9 - 12 : Frontend Analytics & Dashboarding (Phase Déploiement)**
  * Intégration de graphiques en radar comparatifs d'ADN tactique, courbes de forme et exports PDF automatisés.

---

## 🎓 6. Guide Pratique pour briller en Entretien

### 1. Le Pitch de 2 minutes (L'Accroche)
> *« J'ai développé Football IQ Assistant, une plateforme d'intelligence tactique conçue pour aider les staffs professionnels à analyser le jeu et préparer leurs séances d'entraînement. Plutôt que de faire un simple chatbot RAG basique, je me suis confronté à deux défis majeurs d'ingénierie : premièrement, résoudre le biais lexical inhérent aux systèmes de jeu par rapport aux problèmes réels du terrain en créant un algorithme RAG orienté problème pondéré. Deuxièmement, concevoir une vision V2 PRO hybride pour coupler les statistiques d'événements (xG, xA issues de bases relationnelles) avec l'analyse de texte sémantique (comptes-rendus dans Qdrant) pour offrir des rapports complets associant chiffres et contexte. »*

### 2. Comment défendre vos choix d'architecture ?
* **Qdrant (In-Memory)** : Choisi pour le MVP afin de valider l'indexation de similarité en local sans coûts d'infrastructure, facilement scalable vers Qdrant Cloud.
* **SQLite** : Parfait pour le stockage local du MVP car il offre des performances relationnelles immédiates en local, ce qui facilite la jointure parent-enfant et l'analyse de données sans latence réseau.
* **Le Fallback Offline (TF-IDF)** : C'est l'argument de robustesse. En production, un appel API ou internet peut couper. Montrez que vous y avez pensé en mettant en place un RAG 100% autonome en local qui extrait le contenu textuel structuré directement en local en cas de panne.

### 3. Comment valoriser l'audit et la correction de bug ?
Expliquez que vous avez audité la suite de tests et l'API de chat. Vous avez identifié que l'importation de `rag_engine` depuis `app.main` échouait car l'initialisation de ce singleton manquait dans `app/main.py`.
* **La résolution implémentée** : Nous avons résolu cette anomalie en initialisant proprement le singleton `rag_engine` dans `app/main.py` et en adaptant la suite de tests unitaires pour mocker les requêtes API externes afin de permettre des tests hors-ligne stables. **Résultat : la suite de tests est passée de 5 erreurs à 100% de succès (20/20 tests au vert).** C'est un excellent point de storytelling pour valoriser votre autonomie, votre rigueur technique et votre capacité à stabiliser des environnements existants.

---

*Bonne chance pour votre entretien ! Vous disposez désormais de tous les arguments techniques, d'une étude d'architecture de haut niveau et d'une roadmap concrète pour impressionner le jury.*
