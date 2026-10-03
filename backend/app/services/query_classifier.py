import re
from typing import Dict, Any, Optional, Tuple
from app.schemas.grounded_rag import QueryScope


class QueryClassifier:
    """
    Classifie les requêtes de l'utilisateur pour déterminer le type
    (salutation, hors-sujet, question tactique générale ou query vidéo contextualisée)
    et extraire les intentions sémantiques et le QueryScope (EXP-26 / Chapter 8).
    """
    def __init__(self):
        # Mots-clés pour les salutations
        self.greeting_patterns = [
            r"\b(salut|bonjour|bonsoir|hello|hey|yo|coucou|hi)\b",
            r"\bca\s+va\b",
            r"\bcomment\s+ca\s+va\b",
            r"\bcomment\s+allez-vous\b",
            r"\bcomment\s+vas-tu\b"
        ]
        
        # Mots-clés hors-sujet (cuisine, météo, actualités, politique, etc.)
        self.out_of_scope_patterns = [
            r"\bpizza\b",
            r"\brecette\b",
            r"\bcuisine\b",
            r"\bmeteo\b",
            r"\bmétéo\b",
            r"\bpolitique\b",
            r"\bcinema\b",
            r"\bcinéma\b",
            r"\bfilm\b",
            r"\bmusique\b",
            r"\bchanson\b",
            r"\bprésident\b",
            r"\bpresident\b",
            r"\bmacron\b",
            r"\bgouvernement\b",
            r"\bclimat\b"
        ]

        # Mot-clés de requêtes non supportées par l'analyse vidéo EXP-25 (Phase 21)
        self.unsupported_patterns = [
            r"\b(score|score\s+final|qui\s+a\s+gagné|qui\s+a\s+marqué|who\s+scored|final\s+score)\b",
            r"\b(xg|expected\s+goals|combien\s+de\s+xg|valeur\s+xg)\b",
            r"\b(homme\s+du\s+match|man\s+of\s+the\s+match|motm|mvp|note\s+du\s+joueur)\b",
            r"\b(plan\s+(?:tactique|de\s+jeu)?\s*du\s+coach|plan\s+du\s+coach|consigne\s+du\s+coach|coach's\s+plan|plan\s+de\s+jeu|arbitre|arbitrage|carton)\b",
        ]

        # Dictionnaires d'intentions
        self.intent_keywords = {
            "defend": [
                "défend", "defend", "couliss", "compac", "fermer l'axe", "défens", "defens",
                "marquage", "recul-frein", "garer le bus", "fermer les espaces", "repli", "reconstitution"
            ],
            "attack": [
                "attaqu", "attack", "déséquilibr", "desequilibr", "percer", "contourn", "marqu",
                "offens", "centr", "dédoubl", "dedoubl", "amplitude", "surcharge", "overload",
                "underlap", "overlap", "creer des espaces", "créer des espaces"
            ],
            "roles": [
                "faux 9", "pivot", "double pivot", "box-to-box", "gardien-libero", "gardien-libéro",
                "sweeper keeper", "inverted fullback", "latéral inversé", "relayeur", "mezzala",
                "raumdeuter", "inside forward", "piston"
            ],
            "formations": [
                "4-3-3", "3-5-2", "4-4-2", "3-4-3", "3-2-4-1", "4-2-3-1",
                "433", "352", "442", "343", "3241", "4231",
                "système", "systeme", "formation"
            ]
        }

        # Dictionnaires de phases
        self.phase_keywords = {
            "offensive": ["attaqu", "offens", "possession", "construction", "finition"],
            "defensive": ["défend", "défens", "defens", "repli", "recule", "coulisse", "marquage"],
            "transition": ["transition", "contre-press", "gegenpress", "récupér", "perte", "contre-attaq", "recupér"]
        }

    def classify(self, message: str, has_video_context: bool = False) -> Dict[str, Any]:
        """
        Analyse le message et renvoie sa classification complète incluant le QueryScope.
        """
        msg_lower = message.lower().strip()
        
        # 1. Vérification des Salutations
        is_greeting = False
        for pattern in self.greeting_patterns:
            if re.search(pattern, msg_lower):
                is_greeting = True
                break
                
        if is_greeting and not has_video_context:
            return {
                "type": "greeting",
                "intent": "general",
                "phase": "general",
                "query_scope": QueryScope.GENERAL_FOOTBALL,
            }
            
        # 2. Vérification des Hors-Sujets absolus
        is_out_of_scope = False
        for pattern in self.out_of_scope_patterns:
            if re.search(pattern, msg_lower):
                is_out_of_scope = True
                break
                
        if is_out_of_scope:
            return {
                "type": "out_of_scope",
                "intent": "general",
                "phase": "general",
                "query_scope": QueryScope.UNSUPPORTED,
            }

        # 3. Extraction temporelle et entités match
        temporal_info = self._extract_temporal_info(message)
        team_target = self._extract_team_target(msg_lower)
        has_video_indicators = (
            has_video_context
            or temporal_info["timestamp"] is not None
            or temporal_info["time_range"] is not None
            or temporal_info["frame"] is not None
            or team_target is not None
            or any(kw in msg_lower for kw in [
                "cette vidéo", "ce match", "cette séquence", "dans le clip", "l'équipe 0",
                "l'équipe 1", "team 0", "team 1", "qui perd le ballon", "qui a le ballon",
                "le ballon à", "qui presse", "quelle équipe a pressé"
            ])
        )

        # 4. Vérification des Requêtes Non Supportées (Phase 21)
        for pattern in self.unsupported_patterns:
            if re.search(pattern, msg_lower):
                return {
                    "type": "unsupported_metric",
                    "intent": "general",
                    "phase": "general",
                    "query_scope": QueryScope.UNSUPPORTED,
                    "temporal": temporal_info,
                    "target_team": team_target,
                    "entities": self.extract_tactical_entities(message),
                }

        # 5. Extraction des Intentions Tactiques
        detected_intent = "general"
        for intent, keywords in self.intent_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    if detected_intent == "general" or detected_intent in ["roles", "formations"]:
                        detected_intent = intent
                    break
                    
        # 6. Extraction de la Phase de Jeu
        detected_phase = "general"
        for phase, keywords in self.phase_keywords.items():
            for kw in keywords:
                if kw in msg_lower:
                    detected_phase = phase
                    break

        # 7. Détermination du QueryScope (Phase 3)
        query_scope = self._resolve_query_scope(
            msg_lower=msg_lower,
            has_video_indicators=has_video_indicators,
            temporal_info=temporal_info,
            team_target=team_target
        )

        # Type de retour
        if has_video_indicators and query_scope != QueryScope.GENERAL_FOOTBALL:
            resp_type = "video_tactical_query"
        else:
            resp_type = "tactical_question"

        return {
            "type": resp_type,
            "intent": detected_intent,
            "phase": detected_phase,
            "query_scope": query_scope,
            "temporal": temporal_info,
            "target_team": team_target,
            "entities": self.extract_tactical_entities(message)
        }

    def _extract_temporal_info(self, text: str) -> Dict[str, Any]:
        """Extrait les marqueurs temporels, timestamps, intervalles et frames."""
        msg_lower = text.lower()
        res: Dict[str, Any] = {
            "timestamp": None,
            "time_range": None,
            "frame": None,
            "relative_direction": None,
            "relative_window": None,
        }

        # Intervalle explicite: e.g. "entre 2.5s et 6.0s" ou "de 1 à 5 secondes"
        range_match = re.search(
            r"(?:entre|de)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secondes?)?\s*(?:et|à)\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secondes?)?",
            msg_lower
        )
        if range_match:
            t0 = float(range_match.group(1))
            t1 = float(range_match.group(2))
            res["time_range"] = (min(t0, t1), max(t0, t1))

        # Fenêtre relative: "dans les 5 secondes suivant" ou "5s après"
        rel_after = re.search(r"(?:dans les|sur les)?\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secondes?)\s*(?:suivant|après|apres)", msg_lower)
        if rel_after:
            res["relative_direction"] = "after"
            res["relative_window"] = float(rel_after.group(1))

        rel_before = re.search(r"(?:dans les|sur les)?\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secondes?)\s*(?:précédant|precedant|avant)", msg_lower)
        if rel_before:
            res["relative_direction"] = "before"
            res["relative_window"] = float(rel_before.group(1))

        # Timestamp exact: "à 12.4 secondes", "12.4s", "à 1.84 s"
        ts_match = re.search(r"(?:à|a|at)?\s*(\d+(?:\.\d+)?)\s*(?:s|sec|secondes?)\b", msg_lower)
        if ts_match and not range_match:
            res["timestamp"] = float(ts_match.group(1))

        # Frame explicite: "frame 145", "image 50"
        frame_match = re.search(r"(?:frame|image|trame)\s*(\d+)", msg_lower)
        if frame_match:
            res["frame"] = int(frame_match.group(1))

        return res

    def _extract_team_target(self, msg_lower: str) -> Optional[str]:
        """Extrait l'équipe ciblée (TEAM_0 ou TEAM_1)."""
        if re.search(r"\b(équipe\s*0|equipe\s*0|team\s*0)\b", msg_lower):
            return "TEAM_0"
        if re.search(r"\b(équipe\s*1|equipe\s*1|team\s*1)\b", msg_lower):
            return "TEAM_1"
        return None

    def _resolve_query_scope(
        self,
        msg_lower: str,
        has_video_indicators: bool,
        temporal_info: Dict[str, Any],
        team_target: Optional[str]
    ) -> QueryScope:
        """Détermine le QueryScope selon la présence d'éléments vidéo, temporels et conceptuels."""
        if not has_video_indicators:
            return QueryScope.GENERAL_FOOTBALL

        # Vérification si la question est purement conceptuelle/théorique malgré le contexte vidéo
        general_theory_keywords = [
            "c'est quoi", "qu'est-ce que", "qu'est-ce qu'", "définition", "explique ce qu'est",
            "comment fonctionne", "rôle du", "principes du", "différence entre", "avantages du",
            "avantages", "comment ", "quels sont", "quelles sont", "quel est le rôle",
            "définir", "organisation de", "principes de"
        ]
        has_match_anchors = (
            temporal_info["timestamp"] is not None
            or temporal_info["time_range"] is not None
            or temporal_info["frame"] is not None
            or team_target is not None
            or any(kw in msg_lower for kw in [
                "cette vidéo", "ce match", "dans ce match", "dans la vidéo", "l'action",
                "la perte à", "le pressing à", "souffert après", "ont réagi"
            ])
        )
        if any(kw in msg_lower for kw in general_theory_keywords) and not has_match_anchors:
            return QueryScope.GENERAL_FOOTBALL

        # A. MATCH_COMPARISON : comparaisons inter-équipes ou agrégats globaux
        comp_keywords = [
            "qui a pressé le plus", "plus pressé", "pressé le plus", "plus compact",
            "quelle équipe a", "comparer l'équipe", "comparaison des équipes",
            "différence de bloc", "qui a eu le plus la balle", "possession moyenne",
            "laquelle des deux équipes", "qui a dominé"
        ]
        if any(kw in msg_lower for kw in comp_keywords):
            return QueryScope.MATCH_COMPARISON

        # B. MATCH_EXPLANATION : causalité, causes, conséquences, pourquoi
        explanation_keywords = [
            "pourquoi", "pour quelle raison", "comment l'équipe a réagi", "conséquence",
            "conséquences", "qu'est-ce qui a causé", "explication de la perte",
            "suite à la perte", "après la perte", "pourquoi l'équipe 0 a souffert",
            "pourquoi l'équipe 1 a souffert", "pourquoi le bloc", "raison de la perte"
        ]
        if any(kw in msg_lower for kw in explanation_keywords):
            return QueryScope.MATCH_EXPLANATION

        # C. MATCH_TIMELINE : question chronologique ou repère temporel direct
        timeline_keywords = [
            "que se passe-t-il", "qu'est-ce qui se passe", "chronologie", "timeline",
            "déroulement", "à ce moment", "moment précis", "séquence temporelle",
            "que font les", "action à"
        ]
        if any(kw in msg_lower for kw in timeline_keywords) or temporal_info["timestamp"] is not None or temporal_info["time_range"] is not None:
            return QueryScope.MATCH_TIMELINE

        # D. MATCH_FACT : fait précis (porteur, équipe en possession, hauteur exacte, passe)
        fact_keywords = [
            "qui a le ballon", "qui perd le ballon", "qui récupère", "quelle équipe a le ballon",
            "quel est le porteur", "hauteur du bloc", "compactness", "y a-t-il une passe",
            "quelle est la vitesse", "distance du défenseur"
        ]
        if any(kw in msg_lower for kw in fact_keywords) or team_target is not None:
            return QueryScope.MATCH_FACT

        # Par défaut sous contexte vidéo : MATCH_FACT
        return QueryScope.MATCH_FACT

    def extract_tactical_entities(self, text: str) -> Dict[str, Any]:
        """
        Extrait les entités tactiques clés de la requête (formation, problem, phase, goal).
        """
        msg_lower = text.lower().strip()
        
        # 1. Extraction de la formation
        formation = None
        formations_patterns_hyphens = [
            r"4-3-3", r"3-5-2", r"4-4-2", r"3-4-3", r"3-2-4-1", r"4-2-3-1", r"5-4-1", r"4-1-4-1"
        ]
        for pattern in formations_patterns_hyphens:
            if re.search(r"\b" + pattern + r"\b", msg_lower):
                formation = pattern
                break
        
        if not formation:
            formations_no_hyphens = {
                "433": "4-3-3",
                "352": "3-5-2",
                "442": "4-4-2",
                "343": "3-4-3",
                "3241": "3-2-4-1",
                "4231": "4-2-3-1",
                "541": "5-4-1",
                "4141": "4-1-4-1"
            }
            for raw, normalized in formations_no_hyphens.items():
                if re.search(r"\b" + raw + r"\b", msg_lower):
                    formation = normalized
                    break

        # 2. Extraction du problème
        problem = None
        problem_keywords = {
            "pertes de balle": ["perdre", "perte", "perd", "déchet", "dechet"],
            "manque d'occasions": ["occasion", "creer", "créer"],
            "difficulté à défendre": ["defend", "défend", "buts", "encaiss", "transperce", "subit", "dédoubl", "dedoubl"],
            "manque d'intensité": ["intensité", "intensite", "physique", "fatigue", "epuis", "épuis"],
            "erreurs": ["erreur", "faute", "bavure"],
            "isolement": ["isol"]
        }
        for category, keywords in problem_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                problem = category
                break

        # 3. Extraction de la phase de jeu
        phase = None
        phase_keywords = {
            "relance": ["relance", "construction", "sortie de balle", "sortie de press", "ressortir", "build-up", "build up", "relancent", "sortie_balle"],
            "pressing": ["pressing", "contre-press", "gegenpress", "chasser", "harcel", "presser haut"],
            "transition": ["transition", "contre-attaq", "contre", "repli", "contre-defens", "rest defense", "défense préventive"],
            "bloc bas": ["bloc bas", "bloc-bas", "defendre bas", "défendre bas", "entre les lignes", "interlignes"],
            "attaque placée": ["attaque placee", "attaque placée", "possession", "circul"],
            "finition": ["finition", "marquer", "tirer", "centre", "devant le but", "surface"]
        }
        for category, keywords in phase_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                phase = category
                break

        # 4. Extraction du but/goal
        goal = None
        goal_keywords = {
            "améliorer": ["ameliorer", "améliorer", "optimiser", "perfectionner", "developper", "développer"],
            "corriger": ["corriger", "eviter", "éviter", "resoudre", "résoudre", "que faire", "comment faire", "remédier", "remedier", "n’arrive pas", "arrive pas"],
            "préparer": ["preparer", "préparer", "entrainer", "entraîner", "seance", "séance", "exercice"],
            "comprendre": ["comprendre", "expliquer", "c'est quoi", "qu'est-ce que", "analyse", "difference", "différence"],
            "défendre": ["defendre", "défendre", "bloquer", "intercepter", "empecher", "empêcher", "coulisser"],
            "attaquer": ["attaquer", "percer", "passer", "trouver le", "marquer"]
        }
        for category, keywords in goal_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                goal = category
                break

        return {
            "formation": formation,
            "problem": problem,
            "phase": phase,
            "goal": goal
        }
