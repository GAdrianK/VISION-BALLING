# Golden annotation guidelines V1

- Version : 1.0.0
- Dataset : VISION-BALLING internal golden validation
- Rôle : `golden_eval`
- État initial : `ANNOTATIONS_PENDING`
- Source humaine de vérité : export natif CVAT préservant boxes, attributs, tracks, points, polylines et tags temporels

## 1. Identité et supports

L'identité canonique d'une frame est `golden_sha256 + frame_index`, matérialisée par `GOLDEN-ID:00000000`. Elle ne dépend ni du nom, ni du checksum du PNG local. Le frame index est zéro-based, le timestamp vaut `frame_index / fps`, et toute géométrie utilise la résolution originale du golden.

Les supports CVAT sont des PNG lossless à résolution originale générés sous `data/golden/annotation_media/`. Ils sont privés, ignorés par Git et régénérables avec :

```powershell
python scripts/extract_golden_annotation_frames.py --golden-manifest data/manifests/golden_videos_v1.json --frame-inventory data/manifests/golden_frames_v1.csv --tracking-manifest data/manifests/tracking_sequences_v1.json --data-dir data/golden/assets --output-dir data/golden/annotation_media
```

Le script vérifie chaque SHA golden avant décodage, lit séquentiellement la vidéo, n'écrit que les indices sélectionnés et génère `frame_mapping.csv` ainsi que les listes de médias par tâche. Il ne modifie jamais les goldens.

## 2. Tâches CVAT

### Groupe A — détection sparse

- `CVAT-G01-DETECTION` — 240 frames sparse ;
- `CVAT-G02-DETECTION` — 240 frames sparse ;
- `CVAT-G03-DETECTION` — 176 frames sparse.

### Groupe B — tracking et événements

- `CVAT-TRACK-G01-01` — 50 frames ;
- `CVAT-TRACK-G01-02` — 50 frames ;
- `CVAT-TRACK-G02-01` — 50 frames ;
- `CVAT-TRACK-G02-02` — 50 frames ;
- `CVAT-TRACK-G03-01` — 58 frames ;
- `CVAT-TRACK-G03-02` — 58 frames.

### Groupe C — calibration

- `CVAT-G01-CALIBRATION` — 10 frames ;
- `CVAT-G02-CALIBRATION` — 10 frames ;
- `CVAT-G03-CALIBRATION` — 10 frames.

Une frame `sparse+tracking` conserve une identité unique dans l'inventaire, même si elle est référencée par deux listes de tâches. Les événements sont annotés dans les tâches tracking correspondantes.

## 3. Classes objets

- `player` : joueur de champ participant au match ;
- `goalkeeper` : gardien lorsque le rôle est raisonnablement identifiable ;
- `referee` : arbitre ou officiel présent dans le jeu ;
- `ball` : ballon réellement visible ;
- `ignore_person` : staff, coach, spectateur proche, cameraman ou autre personne hors tâche dont la présence créerait une ambiguïté ;
- `ignore_region` : polygone couvrant une zone de foule ou une région où une annotation exhaustive est irréaliste.

La foule entière ne doit jamais devenir des centaines de boxes. Aucun objet ne doit être halluciné derrière une occlusion.

## 4. Bounding boxes et visibilité

Le format exporté est `x_min, y_min, width, height`, origine en haut à gauche. Toutes les coordonnées doivent être finies, strictement positives en largeur et hauteur, et clampées à l'image originale. Aucun redimensionnement n'est autorisé avant annotation.

Annoter une personne partiellement visible si sa localisation et son étendue sont raisonnablement déterminables. Utiliser le champ CVAT natif `occluded=true` lorsque l'objet est masqué par un joueur, poteau, panneau, équipement, personne ou bord d'image. Utiliser `truncated=true` lorsqu'il sort du cadre. Un fragment impossible à attribuer ne reçoit pas de box arbitraire.

Le ballon n'est annoté que s'il est réellement visible. Ne jamais interpoler une box de détection sur une frame `not_visible`. Un ballon partiellement masqué mais localisable peut être annoté avec `occluded=true`.

## 5. Équipes et attributs

Pour `player` et `goalkeeper`, `team` vaut `team_a`, `team_b` ou `unknown`. Pour `referee`, il vaut `official`; pour `ball`, `ignore_person` et `ignore_region`, `not_applicable`.

