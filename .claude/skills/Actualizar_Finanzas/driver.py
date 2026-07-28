# -*- coding: utf-8 -*-
"""
driver.py -- orquestador unico de Finanzas QUEMPIN.

Un solo punto de entrada que deja TODOS los modulos y TODOS los tableros al
dia, en el orden correcto de dependencias:

    Centro de Costos  (registra documentos nuevos)
        -> Analisis Financiero      (lee CC, recalcula KPIs)   [ya encadenado]
        -> Visualizador CC          (lee CC)                   [ya encadenado]
        -> Visualizador AF          (lee AF)                   [ya encadenado]
        -> Visualizador Cotizador   (lee CC)                   <-- LO AGREGA ESTE
        -> Reportes PDF pendientes  (lee AF)                   <-- LO REPORTA ESTE

Por que existe (auditoria 2026-07-28): 'run' de Centro de Costos ya encadena
Analisis Financiero y dos de los tres visualizadores (PASO 12b/12c/12d), pero
el visualizador de Cotizador Historico no lo invocaba NADIE -- pese a leer el
mismo Centro de Costos.xlsx, su tablero quedaba congelado en la ultima vez que
alguien corrio su driver a mano. Los reportes PDF, ademas, solo se avisaban.

Por que SUBPROCESOS y no imports: los tres modulos tienen archivos que se
llaman igual ("build_visualizador.py", "driver.py"). sys.modules cachea por
nombre, asi que importarlos en el mismo proceso entrega el equivocado -- el
codigo existente lo esquiva con sys.modules.pop(), un parche fragil que
depende del orden. Un proceso por modulo elimina la clase de problema entera,
y de paso hace que un modulo que falle no pueda voltear a los demas.

Por que NO se removio el encadenamiento de PASO 12c/12d de Centro de Costos:
sacarlo obligaria a pasar SIEMPRE por este orquestador para que los tableros
queden consistentes. Correr '/Registro_Centro_de_Costos' directo -- que es lo
que documentan sus skills -- dejaria el Excel actualizado y los tableros
viejos: se cambiaria un hueco conocido por uno nuevo. El encadenamiento se
mantiene y este orquestador cubre lo que faltaba.

Uso:
  python driver.py status   # solo lectura: que haria cada modulo, sin tocar nada
  python driver.py run      # cadena completa
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]

DRIVER_CENTRO_COSTOS = (
    RAIZ / "Centro de Costos" / ".claude" / "skills"
    / "Registro_Centro_de_Costos" / "driver.py"
)
DRIVER_ANALISIS_FINANCIERO = (
    RAIZ / "Sistema Analisis Financiero" / ".claude" / "skills"
    / "Registro_Analisis_Financiero" / "driver.py"
)
DRIVER_REPORTES = (
    RAIZ / "Sistema Analisis Financiero" / ".claude" / "skills"
    / "Reportes_Analisis_Financiero" / "driver.py"
)
DRIVER_COTIZADOR = (
    RAIZ / "Cotizador Historico" / ".claude" / "skills"
    / "Cotizador_Historico" / "driver.py"
)


def _ejecutar(titulo, ruta_driver, args, obligatorio):
    """Corre un driver en su propio proceso. Devuelve (ok, salida).

    obligatorio=True  -> si falla, la cadena se detiene (no tiene sentido
                         actualizar tableros sobre datos que no se escribieron).
    obligatorio=False -> si falla, se reporta y la cadena sigue: un tablero
                         caido no debe impedir que los otros se actualicen.
    """
    print("\n" + "=" * 72)
    print(f"  {titulo}")
    print("=" * 72)

    if not ruta_driver.exists():
        print(f"  [OMITIDO] No existe {ruta_driver}")
        return (not obligatorio), ""

    proceso = subprocess.run(
        [sys.executable, str(ruta_driver), *args],
        cwd=str(ruta_driver.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    salida = (proceso.stdout or "") + (proceso.stderr or "")
    print(salida.rstrip() or "  (sin salida)")

    if proceso.returncode != 0:
        etiqueta = "ERROR" if obligatorio else "WARN"
        print(f"  [{etiqueta}] '{ruta_driver.name} {' '.join(args)}' termino con codigo "
              f"{proceso.returncode}.")
        return False, salida
    return True, salida


def _resumir(resultados, mensaje_ok):
    print("\n" + "=" * 72)
    print("  RESUMEN")
    print("=" * 72)
    for titulo, ok in resultados:
        print(f"  [{'OK ' if ok else 'FALLO'}] {titulo}")
    fallidos = [t for t, ok in resultados if not ok]
    if fallidos:
        print(f"\n  {len(fallidos)} paso(s) con problemas. El resto si se completo.")
        return 1
    print(f"\n  {mensaje_ok}")
    return 0


def cmd_status():
    """Solo lectura en los 3 modulos: nadie escribe Excel, archivos ni
    tableros."""
    resultados = []
    for titulo, driver in (
        ("Centro de Costos -- status", DRIVER_CENTRO_COSTOS),
        ("Analisis Financiero -- status", DRIVER_ANALISIS_FINANCIERO),
        ("Reportes PDF -- status", DRIVER_REPORTES),
        ("Cotizador Historico -- status", DRIVER_COTIZADOR),
    ):
        ok, _ = _ejecutar(titulo, driver, ["status"], obligatorio=False)
        resultados.append((titulo, ok))

    print("\n  Nada fue escrito. Para ejecutar de verdad: python driver.py run")
    return _resumir(resultados, "Los 4 modulos respondieron. Nada fue escrito.")


def cmd_run():
    resultados = []

    # 1. Centro de Costos. Su propio 'run' ya encadena Analisis Financiero
    #    (PASO 12d), el visualizador de CC (12c) y, dentro de AF, el
    #    visualizador de AF. Si esto falla no tiene sentido seguir.
    ok_cc, _ = _ejecutar(
        "Centro de Costos -- run (encadena Analisis Financiero y sus 2 tableros)",
        DRIVER_CENTRO_COSTOS, ["run"], obligatorio=True,
    )
    resultados.append(("Centro de Costos + Analisis Financiero + tableros CC/AF", ok_cc))
    if not ok_cc:
        print("\n  [ERROR] Centro de Costos fallo: no se actualiza nada aguas abajo "
              "para no publicar tableros sobre datos a medio escribir.")
        return _resumir(resultados, "")

    # 2. El eslabon que faltaba: el tablero del Cotizador lee el mismo
    #    Centro de Costos.xlsx que acaba de cambiar, y nadie lo regeneraba.
    ok_coti, _ = _ejecutar(
        "Cotizador Historico -- visualizador (el que nadie regeneraba)",
        DRIVER_COTIZADOR, ["visualizador"], obligatorio=False,
    )
    resultados.append(("Tablero Cotizador Historico", ok_coti))

    # 3. Reportes PDF: se listan los que quedaron desactualizados. No se
    #    generan solos a proposito -- cada PDF lleva analisis redactado, no
    #    es una salida puramente mecanica (ver Reportes_Analisis_Financiero).
    ok_rep, salida_rep = _ejecutar(
        "Reportes PDF -- que quedo pendiente",
        DRIVER_REPORTES, ["status"], obligatorio=False,
    )
    resultados.append(("Estado de reportes PDF", ok_rep))

    codigo = _resumir(resultados, "Todos los modulos y tableros quedaron al dia.")

    print("\n  Siguiente paso manual (si corresponde):")
    print("   - Publicar los tableros como Artifact: /Actualizar_CC para Centro de")
    print("     Costos; los de Analisis Financiero y Cotizador se regeneraron en")
    print("     disco pero se publican a mano (ver MEMORY.md de cada skill).")
    if "pendiente" in salida_rep.lower() or "desactualizad" in salida_rep.lower():
        print("   - Generar los reportes PDF pendientes: /Reportes_Analisis_Financiero run")
    return codigo


def main():
    comandos = ("status", "run")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run]")
        return 2
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    return cmd_status() if sys.argv[1] == "status" else cmd_run()


if __name__ == "__main__":
    raise SystemExit(main())
