# -*- coding: utf-8 -*-
"""
driver.py -- arnes de ejecucion para la skill Registro_Analisis_Financiero.

No reimplementa la logica: importa analisis_financiero.py desde Sistema/ y
expone cuatro comandos:

  status           -> Solo lectura (dry_run=True): que carpetas de proyecto
                      se crearian, que categorias de Centro de Costos caen
                      en "Otros" por no tener mapeo explicito, sin tocar
                      ningun archivo.

  run              -> Ejecucion real: backup, crea carpetas de proyecto
                      nuevas, regenera "Detalle Costos Reales" y las
                      formulas de "Proyectos"/"Indicadores"/"Clientes"/
                      "Glosario KPIs", guarda el Excel, y regenera el
                      visualizador web (ya encadenado dentro de ejecutar()).

  confirmar-cliente -> Sin argumentos: lista clientes pendientes de revision
                      (columna "Cliente" en fuente roja). "--todos" o una
                      lista de TAGs: aplica la sugerencia y recolorea azul
                      marino.

  visualizador     -> Regenera solo el dashboard HTML (Visualizador Web/
                      build/index.html) a partir del Excel actual, sin
                      correr todo run.

Uso:
  python driver.py status
  python driver.py run
  python driver.py confirmar-cliente [--todos|TAG ...]
  python driver.py visualizador
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Sistema"))

sys.dont_write_bytecode = True
import analisis_financiero as af  # noqa: E402


def _extraer_pais(argv):
    """Busca '--pais VALOR' en cualquier posicion de argv y lo separa del
    resto -- devuelve (pais, argv_sin_ese_flag). Default 'CL' si no aparece."""
    argv = list(argv)
    if "--pais" in argv:
        idx = argv.index("--pais")
        pais = argv[idx + 1]
        del argv[idx:idx + 2]
        return pais, argv
    return "CL", argv


def cmd_status(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    cfg = af.PAISES[pais]
    print("=" * 70)
    print(f"  ESTADO ANÁLISIS FINANCIERO - {pais} (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel de trabajo: {cfg['ruta_excel_af']}")
    print(f"  Existe: {cfg['ruta_excel_af'].exists()}")
    print(f"\nExcel Centro de Costos: {cfg['ruta_excel_cc']}")
    print(f"  Existe: {cfg['ruta_excel_cc'].exists()}")

    resumen = af.ejecutar(dry_run=True, pais=pais)

    if resumen["proyectos_nuevos"]:
        print(
            f"\nProyectos nuevos que SE CREARÍAN en 'Proyectos' (TAG + Nombre, "
            f"el resto queda en blanco): {', '.join(resumen['proyectos_nuevos'])}"
        )

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


def cmd_run(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    af.main(pais=pais)
    return 0


def cmd_confirmar_cliente(args: list[str], pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    cfg = af.PAISES[pais]

    if not args:
        pendientes = af.confirmar_clientes_pendientes(None, ruta_excel=cfg["ruta_excel_af"])
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
    aplicados = af.confirmar_clientes_pendientes(objetivo, ruta_excel=cfg["ruta_excel_af"])
    if not aplicados:
        print("\nNo hay clientes pendientes que coincidan con lo pedido.")
    for p in aplicados:
        print(f"  [OK] {p['tag']} -> Cliente '{p['cliente_sugerido']}' confirmado (azul marino).")
    return 0


def cmd_visualizador(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raiz_viz = af.PAISES[pais]["raiz_visualizador_web"]
    ruta_build_script = raiz_viz / "build_visualizador.py"
    if not ruta_build_script.exists():
        print(f"[INFO] Visualizador Web de {pais} aún no implementado -- nada que regenerar.")
        return 0
    ya_en_path = str(raiz_viz) in sys.path
    if not ya_en_path:
        sys.path.insert(0, str(raiz_viz))
    sys.dont_write_bytecode = True
    sys.modules.pop("build_visualizador", None)
    import build_visualizador as bv
    return bv.build()


def main() -> int:
    comandos = ("status", "run", "confirmar-cliente", "visualizador")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar-cliente [--todos|TAG ...]|visualizador] [--pais CL|PE]")
        return 2
    comando = sys.argv[1]
    pais, resto = _extraer_pais(sys.argv[2:])
    if comando == "status":
        return cmd_status(pais=pais)
    if comando == "confirmar-cliente":
        return cmd_confirmar_cliente(resto, pais=pais)
    if comando == "visualizador":
        return cmd_visualizador(pais=pais)
    return cmd_run(pais=pais)


if __name__ == "__main__":
    raise SystemExit(main())
