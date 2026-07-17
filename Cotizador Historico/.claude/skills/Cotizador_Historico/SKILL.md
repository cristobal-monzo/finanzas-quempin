---
name: Cotizador_Historico
description: Estima el costo actual de un ítem (material, equipo, herramienta) a partir de sus compras históricas en Centro de Costos, reajustando el precio por la variación de la UF entre la fecha de compra y hoy. Usar cuando el usuario pregunte cuánto debería costar algo hoy, pida una cotización aproximada basada en compras anteriores, o quiera saber el precio histórico reajustado de un ítem ya comprado.
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
quedan excluidos (sin fecha resoluble vía `Master`), cuántas fechas hay en
el caché de UF, y prueba la conexión a `mindicador.cl`.

```
python ".claude/skills/Cotizador_Historico/driver.py" status
```

**`consultar "<texto>"`** — busca el texto contra `Nombre Ítem`/`Descripción`
de `Detalle` (búsqueda difusa) y muestra cada compra encontrada con su
precio original y su precio reajustado a hoy, más promedio y rango.

```
python ".claude/skills/Cotizador_Historico/driver.py" consultar "taladro"
```

Salida esperada (estructura estable; los números cambian según los datos
reales de Centro de Costos y la UF del día):

```
Compras encontradas para "taladro":

  UMAG-014 (2026-03-10): $90,000 -> $94,200 reajustado a hoy
  UMAG-021 (2026-05-02): $85,000 -> $87,100 reajustado a hoy

Promedio reajustado: $90,650
Rango: $87,100 - $94,200
```

Si no hay match: `No se encontraron compras para "<texto>".`, con una lista
de sugerencias si hubo coincidencias de similitud baja.

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
- **Ítems sin fecha resoluble quedan fuera silenciosamente del índice** —
  `status` reporta cuántos son; si un ítem que debería aparecer no
  aparece en una búsqueda, revisar primero si está en ese conteo de
  excluidos.

## Troubleshooting

| Síntoma | Causa / fix |
|---|---|
| `[ERROR] No existe .../Centro de Costos.xlsx` | Confirmar que `Centro de Costos/Excel/Centro de Costos.xlsx` existe y no se movió/renombró |
| `UFNoDisponibleError` al consultar | Sin conexión a internet, o `mindicador.cl` no tiene dato para la fecha de HOY — este es el único caso que aborta toda la consulta, porque el reajuste necesita la UF de hoy para todas las compras por igual |
| Algunas compras encontradas no aparecen en el resultado | Revisar el aviso `[INFO] N compra(s)... se excluyeron del resultado por no poder obtener su UF` al final de la salida — esa(s) fecha(s) específica(s) no se pudieron reajustar (sin conexión, o sin dato en mindicador.cl para esa fecha puntual), pero el resto de las compras encontradas sí se muestran |
| Un ítem que sé que existe no aparece en `consultar` | Correr `status`: revisar el conteo de "Excluidos" — probablemente su `N° Ref.` no tiene fila en `Master`, o su `Fecha` no es una fecha válida |
| `ModuleNotFoundError: No module named 'openpyxl'` | `pip install openpyxl` |
