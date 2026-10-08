# -*- coding: utf-8 -*-
"""publicar.py (2026-10-08): copia un tablero con su carpeta reportes/ a gh-pages
y solo si todo abre con la contraseña. Tableros y gh-pages falsos, en tmp_path."""
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "Visualizador Web"))
import candado  # noqa: E402
import publicar  # noqa: E402

PLANTILLA = f"<script>{candado.MARCADOR_JS}</script>" '<script id="af-data-b64" type="text/plain">__XX__</script>'


def _tablero(tmp_path, contrasena, pdfs=()):
    """Un build de AF falso: index.html cifrado y sus reportes cifrados aparte."""
    build = tmp_path / "Sistema Analisis Financiero" / "Visualizador Web" / "build"
    (build / "reportes").mkdir(parents=True)
    reportes = {}
    for i, pdf in enumerate(pdfs):
        rel = candado.nombre_archivo(pdf)
        (build / rel).write_text(candado.cifrar_bytes(pdf, contrasena), encoding="utf-8")
        reportes[f"proyecto:P{i}"] = {"archivo": rel, "fecha": "01-01-2026", "desactualizado": False}
    html = candado.incrustar(PLANTILLA, "__XX__", json.dumps({"reportes_pdf": reportes}), contrasena)
    (build / "index.html").write_text(html, encoding="utf-8")
    return build


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setattr(publicar, "RAIZ", tmp_path)
    gh = tmp_path / "gh-pages"
    gh.mkdir()
    return tmp_path, gh


def test_copia_el_tablero_y_sincroniza_sus_reportes(entorno):
    tmp_path, gh = entorno
    _tablero(tmp_path, "clave", [b"%PDF uno", b"%PDF dos"])
    viejo = gh / "analisis-financiero" / "reportes" / ("f" * 24 + ".json")
    viejo.parent.mkdir(parents=True)
    viejo.write_text("{}", encoding="utf-8")

    assert publicar.preparar("af", "clave", raiz_gh_pages=gh) == "analisis-financiero"

    destino = gh / "analisis-financiero"
    assert candado.abre_con((destino / "index.html").read_text(encoding="utf-8"), "clave", carpeta=destino)
    assert sorted(p.name for p in (destino / "reportes").glob("*.json")) == sorted(
        Path(candado.nombre_archivo(b)).name for b in (b"%PDF uno", b"%PDF dos"))
    assert not viejo.exists()


def test_no_toca_gh_pages_si_el_tablero_no_abre_con_la_contrasena(entorno):
    tmp_path, gh = entorno
    _tablero(tmp_path, "la de prueba", [b"%PDF uno"])
    with pytest.raises(RuntimeError):
        publicar.preparar("af", "la real", raiz_gh_pages=gh)
    assert not (gh / "analisis-financiero").exists()


def test_no_publica_un_tablero_al_que_le_falta_un_reporte(entorno):
    tmp_path, gh = entorno
    build = _tablero(tmp_path, "clave", [b"%PDF uno"])
    for archivo in (build / "reportes").glob("*.json"):
        archivo.unlink()
    with pytest.raises(RuntimeError):
        publicar.preparar("af", "clave", raiz_gh_pages=gh)
    assert not (gh / "analisis-financiero").exists()


def test_la_tabla_de_tableros_es_la_de_la_receta_de_publicacion():
    receta = (RAIZ / "Visualizador Web" / "CLAUDE.md").read_text(encoding="utf-8")
    for subruta, build in publicar.TABLEROS.values():
        assert f"`{subruta}`" in receta
        assert f"`{build}`" in receta
