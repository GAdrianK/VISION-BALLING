# Limites Connues et Périmètre Opérationnel (RC1)

> **Statut : Release Candidate 1 (v0.9.0-rc1).** Ce document consigne l'état réel des capacités, les frontières opérationnelles et les limites physiques du système après la réalisation des chapitres 1 à 8 (EXP-01 à EXP-26). Pour le détail des hypothèses réfutées et des échecs expérimentaux, se référer à [`negative_results.md`](negative_results.md).

---

## 1. Vision par Ordinateur & Traitement Vidéo

- **Fréquence de traitement (FPS)** :
  - Le pipeline de vision complet (détection fine + tracking ReID + calibration caméra + projection 2D) traite une vidéo entre **11.4 FPS** (`QUALITY`) et **24.2 FPS** (`LOW_LATENCY`) sur machine standard. Le temps réel strict (25 FPS constant) n'est pas garanti sans infrastructure GPU distribuée.
- **Occlusions et coupures de plan** :
  - Les changements de caméra (plans rapprochés, ralentis, banc de touche) rompent la continuité spatio-temporelle. Le système est conçu pour des séquences continues filmées depuis la caméra tactique principale (*main camera broadcast*).
- **Hypothèse de planarité du ballon ($Z = 0$)** :
  - La projection métrique par homographie 2D suppose que les objets sont au niveau du sol. Pour les trajectoires aériennes (dégagements, centres hauts, transversales), la position $(X, Y)$ au sol présente une erreur géométrique liée à la parallaxe de vue oblique.
- **Rappel de détection de passes** :
  - Bien que le moteur logique de détection de passes soit validé à 80 % sur vérité terrain d'états porteur (Oracle), le rappel de bout en bout sur vidéo brute varie de 4 % à 20 % en raison des pertes et scintillements de suivi du ballon lors des duels rapprochés.

---

## 2. Intelligence Tactique & Métriques Spatiales

- **Formations nominales catégoriques** :
  - L'assignation automatique d'étiquettes rigides (ex. 4-4-2, 4-3-3) est formellement déclarée non fiable en broadcast classique en raison de la troncation du champ de vision (FOV) par la caméra TV. Le système s'abstient et fournit à la place les distances inter-lignes continues, centroïdes et étalements métriques.
- **Pression défensive continue vs discrète** :
  - Les seuils discrets (`FORTE`, `FAIBLE`) génèrent des discontinuités de bord. Le système utilise un indice continu normalisé ($\text{PressureIndex} \in [0, 1]$) combinant proximité, vitesse de fermeture et densité locale.
- **Attribution d'équipe sans superviser les effectifs** :
  - La classification des équipes repose sur le clustering colorimétrique non supervisé (espace Lab + ReID). En cas de maillots très similaires (ex. maillots sombres sous forte ombre), une inversion ou une incertitude temporaire peut survenir.

---

## 3. Système RAG & Génération de Rapports

- **Nature de la vérité terrain (Epistémologie du RAG)** :
  - Le RAG tactique traite les événements structurés issus de la vidéo (`TacticalEvidenceEvent`) comme la **source de vérité autoritaire sur les faits du match**. La base de connaissances générale (Source B) sert exclusivement à expliquer le sens tactique des observations.
  - La garantie "zéro hallucination" certifie la **traçabilité intégrale** de chaque affirmation vers un événement vidéo horodaté mesuré par le système. Elle ne prétend pas que le système de vision est infaillible par rapport à la réalité absolue du terrain.
- **Abstention explicite** :
  - Lorsque la vidéo ne contient pas les éléments probants suffisants (ex. caméra cadrant ailleurs, joueurs hors champ, confiance d'estimation faible), le système refuse de répondre ou qualifie l'événement en `AMBIGUOUS` / `PARTIAL`.

---

## 4. Licences & Dépendances Externes

- **PnLCalib (GPL-2.0)** :
  - Le module PnLCalib est isolé dans un processus externe via subprocess. Toute redistribution ou commercialisation doit respecter les termes de la GPL-2.0 ou basculer sur TVCalib (licence MIT).
