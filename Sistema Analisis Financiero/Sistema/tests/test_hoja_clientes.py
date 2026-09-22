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


def test_formulas_suman_solo_proyectos_completos_desde_indicadores(tmp_path):
    """2026-09-21 (auditoría, fase 1): la hoja agrega sobre 'Indicadores'
    filtrando por Cliente Y por 'Datos completos' = Sí -- la misma regla que
    el dashboard y los reportes. Antes sumaba sobre 'Proyectos' todo lo que
    tuviera el cliente, incluidos proyectos a medio cargar (con costos pero
    sin venta, que hundían el margen del cliente)."""
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    li = af.LETRA_COL_INDICADORES

    def rango(nombre):
        return f"Indicadores!${li[nombre]}:${li[nombre]}"

    criterios = f'{rango("Cliente")},$A2,{rango("Datos completos")},"Sí"'
    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.cell(row=2, column=1).value == "AGCID"
    assert ws_clientes.cell(row=2, column=2).value == f"=COUNTIFS({criterios})"
    assert ws_clientes.cell(row=2, column=3).value == f'=SUMIFS({rango("Monto de Venta (sin IVA)")},{criterios})'
    assert ws_clientes.cell(row=2, column=4).value == f'=SUMIFS({rango("Margen estimado al cierre")},{criterios})'
    assert ws_clientes.cell(row=2, column=5).value == '=IF(C2=0,"",D2/C2)'
    assert ws_clientes.cell(row=2, column=6).value == '=IF(B2>=2,"Sí","No")'


def test_clasificacion_por_percentil_solo_entre_clientes_con_proyectos_completos(tmp_path):
    """AGGREGATE(16,6,...) = PERCENTILE.INC ignorando errores: la división
    por (N° de proyectos > 0) deja fuera del percentil a los clientes sin
    ningún proyecto completo (dan #DIV/0!, que la opción 6 ignora). Esos
    clientes quedan como 'Sin proyectos completos'. El rango es exacto
    (filas de clientes), no la columna entera: el arreglo se evalúa celda a
    celda."""
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
        {"fila": 3, "tag": "HTAL1", "nombre": "Hospital Talca", "cliente": "Hospital Talca"},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    for r in (2, 3):
        formula = ws_clientes.cell(row=r, column=7).value
        assert formula.startswith(f'=IF(B{r}=0,"{af.CLASIFICACION_SIN_PROYECTOS}",')
        assert "_xlfn.AGGREGATE(16,6,$D$2:$D$3/($B$2:$B$3>0),0.67)" in formula
        assert "_xlfn.AGGREGATE(16,6,$D$2:$D$3/($B$2:$B$3>0),0.33)" in formula
        assert "PERCENTILE(" not in formula


def test_clientes_espejo_python_cuenta_solo_completos_y_clasifica_por_margen():
    """calcular_clientes es el espejo de la hoja: mismo filtro, mismos
    agregados, misma clasificación por percentil."""
    def k(cliente, venta, margen, completo="Sí"):
        return {"Cliente": cliente, "Categoría": "Mantenimiento", "Datos completos": completo,
                "Monto de Venta (sin IVA)": venta, "Margen estimado al cierre": margen}

    filas = af.calcular_clientes([
        k("A", 100.0, 40.0), k("A", 50.0, 10.0),
        k("B", 200.0, 20.0),
        k("C", 80.0, 5.0),
        k("C", 999.0, 999.0, completo="No"),  # a medio cargar: no cuenta
    ])
    por_cliente = {f["Cliente"]: f for f in filas}
    assert list(por_cliente) == ["A", "B", "C"]
    assert por_cliente["A"]["N° de proyectos"] == 2
    assert por_cliente["A"]["Venta acumulada (sin IVA)"] == 150.0
    assert por_cliente["A"]["Margen acumulado"] == 50.0
    assert por_cliente["A"]["Margen %"] == 50.0 / 150.0
    assert por_cliente["A"]["Cliente recurrente"] == "Sí"
    assert por_cliente["C"]["N° de proyectos"] == 1
    assert por_cliente["C"]["Cliente recurrente"] == "No"
    assert por_cliente["A"]["Clasificación"] == "Clientes estratégicos"
    assert por_cliente["B"]["Clasificación"] == "Clientes potenciales"
    assert por_cliente["C"]["Clasificación"] == "Clientes de oportunidad"
    assert af.tasa_recompra(filas) == 1 / 3
    assert af.tasa_recompra([]) is None


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
