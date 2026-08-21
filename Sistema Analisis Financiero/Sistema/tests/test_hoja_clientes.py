import analisis_financiero as af


def _preparar(tmp_path, filas_proyectos):
    """filas_proyectos: list[dict] con fila/tag/nombre/cliente (+ 'categoria'
    opcional) -- escribe TAG, Nombre, Cliente y Categoría en 'Proyectos' y
    devuelve (wb, ws_proyectos, filas_validas)."""
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)
    ws = wb[af.HOJA_PROYECTOS]
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1
    col_categoria = af.HEADERS_PROYECTOS.index("Categoría") + 1
    filas_validas = []
    for fp in filas_proyectos:
        ws.cell(row=fp["fila"], column=1, value=fp["tag"])
        ws.cell(row=fp["fila"], column=2, value=fp["nombre"])
        ws.cell(row=fp["fila"], column=col_cliente, value=fp["cliente"])
        ws.cell(row=fp["fila"], column=col_categoria, value=fp.get("categoria"))
        filas_validas.append({"fila": fp["fila"], "tag": fp["tag"], "nombre": fp["nombre"]})
    return wb, ws, filas_validas


def test_una_fila_por_cliente_unico(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
        {"fila": 3, "tag": "HTAL1", "nombre": "Hospital Talca Mayo", "cliente": "Hospital Talca"},
        {"fila": 4, "tag": "HTAL2", "nombre": "Hospital Talca Dic", "cliente": "Hospital Talca"},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    valores_cliente = [ws_clientes.cell(row=r, column=1).value for r in (2, 3)]
    assert sorted(valores_cliente) == ["AGCID", "Hospital Talca"]


def test_formulas_agregan_sobre_proyectos_filtrando_por_columna_cliente(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    l = af.LETRA_COL_PROYECTOS
    cliente_col = l["Cliente"]
    venta_col = l["Monto de Venta (sin IVA)"]
    fecha_inicio_col = l["Fecha de inicio"]
    margen_real_col = l["Margen Real"]

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.cell(row=2, column=1).value == "AGCID"
    assert ws_clientes.cell(row=2, column=2).value == (
        f"=AVERAGEIF(Proyectos!${cliente_col}:${cliente_col},$A2,"
        f"Proyectos!${venta_col}:${venta_col})"
    )
    assert ws_clientes.cell(row=2, column=3).value == (
        f"=COUNTIF(Proyectos!${cliente_col}:${cliente_col},$A2)"
    )
    assert ws_clientes.cell(row=2, column=4).value == (
        f"=MAX(12,(_xlfn.MAXIFS(Proyectos!${fecha_inicio_col}:${fecha_inicio_col},"
        f"Proyectos!${cliente_col}:${cliente_col},$A2)"
        f"-_xlfn.MINIFS(Proyectos!${fecha_inicio_col}:${fecha_inicio_col},"
        f"Proyectos!${cliente_col}:${cliente_col},$A2))/30)"
    )
    assert ws_clientes.cell(row=2, column=5).value == "=C2/(D2/12)"
    assert ws_clientes.cell(row=2, column=6).value == (
        f"=SUMIF(Proyectos!${cliente_col}:${cliente_col},$A2,Proyectos!${margen_real_col}:${margen_real_col})"
        f"/SUMIF(Proyectos!${cliente_col}:${cliente_col},$A2,Proyectos!${venta_col}:${venta_col})"
    )
    assert ws_clientes.cell(row=2, column=7).value == "=B2*E2*C2*F2"
    assert ws_clientes.cell(row=2, column=8).value == (
        '=IF(G2>=_xlfn.AGGREGATE(16,6,Clientes!$G:$G,0.67),"Clientes estratégicos",'
        'IF(G2>=_xlfn.AGGREGATE(16,6,Clientes!$G:$G,0.33),"Clientes potenciales","Clientes de oportunidad"))'
    )


def test_clasificacion_ignora_errores_de_otros_clientes_en_el_percentil(tmp_path):
    """Un cliente con proyectos sin Monto de Venta aun cargado produce
    #DIV/0! en su propia columna G (CLTV) -- eso no debe romper la
    Clasificacion de los demas clientes. PERCENTILE(rango) de Excel devuelve
    error si CUALQUIER celda del rango es un error; AGGREGATE(16,6,...)
    tiene la opcion 6 ("ignorar valores de error") para evitar justamente
    esa propagacion."""
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
        {"fila": 3, "tag": "GGEN1", "nombre": "Gastos Generales", "cliente": "Gastos Generales"},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    for r in (2, 3):
        formula = ws_clientes.cell(row=r, column=8).value
        assert "_xlfn.AGGREGATE(16,6,Clientes!$G:$G,0.67)" in formula
        assert "_xlfn.AGGREGATE(16,6,Clientes!$G:$G,0.33)" in formula
        assert "PERCENTILE(" not in formula


def test_filas_sin_cliente_asignado_se_ignoran(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": None},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.max_row == 1


def test_categoria_gastos_generales_no_aparece_como_cliente(tmp_path):
    """2026-08-20: 'Gastos Generales' es un bucket de costos internos de
    Centro de Costos, no una venta a un cliente real -- no debe aparecer
    como pseudo-cliente en 'Clientes' aunque tenga un valor de 'Cliente'
    cargado (que hoy coincide con el nombre de la categoría)."""
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID",
         "categoria": "I+D+i"},
        {"fila": 3, "tag": "GGEN", "nombre": "Gastos Generales", "cliente": "Gastos Generales",
         "categoria": af.CATEGORIA_GASTOS_GENERALES},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    valores_cliente = [
        ws_clientes.cell(row=r, column=1).value for r in range(2, ws_clientes.max_row + 1)
    ]
    assert valores_cliente == ["AGCID"]


def test_regenerar_borra_filas_de_la_corrida_anterior(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
    ])
    af.asegurar_hoja_clientes(wb, filas_validas, ws)
    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.max_row == 2
