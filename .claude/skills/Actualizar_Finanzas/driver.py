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
        -> Carpeta de intercambio   (procesar.py --forzar)     [2026-10-01]
        -> Flujo de Caja            (lee CC + intercambio)     [2026-10-02]

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
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
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
# Procesador de la carpeta de intercambio (plan de integracion, 2026-10-01).
# Corre solo cada 2 horas con su propia tarea; al final de este run se le
# fuerza una vuelta completa para que todo lo publicado salga de los datos
# recien actualizados.
PROCESADOR_INTERCAMBIO = RAIZ / "Sistema Intercambio" / "procesar.py"
# Flujo de Caja (2026-10-02): se arma con lo que publican CC, Sistema QUEMPIN,
# la Planilla y AF, asi que va despues del procesador.
DRIVER_FLUJO_CAJA = (
    RAIZ / "Flujo de Caja" / ".claude" / "skills"
    / "Registro_Flujo_de_Caja" / "driver.py"
)

# Los 4 tableros: (nombre, build/index.html regenerado, subruta fija dentro
# de la rama gh-pages). Desde 2026-08-05 (migracion de Claude Artifacts a
# GitHub Pages) la URL de cada uno es estructural -- ya no hay un link opaco
# que leer de un MEMORY.md ni que cuidar de "no regenerar por error".
RAIZ_GH_PAGES = RAIZ / ".worktrees" / "gh-pages"
# (nombre, build, subruta, clave de "Visualizador Web/publicar.py")
TABLEROS = (
    (
        "Centro de Costos",
        RAIZ / "Centro de Costos" / "Visualizador Web" / "build" / "index.html",
        "centro-de-costos", "cc",
    ),
    (
        "Análisis Financiero",
        RAIZ / "Sistema Analisis Financiero" / "Visualizador Web" / "build" / "index.html",
        "analisis-financiero", "af",
    ),
    (
        "Cotizador Histórico",
        RAIZ / "Cotizador Historico" / "Visualizador Web" / "build" / "index.html",
        "cotizador-historico", "cot",
    ),
    (
        "Flujo de Caja",
        RAIZ / "Flujo de Caja" / "Visualizador Web" / "build" / "index.html",
        "flujo-de-caja", "fc",
    ),
)

URL_BASE_PAGES = "https://cristobal-monzo.github.io/finanzas-quempin"


def _informe_tableros(momento_inicio):
    """Lista los 4 tableros con su ruta, si se regeneraron en esta corrida y
    su URL fija -- todo lo que el agente necesita para publicarlos. Publicar
    (Visualizador Web/publicar.py + commit + git push) es lo unico que este
    driver no hace solo: requiere git push, que el agente corre de forma
    visible/confirmable, no escondido dentro de este script."""
    print("\n" + "=" * 72)
    print("  TABLEROS PARA PUBLICAR")
    print("=" * 72)

    regenerados = []
    for nombre, ruta_build, subruta, clave in TABLEROS:
        print(f"\n  {nombre}")
        if not ruta_build.exists():
            print("    [SIN BUILD] No existe todavia -- nada que publicar.")
            print(f"    Esperado en: {ruta_build}")
            continue

        mtime = ruta_build.stat().st_mtime
        regenerado = mtime >= momento_inicio
        marca = datetime.fromtimestamp(mtime).strftime("%d-%m-%Y %H:%M:%S")
        estado = "REGENERADO en esta corrida" if regenerado else f"sin cambios (del {marca})"

        print(f"    Estado : {estado}")
        print(f"    Archivo: {ruta_build}")
        print(f"    URL    : {URL_BASE_PAGES}/{subruta}/")
        if regenerado:
            regenerados.append(clave)

    # No se copian a mano (2026-10-08): el tablero del AF lleva sus reportes PDF
    # cifrados aparte en build/reportes/, y publicar.py copia todo y lo verifica.
    print("\n  Publicar = dejarlos listos con publicar.py (copia cada uno con su carpeta")
    print("  reportes/, verifica con el candado y hace git add en gh-pages), y despues")
    print("  commit y push en gh-pages:")
    print(f'    py -3.14 "Visualizador Web/publicar.py" {" ".join(regenerados) or "<cc af cot fc>"}')
    print(f'    git -C "{RAIZ_GH_PAGES}" commit -m "..." && git -C "{RAIZ_GH_PAGES}" push')


