# Benchmark Public Football — Sprint 2.1

> **Statut : expérimentation / non normatif.** Ce fichier décrit un protocole ; il ne fournit aucun résultat de référence et ne remplace pas le [protocole golden V1](product/golden_videos_protocol.md).

Ce document décrit le protocole de benchmark public de détection (Ball & Person) et de suivi multi-objets (Tracking) pour la vision par ordinateur appliquée au football.

---

## 1. Datasets & Licences

### SoccerNet-v3 H250 (YOLO Detection) & SoccerNet Tracking
- **Description** : Dataset de référence international pour la détection et le suivi de joueurs/ballon dans des matchs de football professionnels.
- **Format d'annotation** :
  - H250 : format YOLO (`class_id x_center y_center width height` normalisés), avec `0 = ball` et `1 = person`.
  - Tracking : dix colonnes compatibles MOTChallenge (`frame, track_id, left, top, width, height, confidence, -1, -1, -1`). Les classes d'objets ne sont pas encodées dans ce fichier.
- **Licence & Conditions** :
  - Vérifier et respecter la licence distribuée avec chaque archive.
  - H250 est téléchargeable sur [Zenodo](https://zenodo.org/records/7808511).
  - SoccerNet Tracking est distribué via le client officiel et certains contenus peuvent demander l'acceptation des conditions SoccerNet.

> [!NOTE]
> Les scripts de ce dépôt respectent strictement l'exclusion des fichiers de données (`.gitignore`) et ne versionnent ni images, ni vidéos, ni annotations volumineuses, ni poids de modèles.

---

## 2. Commandes Reproductibles

### A. Téléchargement optionnel de SoccerNet Tracking (Split Train)
```bash
pip install SoccerNet
python scripts/soccernet_downloader.py --dest-dir data/external/soccernet --split train
```
Le contenu exact de l'archive de tâche est géré par SoccerNet et peut comprendre des clips et leurs annotations. Cette commande ne lance pas le téléchargement séparé des 12 matchs bruts complets. En cas d'accès protégé, utiliser `--password` ou la variable `SOCCERNET_PASSWORD`.

### B. Évaluation des Détecteurs (YOLO COCO vs Modèle Fine-tuné)

Télécharger puis extraire `YOLO.zip` depuis Zenodo dans `data/external/h250`. Repérer les dossiers d'images et de labels du split à tester, puis lancer d'abord un smoke test :

```bash
python scripts/benchmark_sprint2_1.py \
  --yolo-labels data/external/h250/labels/test \
  --yolo-images data/external/h250/images/test \
  --detector-coco yolo11n.pt \
  --max-frames 100 \
  --output benchmark_detection_report.json
```

Le benchmark s'arrête si les images correspondant aux labels sont absentes. Il ne remplace jamais les images manquantes par des frames noires.

Pour comparer un modèle fine-tuné H250, ajouter :

```bash
--detector-finetuned path/to/football_yolo.pt
```

Le détecteur COCO utilise `0 = person, 32 = sports ball`. Le modèle fine-tuné H250 utilise `0 = ball, 1 = person`.

**Métriques évaluées** :
- **Précision, Rappel, F1-score & mAP@0.5** (par classe `person` et `sports ball`).
- **Rappel Spécifique du Ballon** (`ball_recall`).
- **Vitesse et Mémoire** : FPS (Frames Per Second) et mémoire résidente maximale réelle du processus (`peak_rss_mb`, mesurée par échantillonnage continu et `resource.getrusage`).

### C. Évaluation des Trackers (IoU Tracker vs ByteTrack)
```bash
python scripts/benchmark_sprint2_1.py \
  --mot-gt data/external/soccernet/sequence/gt/gt.txt \
  --mot-frames data/external/soccernet/sequence/img1 \
  --trackers iou,bytetrack \
  --use-trackeval \
  --output benchmark_tracking_report.json
```

**Métriques de suivi évaluées** :
- **HOTA@0.5** (Higher Order Tracking Accuracy à seuil d'IoU 0.5).
- **DetA@0.5** (Detection Accuracy à 0.5).
- **AssA@0.5** (Association Accuracy à 0.5, pondérée par les instances TP d'association).
- **IDF1** (ID F1-score par assignation globale).
- **HOTA, DetA et AssA officiels sur 19 seuils** : calculés directement par les métriques du paquet TrackEval lorsque `trackeval` est installé et `--use-trackeval` activé.

Sans TrackEval, le rapport indique explicitement le moteur intégré et ne fournit que les métriques locales au seuil `0.5`.

### D. Exécution des Tests Automatisés
```bash
backend/.venv/bin/pytest backend/tests/test_benchmark_sprint2_1.py
```
