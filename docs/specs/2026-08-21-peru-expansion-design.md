# Expansión a Perú — Diseño maestro

Fecha: 2026-08-21

## Propósito

Extender los 3 módulos financieros implementados de QUEMPIN (Centro de
Costos, Cotizador Histórico, Análisis Financiero) para que operen también
sobre las operaciones de QUEMPIN en Perú, con:

- Libros Excel **propios y separados** para Perú (nunca mezclados con los de
  Chile).
- La **misma lógica de negocio** que ya usan los módulos de Chile (mismos
  flujos, misma idempotencia, mismo formato), en soles en vez de pesos
  chilenos.
- Dashboards web idénticos en forma a los de Chile, en una URL distinta,
  con montos en soles.
- El hub (`https://cristobal-monzo.github.io/finanzas-quempin/`) mostrando
  los 6 tableros (3 Chile + 3 Perú).

Este documento cubre la **arquitectura transversal** (cómo conviven ambos
países en el mismo código) y **descompone el trabajo en sub-proyectos**
secuenciales, cada uno con su propio ciclo spec→plan→implementación. No
repite el detalle interno de cada módulo (eso vive en el `CLAUDE.md` de cada
uno) — solo el delta que introduce Perú.

## Decisiones ya tomadas (brainstorming 2026-08-21)

1. **Núcleo de código compartido y parametrizado por país** — no un clon de
   código. Cada uno de los 3 scripts existentes (`auditor_centro_costos.py`,
   `cotizador_historico.py`, `analisis_financiero.py`) gana un parámetro de
   país (`CL` por defecto, preservando el comportamiento actual sin tocar
   ninguna invocación existente; `PE` para Perú), en vez de una copia
   independiente por país. Motivo explícito del usuario: coherente con que
   este repo ya no comparte código *entre* sus 3 módulos actuales, pero cada
   módulo individual sí debe seguir siendo un único codebase.
2. **El código no se muda** — sigue viviendo donde está hoy
   (`Centro de Costos/Sistema/`, `Cotizador Historico/Sistema/`,
   `Sistema Analisis Financiero/Sistema/`). La carpeta nueva `Peru/` aloja
   únicamente los artefactos de Perú que el usuario abre/mira: el Excel de
   trabajo, sus respaldos, y los dashboards — nunca código Python.
3. **Reestructuración de "Facturas y Boletas"**: el agente mueve (con
   script, no a mano) las carpetas de proyecto actuales dentro de una nueva
   subcarpeta `Chile/`, y crea `Perú/` vacía al lado, ambas dentro de la
   MISMA carpeta compartida que existe hoy
   (`Centro de Costos/Sitio de comunicación - Centro de Costos 1/Facturas y
   Boletas/`). No se duplica el sitio de SharePoint completo por país.
4. **IGV Perú = 18%** (tasa general SUNAT), reemplaza el 19% IVA de Chile en
   la verificación aritmética de Centro de Costos para los documentos de
   Perú.
5. **Cotizador Histórico Perú no reajusta por ningún índice** — muestra el
   precio nominal en soles tal cual, sin equivalente a la UF chilena. Evita
   una dependencia externa nueva (no hay hoy una fuente pública identificada
   equivalente a `mindicador.cl` para Perú).

## A. Modelo de país

Cada uno de los 3 módulos gana, **de forma independiente** (no hay un
módulo "país" compartido entre los 3, ya que hoy tampoco comparten código
entre sí), una tabla de configuración chica con las claves que ese módulo
específico necesita. Ejemplo indicativo para Centro de Costos — el detalle
exacto (nombres de función, dónde vive la tabla) se resuelve en el plan de
implementación del sub-proyecto 1, no aquí:

```python
PAISES = {
    "CL": {
        "moneda": "CLP", "simbolo": "$",
        "nombre_impuesto": "IVA 19%", "tasa_impuesto": 0.19,
        "ruta_excel": "Excel/Centro de Costos.xlsx",
        "ruta_facturas": "Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/Chile",
    },
    "PE": {
        "moneda": "PEN", "simbolo": "S/",
        "nombre_impuesto": "IGV 18%", "tasa_impuesto": 0.18,
        "ruta_excel": "../Peru/Centro de Costos/Excel/Centro de Costos Perú.xlsx",
        "ruta_facturas": "Sitio de comunicación - Centro de Costos 1/Facturas y Boletas/Perú",
    },
}
```

Cada `driver.py`/skill existente (`Registro_Centro_de_Costos`,
`Cotizador_Historico`, `Registro_Analisis_Financiero`, y los `Actualizar_*`)
gana un flag opcional `--pais CL|PE` (default `CL`) en vez de multiplicarse
en skills nuevas por país. La política de invocación explícita con "/" del
`CLAUDE.md` raíz no cambia — solo se agrega un argumento más a comandos que
ya existen.

Perú arranca **sin proyectos registrados** (0 filas en `Master`, sin
prefijos en `PREFIJOS_PROYECTO`) — se irán agregando a medida que lleguen
documentos reales, igual que pasó con Chile.

## B. Estructura de carpetas resultante

