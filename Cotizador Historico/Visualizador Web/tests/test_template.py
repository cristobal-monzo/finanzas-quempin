# -*- coding: utf-8 -*-
"""Garantias estructurales de template.html, el mismo para Chile y Peru.

El template es un solo HTML con su CSS y su JavaScript de pantalla. No hay
tests de navegador en la suite, asi que estos cubren lo que se rompe sin que
nadie lo vea hasta abrir el dashboard publicado:

- que cada pais resuelva todos los marcadores de la plantilla (la taxonomia y
  el buscador divergieron cuando vivian duplicados en dos templates);
- que el carrito siga sin tocar el almacenamiento del navegador (requisito
  no negociable del usuario, ver CLAUDE.md § Carrito de cotizacion);
- que cada getElementById del JavaScript apunte a un id que exista en el
  HTML (un refactor de la pantalla que renombra un id deja un boton muerto
  sin ningun error visible hasta que alguien lo toca);
- que el JavaScript de la pantalla sea sintacticamente valido.
"""
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_MODULO = Path(__file__).resolve().parents[2]
TEMPLATE_CL = RAIZ_MODULO / "Visualizador Web" / "template.html"
BUILD_CL = RAIZ_MODULO / "Visualizador Web" / "build_visualizador.py"
BUILD_PE = RAIZ_MODULO.parent / "Peru" / "Cotizador Historico" / "Visualizador Web" / "build_visualizador.py"


def _cargar_build(ruta, nombre):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _leer(ruta):
    return ruta.read_text(encoding="utf-8")


def _script_app(html):
    """El <script> de la pantalla (el que define initApp)."""
    bloques = re.findall(r"<script>(.*?)</script>", html, re.S)
    return next(b for b in bloques if "function initApp" in b)


@pytest.mark.parametrize("ruta,nombre", [(BUILD_CL, "build_ch_cl"), (BUILD_PE, "build_ch_pe")], ids=["chile", "peru"])
def test_cada_pais_resuelve_todos_los_marcadores_de_la_misma_plantilla(ruta, nombre):
    build = _cargar_build(ruta, nombre)
    assert build.RUTA_TEMPLATE == TEMPLATE_CL
    marcadores = set(re.findall(r"__CH_[A-Z_]+__", _leer(TEMPLATE_CL)))
    assert marcadores - {"__CH_DATA_B64__", "__CH_BUSQUEDA_JS__"} == set(build.PLANTILLA_PAIS)


def test_lo_que_depende_de_la_uf_lo_decide_el_snapshot():
    """El snapshot de Peru no trae uf_hoy: sin esto, su tablero diria «UF utilizada $0»."""
    js = _script_app(_leer(TEMPLATE_CL))
    assert "var CON_UF = DATA.uf_hoy != null;" in js
    assert js.count("CON_UF") == 4 and "S/ Soles" in js


def test_el_carrito_nunca_usa_el_almacenamiento_del_navegador():
    js = _script_app(_leer(TEMPLATE_CL))
    # Desde la linea siguiente al encabezado, que justamente dice
    # "(solo en memoria -- nunca localStorage/sessionStorage)".
    inicio = js.index("\n", js.index("// ---------- carrito"))
    fin = js.index("// ---------- texto del carrito")
    seccion = js[inicio:fin]
    assert "localStorage" not in seccion and "sessionStorage" not in seccion
    assert "indexedDB" not in js
    # Tampoco al llevarlo a un proyecto (2026-10-29): va como mensaje al Portal
    llevar = js[js.index("// ---------- llevar la cotización"):js.index("// ---------- explorador de carpetas")]
    assert "localStorage" not in llevar and "sessionStorage" not in llevar


def test_cada_getElementById_apunta_a_un_id_que_existe():
    html = _leer(TEMPLATE_CL)
    ids_html = set(re.findall(r'\bid="([^"]+)"', html))
    usados = set(re.findall(r"getElementById\('([^']+)'\)", _script_app(html)))
    faltan = sorted(usados - ids_html)
    assert not faltan, f"el JavaScript busca ids que el HTML no tiene: {faltan}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node no esta instalado en esta maquina")
