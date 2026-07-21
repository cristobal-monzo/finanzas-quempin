import analisis_financiero as af


def test_asegurar_carpeta_proyecto_crea_la_carpeta_si_no_existe(tmp_path):
    creada = af.asegurar_carpeta_proyecto("Cesfam Limache", tmp_path)
    assert creada is True
    assert (tmp_path / "Cesfam Limache").is_dir()


def test_asegurar_carpeta_proyecto_no_duplica_si_ya_existe(tmp_path):
    (tmp_path / "UMAG").mkdir()
    creada = af.asegurar_carpeta_proyecto("UMAG", tmp_path)
    assert creada is False


def test_asegurar_carpetas_proyectos_devuelve_solo_las_nuevas(tmp_path):
    (tmp_path / "UMAG").mkdir()
    filas_validas = [
        {"fila": 2, "tag": "UMAG", "nombre": "UMAG"},
        {"fila": 3, "tag": "CFLI", "nombre": "Cesfam Limache"},
    ]
    creadas = af.asegurar_carpetas_proyectos(filas_validas, tmp_path)
    assert creadas == ["Cesfam Limache"]
    assert (tmp_path / "Cesfam Limache").is_dir()
