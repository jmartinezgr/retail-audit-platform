"""Contexto ambiental por request - no inyección de dependencias clásica
(eso sería un parámetro explícito en la firma de la función), porque la
firma de una tool la define el modelo vía su tool-call JSON, no nosotros
- no podemos agregarle un parámetro `session_id` a `_resolve_dataset_id`
sin volverlo algo que el LLM tendría que acordarse de pasar siempre,
rompiendo el principio de que la tool hace la plomería determinística
sin depender de que el modelo haga lo correcto (ver tools.py).

Mismo patrón que usan SDKs como Sentry/OpenTelemetry para propagar el id
de una request a través de código que no lo recibe como parámetro -
`contextvars.ContextVar`, no un global ni un thread-local a mano: cada
hilo (incluido el threadpool de Starlette, que copia el contexto al
despachar un `def` síncrono - ver apps/backend/src/api/agent/service.py)
recibe su propia copia, así que dos preguntas de dos sesiones distintas
corriendo "al mismo tiempo" no se pisan."""

from contextvars import ContextVar

session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
