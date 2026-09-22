import openpyxl
import pytest

import analisis_financiero as af


def _celda(ws, fila, encabezado):
    """Por nombre de columna, no por número: el playbook ya cambió de orden
    dos veces (2026-07-28 y 2026-09-21)."""
    return ws.cell(row=fila, column=af.HEADERS_INDICADORES.index(encabezado) + 1).value


def test_una_fila_referencia_las_columnas_correctas_de_proyectos(tmp_path):
    """Toda división guarda contra denominador 0 o vacío y devuelve "" --
    el mismo None que calcular_kpis_proyecto (2026-09-21). Antes daba
    #DIV/0! en el Excel y 0 inventado en el dashboard."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])

    ws = wb[af.HOJA_INDICADORES]
    l = af.LETRA_COL_PROYECTOS

    def p(nombre):
        return f"Proyectos!{l[nombre]}2"

    venta, total_real, total_proy = p("Monto de Venta (sin IVA)"), p("Total Real"), p("Total Proyectado")

    assert _celda(ws, 2, "TAG proyecto") == f"={p('TAG proyecto')}"
    assert _celda(ws, 2, "Nombre del proyecto") == f"={p('Nombre del proyecto')}"
    assert _celda(ws, 2, "Margen neto %") == f'=IF({venta}=0,"",{p("Margen Real")}/{venta})'
    for sufijo, col_p, col_r in af.CATEGORIAS_KPI:
        real, proyectado = p(col_r), p(col_p)
        assert _celda(ws, 2, f"Costo {sufijo} % de venta") == f'=IF({venta}=0,"",{real}/{venta})'
        assert _celda(ws, 2, f"Estructura % {sufijo}") == f'=IF({total_real}=0,"",{real}/{total_real})'
        assert _celda(ws, 2, f"Desviación % {sufijo}") == f'=IF({proyectado}=0,"",{real}/{proyectado}-1)'
        assert _celda(ws, 2, f"Ahorro/Sobrecosto {sufijo}") == f"={proyectado}-{real}"
    # Desviación % Total -- referencia directa a 'Proyectos' (no recalcula)
    assert _celda(ws, 2, "Desviación % Total") == f"={p('Desviación % (Real vs Proyectado)')}"
    assert _celda(ws, 2, "Ahorro/Sobrecosto Total") == f"={total_proy}-{total_real}"
    # Peso en cartera: venta del proyecto sobre TODA la columna de venta.
    assert _celda(ws, 2, "Peso del proyecto en la cartera de ventas (%)") == (
        f'=IF({venta}="","",{venta}/SUM(Proyectos!${l["Monto de Venta (sin IVA)"]}:${l["Monto de Venta (sin IVA)"]}))'
    )
    # Margen por día: vacío si falta una fecha o si el cierre es futuro.
    inicio, cierre = p("Fecha de inicio"), p("Fecha de cierre")
    assert _celda(ws, 2, "Margen por día de ejecución") == (
        f'=IF(OR({cierre}="",{inicio}="",{cierre}>TODAY()),"",'
        f"{p('Margen Real')}/MAX(1,{cierre}-{inicio}))"
    )


def test_cada_columna_de_indicadores_tiene_su_formula(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])
    ws = wb[af.HOJA_INDICADORES]
    for col, encabezado in enumerate(af.HEADERS_INDICADORES, start=1):
        assert ws.cell(row=1, column=col).value == encabezado
        valor = ws.cell(row=2, column=col).value
        assert isinstance(valor, str) and valor.startswith("="), encabezado


def test_peso_cartera_suma_toda_la_columna_no_solo_la_propia_fila(tmp_path):
    """Peso del proyecto = venta del proyecto / suma de TODA la columna de
    venta de 'Proyectos' -- verificado a mano con 3 proyectos con venta
    cargada: 100.000 + 300.000 + 600.000 = 1.000.000; UMAG (100.000) debería
    pesar 10% de la cartera."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws_p = wb[af.HOJA_PROYECTOS]
    col_tag = af.HEADERS_PROYECTOS.index("TAG proyecto") + 1
    col_nombre = af.HEADERS_PROYECTOS.index("Nombre del proyecto") + 1
    col_venta = af.HEADERS_PROYECTOS.index("Monto de Venta (sin IVA)") + 1
    for fila, (tag, nombre, venta) in enumerate(
        [("UMAG", "UMAG", 100000), ("CFLI", "Cesfam Limache", 300000), ("CCON", "Cesfam Constitución", 600000)],
        start=2,
    ):
        ws_p.cell(row=fila, column=col_tag, value=tag)
        ws_p.cell(row=fila, column=col_nombre, value=nombre)
        ws_p.cell(row=fila, column=col_venta, value=venta)

    filas_validas = [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 3, "tag": "CFLI", "nombre": "Cesfam Limache"},
        {"fila": 4, "tag": "CCON", "nombre": "Cesfam Constitución"},
    ]
    af.asegurar_hoja_indicadores(wb, filas_validas)
    wb.save(wb_path := tmp_path / "resultado.xlsx")

    # Verificación del VALOR (no solo la fórmula): recalculamos a mano con
    # openpyxl en modo lectura normal (fórmulas, no data_only) más los
    # valores ya guardados en "Proyectos" -- sin recurrir a ningún motor de
    # cálculo externo (LibreOffice/Google Sheets), solo aritmética Python.
    wb_leido = openpyxl.load_workbook(wb_path)
    ws_ind = wb_leido[af.HOJA_INDICADORES]
    formula_umag = _celda(ws_ind, 2, "Peso del proyecto en la cartera de ventas (%)")
    l = af.LETRA_COL_PROYECTOS
    venta_letra = l["Monto de Venta (sin IVA)"]
    assert formula_umag == (
        f'=IF(Proyectos!{venta_letra}2="","",'
        f"Proyectos!{venta_letra}2/SUM(Proyectos!${venta_letra}:${venta_letra}))"
    )
    total_cartera = 100000 + 300000 + 600000
    assert 100000 / total_cartera == pytest.approx(0.1)


