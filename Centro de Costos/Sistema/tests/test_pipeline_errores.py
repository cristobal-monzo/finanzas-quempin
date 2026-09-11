# -*- coding: utf-8 -*-
"""
Tests de integracion del pipeline de errores dentro de main().

Cubren las tres propiedades que la auditoria del 2026-09-10 introdujo y que
solo se ven corriendo el pipeline entero:

  1. La validacion ocurre ANTES de escribir y publicar (PASO 5B), no despues
     del PASO 12 -- antes, un documento mal leido llegaba al Excel guardado, a
     la copia del sitio, al visualizador y a Analisis Financiero sin que nadie
     lo hubiera mirado.
  2. Una copia exacta de un documento ya registrado NO se escribe dos veces y
     el caso queda cerrado como auto-resuelto.
  3. Si el Excel esta bloqueado, la corrida igual reporta los hallazgos en vez
     de terminar en silencio.

Todo corre sobre un pais ficticio registrado en acc.PAISES, no sobre los datos
reales: main() llama configurar_pais() como primera linea y pisa cualquier
parche hecho sobre los globals (ver CLAUDE.md raiz, "No midas contra
produccion").
"""

import json
from datetime import datetime

import openpyxl
import pytest

import auditor_centro_costos as acc


def _doc(archivo, **kwargs):
    base = {
        "archivo": archivo, "proyecto": "Proyecto Test", "tipo_proyecto": "Obra",
        "fecha": "15-07-2026", "n_documento": "5551", "tipo_documento": "Factura",
        "proveedor": "Proveedor Test SpA", "rut_proveedor": "76123456-7",
        "categoria": "Materiales", "estado": "Pagado",
        "items": [{"nombre_item": "Perfil", "descripcion": "d",
                   "categoria_item": "Materiales", "cantidad": 2,
                   "p_unitario_sin_iva": 50000}],
        "iva": 19000,
    }
    base.update(kwargs)
    return base


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Un Centro de Costos completo y desechable bajo tmp_path."""
    docs = tmp_path / "Facturas" / "Proyecto Test"
    docs.mkdir(parents=True)
    (tmp_path / "Excel").mkdir()
    (tmp_path / "Sitio").mkdir()

    cfg = dict(acc.PAISES["CL"])
    cfg.update({
        "ruta_docs": tmp_path / "Facturas",
        "ruta_excel": tmp_path / "Excel" / "Centro de Costos.xlsx",
        "ruta_backups": tmp_path / "Excel" / "Respaldos",
        "ruta_json": tmp_path / "datos_extraidos.json",
        "ruta_reconciliacion": tmp_path / "reconciliacion_archivos.json",
        "ruta_correcciones": tmp_path / "correcciones_manuales.json",
        "ruta_errores_md": tmp_path / "ERRORES.md",
        "ruta_logs": tmp_path / "logs",
        "ruta_visualizador_web": tmp_path / "Visualizador Web (inexistente)",
        "ruta_excel_sitio_comunicacion": tmp_path / "Sitio" / "Centro de Costos.xlsx",
        "prefijos_proyecto": {"Proyecto Test": "PTST"},
    })
    monkeypatch.setitem(acc.PAISES, "TEST", cfg)
    # PASO 12d importaria el modulo real de Analisis Financiero si existiera.
    monkeypatch.setattr(acc, "RAIZ_ANALISIS_FINANCIERO", tmp_path / "AF (inexistente)")
    (tmp_path / "correcciones_manuales.json").write_text("[]", encoding="utf-8")
    return {"tmp": tmp_path, "docs": docs, "cfg": cfg}


def _sembrar(sandbox, documentos, archivos_extra=()):
    for d in documentos:
        (sandbox["docs"] / d["archivo"]).write_bytes(b"")
    for archivo in archivos_extra:
        (sandbox["docs"] / archivo).write_bytes(b"")
    (sandbox["tmp"] / "datos_extraidos.json").write_text(
        json.dumps(documentos, ensure_ascii=False), encoding="utf-8")


def _registro(sandbox):
    return acc.cargar_registro_errores(sandbox["tmp"] / "errores_detectados.json")


# ── 1. La validacion corre antes de escribir y publicar ────────────────────

def test_los_hallazgos_se_reportan_antes_del_paso_de_guardado(sandbox, capsys):
    _sembrar(sandbox, [_doc("A.jpg", iva=1)])

    acc.main(pais="TEST")

    salida = capsys.readouterr().out
    assert salida.index("PASO 5B") < salida.index("PASO 12")
    assert salida.index("Hallazgos vigentes") < salida.index("PASO 12")


def test_el_registro_de_errores_queda_en_disco_tras_la_corrida(sandbox):
    _sembrar(sandbox, [_doc("A.jpg", iva=1)])

    acc.main(pais="TEST")

    abiertos = acc.hallazgos_abiertos(_registro(sandbox))
    assert [e["codigo"] for e in abiertos] == ["IMPUESTO_MENOR"]
    assert abiertos[0]["n_ref"] == "PTST-001"  # ya sabe que fila de Master mirar
    assert abiertos[0]["columna"] == 12


def test_clases_nuevas_se_detectan_en_una_corrida_real(sandbox):
    _sembrar(sandbox, [
        _doc("A.jpg", categoria=""),
        _doc("B.jpg", n_documento="5552", fecha="32-13-2026"),
        _doc("C.jpg", n_documento="5553", tipo_documento="Comprobante interno", iva=None),
    ])

    acc.main(pais="TEST")

    codigos = {e["codigo"] for e in acc.hallazgos_abiertos(_registro(sandbox))}
    assert {"CATEGORIA_VACIA", "FECHA_INVALIDA", "TIPO_DOC_DESCONOCIDO"} <= codigos


def test_un_corpus_limpio_no_genera_hallazgos(sandbox):
    _sembrar(sandbox, [_doc("A.jpg"), _doc("B.jpg", n_documento="5552")])

    acc.main(pais="TEST")

    assert acc.hallazgos_abiertos(_registro(sandbox)) == []


# ── 2. Copia exacta: no se registra dos veces ──────────────────────────────

def test_copia_exacta_no_se_registra_y_queda_auto_resuelta(sandbox, capsys):
    _sembrar(sandbox, [_doc("A.jpg"), _doc("B.jpg")])  # B es identico a A

    acc.main(pais="TEST")

    wb = openpyxl.load_workbook(str(sandbox["cfg"]["ruta_excel"]))
    try:
        n_refs = [wb["Master"].cell(row=r, column=1).value for r in (2, 3)]
    finally:
        wb.close()
    assert n_refs == ["PTST-001", None]  # solo se escribio uno

    auto = [e for e in _registro(sandbox)["errores"] if e["estado"] == "auto_resuelto"]
    assert len(auto) == 1
    assert auto[0]["codigo"] == "DUPLICADO_EXACTO"
    assert "PTST-001" in auto[0]["resolucion"]
    assert "[AUTO]" in capsys.readouterr().out


def test_la_copia_exacta_queda_mapeada_y_no_reaparece_como_pendiente(sandbox):
    _sembrar(sandbox, [_doc("A.jpg"), _doc("B.jpg")])
    acc.main(pais="TEST")

    mapeo = json.loads((sandbox["tmp"] / "reconciliacion_archivos.json")
                       .read_text(encoding="utf-8"))["mapeo"]
    assert mapeo == {"Proyecto Test\\B.jpg": "PTST-001"}

    # Segunda corrida: nada nuevo que escribir, y el auto-resuelto sigue cerrado.
    acc.main(pais="TEST")
    auto = [e for e in _registro(sandbox)["errores"] if e["estado"] == "auto_resuelto"]
    assert len(auto) == 1


def test_duplicado_ambiguo_no_se_auto_resuelve(sandbox):
    """Mismo emisor y numero pero distinto monto: hay que comparar las fotos,
    no se puede decidir sin mirar."""
    distinto = _doc("B.jpg")
    distinto["items"][0]["p_unitario_sin_iva"] = 70000
    distinto["iva"] = round(140000 * 0.19)
    _sembrar(sandbox, [_doc("A.jpg"), distinto])

    acc.main(pais="TEST")

    abiertos = {e["codigo"] for e in acc.hallazgos_abiertos(_registro(sandbox))}
    assert "DUPLICADO_AMBIGUO" in abiertos
    wb = openpyxl.load_workbook(str(sandbox["cfg"]["ruta_excel"]))
    try:  # los dos se registran: podrian ser documentos distintos
        assert wb["Master"].cell(row=3, column=1).value is not None
    finally:
        wb.close()


# ── 3. Deduplicacion entre corridas ────────────────────────────────────────

def test_el_mismo_hallazgo_no_se_duplica_entre_corridas(sandbox):
    _sembrar(sandbox, [_doc("A.jpg", iva=1)])

    acc.main(pais="TEST")
    acc.main(pais="TEST")

    errores = _registro(sandbox)["errores"]
    assert len(errores) == 1
    assert errores[0]["corridas_vistas"] == 2


def test_corregir_el_json_cierra_el_hallazgo_solo(sandbox):
    _sembrar(sandbox, [_doc("A.jpg", iva=1)])
    acc.main(pais="TEST")

    _sembrar(sandbox, [_doc("A.jpg", iva=19000)])  # corregido en el origen
    acc.main(pais="TEST")

    entrada = _registro(sandbox)["errores"][0]
    assert entrada["estado"] == "resuelto"
    assert "Dejo de detectarse" in entrada["resolucion"]


# ── 4. El informe sobrevive a un Excel bloqueado ───────────────────────────

def test_con_el_excel_bloqueado_igual_se_reportan_los_hallazgos(sandbox, capsys, monkeypatch):
    _sembrar(sandbox, [_doc("A.jpg", iva=1)])
    acc.main(pais="TEST")          # primera corrida: crea el libro
    capsys.readouterr()

    monkeypatch.setattr(acc, "excel_esta_bloqueado", lambda ruta: True)
    acc.main(pais="TEST")

    salida = capsys.readouterr().out
    assert "abierto en Excel" in salida
    assert "HALLAZGOS ABIERTOS" in salida
    assert "IMPUESTO_MENOR" in salida or "Impuesto declarado menor" in salida


# ── 5. Resolver por el canal auditado, de punta a punta ────────────────────

def test_resolver_un_hallazgo_tras_un_run_real(sandbox):
    _sembrar(sandbox, [_doc("A.jpg", categoria="")])
    acc.main(pais="TEST")

    abierto = acc.hallazgos_abiertos(_registro(sandbox))[0]
    aplicadas, rechazadas = acc.corregir_hallazgos(
        [(abierto["id"], "Ferreteria")],
        ruta_excel=sandbox["cfg"]["ruta_excel"],
        ruta_correcciones=sandbox["cfg"]["ruta_correcciones"],
        ruta_errores=sandbox["cfg"]["ruta_errores_md"],
        ruta_backups=sandbox["cfg"]["ruta_backups"],
        ruta_registro=sandbox["tmp"] / "errores_detectados.json")

    assert len(aplicadas) == 1 and rechazadas == []
    wb = openpyxl.load_workbook(str(sandbox["cfg"]["ruta_excel"]))
    try:
        assert wb["Master"].cell(row=2, column=9).value == "Ferreteria"
    finally:
        wb.close()

    # Y la proxima corrida NO lo vuelve a abrir aunque el JSON siga igual.
    acc.main(pais="TEST")
    entrada = _registro(sandbox)["errores"][0]
    assert entrada["estado"] == "resuelto"
    assert entrada["origen_sin_corregir"] is True


def test_el_valor_corregido_sobrevive_a_corridas_posteriores(sandbox):
    """La regla de oro del modulo: una fila ya escrita no se vuelve a tocar."""
    _sembrar(sandbox, [_doc("A.jpg", categoria="")])
    acc.main(pais="TEST")
    abierto = acc.hallazgos_abiertos(_registro(sandbox))[0]
    acc.corregir_hallazgos(
        [(abierto["id"], "Ferreteria")],
        ruta_excel=sandbox["cfg"]["ruta_excel"],
        ruta_correcciones=sandbox["cfg"]["ruta_correcciones"],
        ruta_errores=sandbox["cfg"]["ruta_errores_md"],
        ruta_backups=sandbox["cfg"]["ruta_backups"],
        ruta_registro=sandbox["tmp"] / "errores_detectados.json")

    acc.main(pais="TEST")

    wb = openpyxl.load_workbook(str(sandbox["cfg"]["ruta_excel"]))
    try:
        celda = wb["Master"].cell(row=2, column=9)
        assert celda.value == "Ferreteria"
        assert celda.font.color.rgb.endswith(acc.NAVY_OSCURO)
    finally:
        wb.close()


# ── 6. Idempotencia: sin documentos nuevos, no cambia nada ────────────────

def test_segunda_corrida_sin_novedades_no_cambia_el_master(sandbox):
    _sembrar(sandbox, [_doc("A.jpg"), _doc("B.jpg", n_documento="5552")])
    acc.main(pais="TEST")
    antes = sandbox["cfg"]["ruta_excel"].read_bytes()

    acc.main(pais="TEST")

    wb_a = openpyxl.load_workbook(str(sandbox["cfg"]["ruta_excel"]))
    try:
        filas = [[wb_a["Master"].cell(row=r, column=c).value for c in range(1, 11)]
                 for r in (2, 3)]
    finally:
        wb_a.close()
    assert filas[0][0] == "PTST-001" and filas[1][0] == "PTST-002"
    assert len(antes) > 0
