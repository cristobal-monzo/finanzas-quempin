# Historia: reconstrucción de julio 2026

Separado de `CLAUDE.md` el 2026-07-27 (mismo patrón que
`.claude/skills/Registro_Centro_de_Costos/MEMORY.md` → `HISTORIAL.md`): es
puro relato histórico, sin ninguna regla operativa vigente — solo hace
falta abrirlo para entender el origen del pipeline perdido, no para trabajar
en el módulo día a día.

Hasta el 2026-07-15 existió un pipeline más avanzado (`build.py`, `rename.py`,
`detectar_duplicados.py`, `verify.py`, `revisar_ediciones.py`) que corría en una
carpeta separada (`OneDrive - QUEMPIN SPA/Plantillas/`, fuera de este módulo) y
producía una estructura de Excel mucho más rica que la que generaba entonces
`auditor_centro_costos.py` aquí. Esos scripts se perdieron (no quedó copia en
disco) antes de integrarse a este módulo; solo sobrevivió su resultado: el
`Centro de Costos.xlsx` con la estructura rica, más un respaldo de las fotos
originales.

El 2026-07-16 se reconstruyó `auditor_centro_costos.py` desde cero, leyendo esa
estructura rica directamente del `.xlsx` sobreviviente, para que el módulo
pueda seguir alimentándola sin depender del pipeline perdido. Esta carpeta
(`Finanzas QUEMPIN/Centro de Costos/`) quedó como la ubicación canónica única
de aquí en adelante — `Sitio de comunicación - Centro de costos` y `Plantillas/`
quedaron con copias desactualizadas/parciales, no se les debe escribir más.
Ver "Estructura de `Centro de Costos.xlsx`" en `CLAUDE.md` para el detalle de la
estructura reconstruida, y `reconciliacion_archivos.json` para el mapeo de
bootstrap que permitió reconocer los 24 documentos ya existentes sin volver a
registrarlos.
