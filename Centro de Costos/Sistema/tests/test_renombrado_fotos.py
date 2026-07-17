from datetime import datetime

import auditor_centro_costos as acc


def test_sanitizar_nombre_reemplaza_caracteres_invalidos():
    assert acc.sanitizar_nombre('Fandos: "Shell" *Ruta/68*') == "Fandos_Shell_Ruta_68_"


def test_sanitizar_nombre_reemplaza_espacios():
    assert acc.sanitizar_nombre("Estaciones de Servicio") == "Estaciones_de_Servicio"


def test_fecha_iso_desde_datetime():
    assert acc.fecha_iso_desde_valor(datetime(2026, 7, 15)) == "2026-07-15"


def test_fecha_iso_desde_string_dd_mm_yyyy():
    assert acc.fecha_iso_desde_valor("15/07/2026") == "2026-07-15"


def test_fecha_iso_desde_string_invalida_se_sanitiza():
    assert acc.fecha_iso_desde_valor("fecha rara") == "fecha_rara"


def test_nombre_esperado_archivo_heic_pasa_a_jpg():
    nombre = acc.nombre_esperado_archivo("UMAG-001", "Shell", "15/07/2026", ".HEIC")
    assert nombre == "UMAG-001_Shell_2026-07-15.jpg"


def test_nombre_esperado_archivo_pdf_mantiene_extension():
    nombre = acc.nombre_esperado_archivo("CFLI-002", "Beckman", datetime(2026, 1, 5), ".pdf")
    assert nombre == "CFLI-002_Beckman_2026-01-05.pdf"


def test_nombre_esperado_archivo_sin_proveedor():
    nombre = acc.nombre_esperado_archivo("GGEN-001", "", "01/01/2026", ".jpg")
    assert nombre == "GGEN-001_SinProveedor_2026-01-01.jpg"


def test_nombre_esperado_archivo_normaliza_extension_a_minusculas():
    nombre = acc.nombre_esperado_archivo("CFLI-004", "Beckman", "10/05/2026", ".PDF")
    assert nombre == "CFLI-004_Beckman_2026-05-10.pdf"


def test_construir_reconciliacion_inversa():
    reconciliacion = {
        "UMAG\\IMG_7530.HEIC": "UMAG-001",
        "UMAG\\IMG_7534.HEIC": "UMAG-002",
    }
    inversa = acc.construir_reconciliacion_inversa(reconciliacion)
    assert inversa == {
        "UMAG-001": "UMAG\\IMG_7530.HEIC",
        "UMAG-002": "UMAG\\IMG_7534.HEIC",
    }


def test_resolver_ruta_actual_usa_archivo_origen_si_esta_poblado():
    fila = {"n_ref": "UMAG-050", "archivo_origen": "UMAG\\IMG_9999.HEIC"}
    assert acc.resolver_ruta_actual(fila, {}) == "UMAG\\IMG_9999.HEIC"


def test_resolver_ruta_actual_usa_reconciliacion_si_archivo_origen_vacio():
    fila = {"n_ref": "UMAG-002", "archivo_origen": None}
    inversa = {"UMAG-002": "UMAG\\IMG_7534.HEIC"}
    # Nota: UMAG-002 vive fisicamente en UMAG/ aunque Master.Proyecto diga
    # "Gastos Generales" para esa fila (reasignacion manual) -- por eso
    # resolver_ruta_actual NUNCA debe mirar fila["proyecto"].
    assert acc.resolver_ruta_actual(fila, inversa) == "UMAG\\IMG_7534.HEIC"


def test_resolver_ruta_actual_devuelve_none_si_no_hay_dato():
    fila = {"n_ref": "UMAG-099", "archivo_origen": None}
    assert acc.resolver_ruta_actual(fila, {}) is None


