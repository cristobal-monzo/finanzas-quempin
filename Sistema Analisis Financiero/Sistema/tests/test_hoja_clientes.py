import analisis_financiero as af


def _preparar(tmp_path, filas_proyectos):
    """filas_proyectos: list[dict] con fila/tag/nombre/cliente -- escribe TAG,
    Nombre y Cliente en 'Proyectos' y devuelve (wb, ws_proyectos, filas_validas)."""
    ruta = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta)
    ws = wb[af.HOJA_PROYECTOS]
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1
    filas_validas = []
    for fp in filas_proyectos:
        ws.cell(row=fp["fila"], column=1, value=fp["tag"])
        ws.cell(row=fp["fila"], column=2, value=fp["nombre"])
        ws.cell(row=fp["fila"], column=col_cliente, value=fp["cliente"])
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

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.cell(row=2, column=1).value == "AGCID"
    assert ws_clientes.cell(row=2, column=2).value == "=AVERAGEIF(Proyectos!$C:$C,$A2,Proyectos!$G:$G)"
    assert ws_clientes.cell(row=2, column=3).value == "=COUNTIF(Proyectos!$C:$C,$A2)"
    assert ws_clientes.cell(row=2, column=4).value == (
        "=MAX(1,(MAXIFS(Proyectos!$E:$E,Proyectos!$C:$C,$A2)"
        "-MINIFS(Proyectos!$E:$E,Proyectos!$C:$C,$A2))/30)"
    )
    assert ws_clientes.cell(row=2, column=5).value == "=C2/(D2/12)"
    assert ws_clientes.cell(row=2, column=6).value == (
        "=SUMIF(Proyectos!$C:$C,$A2,Proyectos!$S:$S)/SUMIF(Proyectos!$C:$C,$A2,Proyectos!$G:$G)"
    )
    assert ws_clientes.cell(row=2, column=7).value == "=B2*E2*C2*F2"
    assert ws_clientes.cell(row=2, column=8).value == (
        '=IF(G2>=PERCENTILE(Clientes!$G:$G,0.67),"Clientes estratégicos",'
        'IF(G2>=PERCENTILE(Clientes!$G:$G,0.33),"Clientes potenciales","Clientes de oportunidad"))'
    )


def test_filas_sin_cliente_asignado_se_ignoran(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": None},
    ])

    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.max_row == 1


def test_regenerar_borra_filas_de_la_corrida_anterior(tmp_path):
    wb, ws, filas_validas = _preparar(tmp_path, [
        {"fila": 2, "tag": "AGCI1", "nombre": "AGCID Febrero", "cliente": "AGCID"},
    ])
    af.asegurar_hoja_clientes(wb, filas_validas, ws)
    af.asegurar_hoja_clientes(wb, filas_validas, ws)

    ws_clientes = wb[af.HOJA_CLIENTES]
    assert ws_clientes.max_row == 2
