# Métriques de réussite V1 — VISION-BALLING

- Version : 1.0
- Date : 2026-08-30
- Statut : Accepted — cibles à confirmer par benchmark

## Navigation du chapitre 0

- [Contrat produit V1](./product_contract_v1.md)
- [Protocole des vidéos golden](./golden_videos_protocol.md)
- [Priorités du backlog V1](./backlog_priorities_v1.md)
- [ADR 0001 — Périmètre de l’analyse tactique assistée](../adr/0001-assisted-tactical-analysis-scope.md)

## Référentiel V1 commun

Les formulations de cette section sont normatives et reprises sans variation dans les cinq documents du chapitre 0.

**Promesse produit.** « Un atelier d’analyse tactique assistée qui transforme une vidéo football existante en une séquence tactique vérifiable : joueurs et ballon suivis, mini-terrain synchronisé, métriques spatiales compréhensibles, événements corrigibles et rapport relié aux moments vidéo. »

**Cible primaire.** Analyste ou coach d’un club amateur, semi-professionnel, universitaire, d’une académie ou d’un centre de formation qui possède déjà une vidéo, mais ne dispose pas d’un service data professionnel.

**Définition de la V1.** La V1 est un atelier post-match assisté avec correction humaine. Elle transforme des extraits exploitables de 30 secondes à 15 minutes en un état de jeu vérifiable, puis en éléments de décision sourcés. Elle n’est ni un système autonome de compréhension complète du match, ni un fournisseur de tracking certifié.

**Périmètre vidéo.** Vidéos de 30 secondes à 15 minutes ; MP4, MOV ou MKV validés ; 720p ou 1080p ; vue tactique, caméra fixe, wide-angle ou broadcast monocaméra exploitable ; traitement asynchrone post-match ; aucune obligation de caméra propriétaire ; aucune prise en charge live ; aucun match complet de 90 minutes garanti dans la première bêta.

**Cinq familles de métriques V1.**

1. largeur de l’équipe ;
2. longueur du bloc ;
3. centroid robuste de l’équipe ;
4. surface occupée ou compacité spatiale ;
5. distances inter-lignes.

**Non-promesses V1.** La V1 ne garantit pas :

- l’identité nominative automatique des joueurs ;
- une reconnaissance faciale ;
- la position réelle des joueurs hors champ ;
- une précision métrique lorsque la calibration est insuffisante ;
- une distance physique certifiée ;
- une analyse tactique entièrement automatique ;
- la reconnaissance de toutes les passes, tirs, fautes ou possessions ;
- une analyse live ;
- un traitement robuste de tous les types de captation ;
- un match complet de 90 minutes ;
- une équivalence avec des fournisseurs professionnels de tracking data.

**Principe de développement.** Toute fonctionnalité doit contribuer directement à la chaîne « vidéo → état de jeu → décision ». Dans le cas contraire, elle est rejetée, différée ou explicitement classée hors périmètre V1.

## 1. Statut des chiffres

Chaque nombre publié doit porter l’un des statuts suivants :

- **baseline démontrée** : résultat reproductible, lié à un commit, une configuration, un actif checksummé et un protocole ;
- **cible indicative à confirmer** : objectif de conception, non présenté comme performance actuelle ;
- **`TBD — benchmark requis`** : valeur non démontrée ou seuil qui ne peut pas encore être fixé honnêtement.

L’audit au HEAD `2927185d270e512ad22fc7cb9723b9b35b87156a` confirme l’existence de frameworks et tests synthétiques de détection/tracking, mais aucun rapport de benchmark public versionné ni aucun actif golden disponible. Aucune baseline quantitative vidéo n’est donc démontrée dans ce document.

Les objectifs d’intégrité exprimés par `0` ou `100 %` sont eux aussi des cibles indicatives à confirmer par mesure. Leur statut indicatif ne rend pas acceptable une violation des règles produit : aucune métrique simulée, aucune position métrique sur calibration invalide et aucun nombre de rapport sans source.

Les mesures sont rapportées séparément pour `GOLDEN-01-BROADCAST`, `GOLDEN-02-TACTICAL-WIDE` et `GOLDEN-03-DIFFICULT`. Une moyenne globale ne doit pas masquer un échec de profil.

