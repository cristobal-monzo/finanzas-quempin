import pytest

import auditor_centro_costos as acc


def test_separar_documento_combinado_crea_copias_identicas(tmp_path):
    raiz_docs = tmp_path / "docs"
    ruta_backups = tmp_path / "backups"
    carpeta = raiz_docs / "UMAG"
    carpeta.mkdir(parents=True)
    original = carpeta / "IMG_1234.jpg"
    original.write_bytes(b"contenido de la foto")

    destinos = acc.separar_documento_combinado(
        "UMAG", "IMG_1234.jpg", 3, raiz_docs=raiz_docs, ruta_backups=ruta_backups
    )

    assert [d.name for d in destinos] == ["IMG_1234_1.jpg", "IMG_1234_2.jpg", "IMG_1234_3.jpg"]
    for destino in destinos:
        assert destino.exists()
        assert destino.read_bytes() == b"contenido de la foto"


def test_separar_documento_combinado_respalda_y_borra_original(tmp_path):
    raiz_docs = tmp_path / "docs"
    ruta_backups = tmp_path / "backups"
    carpeta = raiz_docs / "UMAG"
    carpeta.mkdir(parents=True)
    original = carpeta / "IMG_1234.jpg"
    original.write_bytes(b"contenido de la foto")

    acc.separar_documento_combinado(
        "UMAG", "IMG_1234.jpg", 2, raiz_docs=raiz_docs, ruta_backups=ruta_backups
    )

    assert not original.exists()
    respaldos = list(ruta_backups.rglob("IMG_1234 - documento combinado - backup *.jpg"))
    assert len(respaldos) == 1
    assert respaldos[0].read_bytes() == b"contenido de la foto"


def test_separar_documento_combinado_preserva_extension_y_carpeta(tmp_path):
    raiz_docs = tmp_path / "docs"
    carpeta = raiz_docs / "259. FACH 2"
    carpeta.mkdir(parents=True)
    (carpeta / "factura_combinada.pdf").write_bytes(b"pdf")

    destinos = acc.separar_documento_combinado(
        "259. FACH 2", "factura_combinada.pdf", 2,
        raiz_docs=raiz_docs, ruta_backups=tmp_path / "backups",
    )

    assert all(d.parent == carpeta for d in destinos)
    assert [d.name for d in destinos] == ["factura_combinada_1.pdf", "factura_combinada_2.pdf"]


def test_separar_documento_combinado_falla_si_no_existe_original(tmp_path):
    raiz_docs = tmp_path / "docs"
    (raiz_docs / "UMAG").mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        acc.separar_documento_combinado(
            "UMAG", "NoExiste.jpg", 2, raiz_docs=raiz_docs, ruta_backups=tmp_path / "backups"
        )


def test_separar_documento_combinado_falla_si_ya_existe_destino(tmp_path):
    raiz_docs = tmp_path / "docs"
    carpeta = raiz_docs / "UMAG"
    carpeta.mkdir(parents=True)
    original = carpeta / "IMG_1234.jpg"
    original.write_bytes(b"contenido")
    (carpeta / "IMG_1234_1.jpg").write_bytes(b"ya estaba aca")

    with pytest.raises(FileExistsError):
        acc.separar_documento_combinado(
            "UMAG", "IMG_1234.jpg", 2, raiz_docs=raiz_docs, ruta_backups=tmp_path / "backups"
        )

    # No debe haber tocado el original ni el destino preexistente al abortar.
    assert original.exists()
    assert (carpeta / "IMG_1234_1.jpg").read_bytes() == b"ya estaba aca"


def test_separar_documento_combinado_falla_con_cantidad_menor_a_dos(tmp_path):
    raiz_docs = tmp_path / "docs"
    carpeta = raiz_docs / "UMAG"
    carpeta.mkdir(parents=True)
    (carpeta / "IMG_1234.jpg").write_bytes(b"contenido")

    with pytest.raises(ValueError):
        acc.separar_documento_combinado(
            "UMAG", "IMG_1234.jpg", 1, raiz_docs=raiz_docs, ruta_backups=tmp_path / "backups"
        )


def test_separar_documento_combinado_usa_globales_por_defecto(tmp_path, monkeypatch):
    raiz_docs = tmp_path / "docs"
    carpeta = raiz_docs / "UMAG"
    carpeta.mkdir(parents=True)
    (carpeta / "IMG_1234.jpg").write_bytes(b"contenido")
    monkeypatch.setattr(acc, "RAIZ_DOCS", raiz_docs)
    monkeypatch.setattr(acc, "RUTA_BACKUPS", tmp_path / "backups")

    destinos = acc.separar_documento_combinado("UMAG", "IMG_1234.jpg", 2)

    assert len(destinos) == 2
