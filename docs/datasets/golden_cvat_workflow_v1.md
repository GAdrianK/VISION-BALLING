# Golden CVAT workflow V1

- Version : 1.0.0
- Projet CVAT : `VISION-BALLING Golden Benchmark V1`
- Visibilité : privée
- Rôle exclusif : `golden_eval`
- État initial : `ANNOTATIONS_PENDING`
- Source humaine de vérité : les douze exports natifs CVAT après annotation et QA humaines

Ce workflow prépare l'annotation, contrôle les exports et rend un futur freeze reproductible. Il ne produit aucune annotation et n'autorise aucune prédiction modèle comme ground truth.

## 1. Préparer les imports privés

Depuis la racine du dépôt, vérifier d'abord les médias :

```powershell
python scripts/verify_internal_validation_dataset.py --annotation-media-dir data/golden/annotation_media
```

La porte attendue est `MEDIA_PASS count=950 tasks=12`. Préparer ensuite l'espace CVAT :

```powershell
python scripts/prepare_golden_cvat_workflow.py
```

Le script vérifie le rôle `golden_eval`, les douze inventaires et chaque média. Il crée sous `data/golden/annotations/` :

```text
cvat/
  annotation_metadata_v1.json
  cvat_import_plan_v1.json
  cvat_label_reference_v1.json
  import/
    CVAT-.../
      images/
qa/
  qa_log_v1.csv
```

Les répertoires `images/` contiennent 1 002 références de tâche vers 950 PNG uniques. Ce sont des liens physiques vers les supports lossless existants : ils n'altèrent pas les originaux et n'en dupliquent pas le contenu. Le script est idempotent et refuse d'écraser un fichier différent. Tout cet espace est privé et ignoré par Git via `/data/golden/`.

## 2. Lancer ou ouvrir CVAT

Utiliser une instance CVAT existante et maintenue par l'utilisateur. Elle doit rester locale ou privée ; aucun média golden ne doit être publié. Si CVAT, Docker et `cvat-cli` sont absents, la porte est :

```text
BLOCKED — CVAT INSTANCE REQUIRED
```

Dans ce cas, installer CVAT et Docker séparément, après décision explicite de l'utilisateur. Aucun téléchargement n'est autorisé par ce chapitre. Une fois une copie officielle de CVAT et Docker disponibles, la reprise locale exacte est :

```powershell
Set-Location <DOSSIER_INSTALLATION_CVAT>
docker compose up -d
docker compose ps
```

Attendre que les services soient sains, puis ouvrir `http://localhost:8080` et s'authentifier. Si aucun compte administrateur n'existe dans cette installation, le créer avec la commande documentée par la version CVAT installée avant d'importer des médias. Revenir ensuite à la racine de VISION-BALLING et relancer les deux commandes de la section 1. Le workflow ne déploie et n'invente jamais un serveur.

## 3. Créer le projet et les labels

Dans CVAT :

1. créer le projet privé `VISION-BALLING Golden Benchmark V1` ;
2. reproduire les définitions de `data/golden/annotations/cvat/cvat_label_reference_v1.json` ;
3. ne créer aucune autre classe ;
4. vérifier les types de géométrie et les valeurs d'attribut avant la première tâche.

Les six classes objet sont `player`, `goalkeeper`, `referee`, `ball`, `ignore_person` et `ignore_region`. Les trois entités spéciales exigées par le schéma sont `event` (tag portant `event_type`), `pitch_line` (polyline) et `pitch_keypoint` (points). Elles matérialisent les sections `events` et `calibration` du schéma ; ce ne sont pas des classes objet supplémentaires.

Pour chaque classe objet, configurer `team`, `truncated`, `uncertain` et `qa_notes`; utiliser le champ CVAT natif pour `occluded`. Les valeurs `team` restent propres au label :

- `player`, `goalkeeper` : `team_a`, `team_b`, `unknown` ;
- `referee` : `official` ;
- `ball`, `ignore_person`, `ignore_region` : `not_applicable`.

Le tag `event` reçoit `event_type`, `team`, `actor_track_id`, `target_track_id`, `notes` et `uncertain`. `pitch_line` reçoit `line_type`; `pitch_keypoint` reçoit `keypoint_type`.

## 4. Créer exactement les douze tâches

Respecter cet ordre et ne fusionner aucune tâche :

