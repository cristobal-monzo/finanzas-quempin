# -*- coding: utf-8 -*-
"""Portal QUEMPIN: Requerimientos (Planilla de Ingreso) y «Cerrado».

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- Planilla de Ingreso en el portal (2026-10-29) --------------------------------------------------------------------
# Pedido del usuario: la Planilla de Ingreso replicada en el portal, donde desde ahora se ingresan los requerimientos, con
# el Excel de respaldo y los dos al día. La vista lee publicado/requerimientos.json y escribe en el buzón
# («nuevo-requerimiento», «editar-requerimiento»); el Excel lo recibe con Sistema Intercambio/planilla_escritura.py,
# que tiene sus propias pruebas.


def test_al_guardar_uno_nuevo_su_n_se_vuelve_a_calcular(navegador, sitio):
    """2026-11-12: el N° de un requerimiento nuevo se calcula de nuevo al guardar, con lo que llegó al buzón mientras se
    escribía; el formulario abierto un rato no repite un N° que otro ya tomó."""
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="ES")
    pagina.locator("#pqNuevo").click()
    dlg = pagina.locator("#dlgPlanilla")
    assert dlg.locator("#dlgPqTit").inner_text() == "Nuevo requerimiento · N° 914"
    # Mientras tanto, otra persona ingresó el 914 (llega con OneDrive)
    nombre, otro = _pedido(914, "nuevo-requerimiento", minutos=-1, requerimiento={"numero": 914, "titulo": "El de otra persona"},
                           fuente={"herramienta": "portal"}, numeroLibre=True)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {"buzon/" + nombre: otro})
    dlg.locator("#pqTitulo").fill("El mío")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    mio = next(m for m in _pedidos_planilla(pagina, "nuevo-requerimiento") if m["requerimiento"]["titulo"] == "El mío")
    assert mio["requerimiento"]["numero"] == 915
    _esperar_aviso(pagina, "El N° 914 lo tomó otro requerimiento mientras escribías")
    assert not errores
    pagina.context.close()


def test_el_formulador_abre_un_requerimiento_nuevo_con_sus_datos(navegador, sitio):
    """2026-11-12: el Formulador ya no da N°; «Ingresar en Requerimientos» abre …/portal/#/planilla?nuevo=<JSON> (suelto)
    o manda un mensaje (dentro del portal), y el portal abre «Nuevo requerimiento» con esos datos y su propio N°."""
    import urllib.parse
    pagina, errores = _portal_con_datos(navegador, sitio, usuario="ES")
    datos = {"titulo": "Caldera del Formulador", "ubicacion": "Temuco", "referencia": "1234-5-LE26", "canal": "Mercado Público",
             "cierre": "2026-12-01T15:00", "presupuesto": 5950000, "estado": "Inventado", "otro": "no se usa"}
    url = pagina.url.split("#")[0] + "#/planilla?nuevo=" + urllib.parse.quote(json.dumps(datos))
    pagina.goto(url)
    pagina.reload()
    dlg = pagina.locator("#dlgPlanilla")
    dlg.wait_for(timeout=15000)
    assert dlg.locator("#dlgPqTit").inner_text() == "Nuevo requerimiento · N° 914"
    assert dlg.locator("#pqTitulo").input_value() == "Caldera del Formulador"
    assert (dlg.locator("#pqUbicacion").input_value(), dlg.locator("#pqReferencia").input_value()) == ("Temuco", "1234-5-LE26")
    assert dlg.locator("#pqCiF").input_value() == "2026-12-01" and dlg.locator("#pqEstado").input_value() == "Evaluación"
    assert "#/planilla" in pagina.url and "nuevo=" not in pagina.url
    dlg.locator("#pqCancelar").click()
    # Desde un marco del portal (el Formulador adentro): el mensaje hace lo mismo; de otro lado, nada
    pagina.evaluate("""() => window.postMessage({ tipo: 'quempin-nuevo-requerimiento', datos: { titulo: 'Desde la misma ventana' } }, location.origin)""")
    pagina.wait_for_timeout(500)
    assert dlg.is_hidden()
    assert not errores
    pagina.context.close()


def test_se_ve_quien_mas_esta_ingresando_un_requerimiento(navegador, sitio):
    """2026-11-12: con el formulario de uno nuevo abierto, la presencia dice «planilla/nuevo», y se ve a quien más lo
    tiene abierto: los dos podrían tomar el mismo N°."""
    esquemas = _cargar("esquemas_para_test_portal", RAIZ / "Sistema Intercambio" / "esquemas.py")
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="ES")
    pagina.evaluate("(d) => localStorage.setItem('quempin_portal_dispositivo', d)", DISPOSITIVO)
    pagina.reload()
    _menu(pagina, "Requerimientos")
    pagina.locator("#pqFilas tr").first.wait_for()
    pagina.locator("#pqNuevo").click()
    propia = f"publicado/presencia/{DISPOSITIVO}.json"
    sobre = _esperar_archivo(pagina, propia, lambda s: s["datos"]["vista"] == "planilla")
    assert sobre["datos"]["donde"] == "nuevo" and esquemas.validar_publicacion("presencia", sobre) == []
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {"publicado/presencia/otro0001.json": _presencia("otro0001", "NB", "planilla", "nuevo")})
    pagina.wait_for_function("document.getElementById('pqConmigo').textContent === 'NB también está ingresando un requerimiento'", timeout=20000)
    pagina.locator("#pqCancelar").click()
    _esperar_archivo(pagina, propia, lambda s: s["datos"]["vista"] == "")
    assert not errores
    pagina.context.close()


def test_sin_la_carpeta_la_planilla_deja_abrir_el_excel(navegador, sitio):
    """Un teléfono no abre carpetas: la vista dice qué falta y el Excel sigue a mano, como antes del 2026-10-29."""
    pagina, errores = _abrir_portal(navegador, sitio)
    _menu(pagina, "Requerimientos")
    pagina.locator("#pqVacio .cx-enlace", has_text="Abrir el Excel de respaldo").wait_for()
    assert pagina.locator("#pqVacio a.cx-enlace").get_attribute("href").startswith("https://quempinspa2020.sharepoint.com/sites/Licitaciones-Enproceso/")
    assert pagina.locator("#pqContenido").is_hidden()
    assert not errores
    pagina.context.close()


def test_las_columnas_de_la_planilla_son_las_del_esquema_y_del_excel():
    """Las columnas que el portal muestra y deja cambiar son las mismas en el portal, en el esquema editar-requerimiento y en
    planilla_escritura.EDITABLES: las que el equipo llena de verdad (las de 45 % o más vacías quedan solo en el Excel)."""
    portal = texto_portal()
    columnas = re.findall(r"\{ id: '([a-zA-Z]+)', et: '[^']+', clase: 'c-", portal)
    esquema = json.loads((RAIZ / "Sistema Intercambio" / "esquemas" / "mensajes" / "editar-requerimiento.json").read_text(encoding="utf-8"))
    cambios = esquema["properties"]["cambios"]["properties"]
    escritor = (RAIZ / "Sistema Intercambio" / "planilla_escritura.py").read_text(encoding="utf-8")
    editables = re.findall(r'"([a-zA-Z]+)"', re.search(r"^EDITABLES = \(([^)]*)\)", escritor, re.M).group(1))
    # El esquema lleva además los montos que exporta el Formulador: el Portal no los muestra como columnas
    solo_formulador = re.findall(r'"([a-zA-Z]+)"', re.search(r"^SOLO_FORMULADOR = \(([^)]*)\)", escritor, re.M).group(1))
    assert columnas[0] == "numero" and columnas[1:] == [c for c in cambios if c not in solo_formulador] == editables
    for c in solo_formulador:
        assert re.search(c + r": '[^']+'", portal), f"el Portal no le da nombre a {c} en la lista de cambios"
    estados = re.search(r"const PQ_ESTADOS = \[([^\]]*)\]", portal).group(1)
    canales = re.search(r"const PQ_CANALES = \[([^\]]*)\]", portal).group(1)
    assert re.findall(r"'([^']+)'", estados) == cambios["estado"]["enum"]
    assert re.findall(r"'([^']+)'", canales) == cambios["canal"]["enum"]
    nuevo = json.loads((RAIZ / "Sistema Intercambio" / "esquemas" / "mensajes" / "nuevo-requerimiento.json").read_text(encoding="utf-8"))
    assert set(nuevo["properties"]["requerimiento"]["properties"]["canal"]["enum"]) == set(cambios["canal"]["enum"])


def test_la_planilla_muestra_las_columnas_que_se_usan_del_mas_nuevo_al_mas_antiguo(navegador, sitio):
    pagina, errores = _planilla_con_datos(navegador, sitio)
    assert _pestanas(pagina) == ["Inicio", "Requerimientos"]
    assert pagina.locator("iframe").count() == 0
    assert pagina.locator("#pqCabeza th").all_inner_texts() == [
        "N°", "Estado", "Canal", "Capt.", "Eval.", "Título", "Cliente", "Ubicación", "ID o referencia", "Apertura", "Cierre"]
    assert _ns(pagina) == list(range(913, 899, -1))
    fila = pagina.locator('#pqFilas tr[data-n="900"]')
    assert fila.locator("td.c-ubic").inner_text() == "Valparaíso"
    assert fila.locator(".pq-est").inner_text() == "Evaluación"
    assert "faltan 2 días" in fila.locator("td.c-ci").inner_text()
    assert "Al día con el Excel" in pagina.locator("#pqSinc").inner_text()
    assert pagina.locator("#pqCuenta").inner_text() == "14 requerimientos"
    # Por estado (con su cuenta) y buscando
    assert pagina.locator('#pqEstados [data-estado="Ofertado"]').text_content() == "Ofertado 3"
    pagina.locator('#pqEstados [data-estado="Ofertado"]').click()
    assert _ns(pagina) == [913, 906, 905]
    pagina.locator('#pqEstados [data-estado=""]').click()
    pagina.locator("#pqBuscar").fill("calderas glp")
    assert _ns(pagina) == [901] and pagina.locator("#pqCuenta").inner_text() == "1 de 14"
    pagina.locator("#pqBuscar").fill("no existe")
    assert _ns(pagina) == [] and "Ningún requerimiento calza" in pagina.locator("#pqNada").inner_text()
    # El Excel de siempre queda a mano, de respaldo
    assert pagina.locator("#pqExcel").get_attribute("href").startswith("https://quempinspa2020.sharepoint.com/sites/Licitaciones-Enproceso/")
    assert not errores
    pagina.context.close()


def test_un_requerimiento_nuevo_se_ve_al_instante_y_queda_en_el_buzon(navegador, sitio):
    from datetime import date, timedelta
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="ES")
    pagina.locator("#pqNuevo").click()
    dlg = pagina.locator("#dlgPlanilla")
    # El siguiente N° libre: después del mayor de la Planilla, de las carpetas y de las formulaciones
    assert dlg.locator("#dlgPqTit").inner_text() == "Nuevo requerimiento · N° 914"
    assert (dlg.locator("#pqEstado").input_value(), dlg.locator("#pqCanal").input_value(), dlg.locator("#pqCaptador").input_value()) == (
        "Evaluación", "Mercado Público", "ES")
    assert dlg.locator("#pqApF").input_value() == date.today().isoformat()
    dlg.locator("#pqGuardar").click()
    assert "Falta el título" in dlg.locator("#pqPista").inner_text() and dlg.is_visible()
    cierre = (date.today() + timedelta(days=6)).isoformat()
    dlg.locator("#pqTitulo").fill("  Reparación de quemador   hospital ")
    dlg.locator("#pqCanal").select_option("Postventa")
    dlg.locator("#pqUbicacion").fill("Talca")
    dlg.locator("#pqCiF").fill(cierre)
    dlg.locator("#pqCiH").fill("15:00")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "nuevo-requerimiento")
    assert m["requerimiento"] == {"numero": 914, "titulo": "Reparación de quemador hospital", "estado": "Evaluación", "canal": "Postventa",
                                  "captador": "ES", "ubicacion": "Talca", "apertura": date.today().isoformat(), "cierre": cierre + "T15:00"}
    assert m["numeroLibre"] is True and m["fuente"] == {"herramienta": "portal"} and m["origen"]["usuario"] == "ES"
    assert _esquemas().validar_mensaje(m) == []
    # Se ve desde ya, marcado como nuevo, y lo que falta pasar al Excel se dice arriba
    fila = pagina.locator('#pqFilas tr[data-n="914"]')
    assert "pq-nueva" in fila.get_attribute("class") and fila.locator(".pq-nuevo-tag").text_content() == "nuevo"
    assert _ns(pagina)[0] == 914
    assert "1 cambio espera pasar al Excel" in pagina.locator("#pqSinc").inner_text()
    # Recién ingresado ya se puede formular (2026-11-11): abre el Formulador con el diálogo de nuevo proyecto de ese N°
    fila.locator(".pq-form", has_text="Formular").click()
    _esperar(pagina, "formulador", "hash", "#/req/914/crear")
    _menu(pagina, "Requerimientos")
    pagina.locator('#pqFilas tr[data-n="914"]').wait_for()
    # El que sigue ya no repite el N°
    pagina.locator("#pqNuevo").click()
    assert dlg.locator("#dlgPqTit").inner_text() == "Nuevo requerimiento · N° 915"
    dlg.locator("#pqCancelar").click()
    # Lo que todavía no llega al Excel se puede retirar
    pagina.locator("#pqSinc summary").click()
    assert "Por pasar al Excel" in pagina.locator("#pqSinc .pq-cambios").inner_text()
    pagina.locator("#pqSinc .pq-retirar").click()
    pagina.locator('#pqFilas tr[data-n="914"]').wait_for(state="detached")
    assert _pedidos_planilla(pagina, "nuevo-requerimiento") == []
    assert not errores
    pagina.context.close()


def test_el_presupuesto_del_mandante_se_ingresa_y_se_cambia_en_la_planilla(navegador, sitio):
    """La caja «Presupuesto del mandante» (2026-11-11): entero en pesos, opcional; viaja en el mismo mensaje."""
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="ES")
    pagina.locator("#pqNuevo").click()
    dlg = pagina.locator("#dlgPlanilla")
    assert dlg.locator("#pqPresupuesto").input_value() == ""
    dlg.locator("#pqTitulo").fill("Cambio de quemador")
    dlg.locator("#pqPresupuesto").fill("12500000")
    assert dlg.locator("#pqPresupuesto").input_value() == "12.500.000"
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "nuevo-requerimiento")
    assert m["requerimiento"]["presupuesto"] == 12500000
    assert _esquemas().validar_mensaje(m) == []
    # Sin presupuesto no se envía la clave
    pagina.locator("#pqSinc summary").click()
    pagina.locator("#pqSinc .pq-retirar").click()
    pagina.locator("#pqNuevo").click()
    dlg.locator("#pqTitulo").fill("Otro requerimiento")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "nuevo-requerimiento")
    assert "presupuesto" not in m["requerimiento"]
    # En una fila que ya existe viaja como cambio, con lo que se veía
    pagina.locator('#pqFilas tr[data-n="900"] .pq-abrir').click()
    dlg.locator("#pqPresupuesto").fill("8.000.000")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "editar-requerimiento")
    assert m["cambios"] == {"presupuesto": 8000000}
    assert _esquemas().validar_mensaje(m) == []
    assert not errores
    pagina.context.close()


def test_evaluador_y_cliente_se_ingresan_y_se_cambian_en_la_planilla(navegador, sitio):
    """Eval. y Cliente: las dos columnas que la regla del 45 % dejaba fuera y el usuario dejó (2026-10-30)."""
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="ES")
    pagina.locator("#pqNuevo").click()
    dlg = pagina.locator("#dlgPlanilla")
    assert dlg.locator("#pqEvaluador").input_value() == "" and dlg.locator("#pqCliente").input_value() == ""
    dlg.locator("#pqTitulo").fill("Cambio de quemador")
    dlg.locator("#pqEvaluador").fill(" cm ")
    dlg.locator("#pqCliente").fill("Colegio de prueba")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "nuevo-requerimiento")
    assert (m["requerimiento"]["evaluador"], m["requerimiento"]["cliente"]) == ("CM", "Colegio de prueba")
    assert _esquemas().validar_mensaje(m) == []
    fila = pagina.locator('#pqFilas tr[data-n="914"]')
    assert (fila.locator("td.c-eval").inner_text(), fila.locator("td.c-cli").inner_text()) == ("CM", "Colegio de prueba")
    # Se busca por cliente, y lo ya escrito se sugiere al escribir
    pagina.locator("#pqBuscar").fill("colegio de prueba")
    assert _ns(pagina) == [914]
    pagina.locator("#pqBuscar").fill("")
    # En una fila que ya existe viaja solo lo cambiado, con lo que se veía
    pagina.locator('#pqFilas tr[data-n="900"] .pq-abrir').click()
    assert dlg.locator("#pqEvaluador").input_value() == "LC"
    assert dlg.locator("#pqClientes option[value='Colegio de prueba']").count() == 1
    dlg.locator("#pqEvaluador").fill("cm")
    dlg.locator("#pqCliente").fill("Liceo de prueba")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "editar-requerimiento")
    assert m["cambios"] == {"evaluador": "CM", "cliente": "Liceo de prueba"}
    assert m["reemplaza"] == {"evaluador": "LC", "cliente": None}
    assert _esquemas().validar_mensaje(m) == []
    fila = pagina.locator('#pqFilas tr[data-n="900"]')
    assert fila.locator("td.c-eval").inner_text() == "CM" and fila.locator("td.c-cli").inner_text() == "Liceo de prueba"
    assert not errores
    pagina.context.close()


def test_cambiar_un_requerimiento_manda_solo_lo_cambiado_y_lo_que_se_veia(navegador, sitio):
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="LC")
    pagina.locator('#pqFilas tr[data-n="900"] .pq-abrir').click()
    dlg = pagina.locator("#dlgPlanilla")
    assert dlg.locator("#dlgPqTit").inner_text() == "Requerimiento N° 900"
    assert dlg.locator("#pqUbicacion").input_value() == "Valparaíso"
    # El canal está vacío en el Excel: se ve vacío, no como «Mercado Público»
    assert dlg.locator("#pqCanal").input_value() == ""
    # Guardar sin cambiar nada no manda nada
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    assert _pedidos_planilla(pagina, "editar-requerimiento") == []
    # Un clic en cualquier parte de la fila también la abre
    pagina.locator('#pqFilas tr[data-n="900"] td.c-capt').click()
    dlg.locator("#pqEstado").select_option("Ofertado")
    dlg.locator("#pqUbicacion").fill("")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "editar-requerimiento")
    assert m["requerimiento"] == {"numero": 900, "titulo": "LICEO"}
    assert m["cambios"] == {"estado": "Ofertado", "ubicacion": None}
    assert m["reemplaza"] == {"estado": "Evaluación", "ubicacion": "Valparaíso"}
    assert _esquemas().validar_mensaje(m) == []
    fila = pagina.locator('#pqFilas tr[data-n="900"]')
    assert fila.locator(".pq-est").inner_text() == "Ofertado"
    assert fila.locator(".pq-punto").count() == 2
    # Otro cambio a la misma fila parte de lo que ya se cambió
    fila.locator(".pq-abrir").click()
    assert "Estado, Ubicación" in dlg.locator("#pqPista").inner_text()
    dlg.locator("#pqEstado").select_option("Adjudicado")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    segundo = [x for x in _pedidos_planilla(pagina, "editar-requerimiento") if x["id"] != m["id"]][0]
    assert segundo["cambios"] == {"estado": "Adjudicado"} and segundo["reemplaza"] == {"estado": "Ofertado"}
    assert not errores
    pagina.context.close()

# ── «Cerrado» y la carpeta a «0 Proyectos Entregados» (2026-11-09) ──────────


def test_cerrar_un_requerimiento_ofrece_mover_su_carpeta_a_los_entregados(navegador, sitio):
    """Pedido del 2026-11-09: al cambiar un proyecto a «Cerrado» desde el Portal, una opción para llevar su carpeta de
    Gestión de Proyectos a «0 Proyectos Entregados <año>». La mueve el procesador (cierre_entregados.py)."""
    from datetime import date
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="NB", extra=_con_gestion("908. En obra"))
    pagina.locator('#pqFilas tr[data-n="908"] .pq-abrir').click()
    dlg = pagina.locator("#dlgPlanilla")
    assert "Cerrado" in dlg.locator("#pqEstado option").all_inner_texts()
    # Solo aparece al elegir «Cerrado», ya marcada y diciendo qué carpeta y adónde
    assert dlg.locator("#pqMoverCampo").is_hidden()
    dlg.locator("#pqEstado").select_option("Cerrado")
    assert dlg.locator("#pqMoverCampo").is_visible() and dlg.locator("#pqMover").is_checked()
    assert dlg.locator("#pqMoverTxt").inner_text() == f"Mover su carpeta a «0 Proyectos Entregados {date.today().year}»"
    assert "908. En obra" in dlg.locator("#pqMoverDe").inner_text()
    # Volver a otro estado la esconde
    dlg.locator("#pqEstado").select_option("Adjudicado")
    assert dlg.locator("#pqMoverCampo").is_hidden()
    dlg.locator("#pqEstado").select_option("Cerrado")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (editar,) = _pedidos_planilla(pagina, "editar-requerimiento")
    assert editar["cambios"] == {"estado": "Cerrado"} and editar["reemplaza"] == {"estado": "Adjudicado"}
    (mover,) = _mover_pedidos(pagina)
    assert mover["destino"] == "carpetas-proyecto" and mover["estado"] == "Cerrado"
    assert mover["requerimiento"] == {"numero": 908, "titulo": "En obra"} and mover["origen"]["usuario"] == "NB"
    assert _esquemas().validar_mensaje(editar) == [] and _esquemas().validar_mensaje(mover) == []
    # Y una vuelta del procesador, para que no espere la de cada 5 minutos
    assert any(m.get("tipo") == "pedir-vuelta" for m in pagina.evaluate(JS_BUZON).values())
    assert "Su carpeta pasa a «0 Proyectos Entregados»" in pagina.locator("#aviso").inner_text()
    assert pagina.locator('#pqFilas tr[data-n="908"] .pq-est').inner_text() == "Cerrado"
    assert not errores
    pagina.context.close()


def test_cerrar_sin_mover_la_carpeta_o_sin_carpeta_en_gestion(navegador, sitio):
    pagina, errores = _planilla_con_datos(navegador, sitio, extra=_con_gestion("908. En obra"))
    dlg = pagina.locator("#dlgPlanilla")
    # Desmarcada: solo cambia el estado
    pagina.locator('#pqFilas tr[data-n="908"] .pq-abrir').click()
    dlg.locator("#pqEstado").select_option("Cerrado")
    dlg.locator("#pqMover").uncheck()
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    assert len(_pedidos_planilla(pagina, "editar-requerimiento")) == 1 and _mover_pedidos(pagina) == []
    # Sin carpeta con su N° en Gestión: la opción se ve, pero no se puede marcar
    pagina.locator('#pqFilas tr[data-n="907"] .pq-abrir').click()
    dlg.locator("#pqEstado").select_option("Cerrado")
    assert dlg.locator("#pqMoverCampo").is_visible() and dlg.locator("#pqMover").is_disabled()
    assert not dlg.locator("#pqMover").is_checked()
    assert "Sin carpeta con el N° 907" in dlg.locator("#pqMoverTxt").inner_text()
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    assert _mover_pedidos(pagina) == []
    assert not errores
    pagina.context.close()


def test_un_requerimiento_ya_cerrado_con_su_carpeta_en_gestion_no_la_mueve_sin_pedirlo(navegador, sitio):
    """Abrir una fila ya «Cerrado» para cambiar otra cosa no mueve nada; la opción está, sin marcar."""
    pagina, errores = _planilla_con_datos(navegador, sitio, extra=_con_gestion("908. En obra", estados={908: "Cerrado"}))
    dlg = pagina.locator("#dlgPlanilla")
    pagina.locator('#pqFilas tr[data-n="908"] .pq-abrir').click()
    assert dlg.locator("#pqMoverCampo").is_visible() and not dlg.locator("#pqMover").is_checked()
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    assert _mover_pedidos(pagina) == [] and "No cambiaste nada" in pagina.locator("#aviso").inner_text()
    # Marcada sin cambiar nada más: solo el pedido de mover
    pagina.locator('#pqFilas tr[data-n="908"] .pq-abrir').click()
    dlg.locator("#pqMover").check()
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    assert len(_mover_pedidos(pagina)) == 1 and _pedidos_planilla(pagina, "editar-requerimiento") == []
    assert not errores
    pagina.context.close()


def test_marcar_cerrado_desde_proyectos_en_ejecucion(navegador, sitio):
    """Pedido del 2026-11-10: en «Proyectos en ejecución» también se cambia el estado a «Cerrado», con la misma opción de
    llevar su carpeta a «0 Proyectos Entregados» que en Requerimientos."""
    pagina, errores = _ejecucion_con_datos(navegador, sitio, usuario="NB", proyecto="req-908", cambiar=_gestion_908)
    pagina.locator('#ejProyecto .ej-cab button[data-foco="marcar-cerrado"]').click()
    dlg = pagina.locator("#dlgEjCerrar")
    assert "a «Cerrado»" in dlg.locator("#ejCerPista").inner_text()
    assert dlg.locator("#ejCerMover").is_checked() and "908. En obra" in dlg.locator("#ejCerMoverDe").inner_text()
    dlg.locator("#ejCerGuardar").click()
    dlg.wait_for(state="hidden")
    _esperar_aviso(pagina, "N° 908 marcado «Cerrado»")
    (editar,) = _pedidos_planilla(pagina, "editar-requerimiento")
    assert editar["requerimiento"]["numero"] == 908 and editar["cambios"] == {"estado": "Cerrado"}
    assert editar["origen"]["usuario"] == "NB" and _esquemas().validar_mensaje(editar) == []
    (mover,) = _mover_pedidos(pagina)
    assert mover["requerimiento"]["numero"] == 908 and _esquemas().validar_mensaje(mover) == []
    assert any(m.get("tipo") == "pedir-vuelta" for m in pagina.evaluate(JS_BUZON).values())
    # Ya «Cerrado» (el pedido espera en el buzón): el botón solo ofrece llevar la carpeta
    assert pagina.locator('#ejProyecto .ej-cab button[data-foco="marcar-cerrado"]').inner_text() == "Llevar su carpeta a entregados"
    assert not errores
    pagina.context.close()


def test_marcar_cerrado_sin_mover_y_ya_cerrado_solo_mueve(navegador, sitio):
    pagina, errores = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=_gestion_908)
    pagina.locator('#ejProyecto .ej-cab button[data-foco="marcar-cerrado"]').click()
    pagina.locator("#ejCerMover").uncheck()
    pagina.locator("#ejCerGuardar").click()
    _esperar_aviso(pagina, "N° 908 marcado «Cerrado»")
    assert len(_pedidos_planilla(pagina, "editar-requerimiento")) == 1 and _mover_pedidos(pagina) == []
    pagina.context.close()
    # Ya «Cerrado» en la Planilla con su carpeta en Gestión: solo el pedido de mover
    pagina, errores2 = _ejecucion_con_datos(navegador, sitio, proyecto="req-908", cambiar=lambda a: _gestion_908(a, "Cerrado"))
    pagina.locator('#ejProyecto .ej-cab button[data-foco="marcar-cerrado"]').click()
    assert pagina.locator("#ejCerMover").is_checked() and pagina.locator("#ejCerMover").is_disabled()
    pagina.locator("#ejCerGuardar").click()
    _esperar_aviso(pagina, "N° 908:")
    assert len(_mover_pedidos(pagina)) == 1 and _pedidos_planilla(pagina, "editar-requerimiento") == []
    assert not errores and not errores2
    pagina.context.close()


def test_cerrado_en_la_planilla_va_al_cierre_del_recorrido(navegador, sitio):
    """908 tiene ficha en el Análisis (40 % de avance): «Cerrado» en la Planilla lo lleva al «Cierre», sin el aviso de que
    corresponde «Adjudicado», y pide dejar el avance en 100 %."""
    pagina, errores = _portal_con_datos(navegador, sitio)
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, _con_gestion(estados={908: "Cerrado"}))
    pagina.reload()
    pagina.locator("#vistaInicio").wait_for()
    _menu(pagina, "Recorrido de proyectos")
    pagina.locator("#rcTablero .rc-tarjeta").first.wait_for()
    columnas = pagina.evaluate(JS_COLUMNAS)
    assert "req-908" in columnas["cierre"] and "req-908" not in columnas["ejecucion"]
    tarjeta = pagina.locator('#rcTablero .rc-tarjeta[data-clave="req-908"]')
    tarjeta.click()
    texto_ficha = pagina.locator("body").inner_text()
    assert "corresponde «Adjudicado»" not in texto_ficha
    assert "40 % de avance" in texto_ficha
    assert not errores
    pagina.context.close()


def test_la_planilla_muestra_lo_que_espera_de_todo_el_equipo_y_lo_que_no_se_pudo(navegador, sitio):
    from datetime import date
    mes = date.today().strftime("%Y-%m")
    n1, editar = _pedido(905, "editar-requerimiento", requerimiento={"numero": 905, "titulo": "Oferta esperando"},
                         cambios={"referencia": "1-1-LE26"}, reemplaza={"referencia": None})
    n2, formulador = _pedido(920, "nuevo-requerimiento", herramienta="formulador", requerimiento={"numero": 920, "titulo": "Del Formulador"},
                             fuente={"herramienta": "formulador", "uid": "f920"})
    n3, choque = _pedido(911, "nuevo-requerimiento", minutos=-3, requerimiento={"numero": 911, "titulo": "Otro con el mismo N°"},
                         fuente={"herramienta": "portal"}, numeroLibre=True)
    n4, rechazado = _pedido(907, "editar-requerimiento", minutos=-60, requerimiento={"numero": 907, "titulo": "Adjudicada sin ficha"},
                            cambios={"estado": "Descartado"})
    rechazado["resultado"] = {"estado": "rechazado", "fecha": date.today().isoformat(), "detalle": ["El N° 907 no está en la planilla."]}
    pagina, errores = _planilla_con_datos(navegador, sitio, extra={
        "buzon/" + n1: editar, "buzon/" + n2: formulador, "buzon/" + n3: choque, f"procesado/{mes}/" + n4: rechazado})
    assert pagina.locator('#pqFilas tr[data-n="905"] td.c-ref').inner_text() == "1-1-LE26"
    assert pagina.locator('#pqFilas tr[data-n="905"] td.c-ref .pq-punto').count() == 1
    assert "pq-nueva" in pagina.locator('#pqFilas tr[data-n="920"]').get_attribute("class")
    # Un N° que ya tiene otra fila: las dos se ven, y la nueva dice que tomará el siguiente
    assert pagina.locator('#pqFilas tr[data-n="911"]').count() == 2
    assert "ya es «Descartada»" in pagina.locator('#pqFilas tr[data-n="911"].pq-nueva .pq-choque').inner_text()
    # Con choque no se ofrece formular: su N° va a cambiar
    assert pagina.locator('#pqFilas tr[data-n="911"].pq-nueva .pq-form').count() == 0
    assert "3 cambios esperan pasar al Excel" in pagina.locator("#pqSinc").inner_text()
    pagina.locator("#pqSinc .pq-avisos").wait_for()
    avisos = pagina.locator("#pqSinc .pq-avisos").inner_text()
    assert "N° 907" in avisos and "no se pudo" in avisos
    # El siguiente N° salta también lo que espera
    pagina.locator("#pqNuevo").click()
    assert pagina.locator("#dlgPqTit").inner_text() == "Nuevo requerimiento · N° 921"
    pagina.locator("#pqCancelar").click()
    # Lo que espera desde hace más de media hora se avisa: ¿está encendido el computador?
    n5, viejo = _pedido(906, "editar-requerimiento", minutos=-90, requerimiento={"numero": 906}, cambios={"canal": "Otro"})
    pagina.evaluate(JS_ESCRIBIR_INTERCAMBIO, {"buzon/" + n5: viejo})
    pagina.locator("#pqActualizar").click()
    pagina.locator('#pqSinc[data-nivel="warn"]').wait_for()
    assert "computador del procesador" in pagina.locator("#pqSinc").inner_text()
    assert not errores
    pagina.context.close()


def test_la_planilla_dice_que_filas_del_excel_no_se_ven(navegador, sitio):
    """Un N° repetido o una fila sin N° no llegan a las herramientas: una réplica no puede esconderlas en silencio."""
    datos = _intercambio_de_prueba()
    sobre = datos["publicado/requerimientos.json"]
    sobre["datos"]["avisos"] = ["El N° 905 aparece más de una vez en la planilla: se usa la primera fila; la fila 40 «Repetida» no se ve en las herramientas.",
                                "La fila 1995 «Sin número» no tiene N° en la planilla: no se ve en las herramientas."]
    pagina, errores = _planilla_con_datos(navegador, sitio, extra={"publicado/requerimientos.json": sobre})
    fuera = pagina.locator("#pqSinc .pq-fuera")
    assert fuera.locator("summary").inner_text() == "2 filas del Excel no se ven aquí: les falta un N° propio"
    fuera.locator("summary").click()
    assert "la fila 40 «Repetida»" in fuera.inner_text() and "La fila 1995 «Sin número»" in fuera.inner_text()
    assert not errores
    pagina.context.close()


def test_el_recorrido_lleva_a_la_fila_de_la_planilla(navegador, sitio):
    """«Actualizar la Planilla» del Recorrido (antes abría el Excel) abre la fila de ese N° en la Planilla del portal."""
    pagina, errores = _recorrido_con_datos(navegador, sitio)
    tarjeta = pagina.locator('.rc-tarjeta[data-clave="req-912"]')
    assert tarjeta.locator(".rc-accion").inner_text() == "Actualizar Requerimientos"
    tarjeta.locator(".rc-accion").click()
    dlg = pagina.locator("#dlgPlanilla")
    dlg.wait_for()
    assert dlg.locator("#dlgPqTit").inner_text() == "Requerimiento N° 912"
    assert dlg.locator("#pqTitulo").input_value() == "Cerró sin oferta"
    assert _pestanas(pagina) == ["Inicio", "Recorrido", "Requerimientos"]
    dlg.locator("#pqEstado").select_option("Descartado")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    # De vuelta en el Recorrido, ya no pide nada: quedó descartado
    pagina.locator("#pestanas .ir", has_text="Recorrido").click()
    assert pagina.locator('.rc-tarjeta[data-clave="req-912"]').count() == 0
    assert not errores
    pagina.context.close()


def test_la_planilla_avisa_un_id_repetido_copia_el_id_y_alterna_el_tono_de_las_filas(navegador, sitio):
    """Observaciones del equipo (2026-11-20 y 2026-11-23): un ID que ya tiene otro requerimiento se avisa una vez antes
    de guardar (el segundo «Guardar» lo deja pasar: puede ser una licitación que se repostula); el ID se copia con un
    clic sin abrir la fila; y las filas van en dos tonos."""
    base = _intercambio_de_prueba()
    reqs = base["publicado/requerimientos.json"]
    for r in reqs["datos"]["requerimientos"]:
        if r["numero"] == 905:
            r["referencia"] = "1-1-LE26"
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="ES", extra={"publicado/requerimientos.json": reqs})
    pagina.context.grant_permissions(["clipboard-read", "clipboard-write"])
    # Dos tonos: una fila par no tiene el mismo fondo que la impar
    fondos = pagina.evaluate("""() => [...document.querySelectorAll('#pqFilas > tr')].slice(0, 2)
        .map((tr) => getComputedStyle(tr).backgroundColor)""")
    assert fondos[0] != fondos[1], fondos
    # Copiar el ID: no abre el requerimiento
    fila = pagina.locator('#pqFilas tr[data-n="905"]')
    fila.locator(".pq-copiar").click()
    _esperar_aviso(pagina, "ID 1-1-LE26 copiado")
    assert not pagina.locator("#dlgPlanilla").is_visible()
    assert pagina.evaluate("navigator.clipboard.readText()") == "1-1-LE26"
    # Un requerimiento nuevo con el mismo ID (con otras mayúsculas y espacios): avisa y no guarda
    pagina.locator("#pqNuevo").click()
    dlg = pagina.locator("#dlgPlanilla")
    dlg.locator("#pqTitulo").fill("La misma licitación")
    dlg.locator("#pqReferencia").fill(" 1-1-le26 ")
    dlg.locator("#pqGuardar").click()
    pista = dlg.locator("#pqPista").inner_text()
    assert "ya está en el N° 905" in pista and "Oferta esperando" in pista and dlg.is_visible()
    assert _pedidos_planilla(pagina, "nuevo-requerimiento") == []
    # El segundo «Guardar» lo deja pasar
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "nuevo-requerimiento")
    assert m["requerimiento"]["referencia"] == "1-1-le26"
    # Cambiar otro campo de uno que ya tiene ese ID no vuelve a avisar
    pagina.locator('#pqFilas tr[data-n="905"] .pq-abrir').click()
    dlg.locator("#pqUbicacion").fill("Temuco")
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    assert not errores
    pagina.context.close()


@pytest.mark.parametrize("ancho", [360, 390, 820])
def test_la_planilla_cabe_sin_desbordes(navegador, sitio, ancho):
    movil = ancho < 760
    pagina, errores = _planilla_con_datos(navegador, sitio, ancho=ancho, alto=844, movil=movil)
    derecha = """() => Math.max(...[...document.querySelectorAll('#vistaPlanilla *')]
        .filter((e) => e.getClientRects().length).map((e) => e.getBoundingClientRect().right))"""
    assert pagina.evaluate(derecha) <= ancho + 0.5
    # En lo angosto, cada fila es una tarjeta con sus datos nombrados
    assert pagina.locator("#pqTabla thead").is_hidden()
    assert pagina.locator('#pqFilas tr[data-n="900"] td.c-ubic').get_attribute("data-et") == "Ubicación"
    pagina.locator("#pqNuevo").click()
    assert pagina.evaluate(derecha.replace("#vistaPlanilla", "#dlgPlanilla")) <= ancho + 0.5
    if movil:
        chicos = pagina.evaluate("""() => [...document.querySelectorAll('#dlgPlanilla input, #dlgPlanilla select')]
            .filter((e) => e.getClientRects().length && parseFloat(getComputedStyle(e).fontSize) < 16).map((e) => e.id)""")
        assert chicos == []
    assert not errores
    pagina.context.close()
