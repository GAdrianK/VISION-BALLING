# Analyse vidéo — Sprint 1

## Objectif et architecture

Ce module fournit une preuve de concept reproductible :

`vidéo brute → upload streaming → validation → frames échantillonnées → détection → vidéo annotée + JSON`

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

