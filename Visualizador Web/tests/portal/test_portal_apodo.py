# -*- coding: utf-8 -*-
"""Portal QUEMPIN: apodo del proyecto, postventas y N° temporales.

Partido de tests/test_portal.py el 2026-11-18; lo común está en portal_comun.py."""
import pytest  # noqa: F401

from portal_comun import *  # noqa: F401,F403


# ---- Apodo del proyecto y postventas (2026-11-06) -----------------------------------------------------------------------
# Pedido del usuario: el apodo de la columna «Apodo» del Análisis Financiero se ve como «270 - Caldera Valdivia»; una
# postventa se asocia a su proyecto original por su N° o su nombre, y queda en «ID o referencia» («164. Talca»).


def test_una_postventa_se_asocia_a_su_proyecto_original_por_su_n(navegador, sitio):
    pagina, errores = _planilla_con_datos(navegador, sitio, usuario="ES")
    pagina.locator("#pqNuevo").click()
    dlg = pagina.locator("#dlgPlanilla")
    assert dlg.locator("#pqOriginalCampo").is_hidden() and dlg.locator("#pqReferenciaCampo").is_visible()
    dlg.locator("#pqTitulo").fill("Cambio de acuastato")
    dlg.locator("#pqCanal").select_option("Postventa")
    assert dlg.locator("#pqOriginalCampo").is_visible() and dlg.locator("#pqReferenciaCampo").is_hidden()
    # Sugiere los requerimientos de la Planilla como «N°. Título»
    assert dlg.locator("#pqProyectos option").count() > 0
    assert all(v.split(". ", 1)[0].isdigit() for v in dlg.locator("#pqProyectos option").evaluate_all("(o) => o.map((x) => x.value)"))
    dlg.locator("#pqOriginal").fill("900")
    dlg.locator("#pqOriginal").press("Tab")
    original = dlg.locator("#pqOriginal").input_value()
    assert original.startswith("900. ") and "liceo" in original.lower()
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    (m,) = _pedidos_planilla(pagina, "nuevo-requerimiento")
    assert m["requerimiento"]["canal"] == "Postventa" and m["requerimiento"]["referencia"] == original
    assert _esquemas().validar_mensaje(m) == []
    # Al abrirla de nuevo, el proyecto original se ve en su campo y no cuenta como cambio
    pagina.locator('#pqFilas tr[data-n="914"] .pq-abrir').click()
    assert dlg.locator("#pqOriginal").input_value() == original and dlg.locator("#pqReferenciaCampo").is_hidden()
    dlg.locator("#pqGuardar").click()
    dlg.wait_for(state="hidden")
    assert _pedidos_planilla(pagina, "editar-requerimiento") == []
    assert not errores
    pagina.context.close()


def test_el_apodo_del_analisis_financiero_da_nombre_al_proyecto(navegador, sitio):
    af = [{"tag": "DEMO", "nombre": "Obra demo", "apodo": "Caldera Demo Valparaíso", "avance": 0.4, "req": "908",
           "venta": {"cargada": True}}]
    pagina, errores = _planilla_con_datos(navegador, sitio, extra={
        "publicado/analisis-financiero.json": _sobre("analisis-financiero", {"proyectos": af})})
    pagina.locator("#pqNuevo").click()
    pagina.locator("#pqCanal").select_option("Postventa")
    valores = pagina.locator("#pqProyectos option").evaluate_all("(o) => o.map((x) => x.value)")
    assert "908. Caldera Demo Valparaíso" in valores
    pagina.locator("#pqOriginal").fill("caldera demo")
    pagina.locator("#pqOriginal").press("Tab")
    assert pagina.locator("#pqOriginal").input_value() == "908. Caldera Demo Valparaíso"
    assert not errores
    pagina.context.close()


def test_un_proyecto_de_gestion_con_n_temporal_se_ve_como_001t_nombre(navegador, sitio):
    """2026-11-09 (pedido del usuario): una carpeta de Gestión sin N° con número temporal («001t») sale en «Proyectos en
    ejecución» con ese N° y su nombre corto, sin los avisos de «falta su N°» ni «no está en la Planilla»."""
    def en_gestion(archivos):
        archivos["publicado/proyectos.json"]["datos"]["gestion"] = [
            {"carpeta": "Rengo Incinerador", "req": "001t", "tag": "001t - Incinerador Rengo"}]
    pagina, errores = _ejecucion_con_datos(navegador, sitio, cambiar=en_gestion)
    vivas = pagina.locator("#ejTarjetas .ej-tarjeta").evaluate_all("bs => bs.map((b) => b.dataset.clave)")
    assert "req-001t" in vivas and "gestion-Rengo Incinerador" not in vivas
    tarjeta = pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-001t"]').inner_text()
    assert "Incinerador Rengo" in tarjeta and "no lleva el N°" not in tarjeta
    pagina.locator('#ejTarjetas .ej-tarjeta[data-clave="req-001t"]').click()
    pagina.locator("#ejProyecto .ej-cab").wait_for()
    assert "no está en la Planilla" not in pagina.locator("#ejProyecto").inner_text()
    assert not errores
