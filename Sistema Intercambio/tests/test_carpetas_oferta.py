# -*- coding: utf-8 -*-
"""La carpeta de cada requerimiento nace con su fila en la Planilla y sigue su Estado (carpetas_oferta.py, 2026-11-25),
y el Estado que cambia en la Planilla llega al Formulador (formulaciones.alinear_estados). Bibliotecas e Intercambio
falsos en una carpeta temporal."""
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import carpetas_oferta as co
import cierre_entregados as ce
import esquemas
import formulaciones
import intercambio
import procesar
import requerimientos as rq

ANIO = datetime.now().year
AHORA = datetime.now().astimezone()


# El título de la fila de cada carpeta del fixture: una carpeta cuyo nombre no se parece a su fila no se mueve sola
TITULOS = {289: "Instalación de prueba", 296: "Caldera de prueba", 310: "Caldera en evaluación", 120: "Perdida de antes"}


def _req(n, estado, titulo=None, cierre=None):
    fila = {"numero": n, "estado": estado, "titulo": titulo or TITULOS.get(n) or f"Proyecto {n}"}
    if cierre:
        fila["cierre"] = cierre
    return fila


def _planilla(raiz, reqs):
    intercambio.publicar(raiz, "requerimientos", "procesador", {"requerimientos": reqs}, validar=False)   # parcial


@pytest.fixture
def e(tmp_path):
    raiz = intercambio.asegurar_carpeta(tmp_path / "Intercambio")
    form = tmp_path / "Formulación de proyectos - Documentos"
    ges = tmp_path / "Gestión de Proyectos - Documentos"
    (form / "310. Caldera en evaluación" / "ANTECEDENTES").mkdir(parents=True)
    (form / "310. Caldera en evaluación" / "ANTECEDENTES" / "bases.pdf").write_bytes(b"bases" * 100)
    (form / "0 OFERTAS PRESENTADAS" / "289. Instalación de prueba").mkdir(parents=True)
    (form / "0 OFERTAS PRESENTADAS" / "0 Ofertas Cerradas 2025" / "120. Perdida de antes").mkdir(parents=True)
    (form / "0 OFERTAS ADJUDICADAS").mkdir()
    (form / ".HERRAMIENTAS FORMULACIÓN").mkdir()
    (ges / "289. Instalación de prueba" / "Formulación").mkdir(parents=True)
    (ges / "0 Carpeta modelo").mkdir()
    (ges / f"0 Proyectos Entregados {ANIO}" / "296. Caldera de prueba").mkdir(parents=True)
    _planilla(raiz, [_req(289, "Adjudicado", "Instalación de prueba"), _req(296, "Cerrado"), _req(310, "Evaluación"),
                     _req(120, "No adjudicado")])
    return {"raiz": raiz, "form": form, "ges": ges}


def _buzon(raiz, tipo=None):
    return intercambio.leer_buzon(raiz, tipo=tipo)[0]


def _procesados(raiz, tipo=co.TIPO_MOVER):
    return [x for x in (intercambio._leer_json(p) for p in (raiz / intercambio.CARPETA_PROCESADO).rglob("*.json"))
            if x["tipo"] == tipo]


def _mover(raiz, n, estado, minutos=-60, crear=None):
    enviado = (datetime.now().astimezone() + timedelta(minutes=minutos)).isoformat(timespec="seconds")
    m = {"esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": co.TIPO_MOVER, "destino": co.DESTINO,
         "origen": {"herramienta": "portal", "usuario": "NB", "enviado": enviado},
         "requerimiento": {"numero": n}, "estado": estado}
    if crear is not None:
        m["crear"] = crear
    assert esquemas.validar_mensaje(m) == []
    intercambio.enviar(raiz, m)
    return m


def _editar(raiz, n, estado, herramienta="portal", tipo="editar-requerimiento"):
    m = {"esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": tipo,
         "destino": rq.DESTINO, "origen": {"herramienta": herramienta, "enviado": intercambio.ahora_iso()},
         "requerimiento": {"numero": n}, "cambios": {"estado": estado}, "reemplaza": {"estado": "Adjudicado"}}
    if tipo == "actualizar-requerimiento":
        m["fuente"] = {"herramienta": herramienta, "uid": "u1", "codigo": "QPN-1"}
    intercambio.enviar(raiz, m)


def _vuelta(e, previo=None, **kw):
    return co.vuelta(e["raiz"], e["form"], e["ges"], {"conocidos": []} if previo is None else previo, **kw)


# ── nombres y dónde está cada una ────────────────────────────────────────────

def test_nombre_de_la_carpeta():
    assert co.nombre_carpeta(331, "Caldera X") == "331. Caldera X"
    assert co.nombre_carpeta(331, "331. Caldera X") == "331. Caldera X"           # sin el N° repetido
    assert co.nombre_carpeta(331, 'Sala: "A/B" #2') == "331. Sala- -A-B- -2"
    assert len(co.nombre_carpeta(5, "x" * 200)) == co.LARGO_NOMBRE
    assert co.nombre_carpeta(5, "   ") == ""


