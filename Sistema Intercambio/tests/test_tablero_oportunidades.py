# -*- coding: utf-8 -*-
"""Tablero de Oportunidades (GitHub Pages, 2026-10-13): se arma cifrado con
la contraseña de los tableros, y la página calcula igual que Python la
categoría y el puntaje, incluido lo que depende de la fecha (el plazo y una
visita que ya pasó), que la página recalcula al día.

Datos ficticios, en tmp_path. La contraseña es la de prueba del conftest raíz:
la real nunca aparece en un test."""
import base64
import importlib.util
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import compra_agil as ca
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


def test_mientras_consulta_la_api_el_procesador_lo_sabe(monkeypatch, tmp_path):
    """2026-11-11: el procesador corre cada 5 minutos; si le toca Mercado Público mientras el tablero consulta, lo
    deja para la vuelta siguiente (la API rechaza las consultas simultáneas)."""
    vistas = []

    def _evaluar(sin_red=False, raiz=None):
        vistas.append((sin_red, build.mercado_publico.api_en_uso()))
        return {"oportunidades": [], "avisos": []}, 0, True
    monkeypatch.setattr(build, "evaluar", _evaluar)
    monkeypatch.setattr(build, "construir", lambda datos: tmp_path / "index.html")
    assert build.main([]) == 0
    assert build.main(["--sin-red"]) == 0
    assert vistas == [(False, True), (True, False)]
    assert not build.mercado_publico.api_en_uso()

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


# Lo publicado hoy (ficticio), para contar frases en «Qué buscamos» (2026-11-26).
ACTIVAS = {f"9000-{i}-LE26": {"nombre": n} for i, n in enumerate([
    "Mantención de calderas del hospital", "Mantto. caldera y calef. del liceo", "Suministro de gas licuado GLP",
    "Instalación de aire acondicionado en oficinas", "Aire acondicionado sala de servidores", "Mantención de chiller",
    "Red de gas natural del CESFAM", "Absorbente de vapor de agua", "Generador de vapor para lavandería",
    "Cambio de válvulas y radiadores", "Proyecto H2 verde", "Agua caliente sanitaria (ACS) del gimnasio",
    "Compra de bombas de agua", "Gas para cocina del casino", "Servicio de aseo"])}


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


def _datos(extra=(), config=None):
    """extra: fichas más, evaluadas hoy (solo para el test que las pide). config: otra configuración
    (la de «Qué buscamos» con ajustes, para comparar con la página)."""
    config = config or op.cargar_config()
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
    fichas += [(ev, f) for f in extra]
    ops = [e.evaluar(op.leer_ficha(f, f["CodigoExterno"])) for e, f in fichas]
    # La visita leída en la ficha de las bases (la API no la trae), con dos fechas:
    # una ya pasó y otra viene (sigue viva); o las dos pasaron desde el build (descartada hoy).
    # Una optativa ya pasada también se retira (pedido del usuario, 2026-10-26).
    for e, codigo, dias, obligatoria in ((ev, "5000-88-LE26", (-2, 3), True), (ev_antes, "5000-89-LE26", (-2, -1), True),
                                         (ev_antes, "5000-86-LE26", (-1,), False)):
        ficha = op.leer_ficha(_ficha(codigo, "Mantención de calderas del hospital", cierre=_en(12)), codigo)
        ficha["visitaBases"] = {"fechas": [{"fecha": _en(d)[:16], "obligatoria": obligatoria, "lugar": None} for d in dias],
                                "nombrada": False, "daPuntaje": False, "contenidoBases": True,
                                "criterios": [{"nombre": "Oferta económica", "ponderacion": 30}, {"nombre": "Experiencia", "ponderacion": 25},
                                              {"nombre": "Propuesta técnica", "ponderacion": 45}]}
        ops.append(e.evaluar(ficha))
    # Compras ágiles (2026-10-14): se cotizan en horas y tienen sus propios tramos de plazo.
    for codigo, horas in (("100-98-COT26", 10), ("100-99-COT26", 3)):
        crudo = {"codigo": codigo, "nombre": "Mantención de caldera del gimnasio", "descripcion": "",
                 "estado": {"codigo": "publicada"}, "fechas": {"fecha_cierre": _en(horas / 24)[:16].replace("T", " ")},
                 "presupuesto": {"monto_disponible_clp": 2_000_000}, "entrega": {"plazo_entrega_dias": 10},
                 "institucion": {"organismo_comprador": "Servicio de ejemplo", "nombre_region": "Región de Valparaíso"}}
        ops.append(ev.evaluar(ca.leer_ficha(crudo, codigo)))
    datos = op.publicacion(ops, ev, historia, config, {"activas": {}, "candidatas": []}, [], False, AHORA)
    datos["buscar"] = op.para_buscar(config, historia, {"activas": ACTIVAS})
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


