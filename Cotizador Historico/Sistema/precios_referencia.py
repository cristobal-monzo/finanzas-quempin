# -*- coding: utf-8 -*-
"""
precios_referencia.py -- Los precios del Cotizador Histórico para el
Formulador de proyectos (carpeta de intercambio, ``publicado/precios-referencia.json``).

Plan de integración (2026-09-30), fase 1b: al escribir un material en el
Formulador, ofrecer el precio de compra reajustado por UF de las compras
reales, con cuántas compras lo respaldan y cuándo fue la última. Hasta hoy
esos precios existían en el tablero del Cotizador, pero el Formulador --donde
cambian una decisión-- no los veía.

QUÉ SE PUBLICA (decisión del 2026-10-01): una entrada por **hoja** (tipo +
material + medida: la unidad de comparación de precios de este módulo), con
el promedio, el rango y el último precio reajustados por UF, **sin IVA**, y
los términos de búsqueda ya indexados. **No** se publican proveedores ni
proyectos: la carpeta la ve todo el que entra a la biblioteca de Formulación,
y para cotizar bastan el precio, el rango y el n° de compras. Los términos de
búsqueda de esos dos campos tampoco viajan (se podría reconstruir el
proveedor desde ellos), ni el campo de códigos (lleva el N° Ref de Centro de
Costos).

La descripción es texto libre extraído de cada factura y arrastra números de
documento tributario («factura n 149187224») y nombres de tiendas
(«sodimac»): medido el 2026-10-01 sobre el catálogo real, 16 hojas los
traían. ``palabras_privadas`` los saca con una regla que sale de los propios
datos, no de una lista a mano: los N° Ref, todo número de 5 o más dígitos, y
cada palabra de un nombre de proveedor que **no** aparece en ningún campo de
producto (así «punta» o «industrial», que también nombran productos, se
conservan; «sodimac», no).

NADA SE RECALCULA AQUÍ: se parte de la foto que ya arma el tablero
(``Visualizador Web/data/cotizador-historico.json``: compras reajustadas a la
UF del día, con su taxonomía y sus términos de búsqueda) y se agrupa con la
misma ``agrupar_por_hoja`` que usan la consola y el tablero. Así el número
que ve el Formulador es el mismo que el del tablero, y la UF se pide una sola
vez (en el build del tablero), no en cada publicación.

El Formulador busca sobre estas hojas con ``busqueda.js`` (copia textual del
de este módulo, ver tests) y la configuración que viaja en ``busqueda``: el
mismo motor y las mismas tablas que el tablero, sin un segundo buscador.
"""

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent                      # Cotizador Historico/Sistema
RAIZ_MODULO = RAIZ.parent                                    # Cotizador Historico
RAIZ_SISTEMA_INTERCAMBIO = RAIZ_MODULO.parent / "Sistema Intercambio"
for ruta in (RAIZ, RAIZ_SISTEMA_INTERCAMBIO):
    if str(ruta) not in sys.path:
        sys.path.insert(0, str(ruta))

import cotizador_historico as ch  # noqa: E402
import esquemas  # noqa: E402
import intercambio  # noqa: E402
import ubicacion  # noqa: E402

RUTA_SNAPSHOT = RAIZ_MODULO / "Visualizador Web" / "data" / "cotizador-historico.json"
PUBLICACION = "precios-referencia"
HERRAMIENTA = "cotizador-historico"
# Campos del índice de búsqueda que no viajan: nombran a proveedores y
# proyectos, o (cod) llevan el N° Ref de Centro de Costos.
CAMPOS_PRIVADOS = ("prov", "proy", "cod")
# Campos que describen el producto: su vocabulario nunca se borra.
CAMPOS_DE_PRODUCTO = ("tipo", "nom", "hoja", "mat", "dim", "esp", "term", "apl", "mar", "cat")
_NUMERO_LARGO = re.compile(r"^\d{5,}$")


def _palabras(texto) -> set:
    plano = "".join(c for c in unicodedata.normalize("NFD", str(texto or "").lower())
                    if unicodedata.category(c) != "Mn")
    return {w for w in re.split(r"[^a-z0-9]+", plano) if w}


def palabras_privadas(compras: list[dict]) -> set:
    """Lo que no puede salir en el índice publicado: los N° Ref (juntos y su
    prefijo, «junj014» y «junj») y las palabras de nombres de proveedores
    que no son vocabulario de producto."""
    privadas = set()
    vocabulario = set()
    proveedores = set()
    for compra in compras:
        ref = str(compra.get("n_ref") or "").lower()
        if ref:
            privadas.add(re.sub(r"[^a-z0-9]", "", ref))
            privadas.add(re.split(r"[^a-z0-9]", ref)[0])
        proveedores |= {w for w in _palabras(compra.get("proveedor_tag")) if len(w) >= 4}
        for campo in CAMPOS_DE_PRODUCTO:
            vocabulario |= set(str((compra.get("_bt") or {}).get(campo) or "").split())
    return privadas | (proveedores - vocabulario)


