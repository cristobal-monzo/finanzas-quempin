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

import formulaciones
import intercambio
import mismo_proyecto
import ubicacion

PUBLICACION = "proyectos"
HERRAMIENTA = "procesador"
# Estados de la Planilla que entran aunque no tengan nada colgando: lo que
# sigue vivo. Lo descartado y lo no adjudicado solo entra si algo lo nombra.
ESTADOS_VIVOS = {"Evaluación", "Ofertado", "Adjudicado"}
_CARPETA_CON_NUMERO = re.compile(r"^\s*(\d{1,4}t?)\s*[.\-_)]\s*(.+)$", re.IGNORECASE)
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
    if es_temporal(texto):
        return texto.lower()
    return texto if texto.isdigit() and int(texto) > 0 else None


def _n_carpeta(grupo: str) -> str | None:
    """N° del comienzo de una carpeta: «036» → «36»; «001T» → «001t» (temporal)."""
    return grupo.lower() if es_temporal(grupo) else _req(int(grupo)) if grupo.isdigit() else None


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
            n = _n_carpeta(coincide.group(1)) if coincide else None
            if n:
                salida.setdefault(n, []).append(hija.relative_to(raiz).as_posix())
            elif nivel < profundidad and hija.name.startswith(CARPETAS_AGRUPADORAS):
                recorrer(hija, nivel + 1)

    recorrer(Path(raiz), 1)
    return salida


ARCHIVO_TEMPORALES = "tags-temporales.json"
_TEMPORAL = re.compile(r"^\d{3,4}t$")


def es_temporal(valor) -> bool:
    """«001t» (2026-11-09, pedido del usuario): número temporal de un proyecto sin N° de la
    Planilla, para no asociarlo a un N° puntual. TAG: «001t - Nombre simplificado»."""
    return bool(_TEMPORAL.match(str(valor or "").strip().lower()))


def tag_temporal(numero: str, nombre: str) -> str:
    return f"{numero.strip().lower()} - {nombre.strip()}"


def leer_temporales(raiz: Path | None) -> dict[str, dict]:
    """{carpeta de Gestión: {'n': '001t', 'nombre': ...}} de ``tags-temporales.json`` en la carpeta de
    Intercambio. Vive ahí y no en git: lleva nombres reales de proyectos. Sin archivo, {}."""
    if raiz is None:
        return {}
    try:
        with open(Path(raiz) / ARCHIVO_TEMPORALES, encoding="utf-8") as f:
            carpetas = (json.load(f) or {}).get("carpetas") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    return {c: v for c, v in carpetas.items()
            if isinstance(v, dict) and es_temporal(v.get("n")) and str(v.get("nombre") or "").strip()}


def asignar_temporales(carpetas_sin_n: list[str], tabla: dict[str, dict]) -> dict[str, dict]:
    """Tabla completa: respeta lo ya asignado (un N° temporal no se reasigna ni se reutiliza) y da
    el siguiente 00Nt, con el nombre de la carpeta, a la carpeta sin N° que aún no lo tiene."""
    salida = {c: dict(v) for c, v in tabla.items()}
    usados = {int(v["n"][:-1]) for v in salida.values()}
    for carpeta in sorted(carpetas_sin_n):
        if carpeta not in salida:
            n = max(usados, default=0) + 1
            usados.add(n)
            salida[carpeta] = {"n": f"{n:03d}t", "nombre": carpeta}
    return salida