def test_sin_respuesta_de_mercado_publico_usa_la_cache_y_lo_avisa(monkeypatch):
    """La tarea diaria publica solo un tablero al día: sin API, el build arma
    uno con la caché (para la corrida semanal) y lo marca con el código 3."""
    pedidas = []

    def revisar_falso(raiz, enviar, sin_red):
        pedidas.append(sin_red)
        if not sin_red:
            raise build.mercado_publico.SinTicket("no hay ticket de Mercado Público en este equipo")
        return {"datos": {"avisos": [], "oportunidades": []}, "llamadas": 0}

    monkeypatch.setattr(build.oportunidades, "revisar", revisar_falso)
    datos, llamadas, al_dia = build.evaluar(raiz=RAIZ_INTERCAMBIO)
    assert al_dia is False and pedidas == [False, True] and llamadas == 0
    assert datos["avisos"][0].startswith("No se pudo consultar Mercado Público")

    escritos = []
    monkeypatch.setattr(build, "construir", lambda datos: escritos.append(datos) or Path("index.html"))   # nunca el build real
    assert build.main([]) == build.CODIGO_CON_CACHE and escritos
    monkeypatch.setattr(build, "evaluar", lambda sin_red=False: ({"avisos": [], "oportunidades": []}, 5, True))
    assert build.main([]) == 0


def test_la_plantilla_repite_las_reglas_de_python():
    """La categoría (con su tope por rubro) y el plazo se calculan en dos lados:
    si cambias una regla, cambia la otra (y el test del navegador de abajo)."""
    plantilla = build.RUTA_TEMPLATE.read_text(encoding="utf-8")
    for pieza in ("Evaluador.categoria", "op.tope", "tope.categoria", "topesPorRubro",
                  "REGLAS.plazoOferta", "plazoOfertaCompraAgil", "menosDeDias", "visitaPasada", "obligatoriaODuda", "descartarFijo"):
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


def _abrir(navegador, tmp_path, ancho=1280, extra=(), pendiente=None, almacen=None):
    datos, config = _datos(extra)
    ruta = build.construir(datos, ruta_json=tmp_path / "data.json", ruta_html=tmp_path / "index.html")
    pagina = navegador.new_page(viewport={"width": ancho, "height": 900})
    errores = []
    pagina.on("pageerror", lambda e: errores.append(str(e)))
    if pendiente is not None:
        # Lo guardado en este navegador que todavía no llega al tablero: la página lo usa como perfil.
        pagina.add_init_script(f"localStorage.setItem('quempin_op_ajustes_pendiente', {json.dumps(json.dumps(pendiente))});")
    for clave, valor in (almacen or {}).items():
        pagina.add_init_script(f"localStorage.setItem({json.dumps(clave)}, {json.dumps(json.dumps(valor))});")
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

    for codigo in ("761391-91-LE26", "5000-92-LE26", "5000-93-LE26", "5000-95-LE26", "100-98-COT26"):
        o = por_codigo[codigo]
        assert codigo in vivas, codigo
        assert vivas[codigo]["categoria"] == nombres[o["categoria"]], codigo
        assert vivas[codigo]["puntaje"] == round(o["puntaje"]), codigo
    assert descartadas["5000-94-LE26"]["categoria"] == "Descartada"            # fuera de rubro: no depende de la fecha
    # Evaluada antes de su visita obligatoria; hoy la visita ya pasó: descartada en la página.
    assert por_codigo["5000-96-LE26"]["categoria"] != "descartar"
    assert "5000-96-LE26" in descartadas and "5000-96-LE26" not in vivas
    assert "5000-97-LE26" not in vivas and "5000-97-LE26" not in descartadas    # ya cerró: no se muestra
    # Visita con varias fechas: pasa cuando pasaron todas.
    assert "5000-88-LE26" in vivas and vivas["5000-88-LE26"]["puntaje"] == round(por_codigo["5000-88-LE26"]["puntaje"])
    assert por_codigo["5000-89-LE26"]["categoria"] != "descartar" and "5000-89-LE26" in descartadas
    # Optativa evaluada antes de su visita; hoy ya pasó: fuera del tablero.
    assert por_codigo["5000-86-LE26"]["categoria"] != "descartar"
    assert "5000-86-LE26" in descartadas and "5000-86-LE26" not in vivas
    # Compra ágil que cierra en 10 horas: viva (una licitación se descartaría); en 3 horas: descartada.
    assert por_codigo["100-98-COT26"]["compraAgil"] and por_codigo["100-99-COT26"]["categoria"] == "descartar"
    assert "100-99-COT26" in descartadas
    pagina.select_option("#fMostrar", "todas")
    pagina.select_option("#fTipo", "compraAgil")
    assert [f["codigo"] for f in _filas(pagina)] == ["100-98-COT26"]
    assert errores == []


