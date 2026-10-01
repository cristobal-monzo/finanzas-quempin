# -*- coding: utf-8 -*-
"""El catálogo del intercambio: esquemas, ejemplos y paridad Python/JavaScript.

POR QUÉ ESTE TEST EXISTE

Un mensaje lo arma una herramienta (a veces en JavaScript, en el navegador)
y lo lee otra (a veces en Python). Si cada lado valida con su propio código,
terminan divergiendo -- ya pasó con el KPI "Nota del Proyecto" y con la
taxonomía en JavaScript. Por eso el formato vive en esquemas/*.json y hay
dos validadores (esquemas.py y esquemas.js) que este test obliga a responder
exactamente lo mismo sobre los mismos ejemplos.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import esquemas

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLOS = esquemas.CARPETA / "ejemplos"
RUTA_JS = RAIZ / "esquemas.js"

# Lo que entienden los dos validadores. Una palabra fuera de esta lista
# (patternProperties, $ref, oneOf...) se ignoraría en silencio.
PALABRAS_SOPORTADAS = {
    "$schema", "title", "description", "destino", "dueno",
    "type", "const", "enum", "required", "properties", "additionalProperties",
    "items", "minItems", "minLength", "pattern", "minimum", "exclusiveMinimum", "maximum", "anyOf",
}


def _todos_los_esquemas():
    return sorted(p for p in esquemas.CARPETA.rglob("*.json") if "ejemplos" not in p.parts)


def _ejemplos():
    for carpeta in ("mensajes", "publicaciones"):
        for d in sorted((EJEMPLOS / carpeta).iterdir()):
            for f in sorted(d.glob("*.json")):
                yield carpeta, d.name, f


def _palabras(nodo, salida, dentro_de_mapa=False):
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if not dentro_de_mapa:
                salida.add(clave)
            # 'properties' es un mapa nombre -> esquema: sus claves son nombres de campo
            _palabras(valor, salida, dentro_de_mapa=(clave == "properties" and not dentro_de_mapa))
    elif isinstance(nodo, list):
        for x in nodo:
            _palabras(x, salida)


def _validar_py(carpeta, nombre, obj):
    if carpeta == "mensajes":
        return esquemas.validar_mensaje(obj)
    return esquemas.validar_publicacion(nombre, obj)


@pytest.mark.parametrize("ruta", _todos_los_esquemas(), ids=lambda p: p.relative_to(esquemas.CARPETA).as_posix())
def test_cada_esquema_usa_solo_lo_que_entienden_los_validadores(ruta):
    palabras = set()
    _palabras(json.loads(ruta.read_text(encoding="utf-8")), palabras)
    assert palabras <= PALABRAS_SOPORTADAS, sorted(palabras - PALABRAS_SOPORTADAS)


def test_cada_tipo_y_publicacion_tiene_ejemplos_validos_e_invalidos():
    for carpeta, nombres in (("mensajes", esquemas.tipos_de_mensaje()), ("publicaciones", esquemas.publicaciones())):
        for nombre in nombres:
            archivos = [f.stem for f in (EJEMPLOS / carpeta / nombre).glob("*.json")]
            assert any(a.startswith("valido") for a in archivos), f"{carpeta}/{nombre} sin ejemplo válido"
            assert any(a.startswith("invalido") for a in archivos), f"{carpeta}/{nombre} sin ejemplo inválido"


@pytest.mark.parametrize("carpeta,nombre,ruta", list(_ejemplos()),
                         ids=lambda x: x.stem if isinstance(x, Path) else str(x))
def test_ejemplos_validos_pasan_e_invalidos_fallan(carpeta, nombre, ruta):
    errores = _validar_py(carpeta, nombre, json.loads(ruta.read_text(encoding="utf-8")))
    if ruta.stem.startswith("valido"):
        assert errores == []
    else:
        assert errores, "un ejemplo inválido pasó la validación"


def test_tipo_desconocido_se_valida_solo_por_el_sobre():
    m = json.loads((EJEMPLOS / "mensajes" / "venta-proyecto" / "valido-1.json").read_text(encoding="utf-8"))
    m["tipo"] = "tipo-que-no-existe"
    m["venta"] = "cualquier cosa"
    assert esquemas.validar_mensaje(m) == []


def test_sobre_invalido_no_sigue_con_el_contenido():
    assert esquemas.validar_mensaje({"tipo": "venta-proyecto"}) == [
        "(raíz): falta 'esquema'", "(raíz): falta 'id'", "(raíz): falta 'destino'", "(raíz): falta 'origen'",
    ]


def test_igualdad_estricta_verdadero_no_es_uno():
    assert esquemas.validar(1, {"const": True}) == ["(raíz): debe ser true"]
    assert esquemas.validar(True, {"enum": [1]}) != []


def test_publicacion_desconocida():
    assert esquemas.validar_publicacion("no-existe", {}) == ["publicación desconocida: 'no-existe'"]


def test_catalogo_y_paquete_cubren_todo():
    cat = esquemas.catalogo()
    assert set(cat["mensajes"]) == set(esquemas.tipos_de_mensaje())
    assert all(f.get("destino") for f in cat["mensajes"].values()), "cada tipo declara su destino"
    assert all(f.get("dueno") for f in cat["publicaciones"].values()), "cada publicación declara su dueño"
    paquete = esquemas.paquete()
    assert set(paquete["mensajes"]) == set(esquemas.tipos_de_mensaje())
    assert set(paquete["publicaciones"]) == set(esquemas.publicaciones())


# ── PARIDAD CON esquemas.js ──────────────────────────────────────────────────

_SCRIPT_NODE = r"""
const fs = require('fs');
const V = require(process.argv[2]);
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
const salida = entrada.casos.map((c) => c.carpeta === 'mensajes'
  ? V.validarMensaje(c.objeto, entrada.paquete)
  : V.validarPublicacion(c.nombre, c.objeto, entrada.paquete));