def proyectos_en_gestion(raiz: Path | None, temporales: dict[str, dict] | None = None) -> list[dict]:
    """[{'carpeta': nombre, 'req': N° o None}] de las carpetas de proyecto de la
    raíz de «Gestión de Proyectos», con o sin N° adelante (2026-11-03, pedido
    del usuario: todas deben verse en «Proyectos en ejecución» del Portal).
    Quedan fuera los archivos y las carpetas complementarias, las agrupadoras
    «0 …» («0 Carpeta modelo», «0 Proyectos Entregados 2026»). Solo lista nombres.
    ``temporales`` (2026-11-09): a la carpeta sin N° que figura ahí se le pone su N°
    temporal en ``req`` («001t») y su ``tag`` («001t - Nombre»)."""
    if raiz is None or not Path(raiz).is_dir():
        return []
    try:
        hijas = sorted(h for h in Path(raiz).iterdir() if h.is_dir() and not h.name.startswith("."))
    except OSError:
        return []
    temporales = temporales or {}
    salida = []
    for hija in hijas:
        if hija.name.startswith(CARPETAS_AGRUPADORAS):
            continue
        coincide = _CARPETA_CON_NUMERO.match(hija.name)
        fila = {"carpeta": hija.name, "req": _n_carpeta(coincide.group(1)) if coincide else None}   # «036.» → «36»
        t = temporales.get(hija.name)
        if t and fila["req"] is None:
            fila["req"] = t["n"].lower()
            fila["tag"] = tag_temporal(t["n"], t["nombre"])
        salida.append(fila)
    return salida


def _es_de_entregados(nombre: str) -> bool:
    """«0 Proyectos Entregados 2026» y las de otros años (sin importar mayúsculas ni tildes)."""
    sin_tildes = unicodedata.normalize("NFD", nombre).encode("ascii", "ignore").decode().lower()
    return nombre.startswith(CARPETAS_AGRUPADORAS) and "entregad" in sin_tildes


def proyectos_entregados(raiz: Path | None) -> list[dict]:
    """[{'carpeta', 'req', 'grupo'}] de las carpetas de proyecto dentro de las
    «0 Proyectos Entregados <año>» de la raíz de Gestión de Proyectos (2026-11-09,
    pedido del usuario: los proyectos que ya se cerraron van en su propia pestaña de
    «Proyectos en ejecución» del Portal). ``grupo`` es la carpeta del año. Con o sin
    N° adelante; sin archivos ni lo oculto. Solo lista nombres."""
    if raiz is None or not Path(raiz).is_dir():
        return []
    salida = []
    try:
        grupos = sorted(h for h in Path(raiz).iterdir() if h.is_dir() and _es_de_entregados(h.name))
    except OSError:
        return []
    for grupo in grupos:
        try:
            hijas = sorted(h for h in grupo.iterdir() if h.is_dir() and not h.name.startswith("."))
        except OSError:
            continue
        for hija in hijas:
            coincide = _CARPETA_CON_NUMERO.match(hija.name)
            salida.append({"carpeta": hija.name, "req": _n_carpeta(coincide.group(1)) if coincide else None,
                           "grupo": grupo.name})
    return salida


def carpetas_de_proyectos(desde: Path | None = None, raiz_facturas: Path | None = None) -> dict:
    """{'oferta': {...}, 'ejecucion': {...}, 'facturas': {...}} con rutas
    relativas a cada biblioteca (cada colega tiene OneDrive en otra ruta).
    procesar.py agrega 'facturasWeb': la dirección en SharePoint de la carpeta
    del Centro de Costos (carpetas_proyecto.py, 2026-10-29)."""
    return {
        "oferta": carpetas_con_numero(ubicacion.biblioteca(ubicacion.BIBLIOTECA_FORMULACION, desde)),
        "ejecucion": carpetas_con_numero(ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, desde)),
        "facturas": carpetas_con_numero(raiz_facturas, profundidad=1) if raiz_facturas else {},
    }


# ── CRUCE ────────────────────────────────────────────────────────────────────

def _datos(raiz, nombre) -> dict:
    sobre = intercambio.leer_publicacion(raiz, nombre)
    return sobre.get("datos") if isinstance(sobre, dict) and isinstance(sobre.get("datos"), dict) else {}


