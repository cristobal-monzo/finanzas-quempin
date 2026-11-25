"""recortar_documento_combinado(): un archivo con varias facturas -> un archivo
por factura, cada uno solo con su recorte (pedido del usuario, 2026-11-25)."""
import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, NameObject,
                           NumberObject)

import auditor_centro_costos as acc


def _carpeta(tmp_path):
    raiz = tmp_path / "docs"
    (raiz / "UMAG").mkdir(parents=True)
    return raiz, tmp_path / "backups"


def _pdf_con_dos_facturas(ruta, rotacion=0):
    """Una pagina carta (612x792) con 'FACTURA 111' arriba y 'FACTURA 222' abajo."""
    escritor = PdfWriter()
    pagina = escritor.add_blank_page(612, 792)
    fuente = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    pagina[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): escritor._add_object(fuente)}),
    })
    contenido = DecodedStreamObject()
    contenido.set_data(b"BT /F1 24 Tf 100 600 Td (FACTURA 111) Tj ET "
                       b"BT /F1 24 Tf 100 200 Td (FACTURA 222) Tj ET")
    pagina[NameObject("/Contents")] = escritor._add_object(contenido)
    if rotacion:
        pagina[NameObject("/Rotate")] = NumberObject(rotacion)
    with open(ruta, "wb") as f:
        escritor.write(f)


def test_interpretar_recorte():
    assert acc.interpretar_recorte("2:0,0.5,1,1") == {"pagina": 2, "caja": (0, 0.5, 1, 1)}
    assert acc.interpretar_recorte("0,0,0.5,1") == {"pagina": 1, "caja": (0, 0, 0.5, 1)}
    assert acc.interpretar_recorte("3") == {"pagina": 3, "caja": (0, 0, 1, 1)}
    for malo in ("", "1:0,0,1", "1:0.5,0,0.4,1", "1:0,0,1.2,1", "0:0,0,1,1", "abc"):
        with pytest.raises(ValueError):
            acc.interpretar_recorte(malo)


def test_recorta_foto_en_dos_y_borra_el_original(tmp_path):
    raiz, backups = _carpeta(tmp_path)
    img = Image.new("RGB", (1000, 800), "white")
    img.paste((255, 0, 0), (0, 0, 1000, 400))      # factura de arriba: roja
    img.paste((0, 0, 255), (0, 400, 1000, 800))    # factura de abajo: azul
    img.save(raiz / "UMAG" / "IMG_1.png")

    destinos = acc.recortar_documento_combinado(
        "UMAG", "IMG_1.png", ["1:0,0,1,0.5", "1:0,0.5,1,1"], raiz_docs=raiz, ruta_backups=backups)

    assert [d.name for d in destinos] == ["IMG_1_1.png", "IMG_1_2.png"]
    arriba, abajo = (Image.open(d) for d in destinos)
    assert arriba.size == (1000, 400) and abajo.size == (1000, 400)
    assert arriba.getpixel((500, 200)) == (255, 0, 0)
    assert abajo.getpixel((500, 200)) == (0, 0, 255)
    assert not (raiz / "UMAG" / "IMG_1.png").exists()
    assert len(list(backups.rglob("IMG_1 - documento combinado - backup *.png"))) == 1


def test_recorta_pdf_conservando_el_texto(tmp_path):
    raiz, backups = _carpeta(tmp_path)
    _pdf_con_dos_facturas(raiz / "UMAG" / "Facturas.pdf")

    destinos = acc.recortar_documento_combinado(
        "UMAG", "Facturas.pdf", ["1:0,0,1,0.5", "1:0,0.5,1,1"], raiz_docs=raiz, ruta_backups=backups)

    arriba, abajo = (PdfReader(str(d)).pages[0] for d in destinos)
    assert [float(v) for v in arriba.cropbox] == [0, 396, 612, 792]
    assert [float(v) for v in abajo.cropbox] == [0, 0, 612, 396]
    # Dos recortes de la misma pagina no comparten la caja.
    assert float(arriba.mediabox.bottom) == 396 and float(abajo.mediabox.top) == 396
    assert "FACTURA 111" in arriba.extract_text()
    assert not (raiz / "UMAG" / "Facturas.pdf").exists()


