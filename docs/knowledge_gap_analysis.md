# 🔍 Analyse des Gaps de Connaissances (Knowledge Gap Analysis)

Ce document analyse la couverture de notre base de connaissances actuelle (4 fichiers) par rapport aux 20 questions de test fonctionnel du MVP. Il identifie les zones d'ombre tactiques et propose une feuille de route pour la création des 20 prochains documents tactiques.

---

## 📊 1. Analyse de Couverture des Questions MVP

Le tableau ci-dessous évalue la couverture de la base de connaissances actuelle par rapport aux questions posées dans le cadre de la validation fonctionnelle.

| Catégorie de Sujet | Questions Rattachées | Couverture Actuelle | Qualité Estimée | Documents Manquants Identifiés | Priorité |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **Sortie de balle & Relance** | Q1, Q8, Q20 | **100%** (Élevée) | Excellente | Aucun (couvert par `sortie_balle.md`) | Basse |
| **Profils & Rôles Individuels** | Q2, Q6, Q9, Q11, Q14, Q15, Q17, Q19 | **90%** (Élevée) | Très bonne | Détails sur le rôle du Box-to-Box en transition offensive | Moyenne |
| **Bloc Bas Défensif** | Q4, Q5, Q13, Q18 | **95%** (Élevée) | Excellente | Aucun (couvert par `bloc_bas.md`) | Basse |
| **Pressing & Contre-Pressing** | Q3, Q10, Q12, Q16 | **90%** (Élevée) | Très bonne | Aucun (couvert par `pressing_contre_pressing.md`) | Basse |
| **Transitions Défensives (Repli)** | Q7 | **40%** (Faible) | Moyenne | Principes de repli après cassage du premier rideau | **Haute** |
| **Systèmes Collectifs Généraux** | Hors-catalogue direct | **10%** (Très faible) | Insuffisante | Fiches dédiées à l'animation des systèmes (4-3-3, 3-5-2, 4-4-2) | **Haute** |
| **Coups de Pied Arrêtés (CPA)** | Hors-catalogue direct | **0%** (Nulle) | Inexistante | Corners et coups francs offensifs / défensifs | Moyenne |

---

## 🎯 2. Identification des Gaps de Connaissances Majeurs

À travers l'audit des questions et des réponses formulées par le système, trois manques critiques ont été identifiés :

1. **La Phase de Transition Offensive (Contre-attaque)** :
   - *Problème :* Le système comprend comment presser et comment sortir d'un pressing, mais n'a aucune donnée sur l'organisation d'une transition rapide vers l'avant (ex: vitesse de projection, positionnement des receveurs, passes verticales vs passes de conservation).
2. **Le Repli Collectif & La Temporisation (Transition Défensive)** :
   - *Problème :* Si le contre-pressing échoue, le système propose de reformer un bloc sans détailler les comportements individuels (cadrer sans se livrer, ralentir le porteur, couverture mutuelle).
3. **L'Animation des Systèmes de Jeu Standardisés** :
   - *Problème :* Hormis le 3-2-4-1 initié par l'Inverted Fullback, le système manque de fiches décrivant comment animer des systèmes classiques (le 4-3-3 de possession, le 4-4-2 compact, le 3-5-2 de transition).

---

## 🚀 3. Proposition : Les 20 Prochains Documents Tactiques

Pour faire passer le Football IQ Assistant d'un MVP à un conseiller tactique complet et robuste, voici la liste des 20 prochains documents structurés à intégrer dans la base RAG :

### 📂 Phase A : Animations & Transitions Collectives (Priorité Haute)
1. **`transition_offensive_contre_attaque.md`** : Sortie de la zone de récupération, critères de verticalité, appel des ailiers et projection des milieux.
2. **`transition_defensive_repli.md`** : Principes de temporisation collective (ralentir le porteur), recul-frein et protection de l'axe.
3. **`attaquer_bloc_bas_desequilibre.md`** : Utilisation de la largeur maximale, principes de fixation intérieure pour libérer l'extérieur (Overload to Isolate).
4. **`animation_offensive_half_spaces.md`** : Occupation et circuits de passes préférentiels dans les demi-espaces (interlignes latéraux).

### 📐 Phase B : Structures & Systèmes de Jeu (Priorité Haute)
5. **`systeme_433_possession.md`** : Positionnement en phase offensive, triangle du milieu de terrain, et comportement des ailiers (pied inverse vs pied naturel).
6. **`systeme_352_transition.md`** : Rôle athlétique et tactique des pistons, complémentarité du duo d'attaquants, et relance à 3 axiaux.
7. **`systeme_442_bloc_compact.md`** : Coulissement horizontal des deux lignes de 4, rigueur défensive et déclencheurs de pressing médians.
8. **`systeme_343_rotations.md`** : Double pivot hybride, rotations entre l'ailier et le piston, et gestion de la largeur offensive.

### ⚽ Phase C : Rôles Tactiques Modernes Additionnels (Priorité Moyenne)
9. **`roles_sweeper_keeper.md`** : Le gardien-libéro, positionnement haut en phase de possession, et couverture de la profondeur défensive.
10. **`roles_defenseur_relanceur.md`** : Le défenseur central créateur, conduite de balle pour fixer le premier rideau, et passes cassant les lignes.
11. **`roles_ailier_inverse_inside_forward.md`** : L'attaquant de couloir rentrant sur son bon pied, création de l'espace pour le latéral qui dédouble.
12. **`roles_raumdeuter_analyse.md`** : L'interprète de l'espace (type Thomas Müller) : détection des failles, timing de course dans la surface et discrétion.
13. **`roles_piston_moderne.md`** : Animation du couloir complet par un seul joueur : endurance, repli défensif et centres en bout de course.

### 🛑 Phase D : Pressings Spécifiques & Animation (Priorité Moyenne)
14. **`pressing_bloc_median.md`** : Structure du bloc médian, temporisation et fermeture des passes axiales vers le numéro 6 adverse.
15. **`pressing_contre_trois_defenseurs.md`** : Comment orienter le pressing face à une structure de relance à 3 axiaux (3-5-2 / 3-4-3).
16. **`pressing_contre_quatre_defenseurs.md`** : Orientation de la course de l'attaquant pour forcer la relance vers un côté fermé.

### 📐 Phase E : Coups de Pied Arrêtés & Spécificités (Priorité Basse)
17. **`cpa_offensifs_corners.md`** : Combinaisons de corners (premier poteau, rentrant/sortant), création de blocs de démarquage.
18. **`cpa_defensifs_marquage.md`** : Organisation sur corner défensif : zone (protection des 6 mètres) vs individuel (marquage des sauteurs).
19. **`tactique_gestion_tempo.md`** : Alternance entre jeu direct et possession lente pour fatiguer l'adversaire ou conserver un score.
20. **`tactique_superiorite_numerique_relance.md`** : Utilisation du gardien et création de triangles dans les 16,50 mètres pour casser les pressings ultra-hauts.
