import json

import analisis_financiero as af


def _preparar_hoja(tmp_path, filas):
    """filas: list[(tag, nombre)] -- escribe TAG/Nombre en Proyectos y
    devuelve (wb, ws, filas_validas)."""
    ruta_excel = tmp_path / "Análisis de Proyectos.xlsx"
    wb = af.asegurar_estructura_workbook(ruta_excel)
    ws = wb[af.HOJA_PROYECTOS]
    filas_validas = []
    for i, (tag, nombre) in enumerate(filas, start=2):
        ws.cell(row=i, column=1, value=tag)
        ws.cell(row=i, column=2, value=nombre)
        filas_validas.append({"fila": i, "tag": tag, "nombre": nombre})
    return wb, ws, filas_validas


def test_deriva_y_asigna_cliente_cuando_coincide_exacto_tras_normalizar(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [
        ("HTAL1", "Hospital Talca (I) Mayo"),
        ("HTAL2", "Hospital Talca (I) Mayo Y Diciembre"),
    ])
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1

    pendientes = af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    assert ws.cell(row=2, column=col_cliente).value == "Hospital Talca"
    assert ws.cell(row=3, column=col_cliente).value == "Hospital Talca"
    assert pendientes == []
    assert not ruta_pendientes.exists()


def test_marca_pendiente_cuando_es_similar_pero_no_exacto(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [
        ("AGCI1", "AGCID Febrero"),
        ("AGCI2", "AGCID Marzo"),
    ])
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1

    pendientes = af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    assert ws.cell(row=2, column=col_cliente).value == "AGCID Febrero"
    assert len(pendientes) == 1
    assert pendientes[0]["tag"] == "AGCI2"
    assert pendientes[0]["fila"] == 3
    assert pendientes[0]["cliente_derivado"] == "AGCID Marzo"
    assert pendientes[0]["cliente_sugerido"] == "AGCID Febrero"
    assert pendientes[0]["estado"] == "Pendiente"
    assert ws.cell(row=3, column=col_cliente).value == "AGCID Febrero"
    assert ws.cell(row=3, column=col_cliente).font.color.rgb == "00C00000"

    assert ruta_pendientes.exists()
    guardado = json.loads(ruta_pendientes.read_text(encoding="utf-8"))
    assert guardado == pendientes


def test_sin_parecido_queda_como_cliente_nuevo_sin_marca(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [
        ("AGCI1", "AGCID Febrero"),
        ("BOMB1", "Bombas de Calor Puerto Montt"),
    ])
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1

    pendientes = af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    assert ws.cell(row=3, column=col_cliente).value == "Bombas de Calor Puerto Montt"
    assert pendientes == []


def test_no_toca_una_celda_cliente_ya_llena_a_mano(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [("UMAG", "UMAG (I) Enero")])
    col_cliente = af.HEADERS_PROYECTOS.index("Cliente") + 1
    ws.cell(row=2, column=col_cliente, value="Universidad de Magallanes")

    af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    assert ws.cell(row=2, column=col_cliente).value == "Universidad de Magallanes"


def test_pendientes_se_acumulan_entre_corridas(tmp_path):
    ruta_pendientes = tmp_path / "clientes_pendientes.json"
    wb, ws, filas_validas = _preparar_hoja(tmp_path, [
        ("AGCI1", "AGCID Febrero"),
        ("AGCI2", "AGCID Marzo"),
    ])
    af.asegurar_columna_cliente(ws, filas_validas, ruta_pendientes)

    wb2, ws2, filas_validas2 = _preparar_hoja(tmp_path, [
        ("AGCI1", "AGCID Febrero"),
        ("AGCI3", "AGCID Abril"),
    ])
    # Simula que "AGCID Febrero" ya quedó registrado en la columna Cliente en
    # la corrida anterior -- se pre-llena a mano para no depender de I/O real
    # de la corrida previa; la celda ya llena hace que asegurar_columna_cliente
    # la salte y la cuente como cliente existente para comparar AGCI3 contra ella.
    ws2.cell(row=2, column=af.HEADERS_PROYECTOS.index("Cliente") + 1, value="AGCID Febrero")
    af.asegurar_columna_cliente(ws2, filas_validas2, ruta_pendientes)

    guardado = json.loads(ruta_pendientes.read_text(encoding="utf-8"))
    assert len(guardado) == 2
    assert {p["tag"] for p in guardado} == {"AGCI2", "AGCI3"}
