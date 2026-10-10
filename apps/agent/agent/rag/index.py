"""Indexa las reglas (estáticas + dinámicas) en Qdrant, un chunk por
regla y por idioma - ver docs/copilot-spec.md Fase 3 y
apps/agent/README.md para por qué chunk-por-regla en vez de ventanas de
tamaño fijo, y por qué también en inglés para las estáticas.

Corre offline / bajo demanda, no en cada pregunta del agente:

    python -m agent.rag.index
"""

import uuid

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from agent.rag.embeddings import embed_documents
from agent.settings import settings


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


def build_index(client: QdrantClient | None = None) -> int:
    """Reconstruye el índice completo - idempotente: el id de cada punto
    es un UUID determinístico derivado de (nombre, idioma) (Qdrant exige
    id entero o UUID, no un string cualquiera), así reindexar actualiza
    en vez de duplicar.

    `client`: si se pasa (ver agent/rag/retrieve.py, reconstrucción
    perezosa en producción), reusa ESE objeto en vez de crear uno nuevo
    - crítico en modo ":memory:" (QDRANT_URL=":memory:"), donde cada
    `QdrantClient(":memory:")` nuevo es una base en RAM totalmente
    aislada de cualquier otra instancia, aunque apunten al mismo
    string - confirmado en vivo, no asumido. Sin esto, indexar con un
    cliente y buscar con otro encontraría una colección vacía."""
    if client is None:
        # `location`, no `url` - `url` fuerza el parseo de URL remota y
        # revienta con ":memory:" (no es una URL válida); `location` es
        # el que detecta ":memory:"/una ruta/una URL real y elige el
        # modo correcto, verificado en vivo antes de escribir esto.
        client = QdrantClient(location=settings.QDRANT_URL)

    reglas = _fetch_rules()
    chunks = [(regla["nombre"], idioma, texto) for regla in reglas for idioma, texto in _chunks_for_rule(regla)]
    ids = [str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{nombre}:{idioma}")) for nombre, idioma, _ in chunks]

    textos = [texto for _, _, texto in chunks]
    vectores = embed_documents(textos)

    if not client.collection_exists(settings.QDRANT_COLLECTION):
        client.create_collection(
            settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=settings.EMBED_DIM, distance=Distance.COSINE),
        )
    else:
        # limpia chunks de reglas dinámicas borradas desde la última vez
        # que se indexó - upsert nunca borra, así que sin esto un chunk
        # huérfano seguiría apareciendo en las búsquedas para siempre.
        existing_ids = {str(p.id) for p in client.scroll(settings.QDRANT_COLLECTION, limit=10_000, with_payload=False)[0]}
        stale_ids = existing_ids - set(ids)
        if stale_ids:
            client.delete(settings.QDRANT_COLLECTION, points_selector=list(stale_ids))

    points = [
        PointStruct(id=point_id, vector=vector, payload={"nombre": nombre, "texto": texto, "idioma": idioma})
        for point_id, (nombre, idioma, texto), vector in zip(ids, chunks, vectores)
    ]
    client.upsert(settings.QDRANT_COLLECTION, points=points)
    return len(points)


if __name__ == "__main__":
    n = build_index()
    print(f"Indexed {n} chunks into Qdrant collection '{settings.QDRANT_COLLECTION}'.")
