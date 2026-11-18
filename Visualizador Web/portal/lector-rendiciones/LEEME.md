# Lector con IA de «Rendiciones»

Sin este lector, «Rendiciones» del Portal lee cada foto en el navegador (Tesseract): es gratis, pero se
equivoca con papel arrugado o fotos oscuras. Con este lector, cada foto se lee con Claude y acierta mucho más.
Los PDF electrónicos se leen igual en los dos casos: traen su texto.

El lector es un Cloudflare Worker (gratis hasta 100.000 pedidos al día). Guarda la clave de Claude, que nunca
llega al navegador, y solo atiende a quien tiene la clave del equipo. No guarda las fotos. No necesita ningún
computador encendido.

## Costo

Cada foto usa unos 2.000 tokens de entrada y 400 de salida. Con `claude-opus-5-5` (US$4 y US$20 por millón),
cuesta unos US$0,016 por documento: una rendición de 10 boletas, unos US$0,16. Para bajarlo, cambia `MODELO` en
`worker.js` a `claude-sonnet-5-5` (unos US$0,008) o `claude-haiku-5-5` (menos de US$0,001); acierta algo menos.

## Instalar (una vez, unos 10 minutos)

1. Crea una clave de API en <https://console.anthropic.com> (Settings › API Keys) y carga saldo. Pon un límite
   de gasto mensual (Settings › Limits).
2. Crea una cuenta gratis en <https://dash.cloudflare.com>.
3. En esta carpeta, en una consola:
   ```
   npm install
   npx wrangler login
   npx wrangler secret put ANTHROPIC_API_KEY      (pega la clave del paso 1)
   npx wrangler secret put CLAVE_EQUIPO           (inventa una clave larga para el equipo)
   npx wrangler deploy
   ```
   `deploy` muestra la dirección del lector: `https://lector-rendiciones.<tu-cuenta>.workers.dev`.
4. En el Portal, Rendiciones › «Lectura en este navegador» (arriba a la derecha): pega la dirección y la clave
   del equipo, y toca Guardar. El Portal prueba la conexión antes de guardar. Cada persona lo hace una vez en
   su navegador.

## Cuidados

- La clave del equipo queda en el navegador de cada persona. Si alguien deja el equipo, cámbiala:
  `npx wrangler secret put CLAVE_EQUIPO` y avisa la nueva.
- El lector solo acepta pedidos desde `https://cristobal-monzo.github.io` (`ORIGENES` en `wrangler.toml`).
- Para cambiar el modelo o las instrucciones, edita `worker.js` y corre `npx wrangler deploy`.
- Si el lector no responde, el Portal avisa una vez y lee esa foto en el navegador: nada se pierde.
