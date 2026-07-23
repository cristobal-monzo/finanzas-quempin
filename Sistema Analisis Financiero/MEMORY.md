# MEMORY.md — Análisis Financiero

Memoria del módulo: decisiones tomadas, historial, y pendientes que dependen del
usuario. El diseño técnico completo vive en el spec (ver `CLAUDE.md`); acá se
registra lo que no está en el código — decisiones de diseño, contexto de
brainstorming — más los pendientes reales que quedan tras la implementación.

## Decisiones tomadas (brainstorming, 2026-07-20)

- **Rol**: el módulo no es solo un pipeline de datos — actúa como analista
  financiero experto (evalúa proyectos, propone/depura KPIs, decide presentación,
  cruza todos los módulos). Ver "Rol de este agente" en `CLAUDE.md`.
- **TAG de proyecto = prefijo de Centro de Costos** (`PREFIJOS_PROYECTO`), no un
  código aparte — evita mantener un mapeo duplicado.
- **Mano de Obra Real queda 100% manual** — hoy no existe esa categoría en los
  datos de Centro de Costos (`categoria_item` solo tiene `Materiales`,
  `Consumibles`, `Equipos-Herramientas`). Se automatiza en una iteración futura
  si aparece una fuente (boletas de honorarios, planillas).
- **Carpetas de proyecto nuevas van en la fuente real** (`Sitio de comunicación -
  Centro de Costos 1/Facturas y Boletas/<Nombre>/`), no en la legado
  (`Centro de Costos/Facturas y Boletas/`) — el usuario confirmó explícitamente
  este punto porque el nombre que él mencionó al pedir la funcionalidad era el
  de la carpeta legado (fácil de confundir, ya pasó antes con Centro de Costos).
- **Disparo encadenado al `run` de Centro de Costos** (no un comando 100% aparte)
  — mismo patrón que el Visualizador Web (paso 12c). Igual queda disponible como
  skill propio para refrescar sin correr todo Centro de Costos.
- **"Rentabilidad por cliente (ROI)" se renombra a "Rentabilidad sobre costo"**
  — el cálculo (Utilidad Neta / Costos Totales) es un markup, no un ROI de
  capital invertido en sentido estricto. Decisión explícita del usuario para
  evitar comparaciones engañosas con un ROI financiero real.
- **Las 4 categorías (Materiales/Equipos/MO/Otros) tienen el mismo tratamiento
  de KPIs** (Productividad + Costo % de venta + Desviación) — el archivo de
  ejemplo original solo cubría Materiales y MO; se extendió por consistencia,
  a pedido del usuario.

## Reorganización de carpetas (2026-07-21)

El usuario pidió que `Análisis Financiero/` (carpeta hermana de esta) quede
**solo** con el Excel de trabajo — todo el código, docs y skill se movieron
acá, a `Sistema Analisis Financiero/`. `RAIZ_DATOS` en
`Sistema/analisis_financiero.py` apunta explícitamente a la carpeta del
Excel; `RAIZ_ANALISIS_FINANCIERO` en
`Centro de Costos/Sistema/auditor_centro_costos.py` apunta a esta carpeta
(la del código). Si en el futuro alguien busca el script "dentro de Análisis
Financiero", no está ahí — está acá.

## Origen del playbook de KPIs

El 2026-07-20 el usuario dejó temporalmente `Ejemplo de indicadores.xlsx` en la
raíz de `Finanzas QUEMPIN/` — un análisis real de 4 proyectos anteriores de la
empresa (con tablas dinámicas y referencias a RRHH/Órdenes de Compra externas).
**Ese archivo se elimina del repo y no se debe buscar ni depender de él** — las
fórmulas extraídas, los 2 bugs encontrados en él (fórmula de "Productividad
Materiales" inconsistente entre proyectos; mezcla de bases IVA entre ingreso y
costos) y las correcciones aplicadas quedan documentadas en el spec
(`docs/superpowers/specs/2026-07-20-analisis-financiero-design.md`, sección
"Playbook de KPIs") y resumidas en `CLAUDE.md`. Si en el futuro aparece un
archivo con nombre parecido, no asumir que es el mismo ni que sigue vigente.

## Estilo visual replicado desde el Excel armado a mano (2026-07-21)

