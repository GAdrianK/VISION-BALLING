# VISION-BALLING

**Plateforme Multimodale d'Intelligence Tactique Footballistique & RAG Ancré**
*Release Candidate 1 (`v0.9.0-rc1`) — Octobre 2026*

[![CI](https://github.com/GAdrianK/football-intelligence-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/GAdrianK/football-intelligence-rag/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-0.9.0--rc1-blue.svg)](https://github.com/GAdrianK/football-intelligence-rag)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](docs/LICENSES.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-20%2B-green.svg)](https://nodejs.org/)

---

## 1. Présentation Générale

**VISION-BALLING** transforme un enregistrement vidéo de match de football broadcast en une analyse tactique computationnelle métrique 2D, géoréférencée, et génère des comptes-rendus automatisés et un système de questions-réponses vérifiables grâce à un moteur RAG multimodal rigoureusement ancré (*grounded*).

Contrairement aux approches fondées sur des prédictions boîte noire ou des résumés génératifs sujets aux hallucinations, VISION-BALLING applique une **discipline d'ancrage absolu** :
- **Vérité des faits de match** : les événements vidéo structurés issus du pipeline de vision et de géométrie métrique constituent la seule et unique source de vérité factuelle sur le match.
- **Rôle de la base de connaissances (RAG)** : la littérature tactique générale sert exclusivement à expliciter le sens et la portée footballistique des observations mesurées.
- **Zéro hallucination** : 100 % des affirmations concernant le match renvoient à une fiche de preuve horodatée (`[REF-TIMESTAMP-ID]`). En l'absence de preuve, le système pratique l'abstention explicite.

---

## 2. Architecture Globale

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VIDÉO DU MATCH (MP4)                           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CHAPITRE 5 — VISION PAR ORDINATEUR & SUIVI MULTI-OBJETS                   │
│  • Détection : RF-DETR Small @ 960px (mAP50: 0.865) / YOLO11n (Low Latency) │
│  • Tracking : BoT-SORT + ReID Conditionnel PRTReID (-68% calculs, IDF1: 76%) │
│  • Ballon : Filtre de Kalman 2D + découplage observations / prédictions     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CHAPITRE 6 — CALIBRATION CAMÉRA & GÉOMÉTRIE MÉTRIQUE 2D                    │
│  • Attribution des Rôles & Équipes : K-Means Lab (Exactitude: 96.2%)        │
│  • Calibration Terrain : PnLCalib / TVCalib (Erreur reprojection: 3.2 px)   │
│  • Homographie Lissée Temporellement (-54% variance) -> Sol 105 m x 68 m    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CHAPITRE 7 — INTELLIGENCE TACTIQUE SPATIO-TEMPORELLE                       │
│  • Possession V2 : Gating adaptatif + hystérésis (+21% F1 porteur)          │
│  • Pression Défensive Continue : PressureIndex ∈ [0, 1] vectoriel          │
│  • Bloc Défensif : Hauteur de ligne continue & Compacité métrique (m²)      │
│  • Transitions : Détection cinématique de contre-pressing                   │
│  • Fusion Causale : Graphe d'événements & Fiches TacticalEvidenceEvent      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CHAPITRE 8 — RAG MULTIMODAL ANCRÉ & RAPPORT POST-MATCH                     │
│  • Base de Preuves : MatchEvidenceStore (Vérité de terrain autoritaire)     │
│  • RAG Hybride : Qdrant + BM25 + FlashRank Reranker + Magasin Parent SQLite │
│  • Générateur de Rapport : Markdown structuré avec citations horodatées     │
│  • Audit de Grounding : 100% affirmations étayées, 0% hallucination         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Résultats Scientifiques Consolidés (EXP-01 à EXP-26)

Le développement a été validé à travers 26 protocoles d'expérimentation stricts scellés :

| Composant | Modèle / Approche | Métrique Clé Validée | Statut |
| :--- | :--- | :--- | :--- |
| **Détection Objets** | RF-DETR Small @ 960px (H250) | **mAP50 : 0.865 / mAP50-95 : 0.618** | Validé (Mode Quality) |
| **Tracking Joueurs** | BoT-SORT + PRTReID (SoccerNet) | **IDF1 : 75.8 %** (Gating ReID : -68% calculs) | Validé en production |
| **Tracking Ballon** | Kalman 2D + découplage obs/pred | **Dérive < 1.2 m, continuité +35%** | Validé |
| **Attribution Équipes** | K-Means Lab non supervisé | **Exactitude : 96.2 %**, Arbitres : 98.4 % | Validé |
| **Calibration Terrain** | PnLCalib (Isolé subprocess) | **Erreur reproj : 3.2 px / IoU terrain : 88.5 %** | Validé |
| **Contrôle & Possession** | Possession V2 (Gating adaptatif) | **F1 identification porteur : +21 %** | Validé et Adopté |
| **Pression Défensive** | $\text{PressureIndex} \in [0, 1]$ vectoriel | **Monotonie physique 100 %, 0 seuil discret** | Validé |
| **Formations Nominales** | Inférence catégorique (EXP-21) | **Macro F1 : 0.00 %** (Troncation FOV broadcast) | **Hypothèse Réfutée** |
| **Ancrage RAG Match** | Grounded Tactical RAG (EXP-26) | **Supported Claim Rate : 100 %, Hallucination : 0%** | **Validé (76/76 cas)** |
| **Débit Global** | Pipeline complet CV + Tactique + RAG | **11.4 FPS** (`QUALITY`) / **24.2 FPS** (`LOW_LATENCY`) | Profilé honnêtement |

Pour le tableau d'évaluation exhaustif, consultez [`docs/consolidated_experiments_benchmark.md`](docs/consolidated_experiments_benchmark.md).

---

## 4. Installation et Démarrage Rapide

### Prérequis
- **OS** : Linux (testé Ubuntu 22.04 / 24.04 LTS) ou macOS / Windows avec WSL2.
- **Python** : 3.10 ou 3.11 recommandé.
- **Node.js** : 20+ et npm.
- **FFmpeg** : Recommandé pour l'encodage vidéo optimal.

### Démarrage en Une Commande

Cloner le dépôt et lancer la plateforme :

```bash
git clone https://github.com/GAdrianK/football-intelligence-rag.git
cd football-intelligence-rag

# Exécuter les tests et validations
make test

# Lancer simultanément l'API FastAPI (port 8000) et le frontend React (port 5173)
make all
```

L'application web est accessible sur `http://localhost:5173`.
La documentation OpenAPI interactive est disponible sur `http://localhost:8000/docs`.

---

## 5. Exécution de l'Analyse Vidéo Complète (CLI)

Une analyse vidéo de bout en bout peut être lancée directement en ligne de commande :

```bash
python scripts/run_full_video_analysis.py --input path/to/match.mp4 --mode QUALITY
```

Deux modes opérationnels sont proposés :
- `--mode QUALITY` : Détecteur haute résolution RF-DETR @ 960px, BoT-SORT avec ReID d'apparence, calibration fine PnLCalib, lissage temporel (~11.4 FPS).
- `--mode LOW_LATENCY` : Détecteur YOLO11n @ 640px, ByteTrack cinématique rapide, calibration TVCalib (~24.2 FPS).

### Artefacts Produits

Chaque analyse génère un répertoire autonome et autoportant dans `runs/analysis/<analysis_id>/` contenant :
1. `metadata.json` : Empreintes cryptographiques (SHA-256 vidéo, git commit, configuration d'exécution).
2. `tactical_events.json` : Fiches d'événements structurés `TacticalEvidenceEvent`.
3. `match_timeline.jsonl` : Chronologie des faits de jeu avec scores de confiance et qualité.
4. `team_summary.json` : Statistiques d'équipe agrégées (possession, hauteur de bloc, compacité).
5. `event_graph.json` : Graphe orienté de dépendances causales spatio-temporelles.
6. `match_report.md` : Rapport de match ancré complet avec citations cliquables.
7. `runtime.json` : Profilage des temps d'exécution par composant et statut FPS.

---

## 6. Interface Web & Visualisation

L'interface React intègre un espace d'analyse tactique complet :
- **Agrégats & CV** : Vue synthétique de la possession V2, de la hauteur de bloc défensif, de la compacité et des métriques de détection.
- **Événements & Timeline** : Fiches de preuves interactives ordonnées chronologiquement, filtrables par équipe et type d'action, avec badges de confiance et saut direct dans la vidéo.
- **Rapport Ancré** : Visualisation du compte-rendu post-match en Markdown avec citations interactives.
- **Grounded Q&A** : Module de questions-réponses interactif connecté à la vidéo courante garantissant une réponse strictement étayée par les preuves du match.
- **Séquences DEMO intégrées** : Chargement instantané des données de démonstration (`SNMOT-068`, `SNMOT-069`), explicitement étiquetées `DEMO`.

---

## 7. Résultats Négatifs & Limites Scientifiques

VISION-BALLING adopte une transparence scientifique totale sur ses limites :
1. **Formations Catégoriques Réfutées (EXP-21)** : L'attribution de compositions fixes (ex. 4-4-2, 4-3-3) est exclue en raison de la troncation du champ de vision des caméras TV et des déformations asymétriques du jeu moderne. Seules les grandeurs continues (distances inter-lignes, centroïdes) sont conservées.
2. **Pression Discrète Réfutée (EXP-23)** : Les classes arbitraires (`FORTE`, `FAIBLE`) créant des discontinuités de bord, seul le score continu $\text{PressureIndex} \in [0, 1]$ est retenu.
3. **Plafond de Fréquence Plein Pipeline** : Le pipeline complet n'atteint pas 25 FPS constants sur CPU/GPU standard (~11.4 FPS en mode `QUALITY`).
4. **Planarité du Ballon ($Z = 0$)** : Les passes et centres aériens subissent une erreur de parallaxe lors de la projection 2D au sol.

Pour la liste complète et argumentée, consultez [`docs/negative_results.md`](docs/negative_results.md).

---

## 8. Licences & Dépendances

VISION-BALLING est distribué sous licence libre **Apache-2.0**.

Les composants tiers sont intégrés en respectant scrupuleusement leurs licences respectives :
- **RF-DETR** : Apache-2.0
- **BoT-SORT & ByteTrack** : MIT
- **PRTReID** : Apache-2.0
- **PnLCalib** : GPL-2.0 (**Isolé sous subprocess hermétique** pour préserver la licence permissive de VISION-BALLING)
- **SoccerNet Tracking 2023** : CC BY-NC 4.0 (Utilisation recherche et benchmarking non commercial)

Consultez [`docs/LICENSES.md`](docs/LICENSES.md) pour les détails complets.

---

## 9. Index de la Documentation

- 📄 [Rapport Final du Projet & Bilan Scientifique](docs/FINAL_PROJECT_REPORT.md)
- 📋 [Fiche Système / Project Card](docs/PROJECT_CARD.md)
- 📊 [Tableau Consolidé des Benchmarks (EXP-01 à 26)](docs/consolidated_experiments_benchmark.md)
- ⚠️ [Résultats Négatifs & Hypothèses Réfutées](docs/negative_results.md)
- 🔒 [Limites Connues & Frontières Opérationnelles](docs/known_limitations.md)
- ⚖️ [Mentions Légales & Licences des Composants Tiers](docs/LICENSES.md)
- 📁 [Politique des Données & Discipline des Jeux d'Évaluation](docs/DATASET_POLICY.md)
