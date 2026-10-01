# -*- coding: utf-8 -*-
"""
panel.py -- La pagina 1 de todo reporte PDF (el panel de verificacion),
armada en Python a partir del paquete de datos.

Hasta el 2026-09-24 esta pagina la escribia el agente a mano, en HTML, una
vez por reporte: ~300 lineas de tablas y tarjetas por cada proyecto, cliente
y categoria. Dos problemas, los mismos que ya dejaron cicatriz en este repo:

- **Costo**: la pagina 1 no tiene ninguna decision editorial (el estandar
  dice "todos los KPIs de la entidad, sin seleccion"), asi que era trabajo
  deterministico pagado como redaccion -- con 20 entidades pendientes, 20
  veces el mismo HTML escrito de nuevo.
- **Divergencia**: dos reportes escritos en sesiones distintas no quedaban
  iguales (mismo KPI con otro formato, una tabla con una fila de menos). Es
  el mismo patron del KPI "Nota del Proyecto" (2026-07-28) y de la taxonomia
  duplicada en JavaScript (2026-09-08): dos caminos que calculan lo mismo
  terminan divergiendo.

Lo que sigue siendo del agente es la pagina 2 -- el analisis -- que es donde
hay juicio. Este modulo solo la envuelve (`pagina_analisis`).
"""

import html
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
if str(RAIZ.parent / "Sistema") not in sys.path:
    sys.path.insert(0, str(RAIZ.parent / "Sistema"))

import brand  # noqa: E402
import graficos  # noqa: E402
from analisis_financiero import (  # noqa: E402
    CATEGORIAS_KPI, NOMBRE_LEGIBLE_CATEGORIA,
)
from datos_reportes import proyecto_esta_en_desarrollo  # noqa: E402

COLOR_CATEGORIA = {
    "Materiales": graficos.COLORES_POR_DEFECTO[0],
    "Equipos": graficos.COLORES_POR_DEFECTO[1],
    "MO": graficos.COLORES_POR_DEFECTO[2],
    "Otros": graficos.COLORES_POR_DEFECTO[3],
}

# `data-una-pagina`: motor_reportes reduce esta pagina con zoom si no cabe en
# su hoja. Su alto depende de datos -- cuantas alertas trae, si los chips de
# la ficha saltan de linea -- y sin eso bastaron 2 alertas y un nombre largo
# (HPIN, 2026-09-24) para que la tabla de indicadores se fuera sola a una
# tercera hoja. La pagina 2 NO lleva la marca: si el analisis se pasa de
# largo se acorta el texto, no se achica la letra.
APERTURA_PAGINA_1 = '<div class="pdf-pagina p1" data-una-pagina>'

# Los 28 indicadores del playbook, agrupados por la pregunta que responden y
# repartidos en 2 columnas. La agrupacion NO es seleccion editorial: el
# contrato (tests/test_panel.py) exige que estos bloques cubran exactamente
# los indicadores que devuelve kpis_recalculados.recalcular_proyecto, ni uno
# mas ni uno menos. En una sola columna no caben junto a los graficos.
BLOQUES_INDICADORES = (
    (1, "Resultado a la fecha", (
        "Margen neto %",
        "Desviación % Total",
        "Ahorro/Sobrecosto Total",
        "Margen por día de ejecución",
    )),
    (2, "Proyección al cierre", (
        "Costo estimado al cierre",
        "Margen estimado al cierre",
        "Margen estimado al cierre %",
        "Desviación estimada al cierre %",
        "Margen al cierre % (escenario índice de costo)",
        "Nota del Proyecto",
        "Evaluación",
    )),
    (1, "Presupuesto por categoría", (
        "Desviación % Materiales",
        "Desviación % Equipos",
        "Desviación % MO",
        "Desviación % Otros",
        "Error del presupuesto %",
        "Ahorro/Sobrecosto Materiales",
        "Ahorro/Sobrecosto Equipos",
        "Ahorro/Sobrecosto MO",
        "Ahorro/Sobrecosto Otros",
    )),
    (2, "Estructura del costo real", (
        "Costo Materiales % de venta",
        "Costo Equipos % de venta",
        "Costo MO % de venta",
        "Costo Otros % de venta",
        "Estructura % Materiales",
        "Estructura % Equipos",
        "Estructura % MO",
        "Estructura % Otros",
    )),
)