def test_abrir_una_fila_no_mueve_la_pagina(navegador, tmp_path):
    """Pedido del usuario (2026-10-15): al hacer clic en un proyecto la página
    volvía al inicio (se rehacía la tabla entera). Abre y cierra en su lugar."""
    pagina, _, _, errores = _abrir(navegador, tmp_path, ancho=390)    # en móvil la tabla son tarjetas: la página es larga
    pagina.select_option("#fMostrar", "todas")
    filas = pagina.locator("#tOps tr.op-row")
    fila = filas.nth(filas.count() - 1)
    fila.scroll_into_view_if_needed()
    pagina.evaluate("window.scrollBy(0, 150)")
    antes = pagina.evaluate("window.scrollY")
    assert antes > 0
    caja = fila.bounding_box()
    pagina.mouse.click(caja["x"] + 20, caja["y"] + 10)
    assert fila.get_attribute("aria-expanded") == "true"
    assert pagina.locator("#tOps tr.detail-row").count() == 1
    assert abs(pagina.evaluate("window.scrollY") - antes) <= 1
    caja = fila.bounding_box()
    pagina.mouse.click(caja["x"] + 20, caja["y"] + 10)
    assert fila.get_attribute("aria-expanded") == "false" and pagina.locator("#tOps tr.detail-row").count() == 0
    assert abs(pagina.evaluate("window.scrollY") - antes) <= 1
    # Ordenar por una columna tampoco la mueve.
    pagina.evaluate("window.scrollTo(0, document.querySelector('#tOps').getBoundingClientRect().top + window.scrollY - 40)")
    antes = pagina.evaluate("window.scrollY")
    pagina.evaluate("document.querySelector('#tOps > thead th[data-k=\"puntaje\"]').click()")
    assert abs(pagina.evaluate("window.scrollY") - antes) <= 1
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
    # El desglose del puntaje va en la ⓘ de la nota, una fila por criterio.
    assert pagina.locator("#tOps tr.detail-row .op-cifras .op-crit-fila").count() == 8
    # Con el rubro al último puesto cambia el puntaje en la tabla (el orden es por persona).
    antes = _filas(pagina)
    pagina.click('.viz-tab-btn[data-tab="tabMetodo"]')
    assert pagina.locator("#opPesosRestablecer").is_hidden()          # sin cambios, es el orden del equipo
    for _ in range(7):
        pagina.get_by_role("button", name="Bajar Rubro").click()
    assert pagina.locator("#opOrden li").last.get_attribute("data-crit") == "rubro"
    assert pagina.get_by_role("button", name="Bajar Rubro").is_disabled()
    pct = [int(t.replace("%", "").strip()) for t in pagina.locator("#opReparto .barra b").all_inner_texts()]
    assert sum(pct) == 100 and pct == sorted(pct, reverse=True)        # el reparto siempre suma 100 %
    pagina.click('.viz-tab-btn[data-tab="tabOportunidades"]')
    assert _filas(pagina) != antes
    # Se queda al recargar y «Volver al orden del equipo» lo deshace.
    pagina.reload()
    pagina.click('.viz-tab-btn[data-tab="tabMetodo"]')
    assert pagina.locator("#opOrden li").last.get_attribute("data-crit") == "rubro"
    pagina.click("#opPesosRestablecer")
    assert pagina.locator("#opOrden li").first.get_attribute("data-crit") == "rubro"
    pagina.click('.viz-tab-btn[data-tab="tabOportunidades"]')
    assert _filas(pagina) == antes
    assert errores == []


