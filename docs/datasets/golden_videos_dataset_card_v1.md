# Dataset card — Golden Videos V1

- Version : 1.0.0
- Date : 2026-09-01
- Statut : constitution bloquée — aucun asset réel disponible
- Manifeste : [`../../data/manifests/golden_videos_v1.json`](../../data/manifests/golden_videos_v1.json)
- Protocole normatif : [`../product/golden_videos_protocol.md`](../product/golden_videos_protocol.md)

## Objectif

Les trois golden videos forment un jeu de validation interne stable pour mesurer les régressions du pipeline vidéo et du parcours de revue. Elles ne constituent ni un dataset d'entraînement, ni une preuve de performance tant que les trois assets ne sont pas `READY`.

Les IDs immuables sont :

- `GOLDEN-01-BROADCAST` : captation TV réaliste avec mouvements et changements d'échelle normaux ;
- `GOLDEN-02-TACTICAL-WIDE` : vue large montrant une grande portion du terrain et de nombreux petits objets ;
- `GOLDEN-03-DIFFICULT` : plusieurs difficultés réalistes documentées, sans dupliquer les deux autres profils.

La cible opérationnelle est un extrait de deux à cinq minutes par profil. Une durée différente doit être justifiée dans le manifeste et rester compatible avec le protocole normatif.

## Audit des sources au 2026-09-01

| Candidat ou espace | Disponibilité | Licence et provenance | Caractéristiques vérifiables | Décision |
|---|---|---|---|---|
| SoccerNet Tracking, chemin documenté `data/external/soccernet` | Absent | L'accès et les conditions SoccerNet doivent être acceptés pour l'archive réellement utilisée | Aucun média local à sonder | Non sélectionné ; `LICENSE_UNRESOLVED` tant que l'archive et sa licence ne sont pas examinées |
| SoccerNet-v3 H250, chemin documenté `data/external/h250` | Absent | Archive Zenodo citée par la documentation ; licence de l'archive réelle à vérifier | Jeu images/labels attendu, pas une vidéo golden confirmée | Non sélectionné |
| Répertoires locaux `backend/data/video_uploads` et `backend/data/video_results` | Aucun clip football candidat | Les seuls contenus repérés sont des artefacts synthétiques de tests | Petites vidéos générées pour tester l'encodage ; non représentatives d'un match | Rejetés ; une source synthétique ne remplace jamais un profil golden |
| Clip Croatie–Tchéquie mentionné dans le protocole | Fichier et référence absents | `LICENSE_UNRESOLVED` | Durée, caméra, résolution et FPS inconnus | Non sélectionné |
| Variables `VISION_BALLING_GOLDEN_DATA_DIR`, `SOCCERNET_DATA_DIR`, `DATASET_DIR` | Non configurées | Sans objet | Aucun chemin local supplémentaire autorisé par le projet | Aucun candidat additionnel |

Aucun parcours arbitraire du disque utilisateur et aucun téléchargement automatique n'ont été réalisés. En conséquence, les trois entrées du manifeste sont `BLOCKED_MISSING`. Aucun checksum, aucune métadonnée et aucune licence n'ont été inventés.

## Origine, droits et usages

Chaque futur asset doit avoir une provenance vérifiable et une preuve écrite autorisant au minimum le développement, le benchmark reproductible et la démonstration interne envisagée. Le manifeste conserve une référence expurgée, le nom du dataset ou du titulaire, la licence et un résumé des conditions d'usage. La preuve complète peut rester dans un stockage d'accès contrôlé hors Git.

Usage autorisé : validation interne selon la licence enregistrée, comparaison entre versions et revue humaine. Usage interdit : entraînement implicite, redistribution, publication d'images ou extraits, démonstration publique ou usage commercial lorsque la licence ne le permet pas. Une source privée doit en plus documenter sa confidentialité, sa durée de conservation, ses accès et sa procédure de suppression.

Une licence absente ou ambiguë impose `BLOCKED_LICENSE`. Un asset dans cet état ne peut jamais être déclaré golden définitif.

