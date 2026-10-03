# Analyse vidéo — état technique actuel

> **Statut : documentation technique actuelle, non normative.** Le périmètre et les garanties V1 sont définis par les documents de `docs/product/` et l'ADR 0001.

Le module `backend/app/video_analysis/` fournit un pipeline local versionné `0.4.0` et un schéma de résultat `1.3.0`. Il valide une vidéo, échantillonne ses frames, exécute le détecteur configuré, applique éventuellement des trackers, produit un JSON et crée une vidéo annotée.

## Composants

- `validation.py` : extension, taille, espace disque, ouverture du flux, durée, résolution et fréquence d'images ;
- `detectors.py` : interface de détection, baseline OpenCV HOG et adaptateur YOLO facultatif ;
- `trackers.py` : suivi des personnes par IoU ou ByteTrack facultatif et suivi temporel expérimental du ballon ;
- `pipeline.py` : traitement frame par frame, résumés, annotations et artefacts ;
- `storage.py` : persistance locale des jobs, résultats JSON et artefacts ;
- `service.py` : orchestration, progression et réutilisation d'un résultat par clé d'analyse reproductible.
- `reproducibility.py` : configuration canonique, checksum modèle, clé d'analyse et commit Git.

## Détecteurs & Modes Canoniques (RC2)

La plateforme supporte deux modes opérationnels canoniques validés :

### 1. Mode QUALITY (Défaut de Production RC2)

`VIDEO_MODE=QUALITY`
- **Détecteur** : RF-DETR Small @ 960px (`rfdetr`) sur GPU CUDA.
- **Poids** : Checkpoint verrouillé EXP-04 (`checkpoint_best_total.pth`). Empreinte SHA-256 obligatoire : `c1a1d88b74edc5ddefa7da4581e2848c4c58c3938d88ad4a1b615f071752ffff`.
- **Tracking joueurs** : BoT-SORT avec compensation de mouvement global (GMC).
- **Tracking ballon** : BallTrackManager V2 (Kalman 2D + découplage observations/prédictions).
- **Attribution d'équipe & rôle** : Clustering non supervisé K-Means Lab/HSV.
- **Chaîne tactique** : Hauteur de bloc, compacité métrique, PressureIndex continu (EXP-23), Possession V2 (EXP-22), transitions causales (EXP-25) et rapport ancré (EXP-26).

### 2. Mode LOW_LATENCY (Cadence Élevée)

`VIDEO_MODE=LOW_LATENCY`
- **Détecteur** : YOLO11n @ 640px (`yolo11n.pt`) sur CUDA ou CPU.
- **Tracking joueurs** : ByteTrack cinématique rapide sans GMC.
- **Cadence** : ~24 FPS pour prévisualisation et exploitation rapide.

> **Note historique sur HOG** : OpenCV HOG était une baseline minimale sur CPU pour les premiers tests unitaires (Sprint 2). Il est formellement déprécié, incompatible avec OpenCV 5+, et ne doit jamais être utilisé en production.

## Configuration Principale (RC2)

| Variable | Défaut RC2 | Effet |
|---|---|---|
| `VIDEO_MODE` | `QUALITY` | Sélectionne le mode canonique (`QUALITY` ou `LOW_LATENCY`) |
| `VIDEO_DETECTOR` | `rfdetr` | Détecteur d'objets (`rfdetr` en Quality, `yolo11n` en Low Latency) |
| `VIDEO_MODEL_PATH` | chemin checkpoint | Chemin absolu vers le checkpoint RF-DETR (`checkpoint_best_total.pth`) |
| `VIDEO_MODEL_PROFILE` | `football` | Profil de classes (`football` ou `coco`) |
| `VIDEO_DEVICE` | `cuda` | Périphérique d'inférence (`cuda` requis en production) |
| `VIDEO_FRAME_SAMPLE_RATE` | `1` | Fréquence d'échantillonnage d'inférence (1 = chaque frame) |
| `VIDEO_TRACKING_ENABLED` | `true` | Active les trackers multi-objets |
| `VIDEO_TRACKER` | `botsort` | Tracker de joueurs (`botsort` en Quality, `bytetrack` en Low Latency) |
| `VIDEO_BALL_TRACK_MAX_MISSING_SECONDS` | `0.2` | Durée maximale d'extrapolation du ballon |
| `VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO` | `0.15` | Filtre de déplacement relatif du ballon |
| `VIDEO_BALL_TRAJECTORY_SECONDS` | `0.5` | Historique visuel de trajectoire affiché |
| `VIDEO_PRESERVE_AUDIO` | `true` | Conservation de la piste audio lors de la normalisation |
| `VIDEO_KEEP_TEMPORARY_FILES` | `false` | Conserve les frames et intermédiaires de diagnostic |
| `VIDEO_RETAIN_SOURCE` | `true` | Conserve la vidéo source pour réanalyse |
| `VIDEO_GIT_SHA` | vide | Injecte le commit Git du build si `.git` absent |

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

