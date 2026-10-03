# RAPPORT D'INTELLIGENCE TACTIQUE VIDÉO : SÉQUENCE `SNMOT-068`
> [!NOTE] Ce rapport d'analyse est généré exclusivement à partir d'évidences visuelles validées (EXP-25) et de primitives géométriques mesurées. Aucune extrapolation spéculative ou formation rigide n'est affirmée sans support probatoire direct.

## 1. VUE D'ENSEMBLE DU MATCH & COUVERTURE D'ÉVIDENCE
La séquence analysée s'étend de 2.08s à 13.96s (durée active observée : 11.88s).
Le pipeline de fusion d'évidences tactiques a extrait un total de 16 événements probants sur la séquence.
La distribution épistémique comprend 14 faits physiques mesurés (Niveau 1), 0 tendances structurelles (Niveau 2), et 2 candidats tactiques qualifiés (Niveau 3).

## 2. CONTRÔLE DU BALLON & CONTINUITÉ DE POSSESSION
> [!IMPORTANT] L'estimateur de possession EXP-22 opère sur des trajectoires de détection soumises aux troncatures broadcast. Les pourcentages ci-dessous reflètent le temps de possession sécurisée mesuré sur les frames analysées, et non une statistique absolue de match.
- **TEAM_0** : Sur les images exploitables, l'estimateur a mesuré 18.6% de possession sécurisée (durée cumulée : 2.60s, transitions/pertes enregistrées : 3) [source:team_summary/TEAM_0/possession | cov=100% | conf=0.54].
- **TEAM_1** : Sur les images exploitables, l'estimateur a mesuré 43.7% de possession sécurisée (durée cumulée : 6.12s, transitions/pertes enregistrées : 1) [source:team_summary/TEAM_1/possession | cov=100% | conf=0.55].

## 3. ORGANISATION DÉFENSIVE, BLOC & COMPACITÉ
> [!TIP] Conformément à la politique EXP-21/EXP-25, les déformations tactiques fluides sont décrites par leurs coordonnées continues (hauteur de ligne, largeur, profondeur) plutôt que par des étiquettes de formation nominales (4-3-3 ou 4-4-2).
- **TEAM_0** : La ligne défensive s'est positionnée à une hauteur moyenne mesurée de 65.7m du but défendu, correspondant à un bloc haut (supérieur à la ligne médiane) [source:team_summary/TEAM_0/defensive_line | cov=100% | conf=0.54].
  La structure spatiale présentait une profondeur moyenne de 24.7m, une largeur de 19.6m et une surface d'enveloppe convexe moyenne de 219.9m² [source:team_summary/TEAM_0/compactness | conf=0.54].
- **TEAM_1** : La ligne défensive s'est positionnée à une hauteur moyenne mesurée de 22.6m du but défendu, correspondant à un bloc bas [source:team_summary/TEAM_1/defensive_line | cov=100% | conf=0.55].
  La structure spatiale présentait une profondeur moyenne de 22.7m, une largeur de 15.4m et une surface d'enveloppe convexe moyenne de 135.9m² [source:team_summary/TEAM_1/compactness | conf=0.55].

## 4. PRESSION DÉFENSIVE & HARCÈLEMENT CONTINU
> [!NOTE] Les indices de pression reposent sur les primitives continues de l'EXP-23 (proximité, vitesse de fermeture géométrique et densité locale).
- **TEAM_0** : Pression moyenne exercée de 0.264 (pic mesuré à 0.775), avec 3 épisodes de pression à haute intensité documentés [source:team_summary/TEAM_0/pressure | conf=0.54].
- **TEAM_1** : Pression moyenne exercée de 0.461 (pic mesuré à 1.000), avec 3 épisodes de pression à haute intensité documentés [source:team_summary/TEAM_1/pressure | conf=0.55].

## 5. TRANSITIONS APRÈS PERTE DE BALLE & CANDIDATS CONTRE-PRESSING
> [!CAUTION] Les détections de transitions (Niveau 3) sont des candidats diagnostiques qualifiés par des heuristiques de physique du jeu. Elles ne constituent pas des annotations tactiques humaines indépendantes certifiées.
- **TEAM_0** : Après perte de balle, les signaux physiques mesurés sont compatibles avec un candidat de contre-pressing (score moyen : 0.529) et un indice de repli défensif de 0.194 [source:team_summary/TEAM_0/transitions | conf=0.54].
- **TEAM_1** : Aucun épisode de transition agressive post-perte significative n'a été détecté [source:team_summary/TEAM_1/transitions | conf=0.55].