def test_el_indice_ve_la_raiz_y_los_grupos_hasta_tres_niveles(e):
    (e["form"] / "001t. Temporal").mkdir()
    idx = co.indice(e["form"])
    assert idx == {310: [["310. Caldera en evaluación"]], 289: [["0 OFERTAS PRESENTADAS", "289. Instalación de prueba"]],
                   120: [["0 OFERTAS PRESENTADAS", "0 Ofertas Cerradas 2025", "120. Perdida de antes"]]}
    assert co.indice(e["ges"]) == {289: [["289. Instalación de prueba"]],
                                   296: [[f"0 Proyectos Entregados {ANIO}", "296. Caldera de prueba"]]}
    assert co.indice(None) == {}


def test_el_anio_del_grupo_es_el_del_cierre_de_la_licitacion():
    assert co.anio_de({"cierre": "2025-12-30T15:00"}, AHORA) == 2025
    assert co.anio_de({"cierre": "30-01-2025"}, AHORA) == ANIO
    assert co.anio_de(None, AHORA) == ANIO


@pytest.mark.parametrize("estado, ruta_f, ruta_g, esperado_f, esperado_g", [
    ("Ofertado", ["310. X"], None, ["0 OFERTAS PRESENTADAS"], None),
    ("Evaluación", ["0 OFERTAS PRESENTADAS", "310. X"], None, [], None),
    ("No adjudicado", ["0 OFERTAS PRESENTADAS", "310. X"], None, ["0 OFERTAS PRESENTADAS", "0 Ofertas Cerradas 2025"], None),
    ("Descartado", ["0 OFERTAS PRESENTADAS", "0 Ofertas Cerradas 2024", "310. X"], None, None, None),   # cualquier año
    ("Adjudicado", ["310. X"], None, ["0 OFERTAS ADJUDICADAS"], ("crear", [])),
    ("Adjudicado", ["0 OFERTAS ADJUDICADAS", "310. X"], ["310. X"], None, None),
    ("Cerrado", ["0 OFERTAS ADJUDICADAS", "310. X"], ["310. X"], None, ("mover", [f"0 Proyectos Entregados {ANIO}"])),
    ("Cerrado", ["0 OFERTAS PRESENTADAS", "310. X"], None, ["0 OFERTAS ADJUDICADAS"], None),
    ("Adjudicado", None, [f"0 Proyectos Entregados {ANIO}", "310. X"], None, ("mover", [])),            # reabierto
    ("Ofertado", None, ["310. X"], None, None),                                                         # Gestión no se toca
    ("Otro estado", ["310. X"], None, None, None),
])
def test_adonde_va_cada_estado(estado, ruta_f, ruta_g, esperado_f, esperado_g):
    p = co.plan(estado, ruta_f, ruta_g, 2025, True, ANIO)
    assert (p["formulacion"] or {}).get("hasta") == esperado_f
    assert ((p["gestion"]["accion"], p["gestion"]["hasta"]) if p["gestion"] else None) == esperado_g


def test_una_carpeta_de_gestion_sin_la_copia_la_recibe_al_adjudicarse():
    p = co.plan("Adjudicado", ["0 OFERTAS ADJUDICADAS", "310. X"], ["310. X"], ANIO, con_copia=False)
    assert p["gestion"]["accion"] == "copiar" and p["formulacion"] is None


# ── 1. las carpetas nuevas ───────────────────────────────────────────────────

def test_la_primera_vez_todo_queda_conocido(e):
    _planilla(e["raiz"], [_req(289, "Adjudicado"), _req(330, "Evaluación")])
    detalle, estado, _ = _vuelta(e, previo={})
    assert estado["conocidos"] == [289, 330] and "carpetas nuevas" not in detalle
    assert not any(h.name.startswith("330") for h in e["form"].iterdir())


