# -*- coding: utf-8 -*-
"""El enlace de SharePoint que abre una factura o boleta (documentos.py).

Lo comparten el Centro de Costos y el Cotizador Histórico, de Chile y de Perú:
estos tests fijan la regla una vez para los cuatro tableros.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "Visualizador Web"))
import documentos  # noqa: E402

BASE = ("https://quempinspa2020.sharepoint.com/Documentos%20compartidos/Centro%20de%20Costos/"
        "Facturas%20y%20Boletas/")


def test_el_enlace_abre_el_archivo_en_sharepoint(tmp_path):
    carpeta = tmp_path / "100. Obra Ejemplo"
    carpeta.mkdir()
    (carpeta / "OBRA-003_A&B_Limitada_22-10-2026.pdf").write_bytes(b"%PDF")
    enlace = documentos.enlace_documento("100. Obra Ejemplo\\OBRA-003_A&B_Limitada_22-10-2026.pdf",
                                         "CL", tmp_path)
    # Cada tramo codificado: el espacio y el "&" no rompen la dirección.
    assert enlace == BASE + "Chile/100.%20Obra%20Ejemplo/OBRA-003_A%26B_Limitada_22-10-2026.pdf"


def test_peru_apunta_a_su_carpeta(tmp_path):
    assert documentos.enlace_documento("Lima Caldera/LIMA-001.pdf", "PE", tmp_path / "no-existe") == (
        BASE + "Per%C3%BA/Lima%20Caldera/LIMA-001.pdf")


def test_sin_el_archivo_en_la_carpeta_no_hay_enlace(tmp_path):
    # La carpeta del proyecto cambió de nombre después del run: el enlace
    # abriría un «no encontrado».
    assert documentos.enlace_documento("Obra Renombrada\\OBRA-001.jpeg", "CL", tmp_path) is None
    assert documentos.enlace_documento(None, "CL", tmp_path) is None
    assert documentos.enlace_documento("", "CL", tmp_path) is None
    assert documentos.enlace_documento("\\", "CL", tmp_path) is None


def test_sin_la_carpeta_en_este_equipo_el_enlace_va_igual(tmp_path):
    assert documentos.enlace_documento("UMAG\\UMAG-001.pdf", "CL", tmp_path / "no-existe") == (
        BASE + "Chile/UMAG/UMAG-001.pdf")


def test_la_carpeta_es_la_del_acceso_directo_del_centro_de_costos():
    sitio = RAIZ / "Centro de Costos" / "Sitio de comunicación - Centro de Costos 1" / "Facturas y Boletas"
    assert documentos.raiz_docs("CL") == sitio / "Chile"
    assert documentos.raiz_docs("PE") == sitio / "Perú"
