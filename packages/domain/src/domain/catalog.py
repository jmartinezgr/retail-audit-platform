from enum import Enum


class TipoDescuento(str, Enum):
    PORCENTAJE = "PORCENTAJE"
    VALOR_FIJO = "VALOR_FIJO"


class Categoria(str, Enum):
    ELECTRONICA = "ELECTRONICA"
    ROPA = "ROPA"
    HOGAR = "HOGAR"
    ALIMENTOS = "ALIMENTOS"
    JUGUETERIA = "JUGUETERIA"
    DEPORTES = "DEPORTES"
    BELLEZA = "BELLEZA"
