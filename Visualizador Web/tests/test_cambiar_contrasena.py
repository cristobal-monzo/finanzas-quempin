# -*- coding: utf-8 -*-
"""cambiar_contrasena.py (2026-11-18): cada sobre se abre con la contraseña anterior y se cifra con la nueva, sin
regenerar los tableros. Contraseñas de mentira y carpetas temporales: nada toca gh-pages ni el Formulador."""
import json
import sys
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import candado  # noqa: E402
import cambiar_contrasena as cc  # noqa: E402

VIEJA, NUEVA, OTRA = "vieja de mentira 1", "nueva de mentira 2", "otra de mentira 3"


def _tablero(datos, contrasena):
    sobre = candado.cifrar(json.dumps(datos), contrasena)
    return ('<!DOCTYPE html><script>/* "kdf":"PBKDF2-SHA256" en el código no es un sobre */</script>\r\n'
            f'<script id="cc-data-b64" type="text/plain">{sobre}</script>\r\n<p>fin</p>')


def _sitio(tmp_path):
    raiz = tmp_path / "gh-pages"
    (raiz / "analisis-financiero" / "reportes").mkdir(parents=True)
    (raiz / "portal" / "datos").mkdir(parents=True)
    (raiz / "analisis-financiero" / "index.html").write_bytes(_tablero({"a": 1}, VIEJA).encode("utf-8"))
    (raiz / "analisis-financiero" / "reportes" / "abc123.json").write_text(
        candado.cifrar_bytes(b"%PDF-1.4 de mentira", VIEJA), encoding="utf-8")
    (raiz / "portal" / "datos" / "estado.json").write_text(candado.cifrar_bytes(b"{}", VIEJA, True), encoding="utf-8")
    (raiz / "portal" / "index.html").write_text("<html>sin datos</html>", encoding="utf-8")
    (raiz / "candado.js").write_text("var x = 'PBKDF2-SHA256';", encoding="utf-8")
    return raiz


def test_encuentra_solo_lo_cifrado_y_deja_fuera_el_resumen_del_telefono(tmp_path):
    raiz = _sitio(tmp_path)
    rels = [p.relative_to(raiz).as_posix() for p in cc.archivos_cifrados(raiz)]
    assert rels == ["analisis-financiero/index.html", "analisis-financiero/reportes/abc123.json"]


def test_recifra_con_la_nueva_y_los_datos_quedan_iguales(tmp_path):
    raiz = _sitio(tmp_path)
    rutas = cc.archivos_cifrados(raiz)
    antes = (raiz / "analisis-financiero" / "index.html").read_bytes()
    hechos = cc.recifrar_archivos(rutas, VIEJA, NUEVA)
    assert sorted(hechos.values()) == [1, 1]
    assert cc.no_abren(rutas, NUEVA) == [] and len(cc.no_abren(rutas, VIEJA)) == 2
    html = (raiz / "analisis-financiero" / "index.html").read_text(encoding="utf-8")
    assert candado.leer_datos(html, "cc-data-b64", NUEVA) == {"a": 1}
    assert candado.abre_con(html, NUEVA, carpeta=raiz / "analisis-financiero")
    # Lo que no es sobre queda byte a byte (los CRLF incluidos) y el sobre conserva su gzip
    despues = (raiz / "analisis-financiero" / "index.html").read_bytes()
    assert despues.split(b'type="text/plain">')[0] == antes.split(b'type="text/plain">')[0]
    assert despues.endswith(b"</script>\r\n<p>fin</p>")
    assert '"comp":"gzip"' in html
    pdf = (raiz / "analisis-financiero" / "reportes" / "abc123.json").read_text(encoding="utf-8")
    assert candado.descifrar_bytes(pdf, NUEVA) == b"%PDF-1.4 de mentira" and '"comp":null' in pdf


def test_una_segunda_corrida_no_cambia_lo_que_ya_abre_con_la_nueva(tmp_path):
    raiz = _sitio(tmp_path)
    rutas = cc.archivos_cifrados(raiz)
    cc.recifrar_archivos(rutas, VIEJA, NUEVA)
    antes = {r: r.read_bytes() for r in rutas}
    assert set(cc.recifrar_archivos(rutas, VIEJA, NUEVA).values()) == {0}
    assert {r: r.read_bytes() for r in rutas} == antes


def test_un_sobre_que_no_abre_con_ninguna_de_las_dos_detiene_todo(tmp_path):
    raiz = _sitio(tmp_path)
    (raiz / "analisis-financiero" / "reportes" / "abc123.json").write_text(
        candado.cifrar_bytes(b"x", OTRA), encoding="utf-8")
    with pytest.raises(InvalidTag):
        cc.recifrar_archivos(cc.archivos_cifrados(raiz), VIEJA, NUEVA)


def test_sin_escribir_solo_cuenta(tmp_path):
    raiz = _sitio(tmp_path)
    rutas = cc.archivos_cifrados(raiz)
    antes = {r: r.read_bytes() for r in rutas}
    assert sorted(cc.recifrar_archivos(rutas, VIEJA, NUEVA, escribir=False).values()) == [1, 1]
    assert {r: r.read_bytes() for r in rutas} == antes


def test_la_contrasena_nueva_es_larga_y_cambia_cada_vez():
    vistas = {cc.nueva_contrasena() for _ in range(50)}
    assert len(vistas) == 50
    for c in vistas:
        partes = c.split("-")
        assert len(partes) == 5 and partes[-1].isdigit() and len(partes[-1]) == 4
        assert candado.normalizar(c) == c          # sin mayúsculas ni tildes: se escribe igual en el teléfono
    assert len(set(cc.PALABRAS)) >= 256


def test_cambiar_no_imprime_la_contrasena():
    # La única salida del script con la contraseña es el archivo: ni un print la nombra
    fuente = Path(cc.__file__).read_text(encoding="utf-8")
    assert "print(nueva" not in fuente and "{nueva}" not in fuente and "{vieja}" not in fuente
