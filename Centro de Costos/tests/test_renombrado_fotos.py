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