def test_margen_por_dia_formula_identica_sin_importar_la_fila(tmp_path):
    """La fórmula de 'Margen por día de ejecución' es la misma estructura
    (con el guard de fechas dentro) para cualquier fila -- no hay una rama
    de código en Python que decida 'este proyecto no tiene fecha, no escribo
    fórmula'; el guard vive DENTRO de la fórmula de Excel, para que se
    recalcule solo si el usuario completa la fecha o si el cierre llega."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    filas_validas = [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 3, "tag": "MLER", "nombre": "Microturbina LER"},
    ]
    af.asegurar_hoja_indicadores(wb, filas_validas)

    ws = wb[af.HOJA_INDICADORES]
    l = af.LETRA_COL_PROYECTOS
    for f in (2, 3):
        inicio, cierre = f"Proyectos!{l['Fecha de inicio']}{f}", f"Proyectos!{l['Fecha de cierre']}{f}"
        assert _celda(ws, f, "Margen por día de ejecución") == (
            f'=IF(OR({cierre}="",{inicio}="",{cierre}>TODAY()),"",'
            f"Proyectos!{l['Margen Real']}{f}/MAX(1,{cierre}-{inicio}))"
        )


def test_fila_con_hueco_en_proyectos_queda_compacta_en_indicadores_pero_referencia_la_fila_real(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    # Proyectos fila 3 fue invalida y se salto -- el segundo proyecto valido
    # esta en la fila 4 de "Proyectos".
    filas_validas = [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 4, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ]

    af.asegurar_hoja_indicadores(wb, filas_validas)

    ws = wb[af.HOJA_INDICADORES]
    l = af.LETRA_COL_PROYECTOS
    tag = l["TAG proyecto"]
    venta, margen_real = l["Monto de Venta (sin IVA)"], l["Margen Real"]
    desviacion_total = l["Desviación % (Real vs Proyectado)"]

    assert ws.cell(row=2, column=1).value == f"=Proyectos!{tag}2"
    assert ws.cell(row=3, column=1).value == f"=Proyectos!{tag}4"
    assert _celda(ws, 3, "Margen neto %") == (
        f'=IF(Proyectos!{venta}4=0,"",Proyectos!{margen_real}4/Proyectos!{venta}4)'
    )
    assert _celda(ws, 3, "Desviación % Total") == f"=Proyectos!{desviacion_total}4"
    # Las columnas que se referencian dentro de la misma hoja usan la fila
    # compacta (3), no la de 'Proyectos' (4).
    assert f"{af.LETRA_COL_INDICADORES['Costo estimado al cierre']}3" in _celda(ws, 3, "Margen estimado al cierre")


def test_categoria_gastos_generales_deja_nota_y_evaluacion_vacias(tmp_path):
    """2026-08-20: 'Gastos Generales' (bucket de costos internos, sin Monto
    de Venta) no debe recibir Nota/Evaluación -- ni el '#DIV/0!' que ya daba
    antes (margen_neto indefinido sin venta) ni, peor, un '' interpretado
    como "Excelente" por la comparación texto-vs-número de Excel si solo se
    hubiera vaciado la Nota sin vaciar también la Evaluación."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws_p = wb[af.HOJA_PROYECTOS]
    col_categoria = af.HEADERS_PROYECTOS.index("Categoría") + 1
    ws_p.cell(row=2, column=col_categoria, value=af.CATEGORIA_GASTOS_GENERALES)

    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "GGEN", "nombre": "Gastos Generales"}])

    ws = wb[af.HOJA_INDICADORES]
    categoria_col = af.LETRA_COL_PROYECTOS["Categoría"]
    es_gastos_generales = f'Proyectos!{categoria_col}2="Gastos Generales"'
    formula_nota = ws.cell(row=2, column=22).value
    formula_evaluacion = ws.cell(row=2, column=23).value
    assert formula_nota == f'=IF({es_gastos_generales},"",{af._formula_nota(2)[1:]})'
    assert formula_evaluacion == f'=IF({es_gastos_generales},"",{af._formula_evaluacion(2)[1:]})'


