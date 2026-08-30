# Protocole des vidéos golden — VISION-BALLING V1

- Version : 1.0
- Date : 2026-08-30
- Statut : Accepted — actifs encore à constituer

## Navigation du chapitre 0

- [Contrat produit V1](./product_contract_v1.md)
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

## 1. Objet du protocole

Les vidéos golden sont trois références stables destinées à comparer les versions du pipeline et du parcours utilisateur. Elles ne constituent pas un dataset d’entraînement. Elles servent à mesurer les régressions, les refus propres et le temps de correction humaine sur des entrées représentatives du domaine V1.

Au HEAD audité, aucun média, manifeste de droits, checksum ou résultat de benchmark correspondant aux trois IDs n’est présent dans le dépôt. Aucun fichier accessible ne confirme le clip Croatie–Tchéquie mentionné dans la demande. Ce clip n’est donc pas retenu ni décrit comme actif ; il pourra seulement devenir candidat après confirmation de sa source, de ses droits et de ses métadonnées.

## 2. Registre normatif

| ID stable | Profil | Durée cible | Statut au 2026-08-30 |
|---|---|---:|---|
| `GOLDEN-01-BROADCAST` | broadcast standard avec mouvements caméra, zooms limités et joueurs partiellement hors champ | 30 s à 2 min | `PENDING_ASSET` |
| `GOLDEN-02-TACTICAL-WIDE` | caméra fixe ou tactique montrant une grande portion du terrain | 2 à 5 min | `PENDING_ASSET` |
| `GOLDEN-03-DIFFICULT` | compression, faible lumière, mouvements importants, maillots proches ou ballon difficile | 1 à 3 min | `PENDING_ASSET` |

Les durées sont des critères de sélection, pas les métadonnées de fichiers existants.

## 3. `GOLDEN-01-BROADCAST`

| Champ | Exigence ou état |
|---|---|
| Objectif | Évaluer le comportement sur un extrait broadcast monocaméra exploitable : changements d’échelle, pans modérés, occlusions et sorties de champ |
| Type de vue | Broadcast standard ; mouvements caméra ; zooms limités ; joueurs partiellement hors champ |
| Durée | Cible : 30 s à 2 min ; valeur réelle : `PENDING_ASSET` |
| Résolution | 720p ou 1080p exigé ; valeur réelle : `PENDING_ASSET` |
| FPS | `PENDING_ASSET` — à lire avec FFprobe après sélection |
| Conteneur et codec | MP4, MOV ou MKV validé ; valeurs réelles : `PENDING_ASSET` |
| Droits/licence | `PENDING_ASSET` — preuve écrite d’usage pour développement, benchmark et démonstration interne requise |
| Checksum | `PENDING_ASSET` — SHA-256 du fichier original requis |
| Statut de disponibilité | `PENDING_ASSET` |
| Vérité terrain attendue | frames annotées pour personnes et ballon ; identités de pistes anonymes ; équipe/rôle lorsque visible ; segments de plan ; points/lignes de terrain visibles ; intervalles exploitables et non exploitables ; événements simples sélectionnés pour évaluation |
| Modules évalués | ingestion, encodage, détection personnes/ballon, tracking personnes/ballon, changements de plan, équipes, calibration broadcast, état 2D, événements simples, cinq métriques, correction, rapport et lecture navigateur |
| Critères de réussite | objectifs applicables du [référentiel de réussite](./success_metrics_v1.md), mesurés séparément ; aucune valeur métrique lorsque la calibration broadcast est invalide |
| Conditions de refus | droits absents ; durée/résolution hors profil ; plans multiples impossibles à segmenter ; terrain trop peu visible pour toute calibration ; fichier illisible ; vérité terrain non révisable |

Le clip Croatie–Tchéquie ne peut être proposé comme candidat à cet ID qu’après confirmation documentaire ou matérielle. Au HEAD audité, cette confirmation n’existe pas.

## 4. `GOLDEN-02-TACTICAL-WIDE`

| Champ | Exigence ou état |
|---|---|
| Objectif | Référence principale pour la calibration, la mini-carte synchronisée et les cinq familles de métriques collectives |
| Type de vue | Caméra fixe ou tactique, wide-angle, grande portion du terrain visible |
| Durée | Cible : 2 à 5 min ; valeur réelle : `PENDING_ASSET` |
| Résolution | 720p ou 1080p exigé ; valeur réelle : `PENDING_ASSET` |
| FPS | `PENDING_ASSET` — à lire avec FFprobe après sélection |
| Conteneur et codec | MP4, MOV ou MKV validé ; valeurs réelles : `PENDING_ASSET` |
| Droits/licence | `PENDING_ASSET` — preuve écrite d’usage requise |
| Checksum | `PENDING_ASSET` — SHA-256 du fichier original requis |
| Statut de disponibilité | `PENDING_ASSET` |
| Vérité terrain attendue | détections et pistes anonymes ; équipes et rôles utiles ; correspondances image-terrain ; positions 2D annotées sur frames échantillonnées ; lignes fonctionnelles validées ; intervalles de couverture ; valeurs manuelles de référence pour les cinq familles |
| Modules évalués | tous les modules, avec priorité calibration, état de jeu 2D, correction humaine, cinq métriques et rapport sourcé |
| Critères de réussite | objectifs applicables du [référentiel de réussite](./success_metrics_v1.md), dont erreur médiane de calibration tactique indicative au plus égale à 1,5 m, à confirmer |
| Conditions de refus | terrain insuffisamment visible ; distorsion non modélisable ; droits absents ; résolution/durée hors profil ; impossibilité d’établir une vérité terrain cohérente |

