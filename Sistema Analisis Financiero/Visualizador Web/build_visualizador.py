# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el visualizador web de Análisis Financiero,
para Chile y para Perú (un solo build y un solo template.html, parametrizados
por país -- unificado el 2026-09-21; antes Perú tenía una copia completa de
los dos archivos y ya había divergido una vez, 2026-08-31).

Las hojas "Indicadores"/"Clientes" de Análisis de Proyectos.xlsx son 100%
formulas que analisis_financiero.py reescribe en cada corrida -- openpyxl
nunca las calcula, asi que su valor cacheado queda obsoleto justo despues de
guardar. Este script NUNCA lee esas celdas: toma las columnas manuales de
"Proyectos" y la hoja "Detalle Costos Reales" (100% valores) y le pide cada
KPI a analisis_financiero.calcular_kpis_proyecto() / calcular_clientes() --
la misma implementación que usan los reportes PDF. Aquí solo se traduce el
resultado a las claves cortas del snapshot y se agrega lo que depende de
toda la cartera (peso en cartera, cobertura, totales).

Ver docs/specs/2026-07-23-analisis-financiero-visualizador-web-
design.md para el diseno original.
"""

import base64
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Sistema"))
import analisis_financiero as af  # noqa: E402

import esquemas  # noqa: E402  (Sistema Intercambio, en sys.path desde analisis_financiero)

RAIZ = Path(__file__).resolve().parent  # Sistema Analisis Financiero/Visualizador Web/

# Candado (2026-10-05): los datos van cifrados con la contraseña de los tableros.
sys.path.insert(0, str(RAIZ.parents[1] / "Visualizador Web"))
import candado  # noqa: E402
RUTA_TEMPLATE = RAIZ / "template.html"
# Pestaña «Ingresar datos» (2026-10-02): su lógica vive en ingreso.js (probada
# con Node) y valida cada envío con el mismo esquemas.js del catálogo del
# Intercambio -- el original, no una copia. Los dos se insertan en el tablero.
RUTA_INGRESO_JS = RAIZ / "ingreso.js"
RUTA_ESQUEMAS_JS = af.pf.RAIZ_SISTEMA_INTERCAMBIO / "esquemas.js"

# Rutas de Chile como constantes de módulo (los tests las reemplazan con
# monkeypatch); las de Perú viven en PAISES_VIZ["PE"].
RUTA_EXCEL = af.RUTA_EXCEL
RUTA_DATA_JSON = RAIZ / "data" / "analisis-financiero.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"
RAIZ_REPORTES = af.RAIZ_DATOS / "Reportes"

URL_PLANILLA_PENDIENTE = (
    "https://quempinspa2020.sharepoint.com/:x:/r/_layouts/15/Doc.aspx"
    "?sourcedoc=%7BB2E1D086-F77F-4668-9CC8-39E0836CD0F5%7D"
    "&file=An%C3%A1lisis%20de%20Proyectos%202026.xlsx"
    "&action=default&mobileredirect=true"
)

_RAIZ_VIZ_PERU = af.PAISES["PE"]["raiz_visualizador_web"]
# Lo único que cambia entre países. "nav_activo" es la subruta publicada del
# tablero (la pestaña que se marca activa en la navegación entre tableros).
PAISES_VIZ = {
    "CL": {
        "titulo": "Análisis Financiero",
        "moneda": {"simbolo": "$", "locale": "es-CL"},
        "nav_activo": "analisis-financiero",
        "url_planilla": URL_PLANILLA_PENDIENTE,
        # Solo Chile: el buzón del Intercambio lo atiende el Análisis
        # Financiero de Chile (Perú no tiene intercambio).
        "ingreso": True,
    },
    "PE": {
        "titulo": "Análisis Financiero Perú",
        "moneda": {"simbolo": "S/", "locale": "es-PE"},
        "nav_activo": "analisis-financiero-peru",
        # Perú no tiene todavía un link de SharePoint para su planilla.
        "url_planilla": None,
        "ruta_excel": af.PAISES["PE"]["ruta_excel_af"],
        "ruta_data_json": _RAIZ_VIZ_PERU / "data" / "analisis-financiero-peru.json",
        "ruta_build_html": _RAIZ_VIZ_PERU / "build" / "index.html",
        "raiz_reportes": _RAIZ_VIZ_PERU.parent / "Reportes",
    },
}


def _rutas(pais: str) -> dict:
    """Rutas de entrada/salida del país -- las de Chile se leen en el momento
    de las constantes de módulo, para que el monkeypatch de los tests valga."""
    if pais == "CL":
        return {
            "ruta_excel": RUTA_EXCEL, "ruta_data_json": RUTA_DATA_JSON,
            "ruta_build_html": RUTA_BUILD_HTML, "raiz_reportes": RAIZ_REPORTES,
        }
    cfg = PAISES_VIZ[pais]
    return {k: cfg[k] for k in ("ruta_excel", "ruta_data_json", "ruta_build_html", "raiz_reportes")}


# Clave corta del snapshot -> encabezado real de la hoja "Proyectos".
CLAVE_POR_ENCABEZADO = {
    "TAG proyecto": "tag",
    "Nombre del proyecto": "nombre",
    "Cliente": "cliente",
    "Categoría": "categoria",
    "% Avance": "avance",
    "Fecha de inicio": "fecha_inicio",
    "Fecha de cierre": "fecha_cierre",
    "Monto de Venta (sin IVA)": "monto_venta",
    "Costos Materiales Proyectados": "materiales_proy",
    "Costos Equipos Proyectados": "equipos_proy",
    "Mano de Obra Proyectada": "mo_proy",
    "Otros Costos Proyectados": "otros_proy",
    "Mano de Obra Real": "mo_real",
}
# Sufijo de categoría en 'Indicadores' -> clave corta del snapshot.
CLAVE_CATEGORIA = {"Materiales": "materiales", "Equipos": "equipos", "MO": "mo", "Otros": "otros"}


def _valores_por_encabezado(p: dict) -> dict:
    """El dict de claves cortas de leer_proyectos, keyed por encabezado --
    la entrada que espera af.calcular_kpis_proyecto."""
    return {encabezado: p.get(clave) for encabezado, clave in CLAVE_POR_ENCABEZADO.items()}


def leer_proyectos(ws_proyectos) -> list[dict]:
    """Lee todas las filas validas (TAG y Nombre no vacios) de 'Proyectos'
    con sus columnas manuales crudas -- solo lectura, nunca toca el Excel."""
    proyectos = []
    for fila in range(2, ws_proyectos.max_row + 1):
        valores = af.valores_fila_proyectos(ws_proyectos, fila)
        if not valores["TAG proyecto"] or not valores["Nombre del proyecto"]:
            continue
        p = {"fila": fila}
        p.update({clave: valores[encabezado] for encabezado, clave in CLAVE_POR_ENCABEZADO.items()})
        proyectos.append(p)
    return proyectos


def es_proyecto_completo(p: dict) -> bool:
    """Aplica la regla unica de completitud (af.CAMPOS_MANUALES_REQUERIDOS),
    la misma que decide si un proyecto genera reporte PDF. Ver la nota en
    analisis_financiero.py, seccion "COMPLETITUD DE UN PROYECTO"."""
    return af.tiene_datos_completos(_valores_por_encabezado(p).get)


def campos_faltantes(p: dict) -> list[str]:
    """Que le falta a un proyecto pendiente, con los nombres de columna de la
    planilla -- misma regla que es_proyecto_completo (af.campos_faltantes)."""
    return af.campos_faltantes(_valores_por_encabezado(p).get)


def es_gastos_generales(p: dict) -> bool:
    """El bucket de gastos internos nunca tiene venta (ver
    af.CATEGORIA_GASTOS_GENERALES): no es un proyecto 'pendiente de
    completar' ni cuenta en la cobertura del analisis."""
    return p["categoria"] == af.CATEGORIA_GASTOS_GENERALES


