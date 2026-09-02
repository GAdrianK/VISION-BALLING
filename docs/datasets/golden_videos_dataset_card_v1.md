# Dataset card — Golden Videos V1

- Version : 1.1.0
- Date de verrouillage : 2026-09-02
- Statut : `READY` — trois assets canoniques vérifiés
- Manifeste : [`../../data/manifests/golden_videos_v1.json`](../../data/manifests/golden_videos_v1.json)
- Protocole normatif : [`../product/golden_videos_protocol.md`](../product/golden_videos_protocol.md)

## Objectif et périmètre

Les trois golden videos forment le jeu de validation interne stable de VISION-BALLING pour détecter les régressions du pipeline vidéo et du parcours de revue. Elles ne constituent ni un dataset d'entraînement, ni une preuve de généralisation, ni un benchmark de qualité de détection. Le verrou du benchmark est le SHA-256 de chaque asset enregistré dans le manifeste, et non la capacité d'une future version de FFmpeg à reproduire le même bitstream.

Les identités logiques immuables sont :

- `GOLDEN-01-BROADCAST` : captation TV élevée avec panoramiques, zooms et jeu continu ;
- `GOLDEN-02-TACTICAL-WIDE` : panorama tactique fixe couvrant le terrain entier, avec joueurs et ballon de petite taille ;
- `GOLDEN-03-DIFFICULT` : captation difficile avec mouvement, vibrations, occlusions, reflets, foule et pertes du terrain.

`GOLDEN-03-DIFFICULT` dure environ 48 secondes, contrairement aux deux autres goldens de quatre minutes. Ce choix est volontaire : sa valeur vient de sa difficulté et non de sa durée. Il est conservé intégralement, sans stabilisation, débruitage, correction de luminosité, recadrage, agrandissement ou retouche.

## Registre d'intégrité

| ID | Source acquise | SHA-256 source | Asset canonique | SHA-256 golden | Taille golden |
|---|---|---|---|---|---:|
| `GOLDEN-01-BROADCAST` | `GOLDEN-01-source.webm` — 1 667 327 404 octets | `6bb488faa3ff13e14a15a2973bcec7afd44ae70abb19e35efc6b7d258382eafc` | `GOLDEN-01-BROADCAST.mp4` | `9bfa4242b1512799c45d802f650cc76bf519b248c54254a7fecdd236f21bd39b` | 784 489 173 octets |
| `GOLDEN-02-TACTICAL-WIDE` | `GOLDEN-02-source.mp4` — 3 576 120 841 octets | `4ca0cc860902c9eebe7c268167b7f65c495aa01effce0688fca710d03caf1eb4` | `GOLDEN-02-TACTICAL-WIDE.mp4` | `1cec8e8b8ac0ceff71352821cba1dbf4d83da4a834f82209fba323285ae1731e` | 260 011 572 octets |
| `GOLDEN-03-DIFFICULT` | `GOLDEN-03-source.mp4` — 13 441 686 octets | `804876b65364612e56ee9ca078023e9ce5c473cea9887b67d44fac5f07ad14e9` | `GOLDEN-03-DIFFICULT.mp4` | `804876b65364612e56ee9ca078023e9ce5c473cea9887b67d44fac5f07ad14e9` | 13 441 686 octets |

Pour `GOLDEN-03-DIFFICULT`, les checksums source et golden sont identiques parce que la vidéo extraite de la distribution officielle est utilisée octet pour octet ; seul son nom local change. Le checksum du conteneur ZIP n'est pas utilisé comme checksum vidéo.

## Métadonnées des assets canoniques

| ID | Segment source | Durée conteneur | FPS exact | Images | Résolution | Codec | Pixel format | Start time |
|---|---:|---:|---:|---:|---:|---|---|---:|
| `GOLDEN-01-BROADCAST` | 03:00–07:00 | 240,021333 s | 25/1 | 6 000 | 3840×2160 | H.264 / `avc1` | `yuv420p` | 0,058667 s |
| `GOLDEN-02-TACTICAL-WIDE` | 08:00–12:00 | 240,021333 s | 25/1 | 6 000 | 4096×1080 | H.264 / `avc1` | `yuv420p` | 0,058667 s |
| `GOLDEN-03-DIFFICULT` | fichier complet | 48,460045 s | 29/1 | 1 405 | 1280×720 | H.264 / `avc1` | `yuv420p` | 0 s |

Les durées ci-dessus viennent de `ffprobe` sur les fichiers réellement verrouillés. Pour les deux segments réencodés, la piste vidéo contient exactement 6 000 images et dure 240 secondes ; la durée conteneur légèrement supérieure inclut les timestamps audio.

## Préparation déterministe

