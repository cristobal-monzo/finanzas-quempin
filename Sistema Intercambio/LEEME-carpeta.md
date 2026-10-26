# Carpeta de intercambio de las herramientas de QUEMPIN

Por esta carpeta se comunican el **Formulador de proyectos**, **Sistema
QUEMPIN** (QUEMPIN.exe), el **Análisis Financiero** y las demás herramientas de
Finanzas. Vive en la biblioteca «Formulación de proyectos», dentro de
`.Herramientas formulación`, para que todo el equipo tenga acceso.

**No edites, muevas ni borres estos archivos a mano.** Cada herramienta los
maneja sola. Este archivo también: lo deja aquí el procesador desde su copia
versionada (`Finanzas QUEMPIN/Sistema Intercambio/LEEME-carpeta.md`), y un
cambio hecho aquí se pierde en la siguiente vuelta.

| Carpeta o archivo | Qué hay |
|---|---|
| `buzon/` | Envíos que todavía no se atienden: costos y venta del Formulador para el Análisis Financiero, lo ingresado en «Ingresar datos» del tablero AF, borradores de cotización para Sistema QUEMPIN, sugerencias para la Planilla de Ingreso y documentos para el Centro de Costos. |
| `buzon/adjuntos/` | Los archivos (facturas, boletas) que se suben desde «Subir documentos» del Portal, uno por envío, hasta que el procesador los deja en el Centro de Costos. |
| `procesado/` | Envíos ya atendidos, por mes, con su resultado: aplicado, sin cambios, reemplazado por uno más reciente, rechazado o descartado. |
| `publicado/` | Lo que cada herramienta comparte con las demás (ver abajo). Un archivo se reescribe solo cuando cambia lo que dice. |
| `publicado/formulador/` | Un archivo por cada proyecto del Formulador: así el equipo ve los mismos proyectos. |
| `publicado/planificacion/` | La Planificación semanal del Portal QUEMPIN: quién va a qué proyecto cada día. Una carpeta por semana y, dentro, un archivo por computador; el Portal los junta. |
| `esquemas.json` | El formato de cada envío y de cada publicación. |
| `intercambio.json` | Marca que identifica esta carpeta. |

## Qué se publica

| Archivo | Quién lo escribe | Para qué |
|---|---|---|
| `requerimientos.json` | el procesador, cuando cambia la Planilla de Ingreso | el N° de requerimiento en el Formulador y en Sistema QUEMPIN |
| `analisis-financiero.json` | Análisis Financiero | los proyectos en ejecución y sus costos, en el Formulador |
| `documentos-comerciales.json`, `contrapartes.json`, `folios.json` | Sistema QUEMPIN | cotizaciones y OC emitidas, clientes y proveedores, último N° del Control de Documentos |
| `precios-referencia.json` | Cotizador Histórico | precios de compra reajustados, en el Formulador |
| `licitaciones.json` | el procesador (Mercado Público) | quién ganó cada licitación de la Planilla |
| `proyectos.json` | el procesador | el cruce N° de requerimiento ↔ TAG ↔ formulaciones ↔ cotizaciones ↔ carpetas |
| `centro-costos-carpetas.json` | el procesador | las carpetas de proyecto de «Facturas y Boletas», para «Subir documentos» del Portal |
| `estado.json` | el procesador, en cada vuelta | el pulso: si el procesador está corriendo |

## El procesador

Un computador del equipo corre el **procesador** cada 2 horas, en horario de
trabajo, con el computador encendido. Aplica los envíos, republica lo que
cambió y deja `estado.json`. Si pasan más de 4 horas hábiles sin una vuelta,
el Formulador y la pestaña «Ingresar datos» lo avisan en rojo: lo enviado queda
esperando hasta que vuelva a correr.

Los documentos subidos desde el Portal («Subir documentos») los copia a
«Facturas y Boletas/<país>/<proyecto>/» del sitio del Centro de Costos, sin
pisar ningún archivo. Desde ahí se registran con `/Registro_Centro_de_Costos`,
igual que los subidos a SharePoint. Si un archivo no termina de llegar en 7
días, el envío se rechaza y el Portal lo muestra como «No se pudo».

## Lo que espera a una persona

- **Sugerencias para la Planilla de Ingreso** (estado, valor ofertado o
  adjudicado, del Formulador o de Mercado Público). Nadie escribe la Planilla
  por programa: se pasa a mano desde «Pendientes del equipo» del Formulador,
  y el procesador cierra la sugerencia cuando la Planilla ya lo muestra. Si
  llega una más nueva para lo mismo, la anterior se archiva sola.
- **Borradores de cotización:** se revisan y emiten en Sistema QUEMPIN, en
  «Borradores del Formulador».
- **Envíos al Análisis Financiero** que pisarían un valor escrito a mano:
  esperan una decisión en el Análisis Financiero.

## Cómo se conecta cada computador

Cada colega necesita la biblioteca «Formulación de proyectos - Documentos»
sincronizada en su OneDrive (botón *Sincronizar* en SharePoint). En el
Formulador o en el Portal QUEMPIN («Configuración y conexiones → Preparar este
computador»), Chrome o Edge de escritorio, se elige esa biblioteca una vez.
Quien no puede (otro navegador, el celular) usa **Descargar** y deja el
archivo en `buzon/`.

Quien tenga acceso a la biblioteca ve también lo publicado aquí, incluidos
los costos por proyecto de `analisis-financiero.json`.

Detalle técnico: `Finanzas QUEMPIN/Sistema Intercambio/CLAUDE.md`.
