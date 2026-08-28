import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent.parent
        / ".claude" / "skills" / "Reportes_Analisis_Financiero"),
)
# Algunos tests de esta suite importan 'analisis_financiero' directamente
# (ej. para comparar contra af.calcular_nota_parcial). No deben depender de
# que 'datos_reportes'/'kpis_recalculados' lo pongan en el sys.path de
# rebote como efecto colateral de su propio import -- ese acoplamiento de
# orden entre imports hermanos es frágil (un reordenamiento alfabético lo
# rompe con ModuleNotFoundError).
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent.parent / "Sistema"),
)
