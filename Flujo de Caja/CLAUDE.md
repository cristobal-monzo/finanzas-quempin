# CLAUDE.md — Flujo de Caja

Módulo implementado el 2026-10-01/02 (plan de integración de herramientas,
fase 4: `Proyectos Claude/2026-09-30-plan-integracion-herramientas.md`).
Solo Chile.

## Qué es

Un **consumidor puro**: no tiene planilla propia que mantener. Arma el flujo
de caja con lo que ya producen las demás herramientas y dice, línea por
línea, de dónde salió cada número.

| Línea | Clase | Fuente |
|---|---|---|
| Egresos pagados | real | Centro de Costos: documentos «Pagado» (foto `Centro de Costos/Visualizador Web/data/centro-de-costos.json`) |
| Facturas por pagar | comprometido | Centro de Costos: documentos «Pendiente» |
| Órdenes de compra sin factura | comprometido | Sistema QUEMPIN (`publicado/documentos-comerciales.json`, tipo 61) que no calzan con una factura |
| Cuotas por cobrar | comprometido | Sistema QUEMPIN: cuotas de la última cotización (tipo 60) de cada proyecto adjudicado |
| Ofertas por adjudicar | probable | Planilla de Ingreso (`publicado/requerimientos.json`): «Ofertado» × tasa histórica de adjudicación |
| Costo por ejecutar | estimado | Análisis Financiero (`publicado/analisis-financiero.json`, `porEjecutar` y `cierre`), con IVA, menos lo ya comprometido |

Lo que **no** existe en ninguna herramienta y por eso no está: los cobros
reales (no hay contabilidad ni banco conectados) y el saldo de caja (se fija
a mano; sin él, el acumulado es la variación, no el saldo).

## Supuestos

Todo lo que el cálculo asume vive en `SUPUESTOS` (`Sistema/flujo_caja.py`),
viaja con el resultado (hoja «Supuestos» del Excel y tabla del tablero) y se
cambia en `Sistema/parametros_flujo_caja.json` (gitignoreado; solo se leen
las claves que existen en `SUPUESTOS`). El más importante: `saldoInicial`,
una estimación a mano que el usuario dio el 2026-10-02 sin tenerla
confirmada (el monto vive solo en ese archivo: este repositorio es público). Se fija con `driver.py saldo <monto>` y se puede probar
otro valor sin tocar el archivo: en el tablero (campo «Saldo de caja al
inicio de…», recordado solo en ese navegador y descartado si cambia el del
archivo) y en el Excel (el saldo proyectado del «Resumen» son fórmulas desde
la celda del saldo en «Supuestos»).

Reglas que no son parámetros:
- Una cuota, factura u OC que debió ocurrir antes de hoy y sigue pendiente se
  cuenta en el mes en curso, marcada «vencido».
- Una cotización sin proyecto (N° de requerimiento o TAG) no aporta cuotas:
  no se sabe si se adjudicó. Se avisa cuántas son.
- Si una oferta es la mitad o más de lo probable, se avisa: se gana o se
  pierde entera. Por eso el tablero muestra las ofertas desmarcadas por defecto.

## Salidas

- `Excel/Flujo de Caja.xlsx` — hojas Resumen, Movimientos y Supuestos
  (guardado atómico; gitignoreado como todo `.xlsx`).
- `Visualizador Web/build/index.html` — tablero con contraseña, subruta
  `flujo-de-caja` en GitHub Pages (ver `Visualizador Web/CLAUDE.md`).

**Nunca** se publica en la carpeta de intercambio: esa carpeta la ve toda la
biblioteca de Formulación, y esto es la caja de la empresa.

## Comandos

```
py -3.14 "Flujo de Caja/.claude/skills/Registro_Flujo_de_Caja/driver.py" status|run|visualizador
py -3.14 -m pytest "Flujo de Caja"
```

`/Actualizar_Finanzas run` corre `run` al final, después del procesador del
intercambio, porque lee lo que ese procesador publica.

## Archivos

- `Sistema/flujo_caja.py` — cálculo, Excel y `ejecutar()`.
- `Sistema/tests/` — datos sintéticos en `tmp_path`, nunca los reales.
- `Visualizador Web/template.html` + `build_visualizador.py` — tablero.
- `.claude/skills/Registro_Flujo_de_Caja/` — skill y driver.