def _t(valor) -> str:
    """Texto de una celda, escapado. Los nombres de proyecto/cliente salen
    del Excel: un "&" o un "<" escrito a mano romperia el HTML."""
    return html.escape("" if valor is None else str(valor))


def fecha_legible(valor) -> str:
    """DD-MM-AAAA, el formato fijo de todo dato visible del repo."""
    if isinstance(valor, datetime):
        valor = valor.date()
    if isinstance(valor, date):
        return valor.strftime("%d-%m-%Y")
    return _t(valor)


def _chips(items: list[tuple[str, str]], destacado: tuple[str, str] | None = None) -> str:
    partes = [
        f'<span class="chip">{_t(etiqueta)} <strong>{_t(valor)}</strong></span>'
        for etiqueta, valor in items if valor not in (None, "")
    ]
    if destacado:
        clase, texto = destacado
        partes.insert(0, f'<span class="chip {clase}">{_t(texto)}</span>')
    return f'<div class="chips">{"".join(partes)}</div>'


def _ficha(titulo: str, items, destacado=None) -> str:
    return (
        f'<div class="ficha"><h2>{_t(titulo)}</h2>{_chips(items, destacado)}</div>'
    )


def _tarjeta(etiqueta: str, valor: str, contexto: str = "", estado: str = "") -> str:
    clase = f"kpi-tarjeta estado-{estado}" if estado else "kpi-tarjeta"
    linea = f'<div class="contexto">{_t(contexto)}</div>' if contexto else ""
    return (
        f'<div class="{clase}"><div class="valor">{_t(valor)}</div>'
        f'<div class="etiqueta">{_t(etiqueta)}</div>{linea}</div>'
    )


def _fila_tarjetas(tarjetas: list[str]) -> str:
    return f'<div class="kpi-fila">{"".join(tarjetas)}</div>'


def _alertas_html(alertas: list[str]) -> str:
    """Las alertas de analisis_financiero.alertas_proyecto. Vacio si no hay
    -- una caja "sin alertas" gasta el espacio que necesita la tabla."""
    if not alertas:
        return ""
    items = "".join(f"<li>{_t(a)}</li>" for a in alertas)
    return (
        f'<div class="alertas"><h3>Alertas de datos y de presupuesto</h3>'
        f"<ul>{items}</ul></div>"
    )


def _tabla(encabezados: list[str], filas: list[list[tuple[str, str]]]) -> str:
    """Tabla estandar del reporte. Cada celda es (texto, clase_css)."""
    ths = "".join(f"<th>{_t(h)}</th>" for h in encabezados)
    trs = []
    for fila in filas:
        tds = "".join(
            f'<td class="{clase}">{_t(texto)}</td>' if clase else f"<td>{_t(texto)}</td>"
            for texto, clase in fila
        )
        trs.append(f"<tr>{tds}</tr>")
    return (
        f'<table class="tabla-reporte"><tr>{ths}</tr>{"".join(trs)}</table>'
    )


def _fila_kpi(nombre: str, valor) -> list[tuple[str, str]]:
    estado = brand.estado_kpi(nombre, valor)
    clase = f"estado-{estado}" if estado else ""
    return [
        (nombre, ""),
        (brand.formatear_kpi(nombre, valor), clase),
        (brand.referencia_kpi(nombre), "referencia"),
    ]


def tabla_indicadores(indicadores: dict) -> str:
    """Los indicadores completos de la entidad, en 2 columnas y agrupados por
    bloque. Cada valor lleva el color de brand.estado_kpi."""
    columnas = []
    for n_columna in (1, 2):
        filas = []
        for columna, titulo, nombres in BLOQUES_INDICADORES:
            if columna != n_columna:
                continue
            filas.append([(titulo, "bloque")])
            filas.extend(_fila_kpi(nombre, indicadores.get(nombre)) for nombre in nombres)
        cuerpo = []
        for fila in filas:
            if len(fila) == 1:
                cuerpo.append(f'<tr class="bloque"><th colspan="3">{_t(fila[0][0])}</th></tr>')
                continue
            tds = "".join(
                f'<td class="{clase}">{_t(texto)}</td>' if clase else f"<td>{_t(texto)}</td>"
                for texto, clase in fila
            )
            cuerpo.append(f"<tr>{tds}</tr>")
        columnas.append(f'<table class="tabla-reporte">{"".join(cuerpo)}</table>')
    return f'<div class="tabla-kpis-2col">{"".join(columnas)}</div>'


