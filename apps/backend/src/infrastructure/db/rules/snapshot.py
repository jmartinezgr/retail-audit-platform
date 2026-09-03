"""
Convierte RuleDefinitionModel (Postgres) a ReglaDinamica (dataclass de
dominio) - lo que consume domain/rules/dynamic.py, que no sabe nada de
SQLAlchemy. Mismo patrón que infrastructure/db/catalog/snapshot.py: se
lee en vivo cada vez que se llama, sin cachear, y trae TODAS las reglas
(activas e inactivas) - el filtrado por `activa` es responsabilidad del
dominio (domain/rules/dynamic.evaluar_dinamicas), no de infraestructura.
"""

from sqlalchemy.orm import Session

from src.domain.rules.types import AmbitoRegla, Operador, ReglaDinamica, Severidad, TipoReglaDinamica
from src.infrastructure.db.rules.repository import RuleDefinitionRepository


def load_reglas_dinamicas(db: Session) -> list[ReglaDinamica]:
    repo = RuleDefinitionRepository(db)
    return [
        ReglaDinamica(
            id=r.id,
            nombre=r.nombre,
            tipo=TipoReglaDinamica(r.tipo),
            ambito=AmbitoRegla(r.ambito),
            severidad=Severidad(r.severidad),
            activa=r.activa,
            mensaje=r.mensaje,
            campo=r.campo,
            operador=Operador(r.operador) if r.operador else None,
            valor=r.valor,
            filtro_categoria=r.filtro_categoria,
            filtro_sede=r.filtro_sede,
            sede_codigo=r.sede_codigo,
            fecha_inicio=r.fecha_inicio,
            fecha_fin=r.fecha_fin,
        )
        for r in repo.list()
    ]
