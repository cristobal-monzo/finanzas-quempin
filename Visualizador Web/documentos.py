# -*- coding: utf-8 -*-
"""El enlace de SharePoint que abre una factura o boleta del Centro de Costos.

Lo usan los tableros que muestran documentos, de Chile y de Perú: el ícono
junto al N° Ref. del Centro de Costos (2026-10-28) y el de cada compra del
Cotizador Histórico (2026-10-29). Vive acá una sola vez: era la misma regla
copiada en dos builds, y dos copias de lo mismo terminan divergiendo.

El enlace se arma en el build, no en el navegador: solo el build puede revisar
que el archivo siga en la carpeta. Lo abre quien tiene acceso al sitio, en el
computador o en el teléfono, sin «Conectar carpeta».
"""
from pathlib import Path
from urllib.parse import quote

RAIZ_FINANZAS = Path(__file__).resolve().parents[1]     # Finanzas QUEMPIN/

# Los documentos, en el acceso directo de OneDrive y en SharePoint: la misma
# carpeta (RAIZ_DOCS de Centro de Costos/Sistema/auditor_centro_costos.py).
CARPETA_PAIS = {"CL": "Chile", "PE": "Perú"}
SHAREPOINT = "https://quempinspa2020.sharepoint.com"
RUTA_WEB_DOCS = ("Documentos compartidos", "Centro de Costos", "Facturas y Boletas")


def raiz_docs(pais="CL"):
    """La carpeta sincronizada con los documentos del país."""
    return (RAIZ_FINANZAS / "Centro de Costos" / "Sitio de comunicación - Centro de Costos 1"
            / "Facturas y Boletas" / CARPETA_PAIS[pais])


def enlace_documento(archivo_origen, pais="CL", raiz=None):
    """El enlace de SharePoint que abre el documento, o None.

    'Archivo origen' (hoja Master) guarda '<carpeta del proyecto>\\<nombre>'.
    Si la carpeta sincronizada está en este equipo y el archivo ya no está ahí
    (la carpeta del proyecto cambió de nombre después del run), no hay enlace:
    abriría un «no encontrado». Sin la carpeta (otro equipo, tests) no se puede
    revisar y el enlace va igual. `raiz` reemplaza la carpeta en los tests."""
    if not archivo_origen:
        return None
    partes = [p for p in str(archivo_origen).replace("\\", "/").split("/") if p]
    if not partes:
        return None
    carpeta = Path(raiz) if raiz is not None else raiz_docs(pais)
    if carpeta.is_dir() and not carpeta.joinpath(*partes).is_file():
        return None
    tramos = (*RUTA_WEB_DOCS, CARPETA_PAIS[pais], *partes)
    return SHAREPOINT + "/" + "/".join(quote(p, safe="") for p in tramos)
