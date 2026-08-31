# Politique de branches

- `main` reste stable, démontrable et n'est mis à jour qu'après validation du périmètre intégré.
- Une branche couvre un périmètre cohérent. Les commits y restent atomiques et utilisent Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Une branche partagée ne reçoit pas de force-push. L'historique publié n'est ni réécrit ni déplacé.
- Une pull request est recommandée avant toute mise à jour de `main`. Cette recommandation ne signifie pas qu'une protection GitHub est configurée.
- Modèles, checkpoints, datasets, vidéos, frames, résultats générés, caches et secrets restent hors Git.
- Une branche est prête à intégrer lorsque son périmètre est documenté, son diff relu, les contrôles backend/frontend applicables réussis et aucune donnée interdite n'est suivie.
- Après intégration vérifiée, la branche locale puis distante peut être supprimée de manière explicite ; aucune branche non fusionnée n'est supprimée par automatisme.
