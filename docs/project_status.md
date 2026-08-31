# État vérifiable du projet

Date de référence : branche `chore/repository-consolidation`, base fonctionnelle `3d3cd64`.

Valeurs utilisées : `IMPLEMENTED`, `EXPERIMENTAL`, `DOCUMENTED_ONLY`, `NOT_IMPLEMENTED`, `DEPRECATED`. `IMPLEMENTED` décrit une fonction présente et testable, sans signifier qu'elle est prête pour la production. `EXPERIMENTAL` signale une preuve logicielle partielle ou une validation de domaine insuffisante.

| Capacité | Statut | Preuve dans le dépôt | Limite connue | Prochain chapitre |
|---|---|---|---|---|
| Ingestion vidéo | IMPLEMENTED | `backend/app/api/video_analysis.py`, route `POST /api/video-analysis` | Fichier local et traitement monoprocessus | Chapitre 2 |
| Validation vidéo | IMPLEMENTED | `backend/app/video_analysis/validation.py` et tests associés | Dépend des capacités OpenCV du système | Chapitre 2 |
| Déduplication | IMPLEMENTED | `storage.py::find_completed_by_sha` | Clé limitée au SHA de la source, sans configuration du pipeline | Chapitre ultérieur cache |
| Détecteur heuristique | IMPLEMENTED | `detectors.py`, baseline OpenCV HOG | Personnes uniquement, précision non benchmarkée | Chapitre 2 |
| Détecteur YOLO | EXPERIMENTAL | `YoloDetector`, configuration `VIDEO_DETECTOR` | Dépendance et poids locaux facultatifs, pas de benchmark golden | Chapitre 2 |
| Profil H250 | EXPERIMENTAL | profil `h250` dans `detectors.py`, tests de mapping | Mapping logiciel seulement, pas de validation terrain | Chapitre 2 |
| Suivi des joueurs | EXPERIMENTAL | tracker IoU et adaptateur ByteTrack dans `backend/app/video_analysis/trackers.py` | Identités fragiles aux occultations ; ByteTrack facultatif | Chapitre 2 |
| Suivi du ballon | EXPERIMENTAL | `BallTracker` dans `backend/app/video_analysis/trackers.py`, états `observed` et `predicted`, tests synthétiques | Pas de validation visuelle golden ni gain mesuré | Chapitre 2 |
| Vidéo annotée | IMPLEMENTED | création d'artefact dans `pipeline.py` | Lisibilité et codec dépendent de l'environnement | Chapitre 2 |
| Compatibilité navigateur | EXPERIMENTAL | commande FFmpeg et tests ciblés | Compatibilité observée incomplète sous Linux ; validation multi-navigateurs absente | Chapitre 2 |
| Export JSON | IMPLEMENTED | schémas `1.1.0`, stockage des détections et artefacts | Contrat local encore susceptible d'évoluer | Chapitre 2 |
| Équipes | NOT_IMPLEMENTED | Aucune classification d'équipe dans le pipeline | Aucun rattachement fiable des joueurs | Chapitre équipes |
| Calibration du terrain | NOT_IMPLEMENTED | Aucun module de calibration | Pas de coordonnées terrain métriques | Chapitre calibration |
| État de jeu 2D | NOT_IMPLEMENTED | Aucun schéma d'état 2D | Les détections restent dans l'image | Chapitre calibration |
| Correction humaine | NOT_IMPLEMENTED | Aucun flux d'édition ou de validation | Impossible de corriger une identité ou une équipe | Chapitre correction |
| Possession | NOT_IMPLEMENTED | Absente des schémas vidéo | Nécessite ballon, joueurs, équipes et règles validées | Chapitre métriques |
| PPDA | NOT_IMPLEMENTED | Absente des résultats vidéo | Événements et actions défensives non disponibles | Hors garanties V1 |
| xT | NOT_IMPLEMENTED | Absente des résultats vidéo | Modèle de menace et événements non disponibles | Hors garanties V1 |
| Largeur | NOT_IMPLEMENTED | Absente des résultats vidéo | Nécessite équipes et état 2D validé | Chapitre métriques |
| Profondeur/longueur | NOT_IMPLEMENTED | Absente des résultats vidéo | Nécessite équipes et état 2D validé | Chapitre métriques |
| centroid robuste de l’équipe | NOT_IMPLEMENTED | Absent des résultats vidéo | Nécessite équipes et positions corrigées | Chapitre métriques |
| Compacité | NOT_IMPLEMENTED | Absente des résultats vidéo | Nécessite le centroid robuste de l’équipe et une dispersion validée | Chapitre métriques |
| Transitions | NOT_IMPLEMENTED | Absentes des résultats vidéo | Le corpus RAG n'est pas un détecteur d'événements | Chapitre métriques |
| Rapport vidéo sourcé | NOT_IMPLEMENTED | Aucun rapport reliant assertion, intervalle et preuve vidéo | JSON et vidéo annotée ne constituent pas ce rapport | Chapitre rapport |
| RAG | IMPLEMENTED | `backend/app/services/rag_engine.py`, route `/api/chat` | Corpus local borné ; distinct des métriques vidéo | Maintenance continue |
| Stockage | IMPLEMENTED | `backend/app/video_analysis/storage.py` | Fichiers JSON et artefacts locaux, pas de stockage distribué | Chapitre infrastructure |
| Traitement asynchrone | EXPERIMENTAL | `BackgroundTasks` dans la route vidéo | Non durable, sans reprise après redémarrage | Chapitre infrastructure |
| Benchmark golden | DOCUMENTED_ONLY | `docs/product/golden_videos_protocol.md` | Aucun média, annotation ou résultat golden versionné | Chapitre benchmark |
| Frontend | IMPLEMENTED | `frontend/src/App.jsx`, `VideoAnalysis.jsx`, scripts Vite | Upload et résultats disponibles ; terrain décoratif explicitement non calculé | Chapitre interface |
| Intégration continue | IMPLEMENTED | `.github/workflows/ci.yml` | À confirmer sur GitHub après push ; aucune exécution distante revendiquée | Intégration vers `main` |

## Interprétation

Les tests synthétiques vérifient des comportements logiciels ciblés. Ils ne prouvent ni une précision football, ni une robustesse sur des matchs réels, ni une amélioration du tracking. Les objectifs et seuils de validation se trouvent dans les documents normatifs, pas dans cette matrice.
