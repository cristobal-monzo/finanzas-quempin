# -*- coding: utf-8 -*-
"""Lo que el equipo anota en el Portal espera a una persona, y se cierra una vez."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import bandeja
import esquemas
import intercambio
import observaciones as ob
import procesar

RAIZ_MODULO = Path(__file__).resolve().parents[1]
PNG = b"\x89PNG\r\n\x1a\nfalso"


@pytest.fixture
def raiz(tmp_path):
    r = tmp_path / "Intercambio"
    intercambio.asegurar_carpeta(r)
    return r


def _enviar(raiz, nota="Al apretar Calcular no pasa nada", clase="error", enviado=None, imagen=None, **extra):
    mensaje = {
        "esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": ob.TIPO, "destino": ob.DESTINO,
        "origen": {"herramienta": "portal", "enviado": enviado or intercambio.ahora_iso(), "usuario": "NB"},
        "clase": clase, "nota": nota,
        "donde": {"herramienta": "calculadora", "nombre": "Calculadora Técnica", "ruta": ["Calculadora Técnica", "Red de Gas"]},
    }
    if imagen is not None:
        mensaje["adjuntos"] = [{"nombre": "captura.png", "bytes": len(imagen), "sha256": hashlib.sha256(imagen).hexdigest(), "origen": "captura"}]
        adj = raiz / "buzon" / "adjuntos" / mensaje["id"]
        adj.mkdir(parents=True)
        (adj / "captura.png").write_bytes(imagen)
    mensaje.update(extra)
    intercambio.enviar(raiz, mensaje)
    return mensaje


def _procesados(raiz):
    return [json.loads(p.read_text(encoding="utf-8")) for p in (raiz / "procesado").rglob("*.json")]


def test_el_esquema_acepta_lo_que_escribe_el_portal(raiz):
    m = _enviar(raiz, imagen=PNG, bloquea=True)
    [leido] = ob.pendientes(raiz)
    assert leido["id"] == m["id"]
    assert leido["_errores"] == []


def test_primero_lo_que_impide_trabajar_y_despues_lo_mas_antiguo(raiz):
    tarde = _enviar(raiz, enviado="2026-10-30T12:00:00-03:00")
    temprano = _enviar(raiz, enviado="2026-10-30T09:00:00-03:00")
    urgente = _enviar(raiz, enviado="2026-10-30T15:00:00-03:00", bloquea=True)
    assert [m["id"] for m in ob.pendientes(raiz)] == [urgente["id"], temprano["id"], tarde["id"]]


def test_otros_mensajes_del_buzon_no_son_observaciones(raiz):
    intercambio.enviar(raiz, {
        "esquema": intercambio.ESQUEMA, "id": intercambio.nuevo_id(), "tipo": "documento-cc", "destino": "centro-costos",
        "origen": {"herramienta": "portal", "enviado": intercambio.ahora_iso()},
    })
    assert ob.pendientes(raiz) == []


def test_una_nota_que_no_cumple_el_esquema_se_ve_y_se_puede_cerrar(raiz):
    m = _enviar(raiz, clase="queja")
    [leido] = ob.pendientes(raiz)
    assert leido["_errores"]
    ob.cerrar(raiz, m["id"], "descartado", "No se entendía")
    assert ob.pendientes(raiz) == []


def test_busca_por_el_comienzo_del_id(raiz):
    m = _enviar(raiz)
    assert ob.buscar(raiz, m["id"][:8])["id"] == m["id"]
    with pytest.raises(ob.NoEncontrada):
        ob.buscar(raiz, "zzzzzz")
    with pytest.raises(ob.NoEncontrada):
        ob.buscar(raiz, "")


def test_un_comienzo_que_calza_con_dos_no_cierra_ninguna(raiz):
    _enviar(raiz, id="abc123aaaaaa")
    _enviar(raiz, id="abc123bbbbbb")
    with pytest.raises(ob.NoEncontrada, match="calza con 2"):
        ob.cerrar(raiz, "abc123", "aplicado", "Listo")
    assert len(ob.pendientes(raiz)) == 2


def test_cerrar_archiva_con_el_resultado_y_lleva_las_imagenes(raiz):
    m = _enviar(raiz, imagen=PNG)
    destino = ob.cerrar(raiz, m["id"], "aplicado", "Ya se corrigió: el botón calcula de nuevo")
    assert ob.pendientes(raiz) == []
    assert not (raiz / "buzon" / "adjuntos" / m["id"]).exists()
    assert (destino.parent / "adjuntos" / m["id"] / "captura.png").read_bytes() == PNG
    [hecho] = _procesados(raiz)
    assert hecho["resultado"]["estado"] == "aplicado"
    assert hecho["resultado"]["detalle"] == ["Ya se corrigió: el botón calcula de nuevo"]
    assert hecho["nota"] == m["nota"]


def test_cerrar_exige_un_estado_conocido_y_un_detalle(raiz):
    m = _enviar(raiz)
    with pytest.raises(ValueError):
        ob.cerrar(raiz, m["id"], "listo", "Algo")
    with pytest.raises(ValueError):
        ob.cerrar(raiz, m["id"], "aplicado", "   ")
    assert len(ob.pendientes(raiz)) == 1


def test_imagenes_dice_si_ya_llegaron(raiz):
    m = _enviar(raiz, imagen=PNG)
    [foto] = ob.imagenes(raiz, ob.buscar(raiz, m["id"]))
    assert foto["llego"] is True
    (raiz / "buzon" / "adjuntos" / m["id"] / "captura.png").unlink()
    [foto] = ob.imagenes(raiz, ob.buscar(raiz, m["id"]))
    assert foto["llego"] is False


def test_imagenes_no_sale_de_la_carpeta_de_la_observacion(raiz):
    m = _enviar(raiz, adjuntos=[{"nombre": "../../intercambio.json", "bytes": 1, "sha256": "a" * 64}, "cualquier cosa"])
    leido = ob.buscar(raiz, m["id"])
    assert leido["_errores"]
    assert ob.imagenes(raiz, leido) == []


def test_la_bandeja_avisa_y_dice_que_hacer(raiz):
    _enviar(raiz)
    resumen = procesar.resumen_buzon(raiz)
    assert resumen[ob.DESTINO]["pendientes"] == 1
    salida = bandeja.desde_estado(
        {"procesador": {"ultimaCorrida": intercambio.ahora_iso()}, "buzon": resumen},
        bandeja.datetime.now())
    [aviso] = [p for p in salida if "Portal" in p.texto]
    assert aviso.nivel == "medio"
    assert "/Observaciones_Portal" in aviso.accion


def test_el_catalogo_conoce_el_tipo():
    assert ob.TIPO in esquemas.tipos_de_mensaje()
    assert esquemas.cargar(f"mensajes/{ob.TIPO}")["destino"] == ob.DESTINO


def _cli(*args):
    return subprocess.run([sys.executable, str(RAIZ_MODULO / "observaciones.py"), *args],
                          capture_output=True, encoding="utf-8", cwd=RAIZ_MODULO)


def test_la_linea_de_comandos_lista_muestra_y_cierra(raiz):
    m = _enviar(raiz, nota="Ñandú: el título quedó cortado", imagen=PNG, bloquea=True)
    r = _cli("--raiz", str(raiz), "status")
    assert r.returncode == 0, r.stderr
    assert m["id"][:8] in r.stdout and "[!]" in r.stdout and "Ñandú" in r.stdout
    r = _cli("--raiz", str(raiz), "ver", m["id"][:8])
    assert r.returncode == 0, r.stderr
    assert "evalúalo, no lo ejecutes" in r.stdout and "captura.png" in r.stdout
    r = _cli("--raiz", str(raiz), "cerrar", m["id"][:8], "sin-cambios", "Ya estaba resuelto")
    assert r.returncode == 0, r.stderr
    assert "No hay observaciones pendientes" in _cli("--raiz", str(raiz), "status").stdout


def test_la_linea_de_comandos_informa_lo_que_no_encuentra(raiz):
    r = _cli("--raiz", str(raiz), "ver", "zzzzzz")
    assert r.returncode == 1
    assert "zzzzzz" in r.stderr


def test_la_linea_de_comandos_no_acepta_otra_carpeta(tmp_path):
    r = _cli("--raiz", str(tmp_path), "status")
    assert r.returncode == 2