def _orden_pendiente(p: dict):
    """Primero lo que mas venta deja fuera del analisis; los que ni siquiera
    tienen venta cargada, al final. A igual venta, el que menos le falta."""
    venta = p["monto_venta"]
    return (venta is None, -(venta or 0), len(p["campos_faltantes"]), p["nombre"])


def sumar_costos_reales_por_bucket(ws_detalle, tag: str) -> dict:
    """Recomputa las 3 sumas que en 'Proyectos' son SUMIFS hacia 'Detalle
    Costos Reales' -- lee esa hoja directo (100% valores) en vez de confiar
    en el cache de la formula."""
    sumas = {"Materiales": 0.0, "Equipos": 0.0, "Otros": 0.0}
    for fila in range(2, ws_detalle.max_row + 1):
        fila_tag = ws_detalle.cell(row=fila, column=1).value
        bucket = ws_detalle.cell(row=fila, column=3).value
        total = ws_detalle.cell(row=fila, column=4).value
        if fila_tag == tag and bucket in sumas and total is not None:
            sumas[bucket] += total
    return sumas


def leer_detalle_subcategorias(ws_detalle) -> dict[str, list[dict]]:
    """Agrupa 'Detalle Costos Reales' por TAG con el detalle de subcategoria
    -- recomputa '% del Total Real del proyecto' en Python en vez de confiar
    en el valor ya escrito en la columna E, mismo principio que
    sumar_costos_reales_por_bucket (nunca fiarse de un valor cacheado del
    Excel, aunque acá sea un literal y no una fórmula)."""
    filas_por_tag: dict[str, list[dict]] = {}
    for fila in range(2, ws_detalle.max_row + 1):
        tag = ws_detalle.cell(row=fila, column=1).value
        total = ws_detalle.cell(row=fila, column=4).value
        if not tag or total is None:
            continue
        filas_por_tag.setdefault(tag, []).append({
            "subcategoria": ws_detalle.cell(row=fila, column=2).value,
            "bucket": ws_detalle.cell(row=fila, column=3).value,
            "total": total,
        })

    resultado: dict[str, list[dict]] = {}
    for tag, filas in filas_por_tag.items():
        total_proyecto = sum(f["total"] for f in filas)
        resultado[tag] = [
            dict(f, pct=(f["total"] / total_proyecto) if total_proyecto else None)
            for f in filas
        ]
    return resultado