def test_arrastrar_un_criterio_cambia_su_puesto(navegador, tmp_path):
    pagina, _, _, errores = _abrir(navegador, tmp_path)
    pagina.click('.viz-tab-btn[data-tab="tabMetodo"]')
    pagina.drag_and_drop('#opOrden li[data-crit="ejecucion"]', '#opOrden li[data-crit="rubro"]')
    assert pagina.locator("#opOrden li").first.get_attribute("data-crit") == "ejecucion"
    assert "tu orden" in pagina.locator("#opPesosNota").inner_text()
    assert errores == []


def test_los_pesos_viejos_de_los_deslizadores_pasan_a_un_orden(navegador, tmp_path):
    viejos = {"rubro": 0, "monto": 40, "dificultad": 1, "visita": 1, "ubicacion": 1, "comprador": 1, "plazoOferta": 1, "ejecucion": 1}
    pagina, _, _, errores = _abrir(navegador, tmp_path, almacen={"quempin_op_pesos": viejos})
    pagina.click('.viz-tab-btn[data-tab="tabMetodo"]')
    ids = pagina.locator("#opOrden li").evaluate_all("l => l.map(x => x.dataset.crit)")
    assert ids[0] == "monto" and ids[-1] == "rubro"
    assert pagina.evaluate("localStorage.getItem('quempin_op_pesos')") is None
    assert errores == []


def _datos_del_enlace(href):
    """El # de «Llevar al Formulador»: JSON en base64url, lo que lee js/oportunidad.js del Formulador."""
    prefijo = "https://cristobal-monzo.github.io/formulacion-proyectos-quempin/#/oportunidad/"
    assert href.startswith(prefijo), href
    cola = href[len(prefijo):]
    assert re.fullmatch(r"[A-Za-z0-9_-]+", cola), "sin «/», «+», «=» ni «%»: pasa por el Portal sin cambiar"
    return json.loads(base64.urlsafe_b64decode(cola + "=" * (-len(cola) % 4)).decode("utf-8"))


def test_llevar_al_formulador_lleva_los_datos_de_la_oportunidad(navegador, tmp_path):
    """Pedido del usuario (2026-10-16): exportar la oportunidad al Formulador con
    su nombre, ID, monto, etc. Va en las recomendadas y en el detalle de cada una."""
    sin_monto = _ficha("5000-87-LE26", "Mantención de calderas del consultorio", monto=None, cierre=_en(9))
    pagina, datos, _, errores = _abrir(navegador, tmp_path, extra=[sin_monto])
    por_codigo = {o["codigo"]: o for o in datos["oportunidades"]}
    boton = pagina.locator("#opTop .op-top").first.locator("a.op-formulador")
    assert boton.inner_text().startswith("Llevar al Formulador") and boton.get_attribute("target") == "_blank"
    d = _datos_del_enlace(boton.get_attribute("href"))
    o = por_codigo[d["codigo"]]
    assert d["v"] == 1 and d["nombre"] == o["nombre"] and d["organismo"] == o["organismo"] == "Servicio de ejemplo"
    assert d["comuna"] == (o["comuna"] or "") and d["region"] == o["region"] and d["tipo"] == o["tipo"]
    assert d["compraAgil"] is o["compraAgil"] and d["cierre"] == o["cierre"] and d["duracionMeses"] == o["duracionMeses"]
    assert d["monto"] == (None if o["monto"]["fuente"].startswith("por tipo") else round(o["monto"]["valor"]))

    def del_detalle(codigo):
        pagina.select_option("#fMostrar", "todas")
        pagina.fill("#fBuscar", codigo)
        pagina.locator(f'#tOps tr.op-row[data-codigo="{codigo}"]').click()
        return _datos_del_enlace(pagina.locator("#tOps tr.detail-row a.op-formulador").get_attribute("href"))

    licitacion = del_detalle("761391-91-LE26")
    assert licitacion["monto"] == 10_000_000 and licitacion["comuna"] == "Quilpué" and licitacion["compraAgil"] is False
    assert licitacion["req"] == "" and licitacion["descripcion"] == ""
    # Sin monto publicado, el que se estima por el tipo de licitación no viaja: no es un presupuesto.
    assert por_codigo["5000-87-LE26"]["monto"]["fuente"].startswith("por tipo")
    assert del_detalle("5000-87-LE26")["monto"] is None
    # La compra ágil va como tal, con su presupuesto disponible.
    agil = del_detalle("100-98-COT26")
    assert agil["compraAgil"] is True and agil["monto"] == 2_000_000 and agil["tipo"] == "COT"
    # La visita que toca hoy: la próxima de sus fechas.
    assert del_detalle("5000-88-LE26")["visita"] == {"fecha": _en(3)[:16], "obligatoria": True, "pasada": False}
    assert errores == []


