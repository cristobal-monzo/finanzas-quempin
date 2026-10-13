# -*- coding: utf-8 -*-
"""bandeja.py (2026-10-13): lo que espera a una persona, junto. Datos ficticios."""
import json
from datetime import datetime

import bandeja


def _estado(ultima="2026-10-13T10:00:00", pasos=None, avisos=(), buzon=None):
    return {"procesador": {"ultimaCorrida": ultima, "pasos": pasos or {"esquemas": {"ok": True}}},
            "avisos": list(avisos), "buzon": buzon or {}}


def test_horas_habiles_no_cuentan_la_noche_ni_el_fin_de_semana():
    viernes_18 = datetime(2026, 10, 9, 18, 0)
    lunes_9 = datetime(2026, 10, 12, 9, 0)
    assert bandeja.minutos_habiles(viernes_18, lunes_9) == 60 + 30


def test_procesador_al_dia_no_genera_pendiente():
    assert bandeja.desde_estado(_estado(), datetime(2026, 10, 13, 11, 0)) == []


def test_procesador_detenido_es_alto():
    lista = bandeja.desde_estado(_estado(ultima="2026-10-12T09:00:00"), datetime(2026, 10, 13, 11, 0))
    assert len(lista) == 1 and lista[0].nivel == "alto" and "no corre desde" in lista[0].texto


def test_pasos_con_error_y_avisos_del_procesador():
    lista = bandeja.desde_estado(
        _estado(pasos={"folios": {"ok": False}}, avisos=["copia en conflicto sin juntar"]),
        datetime(2026, 10, 13, 10, 30))
    textos = " | ".join(p.texto for p in lista)
    assert "folios" in textos and "copia en conflicto" in textos and all(p.nivel == "alto" for p in lista)


def test_el_buzon_dice_que_hacer_por_herramienta():
    buzon = {"planilla-requerimientos": {"pendientes": 6, "masAntiguo": "2026-10-05T16:27:09-03:00"},
             "sistema-quempin": {"pendientes": 0}}
    lista = bandeja.desde_estado(_estado(buzon=buzon), datetime(2026, 10, 13, 10, 30))
    assert len(lista) == 1
    assert lista[0].texto.startswith("6 sugerencia(s)") and "Sugerencias_Requerimientos" in lista[0].accion


def test_sin_requerimiento_cuenta_proyectos_y_cotizaciones_de_chile():
    af = {"proyectos": [{"tag": "AAA", "req": None}, {"tag": "BBB", "req": "12"}]}
    docs = {"documentos": [
        {"tipo": "60", "pais": "Chile", "proyecto": {"req": None}},
        {"tipo": "60", "pais": "Chile", "proyecto": {"req": "12"}},
        {"tipo": "60", "pais": "Peru", "proyecto": {}},
        {"tipo": "61", "pais": "Chile", "proyecto": {}},
    ]}
    textos = [p.texto for p in bandeja.sin_requerimiento(af, docs)]
    assert textos[0].startswith("1 proyecto(s) del AF") and "AAA" in textos[0]
    assert textos[1].startswith("1 de 2 cotizacion(es) de Chile")


def test_lee_la_carpeta_y_pone_primero_lo_alto(tmp_path):
    pub = tmp_path / "publicado"
    pub.mkdir()
    sobre = lambda datos: json.dumps({"esquema": "quempin.intercambio/1", "datos": datos})
    (pub / "estado.json").write_text(sobre(_estado(ultima="2026-10-01T10:00:00")), encoding="utf-8")
    (pub / "analisis-financiero.json").write_text(sobre({"proyectos": [{"tag": "AAA"}]}), encoding="utf-8")
    extra = bandeja.Pendiente("medio", "20 reporte(s) PDF desactualizados.")
    lista = bandeja.pendientes(tmp_path, [extra], ahora=datetime(2026, 10, 13, 11, 0))
    assert [p.nivel for p in lista] == ["alto", "medio", "medio"]
    assert lista[-1] is extra


def test_sin_carpeta_lo_dice():
    lista = bandeja.pendientes(None)
    assert len(lista) == 1 and lista[0].nivel == "alto"
