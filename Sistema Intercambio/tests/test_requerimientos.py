# -*- coding: utf-8 -*-
"""Lector de la Planilla de Ingreso y sugerencias que se cierran solas.

Siempre sobre una planilla armada en tmp_path: nunca la real."""
import json
from datetime import datetime

import openpyxl
import pytest

import esquemas
import intercambio as ic
import requerimientos as rq

ENCABEZADOS = ["N°", "Estado", "Canal", "Capt.", "Eval.", "Título", "Ubicación", "ID o Referencia", "Apertura",
               "Cierre", "Visita", "Visitador", "Presupuesto (IVA inc.)", "Valor ofertado (IVA inc)",
               "Valor adjudicado (IVA inc)", "Entrega (días)", "Plazo Oferta (días)"]


def _planilla(tmp_path, filas, encabezados=ENCABEZADOS):
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = rq.HOJA
    hoja.append(encabezados)
    for fila in filas:
        hoja.append(fila)
    ruta = tmp_path / "Planilla.xlsx"
    libro.save(ruta)
    return ruta


def _fila(numero, estado="Ofertado", titulo="Caldera", ofertado=None, adjudicado=None, ubicacion="Valdivia"):
    return [numero, estado, "Mercado Público", "JB", "CM", titulo, ubicacion, "123-45-LE26",
            datetime(2026, 9, 1), datetime(2026, 9, 15, 15, 30), None, None, 1000000, ofertado, adjudicado, 30, 0]


def test_lee_por_nombre_de_columna_y_limpia_valores(tmp_path):
    ruta = _planilla(tmp_path, [_fila(280, ofertado=3510500, ubicacion="#VALUE!"), [None, "Descartado"], _fila("281")])
    reqs = rq.leer_planilla(ruta)
    assert [r["numero"] for r in reqs] == [280, 281]
    r = reqs[0]
    assert r["ubicacion"] is None                    # error de fórmula = vacío
    assert r["apertura"] == "2026-09-01"             # fecha sin hora
    assert r["cierre"] == "2026-09-15T15:30"         # con hora
    assert r["valorOfertado"] == 3510500 and r["valorAdjudicado"] is None
    assert r["referencia"] == "123-45-LE26"


def test_columnas_en_otro_orden_no_corren_nada(tmp_path):
    orden = list(reversed(ENCABEZADOS))
    ruta = _planilla(tmp_path, [list(reversed(_fila(7, titulo="Horno")))], encabezados=orden)
    (r,) = rq.leer_planilla(ruta)
    assert r["numero"] == 7 and r["titulo"] == "Horno" and r["estado"] == "Ofertado"


def test_numero_repetido_se_avisa(tmp_path):
    ruta = _planilla(tmp_path, [_fila(5, titulo="Primera"), _fila(5, titulo="Segunda")])
    avisos = []
    (r,) = rq.leer_planilla(ruta, avisos)
    assert r["titulo"] == "Primera" and "N° 5" in avisos[0]


def test_sin_columna_numero_es_error_claro(tmp_path):
    ruta = _planilla(tmp_path, [["x"]], encabezados=["Estado"])
    with pytest.raises(ValueError, match="N°"):
        rq.leer_planilla(ruta)


def test_resumen_y_tasa_de_adjudicacion(tmp_path):
    reqs = [{"numero": i, "estado": e} for i, e in enumerate(["Adjudicado", "No adjudicado", "No adjudicado", "Descartado", "Adjudicado"], 1)]
    res = rq.resumen(reqs)
    assert res["porEstado"]["Adjudicado"] == 2 and res["tasaAdjudicacion"] == 0.5
    assert rq.resumen([{"numero": 1, "estado": "Ofertado"}])["tasaAdjudicacion"] is None


def test_publicar_cumple_su_esquema(tmp_path):
    ruta = _planilla(tmp_path, [_fila(280)])
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    rq.publicar(raiz, ruta)
    sobre = ic.leer_publicacion(raiz, "requerimientos")
    assert esquemas.validar_publicacion("requerimientos", sobre) == []
    assert sobre["datos"]["requerimientos"][0]["numero"] == 280


# ── sugerencias ──────────────────────────────────────────────────────────────

def _sugerencia(numero=280, cambios=None, reemplaza=None, id_="sug00001"):
    m = {"esquema": ic.ESQUEMA, "id": id_, "tipo": rq.TIPO_SUGERENCIA, "destino": rq.DESTINO,
         "origen": {"herramienta": "formulador", "enviado": "2026-10-01T10:00:00-03:00"},
         "requerimiento": {"numero": numero}, "cambios": cambios or {"estado": "Adjudicado", "valorAdjudicado": 3000000},
         "fuente": {"herramienta": "formulador", "codigo": "QPN-2026-001"}}
    if reemplaza is not None:
        m["reemplaza"] = reemplaza
    return m


def test_sugerencia_pendiente_dice_que_escribir():
    d = rq.decidir_sugerencia(_sugerencia(), {"numero": 280, "estado": "Ofertado", "valorAdjudicado": None})
    assert d["accion"] == "pendiente"
    assert d["falta"] == {"estado": "Adjudicado", "valorAdjudicado": 3000000}
    assert any("Valor adjudicado" in x and "$3.000.000" in x for x in d["detalle"])


def test_sugerencia_ya_en_la_planilla_queda_aplicada():
    d = rq.decidir_sugerencia(_sugerencia(), {"numero": 280, "estado": "adjudicado ", "valorAdjudicado": 3000000.0})
    assert d["accion"] == "aplicado"


def test_sugerencia_en_conflicto_si_la_planilla_cambio_despues():
    m = _sugerencia(cambios={"valorOfertado": 3500000}, reemplaza={"valorOfertado": None})
    d = rq.decidir_sugerencia(m, {"numero": 280, "estado": "Ofertado", "valorOfertado": 3400000})
    assert d["accion"] == "conflicto"


def test_sugerencia_invalida_se_rechaza():
    m = _sugerencia(cambios={"estado": "Ganado"})
    assert rq.decidir_sugerencia(m, None)["accion"] == "rechazado"


def test_revisar_archiva_solo_aplicadas_y_rechazadas(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ic.enviar(raiz, _sugerencia(id_="aplicada1"))
    ic.enviar(raiz, _sugerencia(numero=281, id_="pendiente1"))
    malo = _sugerencia(id_="rechazada1")
    malo["cambios"] = {"estado": "Ganado"}
    (raiz / "buzon" / "x_rechazada1.json").write_text(json.dumps(malo), encoding="utf-8")
    reqs = [{"numero": 280, "estado": "Adjudicado", "valorAdjudicado": 3000000},
            {"numero": 281, "estado": "Ofertado", "valorAdjudicado": None}]
    decisiones = {d["mensaje"]["id"]: d["accion"] for d in rq.revisar_sugerencias(raiz, reqs)}
    assert decisiones == {"aplicada1": "aplicado", "pendiente1": "pendiente", "rechazada1": "rechazado"}
    quedan = [m["id"] for m in ic.leer_buzon(raiz)[0]]
    assert quedan == ["pendiente1"]
    assert set(ic.resultados_recientes(raiz)) == {"aplicada1", "rechazada1"}


def test_descartar_sugerencia(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ic.enviar(raiz, _sugerencia(id_="descartar1"))
    assert rq.descartar_sugerencia(raiz, "descartar1")
    assert not rq.descartar_sugerencia(raiz, "descartar1")
    assert ic.resultados_recientes(raiz)["descartar1"]["estado"] == "descartado"
