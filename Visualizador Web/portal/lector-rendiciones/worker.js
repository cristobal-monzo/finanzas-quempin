/* lector-rendiciones — lee una boleta o factura con Claude para «Rendiciones» del Portal QUEMPIN (2026-11-18).

   Un Cloudflare Worker: guarda la clave de la API de Claude (secreto ANTHROPIC_API_KEY), que nunca llega al
   navegador, y solo atiende a quien manda la clave del equipo (secreto CLAVE_EQUIPO, en la cabecera x-clave) desde
   el sitio del Portal (ORIGENES). No guarda nada: recibe la foto, devuelve los datos y la olvida.

   GET  /  → {ok: true}            (el Portal lo usa para probar la dirección y la clave)
   POST /  {imagen: <base64>, tipo: "image/jpeg", hoy: "AAAA-MM-DD"}
         → {tipo, numero, fecha (AAAA-MM-DD), proveedor, rut, detalle, valor, dudas: [campos dudosos]}

   Instalar y actualizar: LEEME.md de esta carpeta. */
import Anthropic from '@anthropic-ai/sdk';

const MODELO = 'claude-opus-5-5';
const TIPOS = ['Factura', 'Boleta', 'Boleta de honorarios', 'Comprobante', 'Guía de despacho', 'Otro'];
const DETALLES = ['Combustible', 'Peajes', 'Estacionamiento', 'Transporte', 'Alojamiento', 'Colación', 'Materiales',
  'Herramientas', 'Insumos de oficina', 'Servicios', 'Otros'];
const CAMPOS = ['tipo', 'numero', 'fecha', 'proveedor', 'rut', 'detalle', 'valor'];
const MEDIOS = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_BASE64 = 7_000_000;   // ~5 MB de imagen

const ESQUEMA = {
  type: 'object',
  properties: {
    tipo: { type: 'string', enum: TIPOS },
    numero: { type: 'string' },
    fecha: { type: 'string' },
    proveedor: { type: 'string' },
    rut: { type: 'string' },
    detalle: { type: 'string', enum: DETALLES },
    valor: { type: 'integer' },
    dudas: { type: 'array', items: { type: 'string', enum: CAMPOS } }
  },
  required: ['tipo', 'numero', 'fecha', 'proveedor', 'rut', 'detalle', 'valor', 'dudas'],
  additionalProperties: false
};

function instrucciones(hoy) {
  return `Eres el asistente de rendiciones de gastos de una empresa chilena. La imagen es UN documento de gasto: una
boleta, factura, voucher de tarjeta, pasaje o comprobante (a menudo una foto de papel térmico arrugado).
Devuelve sus datos en el formato pedido:
- tipo: Factura, Boleta (también «válido como boleta» y boletas electrónicas), Boleta de honorarios, Guía de
  despacho, Comprobante (voucher, pasaje, e-ticket u otro sin valor tributario) u Otro.
- numero: el folio o N° del documento (en una factura o boleta, el N° junto a «FACTURA ELECTRÓNICA» o «BOLETA»;
  en un voucher, el N° de comprobante o boleta). Sin ceros a la izquierda. Nunca el N° de transacción, de caja,
  de sucursal ni un RUT.
- fecha: la fecha de emisión, en AAAA-MM-DD. Hoy es ${hoy}: un documento no puede ser del futuro.
- proveedor: la razón social del emisor (no el cliente: el cliente suele ser QUEMPIN SpA, RUT 76.772.215-K).
- rut: el RUT del emisor, con puntos y guion (76.123.456-7). Vacío si no aparece.
- detalle: la categoría del gasto.
- valor: el TOTAL pagado, con impuestos, en pesos enteros (nunca el neto ni el exento).
- dudas: los campos que no se leen con seguridad (borrosos, cortados, ambiguos). Un campo que no aparece va
  vacío ("" o 0) y en dudas. No inventes: es mejor una duda que un dato equivocado.`;
}

function responder(cuerpo, estado, cors) {
  return new Response(JSON.stringify(cuerpo), { status: estado, headers: { ...cors, 'content-type': 'application/json; charset=utf-8' } });
}

export default {
  async fetch(req, env) {
    const permitidos = String(env.ORIGENES || 'https://cristobal-monzo.github.io').split(',').map((s) => s.trim()).filter(Boolean);
    const origen = req.headers.get('origin') || '';
    const cors = {
      'access-control-allow-origin': permitidos.includes(origen) ? origen : permitidos[0],
      'access-control-allow-headers': 'content-type, x-clave',
      'access-control-allow-methods': 'GET, POST, OPTIONS',
      'access-control-max-age': '86400',
      vary: 'origin'
    };
    if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: cors });
    if (origen && !permitidos.includes(origen)) return responder({ error: 'origen no permitido' }, 403, cors);
    if (!env.CLAVE_EQUIPO || req.headers.get('x-clave') !== env.CLAVE_EQUIPO) return responder({ error: 'clave' }, 401, cors);
    if (req.method === 'GET') return responder({ ok: true, servicio: 'lector-rendiciones', modelo: MODELO }, 200, cors);
    if (req.method !== 'POST') return responder({ error: 'método' }, 405, cors);

    let datos;
    try { datos = await req.json(); } catch (e) { return responder({ error: 'json' }, 400, cors); }
    const imagen = datos && datos.imagen;
    const tipo = (datos && datos.tipo) || 'image/jpeg';
    const hoy = /^\d{4}-\d{2}-\d{2}$/.test((datos && datos.hoy) || '') ? datos.hoy : new Date().toISOString().slice(0, 10);
    if (typeof imagen !== 'string' || imagen.length < 100 || imagen.length > MAX_BASE64 || !MEDIOS.includes(tipo)) {
      return responder({ error: 'imagen' }, 400, cors);
    }

    const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
    let r;
    try {
      r = await client.beta.messages.create({
        model: MODELO,
        max_tokens: 4000,
        betas: ['server-side-fallback-2026-07-01'],
        fallbacks: 'default',
        output_config: { effort: 'low', format: { type: 'json_schema', schema: ESQUEMA } },
        system: instrucciones(hoy),
        messages: [{
          role: 'user',
          content: [
            { type: 'image', source: { type: 'base64', media_type: tipo, data: imagen } },
            { type: 'text', text: 'Lee este documento.' }
          ]
        }]
      });
    } catch (e) {
      if (e instanceof Anthropic.RateLimitError) return responder({ error: 'ocupado, intenta en un momento' }, 429, cors);
      if (e instanceof Anthropic.APIError) return responder({ error: 'claude ' + (e.status || '') }, 502, cors);
      return responder({ error: 'sin conexión con claude' }, 502, cors);
    }
    if (r.stop_reason === 'refusal') return responder({ error: 'no se pudo leer' }, 422, cors);
    const bloque = (r.content || []).find((b) => b.type === 'text');
    let salida;
    try { salida = JSON.parse(bloque ? bloque.text : ''); } catch (e) { return responder({ error: 'respuesta' }, 502, cors); }
    return responder(salida, 200, cors);
  }
};