El usuario había formateado a mano solo la hoja "Proyectos" (encabezado en
negrita/centrado/wrap, alto de fila 46.2, relleno de color por grupo de
columna usando 4 colores de theme, formato moneda en columnas de montos).
"Detalle Costos Reales" e "Indicadores" quedaban sin ningún estilo porque se
regeneran 100% en cada corrida. A pedido explícito del usuario ("utiliza un
formato similar para todas las hojas"), se agregó `aplicar_estilo_visual(wb)`
en `Sistema/analisis_financiero.py` que replica ese mismo lenguaje visual en
las 3 hojas y se llama en `ejecutar()` justo antes de `wb.save()`.

- Los 4 colores (`COLOR_IDENTIFICACION`/`COLOR_COSTO_PROYECTADO`/
  `COLOR_COSTO_REAL`/`COLOR_DERIVADO`) son theme colors extraídos del archivo
  original del usuario, reutilizados por grupo semántico de columna en las
  3 hojas (no son una paleta inventada).
- **Bug encontrado al implementar**: `ws.column_dimensions[col].width` NO es
  `None` por defecto en openpyxl -- autovivifica a `13.0` apenas se accede.
  Para detectar "el usuario ya fijó un ancho a mano" hay que revisar
  `columna in ws.column_dimensions` **antes** de tocar esa columna, nunca
  `.width is None` (eso nunca dispara y pisaría anchos por defecto sin
  querer). Ver comentario en el código junto a `aplicar_estilo_visual`.
- Solo se fija ancho de columna si no había uno manual ya guardado; el color
  de encabezado y el formato numérico sí se reaplican siempre (son
  estructurales, no datos del usuario).

## Nota de Proyecto, CLTV de Clientes y Glosario KPIs (brainstorming, 2026-07-21)

- **"Nota" es 100% automática** (no manual, no híbrida) — decisión explícita
  del usuario tras preguntarle las 3 opciones. Escala 0-100, aprobatoria
  ≥55, rentabilidad domina el peso (70% margen neto % vs. objetivo 25%, 30%
  control de desviación total).
- **"CLTV" es sobre CLIENTES, no proveedores** — el usuario pidió
  proveedores primero (confundiendo con el "Proveedor" de Centro de Costos,
  que es un dato de COSTOS/compras) y corrigió a mitad del brainstorming: lo
  que quería era evaluar a quién QUEMPIN le VENDE (clientes), usando el
  archivo de ejemplo AGORA (CLTV por proyecto) como referencia. Si en el
  futuro se pide "evaluar proveedores", es un feature DISTINTO y nuevo, no
  este.
- **"Cliente" se deriva automáticamente + fuzzy-match**, nunca pregunta en
  vivo (el módulo corre encadenado y no bloqueante al `run` de Centro de
  Costos) — coincidencia exacta se asigna sola, similar-no-exacta queda
  "Pendiente de revisión" (mismo patrón rojo/azul marino que Centro de
  Costos), sin parecido se registra como cliente nuevo sin marca.
- **Ambigüedad resuelta del archivo de ejemplo AGORA**: "Vida del cliente" y
  "Frecuencia de compra" del archivo original mezclaban conceptos sin
  fórmula consistente entre filas — este módulo define "Vida del cliente" =
  conteo total de proyectos, "Meses activo" = ventana entre el primer y
  último proyecto (mínimo 1 mes), "Frecuencia" = Vida ÷ (Meses activo ÷ 12).
  Verificado aritméticamente contra los totales del archivo de ejemplo
  (`CLTV = AOV × Frecuencia × Vida × Margen` reproduce el CLTV total como
  promedio simple de los CLTV individuales).
- **Glosario KPIs es una hoja nueva, no comentarios de celda** — a pedido
  explícito del usuario ("que elementos utiliza y en qué se traduce"),
  elegido sobre comentarios de encabezado por ser más legible de corrido y
  más simple de mantener en openpyxl.
- **KPIs adicionales que el usuario mencionó querer agregar después
  quedaron fuera de este spec a propósito** — decisión explícita de cerrar
  este diseño primero en vez de mezclar alcance con features aún sin
  definir.
- **Bug encontrado en el propio test del plan**: el test 5 de
  `test_clientes_pendientes.py` (`test_pendientes_se_acumulan_entre_corridas`)
  seteaba `ws2.cell(..., value=None)` para "simular" un cliente ya
  registrado en otra fila — eso es un no-op (la celda ya era `None`), así
  que el escenario nunca se armaba. Se corrigió para pre-llenar la celda con
  el valor real (`"AGCID Febrero"`), que es lo que el comentario del test ya
  describía.

Diseño completo:
[`docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md`](../docs/superpowers/specs/2026-07-21-analisis-financiero-nota-clientes-design.md)
(ruta relativa a la raíz de `Finanzas QUEMPIN/`).

## Pendientes que dependen del usuario

El script (`Sistema/analisis_financiero.py`, 71 tests), el skill
(`.claude/skills/Registro_Analisis_Financiero/`, comandos
`status`/`run`/`confirmar-cliente`) y el enganche automático al `run` de
Centro de Costos (PASO 12d de `auditor_centro_costos.py`) ya están
implementados — ver detalle e historial de las 12 tareas originales en
`docs/superpowers/plans/2026-07-20-analisis-financiero-implementacion.md` y
de la extensión de Nota/Clientes/Glosario en
`docs/superpowers/plans/2026-07-21-analisis-financiero-nota-clientes-implementacion.md`
(rutas relativas a la raíz de `Finanzas QUEMPIN/`). Lo que queda pendiente:

- `Análisis de Proyectos.xlsx` está vacío — no hay proyectos cargados todavía,
  así que nada de esto se ha ejercitado contra datos reales de QUEMPIN SpA.
- El dashboard HTML (Visualizador Web de este módulo) está fuera de alcance v1
  a propósito — el usuario ya indicó que esa es la forma de presentación a
  mediano plazo, pero no se construye hasta más adelante.
