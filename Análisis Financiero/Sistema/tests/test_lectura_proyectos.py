import analisis_financiero as af


def _ws_proyectos_con_filas(tmp_path, filas):
    """filas: lista de tuplas (tag, nombre) o (tag, nombre) con alguno en None."""
    wb = af.asegurar_estructura_workbook(tmp_path / "Análisis de Proyectos.xlsx")
    ws = wb[af.HOJA_PROYECTOS]
    for idx, (tag, nombre) in enumerate(filas, start=2):
        ws.cell(row=idx, column=1, value=tag)
        ws.cell(row=idx, column=2, value=nombre)
    return ws


def test_lee_filas_validas_con_tag_y_nombre(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [("UMAG", "UMAG"), ("CFLI", "Cesfam Limache")])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 3, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ]
    assert avisos == []


def test_fila_sin_tag_se_salta_con_aviso(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [(None, "Proyecto sin tag"), ("UMAG", "UMAG")])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == [{"fila": 3, "tag": "UMAG", "nombre": "UMAG"}]
    assert len(avisos) == 1
    assert "Fila 2" in avisos[0]


def test_fila_sin_nombre_se_salta_con_aviso(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [("UMAG", None)])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == []
    assert len(avisos) == 1


def test_tag_duplicado_usa_la_primera_fila_y_avisa_de_la_segunda(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [("UMAG", "UMAG"), ("UMAG", "UMAG duplicado")])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == [{"fila": 2, "tag": "UMAG", "nombre": "UMAG"}]
    assert len(avisos) == 1
    assert "duplicado" in avisos[0]


def test_hoja_sin_filas_de_datos_no_produce_avisos(tmp_path):
    ws = _ws_proyectos_con_filas(tmp_path, [])
    filas_validas, avisos = af.leer_filas_proyectos(ws)
    assert filas_validas == []
    assert avisos == []