## 6. TRANSMISSIONS DE BALLE & DISPLACEMENTS OBSERVÉS
- **TEAM_0** : Transmissions de balle directes validées par filtrage qualité : 0 (déplacement longitudinal net : +0.0m) [source:team_summary/TEAM_0/ball_transfers | conf=0.54].
- **TEAM_1** : Transmissions de balle directes validées par filtrage qualité : 0 (déplacement longitudinal net : +0.0m) [source:team_summary/TEAM_1/ball_transfers | conf=0.55].

## 7. CHRONOLOGIE DES ÉVÉNEMENTS PROBANTS CLÉS
- **2.08s – 2.16s** (Fait physique) : TEAM_0 ball transfer completed (2.08–2.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]
- **2.08s – 9.68s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08–9.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]
- **2.16s – 2.16s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW]. [event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]
- **2.16s – 3.20s** (Candidat qualifié) : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16–3.20s, Δt=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60]. [event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]
- **7.80s – 8.24s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (7.80–8.24s, dur: 0.44s). Mean PressureIndex: 0.37 (peak: 0.54), min defender proximity: 1.7m. [event:press_196_207_TEAM_0 | t=7.80s | conf=0.37 | HIGH]
- **9.88s – 11.44s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (9.88–11.44s, dur: 1.56s). Mean PressureIndex: 0.46 (peak: 0.66), min defender proximity: 1.4m. [event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]
- **10.20s – 10.20s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 10.20s (frame 256). Possession confidence: 0.48 [HIGH]. [event:poss_change_256_TEAM_0_to_TEAM_1 | t=10.20s | conf=0.48 | HIGH]
- **10.20s – 10.76s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (10.20–10.76s, dur: 0.56s). Mean PressureIndex: 0.45 (peak: 0.64), min defender proximity: 1.4m. [event:press_256_270_TEAM_0 | t=10.20s | conf=0.45 | HIGH]
- **10.20s – 11.24s** (Candidat qualifié) : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (10.20–11.24s, Δt=1.04s). Nearest defender closed from 3.1m to 3.2m; PressureIndex changed from 0.21 to 0.29. CounterpressScore: 0.46 [Confidence: 0.45]. [event:trans_256_281_TEAM_0_NEUTRAL_TRANSITION | t=10.20s | conf=0.45 | HIGH]
- **12.40s – 13.96s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (12.40–13.96s, dur: 1.56s). Mean PressureIndex: 0.61 (peak: 1.00), min defender proximity: 0.2m. [event:press_311_350_TEAM_1 | t=12.40s | conf=0.61 | HIGH]
- **12.92s – 13.04s** (Fait physique) : TEAM_0 ball transfer completed (12.92–13.04s). Distance: 2.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_324_327_TEAM_0_PASS_INTERCEPTED | t=12.92s | conf=0.86 | HIGH]
- **13.04s – 13.04s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 13.04s (frame 327). Possession confidence: 0.93 [HIGH]. [event:poss_change_327_TEAM_0_to_TEAM_1 | t=13.04s | conf=0.93 | HIGH]
- **13.04s – 13.96s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (13.04–13.96s, dur: 0.92s). Mean PressureIndex: 0.66 (peak: 0.78), min defender proximity: 1.1m. [event:press_327_350_TEAM_0 | t=13.04s | conf=0.66 | HIGH]
- **13.20s – 13.60s** (Fait physique) : TEAM_1 ball transfer completed (13.20–13.60s). Distance: 3.4m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_331_341_TEAM_1_PASS_INTERCEPTED | t=13.20s | conf=0.86 | HIGH]
- **13.60s – 13.60s** (Fait physique) : TEAM_1 lost possession to TEAM_0 at 13.60s (frame 341). Possession confidence: 0.97 [HIGH]. [event:poss_change_341_TEAM_1_to_TEAM_0 | t=13.60s | conf=0.97 | HIGH]

## 8. QUALITÉ DES DONNÉES & LIMITES MÉTHODOLOGIQUES
- L'analyse est soumise à la troncature du champ de vision propre aux retransmissions télévisées standard.
- Les inférences de pressing et de transition restent des proxies physiques sans validation sémantique humaine indépendante.
- L'exactitude des chaînes de passes est dépendante du bruit de tracking sur le porteur du ballon.

**Avertissements spécifiques à cette séquence :**
- Diagnostic candidate semantics; physics-derived GT evaluation
- Downstream of pass detector baseline; precision limited by tracking flicker
