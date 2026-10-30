---
name: Registro_Analisis_Financiero
description: Consolida los costos reales de Centro de Costos en Análisis de Proyectos 2026.xlsx, calcula KPIs y Nota del Proyecto, avisa alertas, crea carpetas de proyectos nuevos y publica el tablero de AF. Usar SOLO si el usuario escribe "/Registro_Analisis_Financiero" (antes /Actualizar_AF); si pide con palabras actualizar AF, refrescar indicadores, evaluar la rentabilidad de un proyecto o confirmar un cliente, confirma primero, porque puede querer /Actualizar_Finanzas.
---

# Registro: Análisis Financiero

**Solo lectura** sobre `Centro de Costos.xlsx`. Las rutas son relativas a `Sistema Analisis Financiero/`; el Excel que
mantiene vive en `../Análisis Financiero/`. `driver.py` es `.claude/skills/Registro_Analisis_Financiero/driver.py`, corrido
con `py -3.14`. Rol y reglas: `../../CLAUDE.md`.

| Comando | Qué hace |
|---|---|
| `status` | Solo lee: carpetas de proyecto que se crearían y categorías de CC que caen en «Otros» |
| `run` | Respaldo, carpetas nuevas en `Facturas y Boletas/<Nombre>/`, «Detalle Costos Reales», fórmulas y tablero (si este falla, avisa y el Excel queda). Idempotente. Corre solo al final de cada `run` de CC (PASO 12d) |
| `confirmar-cliente [--todos \| <TAG>...]` | Clientes «Pendiente de revisión» (fuente roja): sin argumentos los lista. Recolorea a azul marino y marca «Confirmado» en `Sistema/clientes_pendientes.json`. Si la sugerencia no sirve, edita ahí `cliente_sugerido` antes de confirmar |
| `visualizador` | Solo el tablero, sin tocar el Excel |
| `intercambio` | Solo lee: qué se aplicaría en el próximo `run` y qué envíos esperan decisión |
| `intercambio confirmar <id>` / `descartar <id>` | Reemplaza y corre `run` (publica después) / archiva sin tocar el Excel |
| `intercambio publicar` | La lista para el Formulador, sin escribir el Excel |
| `intercambio cargar <archivo.json> ...` | Envíos descargados de «Ingresar datos» (Firefox, Safari, teléfono) → buzón: valida y deja tal cual (mismo id, nunca dos veces) |
| `formulaciones` | Solo lee el repositorio de presupuestos: nuevos, cambiados, en buzón y *Adjudicada* (`CARGADO`, `EN BUZÓN`, `CARGAR`, `ELEGIR TAG`). Uso con el usuario: `/Actualizar_Finanzas` |
| `formulaciones incorporar` / `revisadas` | Entregas por archivo → repositorio / tras mostrárselas al usuario |
| `formulaciones cargar <uid\|código [vN]> <TAG> [--nombre "Nuevo"]` | Deja en el buzón el mismo envío del Formulador, con lo que el usuario vio como If-Match. El TAG lo confirma siempre el usuario; Python no recalcula precios |

Canal y reglas de seguridad: [`docs/intercambio.md`](../../../docs/intercambio.md). `intercambio` y `formulaciones` son solo Chile.

**Perú**: `status`, `run`, `confirmar-cliente` y `visualizador` aceptan `--pais PE` (`Peru/Análisis Financiero/Análisis de
Proyectos Perú.xlsx` y `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`).

## Publicar el tablero

Procedimiento común: [`docs/actualizar-un-modulo.md`](../../../../docs/actualizar-un-modulo.md).

- **Corre `run`** si `status` muestra algo pendiente o el usuario pide un refresco (corrigió el libro a mano, confirmó un
  cliente, o CC acaba de correr).
- **Publicar es obligatorio si corriste `run`**: desde la raíz del repo, `py -3.14 "Visualizador Web/publicar.py" af` (copia
  con los PDF cifrados y verifica) y commit + push en `.worktrees/gh-pages`. Con «sin publicar», no publiques y avisa.

## Cuidados

- **Mano de Obra Real es manual**: `run` no la completa.
- **Las columnas manuales de «Proyectos» no se tocan** (TAG, Nombre, % Avance, fechas, Venta, proyectados, Mano de Obra Real):
  si algo se ve mal, es un dato cargado a mano. Excepción: lo que llega por el buzón, solo en los casos seguros.
- **El TAG debe calzar con el prefijo de CC** (`PREFIJOS_PROYECTO`): si no, los costos reales quedan en $0. `run` lo avisa si
  el TAG no tiene ningún documento; revísalo a mano si tiene facturas y aun así da $0.

| Síntoma | Causa y solución |
|---|---|
| Costos reales en $0 con compras registradas | TAG distinto del prefijo real del `N° Ref.`: revisa `PREFIJOS_PROYECTO` |
| `[AVISO] No se encontró .../Centro de Costos.xlsx` | Confirma que `Centro de Costos/Excel/Centro de Costos.xlsx` existe |
| Una categoría cae en «Otros» con aviso | Esperado si no está en `MAPEO_CATEGORIA_BUCKET`; si merece su bucket, agrégala en `analisis_financiero.py` |
| `[ERROR] No se pudo guardar ...` | El Excel está abierto: ciérralo y vuelve a correr |
