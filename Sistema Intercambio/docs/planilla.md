# Intercambio — la Planilla de Ingreso y el Portal

Detalle de referencia: léelo solo al tocar `planilla_escritura.py` o `planilla_excel.ps1`. Las reglas generales están en
`../CLAUDE.md`; la vista del Portal, en `Visualizador Web/portal/docs/planilla.md`.

Pedido del usuario: «que la planilla
de proyectos sea replicada en el portal», que desde ahora los proyectos se
ingresen ahí y que el Excel quede de respaldo, «actualizándose mutuamente». No
hay servidor, así que el Excel sigue siendo donde queda escrito todo y este
módulo es el puente, en los dos sentidos:

- **Portal → Excel**: el Portal deja `nuevo-requerimiento` y
  `editar-requerimiento` en el buzón; esta vuelta los escribe. Mientras esperan,
  el Portal los muestra a todos los navegadores encima de lo publicado, con un
  punto naranjo, y se pueden retirar.
- **Formulador → Excel** (2026-11-02): «Exportar a la Planilla» muestra qué cambiaría y deja un
  `editar-requerimiento` con lo que la persona marcó. Además de las columnas del Portal, puede llevar
  `SOLO_FORMULADOR`: Presupuesto, Valor ofertado y Valor adjudicado. Un proyecto sin N° va por `nuevo-requerimiento`.
  Las sugerencias `actualizar-requerimiento` siguen igual y se cierran solas cuando la planilla ya muestra lo sugerido.
- **Procesador → Excel** (2026-11-09): `{estado: "Cerrado"}` para lo que está en «0 Proyectos Entregados» de Gestión con la
  Planilla en «Adjudicado» (`cierre_entregados.py`). Es un `editar-requerimiento` como los demás, con `reemplaza`.
- **La lista de Estado del Excel** (operación `estados` de `planilla_excel.ps1`, una vez; a la tercera que falla deja de
  intentar): agrega «Cerrado» a la lista desplegable después de «Adjudicado», sin cambiar el orden ni los mensajes que ya
  tiene, en las mismas celdas que ya tenían validación (medido en una copia el 2026-11-09: `B4:B287` y `B289` hasta el
  final, separada con «;», el separador de listas de Windows en español), más el color de la fila y su línea en el Glosario.
  La hoja está protegida sin contraseña: se quita la protección solo para esto y vuelve con los mismos permisos
  (`Proteccion-De`/`Proteger-Como`; con la protección puesta, `Validation.Add` falla). `Intersect` se llama por
  `.Application` (directo, PowerShell no encuentra la sobrecarga). Probada en una copia de la Planilla real.
- **Excel → Portal**: si el archivo cambió, la vuelta republica
  `requerimientos.json` sin abrir Excel. Antes eso esperaba al procesador (hasta
  2 horas).
- **Si una casilla cambió en los dos lados, manda el cambio más reciente**
  (`ganador_editar`), la regla del resto del Portal. El del Portal vale desde
  `origen.enviado`. El del Excel, desde cuando este módulo escribió esa casilla
  (`escritas` en el estado, si sigue con ese valor) o, si la cambió una persona,
  desde el último guardado del libro: Excel no guarda la hora por casilla.
- **Columnas del Portal** (`EDITABLES`, medidas el 2026-10-29 sobre 323 filas con
  la regla del usuario: 45 % o más de casillas vacías o ilegibles quedan fuera):
  N°, Estado, Canal, Capt., Eval., Título, Cliente, Ubicación, ID o Referencia, Apertura
  y Cierre. Eval. (58 % vacía) y Cliente (98 %) caían por la regla contada en toda la
  planilla, pero se llenan en casi toda fila reciente (en las últimas 9: 78 % las dos;
  Cliente existe desde el 2026-10-27) y el usuario las dejó el 2026-10-30.
  Quedan solo en el Excel: Visita (51 %),
  E° visita (82 %), Visitador (91 %), Presupuesto (69 %), Valor ofertado (87 %),
  Valor adjudicado (91 %), Entrega (96 %) y Plazo Oferta (un contador con `HOY()`,
  0 en el 97 %). Siguen publicándose para las demás herramientas. «Ubicación» se
  quedó porque el 79 % que se leía como #VALUE! son datos geográficos con nombre.
- **Columnas por su encabezado, nunca por su letra.** El 2026-10-27 alguien
  insertó «Cliente» en G: con las letras fijas, una fila nueva habría escrito la
  ubicación en «Cliente» y el ID en «Ubicación». Python calcula cada letra y Excel
  revisa que siga teniendo ese encabezado antes de escribir.
- **Antes de cambiar una fila se confirma su título**: si dos personas toman el
  mismo N° a la vez, el segundo requerimiento queda con otro N° y un cambio hecho
  mientras tanto podría caer en la fila equivocada. Se sigue a la fila nueva si es
  de la misma vuelta; si no, queda `rechazado` con el motivo y el Portal lo muestra.
- **Lo que Excel reinterpretaría va con apóstrofo** (`_texto_celda`): un texto que
  empieza con `= + - @` o que es solo cifras y separadores («10-2» sería una fecha).
- **La fila nueva va en la primera vacía después del último N°**, no después de
  lo último escrito: al fondo de la tabla había dos filas de enero sin N°, y la
  fila habría quedado en la 1997.
- Probado con Excel real sobre una copia el 2026-10-29: fila nueva, cambios, casilla
  vaciada, fecha con hora, título cambiado, los dos frenos (título que no calza,
  columna movida), un cambio escrito en el Excel y los dos casos de «manda el más
  reciente». Siguen la tabla, las validaciones, `xl/richData` y los 256 datos
  geográficos. Las pruebas de `tests/` usan un `escribir` de mentira con openpyxl:
  si cambias `planilla_excel.ps1`, repite esa prueba sobre una copia.
