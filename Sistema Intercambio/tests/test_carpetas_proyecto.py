# -*- coding: utf-8 -*-
"""Las carpetas de facturas de los proyectos: la del Centro de Costos al
adjudicarse, «Facturas del proyecto» en Gestión y la copia de lo que se deja
ahí (carpetas_proyecto.py). Bibliotecas falsas en una carpeta temporal."""
import json
import os
import time

import pytest

import carpetas_proyecto as cp
import formulaciones
import intercambio
import proyectos

FAC = cp.SUB_FACTURAS
HACE_UNA_HORA = time.time() - 3600


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


def _vuelta(e, ahora=None):
    return cp.atender(e["raiz"], e["raices"], e["gestion"], e["estado"], ahora)


def _factura(carpeta, nombre="Factura 1.pdf", contenido=b"%PDF factura", viejo=True):
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre
    ruta.write_bytes(contenido)
    if viejo:
        os.utime(ruta, (HACE_UNA_HORA, HACE_UNA_HORA))
    return ruta


def test_nombre_de_carpeta():
    assert cp.nombre_carpeta("322", "322. Instalación Caldera Vapor") == "322. Instalación Caldera Vapor"
    assert cp.nombre_carpeta("322", "Instalación: caldera/vapor?") == "322. Instalación caldera vapor"
    assert cp.nombre_carpeta("7", "") == "7. Proyecto"
    assert len(cp.nombre_carpeta("1", "x" * 200)) <= cp.LARGO_NOMBRE


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
    estado = json.loads(e["estado"].read_text(encoding="utf-8"))
    assert estado["conocidos"] == ["281", "289"]


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


def test_facturas_del_proyecto_en_gestion_cuando_hay_carpeta_en_el_cc(e):
    r = _vuelta(e)
    assert r["creadasGestion"] == ["289. KeyProcess"]
    assert (e["gestion"] / "289. KeyProcess" / FAC).is_dir()
    assert (e["gestion"] / "289. KeyProcess" / "Compras").is_dir()      # lo demás no se toca
    # Sin carpeta con N° en el CC («H2 Green» no tiene N°) no se crea
    assert not (e["gestion"] / "281. H2 Green" / FAC).exists()
    # Ni en los entregados
    assert not (e["gestion"] / "0 Proyectos Entregados 2026" / "296. Llay llay" / FAC).exists()
    # Una sola vez: si alguien la borra, no vuelve
    (e["gestion"] / "289. KeyProcess" / FAC).rmdir()
    assert _vuelta(e)["creadasGestion"] == []
    assert not (e["gestion"] / "289. KeyProcess" / FAC).exists()


def test_una_carpeta_de_gestion_con_facturas_del_proyecto_recibe_su_carpeta_en_el_cc(e):
    # Como la deja QUEMPIN.exe 1.3.15, aunque el proyecto ya estuviera adjudicado antes
    (e["gestion"] / "281. H2 Green" / FAC).mkdir()
    (e["gestion"] / "314. UA Reactor" / "Formulación").mkdir(parents=True)
    (e["gestion"] / "314. UA Reactor" / FAC).mkdir()
    r = _vuelta(e)
    assert r["creadasCC"] == ["Chile/281. H2 Green", "Chile/314. UA Reactor"]


def test_copia_al_cc_lo_que_se_deja_en_facturas_del_proyecto(e):
    _vuelta(e)
    sub = e["gestion"] / "289. KeyProcess" / FAC
    _factura(sub, "Factura 10.pdf", b"%PDF diez")
    _factura(sub / "Octubre", "Boleta.jpg", b"jpg")
    _factura(sub, "Notas.docx", b"no")              # no es factura ni boleta
    _factura(sub, "~$Temporal.pdf", b"x")
    r = _vuelta(e)
    assert r["copiados"] == 2
    cc = e["chile"] / "289. KeyProcess"
    assert sorted(h.name for h in cc.iterdir()) == ["Boleta.jpg", "Factura 10.pdf"]
    assert (cc / "Factura 10.pdf").read_bytes() == b"%PDF diez"
    assert (sub / "Factura 10.pdf").exists()        # el original queda en Gestión
    # Cada archivo se copia una vez, aunque en el CC lo renombren o lo muevan
    (cc / "Factura 10.pdf").rename(cc / "812 Proveedor.pdf")
    assert _vuelta(e)["copiados"] == 0
    assert sorted(h.name for h in cc.iterdir()) == ["812 Proveedor.pdf", "Boleta.jpg"]