## 2. Métrique produit principale

**Temps humain nécessaire pour produire une analyse tactique validée de cinq minutes de vidéo.**

Le chronomètre mesure le temps humain actif depuis l’import validé jusqu’à l’approbation d’un rapport répondant au contrat produit. Le temps d’attente machine est mesuré séparément. Le protocole compare :

1. une réalisation manuelle de référence avec les mêmes sorties attendues ;
2. le workflow VISION-BALLING partant de la même vidéo et de la même vérité disponible ;
3. la qualité finale, qui doit rester au moins équivalente selon une grille de validation gelée.

Cette métrique est prioritaire parce que le produit vise une décision tactique validée, pas l’accumulation de boîtes ou de fonctions. Plus de détections peut augmenter les corrections ; plus de fonctionnalités peut allonger le parcours ; un traitement rapide peut produire un rapport inutilisable. Le temps humain, sous contrainte de qualité et de provenance, mesure directement la valeur promise à la cible primaire.

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Temps humain pour 5 min validées | Temps actif nécessaire à une personne qualifiée pour obtenir une analyse validée de cinq minutes | Somme des périodes actives d’import, revue, correction et validation ; comparaison appariée au manuel | min humaines / 5 min vidéo | Les trois golden videos, tâches et grille identiques | `TBD — benchmark requis` | Cible chiffrée `TBD — étude utilisateur requise` ; réduction démontrée sans baisse de qualité | `TBD — benchmark requis` | Dépend de l’expérience, de la vue, du niveau d’annotation et du nombre de corrections ; rapporter médiane et dispersion |

## 3. Ingestion

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Taux de jobs valides terminés | Part des vidéos conformes au profil et acceptées qui atteignent `completed` avec artefacts lisibles | jobs valides terminés / jobs valides lancés | % | Trois golden videos et matrice de conteneurs autorisés | `TBD — benchmark requis` | Au moins 95 %, cible indicative à confirmer | Moins de 95 % sur le protocole accepté | N’évalue ni la qualité des détections ni les refus d’entrées invalides |
| Qualité des refus | Entrées invalides rejetées avant calcul coûteux avec motif exploitable | revue d’un catalogue d’erreurs gelé ; taux de codes/motifs corrects | % de cas correctement classés | Corpus léger de cas invalides, à créer | `TBD — benchmark requis` | 100 % des cas critiques produisent un refus explicite, cible indicative à confirmer | Une entrée manifestement illisible passe en traitement ou une erreur est muette | Le catalogue doit couvrir les formats et limites réels de la bêta |

## 4. Encodage

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Compatibilité navigateur | Lecture complète de la vidéo annotée, seek et durée cohérente | matrice manuelle automatisable sur versions gelées | navigateurs réussis / testés | Sorties des trois golden videos | `TBD — benchmark requis` ; commande H.264/AAC testée synthétiquement seulement | Chrome, Firefox et Edge, cible indicative à confirmer | Échec du parcours critique sur un navigateur de la matrice | Ne couvre pas tous les appareils, OS ou accélérateurs matériels |
| Fidélité temporelle | Écart entre timestamps source et sortie | erreur absolue sur points de contrôle répartis | ms ou frames | Trois golden videos | `TBD — benchmark requis` | `TBD — benchmark requis` | Dérive qui désynchronise frame, mini-carte ou rapport | Les flux à fréquence variable nécessitent un protocole dédié |

## 5. Détection des joueurs/personnes

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| mAP personnes à IoU 0,5 | Précision moyenne des détections visibles de personnes | protocole mAP@0.5 par frame annotée | score [0,1] | Trois golden videos et domaine V1 annoté | `TBD — benchmark requis` | Au moins 0,85, cible indicative à confirmer | `TBD — benchmark requis` ; cible manquée bloque l’acceptation tant qu’aucun seuil révisé n’est accepté | Une personne détectée n’est pas nécessairement un joueur ; rapporter par vue et taille apparente |
| Rappel personnes | Part des personnes visibles annotées retrouvées | TP / (TP + FN) au seuil gelé | score [0,1] | mêmes références | `TBD — benchmark requis` | `TBD — benchmark requis` | `TBD — benchmark requis` | Sensible aux occlusions et sorties de champ |

