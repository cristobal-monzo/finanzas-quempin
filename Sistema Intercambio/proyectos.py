# -*- coding: utf-8 -*-
"""
proyectos.py -- El registro de proyectos: el cruce de claves entre las
herramientas (``publicado/proyectos.json``).

Plan de integración (2026-09-30, §5.2): el N° de la Planilla de Ingreso de
Requerimientos (``req``) es la clave común de proyecto; el TAG del Análisis
Financiero y de Centro de Costos se asocia al ``req`` cuando el proyecto se
adjudica. Cada herramienta guarda el ``req`` en su propio dato:

- Análisis Financiero: columna «N° Requerimiento» (publicada como ``req``);
- Formulador: ``vinculos.requerimiento`` del proyecto (repositorio);
- Sistema QUEMPIN: ``proyecto.req`` de cada cotización y orden de compra.

Este módulo **no es dueño de ningún dato**: lee lo que publican los demás
(y los nombres de carpeta de las bibliotecas, que ya llevan el N°: «280. UMAG
- Conexión…») y arma una entrada por requerimiento con todo lo que cuelga de
él. Lo que tiene TAG pero todavía no tiene ``req`` queda en ``sinVincular``,
para que alguien lo complete donde corresponde (no aquí).

Un TAG que aparece con dos ``req`` distintos no se adivina: va a
``conflictos``.

Cada orden de compra dice además si ya está en el Centro de Costos
(``enCentroCostos``, 2026-10-28): desde ese día el Centro de Costos trae a su
libro las OC con proyecto hasta que su factura las reemplaza, así que su monto
ya cuenta en los costos reales del Análisis Financiero. Lo dice el registro de
OC del Centro de Costos (el mismo que lee Flujo de Caja); sin registro en este
equipo el campo no va: no se sabe. Lo usa «Proyectos en ejecución» del Portal
para no contar dos veces una compra.
"""

import json
import re
import unicodedata
from pathlib import Path

import carpetas_proyecto
import formulaciones
import intercambio
import ubicacion

PUBLICACION = "proyectos"
HERRAMIENTA = "procesador"
# Estados de la Planilla que entran aunque no tengan nada colgando: lo que
# sigue vivo. Lo descartado y lo no adjudicado solo entra si algo lo nombra.
ESTADOS_VIVOS = {"Evaluación", "Ofertado", "Adjudicado"}
_CARPETA_CON_NUMERO = re.compile(r"^\s*(\d{1,4})\s*[.\-_)]\s*(.+)$")
# El registro de OC de cada Centro de Costos (gitignoreado: lleva montos), por país
RAIZ_FINANZAS = Path(__file__).resolve().parent.parent
RUTAS_ORDENES_CC = {
    "chile": RAIZ_FINANZAS / "Centro de Costos" / "Sistema" / "ordenes_compra.json",
    "peru": RAIZ_FINANZAS / "Peru" / "Centro de Costos" / "ordenes_compra_peru.json",
}

# Dónde buscar carpetas de proyecto, por biblioteca: subcarpetas que agrupan
# (se mira también un nivel dentro de ellas).
CARPETAS_AGRUPADORAS = ("0 ", "1 ", "2 ")


def _req(valor) -> str | None:
    texto = str(valor if valor is not None else "").strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    return texto if texto.isdigit() and int(texto) > 0 else None


def _tag(valor) -> str | None:
    texto = str(valor or "").strip().upper()
    return texto or None


def _pais(valor) -> str:
    """«Perú», «Peru», «PERÚ» → «peru»."""
    texto = unicodedata.normalize("NFD", str(valor or "")).encode("ascii", "ignore").decode()
    return texto.strip().lower()


def folios_en_centro_costos(rutas: dict | None = None) -> dict[str, set[str]]:
    """{país: folios} de las OC que ya maneja el Centro de Costos de ese país:
    las que están en su libro, las que ya reemplazó su factura y las que
    llegaron con la factura registrada. Un país sin registro no va (no se sabe)."""
    salida = {}
    for pais, ruta in (rutas if rutas is not None else RUTAS_ORDENES_CC).items():
        try:
            with open(ruta, encoding="utf-8") as f:
                salida[pais] = {str(folio) for folio in (json.load(f).get("ordenes") or {})}
        except (OSError, ValueError, AttributeError):
            continue
    return salida