# Cronometro de la corrida: cada _ejecutar() deja aca cuanto tardo su modulo.
# Sin esto no habia forma de saber que paso domina el tiempo de una
# actualizacion -- la auditoria de 2026-09-09 descubrio recien perfilando a
# mano que el tablero del Cotizador se llevaba mas de un tercio del total.
_TIEMPOS = []


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

    inicio = time.perf_counter()
    proceso = subprocess.run(
        [sys.executable, str(ruta_driver), *args],
        cwd=str(ruta_driver.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    fin = time.perf_counter()
    duracion = fin - inicio
    _TIEMPOS.append((titulo, inicio, fin))
    salida = (proceso.stdout or "") + (proceso.stderr or "")
    print(salida.rstrip() or "  (sin salida)")
    print(f"\n  [TIEMPO] {titulo}: {duracion:.2f}s")

    if proceso.returncode != 0:
        etiqueta = "ERROR" if obligatorio else "WARN"
        print(f"  [{etiqueta}] '{ruta_driver.name} {' '.join(args)}' termino con codigo "
              f"{proceso.returncode}.")
        return False, salida
    return True, salida


def _ejecutar_varios(trabajos):
    """Corre varios drivers EN PARALELO y devuelve [(titulo, ok, salida)] en
    el mismo orden en que se pidieron.

    Solo se pasan por aca pasos que no comparten archivos: el tablero del
    Cotizador lee Centro de Costos.xlsx y escribe dentro de Cotizador
    Historico/, y el status de Reportes lee el Excel de Analisis Financiero y
    no escribe nada. Ninguno lee lo que el otro escribe, asi que el orden
    entre ellos es irrelevante y esperarlos en serie era tiempo regalado.

    La salida de cada uno se imprime junta al terminar todos, en orden fijo:
    intercalar stdout de procesos concurrentes haria el log ilegible.
    """
    if len(trabajos) == 1:
        titulo, driver, args, obligatorio = trabajos[0]
        ok, salida = _ejecutar(titulo, driver, args, obligatorio)
        return [(titulo, ok, salida)]

    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(trabajos)) as pool:
        futuros = [
            pool.submit(_correr_driver, driver, args)
            for _titulo, driver, args, _obligatorio in trabajos
        ]
        crudos = [f.result() for f in futuros]

    resultados = []
    for (titulo, driver, args, obligatorio), (rc, salida, ini, fin) in zip(trabajos, crudos):
        print("\n" + "=" * 72)
        print(f"  {titulo}")
        print("=" * 72)
        if rc is None:
            print(f"  [OMITIDO] No existe {driver}")
            resultados.append((titulo, not obligatorio, ""))
            continue
        _TIEMPOS.append((titulo, ini, fin))
        print(salida.rstrip() or "  (sin salida)")
        print(f"\n  [TIEMPO] {titulo}: {fin - ini:.2f}s")
        ok = rc == 0
        if not ok:
            print(f"  [{'ERROR' if obligatorio else 'WARN'}] '{driver.name} "
                  f"{' '.join(args)}' termino con codigo {rc}.")
        resultados.append((titulo, ok, salida))

    print(f"\n  [PARALELO] {len(trabajos)} pasos en {time.perf_counter() - inicio:.2f}s "
          f"(en serie habrian sido {sum(f - i for _, _, i, f in crudos):.2f}s)")
    return resultados


def _correr_driver(ruta_driver, args):
    """Ejecuta un driver y devuelve (returncode, salida, t_inicio, t_fin).
    Se devuelven los dos extremos y no la duracion porque el informe de
    tiempos necesita saber que pasos se solaparon. rc=None si no existe."""
    if not ruta_driver.exists():
        return None, "", 0.0, 0.0
    inicio = time.perf_counter()
    proceso = subprocess.run(
        [sys.executable, str(ruta_driver), *args],
        cwd=str(ruta_driver.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (proceso.returncode,
            (proceso.stdout or "") + (proceso.stderr or ""),
            inicio, time.perf_counter())


def _informe_tiempos(total):
    """Desglose de donde se fue el tiempo. Es la unica forma de detectar que
    un paso se degrado sin tener que perfilar a mano.

    Los pasos que corren en paralelo se solapan, asi que la suma de sus
    duraciones NO es el tiempo transcurrido: lo que se compara contra el
    total es la UNION de sus intervalos. El porcentaje de cada paso es sobre
    el total de pared, y por eso los porcentajes pueden sumar mas de 100 --
    se marca con (P) cual se solapo con otro.
    """
    if not _TIEMPOS:
        return
    print("\n" + "=" * 72)
    print("  TIEMPOS")
    print("=" * 72)

    # Union de intervalos: cuanto tiempo de pared estuvo corriendo ALGUN paso.
    intervalos = sorted((ini, fin) for _, ini, fin in _TIEMPOS)
    cubierto, tope = 0.0, None
    for ini, fin in intervalos:
        if tope is None or ini > tope:
            cubierto += fin - ini
            tope = fin
        elif fin > tope:
            cubierto += fin - tope
            tope = fin

    suma = sum(fin - ini for _, ini, fin in _TIEMPOS)
    for titulo, ini, fin in sorted(_TIEMPOS, key=lambda t: -(t[2] - t[1])):
        duracion = fin - ini
        solapa = any(o != titulo and ini < ofin and oini < fin
                     for o, oini, ofin in _TIEMPOS)
        marca = " (P)" if solapa else ""
        pct = 100 * duracion / total if total else 0
        print(f"  {duracion:7.2f}s  {pct:5.1f}%  {titulo}{marca}")
    print(f"  {'-' * 68}")
    if suma - cubierto > 0.01:
        print(f"  {cubierto:7.2f}s          en algun paso "
              f"(suma de pasos {suma:.2f}s; {suma - cubierto:.2f}s ganados en paralelo)")
    print(f"  {total:7.2f}s  100.0%  TOTAL (orquestacion: {total - cubierto:.2f}s)")


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
    momento_inicio = datetime.now().timestamp()
    inicio = time.perf_counter()
    # Los 6 son de solo lectura y no dependen entre si: van en paralelo.
    trabajos = [
        (titulo, driver, args, False)
        for titulo, driver, args in (
            ("Centro de Costos -- status", DRIVER_CENTRO_COSTOS, ["status"]),
            ("Analisis Financiero -- status", DRIVER_ANALISIS_FINANCIERO, ["status"]),
            ("Reportes PDF -- status", DRIVER_REPORTES, ["status"]),
            ("Cotizador Historico -- status", DRIVER_COTIZADOR, ["status"]),
            # Pedido del usuario (2026-09-30): los presupuestos nuevos del
            # Formulador y los adjudicados que faltan en Analisis Financiero.
            ("Presupuestos del Formulador", DRIVER_ANALISIS_FINANCIERO, ["formulaciones"]),
            ("Flujo de Caja -- status", DRIVER_FLUJO_CAJA, ["status"]),
        )
    ]
    salidas = _ejecutar_varios(trabajos)
    resultados = [(titulo, ok) for titulo, ok, _ in salidas]
    _aviso_presupuestos(salidas[4][2])

    # En 'status' ningun build se regenera, asi que todos saldran como "sin
    # cambios" -- sirve igual para ver cual falta, cuando se genero cada uno y
    # si tiene link registrado.
    _informe_tableros(momento_inicio)
    _informe_tiempos(time.perf_counter() - inicio)

    print("\n  Nada fue escrito. Para ejecutar de verdad: python driver.py run")
    return _resumir(resultados, "Los 6 pasos respondieron. Nada fue escrito.")


def _aviso_presupuestos(salida):
    """Si hay presupuestos del Formulador que revisar o cargar, dejarlo dicho
    al final, donde el agente lo ve junto con lo demas pendiente."""
    salida = salida or ""
    cargar = salida.count("[CARGAR]") + salida.count("[ELEGIR TAG]")
    novedades = salida.count("[NUEVO]") + salida.count("[CAMBIÓ]")
    if not (cargar or novedades):
        return
    print("\n" + "=" * 72)
    print("  PRESUPUESTOS DEL FORMULADOR -- para revisar con el usuario")
    print("=" * 72)
    if novedades:
        print(f"  - {novedades} presupuesto(s) nuevos o cambiados: resumirselos al usuario y luego")
        print("    'Registro_Analisis_Financiero/driver.py formulaciones revisadas'.")
    if cargar:
        print(f"  - {cargar} adjudicado(s) sin cargar en Analisis Financiero: confirmar el TAG con el")
        print("    usuario y usar 'driver.py formulaciones cargar <uid> <TAG>' (se aplica en el run).")


def cmd_run():
    # Marca de tiempo previa a todo: sirve para distinguir que build/index.html
    # se regenero de verdad en esta corrida y cual quedo igual que antes.
    momento_inicio = datetime.now().timestamp()
    inicio = time.perf_counter()
    resultados = []

    # 0. Presupuestos entregados por archivo (navegadores sin acceso a la
    #    carpeta): al repositorio del Formulador. Solo escribe en
    #    publicado/formulador/ con las mismas reglas del Formulador; si falla,
    #    no frena lo demas.
    ok_inc, _ = _ejecutar(
        "Presupuestos del Formulador -- incorporar entregas por archivo",
        DRIVER_ANALISIS_FINANCIERO, ["formulaciones", "incorporar"], obligatorio=False,
    )
    resultados.append(("Entregas de presupuestos por archivo", ok_inc))

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

    # 2 y 3, EN PARALELO -- ninguno lee lo que el otro escribe:
    #   - El tablero del Cotizador lee el mismo Centro de Costos.xlsx que
    #     acaba de cambiar (era el eslabon que nadie regeneraba) y escribe
    #     solo dentro de Cotizador Historico/.
    #   - Reportes PDF solo LISTA los que quedaron desactualizados, leyendo el
    #     Excel de Analisis Financiero. No se generan solos a proposito: cada
    #     PDF lleva analisis redactado, no es una salida mecanica (ver
    #     Reportes_Analisis_Financiero).
    salidas = _ejecutar_varios([
        ("Cotizador Historico -- visualizador (el que nadie regeneraba)",
         DRIVER_COTIZADOR, ["visualizador"], False),
        ("Reportes PDF -- que quedo pendiente",
         DRIVER_REPORTES, ["status"], False),
        # Solo lectura, despues del run de AF: asi ve lo que ese run ya aplico.
        ("Presupuestos del Formulador", DRIVER_ANALISIS_FINANCIERO, ["formulaciones"], False),
    ])
    resultados.append(("Tablero Cotizador Historico", salidas[0][1]))
    resultados.append(("Estado de reportes PDF", salidas[1][1]))
    resultados.append(("Presupuestos del Formulador", salidas[2][1]))
    salida_rep = salidas[1][2]
    _aviso_presupuestos(salidas[2][2])

    # 4. Carpeta de intercambio: todo lo publicado para las demas
    #    herramientas (requerimientos, lista de proyectos de AF con su sesgo,
    #    precios de referencia, Sistema QUEMPIN, registro de proyectos y
    #    estado.json) sale de lo que se acaba de actualizar. Nunca frena.
    ok_inter, _ = _ejecutar(
        "Carpeta de intercambio -- procesador (vuelta completa)",
        PROCESADOR_INTERCAMBIO, ["--forzar"], obligatorio=False,
    )
    resultados.append(("Carpeta de intercambio", ok_inter))

    # 5. Flujo de Caja: Excel y tablero, desde lo que el procesador acaba de
    #    publicar y la foto del Centro de Costos del paso 1. Nunca frena.
    ok_flujo, _ = _ejecutar(
        "Flujo de Caja -- run (Excel y tablero)",
        DRIVER_FLUJO_CAJA, ["run"], obligatorio=False,
    )
    resultados.append(("Flujo de Caja", ok_flujo))

    _informe_tableros(momento_inicio)
    _informe_tiempos(time.perf_counter() - inicio)

    codigo = _resumir(resultados, "Todos los modulos y tableros quedaron al dia en disco.")

    print("\n  Falta para cerrar la actualizacion:")
    print("   - PUBLICAR los 4 tableros de arriba (paso obligatorio: regenerarlos")
    print("     en disco no cambia lo que ve la gente en el link publicado).")
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
