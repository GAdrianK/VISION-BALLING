# Politique des Données & Discipline des Jeux d'Évaluation (Dataset Policy)

Ce document établit les règles d'intégrité, de partitionnement et de provenance des données appliquées à l'ensemble du cycle expérimental VISION-BALLING (EXP-01 à EXP-26).

---

## 1. Règle Fondamentale de Non-Contamination (Zero Data Leakage)

1. **Étanchéité stricte des partitions** :
   - Aucun seuil, hyperparamètre ou modèle de classification/régression n'est ajusté sur la partition **HOLDOUT**.
   - Le code d'évaluation ne lit les annotations de vérité terrain qu'au moment du calcul de métriques finales et ne les réinjecte jamais dans les algorithmes de décision.
2. **Immutabilité des jeux d'évaluation gelés** :
   - Une fois un benchmark exécuté et scellé, ses fichiers JSON de métriques et ses annotations de référence ne sont plus modifiés.

---

## 2. Partitionnement du Dataset Détection H250

Le dataset H250 a été employé pour l'entraînement et l'évaluation comparée des détecteurs (EXP-01 à EXP-04) :

| Partition | Nombre d'Images | Usage Expérimental |
| :--- | :--- | :--- |
| **TRAIN** | 2 842 images | Entraînement supervisé des têtes de détection |
| **VAL / DEV** | 300 images | Validation d'époque et sélection des meilleurs checkpoints |
| **TEST / HOLDOUT** | 2 692 images | Évaluation terminale gelée (EXP-01 à EXP-04) |

Les tests unitaires (`test_chapter5_tracking.py`) vérifient par assertion automatisée que le code de tracking n'importe ni n'accède à la partition de test H250.

---

## 3. Partitionnement SoccerNet Tracking 2023

Pour les chapitres 5, 6, 7 et 8 (tracking, calibration, géométrie tactique, pression, transitions, fusion et RAG), un sous-ensemble standardisé de 12 séquences broadcast de SoccerNet Tracking 2023 a été partitionné :

| Séquence | Durée | Rôle dans le Protocole |
| :--- | :--- | :--- |
| **SNMOT-060** | 750 frames (30s) | **DEV** — Calibrage initial des algorithmes |
| **SNMOT-061** | 750 frames (30s) | **DEV** — Diagnostic de trajectoires et cohabitation d'IDs |
| **SNMOT-062** | 750 frames (30s) | **DEV** — Diagnostic de vitesse et compression |
| **SNMOT-063** | 750 frames (30s) | **VALIDATION** — Évaluation intermédiaire |
| **SNMOT-064** | 750 frames (30s) | **VALIDATION** — Évaluation intermédiaire |
| **SNMOT-065** | 750 frames (30s) | **VALIDATION** — Évaluation intermédiaire |
| **SNMOT-066** | 750 frames (30s) | **VALIDATION** — Évaluation intermédiaire |
| **SNMOT-067** | 750 frames (30s) | **VALIDATION** — Évaluation intermédiaire |
| **SNMOT-068** | 750 frames (30s) | **BENCHMARK / DEMO** — Séquence de référence consolidée |
| **SNMOT-069** | 750 frames (30s) | **HOLDOUT** — Évaluation terminale sans réajustement |
| **SNMOT-070** | 750 frames (30s) | **HOLDOUT** — Évaluation terminale sans réajustement |
| **SNMOT-071** | 750 frames (30s) | **HOLDOUT** — Évaluation terminale sans réajustement |

> **Note de provenance** : Les séquences SNMOT-060 à 071 proviennent du dossier d'entraînement public de SoccerNet Tracking 2023 et ont été isolées localement en trois partitions étanches (DEV / VAL / HOLDOUT). Elles ne constituent pas le jeu officiel de compétition SoccerNet Test (dont les vérités terrain restent privées).

---

## 4. Typologie des Vérités Terrain (Ground Truth Taxonomy)

Pour garantir une intégrité épistémique sans ambiguïté :

1. **Vérité Terrain Humaine Indépendante (Human GT)** :
   - Boîtes englobantes des joueurs et du ballon issues de SoccerNet (`gt.txt`).
   - Rôles officiels et équipes issus de `gameinfo.ini`.
2. **Vérité Terrain Dérivée de Lois Physiques (Physics-Derived Diagnostic GT)** :
   - Annotations d'événements de transition (`transition_gt_v1.json`) ou de pression (`pressure_gt_v1.json`) générées à partir de seuils stricts sur des grandeurs cinématiques (vitesse, distance relative, centroïde). Ces vérités terrain servent d'outils de validation logique et de cohérence, et ne sont pas présentées comme un étiquetage subjectif humain.
3. **Vérité Terrain Documentaire RAG (Grounding Benchmark)** :
   - 76 cas de test couvrant faits exacts, horodatages, explications causales, comparaisons d'équipes, abstentions et culture générale footballistique (`exp26_grounding_eval.json`).
