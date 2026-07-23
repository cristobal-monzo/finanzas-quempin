---
name: Registro_Analisis_Financiero
description: Consolida los costos reales por proyecto y categoría desde Centro de Costos hacia Análisis de Proyectos.xlsx (hojas Proyectos/Detalle Costos Reales/Indicadores/Clientes/Glosario KPIs), calcula la Nota del Proyecto (0-100) y el CLTV por cliente, y crea la carpeta de facturas para proyectos nuevos agregados a mano en el Excel. Usar cuando el usuario pida actualizar Análisis Financiero, refrescar los indicadores de proyectos, ver el estado de Análisis de Proyectos.xlsx, evaluar rentabilidad/KPIs de un proyecto, o revisar/confirmar un cliente detectado como similar a uno existente.
---

# Registro Análisis Financiero

Herramienta de línea de comandos (Python + openpyxl), **solo lectura** sobre
`Centro de Costos/Excel/Centro de Costos.xlsx` -- nunca lo escribe. Todas las
rutas de este documento son relativas a la raíz de esta carpeta
(`Sistema Analisis Financiero/`) -- el Excel que este skill mantiene
(`Análisis de Proyectos.xlsx`) vive en la carpeta hermana
`../Análisis Financiero/`, no acá (reorganizado 2026-07-21, ver `CLAUDE.md`).
El driver vive en `.claude/skills/Registro_Analisis_Financiero/driver.py`.

Ver `../../CLAUDE.md` para el rol del agente (analista financiero, no solo
pipeline) y `docs/superpowers/specs/2026-07-20-analisis-financiero-design.md`
(raíz de `Finanzas QUEMPIN/`) para el diseño completo.

## Comandos

**`status`** -- solo lectura: qué carpetas de proyecto se crearían, qué
categorías de Centro de Costos caen en "Otros" por no tener mapeo explícito.

```
python ".claude/skills/Registro_Analisis_Financiero/driver.py" status
```

**`run`** -- ejecución real: backup de `Análisis de Proyectos.xlsx`, crea
carpetas de proyecto nuevas en
`Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y
Boletas/<Nombre>/`, regenera la hoja "Detalle Costos Reales" y las fórmulas
de "Proyectos"/"Indicadores". Idempotente: correrlo sin cambios en Centro de
Costos no altera nada.

```
python ".claude/skills/Registro_Analisis_Financiero/driver.py" run
```

También corre automáticamente al final de cada `run` de
`/Registro_Centro_de_Costos` (PASO 12d) -- no hace falta correrlo aparte
salvo que se quiera refrescar sin correr todo Centro de Costos.

**`confirmar-cliente`** -- confirma clientes marcados "Pendiente de revisión"
(fuente roja en la columna "Cliente" de "Proyectos"): sin argumentos, solo
lista los pendientes; `--todos` aplica la sugerencia de todos; una lista de
TAGs aplica solo esos. Recolorea la celda a azul marino y marca la entrada
como "Confirmado" en `Sistema/clientes_pendientes.json`.

```
python ".claude/skills/Registro_Analisis_Financiero/driver.py" confirmar-cliente
python ".claude/skills/Registro_Analisis_Financiero/driver.py" confirmar-cliente --todos
```

Si la sugerencia automática no es el cliente correcto, edita
`cliente_sugerido` en `Sistema/clientes_pendientes.json` antes de confirmar
(mismo patrón que `correcciones_manuales.json` de Centro de Costos).

## Gotchas

- **Mano de Obra Real es 100% manual** -- no hay categoría equivalente en
  Centro de Costos hoy. No esperar que `run` la complete sola.
- **Las columnas manuales de "Proyectos" nunca se tocan** (TAG, Nombre,
  Estado, fechas, Venta, proyectados, Mano de Obra Real) -- si algo ahí se
  ve mal, es un dato cargado a mano, no un bug de este script.
- **TAG proyecto debe calzar con el prefijo de Centro de Costos**
  (`PREFIJOS_PROYECTO` en `auditor_centro_costos.py`) -- si no calzan, los
  costos reales de ese proyecto quedan en $0 (el `SUMIFS` no encuentra
  filas), no hay error explícito por ahora.

## Troubleshooting

| Síntoma | Causa / fix |
|---|---|
| Costos reales en $0 para un proyecto con compras registradas | El TAG en "Proyectos" no calza con el prefijo real del `N° Ref.` en Centro de Costos -- revisar `PREFIJOS_PROYECTO` |
| `[AVISO] No se encontró .../Centro de Costos.xlsx` | Confirmar que `Centro de Costos/Excel/Centro de Costos.xlsx` existe |
| Categoría cae en "Otros" sin avisar en años anteriores pero ahora sí | Es esperado: cualquier `categoria_item` que no esté en `MAPEO_CATEGORIA_BUCKET` cae en "Otros" con aviso -- si merece su propio bucket, hay que agregarla a mano en `analisis_financiero.py` |
| `[ERROR] No se pudo guardar ...` | El Excel está abierto en otra aplicación -- cerrarlo y volver a correr `run` |