def _fecha_iso(texto) -> str:
    """'01-10-2026 08:42' (como lo escribe el build) -> '2026-10-01T08:42'."""
    for formato in ("%d-%m-%Y %H:%M", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(texto), formato).isoformat(timespec="minutes")
        except ValueError:
            continue
    return str(texto or "")


def _unir_terminos(compras: list[dict], privadas: set) -> dict:
    """El índice de una hoja: por campo, la unión (sin repetir, en orden de
    aparición) de los términos de sus compras, sin los campos privados ni
    las palabras privadas."""
    por_campo: dict[str, list[str]] = {}
    for compra in compras:
        for campo, texto in (compra.get("_bt") or {}).items():
            if campo in CAMPOS_PRIVADOS or not texto:
                continue
            lista = por_campo.setdefault(campo, [])
            for termino in str(texto).split():
                if termino in privadas or _NUMERO_LARGO.match(termino) or termino in lista:
                    continue
                lista.append(termino)
    return {campo: " ".join(lista) for campo, lista in por_campo.items()}


def hojas(compras: list[dict]) -> list[dict]:
    """Una entrada por hoja cotizable, de la más comprada a la menos."""
    privadas = palabras_privadas(compras)
    salida = []
    for grupo in ch.agrupar_por_hoja(compras):
        if not grupo.get("cotizable", True) or grupo.get("secundaria"):
            continue
        ultima = max(grupo["compras"], key=lambda c: str(c.get("fecha") or ""))
        medidas = sorted({m for c in grupo["compras"] for m in (c.get("_bm") or [])})
        salida.append({
            "clave": grupo["hoja_clave"],
            "nombre": grupo["hoja"],
            "categoria": grupo.get("categoria") or "",
            "subcategoria": grupo.get("subcategoria") or "",
            "tipo": grupo.get("familia") or "",
            "material": grupo.get("material"),
            "medida": grupo.get("medida"),
            "n": grupo["n_compras"],
            "precio": {
                "promedio": grupo["promedio_reajustado"],
                "minimo": grupo["rango_minimo"],
                "maximo": grupo["rango_maximo"],
                "ultimo": ultima["precio_reajustado_hoy"],
            },
            "ultimaCompra": str(ultima.get("fecha") or ""),
            "_bt": _unir_terminos(grupo["compras"], privadas),
            "_bm": medidas,
        })
    return salida


def datos_desde_snapshot(snapshot: dict) -> dict:
    return {
        "uf": {"valor": snapshot["uf_hoy"], "fecha": _fecha_iso(snapshot.get("uf_fecha")),
               "fuente": snapshot.get("uf_fuente") or "mindicador.cl"},
        "fotoDelTablero": _fecha_iso(snapshot.get("generado")),
        "iva": "Precios sin IVA, reajustados por UF a la fecha indicada.",
        "hojas": hojas(snapshot.get("items") or []),
        "busqueda": snapshot.get("busqueda") or {},
    }


def leer_snapshot(ruta: Path = RUTA_SNAPSHOT) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def publicar(raiz_intercambio: Path, ruta_snapshot: Path = RUTA_SNAPSHOT) -> dict:
    """Publica desde la foto del tablero. {'ruta', 'hojas', 'foto'}. Lanza
    FileNotFoundError si el tablero nunca se generó (correr
    ``driver.py visualizador``) y ValueError si no cumple su esquema."""
    datos = datos_desde_snapshot(leer_snapshot(ruta_snapshot))
    sobre = {"esquema": intercambio.ESQUEMA, "herramienta": HERRAMIENTA, "generado": intercambio.ahora_iso(),
             "datos": datos}
    errores = esquemas.validar_publicacion(PUBLICACION, sobre)
    if errores:
        raise ValueError("precios-referencia no cumple su esquema: " + "; ".join(errores[:5]))
    ruta = intercambio.publicar(raiz_intercambio, PUBLICACION, HERRAMIENTA, datos)
    return {"ruta": ruta, "hojas": len(datos["hojas"]), "foto": datos["fotoDelTablero"]}


def publicacion_al_dia(raiz_intercambio: Path, ruta_snapshot: Path = RUTA_SNAPSHOT) -> bool:
    """True si lo publicado ya sale de la foto actual del tablero (el
    procesador del intercambio solo republica cuando cambió)."""
    sobre = intercambio.leer_publicacion(raiz_intercambio, PUBLICACION)
    if not sobre or not ruta_snapshot.exists():
        return False
    try:
        foto = _fecha_iso(leer_snapshot(ruta_snapshot).get("generado"))
    except (OSError, ValueError):
        return False
    return (sobre.get("datos") or {}).get("fotoDelTablero") == foto


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raiz = ubicacion.ubicar_intercambio(RAIZ)
    if raiz is None or not intercambio.es_carpeta_de_intercambio(raiz):
        print("[AVISO] No se encontró la carpeta de intercambio (biblioteca «Formulación de proyectos» sin sincronizar).")
        return 1
    try:
        r = publicar(raiz)
    except FileNotFoundError:
        print("[ERROR] Falta la foto del tablero: corre primero 'driver.py visualizador'.")
        return 1
    print(f"Precios de referencia publicados: {r['hojas']} hojas (foto del tablero del {r['foto']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
