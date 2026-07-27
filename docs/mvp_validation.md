# 🧪 Cadre de Validation Fonctionnelle du MVP — Football IQ Assistant

Ce document définit la stratégie de test fonctionnel, le catalogue des 20 questions de validation sémantique et le protocole de test manuel pour valider le MVP avant d'implémenter de nouvelles fonctionnalités.

---

## 🎯 1. Catalogue de 20 Questions de Test Tactique

### 📋 Profil : Coach Tactique

#### Q1. Comment organiser une séance d'entraînement pour la sortie de balle face à un pressing haut ?
* **Résultat attendu :** Une structure de séance en plusieurs blocs (ex: rondo positionnel, jeu final) avec des règles spécifiques (touches limitées).
* **Connaissances RAG attendues :** `sortie_balle.md` (Section Séance d'entraînement type).
* **Critères de réussite :** Mention du rondo 4 vs 4 + 3 joueurs neutres (gardien, pivot 6, appui 8/10).
* **Critères d'échec :** Fournir des conseils d'entraînement génériques sans lien avec l'utilisation du pivot ou du gardien en appui.

#### Q2. Quelles consignes individuelles donner à mon attaquant pivot dos au but ?
* **Résultat attendu :** Consignes claires sur l'utilisation du corps, la remise en une touche et la fixation des défenseurs centraux.
* **Connaissances RAG attendues :** `roles_modernes.md` (Le Pivot).
* **Critères de réussite :** Termes du terrain comme "fixation", "point d'appui", "remises rapides".
* **Critères d'échec :** Parler du rôle d'un ailier ou d'un faux 9 à la place du pivot.

#### Q3. Comment déclencher le contre-pressing immédiatement après avoir perdu le ballon ?
* **Résultat attendu :** Les 3 à 5 secondes de réaction, cadrage immédiat du porteur, fermeture des lignes courtes.
* **Connaissances RAG attendues :** `pressing_contre_pressing.md` (Le Contre-Pressing / Gegenpressing).
* **Critères de réussite :** Règles des "6 secondes", compacité immédiate, harcèlement à la perte.
* **Critères d'échec :** Conseiller de reculer en bloc bas immédiatement après la perte.

#### Q4. Préparer une séance de travail sur la compacité du bloc bas.
* **Résultat attendu :** Exercices de coulissement, alignement défensif et gestion de la largeur de la surface.
* **Connaissances RAG attendues :** `bloc_bas.md` (Séance d'entraînement type).
* **Critères de réussite :** Mention de l'exercice du rondo de coulissement ou du match thématique 10 vs 8.
* **Critères d'échec :** Proposer une séance axée sur la contre-attaque rapide sans expliquer comment s'aligner ou coulisser.

#### Q5. Quelles consignes donner à mes joueurs pour défendre sur les centres en bloc bas ?
* **Résultat attendu :** Positionnement par rapport au ballon, alignement des défenseurs, orientation du corps.
* **Connaissances RAG attendues :** `bloc_bas.md` (Principes de base du bloc bas).
* **Critères de réussite :** Marquage individuel strict dans la surface, protection du premier poteau, corps orienté pour voir le ballon et le joueur.
* **Critères d'échec :** Conseiller un marquage de zone passif sans consignes d'orientation corporelle.

#### Q6. Comment animer un double pivot dans un schéma de relance ?
* **Résultat attendu :** Complémentarité des deux milieux axiaux (un qui décroche, un qui compense), création d'angles de passe.
* **Connaissances RAG attendues :** `roles_modernes.md` (Le Double Pivot).
* **Critères de réussite :** Mention de l'équilibre défensif, de l'alignement asymétrique et du rôle de compensation.
* **Critères d'échec :** Traiter les deux milieux comme des joueurs purement offensifs ou sans coordination entre eux.

#### Q7. Comment réagir si l'adversaire casse notre premier rideau de pressing ?
* **Résultat attendu :** Repli ordonné, passage en bloc médian/bas temporaire, cadrage du nouveau porteur par la ligne suivante.
* **Connaissances RAG attendues :** `pressing_contre_pressing.md` (Déclencheurs et animation).
* **Critères de réussite :** Mention de la transition défensive rapide et de la reformation du bloc compact.
* **Critères d'échec :** Inciter les attaquants à continuer de courir individuellement vers l'arrière sans coordination du bloc.

---

### 🔍 Profil : Analyste Technique

#### Q8. Quels sont les avantages structurels de la Salida Lavolpiana ?
* **Résultat attendu :** Création d'une supériorité numérique à la relance par le décrochage d'un milieu ou l'écartement des centraux.
* **Connaissances RAG attendues :** `sortie_balle.md` (La Salida Lavolpiana).
* **Critères de réussite :** Utilisation du numéro 6 qui s'intercale entre les deux défenseurs centraux, projection des latéraux.
* **Critères d'échec :** Confondre avec une relance classique à deux défenseurs sans soutien axial.

#### Q9. Analyser le rôle hybride de l'Inverted Fullback dans une structure en 3-2-4-1.
* **Résultat attendu :** Transition d'un latéral classique vers un milieu axial lors de la phase de possession pour densifier le cœur du jeu.
* **Connaissances RAG attendues :** `roles_modernes.md` (Inverted Fullback).
* **Critères de réussite :** Passage d'une ligne de 4 à une ligne de 3 derrière, formation du double pivot avec le 6.
* **Critères d'échec :** Le décrire comme un simple défenseur latéral qui déborde sur l'aile.

#### Q10. Quelle est la différence géométrique entre un pressing haut et un pressing intermédiaire ?
* **Résultat attendu :** Position de la ligne de récupération et de la ligne défensive sur le terrain.
* **Connaissances RAG attendues :** `pressing_contre_pressing.md` (Bloc haut vs bloc médian).
* **Critères de réussite :** Pressing haut (harcèlement dans les 16.5m adverses), Pressing intermédiaire (déclenchement au milieu de terrain, bloc médian compact).
* **Critères d'échec :** Définir la différence uniquement par l'agressivité des joueurs sans repères spatiaux sur le terrain.

#### Q11. Comment se positionne un Faux 9 pour créer des supériorités positionnelles dans les interlignes ?
* **Résultat attendu :** Décrochage de l'attaquant de pointe vers la zone du milieu de terrain pour aspirer un défenseur et libérer l'espace dans son dos.
* **Connaissances RAG attendues :** `roles_modernes.md` (Le Faux 9).
* **Critères de réussite :** Notion de "création d'incertitude", "interlignes", "appels croisés des ailiers".
* **Critères d'échec :** Présenter le faux 9 comme un attaquant de surface statique.

#### Q12. Quels sont les déclencheurs (triggers) de pressing les plus fréquents dans le football moderne ?
* **Résultat attendu :** Événements de jeu qui indiquent au bloc d'avancer et de presser collectivement.
* **Connaissances RAG attendues :** `pressing_contre_pressing.md` (Les déclencheurs de pressing).
* **Critères de réussite :** Mauvais contrôle de balle, passe en retrait lente, joueur orienté vers son propre but (dos au jeu), contrôle sur le mauvais pied.
* **Critères d'échec :** Dire que le pressing se fait de manière aléatoire sans signaux spécifiques.

#### Q13. Analyser la gestion de la largeur et de la profondeur par un bloc bas compact.
* **Résultat attendu :** Réduction des distances entre les lignes (verticale) et entre les joueurs (horizontale), abandon volontaire des couloirs extérieurs.
* **Connaissances RAG attendues :** `bloc_bas.md` (Principes tactiques).
* **Critères de réussite :** Distances cibles de 10-15m entre les lignes, coulissement vers le côté du ballon.
* **Critères d'échec :** Proposer de presser haut les latéraux adverses en élargissant le bloc défensif.

#### Q14. Quelle est la fonction d'un joueur box-to-box lors des transitions offensives et défensives ?
* **Résultat attendu :** Capacité à répéter les efforts dans les deux surfaces, volume de jeu, projection verticale.
* **Connaissances RAG attendues :** `roles_modernes.md` (Le Box-to-Box / Intérieur).
* **Critères de réussite :** Double tâche (soutien offensif à la création, rideau défensif à la perte), endurance.
* **Critères d'échec :** Le limiter à un rôle de milieu récupérateur statique ou de meneur de jeu exclusif.

---

### 📣 Profil : Supporter Passionné (Fan)

#### Q15. Pourquoi Guardiola fait-il jouer ses latéraux au milieu de terrain ?
* **Résultat attendu :** Explication vulgarisée mais tactique de la recherche de contrôle axial (Inverted Fullback).
* **Connaissances RAG attendues :** `roles_modernes.md` (Inverted Fullback), `sortie_balle.md`.
* **Critères de réussite :** Ton enthousiaste, mention de la création d'un double pivot pour étouffer les contres adverses au milieu.
* **Critères d'échec :** Répondre de manière académique sans le ton coloré du supporter.

#### Q16. Le Gegenpressing de Klopp, c'est quoi le secret pour que ça marche ?
* **Résultat attendu :** Explication passionnée du contre-pressing immédiat à la perte pour surprendre l'adversaire désorganisé.
* **Connaissances RAG attendues :** `pressing_contre_pressing.md` (Contre-pressing).
* **Critères de réussite :** Énergie, intensité des courses, récupération rapide près du but adverse.
* **Critères d'échec :** Description clinique de type universitaire sans aucune émotion ou jargon de supporter.

#### Q17. C'est quoi un vrai pivot à l'ancienne et pourquoi c'est en train de revenir ?
* **Résultat attendu :** Nostalgie du grand attaquant physique servant de point d'appui contre les blocs bas modernes compacts.
* **Connaissances RAG attendues :** `roles_modernes.md` (Le Pivot).
* **Critères de réussite :** Jargon de supporter ("tour de contrôle", "jouer des coudes", "remise de la tête").
* **Critères d'échec :** Définir le pivot uniquement à travers des formules de manuel de formation.

#### Q18. Comment garer le bus (bloc bas) sans encaisser de but en fin de match ?
* **Résultat attendu :** Recommandations humoristiques mais tactiquement viables pour verrouiller l'axe et résister à la pression.
* **Connaissances RAG attendues :** `bloc_bas.md` (Défendre dans la surface).
* **Critères de réussite :** Utilisation de l'expression "garer le bus", mention de la compacité axiale et du sacrifice défensif.
* **Critères d'échec :** Recommander d'attaquer à outrance ou d'ouvrir le jeu.

#### Q19. Pourquoi le faux 9 de Messi sous Guardiola a révolutionné le foot ?
* **Résultat attendu :** Hommage au génie tactique de décrochage qui a rendu fous les défenseurs centraux adverses.
* **Connaissances RAG attendues :** `roles_modernes.md` (Le Faux 9).
* **Critères de réussite :** Ton admiratif, explication de l'espace vide créé dans l'axe pour les appels des ailiers.
* **Critères d'échec :** Évoquer uniquement les statistiques de buts de Messi sans expliquer le mécanisme du Faux 9.

#### Q20. Quelle est la meilleure façon de sortir du pressing adverse quand on se fait étouffer ?
* **Résultat attendu :** Conseils animés sur la sérénité technique, le jeu en triangle et la recherche du joueur libre.
* **Connaissances RAG attendues :** `sortie_balle.md` (Principes de sortie).
* **Critères de réussite :** Jargon ("sortir proprement", "trouver le 3ème homme", "triangulations").
* **Critères d'échec :** Conseiller de balancer de grands ballons devant de manière systématique sans mentionner la supériorité numérique ou technique.

---

## 📋 2. Protocole de Test Manuel du MVP

Ce protocole doit être exécuté par le développeur pour valider la pertinence du système.

### Étape 1 : Vérification de la Différenciation des Modes (Style & Ton)
1. Envoyer la même question : `"Quels sont les principes de l'inverted fullback ?"` sur les trois endpoints ou via le payload en variant le champ `mode`.
2. **Mesure de conformité :**
   - Le mode `coach` doit structurer sa réponse avec les titres "Analyse du Coach", "Consignes" et "Exercice".
   - Le mode `analyst` doit employer des termes comme "interlignes", "transition structurelle", "3-2-4-1" et rester neutre.
   - Le mode `fan` doit utiliser un langage chaleureux ("mon pote", "virage") et enthousiaste.

### Étape 2 : Vérification de la Qualité du RAG (Pertinence des Sources)
1. Soumettre la question : `"Comment sortir du pressing haut ?"`.
2. Inspecter la liste des `sources` retournées dans le JSON.
3. **Mesure de conformité :**
   - La liste doit contenir au moins `sortie_balle.md` avec un score de similarité significatif.
   - Le texte retourné en réponse doit citer explicitement les notions de supériorité numérique et d'orientation corporelle présentes dans le document d'origine.

### Étape 3 : Cohérence Tactique (Gestion des Gaps de Connaissances)
1. Poser une question hors-sujet ou hors base de connaissances tactique, par exemple : `"Quelle est la meilleure recette de pizza pour un joueur de foot ?"` ou `"Comment gérer la billetterie d'un club ?"`.
2. **Mesure de conformité :**
   - Le système ne doit pas halluciner de tactique de jeu.
   - Il doit répondre selon la consigne d'insuffisance de données (ex: "Je ne sais pas" ou "Mes connaissances sont limitées à notre base tactique actuelle").

### Étape 4 : Robustesse du Fallback Local (Offline)
1. Configurer la variable `OPENAI_API_KEY=mock-key-for-local-testing` dans le fichier `.env`.
2. Démarrer le serveur FastAPI et soumettre une requête `POST /api/chat`.
3. **Mesure de conformité :**
   - Le serveur ne doit renvoyer aucune erreur 500.
   - La réponse doit être générée localement par le moteur de réponse simulée (`_generate_mock_response`), en incorporant correctement les extraits des fichiers Markdown correspondants au RAG.
