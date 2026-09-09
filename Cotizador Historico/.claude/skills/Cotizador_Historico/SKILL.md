---
name: Cotizador_Historico
description: Usar cuando el usuario escribe "/Cotizador_Historico" explícitamente. Si en cambio pregunta en lenguaje natural (sin el "/") cuánto debería costar algo hoy, pide una cotización aproximada basada en compras anteriores, o quiere saber el precio histórico reajustado de un ítem ya comprado, pedir confirmación antes de invocarlo (ver CLAUDE.md raíz § Invocación de skills; aplica también siendo de solo lectura) -- nunca activarlo automático. Estima el costo actual de un ítem (material, equipo, herramienta) a partir de sus compras históricas en Centro de Costos, reajustando el precio por la variación de la UF entre la fecha de compra y hoy.
---

# Cotizador Historico

Herramienta de línea de comandos (Python + openpyxl + `mindicador.cl`), de
**solo lectura** sobre `Centro de Costos/Excel/Centro de Costos.xlsx` — nunca
lo escribe. Todas las rutas de este documento son relativas a la raíz del
módulo (`Cotizador Historico/`), no a esta carpeta de skill. El driver vive
en `.claude/skills/Cotizador_Historico/driver.py`.

Ver `../../CLAUDE.md` para el diseño completo (fuente de datos, algoritmo de
búsqueda, reajuste por UF, alcance v1).

## Prerequisitos

```
python --version      # mismo interprete que usa Centro de Costos
python -c "import openpyxl; print(openpyxl.__version__)"   # 3.1.5
```

Requiere conexión a internet para consultar `mindicador.cl` en fechas que no
estén todavía en `Sistema/uf_cache.json` (la UF de "hoy" siempre se pide
fresca, nunca se cachea entre corridas).

## Comandos

**`status`** — solo lectura: cuenta ítems indexables en `Detalle`, cuántos
quedan excluidos (sin fecha resoluble vía `Master`, sin precio unitario
válido, por ser Notas de Crédito/devoluciones con precio negativo, o por
venir en $0 en el documento — ver "Gotchas"), cuántas fechas hay en el caché
de UF, y prueba la conexión a `mindicador.cl`.

```
python ".claude/skills/Cotizador_Historico/driver.py" status
```

**`consultar "<texto>"`** — busca el texto contra `Nombre Ítem`/`Descripción`
de `Detalle` (búsqueda difusa) y muestra una tabla con cada compra
encontrada (fecha, N° Ref., precio original sin IVA, ajuste actual sin IVA
y ajuste actual con IVA — este último con la tasa real de IVA del
documento original, no 19% fijo, igual que hace Centro de Costos), más una
fila de promedio y el rango (sin IVA).

Desde 2026-09-08 muestra además una **tabla por hoja** (familia + material +
medida) cuando la búsqueda cae en más de una: ese es el número que responde
la pregunta real, porque el promedio global mezcla productos distintos. Y si
el texto buscado trae una medida, **filtra a esa medida**:

```
python ".claude/skills/Cotizador_Historico/driver.py" consultar "codo bronce 1.1/4"
```

```
Medida detectada en la consulta: 1.1/4" -- solo se muestran compras de esa
medida (46 compra(s) de otra medida quedaron fuera).
```

```
python ".claude/skills/Cotizador_Historico/driver.py" consultar "taladro"
```

Salida esperada (estructura estable; los números cambian según los datos
reales de Centro de Costos y la UF del día):

```
Compras encontradas para "taladro":

| Fecha | N° Ref. | Precio original (sin IVA) | Ajuste actual sin IVA | Ajuste actual con IVA |
|---|---|---|---|---|
| 2026-03-10 | UMAG-014 | $90,000 | $94,200 | $112,098 |
| 2026-05-02 | UMAG-021 | $85,000 | $87,100 | $103,649 |
| **Promedio** | | | $90,650 | $107,874 |

Rango (sin IVA): $87,100 - $94,200
```

Si no hay match: `No se encontraron compras para "<texto>".`, con una lista
de sugerencias si hubo coincidencias de similitud baja.

**`visualizador`** — regenera el visualizador web (`Visualizador Web/build/index.html`)
a partir de `Centro de Costos.xlsx`: indexa todo el catálogo, pide la UF de
hoy una sola vez, y la incrusta en el HTML junto con el resto del snapshot.
Requiere conexión a internet (la UF de hoy nunca se cachea). Ver
`../../../Visualizador Web/CLAUDE.md` para el diseño completo (buscador,
carrito de cotización, texto para copiar a Excel).

