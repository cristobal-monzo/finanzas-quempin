# Reorganización de carpetas — Centro de Costos

Fecha: 2026-07-16

## Contexto

`Centro de Costos/` acumuló, además de los dos elementos "de negocio" que el
usuario navega (el libro `Centro de Costos.xlsx` y los documentos fuente en
`Documentos Centro de Costos/`), un conjunto creciente de archivos técnicos en
la raíz: script, JSON de entrada, docs de formato, tests, respaldos, legado,
infraestructura de Claude Code, y — por error — un `.code-workspace` que
pertenece al nivel de `Finanzas QUEMPIN/`, no a este módulo. El objetivo es
que la raíz sea fácil de navegar para un usuario no técnico, sin romper nada
de lo que ya depende de las rutas actuales (script, skill, tests, git).

`auditor_centro_costos.py` y el driver de la skill derivan todas sus rutas de
una sola constante (`RAIZ = Path(__file__).resolve().parent`), lo que hace el
movimiento seguro siempre que se actualicen esas constantes de forma
consistente.

Parte del contenido de este módulo está versionado en git (código, tests,
skill, docs de formato) y parte está en `.gitignore` por ser datos financieros
reales (Excel, JSON de datos, documentos fuente, respaldos, legado) — ver
`.gitignore` en la raíz de `Finanzas QUEMPIN/`.

## Estructura objetivo

```
Centro de Costos/
├── CLAUDE.md
├── .claude/                          (sin cambios)
├── docs/superpowers/                 (sin cambios)
├── Excel/
│   ├── Centro de Costos.xlsx
│   └── Respaldos/
├── Documentos Centro de Costos/      (sin cambios de contenido, ya era su propia carpeta)
│   ├── UMAG/
│   ├── Cesfam Limache/
│   └── Gastos Generales/
└── Sistema/
    ├── auditor_centro_costos.py
    ├── datos_extraidos.json
    ├── reconciliacion_archivos.json
    ├── Formato.md
    ├── Formato Centro de Costos.md
    ├── Legado/
    └── tests/
```

`.claude/` y `docs/superpowers/` quedan en la raíz de `Centro de Costos/`
porque Claude Code asume esas rutas relativas al abrir el proyecto (la skill
vive bajo `.claude/skills/`, y el flujo de brainstorming/writing-plans escribe
specs/plans en `docs/superpowers/` relativo a la raíz del proyecto abierto).

`Finanzas QUEMPIN v1.code-workspace` se mueve un nivel arriba, a la raíz de
`Finanzas QUEMPIN/` (fuera de este módulo).

## Cambios de código

- `auditor_centro_costos.py`: `RAIZ` pasa a ser `Sistema/`.
  `RUTA_EXCEL` y `RUTA_BACKUPS` pasan a `RAIZ.parent / "Excel" / ...`.
  `RAIZ_DOCS` pasa a `RAIZ.parent / "Documentos Centro de Costos"`.
  `RUTA_JSON` y `RUTA_RECONCILIACION` siguen relativos a `RAIZ` (se mueven
  junto con el script, sin cambio de fórmula).
- `.claude/skills/Registro_Centro_de_Costos/driver.py`: el
  `sys.path.insert(0, str(ROOT))` pasa a `sys.path.insert(0, str(ROOT / "Sistema"))`
  (`ROOT` — `parents[3]` desde `driver.py` — sigue siendo la raíz de
  `Centro de Costos/`, no cambia).
- `tests/conftest.py`: se mueve junto con el script a `Sistema/tests/`. Su
  `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` no
  necesita cambio de fórmula: sigue resolviendo a `Sistema/`, igual que antes
  resolvía a la raíz.

## Git

- Archivos versionados (`auditor_centro_costos.py`, `Formato.md`,
  `Formato Centro de Costos.md`, `tests/*`, `docs/superpowers/*` si se
  reubican) se mueven con `git mv` para conservar historial.
- Archivos con datos reales, ya excluidos vía `.gitignore`
  (`Centro de Costos.xlsx`, `datos_extraidos.json`,
  `reconciliacion_archivos.json`, `Documentos Centro de Costos/`,
  `Respaldos/`, `Legado/`) se mueven directo en el sistema de archivos.
- Se actualizan las rutas correspondientes en `.gitignore` (raíz de
  `Finanzas QUEMPIN/`) a las nuevas ubicaciones.
- `Finanzas QUEMPIN v1.code-workspace` no está versionado (aparece como
  untracked en `git status`); se mueve con el sistema de archivos, sin `git
  mv`.

## Precauciones

- Verificar que `Centro de Costos.xlsx` no esté abierto en Excel antes de
  moverlo (si está abierto, Windows bloquea el move con un error claro, no
  corrompe el archivo).
- Si un movimiento falla a medio camino, no dejar el módulo en estado mixto
  (por ejemplo, script con `RAIZ` ya apuntando a `Sistema/` pero el Excel
  todavía en la raíz vieja): completar o revertir antes de continuar.
- Esta carpeta vive dentro de OneDrive, sincronizada y potencialmente en uso
  por otro dispositivo; preferible ejecutar la reorganización cuando nadie más
  tenga el Excel abierto.

## Verificación posterior

- Correr `python driver.py status` (solo lectura) desde la skill para
  confirmar que encuentra Excel, JSON, reconciliación y Documentos en sus
  nuevas rutas, sin diferencias respecto al inventario previo a la
  reorganización.
- Correr la suite de `pytest` (`Sistema/tests/`) y confirmar que sigue
  pasando.
- Actualizar `CLAUDE.md` de `Centro de Costos/` (árbol de carpetas y las
  menciones de rutas en el texto) para reflejar la nueva estructura.

## Fuera de alcance

- No se reorganiza nada fuera de `Centro de Costos/` salvo mover el
  `.code-workspace` mal ubicado un nivel arriba.
- No se modifica el contenido de `Documentos Centro de Costos/` (subcarpetas
  por proyecto ya existentes, se mueve la carpeta completa tal cual).
- No se toca `docs/superpowers/` ni `.claude/` más allá de la referencia de
  ruta en `driver.py`.