## 6. Détection du ballon

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Précision ballon | Part des détections ballon correspondant à une annotation visible | TP / (TP + FP) au seuil et à l’IoU gelés | score [0,1] | Trois golden videos, frames avec et sans ballon | `TBD — benchmark requis` | Au moins 0,70, cible indicative à confirmer | `TBD — benchmark requis` ; cible manquée bloque l’acceptation tant qu’aucun seuil révisé n’est accepté | Ne mesure pas les frames où le ballon est absent ou non annotable |
| Rappel ballon | Part des ballons visibles annotés retrouvés | TP / (TP + FN) | score [0,1] | mêmes références | `TBD — benchmark requis` | Au moins 0,65, cible indicative à confirmer | `TBD — benchmark requis` | Distinguer visibilité réelle, occlusion et taille sous-pixel |

## 7. Tracking des joueurs/personnes

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| HOTA personnes | Qualité conjointe de détection et d’association | protocole TrackEval gelé | score [0,1] | Pistes anonymes des golden videos | `TBD — benchmark requis` | `TBD — benchmark requis` | `TBD — benchmark requis` | Une piste stable ne donne pas une identité nominative |
| IDF1 personnes | Cohérence des identités anonymes dans le temps | définition TrackEval/IDF1 | score [0,1] | mêmes références | `TBD — benchmark requis` | `TBD — benchmark requis` | `TBD — benchmark requis` | Rapporter changements de plan et occlusions séparément |

## 8. Tracking du ballon

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Erreur de centre observé | Distance image entre centre suivi observé et vérité terrain | médiane et P95 de la distance euclidienne normalisée par diagonale | % diagonale image | Frames annotées ballon | `TBD — benchmark requis` | `TBD — benchmark requis` | `TBD — benchmark requis` | Ne devient pas une distance terrain sans calibration valide |
| Prédictions correctement qualifiées | Positions extrapolées étiquetées `predicted`, sans confiance de détection ni confusion avec une observation | audit du schéma et de l’interface sur toutes les prédictions | % | Séquences d’occlusion des golden videos | `TBD — benchmark requis` | 100 %, cible indicative à confirmer et règle d’intégrité | Une prédiction présentée comme observation | La correction de trajectoire est mesurée séparément de son étiquetage |

## 9. Classification des équipes et rôles

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Macro-F1 équipes | F1 moyen par équipe sur joueurs visibles, après exclusion des cas annotés indéterminés | moyenne non pondérée des F1 de classes | score [0,1] | Golden videos, sous-ensemble à maillots distincts | `TBD — benchmark requis` | Au moins 0,90 lorsque les maillots sont distincts, cible indicative à confirmer | `TBD — benchmark requis` | Ne vaut pas pour maillots proches, gardiens, arbitres ou changements de tenue |
| Taux d’abstention justifiée | Cas ambigus laissés inconnus plutôt que forcés | abstentions correctes / cas ambigus annotés | % | `GOLDEN-03-DIFFICULT` | `TBD — benchmark requis` | `TBD — benchmark requis` | `TBD — benchmark requis` | Un taux élevé peut masquer une faible couverture ; publier les deux |

## 10. Calibration du terrain

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Erreur médiane tactique | Écart terrain entre points projetés et points de référence | médiane des distances sur points indépendants | m | `GOLDEN-02-TACTICAL-WIDE` | `TBD — benchmark requis` | Au plus 1,5 m, cible indicative à confirmer | `TBD — benchmark requis` ; aucune position métrique si validité refusée | Dépend des points visibles, de la distorsion et de la qualité de la référence |
| Erreur médiane broadcast | Même mesure sur segments broadcast exploitables | même protocole, segmenté par plan | m | `GOLDEN-01-BROADCAST` | `TBD — benchmark requis` | Au plus 2,5 m, cible indicative à confirmer | `TBD — benchmark requis` ; aucune position métrique si validité refusée | Ne s’applique pas aux plans non calibrables |
| Garde-fou d’invalidité | Absence totale de coordonnées/distances terrain lorsque la calibration est invalide | audit de toutes les sorties invalides | % de violations | Trois golden videos | `TBD — benchmark requis` | Zéro violation, cible indicative à confirmer et règle d’intégrité | Toute position métrique émise malgré une calibration invalide | Ne juge pas la qualité d’une calibration déclarée valide |

