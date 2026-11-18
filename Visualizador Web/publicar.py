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
import hashlib
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
# Lo que una página sin datos enlaza junto a ella, en su misma carpeta (2026-11-18, fase B del plan del Portal: el Portal
# se partió en portal.css y js/<vista>.js). Se copia con ella; un .js que ya no está en el origen se borra de gh-pages.
PARTES = {
    "portal": ("portal.css", "js"),
}
CARPETA_MARCA = "Visualizador Web/marca"
# logo.png (2026-11-18): el PDF de «Rendiciones» del Portal lo pone en su cabecera (../marca/logo.png)
ARCHIVOS_MARCA = ("fuentes.css", "favicon.png", "logo.png")
# Código común que el hub y el Portal enlazan desde la raíz de gh-pages (../numeros.js). Los tableros
# lo llevan incrustado (candado.incrustar).
ARCHIVOS_COMUNES = ("numeros.js", "candado.js")
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


def _enlaces_locales(html: str) -> list[str]:
    """Los src= de <script> y href= de <link rel="stylesheet"> que apuntan a un archivo del mismo sitio, relativos."""
    enlaces = re.findall(r'<script\b[^>]*\bsrc="([^"]+)"', html)
    enlaces += [m.group(2) for m in re.finditer(r'<link\b([^>]*)\bhref="([^"]+)"', html) if "stylesheet" in m.group(1)]
    return [e for e in enlaces if not re.match(r"^(?:[a-z]+:|//|/)", e, re.I)]


def con_versiones(html: str, carpeta: Path, partes) -> str:
    """Cada enlace a una de sus partes (portal.css, js/x.js) con ?v=<huella del archivo>. GitHub Pages deja cada archivo
    10 minutos en el caché del navegador: sin esto, recién publicado, un index.html nuevo podía correr con un .js viejo."""
    def poner(m):
        ruta = m.group(2).split("?")[0]
        if not any(ruta == p or ruta.startswith(p + "/") for p in partes) or not (carpeta / ruta).is_file():
            return m.group(0)          # lo que falta lo dice preparar_estatico, con su nombre
        huella = hashlib.sha256((carpeta / ruta).read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:12]
        return f'{m.group(1)}{ruta}?v={huella}"'
    return re.sub(r'((?:<script\b[^>]*\bsrc|<link\b[^>]*\bhref)=")([^"]+)"', poner, html)


def esperar_codigo(claves, sin_ci: bool = False, espera_max: float = 1500, paso: float = 20, dormir=None) -> list[str]:
    """Como revisar_codigo, pero mientras el CI corre (o todavía no aparece, recién empujado) espera
    a que termine, hasta espera_max segundos. Lo demás (falló, cambios sin commit) no se espera."""
    import time
    dormir = dormir or time.sleep
    inicio = time.monotonic()
    while True:
        problemas = revisar_codigo(claves, sin_ci=sin_ci)
        transitorios = [p for p in problemas if "aún corre" in p or "no tiene CI" in p]
        if not transitorios or len(transitorios) < len(problemas) or time.monotonic() - inicio >= espera_max:
            return problemas
        print(f"[ESPERA] {transitorios[0]}")
        dormir(paso)


URL_BASE = "https://cristobal-monzo.github.io/finanzas-quempin/"


def _archivos_publicados(subrutas, raiz_gh_pages: Path = RAIZ_GH_PAGES) -> list[str]:
    """Las rutas relativas (con /) de lo que se publicó: archivos sueltos y lo de cada carpeta."""
    salida = []
    for s in subrutas:
        p = raiz_gh_pages / s
        if p.is_dir():
            salida += [f.relative_to(raiz_gh_pages).as_posix() for f in sorted(p.rglob("*")) if f.is_file()]
        elif p.is_file():
            salida.append(Path(s).as_posix())
    return sorted(set(salida))


def _commiteado(ruta: str, raiz_gh_pages: Path = RAIZ_GH_PAGES) -> bytes:
    """Lo que GitHub Pages va a servir: el archivo tal como quedó en el commit de gh-pages. La copia del disco puede
    diferir en los fines de línea (core.autocrlf: en el disco CRLF, en el commit LF; visto con marca/fuentes.css,
    2026-11-12). Fuera de un repo (pruebas), el archivo del disco."""
    r = subprocess.run(["git", "-C", str(raiz_gh_pages), "show", f"HEAD:{ruta}"], capture_output=True)
    return r.stdout if r.returncode == 0 else (raiz_gh_pages / ruta).read_bytes()


def verificar_en_linea(rutas, raiz_gh_pages: Path = RAIZ_GH_PAGES, espera_max: float = 600, paso: float = 20,
                       bajar=None, dormir=None) -> list[str]:
    """Espera a que GitHub Pages sirva cada archivo idéntico al de gh-pages. Devuelve las rutas que no
    quedaron iguales al vencer el plazo ([] = todo en línea)."""
    import time
    import urllib.request

    def _bajar(url):
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Cache-Control": "no-cache"}), timeout=30) as r:
            return r.read()
    bajar = bajar or _bajar
    dormir = dormir or time.sleep
    faltan = list(rutas)
    inicio = time.monotonic()
    while True:
        pendientes = []
        for ruta in faltan:
            try:
                igual = bajar(f"{URL_BASE}{ruta}?v={int(time.time())}") == _commiteado(ruta, raiz_gh_pages)
            except Exception:
                igual = False
            if not igual:
                pendientes.append(ruta)
        faltan = pendientes
        if not faltan or time.monotonic() - inicio >= espera_max:
            return faltan
        print(f"[ESPERA] GitHub Pages todavía no sirve {len(faltan)} archivo(s)…")
        dormir(paso)