def calcular_peso_cartera(proyectos: list[dict]) -> dict[str, float | None]:
    """Peso del proyecto en la cartera de ventas (%) -- ver
    af.calcular_peso_cartera: el denominador son TODOS los proyectos con
    venta cargada, completos o no, igual que la fórmula de Excel."""
    return af.calcular_peso_cartera({p["tag"]: p["monto_venta"] for p in proyectos})


def _fecha_str(valor):
    """Convierte un valor de celda de fecha (datetime, o ya string, o None)
    a 'DD-MM-AAAA' (pedido del usuario 2026-07-28) o None -- nunca deja
    pasar un datetime crudo hacia el JSON del snapshot (json.dump explota con
    TypeError). Solo se muestran como texto, nunca se ordena por ellas."""
    if valor is None:
        return None
    if hasattr(valor, "strftime"):
        return valor.strftime("%d-%m-%Y")
    return str(valor)


def calcular_kpis_proyecto(p: dict, costos_reales: dict, hoy: date | None = None) -> dict:
    """KPIs del proyecto para el snapshot: pide cada valor a
    af.calcular_kpis_proyecto (única implementación, compartida con el Excel
    vía test de contrato y con los reportes PDF) y lo traduce a claves
    cortas. Agrega las alertas del proyecto."""
    valores = _valores_por_encabezado(p)
    k = af.calcular_kpis_proyecto(valores, costos_reales, hoy)

    def por_categoria(prefijo, sufijo=""):
        return {corta: k[f"{prefijo}{larga}{sufijo}"] for larga, corta in CLAVE_CATEGORIA.items()}

    avance = p["avance"]
    venta = k["Monto de Venta (sin IVA)"]
    return {
        "tag": p["tag"], "nombre": p["nombre"], "cliente": p["cliente"], "avance": avance,
        "en_curso": avance is not None and avance < 1,
        "fecha_inicio": _fecha_str(p["fecha_inicio"]), "fecha_cierre": _fecha_str(p["fecha_cierre"]),
        "categoria": p["categoria"],
        "monto_venta": p["monto_venta"],
        "total_proyectado": k["Total Proyectado"],
        "total_real": k["Total Real"],
        # A la fecha: lo gastado hasta hoy contra la venta completa.
        "margen_real": k["Margen Real"],
        "margen_neto_pct": k["Margen neto %"],
        "desviacion_pct": k["Desviación % (Real vs Proyectado)"],
        # Al cierre: lo que usa la Nota (igual al real si el avance es 100%).
        "costo_estimado_cierre": k["Costo estimado al cierre"],
        "margen_estimado_cierre": k["Margen estimado al cierre"],
        "margen_estimado_cierre_pct": k["Margen estimado al cierre %"],
        "desviacion_estimada_cierre_pct": k["Desviación estimada al cierre %"],
        "margen_cierre_pct_indice": k["Margen al cierre % (escenario índice de costo)"],
        "nota": k["Nota del Proyecto"],
        "evaluacion": k["Evaluación"],
        "costos_proyectados": {
            "materiales": p["materiales_proy"], "equipos": p["equipos_proy"],
            "mo": p["mo_proy"], "otros": p["otros_proy"],
        },
        "costos_reales": {
            "materiales": k["Costos Materiales Reales"], "equipos": k["Costos Equipos Reales"],
            "mo": k["Mano de Obra Real"], "otros": k["Otros Costos Reales"],
        },
        "costo_pct_venta": por_categoria("Costo ", " % de venta"),
        "estructura_pct": por_categoria("Estructura % "),
        "desviacion_pct_categoria": por_categoria("Desviación % "),
        "ahorro_sobrecosto": por_categoria("Ahorro/Sobrecosto "),
        "ahorro_sobrecosto_total": k["Ahorro/Sobrecosto Total"],
        "margen_por_dia": k["Margen por día de ejecución"],
        "error_presupuesto_pct": k["Error del presupuesto %"],
        # Ficha del proyecto (2026-10-05): contra qué se compara el cierre y de
        # dónde salen los puntos de la Nota. Todo sale de af; el JS solo lo dibuja.
        "margen_proyectado": k["Margen Proyectado"],
        "margen_proyectado_pct": (k["Margen Proyectado"] / venta)
        if venta and k["Margen Proyectado"] is not None else None,
        # Cuánto más (o menos) margen deja el cierre que el presupuesto.
        "margen_vs_presupuesto": (k["Margen estimado al cierre"] - k["Margen Proyectado"])
        if k["Margen estimado al cierre"] is not None and k["Margen Proyectado"] is not None else None,
        "presupuesto_gastado_pct": (k["Total Real"] / k["Total Proyectado"])
        if k["Total Proyectado"] and k["Total Real"] is not None else None,
        # Escenario pesimista en pesos (el % ya viaja en margen_cierre_pct_indice).
        "costo_cierre_pesimista": af.costo_al_cierre_indice(k["Total Real"], avance),
        "nota_puntos": af.componentes_nota(k["Margen estimado al cierre %"], k["Desviación estimada al cierre %"])
        if k["Nota del Proyecto"] is not None else None,
        "alertas": af.alertas_proyecto(valores, k, hoy),
        # Para calcular_clientes: la salida completa del módulo compartido.
        "_kpis_af": k,
    }


