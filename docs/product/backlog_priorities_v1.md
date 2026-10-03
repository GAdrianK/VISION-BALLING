# Priorités du backlog V1 — VISION-BALLING

- Version : 1.0
- Date : 2026-08-30
- Statut : Accepted — ordre directeur, sans autorisation de commencer le chapitre 1

## Navigation du chapitre 0

- [Contrat produit V1](./product_contract_v1.md)
- [Protocole des vidéos golden](./golden_videos_protocol.md)
- [Métriques de réussite V1](./success_metrics_v1.md)
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

## 1. Lecture des priorités et chapitres

- **P0** : bloque la production de preuves fiables ou entretient une présentation trompeuse ; à traiter avant d’étendre les capacités.
- **P1** : nécessaire pour livrer la V1 définie par le contrat, dans l’ordre de ses dépendances.
- **P2** : hors périmètre V1 ; aucune capacité de ce niveau ne doit détourner les ressources du chemin critique.

| Chapitre de roadmap | Finalité |
|---|---|
| Chapitre 0 | Vision, contrat, golden protocol, critères et priorités |
| Chapitre 1 | Consolidation, intégrité des sorties, actifs golden et benchmark reproductible |
| Chapitre 2 | Perception robuste : modèles, personnes, ballon, tracking, équipes et plans |
| Chapitre 3 | Calibration et état de jeu 2D |
| Chapitre 4 | Correction humaine, événements simples et cinq familles de métriques |
| Chapitre 5 | Rapport sourcé, RAG vidéo, expérience, jobs, stockage et sécurité |
| Chapitre 6+ | Échelle et options futures hors périmètre V1 |

Cet ordre n’autorise pas le démarrage automatique du chapitre suivant. Chaque chapitre doit satisfaire ses propres critères d’entrée et de sortie.

## 2. P0 — Vérité, reproductibilité et fondations

| Élément | Justification | Dépendances | Résultat attendu | Risque s’il est fait trop tôt ou incorrectement | Chapitre |
|---|---|---|---|---|---|
| Consolidation des branches | `main` est à `fbb3621` tandis que le suivi ballon est sur `feat/ball-tracking` à `2927185`; la source de vérité doit être explicite | revue des commits, stratégie d’intégration, worktrees propres | branche de référence unique, historique conservé, fonctions et tests réconciliés | fusion non revue, perte de correctifs ou doublons architecturaux | 1 |
| Correction définitive de l’encodage navigateur | Une commande H.264/AAC et des tests synthétiques existent, sans preuve golden multi-navigateur | FFmpeg disponible, golden videos, matrice Chrome/Firefox/Edge | sorties lisibles, seekables, synchronisées et vérifiées sur la matrice | optimiser le codec avant de geler les entrées peut déplacer les problèmes sans les mesurer | 1 |
| Clé de cache source + modèle + pipeline + configuration | La déduplication actuelle réutilise principalement le SHA-256 source et peut servir un résultat obsolète | schéma de versions, checksum poids, sérialisation canonique config | identité de calcul déterministe, explicable et testée | clé instable causant des recalculs ou clé incomplète causant des collisions | 1 |
| Suppression ou étiquetage des métriques frontend simulées | PPDA, xT, compacité, confiance, phase et positions statiques ressemblent à des sorties réelles | inventaire UI, contrat de provenance | aucune valeur décorative présentée comme calculée ; démos isolées et clairement marquées | supprimer sans alternative peut dégrader la navigation ; étiqueter vaguement maintient la tromperie | 1 |
| Mise à jour de l’adaptateur ByteTrack | L’adaptateur Supervision existe mais doit être validé avec version réelle, mapping et benchmark | dépendance gelée, tests sur sorties de détecteur, annotations MOT | adaptateur compatible, versionné et comparé à une référence reconnue | corriger sans reproduire une incompatibilité peut casser l’association silencieusement | 1 puis 2 |
| Création des vidéos golden | Aucun des trois actifs n’est disponible ; aucun benchmark V1 n’est possible sans eux | droits, sélection, stockage hors Git, protocole accepté | trois actifs manifestés sous IDs stables et vérité terrain révisable | choisir des clips trop faciles, sans droits ou contaminés par l’entraînement | 1 |
| Benchmark reproductible | Les scripts existent mais aucun résultat versionné ne démontre les baselines | golden videos, environnement gelé, métriques définies | rapport par module/profil avec baselines, configs, erreurs et limites | publier des scores sans actifs gelés crée une fausse référence | 1 |
| Documentation comme source de vérité | README et limites disent encore qu’aucune vidéo réelle n’est traitée, alors que le code contient un pipeline | présent chapitre, gouvernance documentaire | hiérarchie documentaire, statut et propriétaire de chaque vérité | réécrire avant consolidation peut remplacer une contradiction par une autre | 1 |

