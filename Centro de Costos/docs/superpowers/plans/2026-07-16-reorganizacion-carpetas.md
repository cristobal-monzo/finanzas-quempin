# Reorganización de carpetas — Centro de Costos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganizar `Centro de Costos/` en una raíz simple de navegar
(`Excel/` para el libro, `Documentos Centro de Costos/` para las fuentes,
`Sistema/` para lo técnico), sin romper el script, la skill, los tests ni el
historial de git.

**Architecture:** Todo el ruteo de archivos del módulo cuelga de una sola
constante (`RAIZ` en `auditor_centro_costos.py`). Moviendo primero los
archivos y luego ajustando esa constante (y el `sys.path.insert` de
`driver.py`) en el mismo paso, el módulo nunca queda en un estado donde el
código apunta a una ruta vieja que ya no existe.

**Tech Stack:** Python 3 + pathlib (sin dependencias nuevas), PowerShell para
mover archivos, git para los archivos versionados, pytest para verificar.

## Global Constraints

- No usar `git mv` ni `git add` sobre archivos listados en `.gitignore`
  (`Centro de Costos.xlsx`, `datos_extraidos.json`,
  `reconciliacion_archivos.json`, `Documentos Centro de Costos/`,
  `Respaldos/`, `Legado/`) — se mueven solo con el sistema de archivos.
- No mover `.claude/` ni `docs/superpowers/` — Claude Code asume esas rutas
  relativas a la raíz del módulo.
- Verificar que `Centro de Costos.xlsx` no esté abierto en otra aplicación
  antes de moverlo.
- Cada task termina con el módulo en estado consistente (el script encuentra
  todo lo que necesita) antes de pasar a la siguiente.
- Commits frecuentes, uno por task, solo con los archivos versionados que
  correspondan a esa task.

---

### Task 1: Crear las carpetas nuevas y capturar el estado base

**Files:**
- Ninguno modificado; solo se crean directorios vacíos:
  `Excel/`, `Sistema/`, `Sistema/tests/`.

**Interfaces:**
- Produces: las carpetas de destino que las Tasks 2-4 usan para mover
  archivos.

- [ ] **Step 1: Capturar el inventario actual como línea base**

Run (desde `Centro de Costos/`):
```
python ".claude/skills/Registro_Centro_de_Costos/driver.py" status
```
Guarda la salida completa (pendientes/omitidos, proyectos, verificación
aritmética) en un archivo temporal fuera del repo, por ejemplo
`C:\Users\quemp\AppData\Local\Temp\claude\...\scratchpad\status_antes.txt`,
para comparar después de la reorganización. No debe haber "pendientes" salvo
los que ya existieran antes de empezar.

- [ ] **Step 2: Crear las carpetas nuevas**

PowerShell (desde `Centro de Costos/`):
```powershell
New-Item -ItemType Directory -Force "Excel"
New-Item -ItemType Directory -Force "Sistema"
New-Item -ItemType Directory -Force "Sistema/tests"
```

- [ ] **Step 3: Verificar que existen y están vacías**

```powershell
Get-ChildItem "Excel","Sistema" | Select-Object FullName
```
Expected: `Excel/` sin contenido, `Sistema/` con solo la subcarpeta `tests/`
(vacía).

No hay commit en esta task (no se tocó ningún archivo versionado ni de
datos).

---

### Task 2: Mover el `.code-workspace` mal ubicado

**Files:**
- Move (filesystem, no versionado): `Finanzas QUEMPIN v1.code-workspace` →
  un nivel arriba, a la raíz de `Finanzas QUEMPIN/`.

**Interfaces:**
- Ninguna — cambio aislado, no afecta al script ni a la skill.

- [ ] **Step 1: Mover el archivo**

PowerShell (desde `Centro de Costos/`):
```powershell
Move-Item "Finanzas QUEMPIN v1.code-workspace" "..\Finanzas QUEMPIN v1.code-workspace"
```

- [ ] **Step 2: Verificar**

```powershell
Test-Path "..\Finanzas QUEMPIN v1.code-workspace"
Test-Path "Finanzas QUEMPIN v1.code-workspace"
```
Expected: el primero `True`, el segundo `False`.

No hay commit (el archivo no está versionado en git).

---

### Task 3: Mover los archivos de datos reales (gitignored)

**Files:**
- Move (filesystem, no versionado):
  - `Centro de Costos.xlsx` → `Excel/Centro de Costos.xlsx`
  - `Respaldos/` → `Excel/Respaldos/`
  - `datos_extraidos.json` → `Sistema/datos_extraidos.json`
  - `reconciliacion_archivos.json` → `Sistema/reconciliacion_archivos.json`
  - `Legado/` → `Sistema/Legado/`

