# Tableau Consolidé des Résultats Expérimentaux (EXP-01 à EXP-26)

> **Statut : Scellé pour VISION-BALLING Release Candidate 1 (v0.9.0-rc1)**.

Ce tableau résume les 26 expériences conduites à travers les chapitres 5, 6, 7 et 8 de VISION-BALLING. Il classe chaque résultat selon son statut épistémique : **Validé en production**, **Outil diagnostique**, ou **Résultat négatif / Hypothèse réfutée**.

---

| Expérience | Domaine / Composant | Approche & Modèle | Métriques Clés Obtenues | Statut Scientifique |
| :--- | :--- | :--- | :--- | :--- |
| **EXP-01** | Détection petits objets | YOLO11n @ 640px (H250) | mAP50: 0.771, mAP50-95: 0.505, 85 FPS | Validé (Mode Low Latency) |
| **EXP-02** | Détection haute résolution | YOLO11n @ 960px (H250) | mAP50: 0.812, mAP50-95: 0.548, 62 FPS | Validé |
| **EXP-03** | Détection capacité accrue | YOLO11s @ 960px (H250) | mAP50: 0.842, mAP50-95: 0.589, 45 FPS | Validé |
| **EXP-04** | Détection transformers | RF-DETR Small @ 960px (H250) | mAP50: **0.865**, mAP50-95: **0.618**, 28 FPS | **Validé (Mode Quality Champion)** |
| **EXP-05** | Multi-Object Tracking | Baseline SoccerNet (ByteTrack) | MOTA: 58.2%, IDF1: 64.1% | Ligne de base historique |
| **EXP-06** | Diagnostics ballon | Analyse des artefacts et occultations | Identification cohabitation IDs, rebonds | Diagnostic |
| **EXP-07** | Suivi du ballon V2 | Filtre de Kalman 2D + découplage obs/pred | Précision spatiale < 1.2 m, continuité +35% | Validé |
| **EXP-08** | Tracking Joueurs sans ReID | BoT-SORT cinématique | MOTA: 66.8%, IDF1: 71.3% | Validé |
| **EXP-09** | Pipeline de Tracking Unifié | Orchestrateur modulaire détection + tracking | Stabilité des identifiants confirmée | Validé |
| **EXP-10** | Re-Identification Joueurs | PRTReID (BPB-ReID HRNet-32, 256-D) | Rank-1: 89.4%, mAP ReID: 82.1% | Validé |
| **EXP-11** | ReID Conditionnel | Gating spatio-temporel d'inférence ReID | IDF1: **75.8%**, Réduction calcul: **-68%** | **Validé en production** |
| **EXP-12** | Rôles & Équipes | K-Means Lab + histogrammes maillot | Exactitude équipe: **96.2%**, Arbitre: 98.4% | Validé |
| **EXP-13** | Calibration Terrain | PnLCalib vs TVCalib | IoU terrain: **88.5%**, Reproj err: **3.2 px** | Validé (Isolé sous subprocess) |
| **EXP-14** | Lissage Temporel Calib | Filtrage homographique temporel EMA | Réduction variance bruit: **-54%** | Validé |
| **EXP-15** | Trajectoires Métriques 2D | Homographie inverse + projection sol 105x68m | Dérive métrique < 0.45 m | Validé |
| **EXP-16** | Géométrie Tactique | Enveloppes convexes, centroïdes d'équipe | Surfaces d'occupation et compacité | Validé |
| **EXP-17** | Orientation & Lignes | Détermination dynamique du sens d'attaque | Alignement des 3 lignes (déf, mil, att) | Validé |
| **EXP-18** | Possession V1 (Baseline) | Distance euclidienne statique joueur-ballon | Précision porteur: 6.67%, F1: 0.0471 | Baseline historique |
| **EXP-19** | Détection de Passes V1 | Machine à états émission/vol/réception | Oracle Recall: **80.0%**, End-to-end: 20.0% | Goulot d'étranglement amont |
| **EXP-20** | Bloc Défensif & Compacité | Hauteur de ligne défensive continue | Erreur moyenne hauteur < 2.1 m | Validé |
| **EXP-21** | Inférence de Formations | 8 prototypes tactiques nominaux | Macro F1 réels: **0.00%** (Troncation FOV) | **Résultat Négatif (Hypothèse réfutée)** |
| **EXP-22** | Possession V2 (Challenger) | Gating spatio-temporel adaptatif + hystérésis | F1 porteur: **+21%**, Robustesse duels | **Validé et Adopté** |
| **EXP-23** | Pression Défensive | $\text{PressureIndex} \in [0, 1]$ vectoriel continu | Monotonie physique 100%, 0 seuil discret | **Validé** |
| **EXP-24** | Transitions Tactiques | Scores continus de contre-pressing & récup | Macro F1 transition: 0.6005 | Outil Diagnostique |
| **EXP-25** | Fusion d'Événements | Graphe de causalité spatio-temporel & cartes | 100% traçabilité horodatée vers vidéo | **Validé (Interface de vérité)** |
| **EXP-26** | Grounded Tactical RAG | RAG hybride multimodal + rapport de match | Supported Claim Rate: **100%**, Hallucination: **0%** | **Validé (76/76 cas réussis)** |
