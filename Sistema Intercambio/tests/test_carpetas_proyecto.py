# -*- coding: utf-8 -*-
"""Las carpetas de facturas de los proyectos: la del Centro de Costos al
adjudicarse y el acceso directo web «Facturas del proyecto» en Gestión
(carpetas_proyecto.py). Bibliotecas falsas en una carpeta temporal."""
import json
import os
import stat

import pytest

import carpetas_proyecto as cp
import formulaciones
import intercambio

URL = cp.ACCESO_FACTURAS
WEB = "https://quempinspa2020.sharepoint.com/Documentos%20compartidos/Centro%20de%20Costos/Facturas%20y%20Boletas/"


@pytest.fixture
def e(tmp_path):
    raiz = intercambio.asegurar_carpeta(tmp_path / "Intercambio")
    chile = tmp_path / "Facturas y Boletas" / "Chile"
    (chile / "289. KeyProcess").mkdir(parents=True)
    (chile / "H2 Green").mkdir()
    (tmp_path / "Facturas y Boletas" / "Perú" / "FACH1").mkdir(parents=True)
    gestion = tmp_path / "Gestión de Proyectos - Documentos"
    (gestion / "289. KeyProcess" / "Compras").mkdir(parents=True)
    (gestion / "281. H2 Green").mkdir()
    (gestion / "0 Proyectos Entregados 2026" / "296. Llay llay").mkdir(parents=True)
    (gestion / "0 Carpeta modelo").mkdir()
    _publicar(raiz, requerimientos=[{"numero": 289, "estado": "Adjudicado", "titulo": "INSTALACIÓN H2"},
                                    {"numero": 281, "estado": "Adjudicado", "titulo": "H2 GREEN"},
                                    {"numero": 315, "estado": "Evaluación", "titulo": "PEUMO"}])
    return {"raiz": raiz, "raices": {"CL": chile, "PE": chile.parent / "Perú"}, "chile": chile, "gestion": gestion,
            "estado": tmp_path / "estado.json"}


def _publicar(raiz, requerimientos=None, af=None):
    if requerimientos is not None:
        intercambio.publicar(raiz, "requerimientos", "procesador", {"requerimientos": requerimientos})
    if af is not None:
        intercambio.publicar(raiz, "analisis-financiero", "procesador", {"proyectos": af})


def _formulacion(raiz, uid, estado, req=None, carpeta=None, codigo="QMPN-2026-1", titulo="Obra", pais=None):
    vinculos = {}
    if req:
        vinculos["requerimiento"] = {"numero": req, "titulo": titulo.upper()}
    if carpeta:
        vinculos["carpetaOferta"] = {"nombre": carpeta, "ruta": [carpeta]}
    if pais:
        vinculos["controlDocumentos"] = {"pais": pais}
    carpeta_repo = formulaciones.carpeta_repositorio(raiz)
    carpeta_repo.mkdir(parents=True, exist_ok=True)
    datos = {"uid": uid, "estado": estado, "codigo": codigo, "titulo": titulo, "vinculos": vinculos}
    (carpeta_repo / formulaciones.nombre_archivo(uid)).write_text(
        json.dumps({"esquema": intercambio.ESQUEMA, "tipo": "proyecto", "datos": datos}), encoding="utf-8")


def _vuelta(e):
    return cp.atender(e["raiz"], e["raices"], e["gestion"], e["estado"])


def test_nombre_de_carpeta():
    assert cp.nombre_carpeta("322", "322. Instalación Caldera Vapor") == "322. Instalación Caldera Vapor"
    assert cp.nombre_carpeta("322", "Instalación: caldera/vapor?") == "322. Instalación caldera vapor"
    assert cp.nombre_carpeta("7", "") == "7. Proyecto"
    assert len(cp.nombre_carpeta("1", "x" * 200)) <= cp.LARGO_NOMBRE


