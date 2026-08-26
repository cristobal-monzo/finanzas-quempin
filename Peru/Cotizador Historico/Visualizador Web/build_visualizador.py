# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Cotizador Historico Peru.

Copia de Cotizador Historico/Visualizador Web/build_visualizador.py
adaptada a Peru: lee Centro de Costos Peru.xlsx (pais="PE"), y en vez de
pedir la UF de hoy y reajustar, usa armar_indice_completo_sin_reajuste --
Peru no reajusta por ningun indice (ver docs/superpowers/specs/
2026-08-21-peru-expansion-design.md decision 5). El snapshot resultante NO
trae uf_hoy/uf_fecha/uf_fuente -- esos campos no existen para Peru.

Salidas (gitignoradas, se regeneran completas en cada corrida):
  data/cotizador-historico-peru.json  -- snapshot saneado intermedio (auditable)
  build/index.html                     -- visualizador final con datos incrustados

Uso:
  python build_visualizador.py
  (o, desde el driver de la skill: python driver.py visualizador --pais PE)
"""

import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent            # Peru/Cotizador Historico/Visualizador Web/
RAIZ_MODULO = RAIZ.parent                          # Peru/Cotizador Historico/
sys.path.insert(0, str(RAIZ_MODULO.parent.parent / "Cotizador Historico" / "Sistema"))
import cotizador_historico as ch  # noqa: E402

RUTA_EXCEL = ch.RUTA_EXCEL_CENTRO_COSTOS_PERU
RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "cotizador-historico-peru.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"


def extraer_indice_saneado(ruta_excel=None):
    """Lee Detalle+Master de Centro de Costos Peru.xlsx (pais="PE") y arma
    el indice completo SIN reajuste (ver ch.armar_indice_completo_sin_reajuste)
    -- a diferencia de la version de Chile, no pide ninguna UF ni incrusta
    uf_hoy/uf_fecha/uf_fuente en el snapshot."""
    items = ch.cargar_items_detalle(ruta_excel, pais="PE")
    excluidos_count = sum(1 for it in items if it["excluido_motivo"] is not None)
    reajustados, sin_uf_count = ch.armar_indice_completo_sin_reajuste(items)

    return {
        "generado": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "excluidos_count": excluidos_count,
        "sin_uf_count": sin_uf_count,
        "items": reajustados,
    }


def build():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    if not RUTA_EXCEL.exists():
        print(f"[ERROR] No existe el Excel: {RUTA_EXCEL}")
        return 1
    if not RUTA_TEMPLATE.exists():
        print(f"[ERROR] No existe la plantilla: {RUTA_TEMPLATE}")
        return 1

    data = extraer_indice_saneado(RUTA_EXCEL)

    RUTA_DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with io.open(RUTA_DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    data_json_text = json.dumps(data, ensure_ascii=False)
    data_b64 = base64.b64encode(data_json_text.encode("utf-8")).decode("ascii")

    with io.open(RUTA_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()
    if "__CH_DATA_B64__" not in template:
        print("[ERROR] template.html no tiene el placeholder __CH_DATA_B64__")
        return 1
    html = template.replace("__CH_DATA_B64__", data_b64)

    RUTA_BUILD_HTML.parent.mkdir(parents=True, exist_ok=True)
    with io.open(RUTA_BUILD_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK — {len(data['items'])} referencias indexadas (sin reajuste, precios nominales en soles)")
    print(f"Excluidos (sin fecha/precio valido, o Notas de Credito/devoluciones): {data['excluidos_count']}")
    print(f"Snapshot: {RUTA_DATA_JSON}")
    print(f"Visualizador: {RUTA_BUILD_HTML}")
    print("Para verlo: copialo a .worktrees/gh-pages/cotizador-historico-peru/index.html y "
          "haz git push, o abrelo directo en el navegador.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(build())
