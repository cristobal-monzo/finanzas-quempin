---
name: Registro_Flujo_de_Caja
description: Arma el flujo de caja de Chile (Excel y tablero) solo con lo que publican Centro de Costos, Sistema QUEMPIN, la Planilla de Ingreso y Análisis Financiero; a mano solo va el saldo inicial. Usar SOLO si el usuario escribe "/Registro_Flujo_de_Caja"; ante «cómo viene la caja» o «qué vamos a cobrar y pagar», confirma primero.
---

# Flujo de Caja

El flujo no se registra: se **arma** con lo que ya producen las demás
herramientas (detalle de cada línea y de cada supuesto en
`Flujo de Caja/CLAUDE.md`). Lo único manual es el saldo de caja, en
`Flujo de Caja/Sistema/parametros_flujo_caja.json` (gitignoreado).

## Comandos

```
py -3.14 "Flujo de Caja/.claude/skills/Registro_Flujo_de_Caja/driver.py" status
py -3.14 "Flujo de Caja/.claude/skills/Registro_Flujo_de_Caja/driver.py" run
py -3.14 "Flujo de Caja/.claude/skills/Registro_Flujo_de_Caja/driver.py" visualizador
py -3.14 "Flujo de Caja/.claude/skills/Registro_Flujo_de_Caja/driver.py" saldo <monto> [AAAA-MM-DD]
```

- **`status`** — resumen mes a mes y avisos; no escribe nada.
- **`run`** — escribe `Excel/Flujo de Caja.xlsx` (hojas Resumen, Movimientos
  y Supuestos) y regenera el tablero `Visualizador Web/build/index.html`.
- **`visualizador`** — solo el tablero.
- **`saldo <monto>`** — fija el saldo de caja inicial (acepta `1500000` o
  `1.500.000`); la fecha por defecto es el inicio del mes en curso. Después,
  `run`.

`/Actualizar_Finanzas run` ya corre `run` al final, después del procesador de
la carpeta de intercambio (el flujo lee lo que ese procesador publica).

## Procedimiento

1. Correr `status` y mostrarle al usuario la tabla y **todos los avisos**: dicen
   qué falta para que el número sea completo (cotizaciones sin proyecto, una
   oferta que domina lo probable, falta de saldo inicial).
2. Si el usuario da el saldo de caja, `driver.py saldo <monto>`. El
   2026-10-02 dio una estimación («no estoy seguro, quiero que se pueda
   cambiar»): por eso el tablero tiene un campo para probar otro
   saldo (se recuerda solo en ese navegador) y en el Excel el saldo
   proyectado son fórmulas desde la celda del saldo en «Supuestos».
3. Correr `run`. Publicar el tablero en GitHub Pages (subruta
   `flujo-de-caja`) **solo si el usuario lo pide**, como los demás tableros.

## Reglas

- Nunca publicar el flujo en la carpeta de intercambio: esa carpeta la ve
  toda la biblioteca de Formulación, y esto es la caja de la empresa.
- Las ofertas por adjudicar van **aparte** (en el tablero, desmarcadas por
  defecto): una oferta se gana o se pierde entera.
