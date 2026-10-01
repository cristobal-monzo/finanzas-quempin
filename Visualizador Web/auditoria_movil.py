# -*- coding: utf-8 -*-
"""Revisa los tableros ya construidos en un telefono emulado.

    py -3.14 "Visualizador Web/auditoria_movil.py"                 # todos, 360/390/768 px
    py -3.14 "Visualizador Web/auditoria_movil.py" cc af --ancho 390
    py -3.14 "Visualizador Web/auditoria_movil.py" --capturas <carpeta>

Por que existe (2026-09-24): Centro de Costos y Cotizador tenian escrito un
diseno movil completo que nunca se activaba en un telefono real, porque les
faltaba <meta name="viewport">; y Analisis Financiero deslizaba de lado tablas
de 9 columnas con el detalle del proyecto cortado. Nada de eso se ve abriendo
el tablero en un escritorio ni achicando la ventana: hace falta emular el
telefono (isMobile), que es lo que hace este script.

Por cada tablero y ancho: pasa la contrasena, recorre las pestanas y una
interaccion tipica (expandir un documento, buscar, abrir un proyecto), y
reporta:
- elementos que se salen de la pantalla (fuera de un contenedor con scroll
  propio, que es lo unico aceptable: el mapa de calor, las subtablas);
- campos de texto con letra < 16 px en anchos de telefono (Safari de iPhone
  hace zoom al tocarlos).

Lee los build/index.html locales (regeneralos antes). Termina con codigo 1 si
encuentra algo. Las capturas son opcionales y van donde se indique: muestran
datos financieros reales, nunca dentro del repo.
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CONTRASENA = "combustion"  # la misma que ya va en claro en cada template

TABLEROS = {
    "cc": "Centro de Costos/Visualizador Web/build/index.html",
    "ccpe": "Peru/Centro de Costos/Visualizador Web/build/index.html",
    "af": "Sistema Analisis Financiero/Visualizador Web/build/index.html",
    "afpe": "Peru/Análisis Financiero/Visualizador Web/build/index.html",
    "cot": "Cotizador Historico/Visualizador Web/build/index.html",
    "cotpe": "Peru/Cotizador Historico/Visualizador Web/build/index.html",
    "hub": "Visualizador Web/index.html",
}

# Elementos mas externos cuyo borde se sale del viewport y que no estan
# dentro de un contenedor con scroll o recorte horizontal propio.
JS_DESBORDES = r"""
() => {
  const W = document.documentElement.clientWidth;
  const recortado = (el) => {
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      if (['auto', 'scroll', 'hidden', 'clip'].includes(getComputedStyle(p).overflowX)) return true;
    }
    return false;
  };
  const sale = (el) => { const r = el.getBoundingClientRect(); return r.right > W + 1 || r.left < -1; };
  const nombre = (el) => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (el.classList.length ? '.' + [...el.classList].slice(0, 2).join('.') : '');
  const out = [];
  for (const el of document.body.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.position === 'fixed') continue;
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || !sale(el) || recortado(el)) continue;
    const p = el.parentElement;
    if (p && p !== document.body && sale(p) && !recortado(p)) continue;
    out.push(nombre(el) + ' (' + Math.round(r.left) + '..' + Math.round(r.right) + ' px)');
  }
  return { ancho: W, doc: document.documentElement.scrollWidth, fuera: out.slice(0, 10) };
}
"""

JS_CAMPOS_CHICOS = r"""
() => [...document.querySelectorAll('input, select, textarea')]
  .filter(e => !['checkbox', 'radio', 'hidden', 'button', 'submit', 'password'].includes(e.type) && !e.readOnly)
  .filter(e => parseFloat(getComputedStyle(e).fontSize) < 16)
  .map(e => (e.id || e.className || e.tagName) + ' ' + getComputedStyle(e).fontSize)
  .filter((x, i, todos) => todos.indexOf(x) === i)