# ── CARPETAS ─────────────────────────────────────────────────────────────────

def carpetas_con_numero(raiz: Path, profundidad: int = 2) -> dict[str, list[str]]:
    """{req: [ruta relativa a 'raiz', ...]} de las carpetas que empiezan con
    un N° («280. UMAG - …», «261. FACH 1»). Baja dentro de las carpetas
    agrupadoras («0 OFERTAS ADJUDICADAS», «0 Ofertas Cerradas 2026») hasta
    'profundidad' niveles. Solo lista nombres: no abre ni descarga archivos."""
    salida: dict[str, list[str]] = {}
    if raiz is None or not Path(raiz).is_dir():
        return salida

    def recorrer(carpeta: Path, nivel: int):
        try:
            hijas = sorted(h for h in carpeta.iterdir() if h.is_dir() and not h.name.startswith("."))
        except OSError:
            return
        for hija in hijas:
            coincide = _CARPETA_CON_NUMERO.match(hija.name)
            if coincide:
                salida.setdefault(str(int(coincide.group(1))), []).append(hija.relative_to(raiz).as_posix())
            elif nivel < profundidad and hija.name.startswith(CARPETAS_AGRUPADORAS):
                recorrer(hija, nivel + 1)

    recorrer(Path(raiz), 1)
    return salida


def carpetas_de_proyectos(desde: Path | None = None, raiz_facturas: Path | None = None) -> dict:
    """{'oferta': {...}, 'ejecucion': {...}, 'facturas': {...}, 'facturasProyecto': {...}}
    con rutas relativas a cada biblioteca (cada colega tiene OneDrive en otra
    ruta). 'facturasProyecto': la subcarpeta «Facturas del proyecto» de la
    carpeta de Gestión (2026-10-28, carpetas_proyecto.py), en la misma
    biblioteca que 'ejecucion'."""
    gestion = ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, desde)
    ejecucion = carpetas_con_numero(gestion)
    return {
        "oferta": carpetas_con_numero(ubicacion.biblioteca(ubicacion.BIBLIOTECA_FORMULACION, desde)),
        "ejecucion": ejecucion,
        "facturas": carpetas_con_numero(raiz_facturas, profundidad=1) if raiz_facturas else {},
        "facturasProyecto": carpetas_proyecto.con_facturas(gestion, ejecucion),
    }


# ── CRUCE ────────────────────────────────────────────────────────────────────

def _datos(raiz, nombre) -> dict:
    sobre = intercambio.leer_publicacion(raiz, nombre)
    return sobre.get("datos") if isinstance(sobre, dict) and isinstance(sobre.get("datos"), dict) else {}