def cruzar(requerimientos: list[dict], proyectos_af: list[dict], repositorio: list[dict],
           documentos: list[dict], carpetas: dict, en_cc: dict | None = None,
           carpetas_cc: list[dict] | None = None) -> dict:
    """Función pura: el cruce completo a partir de lo publicado. en_cc: los
    folios de OC que ya están en el Centro de Costos, por país
    (folios_en_centro_costos). carpetas_cc: las carpetas del Centro de Costos
    de Chile (centro-costos-carpetas): un TAG cuya ficha tiene su carpeta y un
    N° que tiene otra son dos proyectos (mismo_proyecto) y no se unen, venga el
    vínculo de quien venga; va a ``conflictos`` y a ``fichaAjena`` del N°."""
    en_cc = en_cc or {}
    nombre_af = {_tag(p.get("tag")): p.get("nombre") for p in proyectos_af if _tag(p.get("tag"))}
    conflictos = []
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

    def vincular(req, tag, quien="El Análisis Financiero"):
        if not (req and tag):
            return
        ajena = mismo_proyecto.carpeta_ajena(nombre_af.get(tag), req, carpetas_cc)
        if ajena:
            entrada(req).setdefault("fichaAjena", [])
            if tag not in entrada(req)["fichaAjena"]:
                entrada(req)["fichaAjena"].append(tag)
                conflictos.append({"req": req, "tags": [tag], "detalle": f"{quien} une el N° {req} con la ficha {tag}. "
                                   + mismo_proyecto.motivo(tag, nombre_af.get(tag), req, ajena)})
            return
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
        vincular(req, tag, f"La formulación «{d.get('codigo') or d.get('uid')}»")
        ficha = {"uid": d.get("uid"), "codigo": d.get("codigo"), "version": d.get("version"),
                 "titulo": d.get("titulo"), "estado": d.get("estado"), "tag": tag}
        if req:
            entrada(req)["formulaciones"].append(ficha)
        else:
            sin_req["formulaciones"].append(ficha)
    for doc in documentos:
        proyecto = doc.get("proyecto") or {}
        req, tag = _req(proyecto.get("req")), _tag(proyecto.get("tag"))
        vincular(req, tag, f"El documento {doc.get('folio')} de Sistema QUEMPIN")
        ficha = {"folio": doc.get("folio"), "pais": doc.get("pais"), "fecha": doc.get("fecha"),
                 "referencia": doc.get("referencia"), "moneda": doc.get("moneda"), "neto": doc.get("neto"),
                 "contraparte": (doc.get("contraparte") or {}).get("razon_social")}
        if doc.get("tipo") != "60" and _pais(doc.get("pais")) in en_cc:
            ficha["enCentroCostos"] = str(doc.get("folio")) in en_cc[_pais(doc.get("pais"))]
        if req:
            entrada(req)["cotizaciones" if doc.get("tipo") == "60" else "ordenes"].append(ficha)
        else:
            sin_req["documentos"] += 1

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


def publicar(raiz: Path, carpetas: dict | None = None, rutas_ordenes_cc: dict | None = None,
             gestion: list[dict] | None = None, entregados: list[dict] | None = None) -> dict:
    """Arma el cruce desde lo publicado en 'raiz' y lo publica. gestion: las
    carpetas de la raíz de Gestión (proyectos_en_gestion); entregados: las de sus
    «0 Proyectos Entregados <año>» (proyectos_entregados). Devuelve un resumen
    {'proyectos', 'sin_tag_req', 'conflictos', 'gestion', 'entregados'}."""
    datos = cruzar(
        _datos(raiz, "requerimientos").get("requerimientos") or [],
        _datos(raiz, "analisis-financiero").get("proyectos") or [],
        formulaciones.leer_repositorio(raiz),
        _datos(raiz, "documentos-comerciales").get("documentos") or [],
        carpetas if carpetas is not None else carpetas_de_proyectos(raiz),
        folios_en_centro_costos(rutas_ordenes_cc),
        carpetas_cc=((_datos(raiz, "centro-costos-carpetas").get("paises") or {}).get("CL")) or [],
    )
    datos["gestion"] = gestion if gestion is not None else proyectos_en_gestion(
        ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, raiz), leer_temporales(raiz))
    datos["entregados"] = entregados if entregados is not None else proyectos_entregados(
        ubicacion.biblioteca(ubicacion.BIBLIOTECA_GESTION, raiz))
    intercambio.publicar(raiz, PUBLICACION, HERRAMIENTA, datos)
    return {"proyectos": len(datos["proyectos"]), "sin_tag_req": len(datos["sinVincular"]["tags"]),
            "conflictos": len(datos["conflictos"]), "gestion": len(datos["gestion"]),
            "entregados": len(datos["entregados"])}