```
python ".claude/skills/Cotizador_Historico/driver.py" visualizador
```

**Fallback de UF si `mindicador.cl` no responde** (agregado 2026-08-20):
tanto `visualizador` como `consultar` aceptan `--uf-manual VALOR --uf-fuente
"<texto>"` — mindicador.cl se intenta siempre primero, y solo si falla se
usa este valor. El agente debe obtenerlo buscando en internet (`WebSearch`)
una fuente confiable (ej. Banco Central de Chile) **antes** de pasar estos
flags, nunca inventarlo. Ver `../../CLAUDE.md` § Precauciones para el
detalle del mecanismo y `../Actualizar_Cotizador/SKILL.md` para el
procedimiento paso a paso dentro del flujo de publicación.

```
python ".claude/skills/Cotizador_Historico/driver.py" visualizador --uf-manual 39200.50 --uf-fuente "Banco Central de Chile, 20-08-2026"
```

**`categorias [--detalle "<categoria>"] [--top N]`** — auditoría de la
clasificación. **No usa la red** (no pide UF: revisar categorías no necesita
reajustar precios) y no escribe nada. Reporta:

- la distribución por categoría, separando catálogo cotizable de gastos de
  operación;
- la cola de **"Sin Clasificar"** — cada uno necesita una regla nueva en
  `Sistema/catalogo_taxonomia.py`;
- los ítems que **requieren medida y no la tienen** (siguen visibles y
  contados, pero no se promedian con los que sí la tienen);
- cuántas compras tienen al menos otra con que compararse.

```
python ".claude/skills/Cotizador_Historico/driver.py" categorias
python ".claude/skills/Cotizador_Historico/driver.py" categorias --detalle "Piping"
```

**Corre este comando después de tocar `catalogo_taxonomia.py`** (y
`py -3.14 -m pytest` antes), y compara que no se haya movido nada que ya
estaba bien clasificado.

## Perú (`--pais CL|PE`)

Los 3 comandos (`status`/`consultar`/`visualizador`) aceptan `--pais CL|PE`
(default `CL`, sin cambio de comportamiento si se omite). Con `--pais PE`
leen `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx` en vez del
Excel de Chile, y **Perú nunca reajusta por índice** (decisión explícita
del spec de expansión a Perú — no existe una fuente pública equivalente a
la UF chilena): `consultar`/`visualizador` muestran el precio histórico
nominal en soles tal cual, sin llamar nunca a `mindicador.cl` para ese
país (`--uf-manual`/`--uf-fuente` no aplican con `--pais PE`, se ignoran
si se pasan).

```
python ".claude/skills/Cotizador_Historico/driver.py" status --pais PE
python ".claude/skills/Cotizador_Historico/driver.py" consultar "taladro" --pais PE
python ".claude/skills/Cotizador_Historico/driver.py" visualizador --pais PE
```

## Uso conversacional

