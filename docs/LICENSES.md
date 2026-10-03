# Mentions Légales et Licences des Composants Tiers

VISION-BALLING intègre et interagit avec plusieurs bibliothèques et architectures de modèles tiers. Ce document détaille les licences applicables, les garanties d'isolation et les conditions d'utilisation.

---

## 1. Composants Coeur (VISION-BALLING Core)

L'architecture principale de VISION-BALLING (API FastAPI, orchestrateur, géométrie tactique, RAG hybride, interface React) est distribuée sous licence libre **Apache-2.0** (ou MIT).

---

## 2. Bibliothèques et Modèles Détection / Tracking

| Composant | Description | Licence | Modalité d'Intégration |
| :--- | :--- | :--- | :--- |
| **RF-DETR** | Détecteur petit format haute précision | **Apache-2.0** | Poids entraînés sur H250, inférence directe PyTorch |
| **YOLO11** (Ultralytics) | Détecteur standard basse latence | **AGPL-3.0** | Optionnel, interchangeable avec RF-DETR |
| **BoT-SORT** | Traitement d'association multi-objets | **MIT** | Algorithme d'association intégré |
| **ByteTrack** | Suivi par association IoU à deux seuils | **MIT** | Algorithme d'association intégré |
| **PRTReID / BPB-ReID** | Extraction de caractéristiques d'apparence | **Apache-2.0** | Checkpoint SoccerNet officiel évalué en inférence |

---

## 3. Calibration Terrain (Camera Calibration)

| Composant | Description | Licence | Modalité d'Intégration |
| :--- | :--- | :--- | :--- |
| **PnLCalib** | Calibration par points clés et lignes | **GPL-2.0** | **Strictement isolé** dans un sous-processus via `PnLCalibAdapter` (`calibration_adapters.py`). Aucun code PnLCalib n'est importé statiquement dans le coeur de l'application. |
| **TVCalib** | Calibration différentiable caméra de match | **MIT** | Adaptateur externe via `TVCalibAdapter` |

> [!WARNING]
> En raison de la licence **GNU GPL-2.0** de PnLCalib, toute distribution commerciale compilée ou liée statiquement peut être soumise à des obligations de partage de code. Pour un déploiement commercial permissif, utilisez l'adaptateur TVCalib (MIT) ou un calibrateur propriétaire conforme.

---

## 4. Composants RAG & Moteur Documentaire

| Composant | Description | Licence |
| :--- | :--- | :--- |
| **Qdrant Client** | Base vectorielle en mémoire ou distribuée | **Apache-2.0** |
| **FlashRank** | Modèle de reranking local ultra-léger | **Apache-2.0** |
| **Rank-BM25** | Algorithme de recherche lexicale BM25 | **Apache-2.0** |
| **SQLite3** | Magasin persistant parent-document | **Public Domain** |

---

## 5. Datasets et Jeux de Données d'Évaluation

| Dataset | Provenance | Licence / Utilisation |
| :--- | :--- | :--- |
| **SoccerNet Tracking 2023** | SoccerNet / Université de Liège | **CC BY-NC 4.0** (Attribution - NonCommercial) |
| **H250 Dataset** | Benchmark annoté de détection football | Usage recherche et benchmarking |

L'exploitation des jeux de données SoccerNet est strictement réservée à la recherche, au benchmark et à des finalités non commerciales, conformément aux termes de la licence CC BY-NC 4.0.
