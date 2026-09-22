# CLAUDE.md — Visualizador Web de Análisis Financiero Perú

**Desde 2026-09-21 no hay template ni lógica propia de Perú.** El tablero
peruano se genera con el mismo `build_visualizador.py` y el mismo
`template.html` que Chile
([`../../../Sistema Analisis Financiero/Visualizador Web/`](../../../Sistema%20Analisis%20Financiero/Visualizador%20Web/CLAUDE.md)),
parametrizados por país en `PAISES_VIZ`. El `build_visualizador.py` de esta
carpeta es un envoltorio de 10 líneas que llama a ese build con `pais="PE"`:
existe solo para que `analisis_financiero.actualizar_visualizador_af("PE")`
lo siga encontrando acá.

Por qué: la copia completa de Chile ya se había quedado atrás dos veces (el
renombre Estado → % Avance, 2026-08-31, que la rompió; y la fase 0 de la
auditoría del dashboard, 2026-09-21, que no llegó a Perú). Cualquier cambio
al tablero se hace una sola vez, en la carpeta de Chile.

## Qué cambia para Perú (todo en `PAISES_VIZ["PE"]`)

- **Fuente de datos**: `Peru/Análisis Financiero/Análisis de Proyectos
  Perú.xlsx` (scaffolded por `analisis_financiero.ejecutar(pais="PE")`,
  nunca creado a mano) — nunca el Excel de Chile.
- **Moneda**: PEN (`S/`, `es-PE`), viaja en el snapshot (`DATA.moneda`).
- **Título y pestaña activa** de la navegación entre tableros: se reemplazan
  al construir (`__AF_TITULO__`, `__AF_NAV_ACTIVO__`).
- **Sin link a planilla pendiente**: Perú no tiene todavía un SharePoint
  para su planilla (`url_planilla: None`).
- **Salida**: `build/index.html` y `data/analisis-financiero-peru.json` de
  esta carpeta, igual que antes — la receta de publicación no cambia.
- **Comando de build**: `python driver.py visualizador --pais PE` (desde
  `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/`).
- **Publicación**: URL propia `analisis-financiero-peru`.

## Estado

0 proyectos completos al 2026-09-21: la planilla peruana tiene filas de
proyecto (creadas desde Centro de Costos Perú) pero ningún dato manual
cargado. El dashboard se publica igual, vacío, listo para cuando se carguen.