# ── «Qué buscamos» (2026-11-16, variante D1) ────────────────────────────────

AJUSTES = {"temas": {"climatizacion": {"interes": "alto"}, "calderas": {"interes": "medio"}, "calefaccion": {"interes": "no"}},
           "regiones": {"magallanes": 100, "valparaiso": 35},
           "monto": {"minimo": 12_000_000, "minimoCompraAgil": 3_000_000, "maximo": None}}


def _perfil_completo(datos, ajustes):
    """Lo que la página manda al guardar: la versión completa, con los ajustes encima."""
    rb = datos["rubro"]
    temas = {t["id"]: {"interes": t["interes"], "frases": list(t["frases"])} for t in rb["temas"]}
    for k, v in ajustes.get("temas", {}).items():
        temas[k]["interes"] = v["interes"]
    regiones = dict(rb["regiones"], **ajustes.get("regiones", {}))
    monto = dict({"minimo": rb["montoMinimo"], "minimoCompraAgil": rb["montoMinimoCompraAgil"], "maximo": rb["montoMaximo"]},
                 **ajustes.get("monto", {}))
    return {"temas": temas, "excluir": list(rb["excluir"]), "noConfundir": list(rb["noConfundir"].get("frases", [])),
            "regiones": regiones, "monto": monto}


def _categorias_en_pagina(pagina):
    pagina.locator("[data-tab=tabOportunidades]").click()
    pagina.select_option("#fMostrar", "todas")
    vivas = {f["codigo"]: f for f in _filas(pagina)}
    pagina.select_option("#fMostrar", "descartadas")
    vivas.update({f["codigo"]: f for f in _filas(pagina)})
    return vivas


def test_con_ajustes_la_pagina_calcula_igual_que_python(navegador, tmp_path):
    """Lo que depende de «Qué buscamos» (niveles, regiones, montos) la página lo recalcula con resolverRubro,
    calcularTope y resolverMonto: tienen que dar lo mismo que oportunidades.py con esos ajustes aplicados."""
    base, config = _datos()
    con, _ = _datos(config=op.aplicar_ajustes(config, AJUSTES))
    pendiente = {"id": "pendiente-de-prueba", "enviado": AHORA.astimezone().isoformat(timespec="seconds"),
                 "ajustes": _perfil_completo(base, AJUSTES)}
    pagina, _, _, errores = _abrir(navegador, tmp_path, pendiente=pendiente)
    nombres = {c["id"]: c["nombre"] for c in config["categorias"]}
    nombres["descartar"] = "Descartada"
    en_pagina = _categorias_en_pagina(pagina)
    por_codigo = {o["codigo"]: o for o in con["oportunidades"]}
    cambiaron = 0
    for codigo in ("761391-91-LE26", "5000-92-LE26", "5000-93-LE26", "5000-94-LE26", "5000-95-LE26", "5000-88-LE26", "100-98-COT26"):
        o = por_codigo[codigo]
        assert en_pagina[codigo]["categoria"] == nombres[o["categoria"]], (codigo, o["categoria"], o["descartar"], o["tope"])
        if o["categoria"] != "descartar":
            assert en_pagina[codigo]["puntaje"] == round(o["puntaje"]), codigo
        cambiaron += o["categoria"] != next(x for x in base["oportunidades"] if x["codigo"] == codigo)["categoria"]
    assert cambiaron >= 3                                   # los ajustes sí mueven la lista
    assert por_codigo["5000-92-LE26"]["descartar"] == []    # «calderas y calefacción»: calderas sigue en el nombre
    pagina.locator("[data-tab=tabBuscamos]").click()
    assert pagina.locator(".qb-col[data-nivel=no] [data-tema=calefaccion]").count() == 1
    assert pagina.locator("#qbEstado").inner_text().startswith("Guardado")
    assert errores == []


