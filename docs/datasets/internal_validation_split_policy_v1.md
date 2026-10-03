# Internal validation split policy V1

- Version : 1.0.0
- Dataset role : `golden_eval`
- Statut : normatif

## Règle fondamentale

Les trois vidéos golden et toutes les frames référencées par `golden_frames_v1.csv` sont exclusivement destinées à l'évaluation. Aucune vidéo golden, frame golden, annotation golden ou export dérivé ne doit entrer dans un jeu `train` ou `training`, ni être utilisé pour le fine-tuning d'un détecteur, tracker ou modèle de classification.

Cette interdiction couvre les images extraites, les annotations CVAT, les boxes, les trajectoires, les équipes, les événements, les lignes et points terrain. Une prédiction produite sur un golden reste elle aussi un résultat d'évaluation, pas une donnée d'entraînement.

## Séparation future

Toute future partition doit être définie au niveau match ou vidéo avant extraction des frames :

- toutes les frames d'un même match ou d'une même vidéo restent dans une seule partition ;
- aucun échantillonnage aléatoire frame par frame ne peut répartir un même match entre entraînement et test ;
- les doublons, réencodages, extraits temporels et versions dérivées d'une même source héritent de la même partition ;
- une nouvelle donnée d'entraînement doit provenir d'autres matchs ou datasets dont la licence et la provenance sont enregistrées ;
- toute proximité de source, d'événement ou de captation avec un golden doit être examinée avant admission dans l'entraînement.

Le manifeste `internal_benchmark_v1.json` ne déclare qu'une partition : `golden_eval`. La présence d'une partition `train` ou `training` dans ce benchmark constitue un échec de validation.

## Hyperparamètres et fuite indirecte

Comparer des versions sur le benchmark est autorisé. En revanche, modifier répétitivement seuils, règles, architecture ou post-traitement jusqu'à optimiser spécifiquement les trois goldens transforme progressivement le benchmark en jeu de développement. Chaque réglage motivé par ces résultats doit donc être journalisé, et une validation indépendante future sera nécessaire avant toute revendication générale.

Les seuils ne doivent pas être sélectionnés uniquement sur la macro-moyenne. Les résultats sont rapportés par golden, par type de caméra, puis en macro-moyenne. Une grosse régression sur un profil ne peut pas être masquée par une moyenne globale.

## Limites d'interprétation

Ce jeu est un benchmark de régression interne stable. Il n'est ni un test scientifique aveugle indépendant, ni une preuve de généralisation universelle, ni un dataset assez large pour annoncer des performances générales. Ses trois sources couvrent volontairement des profils distincts, mais pas la diversité complète des matchs, stades, caméras, équipes, conditions et populations.

## Contrôle avant freeze

Avant tout gel d'un package d'annotations :

1. confirmer `dataset_role = golden_eval` dans tous les manifestes ;
2. confirmer l'absence de partition d'entraînement ;
3. vérifier que les trois SHA-256 golden correspondent au manifeste 1.1.0 ;
4. vérifier que les exports dérivés restent associés au même benchmark ;
5. enregistrer toute exclusion ou incertitude sans déplacer la frame vers une autre partition.
