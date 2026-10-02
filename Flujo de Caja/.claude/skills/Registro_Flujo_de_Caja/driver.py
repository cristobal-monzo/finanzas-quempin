# -*- coding: utf-8 -*-
"""
driver.py -- Flujo de Caja (plan de integración 2026-09-30, fase 4).

El flujo se arma entero desde lo que ya producen las demás herramientas
(ver Flujo de Caja/CLAUDE.md): no hay nada que registrar a mano salvo el
saldo de caja, en Sistema/parametros_flujo_caja.json.

  status                    -> calcula y muestra el resumen mes a mes; no escribe nada.
  run                       -> escribe Excel/Flujo de Caja.xlsx y regenera el tablero.
  visualizador              -> solo regenera el tablero (build/index.html).
  saldo <monto> [AAAA-MM-DD] -> fija el saldo de caja inicial (estimación a mano) en
                               Sistema/parametros_flujo_caja.json; la fecha por
                               defecto es el inicio del mes en curso.
"""

import sys
from datetime import date
from pathlib import Path

RAIZ_MODULO = Path(__file__).resolve().parents[3]          # Flujo de Caja
sys.path.insert(0, str(RAIZ_MODULO / "Sistema"))
sys.path.insert(0, str(RAIZ_MODULO / "Visualizador Web"))

import build_visualizador as bv  # noqa: E402
import flujo_caja as fc  # noqa: E402


def _clp(v) -> str:
    return ("-" if v < 0 else "") + "$" + f"{abs(round(v)):,}".replace(",", ".")


def _resumen(datos: dict) -> None:
    print("=" * 72)
    print("  FLUJO DE CAJA")
    print("=" * 72)
    print(f"Datos al {datos['hoy']} · {len(datos['movimientos'])} movimientos\n")
    print(f"  {'Mes':8} {'Cobrar':>14} {'Probable':>14} {'Pagar':>14} {'Ejecutar':>14} {'Neto s/prob.':>14}")
    for m in datos["meses"]:
        if not m["proyectado"]:
            continue
        print(f"  {m['mes']:8} {_clp(m['ingreso_comprometido']):>14} {_clp(m['ingreso_probable']):>14} "
              f"{_clp(m['egreso_comprometido'] + m['egreso_real']):>14} {_clp(m['egreso_estimado']):>14} "
              f"{_clp(m['netoSinProbables']):>14}")
    if datos["avisos"]:
        print("\nPara leer estos números:")
        for a in datos["avisos"]:
            print(f"  - {a}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if argv[:1] == ["saldo"] and len(argv) in (2, 3):
        try:
            guardado = fc.guardar_saldo(argv[1], date.fromisoformat(argv[2]) if len(argv) == 3 else None)
        except ValueError as error:
            print(f"[ERROR] {error}")
            return 2
        print(f"[OK] Saldo de caja inicial: {_clp(guardado['saldoInicial'])} al {guardado['saldoInicialFecha']} "
              f"({fc.RUTA_PARAMETROS}).")
        print("Para que el Excel y el tablero lo usen: driver.py run")
        return 0
    if len(argv) != 1 or argv[0] not in ("status", "run", "visualizador"):
        print("Uso: py -3.14 driver.py [status|run|visualizador|saldo <monto> [AAAA-MM-DD]]")
        return 2
    datos = fc.ejecutar(escribir=argv[0] == "run")
    _resumen(datos)
    if argv[0] == "status":
        print("\nNada fue escrito. Para escribir el Excel y el tablero: driver.py run")
        return 0
    if argv[0] == "run":
        if not datos["excel"]:
            print("\n[ERROR] No se escribió el Excel (ver avisos).")
            return 1
        print(f"\n[OK] Excel: {datos['excel']}")
    print(f"[OK] Tablero: {bv.construir(datos)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
