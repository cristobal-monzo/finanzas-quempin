# -*- coding: utf-8 -*-
"""
driver.py — arnes de ejecucion para la skill Cotizador_Historico.

No reimplementa la logica: importa cotizador_historico.py desde Sistema/ y
expone dos comandos, ambos de solo lectura sobre Centro de Costos.xlsx (este
modulo nunca lo escribe):

  status              -> Diagnostico: cuantos items indexables hay en
                          Detalle, cuantos quedan excluidos (sin fecha
                          resoluble via Master), cuantas fechas hay en el
                          cache de UF, y si hay conexion a mindicador.cl.

  consultar "<texto>" -> Busca el texto contra Nombre Item/Descripcion
                          (busqueda difusa) y muestra cada compra
                          encontrada con su precio original y su precio
                          reajustado a hoy por UF, mas promedio y rango.

Uso:
  python driver.py status
  python driver.py consultar "taladro"
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Sistema"))

sys.dont_write_bytecode = True
import cotizador_historico as ch  # noqa: E402


def cmd_status():
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    print("=" * 70)
    print("  ESTADO COTIZADOR HISTORICO (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel Centro de Costos: {ch.RUTA_EXCEL_CENTRO_COSTOS}")
    print(f"  Existe: {ch.RUTA_EXCEL_CENTRO_COSTOS.exists()}")

    if not ch.RUTA_EXCEL_CENTRO_COSTOS.exists():
        print("\n[ERROR] No se encontro Centro de Costos.xlsx. Abortando status.")
        return 1

    try:
        items = ch.cargar_items_detalle()
    except ch.ExcelNoDisponibleError as exc:
        print(f"\n[ERROR] {exc}")
        return 1

    excluidos = [it for it in items if it["excluido_motivo"] is not None]
    print(f"\nItems indexables en Detalle: {len(items)}")
    print(f"  Excluidos (sin fecha resoluble via Master): {len(excluidos)}")

    cache = ch.cargar_cache_uf()
    print(f"\nCache UF ({ch.RUTA_CACHE_UF.name}): {len(cache)} fecha(s) guardadas")

    print("\nProbando conexion a mindicador.cl (UF de hoy)...")
    try:
        uf_hoy = ch.consultar_uf_api(date.today())
        print(f"  OK. UF hoy = {uf_hoy}")
    except ch.UFNoDisponibleError as exc:
        print(f"  [WARN] Sin conexion o sin dato: {exc}")

    print("\n" + "=" * 70)
    print('  Nada fue escrito. Para consultar un item: python driver.py consultar "<texto>"')
    print("=" * 70)
    return 0


def cmd_consultar(args):
    if not args:
        print('Uso: python driver.py consultar "<texto a buscar>"')
        return 2

    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    texto = " ".join(args)

    try:
        resultado = ch.consultar_item(texto)
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
    for c in resultado["compras"]:
        print(
            f"  {c['n_ref']} ({c['fecha']}): "
            f"${c['precio_original_sin_iva']:,.0f} -> "
            f"${c['precio_reajustado_hoy']:,.0f} reajustado a hoy"
        )

    print(f"\nPromedio reajustado: ${resultado['promedio_reajustado']:,.0f}")
    print(f"Rango: ${resultado['rango_minimo']:,.0f} - ${resultado['rango_maximo']:,.0f}")

    if resultado["excluidos_count"]:
        print(
            f"\n[INFO] {resultado['excluidos_count']} item(s) de Detalle excluido(s) "
            "del indice por no tener fecha resoluble via Master."
        )

    if resultado["sin_uf_count"]:
        print(
            f"\n[INFO] {resultado['sin_uf_count']} compra(s) encontrada(s) se excluyeron del "
            "resultado por no poder obtener su UF (sin conexion, o mindicador.cl no tiene "
            "dato para esa fecha)."
        )
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "consultar"):
        print('Uso: python driver.py [status|consultar "<texto>"]')
        return 2
    if sys.argv[1] == "status":
        return cmd_status()
    return cmd_consultar(sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
