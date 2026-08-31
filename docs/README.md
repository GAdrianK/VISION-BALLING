# Index documentaire

Cet index distingue les contrats qui font autorité de la documentation technique, des expérimentations et des archives. En cas de contradiction sur le périmètre V1, les cinq documents du chapitre 0 prévalent.

## Documents normatifs

| Document | Rôle | Statut | Autorité | Dernière pertinence connue | Successeur |
|---|---|---|---|---|---|
| [`product/product_contract_v1.md`](product/product_contract_v1.md) | Définit le produit, ses utilisateurs, ses entrées, sorties et non-promesses | Actuel | Oui | Périmètre V1 | Aucun |
| [`product/golden_videos_protocol.md`](product/golden_videos_protocol.md) | Définit la constitution et l'usage du jeu golden | Actuel | Oui | Validation V1 | Aucun |
| [`product/success_metrics_v1.md`](product/success_metrics_v1.md) | Définit les critères de réussite et leurs règles de mesure | Actuel | Oui | Validation V1 | Aucun |
| [`product/backlog_priorities_v1.md`](product/backlog_priorities_v1.md) | Ordonne le travail après gel du périmètre | Actuel | Oui | Planification V1 | Aucun |
| [`adr/0001-assisted-tactical-analysis-scope.md`](adr/0001-assisted-tactical-analysis-scope.md) | Enregistre le périmètre fonctionnel retenu | Accepté | Oui | Architecture produit V1 | Aucun |

## Documentation technique actuelle

| Document | Rôle | Statut | Autorité | Dernière pertinence connue | Successeur |
|---|---|---|---|---|---|
| [`../README.md`](../README.md) | Point d'entrée, installation et état synthétique | Actuel | État courant uniquement | Branche de consolidation | Aucun |
| [`project_status.md`](project_status.md) | Matrice vérifiable des capacités | Actuel | Preuve technique synthétique | Branche de consolidation | À maintenir avec le code |
| [`video-analysis.md`](video-analysis.md) | Décrit le pipeline vidéo réellement présent | Actuel | Technique, sous le contrat produit | Pipeline 0.2.0 | À maintenir avec le pipeline |
| [`known_limitations.md`](known_limitations.md) | Inventaire des limites confirmées | Actuel | Technique, sous le contrat produit | Branche de consolidation | À maintenir à chaque chapitre |
| [`development/branch_policy.md`](development/branch_policy.md) | Règles de contribution et d'intégration | Actuel | Oui pour le workflow du dépôt | Branche de consolidation | Aucun |
| [`adr/0002-repository-source-of-truth.md`](adr/0002-repository-source-of-truth.md) | Enregistre la base consolidée et la hiérarchie documentaire | Accepté | Oui | Branche de consolidation | Aucun |

## Benchmarks et expérimentations

| Document | Rôle | Statut | Autorité | Dernière pertinence connue | Successeur |
|---|---|---|---|---|---|
| [`public-football-benchmark.md`](public-football-benchmark.md) | Protocole d'évaluation sur données publiques | Expérimental, protocole sans résultat de référence | Non | Cadre de benchmark disponible | Protocole golden et futurs rapports versionnés |
| [`avancement/sprint_02_plan.md`](avancement/sprint_02_plan.md) | Plan d'un sprint vidéo antérieur | Historique | Non | Contexte des premières fonctions vidéo | `video-analysis.md` et `project_status.md` |

## Historique ou propositions non implémentées

| Document | Rôle | Statut | Autorité | Dernière pertinence connue | Successeur |
|---|---|---|---|---|---|
| [`demo_script.md`](demo_script.md) | Scénario de démonstration d'une version antérieure | Historique, non normatif | Non | Interface RAG antérieure | README courant |
| [`blueprint_architectural_v2_pro.md`](blueprint_architectural_v2_pro.md) | Proposition d'architecture à grande échelle | Proposition, non implémentée | Non | Vision prospective | ADR futurs si adoptée |
| [`Synthese_Project_IA_FOOT.md`](Synthese_Project_IA_FOOT.md) | Synthèse historique du prototype | Historique, non normatif | Non | Phase initiale | README courant |
| [`archive/`](archive/) | Documents et prototypes archivés | Historique | Non | Traçabilité seulement | Documentation actuelle ci-dessus |
| `task_*.md`, `roadmap*`, `knowledge_gap_analysis.md` | Plans et analyses ponctuels | Historique ou documentaire seulement | Non | Contexte de travail antérieur | Contrats produit et backlog V1 |
| `p0_*`, `*_test_results.md`, `real_world_eval_sprint02.md`, `mvp_validation.md` | Instantanés de revues ou d'évaluations antérieures | Historique, résultats ponctuels | Non | Mesures de leur exécution d'origine uniquement | Futurs rapports de benchmark versionnés |

Un document non listé comme normatif ne peut pas étendre implicitement les garanties de la V1. Une proposition ne devient l'architecture courante qu'après décision enregistrée et implémentation vérifiée.
