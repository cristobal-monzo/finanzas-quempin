# -*- coding: utf-8 -*-
"""Tablero de Oportunidades (GitHub Pages, 2026-10-13): se arma cifrado con
la contraseña de los tableros, y la página calcula igual que Python la
categoría y el puntaje, incluido lo que depende de la fecha (el plazo y una
visita que ya pasó), que la página recalcula al día.

Datos ficticios, en tmp_path. La contraseña es la de prueba del conftest raíz:
la real nunca aparece en un test."""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import oportunidades as op

RAIZ_INTERCAMBIO = Path(__file__).resolve().parents[1]
RUTA_BUILD = RAIZ_INTERCAMBIO / "Visualizador Web" / "build_visualizador.py"


def _cargar_build():
    """Por ruta y con nombre propio: hay varios build_visualizador.py en el repo."""
    spec = importlib.util.spec_from_file_location("build_visualizador_oportunidades", RUTA_BUILD)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


build = _cargar_build()
candado = build.candado

AHORA = datetime.now().replace(microsecond=0)
HISTORIA = [
    {"numero": 1, "estado": "Adjudicado", "titulo": "Mantención preventiva caldera hospital", "referencia": "5000-1-LE26", "valorOfertado": 8_000_000},
    {"numero": 2, "estado": "No adjudicado", "titulo": "Mantención calderas y red de calefacción", "referencia": "5001-2-LE26", "valorOfertado": 15_000_000},
    {"numero": 3, "estado": "Adjudicado", "titulo": "Reparación caldera agua caliente", "referencia": "5002-3-LE26", "valorOfertado": 4_000_000},
    {"numero": 4, "estado": "Ofertado", "titulo": "Mantención caldera escuela", "referencia": "5003-4-LE26", "valorOfertado": 20_000_000},
    {"numero": 5, "estado": "Descartado", "titulo": "Mantención aire acondicionado oficinas", "referencia": "5004-5-LE26"},
    {"numero": 6, "estado": "Descartado", "titulo": "Convenio aire acondicionado cuarteles", "referencia": "5005-6-LE26"},
    {"numero": 7, "estado": "Descartado", "titulo": "Mantención aire acondicionado edificio", "referencia": "5006-7-LE26"},
    {"numero": 8, "estado": "Adjudicado", "titulo": "Caldera sala de calderas CESFAM", "referencia": "761391-8-LE26", "valorOfertado": 30_000_000},
]