def test_una_fila_nueva_tiene_su_carpeta_con_las_subcarpetas_de_siempre(e):
    _planilla(e["raiz"], [_req(330, "Evaluación", "Caldera: nueva"), _req(331, "Ofertado", "Oferta directa"),
                          _req(332, "Descartado"), _req(289, "Adjudicado"), {"numero": 333, "estado": "Evaluación", "titulo": ""}])
    ahora = datetime.now().astimezone()
    detalle, estado, _ = _vuelta(e, ahora=ahora)
    assert "carpetas nuevas" not in detalle and set(estado["esperanCarpeta"]) == {"330", "331"}   # espera a OneDrive
    despues = ahora + co.ESPERA_CREAR + timedelta(minutes=1)
    detalle, estado, _ = _vuelta(e, estado, ahora=despues)
    nueva = e["form"] / "330. Caldera- nueva"
    assert sorted(h.name for h in nueva.iterdir()) == sorted(co.ESTRUCTURA)
    assert (e["form"] / "0 OFERTAS PRESENTADAS" / "331. Oferta directa").is_dir()          # en el grupo de su estado
    assert not any(h.name.startswith("332") for h in e["form"].iterdir())                  # descartado: sin carpeta
    assert not (e["form"] / "289. Proyecto 289").exists()                                  # ya tenía la suya
    assert estado["esperanCarpeta"] == {} and {330, 331, 332, 289} <= set(estado["conocidos"])
    assert 333 not in estado["conocidos"]                                                  # sin título: espera
    assert "carpetas nuevas" in detalle and "330. Caldera- nueva" in detalle
    # La vuelta siguiente no hace nada
    assert _vuelta(e, estado, ahora=despues)[0] == "sin cambios"


def test_si_alguien_ya_la_creo_a_mano_no_se_duplica(e):
    _planilla(e["raiz"], [_req(330, "Evaluación")])
    ahora = datetime.now().astimezone()
    _, estado, _ = _vuelta(e, ahora=ahora)
    (e["ges"] / "330 - Hecha a mano").mkdir()
    _, estado, _ = _vuelta(e, estado, ahora=ahora + timedelta(hours=1))
    assert not (e["form"] / "330. Proyecto 330").exists() and 330 in estado["conocidos"]


def test_sin_la_biblioteca_o_sin_la_planilla_no_hace_nada(e, tmp_path):
    assert "no está sincronizada" in co.vuelta(e["raiz"], None, e["ges"], {})[0]
    vacia = intercambio.asegurar_carpeta(tmp_path / "otra")
    assert "no está publicada" in co.vuelta(vacia, e["form"], e["ges"], {})[0]


# ── 2. mover lo que pidió el Portal ─────────────────────────────────────────

def test_cerrado_mueve_la_de_gestion_a_los_entregados_y_el_original_a_adjudicadas(e):
    _editar(e["raiz"], 289, "Cerrado")
    _mover(e["raiz"], 289, "Cerrado")
    detalle, _, _ = _vuelta(e)
    assert (e["ges"] / f"0 Proyectos Entregados {ANIO}" / "289. Instalación de prueba" / "Formulación").is_dir()
    assert not (e["ges"] / "289. Instalación de prueba").exists()
    assert (e["form"] / "0 OFERTAS ADJUDICADAS" / "289. Instalación de prueba").is_dir()
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "aplicado" and p["resultado"]["requerimiento"] == 289
    assert "0 Proyectos Entregados" in p["resultado"]["detalle"][0] and "movidas" in detalle
    # El paso siguiente del procesador no pide otra vez «Cerrado»: ya espera en el buzón
    resumen, estado = ce.pedir_cierres(e["raiz"], e["ges"], {})
    assert resumen["pedidos"] == [] and len(_buzon(e["raiz"], "editar-requerimiento")) == 1


def test_mueve_cuando_la_planilla_ya_dice_ese_estado(e):
    _planilla(e["raiz"], [_req(310, "Ofertado")])
    _mover(e["raiz"], 310, "Ofertado")
    _vuelta(e)
    assert (e["form"] / "0 OFERTAS PRESENTADAS" / "310. Caldera en evaluación" / "ANTECEDENTES" / "bases.pdf").exists()


def test_no_adjudicado_va_a_las_cerradas_del_anio_de_su_cierre_y_crea_el_grupo(e):
    _planilla(e["raiz"], [_req(289, "No adjudicado", cierre="2024-06-01T12:00")])
    _mover(e["raiz"], 289, "No adjudicado")
    _vuelta(e)
    assert (e["form"] / "0 OFERTAS PRESENTADAS" / "0 Ofertas Cerradas 2024" / "289. Instalación de prueba").is_dir()
    assert (e["ges"] / "289. Instalación de prueba").is_dir()                     # la de Gestión no se toca


def test_adjudicado_lleva_el_original_y_arma_la_copia_en_gestion(e):
    _planilla(e["raiz"], [_req(310, "Adjudicado")])
    _mover(e["raiz"], 310, "Adjudicado")
    _vuelta(e)
    original = e["form"] / "0 OFERTAS ADJUDICADAS" / "310. Caldera en evaluación"
    copia = e["ges"] / "310. Caldera en evaluación" / "Formulación"
    assert (original / "ANTECEDENTES" / "bases.pdf").exists()
    assert (copia / "ANTECEDENTES" / "bases.pdf").read_bytes() == b"bases" * 100


