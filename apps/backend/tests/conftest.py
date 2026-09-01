import sys
from pathlib import Path

# Sin __init__.py en src/ (namespace packages) - hay que asegurar que
# apps/backend quede en sys.path para que "from src...." funcione sin
# importar cómo/desde dónde se invoque pytest.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