El agente puede responder la consulta directamente en el chat (ej. "¿cuánto
debería costar hoy un taladro?") invocando la misma lógica de
`Sistema/cotizador_historico.py` (función `consultar_item`), sin pasar por
el driver — igual que `/Registro_Centro_de_Costos` puede correr `status`/`run`
conversacionalmente.

## Gotchas

- **Depende de que `Centro de Costos.xlsx` tenga la estructura actual**
  (encabezados en la fila 1 de `Detalle`/`Master`, columna `Fecha` como
  fecha real en `Master`, no texto) — si Centro de Costos cambia su esquema,
  hay que revisar `mapear_encabezados`.
- **La UF de "hoy" nunca se cachea entre corridas** — cada consulta pide un
  valor fresco a `mindicador.cl` para la fecha de hoy, aunque los valores
  históricos de las compras sí queden en `Sistema/uf_cache.json`
  indefinidamente (no cambian una vez publicados).
- **Sin cotizaciones todavía**: este cotizador solo ve compras ya
  realizadas (Factura/Boleta/Guía de Despacho en Centro de Costos), no
  presupuestos. Ver "Alcance actual (v1)" en `../../CLAUDE.md`.
- **La taxonomía se edita en `Sistema/catalogo_taxonomia.py`, nunca en
  `template.html`** (2026-09-08). El HTML dejó de clasificar: solo lee lo que
  el snapshot ya trae. Volver a clasificar en JavaScript reintroduce la
  divergencia Chile/Perú que ese cambio eliminó (Perú se había quedado sin la
  categoría Instrumentación durante 8 días sin que nadie lo notara).
- **Ningún ítem se oculta por no tener medida** (2026-09-08). Antes el
  dashboard descartaba en silencio cualquier fitting sin medida o material
  detectable: 136 de 1193 compras (11,4%). Ahora quedan en una hoja marcada
  `(sin medida)`, visibles, y salen listados en `categorias`. Si un ítem no
  aparece donde debería, revisar ese comando antes de suponer un filtro.
- **Ítems sin fecha resoluble quedan fuera silenciosamente del índice** —
  `status` reporta cuántos son; si un ítem que debería aparecer no
  aparece en una búsqueda, revisar primero si está en ese conteo de
  excluidos.
- **Los ítems en $0 nunca entran al índice** (2026-09-08, pedido explícito
  del usuario tras ver una "Bomba DAB circuladora" figurando en $0 en el
  cotizador): una línea en $0 es algo incluido sin cargo dentro de un
  documento, no una observación de precio — no sirve para estimar cuánto
  cuesta algo y arrastra hacia abajo el promedio de su hoja
  (`excluido_motivo = "precio_cero"`). **Se filtra solo el cero exacto, no
  los precios bajos**: el ítem más barato del catálogo real es un remache de
  $29 y es legítimo, así que cualquier umbral mínimo arbitrario borraría
  datos buenos. Esto revierte la decisión del 2026-07-28 que trataba el $0
  como caso válido.
- **Notas de Crédito/devoluciones nunca entran al índice** (2026-07-28):
  cualquier ítem de `Detalle` con `P. Unitario sin IVA` negativo queda
  excluido (`excluido_motivo = "precio_negativo"`) — una devolución real
  (`UMAG-025`) se coló antes como "el ítem más barato" de una consulta y
  distorsionaba el promedio/rango hacia abajo. No revertir este filtro.

## Troubleshooting

| Síntoma | Causa / fix |
|---|---|
| `[ERROR] No existe .../Centro de Costos.xlsx` | Confirmar que `Centro de Costos/Excel/Centro de Costos.xlsx` existe y no se movió/renombró |
| `UFNoDisponibleError` al consultar | Sin conexión a internet, o `mindicador.cl` no tiene dato para la fecha de HOY — este es el único caso que aborta toda la consulta, porque el reajuste necesita la UF de hoy para todas las compras por igual. Buscar el valor en internet y reintentar con `--uf-manual`/`--uf-fuente` (ver arriba) en vez de simplemente reportar la falla |
| Algunas compras encontradas no aparecen en el resultado | Revisar el aviso `[INFO] N compra(s)... se excluyeron del resultado por no poder obtener su UF` al final de la salida — esa(s) fecha(s) específica(s) no se pudieron reajustar (sin conexión, o sin dato en mindicador.cl para esa fecha puntual), pero el resto de las compras encontradas sí se muestran |
| Un ítem que sé que existe no aparece en `consultar` | Correr `status`: revisar el conteo de "Excluidos" — probablemente su `N° Ref.` no tiene fila en `Master`, su `Fecha` no es una fecha válida, su celda de precio unitario está vacía/no es un número, o es una Nota de Crédito/devolución (precio unitario negativo, excluida a propósito) |
| `ModuleNotFoundError: No module named 'openpyxl'` | `pip install openpyxl` |
| Un ítem quedó en la categoría equivocada | Correr `categorias --detalle "<categoria>"` para ver dónde cayó, y agregar/ajustar su regla en `Sistema/catalogo_taxonomia.py`. Si una palabra genérica se lo está llevando, la regla más específica gana subiéndole `prioridad_extra` o escribiendo la frase completa (el match es por palabra, y una frase de 2 palabras pesa más que una de 1) |
| Una hoja mezcla productos que no son el mismo | Revisar la columna de dispersión en `consultar`: una hoja cotizable con dispersión alta suele ser presentación distinta (unidad vs pack) o una medida que no se pudo leer. Ver "Pendiente (fase 2)" en el spec de la taxonomía |
| Aparece "Sin Clasificar" en el KPI del dashboard | Es una cola de trabajo, no un error: correr `categorias` para ver cuáles son y agregarles regla |
