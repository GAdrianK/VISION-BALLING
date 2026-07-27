import pytest
from app.services.rag_engine import RAGEngine
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest, ChatMode
from app.core.config import settings

@pytest.fixture
def rag_engine(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "mock-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "mock-key")
    engine = RAGEngine(
        knowledge_base_dir=settings.get_kb_dir(),
        openai_api_key="mock-key"
    )
    engine.initialize()
    return engine

def test_chat_service_initialization(rag_engine):
    service = ChatService(rag_engine=rag_engine, openai_api_key="mock-key")
    # Vérifier que les 3 prompts ont bien été chargés
    assert ChatMode.COACH in service.prompts
    assert ChatMode.ANALYST in service.prompts
    assert ChatMode.FAN in service.prompts
    assert len(service.prompts[ChatMode.COACH]) > 0

def test_chat_service_generate_mock_response(rag_engine):
    service = ChatService(rag_engine=rag_engine, openai_api_key="mock-key")
    
    # Test en mode coach
    req_coach = ChatRequest(message="Comment bloquer une relance basse ?", mode=ChatMode.COACH)
    resp_coach = service.generate_response(req_coach)
    
    assert resp_coach.mode == ChatMode.COACH
    assert "Analyse du Coach" in resp_coach.answer
    assert len(resp_coach.sources) > 0
    
    # Test en mode analyste
    req_analyst = ChatRequest(message="Quels sont les rôles tactiques du double pivot ?", mode=ChatMode.ANALYST)
    resp_analyst = service.generate_response(req_analyst)
    
    assert resp_analyst.mode == ChatMode.ANALYST
    assert "Observations Structurelles" in resp_analyst.answer
    
    # Test en mode fan
    req_fan = ChatRequest(message="Le pressing haut c'est quoi ?", mode=ChatMode.FAN)
    resp_fan = service.generate_response(req_fan)
    
    assert resp_fan.mode == ChatMode.FAN
    assert "L'Avis des Fans" in resp_fan.answer

def test_chat_service_mock_specific_requirements(rag_engine):
    service = ChatService(rag_engine=rag_engine, openai_api_key="mock-key")
    
    # 1. Test Mode Fan + Faux 9
    req_fan_f9 = ChatRequest(message="Explique-moi simplement ce qu'est un faux 9", mode=ChatMode.FAN)
    resp_fan_f9 = service.generate_response(req_fan_f9)
    answer_fan_f9 = resp_fan_f9.answer.lower()
    
    # Doit contenir les idées clés du Faux 9
    assert any(w in answer_fan_f9 for w in ["attaquant axial", "décroche", "milieu de terrain", "espace"])
    
    # Ne doit PAS contenir les mots bannis
    for forbidden in ["numéro 6", "guerrier", "pressing", "virage", "tribune"]:
        assert forbidden not in answer_fan_f9

    # 2. Test Mode Coach + Pressing Haut (doit s'ancrer dans pressing_contre_pressing.md)
    req_coach_pressing = ChatRequest(message="Prépare une séance pour améliorer le pressing haut", mode=ChatMode.COACH)
    resp_coach_pressing = service.generate_response(req_coach_pressing)
    answer_coach_pressing = resp_coach_pressing.answer
    
    assert "Analyse du Coach" in answer_coach_pressing
    assert any(src in answer_coach_pressing for src in ["pressing_contre_pressing.md", "analyse_video_pressing_haut.md", "transition_pressing_perte.md", "pressing_haut.md"])
    
    # 3. Test Question hors base (pizza)
    req_pizza = ChatRequest(message="Quelle est la meilleure recette de pizza ?", mode=ChatMode.COACH)
    resp_pizza = service.generate_response(req_pizza)
    
    assert resp_pizza.answer == "Je n’ai pas assez d’informations dans la base actuelle pour répondre précisément."

