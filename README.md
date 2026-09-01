# VISION-BALLING

VISION-BALLING est un prototype d'assistance à l'analyse football post-match. Il réunit une interface React, une API FastAPI, un pipeline vidéo local et un moteur documentaire local afin de préparer une analyse tactique vérifiable par un humain.

> **Statut : prototype V1 en construction.** Le dépôt permet déjà d'ingérer et d'annoter des vidéos, mais il ne produit pas encore les métriques tactiques définies pour la V1 et ne doit pas être considéré comme prêt pour la production.

## État réel du produit

### Fonctionnel aujourd'hui

- interface React/Vite pour le chat, l'import vidéo, le suivi d'un traitement et la lecture des résultats ;
- API FastAPI avec routes de chat, d'export PDF et d'analyse vidéo ;
- validation des fichiers vidéo, traitement frame par frame et stockage local des jobs et résultats ;
- détecteur OpenCV HOG par défaut pour les personnes, sans poids externe ;
- vidéo annotée et export JSON horodaté ;
- moteur RAG local distinct du pipeline vidéo.

### Expérimental

- détecteur YOLO facultatif, qui exige des dépendances et des poids locaux non versionnés ;
- profil de classes H250 (`ball`, `person`) ;
- suivi des personnes par IoU ou ByteTrack facultatif ;
- suivi temporel du ballon, avec séparation entre observations et prédictions ;
- compatibilité de la vidéo annotée entre navigateurs ;
- traitement en arrière-plan basé sur `BackgroundTasks`, non durable.

### Non implémenté

- identification des équipes et correction humaine ;
- calibration du terrain et état de jeu en coordonnées 2D ;
- possession et métriques tactiques V1 : largeur, longueur/profondeur, centroid robuste de l’équipe, compacité et transitions ;
- PPDA et xT ;
- rapport vidéo sourcé et benchmark golden exécuté.

Les illustrations tactiques de l'interface ne sont pas des résultats d'analyse. Une valeur tactique ne doit être considérée comme un résultat que si elle provient de l'API courante et si son origine est traçable.

## Architecture actuelle

```text
frontend/                     React 18 + Vite 5
backend/app/main.py           Application FastAPI et routes principales
backend/app/video_analysis/   Validation, détection, tracking et artefacts
backend/data/                 Stockage local ignoré par Git
knowledge_base/               Corpus du moteur documentaire local
docs/                         Contrats, état courant et documentation technique
```

Le pipeline vidéo est configurable. Le réglage par défaut utilise HOG sur CPU et ne détecte que les personnes. YOLO, le profil H250 et ByteTrack restent des options locales et expérimentales. Le RAG ne fournit pas les métriques issues d'une vidéo.

## Prérequis

- Git ;
- Python 3.10 ou plus récent ;
- Node.js 20 recommandé et npm ;
- FFmpeg facultatif pour la normalisation/lecture de certains artefacts vidéo ;
- uniquement pour YOLO ou ByteTrack : dépendances vidéo facultatives et poids locaux compatibles.

Aucun modèle, dataset ou média n'est téléchargé par les commandes de démarrage ci-dessous.

## Installation et démarrage

Depuis la racine du dépôt.

### Backend — Windows PowerShell

```powershell
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

### Backend — Linux ou macOS

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

L'API est alors disponible sur `http://127.0.0.1:8000`. La documentation OpenAPI est exposée sur `/docs`.

### Frontend

Dans un second terminal :

```bash
cd frontend
npm ci
npm run dev
```

Vite affiche l'URL locale du frontend. `VITE_API_URL` peut cibler une autre API ; sa valeur par défaut est `http://127.0.0.1:8000`.

### Configuration facultative

La configuration est lue depuis les variables d'environnement et, localement, depuis `backend/.env`. Ce fichier est ignoré par Git.

Principaux réglages vidéo :

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `VIDEO_DETECTOR` | `hog` | `hog` ou `yolo` |
| `VIDEO_MODEL_PATH` | `yolo11n.pt` | chemin local du poids YOLO |
| `VIDEO_MODEL_PROFILE` | `coco` | profil `coco` ou `h250` |
| `VIDEO_TRACKER` | `iou` | tracker de personnes |
| `VIDEO_TRACKING_ENABLED` | `true` | active le suivi temporel |

Sans modèle YOLO, conservez `VIDEO_DETECTOR=hog`. Le pipeline fonctionne alors sans poids externe, mais il ne détecte pas le ballon. Pour activer YOLO ou ByteTrack, installez explicitement les dépendances facultatives :

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-video.txt
```

ou sous Linux/macOS :

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-video.txt
```

Cette commande n'installe aucun poids. Ne configurez `VIDEO_MODEL_PATH` que vers un fichier local compatible.

## Routes principales

- `GET /api/health`
- `POST /api/chat`
- `POST /api/analyze`
- `POST /api/export-pdf`
- `GET /api/video-analysis/diagnostics/backend`
- `POST /api/video-analysis`
- `GET /api/video-analysis/{analysis_id}`
- `GET /api/video-analysis/{analysis_id}/detections`
- `GET /api/video-analysis/{analysis_id}/artifacts`
- `GET /api/video-analysis/{analysis_id}/artifacts/{artifact_name}`

`/api/analyze` dépend des données SQL locales disponibles. Certaines réponses génératives peuvent aussi dépendre d'une configuration de fournisseur ; les tests n'exigent ni clé ni appel distant.

## Vérification locale

Avec l'environnement Python local activé ou en utilisant son exécutable, installez les outils de développement puis lancez :

```bash
python -m pip install -r backend/requirements-dev.txt
pytest backend/tests -q
ruff check backend
```

Puis :

```bash
cd frontend
npm run lint
npm run build
```

La CI reproduit ces quatre contrôles. Aucune suite de tests frontend n'est déclarée actuellement.

## Limites et garanties

Le suivi du ballon n'est pas validé sur le terrain et aucune amélioration de qualité n'est revendiquée sans benchmark golden. La sortie nominale est normalisée en H.264 et le cache tient compte de la configuration reproductible complète. La validation navigateur reste conditionnée à la matrice réellement disponible. Le stockage est local et les tâches de fond ne survivent pas à un redémarrage du processus.

Voir [les limites connues](docs/known_limitations.md) et [l'état vérifiable du projet](docs/project_status.md) pour la matrice complète.

## Documentation de référence

Les documents normatifs V1 sont :

- [Contrat produit V1](docs/product/product_contract_v1.md)
- [Protocole des vidéos golden](docs/product/golden_videos_protocol.md)
- [Métriques de réussite V1](docs/product/success_metrics_v1.md)
- [Priorités du backlog V1](docs/product/backlog_priorities_v1.md)
- [ADR 0001 — périmètre de l'analyse tactique assistée](docs/adr/0001-assisted-tactical-analysis-scope.md)

Documentation technique et gouvernance :

- [Index documentaire](docs/README.md)
- [Analyse vidéo](docs/video-analysis.md)
- [Politique de branches](docs/development/branch_policy.md)
- [ADR 0002 — source de vérité du dépôt](docs/adr/0002-repository-source-of-truth.md)

## Données et artefacts locaux

Les secrets, environnements virtuels, dépendances installées, caches, bases générées, résultats, modèles, checkpoints, datasets, vidéos sources, frames et vidéos annotées ne sont pas versionnés. Ils doivent rester dans les emplacements locaux ignorés par Git et être obtenus séparément avec une licence adaptée.
