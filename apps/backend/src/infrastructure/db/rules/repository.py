"""
Repositorio de reglas dinámicas - solo acceso a datos. Primer
repositorio de este proyecto con create/update/delete (CatalogRepository
solo tiene list_*), mismo estilo delgado: constructor toma una Session,
cada método es una operación mínima sobre RuleDefinitionModel.
"""

from sqlalchemy.orm import Session

from src.infrastructure.db.rules.models import RuleDefinitionModel


class RuleDefinitionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[RuleDefinitionModel]:
        return self.db.query(RuleDefinitionModel).order_by(RuleDefinitionModel.created_at).all()

    def get(self, rule_id: int) -> RuleDefinitionModel | None:
        return self.db.get(RuleDefinitionModel, rule_id)

    def get_by_nombre(self, nombre: str) -> RuleDefinitionModel | None:
        return self.db.query(RuleDefinitionModel).filter(RuleDefinitionModel.nombre == nombre).first()

    def create(self, data: dict) -> RuleDefinitionModel:
        rule = RuleDefinitionModel(**data)
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def update(self, rule_id: int, data: dict) -> RuleDefinitionModel | None:
        rule = self.get(rule_id)
        if rule is None:
            return None
        for key, value in data.items():
            setattr(rule, key, value)
        self.db.commit()
        self.db.refresh(rule)
        return rule

    def delete(self, rule_id: int) -> bool:
        rule = self.get(rule_id)
        if rule is None:
            return False
        self.db.delete(rule)
        self.db.commit()
        return True