## 11. État de jeu 2D

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Erreur de position 2D | Écart entre position projetée d’un objet visible et référence | médiane et P95 par classe, équipe et profil | m | Golden videos calibrables | `TBD — benchmark requis` | `TBD — benchmark requis` | `TBD — benchmark requis` | Aucune imputation hors champ ; dépend des erreurs amont |
| Couverture valide | Part des frames où un état 2D conforme peut être émis | frames valides / frames totales | % | Trois golden videos | `TBD — benchmark requis` | `TBD — benchmark requis` | `TBD — benchmark requis` | Une couverture basse peut être honnête sur le profil difficile |

## 12. Événements simples

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Précision des passes candidates | Part des passes proposées correspondant à la vérité annotée dans la tolérance gelée | TP / (TP + FP) | score [0,1] | Golden videos avec passes annotables | `TBD — benchmark requis` | Au moins 0,80, cible indicative à confirmer | `TBD — benchmark requis` | Une passe reste candidate avant correction ; dépend du ballon et de l’équipe |
| Rappel des passes candidates | Part des passes annotées proposées | TP / (TP + FN) | score [0,1] | mêmes références | `TBD — benchmark requis` | Au moins 0,65, cible indicative à confirmer | `TBD — benchmark requis` | La V1 ne garantit pas la reconnaissance de toutes les passes |
| Charge de correction événements | Nombre d’actions humaines pour valider une minute | créations + suppressions + déplacements + confirmations | actions/min vidéo | mêmes références | `TBD — benchmark requis` | `TBD — étude utilisateur requise` | `TBD — benchmark requis` | Une confirmation triviale ne vaut pas une correction complexe |

## 13. Cinq familles de métriques tactiques

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Erreur largeur équipe | Écart entre étendue latérale robuste calculée et référence manuelle avec même sélection | erreur absolue et relative par frame valide | m, % | Golden tactique et broadcast calibrables | `TBD — benchmark requis` | `TBD — benchmark requis` | Toute valeur en m sur calibration invalide | Joueurs hors champ non imputés ; nombre de joueurs fourni |
| Erreur longueur du bloc | Écart entre étendue longitudinale robuste et référence | même protocole | m, % | mêmes références | `TBD — benchmark requis` | `TBD — benchmark requis` | Toute valeur en m sur calibration invalide | Sensible à l’orientation et aux extrêmes |
| Erreur du centroid robuste de l’équipe | Distance entre le centroid robuste calculé et la référence | distance euclidienne par frame valide | m | mêmes références | `TBD — benchmark requis` | `TBD — benchmark requis` | Coordonnée terrain sans calibration valide | Définition robuste et joueurs inclus doivent être identiques |
| Erreur surface/compacité | Écart de surface ou d’indice selon formule versionnée | erreur absolue/relative ; unités séparées | m² ou indice documenté | mêmes références | `TBD — benchmark requis` | `TBD — benchmark requis` | Surface métrique sur calibration invalide ou géométrie dégénérée | L’aire visible n’est pas l’occupation réelle hors champ |
| Erreur distances inter-lignes | Écart entre lignes validées et référence | erreur absolue par paire de lignes | m | frames où les lignes sont annotables | `TBD — benchmark requis` | `TBD — benchmark requis` | Valeur si lignes ou calibration invalides | La formation et les rôles peuvent être ambigus |
| Intégrité de provenance | Valeurs disposant de définition, unité, source, prérequis, méthode, confiance, invalidité et frames/positions | valeurs conformes / valeurs affichées | % | Toute sortie UI/API/rapport | `TBD — audit requis` | 100 %, cible indicative à confirmer et règle d’intégrité | Toute valeur orpheline ou simulée présentée comme réelle | Ne garantit pas à elle seule la justesse du calcul |