def test_planificar_renombrado_fila_ya_correcto(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "UMAG-001_Shell_2026-07-15.jpg").write_bytes(b"contenido")

    fila = {
        "fila": 2, "n_ref": "UMAG-001",
        "archivo_origen": "UMAG\\UMAG-001_Shell_2026-07-15.jpg",
        "proveedor_tag": "Shell", "fecha": "15/07/2026",
    }
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "ya_correcto"
    assert item["fila"] == 2
    assert item["nombre_nuevo"] == "UMAG-001_Shell_2026-07-15.jpg"


def test_planificar_renombrado_fila_renombrar_sin_conversion(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "CFLI").mkdir()
    (tmp_path / "CFLI" / "factura_original.pdf").write_bytes(b"contenido")

    fila = {
        "fila": 5, "n_ref": "CFLI-003",
        "archivo_origen": "CFLI\\factura_original.pdf",
        "proveedor_tag": "Beckman", "fecha": "01/02/2026",
    }
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "renombrar"
    assert item["nombre_nuevo"] == "CFLI-003_Beckman_2026-02-01.pdf"
    assert item["ruta_actual"] == tmp_path / "CFLI" / "factura_original.pdf"
    assert item["ruta_nueva"] == tmp_path / "CFLI" / "CFLI-003_Beckman_2026-02-01.pdf"


def test_planificar_renombrado_fila_convertir_heic(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "IMG_9999.HEIC").write_bytes(b"contenido")

    fila = {
        "fila": 8, "n_ref": "UMAG-025",
        "archivo_origen": "UMAG\\IMG_9999.HEIC",
        "proveedor_tag": "Anwo", "fecha": "20/03/2026",
    }
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "convertir_heic"
    assert item["nombre_nuevo"] == "UMAG-025_Anwo_2026-03-20.jpg"


