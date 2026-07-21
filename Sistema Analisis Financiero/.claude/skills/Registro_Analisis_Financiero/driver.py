# -*- coding: utf-8 -*-
"""
driver.py -- arnes de ejecucion para la skill Registro_Analisis_Financiero.

No reimplementa la logica: importa analisis_financiero.py desde Sistema/ y
expone dos comandos:

  status -> Solo lectura (dry_run=True): que carpetas de proyecto se
            crearian, que categorias de Centro de Costos caen en "Otros"
            por no tener mapeo explicito, sin tocar ningun archivo.

  run    -> Ejecucion real: backup, crea carpetas de proyecto nuevas,
            regenera "Detalle Costos Reales" y las formulas de "Proyectos"/
            "Indicadores", guarda el Excel.

Uso:
  python driver.py status
  python driver.py run
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Sistema"))

sys.dont_write_bytecode = True
import analisis_financiero as af  # noqa: E402


def cmd_status() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    print("=" * 70)
    print("  ESTADO ANÁLISIS FINANCIERO (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel de trabajo: {af.RUTA_EXCEL}")
    print(f"  Existe: {af.RUTA_EXCEL.exists()}")
    print(f"\nCentro de Costos.xlsx: {af.RUTA_EXCEL_CENTRO_COSTOS}")
    print(f"  Existe: {af.RUTA_EXCEL_CENTRO_COSTOS.exists()}")

    resumen = af.ejecutar(dry_run=True)

    if resumen["carpetas_creadas"]:
        print(f"\nCarpetas de proyecto que SE CREARÍAN: {', '.join(resumen['carpetas_creadas'])}")
    else:
        print("\nNo hay carpetas de proyecto nuevas por crear.")

    if resumen["categorias_no_mapeadas"]:
        print(
            "\nCategorías de Centro de Costos sin mapeo explícito (caerían en 'Otros'): "
            + ", ".join(resumen["categorias_no_mapeadas"])
        )

    if resumen["avisos"]:
        print("\nAvisos:")
        for aviso in resumen["avisos"]:
            print(f"  [AVISO] {aviso}")

    print("\n" + "=" * 70)
    print("  Nada fue escrito. Para ejecutar de verdad: python driver.py run")
    print("=" * 70)
    return 0


def cmd_run() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    af.main()
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("status", "run"):
        print("Uso: python driver.py [status|run]")
        return 2
    if sys.argv[1] == "status":
        return cmd_status()
    return cmd_run()


if __name__ == "__main__":
    raise SystemExit(main())
