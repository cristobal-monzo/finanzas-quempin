import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent.parent
        / ".claude" / "skills" / "Reportes_Analisis_Financiero"),
)