def test_arrastrar_un_tema_cambia_la_lista_al_tiro_y_deshacer_vuelve(navegador, tmp_path):
    pagina, datos, _, errores = _abrir(navegador, tmp_path)
    pagina.locator("[data-tab=tabBuscamos]").click()
    assert pagina.locator("#qbEstado").inner_text().startswith("Así busca el equipo")
    assert pagina.locator("#qbGuardar").is_disabled()
    clima = pagina.locator("[data-tema=climatizacion]")
    clima.drag_to(pagina.locator(".qb-col[data-nivel=no]"))
    pagina.locator(".qb-col[data-nivel=no] [data-tema=climatizacion]").wait_for()
    assert pagina.locator("#qbEstado").inner_text().startswith("1 cambio sin guardar")
    # Fuera del Portal no hay carpeta del equipo: no se puede guardar, y se dice dónde.
    assert pagina.locator("#qbGuardar").is_disabled() and "Portal" in pagina.locator("#qbEfecto").inner_text()
    assert _categorias_en_pagina(pagina)["5000-93-LE26"]["categoria"] == "Descartada"
    # Tocar la tarjeta y «Mover a» hace lo mismo que arrastrar (en el celular no se arrastra).
    pagina.locator("[data-tab=tabBuscamos]").click()
    pagina.locator("[data-tema=climatizacion] > button").click()
    pagina.locator("[data-tema=climatizacion] .qb-mover button", has_text="Mucho interés").click()
    pagina.locator(".qb-col[data-nivel=alto] [data-tema=climatizacion]").wait_for()
    # Una región en «No vamos» descarta lo de ahí; el tooltip dice los puntos.
    mag = pagina.locator("#qbRegiones button", has_text="Magallanes")
    while "No vamos" not in mag.inner_text():
        mag.click()
    assert _categorias_en_pagina(pagina)["5000-95-LE26"]["categoria"] == "Descartada"
    pagina.locator("[data-tab=tabBuscamos]").click()
    pagina.locator("#qbDeshacer").click()
    assert pagina.locator("#qbEstado").inner_text().startswith("Así busca el equipo")
    original = {o["codigo"]: o["categoria"] for o in datos["oportunidades"]}
    assert _categorias_en_pagina(pagina)["5000-95-LE26"]["categoria"] != "Descartada" and original["5000-95-LE26"] != "descartar"
    assert errores == []


# ── Contar y proponer frases (2026-11-26) ───────────────────────────────────

def test_las_propuestas_traen_cuantas_publicadas_las_nombran():
    """Pedido del usuario: proponer frases con un número: cuántas licitaciones publicadas hoy las nombran. No se
    propone lo que una frase actual ya encuentra, ni lo que hoy no sale en ninguna."""
    config = op.cargar_config()
    publicadas = op.raices_publicadas(ACTIVAS, config["rubro"].get("noConfundir"))
    assert op.cuenta_publicadas("aire acondicionado", publicadas) == 2
    assert op.cuenta_publicadas("Calderas", publicadas) == 2        # «calderas» y «caldera» son lo mismo
    assert op.cuenta_publicadas("vapor", publicadas) == 1           # «vapor de agua» no es vapor (no confundir)
    assert op.cuenta_publicadas("de la", publicadas) == 0           # sin palabras útiles no cuenta nada
    propuestas = {s["frase"]: s for s in op.sugerencias(config, op.Historia(HISTORIA), publicadas)}
    assert propuestas["aire acondicionado"]["hoy"] == 2 and propuestas["aire acondicionado"]["tema"] == "climatizacion"
    assert propuestas["gas"]["hoy"] == 3 and propuestas["chiller"]["hoy"] == 1
    assert "caldera a pellet" not in propuestas                     # la cubre «caldera»
    assert "biomasa" not in propuestas                              # hoy no sale en ninguna
    assert [s["hoy"] for s in propuestas.values()] == sorted((s["hoy"] for s in propuestas.values()), reverse=True)


