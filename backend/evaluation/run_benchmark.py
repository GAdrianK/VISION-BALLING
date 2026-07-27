import sys
from pathlib import Path
import json

# Ajout du dossier backend au sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from openai import OpenAI
from retrieval.hybrid_engine import HybridSearchEngine
from retrieval.reranker import TacticalReranker
from database.indexer import run_indexing
from database.vector_store import VectorStoreManager
from app.core.config import settings

# Échantillon de questions de test réalistes
BENCHMARK_QUESTIONS = [
    {
        "id": 1,
        "role": "Coach",
        "question": "Comment animer les couloirs avec un ailier inversé dans un système en 4-3-3 ?"
    },
    {
        "id": 2,
        "role": "Analyste",
        "question": "Quelles sont les différences clés de positionnement entre un latéral inversé et un ailier classique ?"
    },
    {
        "id": 3,
        "role": "Fan",
        "question": "Pourquoi dit-on que le faux 9 aide à dominer le milieu de terrain ?"
    }
]

def get_rag_answer(query: str, hybrid_engine, reranker) -> tuple:
    """Récupère le contexte et génère la réponse RAG."""
    raw_results = hybrid_engine.search(query, top_k=10)
    top_results = reranker.rerank_and_resolve(query, raw_results, top_k=3)
    
    # Construction du contexte
    contexts = []
    sources = []
    for res in top_results:
        parent_content = res.get("parent_context", {}).get("content", "")
        parent_source = res.get("parent_context", {}).get("source", "")
        if parent_content and parent_content not in contexts:
            contexts.append(parent_content)
        sources.append(parent_source)
        
    context_text = "\n\n---\n\n".join(contexts) if contexts else "Aucun contexte trouvé."
    
    # Appel LLM pour obtenir la réponse
    api_key = settings.OPENAI_API_KEY
    if not api_key or api_key.startswith("mock-"):
        # Réponse simulée offline
        simulated_answer = (
            "L'ailier inversé repique vers l'intérieur sur son pied opposé pour libérer le couloir latéral. "
            "Le faux 9 décroche pour créer un surnombre au milieu, aspirant un défenseur central hors de sa ligne."
        )
        return simulated_answer, context_text, list(set(sources))
        
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system", 
                "content": f"Tu es un assistant tactique de football. Réponds à la question en te basant sur ce contexte :\n\n{context_text}"
            },
            {"role": "user", "content": query}
        ],
        temperature=0.0
    )
    return response.choices[0].message.content, context_text, list(set(sources))

def evaluate_metrics(question: str, answer: str, context: str) -> dict:
    """Calcule la Faithfulness et l'Answer Relevance via LLM-as-a-judge."""
    api_key = settings.OPENAI_API_KEY
    if not api_key or api_key.startswith("mock-"):
        # Scores simulés offline
        return {
            "faithfulness": {"score": 9.0, "reason": "Toutes les affirmations figurent dans le contexte de simulation."},
            "relevance": {"score": 8.5, "reason": "La réponse cible précisément le faux 9 et l'ailier inversé."}
        }
        
    client = OpenAI(api_key=api_key)
    
    # Prompt de jugement
    prompt = f"""
    Tu es un évaluur d'IA RAG spécialisé dans le football. Évalue la réponse générée selon deux critères principaux sur une échelle de 0 à 10.
    
    ---
    CONTEXTE :
    {context}
    
    ---
    QUESTION :
    {question}
    
    ---
    RÉPONSE :
    {answer}
    
    ---
    Fournis ton évaluation sous forme de JSON strict respectant exactement ce format :
    {{
        "faithfulness": {{
            "score": <float entre 0 et 10>,
            "reason": "<explication concise en français>"
        }},
        "relevance": {{
            "score": <float entre 0 et 10>,
            "reason": "<explication concise en français>"
        }}
    }}
    
    Définitions :
    - Faithfulness (Fidélité au contexte) : La réponse contient-elle des faits inventés ou absents du contexte ? (10 = aucun fait inventé, 0 = pure invention).
    - Answer Relevance (Pertinence de la réponse) : La réponse répond-elle directement et de façon tactiquement pertinente à la question posée ?
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erreur d'évaluation pour la question : {e}")
        return {
            "faithfulness": {"score": 0.0, "reason": "Erreur d'appel API d'évaluation."},
            "relevance": {"score": 0.0, "reason": "Erreur d'appel API d'évaluation."}
        }

def run_evaluation_benchmark():
    print("==================================================")
    print("      BENCHMARK DE PERFORMANCE TACTIQUE RAG       ")
    print("==================================================")
    
    # Indexation automatique si base vide
    v_store = VectorStoreManager()
    should_index = False
    if settings.QDRANT_URL == ":memory:":
        should_index = True
    else:
        try:
            info = v_store.client.get_collection(v_store.collection_name)
            if info.points_count == 0:
                should_index = True
        except Exception:
            should_index = True
            
    if should_index:
        print("Collection Qdrant vide ou en mémoire. Indexation des données brutes...")
        run_indexing()
        print("\nIndexation terminée.\n")
        
    hybrid_engine = HybridSearchEngine()
    reranker = TacticalReranker()
    
    total_faithfulness = 0.0
    total_relevance = 0.0
    results = []
    
    for idx, q_info in enumerate(BENCHMARK_QUESTIONS):
        print(f"\n[{idx+1}/{len(BENCHMARK_QUESTIONS)}] Évaluation pour : {q_info['question']}")
        
        # 1. Génération
        answer, context, sources = get_rag_answer(q_info["question"], hybrid_engine, reranker)
        
        # 2. Évaluation
        metrics = evaluate_metrics(q_info["question"], answer, context)
        
        f_score = metrics["faithfulness"]["score"]
        r_score = metrics["relevance"]["score"]
        
        total_faithfulness += f_score
        total_relevance += r_score
        
        print(f"   -> Faithfulness      : {f_score}/10 (Raison: {metrics['faithfulness']['reason']})")
        print(f"   -> Answer Relevance  : {r_score}/10 (Raison: {metrics['relevance']['reason']})")
        
        results.append({
            "question": q_info["question"],
            "answer": answer,
            "sources": sources,
            "metrics": metrics
        })
        
    avg_f = total_faithfulness / len(BENCHMARK_QUESTIONS)
    avg_r = total_relevance / len(BENCHMARK_QUESTIONS)
    
    print("\n==================================================")
    print("              RÉSULTATS SYNTHÉTIQUES              ")
    print("==================================================")
    print(f"Score Moyen de Fidélité (Faithfulness) : {avg_f:.2f}/10")
    print(f"Score Moyen de Pertinence (Relevance)  : {avg_r:.2f}/10")
    print("==================================================")
    
    # Sauvegarde du rapport d'évaluation localement
    output_path = Path(__file__).resolve().parent / "benchmark_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "average_faithfulness": avg_f,
            "average_relevance": avg_r,
            "details": results
        }, f, indent=4, ensure_ascii=False)
    print(f"Rapport sauvegardé sous : {output_path}")

if __name__ == "__main__":
    run_evaluation_benchmark()