def _en(dias: float) -> str:
    return (AHORA + timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%S")


def _ficha(codigo, nombre, descripcion="", region="Región de Valparaíso", monto=10_000_000, visita=None, cierre=None):
    return {
        "CodigoExterno": codigo, "Nombre": nombre, "CodigoEstado": 5, "Descripcion": descripcion, "Tipo": "LE", "Moneda": "CLP",
        "Comprador": {"NombreOrganismo": "Servicio de ejemplo", "NombreUnidad": "Unidad de ejemplo", "ComunaUnidad": "Quilpué",
                      "RegionUnidad": region},
        "CantidadReclamos": 10, "Obras": "0", "Etapas": 1, "TomaRazon": "0",
        "Fechas": {"FechaPublicacion": _en(-3), "FechaCierre": cierre or _en(20), "FechaVisitaTerreno": visita},
        "VisibilidadMonto": 1, "MontoEstimado": monto, "TiempoDuracionContrato": "12", "UnidadTiempoDuracionContrato": 4,
        "Items": {"Cantidad": 1, "Listado": [{"Correlativo": 1, "Categoria": "Servicios", "NombreProducto": "Servicio", "Descripcion": "x"}]},
    }


def _datos():
    config = op.cargar_config()
    historia = op.Historia(HISTORIA)
    ev = op.Evaluador(config, historia, [], AHORA, 40000)
    # Evaluada hace 3 días, cuando su visita obligatoria todavía no pasaba: la
    # página tiene que descartarla hoy.
    ev_antes = op.Evaluador(config, historia, [], AHORA - timedelta(days=3), 40000)
    fichas = [
        (ev, _ficha("761391-91-LE26", "Mantención preventiva de calderas", cierre=_en(20))),
        (ev, _ficha("5000-92-LE26", "Mantención de calderas y calefacción", cierre=_en(2.5))),
        (ev, _ficha("5000-93-LE26", "Mantención aire acondicionado y climatización", cierre=_en(12))),
        (ev, _ficha("5000-94-LE26", "Suministro de petróleo para calefacción", cierre=_en(15))),
        (ev, _ficha("5000-95-LE26", "Reparación caldera agua caliente", region="Región de Magallanes y de la Antártica Chilena", cierre=_en(8))),
        (ev_antes, _ficha("5000-96-LE26", "Mantención de caldera del liceo", "La visita a terreno será obligatoria.",
                          visita=_en(-1), cierre=_en(10))),
        (ev_antes, _ficha("5000-97-LE26", "Mantención de calderas municipales", cierre=_en(-0.5))),   # ya cerró
    ]
    ops = [e.evaluar(op.leer_ficha(f, f["CodigoExterno"])) for e, f in fichas]
    datos = op.publicacion(ops, ev, historia, config, {"activas": {}, "candidatas": []}, [], False, AHORA)
    return datos, config


def test_el_tablero_se_arma_cifrado_y_abre_con_la_contrasena(tmp_path):
    datos, _ = _datos()
    ruta = build.construir(datos, ruta_json=tmp_path / "data.json", ruta_html=tmp_path / "index.html")
    html = ruta.read_text(encoding="utf-8")
    for marcador in build.MARCADORES + (candado.MARCADOR_JS,):
        assert marcador not in html
    contrasena = candado.leer_contrasena()
    assert candado.abre_con(html, contrasena)
    assert candado.leer_datos(html, "op-data-b64", contrasena)["oportunidades"][0]["codigo"] == datos["oportunidades"][0]["codigo"]
    # Nada de los datos viaja en claro: ni el organismo ni la historia de la Planilla.
    assert "Servicio de ejemplo" not in html and "Mantención preventiva caldera hospital" not in html
    assert 'data-nav-activo="oportunidades"' in html


def test_la_plantilla_repite_las_reglas_de_python():
    """La categoría (con su tope por rubro) y el plazo se calculan en dos lados:
    si cambias una regla, cambia la otra (y el test del navegador de abajo)."""
    plantilla = build.RUTA_TEMPLATE.read_text(encoding="utf-8")
    for pieza in ("Evaluador.categoria", "topesPorRubro", "rubroMenorA", "categoriaMaxima",
                  "REGLAS.plazoOferta", "menosDeDias", "visitaPasada", "obligatoriaODuda", "descartarFijo"):
        assert pieza in plantilla, pieza
    assert "innerHTML" not in plantilla, "los textos de la API se escriben con textContent"


@pytest.fixture(scope="module")
def navegador():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            nav = p.chromium.launch()
        except Exception as error:   # sin Chromium instalado (py -3.14 -m playwright install chromium)
            pytest.skip(f"no se pudo abrir Chromium: {error}")
        yield nav
        nav.close()


def _abrir(navegador, tmp_path, ancho=1280):
    datos, config = _datos()
    ruta = build.construir(datos, ruta_json=tmp_path / "data.json", ruta_html=tmp_path / "index.html")
    pagina = navegador.new_page(viewport={"width": ancho, "height": 900})
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    pagina.goto(ruta.as_uri())
    pagina.fill("#pwInput", candado.leer_contrasena())
    pagina.press("#pwInput", "Enter")
    pagina.locator("#pwGate").wait_for(state="hidden", timeout=20000)
    return pagina, datos, config, errores


def _filas(pagina):
    return pagina.evaluate("""() => [...document.querySelectorAll('#tOps tr.op-row')].map(tr => ({
        codigo: tr.getAttribute('data-codigo'),
        puntaje: +tr.querySelector('.op-puntaje').textContent,
        categoria: tr.querySelector('.cat').textContent }))""")


def test_la_pagina_calcula_igual_que_python_y_recalcula_lo_que_depende_de_la_fecha(navegador, tmp_path):
    pagina, datos, config, errores = _abrir(navegador, tmp_path)
    nombres = {c["id"]: c["nombre"] for c in config["categorias"]}
    nombres["descartar"] = "Descartada"
    pagina.select_option("#fMostrar", "todas")
    vivas = {f["codigo"]: f for f in _filas(pagina)}
    pagina.select_option("#fMostrar", "descartadas")
    descartadas = {f["codigo"]: f for f in _filas(pagina)}
    por_codigo = {o["codigo"]: o for o in datos["oportunidades"]}

    for codigo in ("761391-91-LE26", "5000-92-LE26", "5000-93-LE26", "5000-95-LE26"):
        o = por_codigo[codigo]
        assert codigo in vivas, codigo
        assert vivas[codigo]["categoria"] == nombres[o["categoria"]], codigo
        assert vivas[codigo]["puntaje"] == round(o["puntaje"]), codigo
    assert descartadas["5000-94-LE26"]["categoria"] == "Descartada"            # fuera de rubro: no depende de la fecha
    # Evaluada antes de su visita obligatoria; hoy la visita ya pasó: descartada en la página.
    assert por_codigo["5000-96-LE26"]["categoria"] != "descartar"
    assert "5000-96-LE26" in descartadas and "5000-96-LE26" not in vivas
    assert "5000-97-LE26" not in vivas and "5000-97-LE26" not in descartadas    # ya cerró: no se muestra
    assert errores == []


def test_las_recomendadas_son_las_mejores_y_un_peso_cambia_el_orden(navegador, tmp_path):
    pagina, datos, _, errores = _abrir(navegador, tmp_path)
    tarjetas = pagina.locator("#opTop .op-top")
    assert tarjetas.count() >= 1
    mejor = next(o for o in datos["oportunidades"] if o["categoria"] in ("prioritaria", "buena"))
    assert mejor["nombre"] in tarjetas.first.locator("h3").inner_text()
    assert tarjetas.first.locator(".op-razones .favor").count() >= 1          # siempre dice por qué
    # Ver evaluación abre la fila de esa licitación en la tabla.
    tarjetas.first.get_by_role("button", name="Ver evaluación").click()
    assert pagina.locator(f'#tOps tr.op-row[data-codigo="{mejor["codigo"]}"]').get_attribute("aria-expanded") == "true"
    assert pagina.locator("#tOps tr.detail-row .op-crit").count() == 8
    # Con el peso del rubro en 0 cambia el puntaje en la tabla (los pesos son por persona).
    antes = _filas(pagina)
    pagina.click('.viz-tab-btn[data-tab="tabMetodo"]')
    pagina.locator('input[aria-label="Peso de Rubro"]').fill("0")
    pagina.click('.viz-tab-btn[data-tab="tabOportunidades"]')
    assert _filas(pagina) != antes
    assert errores == []