def test_el_javascript_de_la_pantalla_es_valido(tmp_path):
    archivo = tmp_path / "app.js"
    archivo.write_text(_script_app(_leer(TEMPLATE_CL)), encoding="utf-8")
    proc = subprocess.run(["node", "--check", str(archivo)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_cada_compra_abre_su_documento():
    """2026-10-29: junto al N° Ref. de cada compra, en la tabla y en la tarjeta, el mismo ícono
    del Centro de Costos abre la factura en SharePoint, en otra pestaña. El enlace lo arma el
    build (DATA.documentos); sin enlace solo se ve el N° Ref."""
    js = _script_app(_leer(TEMPLATE_CL))
    assert "var enlace = DATA.documentos[nRef];" in js
    assert "if (!enlace) return esc(nRef);" in js
    assert '<a class="abrir-archivo-btn" href="\' + esc(enlace) + \'" target="_blank" rel="noopener"' in js
    assert "esc(it.nombre_item) + ' · ' + refConDocumento(it.n_ref)" in js            # tabla de compras
    assert "'</span><span>' + refConDocumento(item.n_ref) + '</span></div>'" in js   # tarjeta sin agrupar
    assert "esc(it.n_ref)" not in js and "esc(item.n_ref)" not in js


def test_la_cotizacion_se_copia_para_el_formulador():
    """2026-10-14: «Copiar para el Formulador» deja en el portapapeles las líneas del carrito con el
    encabezado que reconoce «Pegar desde Excel» del Formulador (js/pegar.js) y el costo NETO
    actualizado por UF; como el resto del carrito, no usa el almacenamiento del navegador."""
    html = _leer(TEMPLATE_CL)
    assert 'id="btnCopiarFormulador"' in html
    assert r"'Descripción\tUnidad\tCantidad\tCosto unitario neto'" in html
    assert "Math.round(l.precio_reajustado_hoy)" in html
    assert "copyFormBtn.disabled = !cart.length" not in html   # se habilita junto con «Copiar tabla para Excel»
    assert "copyFormBtn.disabled = true" in html and "copyFormBtn.disabled = false" in html


def test_la_cotizacion_se_lleva_a_un_proyecto_por_el_portal():
    """2026-10-29: «Llevar a un proyecto…» manda las líneas del carrito al Portal QUEMPIN, que conoce los proyectos
    en formulación y en ejecución: a la ventana de arriba si el Cotizador está abierto dentro del Portal, o al Portal
    recién abierto cuando él avisa que está listo. Van como mensaje entre ventanas: ni por el almacenamiento del
    navegador ni en la dirección (el Portal las valida, ver Visualizador Web/tests/test_portal.py)."""
    html = _leer(TEMPLATE_CL)
    js = _script_app(html)
    assert 'id="btnLlevarProyecto"' in html
    seccion = js[js.index("// ---------- llevar la cotización"):js.index("// ---------- explorador de carpetas")]
    assert "localStorage" not in seccion and "sessionStorage" not in seccion
    assert "postMessage({ tipo: 'quempin-cotizacion', datos: datos }, location.origin)" in seccion
    assert "hasAttribute('data-en-portal')" in seccion
    # Al Portal recién abierto solo se le contesta a él, desde su sitio, cuando avisa que está listo
    assert "ev.source !== p.ventana" in seccion and "ev.origin !== PORTAL_ORIGEN" in seccion and "'quempin-portal-listo'" in seccion
    assert "portal/#/llevar-cotizacion'" in seccion and "window.open(PORTAL_LLEVAR, '_blank')" in seccion
    # El costo es el neto, como «Copiar para el Formulador»; la moneda sale del país del tablero
    assert "Math.round(l.precio_reajustado_hoy * dec) / dec" in seccion and "moneda: peru ? 'PEN' : 'CLP'" in seccion
    assert "llevarBtn.disabled = true" in html and "llevarBtn.disabled = false" in html