Les sources et assets restent distincts sous `data/golden/sources/` et `data/golden/assets/`. Les coupes par copie de flux n'ont pas été retenues pour `GOLDEN-01` et `GOLDEN-02`, car les frontières auraient dépendu des images clés et n'auraient pas garanti les bornes temporelles demandées. Les deux segments ont donc été réencodés de façon contrôlée avec FFmpeg 9.0 (`ffmpeg version 9.0-full_build-www.gyan.dev`) : H.264, preset `veryfast`, CRF 20, `yuv420p`, cadence constante à 25 fps, audio AAC 128 kbit/s, `faststart`, timestamps rendus non négatifs et métadonnées supprimées.

```powershell
ffmpeg -hide_banner -loglevel error -stats -y -ss 00:03:00.000 -i data/golden/sources/GOLDEN-01-source.webm -t 240.000 -map 0:v:0 -map 0:a? -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 25 -fps_mode cfr -c:a aac -b:a 128k -movflags +faststart -avoid_negative_ts make_zero -map_metadata -1 data/golden/assets/GOLDEN-01-BROADCAST.mp4

ffmpeg -hide_banner -loglevel error -stats -y -ss 00:08:00.000 -i data/golden/sources/GOLDEN-02-source.mp4 -t 240.000 -map 0:v:0 -map 0:a? -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -r 25 -fps_mode cfr -c:a aac -b:a 128k -movflags +faststart -avoid_negative_ts make_zero -map_metadata -1 data/golden/assets/GOLDEN-02-TACTICAL-WIDE.mp4
```

Le fichier SoccerTrack sélectionné a été acquis seul depuis son Google Drive officiel par requêtes HTTP avec plages d'octets contrôlées, car la réponse monolithique était bloquée par le quota. Chaque réponse partielle a été validée par `Content-Range`, code HTTP 206 et nombre d'octets avant assemblage positionnel ; la taille, le SHA-256 et le décodage du fichier complet ont ensuite été contrôlés.

Pour MUVY, seul le membre exact `MUVY_v01/sport_events/soccer/soccer_event_08/cam_06_S08/vid_WiWXQnEjQTs.mp4` a été extrait de la distribution ZIP officielle. L'asset a été copié sans transformation temporelle ni audiovisuelle, puis renommé. Aucun autre événement MUVY n'a été extrait ni conservé.

## Golden Dataset Attribution

### GOLDEN-01-BROADCAST

