# -*- coding: utf-8 -*-
"""Candado de los tableros (2026-10-05): lo publicado va cifrado.

Hasta esta fecha los tableros publicaban sus datos en base64 junto a la
contrasena escrita en claro, en un sitio y un repo publicos: cualquiera con el
link podia leerlos. Estos tests fijan lo que cambio: el sobre que va en el HTML
no deja ver ni los datos ni la contrasena, solo la contrasena correcta lo abre
(en Python y en el navegador, con la misma normalizacion), las 6 plantillas lo
usan, y la contrasena real nunca termina en un archivo versionado.
"""
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "Visualizador Web"))
import candado  # noqa: E402

hay_node = pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado en esta máquina")
hay_git = pytest.mark.skipif(shutil.which("git") is None or not (RAIZ / ".git").exists(), reason="sin git")

DATOS = json.dumps({"proyecto": "OBRA-SECRETA", "monto": 12_345_678, "cliente": "Ñandú Ltda."}, ensure_ascii=False)


def _plantillas():
    candidatas = (list(RAIZ.glob("*/Visualizador Web/template.html"))
                  + list(RAIZ.glob("Peru/*/Visualizador Web/template.html")))
    return sorted(p for p in candidatas if not any(parte.startswith(".") for parte in p.relative_to(RAIZ).parts))


PLANTILLAS = _plantillas()


def test_la_contrasena_correcta_abre_el_sobre_escrita_como_sea():
    sobre = candado.cifrar(DATOS, "Combustión Lenta")
    assert candado.descifrar(sobre, "  combustion LENTA ") == DATOS


def test_otra_contrasena_no_lo_abre():
    sobre = candado.cifrar(DATOS, "la buena")
    with pytest.raises(InvalidTag):
        candado.descifrar(sobre, "la mala")


def test_el_sobre_no_deja_ver_los_datos_ni_la_contrasena():
    sobre = candado.cifrar(DATOS, "clave-que-no-debe-aparecer")
    for rastro in ("OBRA-SECRETA", "12345678", "clave-que-no-debe-aparecer",
                   base64.b64encode(DATOS.encode("utf-8")).decode("ascii")[:24]):
        assert rastro not in sobre
    assert sobre.isascii() and "<" not in sobre          # va tal cual dentro de un <script>
    assert candado.cifrar(DATOS, "x") != candado.cifrar(DATOS, "x")   # IV nuevo en cada build


def test_los_datos_van_comprimidos_antes_de_cifrar():
    """Sobre version 2 (2026-10-08): lo cifrado no se puede comprimir, asi que
    se comprime antes. Los datos de los tableros son JSON muy repetitivo."""
    filas = json.dumps([{"proveedor": "Ferretería Ñandú", "monto": 12_345, "categoria": "Materiales"}] * 2000,
                       ensure_ascii=False)
    sobre = candado.cifrar(filas, "x")
    assert json.loads(sobre)["v"] == 2 and json.loads(sobre)["comp"] == "gzip"
    assert len(sobre) < len(filas) / 10
    assert candado.descifrar(sobre, "x") == filas


def test_un_sobre_version_1_se_sigue_abriendo():
    """Los tableros ya publicados llevan sobres sin comprimir hasta que se regeneran."""
    iv = b"\x01" * 12
    cifrado = candado.AESGCM(candado.derivar_clave("x")).encrypt(iv, DATOS.encode("utf-8"), None)
    sobre_v1 = json.dumps({"v": 1, "kdf": "PBKDF2-SHA256", "it": candado.ITERACIONES,
                           "sal": candado._b64(candado.SAL), "iv": candado._b64(iv), "datos": candado._b64(cifrado)})
    assert candado.descifrar(sobre_v1, "x") == DATOS


def test_un_archivo_aparte_se_cifra_sin_comprimir_y_con_nombre_por_su_contenido():
    pdf = b"%PDF-1.7 contenido de prueba " * 50
    sobre = candado.cifrar_bytes(pdf, "x")
    assert json.loads(sobre)["comp"] is None and candado.descifrar_bytes(sobre, "x") == pdf
    assert candado.nombre_archivo(pdf) == candado.nombre_archivo(pdf)        # mismo contenido, mismo archivo
    assert candado.nombre_archivo(pdf) != candado.nombre_archivo(pdf + b"!")
    assert candado.nombre_archivo(pdf).startswith("reportes/") and "PDF" not in candado.nombre_archivo(pdf)


