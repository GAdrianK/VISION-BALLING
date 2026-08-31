# Limites connues

> **Statut : inventaire technique actuel.** Ce document complète, sans remplacer, le contrat produit V1 et les critères de réussite normatifs.

## Validation de domaine

- Aucun dataset golden, média golden, jeu d'annotations ou résultat golden n'est versionné.
- La vérité terrain requise pour évaluer les cinq familles de métriques V1 n'existe pas encore dans le dépôt.
- Le suivi temporel du ballon est couvert par des tests synthétiques, mais n'a pas été validé visuellement sur le protocole golden.
- Aucun résultat ne démontre que les prédictions temporelles améliorent la qualité par rapport aux seules observations.

## Détection et suivi

- HOG détecte uniquement des personnes candidates et n'est pas spécialisé pour le football.
- YOLO et le profil H250 exigent des dépendances et des poids locaux facultatifs ; aucun poids n'est versionné.
- Le mapping H250 est présent, mais sa qualité n'a pas été benchmarkée sur une référence versionnée.
- Le suivi des joueurs par IoU reste limité lors des croisements, sorties de champ et occultations. ByteTrack est facultatif et expérimental.
- Une prédiction du ballon est explicitement distincte d'une détection observée et ne possède pas de confiance de détecteur.

## Vidéo et exécution

- La compatibilité de la vidéo annotée doit être finalisée et validée sur plusieurs navigateurs. Un problème de lecture sous Linux reste documenté pour le chapitre 2.
- La commande FFmpeg est testée comme construction logicielle, pas comme matrice complète de décodage navigateur.
- `BackgroundTasks` exécute les jobs dans le processus web : la file n'est ni durable ni reprise après redémarrage.
- Le délai, la mémoire et le débit sur une vidéo de match complète ne sont pas établis par un benchmark versionné.

## État tactique V1

- Les équipes ne sont pas classifiées.
- Le terrain n'est pas calibré et aucun état de jeu 2D fiable n'est produit.
- Il n'existe pas de flux de correction humaine des joueurs, équipes ou positions.
- La possession, la largeur, la longueur/profondeur, le centroid robuste de l’équipe, la compacité et les transitions ne sont pas calculés.
- PPDA et xT ne sont pas calculés par le pipeline vidéo et ne font pas partie des garanties V1.
- Aucun rapport vidéo sourcé ne relie encore une affirmation à un intervalle et à une preuve visuelle.

## Stockage et reproductibilité

- Les jobs, JSON, vidéos et aperçus sont stockés sur le système de fichiers local.
- La déduplication actuelle repose sur le SHA de la vidéo source ; elle doit ultérieurement inclure la configuration, le modèle et la version du pipeline.
- Les artefacts locaux ne sont pas portables entre plusieurs instances et ne disposent pas d'une politique de rétention centralisée.
- Les modèles, datasets et médias restent hors Git ; leur provenance, licence et empreinte doivent être gérées séparément avant un benchmark.

## Moteur documentaire

- Le RAG utilise un corpus local borné dont la couverture dépend des documents disponibles.
- Le RAG est séparé du pipeline vidéo et ne constitue jamais la source d'une métrique calculée sur une vidéo.
- Les routes qui utilisent des données structurées dépendent du contenu local disponible ; une réponse textuelle ne remplace pas une preuve vidéo.

## Qualité statique

- La configuration Ruff du chapitre 1 exécute volontairement une baseline critique et transitoire (`E9`, `F63`, `F7`, `F82`) ; elle ne constitue pas un lint backend complet.
- Un contrôle indépendant avec les règles Ruff par défaut recense 110 constats historiques : 65 `E402`, 30 `F401`, 9 `F541`, 1 `F811` et 5 `F841`. Leur correction globale dépasserait la consolidation du dépôt et doit faire l'objet d'un chantier dédié de qualité backend.
- ESLint ne signale aucune erreur, mais conserve six avertissements historiques hors des fichiers modifiés par le chapitre 1 : cinq imports React inutilisés (`no-unused-vars`) et une dépendance de hook (`react-hooks/exhaustive-deps`). Le hook doit être revu dans un chantier frontend dédié afin de ne pas modifier sa logique sans test ciblé.

La matrice détaillée des capacités se trouve dans [`project_status.md`](project_status.md). Les décisions et objectifs V1 se trouvent dans [`product/product_contract_v1.md`](product/product_contract_v1.md) et [`product/success_metrics_v1.md`](product/success_metrics_v1.md).
