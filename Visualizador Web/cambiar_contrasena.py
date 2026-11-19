# -*- coding: utf-8 -*-
"""Cambia la contraseña del equipo (tableros, Formulador, Carta Gantt y Portal en el teléfono) con un solo comando.

    py -3.14 "Visualizador Web/cambiar_contrasena.py"             # dice qué haría, sin cambiar nada
    py -3.14 "Visualizador Web/cambiar_contrasena.py" --cambiar   # la cambia y publica todo

Por qué existe (2026-11-18): cambiar la contraseña eran varios pasos a mano (editar .contrasena_tableros,
regenerar y publicar los 8 tableros, escribir la llave del Formulador y publicarlo). Regenerar un tablero exige
correr la actualización de su módulo, así que en la práctica nadie la cambiaba, ni siquiera cuando alguien deja
la empresa.

Aquí no se regenera nada: cada sobre cifrado se abre con la contraseña anterior y se vuelve a cifrar con la nueva.
Los datos quedan idénticos; solo cambia la contraseña. Pasos de --cambiar:

1. Revisa que se pueda: gh-pages local limpio y al día con origin; el Formulador en main, con su index.html sin
   cambios y al día; y que todo lo publicado abra con la contraseña actual.
2. Genera la nueva (4 palabras y 4 números) y la guarda en .contrasena_tableros. La anterior queda en
   .contrasena_tableros.anterior (también fuera de git) hasta que todo termine.
3. Vuelve a cifrar lo publicado en .worktrees/gh-pages (tableros y reportes del AF) y los build/ locales.
4. Escribe la llave del Formulador (candado.escribir_llave).
5. Commit y push de gh-pages (publicar.subir, que verifica en línea) y del index.html del Formulador.
6. Rearma y sube el resumen del teléfono (Sistema Intercambio/resumen_movil.py publicar --ya).
7. Verifica que todo abra con la nueva y borra .contrasena_tableros.anterior.

Si algo falla a medias, vuelve a correr --cambiar: con .contrasena_tableros.anterior presente, sigue con la misma
contraseña nueva (lo que ya abre con ella se salta). La contraseña nunca se imprime: se lee en el archivo.
Al terminar, avisa al equipo: cada navegador la pide una vez, y la anterior ya no abre nada.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import candado  # noqa: E402
import publicar  # noqa: E402

RAIZ = candado.RAIZ_REPO
RUTA_ANTERIOR = candado.RUTA_CONTRASENA.with_name(candado.RUTA_CONTRASENA.name + ".anterior")
RAIZ_FORMULADOR = candado.RUTA_INDEX_FORMULADOR.parent
RESUMEN = RAIZ / "Sistema Intercambio" / "resumen_movil.py"
SALIDA_RESUMEN = RAIZ / "Sistema Intercambio" / "resumen_movil"
DATOS_RESUMEN = "portal/datos"          # en gh-pages: lo sube resumen_movil.py, no este script

_SOBRE_HTML = re.compile(r'(<script id="[^"]+" type="text/plain">)(\{"v":[^<]*)(</script>)')

# 256 palabras sin tildes ni ñ (candado.normalizar las quita igual): 4 de ellas y 4 números = ~45 bits, con
# PBKDF2 de 600.000 vueltas por intento. Fácil de dictar y de escribir una vez en el teléfono.
PALABRAS = """
abeja abrigo acero agua aguila ala alba alerce almendra alto amigo ancla anillo arado arbol arcilla arena
arroz astro atun aurora avena azul bahia balsa banco barco barro bosque brisa brujula buho cabra cacao
cactus cafe caldo calle cama camino campo canela canoa canto caracol carbon carta casa castor cedro cereza
cerro cielo cisne ciudad clavel cobre cohete colina condor copa coral cuarzo cubo cuerda cumbre delfin
dia diente duna eco eje espiga estrella faro fiesta flor foca fresa fruta fuego gato globo grano grillo
guinda gusano halcon hielo hierro higo hoja hongo horno huerto huevo humo isla jardin jarro jazmin
juego junco ladrillo lago lana lapiz laurel leche lechuga lente leon libro lima limon lino llama lluvia
lobo loro luna madera maiz manta mapa mar marco martillo mesa miel mina molino monte mora muro nido
niebla nieve noche nube nuez ocaso oceano oliva olmo onda oro oso otono pajaro palma pan papel parque
pato pera perla piedra pino pista plata playa pluma polen pozo prado puente puerto pulpo queso radio
rama rana rayo red rio roble roca rosa rueda sal salmon selva semilla sierra silla sol sombra suelo
tabla tambor taza techo tejado tela tierra tigre tinta toro torre trigo trueno tubo tulipan uva vaca
valle vapor vela verano viento vino violin volcan yegua zorro barco lince puma ciervo nutria alpaca
brote cometa granizo laguna marea musgo neblina ola pradera rocio sendero tormenta trebol vertiente
acequia arroyo cascada glaciar meseta quebrada llanura canal estero albahaca romero menta tomillo
oregano perejil cebolla papa zapallo choclo poroto haba quinoa avellana castana durazno ciruela
""".split()


def nueva_contrasena() -> str:
    palabras = sorted(set(PALABRAS))
    return "-".join(secrets.choice(palabras) for _ in range(4)) + "-" + f"{secrets.randbelow(10000):04d}"


# ---- Volver a cifrar ------------------------------------------------------------------------------------------
def _recifrar_sobre(sobre: str, vieja: str, nueva: str) -> str | None:
    """El sobre cifrado con la nueva; None si ya abría con la nueva (se deja tal cual). Con ninguna de las dos: error."""
    try:
        candado.descifrar_bytes(sobre, nueva)
        return None
    except Exception:
        pass
    datos = candado.descifrar_bytes(sobre, vieja)      # ya descomprimido; levanta InvalidTag si tampoco es la anterior
    return candado.cifrar_bytes(datos, nueva, comprimir=json.loads(sobre).get("comp") == "gzip")


def recifrar_texto(texto: str, vieja: str, nueva: str) -> tuple[str, int]:
    """(texto con cada sobre cifrado con la nueva, cuántos cambiaron). Un .json que es un sobre entero o un HTML
    con <script type="text/plain"> de sobres. Lo que no es sobre queda igual."""
    if texto.lstrip().startswith('{"v":'):
        nuevo = _recifrar_sobre(texto.strip(), vieja, nueva)
        return (texto, 0) if nuevo is None else (nuevo, 1)
    cambios = 0

    def uno(m):
        nonlocal cambios
        nuevo = _recifrar_sobre(m.group(2), vieja, nueva)
        if nuevo is None:
            return m.group(0)
        cambios += 1
        return m.group(1) + nuevo + m.group(3)

    return _SOBRE_HTML.sub(uno, texto), cambios


def archivos_cifrados(carpeta: Path, excluir=(".git", DATOS_RESUMEN)) -> list[Path]:
    """Los .html y .json de carpeta que llevan algún sobre del candado."""
    hallados = []
    if not carpeta.is_dir():
        return hallados
    for ruta in sorted(carpeta.rglob("*")):
        rel = ruta.relative_to(carpeta).as_posix()
        if not ruta.is_file() or ruta.suffix not in (".html", ".json") or any(rel == e or rel.startswith(e + "/") for e in excluir):
            continue
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if '"kdf":"PBKDF2-SHA256"' in texto:
            hallados.append(ruta)
    return hallados


def recifrar_archivos(rutas, vieja: str, nueva: str, escribir: bool = True) -> dict[Path, int]:
    """{ruta: sobres cambiados}. Escritura atómica; un archivo ya cifrado con la nueva no se toca."""
    hechos = {}
    for ruta in rutas:
        with open(ruta, encoding="utf-8", newline="") as f:
            texto = f.read()
        nuevo, n = recifrar_texto(texto, vieja, nueva)
        if n and escribir:
            tmp = ruta.with_name(ruta.name + ".tmp")
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(nuevo)
            os.replace(tmp, ruta)
        hechos[ruta] = n
    return hechos


def no_abren(rutas, contrasena: str) -> list[Path]:
    malos = []
    for ruta in rutas:
        texto = ruta.read_text(encoding="utf-8")
        sobres = [texto.strip()] if texto.lstrip().startswith('{"v":') else [m.group(2) for m in _SOBRE_HTML.finditer(texto)]
        try:
            for s in sobres:
                candado.descifrar_bytes(s, contrasena)
        except Exception:
            malos.append(ruta)
    return malos


# ---- Lo que se cambia -----------------------------------------------------------------------------------------
def carpetas_build() -> list[Path]:
    return [RAIZ / Path(origen).parent for _, origen in publicar.TABLEROS.values()]


def inventario() -> dict[str, list[Path]]:
    return {
        "gh-pages": archivos_cifrados(publicar.RAIZ_GH_PAGES),
        "build": [r for c in carpetas_build() for r in archivos_cifrados(c)],
    }


def _git(repo: Path, *args) -> str:
    return publicar._git(*args, repo=repo)


def revisar(vieja: str, nueva: str | None) -> list[str]:
    """Lo que impide cambiarla ([] = se puede). nueva = la de una corrida anterior que quedó a medias."""
    problemas = []
    if not (publicar.RAIZ_GH_PAGES / ".git").exists():
        return [f"no está el worktree de gh-pages en {publicar.RAIZ_GH_PAGES}"]
    if _git(publicar.RAIZ_GH_PAGES, "status", "--porcelain"):
        problemas.append("gh-pages local tiene cambios sin commit (otra sesión publicando): espera o avísale")
    problemas += publicar.revisar_gh_pages()
    if not candado.RUTA_INDEX_FORMULADOR.exists():
        problemas.append(f"no está el Formulador en {RAIZ_FORMULADOR}")
    else:
        rama = _git(RAIZ_FORMULADOR, "rev-parse", "--abbrev-ref", "HEAD")
        if rama != "main":
            problemas.append(f"el Formulador está en la rama {rama}, no en main")
        if _git(RAIZ_FORMULADOR, "status", "--porcelain", "--", "index.html"):
            problemas.append("el index.html del Formulador tiene cambios sin commit")
        try:
            _git(RAIZ_FORMULADOR, "fetch", "--quiet", "origin", "main")
            atras = _git(RAIZ_FORMULADOR, "rev-list", "--count", "HEAD..origin/main")
            if atras != "0":
                problemas.append(f"el Formulador está {atras} commit(s) atrás de origin/main: primero git pull")
        except RuntimeError as error:
            problemas.append(f"no se pudo revisar el Formulador con origin ({error})")
    publicados = archivos_cifrados(publicar.RAIZ_GH_PAGES)
    if not publicados:
        problemas.append("gh-pages no tiene ningún tablero cifrado: nada que cambiar")
    claves = [vieja] + ([nueva] if nueva else [])
    malos = [r for r in publicados if all(r in no_abren([r], c) for c in claves)]
    if malos:
        problemas.append("no abren con la contraseña actual: "
                         + ", ".join(r.relative_to(publicar.RAIZ_GH_PAGES).as_posix() for r in malos[:5]))
    return problemas


def _guardar(ruta: Path, texto: str) -> None:
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(texto + "\n", encoding="utf-8")
    os.replace(tmp, ruta)


def cambiar() -> int:
    if os.environ.get(candado.VARIABLE_CONTRASENA):
        print(f"[NO SE CAMBIA] la variable {candado.VARIABLE_CONTRASENA} fija la contraseña en este proceso: quítala.")
        return 1
    # Una corrida anterior que quedó a medias: la anterior está guardada aparte y la nueva ya es la actual.
    if RUTA_ANTERIOR.exists():
        vieja = RUTA_ANTERIOR.read_text(encoding="utf-8").strip()
        nueva = candado.leer_contrasena()
        print("[AVISO] hay un cambio a medias: se sigue con la misma contraseña nueva.")
    else:
        vieja, nueva = candado.leer_contrasena(), None
    problemas = revisar(vieja, nueva)
    if problemas:
        for p in problemas:
            print(f"[NO SE CAMBIA] {p}")
        return 1

    if nueva is None:
        nueva = nueva_contrasena()
        _guardar(RUTA_ANTERIOR, vieja)
        _guardar(candado.RUTA_CONTRASENA, nueva)
        print(f"[OK] contraseña nueva guardada en {candado.RUTA_CONTRASENA} (la anterior, aparte hasta terminar).")

    inv = inventario()
    for donde, rutas in inv.items():
        hechos = recifrar_archivos(rutas, vieja, nueva)
        print(f"[OK] {donde}: {sum(1 for n in hechos.values() if n)} de {len(rutas)} archivo(s) cifrados de nuevo.")
    malos = no_abren(inv["gh-pages"] + inv["build"], nueva)
    if malos:
        print("[ERROR] no abren con la nueva: " + ", ".join(str(r) for r in malos[:5]) + ". Vuelve a correr --cambiar.")
        return 1

    candado.escribir_llave(contrasena=nueva)
    if not candado.llave_abre_con(candado.RUTA_INDEX_FORMULADOR.read_text(encoding="utf-8"), nueva):
        print("[ERROR] la llave del Formulador no abre con la nueva. Vuelve a correr --cambiar.")
        return 1
    print("[OK] llave del Formulador escrita.")

    # gh-pages: los archivos cambiados al índice, commit, push y verificación en línea
    rels = [r.relative_to(publicar.RAIZ_GH_PAGES).as_posix() for r in inv["gh-pages"]]
    _git(publicar.RAIZ_GH_PAGES, "add", "--", *rels)
    if publicar.subir(rels, "cambiar la contraseña del equipo: tableros cifrados de nuevo"):
        print("[ERROR] gh-pages no quedó igual en línea. Revisa y vuelve a correr --cambiar.")
        return 1

    if _git(RAIZ_FORMULADOR, "status", "--porcelain", "--", "index.html"):
        _git(RAIZ_FORMULADOR, "commit", "-q", "-m", "Cambiar la contraseña del equipo: llave nueva", "--", "index.html")
        _git(RAIZ_FORMULADOR, "push", "-q", "origin", "main")
        print(f"[OK] Formulador main {_git(RAIZ_FORMULADOR, 'rev-parse', '--short', 'HEAD')} empujado.")

    # El resumen del teléfono: sin sus sobres, resumen_movil.py los arma todos de nuevo con la contraseña actual.
    if RESUMEN.exists():
        for ruta in SALIDA_RESUMEN.glob("*.json"):
            if ruta.name != "indice.json":
                ruta.unlink()
        r = subprocess.run([sys.executable, str(RESUMEN), "publicar", "--ya"], cwd=RESUMEN.parent)
        if r.returncode:
            print("[AVISO] el resumen del teléfono no se pudo subir: la tarea del procesador lo reintenta sola.")

    RUTA_ANTERIOR.unlink(missing_ok=True)
    print("\n[LISTO] Contraseña cambiada. Léela en el archivo (no se imprime):")
    print(f'  notepad "{candado.RUTA_CONTRASENA}"')
    print("Avisa al equipo: cada navegador la pide una vez; la anterior ya no abre nada.")
    return 0


def ver() -> int:
    """Sin cambiar nada: qué se cifraría de nuevo y si hoy se puede."""
    vieja = candado.leer_contrasena()
    nueva = candado.leer_contrasena() if RUTA_ANTERIOR.exists() else None
    if nueva:
        vieja = RUTA_ANTERIOR.read_text(encoding="utf-8").strip()
        print("[AVISO] hay un cambio a medias: --cambiar lo termina con la misma contraseña nueva.")
    for donde, rutas in inventario().items():
        print(f"{donde}: {len(rutas)} archivo(s) cifrados")
    print(f"Formulador: {candado.RUTA_INDEX_FORMULADOR}")
    print(f"Resumen del teléfono: {SALIDA_RESUMEN} (se arma de nuevo)")
    problemas = revisar(vieja, nueva)
    for p in problemas:
        print(f"[NO SE PODRÍA] {p}")
    if not problemas:
        print("[OK] se puede cambiar: corre de nuevo con --cambiar.")
    return 1 if problemas else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cambiar", action="store_true", help="cambiarla y publicar todo (sin esto, solo dice qué haría)")
    args = ap.parse_args(argv)
    return cambiar() if args.cambiar else ver()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main())