## Sélection et biais connus

La sélection doit couvrir trois captations réellement distinctes, le ballon visible sur une part utile des séquences et suffisamment de terrain pour le module évalué. Le profil difficile doit cumuler plusieurs facteurs tels que compression, flou, faible lumière, occlusions, petit ballon, foule, vibrations ou changements de plan.

Trois extraits ne couvrent ni la diversité mondiale des stades et caméras, ni toutes les résolutions, cadences, conditions météo, couleurs de peau, tenues, niveaux sportifs et styles de réalisation. Ils favorisent nécessairement les compétitions, dispositifs de captation et conditions auxquels l'équipe a légalement accès. Les résultats doivent donc rester séparés par profil et ne pas être présentés comme une généralisation universelle.

## Stockage local hors Git

Les médias restent dans un répertoire local ou sécurisé qui n'est jamais versionné. Le chemin est fourni soit par `--data-dir`, soit par la variable :

```powershell
$env:VISION_BALLING_GOLDEN_DATA_DIR = 'D:\chemin\controle\golden'
```

Le répertoire contient exactement les noms enregistrés dans le manifeste, par exemple :

```text
GOLDEN_DATA_DIR/
  GOLDEN-01-BROADCAST.mp4
  GOLDEN-02-TACTICAL-WIDE.mp4
  GOLDEN-03-DIFFICULT.mp4
```

Le dossier de secours `data/golden/` est explicitement ignoré par Git, mais un stockage externe avec contrôle d'accès est préférable. Aucun chemin absolu local ne doit entrer dans le manifeste.

## Extraction déterministe d'un segment

Un match complet reste inchangé. Avant extraction, enregistrer son SHA-256, la référence de source, la licence, la version exacte de FFmpeg et les timestamps de début et de fin. Produire ensuite un nouveau fichier sans écraser la source :

```powershell
ffmpeg -ss START -to END -i SOURCE -map 0:v:0 -map 0:a? -c copy -avoid_negative_ts make_zero SEGMENT
```

Le manifeste enregistre `source_sha256`, `start_timestamp`, `end_timestamp`, puis le SHA-256, la taille et les métadonnées propres du segment. La commande, les timestamps et la version de FFmpeg font partie du journal de constitution hors Git. Si une coupe par copie de flux n'est pas techniquement exploitable, toute autre transformation doit être documentée et ne peut pas être confondue avec l'original.

## Vérification et passage à READY

Exécuter depuis la racine du dépôt :

```powershell
python scripts/verify_golden_videos.py --manifest data/manifests/golden_videos_v1.json
```

Le vérificateur contrôle le schéma, l'unicité des IDs, les collisions de checksum, la présence du fichier, son SHA-256, sa taille, sa licence et ses métadonnées FFprobe. Un checksum ou une métadonnée incompatible est `FAIL`; un fichier absent est `BLOCKED_MISSING`; une licence absente est `BLOCKED_LICENSE`.

Après l'intégrité et les droits, chaque asset doit passer sans pré-transcodage manuel : pipeline Chapitre 2, FFprobe H.264/avc1/yuv420p/timestamps, Chrome, Edge, Firefox s'il existe, réutilisation à configuration identique et nouvelle `analysis_key` après changement d'un threshold. Ces preuves sont enregistrées avant de mettre `pipeline_validation.status` et l'asset à `READY`.

## Versionnement et remplacement

L'ID de profil ne change jamais. Tout remplacement crée une nouvelle version immuable, un nouveau checksum et une nouvelle validation ; l'ancienne entrée et ses preuves restent traçables dans l'historique Git. Une collision de checksum entre IDs doit être justifiée explicitement, sinon le manifeste est invalide. Un changement silencieux de média, de segment ou de licence est interdit.

Les annotations, splits, CVAT, entraînements et benchmarks H250 ne font pas partie du Chapitre 3A. Ils ne commencent qu'après verrouillage des trois médias et décision explicite du Chapitre 3B.
