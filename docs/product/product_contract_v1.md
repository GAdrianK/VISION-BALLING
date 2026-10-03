# Contrat produit V1 — VISION-BALLING

- Version : 1.0
- Date : 2026-08-30
- Statut : Accepted — référence normative pour la V1
- Portée : cadrage produit ; ce document ne certifie pas l’état opérationnel des modules

## Navigation du chapitre 0

- [Protocole des vidéos golden](./golden_videos_protocol.md)
- [Métriques de réussite V1](./success_metrics_v1.md)
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

## 1. Problème utilisateur

La cible primaire possède une vidéo et sait formuler des questions tactiques, mais ne dispose ni du temps humain nécessaire pour relever manuellement toutes les positions, ni d’une chaîne data professionnelle. Les outils génériques séparent souvent la vidéo, les annotations, les mesures et le compte rendu. Le problème à résoudre est la production rapide d’une analyse vérifiable, corrigible et reliée aux images, sans présenter des inférences fragiles comme des faits.

## 2. Persona primaire

La cible primaire est celle du référentiel commun. Ses contraintes structurantes sont : budget limité, matériel de captation hétérogène, temps d’analyse restreint, besoin de comprendre les limites du calcul et responsabilité finale sur l’interprétation communiquée au staff ou aux joueurs.

## 3. Personas secondaires

- analyste freelance ;
- étudiant en analyse vidéo ;
- éducateur ;
- joueur souhaitant revoir des séquences individuelles.

Le fan généraliste, le diffuseur, le recruteur mondial et le club professionnel exigeant des données certifiées ne sont pas prioritaires pour la V1.

## 4. Jobs-to-be-done

1. Importer un extrait existant et savoir rapidement s’il est exploitable.
2. Obtenir une chronologie où personnes et ballon sont distingués entre observations, prédictions et absences.
3. Corriger les équipes, les pistes, les événements ou les segments invalides sans relancer toute l’analyse.
4. Vérifier une situation sur une mini-carte synchronisée avec la frame source.
5. Mesurer les cinq familles spatiales uniquement sur les intervalles où la calibration et les données sont valides.
6. Comparer des séquences ou des phases sans confondre une variation calculée avec une causalité tactique.
7. Produire un rapport où tout nombre renvoie à sa définition, sa source et ses moments vidéo.
8. Obtenir du RAG une explication tactique contextualisée sans qu’il invente une donnée manquante.

## 5. Parcours utilisateur V1

1. L’utilisateur importe une vidéo et renseigne le contexte minimal disponible.
2. Le système valide conteneur, durée, résolution, décodabilité et capacité de traitement.
3. Un job asynchrone expose son état, sa progression, ses avertissements et ses erreurs.
4. Le pipeline produit des observations et pistes candidates pour personnes et ballon.
5. La classification d’équipes et la calibration produisent un état de jeu 2D seulement lorsque leurs critères de validité sont satisfaits.
6. L’utilisateur revoit les passages signalés et corrige ou invalide les sorties candidates.
7. Les cinq familles de métriques sont calculées sur l’état de jeu validé, avec leur confiance et leurs conditions d’invalidité.
8. Des événements simples restent des candidats corrigibles avant validation humaine.
9. Le rapport sépare faits calculés, interprétations et recommandations, et relie chaque affirmation quantitative aux frames ou positions sources.
10. L’utilisateur exporte une analyse validée ou conserve explicitement le statut de brouillon.

## 6. Entrées vidéo acceptées

Le périmètre vidéo est celui du référentiel commun. L’acceptation d’un fichier ne signifie pas que son contenu est exploitable pour toutes les étapes : mouvement de caméra, occlusions, changements de plan, visibilité du terrain, contraste des maillots et résolution effective du ballon peuvent déclencher une dégradation ou un refus propre.

Les limites exactes de taille, codec, FPS et ressources sont des contraintes techniques configurables ; elles ne doivent pas élargir la promesse produit. AVI et WebM peuvent rester acceptés par le pipeline technique sans être des formats garantis de la bêta V1.

## 7. Sorties attendues

- statut du job et diagnostic d’exploitabilité ;
- vidéo annotée distinguant les classes, pistes et états candidats ;
- détections et trajectoires structurées avec timestamps, scores, modèle et configuration ;
- classification d’équipe corrigible et segments où elle est indéterminée ;
- statut de calibration par segment, erreur estimée et motifs d’invalidité ;
- mini-terrain synchronisé fondé exclusivement sur les positions projetables ;
- événements simples candidats, corrigibles et horodatés ;
- cinq familles de métriques V1 avec définition, unité, méthode, confiance et provenance ;
- journal des corrections humaines et statut brouillon/validé ;
- rapport sourcé renvoyant aux timestamps, frames, positions et versions de calcul.