def cruzar(requerimientos: list[dict], proyectos_af: list[dict], repositorio: list[dict],
           documentos: list[dict], carpetas: dict, en_cc: dict | None = None) -> dict:
    """Función pura: el cruce completo a partir de lo publicado. en_cc: los
    folios de OC que ya están en el Centro de Costos, por país
    (folios_en_centro_costos)."""
    en_cc = en_cc or {}
    entradas: dict[str, dict] = {}

    def entrada(req: str) -> dict:
        if req not in entradas:
            entradas[req] = {"req": req, "tag": None, "titulo": None, "estado": None,
                             "formulaciones": [], "cotizaciones": [], "ordenes": [], "carpetas": {}}
        return entradas[req]

    for r in requerimientos:
        req = _req(r.get("numero"))
        if req and r.get("estado") in ESTADOS_VIVOS:
            e = entrada(req)
            e["titulo"], e["estado"] = r.get("titulo"), r.get("estado")
    por_numero = {_req(r.get("numero")): r for r in requerimientos}

    # TAG <-> req: lo que declara cada herramienta. Un TAG puede agrupar
    # varios req (mantenciones JUNJI); un req con dos TAG es un conflicto.
    tags_por_req: dict[str, set] = {}

    def vincular(req, tag):
        if req and tag:
            tags_por_req.setdefault(req, set()).add(tag)

    for p in proyectos_af:
        vincular(_req(p.get("req")), _tag(p.get("tag")))
    sin_req = {"tags": [], "formulaciones": [], "documentos": 0}
    for item in repositorio:
        d = item.get("datos") or {}
        if d.get("eliminado"):
            continue
        vinculos = d.get("vinculos") or {}
        req = _req((vinculos.get("requerimiento") or {}).get("numero") if isinstance(vinculos.get("requerimiento"), dict)
                   else vinculos.get("requerimiento"))
        tag = _tag((vinculos.get("analisisFinanciero") or {}).get("tag"))
        vincular(req, tag)
        ficha = {"uid": d.get("uid"), "codigo": d.get("codigo"), "version": d.get("version"),
                 "titulo": d.get("titulo"), "estado": d.get("estado"), "tag": tag}
        if req:
            entrada(req)["formulaciones"].append(ficha)
        else:
            sin_req["formulaciones"].append(ficha)
    for doc in documentos:
        proyecto = doc.get("proyecto") or {}
        req, tag = _req(proyecto.get("req")), _tag(proyecto.get("tag"))
        vincular(req, tag)
        ficha = {"folio": doc.get("folio"), "pais": doc.get("pais"), "fecha": doc.get("fecha"),
                 "referencia": doc.get("referencia"), "moneda": doc.get("moneda"), "neto": doc.get("neto"),
                 "contraparte": (doc.get("contraparte") or {}).get("razon_social")}
        if doc.get("tipo") != "60" and _pais(doc.get("pais")) in en_cc:
            ficha["enCentroCostos"] = str(doc.get("folio")) in en_cc[_pais(doc.get("pais"))]
        if req:
            entrada(req)["cotizaciones" if doc.get("tipo") == "60" else "ordenes"].append(ficha)
        else:
            sin_req["documentos"] += 1

    conflictos = []
    for req, tags in sorted(tags_por_req.items(), key=lambda par: int(par[0])):
        e = entrada(req)
        if len(tags) == 1:
            e["tag"] = next(iter(tags))
        else:
            conflictos.append({"req": req, "tags": sorted(tags),
                               "detalle": f"El requerimiento {req} aparece con {len(tags)} TAG distintos."})
    # Título y estado de la Planilla también para lo que entró solo porque
    # algo lo nombra (un requerimiento no adjudicado con una OC, por ejemplo).
    for req, e in entradas.items():
        if e["titulo"] is None and req in por_numero:
            e["titulo"], e["estado"] = por_numero[req].get("titulo"), por_numero[req].get("estado")

    tags_con_req = {t for tags in tags_por_req.values() for t in tags}
    for p in proyectos_af:
        tag = _tag(p.get("tag"))
        if tag and tag not in tags_con_req:
            sin_req["tags"].append({"tag": tag, "nombre": p.get("nombre")})

    for tipo, por_req in (carpetas or {}).items():
        for req, rutas in por_req.items():
            if req in entradas:
                entradas[req]["carpetas"][tipo] = rutas

    lista = sorted(entradas.values(), key=lambda e: -int(e["req"]))
    return {"proyectos": lista, "sinVincular": sin_req, "conflictos": conflictos}


def publicar(raiz: Path, carpetas: dict | None = None, rutas_ordenes_cc: dict | None = None) -> dict:
    """Arma el cruce desde lo publicado en 'raiz' y lo publica. Devuelve un
    resumen {'proyectos', 'sin_tag_req', 'conflictos'}."""
    datos = cruzar(
        _datos(raiz, "requerimientos").get("requerimientos") or [],
        _datos(raiz, "analisis-financiero").get("proyectos") or [],
        formulaciones.leer_repositorio(raiz),
        _datos(raiz, "documentos-comerciales").get("documentos") or [],
        carpetas if carpetas is not None else carpetas_de_proyectos(raiz),
        folios_en_centro_costos(rutas_ordenes_cc),
    )
    intercambio.publicar(raiz, PUBLICACION, HERRAMIENTA, datos)
    return {"proyectos": len(datos["proyectos"]), "sin_tag_req": len(datos["sinVincular"]["tags"]),
            "conflictos": len(datos["conflictos"])}