def _costos(fuente: dict) -> tuple[list[str], list[float], list[float], list[str]]:
    """(etiquetas, proyectados, reales, colores) de las 4 categorias de
    gasto, leidas de un dict de proyecto (o de una suma de proyectos)."""
    etiquetas, proyectados, reales, colores = [], [], [], []
    for sufijo, col_p, col_r in CATEGORIAS_KPI:
        etiquetas.append(NOMBRE_LEGIBLE_CATEGORIA[sufijo])
        proyectados.append(fuente.get(col_p) or 0.0)
        reales.append(fuente.get(col_r) or 0.0)
        colores.append(COLOR_CATEGORIA[sufijo])
    return etiquetas, proyectados, reales, colores


def _grafico_presupuesto(fuente: dict, alto_por_categoria: int = 62) -> str:
    etiquetas, proyectados, reales, colores = _costos(fuente)
    if min(proyectados + reales) < 0 or max(proyectados + reales) == 0:
        return '<p class="leyenda-nota">Sin costos cargados para graficar.</p>'
    return (
        '<h3>Presupuesto vs. gasto real por categoría</h3>'
        + graficos.grafico_barras_comparativo_svg(
            etiquetas, proyectados, reales, colores=colores,
            alto_por_categoria=alto_por_categoria, moneda=True,
        )
        + '<p class="leyenda-nota">Achurado = Proyectado · Sólido = Real.</p>'
    )


def _grafico_composicion(fuente: dict) -> str:
    etiquetas, _, reales, colores = _costos(fuente)
    visibles = [(e, v, c) for e, v, c in zip(etiquetas, reales, colores) if v > 0]
    if not visibles:
        return '<p class="leyenda-nota">Sin costos reales registrados.</p>'
    return (
        "<h3>Composición del costo real</h3>"
        '<div class="dona-con-leyenda">'
        + graficos.grafico_dona_svg(
            [e for e, _, _ in visibles], [v for _, v, _ in visibles],
            colores=[c for _, _, c in visibles], radio=62, mostrar_porcentaje=True,
        )
        + graficos.leyenda_html(
            [e for e, _, _ in visibles], [c for _, _, c in visibles],
        )
        + "</div>"
    )


def _pct(valor, defecto: str = "—") -> str:
    return defecto if valor is None else brand.formatear_porcentaje(valor)


def _moneda(valor, defecto: str = "—") -> str:
    return defecto if valor is None else brand.formatear_moneda(valor)


# ── PANEL DE UN PROYECTO ────────────────────────────────────────────────────

def _panel_proyecto(paquete: dict) -> str:
    proyecto, indicadores = paquete["proyecto"], paquete["indicadores"]
    contexto = paquete.get("_contexto", {})
    avance = proyecto.get("% Avance")
    en_desarrollo = paquete.get("en_desarrollo")

    ficha = _ficha(
        proyecto.get("Nombre del proyecto") or paquete["tag"],
        [
            ("TAG", paquete["tag"]),
            ("Cliente", proyecto.get("Cliente")),
            ("Categoría", proyecto.get("Categoría")),
            ("Avance", _pct(avance)),
            ("Inicio", fecha_legible(proyecto.get("Fecha de inicio"))),
            ("Cierre", fecha_legible(proyecto.get("Fecha de cierre")) or "sin fecha"),
        ],
        destacado=(
            ("chip--abierto", "EN DESARROLLO") if en_desarrollo
            else ("chip--cerrado", "CERRADO")
        ),
    )

    nota = indicadores.get("Nota del Proyecto")
    margen_cierre = indicadores.get("Margen estimado al cierre %")
    desviacion_cierre = indicadores.get("Desviación estimada al cierre %")
    peso = (contexto.get("peso_cartera") or {}).get(paquete["tag"])
    mediana = contexto.get("margen_mediano")

    tarjetas = _fila_tarjetas([
        _tarjeta(
            "Nota del Proyecto", brand.formatear_kpi("Nota del Proyecto", nota),
            contexto=_t(indicadores.get("Evaluación") or "sin avance cargado"),
            estado=brand.estado_kpi("Nota del Proyecto", nota),
        ),
        _tarjeta(
            "Margen estimado al cierre", _pct(margen_cierre),
            contexto=(
                f"Objetivo {brand.OBJETIVO_MARGEN_NETO:.0%}"
                + (f" · mediana cartera {_pct(mediana)}" if mediana is not None else "")
            ),
            estado=brand.estado_kpi("Margen estimado al cierre %", margen_cierre),
        ),
        _tarjeta(
            "Desviación estimada al cierre", _pct(desviacion_cierre),
            contexto=f"Presupuesto {_moneda(proyecto.get('Total Proyectado'))}",
            estado=brand.estado_kpi("Desviación estimada al cierre %", desviacion_cierre),
        ),
        _tarjeta(
            "Monto de Venta (sin IVA)", _moneda(proyecto.get("Monto de Venta (sin IVA)")),
            contexto=(f"{_pct(peso)} de la venta de la cartera" if peso is not None else ""),
        ),
    ])

    datos_clave = _tabla(
        ["Concepto", "Monto"],
        [
            [("Monto de Venta (sin IVA)", ""), (_moneda(proyecto.get("Monto de Venta (sin IVA)")), "")],
            [("Costo presupuestado", ""), (_moneda(proyecto.get("Total Proyectado")), "")],
            [("Costo real a la fecha", ""), (_moneda(proyecto.get("Total Real")), "")],
            [("Costo estimado al cierre", ""), (_moneda(indicadores.get("Costo estimado al cierre")), "")],
            [("Margen estimado al cierre", ""), (_moneda(indicadores.get("Margen estimado al cierre")), "")],
        ],
    )

    return (
        APERTURA_PAGINA_1
        + ficha
        + tarjetas
        + _alertas_html(paquete.get("alertas") or [])
        + '<div class="fila-2-col">'
        + f"<div>{_grafico_presupuesto(proyecto)}<h3>Datos clave</h3>{datos_clave}</div>"
        + f"<div>{_grafico_composicion(proyecto)}</div>"
        + "</div>"
        + "<h3>Indicadores completos del playbook</h3>"
        + tabla_indicadores(indicadores)
        + "</div>"
    )


