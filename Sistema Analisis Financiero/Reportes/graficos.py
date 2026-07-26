# -*- coding: utf-8 -*-
"""
graficos.py -- Graficos SVG puros (sin JS, sin librerias externas) para
incrustar en reportes PDF. Pensados para imprimirse via Chromium headless
(motor_reportes.renderizar_pdf), no para interaccion.
"""

import math
import uuid

COLORES_POR_DEFECTO = ["#ff5100", "#000000", "#98989a", "#54565a"]


def grafico_barras_svg(
    etiquetas: list[str], valores: list[float], color: str = "#ff5100",
    colores: list[str] | None = None, opacidades: list[float] | None = None,
    ancho: int = 480, alto: int = 220, ancho_etiqueta: int = 150,
    margen_valor: int = 76, decimales: int = 0, sufijo: str = "",
) -> str:
    """Grafico de barras horizontal simple. valores deben ser >= 0.

    Si se pasa `colores` (misma longitud que valores), cada barra usa su
    propio color -- util para diferenciar categorias de gasto en un grafico
    comparativo (ej. Proyectado vs Real por categoria). Sin `colores`, todas
    las barras usan `color`. `opacidades` (misma longitud) permite ademas
    distinguir dentro de una misma categoria (ej. Proyectado mas translucido
    que Real) sin cambiar el color base.

    `margen_valor` reserva un espacio fijo a la derecha (en unidades del
    viewBox) para que el numero de la barra mas larga (la del 100% de
    `max_valor`) siempre quede completo dentro del grafico -- sin este
    margen, esa barra llega justo al borde y el texto del valor se corta.
    `decimales`/`sufijo` controlan el formato del valor mostrado (ej.
    decimales=1, sufijo="%" para porcentajes chicos donde ".0f" pierde
    precision perceptible, como 2,3% redondeado a 2%)."""
    if not etiquetas or len(etiquetas) != len(valores):
        raise ValueError("etiquetas y valores deben tener la misma longitud y no estar vacios")
    if colores is not None and len(colores) != len(valores):
        raise ValueError("colores debe tener la misma longitud que valores")
    if opacidades is not None and len(opacidades) != len(valores):
        raise ValueError("opacidades debe tener la misma longitud que valores")

    max_valor = max(valores) or 1.0
    alto_barra = alto / len(valores)
    ancho_disponible = ancho - ancho_etiqueta - margen_valor
    partes = []
    for i, (etiqueta, valor) in enumerate(zip(etiquetas, valores)):
        color_barra = colores[i] if colores is not None else color
        opacidad = f' fill-opacity="{opacidades[i]}"' if opacidades is not None else ""
        y = i * alto_barra + alto_barra * 0.15
        ancho_barra = (valor / max_valor) * ancho_disponible
        texto_valor = f"{valor:,.{decimales}f}{sufijo}"
        partes.append(
            f'<text x="0" y="{y + alto_barra * 0.35:.1f}" font-size="11">{etiqueta}</text>'
            f'<rect x="{ancho_etiqueta}" y="{y:.1f}" width="{ancho_barra:.1f}" height="{alto_barra * 0.7:.1f}" fill="{color_barra}"{opacidad}/>'
            f'<text x="{ancho_etiqueta + ancho_barra + 6:.1f}" y="{y + alto_barra * 0.35:.1f}" font-size="11" font-weight="700">{texto_valor}</text>'
        )
    return f'<svg viewBox="0 0 {ancho} {alto}" width="100%" xmlns="http://www.w3.org/2000/svg">{"".join(partes)}</svg>'


