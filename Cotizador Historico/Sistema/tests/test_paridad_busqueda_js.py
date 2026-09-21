# -*- coding: utf-8 -*-
"""El buscador de Python y el del navegador tienen que responder lo mismo.

POR QUE ESTE TEST EXISTE

El dashboard busca en el navegador (el HTML publicado no hace llamadas de
red) y la consola busca en Python. Son dos implementaciones del mismo
ranking, y este proyecto ya sabe como termina eso: la taxonomia vivio
duplicada en JavaScript dentro de los dos template.html hasta 2026-09-08 y
divergio sin que nadie se enterara -- Peru nunca recibio una categoria que
Chile si tenia. Lo mismo paso antes con el KPI "Nota del Proyecto"
(2026-07-28).

La defensa estructural ya esta puesta: el lado del DOCUMENTO se calcula una
sola vez en Python (busqueda.indexar_para_snapshot) y las TABLAS salen de
catalogo_busqueda.py via el snapshot, asi que el JavaScript no tiene copia
propia de ninguna de las dos cosas. Lo que si esta escrito dos veces es el
lado de la CONSULTA: normalizar, leer la medida y puntuar. Este test corre
las mismas consultas por los dos motores y exige el mismo orden.

Si falla, NO se ajusta el JavaScript hasta que pase: se mira cual de los dos
tiene razon. El que suele estar mal es el que se toco ultimo.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import busqueda

RAIZ_MODULO = Path(__file__).resolve().parents[2]
RUTA_JS = RAIZ_MODULO / "Visualizador Web" / "busqueda.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node no esta instalado en esta maquina")


def _item(n_ref, nombre, descripcion):
    return {"n_ref": n_ref, "nombre_item": nombre, "descripcion": descripcion,
            "excluido_motivo": None}


# El mismo corpus que test_busqueda_ranking, mas casos que estresan la
# normalizacion (tildes, ñ, comillas tipograficas, codigos).
CORPUS = [
    _item("V-2", "Valvula bola", "Válvula bola italiana p/estopa Enolgas (08) 2 plg"),
    _item("V-2b", "Válvula", 'Válvula bola Bugatti P/T 2" HI-HI M/MET'),
    _item("V-12", "Valvula bola", "Válvula bola Bugatti P/T 1/2 HI HI M/MET"),
    _item("V-34", "Válvula de bola", 'Válvula bola paso 3/4" acero'),
    _item("V-114", "Valvula bola", "Válvula bola paso total 1 1/4"),
    _item("V-212", "Valvula bola", 'Válvula bola paso total 2.1/2"'),
    _item("V-RET", "Valvula retencion", "Válvula retención vertical Bugatti 2 A/BR HI HI"),
    _item("V-PPR", "Válvula bola", "Válvula bola PPR 50mm 2UA fusión/fusión"),
    _item("C-BR114", "Codo bronce", "Codo SO BR (05) 1.1/4 plg"),
    _item("C-BR112", "Codo bronce", "Codo SO BR (06) 1.1/2 plg"),
    _item("CA-CU12", "Cañeria de cobre", "Cañeria de cobre tipo L 1/2 x 1 metro"),
    _item("G-1", "Guante", "Guante de trabajo cuero spandex"),
    _item("T-1", "Taladro percutor 20V 13mm s/carbones DCD7781", "Cod. 885911729369"),
    _item("M-1", "Manometro", "Manómetro c/glicerina 0-10 bar"),
    _item("TAP-1", "Tapón auditivo", "Tapones reusables para oídos con cordel"),
    _item("TAP-2", "Tapagorro", "Tapagorro BR NI 1/2"),
    _item("N-GALV", "Niple galvanizado", 'Niple galv. 1/2" x 10 cm'),
    _item("E-6010", "Electrodo", "Electrodo 6010 3/32 Indura, 5 kg"),
]

CONSULTAS = [
    'Válvula de bola de 2"',
    "valvula bola 2",
    "válvula 2 pulgadas",
    'bola 2"',
    "válvula esférica 2 in",
    'válbula de vola 2"',
    "valvula de bola dn50",
    'Valvula 2" bola',
    'valvula bola 1/2"',
    "codo bronce 1.1/4",
    "codo de bronce 1 1/4",
    "CAÑERIA DE COBRE",
    "caneria cobre 1/2",
    "tuberia de cobre",
    "guantes",
    "guante",
    "DCD7781",
    "manometro con glicerina",
    "tapones para los oidos",
    "niple galvanizado 1/2",
    "electrodo 6010",
    "valvula bola ppr 50mm",
    "arandela",
    "antiparras",
    "helicoptero",
    "valvula de compuerta",
    "  valvula   de   bola  ",
    "VÁLVULA DE BOLA DE 2”",
]


def _resultados_python(corpus, consultas):
    indice = busqueda.Indice(corpus)
    salida = {}
    for consulta in consultas:
        resultados, sugerencias = indice.buscar(consulta)
        salida[consulta] = {
            "orden": [r["item"]["n_ref"] for r in resultados],
            "medidas": sorted(busqueda.parsear_consulta(consulta)[1]),
            "terminos": list(busqueda.parsear_consulta(consulta)[0]),
            "desconocidos": list(indice.terminos_sin_resultado(consulta)),
            "sugerencias": sugerencias,
        }
    return salida


_GUION_NODE = r"""
const fs = require('fs');
require(process.argv[2]);
const entrada = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const buscador = globalThis.CHBusqueda.crear(entrada.items, entrada.cfg);
const salida = {};
for (const consulta of entrada.consultas) {
  const r = buscador.buscar(consulta);
  salida[consulta] = {
    orden: r.resultados.map(x => x.item.n_ref),
    medidas: r.medidas.slice().sort(),
    terminos: r.terminos,
    desconocidos: r.desconocidos,
    sugerencias: r.sugerencias,
  };
}
process.stdout.write(JSON.stringify(salida));
"""


def _resultados_js(corpus, consultas, tmp_path):
    items = [dict(it) for it in corpus]
    busqueda.indexar_para_snapshot(items)
    entrada = {
        "items": [{"n_ref": it["n_ref"], "nombre_item": it["nombre_item"],
                   "hoja": it.get("hoja"), "_bt": it["_bt"], "_bm": it["_bm"]}
                  for it in items],
        "cfg": busqueda.config_para_snapshot(
            sorted({m for it in items for m in it["_bm"]})),
        "consultas": consultas,
    }
    ruta_entrada = tmp_path / "entrada.json"
    ruta_entrada.write_text(json.dumps(entrada, ensure_ascii=False), encoding="utf-8")
    ruta_guion = tmp_path / "correr.js"
    ruta_guion.write_text(_GUION_NODE, encoding="utf-8")

    proc = subprocess.run(
        ["node", str(ruta_guion), str(RUTA_JS), str(ruta_entrada)],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise AssertionError(f"node fallo:\n{proc.stderr}")
    return json.loads(proc.stdout)


def test_el_archivo_js_existe_y_es_uno_solo():
    """Chile y Peru inyectan ESTE archivo; ninguno tiene su propia copia."""
    assert RUTA_JS.exists()
    peru = RAIZ_MODULO.parent / "Peru" / "Cotizador Historico" / "Visualizador Web" / "busqueda.js"
    assert not peru.exists(), (
        "Peru no debe tener su propio busqueda.js -- su build inyecta el de Chile")


@pytest.fixture(scope="module")
def comparacion(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("paridad")
    return _resultados_python(CORPUS, CONSULTAS), _resultados_js(CORPUS, CONSULTAS, tmp)


def test_los_dos_motores_leen_la_misma_medida(comparacion):
    py, js = comparacion
    for consulta in CONSULTAS:
        assert py[consulta]["medidas"] == js[consulta]["medidas"], consulta


def test_los_dos_motores_extraen_los_mismos_terminos(comparacion):
    py, js = comparacion
    for consulta in CONSULTAS:
        assert py[consulta]["terminos"] == js[consulta]["terminos"], consulta


def test_los_dos_motores_devuelven_el_mismo_orden(comparacion):
    py, js = comparacion
    for consulta in CONSULTAS:
        assert py[consulta]["orden"] == js[consulta]["orden"], (
            f"{consulta!r}: python={py[consulta]['orden']} js={js[consulta]['orden']}")


def test_los_dos_motores_coinciden_en_lo_que_no_encontraron(comparacion):
    py, js = comparacion
    for consulta in CONSULTAS:
        assert py[consulta]["desconocidos"] == js[consulta]["desconocidos"], consulta
        assert py[consulta]["sugerencias"] == js[consulta]["sugerencias"], consulta