def subir(subrutas, mensaje: str, raiz_gh_pages: Path = RAIZ_GH_PAGES) -> int:
    """Commit y push de gh-pages y verificación en línea. 0 = publicado e idéntico en línea."""
    if not _git("diff", "--cached", "--name-only", repo=raiz_gh_pages):
        print("[OK] gh-pages ya tenía exactamente esto: no hay nada que subir.")
        return 0
    _git("commit", "-q", "-m", mensaje, repo=raiz_gh_pages)
    _git("push", "-q", "origin", "gh-pages", repo=raiz_gh_pages)
    commit = _git("rev-parse", "--short", "HEAD", repo=raiz_gh_pages)
    print(f"[OK] gh-pages {commit} empujado; se verifica en línea…")
    faltan = verificar_en_linea(_archivos_publicados(subrutas, raiz_gh_pages), raiz_gh_pages)
    if faltan:
        print(f"[REVISAR] a los 10 minutos GitHub Pages aún no sirve igual: {', '.join(faltan[:5])}")
        return 1
    print(f"[EN LÍNEA] gh-pages {commit}: todo idéntico en {URL_BASE}")
    return 0


def revisar_codigo(claves, sin_ci: bool = False) -> list[str]:
    """Lo que impide publicar el hub o el Portal desde este commit ([] = se puede)."""
    origenes = [ESTATICOS[c][1] for c in claves if c in ESTATICOS]
    origenes += [str(Path(ESTATICOS[c][1]).parent / p).replace("\\", "/") for c in claves if c in ESTATICOS
                 for p in PARTES.get(c, ())]
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
    """[] si gh-pages local tiene todo lo de origin/gh-pages (otra sesión pudo publicar después). Si está atrás y
    sin nada propio a medias, se pone al día solo (pull --ff-only): desde 2026-11-18 el resumen del teléfono sube a
    origin cada hora sin pasar por esta carpeta (subir_carpeta_aparte), así que quedar atrás es lo normal."""
    try:
        _git("fetch", "--quiet", "origin", "gh-pages", repo=raiz_gh_pages)
    except RuntimeError as error:
        print(f"[AVISO] no se pudo revisar origin/gh-pages ({error}); se sigue con lo local.")
        return []
    atras = _git("rev-list", "--count", "HEAD..origin/gh-pages", repo=raiz_gh_pages)
    if atras == "0":
        return []
    if not _git("status", "--porcelain", repo=raiz_gh_pages):
        try:
            _git("merge", "--ff-only", "--quiet", "origin/gh-pages", repo=raiz_gh_pages)
            print(f"[OK] gh-pages local se puso al día con origin ({atras} commit(s)).")
            return []
        except RuntimeError as error:
            print(f"[AVISO] no se pudo poner al día gh-pages local ({error}).")
    return [f"gh-pages local está {atras} commit(s) atrás de origin: otra sesión publicó. "
            f'Primero: git -C "{raiz_gh_pages}" pull --ff-only']


def subir_carpeta_aparte(carpeta: Path, destino: str, mensaje: str, repo: Path = RAIZ, remoto: str = "origin",
                         intentos: int = 3) -> str | None:
    """Sube a gh-pages, en destino/, los archivos de carpeta (y borra de destino/ los que ya no están), con un commit
    sobre origin/gh-pages armado con un índice temporal: no toca ninguna carpeta de trabajo, ni la de gh-pages que usan
    las sesiones (2026-11-18, el resumen del teléfono: lo sube la tarea del procesador). Si otra sesión empujó entre
    medio, vuelve a armarlo sobre lo nuevo. Devuelve el commit corto, o None si gh-pages ya tenía exactamente eso."""
    import os
    import tempfile
    rama = f"refs/remotes/{remoto}/gh-pages"
    archivos = sorted(p for p in Path(carpeta).rglob("*") if p.is_file() and p.suffix == ".json")
    for intento in range(intentos):
        _git("fetch", "--quiet", remoto, "gh-pages", repo=repo)
        base = _git("rev-parse", rama, repo=repo)
        with tempfile.TemporaryDirectory() as tmp:
            entorno = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "indice"))

            def git(*args):
                r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                                   env=entorno)
                if r.returncode:
                    raise RuntimeError(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()}")
                return r.stdout.strip()
            git("read-tree", base)
            viejos = [l for l in git("ls-files", "--", destino + "/").splitlines() if l]
            if viejos:
                git("rm", "--cached", "--quiet", "--", *viejos)
            for p in archivos:
                # --no-filters: los bytes tal cual (con core.autocrlf, git les cambiaría los fines de línea)
                sha = git("hash-object", "-w", "--no-filters", "--", str(p))
                git("update-index", "--add", "--cacheinfo", f"100644,{sha},{destino}/{p.relative_to(carpeta).as_posix()}")
            arbol = git("write-tree")
        if arbol == _git("rev-parse", base + "^{tree}", repo=repo):
            return None
        commit = _git("commit-tree", arbol, "-p", base, "-m", mensaje, repo=repo)
        try:
            _git("push", "--quiet", remoto, f"{commit}:refs/heads/gh-pages", repo=repo)
            return commit[:7]
        except RuntimeError:
            if intento == intentos - 1:
                raise
    return None


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


