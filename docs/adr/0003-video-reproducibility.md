# ADR 0003 — Reproductibilité du pipeline vidéo

- Statut : accepté pour le chapitre 2A
- Date : 2026-08-31
- Portée : pipeline vidéo local et artefacts associés

## Contexte

Le cache historique réutilisait un job terminé à partir du seul SHA-256 de la vidéo source. Deux analyses d'une même source pouvaient pourtant différer selon le modèle, ses poids, les seuils, le sampling, le tracker, la version du pipeline ou l'encodage final. Le SHA source seul ne permet donc ni d'identifier un résultat ni de le reproduire.

La sortie vidéo pouvait aussi rester directement en `mp4v` OpenCV lorsque l'audio n'était pas conservé. Ce chemin ne fournissait pas une garantie uniforme de lecture navigateur. Enfin, `VIDEO_KEEP_TEMPORARY_FILES` décidait à la fois du sort des frames temporaires et de la vidéo source, alors que ces données ont des cycles de vie différents.

## Décision

### Clé d'analyse

Chaque nouveau job reçoit une `analysis_key` :

```text
SHA256(source_sha256 + model_checksum + pipeline_version + canonical_config_json)
```

Le JSON canonique utilise des clés triées, des séparateurs stables et refuse les nombres non finis. Il contient uniquement les paramètres qui influencent les détections, le tracking ou l'artefact final : détecteur, modèle et profil, checksum, seuils effectifs, sampling, tracker, paramètres du tracker ballon, conservation audio et profil/version du normaliseur vidéo.

Les secrets, chemins absolus, répertoires temporaires et options sans effet sur le résultat sont exclus. Le device est inclus pour YOLO car des différences numériques entre CPU et accélérateur peuvent modifier les prédictions. HOG étant fixé au CPU, ce paramètre n'y est pas dupliqué.

Le cache recherche désormais uniquement un job terminé portant cette clé. Une source identique et une configuration identique sont réutilisables ; toute variation d'un paramètre effectif produit un nouveau run.

### Identité du modèle

Quand le chemin modèle désigne un fichier présent, son SHA-256 réel est calculé. Le calcul est mémorisé selon le chemin résolu, la taille et la date de modification : il n'est jamais répété par frame. Le chemin local n'est pas sérialisé ; seul un identifiant sans répertoire et le checksum sont exposés.

Quand aucun poids n'existe, comme pour OpenCV HOG, le checksum est dérivé de façon déterministe du backend, du `model_id`, du profil éventuel et de la version du détecteur. Aucune valeur aléatoire n'est utilisée.

### Métadonnées et versions

`PipelineMetadata` reste l'unique structure de métadonnées pipeline. Elle porte désormais le SHA source, l'`analysis_key`, le commit Git, les versions pipeline/détecteur/tracker, l'identité et le checksum modèle, les seuils, le FPS source validé, le sampling, la version FFmpeg, le backend vidéo et la configuration canonique.

Le commit Git est résolu dans cet ordre : `VIDEO_GIT_SHA` valide sur 40 caractères hexadécimaux, `git rev-parse HEAD`, puis la valeur littérale `unknown`. L'absence de `.git` n'empêche jamais le traitement.

Le pipeline passe de `0.2.0` à `0.3.0`. Le schéma passe de `1.1.0` à `1.2.0`, car les jobs et résultats sérialisés gagnent une identité reproductible. Les champs nouveaux ont des valeurs par défaut ou sont optionnels ; les anciens jobs et résultats restent lisibles. Un ancien job sans `analysis_key` n'est pas réutilisé automatiquement, car son identité complète est inconnue.

### Normalisation vidéo finale

Lorsque FFmpeg est présent, tout fichier final est réencodé avec `libx264`, `yuv420p`, le tag `avc1`, le FPS validé en CFR, des timestamps rendus non négatifs et `+faststart`. L'audio source est facultatif et encodé en AAC lorsqu'il doit être conservé. L'appel est toujours effectué avec `shell=False`.

Si FFmpeg manque ou échoue, le `mp4v` intermédiaire devient le fallback. Le résultat reçoit un warning indiquant explicitement qu'il ne satisfait pas la garantie navigateur. Le backend réellement utilisé est enregistré dans les métadonnées et participe à l'identité du run.

### Conservation de la source

`VIDEO_RETAIN_SOURCE=true` est le défaut. Tant qu'aucun stockage objet ne prend le relais, conserver la source est nécessaire pour relancer exactement une analyse. Ce choix augmente l'occupation disque et peut être désactivé explicitement. `VIDEO_KEEP_TEMPORARY_FILES` ne contrôle plus que les frames et intermédiaires de diagnostic ; il ne décide jamais de la suppression de la source.

## Conséquences

- Le cache évite les réutilisations incorrectes entre configurations différentes.
- Les résultats exposent assez d'informations pour reconstruire l'identité d'un run sans révéler de secret ou de chemin utilisateur.
- Un changement de poids est détecté même si le nom du fichier reste identique.
- Les sorties nominales ont un profil MP4 navigateur uniforme lorsque FFmpeg est disponible.
- La conservation par défaut consomme davantage de disque jusqu'à l'introduction du stockage objet.
- Les jobs anciens restent consultables mais ne bénéficient pas du nouveau cache.

## Suite au chapitre 2B

Le chapitre 2B complétera cette décision avec un paramètre de sampling unique, des unités temporelles explicites pour les trackers, le comptage `frames_read / inferred / interpolated / written` et la validation Chrome, Firefox et Edge.
