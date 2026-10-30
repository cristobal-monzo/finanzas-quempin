# CLAUDE.md — Tablero del Cotizador Histórico

Reglas comunes (marca, teléfono, candado, publicar): [`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md).
Cada parte de la pantalla, el carrito y la exportación en detalle: [`../docs/tablero.md`](../docs/tablero.md). Cómo se llegó
aquí: [`HISTORIA.md`](HISTORIA.md). URL fija: `https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico/`.

## Piezas

- `template.html` (308 KB: Grep, no lo leas entero): estructura, CSS y JS, sin datos.
- `busqueda.js`: el motor del navegador, compartido con Perú; el build lo inyecta en `__CH_BUSQUEDA_JS__`.
- `build_visualizador.py`: lee el Excel (solo lectura) con `cargar_items_detalle`, pide la UF de hoy **una sola vez**
  (`reajustar_todos`), escribe `data/cotizador-historico.json` (auditable) e incrusta todo cifrado en `build/index.html`.
  `data/` y `build/` están gitignorados y no se editan a mano. `driver.py visualizador` lo regenera.

## Reglas

- **La página no calcula ni clasifica**: lee lo que el build dejó en el snapshot (`categoria`, `subcategoria`, `familia`,
  `material`, `medida`, `hoja`, `cotizable`, `atr`, `_bt`, `_bm`, `DATA.categorias`, `DATA.sugerencias`, `DATA.facetas`,
  `DATA.documentos`). Clasificar se cambia en `Sistema/catalogo_taxonomia.py`; encontrar, en `catalogo_busqueda.py`; qué
  filtro va con qué familia, en `catalogo_atributos.FACETAS_POR_FAMILIA`; las marcas, en `MARCAS`, una lista curada.
- **La UF se fija al construir**: la página nunca llama a la red. Refrescarla es correr `driver.py visualizador` y publicar.
  Con respaldo manual, cabecera, KPI y pie agregan «· fuente: <texto>» (`ufFuenteSufijo()`), obligatorio: se debe poder
  distinguir de `mindicador.cl`.
- **Ítem que no calza** (categoría sin sentido, marca poco conocida): en la próxima mantención busca qué es y ajusta el
  catálogo. No es una función de la página publicada.
- **Ningún ítem se oculta** (`ITEMS_VISIBLES` = `DATA.items`). El filtro Categoría usa la taxonomía, no la columna del
  Excel, que trae duplicados por tilde. **Sin clasificar** es un KPI: si crece, faltan reglas.
- **Se compara por hoja** (`buildLeafIndex`, `MARKET_STATS`), con IVA: dos codos de distinta medida nunca se promedian. La
  barra de resultados no muestra un promedio general a propósito.
- **El carrito nunca persiste** (requisito no negociable del usuario): `var cart = []`, solo en memoria; ni `localStorage`,
  ni `sessionStorage`, ni la dirección. `test_template.py` lo vigila. Sí persisten, a propósito, el tema (`ch_viz_theme`),
  la clave recordada (`quempin_viz_clave`) y las búsquedas recientes de la sesión (`ch_viz_recientes` en `sessionStorage`,
  máximo 8).
- **Exportar es copiar, no descargar**: un `<textarea>` que se reconstruye en cada `renderCart()` y «Copiar tabla para
  Excel». Promedio, más barato y su proveedor salen de `MARKET_STATS[hoja]`, contra todas las compras de esa hoja.
- **«Copiar para el Formulador»** (`Descripción · Unidad · Cantidad · Costo neto`, lo que entiende «Pegar desde Excel») y
  **«Llevar a un proyecto…»** (`datosParaProyecto()`, `postMessage` tipo `quempin-cotizacion` al Portal,
  [`portal/docs/llevar-cotizacion.md`](../../Visualizador%20Web/portal/docs/llevar-cotizacion.md)): `test_template.py` los
  exige en los dos países.
- **Factura de una compra**: ícono junto al N° Ref. (`refConDocumento`), un enlace por documento en `DATA.documentos`, con
  la regla única de `../../Visualizador Web/documentos.py`. El carrito no lo lleva: su foco atrapado solo recorre botones y
  campos.
- **Chile y Perú comparten el template línea por línea**, salvo las ~14 líneas del país (título, pestaña activa, moneda,
  pie, UF o soles). `tests/test_template.py` lo exige: edita Chile y aplica igual en Perú.
- El campo de búsqueda usa 16 px: con menos, Safari de iPhone hace zoom al tocarlo. `.viz-compras` fija `color` explícito.

## Fuera de alcance

Consultor en lenguaje natural, persistir el carrito y un `.xlsx` descargable.
