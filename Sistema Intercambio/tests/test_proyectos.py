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


def test_cada_oc_dice_si_ya_esta_en_el_centro_de_costos(tmp_path):
    """2026-10-28: el Centro de Costos trae las OC con proyecto (su registro ordenes_compra.json); «Proyectos en
    ejecución» del Portal cuenta como comprometida solo la que todavía no está ahí. Sin registro de ese país, no se sabe."""
    registro = tmp_path / "ordenes_compra.json"
    registro.write_text(json.dumps({"ordenes": {"612609": {"estado": "en_cc"}, "612600": {"estado": "reemplazada"}}}),
                        encoding="utf-8")
    en_cc = pj.folios_en_centro_costos({"chile": registro, "peru": tmp_path / "no-existe.json"})
    assert en_cc == {"chile": {"612609", "612600"}}
    docs = [{"tipo": "61", "folio": "612609", "pais": "Chile", "proyecto": {"req": "261"}},
            {"tipo": "61", "folio": "612610", "pais": "Chile", "proyecto": {"req": "261"}},
            {"tipo": "61", "folio": "7001", "pais": "Perú", "proyecto": {"req": "261"}},
            {"tipo": "60", "folio": "602695", "pais": "Chile", "proyecto": {"req": "261"}}]
    (p,) = [p for p in pj.cruzar(REQS, [], [], docs, {}, en_cc)["proyectos"] if p["req"] == "261"]
    por_folio = {o["folio"]: o for o in p["ordenes"]}
    assert por_folio["612609"]["enCentroCostos"] is True
    assert por_folio["612610"]["enCentroCostos"] is False
    assert "enCentroCostos" not in por_folio["7001"]          # Perú sin registro en este equipo: no se sabe
    assert "enCentroCostos" not in p["cotizaciones"][0]
    # Sin ningún registro (antes de que el Centro de Costos traiga OC), el campo no va
    (p,) = [p for p in pj.cruzar(REQS, [], [], docs, {})["proyectos"] if p["req"] == "261"]
    assert all("enCentroCostos" not in o for o in p["ordenes"])


def test_carpetas_con_numero_bajan_por_las_agrupadoras(tmp_path):
    for ruta in ("0 OFERTAS ADJUDICADAS/261. FACH 1 - CALDERA", "0 OFERTAS PRESENTADAS/0 Ofertas Cerradas 2026/220. Vilcún",
                 "280. UMAG - Conexión", "Carpeta modelo", ".HERRAMIENTAS FORMULACIÓN/999. no", "29. Concepción"):
        (tmp_path / ruta).mkdir(parents=True)
    c = pj.carpetas_con_numero(tmp_path, profundidad=3)
    assert c["261"] == ["0 OFERTAS ADJUDICADAS/261. FACH 1 - CALDERA"]
    assert c["220"] == ["0 OFERTAS PRESENTADAS/0 Ofertas Cerradas 2026/220. Vilcún"]
    assert set(c) == {"261", "220", "280", "29"}


def test_proyectos_en_gestion_son_las_carpetas_de_la_raiz_sin_las_complementarias(tmp_path):
    """Pedido del usuario (2026-11-03): todos los proyectos de Gestión de Proyectos en «Proyectos en ejecución», sin las
    carpetas complementarias: las agrupadoras «0 …», lo oculto y los archivos quedan fuera; las sin N° entran."""
    for ruta in ("0 Carpeta modelo", "0 Proyectos Entregados 2026/303. Quemador Osorno", "036. Quilpué - Fiscalía",
                 "314. UA Reactor", "Rengo Incinerador", ".oculta"):
        (tmp_path / ruta).mkdir(parents=True)
    (tmp_path / "Proyecto ECIFA - Acceso directo.lnk").write_bytes(b"")
    (tmp_path / "manual.pdf").write_bytes(b"")
    assert pj.proyectos_en_gestion(tmp_path) == [
        {"carpeta": "036. Quilpué - Fiscalía", "req": "36"},
        {"carpeta": "314. UA Reactor", "req": "314"},
        {"carpeta": "Rengo Incinerador", "req": None}]
    assert pj.proyectos_en_gestion(None) == [] and pj.proyectos_en_gestion(tmp_path / "no-existe") == []


