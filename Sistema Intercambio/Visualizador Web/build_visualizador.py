# -*- coding: utf-8 -*-
"""
build_visualizador.py -- genera el tablero web de Oportunidades en Mercado
Público (solo Chile; 2026-10-13).

Pide la evaluación a oportunidades.revisar() -- la misma que publica
oportunidades.json para las demás herramientas -- y la inyecta en
template.html junto con las fuentes Lato y el logo, que se toman del módulo
de marca (brand.py) en vez de duplicarlos aquí. Los datos van cifrados con la
contraseña de los tableros (Visualizador Web/candado.py), como los demás.

Si Mercado Público no responde (sin ticket, sin red), arma el tablero con la
última evaluación guardada en la caché, lo dice en sus avisos y termina con
código 3: la tarea diaria (Actualizar_Finanzas/driver.py oportunidades) no
publica ese tablero y deja el anterior; la corrida semanal sí lo publica, con
el aviso a la vista.

Salidas (gitignoreadas: llevan la historia de la Planilla de Ingreso):
  data/oportunidades.json   snapshot de lo inyectado
  build/index.html          la página autocontenida

Uso:  py -3.14 build_visualizador.py [--sin-red]
      --sin-red  no consulta la API: evalúa con la caché (para cambiar solo la página)
Código de salida: 0 al día, 3 armado con la caché porque Mercado Público no
respondió, 1 error (sin contraseña de los tableros).
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent                 # Sistema Intercambio/Visualizador Web
RAIZ_INTERCAMBIO = RAIZ.parent
RAIZ_FINANZAS = RAIZ.parents[1]
sys.path.insert(0, str(RAIZ_FINANZAS / "Visualizador Web"))
sys.path.insert(0, str(RAIZ_FINANZAS / "Sistema Analisis Financiero" / "Reportes"))
sys.path.insert(0, str(RAIZ_INTERCAMBIO))
import brand  # noqa: E402
import candado  # noqa: E402  (los datos van cifrados con la contraseña de los tableros)
import mercado_publico  # noqa: E402
import oportunidades  # noqa: E402

RUTA_TEMPLATE = RAIZ / "template.html"
RUTA_DATA_JSON = RAIZ / "data" / "oportunidades.json"
RUTA_BUILD_HTML = RAIZ / "build" / "index.html"
MARCADORES = ("__OP_FUENTES__", "__OP_LOGO__", "__OP_DATA_B64__")
CODIGO_CON_CACHE = 3


def renderizar(datos: dict, template: str | None = None) -> str:
    template = RUTA_TEMPLATE.read_text(encoding="utf-8") if template is None else template
    for marcador in MARCADORES:
        if marcador not in template:
            raise ValueError(f"Falta {marcador} en template.html")
    html = (template.replace("__OP_FUENTES__", brand.cargar_font_face_lato())
            .replace("__OP_LOGO__", brand.cargar_logo_base64()))
    return candado.incrustar(html, "__OP_DATA_B64__", json.dumps(datos, ensure_ascii=False))


def _escribir(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(texto, encoding="utf-8")
    temporal.replace(ruta)


def evaluar(sin_red: bool = False, raiz=None) -> tuple[dict, int, bool]:
    """(datos, consultas a la API, al día). Sin respuesta de Mercado Público,
    la última evaluación guardada, con el aviso, y al día = False."""
    raiz = oportunidades._raiz() if raiz is None else raiz
    try:
        r = oportunidades.revisar(raiz, enviar=False, sin_red=sin_red)
        al_dia = True
    except mercado_publico.ErrorMercadoPublico as error:
        r = oportunidades.revisar(raiz, enviar=False, sin_red=True)
        r["datos"]["avisos"].insert(0, f"No se pudo consultar Mercado Público ({error}): se muestra la última evaluación guardada.")
        al_dia = False
    return r["datos"], r["llamadas"], al_dia


def construir(datos: dict | None = None, sin_red: bool = False,
              ruta_json: Path = RUTA_DATA_JSON, ruta_html: Path = RUTA_BUILD_HTML) -> Path:
    if datos is None:
        datos, _, _ = evaluar(sin_red)
    _escribir(ruta_json, json.dumps(datos, ensure_ascii=False, indent=1))
    _escribir(ruta_html, renderizar(datos))
    return ruta_html


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        datos, llamadas, al_dia = evaluar(sin_red="--sin-red" in argv)
        ruta = construir(datos)
    except candado.SinContrasena as e:
        print(f"[ERROR] {e}")
        return 1
    cuenta = {c: sum(1 for o in datos["oportunidades"] if o["categoria"] == c) for c in ("prioritaria", "buena")}
    print(f"[{'OK' if al_dia else 'CON CACHÉ'}] Tablero de Oportunidades: {ruta}")
    print(f"     {len(datos['oportunidades'])} evaluadas: {cuenta['prioritaria']} prioritaria(s), {cuenta['buena']} buena(s); "
          f"{llamadas} consulta(s) a Mercado Público.")
    for aviso in datos.get("avisos") or []:
        print(f"     [AVISO] {aviso}")
    return 0 if al_dia else CODIGO_CON_CACHE


if __name__ == "__main__":
    raise SystemExit(main())