def test_no_pisa_ni_repite(e):
    _vuelta(e)
    cc = e["chile"] / "289. KeyProcess"
    (cc / "Factura 1.pdf").write_bytes(b"otra factura")
    (cc / "Ya subida.pdf").write_bytes(b"%PDF igual")
    sub = e["gestion"] / "289. KeyProcess" / FAC
    _factura(sub, "Factura 1.pdf", b"%PDF nueva")
    _factura(sub, "Copia local.pdf", b"%PDF igual")
    r = _vuelta(e)
    assert r["copiados"] == 1
    assert (cc / "Factura 1.pdf").read_bytes() == b"otra factura"
    assert (cc / "Factura 1 (2).pdf").read_bytes() == b"%PDF nueva"
    assert not (cc / "Copia local.pdf").exists()
    assert any("ya estaba" in d for d in r["detalle"])


def test_espera_a_que_el_archivo_termine_de_guardarse(e):
    _vuelta(e)
    sub = e["gestion"] / "289. KeyProcess" / FAC
    _factura(sub, "Recien.pdf", b"%PDF", viejo=False)
    assert _vuelta(e)["copiados"] == 0
    assert _vuelta(e, ahora=time.time() + cp.MINUTOS_QUIETO * 60 + 1)["copiados"] == 1


def test_un_archivo_que_cambia_se_copia_otra_vez(e):
    _vuelta(e)
    sub = e["gestion"] / "289. KeyProcess" / FAC
    _factura(sub, "Factura.pdf", b"%PDF v1")
    assert _vuelta(e)["copiados"] == 1
    ruta = _factura(sub, "Factura.pdf", b"%PDF v2 corregida")
    os.utime(ruta, (HACE_UNA_HORA + 60, HACE_UNA_HORA + 60))
    assert _vuelta(e)["copiados"] == 1
    assert (e["chile"] / "289. KeyProcess" / "Factura (2).pdf").read_bytes() == b"%PDF v2 corregida"


def test_tambien_de_los_proyectos_entregados(e):
    _vuelta(e)
    (e["chile"] / "296. Llay llay").mkdir()
    _factura(e["gestion"] / "0 Proyectos Entregados 2026" / "296. Llay llay" / FAC, "Tardia.pdf")
    assert _vuelta(e)["copiados"] == 1
    assert (e["chile"] / "296. Llay llay" / "Tardia.pdf").exists()


def test_con_facturas_sin_carpeta_en_el_cc_lo_avisa(e):
    _vuelta(e)
    sub = e["gestion"] / "0 Proyectos Entregados 2026" / "296. Llay llay" / FAC
    _factura(sub, "Factura.pdf")
    r = _vuelta(e)
    assert r["copiados"] == 0 and r["sinCarpetaCC"] == ["296. Llay llay"]


def test_sin_el_sitio_del_cc_no_hace_nada(e, tmp_path):
    (e["gestion"] / "314. UA Reactor" / FAC).mkdir(parents=True)
    r = cp.atender(e["raiz"], {"CL": tmp_path / "no", "PE": tmp_path / "no2"}, e["gestion"], e["estado"])
    assert r["creadasCC"] == [] and not e["estado"].exists()


def test_una_carpeta_sin_numero_cuenta_por_su_equivalencia(e):
    """«H2 Green» no se renombra (el CC reconoce lo registrado por «carpetarchivo»): se anota que es la del 281."""
    e["estado"].write_text(json.dumps({"equivalencias": {"281": "Chile/h2 green"}}), encoding="utf-8")
    r = _vuelta(e)
    assert "281. H2 Green" in r["creadasGestion"]
    assert r["creadasCC"] == [] and sorted(h.name for h in e["chile"].iterdir()) == ["289. KeyProcess", "H2 Green"]
    _factura(e["gestion"] / "281. H2 Green" / FAC, "Factura H2.pdf")
    assert _vuelta(e)["copiados"] == 1
    assert (e["chile"] / "H2 Green" / "Factura H2.pdf").exists()
    assert json.loads(e["estado"].read_text(encoding="utf-8"))["equivalencias"] == {"281": "Chile/h2 green"}


def test_proyectos_publica_donde_esta_facturas_del_proyecto(e):
    (e["gestion"] / "289. KeyProcess" / FAC).mkdir()
    rutas = proyectos.carpetas_con_numero(e["gestion"])
    assert cp.con_facturas(e["gestion"], rutas) == {"289": [f"289. KeyProcess/{FAC}"]}
