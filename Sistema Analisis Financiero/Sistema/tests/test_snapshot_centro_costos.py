"""Las lecturas de Centro de Costos salen del snapshot cuando esta al dia.

El visualizador de Centro de Costos deja un snapshot saneado (PASO 12c)
inmediatamente antes de que corra este modulo (PASO 12d). Leer ese JSON
cuesta ~20 ms; abrir el .xlsx con openpyxl costaba ~0,5 s y se hacia tres
veces sobre el mismo archivo.

Lo que estos tests protegen es la condicion que hace segura la sustitucion:
el snapshot se usa SOLO si refleja el libro actual, y ante cualquier duda se
vuelve al Excel.
"""

import json

import openpyxl
import pytest

import analisis_financiero as af


def _snapshot(tmp_path, documentos):
    ruta = tmp_path / "centro-de-costos.json"
    ruta.write_text(json.dumps({"documentos": documentos}, ensure_ascii=False),
                    encoding="utf-8")
    return ruta


DOCS = [
    {"ref": "UMAG-001", "proyecto": "UMAG", "tipo_proyecto": "I+D+i",
     "items": [{"categoria_item": "Ferreteria", "total_sin_iva": 1000},
               {"categoria_item": "Materiales", "total_sin_iva": 500}]},
    {"ref": "UMAG-002", "proyecto": "UMAG", "tipo_proyecto": "I+D+i",
     "items": [{"categoria_item": "Ferreteria", "total_sin_iva": 250}]},
    {"ref": "CFLI-001", "proyecto": "Cesfam Limache", "tipo_proyecto": "Mantenimiento",
     "items": [{"categoria_item": "Combustible", "total_sin_iva": 800}]},
]


# ── lectura ────────────────────────────────────────────────────────────────

def test_lee_los_items_con_las_tres_columnas_que_usa_af(tmp_path):
    items, _, _ = af.leer_centro_costos_desde_snapshot(_snapshot(tmp_path, DOCS))

    assert len(items) == 4
    assert items[0] == {"n_ref": "UMAG-001", "categoria_item": "Ferreteria",
                        "total_sin_iva": 1000.0}


def test_arma_los_dos_mapas_por_prefijo(tmp_path):
    _, tipos, nombres = af.leer_centro_costos_desde_snapshot(_snapshot(tmp_path, DOCS))

    assert tipos == {"UMAG": "I+D+i", "CFLI": "Mantenimiento"}
    assert nombres == {"UMAG": "UMAG", "CFLI": "Cesfam Limache"}


def test_descarta_items_sin_total(tmp_path):
    docs = [{"ref": "UMAG-001", "proyecto": "UMAG", "tipo_proyecto": "I+D+i",
             "items": [{"categoria_item": "Ferreteria", "total_sin_iva": None},
                       {"categoria_item": "Ferreteria", "total_sin_iva": 100}]}]

    items, _, _ = af.leer_centro_costos_desde_snapshot(_snapshot(tmp_path, docs))

    assert len(items) == 1


@pytest.mark.parametrize("contenido", ['{"no_es": "lo esperado"}', "{", ""])
def test_devuelve_none_si_el_snapshot_no_sirve(tmp_path, contenido):
    ruta = tmp_path / "roto.json"
    ruta.write_text(contenido, encoding="utf-8")

    assert af.leer_centro_costos_desde_snapshot(ruta) is None


def test_devuelve_none_si_no_existe(tmp_path):
    assert af.leer_centro_costos_desde_snapshot(tmp_path / "no_existe.json") is None


# ── frescura ───────────────────────────────────────────────────────────────

def _par(tmp_path, snapshot_mas_nuevo):
    excel = tmp_path / "Centro de Costos.xlsx"
    openpyxl.Workbook().save(excel)
    snap = _snapshot(tmp_path, DOCS)
    import os
    t = excel.stat().st_mtime
    os.utime(snap, (t + 10, t + 10) if snapshot_mas_nuevo else (t - 10, t - 10))
    return snap, excel


def test_el_snapshot_sirve_si_es_mas_nuevo_que_el_libro(tmp_path):
    snap, excel = _par(tmp_path, snapshot_mas_nuevo=True)

    assert af.snapshot_al_dia(snap, excel) is True


def test_el_snapshot_no_sirve_si_el_libro_cambio_despues(tmp_path):
    """Alguien edito el Excel a mano, o el visualizador fallo. Usar el
    snapshot ahi metaria costos viejos en los KPIs."""
    snap, excel = _par(tmp_path, snapshot_mas_nuevo=False)

    assert af.snapshot_al_dia(snap, excel) is False


def test_sin_snapshot_no_esta_al_dia(tmp_path):
    excel = tmp_path / "Centro de Costos.xlsx"
    openpyxl.Workbook().save(excel)

    assert af.snapshot_al_dia(tmp_path / "no_existe.json", excel) is False