**Interfaces:**
- Consumes: las carpetas `Excel/` y `Sistema/` creadas en Task 1.
- Produces: las rutas de datos reales que Task 4 debe reflejar en
  `auditor_centro_costos.py`. **Importante:** al terminar esta task el
  script todavía apunta a las rutas viejas — no ejecutar
  `auditor_centro_costos.py` ni `driver.py` entre esta task y la Task 4.

- [ ] **Step 1: Confirmar que el Excel no está abierto**

PowerShell:
```powershell
try {
    $stream = [System.IO.File]::Open("Centro de Costos.xlsx", 'Open', 'ReadWrite', 'None')
    $stream.Close()
    "OK: no está abierto"
} catch {
    "BLOQUEADO: cerrar el archivo antes de continuar"
}
```
Expected: `OK: no está abierto`. Si dice `BLOQUEADO`, pide al usuario que
cierre Excel antes de seguir.

- [ ] **Step 2: Mover los archivos**

```powershell
Move-Item "Centro de Costos.xlsx" "Excel\Centro de Costos.xlsx"
Move-Item "Respaldos" "Excel\Respaldos"
Move-Item "datos_extraidos.json" "Sistema\datos_extraidos.json"
Move-Item "reconciliacion_archivos.json" "Sistema\reconciliacion_archivos.json"
Move-Item "Legado" "Sistema\Legado"
```

- [ ] **Step 3: Verificar**

```powershell
Test-Path "Excel\Centro de Costos.xlsx"
Test-Path "Excel\Respaldos"
Test-Path "Sistema\datos_extraidos.json"
Test-Path "Sistema\reconciliacion_archivos.json"
Test-Path "Sistema\Legado"
Test-Path "Centro de Costos.xlsx"
```
Expected: los primeros cinco `True`, el último (ruta vieja) `False`.

No hay commit (ninguno de estos archivos está versionado).

---

### Task 4: Mover el código versionado y actualizar sus rutas internas

**Files:**
- Move (git mv): `auditor_centro_costos.py` → `Sistema/auditor_centro_costos.py`
- Move (git mv): `Formato.md` → `Sistema/Formato.md`
- Move (git mv): `Formato Centro de Costos.md` → `Sistema/Formato Centro de Costos.md`
- Move (git mv): `tests/conftest.py` → `Sistema/tests/conftest.py`
- Move (git mv): `tests/test_driver_preview_renombrados.py` → `Sistema/tests/test_driver_preview_renombrados.py`
- Move (git mv): `tests/test_renombrado_fotos.py` → `Sistema/tests/test_renombrado_fotos.py`
- Modify: `Sistema/auditor_centro_costos.py:36-41`
- Modify: `.claude/skills/Registro_Centro_de_Costos/driver.py:28-29`

**Interfaces:**
- Consumes: `Excel/`, `Sistema/`, `Sistema/tests/` de Task 1; archivos de
  datos ya movidos por Task 3 (`Excel/Centro de Costos.xlsx`,
  `Excel/Respaldos/`, `Sistema/datos_extraidos.json`,
  `Sistema/reconciliacion_archivos.json`).
- Produces: `Sistema/auditor_centro_costos.py` con `RAIZ`, `RAIZ_DOCS`,
  `RUTA_EXCEL`, `RUTA_JSON`, `RUTA_RECONCILIACION`, `RUTA_BACKUPS`
  apuntando a las rutas nuevas — Task 5/6 no dependen de nombres nuevos,
  solo de que el módulo funcione end-to-end.

- [ ] **Step 1: Mover los archivos versionados con `git mv`**

Bash (desde `Centro de Costos/`):
```bash
git mv auditor_centro_costos.py "Sistema/auditor_centro_costos.py"
git mv "Formato.md" "Sistema/Formato.md"
git mv "Formato Centro de Costos.md" "Sistema/Formato Centro de Costos.md"
git mv "tests/conftest.py" "Sistema/tests/conftest.py"
git mv "tests/test_driver_preview_renombrados.py" "Sistema/tests/test_driver_preview_renombrados.py"
git mv "tests/test_renombrado_fotos.py" "Sistema/tests/test_renombrado_fotos.py"
```

- [ ] **Step 2: Editar las constantes de ruta en el script movido**

En `Sistema/auditor_centro_costos.py`, reemplazar las líneas 36-41:

```python
RAIZ = Path(__file__).resolve().parent
RAIZ_DOCS = RAIZ / "Documentos Centro de Costos"
RUTA_EXCEL = RAIZ / "Centro de Costos.xlsx"
RUTA_JSON = RAIZ / "datos_extraidos.json"
RUTA_RECONCILIACION = RAIZ / "reconciliacion_archivos.json"
RUTA_BACKUPS = RAIZ / "Respaldos"
```

por:

