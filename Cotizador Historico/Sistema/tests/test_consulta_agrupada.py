# -*- coding: utf-8 -*-
"""La consulta puntual agrupa por hoja y respeta la medida pedida.

Antes de esto, `consultar "codo"` promediaba en un solo numero codos de 1/2"
y de 2" -- el promedio no respondia ninguna pregunta real.
"""
from datetime import date, datetime

import cotizador_historico as ch


def _item(n_ref, nombre, descripcion, precio, fecha):
    return {
        "n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
        "precio_unitario_sin_iva": precio, "fecha": fecha, "excluido_motivo": None,
        "total_sin_iva": None, "total_con_iva": None,
    }


UF = {"2026-01-01": 36000.0, "2026-03-01": 36000.0, "2026-07-17": 36000.0}


def _preparar(monkeypatch, tmp_path, items):
    monkeypatch.setattr(ch, "cargar_items_detalle", lambda ruta_excel=None, pais="CL": items)
    monkeypatch.setattr(ch, "RUTA_CACHE_UF", tmp_path / "uf_cache.json")
    monkeypatch.setattr(ch, "consultar_uf_api", lambda f: UF[f.strftime("%Y-%m-%d")])


CODOS = [
    _item("A-1", "Codo bronce", "Codo SO BR (05) 1/2 plg", 1000, datetime(2026, 1, 1)),
    _item("A-2", "Codo bronce", "Codo SO BR (05) 1/2 plg", 1200, datetime(2026, 3, 1)),
    _item("A-3", "Codo bronce", "Codo SO BR (08) 2 plg", 9000, datetime(2026, 3, 1)),
]


def test_agrupa_por_hoja_en_vez_de_un_solo_promedio(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, CODOS)
    r = ch.consultar_item("codo bronce", fecha_hoy=date(2026, 7, 17))

    hojas = {g["hoja"]: g for g in r["grupos"]}
    assert set(hojas) == {'Codo de Bronce 1/2"', 'Codo de Bronce 2"'}
    assert hojas['Codo de Bronce 1/2"']["n_compras"] == 2
    assert hojas['Codo de Bronce 1/2"']["promedio_reajustado"] == 1100
    assert hojas['Codo de Bronce 2"']["promedio_reajustado"] == 9000


def test_la_medida_de_la_consulta_filtra_las_compras(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, CODOS)
    r = ch.consultar_item('codo bronce 1/2"', fecha_hoy=date(2026, 7, 17))

    assert r["medida_consultada"] == '1/2"'
    assert [c["n_ref"] for c in r["compras"]] == ["A-1", "A-2"]
    assert r["descartadas_por_medida"] == 1
    assert r["promedio_reajustado"] == 1100      # sin el codo de 2" contaminando


def test_una_pulgada_y_cuarto_no_matchea_un_cuarto(monkeypatch, tmp_path):
    items = [
        _item("B-1", "Canieria cobre", "Cañería L cobre (05) 1.1/4 plg", 8000, datetime(2026, 1, 1)),
        _item("B-2", "Canieria cobre", "Cañería L cobre (02) 1/4 plg", 2000, datetime(2026, 1, 1)),
    ]
    _preparar(monkeypatch, tmp_path, items)
    r = ch.consultar_item("cañeria cobre 1.1/4", fecha_hoy=date(2026, 7, 17))

    assert r["medida_consultada"] == '1.1/4"'
    assert [c["n_ref"] for c in r["compras"]] == ["B-1"]
    assert r["promedio_reajustado"] == 8000


def test_sin_medida_en_la_consulta_no_filtra_nada(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, CODOS)
    r = ch.consultar_item("codo bronce", fecha_hoy=date(2026, 7, 17))

    assert r["medida_consultada"] is None
    assert r["descartadas_por_medida"] == 0
    assert len(r["compras"]) == 3


def test_cada_compra_trae_su_clasificacion(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, CODOS)
    r = ch.consultar_item("codo bronce", fecha_hoy=date(2026, 7, 17))

    compra = r["compras"][0]
    assert compra["categoria"] == "Piping y Fittings"
    assert compra["familia"] == "Codo"
    assert compra["material"] == "Bronce"
    assert compra["medida"] == '1/2"'


def test_los_gastos_se_agrupan_pero_quedan_marcados_no_cotizables(monkeypatch, tmp_path):
    items = [
        _item("C-1", "Peaje", "Peaje de autopista", 3000, datetime(2026, 1, 1)),
        _item("C-2", "Peaje", "Peaje de autopista", 900, datetime(2026, 1, 1)),
    ]
    _preparar(monkeypatch, tmp_path, items)
    r = ch.consultar_item("peaje", fecha_hoy=date(2026, 7, 17))

    assert r["grupos"][0]["cotizable"] is False
    assert r["grupos"][0]["dispersion"] == 3.3


def test_filtrar_por_medida_sin_resultados_no_inventa_un_promedio(monkeypatch, tmp_path):
    _preparar(monkeypatch, tmp_path, CODOS)
    r = ch.consultar_item('codo bronce 3/8"', fecha_hoy=date(2026, 7, 17))

    assert r["encontrado"] is False
    assert r["compras"] == []
    assert r["promedio_reajustado"] is None
    assert r["descartadas_por_medida"] == 3
