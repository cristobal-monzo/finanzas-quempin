---
name: Organizar_Proyecto
description: Use when a project folder under this workspace (Centro de Costos, Flujo de Caja, Cotizador Historico, or any future module) has grown cluttered at its root and needs reorganizing into a navigable folder structure — e.g. "reorganiza las carpetas de X", "ordena esta carpeta", "quiero una carpeta exclusiva para el Excel". Also use before moving any files whose paths are referenced by code (imports, sys.path, hardcoded paths, .gitignore entries), since moving them blind breaks the scripts that use them.
---

# Organizar Proyecto

## Cuándo usar

- El usuario pide reorganizar/ordenar la estructura de carpetas de un módulo.
- La raíz de un proyecto mezcla el archivo "producto" (Excel, etc.), documentos
  fuente, código, datos, tests, docs, respaldos y cachés — y cuesta navegarla.
- Antes de mover archivos que el código referencia por ruta (`Path(__file__)`,
  `sys.path.insert`, rutas hardcodeadas, entradas de `.gitignore`).

**No usar** para mover un solo archivo aislado sin referencias de código, ni
para un simple renombrado — ahí es más rápido hacerlo a mano.

## Procedimiento

1. **Inventariar la raíz** (`Get-ChildItem -Force`) y clasificar cada elemento:
   - **Ancla fija** — nunca se mueve: `.git`, `.claude/`, `docs/superpowers/`
     (ruta relativa que asume el flujo brainstorming/writing-plans de Claude
     Code), el `CLAUDE.md` de nivel superior si otro `CLAUDE.md` lo enlaza
     por ruta.
   - **Producto** — el/los archivo(s) que el usuario abre y edita a mano
     (ej. un `.xlsx`).
   - **Fuente/datos** — documentos de entrada, JSON de datos, carpetas de
     material fuente.
   - **Sistema** — código, tests, docs técnicos, respaldos, legado: lo que
     el usuario no navega directamente.
   - **Huérfano** — archivos que claramente pertenecen a otro nivel (ej. un
     `.code-workspace` de un proyecto padre metido por error en un módulo).
   - **Caché regenerable** — `__pycache__/`, `.pytest_cache/`: se borra, no
     se mueve.

2. **Separar versionado de no versionado.** `git ls-files <carpeta>` contra
   `.gitignore` — no asumir. Los datos financieros reales suelen estar
   gitignored; eso determina el método de movimiento del paso 5.

3. **Proponer la estructura y confirmar con el usuario antes de mover nada.**
   2-4 carpetas de primer nivel como máximo, nombradas por lo que contienen,
   en el idioma/vocabulario que ya usa el proyecto (ej. `Excel/`,
   `Documentos <Proyecto>/`, `Sistema/` — no `data/`/`src/` genéricos).
   Mostrar el árbol propuesto y esperar aprobación explícita: son datos
   reales sin red de seguridad de versionado.

4. **Encontrar todas las referencias de ruta en el código antes de mover
   nada.** Grep en los scripts del proyecto por la constante raíz (ej.
   `RAIZ = Path(__file__).resolve().parent`), cualquier `sys.path.insert`, y
   menciones de las rutas afectadas en `CLAUDE.md`/`SKILL.md`/`.gitignore`.
   Si el proyecto ya centraliza sus rutas en una sola constante, el
   movimiento es seguro: basta actualizar esa constante y lo que dependa de
   ella. Si las rutas están dispersas y hardcodeadas en varios lugares,
   señalarlo al usuario — vale la pena centralizarlas de paso.

5. **Mover.** Archivos versionados: `git mv` (conserva historial). Archivos
   en `.gitignore` (datos reales): `Move-Item` en el sistema de archivos —
   nunca `git mv` sobre ellos. Antes de mover un archivo de Office (`.xlsx`,
   `.docx`, ...), verificar que no esté abierto (intentar abrirlo en modo
   `ReadWrite` exclusivo; si falla, está bloqueado — pedir al usuario que lo
   cierre).

6. **Actualizar referencias** encontradas en el paso 4: constantes de
   código, `sys.path.insert`, entradas de `.gitignore`, árbol y menciones de
   ruta en `CLAUDE.md`/`SKILL.md`.

7. **Verificar antes y después.** Si el proyecto tiene un comando de solo
   lectura (ej. `driver.py status`) o suite de tests, correrlo antes de
   mover (línea base) y después (comparar sin diferencias). Si no tiene
   ninguno, al menos ejecutar/importar el script principal y confirmar que
   no lanza `FileNotFoundError`.

8. **Limpiar cachés obsoletas** en la ubicación vieja — son regenerables, no
   se mueven.

## Errores comunes

- Mover un archivo gitignored con `git mv` — git no lo rastrea, no hace lo
  esperado; usar `Move-Item`.
- Mover el Excel/Office mientras está abierto — Windows bloquea el move a
  medio camino si no se verifica antes.
- Dejar el código apuntando a la ruta vieja entre el movimiento de archivos
  y la actualización de constantes — no ejecutar nada del proyecto en ese
  estado intermedio.
- Anidar `docs/superpowers/` o `.claude/` dentro de una subcarpeta nueva —
  rompe la convención de rutas relativas que asume Claude Code.
- Proponer nombres de carpeta genéricos en inglés cuando el proyecto ya
  tiene su propio vocabulario en español — reduce la navegabilidad real.
