---
name: Registro_Analisis_Financiero
description: Usar cuando el usuario escribe "/Registro_Analisis_Financiero" explícitamente. Si en cambio pide en lenguaje natural (sin el "/") actualizar Análisis Financiero, refrescar los indicadores de proyectos, ver el estado de Análisis de Proyectos 2026.xlsx, evaluar rentabilidad/KPIs de un proyecto, o revisar/confirmar un cliente detectado como similar a uno existente, pedir confirmación antes de invocarlo -- puede que el usuario quiera /Actualizar_AF en vez de este (ver CLAUDE.md raíz § Invocación de skills). Consolida los costos reales por proyecto y categoría desde Centro de Costos hacia Análisis de Proyectos 2026.xlsx (hojas Proyectos/Detalle Costos Reales/Indicadores/Clientes/Glosario KPIs), calcula la Nota del Proyecto (0-100) y el CLTV por cliente, y crea la carpeta de facturas para proyectos nuevos agregados a mano en el Excel.
---

# Registro Análisis Financiero

Herramienta de línea de comandos (Python + openpyxl), **solo lectura** sobre
`Centro de Costos/Excel/Centro de Costos.xlsx` -- nunca lo escribe. Todas las
rutas de este documento son relativas a la raíz de esta carpeta
(`Sistema Analisis Financiero/`) -- el Excel que este skill mantiene
(`Análisis de Proyectos 2026.xlsx`) vive en la carpeta hermana
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

**`run`** -- ejecución real: backup de `Análisis de Proyectos 2026.xlsx`, crea
carpetas de proyecto nuevas en
`Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y
Boletas/<Nombre>/`, regenera la hoja "Detalle Costos Reales" y las fórmulas
de "Proyectos"/"Indicadores", y al final regenera el visualizador web
(`Visualizador Web/build/index.html`) -- si este último paso falla, no
aborta el `run` ni pierde el Excel ya guardado, solo agrega un aviso al
resumen. Idempotente: correrlo sin cambios en Centro de Costos no altera
nada.

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

**`visualizador`** -- regenera solo el dashboard HTML
(`Visualizador Web/build/index.html`) a partir del `Análisis de
Proyectos.xlsx` actual, sin correr todo `run`. Ya se corre automáticamente
al final de `run` -- usar este comando aparte solo para refrescar el
dashboard sin tocar el Excel (por ejemplo tras un cambio manual en el
Excel que no ameríta un `run` completo).

```
python ".claude/skills/Registro_Analisis_Financiero/driver.py" visualizador
```

## Perú (`--pais CL|PE`)

Los 4 comandos aceptan `--pais CL|PE` (default `CL`, sin cambio de
comportamiento si se omite). Con `--pais PE` leen/escriben
`Peru/Análisis Financiero/Análisis de Proyectos Perú.xlsx` y
`Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx` en vez de los
Excel de Chile.

```
python ".claude/skills/Registro_Analisis_Financiero/driver.py" status --pais PE
python ".claude/skills/Registro_Analisis_Financiero/driver.py" run --pais PE
python ".claude/skills/Registro_Analisis_Financiero/driver.py" confirmar-cliente --pais PE
python ".claude/skills/Registro_Analisis_Financiero/driver.py" visualizador --pais PE
```

## Gotchas

- **Mano de Obra Real es 100% manual** -- no hay categoría equivalente en
  Centro de Costos hoy. No esperar que `run` la complete sola.
- **Las columnas manuales de "Proyectos" nunca se tocan** (TAG, Nombre,
  Estado, fechas, Venta, proyectados, Mano de Obra Real) -- si algo ahí se
  ve mal, es un dato cargado a mano, no un bug de este script.
- **TAG proyecto debe calzar con el prefijo de Centro de Costos**
  (`PREFIJOS_PROYECTO` en `auditor_centro_costos.py`) -- si no calzan, los
  costos reales de ese proyecto quedan en $0 (el `SUMIFS` no encuentra
  filas). Desde 2026-08-05 `run` avisa esto explícitamente (mismo aviso que
  "Categoría queda vacía", ambos comparten el mismo lookup por prefijo --
  ver `asegurar_categoria_proyectos`), pero solo lo detecta si el TAG no
  tiene NINGÚN documento en Centro de Costos; revisar igual a mano si el
  proyecto sí tiene facturas y aun así aparece en $0.

## Troubleshooting

| Síntoma | Causa / fix |
|---|---|
| Costos reales en $0 para un proyecto con compras registradas | El TAG en "Proyectos" no calza con el prefijo real del `N° Ref.` en Centro de Costos -- revisar `PREFIJOS_PROYECTO` |
| `[AVISO] No se encontró .../Centro de Costos.xlsx` | Confirmar que `Centro de Costos/Excel/Centro de Costos.xlsx` existe |
| Categoría cae en "Otros" sin avisar en años anteriores pero ahora sí | Es esperado: cualquier `categoria_item` que no esté en `MAPEO_CATEGORIA_BUCKET` cae en "Otros" con aviso -- si merece su propio bucket, hay que agregarla a mano en `analisis_financiero.py` |
| `[ERROR] No se pudo guardar ...` | El Excel está abierto en otra aplicación -- cerrarlo y volver a correr `run` |