"""


def _pasar_gate(page):
    campo = page.locator("#pwInput")
    if campo.count() and campo.is_visible():
        campo.fill(CONTRASENA)
        campo.press("Enter")
        page.wait_for_timeout(500)


def _escenas(page, clave):
    """Genera (nombre, preparar) de cada vista a revisar en este tablero."""
    pestanas = page.locator(".viz-tab-btn")
    if pestanas.count():
        for i in range(pestanas.count()):
            yield f"pestana {pestanas.nth(i).inner_text().strip()}", lambda i=i: pestanas.nth(i).click()
    else:
        yield "inicio", lambda: None
    if clave in ("cc", "ccpe", "af", "afpe"):
        def expandir():
            if clave in ("af", "afpe"):
                page.locator('.viz-tab-btn[data-tab="tabProyectos"]').click()
            fila = page.locator(".viz-tab-panel.active tr.doc-row, #docTable tr.doc-row").first
            if fila.count():
                fila.click()
        yield "fila expandida", expandir
    if clave in ("cot", "cotpe"):
        def buscar():
            page.fill("#fSearch", "valvula bola 2 pulgadas")
            page.keyboard.press("Enter")
        yield "busqueda", buscar

        def filtros():
            page.fill("#fSearch", "")
            page.click("#btnFiltros")
        yield "panel de filtros", filtros


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("tableros", nargs="*", metavar="tablero", help="subconjunto de: " + ", ".join(TABLEROS))
    ap.add_argument("--ancho", type=int, action="append", help="ancho en px (repetible); por defecto 360, 390 y 768")
    ap.add_argument("--capturas", type=Path, help="carpeta donde guardar una captura por vista (datos reales: fuera del repo)")
    args = ap.parse_args(argv)
    desconocidos = [t for t in args.tableros if t not in TABLEROS]
    if desconocidos:
        ap.error(f"tablero(s) desconocido(s) {desconocidos}; opciones: {', '.join(TABLEROS)}")
    anchos = args.ancho or [360, 390, 768]
    tableros = args.tableros or list(TABLEROS)

    from playwright.sync_api import sync_playwright  # solo quien corre la auditoria la necesita

    problemas = 0
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for ancho in anchos:
            ctx = navegador.new_context(viewport={"width": ancho, "height": 844}, device_scale_factor=2,
                                        is_mobile=True, has_touch=True)
            for clave in tableros:
                ruta = RAIZ / TABLEROS[clave]
                if not ruta.exists():
                    print(f"[--] {clave}: no existe {ruta.relative_to(RAIZ)} (corre su build primero)")
                    continue
                page = ctx.new_page()
                errores_js = []
                page.on("pageerror", lambda e: errores_js.append(str(e)))
                page.goto(ruta.as_uri())
                page.wait_for_timeout(400)
                _pasar_gate(page)
                for escena, preparar in _escenas(page, clave):
                    preparar()
                    page.wait_for_timeout(400)
                    d = page.evaluate(JS_DESBORDES)
                    # El zoom al enfocar es de Safari de iPhone; el iPad pide la
                    # version de escritorio. Los templates lo corrigen bajo 640 px.
                    chicos = page.evaluate(JS_CAMPOS_CHICOS) if ancho <= 640 else []
                    ok = d["ancho"] == ancho and d["doc"] <= ancho and not d["fuera"] and not chicos
                    estado = "ok" if ok else "!!"
                    print(f"[{estado}] {ancho} px  {clave:<6} {escena}")
                    if d["ancho"] != ancho:
                        print(f"       se dibuja a {d['ancho']} px en vez de {ancho}: falta <meta name=\"viewport\">")
                    for f in d["fuera"]:
                        print(f"       se sale de la pantalla: {f}")
                    for c in chicos:
                        print(f"       campo con letra < 16 px (zoom en iPhone): {c}")
                    problemas += not ok
                    if args.capturas:
                        args.capturas.mkdir(parents=True, exist_ok=True)
                        nombre = f"{ancho}_{clave}_{escena.replace(' ', '_')}.png"
                        page.screenshot(path=str(args.capturas / nombre), full_page=True)
                if errores_js:
                    print(f"       errores de JavaScript: {errores_js[:3]}")
                    problemas += 1
                page.close()
            ctx.close()
        navegador.close()
    print(f"\n{problemas} vista(s) con problemas." if problemas else "\nTodo cabe en pantalla.")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raise SystemExit(main())
