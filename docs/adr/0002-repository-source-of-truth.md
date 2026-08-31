# ADR 0002 — Source de vérité du dépôt

- Statut : Accepté
- Date : 2026-08-30

## Contexte

Le dépôt contient une suite linéaire de branches fonctionnelles, des contrats produit récents, une documentation technique d'âges différents et plusieurs blueprints prospectifs. Le README historique décrivait encore une version centrée sur le chat alors que le code contient désormais un pipeline vidéo. À l'inverse, certaines interfaces et notes présentaient des capacités ou des chiffres que le pipeline ne calcule pas.

Sans hiérarchie explicite, un lecteur peut confondre intention, expérimentation et fonction vérifiée. Une base commune est nécessaire avant toute intégration future vers `main`.

## Décision

1. L'historique linéaire contenu dans `feat/ball-tracking` jusqu'au commit `3d3cd64` constitue la base fonctionnelle consolidée.
2. Les quatre documents de `docs/product/` et l'ADR 0001 constituent le référentiel normatif du périmètre V1.
3. Le README décrit l'état courant, les commandes et les limites. Il ne remplace pas les contrats normatifs.
4. Les blueprints, roadmaps, scripts de démonstration et plans de sprint prospectifs restent informatifs et sont signalés comme non normatifs.
5. Tout résultat chiffré présenté comme une mesure doit être relié à une sortie courante traçable ou à un artefact de benchmark versionné. Une constante d'interface n'est pas une preuve.
6. `main` ne sera mis à jour qu'après validation complète de la branche d'intégration. Cette décision n'effectue ni fusion ni publication.

## Conséquences

- l'état courant devient lisible depuis le README et `docs/project_status.md` ;
- les contrats produit restent stables pendant les travaux techniques ;
- les interfaces doivent distinguer résultats API, démonstrations et fonctions absentes ;
- une nouvelle capacité exige une preuve dans le code ou les tests et une mise à jour documentaire cohérente ;
- les résultats locaux non versionnés ne peuvent pas soutenir une affirmation permanente dans la documentation ;
- l'intégration vers `main` reste une action séparée, après revue et exécution de la CI distante.

## Alternatives rejetées

### Considérer le README comme unique contrat

Rejeté : un guide d'entrée évolue avec l'implémentation et ne porte pas à lui seul les critères de réussite, non-promesses et règles golden.

### Traiter tous les documents existants comme équivalents

Rejeté : des plans historiques et propositions à grande échelle contredisent l'état actuel ou décrivent des capacités non implémentées.

### Mettre immédiatement `main` à jour

Rejeté : la branche d'intégration doit d'abord être relue et validée localement puis par la CI distante, sans réécriture de l'historique.
