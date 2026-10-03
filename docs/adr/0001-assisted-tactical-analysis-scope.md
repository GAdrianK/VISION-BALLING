# ADR 0001 — Périmètre de l’analyse tactique assistée

- Statut : Accepted
- Date : 2026-08-30
- Décideurs : gouvernance produit VISION-BALLING
- Portée : V1 et critères d’architecture des chapitres suivants

## Documents liés

- [Contrat produit V1](../product/product_contract_v1.md)
- [Protocole des vidéos golden](../product/golden_videos_protocol.md)
- [Métriques de réussite V1](../product/success_metrics_v1.md)
- [Priorités du backlog V1](../product/backlog_priorities_v1.md)

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

## Contexte

Le dépôt réunit trois ensembles qui ont évolué sans contrat produit commun :

1. un assistant tactique RAG et un export PDF ;
2. un moteur SQL de statistiques et de comparaison de joueurs ;
3. un pipeline vidéo FastAPI/React comprenant validation, détection, tracking, artefacts et frameworks de benchmark.

Au HEAD audité, le pipeline vidéo possède des abstractions de détecteur, des profils COCO/H250, des trackers personnes, un suivi temporel léger du ballon, un encodage FFmpeg et un stockage local. Il ne possède pas encore la chaîne validée d’équipes, calibration, état de jeu 2D, correction humaine, cinq métriques et rapport vidéo sourcé. Les tests synthétiques prouvent des comportements logiciels ciblés, pas une qualité de domaine.

La documentation est contradictoire : le README présente encore le chatbot comme produit principal et `known_limitations.md` affirme que le système ne traite pas de vraies vidéos, alors qu’un module vidéo existe. Inversement, le frontend montre des valeurs et overlays statiques de PPDA, xT, compacité, confiance, phase et positions qui ne proviennent pas du pipeline. Sans décision d’architecture fonctionnelle, les trois ensembles peuvent continuer à diverger ou à donner une impression de capacité supérieure aux preuves disponibles.

## Décision

VISION-BALLING est un atelier d’analyse tactique assistée avec correction humaine. La vidéo existante de l’utilisateur est l’entrée primaire ; un état de jeu vérifiable est l’interface de données centrale ; une décision tactique sourcée est la sortie utile.

L’architecture fonctionnelle suit l’ordre :

`vidéo → détection → tracking → classification des équipes → calibration du terrain → état de jeu 2D → événements simples → métriques tactiques → correction humaine → rapport sourcé`

La correction humaine est un composant explicite de la V1. Les sorties automatiques restent candidates jusqu’à leur validation lorsque le contrat l’exige. Les états inconnus, absents, prédits et invalides sont distincts et persistent jusqu’aux consommateurs aval.

L’état de jeu 2D devient le contrat entre perception et analyse. Il ne contient aucune position réelle supposée hors champ et aucune coordonnée métrique lorsque la calibration est invalide. Chaque donnée conserve sa provenance : vidéo et checksum, frame et timestamp, modèle et poids, pipeline et configuration, statut observation/prédiction, correction et version.

Les cinq familles du référentiel commun constituent les seules métriques spatiales garanties visées en V1. Le RAG consomme des faits calculés et validés ; il explique, contextualise et recommande sans créer de mesure ou d’identité. Le [contrat produit](../product/product_contract_v1.md) régit la distinction entre constat, interprétation et recommandation.

La qualité est jugée d’abord par le temps humain nécessaire pour produire une analyse tactique validée de cinq minutes, sous contrainte de provenance et de qualité. Le nombre de détections, de modèles ou de fonctions n’est pas une métrique produit principale.

## Options rejetées pour la V1

### Chatbot football généraliste comme produit principal

Rejeté parce qu’il n’unifie pas les trois ensembles autour d’une vidéo possédée par l’utilisateur. Le RAG reste utile comme couche d’explication du résultat, pas comme source de faits vidéo.

### Clone de Hudl, Veo ou SkillCorner

Rejeté parce que ces références recouvrent captation, distribution, données ou services professionnels que la V1 ne peut ni ne doit garantir. Le produit se concentre sur l’atelier post-match assisté pour une cible moins équipée.

### Plateforme de captation

