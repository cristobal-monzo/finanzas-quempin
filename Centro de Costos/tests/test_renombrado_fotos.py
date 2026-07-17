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