```python
RAIZ = Path(__file__).resolve().parent
RAIZ_MODULO = RAIZ.parent
RAIZ_DOCS = RAIZ_MODULO / "Documentos Centro de Costos"
RUTA_EXCEL = RAIZ_MODULO / "Excel" / "Centro de Costos.xlsx"
RUTA_JSON = RAIZ / "datos_extraidos.json"
RUTA_RECONCILIACION = RAIZ / "reconciliacion_archivos.json"
RUTA_BACKUPS = RAIZ_MODULO / "Excel" / "Respaldos"
```

- [ ] **Step 3: Editar el `sys.path.insert` de `driver.py`**

En `.claude/skills/Registro_Centro_de_Costos/driver.py`, reemplazar la
línea 29:

```python
sys.path.insert(0, str(ROOT))
```

por:

```python
sys.path.insert(0, str(ROOT / "Sistema"))
```

(`ROOT` en la línea 28, `Path(__file__).resolve().parents[3]`, no cambia —
sigue siendo la raíz de `Centro de Costos/`.)

- [ ] **Step 4: Verificar que el script encuentra todo (solo lectura)**

Run (desde `Centro de Costos/`):
```
python ".claude/skills/Registro_Centro_de_Costos/driver.py" status
```
Expected: misma salida que la línea base de Task 1 Step 1 (mismos
pendientes/omitidos, mismos proyectos, misma verificación aritmética) — sin
errores de ruta no encontrada.

- [ ] **Step 5: Correr los tests**

Run (desde `Centro de Costos/`):
```
python -m pytest Sistema/tests/ -v
```
Expected: todos los tests en `PASS`, mismo resultado que antes de mover
nada.

- [ ] **Step 6: Commit**

```bash
git add -A "Sistema/auditor_centro_costos.py" "Sistema/Formato.md" \
  "Sistema/Formato Centro de Costos.md" "Sistema/tests/" \
  ".claude/skills/Registro_Centro_de_Costos/driver.py"
git commit -m "refactor: mover script, tests y docs de formato a Sistema/

Actualiza RAIZ/RUTA_EXCEL/RUTA_BACKUPS/RAIZ_DOCS en auditor_centro_costos.py
y el sys.path de driver.py para reflejar la nueva ubicacion."
```

---

### Task 5: Actualizar `.gitignore` con las rutas nuevas

**Files:**
- Modify: `.gitignore` (raíz de `Finanzas QUEMPIN/`)

**Interfaces:**
- Ninguna — solo texto de configuración de git.

- [ ] **Step 1: Editar las rutas del bloque de Centro de Costos**

En `.gitignore` (raíz de `Finanzas QUEMPIN/`), reemplazar:

```
Centro de Costos/Centro de Costos.xlsx
Centro de Costos/datos_extraidos.json
Centro de Costos/reconciliacion_archivos.json
Centro de Costos/Documentos Centro de Costos/
Centro de Costos/Respaldos/
Centro de Costos/Legado/
```

por:

```
Centro de Costos/Excel/Centro de Costos.xlsx
Centro de Costos/Excel/Respaldos/
Centro de Costos/Sistema/datos_extraidos.json
Centro de Costos/Sistema/reconciliacion_archivos.json
Centro de Costos/Sistema/Legado/
Centro de Costos/Documentos Centro de Costos/
```

- [ ] **Step 2: Verificar que git no empieza a trackear datos reales**

Run (desde la raíz de `Finanzas QUEMPIN/`):
```bash
git status --porcelain "Centro de Costos"
```
Expected: no aparece ninguno de
`Excel/Centro de Costos.xlsx`, `Excel/Respaldos/`,
`Sistema/datos_extraidos.json`, `Sistema/reconciliacion_archivos.json`,
`Sistema/Legado/`, `Documentos Centro de Costos/` en la salida (siguen
ignorados). Sí puede aparecer `.gitignore` como modificado.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: actualizar .gitignore con las rutas de Excel/ y Sistema/"
```

---

### Task 6: Actualizar `CLAUDE.md` de Centro de Costos

**Files:**
- Modify: `Centro de Costos/CLAUDE.md`

**Interfaces:**
- Ninguna — solo documentación.

- [ ] **Step 1: Reemplazar el árbol de "Estructura del repositorio"**

En `Centro de Costos/CLAUDE.md`, dentro del bloque de "Estructura del
repositorio" (líneas ~66-85), reemplazar el árbol completo por:

```
/
├── CLAUDE.md                              # este archivo
├── Excel/
│   ├── Centro de Costos.xlsx              # libro maestro (Master + Detalle + hoja por proyecto)
│   └── Respaldos/                         # backups automáticos con timestamp (generados por el script) + manuales
├── Documentos Centro de Costos/           # documentos fuente (facturas/boletas), un subdirectorio por proyecto
│   ├── UMAG/
│   ├── Cesfam Limache/
│   └── Gastos Generales/
├── Sistema/
│   ├── auditor_centro_costos.py           # script principal del módulo Centro de Costos
│   ├── datos_extraidos.json               # datos ya extraídos de facturas/boletas (input del script), esquema con ítems de línea
│   ├── reconciliacion_archivos.json       # bootstrap: archivo original -> N° Ref para los 24 documentos que ya existían al reconstruir la estructura rica (2026-07-16)
│   ├── Formato.md                         # patrón GENÉRICO de formato (reutilizable por módulos futuros)
│   ├── Formato Centro de Costos.md        # formato REAL específico de este módulo: colores, columnas, filtros, validaciones
│   ├── Legado/                            # archivos históricos que el script ya no lee, conservados por trazabilidad
│   │   └── datos_extraidos_legacy_umag.json
│   └── tests/                             # tests de pytest del módulo
└── .claude/
    ├── settings.json
    └── skills/Registro_Centro_de_Costos/  # skill /Registro_Centro_de_Costos (antes /run-centro-de-costos)