def test_enlace_web_y_acceso_directo(e):
    url = cp.enlace_web(e["chile"] / "289. KeyProcess")
    assert url == WEB + "Chile/289.%20KeyProcess"
    assert cp.enlace_web(e["raices"]["PE"] / "FACH1") == WEB + "Per%C3%BA/FACH1"
    assert cp.contenido_acceso(url) == f"[InternetShortcut]\r\nURL={url}\r\n".encode("ascii")


def test_ganados_prefiere_la_carpeta_de_la_oferta(e):
    _formulacion(e["raiz"], "a", "Adjudicada", req="322", carpeta="322. Instalación Caldera Vapor")
    _formulacion(e["raiz"], "b", "Adjudicada", req="323", codigo="323. Comolsa", pais="Perú")
    _formulacion(e["raiz"], "c", "Enviada", req="324", carpeta="324. No ganada")
    g = cp.ganados([{"numero": 322, "estado": "Adjudicado", "titulo": "INSTALACIÓN CALDERA"}],
                   [{"req": "325", "nombre": "Obra del Análisis"}], formulaciones.leer_repositorio(e["raiz"]))
    assert g["322"] == {"nombre": "322. Instalación Caldera Vapor", "pais": "CL"}
    assert g["323"] == {"nombre": "323. Comolsa", "pais": "PE"}
    assert g["325"]["nombre"] == "325. Obra del Análisis"
    assert "324" not in g


def test_la_primera_vuelta_solo_anota_lo_adjudicado_y_no_crea_carpetas_en_el_cc(e):
    r = _vuelta(e)
    assert r["creadasCC"] == []
    # «281. H2 Green» ya estaba adjudicado: no se crea otra carpeta junto a «H2 Green»
    assert sorted(h.name for h in e["chile"].iterdir()) == ["289. KeyProcess", "H2 Green"]
    assert json.loads(e["estado"].read_text(encoding="utf-8"))["conocidos"] == ["281", "289"]


def test_lo_que_se_adjudica_despues_tiene_su_carpeta_en_el_cc(e):
    _vuelta(e)
    _formulacion(e["raiz"], "a", "Adjudicada", req="322", carpeta="322. Instalación Caldera Vapor")
    _publicar(e["raiz"], af=[{"req": "330", "nombre": "Ingresado en el Portal"}])
    r = _vuelta(e)
    assert r["creadasCC"] == ["Chile/322. Instalación Caldera Vapor", "Chile/330. Ingresado en el Portal"]
    assert (e["chile"] / "322. Instalación Caldera Vapor").is_dir()
    # Una vez: si después se borra, no vuelve
    (e["chile"] / "322. Instalación Caldera Vapor").rmdir()
    assert _vuelta(e)["creadasCC"] == []


def test_un_adjudicado_nuevo_con_carpeta_en_el_cc_no_recibe_otra(e):
    _vuelta(e)
    (e["chile"] / "322. Ya creada a mano").mkdir()
    _formulacion(e["raiz"], "a", "Adjudicada", req="322", carpeta="322. Otro nombre")
    assert _vuelta(e)["creadasCC"] == []


def test_peru_va_a_su_carpeta(e):
    _vuelta(e)
    _formulacion(e["raiz"], "a", "Adjudicada", req="340", codigo="340. Molino", pais="Perú")
    assert _vuelta(e)["creadasCC"] == ["Perú/340. Molino"]


def test_lo_que_quempin_exe_paso_a_gestion_recibe_su_carpeta_en_el_cc(e):
    (e["gestion"] / "314. UA Reactor" / "Formulación").mkdir(parents=True)
    r = _vuelta(e)
    assert r["creadasCC"] == ["Chile/314. UA Reactor"]
    assert cp.url_de_acceso(e["gestion"] / "314. UA Reactor" / URL) == WEB + "Chile/314.%20UA%20Reactor"