## 8. Contrat des cinq métriques initiales

| Famille | Définition V1 | Unité principale | Prérequis minimaux | Invalidité obligatoire |
|---|---|---|---|---|
| Largeur de l’équipe | Étendue latérale robuste des joueurs visibles et assignés à une même équipe dans l’état de jeu | mètre si calibration valide ; pixel sinon, étiqueté non métrique | équipe, nombre minimal de joueurs défini, positions valides | calibration invalide pour toute valeur en mètres ; couverture insuffisante |
| Longueur du bloc | Étendue longitudinale robuste de l’équipe entre ses joueurs valides | mètre si calibration valide ; pixel sinon, étiqueté non métrique | mêmes prérequis que la largeur | mêmes invalidités ; orientation de terrain indéterminée |
| Centroid robuste de l’équipe | Position centrale robuste de l’équipe, résistante aux détections aberrantes | coordonnées terrain en mètres ou coordonnées image explicitement qualifiées | équipe, calibration pour le terrain, échantillon valide | aucune coordonnée terrain si calibration invalide |
| Surface occupée ou compacité spatiale | Surface de l’enveloppe spatiale robuste et mesures dérivées explicitement définies | m² pour la surface ; aucune unité pour un indice normalisé documenté | positions terrain suffisantes et non aberrantes | calibration invalide, trop peu de joueurs, géométrie dégénérée |
| Distances inter-lignes | Distances entre centres robustes de lignes fonctionnelles validées | mètre | équipe, affectation de lignes validée, calibration valide | lignes non identifiables, couverture ou calibration insuffisante |

Chaque valeur affichée doit posséder : une définition, une unité, une source, des prérequis, une méthode de calcul versionnée, un niveau de confiance, des conditions d’invalidité et un lien vers les frames ou positions utilisées. Une valeur absente ou invalide reste absente ou invalide. Aucune valeur de démonstration ne peut emprunter l’apparence d’une mesure réelle.

## 9. Place exacte de la correction humaine

La correction humaine intervient après la génération des sorties candidates et avant la validation des événements, des métriques et du rapport. Elle n’est pas une solution de secours masquée : elle fait partie du produit V1.

L’utilisateur peut au minimum :

- confirmer, corriger ou laisser inconnues les équipes et rôles ;
- fusionner, séparer ou invalider une piste ;
- corriger les ancres et segments de calibration ;
- exclure un intervalle non exploitable ;
- confirmer, déplacer, créer ou supprimer un événement candidat ;
- approuver ou refuser une métrique et son intervalle source.

Toute correction doit être attribuée, horodatée, réversible et reliée à la version automatique d’origine. Une correction ne transforme pas une information inconnue en mesure certifiée sans données suffisantes.

## 10. Rôle exact du RAG

Le RAG doit :

- expliquer les faits calculés ;
- relier métriques et principes tactiques ;
- distinguer constat, interprétation et recommandation ;
- citer les timestamps et données sources ;
- ne jamais inventer une mesure, une action ou une identité absente.

Le RAG n’est ni la source des coordonnées, ni un détecteur d’événements, ni une autorité de validation. Il consomme l’état de jeu et les corrections validées. En l’absence de preuve, il formule explicitement l’incertitude ou refuse la conclusion.

## 11. Non-promesses

La liste normative est celle du référentiel commun. Elle doit apparaître dans l’interface, l’aide, les rapports et toute communication produit pertinente. Elle interdit notamment d’assimiler une prédiction temporaire du ballon à une observation, une piste à une identité, ou une position image à une distance physique.

## 12. Périmètre V1

Sont dans le périmètre V1 : ingestion et encodage fiables ; détection et tracking de personnes et ballon ; classification corrigible des équipes et rôles utiles ; détection des changements de plan ; calibration avec validité explicite ; état de jeu 2D ; événements simples candidats ; cinq familles de métriques ; correction humaine ; rapport sourcé ; RAG borné aux faits ; expérience post-match asynchrone ; sécurité, suppression des données et observabilité proportionnées.

## 13. Hors périmètre