## 3. P1 — Capacités nécessaires à la V1

| Élément | Justification | Dépendances | Résultat attendu | Risque s’il est fait trop tôt ou incorrectement | Chapitre |
|---|---|---|---|---|---|
| Validation complète du modèle H250 | Le profil `0 = ball`, `1 = person` est codé, mais aucun score de domaine n’est démontré | P0 golden + benchmark, poids et licence identifiés | précision/rappel/mAP par classe et profil, seuils gelés | assimiler un class map correct à un modèle performant | 2 |
| Trackers reconnus pour les joueurs | Les IDs IoU sont une baseline ; la V1 a besoin d’associations comparées | détection stable, vérité MOT, adaptateur ByteTrack validé | HOTA/IDF1 mesurés, tracker choisi et fallback documenté | compenser une mauvaise détection par une complexité de tracking prématurée | 2 |
| Benchmark séparé du ballon | Le petit objet exige des seuils et erreurs propres | H250 validé, annotations ballon visibles/absentes | précision, rappel, erreurs et profils difficiles séparés des personnes | une métrique agrégée masquerait l’échec ballon | 2 |
| Classification équipes/arbitres/gardiens | Les `person` actuelles restent des candidats non différenciés | tracks personnes stables, vérité rôles, cas ambigus | équipes corrigibles, rôles utiles et abstention explicite | forcer une classe sur maillots proches ou tracks instables | 2 |
| Détection des changements de plan | Calibration, tracking et métriques ne doivent pas traverser une coupe | frames/temps fiables, golden broadcast | segments de plan, resets contrôlés et provenance par segment | construire la calibration avant la segmentation propage des états invalides | 2 |
| Calibration terrain | Condition des positions et distances métriques | lignes/points visibles, segments, golden tactique/broadcast | transformation versionnée, erreur estimée, statut valide/invalide | produire des mètres avant d’avoir un garde-fou d’invalidité | 3 |
| État de jeu 2D | Objet central entre perception et décision | détection, tracks, équipes, calibration | état synchronisé contenant uniquement positions valides et absences explicites | agréger trop tôt fige les erreurs et encourage l’extrapolation hors champ | 3 |
| Correction humaine | Partie contractuelle du produit, pas un correctif annexe | schémas d’état et provenance stables | corrections réversibles, attribuées et réutilisées par calcul/rapport | concevoir l’UI avant le modèle de correction crée des éditions non traçables | 4 |
| Événements simples | Fournissent des moments navigables sans promettre la compréhension complète | état 2D, ballon, équipes, correction | candidats horodatés, confiance, motifs et édition | viser toutes les passes/tirs avant la perception robuste multiplie les faux faits | 4 |
| Cinq métriques tactiques | Cœur analytique V1 explicitement limité | état 2D valide, équipes, calibration, correction | largeur, longueur, centroid, surface/compacité et inter-lignes avec provenance | calculer sur données image ou joueurs incomplets sans invalidité produit une fausse précision | 4 |
| RAG relié aux données vidéo | Le RAG actuel est séparé du pipeline vidéo | schémas de faits validés, timestamps, métriques versionnées | explications distinguant constat/interprétation/recommandation et citant les sources | brancher le LLM avant la provenance encourage l’invention de faits | 5 |
| Rapport sourcé | Sortie décisionnelle finale de la promesse | corrections, métriques, RAG borné | 100 % des nombres liés à données, méthodes et moments vidéo, objectif indicatif et règle d’intégrité | travailler le style avant l’intégrité rend les erreurs plus convaincantes | 5 |
| Queue de jobs et stockage objet | `BackgroundTasks` et fichiers locaux ne suffisent pas à la reprise et à la concurrence | identité cache, artefacts versionnés, modèle de rétention | workers reprenables, stockage durable, statuts idempotents | distribuer avant stabilisation du contrat augmente la complexité et les coûts | 5 |
| Sécurité et suppression des données | Les vidéos peuvent contenir des données sensibles ou sous droits | modèle de stockage, identité utilisateur minimale, politique de rétention | accès contrôlé, suppression vérifiable, journal et durées de rétention | ajouter des comptes sans cartographie des données crée une sécurité superficielle | 5 |
| Expérience de revue synchronisée | La cible doit passer de la vidéo aux corrections puis à la décision | état 2D, correction, rapport, encodage navigateur | vidéo/mini-carte/timeline synchronisées, incertitudes compréhensibles | polir une visualisation avant les données renforce les signaux décoratifs | 5 |
| Mesure du temps humain | Vérifie la valeur principale plutôt que le volume fonctionnel | parcours complet, golden videos, protocole manuel comparable | médiane et dispersion du temps actif pour cinq minutes validées | mesurer avant stabilisation du parcours donne une baseline non comparable | 5 |

