# -*- coding: utf-8 -*-
"""Los documentos subidos desde el Portal llegan a la carpeta del Centro de Costos."""
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone

import pytest

import documentos_cc as dc
import intercambio


@pytest.fixture
def entorno(tmp_path):
    raiz = tmp_path / "Intercambio"
    intercambio.asegurar_carpeta(raiz)
    chile = tmp_path / "Facturas y Boletas" / "Chile"
    (chile / "280. Obra de ejemplo").mkdir(parents=True)
    (chile / "Gastos Generales").mkdir()
    return {"raiz": raiz, "raices": {"CL": chile, "PE": tmp_path / "Facturas y Boletas" / "Perú"}, "chile": chile}


def _enviar(raiz, carpeta="280. Obra de ejemplo", archivos=None, escribir=True, enviado=None, **extra):
    archivos = archivos if archivos is not None else {"Factura 1.pdf": b"%PDF-1 factura"}
    mensaje = {
        "esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": dc.TIPO, "destino": dc.DESTINO,
        "origen": {"herramienta": "portal", "enviado": enviado or intercambio.ahora_iso(), "usuario": "NB"},
        "pais": "CL", "carpeta": carpeta,
        "archivos": [{"nombre": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()} for n, b in archivos.items()],
    }
    mensaje.update(extra)
    if escribir:
        adj = raiz / "buzon" / "adjuntos" / mensaje["id"]
        adj.mkdir(parents=True)
        for n, b in archivos.items():
            (adj / n).write_bytes(b)
    intercambio.enviar(raiz, mensaje)
    return mensaje


def _procesados(raiz):
    return [json.loads(p.read_text(encoding="utf-8")) for p in (raiz / "procesado").rglob("*.json")]


def test_copia_a_la_carpeta_del_proyecto_y_archiva(entorno):
    m = _enviar(entorno["raiz"], carpeta="280. OBRA de ejemplo")    # sin distinguir mayúsculas
    r = dc.atender(entorno["raiz"], entorno["raices"])
    assert r == {"aplicados": 1, "archivos": 1, "esperan": 0, "rechazados": 0}
    assert (entorno["chile"] / "280. Obra de ejemplo" / "Factura 1.pdf").read_bytes() == b"%PDF-1 factura"
    assert not (entorno["raiz"] / "buzon" / "adjuntos" / m["id"]).exists()
    [hecho] = _procesados(entorno["raiz"])
    assert hecho["resultado"]["estado"] == "aplicado"
    assert hecho["resultado"]["carpeta"] == "Chile/280. Obra de ejemplo"


def test_nunca_pisa_y_detecta_repetidos(entorno):
    carpeta = entorno["chile"] / "280. Obra de ejemplo"
    (carpeta / "Factura 1.pdf").write_bytes(b"otro contenido")
    (carpeta / "UMAG-001_ya_registrada.pdf").write_bytes(b"%PDF repetida")
    _enviar(entorno["raiz"], archivos={"Factura 1.pdf": b"%PDF-1 factura", "copia.pdf": b"%PDF repetida"})
    dc.atender(entorno["raiz"], entorno["raices"])
    assert (carpeta / "Factura 1.pdf").read_bytes() == b"otro contenido"
    assert (carpeta / "Factura 1 (2).pdf").read_bytes() == b"%PDF-1 factura"
    assert not (carpeta / "copia.pdf").exists()
    [hecho] = _procesados(entorno["raiz"])
    assert [a["repetido"] for a in hecho["resultado"]["archivos"]] == [False, True]


def test_espera_si_los_archivos_no_llegan_y_rechaza_a_los_7_dias(entorno):
    viejo = (datetime.now(timezone.utc) - timedelta(days=dc.DIAS_ESPERA + 1)).isoformat(timespec="seconds")
    _enviar(entorno["raiz"], escribir=False)
    _enviar(entorno["raiz"], escribir=False, enviado=viejo)
    r = dc.atender(entorno["raiz"], entorno["raices"])
    assert r["esperan"] == 1 and r["rechazados"] == 1
    assert len(list((entorno["raiz"] / "buzon").glob("*.json"))) == 1


def test_espera_si_el_archivo_llega_a_medias(entorno):
    m = _enviar(entorno["raiz"])
    (entorno["raiz"] / "buzon" / "adjuntos" / m["id"] / "Factura 1.pdf").write_bytes(b"%PDF")
    assert dc.atender(entorno["raiz"], entorno["raices"])["esperan"] == 1


def test_carpeta_inexistente_se_rechaza_salvo_nueva(entorno):
    _enviar(entorno["raiz"], carpeta="No existe")
    _enviar(entorno["raiz"], carpeta="Obra nueva", nueva=True)
    r = dc.atender(entorno["raiz"], entorno["raices"])
    assert r["rechazados"] == 1 and r["aplicados"] == 1
    assert (entorno["chile"] / "Obra nueva" / "Factura 1.pdf").is_file()
    assert not (entorno["chile"] / "No existe").exists()


def test_rechaza_rutas_y_extensiones_peligrosas(entorno):
    _enviar(entorno["raiz"], carpeta="../Excel")
    _enviar(entorno["raiz"], archivos={"planilla.xlsx": b"x"})
    r = dc.atender(entorno["raiz"], entorno["raices"])
    assert r["rechazados"] == 2
    assert not (entorno["chile"].parent / "Excel").exists()


def test_sin_el_sitio_del_cc_sincronizado_espera(entorno, tmp_path):
    _enviar(entorno["raiz"])
    r = dc.atender(entorno["raiz"], {"CL": tmp_path / "no-sincronizado"})
    assert r["esperan"] == 1
    assert len(list((entorno["raiz"] / "buzon").glob("*.json"))) == 1


def test_borra_adjuntos_huerfanos_viejos(entorno):
    base = entorno["raiz"] / "buzon" / "adjuntos"
    viejo, nuevo = base / "aaaaaaaaaaaa", base / "bbbbbbbbbbbb"
    for c in (viejo, nuevo):
        c.mkdir(parents=True)
        (c / "x.pdf").write_bytes(b"x")
    hace = time.time() - (dc.DIAS_ESPERA + 1) * 86400
    os.utime(viejo, (hace, hace))
    dc.atender(entorno["raiz"], entorno["raices"])
    assert not viejo.exists() and nuevo.exists()


def test_publica_las_carpetas(entorno):
    (entorno["chile"] / "280. Obra de ejemplo" / "f.pdf").write_bytes(b"x")
    (entorno["chile"] / "280. Obra de ejemplo" / "desktop.ini").write_bytes(b"x")
    assert dc.publicar_carpetas(entorno["raiz"], {"CL": entorno["chile"]}) == {"CL": 2}
    datos = intercambio.leer_publicacion(entorno["raiz"], dc.PUBLICACION)["datos"]
    assert datos["paises"]["CL"] == [{"nombre": "280. Obra de ejemplo", "req": "280", "documentos": 1},
                                     {"nombre": "Gastos Generales", "req": None, "documentos": 0}]