- PPDA, xG, xT, pitch control avancé et valeur de possession complexe comme fonctions garanties ;
- vitesse, distance ou charge physique certifiées ;
- notes automatiques attribuées aux joueurs ;
- identité nominative automatique, reconnaissance faciale et réidentification avancée ;
- extrapolation présentée comme position réelle hors champ ;
- live, multi-caméra et captation propriétaire ;
- garantie de traitement d’un match complet de 90 minutes ;
- plateforme mondiale de scouting ;
- fonctions commerciales, tarification, paiement ou publicité.

Ces sujets ne peuvent apparaître que dans le backlog futur avec leurs prérequis et conditions de réexamen.

## 14. Hypothèses

| Hypothèse | Statut | Méthode de validation |
|---|---|---|
| La cible dispose d’extraits vidéo légalement utilisables | À valider | entretiens et constitution des vidéos golden |
| Une correction guidée réduit le temps total par rapport à une annotation entièrement manuelle | À valider | métrique produit principale sur tâches comparables |
| Les vues définies permettent une calibration exploitable sur une part suffisante des segments | À valider | golden videos et benchmark de calibration |
| Les cinq familles répondent à des décisions récurrentes de la cible | Décision produit à confirmer par usage | tests de tâches et entretiens structurés |
| Un rapport sourcé est plus utile qu’un volume supérieur de métriques non vérifiables | Décision directrice | mesure d’usage et taux de corrections/acceptations |

## 15. Risques

- confusion entre présence d’un module et qualité démontrée sur le domaine V1 ;
- faux sentiment de précision créé par les overlays et valeurs statiques du frontend actuel ;
- propagation d’erreurs de détection vers la calibration, les événements et le rapport ;
- temps de correction supérieur au gain obtenu ;
- dérive vers des métriques avancées avant stabilisation de l’état de jeu ;
- incompatibilités de captation et de navigateur ;
- cache réutilisant un résultat produit avec une autre configuration ;
- conservation locale insuffisante pour la sécurité, la suppression et le traitement concurrent ;
- droits insuffisants sur les vidéos de référence.

## 16. Critères d’acceptation produit

1. Les trois profils golden sont disponibles, licenciés, checksummés, versionnés hors Git et annotés selon le [protocole](./golden_videos_protocol.md).
2. Les objectifs acceptés dans les [métriques de réussite](./success_metrics_v1.md) sont mesurés par un benchmark reproductible ; toute baseline inconnue reste marquée `TBD — benchmark requis`.
3. Au moins 95 % des jobs valides du protocole accepté terminent correctement, objectif indicatif à confirmer.
4. Le parcours critique fonctionne sur Chrome, Firefox et Edge selon une matrice de versions gelée pour la bêta, objectif indicatif à confirmer.
5. Aucune métrique simulée n’est présentée comme un résultat réel.
6. Aucune position ou distance métrique n’est émise lorsque la calibration est invalide.
7. Les cinq familles exposent définition, unité, version de calcul, confiance, invalidité et provenance.
8. La correction humaine précède la validation finale et laisse un journal réversible.
9. 100 % des affirmations quantitatives du rapport possèdent une source, objectif indicatif à confirmer et règle d’intégrité non négociable.
10. Le RAG distingue constat, interprétation et recommandation, et refuse d’inventer une donnée absente.

## 17. Definition of Done globale de la V1

La V1 est terminée uniquement lorsque :

- le parcours du référentiel commun est utilisable de bout en bout sur les trois golden videos ;
- les seuils acceptés sont mesurés et publiés avec protocoles, versions et limites ;
- les segments invalides échouent proprement sans produire de fausse précision ;
- la correction humaine est opérationnelle, traçable et intégrée au calcul final ;
- les cinq familles sont calculées exclusivement depuis un état de jeu valide ;
- le rapport est sourcé et ne contient aucun nombre orphelin ;
- la métrique produit principale, « Temps humain nécessaire pour produire une analyse tactique validée de cinq minutes de vidéo », est mesurée contre une référence manuelle comparable ;
- la sécurité, la suppression, la reprise des jobs et le stockage répondent au périmètre de bêta défini ;
- la documentation, l’interface et les limites décrivent le même produit ;
- aucun élément hors périmètre n’est présenté comme une capacité garantie.

## 18. Règle de décision

Pour toute proposition future, répondre successivement :

1. Quelle étape de « vidéo → état de jeu → décision » améliore-t-elle ?
2. Quelle donnée observable la justifie ?
3. Comment sa qualité et son invalidité seront-elles mesurées ?
4. Quel temps humain fait-elle gagner sans masquer l’incertitude ?

Sans réponse vérifiable à ces quatre questions, la proposition est rejetée, différée ou classée hors périmètre V1.
