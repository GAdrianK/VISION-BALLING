# Benchmark Public Football — Sprint 2.1

Ce document décrit le protocole de benchmark public de détection (Ball & Person) et de suivi multi-objets (Tracking) pour la vision par ordinateur appliquée au football.

---

## 1. Datasets & Licences

### SoccerNet-v3 H250 (YOLO Detection) & SoccerNet Tracking
- **Description** : Dataset de référence international pour la détection et le suivi de joueurs/ballon dans des matchs de football professionnels.
- **Format d'annotation** :
  - Détection : Format YOLO (`class_id x_center y_center width height` normalisés).
  - Tracking : Format MOTChallenge (`gt.txt` avec `frame, track_id, bb_left, bb_top, bb_width, bb_height, mark, class_id, visibility`).
- **Licence & Conditions** :
  - Données fournies sous licence **SoccerNet Research License** (usage non commercial).
  - L'accès aux archives requiert une inscription préalable sur [SoccerNet.org](https://www.soccer-net.org/).

> [!NOTE]
> Les scripts de ce dépôt respectent strictement l'exclusion des fichiers de données (`.gitignore`) et ne versionnent ni images, ni vidéos, ni annotations volumineuses, ni poids de modèles.

---

## 2. Commandes Reproductibles

### A. Téléchargement optionnel de SoccerNet Tracking (Split Train)
```bash
python scripts/soccernet_downloader.py --dest-dir data/external/soccernet --split train
```
*Remarque* : Ce script ne télécharge pas les matchs vidéos complets. En cas de demande d'identifiants par l'API SoccerNet, le script s'arrête proprement et affiche la procédure à suivre.

### B. Évaluation des Détecteurs (YOLO COCO vs Modèle Fine-tuné)
```bash
python scripts/benchmark_sprint2_1.py \
  --yolo-dir data/external/soccernet/labels \
  --detector-coco yolo11n.pt \
  --detector-finetuned path/to/football_yolo.pt \
  --output benchmark_detection_report.json
```

**Métriques évaluées** :
- **Précision, Rappel, F1-score & mAP@0.5** (par classe `person` et `sports ball`).
- **Rappel Spécifique du Ballon** (`ball_recall`).
- **Vitesse et Mémoire** : FPS (Frames Per Second) et mémoire résidente maximale réelle du processus (`peak_rss_mb`, mesurée par échantillonnage continu et `resource.getrusage`).

### C. Évaluation des Trackers (IoU Tracker vs ByteTrack)
```bash
python scripts/benchmark_sprint2_1.py \
  --mot-gt data/external/soccernet/gt.txt \
  --trackers iou,bytetrack \
  --use-trackeval \
  --output benchmark_tracking_report.json
```

**Métriques de suivi évaluées** :
- **HOTA@0.5** (Higher Order Tracking Accuracy à seuil d'IoU 0.5).
- **DetA@0.5** (Detection Accuracy à 0.5).
- **AssA@0.5** (Association Accuracy à 0.5, pondérée par les instances TP d'association).
- **IDF1** (ID F1-score par assignation globale).
- **HOTA Officiel 19 Seuils** (`HOTA_official_19_thresholds`) : généré lorsque le paquet optionnel `trackeval` (`pip install trackeval`) est installé et le drapeau `--use-trackeval` est activé.

### D. Exécution des Tests Automatisés
```bash
backend/.venv/bin/pytest backend/tests/test_benchmark_sprint2_1.py
```