process.stdout.write(JSON.stringify(salida));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado en esta máquina")
def test_esquemas_js_responde_lo_mismo_que_esquemas_py(tmp_path):
    casos = [{"carpeta": c, "nombre": n, "objeto": json.loads(r.read_text(encoding="utf-8")), "archivo": r.name}
             for c, n, r in _ejemplos()]
    # Casos borde que los ejemplos no cubren.
    raros = [
        {"carpeta": "mensajes", "nombre": "x", "objeto": {"esquema": 1, "id": "corto"}},
        {"carpeta": "publicaciones", "nombre": "folios", "objeto": {"esquema": "quempin.intercambio/1"}},
        {"carpeta": "publicaciones", "nombre": "no-existe", "objeto": {}},
    ]
    casos += [dict(r, archivo=f"raro-{i}") for i, r in enumerate(raros)]
    script = tmp_path / "paridad.js"
    script.write_text(_SCRIPT_NODE, encoding="utf-8")
    entrada = json.dumps({"paquete": esquemas.paquete(), "casos": casos}, ensure_ascii=False)
    proc = subprocess.run(["node", str(script), str(RUTA_JS)], input=entrada.encode("utf-8"),
                          capture_output=True, check=True)
    resultados_js = json.loads(proc.stdout.decode("utf-8"))
    for caso, js in zip(casos, resultados_js):
        py = _validar_py(caso["carpeta"], caso["nombre"], caso["objeto"])
        # Se compara sin orden: JavaScript recorre primero las claves que
        # parecen números ("60", "81") y Python en el orden del archivo.
        assert sorted(js) == sorted(py), caso["archivo"]


def test_copia_del_formulador_es_textual():
    """El Formulador lleva una copia de esquemas.js (otro repositorio). Si
    está en esta máquina, tiene que ser idéntica a esta."""
    copia = RAIZ.parents[1] / "Formulación de proyectos" / "quempin-formulacion" / "js" / "esquemas.js"
    if not copia.exists():
        pytest.skip("el Formulador no está en esta máquina (o todavía no lleva la copia)")
    assert copia.read_bytes() == RUTA_JS.read_bytes(), "vuelve a copiar Sistema Intercambio/esquemas.js al Formulador"