def test_planificar_renombrado_fila_archivo_no_existe_en_disco(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()

    fila = {
        "fila": 9, "n_ref": "UMAG-030",
        "archivo_origen": "UMAG\\NoExiste.jpg",
        "proveedor_tag": "Anwo", "fecha": "20/03/2026",
    }
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "archivo_no_encontrado"


def test_planificar_renombrado_fila_sin_ruta_resoluble(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    fila = {"fila": 10, "n_ref": "UMAG-099", "archivo_origen": None,
            "proveedor_tag": "Anwo", "fecha": "20/03/2026"}
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "archivo_no_encontrado"


def test_planificar_renombrados_procesa_varias_filas(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "a.jpg").write_bytes(b"x")
    (tmp_path / "UMAG" / "UMAG-002_Shell_2026-01-01.jpg").write_bytes(b"x")

    filas = [
        {"fila": 2, "n_ref": "UMAG-001", "archivo_origen": "UMAG\\a.jpg",
         "proveedor_tag": "Shell", "fecha": "01/01/2026"},
        {"fila": 3, "n_ref": "UMAG-002", "archivo_origen": "UMAG\\UMAG-002_Shell_2026-01-01.jpg",
         "proveedor_tag": "Shell", "fecha": "01/01/2026"},
    ]
    planes = acc.planificar_renombrados(filas, {})
    assert [p["accion"] for p in planes] == ["renombrar", "ya_correcto"]


def _crear_heic_de_prueba(ruta, color=(200, 50, 50), size=(10, 10)):
    from PIL import Image
    import pillow_heif

    img = Image.new("RGB", size, color=color)
    heif_file = pillow_heif.from_pillow(img)
    heif_file.save(str(ruta))


def test_convertir_heic_a_jpg(tmp_path):
    from PIL import Image

    origen = tmp_path / "foto.heic"
    destino = tmp_path / "foto.jpg"
    _crear_heic_de_prueba(origen, color=(200, 50, 50))

    acc.convertir_heic_a_jpg(origen, destino)

    assert destino.exists()
    with Image.open(destino) as img:
        assert img.format == "JPEG"
        assert img.size == (10, 10)


def test_ejecutar_plan_renombrado_renombra_sin_convertir(tmp_path):
    ruta_actual = tmp_path / "factura.pdf"
    ruta_actual.write_bytes(b"contenido")
    ruta_nueva = tmp_path / "CFLI-003_Beckman_2026-02-01.pdf"

    item = {"accion": "renombrar", "ruta_actual": ruta_actual, "ruta_nueva": ruta_nueva}
    ok, error = acc.ejecutar_plan_renombrado(item)

    assert ok is True
    assert error is None
    assert ruta_nueva.exists()
    assert not ruta_actual.exists()


def test_ejecutar_plan_renombrado_convierte_heic_y_borra_original(tmp_path):
    ruta_actual = tmp_path / "IMG_9999.HEIC"
    _crear_heic_de_prueba(ruta_actual)
    ruta_nueva = tmp_path / "UMAG-025_Anwo_2026-03-20.jpg"

    item = {"accion": "convertir_heic", "ruta_actual": ruta_actual, "ruta_nueva": ruta_nueva}
    ok, error = acc.ejecutar_plan_renombrado(item)

    assert ok is True
    assert error is None
    assert ruta_nueva.exists()
    assert not ruta_actual.exists()


def test_ejecutar_plan_renombrado_conversion_fallida_no_borra_original(tmp_path):
    ruta_actual = tmp_path / "corrupto.HEIC"
    ruta_actual.write_bytes(b"esto no es un heic valido")
    ruta_nueva = tmp_path / "UMAG-025_Anwo_2026-03-20.jpg"

    item = {"accion": "convertir_heic", "ruta_actual": ruta_actual, "ruta_nueva": ruta_nueva}
    ok, error = acc.ejecutar_plan_renombrado(item)

    assert ok is False
    assert error is not None
    assert ruta_actual.exists()
    assert not ruta_nueva.exists()


def test_ejecutar_plan_renombrado_ya_correcto_no_hace_nada(tmp_path):
    ruta = tmp_path / "UMAG-001_Shell_2026-07-15.jpg"
    ruta.write_bytes(b"contenido")
    item = {"accion": "ya_correcto", "ruta_actual": ruta, "ruta_nueva": ruta}
    ok, error = acc.ejecutar_plan_renombrado(item)
    assert ok is True
    assert error is None
    assert ruta.exists()


class _WsFake:
    """Reemplaza una worksheet de openpyxl para estos tests: solo soporta
    cell(row, column, value=None), que basta para lo que aplicar_renombrados usa."""

    def __init__(self):
        self.valores = {}

    def cell(self, row, column, value=None):
        clave = (row, column)
        if value is not None:
            self.valores[clave] = value
        return _CeldaFake(self, clave)


class _CeldaFake:
    def __init__(self, ws, clave):
        self._ws = ws
        self._clave = clave

    @property
    def value(self):
        return self._ws.valores.get(self._clave)

    @value.setter
    def value(self, v):
        self._ws.valores[self._clave] = v


def test_aplicar_renombrados_renombra_y_actualiza_master(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "CFLI").mkdir()
    (tmp_path / "CFLI" / "factura_original.pdf").write_bytes(b"contenido")

    ws = _WsFake()
    filas = [{"fila": 5, "n_ref": "CFLI-003", "archivo_origen": "CFLI\\factura_original.pdf",
              "proveedor_tag": "Beckman", "fecha": "01/02/2026"}]

    renombrados, advertencias = acc.aplicar_renombrados(ws, filas, {})

    assert renombrados == 1
    assert advertencias == []
    assert ws.cell(row=5, column=15).value == "CFLI\\CFLI-003_Beckman_2026-02-01.pdf"
    assert ws.cell(row=5, column=16).value is not None
    assert (tmp_path / "CFLI" / "CFLI-003_Beckman_2026-02-01.pdf").exists()


def test_aplicar_renombrados_ya_correcto_no_cuenta_ni_toca_master(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "UMAG-001_Shell_2026-07-15.jpg").write_bytes(b"contenido")

    ws = _WsFake()
    filas = [{"fila": 2, "n_ref": "UMAG-001", "archivo_origen": "UMAG\\UMAG-001_Shell_2026-07-15.jpg",
              "proveedor_tag": "Shell", "fecha": "15/07/2026"}]

    renombrados, advertencias = acc.aplicar_renombrados(ws, filas, {})

    assert renombrados == 0
    assert advertencias == []
    assert ws.cell(row=2, column=15).value is None


def test_aplicar_renombrados_archivo_no_encontrado_genera_advertencia(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()

    ws = _WsFake()
    filas = [{"fila": 3, "n_ref": "UMAG-030", "archivo_origen": "UMAG\\NoExiste.jpg",
              "proveedor_tag": "Anwo", "fecha": "20/03/2026"}]

    renombrados, advertencias = acc.aplicar_renombrados(ws, filas, {})

    assert renombrados == 0
    assert len(advertencias) == 1
    assert advertencias[0]["n_ref"] == "UMAG-030"


def test_aplicar_renombrados_conversion_fallida_genera_advertencia(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "corrupto.HEIC").write_bytes(b"no es un heic valido")

    ws = _WsFake()
    filas = [{"fila": 4, "n_ref": "UMAG-031", "archivo_origen": "UMAG\\corrupto.HEIC",
              "proveedor_tag": "Anwo", "fecha": "20/03/2026"}]

    renombrados, advertencias = acc.aplicar_renombrados(ws, filas, {})

    assert renombrados == 0
    assert len(advertencias) == 1
    assert advertencias[0]["n_ref"] == "UMAG-031"
    assert (tmp_path / "UMAG" / "corrupto.HEIC").exists()


def test_ejecutar_plan_renombrado_renombrar_fallido_retorna_error(tmp_path, monkeypatch):
    ruta_actual = tmp_path / "factura.pdf"
    ruta_actual.write_bytes(b"contenido")
    ruta_nueva = tmp_path / "CFLI-003_Beckman_2026-02-01.pdf"

    def _rename_que_falla(self, target):
        raise PermissionError("simulado: archivo bloqueado por sincronizacion")

    monkeypatch.setattr(type(ruta_actual), "rename", _rename_que_falla)

    item = {"accion": "renombrar", "ruta_actual": ruta_actual, "ruta_nueva": ruta_nueva}
    ok, error = acc.ejecutar_plan_renombrado(item)

    assert ok is False
    assert error is not None
    assert ruta_actual.exists()
    assert not ruta_nueva.exists()


def test_planificar_renombrado_fila_ruta_sin_carpeta_es_archivo_no_encontrado():
    fila = {"fila": 7, "n_ref": "UMAG-040", "archivo_origen": "archivo_sin_carpeta.jpg",
            "proveedor_tag": "Anwo", "fecha": "01/01/2026"}
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "archivo_no_encontrado"


def test_excel_esta_bloqueado_devuelve_false_si_no_existe(tmp_path):
    ruta = tmp_path / "no_existe.xlsx"
    assert acc.excel_esta_bloqueado(ruta) is False


def test_excel_esta_bloqueado_devuelve_false_si_se_puede_abrir(tmp_path):
    ruta = tmp_path / "Centro de Costos.xlsx"
    ruta.write_bytes(b"contenido")
    assert acc.excel_esta_bloqueado(ruta) is False


def test_excel_esta_bloqueado_devuelve_true_si_permission_error(tmp_path, monkeypatch):
    ruta = tmp_path / "Centro de Costos.xlsx"
    ruta.write_bytes(b"contenido")

    def _open_que_falla(*args, **kwargs):
        raise PermissionError("simulado: archivo abierto en Excel")

    monkeypatch.setattr("builtins.open", _open_que_falla)
    assert acc.excel_esta_bloqueado(ruta) is True
