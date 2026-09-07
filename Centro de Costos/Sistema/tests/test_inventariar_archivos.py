import auditor_centro_costos as acc


def _crear(raiz, proyecto, nombre, contenido=b"x"):
    carpeta = raiz / proyecto
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_bytes(contenido)


def test_clasifica_pendiente_si_no_esta_en_archivos_registrados(tmp_path):
    _crear(tmp_path, "UMAG", "factura.jpg")

    pendientes, omitidos = acc.inventariar_archivos(tmp_path, archivos_registrados=set())

    assert len(pendientes) == 1
    assert omitidos == []
    assert pendientes[0]["archivo"] == "factura.jpg"
    assert pendientes[0]["proyecto"] == "UMAG"
    assert pendientes[0]["ruta_relativa"] == "UMAG\\factura.jpg"


def test_clasifica_omitido_si_ya_esta_en_archivos_registrados(tmp_path):
    _crear(tmp_path, "UMAG", "factura.jpg")

    pendientes, omitidos = acc.inventariar_archivos(
        tmp_path, archivos_registrados={"UMAG\\factura.jpg"}
    )

    assert pendientes == []
    assert len(omitidos) == 1
    assert omitidos[0]["archivo"] == "factura.jpg"


def test_ignora_extensiones_no_validas_y_desktop_ini(tmp_path):
    _crear(tmp_path, "UMAG", "factura.jpg")
    _crear(tmp_path, "UMAG", "notas.txt")
    _crear(tmp_path, "UMAG", "desktop.ini")
    _crear(tmp_path, "UMAG", "resumen.html")

    pendientes, omitidos = acc.inventariar_archivos(tmp_path, archivos_registrados=set())

    assert [p["archivo"] for p in pendientes] == ["factura.jpg"]
    assert omitidos == []


def test_ignora_carpetas_que_empiezan_con_guion_bajo_o_punto(tmp_path):
    _crear(tmp_path, "_Legado", "factura.jpg")
    _crear(tmp_path, ".oculta", "factura.jpg")
    _crear(tmp_path, "UMAG", "factura.jpg")

    pendientes, omitidos = acc.inventariar_archivos(tmp_path, archivos_registrados=set())

    assert [p["proyecto"] for p in pendientes] == ["UMAG"]


def test_ignora_archivos_sueltos_en_la_raiz_sin_carpeta_de_proyecto(tmp_path):
    (tmp_path / "suelto.jpg").write_bytes(b"x")
    _crear(tmp_path, "UMAG", "factura.jpg")

    pendientes, omitidos = acc.inventariar_archivos(tmp_path, archivos_registrados=set())

    assert [p["archivo"] for p in pendientes] == ["factura.jpg"]


def test_normalizar_nombre_proyecto_quita_codigo_numerico():
    assert acc.normalizar_nombre_proyecto("259. FACH 2") == "FACH2"
    assert acc.normalizar_nombre_proyecto("261. FACH 1") == "FACH1"
    assert acc.normalizar_nombre_proyecto("1234_Nombre") == "Nombre"
    assert acc.normalizar_nombre_proyecto("1234-Nombre") == "Nombre"


def test_normalizar_nombre_proyecto_sin_codigo_no_cambia():
    assert acc.normalizar_nombre_proyecto("Cesfam Limache") == "Cesfam Limache"
    assert acc.normalizar_nombre_proyecto("UMAG") == "UMAG"


def test_proyecto_mostrado_usa_nombre_normalizado_pero_ruta_usa_carpeta_fisica(tmp_path):
    _crear(tmp_path, "259. FACH 2", "factura.jpg")

    pendientes, _ = acc.inventariar_archivos(tmp_path, archivos_registrados=set())

    assert pendientes[0]["proyecto"] == "FACH2"
    assert pendientes[0]["ruta_relativa"] == "259. FACH 2\\factura.jpg"


def test_archivo_ya_registrado_con_ruta_fisica_se_omite_pese_a_nombre_normalizado(tmp_path):
    _crear(tmp_path, "259. FACH 2", "factura.jpg")

    pendientes, omitidos = acc.inventariar_archivos(
        tmp_path, archivos_registrados={"259. FACH 2\\factura.jpg"}
    )

    assert pendientes == []
    assert len(omitidos) == 1
