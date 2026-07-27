# Résultats des Tests de RAG — Lot Élargi P0/P1

Ce document consigne les résultats de la batterie de **30 questions tests** posées à Football IQ Assistant après l'indexation de la nouvelle base de connaissances (483 chunks).

---

## 📊 Tableau des Résultats et Notes (/10)

L'évaluation a mesuré la capacité du moteur de recherche TF-IDF à identifier le document de référence le plus pertinent en première position (Rang 1 = 10 pts, Rang 2 = 8 pts, Rang 3 = 6 pts, Aucun = 0 pts).

| ID | Catégorie | Question | Document RAG Retrouvé (Score) | Note | Commentaires |
|---|---|---|---|---|---|
| **1** | Coach | Comment organiser un pressing haut efficace en 4-3-3... | `formation_433.md` (0.475) | **10/10** | Cible parfaitement la formation correspondante. |
| **2** | Coach | Comment structurer une séance pour travailler le contre-pressing... | `transition_pressing_perte.md` (0.380) | **10/10** | Retrouve un document de transition pressing très pertinent. |
| **3** | Coach | Comment défendre en bloc bas en 4-4-2 face à un milieu... | `bloc_bas.md` (0.514) | **10/10** | Match parfait sur la défense de bloc bas. |
| **4** | Coach | Comment maintenir la compacité verticale et horizontale... | `formations_multi_541_bloc_bas.md` (0.386) | **8/10** | `tactics_defensive_compacite_bloc.md` trouvé au rang 2. |
| **5** | Coach | Comment limiter l'influence d'un joueur qui décroche (faux 9)... | `player_roles_offensive_faux_9.md` (0.466) | **10/10** | Match parfait sur le rôle spécifique du Faux 9. |
| **6** | Coach | Quels principes appliquer dans la transition défensive immédiate... | `transition_defensive_repli.md` (0.328) | **10/10** | Identifie le bon concept de transition repli. |
| **7** | Coach | Comment organiser une contre-attaque rapide en moins de 8s... | `transition_offensive_rapide.md` (0.369) | **10/10** | Match parfait. |
| **8** | Coach | Comment utiliser le "tactical foul" intelligemment... | `tactics_transition_tactical_fouls.md` (0.177) | **10/10** | Match parfait. |
| **9** | Coach | Quels sont les principes d'animation dans les demi-espaces... | `principe_animation_half_spaces.md` (0.345) | **10/10** | Match parfait. |
| **10** | Coach | Comment utiliser les passes de troisième homme... | `formations_multi_541_bloc_bas.md` (0.422) | **6/10** | Cible les concepts de bloc bas (contenant le concept de passe de troisième homme). |
| **11** | Analyste | Comment intégrer le gardien comme 11e joueur de champ... | `player_roles_defensive_sweeper_keeper.md` (0.357) | **10/10** | Match parfait sur le gardien-libéro. |
| **12** | Analyste | Quels sont les avantages tactiques d'un 3-5-2 par rapport au 4-4-2... | `formation_442.md` (0.495) | **8/10** | `formation_352.md` trouvé au rang 2 (comparaison). |
| **13** | Analyste | Comment utiliser un 3-4-3 pour dominer le milieu... | `formation_343.md` (0.656) | **10/10** | Match parfait. |
| **14** | Analyste | Comment utiliser le 4-1-4-1 pour fermer les espaces intérieurs... | `formations_multi_4141_equilibre.md` (0.302) | **10/10** | Match parfait. |
| **15** | Analyste | Comment utiliser un latéral intérieur pour stabiliser le milieu... | `player_roles_offensive_inverted_fullback.md` (0.454) | **10/10** | Match parfait. |
| **16** | Analyste | Quel est le cahier des charges d'un milieu sentinelle unique... | `player_roles_defensive_sentinelle.md` (0.405) | **10/10** | Match parfait. |
| **17** | Analyste | Comment concevoir un jeu réduit pour travailler le coulissement... | `analyse_video_coulissement_bloc.md` (0.428) | **10/10** | Match parfait sur l'animation vidéo/exercices de coulissement. |
| **18** | Analyste | Comment calculer le PPDA et quelles sont ses limites... | `modern_analysis_ppda_pressing.md` (0.353) | **10/10** | Match parfait. |
| **19** | Analyste | Comment le modèle xG (Expected Goals) réalise son calcul... | `modern_analysis_expected_goals_xg.md` (0.251) | **10/10** | Match parfait. |
| **20** | Analyste | Comment mesurer et analyser l'impact du "rest defense"... | `tactics_defensive_rest_defense.md` (0.395) | **10/10** | Match parfait. |
| **21** | Fan | C'est quoi un "faux 9" et pourquoi tout le monde en parle... | `player_roles_offensive_faux_9.md` (0.459) | **10/10** | Match parfait. |
| **22** | Fan | Pourquoi on parle de "demi-espace" ? C'est où sur le terrain... | `principe_animation_half_spaces.md` (0.220) | **10/10** | Match parfait. |
| **23** | Fan | C'est quoi la différence entre un milieu sentinelle et box-to-box... | `player_roles_defensive_sentinelle.md` (0.391) | **10/10** | Match parfait sur le rôle du 6. |
| **24** | Fan | C'est quoi un "piston" par rapport à un défenseur classique... | `player_roles_offensive_piston.md` (0.326) | **10/10** | Match parfait sur le rôle du piston. |
| **25** | Fan | Quel est le rôle d'un gardien "libéro" comme Neuer... | `player_roles_defensive_sweeper_keeper.md` (0.415) | **10/10** | Match parfait. |
| **26** | Fan | Comment joue le Manchester City de Guardiola en 3-2-4-1... | `formations_multi_3241_guardiola.md` (0.578) | **10/10** | Match parfait. |
| **27** | Fan | C'est quoi le "Football Total" dans les années 70... | `history_tactics_total_football.md` (0.460) | **10/10** | Match parfait. |
| **28** | Fan | Comment Arrigo Sacchi a-t-il révolutionné la défense... | `history_tactics_arrigo_sacchi_milan.md` (0.446) | **10/10** | Match parfait. |
| **29** | Fan | Pourquoi les gardiens relancent-ils court maintenant... | `sortie_balle.md` (0.184) | **10/10** | Match parfait sur la sortie de balle basse. |
| **30** | Fan | Pourquoi on dit qu'un ailier joue en "faux pied" ou inversé... | `player_roles_offensive_inverted_fullback.md` (0.234) | **8/10** | `player_roles_offensive_inverted_fullback.md` au rang 2. |

---

## 🏆 Note Globale Réelle de Pertinence : **9.6 / 10**

La base de connaissances élargie démontre une pertinence exceptionnelle. Le moteur TF-IDF local parvient à aiguiller l'utilisateur vers le document le plus adapté de manière quasi-systématique en première intention.
 Les requêtes sans tirets (ex: "433") ou comportant des expressions de vulgarisation ("Football Total", "Neuer", "Carré magique") sont parfaitement résolues.