## Sampling, temporalité et frames

`VIDEO_FRAME_SAMPLE_RATE=N` signifie qu'une inférence est exécutée sur les indices de frame divisibles par N. Toutes les frames restent lues, suivies et écrites. Le tracker ballon avance donc à la cadence source, indépendamment de la fréquence d'inférence.

Les durées du tracker sont configurées en secondes. Après validation de la vidéo, elles sont converties en frames source par `ceil(secondes × FPS source validé)`. Le plafond évite de raccourcir la durée demandée ; une durée positive très faible produit au moins une frame. Les valeurs configurées et effectives sont enregistrées dans `PipelineMetadata`.

Le résultat distingue désormais :

- `frames_read` : lectures OpenCV réussies ;
- `frames_inferred` : appels réels à `detector.detect()` ;
- `frames_interpolated` : positions ballon `predicted` sans observation correspondante ;
- `frames_written` : appels à `VideoWriter.write()`.

`frames_analyzed` est conservé pour compatibilité et vaut exactement `frames_inferred`. Il est déprécié au profit des compteurs explicites.

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

Ils sont écrits dans le stockage local configuré et ignorés par Git. La source est conservée par défaut, indépendamment des frames temporaires. Ce choix permet une réanalyse reproductible avant l'arrivée d'un stockage objet, au prix d'une consommation disque proportionnelle aux uploads. `VIDEO_RETAIN_SOURCE=false` supprime la source après un traitement réussi ; une source ayant échoué reste disponible pour diagnostic.

## Reproductibilité et cache

Le SHA-256 de la source ne suffit pas à identifier un résultat. Le service calcule désormais une `analysis_key` déterministe à partir du SHA source, du checksum modèle, de la version pipeline et d'un JSON canonique trié. Ce JSON contient uniquement les paramètres ayant un effet sur le run : détecteur et modèle, seuils effectifs, sampling, tracker, durées configurées du tracker ballon, profil de normalisation vidéo, audio et version du normaliseur.

Pour YOLO, le device fait partie de l'identité car CPU et accélérateurs peuvent produire des différences numériques affectant les détections. Le device HOG, fixé au CPU, n'est pas dupliqué dans la configuration canonique. Les chemins absolus, répertoires temporaires et secrets sont exclus.

Si `VIDEO_MODEL_PATH` désigne un fichier présent, son SHA-256 réel est calculé et mis en cache selon le chemin résolu, la taille et la date de modification. Sans poids, l'identité est un SHA-256 déterministe du backend, du modèle, de son profil et de sa version. Le commit Git vient de `VIDEO_GIT_SHA`, puis de `git rev-parse HEAD`, sinon vaut exactement `unknown`.

Seul un job terminé portant la même `analysis_key` est réutilisé. Les anciens JSON sans cette clé restent lisibles grâce aux valeurs optionnelles du schéma, mais ne sont pas réutilisés automatiquement : leur configuration complète ne peut pas être prouvée.

## Encodage et navigateurs

Quand FFmpeg est disponible, la vidéo finale passe toujours par une normalisation `libx264`, `yuv420p`, tag `avc1`, cadence source explicite en CFR, timestamps non négatifs et `+faststart`, avec ou sans conservation de l'audio. Les commandes utilisent une liste d'arguments et `shell=False`.

Sans FFmpeg, ou si la normalisation échoue, le fichier `mp4v` OpenCV est conservé avec un warning explicite : il ne satisfait pas la garantie de compatibilité navigateur. Un smoke test synthétique vérifie avec ffprobe H.264, `avc1`, `yuv420p`, FPS, durée et timestamp initial ; il est skippé explicitement lorsque FFmpeg ou ffprobe manque. La validation navigateur réelle est exécutée sur chaque navigateur local disponible et reste bloquée pour les navigateurs absents.

Le harness léger `scripts/browser_video_probe.py` ouvre une vraie sortie du pipeline dans un navigateur Chromium installé. Il attend `loadedmetadata` puis `loadeddata`, exige des dimensions strictement positives et échoue sur timeout ou erreur de décodage. Un navigateur absent reste `BLOCKED` ; ffprobe ne remplace jamais cette validation.

## Limites

- aucun jeu golden, annotation de vérité terrain ou rapport de benchmark n'est versionné ;
- HOG n'est qu'une baseline de personnes ;
- YOLO, H250, ByteTrack et le tracker ballon sont expérimentaux ;
- le suivi des personnes ne garantit pas une identité stable lors des occultations ;
- aucune équipe, calibration, correction humaine, possession ou métrique tactique V1 n'est produite ;
- les résultats locaux ne doivent pas être interprétés comme une validation terrain.

Voir aussi [`project_status.md`](project_status.md) et [`known_limitations.md`](known_limitations.md).
