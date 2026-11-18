"""Un archivo nuevo con el nombre de un documento ya registrado no hereda sus datos.

Caso real (2026-11-06): 'run' renombra cada documento registrado, asi que el
nombre original ('Documento (1).pdf') queda libre. Dos facturas distintas que
se subieron despues a la misma carpeta con ese nombre calzaron con la entrada
vieja del JSON y quedaron registradas como copias de la primera. Los
identificadores reales (proveedores, folios, montos) no van aca: este
repositorio es publico.
"""

import json
from datetime import datetime

import openpyxl

import auditor_centro_costos as acc


def _libro(documentos):
    """documentos: [(n_ref, proyecto, fecha, n_documento, razon_social, neto)]"""
    wb = openpyxl.Workbook()
    ws_m = wb.active
    ws_m.title = "Master"
    ws_d = wb.create_sheet("Detalle")
    for c, h in enumerate(acc.ENCABEZADOS_MASTER, 1):
        ws_m.cell(row=1, column=c, value=h)
    for c, h in enumerate(acc.ENCABEZADOS_DETALLE, 1):
        ws_d.cell(row=1, column=c, value=h)
    for fila, (n_ref, proyecto, fecha, n_doc, razon, neto) in enumerate(documentos, start=2):
        ws_m.cell(row=fila, column=1, value=n_ref)
        ws_m.cell(row=fila, column=2, value=proyecto)
        ws_m.cell(row=fila, column=4, value=datetime.strptime(fecha, "%d-%m-%Y"))
        ws_m.cell(row=fila, column=5, value=n_doc)
        ws_m.cell(row=fila, column=7, value=acc.generar_tag_proveedor(razon))
        ws_m.cell(row=fila, column=8, value=razon)
        ws_m.cell(row=fila, column=15, value=f"{proyecto}\\{n_ref}_x.pdf")
        ws_d.cell(row=fila, column=1, value=n_ref)
        ws_d.cell(row=fila, column=10, value=neto)
    return ws_m, ws_d


def _entrada(archivo, n_documento, proveedor, neto, fecha="10-10-2026", proyecto="Proyecto Alfa"):
    return {"archivo": archivo, "proyecto": proyecto, "fecha": fecha, "n_documento": n_documento,
            "tipo_documento": "Factura", "proveedor": proveedor,
            "items": [{"nombre_item": "Perno", "cantidad": 1, "p_unitario_sin_iva": neto}]}


PENDIENTE = [{"proyecto": "Proyecto Alfa", "archivo": "Documento (1).pdf"}]


def test_la_entrada_de_un_documento_registrado_no_se_reusa():
    ws_m, ws_d = _libro([("ALFA-001", "Proyecto Alfa", "10-10-2026", "1001", "Proveedor Uno SpA", 5000)])
    datos = [_entrada("Documento (1).pdf", "1001", "Proveedor Uno SpA", 5000)]

    usadas = acc.entradas_ya_registradas(datos, ws_m, ws_d)

    assert acc.buscar_dato_por_archivo(datos, "Proyecto Alfa", "Documento (1).pdf", usadas) is None
    usados = acc.nombres_ya_usados(PENDIENTE, datos, usadas)
    assert [refs for _info, refs in usados] == [["ALFA-001"]]


def test_la_entrada_nueva_con_el_mismo_nombre_si_se_usa():
    ws_m, ws_d = _libro([("ALFA-001", "Proyecto Alfa", "10-10-2026", "1001", "Proveedor Uno SpA", 5000)])
    vieja = _entrada("Documento (1).pdf", "1001", "Proveedor Uno SpA", 5000)
    nueva = _entrada("Documento (1).pdf", "777", "Proveedor Dos SpA", 900, fecha="05-11-2026")
    datos = [vieja, nueva]

    usadas = acc.entradas_ya_registradas(datos, ws_m, ws_d)

    assert acc.buscar_dato_por_archivo(datos, "Proyecto Alfa", "Documento (1).pdf", usadas) is nueva
    assert acc.nombres_ya_usados(PENDIENTE, datos, usadas) == []


def test_un_documento_todavia_sin_registrar_conserva_su_entrada():
    ws_m, ws_d = _libro([("ALFA-001", "Proyecto Alfa", "10-10-2026", "1001", "Proveedor Uno SpA", 5000)])
    datos = [_entrada("Documento (1).pdf", "2002", "Proveedor Uno SpA", 5000)]

    usadas = acc.entradas_ya_registradas(datos, ws_m, ws_d)

    assert acc.buscar_dato_por_archivo(datos, "Proyecto Alfa", "Documento (1).pdf", usadas) is datos[0]


def test_el_mismo_numero_de_otro_emisor_u_otro_proyecto_no_cuenta():
    ws_m, ws_d = _libro([("ALFA-001", "Proyecto Alfa", "10-10-2026", "1001", "Proveedor Uno SpA", 5000),
                         ("BETA-001", "Proyecto Beta", "10-10-2026", "3003", "Proveedor Dos SpA", 5000)])
    datos = [_entrada("a.pdf", "1001", "Proveedor Dos SpA", 5000),
             _entrada("b.pdf", "3003", "Proveedor Dos SpA", 5000)]

    assert acc.entradas_ya_registradas(datos, ws_m, ws_d) == {}