# ── PANEL DE UN CLIENTE / DE UNA CATEGORIA ──────────────────────────────────

def agregar_costos(proyectos: list[dict]) -> dict:
    """Suma las columnas de costo (proyectado y real) de varios proyectos,
    para graficar un cliente o una categoria con los mismos graficos que un
    proyecto solo."""
    suma: dict[str, float] = {}
    for _, col_p, col_r in CATEGORIAS_KPI:
        for col in (col_p, col_r):
            suma[col] = sum(p.get(col) or 0.0 for p in proyectos)
    return suma


def _tabla_proyectos(proyectos: list[dict]) -> str:
    clase = lambda nombre, valor: (  # noqa: E731
        f"estado-{brand.estado_kpi(nombre, valor)}" if brand.estado_kpi(nombre, valor) else ""
    )
    filas = []
    for p in sorted(proyectos, key=lambda x: -(x.get("Monto de Venta (sin IVA)") or 0)):
        nota = p.get("Nota del Proyecto")
        margen = p.get("Margen estimado al cierre %")
        filas.append([
            (p.get("TAG proyecto"), ""),
            (p.get("Nombre del proyecto"), ""),
            (_pct(p.get("% Avance")), ""),
            (_moneda(p.get("Monto de Venta (sin IVA)")), ""),
            (_moneda(p.get("Margen estimado al cierre")), ""),
            (_pct(margen), clase("Margen estimado al cierre %", margen)),
            (brand.formatear_kpi("Nota del Proyecto", nota), clase("Nota del Proyecto", nota)),
        ])
    return _tabla(
        ["TAG", "Proyecto", "Avance", "Venta", "Margen al cierre", "Margen %", "Nota"],
        filas,
    )


