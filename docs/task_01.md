# 📋 Fiche Technique : Tâche T-01 — Base de Connaissances Tactiques - Partie A (Bloc Bas & Sortie de Balle)

Cette fiche spécifie le travail requis pour rédiger les concepts tactiques de référence concernant l'animation contre bloc bas et la sortie de balle sous pressing.

---

## 🎯 1. Objectif
Rédiger des fiches de connaissances tactiques de niveau professionnel en format Markdown. Ces fiches serviront de base de données documentaire sémantique pour le moteur RAG. Elles doivent surclasser les connaissances génériques des modèles de langage en fournissant des principes précis, de la terminologie d'entraîneur (troisième homme, joueur libre, supériorité positionnelle), des structures d'exercices d'entraînement et des consignes concrètes.

---

## 📂 2. Structure des Fichiers
Les fichiers seront créés dans un répertoire dédié à la base de connaissances du système RAG :
- `[NEW] football-rag-system/data_football/knowledge_base/bloc_bas.md` : Guide d'attaque et de contournement d'un bloc bas défensif.
- `[NEW] football-rag-system/data_football/knowledge_base/sortie_balle.md` : Principes tactiques de la relance et de la sortie de balle sous pressing adverse.

---

## 🏗️ 3. Contenu Attendu

### A. Fichier `bloc_bas.md`
Ce document doit couvrir :
1. **Définition & Structure :** Qu'est-ce qu'un bloc bas (5-4-1, 4-4-2 compact) et les contraintes qu'il impose (densité centrale, absence d'espace dans le dos de la défense).
2. **Principes d'Attaque :**
   - *Fixer pour libérer :* Utiliser les ailiers ou pistons pour étirer la ligne défensive.
   - *Jeu entre les lignes :* Rôle des milieux offensifs/relayeurs dans les demi-espaces (half-spaces).
   - *Supériorité numérique et positionnelle :* Triangles sur les côtés, dédoublements.
   - *Changement de rythme et verticalité :* Passes progressives rapides à travers le bloc.
3. **Exercice d'entraînement type :** Une séance structurée (Échauffement, Exercice de conservation, Jeu dirigé).
4. **Consignes clés de terrain :** Phrases courtes pour le coach à crier lors des séances.

### B. Fichier `sortie_balle.md`
Ce document doit couvrir :
1. **Objectifs de la Sortie de Balle :** Conserver la possession sous pression, progresser proprement, et créer des décalages dès la première ligne.
2. **Mécanismes Tactiques Clés :**
   - *Supériorité à la relance :* Sortie à 3 (milieu qui descend entre ou à côté des défenseurs centraux - Salida Lavolpiana).
   - *Le concept de "Joueur Libre" & "Troisième Homme" :* Utiliser le gardien comme appui ou trouver le milieu défensif dos au jeu pour jouer en un temps vers un joueur face au jeu.
   - *Fixations provocatrices :* Le défenseur central conduit le ballon pour forcer un joueur adverse à sortir de sa zone.
3. **Exercice d'entraînement type :** Un exercice de transition/conservation sous pression (ex. 4+Gardien vs 3 avec cibles de progression).
4. **Consignes clés de terrain :** Consignes de placement, de profil d'orientation et de synchronisation des appels.

---

## 🚀 4. Plan d'Implémentation

### Étape 1 : Rédaction de `bloc_bas.md`
Rédiger de manière exhaustive avec une structure Markdown propre en utilisant des balises de titre (H1, H2, H3), des listes à puces et des encadrés de conseils pratiques.

### Étape 2 : Rédaction de `sortie_balle.md`
Rédiger le second document en suivant les mêmes exigences de précision théorique et d'application terrain.

### Étape 3 : Structuration RAG
S'assurer que le dossier `football-rag-system/data_football/knowledge_base/` est correctement organisé pour que le futur ingesteur sémantique puisse le scanner de façon récursive.

---

## 🧪 5. Validation

### Protocole de Test Humain
1. Vérifier la lisibilité des fichiers Markdown.
2. S'assurer que le vocabulaire utilisé est technique et crédible pour un entraîneur diplômé.
3. Vérifier que la structure des exercices respecte les 4 blocs fondamentaux (Échauffement, Exercice 1, Exercice 2, Jeu final) pour être compatible avec l'export PDF.

---

## 🏁 6. Critères de Validation
- [ ] Le répertoire `football-rag-system/data_football/knowledge_base/` existe.
- [ ] Le fichier `bloc_bas.md` est rédigé de manière complète avec au moins 4 sections tactiques.
- [ ] Le fichier `sortie_balle.md` est rédigé de manière complète avec au moins 4 sections tactiques.
- [ ] Les deux fichiers sont exempts d'erreurs de syntaxe Markdown et contiennent des fiches d'exercices structurées.
