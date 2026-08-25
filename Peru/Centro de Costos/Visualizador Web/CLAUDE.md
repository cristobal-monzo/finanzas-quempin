# CLAUDE.md — Visualizador Web de Centro de Costos Perú

Mismo contenido/decisiones de saneado que
[`../../../Centro de Costos/Visualizador Web/CLAUDE.md`](../../../Centro%20de%20Costos/Visualizador%20Web/CLAUDE.md)
(estructura de `template.html`/`build_visualizador.py`, gate de contraseña,
datos incrustados en base64, KPIs, tabla dinámica, gráficos, filtros) — este
archivo solo documenta lo que difiere para Perú. Ver también
[`../../../Visualizador Web/CLAUDE.md`](../../../Visualizador%20Web/CLAUDE.md)
(doc maestro: marca, hosting, mandato de herramientas dinámicas).

## Qué difiere de la versión de Chile

- **Fuente de datos**: `Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx`
  (nunca `Centro de Costos/Excel/Centro de Costos.xlsx` — son libros
  completamente separados desde el split por país del 2026-08-21, ver
  `Centro de Costos/CLAUDE.md` § "Split por país").
- **Moneda**: PEN (`S/`), impuesto IGV 18% (no IVA 19% / CLP) — columnas
  `Total sin IGV (PEN)`, `IGV 18% (PEN)`, `Total con IGV (PEN)` en vez de
  las de Chile. `template.html` formatea con `Intl.NumberFormat('es-PE',
  {currency:'PEN'})`.
- **Razón social del proveedor**: sigue mostrando el tag corto en la tabla
  y la razón social completa al expandir, igual que Chile — solo cambia que
  los documentos de Perú se emiten a nombre de "QUEMPIN SAC", no "QUEMPIN
  SpA" (dato que ya vive en `Sistema/auditor_centro_costos.py`
  `PAISES["PE"]["razon_social"]`, no en este visualizador).
- **Gate de contraseña**: reutiliza el mismo mecanismo/contraseña que
  Chile — decisión explícita del spec de expansión a Perú (no una barrera
  nueva).
- **Comando de build**: `python driver.py visualizador --pais PE` (desde
  `Centro de Costos/.claude/skills/Registro_Centro_de_Costos/`) en vez de
  sin `--pais` (default `CL`) — el driver ya resolvía esta ruta antes de
  que este archivo existiera (`cmd_visualizador` imprimía "[INFO]
  Visualizador Web de PE aún no implementado" hasta esta implementación).
- **Publicación**: URL propia `centro-de-costos-peru` (no
  `centro-de-costos`) — ver `../../../Visualizador Web/CLAUDE.md` § Hosting
  para la tabla completa con las 4 subrutas.

## Estado

0 documentos al 2026-08-24 (Perú recién tiene su Excel scaffolding, sin
facturas/boletas registradas todavía — ver `Peru/Centro de Costos/
datos_extraidos_peru.json`, vacío). El dashboard se publica igual, vacío,
para que quede listo apenas empiecen a fluir documentos reales — evita
tener que repetir este trabajo de implementación más adelante.