## 5. `GOLDEN-03-DIFFICULT`

| Champ | Exigence ou état |
|---|---|
| Objectif | Mesurer les limites, la dégradation contrôlée, les avertissements et les refus propres plutôt que maximiser artificiellement un score agrégé |
| Type de vue | Un ou plusieurs facteurs difficiles documentés : compression, faible lumière, mouvement important, maillots proches ou ballon difficile |
| Durée | Cible : 1 à 3 min ; valeur réelle : `PENDING_ASSET` |
| Résolution | 720p ou 1080p souhaité pour isoler les autres difficultés ; valeur réelle : `PENDING_ASSET` |
| FPS | `PENDING_ASSET` — à lire avec FFprobe après sélection |
| Conteneur et codec | MP4, MOV ou MKV validé ; valeurs réelles : `PENDING_ASSET` |
| Droits/licence | `PENDING_ASSET` — preuve écrite d’usage requise |
| Checksum | `PENDING_ASSET` — SHA-256 du fichier original requis |
| Statut de disponibilité | `PENDING_ASSET` |
| Vérité terrain attendue | annotations des objets visibles ; zones d’ambiguïté ; occlusions ; changements de plan ; similarité de maillots ; segments où ballon, équipe, calibration ou métrique doivent rester inconnus |
| Modules évalués | validation, détection, tracking, équipes, calibration, invalidation de l’état 2D, correction, rapport d’incertitude et expérience d’échec |
| Critères de réussite | aucun fait inventé ; séparation observation/prédiction ; refus ou invalidation explicite lorsque les prérequis manquent ; objectifs quantitatifs mesurés sans cacher le profil difficile |
| Conditions de refus | absence de droits ou d’annotations révisables ; difficulté non documentée ; fichier techniquement illisible avant même l’évaluation visée |

Un refus propre du module aval peut constituer un succès pour cette référence si le protocole établit que les prérequis sont absents.

## 6. Vérité terrain minimale

La vérité terrain est produite ou revue par au moins une personne compétente en annotation vidéo football. Toute divergence non résolue reste marquée incertaine et est exclue du dénominateur concerné. Elle comprend, selon le profil :

- dictionnaire des frames et timestamps de référence ;
- boîtes personnes et ballon, avec visibilité et occlusion ;
- pistes anonymes cohérentes, sans identité nominative ;
- équipe, arbitre et gardien uniquement lorsque l’annotation est défendable ;
- segments et changements de plan ;
- points ou lignes de terrain et transformation de référence ;
- positions 2D et intervalles hors champ explicitement absents ;
- événements simples avec tolérance temporelle définie avant mesure ;
- valeurs des cinq familles avec formule et sélection de joueurs documentées ;
- journal des désaccords et version de l’annotation.

Les données d’entraînement et de validation doivent rester séparées. Une vidéo golden utilisée pour régler un seuil doit être signalée et ne peut plus servir seule à estimer la généralisation.

## 7. Manifeste hors Git

Pour chaque actif sélectionné, un manifeste contrôlé doit enregistrer sans exposer le média :

| Champ | Règle |
|---|---|
| `golden_id` | un des trois IDs exacts |
| `asset_version` | version immuable de l’actif |
| nom logique | ne doit pas révéler de donnée personnelle inutile |
| durée, résolution, FPS, codec | valeurs extraites, jamais supposées |
| SHA-256 | checksum du binaire original |
| droits | titulaire, portée, expiration et restrictions |
| vérité terrain | version, auteur/relecteur, format et checksum |
| split | `golden-evaluation`, distinct de l’entraînement |
| date de gel | date de validation du manifeste |

L’emplacement de stockage n’est pas défini au chapitre 0. Il devra être sécurisé, contrôlé par accès et compatible avec la suppression. Aucun chemin fictif n’est prescrit.

## 8. Exécution reproductible

1. Vérifier checksum et droits avant toute lecture.
2. Geler commit, modèle, checksum des poids, configuration complète, versions du pipeline et environnement.
3. Exécuter chaque module et conserver ses sorties séparément.
4. Mesurer les objectifs du [référentiel de réussite](./success_metrics_v1.md) sans remplacer les absences par des valeurs nulles trompeuses.
5. Faire exécuter la tâche de correction à partir du même état initial.
6. Mesurer le temps humain actif, les corrections et le résultat validé.
7. Produire un rapport de benchmark contenant protocole, résultats, intervalles de confiance lorsque possible, échecs et limites.
8. Comparer à la baseline gelée ; une amélioration sur un profil ne masque pas une régression sur un autre.

## 9. Règle de non-versionnement

Les vidéos, frames extraites, annotations volumineuses, poids, sorties annotées et résultats bruts ne doivent jamais être versionnés dans Git. Seuls les protocoles, schémas légers, manifestes expurgés et synthèses de benchmark autorisées peuvent l’être après revue des droits et de la confidentialité.

Les IDs `GOLDEN-01-BROADCAST`, `GOLDEN-02-TACTICAL-WIDE` et `GOLDEN-03-DIFFICULT` sont immuables. Le remplacement d’un fichier crée une nouvelle `asset_version` et un nouveau checksum ; il ne réécrit pas silencieusement l’historique de mesure.

## 10. Conditions de sortie de `PENDING_ASSET`

Un profil quitte `PENDING_ASSET` uniquement lorsque : droits, fichier, métadonnées extraites, checksum, vérité terrain, relecture, stockage hors Git et manifeste sont disponibles. Tant que ces éléments manquent, aucun score ne peut être présenté comme baseline V1 pour ce profil.