## 14. Rapport et RAG

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Affirmations quantitatives sourcées | Nombre du rapport relié à une donnée, formule, version et intervalle vidéo | affirmations quantitatives sourcées / total | % | Rapports des trois golden videos | `TBD — audit requis` | 100 %, cible indicative à confirmer et règle d’intégrité | Une seule affirmation quantitative sans source | Une source existante peut encore être erronée ; vérifier séparément |
| Séparation des niveaux | Constat, interprétation et recommandation explicitement distingués | grille de revue | % de sections conformes | rapports golden | `TBD — audit requis` | 100 % des sections concernées, cible indicative à confirmer | Une recommandation présentée comme fait | Requiert une grille et des relecteurs cohérents |
| Hallucinations factuelles | Actions, identités ou mesures absentes inventées par le RAG | nombre d’énoncés non soutenus | compte | rapports golden et cas négatifs | `TBD — benchmark requis` | Zéro, cible indicative à confirmer et règle d’intégrité | Toute invention non signalée | La couverture du jeu de questions borne la conclusion |

## 15. Expérience utilisateur

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Réussite du parcours critique | Importer, suivre, corriger, valider et exporter sans assistance | utilisateurs réussissant / utilisateurs testés | % | scénario de 5 min sur golden video | `TBD — étude utilisateur requise` | `TBD — étude utilisateur requise` | `TBD — étude utilisateur requise` | Segmenter par expérience et navigateur |
| Aucune métrique simulée | Valeur de démonstration absente ou explicitement étiquetée comme telle et isolée des résultats | audit exhaustif UI | violations | toutes les vues | Baseline démontrée par audit : violations présentes dans le frontend au HEAD audité | Zéro violation, cible indicative à confirmer et règle d’intégrité | Une valeur statique présentée comme calculée | L’audit doit être répété à chaque version |
| Compréhension de l’incertitude | Utilisateur distingue observation, prédiction, absence et invalidité | test de compréhension sur scénarios | % de réponses correctes | parcours golden | `TBD — étude utilisateur requise` | `TBD — étude utilisateur requise` | `TBD — étude utilisateur requise` | Dépend de la formulation et du niveau de la cible |

## 16. Coût et performance système

| Nom | Définition | Formule ou protocole | Unité | Référence | Baseline actuelle | Cible V1 | Seuil d’échec | Limites d’interprétation |
|---|---|---|---|---|---|---|---|---|
| Temps de traitement | Temps mur entre début du worker et artefacts disponibles | fin - début, par minute vidéo | min/min vidéo | trois golden videos ; CPU/GPU gelés | `TBD — benchmark requis` | `TBD — benchmark et budget requis` | `TBD — benchmark requis` | Toujours publier matériel, modèle, échantillonnage et concurrence |
| Coût de calcul | Coût direct estimé d’un job et consommation de ressources | coût worker + stockage + appels externes | EUR/job, GPU-min, CPU-min | mêmes références | `TBD — benchmark requis` | `TBD — budget produit requis` | `TBD — budget produit requis` | Ne comprend pas le temps humain, mesuré séparément |
| Reprise et durabilité | Jobs récupérables après interruption sans résultat incohérent | scénarios d’incident réussis / testés | % | matrice d’incidents à créer | `TBD — benchmark requis` | 100 % des scénarios critiques acceptés, cible indicative à confirmer | Perte silencieuse ou résultat partiel marqué complet | Le système actuel `BackgroundTasks` et stockage local n’établit pas cette capacité |
| Isolation du cache | Résultat réutilisé uniquement si source, modèle, pipeline et configuration correspondent | collisions erronées / cas testés | compte | matrice de configurations | Baseline fonctionnelle connue : clé actuelle principalement fondée sur SHA-256 source, donc insuffisante | Zéro collision erronée, cible indicative à confirmer et règle d’intégrité | Toute réutilisation inter-configuration | Exige des versions et checksums complets, pas seulement un nom de modèle |

## 17. Règles de publication

- Publier les numérateurs, dénominateurs, exclusions et intervalles d’incertitude pertinents.
- Ne jamais convertir un taux apparent de présence du ballon en rappel sans vérité terrain.
- Séparer observations et prédictions ; les prédictions n’augmentent pas le rappel de détection.
- Ne pas agréger les trois golden videos sans publier aussi leurs résultats séparés.
- Ne jamais présenter une cible indicative comme une baseline actuelle.
- Toute révision d’une cible exige une décision documentée, motivée par un benchmark ou un besoin produit, et ne réécrit pas les résultats historiques.