def _indicadores_agregados(proyectos: list[dict], venta: float, margen: float) -> dict:
    """Los mismos indicadores del playbook, calculados sobre la suma de los
    proyectos de un cliente o una categoria: cada KPI es la razon de las
    sumas (ponderado por tamaño), nunca el promedio simple de los KPIs de
    cada proyecto -- un proyecto de $200.000 no pesa lo mismo que uno de
    $14 millones."""
    costos = agregar_costos(proyectos)
    total_proyectado = sum(costos[col_p] for _, col_p, _ in CATEGORIAS_KPI)
    total_real = sum(costos[col_r] for _, _, col_r in CATEGORIAS_KPI)
    dividir = lambda a, b: (a / b if b else None)  # noqa: E731
    desviacion = lambda real, proy: (real / proy - 1 if proy else None)  # noqa: E731

    indicadores = {
        "Margen neto %": dividir(venta - total_real, venta),
        "Desviación % Total": desviacion(total_real, total_proyectado),
        "Ahorro/Sobrecosto Total": total_proyectado - total_real,
        "Margen por día de ejecución": None,
        "Costo estimado al cierre": sum(p.get("Costo estimado al cierre") or 0.0 for p in proyectos),
        "Margen estimado al cierre": margen,
        "Margen estimado al cierre %": dividir(margen, venta),
        "Desviación estimada al cierre %": None,
        "Margen al cierre % (escenario índice de costo)": None,
        "Nota del Proyecto": None,
        "Evaluación": None,
        "Error del presupuesto %": dividir(
            sum(abs(costos[col_r] - costos[col_p]) for _, col_p, col_r in CATEGORIAS_KPI),
            total_proyectado,
        ),
    }
    costo_estimado = indicadores["Costo estimado al cierre"]
    if total_proyectado:
        indicadores["Desviación estimada al cierre %"] = costo_estimado / total_proyectado - 1
    for sufijo, col_p, col_r in CATEGORIAS_KPI:
        real, proyectado = costos[col_r], costos[col_p]
        indicadores[f"Desviación % {sufijo}"] = desviacion(real, proyectado)
        indicadores[f"Ahorro/Sobrecosto {sufijo}"] = proyectado - real
        indicadores[f"Costo {sufijo} % de venta"] = dividir(real, venta)
        indicadores[f"Estructura % {sufijo}"] = dividir(real, total_real)
    return indicadores


def _panel_agregado(titulo: str, chips: list[tuple[str, str]], tarjetas: list[str],
                    proyectos: list[dict], venta: float, margen: float) -> str:
    costos = agregar_costos(proyectos)
    return (
        APERTURA_PAGINA_1
        + _ficha(titulo, chips)
        + _fila_tarjetas(tarjetas)
        + '<div class="fila-2-col">'
        + f"<div>{_grafico_presupuesto(costos, alto_por_categoria=58)}</div>"
        + f"<div>{_grafico_composicion(costos)}</div>"
        + "</div>"
        + "<h3>Proyectos considerados (solo los de datos completos)</h3>"
        + _tabla_proyectos(proyectos)
        + "<h3>Indicadores completos del playbook (ponderados por venta)</h3>"
        + tabla_indicadores(_indicadores_agregados(proyectos, venta, margen))
        + "</div>"
    )


def _panel_cliente(paquete: dict) -> str:
    kpis, proyectos = paquete["kpis_cliente"], paquete["proyectos"]
    contexto = paquete.get("_contexto", {})
    venta = kpis.get("Venta acumulada (sin IVA)") or sum(
        p.get("Monto de Venta (sin IVA)") or 0.0 for p in proyectos
    )
    margen = kpis.get("Margen acumulado") or 0.0
    participacion = next(
        (r["parte"] for r in (contexto.get("concentracion") or {}).get("ranking", [])
         if r["cliente"] == paquete["cliente"]),
        None,
    )
    margen_pct = kpis.get("Margen %")

    tarjetas = [
        _tarjeta("Venta acumulada (sin IVA)", _moneda(venta),
                 contexto=(f"{_pct(participacion)} de la venta de la cartera"
                           if participacion is not None else "")),
        _tarjeta("Margen acumulado (al cierre)", _moneda(margen)),
        _tarjeta("Margen %", _pct(margen_pct),
                 contexto=f"Objetivo {brand.OBJETIVO_MARGEN_NETO:.0%}",
                 estado=brand.estado_kpi("Margen estimado al cierre %", margen_pct)),
        _tarjeta("Clasificación", kpis.get("Clasificación") or "—",
                 contexto=f"{kpis.get('N° de proyectos') or len(proyectos)} proyecto(s) completos"),
    ]
    return _panel_agregado(
        paquete["cliente"],
        [
            ("Proyectos completos", str(kpis.get("N° de proyectos") or len(proyectos))),
            ("Cliente recurrente", kpis.get("Cliente recurrente")),
            ("Clasificación", kpis.get("Clasificación")),
        ],
        tarjetas, proyectos, venta, margen,
    )


