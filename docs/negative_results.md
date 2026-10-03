# VISION-BALLING : Résultats Négatifs & Limites Scientifiques

Ce document compile les résultats négatifs, hypothèses réfutées et limites intrinsèques constatés au cours des expériences scientifiques (EXP-01 à EXP-26). Conformément aux principes de transparence scientifique et de rigueur méthodologique, ces constats documentent ce que le système ne peut pas garantir afin d'éviter toute sur-interprétation ou hallucination de capacités non éprouvées.

---

## 1. Échec de l'Inférence des Formations Tactiques Catégoriques (EXP-21)

### Hypothèse initiale
Déduire la composition structurelle nominale d'une équipe (ex. 4-4-2, 4-3-3, 3-5-2) directement à partir des positions métriques 2D des joueurs et de l'orientation tactique, sans attribution de postes fixes prédéfinis.

### Constat expérimental
- **Performance synthétique** : 100 % d'exactitude sur des constellations complètes (10 joueurs de champ visibles) sous bruit gaussien modéré ($\sigma \le 1.5$ m).
- **Performance sur séquences réelles de broadcast (SNMOT-060 à SNMOT-071)** :
  - **Macro F1** : 0.00 % sur les séquences de test/holdout.
  - Taux d'abstention explicite : élevé (conformément aux seuils de visibilité $N \le 6 \implies \text{UNKNOWN}$, $N \in [7, 8] \implies \text{PARTIAL}$).
- **Facteurs causaux identifiés** :
  1. **Troncation du champ de vision (FOV Truncation)** : Les caméras de retransmission TV cadrent le porteur du ballon et le duel immédiat, coupant fréquemment la ligne défensive ou les ailiers opposés.
  2. **Déformations tactiques fluides** : En phase dynamique, une équipe en 4-3-3 déforme constamment son bloc (décrochage d'un milieu, projection d'un latéral), rendant la distance aux prototypes rigides caduque.
  3. **Inadéquation du concept de "formation fixe"** : Le football moderne opère en asymétries de phase (ex. 3-2-4-1 avec ballon, 4-4-2 sans ballon).

### Décision scientifique & Traitement
- **Fermeture des formations nominales** : Les labels catégoriques de formation ne sont pas retenus comme métriques de production fiables.
- **Remplacement par des grandeurs continues** : Le système préserve les coordonnées continues de centroïdes, les distances inter-lignes (défense-milieu-attaque) et l'étalement spatial (largeur, profondeur), sans imposer d'étiquette catégorique artificielle.

---

## 2. Inadéquation des Catégories Discrètes de Pression Défensive (EXP-23)

### Hypothèse initiale
Classifier la pression défensive subie par le porteur en classes discrètes : `AUCUNE`, `FAIBLE`, `MOYENNE`, `FORTE`.

### Constat expérimental
- Les seuils discrets introduisent des effets de bord arbitraires : un défenseur situé à 3,01 m classe l'action en `MOYENNE`, tandis qu'à 2,99 m elle bascule en `FORTE`, générant un scintillement fréquentiel nuisible aux analyses downstream.
- La pression réelle dépend conjointement de la distance relative, de la vitesse d'approche ($\vec{v}_{\text{closing}}$), de la densité locale de soutiens et de la couverture angulaire des lignes de passe.

### Décision scientifique & Traitement
- **Abandon des classes discrètes** au profit d'un indice scalaire continu :
  $$\text{PressureIndex} \in [0, 1]$$
  calibré selon des lois exponentielles physiques dépendantes de la distance, pondéré par la vitesse de fermeture vectorielle et la densité d'adversaires dans un rayon de 3 m à 8 m.

---

## 3. Goulot d'Étranglement de la Détection de Passes de Bout en Bout (EXP-19 / EXP-22)

### Hypothèse initiale
Détecter l'intégralité des passes et changements de possession uniquement via le pipeline de vision automatique.

### Constat expérimental
- **Mode A (Pipeline CV automatique complet)** :
  - Recall passes : ~3.64 % à 20.0 % selon les séquences de holdout.
  - Précision : 4.17 % à 13.33 %.
- **Mode B (Oracle état porteur propre)** :
  - Recall passes : **80.0 %**.
- **Conclusion diagnostique** : La machine à états tactique de transition et de passe fonctionne rigoureusement sur le plan logique, mais son rappel end-to-end reste étroitement conditionné par les instabilités amont du tracking vidéo (pertes du ballon, occultations du porteur lors des duels, faux positifs de proximité).

---

## 4. Limite de Fréquence Plein Pipeline (25 FPS non atteint)

### Hypothèse initiale
Exécuter la chaîne complète de vision par ordinateur et d'intelligence tactique en temps réel strict (25 images par seconde).

### Constat expérimental
- Sur station de travail type CPU/GPU standard :
  - **Mode `QUALITY`** (RF-DETR small 960p / YOLO11s + BoT-SORT ReID + PnLCalib complet + lissage géométrique + calculs de pression + fusion RAG) : **~11.4 FPS**.
  - **Mode `LOW_LATENCY`** (YOLO11n 640p + ByteTrack + homographie rapide) : **~24.2 FPS**.
- Le pipeline complet ne garantit donc pas un traitement temps réel strict à 25 FPS sans compromis sur la résolution ou sans infrastructure multi-GPU dédiée.

---

## 5. Hypothèse Planarité du Ballon ($Z = 0$)

### Limite physique
La projection par homographie 2D planaire calcule les coordonnées métriques terrain $(X, Y)$ en supposant que l'objet est situé au niveau du sol ($Z = 0$).
- Cette hypothèse est valide pour les pieds des joueurs en contact avec la pelouse.
- Pour le ballon lors des passes lobées, transversales aériennes, dégagements du gardien et tirs en hauteur, la parallaxe induit une déformation géométrique : la position projetée du ballon "au sol" s'éloigne de sa projection orthogonale réelle.

---

## 6. Contraintes Légales et Isolement de PnLCalib (GPL-2.0)

- PnLCalib est distribué sous licence GNU GPL-2.0.
- Pour respecter scrupuleusement les exigences de licence et préserver la modularité permissive du reste de l'architecture VISION-BALLING (FastAPI, React, SQLite, Qdrant), PnLCalib est encapsulé dans un adaptateur subprocess hermétique (`calibration_adapters.py`).
- Toute utilisation commerciale directe exige une étude de conformité ou le recours exclusif à des briques alternatives permissives (TVCalib sous licence MIT).
