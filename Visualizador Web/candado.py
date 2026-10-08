# -*- coding: utf-8 -*-
"""Candado de los tableros publicados: sus datos viajan cifrados con la contraseña.

Por que existe (2026-10-05): el sitio de GitHub Pages y su repo son publicos, y
hasta esta fecha cada tablero llevaba sus datos solo codificados en base64, con
la contrasena escrita en claro en el propio HTML (y en las plantillas
versionadas). Cualquiera con el link podia leer todas las cifras sin saberla, y
el clasificador de permisos de Claude Code empezo a bloquear el push por eso.

Ahora cada build guarda en el HTML un "sobre" con los datos cifrados
(AES-256-GCM, clave derivada de la contrasena con PBKDF2-SHA256) y candado.js
los abre en el navegador. La contrasena no esta en ningun archivo versionado ni
publicado: sin ella, lo publicado es ilegible.

La contrasena se lee, en este orden, de:
1. la variable de entorno QUEMPIN_TABLEROS_CONTRASENA (los tests la fijan, ver
   conftest.py de la raiz);
2. el archivo .contrasena_tableros en la raiz del repo (una linea; gitignored).
Si no hay ninguna, el build falla: nunca se genera un tablero sin cifrar.

Cambiar la contrasena: editar ese archivo, regenerar y publicar los 7 tableros.
Un navegador que recordaba la anterior la vuelve a pedir solo.
"""
import base64
import functools
import gzip
import hashlib
import json
import os
import re
import secrets
import unicodedata
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RAIZ_REPO = Path(__file__).resolve().parents[1]
RUTA_CONTRASENA = RAIZ_REPO / ".contrasena_tableros"
VARIABLE_CONTRASENA = "QUEMPIN_TABLEROS_CONTRASENA"
RUTA_JS = Path(__file__).resolve().with_name("candado.js")
MARCADOR_JS = "__CANDADO_JS__"

# La sal es publica (va en el sobre) y es la misma en los 7 tableros: asi la
# clave que el navegador recuerda al escribir la contrasena en uno abre tambien
# los demas, como hacia la barrera anterior.
SAL = b"quempin-tableros-2026"
# PBKDF2-SHA256 con 600.000 iteraciones (recomendacion OWASP 2023): en un
# telefono tarda menos de un par de segundos, una sola vez por navegador.
ITERACIONES = 600_000


class SinContrasena(RuntimeError):
    """No hay contrasena de los tableros configurada en este equipo."""


def normalizar(contrasena: str) -> str:
    """Igual que normalizar() de candado.js: sin mayusculas, tildes ni espacios en los extremos."""
    s = unicodedata.normalize("NFD", str(contrasena).lower())
    return "".join(c for c in s if not "\u0300" <= c <= "\u036f").strip()


def leer_contrasena() -> str:
    valor = os.environ.get(VARIABLE_CONTRASENA)
    if valor is None and RUTA_CONTRASENA.exists():
        valor = RUTA_CONTRASENA.read_text(encoding="utf-8").strip()
    if not valor or not normalizar(valor):
        raise SinContrasena(
            f"No hay contraseña de los tableros en este equipo: escríbela en una línea en "
            f"{RUTA_CONTRASENA} (no se versiona) o en la variable de entorno {VARIABLE_CONTRASENA}."
        )
    return valor


@functools.lru_cache(maxsize=8)
def derivar_clave(contrasena: str, sal: bytes = SAL, iteraciones: int = ITERACIONES) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", normalizar(contrasena).encode("utf-8"), sal, iteraciones, 32)


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def cifrar_bytes(datos: bytes, contrasena: str | None = None, comprimir: bool = False) -> str:
    """Sobre de unos bytes cualquiera (JSON de una linea, solo ASCII).

    Version 2 (2026-10-08): con comprimir=True los bytes pasan por gzip ANTES
    de cifrar ("comp": "gzip"). Lo cifrado no se puede comprimir, asi que esa
    es la unica oportunidad: los datos de Centro de Costos bajan de 1,0 MB a
    ~0,1 MB y los del Cotizador de 3,0 MB a ~0,25 MB. mtime=0 deja el gzip
    igual en cada build. Los PDF van sin comprimir: ya vienen comprimidos."""
    if contrasena is None:
        contrasena = leer_contrasena()
    if comprimir:
        datos = gzip.compress(datos, mtime=0)
    iv = secrets.token_bytes(12)
    cifrado = AESGCM(derivar_clave(contrasena)).encrypt(iv, datos, None)
    return json.dumps({"v": 2, "kdf": "PBKDF2-SHA256", "it": ITERACIONES, "sal": _b64(SAL), "iv": _b64(iv),
                       "comp": "gzip" if comprimir else None, "datos": _b64(cifrado)}, separators=(",", ":"))


def cifrar(texto: str, contrasena: str | None = None) -> str:
    """El sobre que va en el HTML en lugar de los datos: el texto, comprimido y cifrado."""
    return cifrar_bytes(texto.encode("utf-8"), contrasena, comprimir=True)


