# Intercambio — la carpeta de cada proyecto y su Estado (`carpetas_oferta.py`)

Detalle de referencia: léelo solo al tocar esto. Las reglas generales están en `../CLAUDE.md`; la parte del Portal, en
`Visualizador Web/portal/docs/planilla.md`.

Pedido del usuario (2026-11-02): que al crearse un proyecto en la Planilla de Ingreso se cree su carpeta en «Formulación de
proyectos», con la estructura de siempre, como carpeta principal del proyecto en vez de armarla a mano; los estados nuevos
**Post-venta** y **Cerrado**; que un cambio de estado hecho en cualquier parte se refleje en todo el Portal, y un aviso antes
de que la carpeta se mueva.

- **Cuándo corre**: al final de cada vuelta de `planilla_escritura.py` (cada 10 minutos, `main`), con la Planilla ya publicada.
  `py -3.14 carpetas_oferta.py --simular` dice lo que haría sin tocar nada. Estado en `carpetas_oferta_estado.json` (gitignoreado).
- **Adónde va** (`DESTINOS`), medido en las 203 carpetas de las dos bibliotecas: Evaluación en la raíz; Ofertado en
  0 OFERTAS PRESENTADAS; No adjudicado y Descartado en 0 OFERTAS PRESENTADAS › 0 Ofertas Cerradas <año>; Adjudicado: el original
  en 0 OFERTAS ADJUDICADAS y la copia en Gestión de Proyectos › «N°. Nombre» › Formulación (como desde el 2026-10-19);
  Post-venta: igual, sin crear la de Gestión; Cerrado: la de Gestión en 0 Proyectos Entregados <año>. Una carpeta que ya está
  en ese grupo de cualquier año no se mueve. La misma tabla está en el Portal (`PQ_CARPETA`) y en el Formulador (`js/oferta.js`):
  `test_portal.py` compara las tres. **Volver atrás** mueve la carpeta de Formulación y deja la de Gestión donde está.
- **La estructura** (`ESTRUCTURA`): ANTECEDENTES, DOCUMENTOS EN TRABAJO, ENTREGABLES y VISITA TÉCNICA, con el nombre exacto que
  tienen 68 de las 156 carpetas de oferta (hasta el N° 278; después se dejó de usar). El nombre es «N°. Título», de 70
  caracteres como máximo, para que un Excel adentro se abra aun en 0 Ofertas Cerradas (Excel no abre rutas de más de 218).
- **Crear**: una fila nueva sin carpeta con su N° (en las dos bibliotecas) se crea después de `ESPERA_CREAR` (15 minutos: si la
  creó el Portal en otro computador, OneDrive la trae entretanto). La primera vuelta dejó todo lo que había como conocido; lo que
  entra «Descartado» o «No adjudicado» y lo que no tiene título no lleva carpeta. Si un requerimiento del Portal tomó otro N°
  (`numeroLibre`), su carpeta pasa a ese N° (`renombres`, hasta 24 horas).
- **Mover** (mensaje `mover-carpeta`): solo con el aviso aceptado en el Portal o el Formulador. Se atiende cuando la Planilla
  dice ese estado (si un `editar-requerimiento` del mismo N° espera, o pasaron menos de 30 minutos, espera; después queda
  `reemplazado`). Del mismo N° vale el último. Dos carpetas con el mismo N° → `rechazado`, lo decide una persona. Con algo abierto
  reintenta 7 días. Primero Gestión, después el original: si la copia falla, nada se movió. La copia se arma en «Formulación
  (copiando)» y se retoma en la vuelta siguiente si no alcanza (`SEGUNDOS_POR_VUELTA`, la tarea tiene 15 minutos). Nunca
  borra ni pisa: si ya hay otra con ese nombre en el destino, no la mueve.
- **El Estado al Formulador** (`formulaciones.alinear_estados`): lo que cambió en la Planilla desde la vuelta anterior pasa al
  presupuesto que manda en ese N° (la regla de `rcArmar`), como una versión nueva con la anterior en su historia. No se toca lo
  que ya estaba distinto la primera vez, lo que cambió el propio Formulador, un presupuesto editado hace menos de 10 minutos ni
  uno cuya carpeta o código dicen otro N° (2026-11-02: «314. UA Reactor» unido al N° 313).
- **QUEMPIN.exe** (`quempin://trasladar`) ya no lo pide nadie; quedó en el programa para páginas antiguas.
- **El Excel** (`planilla_excel.ps1`, operación `estados`, una vez): la lista de la columna Estado con los siete estados, los
  colores de Post-venta y Cerrado y su línea en el Glosario. Las hojas están protegidas sin contraseña: se quita la protección
  solo para esto y vuelve igual (con la protección puesta, `Validation.Delete` funciona y `Validation.Add` no, visto en una copia).
  La hoja «Resumen» sigue contando solo «Adjudicado».
