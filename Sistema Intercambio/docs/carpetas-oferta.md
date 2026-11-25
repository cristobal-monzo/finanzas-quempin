# Intercambio — la carpeta de cada requerimiento y su Estado (`carpetas_oferta.py`)

Detalle de referencia: léelo solo al tocar esto. Las reglas generales están en `../CLAUDE.md`; la parte del Portal, en
`Visualizador Web/portal/docs/planilla.md`.

Pedido del usuario (2026-11-02; retomado y terminado el 2026-11-25, sobre `master`, con la rama de noviembre como guía):
que cada requerimiento nuevo de la Planilla tenga su carpeta en «Formulación de proyectos», con la estructura de siempre;
que al cambiar el Estado la carpeta vaya adonde corresponde, con un aviso antes; una lista de las que están fuera de
lugar; y que el Estado que cambia en la Planilla se vea también en el Formulador. El 2026-11-25 eligió: las cuatro
subcarpetas de siempre; al adjudicarse, original más copia en Gestión; el aviso, una casilla ya marcada; la lista, una
línea arriba de la tabla de Requerimientos. «Post-venta» como estado ya no va: desde el 2026-11-06 una postventa es un
requerimiento con N° propio y «Proyecto original».

## Dónde va cada una (`DESTINOS`)

Medido en las carpetas reales de las dos bibliotecas (2026-11-02 y de nuevo el 2026-11-25):

| Estado | Formulación de proyectos | Gestión de Proyectos |
|---|---|---|
| Evaluación | la raíz | no se toca |
| Ofertado | 0 OFERTAS PRESENTADAS | no se toca |
| No adjudicado, Descartado | 0 OFERTAS PRESENTADAS › 0 Ofertas Cerradas <año del cierre> | no se toca |
| Adjudicado | 0 OFERTAS ADJUDICADAS | la raíz; si no tiene, se crea «N°. Nombre» con la copia de la oferta en «Formulación» |
| Cerrado | 0 OFERTAS ADJUDICADAS | 0 Proyectos Entregados <año en curso> |

- Una carpeta que ya está en ese grupo, de cualquier año, no se mueve. El año de «0 Ofertas Cerradas» es el del cierre de
  la licitación (`cierre` de la fila), como ordenó el equipo las de 2025; sin fecha, el año en curso.
- La misma tabla está en el Portal (`PQ_CARPETA`, `js/planilla.js`): `tests/portal/test_portal_planilla.py` compara la
  tabla y el resultado de `pqPlanCarpeta` con `plan()` en 126 casos.
- Las carpetas se reconocen por el N° adelante (la regla de `proyectos._CARPETA_CON_NUMERO`), en la raíz y en los grupos
  «0 …» hasta tres niveles. Un N° temporal («001t») no es de la Planilla. Las carpetas sin N° no se pueden cruzar.

## Lo que hace cada vuelta (paso `carpetas-oferta` del procesador, cada 5 minutos)

- **Crear**: una fila nueva sin carpeta con su N° en las dos bibliotecas recibe «N°. Título» (70 caracteres como máximo,
  para que un Excel adentro se abra aun en 0 Ofertas Cerradas) con ANTECEDENTES, DOCUMENTOS EN TRABAJO, ENTREGABLES y
  VISITA TÉCNICA, en el grupo de Formulación de su estado, después de `ESPERA_CREAR` (15 minutos: si alguien la creó a
  mano en otro computador, OneDrive la trae entretanto). Gestión no: eso lo pide una persona. La primera vuelta dejó todo
  lo que había como conocido (`conocidos`, en `procesador_estado.json`); lo que entra «No adjudicado» o «Descartado» y lo
  que no tiene título no lleva carpeta.
- **Mover** (mensaje `mover-carpeta`): se atiende cuando la Planilla dice ese estado o el cambio espera en el buzón. Si
  no, espera 30 minutos (OneDrive puede traer el mover antes que el cambio) o mientras haya otro cambio de esa fila en el
  buzón; después queda `descartado`. Del mismo N° vale el último (`reemplazado`). Dos carpetas con el mismo N° →
  `rechazado`, lo decide una persona. Sin carpeta: con `crear` se crea; si no, `rechazado`. Con algo abierto reintenta
  7 días. Primero Gestión, después el original: si la copia falla, nada se movió. La copia se arma en «Formulación
  (copiando)» y se retoma en la vuelta siguiente si no alcanza (`SEGUNDOS_POR_VUELTA`, 2 minutos). Nunca borra ni pisa:
  si ya hay otra con ese nombre en el destino, no la mueve (`YaExiste` → `rechazado`).
- Hasta el 2026-11-25 los `mover-carpeta` (solo «Cerrado») los atendía `cierre_entregados.py`; ese módulo quedó solo con
  lo contrario: lo que alguien movió a mano a los entregados pasa a «Cerrado» en la Planilla.

## Fuera de lugar (`fuera_de_lugar`)

El paso `proyectos` publica en `proyectos.json`:

- `ofertas`: `{req, ruta}` de cada carpeta con N° de Formulación (la ruta desde la biblioteca, con «/»);
- `fueraDeLugar`: `{req, carpeta, estado, detalle}` de las que no están donde dice su Estado. No cuenta las de un N° con
  dos carpetas, las que ya tienen un `mover-carpeta` en el buzón ni la carpeta de Gestión hecha a mano a la que solo le
  falta la copia de la oferta (eso no es estar fuera de lugar; se completa si alguien la mueve).

Medido el 2026-11-25: 65 fuera de lugar, casi todas ofertas «No adjudicado» o «Descartado» que siguen en «0 OFERTAS
PRESENTADAS». El Portal las muestra con «Mover las N».

## El Estado al Formulador (`formulaciones.alinear_estados`, paso `estados-formulador`)

Lo que cambió en la Planilla desde la vuelta anterior pasa al presupuesto que manda en ese N° (la regla de `rcArmar`: la
última versión de cada código y, entre códigos del mismo N°, el más reciente), como una versión nueva firmada «Planilla de
Ingreso», con la anterior en su historia. `AL_FORMULADOR`: Evaluación → En revisión, Ofertado → Enviada, Adjudicado →
Adjudicada, Cerrado → Cerrada, No adjudicado → Perdida, Descartado → Descartada.

No se toca: lo que ya estaba distinto la primera vez (se anota lo que hay), un presupuesto que ya dice lo mismo
(`EN_PLANILLA`, la tabla de `js/flujo.js` del Formulador), uno editado hace menos de 10 minutos (se mira en la vuelta
siguiente), uno cuyo código o carpeta dicen otro N° (2026-11-02: «314. UA Reactor» unido al 313) y un N° con un aviso de
estado del Formulador que todavía espera en el buzón (una sugerencia sin decidir). Desde el 2026-11-25 el Formulador
traduce «Cerrada» a «Cerrado» (antes a «Adjudicado»), para que los dos sentidos calcen.

## Probar y revisar

- `py -3.14 carpetas_oferta.py` dice qué haría y lista lo fuera de lugar, sin tocar nada.
- Pruebas: `tests/test_carpetas_oferta.py` (bibliotecas falsas en `tmp_path`) y, en el Portal,
  `tests/portal/test_portal_planilla.py`.
