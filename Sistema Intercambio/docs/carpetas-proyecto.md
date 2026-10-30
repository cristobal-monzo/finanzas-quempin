# Intercambio — carpetas de facturas de los proyectos (`carpetas_proyecto.py`)

Detalle de referencia: léelo solo al tocar esto. Las reglas generales están en `../CLAUDE.md`.

**Carpetas de facturas de los proyectos** (`carpetas_proyecto.py`, paso
`carpetas-proyecto`). Pedido del usuario (2026-10-28): al adjudicarse o
pasar a ejecución un proyecto, su carpeta del Centro de Costos aunque no
tenga facturas, y en su carpeta de Gestión de Proyectos «Facturas del
proyecto» conectada a ella. Primero fue una carpeta común que el paso
copiaba al CC; el 2026-10-29 el usuario la vio vacía y sin enlace y eligió
un acceso directo web: `Facturas del proyecto.url` abre en SharePoint la
carpeta del proyecto en el CC (las facturas que ya tiene; lo que se sube
entra directo). Un `.lnk` no sirve: guarda la ruta de un solo computador.
El paso (solo si el sitio del CC está en este equipo) crea
«Facturas y Boletas/<país>/<N°. Nombre>» de lo que se adjudica después de
su primera vuelta (Formulador «Adjudicada», Planilla «Adjudicado» o ficha
del Análisis con N°; lo de antes queda en `conocidos`, porque muchas de
esas carpetas existen sin N°) y de cada carpeta de la raíz de Gestión con
«Formulación» (la arma QUEMPIN.exe); y deja el `.url` en cada carpeta de la
raíz de Gestión con carpeta en el CC (lo actualiza si la carpeta del CC
cambia; si lo borran, no vuelve; una carpeta «Facturas del proyecto» vacía
de antes se reemplaza, con archivos se avisa). Estado en
`carpetas_proyecto_estado.json` (gitignoreado). `proyectos.json` publica
`carpetas.facturasWeb` (la dirección) para el botón del Portal.
Una carpeta del CC sin N° no se renombra (el CC reconoce lo registrado por
carpeta y nombre de archivo, «Archivo origen», y lo tomaría por nuevo): se
anota en `equivalencias` del estado, `{"281": "Chile/H2 Green"}`. El
2026-10-29 se anotaron 281 y 284 y se crearon a mano las carpetas del CC de
164, 297, 308 y 314.
