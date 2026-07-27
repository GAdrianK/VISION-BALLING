---
title: "Comprendre et Analyser les Expected Goals (xG)"
topic: "modern_analysis"
intent: "general"
phase: "multi"
level: "beginner"
audience: "all"
keywords: ["xg", "expected-goals", "probabilite-tir", "data-science", "analyse-tactique", "efficacite-offensive", "statistiques", "performance"]
---

# Définition
Les *Expected Goals* (xG) sont une métrique statistique qui mesure la probabilité qu'un tir se transforme en but, en fonction des caractéristiques historiques de milliers de tirs similaires. La valeur d'un xG est comprise entre 0 (but impossible) et 1 (but certain). Par exemple, un tir évalué à 0.35 xG a 35% de chances de finir au fond des filets.

# Objectifs
- Évaluer la qualité des occasions de but créées par une équipe, indépendamment du résultat final.
- Mesurer l'efficacité défensive en quantifiant la dangerosité des occasions concédées.
- Analyser la qualité des choix des joueurs face au but (pertinence de la frappe vs passe supplémentaire).
- Nuancer les scores parfois trompeurs d'un match (ex: une équipe dominant aux xG mais perdant 1-0).

# Principes clés

## A. Les Facteurs d'évaluation du Tir
Les algorithmes d'xG prennent en compte plusieurs variables pour chaque tir :
1. **La distance au but** : Plus le tir est proche, plus la valeur xG est élevée.
2. **L'angle de tir** : Un tir face au but a plus de valeur qu'un tir excentré.
3. **Le type de passe décisive** : Une passe en retrait au sol génère de meilleurs xGs qu'un centre aérien sous pression.
4. **La position des défenseurs et du gardien** : La densité de joueurs devant le tireur réduit considérablement les chances de but.
5. **La partie du corps utilisée** : Une frappe du pied fort a une probabilité supérieure à une tête ou une reprise du pied faible.

## B. La Somme des xG (Performance Collective)
En additionnant les xG de tous les tirs tentés par une équipe durant un match, on obtient un score cumulé (ex: 2.4 xG contre 0.8 xG). Cela permet aux analystes de valider si le plan de jeu tactique a fonctionné en créant des occasions de haute qualité, même si le score réel affiche un nul 0-0 dû à de la malchance ou à un grand gardien.

## C. La Surperformance et la Sous-performance (Efficacité)
Un attaquant qui marque 15 buts sur une saison avec un total de 10 xG surperforme ses statistiques de +5. Cela peut traduire une habileté de finition exceptionnelle (ex: Lionel Messi) ou une part de réussite temporaire. À l'inverse, sous-performer ses xG de manière répétée révèle un manque de lucidité dans le dernier geste ou un problème psychologique de confiance.

# Erreurs fréquentes
1. **Confondre quantité et qualité** : Analyser uniquement le nombre brut de tirs (ex: 20 tirs lointains à 0.02 xG chacun font 0.4 xG global, ce qui est moins dangereux qu'une seule occasion franche face au but évaluée à 0.6 xG).
2. **L'ignorer en bloc** : Rejeter la métrique sous prétexte que "le football n'est pas des maths", passant à côté d'un indicateur de performance stable à moyen terme.
3. **L'utiliser sur un seul match de manière absolue** : Oublier que la variance à court terme est énorme au football. L'xG est pertinent lorsqu'il est analysé sur un échantillon de 5 à 10 matchs.

# Corrections terrain
1. *"Arrêtez de frapper de 30 mètres sous pression, cherchez une passe de plus dans la surface pour augmenter nos chances de marquer (meilleur xG) !"*
2. *"Défensivement, forcez-les à tirer de loin et excentrés pour maintenir leurs xG très bas !"*
3. *"Ne paniquez pas après cette défaite, les xG montrent que notre animation offensive crée les bonnes situations. Les buts vont finir par arriver !"*

# Exemple concret
Un penalty vaut historiquement 0.79 xG (79% de chances de réussite). Une frappe de 35 mètres excentrée à travers une forêt de jambes vaut généralement moins de 0.02 xG (2% de chances de marquer).

# Exercice d'entraînement
### Exercice de Sensibilisation à la Zone Haute xG (6v6 + Gardien)
- **Dimensions & Matériel** : Zone offensive des 20 mètres. Tracer une "zone dorée" (golden zone) en demi-cercle à 12 mètres du but.
- **Consignes & Règles de jeu** : Match classique. Cependant, les buts inscrits depuis l'extérieur de la "zone dorée" ne comptent que pour 1 point. Les buts inscrits à l'intérieur de la zone (haute valeur xG historique) comptent pour 3 points. Les joueurs sont forcés de combiner pour pénétrer dans la zone de haute efficacité avant de tirer.
- **Variantes** : Limiter à une seule touche pour la finition dans la zone dorée.

# Points de vigilance
- L'xG classique ne mesure pas l'intention ou les occasions manquées où le joueur n'a pas pu déclencher sa frappe (non-shot xG ou xT).
- Dépendance envers la qualité du modèle mathématique utilisé (Opta, StatsBomb, etc. ont des calculs légèrement différents).
- Ne pas dénaturer l'instinct des buteurs spontanés en les bridant par des contraintes statistiques strictes.

# Questions fréquentes
- **Qui a inventé les xG ?** Les modèles ont été développés au début des années 2010 par des analystes de données comme Sam Green et Ted Knutson, avant d'être adoptés par les clubs professionnels du monde entier.
- **Pourquoi une équipe perd-elle malgré un xG supérieur ?** C'est la glorieuse incertitude du sport : la finition individuelle clinique ou les arrêts miracles du gardien sur le match instantané déjouent temporairement les probabilités historiques moyennes.

# Mots-clés RAG
expected goals, xG, statistiques, probabilité de tir, data football, analyse moderne, efficacité offensive, tir surface, probabilités.
