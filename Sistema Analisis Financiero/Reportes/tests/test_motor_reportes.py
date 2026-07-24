# -*- coding: utf-8 -*-
import motor_reportes


def test_renderizar_pdf_produce_un_archivo_pdf_valido(tmp_path):
    html = "<html><body><h1>Prueba</h1></body></html>"
    destino = tmp_path / "sub" / "prueba.pdf"

    motor_reportes.renderizar_pdf(html, destino)

    assert destino.exists()
    assert destino.stat().st_size > 0
    assert destino.read_bytes()[:5] == b"%PDF-"
