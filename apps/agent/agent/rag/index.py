"""Indexa las reglas (estáticas + dinámicas) en Qdrant, un chunk por
regla y por idioma - ver docs/copilot-spec.md Fase 3 y
apps/agent/README.md para por qué chunk-por-regla en vez de ventanas de
tamaño fijo, y por qué también en inglés para las estáticas.

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


def _chunks_for_rule(regla: dict) -> list[tuple[str, str]]:
    """Devuelve [(idioma, texto)] para una regla.

    Una regla estática produce DOS chunks (es/en) - `descripcion_en` en
    catalog.py es texto real ya escrito para el landing page del
    frontend, no algo inventado acá para este índice (ver el propio
    catalog.py). Una regla dinámica produce solo uno (es) - lo que
    escribió el usuario al crearla no tiene traducción real en ningún
    lado, no se fabrica una.
    """
    if "descripcion" in regla:  # estática
        sufijo = f"Severity: {regla['severidad']}. Scope: {regla['ambito']}."
        return [
            ("es", f"{regla['nombre']}: {regla['descripcion']}. {sufijo}"),
            ("en", f"{regla['nombre']}: {regla['descripcion_en']}. {sufijo}"),
        ]

    if regla["tipo"] == "UMBRAL":
        detalle = f"{regla['mensaje']} (condición: {regla['campo']} {regla['operador']} {regla['valor']})"
    else:  # VENTANA_EXCLUSION
        detalle = f"{regla['mensaje']} (sede {regla.get('sede_codigo')}, del {regla.get('fecha_inicio')} al {regla.get('fecha_fin')})"
    texto = f"{regla['nombre']}: {detalle}. Severity: {regla['severidad']}. Scope: {regla.get('ambito', 'CABECERA')}."
    return [("es", texto)]


def build_index() -> int:
    """Reconstruye el índice completo - idempotente: el id de cada punto
    es un UUID determinístico derivado de (nombre, idioma) (Qdrant exige
    id entero o UUID, no un string cualquiera), así reindexar actualiza
    en vez de duplicar."""
    reglas = _fetch_rules()
    chunks = [(regla["nombre"], idioma, texto) for regla in reglas for idioma, texto in _chunks_for_rule(regla)]

    embeddings = OllamaEmbeddings(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_EMBED_MODEL)
    textos = [texto for _, _, texto in chunks]
    vectores = embeddings.embed_documents(textos)

    client = QdrantClient(url=settings.QDRANT_URL)
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        client.create_collection(
            settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{nombre}:{idioma}")),
            vector=vector,
            payload={"nombre": nombre, "texto": texto, "idioma": idioma},
        )
        for (nombre, idioma, texto), vector in zip(chunks, vectores)
    ]
    client.upsert(settings.QDRANT_COLLECTION, points=points)
    return len(points)


if __name__ == "__main__":
    n = build_index()
    print(f"Indexed {n} chunks into Qdrant collection '{settings.QDRANT_COLLECTION}'.")
