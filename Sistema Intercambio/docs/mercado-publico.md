# Intercambio — monitor de Mercado Público (`mercado_publico.py`)

Detalle de referencia: léelo solo al tocar esto. Las reglas generales están en `../CLAUDE.md`.

El 97 % de los requerimientos viene de Mercado Público y su resultado se
pasaba a mano (análisis del 2026-10-08, §6 punto 1). En cada vuelta del
procesador, con la API pública de ChileCompra:

1. Consulta las licitaciones de la Planilla con código en «ID o Referencia»
   que esperan resultado (Ofertado, Evaluación); después barre las órdenes
   de compra emitidas a QUEMPIN (proveedor 1717812, 60 días hacia atrás la
   primera vez; después solo hoy y ayer), y por último verifica una vez las
   ya cerradas (de nuevo al mes, por si se revoca).
2. Sugiere a la Planilla **solo lo que Mercado Público prueba** (`decidir`):
   - ganada, o con OC: «Adjudicado» y el valor con IVA. Usa el total de las OC
     si suman el neto adjudicado; si no, el neto del acta más 19 %. Nunca pisa
     un valor ya escrito.
   - adjudicada a otro, desierta o revocada, con la Planilla en «Ofertado»:
     «No adjudicado».
   - Lo dudoso va a `revisar` y a la bandeja, no al buzón. Por ejemplo, la
     Planilla dice «Adjudicado» y Mercado Público dice otro ganador, o una
     licitación resuelta sigue en «Evaluación» (no se sabe si se ofertó).
   - Una sugerencia no se repite: ni si ya hay una igual en el buzón (de
     cualquier herramienta), ni si alguien la descartó (claves en la caché).
3. Las Compras Ágiles (COT) no existen como licitación en la API: se sabe que
   se ganaron solo por la OC, que nombra la COT en su título. Las OC que no
   calzan con ningún requerimiento van a la bandeja.

**Seguridad:**
- El ticket es personal (ClaveÚnica). Va cifrado con DPAPI en
  `%LOCALAPPDATA%\QUEMPIN\mercado-publico.ticket`, fuera de OneDrive y del
  repo. Solo el mismo usuario de Windows lo descifra, y la tarea programada
  corre como ese usuario.
- Se ingresa con `py -3.14 mercado_publico.py configurar`, sin eco y nunca
  por argumento. Antes de guardarlo se prueba contra la API.
- `QUEMPIN_MP_TICKET` lo reemplaza en pruebas o en otro equipo.
- Se censura en todo mensaje de error.
- Solo HTTPS a api.mercadopublico.cl, con tiempo límite y tope de 5 MB por
  respuesta. Los códigos se validan con regex antes de armar la URL.
- Los textos de la API se limpian de caracteres de control y se acortan.
- Los enlaces se limitan a https://www.mercadopublico.cl.
- No se publican nombres ni contactos de funcionarios del comprador.
- El Formulador vuelve a validar el enlace y escapa todo: la carpeta la
  puede editar cualquiera con acceso a la biblioteca.

**Límites de la API (medido el 2026-10-13):**
- Rechaza consultas seguidas con el error 10500: 2 s entre llamadas y
  reintento con espera creciente.
- El 203 es ticket inválido: corta la vuelta y la bandeja lo muestra.
- Tope de 120 llamadas por vuelta (unos 4 minutos). La primera vez necesitó
  dos vueltas.

`py -3.14 mercado_publico.py status` dice qué sugeriría sin escribir en la
carpeta. La caché (`mercado_publico_estado.json`, gitignoreada) solo lleva
datos públicos. Las pruebas cortan la red y el ticket en `tests/conftest.py`:
ninguna consulta la API real.
