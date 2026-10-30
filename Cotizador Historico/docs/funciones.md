# Cotizador Histórico: funciones de `Sistema/cotizador_historico.py`

Detalle de referencia: léelo solo al tocar esto. Las reglas vigentes están en `../CLAUDE.md`.

- `cargar_items_detalle(ruta_excel=None)` — lee `Detalle`+`Master`, resuelve
  la fecha de cada ítem vía `N° Ref.` e incluye `total_sin_iva`/
  `total_con_iva` de esa misma fila; ítems sin `Master` correspondiente,
  con fecha no parseable, cuya celda `P. Unitario sin IVA` no es un número
  finito, o cuyo `P. Unitario sin IVA` es negativo o **cero**, quedan con
  `excluido_motivo` poblado (`"sin_master"`, `"fecha_invalida"`,
  `"precio_invalido"`, `"precio_negativo"` o `"precio_cero"`) y no entran a
  ninguna búsqueda ni agregación.
  `"precio_cero"` (2026-09-08, pedido explícito del usuario tras ver una
  "Bomba DAB circuladora" figurando en $0 en el cotizador): una línea en $0
  es algo incluido sin cargo dentro de un documento, no una observación de
  precio. **Se filtra el cero exacto, nunca un umbral mínimo**: el ítem más
  barato del catálogo real es un remache de $29 y es legítimo. Revierte la
  decisión del 2026-07-28 que trataba el $0 como caso válido.
  `"precio_negativo"` es la exclusión de Notas de Crédito/devoluciones
  (pedido explícito del usuario 2026-07-28, tras encontrar una devolución
  real —`UMAG-025`— colándose como "el ítem más barato" de una consulta):
  se filtra por signo del precio unitario, no por `Tipo Documento` de
  `Master` (que este módulo no lee), porque una devolución siempre viene
  con precio negativo en `Detalle` independiente de cómo haya quedado
  tipificado el documento. **No agregar más Notas de Crédito al índice de
  este módulo.**
- `buscar_items(items, texto_busqueda, aplicar_medida=True)` — búsqueda por
  relevancia contra todos los campos del ítem (delega en `busqueda.Indice`);
  devuelve `(coincidencias, sugerencias)` con las coincidencias ordenadas de
  más a menos relevante. `aplicar_medida=False` apaga el ranking por medida
  y devuelve las coincidencias de texto puras — lo usa `consultar_item`,
  que necesita **todas** las compras de la familia para poder informar
  cuántas descartó por ser de otro calibre.
- `obtener_valor_uf(fecha, cache_uf)` / `consultar_uf_api(fecha)` — UF
  histórica cacheada localmente; la UF de "hoy" se pide siempre fresca (no
  pasa por el caché de archivo).
- `obtener_uf_hoy(fecha, uf_manual=None, fuente_manual=None)` — la UF de
  "hoy" con fallback (agregado 2026-08-20): intenta `consultar_uf_api`
  primero; si `mindicador.cl` no responde y se pasó un valor manual (ver
  "Precauciones" abajo), lo usa y devuelve `(valor, fuente)`. Sin valor
  manual, relanza `UFNoDisponibleError` igual que siempre. `consultar_item`
  y `build_visualizador.py::extraer_indice_saneado` llaman a esta función,
  no a `consultar_uf_api` directo, para heredar el fallback.
- `tasa_iva_real(total_sin_iva, total_con_iva)` — tasa real de IVA del
  documento original; `1.0` (sin IVA adicional) como respaldo si los
  totales no son numéricos o el total sin IVA es 0.
- `agregar_taxonomia(compra)` / `agrupar_por_hoja(compras)` — agregan la
  clasificación a una compra y agrupan por hoja con su propio promedio,
  rango y dispersión. Se aplican en los dos caminos (dashboard y consulta)
  para que ambos clasifiquen idéntico.
- `consultar_item(texto_busqueda, ruta_excel=None, fecha_hoy=None)` —
  orquesta todo lo anterior y devuelve el resultado completo: compras
  individuales (cada una con su categoría/familia/material/medida/hoja),
  promedio y rango globales, **`grupos`** (una entrada por hoja, con su
  propio promedio: es el número que responde la pregunta real, el global
  mezcla hojas distintas), y sugerencias si no hubo match. Si el texto
  buscado trae una medida (`"codo bronce 1.1/4"`), solo entran las compras
  de esa medida y las demás se cuentan en `descartadas_por_medida`.
