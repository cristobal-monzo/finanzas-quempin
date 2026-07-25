# -*- coding: utf-8 -*-
"""
graficos.py -- Graficos SVG puros (sin JS, sin librerias externas) para
incrustar en reportes PDF. Pensados para imprimirse via Chromium headless
(motor_reportes.renderizar_pdf), no para interaccion.
"""

import math

COLORES_POR_DEFECTO = ["#ff5100", "#000000", "#98989a", "#54565a"]


def grafico_barras_svg(
    etiquetas: list[str], valores: list[float], color: str = "#ff5100",
    colores: list[str] | None = None, opacidades: list[float] | None = None,
    ancho: int = 480, alto: int = 220,
) -> str:
    """Grafico de barras horizontal simple. valores deben ser >= 0.

    Si se pasa `colores` (misma longitud que valores), cada barra usa su
    propio color -- util para diferenciar categorias de gasto en un grafico
    comparativo (ej. Proyectado vs Real por categoria). Sin `colores`, todas
    las barras usan `color`. `opacidades` (misma longitud) permite ademas
    distinguir dentro de una misma categoria (ej. Proyectado mas translucido
    que Real) sin cambiar el color base."""
    if not etiquetas or len(etiquetas) != len(valores):
        raise ValueError("etiquetas y valores deben tener la misma longitud y no estar vacios")
    if colores is not None and len(colores) != len(valores):
        raise ValueError("colores debe tener la misma longitud que valores")
    if opacidades is not None and len(opacidades) != len(valores):
        raise ValueError("opacidades debe tener la misma longitud que valores")

    max_valor = max(valores) or 1.0
    alto_barra = alto / len(valores)
    partes = []
    for i, (etiqueta, valor) in enumerate(zip(etiquetas, valores)):
        color_barra = colores[i] if colores is not None else color
        opacidad = f' fill-opacity="{opacidades[i]}"' if opacidades is not None else ""
        y = i * alto_barra + alto_barra * 0.15
        ancho_barra = (valor / max_valor) * (ancho - 160)
        partes.append(
            f'<text x="0" y="{y + alto_barra * 0.35:.1f}" font-size="11">{etiqueta}</text>'
            f'<rect x="150" y="{y:.1f}" width="{ancho_barra:.1f}" height="{alto_barra * 0.7:.1f}" fill="{color_barra}"{opacidad}/>'
            f'<text x="{150 + ancho_barra + 6:.1f}" y="{y + alto_barra * 0.35:.1f}" font-size="11">{valor:,.0f}</text>'
        )
    return f'<svg viewBox="0 0 {ancho} {alto}" width="100%" xmlns="http://www.w3.org/2000/svg">{"".join(partes)}</svg>'


def leyenda_html(etiquetas: list[str], colores: list[str] | None = None) -> str:
    """Leyenda HTML (swatch de color + etiqueta) para acompanar un grafico
    de dona o de barras por categoria -- ninguno de los dos incluye leyenda
    propia porque son SVG puro. Se inserta junto al grafico en el
    contenido del reporte."""
    if not etiquetas:
        raise ValueError("etiquetas no puede estar vacio")
    colores = colores or COLORES_POR_DEFECTO
    items = "".join(
        f'<span class="leyenda-item"><span class="leyenda-swatch" '
        f'style="background:{colores[i % len(colores)]}"></span>{etiqueta}</span>'
        for i, etiqueta in enumerate(etiquetas)
    )
    return f'<div class="leyenda-graficos">{items}</div>'


def grafico_dona_svg(
    etiquetas: list[str], valores: list[float], colores: list[str] | None = None,
    radio: int = 80,
) -> str:
    """Grafico de dona simple via arcos SVG calculados a mano. La suma de
    valores debe ser mayor que 0."""
    if not etiquetas or len(etiquetas) != len(valores):
        raise ValueError("etiquetas y valores deben tener la misma longitud y no estar vacios")
    total = sum(valores)
    if total <= 0:
        raise ValueError("la suma de valores debe ser mayor que 0")

    colores = colores or COLORES_POR_DEFECTO
    centro = radio + 10
    tam = centro * 2
    partes = []
    angulo_acum = -90.0
    for i, valor in enumerate(valores):
        angulo = (valor / total) * 360.0
        color = colores[i % len(colores)]
        # Un unico arco SVG no puede describir un circulo completo: si un
        # segmento cubre >= ~100% del total (start == end), el comando "A"
        # degenera en una linea invisible. En ese caso dibujamos un circulo.
        if angulo >= 359.99:
            partes.append(
                f'<circle cx="{centro}" cy="{centro}" r="{radio}" fill="{color}"/>'
            )
            angulo_acum += angulo
            continue
        x1 = centro + radio * math.cos(math.radians(angulo_acum))
        y1 = centro + radio * math.sin(math.radians(angulo_acum))
        angulo_acum += angulo
        x2 = centro + radio * math.cos(math.radians(angulo_acum))
        y2 = centro + radio * math.sin(math.radians(angulo_acum))
        gran_arco = 1 if angulo > 180 else 0
        partes.append(
            f'<path d="M{centro},{centro} L{x1:.2f},{y1:.2f} '
            f'A{radio},{radio} 0 {gran_arco} 1 {x2:.2f},{y2:.2f} Z" fill="{color}"/>'
        )
    return (
        f'<svg viewBox="0 0 {tam} {tam}" width="220" height="220" xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(partes)}<circle cx="{centro}" cy="{centro}" r="{radio * 0.55:.1f}" fill="white"/></svg>'
    )