`team_a` et `team_b` décrivent les tenues observées, jamais une supposition `home`/`away`. Les observations initiales du schéma doivent être confirmées par l'annotateur, surtout pour les petites silhouettes G02 et la séquence difficile G03. Toute box ambiguë reçoit `unknown`.

Les attributs communs sont `truncated`, `uncertain` et `qa_notes`; l'occlusion utilise le champ natif CVAT. Ne pas déduire automatiquement une équipe à partir d'une couleur incertaine.

## 6. Tracking

Les track IDs sont requis uniquement dans les six séquences continues et restent locaux à chaque `sequence_id`. Une personne présente dans deux séquences peut donc avoir deux IDs différents. Les classes principales trackées sont `player`, `goalkeeper`, `referee` et `ball`; `ignore_person` n'entre pas dans l'évaluation tracking principale.

Après une occlusion brève, conserver l'ID seulement si l'identité reste certaine. Après une sortie complète suivie d'une réentrée incertaine, créer un nouvel ID. Ne jamais forcer une association ; documenter le cas dans `qa_notes`.

## 7. Événements simples

Les seuls tags frame-level autorisés sont :

- `pass` : frame du contact initial envoyant volontairement le ballon vers un coéquipier ;
- `shot` : frame du contact d'une frappe dirigée vers le but ;
- `ball_out` : première frame où le ballon est clairement hors des limites, si observable ;
- `restart` : premier contact remettant le ballon en jeu après un arrêt.

Attributs : `event_type`, `team`, `actor_track_id`, `target_track_id`, `notes`, `uncertain`. Les IDs acteur/cible peuvent être nuls. Un événement ambigu n'est pas forcé et n'entre pas dans le benchmark concerné tant qu'il n'est pas résolu. Les notions xG, xT, PPDA, pressing, possession probabiliste, turnover complexe, faute automatique et hors-jeu sont hors périmètre V1.

## 8. Calibration

Les 30 frames déjà présentes dans l'inventaire reçoivent éventuellement :

- une polyline `pitch_line` avec `line_type` parmi `touchline`, `goal_line`, `halfway_line`, `penalty_area`, `goal_area`, `center_circle`, `penalty_arc`, `other_marking` ;
- un point `pitch_keypoint` avec `keypoint_type` parmi `line_intersection`, `corner`, `center_spot`, `penalty_spot`, `other_known_landmark`.

Ne pas annoter une ligne ou un point qui n'est pas réellement visible. Les coordonnées métriques ne sont enregistrées que si les dimensions réelles du terrain sont documentées. Ne jamais supposer 105 m × 68 m.

## 9. QA et désaccords

Avant freeze :

- seconde revue d'au moins 10 % des frames sparse, stratifiée par golden ;
- revue de 100 % des boxes `ball` ;
- revue de 100 % des six séquences tracking et de leurs IDs ;
- revue de 100 % des 30 frames calibration ;
- revue de 100 % des événements ;
- correction de toutes les incohérences bloquantes.

Chaque campagne conserve uniquement : identifiant d'annotateur, identifiant de reviewer, date, version, problèmes, décision et résolution. Aucune donnée personnelle inutile n'est enregistrée.

Une revue est obligatoire pour `player`/`goalkeeper`, `player`/`referee`, `team_a`/`team_b`, très petite box ballon, track ID après occlusion, événement ambigu ou keypoint incertain. Si le doute persiste, marquer `uncertain=true` et exclure l'élément de la métrique concernée, ou supprimer l'annotation si aucune vérité défendable n'existe. Un désaccord n'est jamais tranché au hasard.

## 10. Confidentialité, exports et freeze

Le dépôt est public, les médias et annotations restent privés sous :

```text
data/golden/
  annotation_media/
  annotations/
    cvat/
    exports/
    qa/
```

Ne jamais committer PNG/JPEG, vidéos, archives, exports CVAT bruts, annotations individuelles ou trajectoires détaillées. L'export natif CVAT est la source humaine de vérité. COCO (détection), MOTChallenge ou format interne (tracking), et JSON versionné (calibration/événements) sont uniquement des exports dérivés déterministes.

Après annotation et QA, le freeze final reçoit : l'export CVAT natif, le journal QA, la version du package et son SHA-256. `internal_benchmark_v1.json` est alors mis à jour avec `annotation_package_version` et `annotation_package_sha256`, sans committer le contenu privé.