Rejetée parce que la V1 part d’une vidéo existante et n’impose aucune caméra propriétaire. Le matériel, le streaming et la gestion d’un parc de caméras formeraient un autre produit.

### Analyse intégralement automatique

Rejetée parce que détection, équipes, calibration et événements comportent des ambiguïtés irréductibles dans le domaine V1. Cacher la correction humaine transformerait l’incertitude en fausse certitude.

### Match complet dès la première version

Rejeté parce que la fiabilité, la reprise, le coût et le temps de correction doivent d’abord être démontrés sur 30 secondes à 15 minutes. Un match de 90 minutes reste P2.

### Tracker joueurs entièrement maison

Rejeté comme orientation principale. Une baseline IoU peut rester un fallback explicable, mais la V1 doit comparer et adapter des trackers reconnus avant d’investir dans un tracker propriétaire.

### Reconnaissance faciale

Rejetée pour des raisons de périmètre, de droits, de données personnelles et d’absence de nécessité pour les cinq métriques. Une piste anonyme et une correction humaine suffisent au contrat V1.

### Métriques avancées sans prérequis

PPDA, xG, xT, pitch control avancé, données physiques certifiées, valeur de possession complexe et notes automatiques sont rejetés comme garanties V1. Ils exigent des événements, positions, dynamiques, modèles et validations absents. Une visualisation disponible ou une constante frontend ne constitue pas un prérequis satisfait.

## Conséquences positives

- une chaîne de valeur unique permet d’arbitrer le backlog ;
- les trois ensembles du dépôt obtiennent un rôle borné au lieu de se concurrencer ;
- la correction humaine devient mesurable et conçue dès l’état de données ;
- les absences et invalidités empêchent la propagation silencieuse d’une fausse précision ;
- les cinq familles réduisent la surface de validation initiale ;
- les rapports deviennent auditables grâce aux liens vers les frames et calculs ;
- les golden videos et métriques donnent une base de comparaison aux chapitres suivants ;
- l’architecture peut remplacer modèles, trackers, workers et stockage sans changer la promesse.

## Conséquences négatives

- la V1 demande un outil de correction et de provenance, ce qui augmente le travail avant une démonstration complète ;
- certaines vidéos acceptées à l’ingestion resteront partiellement ou totalement non exploitables ;
- des valeurs séduisantes devront disparaître de l’interface tant qu’elles ne sont pas calculées ;
- le produit exposera plus visiblement ses incertitudes et pourra sembler moins automatique ;
- le choix de cinq familles diffère d’une plateforme généraliste et reporte des demandes usuelles comme xT ou PPDA ;
- la constitution d’actifs golden licenciés et annotés nécessite un investissement humain préalable.

## Risques

- la correction peut prendre plus de temps que l’analyse manuelle si les sorties candidates sont trop faibles ;
- l’état de jeu peut devenir un schéma trop large s’il absorbe des besoins P2 ;
- les seuils indicatifs peuvent être interprétés comme résultats actuels ;
- la cible peut avoir trop peu de vidéos calibrables pour les métriques en mètres ;
- des changements de modèle ou configuration peuvent contourner le cache si son identité reste fondée sur la source seule ;
- le RAG peut reformuler une incertitude en certitude sans garde-fou et tests négatifs ;
- les droits et la confidentialité des vidéos peuvent bloquer la création du benchmark ;
- les branches, documents et interfaces peuvent diverger à nouveau sans gouvernance de source de vérité.

## Critères de réexamen

Cette décision doit être réexaminée uniquement si au moins une condition documentée est remplie :

1. le benchmark golden démontre que la correction humaine n’apporte aucun gain de temps ou de qualité par rapport au manuel ;
2. des entretiens structurés montrent que les cinq familles ne répondent pas aux décisions récurrentes de la cible primaire ;
3. la majorité des vidéos conformes au profil reste non calibrable malgré une implémentation validée ;
4. une évolution réglementaire ou de droits interdit le traitement ou la conservation nécessaires ;
5. une nouvelle cible prioritaire est décidée avec preuve et financement, ce qui exige un nouveau contrat produit ;
6. la V1 satisfait sa Definition of Done et des preuves justifient l’ouverture d’un élément P2.

Un réexamen exige un nouvel ADR. Il ne doit pas modifier rétroactivement les baselines, les droits ou les résultats historiques.
