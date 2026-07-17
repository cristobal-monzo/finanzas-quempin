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
| Flujo de Caja | No iniciado | — |

**Centro de Costos** registra el gasto por centro de costos: lee fotos de facturas/boletas depositadas en carpetas por proyecto más un `datos_extraidos.json` ya extraído (con desglose en ítems de línea), y mantiene `Centro de Costos.xlsx` (Master = 1 fila/documento con fórmulas, Detalle = 1 fila/ítem, una hoja de solo lectura por proyecto), de forma idempotente y con backup automático con timestamp antes de cada escritura. La arquitectura completa, el flujo del script, el esquema del JSON y el skill `/Registro_Centro_de_Costos` (comandos `status`/`run`) están documentados en su propio `CLAUDE.md` — léelo antes de tocar cualquier cosa bajo `Centro de Costos/`.

Se espera que los módulos futuros (ej. Flujo de Caja) consuman datos que ya producen módulos anteriores (ej. totales por proyecto de Centro de Costos) en vez de construirse de forma aislada — revisa qué datos ya calculan los módulos existentes antes de duplicar esa lógica en uno nuevo.

## Al trabajar en este directorio

- **Datos financieros reales, sin control de versiones**: todo lo que hay bajo cada módulo (JSON extraído, fotos de documentos fuente, los libros `.xlsx`) es información financiera real de la empresa — montos, proveedores, números de documentos tributarios. Trátalo como sensible; no hay `.gitignore` porque todavía no hay repo git.
- **Esta es una carpeta de OneDrive sincronizada**, potencialmente editada por más de una persona/dispositivo en paralelo. Antes de sobrescribir cualquier `.xlsx`, considera que puede tener ediciones manuales recientes hechas fuera de un script.
- **Ubicación duplicada — resuelta el 2026-07-16**: `Finanzas QUEMPIN/Centro de Costos/` es ahora la única ubicación canónica del módulo (rutas de `auditor_centro_costos.py` recalculadas desde `Path(__file__)`, ya no hardcodeadas a otra carpeta). Existen otras dos copias con datos desactualizados/parciales que **no** hay que editar ni usar como fuente de verdad: `OneDrive - QUEMPIN SPA/Sitio de comunicación - Centro de costos/` (quedó con una estructura simple antigua) y `OneDrive - QUEMPIN SPA/Plantillas/` (ahí corrió un pipeline más avanzado — `build.py`/`rename.py`/etc. — que se perdió antes de integrarse aquí; su resultado final fue la base para reconstruir la estructura actual, ver `Centro de Costos/CLAUDE.md`). Si en el futuro aparece contenido nuevo en cualquiera de esas dos carpetas, confírmalo con el usuario antes de asumir que reemplaza lo que hay aquí.
