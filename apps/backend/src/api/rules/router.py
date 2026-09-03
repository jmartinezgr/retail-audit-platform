"""
Router de Rules - CRUD de reglas dinámicas configurables desde el
frontend, sin tocar código. Ver domain/rules/dynamic.py para el
evaluador y docs/PLANNING.md §7 / docs/ARCHITECTURE.md para el diseño.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.rules.schemas import (
    AvailableFieldsResponse,
    RuleDefinitionCreate,
    RuleDefinitionResponse,
    RuleDefinitionUpdate,
)
from src.api.rules.service import RuleService, RuleValidationError
from src.infrastructure.db.session import SessionLocal

router = APIRouter(prefix="/rules", tags=["rules"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/fields", response_model=AvailableFieldsResponse)
def get_available_fields(db: Session = Depends(get_db)):
    """Whitelist de campos evaluables por ámbito + categorías/sedes reales
    del catálogo - para poblar los selects del formulario sin
    hardcodearlos en el frontend"""
    return RuleService(db).get_available_fields()


@router.get("/", response_model=list[RuleDefinitionResponse])
def list_rules(db: Session = Depends(get_db)):
    return RuleService(db).list_rules()


@router.post("/", response_model=RuleDefinitionResponse)
def create_rule(payload: RuleDefinitionCreate, db: Session = Depends(get_db)):
    try:
        return RuleService(db).create_rule(payload.model_dump())
    except RuleValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/{rule_id}", response_model=RuleDefinitionResponse)
def update_rule(rule_id: int, payload: RuleDefinitionUpdate, db: Session = Depends(get_db)):
    try:
        return RuleService(db).update_rule(rule_id, payload.model_dump(exclude_unset=True))
    except RuleValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Borra la regla - el próximo 're-run gold' ya no la evalúa"""
    if not RuleService(db).delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return {"deleted": True}
