import sys
from app.services.rag_engine import RAGEngine
from app.services.query_classifier import QueryClassifier
from app.core.config import settings

def run_evaluation():
    engine = RAGEngine(knowledge_base_dir=settings.get_kb_dir(), openai_api_key="mock-key")
    engine.initialize()
    classifier = QueryClassifier()

    tests = [
        # Coach
        ("Comment organiser un pressing haut efficace en 4-3-3 contre une relance à 3 ?", ["pressing_haut.md", "formation_433.md"]),
        ("Comment structurer une séance pour travailler le contre-pressing à la perte ?", ["tactics_transition_regle_6_secondes.md", "pressing_contre_pressing.md"]),
        ("Comment défendre en bloc bas en 4-4-2 face à un milieu en supériorité numérique ?", ["bloc_bas.md", "formation_442.md"]),
        ("Comment maintenir la compacité verticale et horizontale entre la ligne de 4 et le milieu ?", ["tactics_defensive_compacite_bloc.md"]),
        ("Comment limiter l'influence d'un joueur adverse qui décroche entre les lignes (faux 9) ?", ["player_roles_offensive_faux_9.md", "roles_modernes.md"]),
        ("Quels principes appliquer dans la transition défensive immédiate après perte de balle ?", ["tactics_transition_regle_6_secondes.md", "pressing_contre_pressing.md"]),
        ("Comment organiser une contre-attaque rapide en moins de 8 secondes après récupération ?", ["transition_offensive_rapide.md"]),
        ("Comment utiliser le \"tactical foul\" intelligemment sans prendre de cartons inutiles ?", ["tactics_transition_tactical_fouls.md"]),
        ("Quels sont les principes d'animation dans les demi-espaces (half-spaces) ?", ["principe_animation_half_spaces.md"]),
        ("Comment utiliser les passes de troisième homme pour casser une ligne défensive ?", ["tactics_offensive_passe_troisieme_homme.md"]),
        
        # Analyst
        ("Comment intégrer le gardien comme onzième joueur de champ lors de la phase de construction ?", ["player_roles_defensive_sweeper_keeper.md", "sortie_balle.md"]),
        ("Quels sont les avantages tactiques d'un 3-5-2 par rapport à un 4-4-2 à plat ?", ["formation_352.md"]),
        ("Comment utiliser un 3-4-3 pour dominer le milieu de terrain adverse ?", ["formation_343.md"]),
        ("Comment utiliser le 4-1-4-1 pour fermer les espaces intérieurs tout en restant menaçant en contre ?", ["formations_multi_4141_equilibre.md"]),
        ("Comment utiliser un latéral intérieur (inverted fullback) pour stabiliser le milieu ?", ["player_roles_offensive_inverted_fullback.md"]),
        ("Quel est le cahier des charges d'un milieu défensif dans le rôle de sentinelle unique ?", ["player_roles_defensive_sentinelle.md"]),
        ("Comment concevoir un jeu réduit pour travailler le coulissement défensif du bloc médian ?", ["analyse_video_coulissement_bloc.md"]),
        ("Comment calculer le PPDA et quelles sont les limites de cette métrique pour évaluer le pressing ?", ["modern_analysis_ppda_pressing.md"]),
        ("Comment le modèle xG (Expected Goals) réalise son calcul ?", ["modern_analysis_expected_goals_xg.md"]),
        ("Comment mesurer et analyser l'impact du \"rest defense\" d'une équipe ?", ["tactics_defensive_rest_defense.md"]),
        
        # Fan
        ("C'est quoi un \"faux 9\" et pourquoi tout le monde en parle quand on évoque Messi ou Guardiola ?", ["player_roles_offensive_faux_9.md"]),
        ("Pourquoi on parle de \"demi-espace\" ou \"half-space\" ? C'est où sur le terrain ?", ["principe_animation_half_spaces.md"]),
        ("C'est quoi la différence entre un milieu défensif \"sentinelle\" et un milieu \"box-to-box\" ?", ["player_roles_defensive_sentinelle.md"]),
        ("C'est quoi un \"piston\" (wingback) par rapport à un défenseur latéral classique ?", ["player_roles_offensive_piston.md"]),
        ("Quel est le rôle d'un gardien \"libéro\" (sweeper keeper) comme Neuer ?", ["player_roles_defensive_sweeper_keeper.md"]),
        ("Comment joue le Manchester City de Pep Guardiola en 3-2-4-1 ?", ["formations_multi_3241_guardiola.md"]),
        ("C'est quoi le \"Football Total\" de l'Ajax et des Pays-Bas dans les années 1970 ?", ["history_tactics_total_football.md"]),
        ("Comment Arrigo Sacchi a-t-il révolutionné la défense avec son Milan AC à la fin des années 80 ?", ["history_tactics_arrigo_sacchi_milan.md"]),
        ("Pourquoi les gardiens relancent-ils court maintenant au lieu de dégager loin devant ?", ["sortie_balle.md"]),
        ("Pourquoi on dit qu'un ailier joue en \"faux pied\" ou \"inversé\" ?", ["player_roles_offensive_inverted_winger.md"])
    ]

    total_score = 0
    results_report = []

    for i, (q, targets) in enumerate(tests, 1):
        metadata = classifier.classify(q)
        res = engine.search(q, top_k=3, query_metadata=metadata)
        
        matched_source = None
        score = 0.0
        
        if res:
            # Check if any of target files is in the top 3 search results
            for rank, r in enumerate(res):
                if r["source"] in targets:
                    matched_source = r["source"]
                    score = r["score"]
                    # Calculate rank-based points: rank 0 = 10, rank 1 = 8, rank 2 = 6
                    points = 10 - (rank * 2)
                    break
            else:
                points = 0
        else:
            points = 0

        total_score += points
        results_report.append({
            "id": i,
            "query": q,
            "intent": metadata["intent"],
            "top_match": res[0]["source"] if res else "N/A",
            "top_score": res[0]["score"] if res else 0.0,
            "target_matched": matched_source,
            "points": points
        })

    avg_score = total_score / len(tests)
    print(f"EVAL_COMPLETE: AVG_SCORE={avg_score:.2f}/10")
    for r in results_report:
        print(f"{r['id']}. Q: '{r['query']}' | Match: {r['top_match']} ({r['top_score']:.3f}) | Target Matched: {r['target_matched']} | Points: {r['points']}/10")

if __name__ == "__main__":
    run_evaluation()
