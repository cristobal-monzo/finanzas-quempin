# CLAUDE.md — Tablero de Análisis Financiero

Reglas comunes (marca, teléfono, candado, publicar): [`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md).
Cada pestaña, la ficha del proyecto y las auditorías en detalle: [`../docs/tablero.md`](../docs/tablero.md). URL fija:
`https://cristobal-monzo.github.io/finanzas-quempin/analisis-financiero/`.

## Piezas

- `template.html` (389 KB: Grep, no lo leas entero): estructura, CSS y JS, sin datos. **Chile y Perú usan el mismo**
  (`build(pais)`, `PAISES_VIZ`); `Peru/Análisis Financiero/Visualizador Web/build_visualizador.py` es un envoltorio.
- `ingreso.js`: la pestaña «Ingresar datos». La inserta el build, junto con `Sistema Intercambio/esquemas.js` y
  `pulso.js` (los originales); funciona en Node (`tests/test_ingreso.py`).
- `build_visualizador.py`: export saneado + build. `driver.py visualizador` regenera todo (ya encadenado en `ejecutar()`).
- `data/` y `build/`: gitignored. Se publica con `Visualizador Web/publicar.py`: los PDF van cifrados aparte, en
  `build/reportes/<huella>.json` (`escribir_reportes_cifrados`), y se bajan al abrirlos.

## Reglas

- **El tablero no calcula**: cada KPI sale de `af.calcular_kpis_proyecto()` y `af.calcular_clientes()`, desde las columnas
  manuales y «Detalle Costos Reales»; **nunca lee celdas de fórmula** ni copia umbrales al JS. Un número nuevo se calcula
  en `analisis_financiero.py`. Vacío = `None` → «—», nunca un 0.
- **Proyectos incompletos** (`af.CAMPOS_MANUALES_REQUERIDOS`): no reciben KPIs y aparecen en el aviso de pendientes con
  qué les falta (`af.campos_faltantes`), ordenados por venta. Gastos Generales nunca es pendiente. Los clientes suman solo
  sus proyectos completos.
- **Una clave mal escrita no da error: deja una cifra en «—»**. Por eso
  `test_la_ficha_del_proyecto_solo_lee_claves_que_trae_el_snapshot`; agrega al snapshot lo que la ficha lea.
- **Colores de la ficha**: gris = costo, naranjo = margen, rojo = lo que pasa del presupuesto o de la venta (variables
  `--ficha-*`, validadas con la skill `dataviz`). El color solo va donde hay un juicio.
- Textos de las «i»: `GLOSARIO_KPIS` en el template; los números salen de `umbrales` del snapshot.

## Pestañas

**Resumen** (abre aquí: qué mirar primero y dispersión margen contra desviación), **Presupuesto vs Real** (sesgo por
categoría y mapa de calor: sirve para cotizar mejor), **Proyectos** (filtros, orden por encabezado, ficha al abrir una
fila), **Clientes** (margen acumulado, recompra, concentración), **Categoría** e **Ingresar datos**.

## «Ingresar datos»: la única pestaña que escribe

Deja un mensaje `datos-proyecto` por proyecto en `buzon/` (solo Chile; en Perú `ingreso` es `None` y no aparece). Canal:
[`../docs/intercambio.md`](../docs/intercambio.md).

- Campos, tipos y orden llegan en `DATA.ingreso` (`pf.CAMPOS_TABLERO`): **el template no repite ninguna columna**, un test
  lo exige.
- La carpeta conectada es la del Formulador (IndexedDB `qpn-intercambio`, mismo sitio). Sin Chrome/Edge de escritorio,
  «Descargar» baja los archivos para dejarlos en `buzon/`.
- `localStorage`: `af_ingreso_borrador_v1`, `af_ingreso_envios_v1` (últimos 60), `af_ingreso_filtro`, `af_ingreso_como`.
  Autor: `quempin_usuario` si este navegador no tenía nombre.
- «Lo que se vio» (`reemplaza`) es lo del snapshot, salvo que este navegador ya haya enviado algo más nuevo: así un segundo
  cambio se apoya en el primero.
- El tablero publicado no cambia solo: el procesador aplica el envío en ≤ 2 horas, y Pages se actualiza al publicar.
- **Los textos no nombran `/Actualizar_Finanzas` ni `driver.py`** (un test lo exige): eso es de quien mantiene el sistema.

## Enlaces

Entrada `#proyecto=<TAG>` (`abrirDesdeEnlace`): abre la ficha; si no está en el análisis, «Ingresar datos» con el proyecto
buscado; si no, un aviso. Salida «Ver la formulación ↗» (`enlaceFormuladorHtml`): `#/req/<N°>` o `#/tag/<TAG>` en el
Formulador. Pruebas: `tests/test_build_visualizador.py`, `tests/test_ingreso.py`.