def test_una_copia_que_no_alcanza_sigue_en_la_vuelta_siguiente(e):
    _planilla(e["raiz"], [_req(310, "Adjudicado")])
    _mover(e["raiz"], 310, "Adjudicado")
    detalle, _, _ = _vuelta(e, segundos=-1)
    assert "sigue en la próxima vuelta" in detalle and len(_buzon(e["raiz"], co.TIPO_MOVER)) == 1
    assert (e["form"] / "310. Caldera en evaluación").is_dir()                     # el original no se movió
    assert (e["ges"] / "310. Caldera en evaluación" / "Formulación (copiando)").is_dir()
    _vuelta(e)
    assert (e["ges"] / "310. Caldera en evaluación" / "Formulación" / "ANTECEDENTES" / "bases.pdf").exists()
    assert not (e["ges"] / "310. Caldera en evaluación" / "Formulación (copiando)").exists()
    assert (e["form"] / "0 OFERTAS ADJUDICADAS" / "310. Caldera en evaluación").is_dir()


def test_si_el_cambio_se_retiro_no_mueve_nada(e):
    m = _mover(e["raiz"], 310, "Ofertado", minutos=-5)
    _vuelta(e)
    assert [x["id"] for x in _buzon(e["raiz"], co.TIPO_MOVER)] == [m["id"]]     # recién llegado: espera a OneDrive
    for x in _buzon(e["raiz"], co.TIPO_MOVER):
        os.remove(x["_archivo"])
    _mover(e["raiz"], 310, "Ofertado", minutos=-45)
    _vuelta(e)
    assert (e["form"] / "310. Caldera en evaluación").is_dir() and _buzon(e["raiz"], co.TIPO_MOVER) == []
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "descartado" and "Evaluación" in p["resultado"]["detalle"][0]


def test_espera_mientras_haya_un_cambio_de_esa_fila_en_el_buzon(e):
    _editar(e["raiz"], 310, "Descartado")
    _mover(e["raiz"], 310, "Ofertado", minutos=-120)
    detalle, _, _ = _vuelta(e)
    assert "espera que la Planilla diga «Ofertado»" in detalle and len(_buzon(e["raiz"], co.TIPO_MOVER)) == 1


def test_de_un_mismo_n_vale_lo_ultimo_que_se_pidio(e):
    _planilla(e["raiz"], [_req(310, "Descartado")])
    _mover(e["raiz"], 310, "Ofertado", minutos=-90)
    _mover(e["raiz"], 310, "Descartado", minutos=-60)
    _vuelta(e)
    assert (e["form"] / "0 OFERTAS PRESENTADAS" / f"0 Ofertas Cerradas {ANIO}" / "310. Caldera en evaluación").is_dir()
    assert sorted(p["resultado"]["estado"] for p in _procesados(e["raiz"])) == ["aplicado", "reemplazado"]


def test_nunca_pisa_una_carpeta_que_ya_esta_en_el_destino(e):
    (e["ges"] / f"0 Proyectos Entregados {ANIO}" / "289. Instalación de prueba").mkdir()
    _planilla(e["raiz"], [_req(289, "Cerrado")])
    _mover(e["raiz"], 289, "Cerrado")
    _vuelta(e)
    assert (e["ges"] / "289. Instalación de prueba" / "Formulación").is_dir()
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "rechazado"
    # 289 tiene dos carpetas en Gestión (la raíz y los entregados): eso lo decide una persona
    assert "lo decide una persona" in p["resultado"]["detalle"][0]


def test_nunca_pisa_en_el_destino_de_formulacion(e):
    (e["form"] / "0 OFERTAS PRESENTADAS" / "310. Caldera en evaluación" / "otra").mkdir(parents=True)
    (e["form"] / "0 OFERTAS PRESENTADAS" / "310. Caldera en evaluación" / "otra" / "a.txt").write_text("x")
    # Ahora 310 tiene dos carpetas: no se mueve. Con una sola en el destino, YaExiste
    _planilla(e["raiz"], [_req(310, "Ofertado")])
    _mover(e["raiz"], 310, "Ofertado")
    _vuelta(e)
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "rechazado"
    with pytest.raises(co.YaExiste):
        co._mover(e["form"] / "310. Caldera en evaluación", e["form"] / "0 OFERTAS PRESENTADAS")
    assert (e["form"] / "0 OFERTAS PRESENTADAS" / "310. Caldera en evaluación" / "otra" / "a.txt").exists()


def test_si_ya_estaba_donde_corresponde_no_hace_nada(e):
    _mover(e["raiz"], 296, "Cerrado")
    _vuelta(e)
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "sin-cambios"


def test_sin_carpeta_la_crea_si_se_pidio(e):
    _planilla(e["raiz"], [_req(340, "Ofertado", "Pedida desde el Portal")])
    _mover(e["raiz"], 340, "Ofertado", crear=True)
    _vuelta(e)
    nueva = e["form"] / "0 OFERTAS PRESENTADAS" / "340. Pedida desde el Portal"
    assert sorted(h.name for h in nueva.iterdir()) == sorted(co.ESTRUCTURA)