def test_acceso_directo_a_la_carpeta_del_cc(e):
    r = _vuelta(e)
    assert r["accesos"] == ["289. KeyProcess"]
    acceso = e["gestion"] / "289. KeyProcess" / URL
    assert acceso.read_bytes() == cp.contenido_acceso(WEB + "Chile/289.%20KeyProcess")
    assert (e["gestion"] / "289. KeyProcess" / "Compras").is_dir()      # lo demás no se toca
    # Sin carpeta con N° en el CC («H2 Green» no tiene N°) no hay acceso; ni en los entregados
    assert not (e["gestion"] / "281. H2 Green" / URL).exists()
    assert not (e["gestion"] / "0 Proyectos Entregados 2026" / "296. Llay llay" / URL).exists()
    # Al día: no se reescribe
    assert _vuelta(e)["accesos"] == []
    # Si alguien lo borra, no vuelve
    acceso.unlink()
    assert _vuelta(e)["accesos"] == [] and not acceso.exists()


def test_si_cambia_la_carpeta_del_cc_el_acceso_se_actualiza(e):
    _vuelta(e)
    (e["chile"] / "289. KeyProcess").rename(e["chile"] / "289. KeyProcess H2")
    assert _vuelta(e)["accesos"] == ["289. KeyProcess"]
    assert cp.url_de_acceso(e["gestion"] / "289. KeyProcess" / URL) == WEB + "Chile/289.%20KeyProcess%20H2"


def test_la_carpeta_vacia_de_antes_se_reemplaza_y_con_archivos_se_avisa(e):
    vieja = e["gestion"] / "289. KeyProcess" / cp.SUB_FACTURAS
    vieja.mkdir()
    (vieja / "desktop.ini").write_text("[.ShellClassInfo]")
    os.chmod(vieja / "desktop.ini", stat.S_IREAD)
    os.chmod(vieja, stat.S_IREAD)          # como las deja OneDrive: solo lectura
    con_archivos = e["gestion"] / "281. H2 Green" / cp.SUB_FACTURAS
    con_archivos.mkdir()
    (con_archivos / "Factura.pdf").write_bytes(b"%PDF")
    e["estado"].write_text(json.dumps({"equivalencias": {"281": "Chile/H2 Green"}}), encoding="utf-8")
    r = _vuelta(e)
    assert not vieja.exists() and (e["gestion"] / "289. KeyProcess" / URL).is_file()
    assert r["conArchivos"] == ["281. H2 Green"]
    assert (con_archivos / "Factura.pdf").exists() and (e["gestion"] / "281. H2 Green" / URL).is_file()


def test_una_carpeta_sin_numero_cuenta_por_su_equivalencia(e):
    """«H2 Green» no se renombra (el CC reconoce lo registrado por «carpeta\\archivo»): se anota que es la del 281."""
    e["estado"].write_text(json.dumps({"equivalencias": {"281": "Chile/h2 green"}}), encoding="utf-8")
    r = _vuelta(e)
    assert "281. H2 Green" in r["accesos"] and r["creadasCC"] == []
    assert cp.url_de_acceso(e["gestion"] / "281. H2 Green" / URL) == WEB + "Chile/H2%20Green"
    assert cp.enlaces_web(e["raices"], e["estado"])["281"] == [WEB + "Chile/H2%20Green"]
    assert json.loads(e["estado"].read_text(encoding="utf-8"))["equivalencias"] == {"281": "Chile/h2 green"}


def test_si_no_se_puede_quitar_la_carpeta_vieja_avisa_y_sigue(e, monkeypatch):
    (e["gestion"] / "289. KeyProcess" / cp.SUB_FACTURAS).mkdir()
    monkeypatch.setattr(cp, "_quitar", lambda carpeta: False)
    r = _vuelta(e)
    assert r["sinQuitar"] == ["289. KeyProcess"] and r["accesos"] == ["289. KeyProcess"]


def test_sin_el_sitio_del_cc_no_hace_nada(e, tmp_path):
    (e["gestion"] / "314. UA Reactor" / "Formulación").mkdir(parents=True)
    r = cp.atender(e["raiz"], {"CL": tmp_path / "no", "PE": tmp_path / "no2"}, e["gestion"], e["estado"])
    assert r["creadasCC"] == [] and r["accesos"] == [] and not e["estado"].exists()
