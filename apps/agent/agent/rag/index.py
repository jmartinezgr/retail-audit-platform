"""Indexa las reglas (estáticas + dinámicas) en Qdrant, un chunk por
regla - ver docs/copilot-spec.md Fase 3 y apps/agent/README.md para por
qué chunk-por-regla en vez de ventanas de tamaño fijo (las descripciones
son cortas y autocontenidas).

Corre offline / bajo demanda, no en cada pregunta del agente:

    python -m agent.rag.index
"""

import uuid

import httpx
from langchain_ollama import OllamaEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from agent.settings import settings

EMBED_DIM = 768  # nomic-embed-text


def _fetch_rules() -> list[dict]:
    """Trae las 18 reglas estáticas + las dinámicas - mismo HTTP al
    backend que usan las demás tools (ver tools.py), no una segunda
    forma de leer datos del backend."""
    static = httpx.get(f"{settings.BACKEND_BASE_URL}/rules/static", timeout=10).json()
    dynamic = httpx.get(f"{settings.BACKEND_BASE_URL}/rules/", timeout=10).json()
    return static + dynamic


def _chunk_text(regla: dict) -> str:
    """Un chunk por regla: nombre + qué valida + severidad + ámbito -
    suficiente contexto para que la búsqueda semántica la encuentre sin
    necesitar el nombre exacto (a diferencia de get_rule)."""
    if "descripcion" in regla:  # estática, de packages/domain/.../catalog.py
        detalle = regla["descripcion"]
    elif regla["tipo"] == "UMBRAL":
        detalle = f"{regla['mensaje']} (condición: {regla['campo']} {regla['operador']} {regla['valor']})"
    else:  # VENTANA_EXCLUSION
        detalle = f"{regla['mensaje']} (sede {regla.get('sede_codigo')}, del {regla.get('fecha_inicio')} al {regla.get('fecha_fin')})"
    return f"{regla['nombre']}: {detalle}. Severity: {regla['severidad']}. Scope: {regla.get('ambito', 'CABECERA')}."


def build_index() -> int:
    """Reconstruye el índice completo - idempotente: el id de cada punto
    es un UUID determinístico derivado del nombre de la regla (Qdrant
    exige id entero o UUID, no un string cualquiera), así reindexar
    actualiza en vez de duplicar."""
    reglas = _fetch_rules()
    embeddings = OllamaEmbeddings(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_EMBED_MODEL)

    textos = [_chunk_text(r) for r in reglas]
    vectores = embeddings.embed_documents(textos)

    client = QdrantClient(url=settings.QDRANT_URL)
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        client.create_collection(
            settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, regla["nombre"])),
            vector=vector,
            payload={"nombre": regla["nombre"], "texto": texto},
        )
        for regla, texto, vector in zip(reglas, textos, vectores)
    ]
    client.upsert(settings.QDRANT_COLLECTION, points=points)
    return len(points)


if __name__ == "__main__":
    n = build_index()
    print(f"Indexed {n} rules into Qdrant collection '{settings.QDRANT_COLLECTION}'.")
