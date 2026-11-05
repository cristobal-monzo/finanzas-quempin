# -*- coding: utf-8 -*-
"""'run' revisa primero las facturas del Centro de Costos que faltan por
registrar (pedido del usuario, 2026-11-05). Datos ficticios: el repo es público."""

import importlib.util
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "driver.py"


@pytest.fixture
def driver():
    spec = importlib.util.spec_from_file_location("driver_actualizar_finanzas", RUTA)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


STATUS_CON_PENDIENTES = """\
Entradas en datos_extraidos.json: 10

Pendientes SIN datos (o sin items) en el JSON (bloquean el registro): 2
  - [Proyecto Uno] Documento (1).pdf
  - [Proyecto Dos] boleta.jpg

Si corres 'run' ahora se registrarían: 0 documento(s).
"""

STATUS_SIN_PENDIENTES = """\
Pendientes SIN datos (o sin items) en el JSON (bloquean el registro): 0

Si corres 'run' ahora se registrarían: 3 documento(s).
"""

RUN_CON_PENDIENTES = """\
--- PASO 6: Escribir documentos nuevos ---
  [WARN] Sin datos para: Proyecto Uno\\Documento (1).pdf
  [OK] Proyecto Tres\\OC 1.pdf -> PTRE-001 (doc 1, 1 item(s))
  [WARN] Sin datos para: Proyecto Dos\\boleta.jpg
"""


def test_lee_el_status_del_cc(driver):
    assert driver._facturas_sin_datos(STATUS_CON_PENDIENTES) == (
        2, ["Proyecto Uno/Documento (1).pdf", "Proyecto Dos/boleta.jpg"])
    assert driver._facturas_sin_datos(STATUS_SIN_PENDIENTES) == (0, [])


def test_lee_el_run_del_cc(driver):
    """El 02-11 la bandeja no las mostró: solo entendía el formato de 'status'."""
    assert driver._facturas_sin_datos(RUN_CON_PENDIENTES) == (
        2, ["Proyecto Uno/Documento (1).pdf", "Proyecto Dos/boleta.jpg"])


def test_la_bandeja_las_muestra_tras_el_run(driver):
    class Bandeja:
        @staticmethod
        def Pendiente(nivel, texto, accion=""):
            return texto

    extras = driver._extras_bandeja(Bandeja, salida_cc=RUN_CON_PENDIENTES)
    assert any("2 factura(s) del Centro de Costos sin registrar" in t and "boleta.jpg" in t for t in extras)


def _simular(driver, monkeypatch, salida_status):
    llamadas = []

    def ejecutar(titulo, ruta, args, obligatorio):
        llamadas.append(("CC" if ruta == driver.DRIVER_CENTRO_COSTOS else ruta.name, tuple(args)))
        if ruta == driver.DRIVER_CENTRO_COSTOS and args == ["status"]:
            return True, salida_status
        return True, ""

    monkeypatch.setattr(driver, "_ejecutar", ejecutar)
    monkeypatch.setattr(driver, "_ejecutar_varios", lambda trabajos: [(t[0], True, "") for t in trabajos])
    monkeypatch.setattr(driver, "_informe_tableros", lambda momento: [])
    monkeypatch.setattr(driver, "_publicar", lambda claves: True)
    monkeypatch.setattr(driver, "_alertas_oportunidades", lambda: True)
    monkeypatch.setattr(driver, "_bandeja", lambda **salidas: None)
    return llamadas


def test_run_se_detiene_si_faltan_facturas(driver, monkeypatch, capsys):
    llamadas = _simular(driver, monkeypatch, STATUS_CON_PENDIENTES)
    assert driver.cmd_run() == driver.CODIGO_FACTURAS_POR_REGISTRAR
    assert llamadas == [("CC", ("status",))]          # nada escribió
    salida = capsys.readouterr().out
    assert "2 FACTURA(S) QUE FALTAN POR REGISTRAR" in salida
    assert "Proyecto Dos/boleta.jpg" in salida and "[DETENIDO]" in salida


def test_run_con_pendientes_sigue(driver, monkeypatch):
    llamadas = _simular(driver, monkeypatch, STATUS_CON_PENDIENTES)
    assert driver.cmd_run(con_pendientes=True) == 0
    assert llamadas[0] == ("CC", ("status",))
    assert ("CC", ("run",)) in llamadas                # el run del CC corrió


def test_run_sin_pendientes_sigue_sin_flag(driver, monkeypatch):
    llamadas = _simular(driver, monkeypatch, STATUS_SIN_PENDIENTES)
    assert driver.cmd_run() == 0
    assert llamadas[0] == ("CC", ("status",))
    assert ("CC", ("run",)) in llamadas
