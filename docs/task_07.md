# 🎨 Spécifications de la Tâche T-07 : Interface Frontend & Layout HTML/CSS Premium

Ce document sert de spécification technique et visuelle pour la création du layout de l'application Football IQ Assistant.

---

## 🎯 1. Objectif

Concevoir et réaliser l'interface utilisateur (UI/UX) de l'assistant de chat sous forme d'une application monopage (SPA) moderne. L'accent est mis sur une esthétique haut de gamme (Dark mode ardoise, accents vert terrain, design épuré, transitions fluides) et sur la clarté du sélecteur de mode tactique (Coach, Analyste, Fan).

---

## 📐 2. Wireframe Textuel de l'Interface

```text
+------------------------------------------------------------------------------------+
| SIDEBAR                 | MAIN PANEL (Zone de discussion)                         |
|                         |                                                          |
| ⚽ Football IQ          |  Header: [ Football IQ Assistant ]       ● RAG Local     |
|    Assistant Tactique   |  ------------------------------------------------------  |
|                         |  Sélecteur de Mode :                                     |
| +---------------------+ |  [ 📋 Coach (Actif) ]   [ 🔍 Analyste ]      [ 📣 Fan ]  |
| | + Nouvelle Session  | |  ------------------------------------------------------  |
| +---------------------+ |  Zone de Messages :                                      |
|                         |                                                          |
| Historique (Mock)       |    [Utilisateur] : Explique-moi ce qu'est un faux 9.      |
| - Séance Pressing Haut  |                                                          |
| - Relance Inverted L    |    [Assistant - Coach] : Le Faux 9 est un attaquant...   |
|                         |    +---------------------------------------------------+ |
|                         |    | 📄 Source : roles_modernes.md                     | |
|                         |    +---------------------------------------------------+ |
|                         |    [ 📥 PDF ] [ ⚡ Simplifier ] [ 🔍 Approfondir ] [📋]   |
|                         |                                                          |
|                         |  ------------------------------------------------------  |
| v1.0.0 (MVP)            |  [ Écrivez votre question tactique...               ] (>) |
|                         |  Football IQ v1.0.0. Propulsé par RAG Local.             |
+------------------------------------------------------------------------------------+
```

---

## 📂 3. Fichiers Concernés

- `[NEW] frontend/index.html` : Squelette structurel sémantique de l'application.
- `[NEW] frontend/styles.css` : Système de styles CSS customisé premium.
- `[NEW] frontend/app.js` : Logique minimale d'interaction UI (sélecteur de modes, gestion des placeholders).
- `[MODIFY] docs/sprint_01_progress.md` : Mise à jour du tableau de bord de suivi.

---

## 🚀 4. Plan d'Implémentation

1. **Création du dossier `frontend/`** s'il n'existe pas.
2. **Définition de la palette CSS :**
   - Fond global : Midnight Slate (`#0b0f19`).
   - Conteneurs : Glassmorphism (`rgba(30, 41, 59, 0.5)`).
   - Accents : Vert Émeraude (`#10b981`).
   - Texte : Blanc cassé/Gris clair (`#f8fafc` / `#94a3b8`).
3. **Mise en page structurelle (`index.html`) :**
   - Sidebar gauche avec logo et sections d'historique factices.
   - Header de chat avec titre et voyant RAG actif.
   - Zone de sélection des 3 modes tactiques (boutons avec icônes SVG intégrées).
   - Chat area contenant un mock complet d'échange tactique pour prévisualiser les bulles.
   - Input de chat fixe en bas.
4. **Logique JS (`app.js`) :**
   - Gestion de l'état `active` des 3 modes.
   - Adaptation dynamique du message de bienvenue et du placeholder de saisie.

---

## 🏁 5. Critères de Validation

- L'affichage dans le navigateur est net, sans bug visuel ou débordement.
- Les boutons Coach, Analyste, et Fan changent d'état actif (couleur verte et surbrillance) au clic.
- La mise en page est responsive (la sidebar devient un tiroir ou se collapse proprement sur écran mobile).
- Aucun appel d'API n'est déclenché (que des données mockées à ce stade).
