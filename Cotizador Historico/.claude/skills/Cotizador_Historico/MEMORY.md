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
