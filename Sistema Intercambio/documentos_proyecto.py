# -*- coding: utf-8 -*-
"""Las facturas y boletas del Centro de Costos de cada proyecto, para el Portal.

Pedido del usuario (2026-11-06): en «Proyectos en ejecución» ver los costos del
proyecto registrados en el Centro de Costos y asociar cada factura a uno o
varios de sus gastos proyectados y cotizados. El Portal no lee el libro del
Centro de Costos (las herramientas no se leen entre sí): el procesador publica
`publicado/documentos-proyecto.json` (esquema `documentos-proyecto`) desde el
snapshot saneado que el Centro de Costos ya arma en cada `run`
(`Centro de Costos/Visualizador Web/data/centro-de-costos.json`, PASO 12c),
igual que los precios de referencia salen del snapshot del Cotizador.

Cada documento va con su TAG (el prefijo del N° Ref.: 261-012 → 261, la clave
del Análisis Financiero) y cada ítem con la categoría del Análisis Financiero
(Materiales, Equipos, Otros), con el mismo mapeo que él usa
(MAPEO_CATEGORIA_BUCKET de analisis_financiero.py; `test_documentos_proyecto`
exige que esta copia sea igual). Así lo gastado del Portal es lo mismo que suma
el Análisis Financiero, pero al día con el último registro del Centro de Costos.
"""
from __future__ import annotations

import json
from pathlib import Path

import intercambio

NOMBRE = "documentos-proyecto"
HERRAMIENTA = "procesador"

# La misma tabla que Sistema Analisis Financiero/Sistema/analisis_financiero.py
# (MAPEO_CATEGORIA_BUCKET). Lo que no está ahí va a «Otros», como allá.
MAPEO_CATEGORIA_BUCKET = {
    "Materiales": "Materiales",
    "Consumibles": "Materiales",
    "Ferretería": "Materiales",
    "Reposición de Material": "Materiales",
    "Equipos-Herramientas": "Equipos",
    "Herramientas": "Equipos",
    "Arriendo": "Equipos",
    "Servicios": "Otros",
    "Combustible": "Otros",
    "Transporte": "Otros",
    "Alimentación": "Otros",
    "Viáticos/Alojamiento": "Otros",
    "Despachos": "Otros",
    "Seguridad Industrial": "Otros",
    "Oficina": "Otros",
    "Descuento": "Otros",
}


def categoria_af(categoria_cc) -> str:
    return MAPEO_CATEGORIA_BUCKET.get(categoria_cc, "Otros")


def _txt(v, maximo=200) -> str:
    return " ".join(str(v).split())[:maximo] if v not in (None, "") else ""


def _num(v) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def tag_de_ref(ref) -> str | None:
    ref = str(ref or "").strip()
    return ref.rsplit("-", 1)[0].upper() if "-" in ref else None


def documentos(foto: dict) -> list[dict]:
    """Los documentos del snapshot del Centro de Costos, en la forma de la
    publicación: sin el archivo de origen (ruta de la carpeta) ni el IVA."""
    salida = []
    for d in foto.get("documentos") or []:
        tag = tag_de_ref(d.get("ref"))
        if not tag:
            continue
        items = []
        for it in d.get("items") or []:
            items.append({
                "nombre": _txt(it.get("nombre_item") or it.get("descripcion"), 160),
                "cantidad": _num(it.get("cantidad")),
                "unitario": _num(it.get("p_unitario_sin_iva")),
                "neto": round(_num(it.get("total_sin_iva")), 2),
                "categoria": categoria_af(it.get("categoria_item")),
            })
        neto = sum(i["neto"] for i in items) if items else _num(d.get("total_sin_iva"))
        salida.append({
            "ref": str(d.get("ref")),
            "tag": tag,
            "proyecto": _txt(d.get("proyecto"), 120),
            "fecha": d.get("fecha") or None,
            "tipo": _txt(d.get("tipo_documento"), 40),
            "numero": _txt(d.get("n_documento"), 40),
            "proveedor": _txt(d.get("proveedor_razon_social") or d.get("proveedor_tag"), 120),
            "resumen": _txt(d.get("resumen_items"), 300),
            # Sin detalle (pocas veces): todo el documento en la categoría del documento
            "categoria": categoria_af(d.get("categoria")) if not items else
                         max(("Materiales", "Equipos", "Otros"), key=lambda c: sum(abs(i["neto"]) for i in items if i["categoria"] == c)),
            "neto": round(neto, 2),
            "estado": _txt(d.get("estado"), 40),
            "pendiente": bool(d.get("pendiente_revision")),
            "enlace": d.get("enlace_archivo") or None,
            "items": items,
        })
    salida.sort(key=lambda x: (x["tag"], x["fecha"] or "", x["ref"]), reverse=True)
    return salida


def publicar(raiz: Path, ruta_foto: Path) -> dict:
    """Publica los documentos del snapshot. Devuelve {documentos, proyectos}."""
    foto = json.loads(Path(ruta_foto).read_text(encoding="utf-8"))
    docs = documentos(foto)
    intercambio.publicar(raiz, NOMBRE, HERRAMIENTA, {
        "actualizado": foto.get("ultima_actualizacion") or foto.get("generado"),
        "documentos": docs,
    })
    return {"documentos": len(docs), "proyectos": len({d["tag"] for d in docs})}