def test_sin_carpeta_y_sin_pedir_crearla_se_rechaza(e):
    _planilla(e["raiz"], [_req(340, "Ofertado")])
    _mover(e["raiz"], 340, "Ofertado")
    _vuelta(e)
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "rechazado" and "no hay una carpeta" in p["resultado"]["detalle"][0]


def test_con_algo_abierto_reintenta_y_a_los_7_dias_se_rinde(e, monkeypatch):
    def ocupado(a, b):
        raise PermissionError(32, "El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso")
    monkeypatch.setattr(co.os, "rename", ocupado)
    _planilla(e["raiz"], [_req(310, "Ofertado")])
    _mover(e["raiz"], 310, "Ofertado")
    detalle, _, avisos = _vuelta(e)
    assert len(_buzon(e["raiz"], co.TIPO_MOVER)) == 1 and "se reintenta" in detalle and avisos
    for x in _buzon(e["raiz"], co.TIPO_MOVER):
        os.remove(x["_archivo"])
    _mover(e["raiz"], 310, "Ofertado", minutos=-8 * 24 * 60)
    _vuelta(e)
    assert _buzon(e["raiz"], co.TIPO_MOVER) == []
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "rechazado" and "a mano" in p["resultado"]["detalle"][0]


def test_un_mensaje_invalido_se_rechaza(e):
    m = _mover(e["raiz"], 310, "Ofertado")
    ruta = Path(_buzon(e["raiz"], co.TIPO_MOVER)[0]["_archivo"])
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    datos["estado"] = "Post-venta"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    _vuelta(e)
    (p,) = _procesados(e["raiz"])
    assert p["id"] == m["id"] and p["resultado"]["estado"] == "rechazado"


# ── una carpeta con el N° pero de otro proyecto ─────────────────────────────

def test_coincide_compara_el_nombre_con_la_fila():
    assert co.coincide("31. Concepción - Hornos crematorios", {"titulo": "Hornos crematorio", "ubicacion": "Concepción"})
    assert not co.coincide("29. Concepción - Hornos crematorios", {"titulo": "Mantención de Climatización DC 235"})
    assert co.coincide("310. Hornos crematorios", {"titulo": "Horno crematorio"})            # plural
    # Todas sus palabras en la fila, aunque sean comunes
    assert co.coincide("108. Servicio de mantención preventiva", {"titulo": "Servicio de mantención preventiva a caldera"})
    assert not co.coincide("50. Mantención anual", {"titulo": "Mantención de bombas"})       # solo una palabra común
    assert not co.coincide("50. Algo", None)
    # Sin N° hacen falta dos palabras que distinguen: una ciudad sola no basta
    assert co.coincide("JUNJI VALPARAÍSO CORRECTIVOS", {"titulo": "Correctivos Junji Valparaíso"}, minimo=2)
    assert not co.coincide("Casino Valparaíso", {"titulo": "Junji Valparaíso"}, minimo=2)


def test_una_carpeta_que_no_es_de_su_fila_no_se_mueve_ni_se_lista(e):
    _planilla(e["raiz"], [_req(310, "Ofertado", "Mantención de bombas"), _req(289, "Adjudicado")])
    reqs = co.leer_planilla(e["raiz"])
    assert co.dudosos(reqs, co.indice(e["form"]), co.indice(e["ges"])) == {310}
    assert "310" not in {x["req"] for x in co.fuera_de_lugar(reqs, co.indice(e["form"]), co.indice(e["ges"]), e["ges"], AHORA)}
    _mover(e["raiz"], 310, "Ofertado")
    _vuelta(e)
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "rechazado" and "no parece" in p["resultado"]["detalle"][0]
    assert (e["form"] / "310. Caldera en evaluación").is_dir()                       # no se movió


def test_no_crea_carpeta_a_una_postventa_ni_si_ya_hay_una_sin_n_que_se_le_parece(e):
    (e["form"] / "0 OFERTAS PRESENTADAS" / "JUNJI VALPARAÍSO CORRECTIVOS").mkdir()
    _planilla(e["raiz"], [dict(_req(330, "Evaluación", "Revisión de calderas"), canal="Postventa"),
                          _req(331, "Ofertado", "Correctivos Junji Valparaíso"), _req(332, "Ofertado", "Casino Valparaíso")])
    ahora = datetime.now().astimezone()
    _, estado, _ = _vuelta(e, ahora=ahora)
    _vuelta(e, estado, ahora=ahora + co.ESPERA_CREAR + timedelta(minutes=1))
    nombres = {h.name for h in e["form"].rglob("*") if h.is_dir()}
    assert not any(x.startswith(("330.", "331.")) for x in nombres)
    assert "332. Casino Valparaíso" in nombres                                       # una ciudad sola no basta


