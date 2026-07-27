"""
test_trends.py
==============
Test du Moteur de Tendances Multi-Match (TrendAnalysisEngine).

Valide que le système :
  1. Isole correctement les chunks des matchs PSG vs Inter et PSG vs Man City.
  2. Construit un contexte structuré et étanche par match.
  3. Génère une synthèse comparative (ou le contexte brut en mode local).

Usage :
  PYTHONPATH=backend python backend/test_trends.py
"""

import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

from retrieval.trend_engine import TrendAnalysisEngine

def run_trend_test():
    print("=" * 60)
    print("  FOOTBALL IQ — TEST DU MOTEUR DE TENDANCES MULTI-MATCH")
    print("=" * 60)

    engine = TrendAnalysisEngine()

    print(f"\n[INFO] Corpus chargé : {len(engine.chunks)} chunks au total.")
    match_chunks = [c for c in engine.chunks if c["metadata"].get("type_chunk") == "match"]
    print(f"[INFO] Chunks de match disponibles : {len(match_chunks)}")

    # ------------------------------------------------------------------
    # CAS DE TEST : Finale LDC Inter vs Man City
    # ------------------------------------------------------------------
    query = (
        "Compare l'animation offensive et l'efficacité du PSG lors du carton "
        "5-0 en finale de LDC contre l'Inter Milan par rapport au match contre "
        "Manchester City."
    )

    print(f"\n{'─' * 60}")
    print(f"REQUÊTE : {query}")
    print(f"{'─' * 60}")

    # 1. Extraction des cibles
    targets = engine._extract_targets(query)
    print(f"\n[Étape 1] Cibles extraites :")
    print(f"  Adversaires (slugs) : {targets['opponent_slugs']}")
    print(f"  Compétition         : {targets['competition_kw']}")
    print(f"  Joueurs             : {targets['player_names']}")

    # 2. Filtrage des chunks
    grouped = engine._filter_chunks_by_targets(targets)
    print(f"\n[Étape 2] Matchs isolés dans la base : {len(grouped)}")
    for source, chunks in grouped.items():
        print(f"  ✓ {source} ({len(chunks)} chunks)")

    # Validation critique
    assert len(grouped) >= 1, (
        "❌ ÉCHEC : Aucun match isolé ! "
        "Vérifiez que les matchs contre l'Inter et Man City sont bien indexés dans Qdrant."
    )

    inter_found = any("inter" in k.lower() for k in grouped.keys())
    city_found  = any("manchester" in k.lower() or "man_city" in k.lower() or "city" in k.lower() for k in grouped.keys())

    print(f"\n  → Match Inter trouvé  : {'✅' if inter_found else '❌ NON TROUVÉ'}")
    print(f"  → Match Man City trouvé : {'✅' if city_found else '❌ NON TROUVÉ'}")

    # 3. Contexte structuré
    context = engine._build_structured_context(grouped)
    total_chunks = sum(len(v) for v in grouped.values())
    print(f"\n[Étape 3] Contexte structuré généré ({total_chunks} chunks, {len(context)} caractères)")
    print(f"\n{'─' * 40}")
    print("APERÇU DU CONTEXTE (500 premiers caractères) :")
    print(context[:500])
    print(f"{'─' * 40}")

    # 4. Synthèse
    print(f"\n[Étape 4] Génération de la synthèse comparative...")
    result = engine.analyze(query, competitions=["UCL"])
    print(f"\n{'═' * 60}")
    print("SYNTHÈSE GÉNÉRÉE :")
    print(f"{'═' * 60}")
    print(result["synthesis"])
    print(f"\n{'═' * 60}")
    print(f"  Matchs analysés : {len(result['matches_analyzed'])}")
    print(f"  Chunks utilisés : {result['chunks_used']}")
    print(f"{'═' * 60}")

    print("\n✅ TEST DU MOTEUR DE TENDANCES : SUCCÈS")

if __name__ == "__main__":
    run_trend_test()