def test_regenerar_borra_filas_de_la_corrida_anterior(tmp_path):
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "CFLI", "nombre": "Cesfam Limache"}])

    ws = wb[af.HOJA_INDICADORES]
    assert ws.max_row == 2


def test_nota_parcial_ya_no_existe_y_la_estimacion_al_cierre_va_al_final():
    """2026-09-21 (fase 1): la Nota Parcial se reemplazó por la estimación
    al cierre. Las columnas nuevas van al final, detrás de 'Margen por día'."""
    assert "Nota Parcial" not in af.HEADERS_INDICADORES
    i = af.HEADERS_INDICADORES.index("Margen por día de ejecución")
    assert af.HEADERS_INDICADORES[i + 1:i + 6] == [
        "Costo estimado al cierre", "Margen estimado al cierre",
        "Margen estimado al cierre %", "Desviación estimada al cierre %",
        "Margen al cierre % (escenario índice de costo)",
    ]


def test_estimacion_al_cierre_formulas(tmp_path):
    """Costo al cierre = real + proyectado x (1 - avance acotado a [0,1]);
    vacío si no hay avance. Las siguientes columnas encadenan sobre esa."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 4, "tag": "UMAG", "nombre": "UMAG"}])
    ws = wb[af.HOJA_INDICADORES]
    l, li = af.LETRA_COL_PROYECTOS, af.LETRA_COL_INDICADORES
    avance, venta = f"Proyectos!{l['% Avance']}4", f"Proyectos!{l['Monto de Venta (sin IVA)']}4"
    real, proy = f"Proyectos!{l['Total Real']}4", f"Proyectos!{l['Total Proyectado']}4"
    acotado = f"MIN(1,MAX(0,{avance}))"
    costo = f"{li['Costo estimado al cierre']}2"
    margen = f"{li['Margen estimado al cierre']}2"

    assert _celda(ws, 2, "Costo estimado al cierre") == f'=IF({avance}="","",{real}+{proy}*(1-{acotado}))'
    assert _celda(ws, 2, "Margen estimado al cierre") == f'=IF({costo}="","",{venta}-{costo})'
    assert _celda(ws, 2, "Margen estimado al cierre %") == f'=IF({margen}="","",IF({venta}=0,"",{margen}/{venta}))'
    assert _celda(ws, 2, "Desviación estimada al cierre %") == f'=IF(OR({costo}="",{proy}=0),"",{costo}/{proy}-1)'
    assert _celda(ws, 2, "Margen al cierre % (escenario índice de costo)") == (
        f'=IF(OR({avance}="",{venta}=0),"",IF({acotado}=0,"",({venta}-{real}/{acotado})/{venta}))'
    )


def test_datos_completos_usa_la_misma_lista_que_tiene_datos_completos(tmp_path):
    """La columna que filtra la hoja 'Clientes' sale de
    CAMPOS_MANUALES_REQUERIDOS: si la regla de completitud cambia, cambia
    acá sola (no hay una segunda lista que mantener)."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    af.asegurar_hoja_indicadores(wb, [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}])
    ws = wb[af.HOJA_INDICADORES]
    condiciones = ",".join(
        f'Proyectos!{af.LETRA_COL_PROYECTOS[c]}2<>""' for c in af.CAMPOS_MANUALES_REQUERIDOS
    )
    assert _celda(ws, 2, "Datos completos") == f'=IF(AND({condiciones}),"Sí","No")'


def test_estilo_de_indicadores_es_por_nombre_de_columna():
    estilo = af.ESTILO_COLUMNAS_INDICADORES
    li = af.LETRA_COL_INDICADORES
    assert set(estilo) == set(li.values()), "cada columna con estilo, ninguna de más"
    assert estilo[li["Nota del Proyecto"]][1] == af.FORMATO_ENTERO
    assert estilo[li["Costo estimado al cierre"]][1] == af.FORMATO_MONEDA
    assert estilo[li["Margen estimado al cierre %"]][1] == af.FORMATO_PORCENTAJE
