"""
Inspecciona una tabla Delta del bucket - lectura rápida para depurar
manualmente sin pasar por la API.

Uso (desde apps/backend, con el venv activo):
    python scripts/inspect_delta.py jobs/<upload_id>/bronze
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.infrastructure.storage import lake


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python scripts/inspect_delta.py <object_key>")
        print("Ejemplo: python scripts/inspect_delta.py jobs/<upload_id>/bronze")
        sys.exit(1)

    object_key = sys.argv[1]
    df = lake.read_delta(object_key)

    print(f"Tabla: {object_key}")
    print(f"Filas: {df.height}")
    print(f"Columnas: {df.columns}")
    print(df)


if __name__ == "__main__":
    main()
