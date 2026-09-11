# -*- coding: utf-8 -*-
"""
sandbox.py -- monta un Centro de Costos completo y desechable sobre un
directorio temporal, para poder medir el pipeline sin tocar un solo byte de
los datos reales.

Por que asi y no parcheando globals desde afuera (ver CLAUDE.md raiz,
"No midas contra produccion"): `main()` llama a `configurar_pais()` como
primera linea y REESCRIBE todos los globals de ruta, asi que cualquier parche
externo se pierde. La unica forma estable es registrar un pais ficticio en
`acc.PAISES` cuyas rutas ya apunten al sandbox.

`montar()` deja ademas un guard activo: si alguna ruta de escritura quedara
fuera del directorio temporal, aborta antes de correr nada.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ_SISTEMA = Path(__file__).resolve().parent.parent
if str(RAIZ_SISTEMA) not in sys.path:
    sys.path.insert(0, str(RAIZ_SISTEMA))

sys.dont_write_bytecode = True
import auditor_centro_costos as acc  # noqa: E402

PAIS_BENCH = "BENCH"

PLANTILLA_ERRORES_MD = """# Errores (sandbox de benchmark)

## Correcciones manuales pendientes de recolorear

| Fecha | Hoja | N° Ref. | Campo / Columna | Valor anterior (rojo) | Valor corregido | Estado | Nota |
|---|---|---|---|---|---|---|---|
| *(sin entradas todavía)* | | | | | | | |

## Fin
"""


def _rutas_de_escritura(cfg):
    return [
        cfg["ruta_excel"], cfg["ruta_backups"], cfg["ruta_json"],
        cfg["ruta_reconciliacion"], cfg["ruta_correcciones"],
        cfg["ruta_errores_md"], cfg["ruta_logs"], cfg["ruta_docs"],
        cfg["ruta_excel_sitio_comunicacion"],
    ]


def montar(raiz_tmp, documentos, archivos_sin_entrada):
    """Crea el arbol de archivos del sandbox, escribe el JSON del corpus y
    registra el pais BENCH en acc.PAISES. Devuelve la config registrada."""
    raiz_tmp = Path(raiz_tmp).resolve()
    excel_dir = raiz_tmp / "Excel"
    docs_dir = raiz_tmp / "Facturas y Boletas"
    sitio_dir = raiz_tmp / "Sitio"
    for d in (excel_dir, excel_dir / "Respaldos", docs_dir, sitio_dir, raiz_tmp / "logs"):
        d.mkdir(parents=True, exist_ok=True)

    # Fotos: archivos vacios con extension valida. El pipeline solo los
    # inventaria, renombra y (para .heic) convierte -- nunca los decodifica.
    proyectos = {d["proyecto"] for d in documentos} | {p for p, _ in archivos_sin_entrada}
    for proyecto in proyectos:
        (docs_dir / proyecto).mkdir(parents=True, exist_ok=True)
    for d in documentos:
        (docs_dir / d["proyecto"] / d["archivo"]).write_bytes(b"")
    for proyecto, archivo in archivos_sin_entrada:
        (docs_dir / proyecto / archivo).write_bytes(b"")

    ruta_json = raiz_tmp / "datos_extraidos.json"
    ruta_json.write_text(json.dumps(documentos, ensure_ascii=False, indent=1), encoding="utf-8")
    ruta_correcciones = raiz_tmp / "correcciones_manuales.json"
    ruta_correcciones.write_text("[]", encoding="utf-8")
    ruta_errores_md = raiz_tmp / "ERRORES.md"
    ruta_errores_md.write_text(PLANTILLA_ERRORES_MD, encoding="utf-8")

    cfg = {
        "razon_social": "QUEMPIN BENCH",
        "moneda": "CLP", "simbolo": "$",
        "nombre_impuesto_corto": "IVA", "tasa_impuesto": 0.19,
        "ruta_excel": excel_dir / "Centro de Costos.xlsx",
        "ruta_docs": docs_dir,
        "ruta_backups": excel_dir / "Respaldos",
        "ruta_json": ruta_json,
        "ruta_reconciliacion": raiz_tmp / "reconciliacion_archivos.json",
        "ruta_correcciones": ruta_correcciones,
        "ruta_errores_md": ruta_errores_md,
        "ruta_logs": raiz_tmp / "logs",
        # No existe -> PASO 12c se omite solo, sin tocar ningun visualizador real.
        "ruta_visualizador_web": raiz_tmp / "Visualizador Web (inexistente)",
        "ruta_excel_sitio_comunicacion": sitio_dir / "Centro de Costos.xlsx",
        "prefijos_proyecto": {
            "Proyecto Alfa": "BALF", "Proyecto Beta": "BBET",
            "Proyecto Gamma": "BGAM", "Proyecto Delta": "BDEL",
        },
    }

    for ruta in _rutas_de_escritura(cfg):
        if ruta is None:
            continue
        try:
            Path(ruta).resolve().relative_to(raiz_tmp)
        except ValueError:
            raise AssertionError(
                "GUARD del sandbox: la ruta de escritura %s quedo FUERA de %s" % (ruta, raiz_tmp)
            )

    acc.PAISES[PAIS_BENCH] = cfg
    # RAIZ_ANALISIS_FINANCIERO no la toca configurar_pais() -- si la dejamos
    # apuntando al modulo real, PASO 12d intentaria correr Analisis Financiero
    # de verdad. Se apunta a un inexistente para que el guard .exists() corte.
    acc.RAIZ_ANALISIS_FINANCIERO = raiz_tmp / "Sistema Analisis Financiero (inexistente)"
    return cfg


def desmontar():
    acc.PAISES.pop(PAIS_BENCH, None)
    acc.configurar_pais("CL")
