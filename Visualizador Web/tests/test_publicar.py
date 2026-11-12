# -*- coding: utf-8 -*-
"""publicar.py (2026-10-08): copia un tablero con su carpeta reportes/ a gh-pages
y solo si todo abre con la contraseña. Tableros y gh-pages falsos, en tmp_path."""
import json
import re
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


@pytest.mark.parametrize("clave,destino", [("hub", "index.html"), ("portal", "portal/index.html")])
def test_el_hub_y_el_portal_se_copian_con_los_archivos_de_marca_que_enlazan(tmp_path, clave, destino):
    gh = tmp_path / "gh-pages"
    gh.mkdir()
    assert publicar.preparar_estatico(clave, raiz_gh_pages=gh) == destino
    pagina = (gh / destino).read_text(encoding="utf-8")
    enlaces = re.findall(r'href="((?:\.\./)?marca/[^"]+)"', pagina)
    assert enlaces
    for enlace in enlaces:
        assert ((gh / destino).parent / enlace).resolve().is_file(), enlace


# ---- Auditoría del flujo de entrega (2026-11-06): sello, CI y gh-pages al día -------------------------------------

def _repo(carpeta: Path) -> Path:
    import subprocess
    carpeta.mkdir(parents=True, exist_ok=True)
    for args in (["init", "-q", "-b", "master"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", "-C", str(carpeta), *args], check=True)
    return carpeta


def _commit(repo: Path, rel: str, texto: str):
    import subprocess
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(texto, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "--all"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", rel], check=True)


def test_el_sello_de_version_va_en_el_head_y_reemplaza_al_anterior():
    html = "<html><head><title>x</title></head><body></body></html>"
    una = publicar.con_sello(html, "master@abc1234 2026-11-06")
    assert '<meta name="quempin-version" content="master@abc1234 2026-11-06">\n</head>' in una
    dos = publicar.con_sello(una, "master@def5678 2026-11-07")
    assert dos.count("quempin-version") == 1 and "def5678" in dos


def test_el_portal_publicado_lleva_su_sello(tmp_path):
    gh = tmp_path / "gh-pages"
    gh.mkdir()
    publicar.preparar_estatico("portal", raiz_gh_pages=gh, sello="master@abc1234 2026-11-06")
    assert '<meta name="quempin-version" content="master@abc1234 2026-11-06">' in (gh / "portal" / "index.html").read_text(encoding="utf-8")


@pytest.fixture
def repo_con_portal(tmp_path, monkeypatch):
    """Un repo de mentira con el Portal commiteado, y gh (GitHub CLI) de mentira que responde lo que diga 'ci'."""
    import subprocess
    repo = _repo(tmp_path / "repo")
    _commit(repo, "Visualizador Web/portal/index.html", "<html><head></head></html>")
    monkeypatch.setattr(publicar, "RAIZ", repo)
    ci = {"corridas": []}
    real = subprocess.run

    def run(cmd, *a, **kw):
        if cmd[0] == "gh":
            return subprocess.CompletedProcess(cmd, 0, json.dumps(ci["corridas"]), "")
        return real(cmd, *a, **kw)
    monkeypatch.setattr(publicar.subprocess, "run", run)
    return repo, ci


def test_el_portal_se_publica_solo_commiteado_y_con_el_ci_en_verde(repo_con_portal):
    repo, ci = repo_con_portal
    assert publicar.revisar_codigo(["cc"]) == []                       # los tableros con datos no son código
    assert "no tiene CI" in publicar.revisar_codigo(["portal"])[0]
    ci["corridas"] = [{"status": "in_progress", "conclusion": "", "url": "u"}]
    assert "aún corre" in publicar.revisar_codigo(["portal"])[0]
    ci["corridas"] = [{"status": "completed", "conclusion": "failure", "url": "u"}]
    assert "falló" in publicar.revisar_codigo(["portal"])[0]
    ci["corridas"] = [{"status": "completed", "conclusion": "success", "url": "u"}]
    assert publicar.revisar_codigo(["portal", "hub"]) == []
    (repo / "Visualizador Web" / "portal" / "index.html").write_text("<html><head></head><body>sin commit</body></html>", encoding="utf-8")
    assert publicar.revisar_codigo(["portal"]) == ["hay cambios sin commit en: Visualizador Web/portal/index.html"]
    ci["corridas"] = []
    assert publicar.revisar_codigo(["portal"], sin_ci=True) == ["hay cambios sin commit en: Visualizador Web/portal/index.html"]
    assert publicar.sello_de_version().startswith("master@")


def test_con_subir_espera_el_ci_que_corre_y_no_el_que_fallo(repo_con_portal):
    repo, ci = repo_con_portal
    vueltas = []

    def dormir(_):
        vueltas.append(1)
        # Recién empujado no hay CI; después corre; después termina
        ci["corridas"] = [{"status": "in_progress", "conclusion": "", "url": "u"}] if len(vueltas) == 1 else \
            [{"status": "completed", "conclusion": "success", "url": "u"}]
    assert publicar.esperar_codigo(["portal"], dormir=dormir) == [] and len(vueltas) == 2
    ci["corridas"] = [{"status": "completed", "conclusion": "failure", "url": "u"}]
    vueltas.clear()
    assert "falló" in publicar.esperar_codigo(["portal"], dormir=dormir)[0] and not vueltas
    ci["corridas"] = [{"status": "in_progress", "conclusion": "", "url": "u"}]
    assert "aún corre" in publicar.esperar_codigo(["portal"], espera_max=0, dormir=lambda _: None)[0]


def test_con_subir_verifica_que_github_pages_sirva_lo_mismo(tmp_path):
    (tmp_path / "portal").mkdir()
    (tmp_path / "portal" / "index.html").write_bytes(b"nuevo")
    (tmp_path / "numeros.js").write_bytes(b"js")
    rutas = publicar._archivos_publicados(["portal/index.html", "numeros.js", "no-existe"], tmp_path)
    assert rutas == ["numeros.js", "portal/index.html"]
    servido = {"portal/index.html": b"viejo", "numeros.js": b"js"}
    vueltas = []

    def bajar(url):
        return servido[url.split(publicar.URL_BASE)[1].split("?")[0]]

    def dormir(_):
        vueltas.append(1)
        servido["portal/index.html"] = b"nuevo"     # Pages termina de desplegar
    assert publicar.verificar_en_linea(rutas, tmp_path, bajar=bajar, dormir=dormir) == [] and len(vueltas) == 1
    servido["portal/index.html"] = b"viejo"
    assert publicar.verificar_en_linea(rutas, tmp_path, espera_max=0, bajar=bajar, dormir=dormir) == ["portal/index.html"]


def test_no_se_publica_si_otra_sesion_publico_despues(tmp_path):
    import subprocess
    origen = tmp_path / "origen.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "gh-pages", str(origen)], check=True)
    una = _repo(tmp_path / "una")
    subprocess.run(["git", "-C", str(una), "checkout", "-q", "-b", "gh-pages"], check=True)
    _commit(una, "index.html", "1")
    subprocess.run(["git", "-C", str(una), "remote", "add", "origin", str(origen)], check=True)
    subprocess.run(["git", "-C", str(una), "push", "-q", "origin", "gh-pages"], check=True)
    otra = tmp_path / "otra"
    subprocess.run(["git", "clone", "-q", "-b", "gh-pages", str(origen), str(otra)], check=True)
    assert publicar.revisar_gh_pages(una) == []
    subprocess.run(["git", "-C", str(otra), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(otra), "config", "user.name", "t"], check=True)
    _commit(otra, "index.html", "2")
    subprocess.run(["git", "-C", str(otra), "push", "-q", "origin", "gh-pages"], check=True)
    problemas = publicar.revisar_gh_pages(una)
    assert len(problemas) == 1 and "1 commit(s) atrás" in problemas[0] and "pull --ff-only" in problemas[0]


def test_en_linea_se_compara_con_el_commit_y_no_con_el_disco(tmp_path):
    """2026-11-12: con core.autocrlf la copia del disco lleva CRLF y el commit (lo que sirve Pages) LF: no es una diferencia."""
    import subprocess
    repo = _repo(tmp_path / "gh")
    subprocess.run(["git", "-C", str(repo), "config", "core.autocrlf", "false"], check=True)
    (repo / "marca").mkdir()
    (repo / "marca" / "fuentes.css").write_bytes(b"a\nb\n")      # write_text en Windows ya escribiría CRLF
    subprocess.run(["git", "-C", str(repo), "add", "--all"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "css"], check=True)
    (repo / "marca" / "fuentes.css").write_bytes(b"a\r\nb\r\n")       # como lo deja autocrlf en el disco
    servido = {"marca/fuentes.css": b"a\nb\n"}
    assert publicar.verificar_en_linea(["marca/fuentes.css"], repo, espera_max=0,
                                       bajar=lambda u: servido[u.split(publicar.URL_BASE)[1].split("?")[0]], dormir=lambda _: None) == []