```
Finanzas QUEMPIN/
├── Centro de Costos/                          # Chile — código en su lugar actual
│   ├── Sistema/auditor_centro_costos.py        # ahora acepta país=CL|PE
│   └── Sitio de comunicación .../Facturas y Boletas/
│       ├── Chile/          ← carpetas de proyecto actuales, movidas aquí
│       │   ├── UMAG/
│       │   ├── Cesfam Limache/
│       │   └── ... (resto de proyectos actuales)
│       └── Perú/           ← nueva, vacía
├── Cotizador Historico/                        # código compartido, sin mudanza
├── Sistema Analisis Financiero/                # código compartido, sin mudanza
├── Visualizador Web/index.html                 # hub → 6 tarjetas (3 Chile arriba, 3 Perú abajo)
└── Peru/
    ├── Centro de Costos/
    │   ├── Excel/
    │   │   ├── Centro de Costos Perú.xlsx
    │   │   └── Respaldos/
    │   └── Visualizador Web/
    │       └── build/index.html
    ├── Cotizador Historico/
    │   └── Visualizador Web/
    │       └── build/index.html
    └── Análisis Financiero/
        ├── Análisis de Proyectos Perú.xlsx
        ├── Respaldos/
        └── Visualizador Web/
            └── build/index.html
```

`Peru/` no tiene `Sistema/` ni tests propios — los tests que cubran el
comportamiento de Perú viven junto a los de Chile, en los `tests/` que ya
existen en cada módulo (parametrizados por país donde corresponda).

## C. Dashboards y hub

- Los 3 `build_visualizador.py` existentes ganan el mismo parámetro de país
  que su script de datos — generan el mismo HTML/JS que hoy, con la moneda,
  símbolo y datos del país pedido, hacia la ruta de build de ese país.
- URLs de GitHub Pages para Perú (paralelas a las 3 de Chile, sufijo
  `-peru`): `/centro-de-costos-peru/`, `/analisis-financiero-peru/`,
  `/cotizador-historico-peru/`. Mismo mecanismo de publicación documentado
  en `Visualizador Web/CLAUDE.md` (copiar a `.worktrees/gh-pages/<subruta>/`
  y push) — se agregan 3 filas a la tabla de ese archivo.
- El hub (`Visualizador Web/index.html`, editado a mano, sin build) pasa de
  3 a 6 tarjetas: las 3 de Chile arriba, las 3 de Perú abajo, con la bandera
  🇵🇪 en las tarjetas de Perú.
- Gate de contraseña: se reutiliza el mismo mecanismo ya existente en los
  dashboards de Chile (no una barrera nueva) — si el usuario quiere una
  contraseña distinta para Perú, se decide en el sub-proyecto 4.

## D. Orquestación

`/Actualizar_Finanzas` corre ambos países por defecto; acepta `--pais` para
limitarse a uno solo. Se actualiza su `SKILL.md` y `driver.py` para reflejar
esto explícitamente.

## Sub-proyectos (orden de implementación)

Cada uno se brainstorma/planifica cuando le toca su turno — este documento
no fija su diseño interno, solo el orden y las dependencias.

1. **Núcleo país + Centro de Costos Perú** — parametrizar
   `auditor_centro_costos.py` (país, IGV 18%), reestructurar "Facturas y
   Boletas" (Chile/Perú), crear el Excel vacío de Perú, actualizar el skill
   `Registro_Centro_de_Costos` (+ `Actualizar_CC`, `Actualizar_Base_de_Datos`)
   con `--pais`. Al terminar: correr el registro para Perú sobre un Excel
   vacío debe funcionar sin errores (0 documentos, 0 proyectos).
2. **Cotizador Histórico Perú** — parametrizar `cotizador_historico.py`
   (lee el Excel de Perú, sin reajuste por índice), skill
   `Cotizador_Historico` (+ `Actualizar_Cotizador`) con `--pais`. Depende de 1.
3. **Análisis Financiero Perú** — parametrizar `analisis_financiero.py`,
   crear `Análisis de Proyectos Perú.xlsx`, skill
   `Registro_Analisis_Financiero` (+ `Actualizar_AF`) con `--pais`. Depende
   de 1.
4. **Visualizadores Web de Perú (×3) + Hub de 6 tableros** — parametrizar
   los 3 `build_visualizador.py`, publicar las 3 URLs nuevas, editar el hub
   a 6 tarjetas con bandera 🇵🇪. Depende de 1–3 (necesita datos, aunque sea
   vacíos, fluyendo desde cada Excel de Perú).
5. **Orquestación y limpieza de documentación** — `/Actualizar_Finanzas`
   país-aware, y pasar por los `CLAUDE.md` de cada módulo + el raíz para que
   describan el soporte multi-país en vez de asumir Chile implícitamente.

## Fuera de alcance (explícito)

- Flujo de Caja (no existe todavía ni para Chile ni para Perú).
- Cualquier tipo de cambio CLP↔PEN o consolidado multi-moneda — cada país
  reporta en su propia moneda, sin conversión ni vista combinada.
- Reajuste por inflación en Cotizador Histórico Perú (ver decisión 5).
- Contraseña distinta para los dashboards de Perú (se reutiliza el gate
  actual salvo que el sub-proyecto 4 decida lo contrario).
