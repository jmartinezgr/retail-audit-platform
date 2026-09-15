"""Router del copiloto conversacional - expone por HTTP el mismo grafo
LangGraph que ya se usa por CLI y por MCP (apps/agent), para una interfaz
de chat en el frontend. Demo local únicamente: en producción (Render) no
hay Ollama ni Qdrant corriendo, así que este endpoint responde 503 ahí -
ver apps/agent/README.md y el README raíz."""

from fastapi import APIRouter, HTTPException

from src.api.agent.schemas import AgentAskRequest, AgentAskResponse
from src.api.agent.service import AgentUnavailableError, ask

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/ask", response_model=AgentAskResponse)
def ask_agent(payload: AgentAskRequest):
    try:
        return ask(payload.question)
    except AgentUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