percentil_inclusivo = af.percentil_inclusivo


def calcular_clientes(kpis_proyectos_completos: list[dict]) -> list[dict]:
    """Clientes del snapshot: af.calcular_clientes (la misma que la hoja
    'Clientes' y los reportes) traducida a claves cortas. Solo cuentan los
    proyectos completos -- un proyecto incompleto de un cliente no
    contamina sus números, como si todavia no existiera."""
    filas = af.calcular_clientes([k["_kpis_af"] for k in kpis_proyectos_completos])
    return [{
        "cliente": f["Cliente"],
        "n_proyectos": f["N° de proyectos"],
        "venta_acumulada": f["Venta acumulada (sin IVA)"],
        "margen_acumulado": f["Margen acumulado"],
        "margen_pct": f["Margen %"],
        "recurrente": f["Cliente recurrente"] == "Sí",
        "clasificacion": f["Clasificación"],
    } for f in filas]


def calcular_categorias(kpis_proyectos_completos: list[dict]) -> list[dict]:
    """Agrupa los proyectos completos por 'categoria'. Un proyecto sin
    categoria asignada cae en "Sin categoría" en vez de excluirse. El margen
    es el estimado al cierre (el mismo que usa la Nota) y el margen % se
    pondera por venta, no se promedia."""
    por_categoria: dict[str, list[dict]] = {}
    for kpi in kpis_proyectos_completos:
        categoria = kpi["categoria"] or "Sin categoría"
        por_categoria.setdefault(categoria, []).append(kpi)

    filas = []
    for categoria, kpis in por_categoria.items():
        n = len(kpis)
        venta = sum(k["monto_venta"] for k in kpis)
        margen = sum(k["margen_estimado_cierre"] for k in kpis)
        notas = [k["nota"] for k in kpis if k["nota"] is not None]
        filas.append({
            "categoria": categoria,
            "n_proyectos": n,
            "venta_total": venta,
            "margen_estimado_total": margen,
            "margen_pct": (margen / venta) if venta else None,
            "nota_promedio": (sum(notas) / len(notas)) if notas else None,
            "tags_proyectos": [k["tag"] for k in kpis],
        })
    return filas


