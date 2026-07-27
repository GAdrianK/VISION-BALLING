# Analyse vidéo — Sprint 2

> Le socle Sprint 1 reste disponible. Le Sprint 2 ajoute une baseline football
> interchangeable, le tracking, le remux audio FFmpeg et l'évaluation.

## Objectif et architecture

Ce module fournit une preuve de concept reproductible :

`vidéo brute → validation → détection personnes/ballon → tracking → vidéo annotée avec IDs + JSON + rapport`

Il est isolé du moteur RAG existant dans `backend/app/video_analysis` :

- `schemas.py` : contrat Pydantic versionné `1.0.0` ;
- `validation.py` : format, taille, disque, flux, durée, résolution et FPS ;
- `detectors.py` : interface `ObjectDetector` et baseline OpenCV HOG ;
- `pipeline.py` : lecture frame par frame, détection, annotation et aperçu ;
- `storage.py` : jobs et résultats JSON persistants, écritures atomiques ;
- `service.py` : orchestration, déduplication SHA-256 et gestion des statuts ;
- `app/api/video_analysis.py` : routes FastAPI.

Les fichiers générés sont stockés sous
`backend/data/video_results/analysis_<uuid>/`. Ils sont ignorés par Git.

## Baseline et licence

La baseline est le détecteur de personnes HOG/SVM fourni par OpenCV
(OpenCV 4.x est sous licence Apache 2.0). Elle fonctionne localement sur CPU,
sans télécharger de poids. Elle n'est pas entraînée spécifiquement pour le
football :

- une `person` reçoit provisoirement le rôle `unknown_player` ;
- elle peut manquer des joueurs petits, partiellement cachés ou vus de loin ;
- elle ne distingue ni équipes, ni arbitres ;
- elle ne détecte pas le ballon et n'en invente jamais la position.

`ObjectDetector` permet de la remplacer ultérieurement par une baseline
football validée, sans modifier le pipeline ni le contrat API.

## Architecture 0.2 et dépendances externes

- `ObjectDetector` conserve HOG et accepte l'adaptateur YOLO/Ultralytics ;
- `Tracker` accepte `none`, le tracker IoU CPU ou l'adaptateur ByteTrack de
  Supervision ;
- FFprobe lit les métadonnées, OpenCV traite la vidéo en streaming et FFmpeg
  remuxe l'audio source ;
- le schéma JSON `1.1.0` relit encore les résultats Sprint 1 `1.0.0`.

Les sorties distinguent `person` + `player_candidate` de `sports ball` +
`ball_candidate`. Une personne n'est jamais présentée comme un joueur certain.

Installation optionnelle du détecteur moderne :

```bash
cd backend
.venv/bin/pip install -r requirements-video.txt
```

Sous Windows, remplacer `.venv/bin/pip` par `.venv\Scripts\pip.exe`.
`VIDEO_DETECTOR=yolo` charge `VIDEO_MODEL_PATH`. Aucun poids n'est versionné et
les tests ne téléchargent aucun modèle. Ultralytics propose des conditions
AGPL-3.0 ou une licence Enterprise selon l'usage : vérifier la licence avant tout
usage commercial. L'import reste confiné à l'adaptateur.

## Configuration Sprint 2

```dotenv
VIDEO_DETECTOR=hog
VIDEO_MODEL_PATH=yolo11n.pt
VIDEO_DEVICE=cpu
VIDEO_PERSON_CONFIDENCE_THRESHOLD=0.45
VIDEO_BALL_CONFIDENCE_THRESHOLD=0.25
VIDEO_FRAME_SAMPLE_RATE=10
VIDEO_TRACKING_ENABLED=true
VIDEO_TRACKER=iou
VIDEO_PRESERVE_AUDIO=true
VIDEO_MAX_PROCESSING_SECONDS=0
```

Utiliser `VIDEO_DEVICE=cuda` uniquement si CUDA est réellement disponible.
`VIDEO_TRACKER=none` désactive le tracking. Le tracker est recréé et réinitialisé
pour chaque job.

## FFmpeg sous Windows

```powershell
winget install Gyan.FFmpeg
ffmpeg -version
ffprobe -version
```

Rouvrir le terminal après l'installation. L'endpoint
`GET /api/video-analysis/diagnostics/backend` expose la disponibilité, la version
et le backend. Les commandes sont passées comme arguments séparés avec
`shell=False`, y compris pour les chemins Windows contenant des espaces. Si
FFmpeg manque ou si le remux échoue, le fallback OpenCV produit une vidéo sans
audio et ajoute un avertissement.

## Benchmark HOG / YOLO

```bash
python scripts/benchmark_detectors.py \
  --video samples/private/match_test.mp4 \
  --detectors hog,yolo \
  --sample-rate 10 \
  --output samples/private/benchmark_report.json
```