def _panel_categoria(paquete: dict) -> str:
    proyectos = paquete["proyectos"]
    contexto = paquete.get("_contexto", {})
    venta = sum(p.get("Monto de Venta (sin IVA)") or 0.0 for p in proyectos)
    margen = sum(p.get("Margen estimado al cierre") or 0.0 for p in proyectos)
    margen_pct = (margen / venta) if venta else None
    notas = [p.get("Nota del Proyecto") for p in proyectos if p.get("Nota del Proyecto") is not None]
    nota_promedio = (sum(notas) / len(notas)) if notas else None
    clientes = sorted({p.get("Cliente") for p in proyectos if p.get("Cliente")})
    venta_total = contexto.get("venta_total")

    tarjetas = [
        _tarjeta("Venta de la categoría", _moneda(venta),
                 contexto=(f"{_pct(venta / venta_total)} de la venta de la cartera"
                           if venta_total else "")),
        _tarjeta("Margen acumulado (al cierre)", _moneda(margen)),
        _tarjeta("Margen % ponderado", _pct(margen_pct),
                 contexto=f"Objetivo {brand.OBJETIVO_MARGEN_NETO:.0%}",
                 estado=brand.estado_kpi("Margen estimado al cierre %", margen_pct)),
        _tarjeta("Nota promedio", brand.formatear_kpi("Nota del Proyecto", nota_promedio),
                 contexto=f"{len(proyectos)} proyecto(s) · {len(clientes)} cliente(s)",
                 estado=brand.estado_kpi("Nota del Proyecto", nota_promedio)),
    ]
    return _panel_agregado(
        paquete["categoria"],
        [
            ("Proyectos completos", str(len(proyectos))),
            ("Clientes", ", ".join(clientes)),
        ],
        tarjetas, proyectos, venta, margen,
    )


_PANEL_POR_TIPO = {
    "proyecto": _panel_proyecto,
    "cliente": _panel_cliente,
    "categoria": _panel_categoria,
}


def panel(paquete: dict) -> str:
    """Pagina 1 completa (un `<div class="pdf-pagina p1" ...>`) para un paquete
    de datos de proyecto, cliente o categoria."""
    constructor = _PANEL_POR_TIPO.get(paquete.get("tipo"))
    if constructor is None:
        raise ValueError(
            f"No hay panel definido para el tipo '{paquete.get('tipo')}'. "
            f"La comparacion ad-hoc no tiene layout de 2 paginas definido "
            f"(ver Gotchas del SKILL.md)."
        )
    return constructor(paquete)


def pagina_analisis(titulo: str, generado_el: str, cuerpo_html: str) -> str:
    """Pagina 2: envuelve el analisis redactado por el agente. Repite el
    encabezado con marca (el PDF impreso lleva identificacion en todas sus
    paginas fisicas) para que el agente no tenga que acordarse."""
    return (
        f'<div class="pdf-pagina p2">{brand.encabezado_html(titulo, generado_el)}'
        f"{cuerpo_html}</div>"
    )


def titulo_reporte(paquete: dict) -> str:
    tipo = paquete.get("tipo")
    if tipo == "proyecto":
        nombre = paquete["proyecto"].get("Nombre del proyecto") or paquete["tag"]
        return f"Proyecto {nombre}"
    if tipo == "cliente":
        return f"Cliente {paquete['cliente']}"
    if tipo == "categoria":
        return f"Categoría {paquete['categoria']}"
    raise ValueError(f"Tipo de entidad sin titulo definido: '{tipo}'.")


def fecha_corte(paquete: dict, hoy: date | None = None) -> str | None:
    """Fecha de cierre real de los datos que muestra el reporte: la mas
    reciente entre los proyectos que lo componen. None si ninguno esta
    cerrado. Un cierre futuro no cuenta: es un proyecto en desarrollo (la
    regla de proyecto_esta_en_desarrollo), y "Datos al 03-03-2027" en un
    reporte de hoy no es una fecha de corte."""
    if paquete.get("tipo") == "proyecto":
        proyectos = [paquete["proyecto"]]
    else:
        proyectos = paquete.get("proyectos") or []
    fechas = []
    for p in proyectos:
        if proyecto_esta_en_desarrollo(p, hoy):
            continue
        valor = p["Fecha de cierre"]
        fechas.append(valor.date() if isinstance(valor, datetime) else valor)
    return max(fechas).strftime("%d-%m-%Y") if fechas else None


def documento(paquete: dict, narrativa_html: str, generado_el: str) -> str:
    """El reporte completo: pagina 1 (esta, deterministica) + pagina 2 (el
    analisis del agente), con la marca QUEMPIN alrededor."""
    titulo = titulo_reporte(paquete)
    return brand.construir_html(
        titulo, generado_el,
        panel(paquete) + pagina_analisis(titulo, generado_el, narrativa_html),
        fecha_corte=fecha_corte(paquete),
    )
