# -*- coding: utf-8 -*-
"""
driver.py -- arnes de ejecucion para la skill Registro_Analisis_Financiero.

No reimplementa la logica: importa analisis_financiero.py desde Sistema/ y
expone tres comandos:

  status           -> Solo lectura (dry_run=True): que carpetas de proyecto
                      se crearian, que categorias de Centro de Costos caen
                      en "Otros" por no tener mapeo explicito, sin tocar
                      ningun archivo.

  run              -> Ejecucion real: backup, crea carpetas de proyecto
                      nuevas, regenera "Detalle Costos Reales" y las
                      formulas de "Proyectos"/"Indicadores"/"Clientes"/
                      "Glosario KPIs", guarda el Excel.

  confirmar-cliente -> Sin argumentos: lista clientes pendientes de revision
                      (columna "Cliente" en fuente roja). "--todos" o una
                      lista de TAGs: aplica la sugerencia y recolorea azul
                      marino.

Uso:
  python driver.py status
  python driver.py run
  python driver.py confirmar-cliente [--todos|TAG ...]
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


def cmd_confirmar_cliente(args: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    if not args:
        pendientes = af.confirmar_clientes_pendientes(None)
        print(f"\nClientes pendientes de confirmar: {len(pendientes)}")
        for p in pendientes:
            print(
                f"  - {p['tag']}: '{p['nombre_proyecto']}' -> sugerido "
                f"'{p['cliente_sugerido']}' (similitud {p['similitud']})"
            )
        if pendientes:
            print(
                "\nPara aplicar: python driver.py confirmar-cliente --todos"
                " (o 'python driver.py confirmar-cliente <TAG> ...' para solo algunos)"
            )
        return 0

    objetivo = "TODOS" if args == ["--todos"] else args
    aplicados = af.confirmar_clientes_pendientes(objetivo)
    if not aplicados:
        print("\nNo hay clientes pendientes que coincidan con lo pedido.")
    for p in aplicados:
        print(f"  [OK] {p['tag']} -> Cliente '{p['cliente_sugerido']}' confirmado (azul marino).")
    return 0


def main() -> int:
    comandos = ("status", "run", "confirmar-cliente")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar-cliente [--todos|TAG ...]]")
        return 2
    if sys.argv[1] == "status":
        return cmd_status()
    if sys.argv[1] == "confirmar-cliente":
        return cmd_confirmar_cliente(sys.argv[2:])
    return cmd_run()


if __name__ == "__main__":
    raise SystemExit(main())
