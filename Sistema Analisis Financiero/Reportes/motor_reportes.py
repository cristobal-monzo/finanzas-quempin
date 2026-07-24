# -*- coding: utf-8 -*-
"""
motor_reportes.py -- Imprime un documento HTML autocontenido (sin recursos
externos -- CSS/fuentes/imagenes ya embebidos por brand.construir_html) a PDF
via Chromium headless (playwright). No conoce el contenido del reporte, solo
lo renderiza.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright


def renderizar_pdf(html: str, ruta_salida: Path) -> None:
    """Crea las carpetas padre de ruta_salida si no existen y escribe el PDF
    ahi. Lanza la excepcion de playwright tal cual si el render falla (sin
    capturarla) -- quien llama decide como reportarlo."""
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            pagina = navegador.new_page()
            pagina.set_content(html, wait_until="networkidle")
            pagina.pdf(
                path=str(ruta_salida),
                format="A4",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
        finally:
            navegador.close()