def test_las_propuestas_salen_tambien_de_la_planilla():
    """Una frase que se repite en lo que QUEMPIN ofertó y es rara en lo publicado se propone, con el tema que más
    nombran esos títulos. Un trozo de una frase actual no («caliente» de «agua caliente»)."""
    config = op.cargar_config()
    config["rubro"]["sugerencias"] = {}
    historia = op.Historia([{"numero": i, "estado": "Ofertado", "titulo": f"Termocañones y calefacción del gimnasio {i}"}
                            for i in range(5)] + [{"numero": 9, "estado": "Ofertado", "titulo": "Agua caliente del liceo"}] * 5)
    publicadas = op.raices_publicadas({"1": {"nombre": "Arriendo de termocañones"}, "2": {"nombre": "Agua caliente"},
                                       **{str(i + 10): {"nombre": f"Servicio de aseo {i}"} for i in range(200)}}, None)
    propuestas = op.sugerencias(config, historia, publicadas)
    assert [(s["frase"], s["tema"], s["origen"], s["hoy"]) for s in propuestas] == [("termocañones", "calefaccion", "planilla", 1)]


FRASES_PARIDAD = ["Calderas", "mantto. de calef.", "ACS", "H2", "vapor", "Válvulas", "radiadores", "aire  acondicionado",
                  "GLP", "gas", "de la", "Ñandú", "bombas"]


def test_contar_frases_en_la_pagina_da_lo_mismo_que_python(navegador, tmp_path):
    """raicesTexto y cuentaPublicadas del tablero repiten raices y cuenta_publicadas: el número que aparece al
    escribir una frase es el de Python."""
    pagina, datos, config, errores = _abrir(navegador, tmp_path)
    publicadas = datos["buscar"]["publicadas"]
    pagina.locator("[data-tab=tabBuscamos]").click()
    pagina.locator("[data-tema=calderas] > button").click()
    caja = pagina.locator("[data-tema=calderas] input.qb-nueva")
    for frase in FRASES_PARIDAD:
        caja.fill(frase)
        n = op.cuenta_publicadas(frase, publicadas)
        esperado = "" if len(frase.strip()) < 2 else ("1 publicada hoy" if n == 1 else f"{n} publicadas hoy")
        assert pagina.locator("[data-tema=calderas] .qb-cuenta").inner_text() == esperado, frase
    assert errores == []


def test_agregar_una_propuesta_y_escribir_otra_frase(navegador, tmp_path):
    pagina, datos, _, errores = _abrir(navegador, tmp_path)
    pagina.locator("[data-tab=tabBuscamos]").click()
    caja = pagina.locator("#qbPropuestas")
    assert caja.locator(".qb-idea").first.inner_text().startswith("+ gas")
    caja.locator(".qb-idea", has_text="aire acondicionado").click()
    assert pagina.locator("#qbEstado").inner_text().startswith("1 cambio sin guardar")
    assert caja.locator(".qb-idea", has_text="aire acondicionado").count() == 0     # ya no se propone
    pagina.locator("[data-tema=climatizacion] > button").click()
    chip = pagina.locator("[data-tema=climatizacion] .qb-chip", has_text="aire acondicionado")
    assert chip.locator(".qb-n").inner_text() == "2"
    # Escribir y Enter agrega la frase con su número, y el cursor queda para escribir otra.
    caja_tema = pagina.locator("[data-tema=climatizacion] input.qb-nueva")
    caja_tema.fill("chiller")
    caja_tema.press("Enter")
    assert pagina.locator("[data-tema=climatizacion] .qb-chip", has_text="chiller").locator(".qb-n").inner_text() == "1"
    assert pagina.evaluate("document.activeElement.dataset.clave") == "climatizacion"
    # Quitar con ×.
    pagina.locator("[data-tema=climatizacion] .qb-chip", has_text="chiller").locator("button").click()
    assert pagina.locator("[data-tema=climatizacion] .qb-chip", has_text="chiller").count() == 0
    assert errores == []


