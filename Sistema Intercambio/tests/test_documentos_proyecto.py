# -*- coding: utf-8 -*-
"""Las facturas del Centro de Costos de cada proyecto, para «Proyectos en ejecución» del Portal (2026-11-06)."""
import ast
import json
from pathlib import Path

import documentos_proyecto as dp
import esquemas
import intercambio

AF = Path(__file__).resolve().parents[2] / "Sistema Analisis Financiero" / "Sistema" / "analisis_financiero.py"


def _foto():
    return {"generado": "2026-11-06 14:00", "ultima_actualizacion": "2026-11-06 13:50", "documentos": [
        {"ref": "950-001", "proyecto": "950. Obra", "fecha": "2026-11-02", "tipo_documento": "Factura", "n_documento": 77,
         "proveedor_tag": "FERR", "proveedor_razon_social": "Ferretería Ejemplo SpA", "categoria": "Ferretería",
         "resumen_items": "Cañería", "total_sin_iva": None, "estado": "Pagado", "pendiente_revision": False,
         "archivo_origen": "950. Obra/950-001.pdf", "enlace_archivo": "https://quempinspa2020.sharepoint.com/x/950-001.pdf",
         "items": [{"nombre_item": "Cañería", "categoria_item": "Ferretería", "cantidad": 10, "p_unitario_sin_iva": 1000, "total_sin_iva": 10000},
                   {"nombre_item": "Flete", "categoria_item": "Transporte", "cantidad": 1, "p_unitario_sin_iva": 5000, "total_sin_iva": 5000},
                   {"nombre_item": "Algo nuevo", "categoria_item": "Categoría nueva", "cantidad": 1, "p_unitario_sin_iva": 1, "total_sin_iva": 1}]},
        {"ref": "UML1-002", "proyecto": "280. UMAG", "fecha": None, "tipo_documento": "Nota de Crédito", "categoria": "Arriendo",
         "total_sin_iva": -3000, "estado": "Nota de Crédito", "items": []},
        {"ref": "sin guion", "items": []}]}


def test_el_mapeo_es_el_del_analisis_financiero():
    """La copia de MAPEO_CATEGORIA_BUCKET es igual a la del Análisis Financiero: lo gastado del Portal suma lo mismo."""
    arbol = ast.parse(AF.read_text(encoding="utf-8"))
    original = next(ast.literal_eval(n.value) for n in arbol.body if isinstance(n, ast.Assign)
                    and any(getattr(t, "id", "") == "MAPEO_CATEGORIA_BUCKET" for t in n.targets))
    assert dp.MAPEO_CATEGORIA_BUCKET == original


def test_documentos_por_tag_con_la_categoria_del_analisis():
    docs = {d["ref"]: d for d in dp.documentos(_foto())}
    assert set(docs) == {"950-001", "UML1-002"}, "sin N° Ref. válido no entra"
    f = docs["950-001"]
    assert (f["tag"], f["neto"], f["categoria"], f["numero"], f["proveedor"]) == ("950", 15001, "Materiales", "77", "Ferretería Ejemplo SpA")
    assert [i["categoria"] for i in f["items"]] == ["Materiales", "Otros", "Otros"]
    assert "archivo_origen" not in f
    nc = docs["UML1-002"]
    assert (nc["tag"], nc["neto"], nc["categoria"], nc["enlace"]) == ("UML1", -3000, "Equipos", None)


def test_publica_y_valida_con_su_esquema(tmp_path):
    raiz = tmp_path / "intercambio"
    intercambio.asegurar_carpeta(raiz)
    foto = tmp_path / "centro-de-costos.json"
    foto.write_text(json.dumps(_foto(), ensure_ascii=False), encoding="utf-8")
    assert dp.publicar(raiz, foto) == {"documentos": 2, "proyectos": 2}
    sobre = intercambio.leer_publicacion(raiz, dp.NOMBRE)
    assert sobre["datos"]["actualizado"] == "2026-11-06 13:50"
    assert esquemas.validar_publicacion(dp.NOMBRE, sobre) == []
