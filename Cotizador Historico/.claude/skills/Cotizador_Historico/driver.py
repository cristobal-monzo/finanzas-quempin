# -*- coding: utf-8 -*-
"""
driver.py — arnes de ejecucion para la skill Cotizador_Historico.

No reimplementa la logica: importa cotizador_historico.py desde Sistema/ y
expone dos comandos, ambos de solo lectura sobre Centro de Costos.xlsx (este
modulo nunca lo escribe):

  status              -> Diagnostico: cuantos items indexables hay en
                          Detalle, cuantos quedan excluidos (sin fecha
                          resoluble via Master, sin precio unitario
                          valido, o con precio negativo -- Notas de
                          Credito/devoluciones), cuantas fechas hay en el
                          cache de UF, y si hay conexion a mindicador.cl.

  consultar "<texto>" [--uf-manual VALOR --uf-fuente "<texto>"]
                      -> Busca el texto contra Nombre Item/Descripcion
                         (busqueda difusa) y muestra una tabla con cada
                         compra encontrada: fecha, N Ref., precio original
                         sin IVA, ajuste actual sin IVA y ajuste actual con
                         IVA (tasa real del documento, no 19% fijo) -- mas
                         una fila de promedio y el rango sin IVA.

  visualizador [--uf-manual VALOR --uf-fuente "<texto>"]
                      -> Regenera el visualizador web.

  Los dos flags `--uf-manual`/`--uf-fuente` son el fallback para la UF de
  "hoy" (unica para toda la consulta/build, nunca cacheada): se pide a
  mindicador.cl primero, y solo si no responde y se pasaron estos dos flags
  (valor buscado por el agente en una fuente confiable, ej. Banco Central
  de Chile) usa ese valor en su lugar -- queda marcado como "uf_fuente" en
  la salida y en el visualizador publicado. Sin estos flags, una falla de
  mindicador.cl sigue abortando (UFNoDisponibleError) -- nunca se inventa
  un valor de UF por cuenta propia.

Uso:
  python driver.py status
  python driver.py consultar "taladro"
  python driver.py consultar "taladro" --uf-manual 39200.50 --uf-fuente "Banco Central de Chile, 20-08-2026"
  python driver.py visualizador
  python driver.py visualizador --uf-manual 39200.50 --uf-fuente "Banco Central de Chile, 20-08-2026"
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Sistema"))

sys.dont_write_bytecode = True
import cotizador_historico as ch  # noqa: E402


def _extraer_pais(argv):
    """Busca '--pais VALOR' en cualquier posicion de argv y lo separa del
    resto -- devuelve (pais, argv_sin_ese_flag). Default 'CL' si no aparece.
    Misma implementacion que Centro de Costos/.claude/skills/
    Registro_Centro_de_Costos/driver.py -- no se comparte el archivo entre
    skills (cada modulo financiero es su propio codebase, ver CLAUDE.md
    raiz), pero sí el patron."""
    argv = list(argv)
    if "--pais" in argv:
        idx = argv.index("--pais")
        pais = argv[idx + 1]
        del argv[idx:idx + 2]
        return pais, argv
    return "CL", argv


def _fmt_fecha(fecha_iso):
    """'YYYY-MM-DD' -> 'DD-MM-YYYY' para mostrar (pedido del usuario
    2026-07-28). ch.reajustar_item devuelve la fecha en ISO a proposito
    (ver su docstring) -- este driver es el unico lugar donde se reformatea
    para pantalla."""
    anio, mes, dia = fecha_iso.split("-")
    return f"{dia}-{mes}-{anio}"


def cmd_status(pais="CL"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    cfg = ch.PAISES[pais]
    print("=" * 70)
    print(f"  ESTADO COTIZADOR HISTORICO - {pais} (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel Centro de Costos: {cfg['ruta_excel']}")
    print(f"  Existe: {cfg['ruta_excel'].exists()}")

    if not cfg["ruta_excel"].exists():
        print("\n[ERROR] No se encontro el Excel. Abortando status.")
        return 1

    try:
        items = ch.cargar_items_detalle(pais=pais)
    except ch.ExcelNoDisponibleError as exc:
        print(f"\n[ERROR] {exc}")
        return 1

    excluidos = [it for it in items if it["excluido_motivo"] is not None]
    print(f"\nItems indexables en Detalle: {len(items)}")
    print(
        f"  Excluidos (sin fecha resoluble via Master, sin precio unitario valido, "
        f"o Notas de Credito/devoluciones con precio negativo): {len(excluidos)}"
    )

    if pais == "CL":
        cache = ch.cargar_cache_uf()
        print(f"\nCache UF ({ch.RUTA_CACHE_UF.name}): {len(cache)} fecha(s) guardadas")

        print("\nProbando conexion a mindicador.cl (UF de hoy)...")
        try:
            uf_hoy = ch.consultar_uf_api(date.today())
            print(f"  OK. UF hoy = {uf_hoy}")
        except ch.UFNoDisponibleError as exc:
            print(f"  [WARN] Sin conexion o sin dato: {exc}")
    else:
        print("\nPerú no reajusta por indice (sin equivalente a la UF chilena) -- "
              "los precios se muestran nominales, no hay UF que consultar.")

    print("\n" + "=" * 70)
    print('  Nada fue escrito. Para consultar un item: python driver.py consultar "<texto>"')
    print("=" * 70)
    return 0


def cmd_consultar(args, pais="CL"):
    uf_manual, fuente_manual, args = _extraer_flags_uf(args)
    if not args:
        print('Uso: python driver.py consultar "<texto a buscar>" [--uf-manual VALOR --uf-fuente "<texto>"] [--pais CL|PE]')
        return 2

    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    texto = " ".join(args)
    simbolo = "S/" if pais == "PE" else "$"

    try:
        resultado = ch.consultar_item(texto, uf_manual=uf_manual, fuente_manual=fuente_manual, pais=pais)
    except (ch.ExcelNoDisponibleError, ch.UFNoDisponibleError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    if not resultado["encontrado"]:
        if resultado["sin_uf_count"]:
            print(
                f'Se encontraron {resultado["sin_uf_count"]} compra(s) para "{texto}", pero no '
                "se pudo obtener la UF de ninguna de sus fechas (sin conexion, o mindicador.cl "
                "no tiene dato para esas fechas)."
            )
        else:
            print(f'No se encontraron compras para "{texto}".')
            if resultado["sugerencias"]:
                print("Quizas quisiste decir:")
                for s in resultado["sugerencias"]:
                    print(f"  - {s}")
        return 0

    print(f'Compras encontradas para "{texto}":\n')
    if pais == "PE":
        print("| Fecha | N° Ref. | Precio (sin IGV) | Precio (con IGV) |")
        print("|---|---|---|---|")
        for c in resultado["compras"]:
            print(
                f"| {_fmt_fecha(c['fecha'])} | {c['n_ref']} | "
                f"{simbolo}{c['precio_reajustado_hoy']:,.0f} | "
                f"{simbolo}{c['precio_reajustado_hoy_con_iva']:,.0f} |"
            )
        print(
            f"| **Promedio** | | "
            f"{simbolo}{resultado['promedio_reajustado']:,.0f} | "
            f"{simbolo}{resultado['promedio_reajustado_con_iva']:,.0f} |"
        )
        print(f"\nRango: {simbolo}{resultado['rango_minimo']:,.0f} - {simbolo}{resultado['rango_maximo']:,.0f}")
    else:
        print("| Fecha | N° Ref. | Precio original (sin IVA) | Ajuste actual sin IVA | Ajuste actual con IVA |")
        print("|---|---|---|---|---|")
        for c in resultado["compras"]:
            print(
                f"| {_fmt_fecha(c['fecha'])} | {c['n_ref']} | "
                f"${c['precio_original_sin_iva']:,.0f} | "
                f"${c['precio_reajustado_hoy']:,.0f} | "
                f"${c['precio_reajustado_hoy_con_iva']:,.0f} |"
            )
        print(
            f"| **Promedio** | | | "
            f"${resultado['promedio_reajustado']:,.0f} | "
            f"${resultado['promedio_reajustado_con_iva']:,.0f} |"
        )
        print(f"\nRango (sin IVA): ${resultado['rango_minimo']:,.0f} - ${resultado['rango_maximo']:,.0f}")

    if resultado["excluidos_count"]:
        print(
            f"\n[INFO] {resultado['excluidos_count']} item(s) de Detalle excluido(s) "
            "del indice por no tener fecha resoluble via Master, por no tener precio "
            "unitario valido, o por ser Notas de Credito/devoluciones (precio negativo)."
        )

    if pais == "CL":
        if resultado["sin_uf_count"]:
            print(
                f"\n[INFO] {resultado['sin_uf_count']} compra(s) encontrada(s) se excluyeron del "
                "resultado por no poder obtener su UF (sin conexion, o mindicador.cl no tiene "
                "dato para esa fecha)."
            )
        if resultado.get("uf_fuente") and resultado["uf_fuente"] != "mindicador.cl":
            print(f"\n[AVISO] mindicador.cl no respondio -- se uso UF manual (fuente: {resultado['uf_fuente']}).")
    return 0


def cmd_visualizador(pais="CL", uf_manual=None, fuente_manual=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raiz_modulo = Path(__file__).resolve().parents[3]
    if pais == "CL":
        ruta_viz = raiz_modulo / "Visualizador Web"
    else:
        ruta_viz = raiz_modulo.parent / "Peru" / "Cotizador Historico" / "Visualizador Web"
    ruta_build_script = ruta_viz / "build_visualizador.py"
    if not ruta_build_script.exists():
        print(f"[INFO] Visualizador Web de {pais} aún no implementado -- nada que regenerar.")
        return 0
    sys.path.insert(0, str(ruta_viz))
    sys.dont_write_bytecode = True
    import build_visualizador as bv  # noqa: E402
    if pais == "PE":
        return bv.build()
    return bv.build(uf_manual=uf_manual, fuente_manual=fuente_manual)


def _extraer_flags_uf(args):
    """Extrae --uf-manual VALOR --uf-fuente "<texto>" de args (ambos
    opcionales, fallback cuando mindicador.cl no responde -- ver docstring
    del modulo). Devuelve (uf_manual, fuente_manual, args_restantes)."""
    uf_manual = None
    fuente_manual = None
    restantes = []
    i = 0
    while i < len(args):
        if args[i] == "--uf-manual" and i + 1 < len(args):
            uf_manual = float(args[i + 1])
            i += 2
        elif args[i] == "--uf-fuente" and i + 1 < len(args):
            fuente_manual = args[i + 1]
            i += 2
        else:
            restantes.append(args[i])
            i += 1
    return uf_manual, fuente_manual, restantes


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "consultar", "visualizador"):
        print(
            'Uso: python driver.py [status|consultar "<texto>"|'
            'visualizador] [--uf-manual VALOR --uf-fuente "<texto>"] [--pais CL|PE]'
        )
        return 2
    comando = sys.argv[1]
    pais, resto = _extraer_pais(sys.argv[2:])
    if comando == "status":
        return cmd_status(pais=pais)
    if comando == "visualizador":
        uf_manual, fuente_manual, _resto = _extraer_flags_uf(resto)
        return cmd_visualizador(pais=pais, uf_manual=uf_manual, fuente_manual=fuente_manual)
    return cmd_consultar(resto, pais=pais)


if __name__ == "__main__":
    raise SystemExit(main())
