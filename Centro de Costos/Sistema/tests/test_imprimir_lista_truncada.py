import auditor_centro_costos as acc


def test_imprime_todos_los_items_si_no_supera_el_limite(capsys):
    acc._imprimir_lista_truncada([1, 2, 3], lambda i: f"item {i}", limite=15)
    salida = capsys.readouterr().out
    assert salida == "item 1\nitem 2\nitem 3\n"


def test_trunca_y_resume_el_resto_si_supera_el_limite(capsys):
    acc._imprimir_lista_truncada(list(range(20)), lambda i: f"item {i}", limite=15)
    salida = capsys.readouterr().out.splitlines()
    assert len(salida) == 16
    assert salida[:15] == [f"item {i}" for i in range(15)]
    assert salida[15] == "   ... y 5 mas."


def test_formatear_puede_devolver_texto_multilinea(capsys):
    acc._imprimir_lista_truncada(["x"], lambda i: f"linea 1 de {i}\nlinea 2 de {i}", limite=15)
    salida = capsys.readouterr().out
    assert salida == "linea 1 de x\nlinea 2 de x\n"