Le rapport sépare performance technique, volume de détections et précision.
Sans vérité terrain, `precision` reste `null` : davantage de rectangles ne prouve
pas une meilleure qualité.

## Jeu annoté léger

```bash
python scripts/extract_evaluation_frames.py \
  --video samples/private/match_test.mp4 \
  --count 30 \
  --output samples/private/evaluation_frames
```

Le template attend des annotations de la forme :

```json
{"class_name": "person", "bbox": [100, 200, 170, 390]}
```

CVAT peut servir à l'annotation manuelle. Les médias et annotations privées
restent sous `samples/private/`.

```bash
python scripts/evaluate_detector.py \
  --annotations samples/private/annotations.json \
  --predictions samples/private/predictions.json
```

La commande calcule précision, rappel et IoU sans inventer d'annotation.

## Interprétation et limites

`class_summary` expose personnes, ballons, frames avec ballon, taux apparent,
confiance moyenne et plus longue séquence sans ballon. `tracking_summary` expose
les tracks de personnes. Le taux apparent n'est pas un rappel réel : le ballon
peut être absent, caché ou trop petit.

### Ce que cette version ne sait pas encore faire

- l'identité réelle des joueurs est inconnue ;
- les équipes ne sont pas classifiées ;
- le ballon est parfois invisible ou non détecté, sans interpolation ;
- les track IDs peuvent changer ;
- aucune position métrique sur le terrain n'est calculée ;
- aucune possession ni passe n'est détectée ;
- aucune analyse tactique n'est produite.

### Dépannage Windows

- `ffmpeg not found` : vérifier le `PATH`, puis rouvrir PowerShell ;
- erreur YOLO : vérifier le poids et `requirements-video.txt` ;
- CUDA indisponible : repasser à `VIDEO_DEVICE=cpu` ;
- vidéo sans audio : consulter `warnings` et le diagnostic backend ;
- traitement trop long : augmenter `VIDEO_FRAME_SAMPLE_RATE`.

## Prérequis et installation

- Python 3.10 ou supérieur ;
- FFmpeg/FFprobe recommandé pour une lecture fiable des métadonnées ;
- Node.js pour le frontend.

Sous Debian/Ubuntu :

```bash
sudo apt-get install ffmpeg
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cd frontend && npm install
```

Copier ensuite la configuration :

```bash
cp backend/.env.example backend/.env
```

Les paramètres `VIDEO_*` contrôlent les dossiers, extensions, limites,
fréquence d'analyse, seuil, device et conservation des frames extraites.
`VIDEO_FRAME_INTERVAL=10` signifie qu'une frame sur dix est analysée. Toutes
les frames restent écrites dans la vidéo de sortie afin de préserver la durée.

## Lancement local

Backend :

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Frontend :

```bash
cd frontend
npm run dev
```

Si l'API n'est pas sur `http://127.0.0.1:8000`, définir `VITE_API_URL`.

## API

Créer une analyse :

```bash
curl -X POST http://127.0.0.1:8000/api/video-analysis \
  -F "video=@/chemin/match.mp4" \
  -F "match_id=match_demo"
```

Réponse :

```json
{
  "analysis_id": "analysis_...",
  "match_id": "match_demo",
  "status": "queued",
  "reused": false
}
```

Consulter le job et les résultats :

```bash
curl http://127.0.0.1:8000/api/video-analysis/analysis_xxx
curl http://127.0.0.1:8000/api/video-analysis/analysis_xxx/detections
curl http://127.0.0.1:8000/api/video-analysis/analysis_xxx/artifacts
```

Le contrat inclut pour chaque prédiction la frame, le timestamp, la classe, le
rôle football provisoire, la confiance, la bounding box, le `track_id` nul et
l'identifiant du modèle. Une vidéo identique déjà terminée réutilise le résultat
grâce à son SHA-256.

## Tests

```bash
backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run lint && npm run build
```

Les tests vidéo génèrent un minuscule AVI local. Aucun modèle n'est téléchargé.
Le pipeline et les endpoints utilisent un `FakeDetector` injecté.

## Limites et prochaine étape

Cette version ne reconnaît pas automatiquement tous les joueurs, ne garantit
aucune touche de balle, ne reconstruit pas le terrain en 2D et ne produit pas
d'analyse tactique complète.

Le traitement utilise pour le MVP les tâches d'arrière-plan FastAPI. Cela reste
adapté aux courtes vidéos et à un seul processus. La prochaine étape exacte est
de mesurer une baseline de détection football sur un petit jeu de validation
annoté, puis d'ajouter un détecteur football/ballon sous `ObjectDetector`. Avant
la mise en production, déplacer `VideoAnalysisService.process` vers une file
Redis/Celery ou RQ avec worker GPU, stockage objet et reprise sur incident.
