"""Router del copiloto conversacional - expone por HTTP el mismo grafo
LangGraph que ya se usa por CLI y por MCP (apps/agent), para una interfaz
de chat en el frontend. En producción corre contra proveedores gratuitos
hosteados (Groq + Gemini, ver apps/agent/README.md) en vez de responder
503 siempre - por eso lleva un rate limit propio, para no agotar esas
cuotas gratis."""

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request

from src.api.agent.schemas import AgentAskRequest, AgentAskResponse
from src.api.agent.service import AgentUnavailableError, ask

router = APIRouter(prefix="/agent", tags=["agent"])

_RATE_LIMIT = 10  # preguntas por IP por hora
_RATE_WINDOW_SECONDS = 3600

# dict en memoria del proceso, no Redis - funciona porque Render corre
# este servicio con WEB_CONCURRENCY=1 (un solo proceso, confirmado en el
# log real de un deploy) - con más de un worker cada uno tendría su
# propio contador y el límite real efectivo sería N veces más alto. Las
# IPs que ya no preguntan se quedan con una lista vacía para siempre (no
# se podan las claves) - aceptable para el volumen de un demo de
# portafolio, no para tráfico real.
_requests_by_ip: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    # Detrás de un proxy (Render, o cualquier otro) request.client.host
    # es la IP del proxy, no la del visitante - esa va en X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    recent = [t for t in _requests_by_ip[ip] if t > now - _RATE_WINDOW_SECONDS]
    if len(recent) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Too many questions from this IP - limit is {_RATE_LIMIT} per hour. Try again later.",
        )
    recent.append(now)
    _requests_by_ip[ip] = recent


@router.post("/ask", response_model=AgentAskResponse)
def ask_agent(payload: AgentAskRequest, request: Request):
    _check_rate_limit(_client_ip(request))
    # Mismo header que ya manda lib/api.ts en cada request (igual que
    # /uploads/, /rules/, etc.) - sin pasarlo, el copiloto nunca ve los
    # datasets de quien está chateando (ver tools.py:_resolve_dataset_id).
    session_id = request.headers.get("x-client-id")
    try:
        return ask(payload.question, session_id=session_id)
    except AgentUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
