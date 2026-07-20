# MEMORY.md — Análisis Financiero

Memoria del módulo: decisiones tomadas, historial, y pendientes que dependen del
usuario. El diseño técnico completo vive en el spec (ver `CLAUDE.md`); acá se
registra lo que no está en el código porque el código todavía no existe.

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

## Pendientes que dependen del usuario

- `Análisis de Proyectos.xlsx` está vacío — no hay proyectos cargados todavía,
  así que nada de esto se ha probado contra datos reales.
- El script (`Sistema/analisis_financiero.py`), el skill
  (`.claude/skills/Registro_Analisis_Financiero/`) y los tests no están
  implementados — falta decidir cuándo pasar de spec a plan de implementación
  (`writing-plans`) y construirlo.
- El dashboard HTML (Visualizador Web de este módulo) está fuera de alcance v1
  a propósito — el usuario ya indicó que esa es la forma de presentación a
  mediano plazo, pero no se construye hasta más adelante.
