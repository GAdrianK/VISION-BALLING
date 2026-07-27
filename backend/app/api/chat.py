from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.core.config import settings

router = APIRouter()

@router.post("/api/chat", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest):
    """
    Route principale du chat conversationnel.
    Prend une requête utilisateur, interroge le RAG local et génère une réponse
    selon le profil tactique demandé (coach, analyste ou fan).
    """
    # Import dynamique pour éviter les dépendances circulaires avec app.main
    from app.main import rag_engine
    
    try:
        chat_service = ChatService(
            rag_engine=rag_engine,
            openai_api_key=settings.OPENAI_API_KEY,
            gemini_api_key=settings.gemini_key
        )
        response = chat_service.generate_response(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur interne du chat service : {str(e)}")