def subrutas_estatico(clave: str) -> list[str]:
    """Lo que preparar_estatico deja en gh-pages para esa página: ella, sus partes, marca/ y el código común."""
    destino = ESTATICOS[clave][0]
    partes = [(Path(destino).parent / p).as_posix() for p in PARTES.get(clave, ())]
    return [destino, *partes, "marca", *ARCHIVOS_COMUNES]


def preparar_estatico(clave: str, raiz_gh_pages: Path = RAIZ_GH_PAGES, sello: str | None = None) -> str:
    """Copia el hub o el Portal con sus partes (portal.css, js/) y los archivos de marca que enlazan, con su sello de
    versión y ?v= en cada parte. Revisa que cada script u hoja enlazada exista en gh-pages. Devuelve su destino."""
    destino, origen = ESTATICOS[clave]
    origen = RAIZ / origen
    if not origen.exists():
        raise RuntimeError(f"{clave}: no existe {origen.relative_to(RAIZ).as_posix()}")
    copia = raiz_gh_pages / destino
    copia.parent.mkdir(parents=True, exist_ok=True)
    partes = PARTES.get(clave, ())
    for parte in partes:
        fuente, meta = origen.parent / parte, copia.parent / parte
        if fuente.is_dir():
            meta.mkdir(exist_ok=True)
            nombres = {p.name for p in fuente.glob("*.js")}
            for nombre in sorted(nombres):
                shutil.copy2(fuente / nombre, meta / nombre)
            for viejo in meta.glob("*.js"):
                if viejo.name not in nombres:
                    viejo.unlink()
        elif fuente.is_file():
            shutil.copy2(fuente, meta)
        else:
            raise RuntimeError(f"{clave}: no existe {fuente.relative_to(RAIZ).as_posix()}")
    html = origen.read_text(encoding="utf-8")
    if partes:
        html = con_versiones(html, origen.parent, partes)
    if sello:
        html = con_sello(html, sello)
    with open(copia, "w", encoding="utf-8", newline="") as f:
        f.write(html)
    carpeta = raiz_gh_pages / "marca"
    carpeta.mkdir(exist_ok=True)
    for nombre in ARCHIVOS_MARCA:
        shutil.copy2(RAIZ / CARPETA_MARCA / nombre, carpeta / nombre)
    for nombre in ARCHIVOS_COMUNES:
        shutil.copy2(RAIZ / "Visualizador Web" / nombre, raiz_gh_pages / nombre)
    faltan = [e for e in _enlaces_locales(html) if not (copia.parent / e.split("?")[0]).resolve().is_file()]
    if faltan:
        raise RuntimeError(f"{clave}: enlaza archivos que no quedan en gh-pages: {', '.join(faltan)}")
    extra = "".join(f"{p}, " for p in partes)
    print(f"[OK] {clave:<6} -> {destino}, {extra}marca/ y {', '.join(ARCHIVOS_COMUNES)}")
    return destino


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tableros", nargs="*", metavar="tablero", help="subconjunto de: " + ", ".join([*TABLEROS, *ESTATICOS]))
    ap.add_argument("--todos", action="store_true", help="todos los tableros")
    ap.add_argument("--sin-ci", action="store_true", help="publicar el hub o el Portal sin revisar el CI de este commit")
    ap.add_argument("--subir", action="store_true",
                    help="todo de una vez: espera el CI si corre, hace commit y push de gh-pages y verifica que quede igual en línea")
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
        problemas += (esperar_codigo if args.subir else revisar_codigo)(claves, sin_ci=args.sin_ci)
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
                preparar_estatico(clave, sello=sello)
                subrutas += subrutas_estatico(clave)
            else:
                subrutas.append(preparar(clave, contrasena))
        except RuntimeError as error:
            print(f"[NO ABRE] {error}")
            print("No se publica nada más: regenera ese tablero y vuelve a correr esto.")
            return 1
    subprocess.run(["git", "-C", str(RAIZ_GH_PAGES), "add", "--all", "--", *subrutas], check=True)
    if args.subir:
        return subir(subrutas, f"publicar: {' '.join(claves)}" + (f" ({sello})" if sello else ""))
    print("\nListo en el índice de gh-pages. Para publicar:")
    print(f'  git -C "{RAIZ_GH_PAGES}" commit -m "actualizar tableros: ...' + (f' ({sello})' if sello else '') + '"')
    print(f'  git -C "{RAIZ_GH_PAGES}" push')
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main())
