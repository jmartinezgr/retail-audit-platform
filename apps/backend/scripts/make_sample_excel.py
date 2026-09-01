"""
Genera un Excel de ventas de muestra (pocas filas, códigos reales del
catálogo sembrado) - solo para probar el pipeline manualmente. No es el
generador sintético de la fase 5 (ese va a inyectar errores a propósito).

Uso (desde apps/backend, con el venv activo):
    python scripts/make_sample_excel.py [ruta_salida.xlsx]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import polars as pl

FILAS = [
    {
        "numero_factura": "FAC-0001",
        "fecha": "2026-08-15",
        "sede_codigo": "TDA-001",
        "trabajador_codigo": "EMP-0001",
        "producto_sku": "ELEC-0001",
        "cantidad": 2,
        "precio_unitario": 180000,
        "codigo_descuento": "",
        "total": 360000,
        "metodo_pago": "TARJETA",
    },
    {
        "numero_factura": "FAC-0002",
        "fecha": "2026-08-16",
        "sede_codigo": "TDA-003",
        "trabajador_codigo": "EMP-0007",
        "producto_sku": "ROPA-0003",
        "cantidad": 1,
        "precio_unitario": 190000,
        "codigo_descuento": "MEDELLIN_VIP",
        "total": 167200,
        "metodo_pago": "EFECTIVO",
    },
    {
        "numero_factura": "FAC-0003",
        "fecha": "2026-08-17",
        "sede_codigo": "TDA-005",
        "trabajador_codigo": "EMP-0004",
        "producto_sku": "BELL-0003",
        "cantidad": 3,
        "precio_unitario": 190000,
        "codigo_descuento": "",
        "total": 570000,
        "metodo_pago": "TARJETA",
    },
]


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "ventas_muestra.xlsx"
    df = pl.DataFrame(FILAS)
    df.write_excel(out_path)
    print(f"Escrito {out_path} ({df.height} filas)")


if __name__ == "__main__":
    main()
