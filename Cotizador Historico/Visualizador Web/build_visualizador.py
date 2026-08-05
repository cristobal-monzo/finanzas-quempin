# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Cotizador Historico.

Mismo patron que Centro de Costos/Visualizador Web/build_visualizador.py:
lee Centro de Costos.xlsx (solo lectura), pide la UF de hoy UNA vez, y
embebe un snapshot saneado dentro de template.html para producir un
build/index.html autocontenido (un solo archivo, sin servidor).

Salidas (gitignoradas, se regeneran completas en cada corrida):
  data/cotizador-historico.json  -- snapshot saneado intermedio (auditable)
  build/index.html                -- visualizador final con datos incrustados

Uso:
  python build_visualizador.py
  (o, desde el driver de la skill: python driver.py visualizador)
"""

import base64
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent            # Cotizador Historico/Visualizador Web/
RAIZ_MODULO = RAIZ.parent                          # Cotizador Historico/
sys.path.insert(0, str(RAIZ_MODULO / "Sistema"))
import cotizador_historico as ch  # noqa: E402

RUTA_EXCEL = ch.RUTA_EXCEL_CENTRO_COSTOS
RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "cotizador-historico.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"


def extraer_indice_saneado(ruta_excel=None, fecha_hoy=None):
    """Lee Detalle+Master (via cargar_items_detalle) y reajusta TODO el
    catalogo indexable a la UF de hoy (via reajustar_todos), pedida UNA
    sola vez -- nunca una por item. fecha_hoy es inyectable para tests
    (default: date.today())."""
    hoy = fecha_hoy or date.today()
    items = ch.cargar_items_detalle(ruta_excel)
    excluidos_count = sum(1 for it in items if it["excluido_motivo"] is not None)

    uf_hoy = ch.consultar_uf_api(hoy)
    reajustados, sin_uf_count = ch.reajustar_todos(items, uf_hoy)

    return {
        "generado": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "uf_hoy": uf_hoy,
        "uf_fecha": datetime.now().strftime("%d-%m-%Y %H:%M"),
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

    print(f"OK — {len(data['items'])} referencias indexadas, "
          f"UF utilizada ${data['uf_hoy']:,.2f}".replace(",", "."))
    print(f"Excluidos (sin fecha/precio valido, o Notas de Credito/devoluciones): {data['excluidos_count']}")
    print(f"Sin UF disponible para su fecha de compra: {data['sin_uf_count']}")
    print(f"Snapshot: {RUTA_DATA_JSON}")
    print(f"Visualizador: {RUTA_BUILD_HTML}")
    print("Para verlo: copialo a .worktrees/gh-pages/cotizador-historico/index.html y "
          "haz git push (ver /Actualizar_Cotizador), o abrelo directo en el navegador.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(build())
