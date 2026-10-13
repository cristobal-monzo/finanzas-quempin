# CLAUDE.md — Visualizador Web de Oportunidades en Mercado Público

Ver el doc maestro compartido en
[`../../Visualizador Web/CLAUDE.md`](../../Visualizador%20Web/CLAUDE.md)
(rol, manual de marca, política de datos, hosting) y el motor en
[`../CLAUDE.md`](../CLAUDE.md) § Oportunidades de negocio.

Pedido del usuario (2026-10-13): «realiza mejoras en UX/UI, que sea más claro
cuáles son las oportunidades más relevantes, y publica en GitHub con
contraseña igual que el resto, con la estética del resto de herramientas
QUEMPIN». Reemplazó a la página suelta que se dejaba junto a la Planilla.

- **Fuente de datos**: `oportunidades.revisar(enviar=False)`, la misma
  evaluación que publica `oportunidades.json`. `build_visualizador.py`
  consulta la API (unos 3 minutos con el tope de 80 consultas) y guarda el
  snapshot en `data/oportunidades.json` y la página en `build/index.html`
  (ambos gitignoreados: llevan la historia de la Planilla). Sin respuesta de
  Mercado Público usa la caché y lo avisa. `--sin-red` arma solo la página.
- **Publicado** en `oportunidades/` de gh-pages, clave `op` de
  `Visualizador Web/publicar.py`; `/Actualizar_Finanzas run` lo regenera y
  publica con los demás.
- **Marca**: fuentes Lato y logo desde `brand.py` de Análisis Financiero.
  Tokens de color, cabecera, gate, navegación y menús iguales a los demás
  tableros. Pestaña «Oportunidades» en los 7 templates; solo existe para Chile
  (`SOLO_CHILE`).
- **Lo más relevante primero** (el pedido):
  - Los 4 KPIs: prioritarias, cuántas cierran en 5 días o menos, nuevas desde
    la última visita y cuántas son del rubro.
  - «Para revisar primero»: las 3 mejores, con puntaje en anillo, monto, cierre
    contado al día, visita, y lo que juega a favor (✓) y en contra (!), que
    salen de `aFavor`/`enContra` del motor.
  - «Mapa de prioridad»: puntaje contra días para el cierre.
  - La tabla, ordenada por categoría y después por puntaje.
- **Lo que depende de la fecha se recalcula en el navegador**: los días para
  el cierre, el criterio plazo y una visita que ya pasó, con las tablas de
  `DATA.reglas` (las mismas de `oportunidades_config.json`). Una licitación que
  ya cerró no se muestra. `categoria()` y `evaluar()` del JS repiten
  `Evaluador.categoria` y los tramos del plazo:
  `tests/test_tablero_oportunidades.py` las compara en Chromium.
- **Mapa (guía de dataviz)**: énfasis, no colores de identidad. Prioritaria es
  el naranjo oficial lleno, Buena un anillo del mismo naranjo y el resto gris.
  Las distingue la forma: en tema oscuro dos naranjos no se separan
  (validador: ΔE 10,4 < 15). Hay leyenda y la tabla como gemela. Cada punto
  tiene un área de toque de 24 px, tooltip con el puntaje primero y abre su
  fila al tocarlo. Los rótulos #1 a #3 eligen un lado libre, para no pisarse.
- **Por persona, en el navegador**: los pesos (`quempin_op_pesos`), el tema
  (`op_viz_theme`) y qué códigos ya vio (`quempin_op_vistas`). Con eso se
  marca «Nueva» durante 24 horas lo que aparece desde la visita anterior; la
  primera visita no marca nada.
- **Tabla**: búsqueda, filtros (qué mostrar, región, cierre, solo nuevas,
  incluir las de la Planilla) que valen para las recomendadas, el mapa y la
  tabla; orden por columna; en móvil, tarjetas (`data-label`).
- Todo texto de la API se escribe con `textContent` (`el()`), y los enlaces
  solo van a https://www.mercadopublico.cl/.
