from PIL import Image
from pypdf import PdfReader, PdfWriter

import auditor_centro_costos as acc


def _crear_png_con_marcador(ruta, size=(4, 2)):
    """Imagen blanca con un pixel rojo en (0,0) -- esquina superior-izquierda.
    PNG (sin perdida) para poder verificar la posicion exacta del marcador
    tras rotar."""
    img = Image.new("RGB", size, color=(255, 255, 255))
    img.putpixel((0, 0), (255, 0, 0))
    img.save(str(ruta), "PNG")


def _crear_heic_de_prueba(ruta, size=(10, 10)):
    import pillow_heif

    img = Image.new("RGB", size, color=(200, 50, 50))
    heif_file = pillow_heif.from_pillow(img)
    heif_file.save(str(ruta))


def _crear_pdf_de_prueba(ruta, n_paginas=1):
    escritor = PdfWriter()
    for _ in range(n_paginas):
        escritor.add_blank_page(width=200, height=300)
    with open(ruta, "wb") as f:
        escritor.write(f)


def test_rotar_imagen_90_grados_gira_en_sentido_horario(tmp_path):
    ruta = tmp_path / "foto.png"
    _crear_png_con_marcador(ruta)

    acc.rotar_imagen(ruta, 90)

    with Image.open(ruta) as img:
        assert img.size == (2, 4)
        assert img.getpixel((1, 0)) == (255, 0, 0)


def test_rotar_imagen_180_grados_gira_en_sentido_horario(tmp_path):
    ruta = tmp_path / "foto.png"
    _crear_png_con_marcador(ruta)

    acc.rotar_imagen(ruta, 180)

    with Image.open(ruta) as img:
        assert img.size == (4, 2)
        assert img.getpixel((3, 1)) == (255, 0, 0)


def test_rotar_imagen_270_grados_gira_en_sentido_horario(tmp_path):
    ruta = tmp_path / "foto.png"
    _crear_png_con_marcador(ruta)

    acc.rotar_imagen(ruta, 270)

    with Image.open(ruta) as img:
        assert img.size == (2, 4)
        assert img.getpixel((0, 3)) == (255, 0, 0)


def test_rotar_imagen_conserva_formato_jpeg(tmp_path):
    ruta = tmp_path / "foto.jpg"
    Image.new("RGB", (6, 4), color=(0, 128, 0)).save(str(ruta), "JPEG")

    acc.rotar_imagen(ruta, 90)

    with Image.open(ruta) as img:
        assert img.format == "JPEG"
        assert img.size == (4, 6)


def test_rotar_imagen_conserva_formato_heic(tmp_path):
    ruta = tmp_path / "foto.heic"
    _crear_heic_de_prueba(ruta, size=(6, 4))

    acc.rotar_imagen(ruta, 90)

    with Image.open(ruta) as img:
        assert img.format == "HEIF"
        assert img.size == (4, 6)


def test_rotar_pdf_90_grados_establece_rotate_horario(tmp_path):
    ruta = tmp_path / "factura.pdf"
    _crear_pdf_de_prueba(ruta)

    acc.rotar_pdf(ruta, 90)

    lector = PdfReader(str(ruta))
    assert lector.pages[0].rotation == 90


def test_rotar_pdf_270_grados_establece_rotate_horario(tmp_path):
    ruta = tmp_path / "factura.pdf"
    _crear_pdf_de_prueba(ruta)

    acc.rotar_pdf(ruta, 270)

    lector = PdfReader(str(ruta))
    assert lector.pages[0].rotation == 270


def test_rotar_pdf_rota_todas_las_paginas(tmp_path):
    ruta = tmp_path / "factura_multipagina.pdf"
    _crear_pdf_de_prueba(ruta, n_paginas=2)

    acc.rotar_pdf(ruta, 90)

    lector = PdfReader(str(ruta))
    assert [p.rotation for p in lector.pages] == [90, 90]


def test_rotar_archivo_despacha_pdf_a_rotar_pdf(tmp_path):
    ruta = tmp_path / "factura.pdf"
    _crear_pdf_de_prueba(ruta)

    acc.rotar_archivo(ruta, 90)

    lector = PdfReader(str(ruta))
    assert lector.pages[0].rotation == 90


def test_rotar_archivo_despacha_imagen_a_rotar_imagen(tmp_path):
    ruta = tmp_path / "foto.png"
    _crear_png_con_marcador(ruta)

    acc.rotar_archivo(ruta, 90)

    with Image.open(ruta) as img:
        assert img.size == (2, 4)


def test_rotar_si_corresponde_sin_rotacion_no_hace_nada(tmp_path):
    ruta = tmp_path / "foto.png"
    _crear_png_con_marcador(ruta)

    error = acc.rotar_si_corresponde(ruta, None)

    assert error is None
    with Image.open(ruta) as img:
        assert img.size == (4, 2)


def test_rotar_si_corresponde_rota_y_no_devuelve_error(tmp_path):
    ruta = tmp_path / "foto.png"
    _crear_png_con_marcador(ruta)

    error = acc.rotar_si_corresponde(ruta, 90)

    assert error is None
    with Image.open(ruta) as img:
        assert img.size == (2, 4)


def test_rotar_si_corresponde_devuelve_mensaje_si_falla(tmp_path):
    ruta = tmp_path / "corrupto.jpg"
    ruta.write_bytes(b"esto no es una imagen valida")

    error = acc.rotar_si_corresponde(ruta, 90)

    assert error is not None
    assert ruta.exists()
    assert ruta.read_bytes() == b"esto no es una imagen valida"
