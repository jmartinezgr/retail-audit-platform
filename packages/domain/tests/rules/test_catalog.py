from domain.rules.catalog import CATALOGO_REGLAS_ESTATICAS
from domain.rules.engine import NOMBRES_REGLAS_ESTATICAS


def test_catalogo_cubre_las_18_reglas_estaticas():
    assert set(CATALOGO_REGLAS_ESTATICAS) == NOMBRES_REGLAS_ESTATICAS


def test_cada_entrada_tiene_descripcion_no_vacia():
    for descripcion in CATALOGO_REGLAS_ESTATICAS.values():
        assert descripcion.descripcion.strip()