# ── PESTAÑA «INGRESAR DATOS» (2026-10-02) ───────────────────────────────────
# Qué campos se ingresan, de qué tipo y en qué orden lo decide
# presupuestos_formulador.CAMPOS_TABLERO (el mismo que aplica los envíos); aquí
# solo se agrega cómo se rotulan en la pestaña y cuáles no se muestran.
#
# N° Requerimiento sale de la pestaña (pedido del usuario, 2026-10-05: «no
# aporta»). El canal lo sigue aceptando: lo completan los envíos del
# Formulador (`proyecto.req`) y un `datos-proyecto` que lo traiga.
FUERA_DE_LA_PESTANA = {af.pf.COLUMNA_REQ}
ROTULOS_INGRESO = {
    "% Avance": ("Avance y plazos", "% Avance"),
    "Fecha de inicio": ("Avance y plazos", "Inicio"),
    "Fecha de cierre": ("Avance y plazos", "Cierre"),
    af.pf.CLAVE_VENTA: ("Venta", "Venta sin IVA"),
    "Materiales": ("Costos proyectados", "Materiales"),
    "Equipos": ("Costos proyectados", "Equipos"),
    "Mano de Obra": ("Costos proyectados", "Mano de obra"),
    "Otros": ("Costos proyectados", "Otros"),
    "Mano de Obra Real": ("Costo real", "Mano de obra real"),
}


