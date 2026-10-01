# -*- coding: utf-8 -*-
"""
driver.py -- sugerencias para la Planilla de Ingreso de Requerimientos.

Las herramientas (Formulador, Sistema QUEMPIN) mandan el mensaje
«actualizar-requerimiento» cuando un requerimiento pasa a Ofertado o
Adjudicado, con el valor ofertado o adjudicado. La planilla es de las
personas y **no se escribe desde código** (guardarla con openpyxl borra sus
matrices dinámicas e imágenes en celdas, ver Sistema Intercambio/
requerimientos.py): una persona pasa la sugerencia a mano y el procesador del
intercambio la cierra sola cuando la planilla ya la muestra.

  status              -> qué falta pasar a la planilla, fila por fila (lee la
                         planilla en este momento, no la copia publicada) y
                         cierra las que ya están pasadas.
  descartar <id>      -> archiva una sugerencia que no corresponde.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "Sistema Intercambio"))

import intercambio  # noqa: E402
import requerimientos as rq  # noqa: E402
import ubicacion  # noqa: E402


def _carpetas():
    raiz = ubicacion.ubicar_intercambio(RAIZ)
    if raiz is None or not intercambio.es_carpeta_de_intercambio(raiz):
        print("[AVISO] No se encontró la carpeta de intercambio (biblioteca «Formulación de proyectos» sin sincronizar).")
        return None, None
    planilla = ubicacion.ubicar_planilla(RAIZ)
    if planilla is None:
        print("[AVISO] No se encontró la Planilla de Ingreso de Requerimientos.")
        return raiz, None
    return raiz, planilla


def cmd_status() -> int:
    raiz, planilla = _carpetas()
    if planilla is None:
        return 1
    reqs = rq.leer_planilla(planilla)
    decisiones = rq.revisar_sugerencias(raiz, reqs)
    cerradas = [d for d in decisiones if d["accion"] == "aplicado"]
    abiertas = [d for d in decisiones if d["accion"] in ("pendiente", "conflicto")]
    print("=" * 70)
    print("  SUGERENCIAS PARA LA PLANILLA DE INGRESO")
    print("=" * 70)
    print(f"Planilla: {planilla}")
    if cerradas:
        print(f"\n{len(cerradas)} sugerencia(s) ya estaban pasadas a la planilla: se cerraron.")
    if not abiertas:
        print("\nNo hay nada que pasar a la planilla.")
        return 0
    print(f"\n{len(abiertas)} sugerencia(s) por pasar a mano:\n")
    for d in abiertas:
        m = d["mensaje"]
        origen = m.get("origen") or {}
        fuente = m.get("fuente") or {}
        de = fuente.get("codigo") or fuente.get("folio") or origen.get("herramienta")
        print(f"  [{m['id']}] de {de} ({origen.get('usuario') or origen.get('herramienta')}, {origen.get('enviado', '')[:10]})")
        if d["accion"] == "conflicto":
            print("    OJO: la planilla cambió después de que se hizo la sugerencia:")
        for linea in d["detalle"]:
            print(f"    - {linea}")
    print("\nCuando estén pasadas, el procesador las cierra solo (o vuelve a correr 'status').")
    print("Para descartar una: driver.py descartar <id>")
    return 0


def cmd_descartar(args) -> int:
    if len(args) != 1:
        print("Uso: python driver.py descartar <id>")
        return 2
    raiz, _ = _carpetas()
    if raiz is None:
        return 1
    if not rq.descartar_sugerencia(raiz, args[0]):
        print(f"[INFO] No hay una sugerencia con id {args[0]} en el buzón.")
        return 1
    print(f"[OK] Sugerencia {args[0]} descartada: la planilla queda como está.")
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "descartar"):
        print("Uso: python driver.py [status|descartar <id>]")
        return 2
    return cmd_status() if sys.argv[1] == "status" else cmd_descartar(sys.argv[2:])


if __name__ == "__main__":
    raise SystemExit(main())