```

- [ ] **Step 2: Actualizar las menciones de ruta sueltas en el texto**

Recorrer `Centro de Costos/CLAUDE.md` y reemplazar toda referencia textual a
rutas movidas por su ruta nueva:
- `` `Centro de Costos.xlsx` `` (como archivo suelto) → `` `Excel/Centro de Costos.xlsx` ``
  la primera vez que se menciona en una sección nueva, y puede abreviarse
  después dentro de la misma sección.
- `` `Respaldos/` `` → `` `Excel/Respaldos/` ``
- `` `Legado/` `` → `` `Sistema/Legado/` ``
- `` `auditor_centro_costos.py` `` (como archivo suelto, no como comando) →
  `` `Sistema/auditor_centro_costos.py` ``
- `` `Formato.md` `` → `` `Sistema/Formato.md` ``
- `` `Formato Centro de Costos.md` `` → `` `Sistema/Formato Centro de Costos.md` ``
- `` `datos_extraidos.json` `` (como archivo suelto) → `` `Sistema/datos_extraidos.json` ``
- `` `reconciliacion_archivos.json` `` → `` `Sistema/reconciliacion_archivos.json` ``

No cambiar las menciones que ya son parte de una ruta compuesta correcta
(por ejemplo `.claude/skills/Registro_Centro_de_Costos/driver.py`, que no se
movió), ni los nombres de columnas del Excel que coinciden por casualidad
(ninguno en este caso).

- [ ] **Step 3: Revisar visualmente el diff**

```bash
git diff "Centro de Costos/CLAUDE.md"
```
Confirmar que el árbol nuevo coincide con la estructura real
(`Get-ChildItem` de la Task 7) y que no quedó ninguna ruta vieja mencionada
fuera de la sección "Historia" (esa sección describe el pasado, no debe
actualizarse).

- [ ] **Step 4: Commit**

```bash
git add "Centro de Costos/CLAUDE.md"
git commit -m "docs: actualizar arbol de carpetas y rutas en CLAUDE.md tras la reorganizacion"
```

---

### Task 7: Verificación final end-to-end

**Files:**
- Ninguno modificado — solo verificación.

**Interfaces:**
- Consumes: el estado final de todas las tasks anteriores.

- [ ] **Step 1: Confirmar el árbol final**

PowerShell (desde `Centro de Costos/`):
```powershell
Get-ChildItem -Depth 1 | Select-Object FullName
```
Expected: en la raíz, solo `CLAUDE.md`, `.claude/`, `docs/`, `Excel/`,
`Documentos Centro de Costos/`, `Sistema/` (más `__pycache__`/
`.pytest_cache` regenerables, que se pueden ignorar o borrar).

- [ ] **Step 2: Volver a correr `status` y comparar con la línea base**

```
python ".claude/skills/Registro_Centro_de_Costos/driver.py" status
```
Comparar contra el archivo guardado en Task 1 Step 1. Expected: idéntico en
pendientes/omitidos/proyectos/verificación aritmética.

- [ ] **Step 3: Volver a correr los tests**

```
python -m pytest Sistema/tests/ -v
```
Expected: todos `PASS`.

- [ ] **Step 4: Limpiar cachés obsoletas en la raíz vieja**

Si quedó un `__pycache__/` o `.pytest_cache/` en la raíz de
`Centro de Costos/` (de antes de mover `auditor_centro_costos.py` y
`tests/`), borrarlo — es regenerable y ahora está en la ubicación
equivocada:
```powershell
Remove-Item -Recurse -Force "__pycache__" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force ".pytest_cache" -ErrorAction SilentlyContinue
```

- [ ] **Step 5: Confirmar estado de git limpio**

```bash
git status
```
Expected: sin cambios pendientes salvo, potencialmente, cachés regeneradas
bajo `Sistema/` (ya cubiertas por `.gitignore`).