| Ordre | Tâche | Frames | Mode humain |
|---:|---|---:|---|
| 1 | `CVAT-G01-DETECTION` | 240 | shapes |
| 2 | `CVAT-G02-DETECTION` | 240 | shapes |
| 3 | `CVAT-G03-DETECTION` | 176 | shapes |
| 4 | `CVAT-TRACK-G01-01` | 50 | tracks + tags |
| 5 | `CVAT-TRACK-G01-02` | 50 | tracks + tags |
| 6 | `CVAT-TRACK-G02-01` | 50 | tracks + tags |
| 7 | `CVAT-TRACK-G02-02` | 50 | tracks + tags |
| 8 | `CVAT-TRACK-G03-01` | 58 | tracks + tags |
| 9 | `CVAT-TRACK-G03-02` | 58 | tracks + tags |
| 10 | `CVAT-G01-CALIBRATION` | 10 | polylines + points |
| 11 | `CVAT-G02-CALIBRATION` | 10 | polylines + points |
| 12 | `CVAT-G03-CALIBRATION` | 10 | polylines + points |

Pour chaque tâche, sélectionner tous les PNG du dossier `data/golden/annotations/cvat/import/<TASK_ID>/images/`. Conserver l'ordre lexical des noms, la résolution originale et le nom exact de la tâche. Comparer le compteur CVAT au champ `expected_frames` de `cvat_import_plan_v1.json` avant annotation.

## 5. Annotation et progression humaine

Suivre `golden_annotation_guidelines_v1.md`. L'ordre recommandé est G01 détection, G02 détection, G03 détection, les six séquences tracking, les trois tâches calibration, les événements non ambigus, puis la QA.

Mettre à jour uniquement les faits réellement vérifiés dans `annotation_metadata_v1.json` :

- `visited_frame_uids` après visite explicite de chaque frame, même vide ;
- `reviewed_frame_uids` après seconde revue réelle ;
- statut de tâche parmi `PENDING`, `ANNOTATING`, `REVIEW_REQUIRED`, `QA_PASS`, `QA_FAIL` ;
- identifiants non personnels d'annotateur et reviewer ;
- compteurs QA à partir des exports, jamais par estimation.

Une frame vide n'est pas une erreur, mais elle doit apparaître dans `visited_frame_uids`. Ne jamais copier les listes complètes à titre de raccourci avant la visite humaine.

## 6. QA obligatoire

La QA minimale est :

- seconde revue stratifiée d'au moins 24 frames G01, 24 frames G02 et 18 frames G03 parmi les tâches détection ;
- revue de 100 % des boxes `ball` ;
- revue frame par frame de 100 % des six tâches tracking ;
- revue de 100 % des trente frames calibration ;
- revue de 100 % des événements ;
- zéro problème bloquant non résolu.

Consigner les problèmes réels dans `data/golden/annotations/qa/qa_log_v1.csv`. Ne conserver aucune donnée personnelle inutile. Une tâche ne passe à `QA_PASS` qu'après correction et revue. Le dataset passe à `READY_TO_FREEZE` seulement lorsque les douze tâches satisfont la porte.

## 7. Export natif et vérification

Exporter chaque tâche au format natif CVAT préservant boxes, attributs, tracks, points, polylines et tags. Enregistrer exactement l'un des noms suivants par tâche sous `data/golden/annotations/cvat/` :

```text
<TASK_ID>.xml
<TASK_ID>.zip
```

Un ZIP doit contenir exactement un `annotations.xml`. YOLO TXT n'est jamais la source de vérité. Lancer ensuite :

```powershell
python scripts/verify_golden_annotations.py
```

Le vérificateur contrôle les douze tâches, les 950 frame UIDs, les labels et teams, les géométries et limites image, les IDs locaux de tracking, les séquences, le subset calibration, les événements, la couverture visitée, la QA et l'absence de rôle training. Tant qu'un export manque, la réponse correcte reste `BLOCKED — CVAT EXPORTS REQUIRED`.

## 8. Freeze et exports dérivés

Ne créer `golden_annotations_v1.0.0.zip`, son checksum, COCO, MOTChallenge et les JSON calibration/événements qu'après `ANNOTATION_EXPORTS_PASS` et QA complète. Le package privé contient les exports CVAT natifs, le journal QA, les métadonnées, la version et la liste des tâches. Il reste hors Git.

Après création déterministe du package, calculer son SHA-256, passer les métadonnées privées à `FROZEN`, puis seulement mettre à jour `internal_benchmark_v1.json` avec la version, le SHA, `frozen_at`, la synthèse QA, les statistiques et `annotation_status = FROZEN`. La vérification finale utilise :

```powershell
python scripts/verify_golden_annotations.py --require-frozen --package data/golden/annotations/exports/golden_annotations_v1.0.0.zip
```

Les exports COCO, tracking, événements et calibration sont dérivés. Aucun golden, export ou résultat golden ne doit entrer dans `train`, `training`, un fine-tuning ou une configuration d'entraînement.