def test_antes_de_publicar_tambien_se_revisan_los_archivos_que_citan_los_datos(tmp_path):
    pdf = b"%PDF-1.7 reporte"
    rel = candado.nombre_archivo(pdf)
    datos = json.dumps({"reportes_pdf": {"proyecto:X": {"archivo": rel, "fecha": "01-01-2026"}}})
    tablero = candado.incrustar(f"<script>{candado.MARCADOR_JS}</script>"
                                '<script id="xx-data-b64" type="text/plain">__XX__</script>', "__XX__", datos, "la real")
    assert candado.archivos_citados(json.loads(datos)) == [rel]
    assert not candado.abre_con(tablero, "la real", carpeta=tmp_path)          # falta la carpeta reportes/
    (tmp_path / "reportes").mkdir()
    (tmp_path / rel).write_text(candado.cifrar_bytes(pdf, "otra"), encoding="utf-8")
    assert not candado.abre_con(tablero, "la real", carpeta=tmp_path)          # cifrado con otra contraseña
    (tmp_path / rel).write_text(candado.cifrar_bytes(pdf, "la real"), encoding="utf-8")
    assert candado.abre_con(tablero, "la real", carpeta=tmp_path)
    assert candado.abre_con(tablero, "la real")                                # sin carpeta: solo el sobre


def test_sin_contrasena_no_se_construye_nada(monkeypatch, tmp_path):
    monkeypatch.delenv(candado.VARIABLE_CONTRASENA)
    monkeypatch.setattr(candado, "RUTA_CONTRASENA", tmp_path / "no-existe")
    with pytest.raises(candado.SinContrasena):
        candado.incrustar(f"{candado.MARCADOR_JS} __X__", "__X__", DATOS)
    (tmp_path / "vacia").write_text("  \n", encoding="utf-8")
    monkeypatch.setattr(candado, "RUTA_CONTRASENA", tmp_path / "vacia")
    with pytest.raises(candado.SinContrasena):
        candado.leer_contrasena()


def test_la_contrasena_se_lee_del_archivo_local(monkeypatch, tmp_path):
    monkeypatch.delenv(candado.VARIABLE_CONTRASENA)
    (tmp_path / "clave").write_text("Una Clave Local\n", encoding="utf-8")
    monkeypatch.setattr(candado, "RUTA_CONTRASENA", tmp_path / "clave")
    assert candado.leer_contrasena() == "Una Clave Local"


def test_antes_de_publicar_se_detecta_un_tablero_que_no_abre():
    """Lo que revisa `py -3.14 "Visualizador Web/candado.py" <index.html>` antes de
    publicar (2026-10-05: se publicó uno cifrado con la contraseña de prueba)."""
    tablero = candado.incrustar(f"<script>{candado.MARCADOR_JS}</script>"
                                '<script id="xx-data-b64" type="text/plain">__XX__</script>', "__XX__", DATOS, "la real")
    assert candado.abre_con(tablero, "La Real")
    assert not candado.abre_con(tablero, "la de prueba")
    sin_sobre = '<script id="xx-data-b64" type="text/plain">eyJhIjogMX0=</script>'   # base64 sin cifrar
    assert not candado.abre_con(sin_sobre, "la real")


def test_incrustar_pone_el_js_y_el_sobre():
    html = candado.incrustar(f"<script>{candado.MARCADOR_JS}</script>"
                             '<script id="xx-data-b64" type="text/plain">__XX__</script>', "__XX__", DATOS, "abc")
    assert "var QuempinCandado" in html and candado.MARCADOR_JS not in html and "__XX__" not in html
    assert candado.leer_datos(html, "xx-data-b64", "ABC")["monto"] == 12_345_678


_SCRIPT_NODE = r"""
const fs = require('fs');
(0, eval)(fs.readFileSync(process.argv[2], 'utf8'));
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
const sobre = JSON.parse(entrada.sobre);
const hex = (a) => Array.from(a, (b) => b.toString(16).padStart(2, '0')).join('');
Promise.all(entrada.intentos.map((c) =>
  QuempinCandado.derivar(c, sobre).then((clave) =>
    QuempinCandado.descifrar(clave, sobre).then((datos) => ({ clave: hex(clave), datos }), () => ({ clave: hex(clave), error: true })))))
  .then((r) => process.stdout.write(JSON.stringify(r)));
"""


