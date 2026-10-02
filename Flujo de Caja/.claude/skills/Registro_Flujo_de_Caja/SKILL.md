---
name: Registro_Flujo_de_Caja
description: Use when the user types "/Registro_Flujo_de_Caja" explicitly. If the user instead asks in natural language without the leading "/" — "cómo viene la caja", "flujo de caja", "qué vamos a cobrar y pagar los próximos meses" — ask for confirmation before invoking (see root CLAUDE.md § Invocación de skills), never auto-invoke. Builds QUEMPIN's cash flow (Chile) only from what the other tools already publish — Centro de Costos, Sistema QUEMPIN, the Planilla de Ingreso and Análisis Financiero — and writes its Excel and its dashboard. Nothing is typed in by hand except the opening cash balance.
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
```

- **`status`** — resumen mes a mes y avisos; no escribe nada.
- **`run`** — escribe `Excel/Flujo de Caja.xlsx` (hojas Resumen, Movimientos
  y Supuestos) y regenera el tablero `Visualizador Web/build/index.html`.
- **`visualizador`** — solo el tablero.

`/Actualizar_Finanzas run` ya corre `run` al final, después del procesador de
la carpeta de intercambio (el flujo lee lo que ese procesador publica).

## Procedimiento

1. Correr `status` y mostrarle al usuario la tabla y **todos los avisos**: dicen
   qué falta para que el número sea completo (cotizaciones sin proyecto, una
   oferta que domina lo probable, falta de saldo inicial).
2. Si el usuario da el saldo de caja, escribirlo en
   `parametros_flujo_caja.json` como `{"saldoInicial": <monto>, "saldoInicialFecha": "AAAA-MM-DD"}`
   (las claves que no estén en `SUPUESTOS` se ignoran).
3. Correr `run`. Publicar el tablero en GitHub Pages (subruta
   `flujo-de-caja`) **solo si el usuario lo pide**, como los demás tableros.

## Reglas

- Nunca publicar el flujo en la carpeta de intercambio: esa carpeta la ve
  toda la biblioteca de Formulación, y esto es la caja de la empresa.
- Las ofertas por adjudicar van **aparte** (en el tablero, desmarcadas por
  defecto): una oferta se gana o se pierde entera.