- Origine et auteur : Wikimedia Commons, NK Nafta 1903.
- Licence : CC BY 3.0 Unported (`LICENSE_CONFIRMED_COMMERCIAL`).
- Source : [page du fichier Wikimedia Commons](https://commons.wikimedia.org/wiki/File:U17_-_2._SKL_-_22._krog_-_Nafta_1903_2-2_Hajdina_-_1._pol%C4%8Das_-_1-2.webm).
- Segment : 03:00 à 07:00.
- Justification : caméra broadcast élevée, panoramiques, zooms et jeu continu représentatifs.
- Modifications : extrait, réencodé avec les paramètres contrôlés ci-dessus et renommé.
- Limites : un seul match et un seul dispositif de captation ; UHD coûteux à traiter ; cadrage et conditions lumineuses non représentatifs de toutes les productions.

Attribution : « NK Nafta 1903 — CC BY 3.0 Unported — extrait 03:00–07:00, réencodé et renommé pour le benchmark VISION-BALLING. »

### GOLDEN-02-TACTICAL-WIDE

- Origine et auteur : SoccerTrack v2, Atom Scott et coauteurs.
- Licence : CC BY 4.0, y compris les fichiers vidéo/annotations selon `LICENSE-DATA` (`LICENSE_CONFIRMED_COMMERCIAL`).
- Source : [site officiel SoccerTrack v2](https://atomscott.github.io/SoccerTrack-v2/), match 118577, `videos/118577/118577_panorama_1st_half.mp4`.
- Segment : 08:00 à 12:00.
- Justification : caméra tactique panoramique fixe, terrain entier, forte densité et objets de petite taille.
- Modifications : extrait, réencodé avec les paramètres contrôlés ci-dessus et renommé.
- Limites : format atypique 4096×1080, une seule rencontre, caméra fixe non représentative des captations broadcast.

Attribution : « SoccerTrack v2 — Atom Scott et coauteurs — CC BY 4.0 — extrait 08:00–12:00, réencodé et renommé pour le benchmark VISION-BALLING. »

### GOLDEN-03-DIFFICULT

- Origine et auteurs : MUVY v1.0.0 ; Larissa Pessoa, Elton Alencar, Fernanda Costa, Guilherme Souza et Rosiane de Freitas.
- Licence : CC BY 4.0 (`LICENSE_CONFIRMED_COMMERCIAL`).
- Source : [DOI 10.5281/zenodo.13883315](https://doi.org/10.5281/zenodo.13883315), `soccer_event_08`, `cam_06_S08`, identifiant source `WiWXQnEjQTs`.
- Segment : fichier complet, environ 48,46 secondes.
- Justification : mouvement fort, vibrations, occlusions, reflets, foule, ballon petit ou distant et pertes du terrain.
- Modifications : extraction du membre ZIP exact et renommage uniquement ; aucune retouche.
- Limites : clip court, instable et difficile ; sa mauvaise qualité de détection éventuelle est intentionnelle et ne constitue pas un échec d'ingestion.

Attribution : « MUVY v1.0.0 — Larissa Pessoa, Elton Alencar, Fernanda Costa, Guilherme Souza et Rosiane de Freitas — DOI 10.5281/zenodo.13883315 — CC BY 4.0 — fichier complet renommé pour le benchmark VISION-BALLING. »

## Validation pipeline et reproductibilité

Les trois assets canoniques ont été soumis directement au pipeline 0.4.0 au commit `86815a75e5e1eca621c83d73bb6cc4324d75cc05`, sans retranscodification manuelle intermédiaire. Profil nominal : HOG OpenCV 4.14.0, modèle `opencv-hog-default-people-detector`, checksum modèle `e9ba6f8d56f1a0a020ba3747fdfd7d0d6756dd308cd3c3028efd25529b526366`, CPU, échantillonnage 10, seuil global 0,45, tracker IoU 1.0. Le contrôle de configuration différente n'a changé que le seuil global, à 0,46.

| ID | Analysis ID nominal | Analysis key nominal | Traitement | Cache identique | Variante à 0,46 |
|---|---|---|---:|---|---|
| `GOLDEN-01-BROADCAST` | `analysis_dc0ee3467ed74783a82435e3fce30424` | `76b30f1d70a5b7968ca46892f09c21d63ce84f6f60767deb08e5d6d1f4c3c542` | 1 758,953 s | PASS — même ID, `reused=true` | PASS — `analysis_d5957ab2f2a2487881f58538e316f648`, key `b46e529f00349011895d01cbf00aafbe83c9c17e2a6fbd393aad7264d9a05df7`, `reused=false` |
| `GOLDEN-02-TACTICAL-WIDE` | `analysis_404bec6cc56f4f3498385750e34add8c` | `0dc8ae28e47ee1bca00e1a44bb88e2c8821887937df6d40eca23e5537c053e6d` | 836,625 s | PASS — même ID, `reused=true` | PASS — `analysis_dd440fdcfdff493fb457ec518990753b`, key `193b038c7c4f2bd954a747aa1a37c0e65d618ace61b7bc937dd6675f538e288b`, `reused=false` |
| `GOLDEN-03-DIFFICULT` | `analysis_336f19bbe0cc46ebb6faf304b03b4306` | `1b908c15c8df7659c1e249b5a44d84dc537be08ee087197b470136565de01818` | 38,562 s | PASS — même ID, `reused=true` | PASS — `analysis_a229fca24bd34eebb2c7760004e9ef12`, key `c6c73ec62d7a5b72c1278d5f776abf37721e81c758119b462bb5380f7c2b0fa0`, `reused=false` |

Chaque pipeline nominal a terminé, écrit autant d'images qu'il en a lu et produit une vidéo non vide en H.264, tag `avc1`, `yuv420p`, avec timestamp non négatif et durée cohérente. Les sorties nominales ont été lues avec succès par Chrome et Edge : `metadataLoaded=true`, `readyState=4`, largeur et hauteur strictement positives. Firefox n'était pas installé lors de l'unique contrôle : `BLOCKED — browser unavailable`. Ce blocage navigateur distinct ne retire pas le statut `READY` aux assets.

## Stockage et vérification

Les médias ne sont jamais versionnés. Le stockage local logique est :

```text
data/golden/
  sources/
  assets/
  runs/
```

`data/golden/` est ignoré par Git. Un autre emplacement peut être fourni par `--data-dir` ou `VISION_BALLING_GOLDEN_DATA_DIR`, sans enregistrer de chemin Windows personnel dans le manifeste.

Depuis la racine du dépôt :

```powershell
python scripts/verify_golden_videos.py --manifest data/manifests/golden_videos_v1.json --data-dir data/golden/assets
```

Le résultat attendu pour cette version verrouillée est `PASS=3 FAIL=0 BLOCKED=0`.

## Biais, limites et usages

Trois extraits ne couvrent ni la diversité mondiale des stades et caméras, ni toutes les résolutions, cadences, conditions météo, couleurs de peau, tenues, niveaux sportifs et styles de réalisation. Les résultats doivent rester séparés par profil et ne pas être présentés comme une généralisation universelle.

Usage autorisé : validation et comparaison de versions dans le respect des licences et attributions enregistrées. L'intégration des médias à Git et leur emploi implicite pour l'entraînement sont interdits. Toute redistribution ou publication doit respecter directement la licence de la source concernée et conserver l'attribution et l'indication des modifications.

Tout remplacement futur conserve l'ID logique, mais crée une nouvelle version immuable avec nouveau checksum et validation complète. Un changement silencieux de média, segment ou licence est interdit. Les annotations, splits, CVAT, entraînements et benchmark H250 relèvent des chapitres suivants.
