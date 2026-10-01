# -*- coding: utf-8 -*-
"""
motor_reportes.py -- Imprime un documento HTML autocontenido (sin recursos
externos -- CSS/fuentes/imagenes ya embebidos por brand.construir_html) a PDF
via Chromium headless (playwright). No conoce el contenido del reporte, solo
lo renderiza.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

# A4 a 96 dpi, el mismo formato que se le pide a pagina.pdf(). Se mide con
# este ancho porque de el depende donde saltan de linea los textos.
ANCHO_A4_PX, ALTO_A4_PX = 794, 1122

# Todo elemento con `data-una-pagina` tiene que caber en la hoja donde
# empieza: si la pasa, se reduce con `zoom` (que, a diferencia de transform,
# achica tambien el espacio que ocupa) lo justo para que quepa. Nunca agranda.
# Espera las fuentes: medir con la de respaldo daria otro alto.
_JS_AJUSTAR_A_UNA_PAGINA = """async (alto) => {
  await document.fonts.ready;
  for (const el of document.querySelectorAll('[data-una-pagina]')) {
    const caja = el.getBoundingClientRect();
    const arriba = caja.top + window.scrollY;
    const limite = (Math.floor(arriba / alto) + 1) * alto - 2;
    const fondo = caja.bottom + window.scrollY;
    if (fondo > limite) el.style.zoom = (limite - arriba) / (fondo - arriba);
  }
}"""


def renderizar_pdfs(documentos: list[tuple[str, Path]]) -> None:
    """Varios documentos a PDF reutilizando un unico Chromium: levantarlo
    cuesta ~1 s, y una corrida que regenera la cartera completa son 20
    reportes. Crea las carpetas padre que falten. Lanza la excepcion de
    playwright tal cual si un render falla (sin capturarla) -- quien llama
    decide como reportarlo."""
    if not documentos:
        return
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            for html, ruta_salida in documentos:
                ruta_salida = Path(ruta_salida)
                ruta_salida.parent.mkdir(parents=True, exist_ok=True)
                pagina = navegador.new_page(viewport={"width": ANCHO_A4_PX, "height": ALTO_A4_PX})
                try:
                    pagina.emulate_media(media="print")
                    pagina.set_content(html, wait_until="networkidle")
                    pagina.evaluate(_JS_AJUSTAR_A_UNA_PAGINA, ALTO_A4_PX)
                    pagina.pdf(
                        path=str(ruta_salida),
                        format="A4",
                        print_background=True,
                        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                    )
                finally:
                    pagina.close()
        finally:
            navegador.close()


def renderizar_pdf(html: str, ruta_salida: Path) -> None:
    """Un documento HTML autocontenido a PDF."""
    renderizar_pdfs([(html, ruta_salida)])
