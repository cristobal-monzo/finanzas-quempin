# Memoria: Cotizador_Historico

Bitácora de observaciones, preferencias y decisiones que surgen de **usar**
este skill sobre datos reales. Complementa a [SKILL.md](SKILL.md) (el
procedimiento estable: comandos, gotchas estructurales, troubleshooting).

## Notas de Crédito — nunca entran al índice

Pedido explícito del usuario (2026-07-28): las Notas de Crédito
(devoluciones) **no deben ingresarse** al índice de este módulo. Se
encontró `UMAG-025` (devolución a Danus) apareciendo como "el ítem más
barato" en una consulta — no sirve para evaluar costos futuros, distorsiona
el promedio/rango hacia abajo. Arreglado en `cargar_items_detalle`
(`Sistema/cotizador_historico.py`): cualquier ítem de `Detalle` con
`P. Unitario sin IVA` negativo queda excluido (`excluido_motivo =
"precio_negativo"`), igual que ya pasaba con fecha/master/precio inválidos.
**No revertir este filtro ni agregar Notas de Crédito de vuelta al índice.**

## Visualizador web

- **Publicado en GitHub Pages desde 2026-08-05** (reemplaza al Claude
  Artifact usado antes — link viejo:
  `https://claude.ai/code/artifact/e589aa77-07bd-48c8-aa31-cb7c8fb1d0ab`,
  ya no se actualiza). URL fija actual:
  `https://cristobal-monzo.github.io/finanzas-quempin/cotizador-historico/`
  — ver [`/Actualizar_Cotizador`](../Actualizar_Cotizador/SKILL.md) para
  los comandos exactos de publicación y
  [../../Visualizador Web/CLAUDE.md](../../Visualizador%20Web/CLAUDE.md)
  § Hosting para la arquitectura completa.
- Flujo para actualizar: `python driver.py visualizador` (regenera
  `Visualizador Web/build/index.html` a partir de `Centro de Costos.xlsx` y
  la UF vigente) → publicar como arriba.
- La contraseña de acceso del gate vive como constante en
  `Visualizador Web/template.html` (no se repite acá — ya es visible en el
  HTML publicado, ver nota de "no es seguridad real" en ese `CLAUDE.md`).
  Es la misma contraseña que usa el visualizador de Centro de Costos.
- **`mindicador.cl` fue intermitente durante la implementación y la primera
  publicación (2026-07-20)** — timeouts, fallos de handshake TLS, y
  desconexiones remotas, todos transitorios (se recuperaba solo en minutos).
  El build de la primera publicación real quedó con 104 referencias
  indexadas (7 compras excluidas del índice por no poder resolver su UF
  histórica puntual durante esa corrida — no es un bug, es el
  comportamiento documentado: solo se excluye la compra puntual, no aborta
  todo el build). Si un build futuro sale con un conteo de excluidos
  inusualmente alto, probablemente sea este mismo tipo de intermitencia,
  no un cambio real en los datos — vale la pena reintentar antes de
  investigar más a fondo.
- **Fallback de UF de "hoy" agregado 2026-08-20**, tras un corte real de
  `mindicador.cl` durante una corrida de `/Actualizar_Finanzas` (timeout en
  dos intentos seguidos, se recuperó solo ~15 minutos después — mismo
  patrón intermitente que arriba, pero esta vez con pedido explícito del
  usuario de no limitarse a reportar la falla). Mecanismo: `mindicador.cl`
  se sigue intentando siempre primero; solo si falla, el agente busca el
  valor en internet (fuente confiable, ej. Banco Central de Chile) y lo
  pasa via `--uf-manual`/`--uf-fuente`. Detalle completo en
  `../../CLAUDE.md` § Precauciones y `../Actualizar_Cotizador/SKILL.md`
  paso 2. El valor manual usado ese día real (verificado contra
  calcular.cl/Banco Central, coincidió exacto con el que mindicador.cl
  devolvió en un intento exitoso aparte): $40.859,28 para el 20-08-2026.

## Reestructuración de la taxonomía — 2026-09-08

Pedido explícito del usuario: "mejorar el flujo de trabajo, sobre todo la
categorización... hay elementos que son de 1.1/4\" y que se indican como si
fueran de 1/4\"". El diagnóstico se hizo portando el clasificador JS a
Python y midiéndolo sobre las 1193 compras reales, no estimando.

**Lo que estaba roto** (todo medido, ver el spec
`docs/superpowers/specs/2026-09-08-taxonomia-cotizador-design.md`):

- La fracción mixta chilena no se reconocía: `1.1/4` se leía `1/4`. Efecto
  concreto: la hoja "Valvula bola" mostraba $38.152 promediando una válvula
  de 2\" ($48.349) con una de 1\" ($7.561); "Copla de Bronce 1/2" mezclaba
  una copla de 1/2\" con una reducción de 1.1/2x1.1/4\".
- `plg`, la abreviatura de pulgada más usada del catálogo, no estaba en el
  patrón: esos ítems quedaban sin medida y por lo tanto **invisibles**.
- 136 compras (11,4%) se descartaban del dashboard sin ningún aviso.
- 287 (24,1%) caían en el cajón de sastre "Otros / Servicios".
- El match era por substring: "S-**tee**-lgen" clasificaba un buzo como
  fitting, "**dado** que" clasificaba una gasolina como herramienta.

**Decisiones que conviene no revertir:**

1. **La taxonomía vive en Python** (`Sistema/taxonomia.py` +
   `catalogo_taxonomia.py`), no en `template.html`. La versión JS estaba
   duplicada en Chile y Perú y **ya había divergido**: Perú nunca recibió la
   categoría Instrumentación agregada el 2026-08-31.
2. **El material es faceta, no categoría.** Un solo `Piping y Fittings` con
   el material en la hoja. Con material-como-categoría, los materiales que
   faltaban en la lista (PVC, PEX, acero negro, y la abreviatura `BR`)
   dejaban 76 fittings sin categoría y ocultos.
3. **Ningún ítem se oculta.** Sin medida → hoja `(sin medida)`, visible.
4. **Gastos separados de productos** (`cotizable=False`): el precio unitario
   promedio de un peaje no significa nada (dispersión 101x).
5. **"Sin Clasificar" es cola de trabajo, no basurero**: KPI en el dashboard
   y lista en `driver.py categorias`. Quedó en 1 de 1193.

**Casos ambiguos que se resolvieron a mano** (si reaparecen, están acá):
"combo" es comida en este catálogo, no un mazo; "cono" suelto es un fitting
y el de señalización se nombra completo; "cinta" se reparte entre eléctrica,
de aluminio (aislación), de amarre (izaje) y de sello; "consumo" es consumo
en restaurant.

**Pendiente (fase 2), con evidencia:** las hojas cuya especificación no es
una longitud quedan con dispersión alta y la auditoría las marca — Estanque
(se compara por litros, 20x), Caldera/Quemador (por kW), Guante (unidad vs
pack de 10 pares, 15x).