def test_pdf_girado_se_recorta_como_se_ve(tmp_path):
    raiz, backups = _carpeta(tmp_path)
    _pdf_con_dos_facturas(raiz / "UMAG" / "Girado.pdf", rotacion=90)

    destinos = acc.recortar_documento_combinado(
        "UMAG", "Girado.pdf", ["1:0,0,0.5,1", "1:0.5,0,1,1"], raiz_docs=raiz, ruta_backups=backups)

    # Visto girado 90°, la pagina mide 792 de ancho y 612 de alto: cada mitad 396x612, derecha.
    for d in destinos:
        pagina = PdfReader(str(d)).pages[0]
        assert pagina.rotation == 0
        assert (round(float(pagina.cropbox.width)), round(float(pagina.cropbox.height))) == (396, 612)


def test_pdf_con_una_factura_por_pagina(tmp_path):
    raiz, backups = _carpeta(tmp_path)
    escritor = PdfWriter()
    escritor.add_blank_page(612, 792)
    escritor.add_blank_page(300, 400)
    with open(raiz / "UMAG" / "Dos.pdf", "wb") as f:
        escritor.write(f)

    destinos = acc.recortar_documento_combinado(
        "UMAG", "Dos.pdf", ["1", "2"], raiz_docs=raiz, ruta_backups=backups)

    paginas = [PdfReader(str(d)).pages for d in destinos]
    assert [len(p) for p in paginas] == [1, 1]
    assert float(paginas[1][0].mediabox.width) == 300


def test_heic_sale_como_jpg(tmp_path):
    pillow_heif = pytest.importorskip("pillow_heif")
    pillow_heif.register_heif_opener()
    raiz, backups = _carpeta(tmp_path)
    Image.new("RGB", (400, 200), "white").save(raiz / "UMAG" / "IMG_2.heic", format="HEIF")

    destinos = acc.recortar_documento_combinado(
        "UMAG", "IMG_2.heic", ["0,0,0.5,1", "0.5,0,1,1"], raiz_docs=raiz, ruta_backups=backups)

    assert [d.name for d in destinos] == ["IMG_2_1.jpg", "IMG_2_2.jpg"]
    assert Image.open(destinos[0]).size == (200, 200)


def test_pagina_inexistente_no_toca_nada(tmp_path):
    raiz, backups = _carpeta(tmp_path)
    _pdf_con_dos_facturas(raiz / "UMAG" / "Facturas.pdf")

    with pytest.raises(ValueError):
        acc.recortar_documento_combinado(
            "UMAG", "Facturas.pdf", ["1", "2"], raiz_docs=raiz, ruta_backups=backups)

    assert sorted(p.name for p in (raiz / "UMAG").iterdir()) == ["Facturas.pdf"]
    assert not backups.exists()


def test_un_solo_recorte_o_destino_existente_falla(tmp_path):
    raiz, backups = _carpeta(tmp_path)
    Image.new("RGB", (100, 100)).save(raiz / "UMAG" / "A.png")
    with pytest.raises(ValueError):
        acc.recortar_documento_combinado("UMAG", "A.png", ["1"], raiz_docs=raiz, ruta_backups=backups)
    (raiz / "UMAG" / "A_2.png").write_bytes(b"ya estaba")
    with pytest.raises(FileExistsError):
        acc.recortar_documento_combinado(
            "UMAG", "A.png", ["0,0,1,0.5", "0,0.5,1,1"], raiz_docs=raiz, ruta_backups=backups)
    assert (raiz / "UMAG" / "A.png").exists()


def test_vista_con_cuadricula_de_un_pdf(tmp_path):
    pytest.importorskip("pypdfium2")
    raiz, _ = _carpeta(tmp_path)
    _pdf_con_dos_facturas(raiz / "UMAG" / "Facturas.pdf")

    pngs = acc.vista_con_cuadricula(raiz / "UMAG" / "Facturas.pdf", tmp_path / "vista")

    assert [p.name for p in pngs] == ["Facturas - pagina 1.png"]
    assert Image.open(pngs[0]).size[0] > 0
