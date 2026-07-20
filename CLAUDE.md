# CLAUDE.md

Este archivo guía a Claude Code (claude.ai/code) al trabajar con código en este repositorio.

## Qué es este directorio

`Finanzas QUEMPIN` es el punto de consolidación de las herramientas de automatización financiera de QUEMPIN SpA. No es un codebase en sí mismo — es un contenedor pensado para tener una subcarpeta por cada módulo financiero, donde cada módulo es una herramienta independiente en Python/openpyxl que mantiene un proceso manual de Excel sincronizado con sus documentos fuente (facturas, boletas, etc.).

No hay repositorio git aquí ni herramientas de build/lint/test a nivel raíz — cada módulo tiene las suyas propias.

## Módulos

| Módulo | Estado | Documentación |
|---|---|---|
| [Centro de Costos/](Centro%20de%20Costos/CLAUDE.md) | Implementado | `Centro de Costos/CLAUDE.md` |
| [Cotizador Historico/](Cotizador%20Historico/CLAUDE.md) | Implementado | `Cotizador Historico/CLAUDE.md` |
| [Análisis Financiero/](Análisis%20Financiero/CLAUDE.md) | Diseño aprobado (spec), sin implementar | `Análisis Financiero/CLAUDE.md` |
| Flujo de Caja | No iniciado | — |
| [Visualizador Web/](Visualizador%20Web/CLAUDE.md) | Centro de Costos implementado (2026-07-19); resto scaffolding | `Visualizador Web/CLAUDE.md` |

**Centro de Costos** registra el gasto por centro de costos: lee fotos de facturas/boletas depositadas en carpetas por proyecto más un `datos_extraidos.json` ya extraído (con desglose en ítems de línea), y mantiene `Centro de Costos.xlsx` (Master = 1 fila/documento con fórmulas, Detalle = 1 fila/ítem, una hoja de solo lectura por proyecto), de forma idempotente y con backup automático con timestamp antes de cada escritura. La arquitectura completa, el flujo del script, el esquema del JSON y el skill `/Registro_Centro_de_Costos` (comandos `status`/`run`) están documentados en su propio `CLAUDE.md` — léelo antes de tocar cualquier cosa bajo `Centro de Costos/`.

**Visualizador Web** es transversal a todos los módulos: cada uno tendrá, en su propia carpeta, una subcarpeta `Visualizador Web/` con un HTML publicado online (gráficos, tablas dinámicas, buscadores, filtros). El doc maestro compartido (marca, mandato de herramientas dinámicas, política de datos, hosting) vive en `Visualizador Web/CLAUDE.md` a nivel raíz; cada módulo tiene su propio `<Módulo>/Visualizador Web/CLAUDE.md` con el contenido específico a presentar. **Centro de Costos ya tiene una implementación real** (2026-07-19): `Centro de Costos/Visualizador Web/template.html` (estructura, versionada) + `build_visualizador.py` (export + build, corrible vía `driver.py visualizador` del skill `/Registro_Centro_de_Costos`) generan un `build/index.html` autocontenido con los datos incrustados, publicado como Claude Artifact privado (no GitHub Pages todavía — el punto de control de acceso del maestro sigue sin resolverse). Cotizador Historico y Flujo de Caja siguen solo con el scaffolding de `CLAUDE.md`, ver el spec original en `docs/superpowers/specs/2026-07-19-visualizador-web-design.md`.

**Análisis Financiero** es distinto a los demás: no es solo un pipeline de registro, es un rol consultivo — actúa como analista financiero experto (evalúa proyectos, propone/depura KPIs, decide cómo presentar la información, cruza todos los módulos), sobre un Excel (`Análisis de Proyectos.xlsx`) que consolida costos reales de Centro de Costos contra ventas y proyecciones manuales por proyecto. Diseño completo en `Análisis Financiero/CLAUDE.md` y el spec referenciado ahí — el script y el skill todavía no están implementados.

Se espera que los módulos futuros (ej. Flujo de Caja) consuman datos que ya producen módulos anteriores (ej. totales por proyecto de Centro de Costos) en vez de construirse de forma aislada — revisa qué datos ya calculan los módulos existentes antes de duplicar esa lógica en uno nuevo.

## Al trabajar en este directorio

- **Datos financieros reales, sin control de versiones**: todo lo que hay bajo cada módulo (JSON extraído, fotos de documentos fuente, los libros `.xlsx`) es información financiera real de la empresa — montos, proveedores, números de documentos tributarios. Trátalo como sensible; no hay `.gitignore` porque todavía no hay repo git.
- **Esta es una carpeta de OneDrive sincronizada**, potencialmente editada por más de una persona/dispositivo en paralelo. Antes de sobrescribir cualquier `.xlsx`, considera que puede tener ediciones manuales recientes hechas fuera de un script.
- **Ubicación duplicada — resuelta el 2026-07-16**: `Finanzas QUEMPIN/Centro de Costos/` es ahora la única ubicación canónica del módulo (rutas de `auditor_centro_costos.py` recalculadas desde `Path(__file__)`, ya no hardcodeadas a otra carpeta). Existen otras dos copias con datos desactualizados/parciales que **no** hay que editar ni usar como fuente de verdad: `OneDrive - QUEMPIN SPA/Sitio de comunicación - Centro de costos/` (quedó con una estructura simple antigua) y `OneDrive - QUEMPIN SPA/Plantillas/` (ahí corrió un pipeline más avanzado — `build.py`/`rename.py`/etc. — que se perdió antes de integrarse aquí; su resultado final fue la base para reconstruir la estructura actual, ver `Centro de Costos/CLAUDE.md`). Si en el futuro aparece contenido nuevo en cualquiera de esas dos carpetas, confírmalo con el usuario antes de asumir que reemplaza lo que hay aquí.
