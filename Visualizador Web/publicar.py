# -*- coding: utf-8 -*-
"""Deja los tableros recien construidos listos para publicar en gh-pages.

    py -3.14 "Visualizador Web/publicar.py" cc af cot fc      # los que se regeneraron
    py -3.14 "Visualizador Web/publicar.py" --todos

Por cada tablero: copia su build/index.html a .worktrees/gh-pages/<subruta>/,
sincroniza la carpeta reportes/ (los archivos cifrados que el tablero baja al
usarlos: hoy, los reportes PDF de Analisis Financiero), verifica con el candado
que todo abre con la contrasena de este equipo y lo deja en el indice de git
(git add). No hace commit ni push: eso sigue siendo un paso explicito.

Por que existe (2026-10-08): publicar era copiar un archivo a mano y correr
candado.py sobre el. Desde que los reportes PDF del AF van cifrados aparte, un
tablero son varios archivos, y copiar solo el index.html dejaria botones que no
abren nada. Si algo no abre, no se toca gh-pages.
"""
import argparse
import shutil
import subprocess
import sys
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
}


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tableros", nargs="*", metavar="tablero", help="subconjunto de: " + ", ".join(TABLEROS))
    ap.add_argument("--todos", action="store_true", help="los 7 tableros")
    args = ap.parse_args(argv)
    claves = list(TABLEROS) if args.todos else args.tableros
    desconocidos = [c for c in claves if c not in TABLEROS]
    if not claves or desconocidos:
        ap.error(f"indica tableros ({', '.join(TABLEROS)}) o --todos" + (f"; desconocidos: {desconocidos}" if desconocidos else ""))
    if not (RAIZ_GH_PAGES / ".git").exists():
        print(f"[ERROR] No está el worktree de gh-pages en {RAIZ_GH_PAGES} (git worktree list).")
        return 1
    contrasena = candado.leer_contrasena()
    subrutas = []
    for clave in claves:
        try:
            subrutas.append(preparar(clave, contrasena))
        except RuntimeError as error:
            print(f"[NO ABRE] {error}")
            print("No se publica nada más: regenera ese tablero y vuelve a correr esto.")
            return 1
    subprocess.run(["git", "-C", str(RAIZ_GH_PAGES), "add", "--all", "--", *subrutas], check=True)
    print("\nListo en el índice de gh-pages. Para publicar:")
    print(f'  git -C "{RAIZ_GH_PAGES}" commit -m "actualizar tableros: ..."')
    print(f'  git -C "{RAIZ_GH_PAGES}" push')
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main())
