# Analyse vidéo — état technique actuel

> **Statut : documentation technique actuelle, non normative.** Le périmètre et les garanties V1 sont définis par les documents de `docs/product/` et l'ADR 0001.

Le module `backend/app/video_analysis/` fournit un pipeline local versionné `0.2.0` et un schéma de résultat `1.1.0`. Il valide une vidéo, échantillonne ses frames, exécute le détecteur configuré, applique éventuellement des trackers, produit un JSON et tente de créer une vidéo annotée.

## Composants

- `validation.py` : extension, taille, espace disque, ouverture du flux, durée, résolution et fréquence d'images ;
- `detectors.py` : interface de détection, baseline OpenCV HOG et adaptateur YOLO facultatif ;
- `trackers.py` : suivi des personnes par IoU ou ByteTrack facultatif et suivi temporel expérimental du ballon ;
- `pipeline.py` : traitement frame par frame, résumés, annotations et artefacts ;
- `storage.py` : persistance locale des jobs, résultats JSON et artefacts ;
- `service.py` : orchestration, progression et réutilisation d'un résultat par SHA source.

## Détecteurs disponibles

### HOG par défaut

`VIDEO_DETECTOR=hog` utilise OpenCV HOG sur CPU. Il fonctionne sans poids externe et détecte des personnes candidates. Il ne détecte pas le ballon et aucune précision football n'est revendiquée.

### YOLO facultatif

`VIDEO_DETECTOR=yolo` charge un poids présent localement à `VIDEO_MODEL_PATH`. Les dépendances sont isolées dans `backend/requirements-video.txt`. Le dépôt ne contient ni ne télécharge de poids.

Deux profils de classes sont présents :

- `coco` : classes usuelles, dont `person` et `sports ball` ;
- `h250` : mapping local `0 = ball`, `1 = person`.

Le profil H250 est vérifié par des tests de mapping, pas validé sur les vidéos golden ni sur le terrain.

## Configuration principale

| Variable | Défaut | Effet |
|---|---|---|
| `VIDEO_DETECTOR` | `hog` | sélectionne HOG ou YOLO |
| `VIDEO_MODEL_PATH` | `yolo11n.pt` | chemin du poids YOLO local |
| `VIDEO_MODEL_PROFILE` | `coco` | sélectionne le profil de classes |
| `VIDEO_DEVICE` | `cpu` | périphérique transmis au détecteur |
| `VIDEO_FRAME_INTERVAL` | `10` | intervalle d'échantillonnage par défaut |
| `VIDEO_TRACKING_ENABLED` | `true` | active les trackers configurés |
| `VIDEO_TRACKER` | `iou` | tracker de personnes |
| `VIDEO_BALL_TRACK_MAX_MISSING_FRAMES` | `5` | limite des prédictions consécutives du ballon |
| `VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO` | `0.15` | filtre de déplacement relatif |
| `VIDEO_PRESERVE_AUDIO` | `true` | demande la conservation de l'audio lors de l'encodage |

Les autres contraintes d'entrée sont centralisées dans `backend/app/core/config.py`.

## Observations et prédictions

Une détection issue du détecteur est une observation. Le tracker du ballon peut compléter une courte absence par un point de trajectoire dont `state` vaut `predicted`. Une telle prédiction :

- n'est pas une nouvelle détection ;
- a une confiance nulle dans le sens où le champ `confidence` vaut `null` ;
- doit rester distinguée d'un point `observed` dans toute interface ou analyse ;
- ne prouve pas une amélioration tant qu'un benchmark golden ne l'a pas mesurée.

Le JSON expose `ball_trajectory` avec les états `observed` et `predicted`. Le résumé de tracking peut contenir :

- `unique_person_tracks` et `tracked_person_detections` ;
- `observed_frames`, `predicted_frames` et `missing_frames` ;
- `observed_coverage` et `effective_coverage` ;
- `longest_missing_gap` et `reset_count`.

Le résumé de classes expose notamment les nombres de détections de personnes et de ballon, les frames avec ballon, le taux apparent de détection et la confiance moyenne. Ces valeurs décrivent le comportement du pipeline ; elles ne sont pas des métriques tactiques.

## Routes

- `GET /api/video-analysis/diagnostics/backend`
- `POST /api/video-analysis`
- `GET /api/video-analysis/{analysis_id}`
- `GET /api/video-analysis/{analysis_id}/detections`
- `GET /api/video-analysis/{analysis_id}/artifacts`
- `GET /api/video-analysis/{analysis_id}/artifacts/{artifact_name}`

Le traitement est lancé avec FastAPI `BackgroundTasks`. Il n'est pas durable : un redémarrage peut interrompre un job et aucune file externe ne le reprend.

## Artefacts

Un job terminé peut référencer :

- la vidéo annotée ;
- le JSON de détections ;
- une image d'aperçu.

Ils sont écrits dans le stockage local configuré et ignorés par Git. La réutilisation actuelle cherche un résultat complété à partir du SHA de la vidéo source ; elle ne tient pas compte de toute la configuration du pipeline.

## Encodage et navigateurs

Le pipeline contient une étape FFmpeg visant un flux H.264/AAC, un pixel format `yuv420p` et le déplacement des métadonnées au début du fichier. Les tests vérifient la construction de la commande, mais pas la lecture réelle sur une matrice de navigateurs.

Une incompatibilité de lecture a été observée sous Linux et n'est pas considérée comme résolue par cette documentation. La normalisation définitive de l'encodage et sa validation multi-navigateurs relèvent du chapitre 2.

## Limites

- aucun jeu golden, annotation de vérité terrain ou rapport de benchmark n'est versionné ;
- HOG n'est qu'une baseline de personnes ;
- YOLO, H250, ByteTrack et le tracker ballon sont expérimentaux ;
- le suivi des personnes ne garantit pas une identité stable lors des occultations ;
- aucune équipe, calibration, correction humaine, possession ou métrique tactique V1 n'est produite ;
- les résultats locaux ne doivent pas être interprétés comme une validation terrain.

Voir aussi [`project_status.md`](project_status.md) et [`known_limitations.md`](known_limitations.md).
