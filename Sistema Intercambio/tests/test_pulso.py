# -*- coding: utf-8 -*-
"""pulso.js (2026-10-08): cuándo las herramientas avisan que el procesador del
intercambio está detenido. Solo cuentan las horas hábiles: de noche o el fin de
semana, con el computador apagado, esperar no es una falla.

Las fechas se arman con la hora local de Node, igual que en el navegador, así
el resultado no depende de la zona horaria de la máquina que corre el test."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]          # Sistema Intercambio
RUTA_JS = RAIZ / "pulso.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado en esta máquina")

_SCRIPT = r"""
const fs = require('fs');
(0, eval)(fs.readFileSync(process.argv[2], 'utf8'));
const casos = JSON.parse(fs.readFileSync(0, 'utf8'));
const f = (a) => new Date(a[0], a[1] - 1, a[2], a[3], a[4]);   // [año, mes, día, hora, minuto] locales
const salida = casos.map((c) => {
  const estado = c.ultima ? { procesador: { ultimaCorrida: f(c.ultima).toISOString(), pasos: c.pasos || {} } } : null;
  const l = QPulso.lectura(estado, f(c.ahora));
  return l && { nivel: l.nivel, detenido: l.detenido, habiles: l.minutosHabiles, texto: l.texto };
});
process.stdout.write(JSON.stringify(salida));
"""


def _leer(casos, tmp_path):
    script = tmp_path / "pulso_prueba.js"
    script.write_text(_SCRIPT, encoding="utf-8")
    proc = subprocess.run(["node", str(script), str(RUTA_JS)], input=json.dumps(casos).encode("utf-8"),
                          capture_output=True, check=True)
    return json.loads(proc.stdout.decode("utf-8"))


# 2026-10-09 es viernes; 2026-10-12, lunes.
def test_media_hora_despues_de_una_vuelta_esta_al_dia(tmp_path):
    (r,) = _leer([{"ultima": [2026, 10, 9, 11, 0], "ahora": [2026, 10, 9, 11, 30]}], tmp_path)
    assert r["nivel"] == "ok" and not r["detenido"] and r["texto"] == "Las demás herramientas revisaron la carpeta hace 30 min."


def test_un_fin_de_semana_con_el_computador_apagado_no_es_una_falla(tmp_path):
    (r,) = _leer([{"ultima": [2026, 10, 9, 18, 0], "ahora": [2026, 10, 12, 9, 30]}], tmp_path)
    assert r["habiles"] == 60 + 60          # viernes 18:00-19:00 y lunes 08:30-09:30
    assert not r["detenido"] and r["nivel"] == "warn"


def test_mas_de_cuatro_horas_habiles_sin_correr_es_detenido(tmp_path):
    al_limite, pasado = _leer([
        {"ultima": [2026, 10, 12, 9, 0], "ahora": [2026, 10, 12, 13, 0]},
        {"ultima": [2026, 10, 12, 9, 0], "ahora": [2026, 10, 12, 13, 1]},
    ], tmp_path)
    assert not al_limite["detenido"]
    assert pasado["detenido"] and pasado["nivel"] == "bad"
    assert "no corre desde hace 4 h" in pasado["texto"] and "Avisa a quien administra" in pasado["texto"]


def test_la_noche_no_cuenta(tmp_path):
    (r,) = _leer([{"ultima": [2026, 10, 12, 18, 0], "ahora": [2026, 10, 13, 9, 0]}], tmp_path)
    assert r["habiles"] == 60 + 30 and not r["detenido"]


def test_un_paso_con_falla_se_ve(tmp_path):
    (r,) = _leer([{"ultima": [2026, 10, 12, 10, 0], "ahora": [2026, 10, 12, 10, 5],
                   "pasos": {"precios-referencia": {"ok": False}, "proyectos": {"ok": True}}}], tmp_path)
    assert r["nivel"] == "warn" and "con problemas en: precios-referencia" in r["texto"]


def test_sin_estado_no_hay_lectura(tmp_path):
    assert _leer([{"ultima": None, "ahora": [2026, 10, 12, 10, 0]}], tmp_path) == [None]


def test_copia_del_formulador_es_textual():
    """El Formulador lleva una copia de pulso.js (otro repositorio). Si está en
    esta máquina, tiene que ser idéntica a esta."""
    copia = RAIZ.parents[1] / "Formulación de proyectos" / "quempin-formulacion" / "js" / "pulso.js"
    if not copia.exists():
        pytest.skip("el Formulador no está en esta máquina")
    assert copia.read_bytes() == RUTA_JS.read_bytes(), "vuelve a copiar Sistema Intercambio/pulso.js al Formulador"
