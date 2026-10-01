# -*- coding: utf-8 -*-
"""Registro de proyectos: el cruce de claves entre herramientas."""
import json

import esquemas
import intercambio as ic
import proyectos as pj

REQS = [
    {"numero": 280, "estado": "Ofertado", "titulo": "Conexión H2 - LAB 1 - UMAG"},
    {"numero": 261, "estado": "Adjudicado", "titulo": "FACH 1"},
    {"numero": 12, "estado": "Descartado", "titulo": "Viejo"},
    {"numero": 13, "estado": "No adjudicado", "titulo": "Perdido pero cotizado"},
]


def _formulacion(uid, req=None, tag=None, estado="Adjudicada"):
    vinculos = {}
    if req:
        vinculos["requerimiento"] = {"numero": req}
    if tag:
        vinculos["analisisFinanciero"] = {"tag": tag}
    return {"uid": uid, "datos": {"uid": uid, "codigo": f"QPN-{uid}", "version": 1, "titulo": "T", "estado": estado,
                                  "vinculos": vinculos}}


def test_cruce_por_requerimiento():
    datos = pj.cruzar(
        REQS,
        [{"tag": "FCH1", "req": "261", "nombre": "FACH 1"}, {"tag": "UMAG", "req": None, "nombre": "UMAG"}],
        [_formulacion("a1", req=280, tag="UMAG"), _formulacion("b2")],
        [{"tipo": "60", "folio": "602695", "pais": "Chile", "proyecto": {"req": "280", "tag": None},
          "contraparte": {"razon_social": "UMAG"}},
         {"tipo": "61", "folio": "612609", "pais": "Chile", "proyecto": {"req": "13"}},
         {"tipo": "60", "folio": "602696", "pais": "Chile", "proyecto": {}}],
        {"oferta": {"280": ["0 OFERTAS PRESENTADAS/280. UMAG"]}, "facturas": {"261": ["261. FACH 1"]}},
    )
    por_req = {p["req"]: p for p in datos["proyectos"]}
    assert set(por_req) == {"280", "261", "13"}            # 12 (descartado, sin nada) no entra
    assert por_req["280"]["tag"] == "UMAG"                 # el TAG lo da el vínculo del Formulador
    assert por_req["280"]["cotizaciones"][0]["folio"] == "602695"
    assert por_req["280"]["carpetas"] == {"oferta": ["0 OFERTAS PRESENTADAS/280. UMAG"]}
    assert por_req["261"]["tag"] == "FCH1" and por_req["261"]["carpetas"]["facturas"] == ["261. FACH 1"]
    assert por_req["13"]["ordenes"][0]["folio"] == "612609" and por_req["13"]["estado"] == "No adjudicado"
    assert [p["req"] for p in datos["proyectos"]] == ["280", "261", "13"]
    assert datos["sinVincular"]["tags"] == []              # UMAG ya quedó vinculado por el Formulador
    assert [f["uid"] for f in datos["sinVincular"]["formulaciones"]] == ["b2"]
    assert datos["sinVincular"]["documentos"] == 1


def test_un_req_con_dos_tag_es_conflicto_y_no_se_adivina():
    datos = pj.cruzar(REQS, [{"tag": "AAA", "req": "280"}, {"tag": "BBB", "req": "280"}], [], [], {})
    (p,) = [p for p in datos["proyectos"] if p["req"] == "280"]
    assert p["tag"] is None
    assert datos["conflictos"][0]["tags"] == ["AAA", "BBB"]


def test_un_tag_con_varios_req_no_es_conflicto():
    datos = pj.cruzar(REQS, [{"tag": "JUNJ", "req": "280"}, {"tag": "JUNJ", "req": "261"}], [], [], {})
    assert datos["conflictos"] == []


def test_carpetas_con_numero_bajan_por_las_agrupadoras(tmp_path):
    for ruta in ("0 OFERTAS ADJUDICADAS/261. FACH 1 - CALDERA", "0 OFERTAS PRESENTADAS/0 Ofertas Cerradas 2026/220. Vilcún",
                 "280. UMAG - Conexión", "Carpeta modelo", ".HERRAMIENTAS FORMULACIÓN/999. no", "29. Concepción"):
        (tmp_path / ruta).mkdir(parents=True)
    c = pj.carpetas_con_numero(tmp_path, profundidad=3)
    assert c["261"] == ["0 OFERTAS ADJUDICADAS/261. FACH 1 - CALDERA"]
    assert c["220"] == ["0 OFERTAS PRESENTADAS/0 Ofertas Cerradas 2026/220. Vilcún"]
    assert set(c) == {"261", "220", "280", "29"}


def test_publicar_desde_la_carpeta_cumple_su_esquema(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ic.publicar(raiz, "requerimientos", "planilla-requerimientos", {"fuente": "x", "requerimientos": REQS})
    repo = raiz / "publicado" / "formulador"
    repo.mkdir(parents=True)
    f = _formulacion("a1", req=280)
    (repo / "a1.json").write_text(json.dumps({"esquema": ic.ESQUEMA, "herramienta": "formulador", "tipo": "proyecto",
                                              "historia": [], "datos": dict(f["datos"], modificado="2026-10-01")}),
                                  encoding="utf-8")
    r = pj.publicar(raiz, carpetas={})
    assert r["proyectos"] == 2
    sobre = ic.leer_publicacion(raiz, "proyectos")
    assert esquemas.validar_publicacion("proyectos", sobre) == []
    assert sobre["datos"]["proyectos"][0]["formulaciones"][0]["uid"] == "a1"