def test_una_copia_exacta_pendiente_sigue_libre_para_validar_corpus():
    """Dos entradas iguales y un solo registro: es la misma compra fotografiada
    dos veces, y la copia la resuelve validar_corpus (copia exacta)."""
    ws_m, ws_d = _libro([("ALFA-001", "Proyecto Alfa", "10-10-2026", "1001", "Proveedor Uno SpA", 5000)])
    datos = [_entrada("foto.jpg", "1001", "Proveedor Uno SpA", 5000),
             _entrada("foto (2).jpg", "1001", "Proveedor Uno SpA", 5000)]

    assert acc.entradas_ya_registradas(datos, ws_m, ws_d) == {}


def test_peajes_sin_numero_cuentan_por_fecha_y_neto():
    peaje = ("Proyecto Alfa", "10-10-2026", "N/A", "Autopista Ejemplo S.A.", 1300)
    datos = [_entrada(f"peaje_{i}.pdf", "N/A", "Autopista Ejemplo S.A.", 1300) for i in range(3)]

    ws_m, ws_d = _libro([(f"ALFA-00{i}", *peaje) for i in (1, 2)])
    assert acc.entradas_ya_registradas(datos, ws_m, ws_d) == {}

    ws_m, ws_d = _libro([(f"ALFA-00{i}", *peaje) for i in (1, 2, 3)])
    assert len(acc.entradas_ya_registradas(datos, ws_m, ws_d)) == 3
    # Sin Detalle no hay netos: los documentos sin numero no se evaluan.
    assert acc.entradas_ya_registradas(datos, ws_m) == {}


def _sandbox(tmp_path, monkeypatch):
    raiz_docs = tmp_path / "Facturas"
    carpeta = raiz_docs / "Proyecto Alfa"
    carpeta.mkdir(parents=True)
    (tmp_path / "Excel").mkdir()
    ruta_json = tmp_path / "datos_extraidos.json"
    cfg = dict(acc.PAISES["PE"])
    cfg.update({
        "ruta_docs": raiz_docs, "ruta_excel": tmp_path / "Excel" / "CC.xlsx",
        "ruta_backups": tmp_path / "Excel" / "Respaldos", "ruta_json": ruta_json,
        "ruta_reconciliacion": tmp_path / "reconciliacion.json",
        "ruta_logs": tmp_path / "logs", "ruta_excel_sitio_comunicacion": None,
        "ruta_visualizador_web": tmp_path / "Visualizador Web",
    })
    monkeypatch.setitem(acc.PAISES, "PE", cfg)
    monkeypatch.setattr(acc, "actualizar_analisis_financiero", lambda pais="CL": True)
    return carpeta, ruta_json, cfg["ruta_excel"]


def _documentos(ruta_excel):
    ws = openpyxl.load_workbook(str(ruta_excel))["Master"]
    return [(ws.cell(row=r, column=1).value, ws.cell(row=r, column=5).value)
            for r in range(2, acc.ultima_fila_datos(ws) + 1)
            if acc.PATRON_NREF.match(str(ws.cell(row=r, column=1).value or ""))]


def test_run_no_registra_un_archivo_nuevo_con_los_datos_de_otro(tmp_path, monkeypatch, capsys):
    carpeta, ruta_json, ruta_excel = _sandbox(tmp_path, monkeypatch)
    entradas = [dict(_entrada("Documento (1).pdf", "1001", "Proveedor Uno SpA", 5000),
                     tipo_proyecto="Servicio", categoria="Materiales", estado="Pagado")]
    ruta_json.write_text(json.dumps(entradas), encoding="utf-8")
    (carpeta / "Documento (1).pdf").write_bytes(b"%PDF-1.4 primera factura")
    acc.main(pais="PE")
    assert [n_doc for _ref, n_doc in _documentos(ruta_excel)] == ["1001"]
    assert not (carpeta / "Documento (1).pdf").exists()  # renombrado: el nombre quedo libre

    # Otra factura, subida despues con el mismo nombre generico.
    (carpeta / "Documento (1).pdf").write_bytes(b"%PDF-1.4 otra factura distinta")
    capsys.readouterr()
    acc.main(pais="PE")
    assert [n_doc for _ref, n_doc in _documentos(ruta_excel)] == ["1001"]
    assert "ese nombre ya es de" in capsys.readouterr().out

    # Con su propia entrada (mismo nombre) se registra con SUS datos.
    entradas.append(dict(_entrada("Documento (1).pdf", "777", "Proveedor Dos SpA", 900,
                                  fecha="05-11-2026"),
                         tipo_proyecto="Servicio", categoria="Materiales", estado="Pagado"))
    ruta_json.write_text(json.dumps(entradas), encoding="utf-8")
    acc.main(pais="PE")
    assert sorted(n_doc for _ref, n_doc in _documentos(ruta_excel)) == ["1001", "777"]