def test_la_copia_no_lleva_los_temporales_de_office_ni_lo_que_ya_no_esta(e):
    (e["form"] / "310. Caldera en evaluación" / "ANTECEDENTES" / "~$bases.docx").write_bytes(b"x")
    a_medias = e["ges"] / "310. Caldera en evaluación" / "Formulación (copiando)"
    a_medias.mkdir(parents=True)
    (a_medias / "borrado.pdf").write_bytes(b"ya no esta en el original")
    (a_medias / "~$viejo.xlsx").write_bytes(b"x")
    _planilla(e["raiz"], [_req(310, "Adjudicado")])
    _mover(e["raiz"], 310, "Adjudicado")
    _vuelta(e)
    copia = e["ges"] / "310. Caldera en evaluación" / "Formulación"
    assert sorted(x.relative_to(copia).as_posix() for x in copia.rglob("*") if x.is_file()) == ["ANTECEDENTES/bases.pdf"]
    (p,) = _procesados(e["raiz"])
    assert p["resultado"]["estado"] == "aplicado"



def test_fuera_de_lugar(e):
    _planilla(e["raiz"], [_req(289, "Adjudicado"), _req(296, "Cerrado"), _req(310, "Ofertado"),
                          _req(120, "No adjudicado"), _req(400, "Ofertado")])
    (e["form"] / "0 OFERTAS PRESENTADAS" / "296. Caldera de prueba").mkdir()      # cerrado, el original no está en adjudicadas
    lista = co.fuera_de_lugar(co.leer_planilla(e["raiz"]), co.indice(e["form"]), co.indice(e["ges"]), e["ges"], AHORA)
    por_n = {x["req"]: x for x in lista}
    assert set(por_n) == {"289", "296", "310"}
    assert por_n["310"]["carpeta"] == "310. Caldera en evaluación" and por_n["310"]["estado"] == "Ofertado"
    assert por_n["310"]["detalle"] == ["De Formulación de proyectos a Formulación de proyectos › 0 OFERTAS PRESENTADAS."]
    assert "0 OFERTAS ADJUDICADAS" in por_n["289"]["detalle"][0]
    # Un «mover» que ya espera no se repite
    lista = co.fuera_de_lugar(co.leer_planilla(e["raiz"]), co.indice(e["form"]), co.indice(e["ges"]), e["ges"], AHORA,
                              omitir={310})
    assert "310" not in {x["req"] for x in lista}


def test_fuera_de_lugar_no_cuenta_la_carpeta_de_gestion_que_falta_ni_los_n_repetidos(e):
    (e["form"] / "0 OFERTAS ADJUDICADAS" / "500. Hecha a mano").mkdir()
    (e["ges"] / "500. Hecha a mano").mkdir()                                        # sin «Formulación»
    (e["form"] / "0 OFERTAS ADJUDICADAS" / "501. Gestión sin N°").mkdir()           # su carpeta de Gestión no tiene N°
    (e["form"] / "0 OFERTAS PRESENTADAS" / "310. Repetida").mkdir()
    _planilla(e["raiz"], [_req(500, "Adjudicado"), _req(501, "Adjudicado"), _req(310, "Ofertado")])
    assert co.fuera_de_lugar(co.leer_planilla(e["raiz"]), co.indice(e["form"]), co.indice(e["ges"]), e["ges"], AHORA) == []


# ── en el procesador ────────────────────────────────────────────────────────

def _bibliotecas(monkeypatch, e):
    def biblioteca(nombre, desde=None):
        return {co.ubicacion.BIBLIOTECA_FORMULACION: e["form"], co.ubicacion.BIBLIOTECA_GESTION: e["ges"]}.get(nombre)
    monkeypatch.setattr(procesar.ubicacion, "biblioteca", biblioteca)


def test_el_procesador_lo_corre_antes_de_los_entregados_y_del_cruce(e, monkeypatch):
    nombres = [n for n, _ in procesar.PASOS]
    assert nombres.index("requerimientos") < nombres.index("carpetas-oferta") < nombres.index("entregados") < nombres.index("proyectos")
    assert nombres.index("requerimientos") < nombres.index("estados-formulador")
    _bibliotecas(monkeypatch, e)
    _planilla(e["raiz"], [_req(310, "Ofertado")])
    _mover(e["raiz"], 310, "Ofertado")
    detalle, firma = procesar.paso_carpetas_oferta(e["raiz"], None, False)
    assert "movidas" in detalle and firma["conocidos"] == [310]
    assert (e["form"] / "0 OFERTAS PRESENTADAS" / "310. Caldera en evaluación").is_dir()


