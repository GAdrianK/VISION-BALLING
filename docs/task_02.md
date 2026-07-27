# 📋 Fiche Technique : Tâche T-02 — Base de Connaissances Tactiques - Partie B (Pressing & Rôles Modernes)

Cette fiche spécifie le travail requis pour rédiger la seconde partie de la base de connaissances tactiques de Football IQ Assistant, focalisée sur la récupération de balle et la définition des rôles de joueurs.

---

## 🎯 1. Objectif
Rédiger deux documents Markdown exhaustifs décrivant :
1. Les différents types de pressing collectifs et leurs déclencheurs (pressing haut, pressing intermédiaire, contre-pressing).
2. La définition théorique et le rôle terrain des postes modernes du football (Faux 9, Pivot, Double Pivot, Inverted Fullback, Box-to-Box, Mezzala/Intérieur).

Ces documents doivent enrichir sémantiquement la base du moteur RAG en employant un lexique d'expert et en fournissant des séances d'entraînement adaptées.

---

## 📂 2. Structure des Documents
Les fichiers seront placés dans le dossier RAG existant :
- `[NEW] football-rag-system/data_football/knowledge_base/pressing_contre_pressing.md` : Concepts de récupération, types de pressing et déclencheurs.
- `[NEW] football-rag-system/data_football/knowledge_base/roles_modernes.md` : Lexique détaillé des rôles tactiques contemporains.

---

## 📐 3. Plan Détaillé & Concepts Indispensables

### A. Fichier `pressing_contre_pressing.md`
1. **Introduction au Pressing :** Transition défensive et volonté de dicter le rythme sans ballon.
2. **Pressing Haut (High Press) :** Bloc haut, cadrage individuel, orientation vers l'extérieur.
3. **Pressing Intermédiaire (Mid Press / Block) :** Bloc médian (4-4-2 compact), fermer les lignes intérieures, coulissement rigoureux.
4. **Le Contre-Pressing (Gegenpressing) :** Réaction dans les 3 à 5 secondes après la perte. Modèles Klopp (cadrage porteur) vs Guardiola (fermeture des lignes de passes proches).
5. **Déclencheurs de Pressing (Pressing Triggers) :**
   - Passe latérale lente ou rebondissante.
   - Contrôle raté ou joueur dos au jeu.
   - Passe dans un couloir ou vers un joueur en infériorité.
6. **Exercice d'entraînement :** Séance en 4 blocs (Échauffement Rondo de transition, Exercice de pressing en cage/zone, Jeu dirigé sous contrainte temporelle de récupération).

### B. Fichier `roles_modernes.md`
1. **Rôles Offensifs :**
   - *Faux 9 (False 9) :* Décrochage pour créer le surnombre au milieu, aspiration des défenseurs centraux.
   - *Pivot :* Point d'appui dos au jeu, déviation et conservation sous pression physique.
2. **Rôles du Milieu :**
   - *Double Pivot (Double 6/8) :* Stabilité défensive (3-2 ou 4-2), couverture mutuelle, relance propre.
   - *Box-to-Box (8 moderne) :* Volume de course, capacité à répéter les efforts, présent dans les deux surfaces.
   - *Intérieur / Mezzala (8 offensif) :* Occupation des demi-espaces (half-spaces), projection dans la surface et création.
3. **Rôles Défensifs :**
   - *Inverted Fullback (Latéral inversé) :* Latéral qui rentre dans l'axe en phase de possession pour former un milieu à 3 ou un double pivot.
4. **Exercice d'entraînement :** Exercice de positionnement axé sur la coordination entre l'Inverted Fullback et le double pivot pour sécuriser les transitions.

---

## 📏 4. Longueur Cible
- Chaque fichier Markdown doit contenir au moins 1500 à 2000 mots pour offrir une granularité d'information suffisante lors du découpage (chunking) RAG.
- Richesse terminologique exigée.

---

## 🚀 5. Plan d'Implémentation
1. **Rédaction de `pressing_contre_pressing.md`** : Expliquer les déclencheurs et les blocs de pressing de façon didactique.
2. **Rédaction de `roles_modernes.md`** : Décrire chaque rôle individuellement avec ses forces, ses responsabilités et son animation dans le football de position.
3. **Validation de la structure Markdown** : Vérifier le rendu des titres et des listes à puces.

---

## 🧪 6. Critères de Validation
- [ ] Les fichiers `pressing_contre_pressing.md` et `roles_modernes.md` sont créés dans le bon répertoire.
- [ ] Tous les rôles demandés (Faux 9, Pivot, Double Pivot, Inverted Fullback, Box-to-Box, Intérieur) sont explicités.
- [ ] Les types de pressing (Haut, Intermédiaire, Gegenpressing) et leurs déclencheurs sont détaillés.
- [ ] Chaque fichier inclut une séance/exercice d'entraînement cohérent.
