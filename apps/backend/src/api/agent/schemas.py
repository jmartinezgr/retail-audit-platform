from pydantic import BaseModel


class AgentAskRequest(BaseModel):
    question: str


class ToolCallTrace(BaseModel):
    """Una llamada a tool durante el run - solo para mostrar en la UI el
    razonamiento del agente (qué tool, con qué argumentos, qué devolvió),
    no es parte de la respuesta en sí."""

    name: str
    args: dict
    result: str


class AgentAskResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallTrace]
