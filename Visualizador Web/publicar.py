# -*- coding: utf-8 -*-
"""Deja los tableros recien construidos listos para publicar en gh-pages.

    py -3.14 "Visualizador Web/publicar.py" cc af cot fc op   # los que se regeneraron
    py -3.14 "Visualizador Web/publicar.py" --todos
    py -3.14 "Visualizador Web/publicar.py" portal hub        # las dos paginas sin datos

Por cada tablero: copia su build/index.html a .worktrees/gh-pages/<subruta>/,
sincroniza la carpeta reportes/ (los archivos cifrados que el tablero baja al
usarlos: hoy, los reportes PDF de Analisis Financiero), verifica con el candado
que todo abre con la contrasena de este equipo y lo deja en el indice de git
(git add). No hace commit ni push: eso sigue siendo un paso explicito.

Por que existe (2026-10-08): publicar era copiar un archivo a mano y correr
candado.py sobre el. Desde que los reportes PDF del AF van cifrados aparte, un
tablero son varios archivos, y copiar solo el index.html dejaria botones que no
abren nada. Si algo no abre, no se toca gh-pages.

El hub y el Portal (2026-10-30) no llevan datos ni candado: se copian tal cual,
con los archivos de marca que enlazan. Sin ellos se verian con la letra del sistema.

Desde la auditoria del flujo de entrega (2026-11-06), antes de tocar gh-pages:
- gh-pages local al dia con origin (git fetch): si otra sesion publico despues,
  primero se trae lo suyo (git -C .worktrees/gh-pages pull --ff-only).
- El hub y el Portal son codigo: solo se publican commiteados (sin cambios
  locales en su archivo) y con el CI de ese commit en verde (gh run list). Sin
  push no hay CI: primero git push. --sin-ci se salta esa revision, y lo dice.
- La copia publicada lleva <meta name="quempin-version" content="rama@commit
  fecha">: las observaciones del Portal lo anotan, asi se sabe que version vio
  quien la escribio. El commit sugerido para gh-pages lleva el mismo sello.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import candado  # noqa: E402

RAIZ_GH_PAGES = RAIZ / ".worktrees" / "gh-pages"

# clave -> (subruta en gh-pages, build de origen). Misma tabla que la receta de
# Visualizador Web/CLAUDE.md § Hosting.
TABLEROS = {
    "cc": ("centro-de-costos", "Centro de Costos/Visualizador Web/build/index.html"),
    "ccpe": ("centro-de-costos-peru", "Peru/Centro de Costos/Visualizador Web/build/index.html"),
    "af": ("analisis-financiero", "Sistema Analisis Financiero/Visualizador Web/build/index.html"),
    "afpe": ("analisis-financiero-peru", "Peru/Análisis Financiero/Visualizador Web/build/index.html"),
    "cot": ("cotizador-historico", "Cotizador Historico/Visualizador Web/build/index.html"),
    "cotpe": ("cotizador-historico-peru", "Peru/Cotizador Historico/Visualizador Web/build/index.html"),
    "fc": ("flujo-de-caja", "Flujo de Caja/Visualizador Web/build/index.html"),
    # Oportunidades en Mercado Público (2026-10-13): solo Chile.
    "op": ("oportunidades", "Sistema Intercambio/Visualizador Web/build/index.html"),
}

# Paginas sin datos: clave -> (destino en gh-pages, origen).
ESTATICOS = {
    "hub": ("index.html", "Visualizador Web/index.html"),
    "portal": ("portal/index.html", "Visualizador Web/portal/index.html"),
}
CARPETA_MARCA = "Visualizador Web/marca"
ARCHIVOS_MARCA = ("fuentes.css", "favicon.png")
FLUJO_CI = "tests.yml"
META_VERSION = "quempin-version"


def _git(*args, repo: Path | None = None) -> str:
    r = subprocess.run(["git", "-C", str(repo or RAIZ), *args], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def sello_de_version(hoy: date | None = None) -> str:
    """El sello del código que se publica: «master@abc1234 2026-11-06»."""
    rama = _git("rev-parse", "--abbrev-ref", "HEAD")
    commit = _git("rev-parse", "--short", "HEAD")
    return f"{rama}@{commit} {(hoy or date.today()).isoformat()}"


def con_sello(html: str, texto: str) -> str:
    """La página con su meta quempin-version (reemplaza una anterior)."""
    sin = re.sub(r'\s*<meta name="' + META_VERSION + r'"[^>]*>', "", html)
    if "</head>" not in sin:
        raise RuntimeError("la página no tiene </head> para su sello de versión")
    return sin.replace("</head>", f'<meta name="{META_VERSION}" content="{texto}">\n</head>', 1)


def revisar_codigo(claves, sin_ci: bool = False) -> list[str]:
    """Lo que impide publicar el hub o el Portal desde este commit ([] = se puede)."""
    origenes = [ESTATICOS[c][1] for c in claves if c in ESTATICOS]
    if not origenes:
        return []
    problemas = []
    sucios = _git("status", "--porcelain", "--", *origenes)
    if sucios:
        problemas.append("hay cambios sin commit en: " + ", ".join(l[3:].strip('"') for l in sucios.splitlines()))
    if sin_ci:
        print("[AVISO] --sin-ci: se publica sin revisar el CI de este commit.")
        return problemas
    commit = _git("rev-parse", "HEAD")
    try:
        r = subprocess.run(["gh", "run", "list", "--commit", commit, "--workflow", FLUJO_CI, "--json", "status,conclusion,url"],
                           cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return problemas + ["no está gh (GitHub CLI) para revisar el CI: instálalo o usa --sin-ci"]
    if r.returncode:
        return problemas + [f"no se pudo revisar el CI ({(r.stderr or r.stdout).strip()}): reintenta o usa --sin-ci"]
    corridas = json.loads(r.stdout or "[]")
    if not corridas:
        problemas.append(f"el commit {commit[:7]} no tiene CI: haz git push de su rama y espera que termine")
    elif corridas[0]["status"] != "completed":
        problemas.append(f"el CI del commit {commit[:7]} aún corre: {corridas[0]['url']}")
    elif corridas[0]["conclusion"] != "success":
        problemas.append(f"el CI del commit {commit[:7]} falló: {corridas[0]['url']}")
    return problemas


def revisar_gh_pages(raiz_gh_pages: Path = RAIZ_GH_PAGES) -> list[str]:
    """[] si gh-pages local tiene todo lo de origin/gh-pages (otra sesión pudo publicar después)."""
    try:
        _git("fetch", "--quiet", "origin", "gh-pages", repo=raiz_gh_pages)
    except RuntimeError as error:
        print(f"[AVISO] no se pudo revisar origin/gh-pages ({error}); se sigue con lo local.")
        return []
    atras = _git("rev-list", "--count", "HEAD..origin/gh-pages", repo=raiz_gh_pages)
    if atras != "0":
        return [f"gh-pages local está {atras} commit(s) atrás de origin: otra sesión publicó. "
                f'Primero: git -C "{raiz_gh_pages}" pull --ff-only']
    return []


def _sincronizar_carpeta(origen: Path, destino: Path) -> tuple[int, int]:
    """Deja 'destino' igual a 'origen' (solo archivos .json). Devuelve (copiados, borrados)."""
    copiados = borrados = 0
    nombres = {p.name for p in origen.glob("*.json")} if origen.is_dir() else set()
    if nombres:
        destino.mkdir(parents=True, exist_ok=True)
    for nombre in sorted(nombres):
        fuente, copia = origen / nombre, destino / nombre
        if not copia.exists() or copia.read_bytes() != fuente.read_bytes():
            shutil.copy2(fuente, copia)
            copiados += 1
    if destino.is_dir():
        for viejo in destino.glob("*.json"):
            if viejo.name not in nombres:
                viejo.unlink()
                borrados += 1
    return copiados, borrados


def preparar(clave: str, contrasena: str, raiz_gh_pages: Path = RAIZ_GH_PAGES) -> str:
    """Copia y verifica un tablero. Devuelve la subruta; levanta RuntimeError si no abre."""
    subruta, build = TABLEROS[clave]
    origen = RAIZ / build
    if not origen.exists():
        raise RuntimeError(f"{clave}: no existe {build} (corre su build primero)")
    html = origen.read_text(encoding="utf-8")
    # Primero se verifica el build: si no abre, gh-pages no se toca.
    if not candado.abre_con(html, contrasena, carpeta=origen.parent):
        raise RuntimeError(f"{clave}: el build no abre con la contraseña de este equipo (o le falta un archivo de reportes/)")
    destino = raiz_gh_pages / subruta
    destino.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino / "index.html")
    copiados, borrados = _sincronizar_carpeta(origen.parent / candado.CARPETA_ARCHIVOS,
                                              destino / candado.CARPETA_ARCHIVOS)
    if not candado.abre_con((destino / "index.html").read_text(encoding="utf-8"), contrasena, carpeta=destino):
        raise RuntimeError(f"{clave}: la copia en gh-pages no abre")
    extra = f" · reportes/: {copiados} nuevo(s), {borrados} borrado(s)" if copiados or borrados else ""
    print(f"[OK] {clave:<6} -> {subruta}/{extra}")
    return subruta


def preparar_estatico(clave: str, raiz_gh_pages: Path = RAIZ_GH_PAGES, sello: str | None = None) -> str:
    """Copia el hub o el Portal con los archivos de marca que enlazan (y su sello de versión). Devuelve su destino."""
    destino, origen = ESTATICOS[clave]
    if not (RAIZ / origen).exists():
        raise RuntimeError(f"{clave}: no existe {origen}")
    copia = raiz_gh_pages / destino
    copia.parent.mkdir(parents=True, exist_ok=True)
    if sello:
        with open(copia, "w", encoding="utf-8", newline="") as f:
            f.write(con_sello((RAIZ / origen).read_text(encoding="utf-8"), sello))
    else:
        shutil.copy2(RAIZ / origen, copia)
    carpeta = raiz_gh_pages / "marca"
    carpeta.mkdir(exist_ok=True)
    for nombre in ARCHIVOS_MARCA:
        shutil.copy2(RAIZ / CARPETA_MARCA / nombre, carpeta / nombre)
    print(f"[OK] {clave:<6} -> {destino} y marca/")
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tableros", nargs="*", metavar="tablero", help="subconjunto de: " + ", ".join([*TABLEROS, *ESTATICOS]))
    ap.add_argument("--todos", action="store_true", help="todos los tableros")
    ap.add_argument("--sin-ci", action="store_true", help="publicar el hub o el Portal sin revisar el CI de este commit")
    args = ap.parse_args(argv)
    claves = list(TABLEROS) if args.todos else args.tableros
    desconocidos = [c for c in claves if c not in TABLEROS and c not in ESTATICOS]
    if not claves or desconocidos:
        ap.error(f"indica tableros ({', '.join([*TABLEROS, *ESTATICOS])}) o --todos" + (f"; desconocidos: {desconocidos}" if desconocidos else ""))
    if not (RAIZ_GH_PAGES / ".git").exists():
        print(f"[ERROR] No está el worktree de gh-pages en {RAIZ_GH_PAGES} (git worktree list).")
        return 1
    problemas = revisar_gh_pages()
    try:
        problemas += revisar_codigo(claves, sin_ci=args.sin_ci)
    except RuntimeError as error:
        problemas.append(str(error))
    if problemas:
        for problema in problemas:
            print(f"[NO SE PUBLICA] {problema}")
        return 1
    sello = sello_de_version() if any(c in ESTATICOS for c in claves) else None
    contrasena = candado.leer_contrasena() if any(c in TABLEROS for c in claves) else None
    subrutas = []
    for clave in claves:
        try:
            if clave in ESTATICOS:
                subrutas += [preparar_estatico(clave, sello=sello), "marca"]
            else:
                subrutas.append(preparar(clave, contrasena))
        except RuntimeError as error:
            print(f"[NO ABRE] {error}")
            print("No se publica nada más: regenera ese tablero y vuelve a correr esto.")
            return 1
    subprocess.run(["git", "-C", str(RAIZ_GH_PAGES), "add", "--all", "--", *subrutas], check=True)
    print("\nListo en el índice de gh-pages. Para publicar:")
    print(f'  git -C "{RAIZ_GH_PAGES}" commit -m "actualizar tableros: ...' + (f' ({sello})' if sello else '') + '"')
    print(f'  git -C "{RAIZ_GH_PAGES}" push')
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main())