def grafico_barras_comparativo_svg(
    categorias: list[str], valores_proyectado: list[float], valores_real: list[float],
    colores: list[str] | None = None, ancho: int = 540, alto_por_categoria: int = 70,
    ancho_etiqueta: int = 130, margen_valor: int = 90, decimales: int = 0, sufijo: str = "",
) -> str:
    """Grafico de barras horizontal agrupado por categoria, para comparar
    Proyectado vs Real (ej. costos por categoria de gasto). Reemplaza la
    variante de `grafico_barras_svg` con `opacidades` -- en la practica esa
    variante costaba distinguir a simple vista que barra era de que
    categoria (mismo tono, solo mas claro/oscuro). Aca cada categoria es un
    grupo: nombre de la categoria una sola vez (no repetido en cada barra),
    Proyectado con relleno achurado (patron diagonal) y Real con relleno
    solido -- mismo color de categoria en ambas -- mas una banda de fondo
    tenue agrupando el par, un acento vertical y un cuadro de color junto
    al nombre (mismo color que las barras del grupo, para que la categoria
    se identifique aun mas rapido que solo por el color de la barra) y una
    linea separadora entre categorias."""
    if not categorias or len(categorias) != len(valores_proyectado) or len(categorias) != len(valores_real):
        raise ValueError(
            "categorias, valores_proyectado y valores_real deben tener la misma longitud y no estar vacios"
        )
    colores = colores or COLORES_POR_DEFECTO
    max_valor = max(max(valores_proyectado), max(valores_real)) or 1.0
    ancho_disponible = ancho - ancho_etiqueta - margen_valor
    alto = alto_por_categoria * len(categorias)
    alto_barra = alto_por_categoria * 0.28

    prefijo_id = f"hatch{uuid.uuid4().hex[:8]}"
    defs, partes = [], []
    for i, categoria in enumerate(categorias):
        color = colores[i % len(colores)]
        pattern_id = f"{prefijo_id}-{i}"
        defs.append(
            f'<pattern id="{pattern_id}" width="6" height="6" patternTransform="rotate(45)" '
            f'patternUnits="userSpaceOnUse">'
            f'<rect width="6" height="6" fill="white"/>'
            f'<line x1="0" y1="0" x2="0" y2="6" stroke="{color}" stroke-width="3"/>'
            f'</pattern>'
        )
        y0 = i * alto_por_categoria
        if i % 2 == 1:
            partes.append(
                f'<rect x="0" y="{y0:.1f}" width="{ancho}" height="{alto_por_categoria:.1f}" '
                f'fill="{color}" fill-opacity="0.06"/>'
            )
        # Acento vertical (mismo color del grupo) + cuadro de color junto al
        # nombre -- la categoria se identifica por color incluso antes de
        # mirar las barras, no solo por el achurado/relleno solido.
        partes.append(
            f'<rect x="0" y="{y0 + 2:.1f}" width="3" height="{alto_por_categoria - 4:.1f}" fill="{color}"/>'
            f'<rect x="9" y="{y0 + 5:.1f}" width="10" height="10" fill="{color}"/>'
            f'<text x="25" y="{y0 + 15:.1f}" font-size="12" font-weight="700">{categoria}</text>'
        )

        y_proy = y0 + 21
        ancho_proy = (valores_proyectado[i] / max_valor) * ancho_disponible
        texto_proy = f"{valores_proyectado[i]:,.{decimales}f}{sufijo}"
        partes.append(
            f'<text x="0" y="{y_proy + alto_barra * 0.7:.1f}" font-size="9.5" fill="#54565a">Proyectado</text>'
            f'<rect x="{ancho_etiqueta}" y="{y_proy:.1f}" width="{ancho_proy:.1f}" height="{alto_barra:.1f}" '
            f'fill="url(#{pattern_id})" stroke="{color}" stroke-width="1"/>'
            f'<text x="{ancho_etiqueta + ancho_proy + 6:.1f}" y="{y_proy + alto_barra * 0.7:.1f}" '
            f'font-size="10.5" font-weight="700">{texto_proy}</text>'
        )

        y_real = y_proy + alto_barra + 5
        ancho_real = (valores_real[i] / max_valor) * ancho_disponible
        texto_real = f"{valores_real[i]:,.{decimales}f}{sufijo}"
        partes.append(
            f'<text x="0" y="{y_real + alto_barra * 0.7:.1f}" font-size="9.5" fill="#54565a">Real</text>'
            f'<rect x="{ancho_etiqueta}" y="{y_real:.1f}" width="{ancho_real:.1f}" height="{alto_barra:.1f}" fill="{color}"/>'
            f'<text x="{ancho_etiqueta + ancho_real + 6:.1f}" y="{y_real + alto_barra * 0.7:.1f}" '
            f'font-size="10.5" font-weight="700">{texto_real}</text>'
        )

        if i < len(categorias) - 1:
            y_sep = y0 + alto_por_categoria - 1
            partes.append(f'<line x1="0" y1="{y_sep:.1f}" x2="{ancho}" y2="{y_sep:.1f}" stroke="#e2e2e2" stroke-width="1"/>')

    return (
        f'<svg viewBox="0 0 {ancho} {alto}" width="100%" xmlns="http://www.w3.org/2000/svg">'
        f'<defs>{"".join(defs)}</defs>{"".join(partes)}</svg>'
    )


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
    radio: int = 80, mostrar_porcentaje: bool = False,
) -> str:
    """Grafico de dona simple via arcos SVG calculados a mano. La suma de
    valores debe ser mayor que 0. Con `mostrar_porcentaje=True`, cada
    segmento con al menos ~6% del total lleva su porcentaje como texto
    encima del arco (segmentos mas chicos no alcanzan a mostrar el numero
    sin solaparse)."""
    if not etiquetas or len(etiquetas) != len(valores):
        raise ValueError("etiquetas y valores deben tener la misma longitud y no estar vacios")
    total = sum(valores)
    if total <= 0:
        raise ValueError("la suma de valores debe ser mayor que 0")

    colores = colores or COLORES_POR_DEFECTO
    centro = radio + 10
    tam = centro * 2
    radio_texto = radio * 0.75
    partes = []
    angulo_acum = -90.0
    for i, valor in enumerate(valores):
        angulo = (valor / total) * 360.0
        color = colores[i % len(colores)]
        angulo_medio = angulo_acum + angulo / 2
        # Un unico arco SVG no puede describir un circulo completo: si un
        # segmento cubre >= ~100% del total (start == end), el comando "A"
        # degenera en una linea invisible. En ese caso dibujamos un circulo.
        if angulo >= 359.99:
            partes.append(
                f'<circle cx="{centro}" cy="{centro}" r="{radio}" fill="{color}"/>'
            )
            if mostrar_porcentaje:
                partes.append(
                    f'<text x="{centro}" y="{centro - radio_texto:.1f}" font-size="11" '
                    f'fill="white" text-anchor="middle">100%</text>'
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
        if mostrar_porcentaje and angulo / 360.0 >= 0.06:
            tx = centro + radio_texto * math.cos(math.radians(angulo_medio))
            ty = centro + radio_texto * math.sin(math.radians(angulo_medio))
            partes.append(
                f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="11" fill="white" '
                f'text-anchor="middle" dominant-baseline="middle">{angulo / 360.0 * 100:.0f}%</text>'
            )
    return (
        f'<svg viewBox="0 0 {tam} {tam}" width="220" height="220" xmlns="http://www.w3.org/2000/svg">'
        f'{"".join(partes)}<circle cx="{centro}" cy="{centro}" r="{radio * 0.55:.1f}" fill="white"/></svg>'
    )