def descifrar_bytes(sobre: str, contrasena: str) -> bytes:
    """Inverso de cifrar_bytes(); abre tambien los sobres version 1 (sin "comp").
    Con otra contrasena levanta cryptography.exceptions.InvalidTag."""
    s = json.loads(sobre)
    clave = derivar_clave(contrasena, base64.b64decode(s["sal"]), s["it"])
    plano = AESGCM(clave).decrypt(base64.b64decode(s["iv"]), base64.b64decode(s["datos"]), None)
    return gzip.decompress(plano) if s.get("comp") == "gzip" else plano


def descifrar(sobre: str, contrasena: str) -> str:
    """Inverso de cifrar(). Con otra contrasena levanta cryptography.exceptions.InvalidTag."""
    return descifrar_bytes(sobre, contrasena).decode("utf-8")


# Archivos cifrados que un tablero baja al usarlos (2026-10-08): hoy, los
# reportes PDF de Analisis Financiero, que eran el 97 % de sus datos. Van junto
# al index.html, con el nombre derivado de su contenido.
CARPETA_ARCHIVOS = "reportes"
_PATRON_ARCHIVO = re.compile(r"^" + CARPETA_ARCHIVOS + r"/[0-9a-f]{16,64}\.json$")


def nombre_archivo(datos: bytes) -> str:
    """Ruta relativa al index.html de un archivo cifrado: la misma para el
    mismo contenido, asi un reporte que no cambio no ensucia gh-pages."""
    return f"{CARPETA_ARCHIVOS}/{hashlib.sha256(datos).hexdigest()[:24]}.json"


def archivos_citados(datos) -> list[str]:
    """Rutas de archivos cifrados que nombran los datos de un tablero."""
    encontrados = []

    def recorrer(x):
        if isinstance(x, dict):
            for v in x.values():
                recorrer(v)
        elif isinstance(x, list):
            for v in x:
                recorrer(v)
        elif isinstance(x, str) and _PATRON_ARCHIVO.match(x):
            encontrados.append(x)

    recorrer(datos)
    return sorted(set(encontrados))


def incrustar(html: str, marcador_datos: str, texto: str, contrasena: str | None = None) -> str:
    """Pone candado.js y el sobre con `texto` cifrado en la plantilla ya armada.

    Va al final de cada build: el sobre es lo ultimo que se reemplaza, asi
    ningun texto suyo puede pasar por un marcador.
    """
    for marcador in (MARCADOR_JS, marcador_datos):
        if marcador not in html:
            raise ValueError(f"la plantilla no tiene el marcador {marcador}")
    sobre = cifrar(texto, contrasena)
    return html.replace(MARCADOR_JS, RUTA_JS.read_text(encoding="utf-8")).replace(marcador_datos, sobre)


def leer_datos(html: str, id_script: str, contrasena: str):
    """Los datos que lleva un tablero ya construido (para tests y revisiones)."""
    m = re.search(r'<script id="' + re.escape(id_script) + r'" type="text/plain">([^<]*)</script>', html)
    if not m:
        raise ValueError(f"el HTML no tiene <script id=\"{id_script}\">")
    return json.loads(descifrar(m.group(1), contrasena))


def abre_con(html: str, contrasena: str, carpeta: Path | None = None) -> bool:
    """True si el tablero trae sus datos en un sobre y la contrasena lo abre.
    Con 'carpeta' (la del index.html), tambien cada archivo cifrado que citan
    sus datos tiene que estar ahi y abrir: un tablero publicado sin su carpeta
    reportes/ tendria botones que no abren nada."""
    sobres = re.findall(r'<script id="[^"]+" type="text/plain">(\{"v":[^<]*)</script>', html)
    try:
        if not sobres:
            return False
        for s in sobres:
            datos = json.loads(descifrar(s, contrasena))
            if datos is None:
                return False
            if carpeta is not None:
                for rel in archivos_citados(datos):
                    descifrar_bytes((Path(carpeta) / rel).read_text(encoding="utf-8"), contrasena)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Paso obligatorio antes de publicar (receta de Visualizador Web/CLAUDE.md
    # § Hosting): cada tablero tiene que abrir con la contrasena de este equipo.
    # El 2026-10-05 se publico Analisis Financiero cifrado con la de prueba (los
    # tests lo habian regenerado entre el build y la copia) y el equipo no podia
    # abrirlo.
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    contrasena_real = leer_contrasena()
    rutas = sys.argv[1:]
    malos = [r for r in rutas
             if not abre_con(Path(r).read_text(encoding="utf-8"), contrasena_real, carpeta=Path(r).parent)]
    for ruta in rutas:
        print(f"[{'NO ABRE' if ruta in malos else 'OK'}] {ruta}")
    if malos:
        print("No publiques: regenera esos tableros (build_visualizador.py) y vuelve a verificar.")
    raise SystemExit(1 if malos or not rutas else 0)