def test_proyectos_json_lleva_las_ofertas_y_lo_fuera_de_lugar(e, monkeypatch, tmp_path):
    _bibliotecas(monkeypatch, e)
    monkeypatch.setattr(procesar, "RAIZ_FACTURAS_CL", tmp_path / "sin-centro-de-costos" / "Chile")
    monkeypatch.setattr(procesar.carpetas_proyecto, "enlaces_web", lambda raices, ruta: {})
    _planilla(e["raiz"], [_req(289, "Adjudicado"), _req(296, "Cerrado"), _req(310, "Ofertado"),
                          _req(120, "No adjudicado", "Mantención de bombas")])          # su carpeta es de otro
    detalle, _ = procesar.paso_proyectos(e["raiz"], None, False)
    sobre = intercambio.leer_publicacion(e["raiz"], "proyectos")
    assert esquemas.validar_publicacion("proyectos", sobre) == []
    datos = sobre["datos"]
    assert {"req": "310", "ruta": "310. Caldera en evaluación"} in datos["ofertas"]
    assert {"req": "120", "ruta": "0 OFERTAS PRESENTADAS/0 Ofertas Cerradas 2025/120. Perdida de antes"} in datos["ofertas"]
    assert {x["req"] for x in datos["fueraDeLugar"]} == {"289", "310"}
    assert "2 carpeta(s) fuera de lugar" in detalle and datos["carpetasDudosas"] == ["120"]


# ── el Estado de la Planilla al Formulador ──────────────────────────────────

def _presupuesto(raiz, uid, n, estado, minutos=-60, codigo=None, version=1):
    mod = (datetime.now().astimezone() + timedelta(minutes=minutos)).astimezone().isoformat(timespec="milliseconds")
    datos = {"uid": uid, "modificado": mod, "codigo": codigo or f"QPN-{uid}", "version": version, "estado": estado,
             "titulo": f"Presupuesto {uid}", "vinculos": {"requerimiento": {"numero": n}}}
    formulaciones._escribir(raiz, datos, [], {}, "NB")
    return datos


def _leer(raiz, uid):
    return {i["uid"]: i for i in formulaciones.leer_repositorio(raiz)}[uid]


def test_la_primera_vez_solo_anota_lo_que_hay(e):
    _presupuesto(e["raiz"], "a", 310, "Borrador")
    vistos, cambiados = formulaciones.alinear_estados(e["raiz"], [_req(310, "Ofertado")], None)
    assert vistos == {"310": "Ofertado"} and cambiados == [] and _leer(e["raiz"], "a")["datos"]["estado"] == "Borrador"


def test_un_cambio_en_la_planilla_llega_al_formulador_como_version_nueva(e):
    antes = _presupuesto(e["raiz"], "a", 310, "En revisión")
    vistos, cambiados = formulaciones.alinear_estados(e["raiz"], [_req(310, "Adjudicado")], {"310": "Evaluación"})
    item = _leer(e["raiz"], "a")
    assert item["datos"]["estado"] == "Adjudicada" and item["datos"]["modificadoPor"] == formulaciones.FIRMA_PLANILLA
    assert item["historia"] == [antes["modificado"]] and item["mod"] > antes["modificado"]
    assert re.search(r"Z$", item["mod"]) and vistos["310"] == "Adjudicado" and "Adjudicada" in cambiados[0]
    assert vistos[formulaciones.ESCRITOS] == {"310": {"sello": item["mod"], "estado": "Adjudicado", "antes": "Evaluación"}}
    # La vuelta siguiente lo ve escrito y no hace nada más
    assert formulaciones.alinear_estados(e["raiz"], [_req(310, "Adjudicado")], vistos) == ({"310": "Adjudicado"}, [])


@pytest.mark.parametrize("caso", ["igual", "reciente", "otro-n", "sugerencia", "sin-presupuesto"])
def test_lo_que_no_se_toca(e, caso):
    estado = "Enviada" if caso == "igual" else "En revisión"
    _presupuesto(e["raiz"], "a", 310 if caso != "sin-presupuesto" else 999, estado,
                 minutos=-2 if caso == "reciente" else -60, codigo="314. UA Reactor" if caso == "otro-n" else None)
    omitir = {310} if caso == "sugerencia" else ()
    vistos, cambiados = formulaciones.alinear_estados(e["raiz"], [_req(310, "Ofertado")], {"310": "Evaluación"}, omitir)
    assert cambiados == [] and _leer(e["raiz"], "a")["datos"]["estado"] == estado
    # Lo reciente y la sugerencia que espera se vuelven a mirar; lo demás queda visto
    assert vistos["310"] == ("Evaluación" if caso in ("reciente", "sugerencia") else "Ofertado")


def test_manda_el_presupuesto_mas_nuevo_de_ese_n(e):
    _presupuesto(e["raiz"], "viejo", 310, "En revisión", minutos=-300, codigo="QPN-1")
    _presupuesto(e["raiz"], "nuevo", 310, "En revisión", minutos=-60, codigo="QPN-2")
    formulaciones.alinear_estados(e["raiz"], [_req(310, "Ofertado")], {"310": "Evaluación"})
    assert _leer(e["raiz"], "nuevo")["datos"]["estado"] == "Enviada" and _leer(e["raiz"], "viejo")["datos"]["estado"] == "En revisión"