## 4. P2 — Hors périmètre V1

| Élément | Justification du report | Dépendances avant réexamen | Résultat futur éventuel | Risque s’il est fait trop tôt | Chapitre |
|---|---|---|---|---|---|
| Match complet de 90 minutes | La bêta ne le garantit pas | fiabilité 15 min, reprise, budget, stockage | traitement long segmenté et reprenable | coûts et incidents masquent la qualité fondamentale | 6+ |
| Live | Le produit est post-match | latence, streaming, reprise, exploitation temps réel validée | états à faible latence explicitement bornés | contraintes live déforment toute l’architecture V1 | 6+ |
| Réidentification avancée | Les pistes anonymes suffisent au socle | tracking robuste, gouvernance identité, évaluation | continuité inter-plans sans reconnaissance faciale | confusion entre réidentification et identité certaine | 6+ |
| Reconnaissance de numéro | Fragile et non nécessaire aux cinq métriques | résolution, vues, vérité terrain et correction | numéro candidat corrigible | faux numéros présentés comme identités | 6+ |
| Extrapolation hors champ | Une position réelle hors champ n’est pas observable | modèle probabiliste, affichage d’incertitude, validation dédiée | hypothèses visuelles séparées des faits | création de positions fictives utilisées comme mesures | 6+ |
| Pitch control avancé | Dépend de positions, vitesses et hypothèses robustes | état 2D validé, dynamique, calibration, modèle évalué | surface de contrôle explicitement modélisée | visualisation persuasive sans données suffisantes | 6+ |
| xT | Nécessite événements et modèle de valeur validés | possession, événements, zones, corpus adapté | valeur attendue sourcée | valeur statique ou importée sans provenance | 6+ |
| Données physiques | La V1 ne fournit pas de distances certifiées | calibration certifiée, FPS, validation scientifique | mesures physiques avec domaine d’usage borné | risque de décisions de charge sur données non certifiées | 6+ |
| Multi-caméra | Hors captation monocaméra V1 | synchronisation, calibration multi-vues, association | état fusionné multi-vues | explosion du périmètre avant une caméra fiable | 6+ |
| Scouting mondial | Persona non prioritaire et données externes non unifiées | droits, couverture, identité, qualité internationale | recherche de profils à grande échelle | détourne le produit de l’analyse d’une vidéo possédée | 6+ |
| Fonctions commerciales | Exclues du chapitre produit V1 | proposition validée, sécurité et service stable | capacités administratives ultérieures | optimise la vente avant la preuve de valeur | 6+ |
| Paiement | Aucun besoin V1 | fonctions commerciales et conformité | transaction future éventuelle | introduit risques légaux et opérationnels prématurés | 6+ |
| Publicité | Incompatible avec le chemin critique actuel | décision produit ultérieure explicite | `TBD` | détourne l’interface et la gouvernance des données | 6+ |
| Plateforme de captation | Le produit exploite une vidéo existante | décision stratégique distincte | matériel/service séparé éventuel | transforme le produit en concurrent de captation hors mission | 6+ |

## 5. Règles d’arbitrage

1. Un P2 ne remonte pas en P1 parce qu’une bibliothèque ou une démo le rend facile à coder.
2. Une fonctionnalité n’est pas terminée tant que sa qualité, ses refus et sa provenance ne sont pas mesurés.
3. Toute métrique avancée exige ses prérequis de données ; PPDA, xG, xT et pitch control avancé restent hors garantie V1.
4. Les éléments P1 suivent les dépendances « vidéo → état de jeu → décision » ; l’interface ne devance pas la vérité des données.
5. Le [référentiel de réussite](./success_metrics_v1.md) et le [contrat produit](./product_contract_v1.md) priment sur le nombre de fonctionnalités livrées.