def test_crear_un_tema_agregarle_frases_y_eliminarlo(navegador, tmp_path):
    """2026-11-26, pedido del usuario: crear temas nuevos. «+ Nuevo tema» en la columna, nombre, frases; uno creado
    por el equipo se puede eliminar (los del archivo no)."""
    pagina, _, _, errores = _abrir(navegador, tmp_path)
    pagina.locator("[data-tab=tabBuscamos]").click()
    pagina.locator(".qb-col[data-nivel=medio] .qb-crear").click()
    nombre = pagina.locator(".qb-col[data-nivel=medio] input[data-clave=_crear]")
    assert pagina.evaluate("document.activeElement.dataset.clave") == "_crear"
    nombre.fill("Termocañones")
    nombre.press("Enter")
    carta = pagina.locator(".qb-col[data-nivel=medio] .qb-tema", has_text="Termocañones")
    assert carta.locator("small").inner_text() == "Sin frases: agrega una"
    assert pagina.locator("#qbEstado").inner_text().startswith("1 cambio sin guardar")
    tid = carta.get_attribute("data-tema")
    assert re.match(r"^nuevo-termocanones-[a-z0-9]+$", tid)
    assert pagina.evaluate("document.activeElement.dataset.clave") == tid      # listo para escribir la primera frase
    caja = carta.locator("input.qb-nueva")
    caja.fill("aire acondicionado")
    assert carta.locator(".qb-cuenta").inner_text() == "2 publicadas hoy"
    caja.press("Enter")
    assert carta.locator(".qb-chip .qb-n").inner_text() == "2"
    # Se arrastra como cualquier otro.
    carta.drag_to(pagina.locator(".qb-col[data-nivel=alto]"))
    pagina.locator(f".qb-col[data-nivel=alto] [data-tema={tid}]").wait_for()
    assert pagina.locator("[data-tema=calderas] .qb-eliminar").count() == 0
    pagina.locator(f"[data-tema={tid}] .qb-eliminar").click()
    assert pagina.locator(f"[data-tema={tid}]").count() == 0
    assert pagina.locator("#qbEstado").inner_text().startswith("Así busca el equipo")
    assert errores == []


def test_un_tema_del_equipo_se_ve_y_se_puede_eliminar(navegador, tmp_path, monkeypatch):
    """Lo que el equipo creó llega en rubro.temas con «nuevo»: la página lo muestra con su nombre y lo deja eliminar."""
    original = op.cargar_config

    def con_tema():
        return op.aplicar_ajustes(original(), {"temas": {"nuevo-hornos-pan-x1": {"interes": "bajo", "nombre": "Hornos de pan",
                                                                                   "frases": ["horno panadero"]}}})
    monkeypatch.setattr(op, "cargar_config", con_tema)
    pagina, datos, _, errores = _abrir(navegador, tmp_path)
    assert any(t.get("nuevo") for t in datos["rubro"]["temas"])
    pagina.locator("[data-tab=tabBuscamos]").click()
    carta = pagina.locator(".qb-col[data-nivel=bajo] [data-tema=nuevo-hornos-pan-x1]")
    assert carta.locator("button").first.inner_text().startswith("Hornos de pan")
    carta.locator("> button").click()
    carta.locator(".qb-eliminar").click()
    assert pagina.locator("#qbEstado").inner_text().startswith("1 cambio sin guardar")
    assert errores == []


def test_el_detalle_muestra_la_linea_de_tiempo_la_pauta_y_las_tareas(navegador, tmp_path):
    """Detalle F4 (pedido del usuario, 2026-11-27): línea hoy → visita → cierre → contrato, cómo adjudica
    el comprador (ficha de las bases), para ganar y «Qué hay que hacer» (resumen por reglas)."""
    pagina, datos, _, errores = _abrir(navegador, tmp_path)
    pagina.select_option("#fMostrar", "todas")
    fila = pagina.locator('#tOps tr.op-row[data-codigo="5000-88-LE26"]')
    fila.click()
    det = pagina.locator("#tOps tr.detail-row .op-detalle")
    hitos = det.locator(".op-tl .hito .f").all_inner_texts()
    assert hitos[0] == "Hoy" and hitos[1].startswith("Visita ") and hitos[2].startswith("Cierre ") and hitos[3] == "Contrato"
    assert "obligatoria" in det.locator(".op-tl .hito.visita .d").inner_text()
    assert det.locator(".op-adj span").count() == 3
    assert det.locator(".op-adj-ley li").first.inner_text().startswith("Propuesta técnica")     # de mayor a menor peso
    ganar = det.locator(".op-ganar").inner_text()
    assert "Ir a la visita" in ganar and "El precio pesa solo 30 %" in ganar and "la experiencia pesa 25 %" in ganar
    o = next(x for x in datos["oportunidades"] if x["codigo"] == "5000-88-LE26")
    assert det.locator(".op-tareas .frase").inner_text() == o["resumen"]["frase"]
    # El desglose de la ⓘ suma el puntaje.
    filas = [float(t.replace(",", ".")) for t in det.locator(".op-cifras .op-crit-fila span:last-child").all_text_contents()]
    assert abs(sum(filas) - o["puntaje"]) < 0.3
    assert errores == []
