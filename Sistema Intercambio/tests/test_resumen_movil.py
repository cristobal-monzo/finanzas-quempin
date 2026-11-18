# -*- coding: utf-8 -*-
"""El resumen cifrado del Portal en el teléfono (resumen_movil.py, 2026-11-18). El Portal que lo lee se prueba en
Visualizador Web/tests/portal/test_portal_movil.py."""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "Visualizador Web"))
import candado  # noqa: E402
import resumen_movil as rm  # noqa: E402

CLAVE = "clave de mentira del resumen"


def _carpeta(tmp_path, hoy=date(2026, 11, 18)):
    raiz = tmp_path / "Intercambio"
    lunes = hoy - timedelta(days=hoy.weekday())
    semana = "%d-W%02d" % lunes.isocalendar()[:2]
    archivos = {
        "publicado/requerimientos.json": {"datos": {"requerimientos": [{"numero": 900}]}},
        "publicado/proyectos.json": {"datos": {"proyectos": []}},
        "publicado/analisis-financiero.json": {"datos": {"proyectos": [{"tag": "DEMO"}]}},
        "publicado/licitaciones.json": {"datos": {"licitaciones": []}},
        "publicado/estado.json": {"datos": {"procesador": {"ultimaCorrida": "2026-11-18T10:00:00"}}},
        "publicado/documentos-proyecto.json": {"datos": {}},
        "publicado/precios-referencia.json": {"datos": {"precios": [1, 2, 3]}},
        "publicado/contrapartes.json": {"datos": {}},
        "publicado/uso-portal/x.json": {"datos": {}},
        "publicado/presencia/x.json": {"datos": {}},
        "publicado/formulador/f1.json": {"datos": {"codigo": "QMPN-1"}},
        "publicado/ejecucion/x.json": {"datos": {"items": []}},
        "publicado/gantt/g.json": {"datos": {}},
        f"publicado/planificacion/{semana}/x.json": {"datos": {"semana": semana}},
        "publicado/planificacion/2025-W01/x.json": {"datos": {"semana": "vieja"}},
        "publicado/planificacion/lista/x.json": {"datos": {}},
        "buzon/20261118-100000_portal_editar-requerimiento_a.json": {"tipo": "editar-requerimiento"},
        "procesado/2026-11/m.json": {"tipo": "x"},
    }
    for ruta, d in archivos.items():
        (raiz / ruta).parent.mkdir(parents=True, exist_ok=True)
        (raiz / ruta).write_text(json.dumps(d), encoding="utf-8")
    (raiz / "buzon" / "grande.json").write_text(json.dumps({"x": "a" * (rm.MAX_BUZON + 1)}), encoding="utf-8")
    (raiz / "buzon" / "a-medias.json").write_text('{"sin cerrar', encoding="utf-8")
    return raiz, semana


def _abrir(salida, parte):
    return json.loads(candado.descifrar_bytes((salida / f"{parte}.json").read_text(encoding="ascii"), CLAVE))["archivos"]


def test_el_resumen_lleva_lo_que_el_portal_lee_y_nada_mas(tmp_path):
    raiz, semana = _carpeta(tmp_path)
    salida = tmp_path / "salida"
    ahora = datetime(2026, 11, 18, 14, 35).astimezone()
    r = rm.armar(raiz, salida, ahora, contrasena=CLAVE)
    assert sorted(r["cambiadas"]) == sorted(rm.PARTES)
    rutas = {ruta for p in rm.PARTES for ruta in _abrir(salida, p)}
    assert rutas == {
        "publicado/requerimientos.json", "publicado/proyectos.json", "publicado/analisis-financiero.json",
        "publicado/licitaciones.json", "publicado/estado.json", "publicado/documentos-proyecto.json",
        "publicado/formulador/f1.json", "publicado/ejecucion/x.json", "publicado/gantt/g.json",
        f"publicado/planificacion/{semana}/x.json", "publicado/planificacion/lista/x.json",
        "buzon/20261118-100000_portal_editar-requerimiento_a.json"}
    base = _abrir(salida, "base")
    assert base["publicado/requerimientos.json"]["d"] == {"datos": {"requerimientos": [{"numero": 900}]}}
    assert isinstance(base["publicado/requerimientos.json"]["m"], int)
    indice = json.loads((salida / "indice.json").read_text(encoding="utf-8"))
    assert indice["revisado"].startswith("2026-11-18T14:35") and set(indice["partes"]) == set(rm.PARTES)
    assert rm.abre_con(salida, CLAVE) == [] and rm.abre_con(salida, "otra") == sorted(rm.PARTES, key=list(rm.PARTES).index)
    # Ni el precio de referencia ni el texto de la contraseña quedan a la vista en lo que se sube
    for f in salida.iterdir():
        t = f.read_text(encoding="utf-8")
        assert "precios" not in t and "QMPN" not in t and CLAVE not in t


def test_una_parte_que_no_cambio_conserva_su_sobre(tmp_path):
    """gh-pages guarda cada versión: lo que no cambió no debe volver a subirse distinto (el cifrado cambia cada vez)."""
    raiz, semana = _carpeta(tmp_path)
    salida = tmp_path / "salida"
    rm.armar(raiz, salida, contrasena=CLAVE)
    antes = {p: (salida / f"{p}.json").read_bytes() for p in rm.PARTES}
    (raiz / "publicado" / "planificacion" / semana / "y.json").write_text('{"datos": {}}', encoding="utf-8")
    r = rm.armar(raiz, salida, contrasena=CLAVE)
    assert r["cambiadas"] == ["planificacion"]
    for p in rm.PARTES:
        assert ((salida / f"{p}.json").read_bytes() == antes[p]) == (p != "planificacion")


@pytest.mark.parametrize("hora,dia,estado,cambiadas,esperado", [
    (10, 2, {}, [], "latido"),                                                        # nunca se subió
    (10, 2, {"subido": "2026-11-18T09:50:00"}, [], None),                             # latido hace 10 min
    (10, 2, {"subido": "2026-11-18T08:55:00"}, [], "latido"),                         # más de una hora
    (10, 2, {"subido": "2026-11-18T09:50:00"}, ["base"], None),                       # cambio, pero hace 10 min
    (10, 2, {"subido": "2026-11-18T09:25:00"}, ["base"], "cambió base"),              # cambio y más de 30 min
    (10, 2, {"subido": "2026-11-18T09:25:00", "pendientes": ["planificacion"]}, [], "cambió planificacion"),
    (10, 2, {"subido": "2026-11-18T09:25:00"}, ["estado"], None),                     # el latido del procesador no cuenta
    (21, 2, {}, ["base"], None),                                                      # de noche no
    (10, 6, {}, ["base"], None),                                                      # domingo no
    (10, 5, {}, ["base"], "cambió base"),                                             # sábado sí
])
def test_cuando_toca_subir(hora, dia, estado, cambiadas, esperado):
    ahora = datetime(2026, 11, 16 + dia, hora, 0)          # 16 = lunes
    if "subido" in estado:
        estado = dict(estado, subido=estado["subido"].replace("2026-11-18", ahora.date().isoformat()))
    assert rm.toca_subir(estado, cambiadas, ahora) == esperado


def test_nunca_lleva_lo_prohibido():
    """Aunque alguien agregue una ruta a PARTES, NUNCA la saca: el Flujo de Caja, los precios y lo que solo se escribe."""
    assert {"precios-referencia", "flujo-de-caja", "uso-portal", "presencia", "procesado"} <= set(rm.NUNCA)