def _valor_para_mensaje(valor):
    """Una celda en la forma en que el tablero la muestra y la devuelve como
    'lo que se vio' (reemplaza): fechas AAAA-MM-DD, números tal cual, y un
    texto escrito a mano como texto. Nunca un datetime (no es JSON)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, bool):
        return str(valor)
    if isinstance(valor, (int, float)):
        return int(valor) if float(valor).is_integer() else valor
    return str(valor)


def datos_para_ingreso(ws_proyectos, proyectos: list[dict]) -> dict:
    """Lo que necesita la pestaña: los campos (desde CAMPOS_TABLERO), cada
    proyecto con sus valores actuales y lo que le falta para entrar al
    análisis, y lo necesario para armar y validar el mensaje sin copiar nada
    en el JavaScript."""
    columna = {nombre: idx for idx, nombre in enumerate(af.HEADERS_PROYECTOS, start=1)}
    requeridas = set(af.CAMPOS_MANUALES_REQUERIDOS)
    campos = [{
        "clave": clave, "columna": col, "tipo": tipo,
        "grupo": ROTULOS_INGRESO[clave][0], "etiqueta": ROTULOS_INGRESO[clave][1],
        "requerido": col in requeridas, "positivo": clave == af.pf.CLAVE_VENTA,
    } for clave, (col, tipo) in af.pf.CAMPOS_TABLERO.items() if clave not in FUERA_DE_LA_PESTANA]
    filas = []
    for p in proyectos:
        valores = {c["clave"]: _valor_para_mensaje(ws_proyectos.cell(row=p["fila"], column=columna[c["columna"]]).value)
                   for c in campos}
        gastos_generales = es_gastos_generales(p)
        filas.append({
            "tag": af.pf.normalizar_tag(p["tag"]), "nombre": p["nombre"], "cliente": p["cliente"],
            "categoria": p["categoria"], "gastos_generales": gastos_generales,
            "faltan": [] if gastos_generales else [c["clave"] for c in campos
                                                   if c["requerido"] and valores[c["clave"]] is None],
            "valores": valores,
        })
    paquete = esquemas.paquete()
    return {
        "generado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "esquema": af.pf.intercambio.ESQUEMA, "tipo": af.pf.TIPO_DATOS, "destino": af.pf.DESTINO,
        "herramienta": af.pf.HERRAMIENTA_TABLERO, "patron_tag": af.pf.PATRON_TAG.pattern,
        "campos": campos,
        "proyectos": filas,
        "tags": [f["tag"] for f in filas],
        # Solo lo necesario para validar el envío en el navegador.
        "esquemas": {"sobreMensaje": paquete["sobreMensaje"],
                     "mensajes": {af.pf.TIPO_DATOS: paquete["mensajes"][af.pf.TIPO_DATOS]}},
    }


def embeber_reportes_pdf(proyectos: list[dict], categorias: list[dict], raiz_reportes: Path | None = None) -> dict[str, str]:
    """Escanea <raiz_reportes>/{Proyectos,Categorías}/*.pdf y embebe en
    base64 los que existen. La ausencia de una clave en el dict devuelto ES
    la señal de "sin reporte" -- nunca se agrega una clave con valor None o
    cadena vacia. Nunca escribe ni modifica ningun PDF, solo lee."""
    raiz = raiz_reportes if raiz_reportes is not None else RAIZ_REPORTES
    reportes: dict[str, str] = {}
    if not raiz.exists():
        return reportes

    for p in proyectos:
        ruta = raiz / "Proyectos" / f"{p['tag']}.pdf"
        if ruta.exists():
            reportes[f"proyecto:{p['tag']}"] = base64.b64encode(ruta.read_bytes()).decode("ascii")

    for c in categorias:
        ruta = raiz / "Categorías" / f"{c['categoria']}.pdf"
        if ruta.exists():
            reportes[f"categoria:{c['categoria']}"] = base64.b64encode(ruta.read_bytes()).decode("ascii")

    return reportes


def extraer_datos_saneados(ruta_excel=None, pais: str = "CL", hoy: date | None = None) -> dict:
    """Arma el snapshot saneado completo: proyectos completos + sus KPIs y
    alertas, clientes (excluyendo incompletos), categorías, y la lista de
    proyectos pendientes de completar con qué les falta. `ruta_excel` es
    parametrizable para testear contra un workbook temporal, nunca el Excel
    real de la empresa."""
    rutas = _rutas(pais)
    ruta_excel = ruta_excel if ruta_excel is not None else rutas["ruta_excel"]
    cfg = PAISES_VIZ[pais]

    wb = openpyxl.load_workbook(str(ruta_excel), data_only=True)
    ws_proyectos = wb[af.HOJA_PROYECTOS]
    ws_detalle = wb[af.HOJA_DETALLE_COSTOS_REALES]

    proyectos = leer_proyectos(ws_proyectos)
    peso_cartera_por_tag = calcular_peso_cartera(proyectos)
    detalle_subcategorias_por_tag = leer_detalle_subcategorias(ws_detalle)

    completos = []
    pendientes = []
    for p in proyectos:
        if es_proyecto_completo(p):
            costos_reales = sumar_costos_reales_por_bucket(ws_detalle, p["tag"])
            kpi = calcular_kpis_proyecto(p, costos_reales, hoy)
            kpi["peso_cartera_pct"] = peso_cartera_por_tag.get(p["tag"])
            kpi["detalle_subcategorias"] = detalle_subcategorias_por_tag.get(p["tag"], [])
            completos.append(kpi)
        elif not es_gastos_generales(p):
            pendientes.append({
                "tag": p["tag"],
                "nombre": p["nombre"],
                "mensaje": f"{p['nombre']} — Falta ingresar información en 'Análisis de Proyectos'",
                "link": cfg["url_planilla"],
                "campos_faltantes": campos_faltantes(p),
                "monto_venta": p["monto_venta"],
                # Las alertas de fechas/avance valen aunque falten datos.
                "alertas": af.alertas_proyecto(_valores_por_encabezado(p), None, hoy),
            })
    pendientes.sort(key=_orden_pendiente)

    clientes = calcular_clientes(completos)
    categorias = calcular_categorias(completos)
    reportes_pdf = embeber_reportes_pdf(completos, categorias, rutas["raiz_reportes"])

    pendientes_por_cliente: dict[str, int] = {}
    for p in proyectos:
        if not es_proyecto_completo(p) and p["cliente"] and not es_gastos_generales(p):
            pendientes_por_cliente[p["cliente"]] = pendientes_por_cliente.get(p["cliente"], 0) + 1
    for c in clientes:
        c["proyectos_pendientes"] = pendientes_por_cliente.get(c["cliente"], 0)

    kpis_af_todos = [k["_kpis_af"] for k in completos]
    for k in completos:
        del k["_kpis_af"]

    n_completos = len(completos)
    venta_total = sum(k["monto_venta"] for k in completos)
    margen_estimado_total = sum(k["margen_estimado_cierre"] for k in completos)
    notas = [k["nota"] for k in completos if k["nota"] is not None]
    # Cuanto de la cartera real queda dentro del analisis: sin este dato el
    # tablero no deja ver que parte de la venta cargada puede estar afuera.
    proyectos_de_venta = [p for p in proyectos if not es_gastos_generales(p)]
    cobertura = {
        "n_proyectos": len(proyectos_de_venta),
        "n_completos": n_completos,
        "venta_cargada_total": sum(p["monto_venta"] or 0 for p in proyectos_de_venta),
        "venta_completos": venta_total,
    }
    # Análisis de cartera (fase 2): en qué se equivoca el presupuesto y de
    # cuántos clientes depende el ingreso. El sesgo mira TODOS los proyectos
    # (la función se queda con los terminados y completos); la concentración,
    # toda la venta cargada, también la de proyectos que aún no entran.
    sesgo_categorias = af.sesgo_por_categoria(kpis_af_todos)
    ventas_por_cliente: dict[str, float] = {}
    for p in proyectos_de_venta:
        if p["cliente"] and p["monto_venta"]:
            ventas_por_cliente[p["cliente"]] = ventas_por_cliente.get(p["cliente"], 0.0) + p["monto_venta"]
    concentracion = af.concentracion_cartera(ventas_por_cliente)
    n_recurrentes = sum(1 for c in clientes if c["recurrente"])
    return {
        "generado": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "pais": pais,
        "titulo": cfg["titulo"],
        "moneda": cfg["moneda"],
        "umbrales": {
            "excelente": af.UMBRAL_EXCELENTE, "bueno": af.UMBRAL_BUENO, "aprobado": af.UMBRAL_APROBADO,
            "sobrecosto_nota_cero": af.SOBRECOSTO_NOTA_CERO,
            "margen_objetivo": af.MARGEN_OBJETIVO_NOTA,
            # Pesos de la Nota: la ficha muestra sus puntos sobre 70 y sobre 30.
            "peso_rentabilidad": af.PESO_RENTABILIDAD_NOTA,
            "peso_control": af.PESO_DESVIACION_NOTA,
            "alerta_sobrecosto": af.UMBRAL_ALERTA_SOBRECOSTO,
            "alerta_costo_incompleto": af.UMBRAL_ALERTA_COSTO_INCOMPLETO,
        },
        "cobertura": cobertura,
        "kpis_proyectos": {
            "n_completos": n_completos,
            "monto_venta_total": venta_total,
            "costo_estimado_total": sum(k["costo_estimado_cierre"] for k in completos),
            "margen_estimado_total": margen_estimado_total,
            "margen_ponderado_pct": (margen_estimado_total / venta_total) if venta_total else None,
            "n_en_curso": sum(1 for k in completos if k["en_curso"]),
            "nota_promedio": (sum(notas) / len(notas)) if notas else None,
            "n_requiere_atencion": sum(1 for k in completos if k["evaluacion"] == "Requiere atención"),
            "n_con_alertas": sum(1 for k in completos if k["alertas"]),
        },
        "presupuesto": {"sesgo_categorias": sesgo_categorias},
        "concentracion": concentracion,
        "clientes_resumen": {
            "n_clientes": len(clientes),
            "n_recurrentes": n_recurrentes,
            "tasa_recompra": (n_recurrentes / len(clientes)) if clientes else None,
        },
        "proyectos": completos,
        "clientes": clientes,
        "categorias": categorias,
        "pendientes": pendientes,
        "reportes_pdf": reportes_pdf,
        # Pestaña «Ingresar datos»: None en Perú (la pestaña no aparece).
        "ingreso": datos_para_ingreso(ws_proyectos, proyectos) if cfg.get("ingreso") else None,
    }


def build(pais: str = "CL") -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    rutas = _rutas(pais)
    cfg = PAISES_VIZ[pais]
    if not rutas["ruta_excel"].exists():
        print(f"[ERROR] No existe el Excel: {rutas['ruta_excel']}")
        return 1
    if not RUTA_TEMPLATE.exists():
        print(f"[ERROR] No existe la plantilla: {RUTA_TEMPLATE}")
        return 1

    data = extraer_datos_saneados(rutas["ruta_excel"], pais=pais)

    rutas["ruta_data_json"].parent.mkdir(parents=True, exist_ok=True)
    with io.open(rutas["ruta_data_json"], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    data_json_text = json.dumps(data, ensure_ascii=False)

    with io.open(RUTA_TEMPLATE, "r", encoding="utf-8") as f:
        template = f.read()
    for marcador in ("__AF_DATA_B64__", "__AF_TITULO__", "__AF_NAV_ACTIVO__", "__AF_ESQUEMAS_JS__", "__AF_INGRESO_JS__"):
        if marcador not in template:
            print(f"[ERROR] template.html no tiene el placeholder {marcador}")
            return 1
    with io.open(RUTA_ESQUEMAS_JS, "r", encoding="utf-8") as f:
        esquemas_js = f.read()
    with io.open(RUTA_INGRESO_JS, "r", encoding="utf-8") as f:
        ingreso_js = f.read()
    # Los dos scripts van primero: el sobre cifrado (candado.incrustar) es lo
    # último que se reemplaza, así ningún texto suyo puede pasar por un marcador.
    html = (
        template.replace("__AF_ESQUEMAS_JS__", esquemas_js)
        .replace("__AF_INGRESO_JS__", ingreso_js)
        .replace("__AF_TITULO__", cfg["titulo"])
        .replace("__AF_NAV_ACTIVO__", cfg["nav_activo"])
    )
    try:
        html = candado.incrustar(html, "__AF_DATA_B64__", data_json_text)
    except (ValueError, candado.SinContrasena) as e:
        print(f"[ERROR] {e}")
        return 1

    rutas["ruta_build_html"].parent.mkdir(parents=True, exist_ok=True)
    with io.open(rutas["ruta_build_html"], "w", encoding="utf-8") as f:
        f.write(html)

    print(f"OK ({pais}) — {len(data['proyectos'])} proyecto(s) completo(s), "
          f"{len(data['pendientes'])} pendiente(s), {len(data['clientes'])} cliente(s)")
    print(f"Snapshot: {rutas['ruta_data_json']}")
    print(f"Visualizador: {rutas['ruta_build_html']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(build(sys.argv[1] if len(sys.argv) > 1 else "CL"))
