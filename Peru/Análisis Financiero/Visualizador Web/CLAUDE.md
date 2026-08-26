# CLAUDE.md — Visualizador Web de Análisis Financiero Perú

Mismo contenido/decisiones que
[`../../../Sistema Analisis Financiero/Visualizador Web/CLAUDE.md`](../../../Sistema%20Analisis%20Financiero/Visualizador%20Web/CLAUDE.md)
(pestañas Proyectos/Clientes, recomputo en Python de KPIs, gate de
contraseña) — este archivo solo documenta lo que difiere para Perú.

## Qué difiere de la versión de Chile

- **Fuente de datos**: `Peru/Análisis Financiero/Análisis de Proyectos
  Perú.xlsx` (scaffolded por `analisis_financiero.ejecutar(pais="PE")`,
  nunca creado a mano) — nunca el Excel de Chile.
- **Moneda**: PEN (`S/`), `formatoCLP` (mismo nombre de función que Chile,
  por consistencia con el resto del código copiado) formatea con
  `toLocaleString('es-PE')`.
- **Sin link a planilla pendiente**: Chile linkea a un SharePoint real para
  "proyectos pendientes de completar"; Perú no tiene ese link todavía
  (`URL_PLANILLA_PENDIENTE = None` en `build_visualizador.py`) — sin efecto
  visible mientras haya 0 proyectos.
- **Comando de build**: `python driver.py visualizador --pais PE` (desde
  `Sistema Analisis Financiero/.claude/skills/Registro_Analisis_Financiero/`).
- **Publicación**: URL propia `analisis-financiero-peru`.

## Estado

0 proyectos al 2026-08-26 (Perú recién tiene su Excel scaffolding). El
dashboard se publica igual, vacío, listo para cuando se carguen proyectos
reales a mano en la planilla.