@hay_node
def test_el_navegador_abre_lo_que_cifra_python(tmp_path):
    """candado.js (WebCrypto, lo mismo que corre en el navegador) con un sobre de candado.py."""
    sobre = candado.cifrar(DATOS, "Contraseña Ñandú")
    script = tmp_path / "candado_prueba.js"
    script.write_text(_SCRIPT_NODE, encoding="utf-8")
    entrada = {"sobre": sobre, "intentos": ["  CONTRASENA nandu", "otra"]}
    proc = subprocess.run(["node", str(script), str(candado.RUTA_JS)], capture_output=True, check=True,
                          input=json.dumps(entrada, ensure_ascii=False).encode("utf-8"))
    buena, mala = json.loads(proc.stdout.decode("utf-8"))
    assert buena["clave"] == candado.derivar_clave("Contraseña Ñandú").hex()   # misma normalización y misma clave
    assert buena["datos"] == json.loads(DATOS)                                 # sobre v2: descomprime en el navegador
    assert mala.get("error") is True


_SCRIPT_NODE_ARCHIVO = r"""
const fs = require('fs');
(0, eval)(fs.readFileSync(process.argv[2], 'utf8'));
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
const sobre = JSON.parse(entrada.sobre);
QuempinCandado.derivar(entrada.clave, sobre)
  .then((clave) => QuempinCandado.descifrarBytes(clave, sobre))
  .then((buf) => process.stdout.write(Buffer.from(buf).toString('base64')));
"""


@hay_node
def test_el_navegador_abre_un_archivo_cifrado_aparte(tmp_path):
    """Un reporte PDF: bytes sin comprimir, que el tablero baja al abrirlo."""
    pdf = b"%PDF-1.7 \x00\x01\x02 binario de prueba"
    script = tmp_path / "candado_archivo.js"
    script.write_text(_SCRIPT_NODE_ARCHIVO, encoding="utf-8")
    entrada = {"sobre": candado.cifrar_bytes(pdf, "Clave Ñ"), "clave": "clave n"}
    proc = subprocess.run(["node", str(script), str(candado.RUTA_JS)], capture_output=True, check=True,
                          input=json.dumps(entrada, ensure_ascii=False).encode("utf-8"))
    assert base64.b64decode(proc.stdout) == pdf


@pytest.mark.parametrize("ruta", PLANTILLAS, ids=lambda p: str(p.relative_to(RAIZ).parent.parent))
def test_cada_plantilla_abre_sus_datos_con_el_candado(ruta):
    html = ruta.read_text(encoding="utf-8")
    id_sobre = html.split('type="text/plain">__')[0].rsplit('<script id="', 1)[1].split('"')[0]
    assert f"<script>{candado.MARCADOR_JS}</script>" in html
    assert html.index(candado.MARCADOR_JS) < html.index(f'<script id="{id_sobre}"')
    assert f"QuempinCandado.abrir('{id_sobre}', initApp);" in html
    for resto in ("combustion", "GATE_PASSWORD", "quempin_viz_unlocked", "no seguridad real"):
        assert resto not in html


def test_estan_las_6_plantillas():
    assert len(PLANTILLAS) == 6, [str(p) for p in PLANTILLAS]


@hay_git
def test_el_archivo_de_la_contrasena_no_se_versiona():
    proc = subprocess.run(["git", "-C", str(RAIZ), "check-ignore", "-q", str(candado.RUTA_CONTRASENA)])
    assert proc.returncode == 0, ".contrasena_tableros tiene que estar en .gitignore"


@hay_git
@pytest.mark.skipif(not candado.RUTA_CONTRASENA.exists(), reason="solo en el equipo que tiene la contraseña real")
def test_la_contrasena_real_no_esta_en_ningun_archivo_versionado():
    real = candado.normalizar(candado.RUTA_CONTRASENA.read_text(encoding="utf-8"))
    archivos = subprocess.run(["git", "-C", str(RAIZ), "ls-files", "-z"], capture_output=True, check=True
                              ).stdout.decode("utf-8").split("\0")
    con_ella = []
    for rel in filter(None, archivos):
        ruta = RAIZ / rel
        if ruta.is_file() and real in candado.normalizar(ruta.read_bytes().decode("utf-8", errors="ignore")):
            con_ella.append(rel)
    assert con_ella == []