def test_el_paso_del_procesador_no_toca_lo_que_espera_del_formulador(e):
    _presupuesto(e["raiz"], "a", 310, "En revisión")
    _, vistos = procesar.paso_estados_formulador(e["raiz"], None, False)
    _planilla(e["raiz"], [_req(310, "Ofertado")])
    _editar(e["raiz"], 310, "Adjudicado", herramienta="formulador", tipo="actualizar-requerimiento")
    detalle, vistos = procesar.paso_estados_formulador(e["raiz"], vistos, False)
    assert detalle == "sin cambios de estado" and vistos["310"] == "Evaluación"
    for x in _buzon(e["raiz"], "actualizar-requerimiento"):
        os.remove(x["_archivo"])
    detalle, vistos = procesar.paso_estados_formulador(e["raiz"], vistos, False)
    assert "Enviada" in detalle and _leer(e["raiz"], "a")["datos"]["estado"] == "Enviada"


def test_la_planilla_atrasada_no_hace_retroceder_al_presupuesto(e):
    """La Planilla se pone al día tarde (pasa de «Ofertado» a «Adjudicado» cuando el presupuesto ya está «Cerrada»)."""
    _presupuesto(e["raiz"], "a", 310, "Cerrada")
    vistos, cambiados = formulaciones.alinear_estados(e["raiz"], [_req(310, "Adjudicado")], {"310": "Ofertado"})
    assert cambiados == [] and vistos == {"310": "Adjudicado"} and _leer(e["raiz"], "a")["datos"]["estado"] == "Cerrada"


def test_reabrir_en_la_planilla_si_llega_al_presupuesto(e):
    """Estaban iguales («Cerrado») y alguien lo reabre en la Planilla: eso sí pasa."""
    _presupuesto(e["raiz"], "a", 310, "Cerrada")
    _, cambiados = formulaciones.alinear_estados(e["raiz"], [_req(310, "Adjudicado")], {"310": "Cerrado"})
    assert cambiados and _leer(e["raiz"], "a")["datos"]["estado"] == "Adjudicada"


def test_lo_escrito_que_onedrive_pierde_se_vuelve_a_escribir(e):
    _presupuesto(e["raiz"], "a", 310, "En revisión")
    vistos, _ = formulaciones.alinear_estados(e["raiz"], [_req(310, "Ofertado")], {"310": "Evaluación"})
    assert _leer(e["raiz"], "a")["datos"]["estado"] == "Enviada"
    _presupuesto(e["raiz"], "a", 310, "En revisión")       # un conflicto de OneDrive deja la versión anterior
    vistos, cambiados = formulaciones.alinear_estados(e["raiz"], [_req(310, "Ofertado")], vistos)
    assert cambiados and _leer(e["raiz"], "a")["datos"]["estado"] == "Enviada" and formulaciones.ESCRITOS in vistos
    # Si alguien lo cambió después de escribirlo, manda esa persona
    _presupuesto(e["raiz"], "a", 310, "Borrador", minutos=1)
    vistos, cambiados = formulaciones.alinear_estados(e["raiz"], [_req(310, "Ofertado")], vistos)
    assert cambiados == [] and vistos == {"310": "Ofertado"} and _leer(e["raiz"], "a")["datos"]["estado"] == "Borrador"


def test_las_tablas_de_estados_calzan_con_el_formulador():
    """EN_PLANILLA es la de js/flujo.js del Formulador y cubre los estados de js/store.js (si el repo está al lado)."""
    assert set(formulaciones.AL_FORMULADOR) == set(rq.ESTADOS)
    assert all(formulaciones.EN_PLANILLA[v] == k for k, v in formulaciones.AL_FORMULADOR.items())
    repo = Path(__file__).resolve().parents[3] / "Formulación de proyectos" / "quempin-formulacion"
    if not (repo / "js" / "flujo.js").exists():
        repo = Path(__file__).resolve().parents[5] / "Formulación de proyectos" / "quempin-formulacion"
    if not (repo / "js" / "flujo.js").exists():
        pytest.skip("sin el repositorio del Formulador al lado")
    flujo = (repo / "js" / "flujo.js").read_text(encoding="utf-8")
    tabla = re.search(r"const EN_PLANILLA = \{([^}]*)\}", flujo).group(1)
    js = dict(re.findall(r"'([^']+)':\s*'([^']+)'", tabla))
    assert js and all(formulaciones.EN_PLANILLA[k] == v for k, v in js.items()), js
    store = (repo / "js" / "store.js").read_text(encoding="utf-8")
    estados = re.findall(r"'([^']+)'", re.search(r"const ESTADOS = \[([^\]]*)\]", store).group(1))
    assert set(estados) == set(formulaciones.EN_PLANILLA)