def test_publicar_desde_la_carpeta_cumple_su_esquema(tmp_path):
    raiz = ic.asegurar_carpeta(tmp_path / "Intercambio")
    ic.publicar(raiz, "requerimientos", "planilla-requerimientos", {"fuente": "x", "requerimientos": REQS})
    repo = raiz / "publicado" / "formulador"
    repo.mkdir(parents=True)
    f = _formulacion("a1", req=280)
    (repo / "a1.json").write_text(json.dumps({"esquema": ic.ESQUEMA, "herramienta": "formulador", "tipo": "proyecto",
                                              "historia": [], "datos": dict(f["datos"], modificado="2026-10-01")}),
                                  encoding="utf-8")
    r = pj.publicar(raiz, carpetas={}, gestion=[{"carpeta": "Rengo Incinerador", "req": None}])
    assert (r["proyectos"], r["gestion"]) == (2, 1)
    sobre = ic.leer_publicacion(raiz, "proyectos")
    assert esquemas.validar_publicacion("proyectos", sobre) == []
    assert sobre["datos"]["gestion"] == [{"carpeta": "Rengo Incinerador", "req": None}]
    assert sobre["datos"]["proyectos"][0]["formulaciones"][0]["uid"] == "a1"


# Caso real del 2026-11-03: la ficha UMAG («UMAG Linea de H2», carpeta «UMAG»
# con facturas) llevaba el N° 280, que es otro proyecto con su propia carpeta.
CARPETAS_CC = [{"nombre": "UMAG", "req": None, "documentos": 45},
               {"nombre": "280. UMAG - Conexión y PH Lab 1", "req": "280", "documentos": 1},
               {"nombre": "Instalación H2 KeyProcess", "req": None, "documentos": 0},
               {"nombre": "289. KeyProcess", "req": "289", "documentos": 8}]


def test_la_ficha_de_otra_carpeta_no_se_une_con_el_n_venga_de_quien_venga():
    datos = pj.cruzar(
        REQS + [{"numero": 289, "estado": "Adjudicado", "titulo": "KeyProcess"}],
        [{"tag": "UMAG", "req": "280", "nombre": "UMAG"},
         {"tag": "KPH2", "req": "289", "nombre": "Instalación H2 KeyProcess"}],
        [_formulacion("a1", req=280, tag="UMAG")],
        [{"tipo": "60", "folio": "6020099", "pais": "Chile", "proyecto": {"req": "280", "tag": "UMAG"}}],
        {}, carpetas_cc=CARPETAS_CC,
    )
    por_req = {p["req"]: p for p in datos["proyectos"]}
    assert por_req["280"]["tag"] is None
    assert por_req["280"]["fichaAjena"] == ["UMAG"]
    assert [c["req"] for c in datos["conflictos"]] == ["280"]
    assert "proyectos distintos" in datos["conflictos"][0]["detalle"]
    assert por_req["289"]["tag"] == "KPH2"         # su carpeta vacía no es otro proyecto
    assert "fichaAjena" not in por_req["289"]


def test_la_ficha_propia_del_n_si_se_une():
    datos = pj.cruzar(REQS, [{"tag": "UMAG", "req": None, "nombre": "UMAG"},
                             {"tag": "UML1", "req": "280", "nombre": "UMAG - Conexión y PH Lab1"}],
                      [_formulacion("a1", req=280, tag="UMAG")], [], {}, carpetas_cc=CARPETAS_CC)
    (p,) = [p for p in datos["proyectos"] if p["req"] == "280"]
    assert p["tag"] == "UML1"                      # la formulación que recuerda UMAG no la confunde
    assert p["fichaAjena"] == ["UMAG"]
