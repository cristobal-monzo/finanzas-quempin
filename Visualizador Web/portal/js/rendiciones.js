/* Portal QUEMPIN — Rendiciones (rd*).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Rendiciones (2026-11-18) --------------------------------------------------------------------------------
/* Pedido del usuario: la rendición de gastos (vale a rendir, recuperación de gastos, caja chica) con la lectura de cada
   boleta o factura en el momento de subirla, una tabla para corregir lo leído y elegir el proyecto de cada documento,
   un PDF con el resumen y una página por documento, y cada documento en la carpeta de su proyecto del Centro de Costos.
   Todo corre en el navegador: los PDF electrónicos traen su texto (pdf.js) y las fotos se leen con Tesseract; con el
   lector con IA configurado (lector-rendiciones/, un servicio aparte que guarda la clave de Claude) las fotos van a él.
   Las librerías se bajan de un CDN solo al usarlas. Lo que se lleva queda en este navegador (IndexedDB) hasta empezar
   otra rendición. Detalle: docs/rendiciones.md. */
const RD_LIB = {
  tesseract: ['https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js', 'Tesseract'],
  pdfjs: ['https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js', 'pdfjsLib'],
  jspdf: ['https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js', 'jspdf']
};
const RD_PDFJS_WORKER = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
const RD_TIPOS = { vale: 'Vale a rendir', recuperacion: 'Recuperación de Gastos', caja: 'Rendición Caja Chica' };
const RD_DOCS = ['Factura', 'Boleta', 'Boleta de honorarios', 'Comprobante', 'Guía de despacho', 'Otro'];
const RD_DETALLES = ['Combustible', 'Peajes', 'Estacionamiento', 'Transporte', 'Alojamiento', 'Colación', 'Materiales', 'Herramientas', 'Insumos de oficina', 'Servicios', 'Otros'];
const RD_CAMPOS = ['tipo', 'numero', 'fecha', 'proveedor', 'rut', 'detalle', 'valor'];
const RD_UNIDAD = 'Gastos Operaciones y Materiales';
const RD_RUT_QUEMPIN = '76772215K';
const RD_MAX_DOCS = 60;
const RD_MAX_PAGINAS = 6;               // de un PDF largo, solo las primeras páginas van al PDF de la rendición
const RD_EXT_CC = /\.(pdf|png|jpe?g|heic)$/i;   // las que acepta el Centro de Costos (documentos_cc.EXTENSIONES)
const RD_CLAVE_LECTOR = 'quempin_portal_rendiciones_lector';
const RD_CLAVE_DEUDOR = 'quempin_portal_rendiciones_deudor';
// Nombre y apellido de cada persona del equipo (pedido del usuario, 2026-11-18): el registro los lleva en «nombres»
const RD_NOMBRES = REG.nombres && typeof REG.nombres === 'object' ? REG.nombres : {};
const rdNombreUsuario = () => RD_NOMBRES[estado.usuario] || '';
const rdConApellido = (s) => texto(s).split(/\s+/).filter(Boolean).length >= 2;
const RD_MESES = { ENE: 1, FEB: 2, MAR: 3, ABR: 4, MAY: 5, JUN: 6, JUL: 7, AGO: 8, SEP: 9, SET: 9, OCT: 10, NOV: 11, DIC: 12 };
const RD_NOMBRE_MES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const rd = {
  cab: null, docs: [], recuperado: null, carpetas: null, envios: [], leyendoCarpeta: null, leidoCarpeta: 0,
  cola: Promise.resolve(), ocr: null, progreso: null, enviando: false, haciendoPdf: false, confirmarEnvio: false,
  confirmarNueva: 0, abierto: null, avisoIA: false, db: null, logo: undefined
};
// Punto de miles fijo, como numeros.js: no depende del idioma del navegador.
const rdMiles = (n) => String(Math.round(Math.abs(+n || 0))).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
const rdPesos = (n) => '$ ' + rdMiles(n);
const rdFechaCL = (iso) => (/^\d{4}-\d{2}-\d{2}$/.test(iso || '') ? iso.slice(8, 10) + '-' + iso.slice(5, 7) + '-' + iso.slice(0, 4) : '');

// ---- Leer el texto de una boleta o factura (solo calcula; lo prueba tests/portal/test_portal_rendiciones.py) ----------------------------
// Un monto escrito a la chilena: «70.780», «$ 6.190», «104.832,00», «70780».
function rdMonto(s) {
  const t = String(s === null || s === undefined ? '' : s).replace(/CLP|\$|\s/gi, '');
  if (/^\d{1,3}(\.\d{3})+(,\d{1,2})?$/.test(t)) return Math.round(+t.replace(/\./g, '').replace(',', '.'));
  if (/^\d{1,3}(,\d{3})+$/.test(t)) return +t.replace(/,/g, '');
  if (/^\d+(,\d{1,2})?$/.test(t)) return Math.round(+t.replace(',', '.'));
  return null;
}
function rdRutValido(cuerpo, dv) {
  let s = 0, m = 2;
  for (let i = cuerpo.length - 1; i >= 0; i--) { s += (+cuerpo[i]) * m; m = m === 7 ? 2 : m + 1; }
  const r = 11 - (s % 11);
  return (r === 11 ? '0' : r === 10 ? 'K' : String(r)) === String(dv).toUpperCase();
}
const rdRutFormato = (cuerpo, dv) => String(+cuerpo).replace(/\B(?=(\d{3})+(?!\d))/g, '.') + '-' + String(dv).toUpperCase();
function rdTitulo(s) {
  return String(s).toLowerCase().replace(/(^|[\s(.-])([a-záéíóúñü])/g, (m, a, b) => a + b.toUpperCase())
    .replace(/\bSpa\b/g, 'SpA').replace(/\bLtda\b\.?/g, 'Ltda.').replace(/\bS\.a\.?/g, 'S.A.').replace(/\bE\.i\.r\.l\.?/gi, 'E.I.R.L.');
}
/* Lo que se sabe de un documento a partir de su texto: tipo, N°, fecha (AAAA-MM-DD), proveedor, RUT, detalle (la
   categoría del gasto) y valor (el total pagado), y la lista «dudas» con los campos que conviene revisar.
   opciones.fuente: 'pdf' (texto exacto) u 'ocr'; opciones.confianza(token) → 0–100, de las palabras del OCR. */
function rdInterpretar(textoOriginal, opciones) {
  const op = opciones || {};
  const hoy = op.hoy ? new Date(op.hoy + 'T12:00:00') : new Date();
  const conf = typeof op.confianza === 'function' ? op.confianza : () => 100;
  const exacto = op.fuente === 'pdf';
  const lineas = String(textoOriginal || '').replace(/\r/g, '').split('\n').map((l) => l.replace(/[|]/g, ' ').replace(/\s+/g, ' ').trim()).filter(Boolean);
  const N = lineas.map((l) => norm(l).toUpperCase());
  const todo = N.join('\n');
  const r = { tipo: '', numero: '', fecha: '', proveedor: '', rut: '', detalle: '', valor: null, dudas: [] };
  const duda = (c) => { if (!r.dudas.includes(c)) r.dudas.push(c); };
  const dudoso = (token) => !exacto && conf(token) < 80;

  // Tipo
  if (/BOLETA\s+DE\s+HONORARIOS/.test(todo)) r.tipo = 'Boleta de honorarios';
  else if (/VALIDO\s+COMO\s+BOLETA|BOLETA\s+ELECTRONICA/.test(todo) || (/\bBOLETA\b/.test(todo) && !/FACTURA\s+ELECTRONICA/.test(todo))) r.tipo = 'Boleta';
  else if (/FACTURA/.test(todo)) r.tipo = 'Factura';
  else if (/GUIA\s+DE\s+DESPACHO/.test(todo)) r.tipo = 'Guía de despacho';
  else if (/VOUCHER|COMPROBANTE|TRANSBANK|REDCOMPRA|E-?TICKET|PASAJE|BOLETO/.test(todo)) r.tipo = 'Comprobante';
  else { r.tipo = 'Boleta'; duda('tipo'); }

  // RUT del emisor: el primero válido que no sea el de QUEMPIN, mejor si es de empresa (desde 50 millones)
  const ruts = [];
  const reRut = /(\d{1,2})[.,\s]?(\d{3})[.,\s]?(\d{3})\s*-\s*([0-9K])(?![0-9A-Z])/g;
  let m;
  while ((m = reRut.exec(todo))) {
    const cuerpo = m[1] + m[2] + m[3];
    if (cuerpo + m[4] === RD_RUT_QUEMPIN) continue;
    ruts.push({ cuerpo, dv: m[4], ok: rdRutValido(cuerpo, m[4]), empresa: +cuerpo >= 50000000, i: m.index });
  }
  ruts.sort((a, b) => (b.ok - a.ok) || (b.empresa - a.empresa) || (a.i - b.i));
  if (ruts.length) {
    const x = ruts[0];
    r.rut = rdRutFormato(x.cuerpo, x.dv);
    if (!x.ok || !x.empresa || dudoso(x.cuerpo.slice(-3))) duda('rut');
  }

  // N° del documento
  const cands = [];
  const EXCL = /TRANSACCI|RESERVA|SUCURSAL|ASIENTO|\bCAJA\b|TARJETA|OPERACI|AUTORIZ|CLIENTE|TELEF|FONO|CUENTA|PEDIDO|ORDEN|RESOLUCI|\bRES\b|TERMINAL|\bLOCAL\b|CODIGO|\bCOD\b|CELULAR|DIRECCI|PATENTE|VENDEDOR/;
  const deRut = (num) => ruts.some((x) => (x.cuerpo + x.dv).startsWith(num)) || num === RD_RUT_QUEMPIN.slice(0, num.length);
  N.forEach((l, i) => {
    const add = (num, pts) => { if (num && !deRut(num)) cands.push({ num, pts, i }); };
    let x;
    if ((x = l.match(/(?:FACTURA|BOLETA)[^0-9]{0,40}?\bN\s*[°ºO*]?\s*[:.]?\s*(\d{3,12})\b/))) add(x[1], 6);
    if (!EXCL.test(l)) {
      if ((x = l.match(/(?:\bN\s*[°º*]|\bNRO\b\.?|\bNUMERO\b|\bFOLIO\b|\bN[O0]\.)\s*[:.]?\s*(\d{3,12})\b/))) add(x[1], 4);
      else if ((x = l.match(/\bN[I1L9]\s*[:.]?\s+(\d{5,12})\b/))) add(x[1], 3);      // «N°» mal leído
      if (/(?:\bN\s*[°º]|\bNRO\b|\bFOLIO\b)[^0-9]*$/.test(l) && i + 1 < N.length) {
        const y = N[i + 1].match(/^\D{0,3}(\d{3,12})\b/);
        if (y) add(y[1], 2);
      }
    }
    if ((x = l.match(/\bBOLETO\b[^0-9]{0,6}(\d{6,12})\b/))) add(x[1], 3);
    if ((x = l.match(/\bCOMPR[OA0]BANTE\b\s*[:.]?\s*(\d{3,12})\b/))) add(x[1], 3);
    // El código único de un documento electrónico: <RUT emisor>_<tipo SII>_<folio> (39 boleta, 33/34 factura)
    if ((x = l.match(/\d{7,8}_(?:33|34|39|41)_(\d{1,12})\b/))) add(x[1], 5);
  });
  cands.sort((a, b) => (b.pts - a.pts) || (a.i - b.i));
  if (cands.length) {
    r.numero = cands[0].num.replace(/^0+(?=\d)/, '');
    if (cands[0].pts < 4 || dudoso(cands[0].num)) duda('numero');
  } else duda('numero');

  // Fecha: la de una línea con «Fecha» o «Emisión» primero; solo del último año (no del futuro)
  const fechas = [];
  const pon = (a, mes, d, i, pts, txt) => {
    a = +a;
    if (a < 100) a += 2000;
    const f = new Date(a, mes - 1, +d);
    if (!mes || f.getFullYear() !== a || f.getMonth() !== mes - 1 || f.getDate() !== +d) return;
    fechas.push({ a, mes, d: +d, i, pts, txt });
  };
  N.forEach((l, i) => {
    const extra = /FECHA|EMISION|EMITID/.test(l) ? 2 : 0;
    let x;
    const re1 = /\b(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4}|\d{2})\b/g;
    while ((x = re1.exec(l))) pon(x[3], +x[2], x[1], i, 1 + extra, x[0]);
    const re2 = extra ? /\b(\d{4})\s*[/\-.\s]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\b/g : /\b(\d{4})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\b/g;
    while ((x = re2.exec(l))) pon(x[1], +x[2], x[3], i, 1 + extra, x[0]);
    const re3 = /\b(\d{1,2})\s*(?:DE\s+)?(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|SET|OCT|NOV|DIC)[A-Z]*\.?\s*(?:DE\s+|DEL\s+)?(\d{4})\b/g;
    while ((x = re3.exec(l))) pon(x[3], RD_MESES[x[2]], x[1], i, 1 + extra, x[0]);
  });
  const desde = new Date(hoy); desde.setDate(desde.getDate() - 400);
  const hasta = new Date(hoy); hasta.setDate(hasta.getDate() + 2);
  const iso = (f) => f.a + '-' + String(f.mes).padStart(2, '0') + '-' + String(f.d).padStart(2, '0');
  const orden = (a, b) => (b.pts - a.pts) || (a.i - b.i);
  const buenas = fechas.filter((f) => { const x = new Date(f.a, f.mes - 1, f.d); return x >= desde && x <= hasta; }).sort(orden);
  if (buenas.length) {
    r.fecha = iso(buenas[0]);
    if (dudoso(buenas[0].txt.replace(/\D/g, '').slice(-4))) duda('fecha');
  } else if (fechas.length) {
    // Año mal leído («2076»): sirven el día y el mes, con el año más reciente que no quede en el futuro
    const f = fechas.sort(orden)[0];
    let a = hoy.getFullYear();
    if (new Date(a, f.mes - 1, f.d) > hasta) a -= 1;
    r.fecha = iso({ a, mes: f.mes, d: f.d });
    duda('fecha');
  } else duda('fecha');

  // Valor: el TOTAL (no el neto ni el exento); si neto + IVA da justo un total, está confirmado
  const montosDe = (l) => {
    const s = l.replace(/\(?\d{1,2}([.,]\d+)?\s*%\)?/g, ' ');
    const out = [];
    let x;
    const re = /(\d[\d.,]*\d|\d)/g;
    while ((x = re.exec(s))) { const v = rdMonto(x[1]); if (v !== null && v > 0) out.push({ v, txt: x[1] }); }
    return out;
  };
  const totales = [];
  N.forEach((l, i) => {
    if (!/TOTAL/.test(l) || /SUB\s*TOTAL|TOTAL\s*(NETO|EXENTO|AFECTO|IVA|DESC|ITEM|ARTIC)/.test(l.slice(l.lastIndexOf('TOTAL') - 4))) return;
    let ms = montosDe(l.slice(l.lastIndexOf('TOTAL')));
    if (!ms.length && i + 1 < N.length) ms = montosDe(N[i + 1]);
    if (!ms.length) return;
    const pts = /MONTO\s+TOTAL|TOTAL\s+A\s+PAGAR|TOTAL\s*\$|TOTAL\s*:/.test(l) ? 3 : 2;
    totales.push({ v: ms[ms.length - 1].v, txt: ms[ms.length - 1].txt, pts, i });
  });
  const primero = (re) => {
    for (const l of N) {
      const k = l.search(re);
      if (k < 0) continue;
      const ms = montosDe(l.slice(k));
      if (ms.length) return ms[ms.length - 1].v;
    }
    return null;
  };
  const neto = primero(/\bNETO\b/);
  const iva = primero(/\bI\.?\s?V\.?\s?A\b/);
  const exento = primero(/\bEXENTO\b/) || 0;
  totales.sort((a, b) => (b.pts - a.pts) || (b.i - a.i));
  let cuadra = false;
  if (neto && iva) {
    const suma = neto + iva + exento;
    if (totales.some((x) => x.v === suma) || totales.some((x) => x.v === neto + iva)) { r.valor = totales.some((x) => x.v === suma) ? suma : neto + iva; cuadra = true; }
    else if (!totales.length) r.valor = suma;
  }
  if (r.valor === null && totales.length) r.valor = totales[0].v;
  if (r.valor === null) {
    const montos = [];
    N.forEach((l) => { const k = l.search(/\$|MONTO|VALOR/); if (k >= 0) montosDe(l.slice(k)).forEach((x) => montos.push(x.v)); });
    if (montos.length) r.valor = Math.max(...montos);
  }
  if (r.valor !== null && r.valor > 50000000) r.valor = null;
  if (r.valor === null) duda('valor');
  else if (!cuadra) {
    const t0 = totales.find((x) => x.v === r.valor);
    if (new Set(totales.map((x) => x.v)).size > 1 || !t0 || dudoso(t0.txt)) duda('valor');
  }

  // Proveedor: la razón social (una línea con SpA, Ltda., S.A.…) o una marca conocida
  const MARCAS = [[/\bCOPEC\b/, 'Copec'], [/\bSHELL\b/, 'Shell'], [/PETROBRAS/, 'Petrobras'], [/ARAMCO|ESMAX/, 'Aramco (Esmax)'], [/\bENEX\b/, 'Enex'],
    [/\bTERPEL\b/, 'Terpel'], [/TUR\s?BUS/, 'Turbus'], [/PULLMAN/, 'Pullman Bus'], [/SODIMAC|HOMECENTER/, 'Sodimac'], [/\bEASY\b/, 'Easy'],
    [/CONSTRUMART/, 'Construmart'], [/CHILEMAT/, 'Chilemat'], [/\bLIDER\b|WALMART/, 'Líder'], [/\bJUMBO\b/, 'Jumbo'], [/UNIMARC/, 'Unimarc'],
    [/SANTA ISABEL/, 'Santa Isabel'], [/TOTTUS/, 'Tottus'], [/ARAMARK/, 'Aramark'], [/MCDONALD/, "McDonald's"], [/STARBUCKS/, 'Starbucks'],
    [/\bUBER\b/, 'Uber'], [/CABIFY/, 'Cabify'], [/\bLATAM\b/, 'LATAM'], [/JETSMART/, 'JetSMART'], [/SKY AIRLINE/, 'Sky Airline']];
  const SUFIJO = /(^|\s)(S\.?\s?P\.?\s?A\.?|LTDA\.?|LIMITADA|S\.\s?A\.?|E\.?\s?I\.?\s?R\.?\s?L\.?)(?=\s|$|[.,])/;
  for (let i = 0; i < N.length && i < 30; i++) {
    const l = N[i];
    if (!SUFIJO.test(l) || /QUEMPIN|MANDANTE|RAZON SOCIAL|SENOR|CLIENTE/.test(l)) continue;
    let p = lineas[i].replace(/^(raz[oó]n social|nombre|emisor)\s*:?\s*/i, '').replace(/\s*R\.?\s*U\.?\s*T\.?.*$/i, '').replace(/^[^A-Za-zÁÉÍÓÚÑáéíóúñ]+/, '');
    // Al menos 4 letras sin contar el sufijo: «Ca SpA» es una lectura rota, no un nombre
    const sinSufijo = norm(p).toUpperCase().replace(SUFIJO, ' ');
    if (sinSufijo.replace(/[^A-Z]/g, '').length >= 4) { r.proveedor = rdTitulo(p).slice(0, 70); break; }
  }
  if (!r.proveedor) {
    const marca = MARCAS.find(([re]) => re.test(todo));
    if (marca) r.proveedor = marca[1];
    else duda('proveedor');
  }

  // Detalle: la categoría del gasto, por palabras del documento
  const REGLAS = [
    ['Combustible', /DIESEL|PETROLEO|GASOLINA|BENCINA|COMBUSTIBLE|COPEC|\bSHELL\b|PETROBRAS|ARAMCO|ESMAX|\bENEX\b|TERPEL|KEROSEN|\bLITROS?\b/],
    ['Peajes', /PEAJE|AUTOPISTA|PASE DIARIO|VESPUCIO|COSTANERA|AUTOPASE|\bTAG\b/],
    ['Estacionamiento', /ESTACIONAMIENTO|PARKING|PARQUIMETRO/],
    ['Alojamiento', /HOTEL|HOSTAL|ALOJAMIENTO|HOSPEDAJE|CABANA|AIRBNB/],
    ['Transporte', /PASAJE|\bBUS\b|TUR\s?BUS|PULLMAN|TRANSPORTE|TAXI|\bUBER\b|CABIFY|\bDIDI\b|\bMETRO\b|TRANSFER|BOLETO|LATAM|JETSMART|SKY AIRLINE|VUELO/],
    ['Colación', /RESTAURANT|RESTORAN|COLACION|ALMUERZO|COMIDA|\bCAFE\b|CAFETERIA|ARAMARK|SANDWICH|\bMENU\b|BEBIDA|PIZZA|SUSHI|MCDONALD|BURGER|STARBUCKS|PANADERIA|FUENTE DE SODA/],
    ['Materiales', /FERRETERIA|SODIMAC|\bEASY\b|CONSTRUMART|CHILEMAT|IMPERIAL|MATERIAL|TORNILL|PERNO|CABLE|\bTUBO|\bPVC\b|CEMENTO|PINTURA|MADERA|FITTING|VALVULA|ABRAZADERA/],
    ['Insumos de oficina', /LIBRERIA|PAPELERIA|RESMA|TONER|IMPRESION|FOTOCOPIA/]
  ];
  const regla = REGLAS.find(([, re]) => re.test(todo));
  if (regla) r.detalle = regla[0];
  else { r.detalle = 'Otros'; duda('detalle'); }
  return r;
}
// La confianza del OCR en un número: la menor de las palabras que lo contienen
function rdConfianza(palabras) {
  return (token) => {
    const d = String(token).replace(/\D/g, '');
    if (!d) return 100;
    let min = null;
    (palabras || []).forEach((p) => {
      const w = String(p.t).replace(/\D/g, '');
      if (w.length >= 2 && (w.includes(d) || d.includes(w))) min = min === null ? p.c : Math.min(min, p.c);
    });
    return min === null ? 100 : min;
  };
}
// Lo que devuelve el lector con IA → los mismos campos
function rdDeIA(j) {
  j = j || {};
  const r = {
    tipo: RD_DOCS.includes(j.tipo) ? j.tipo : 'Boleta',
    numero: texto(j.numero).replace(/^0+(?=\d)/, '').slice(0, 30),
    fecha: /^\d{4}-\d{2}-\d{2}$/.test(texto(j.fecha)) ? texto(j.fecha) : '',
    proveedor: texto(j.proveedor).slice(0, 70),
    rut: texto(j.rut).slice(0, 14),
    detalle: texto(j.detalle).slice(0, 40) || 'Otros',
    valor: Number.isFinite(+j.valor) && +j.valor > 0 ? Math.round(+j.valor) : null,
    dudas: Array.isArray(j.dudas) ? j.dudas.filter((c) => RD_CAMPOS.includes(c)) : []
  };
  if (!r.fecha && !r.dudas.includes('fecha')) r.dudas.push('fecha');
  if (r.valor === null && !r.dudas.includes('valor')) r.dudas.push('valor');
  if (!r.numero && !r.dudas.includes('numero')) r.dudas.push('numero');
  return r;
}
window.QRendiciones = { interpretar: rdInterpretar, monto: rdMonto, deIA: rdDeIA };

// ---- Librerías, imágenes y PDF de entrada ------------------------------------------------------------------
const rdLibs = {};
function rdLib(clave) {
  const [url, global] = RD_LIB[clave];
  if (window[global]) return Promise.resolve(window[global]);
  if (!rdLibs[clave]) {
    rdLibs[clave] = new Promise((listo, mal) => {
      const s = document.createElement('script');
      s.src = url;
      s.crossOrigin = 'anonymous';
      s.onload = () => (window[global] ? listo(window[global]) : mal(new Error('sin ' + global)));
      s.onerror = () => { delete rdLibs[clave]; s.remove(); mal(new Error('sin conexión con ' + url)); };
      document.head.append(s);
    });
  }
  return rdLibs[clave];
}
async function rdImagen(blob) {
  if (window.createImageBitmap) {
    try { return await createImageBitmap(blob, { imageOrientation: 'from-image' }); } catch (e) { /* el navegador no la abre así */ }
  }
  const url = URL.createObjectURL(blob);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    return img;
  } finally { setTimeout(() => URL.revokeObjectURL(url), 2000); }
}
async function rdCargarImagen(dataUrl) {
  const img = new Image();
  img.src = dataUrl;
  await img.decode();
  return img;
}
// Un lienzo con la imagen girada (0, 90, 180, 270 a la derecha) y escalada; gris = para el OCR (gris y contraste)
function rdLienzo(fuente, op) {
  const o = op || {};
  const w0 = fuente.naturalWidth || fuente.width, h0 = fuente.naturalHeight || fuente.height;
  const largo = Math.max(w0, h0);
  let k = 1;
  if (o.max && largo > o.max) k = o.max / largo;
  if (o.min && largo < o.min) k = Math.min(3, o.min / largo);
  // area = tope de píxeles (para el OCR): una boleta larga y angosta no se achica por su largo
  if (o.area && w0 * h0 * k * k > o.area) k = Math.sqrt(o.area / (w0 * h0));
  const w = Math.max(1, Math.round(w0 * k)), h = Math.max(1, Math.round(h0 * k));
  const rot = ((o.rot || 0) % 360 + 360) % 360;
  const c = document.createElement('canvas');
  c.width = rot % 180 ? h : w;
  c.height = rot % 180 ? w : h;
  const x = c.getContext('2d');
  x.fillStyle = '#ffffff';
  x.fillRect(0, 0, c.width, c.height);
  x.imageSmoothingQuality = 'high';
  x.translate(c.width / 2, c.height / 2);
  x.rotate(rot * Math.PI / 180);
  x.drawImage(fuente, -w / 2, -h / 2, w, h);
  if (o.gris) {
    const d = x.getImageData(0, 0, c.width, c.height);
    const p = d.data;
    const hist = new Uint32Array(256);
    for (let i = 0; i < p.length; i += 4) { const g = (p[i] * 299 + p[i + 1] * 587 + p[i + 2] * 114) / 1000 | 0; p[i] = g; hist[g]++; }
    const total = p.length / 4;
    let bajo = 0, alto = 255, s = 0;
    for (let i = 0; i < 256; i++) { s += hist[i]; if (s > total * 0.02) { bajo = i; break; } }
    s = 0;
    for (let i = 255; i >= 0; i--) { s += hist[i]; if (s > total * 0.02) { alto = i; break; } }
    const rango = Math.max(1, alto - bajo);
    for (let i = 0; i < p.length; i += 4) { const g = Math.max(0, Math.min(255, (p[i] - bajo) * 255 / rango)); p[i] = p[i + 1] = p[i + 2] = g; }
    x.putImageData(d, 0, 0);
  }
  return c;
}
async function rdPdfAbrir(blob) {
  const lib = await rdLib('pdfjs');
  lib.GlobalWorkerOptions.workerSrc = RD_PDFJS_WORKER;
  return lib.getDocument({ data: new Uint8Array(await blob.arrayBuffer()) }).promise;
}
// El texto de las primeras páginas, línea por línea (las piezas de igual altura forman una línea)
async function rdPdfTexto(pdf) {
  const lineas = [];
  for (let n = 1; n <= Math.min(pdf.numPages, 3); n++) {
    const pag = await pdf.getPage(n);
    const c = await pag.getTextContent();
    const filas = new Map();
    c.items.forEach((it) => {
      if (!it.str || !it.str.trim()) return;
      const y = Math.round(it.transform[5] / 2.5);
      if (!filas.has(y)) filas.set(y, []);
      filas.get(y).push(it);
    });
    [...filas.keys()].sort((a, b) => b - a).forEach((y) => {
      lineas.push(filas.get(y).sort((a, b) => a.transform[4] - b.transform[4]).map((it) => it.str.trim()).join(' '));
    });
  }
  return lineas.join('\n');
}
async function rdPdfPaginas(pdf) {
  const salida = [];
  for (let n = 1; n <= Math.min(pdf.numPages, RD_MAX_PAGINAS); n++) {
    const pag = await pdf.getPage(n);
    const base = pag.getViewport({ scale: 1 });
    const vp = pag.getViewport({ scale: Math.min(3, 1500 / Math.max(base.width, base.height)) });
    const c = document.createElement('canvas');
    c.width = Math.round(vp.width);
    c.height = Math.round(vp.height);
    const x = c.getContext('2d');
    x.fillStyle = '#ffffff';
    x.fillRect(0, 0, c.width, c.height);
    await pag.render({ canvasContext: x, viewport: vp }).promise;
    salida.push(c.toDataURL('image/jpeg', 0.85));
  }
  return salida;
}
async function rdOcr(lienzo) {
  if (!rd.ocr) {
    rd.ocr = rdLib('tesseract').then((T) => T.createWorker('spa', 1, {
      logger: (msg) => { if (msg && msg.status === 'recognizing text' && rd.progreso) rd.progreso(msg.progress); }
    }));
    rd.ocr.catch(() => { rd.ocr = null; });
  }
  const w = await rd.ocr;
  const { data } = await w.recognize(lienzo);
  return { texto: data.text || '', conf: data.confidence || 0, palabras: (data.words || []).map((p) => ({ t: p.text, c: p.confidence })) };
}
function rdLectorIA() {
  const l = leer(RD_CLAVE_LECTOR, null);
  return l && /^https:\/\//.test(texto(l.url)) ? { url: texto(l.url), clave: texto(l.clave) } : null;
}
async function rdLeerConIA(ia, d) {
  const img = await rdCargarImagen(d.paginas[0]);
  const datos = rdLienzo(img, { max: 1600, rot: d.rot }).toDataURL('image/jpeg', 0.85);
  const res = await fetch(ia.url, {
    method: 'POST', headers: { 'content-type': 'application/json', 'x-clave': ia.clave },
    body: JSON.stringify({ imagen: datos.split(',')[1], tipo: 'image/jpeg', hoy: rdHoy() })
  });
  if (!res.ok) throw new Error('el lector con IA respondió ' + res.status);
  return rdDeIA(await res.json());
}
function rdHoy() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

// ---- Leer un documento -------------------------------------------------------------------------------------
async function rdLeer(d) {
  if (!rd.docs.includes(d)) return;
  d.estado = 'leyendo';
  d.progreso = 0;
  d.error = '';
  rdPintarFila(d);
  rdPintarResumen();
  try {
    let txt = '', fuente = 'ocr', base = null;
    if (d.esPdf) {
      const pdf = await rdPdfAbrir(d.archivo);
      d.paginasTotal = pdf.numPages;
      if (!d.paginas.length) d.paginas = await rdPdfPaginas(pdf);
      txt = await rdPdfTexto(pdf);
      if (norm(txt).replace(/[^a-z0-9]/g, '').length >= 40) fuente = 'pdf';
    } else if (!d.paginas.length) {
      try { base = await rdImagen(d.archivo); } catch (e) { throw new Error('heic'); }
      d.paginas = [rdLienzo(base, { max: 1800 }).toDataURL('image/jpeg', 0.82)];
    }
    if (d.paginas.length) d.mini = rdLienzo(await rdCargarImagen(d.paginas[0]), { max: 160, rot: d.rot }).toDataURL('image/jpeg', 0.7);
    rdPintarFila(d);
    let campos = null;
    const ia = fuente === 'pdf' ? null : rdLectorIA();
    if (ia && d.paginas.length) {
      try { campos = await rdLeerConIA(ia, d); d.fuente = 'ia'; } catch (e) {
        console.error(e);
        if (!rd.avisoIA) { rd.avisoIA = true; avisar('El lector con IA no respondió: se lee en este navegador.'); }
      }
    }
    if (!campos) {
      let palabras = [];
      if (fuente !== 'pdf') {
        if (!d.paginas.length) throw new Error('sin imagen');
        // Se lee la foto original (la copia guardada está achicada); al volver a leer, desde el archivo
        let img = base;
        if (!img) { try { img = await rdImagen(d.archivo); } catch (e) { img = await rdCargarImagen(d.paginas[0]); } }
        rd.progreso = (p) => { d.progreso = p; rdPintarLectura(d); };
        let o = await rdOcr(rdLienzo(img, { area: 6e6, min: 1800, rot: d.rot, gris: true }));
        // Una foto de lado se lee mal: se prueba girada y queda la vuelta que mejor se lee
        if (o.conf < 45 && norm(o.texto).replace(/[^a-z0-9]/g, '').length < 120) {
          for (const g of [90, 270]) {
            const rot = (d.rot + g) % 360;
            const o2 = await rdOcr(rdLienzo(img, { area: 6e6, min: 1800, rot, gris: true }));
            if (o2.conf > o.conf + 10) { o = o2; d.rot = rot; }
          }
          d.mini = rdLienzo(img, { max: 160, rot: d.rot }).toDataURL('image/jpeg', 0.7);
        }
        rd.progreso = null;
        txt = o.texto;
        palabras = o.palabras;
      }
      campos = rdInterpretar(txt, { fuente, confianza: rdConfianza(palabras) });
      d.fuente = fuente;
    }
    d.texto = String(txt || '').slice(0, 4000);
    RD_CAMPOS.forEach((c) => { if (!d.editado.includes(c)) d.campos[c] = campos[c] === undefined ? d.campos[c] : campos[c]; });
    d.dudas = campos.dudas.filter((c) => !d.editado.includes(c));
    d.estado = 'listo';
  } catch (e) {
    console.error(e);
    rd.progreso = null;
    d.estado = 'error';
    d.error = String(e && e.message) === 'heic' ? 'Este navegador no abre esta foto (HEIC). Llena los datos a mano.'
      : /conexi/i.test(String(e && e.message)) ? 'Sin internet para leerla. Llena los datos a mano.' : 'No se pudo leer. Llena los datos a mano.';
    d.dudas = RD_CAMPOS.filter((c) => !d.editado.includes(c) && !d.campos[c] && c !== 'rut');
  }
  rdPeriodoAuto();
  rdGuardar();
  rdPintarFila(d);
  rdPintarResumen();
}
function rdEncolar(d) {
  rd.cola = rd.cola.then(() => rdLeer(d)).catch((e) => console.error(e));
}

// ---- Agregar, quitar y guardar en este navegador -------------------------------------------------------------
function rdCabNueva() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return {
    tipo: 'recuperacion', deudor: texto(leer(RD_CLAVE_DEUDOR, '')) || rdNombreUsuario(), periodo: '', periodoAMano: false, unidad: RD_UNIDAD,
    numero: 'R-' + d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '-' + p(d.getHours()) + p(d.getMinutes()) + (estado.usuario ? '-' + estado.usuario : ''),
    valeMonto: null, valeFecha: '', ultimoProyecto: '', enviada: null, pdf: false
  };
}
async function rdAgregar(lista) {
  // Copia antes de esperar: borrar el valor del campo vacía su FileList (es la misma lista, viva).
  const archivos = Array.from(lista || []);
  if (!rd.recuperado) rd.recuperado = rdRecuperar();
  await rd.recuperado;
  if (!rd.cab) rd.cab = rdCabNueva();
  const malos = [];
  archivos.forEach((f) => {
    const esPdf = /\.pdf$/i.test(f.name) || f.type === 'application/pdf';
    const esImg = /^image\//.test(f.type) || /\.(jpe?g|png|heic|heif|webp|gif|bmp)$/i.test(f.name);
    if (!esPdf && !esImg) { malos.push(f.name + ' (no es foto ni PDF)'); return; }
    if (!f.size) { malos.push(f.name + ' (está vacío)'); return; }
    if (f.size > SC_MAX) { malos.push(f.name + ' (más de 25 MB)'); return; }
    if (rd.docs.length >= RD_MAX_DOCS) { malos.push(f.name + ' (más de ' + RD_MAX_DOCS + ' documentos)'); return; }
    if (rd.docs.some((d) => d.nombre === f.name && d.archivo.size === f.size)) { malos.push(f.name + ' (ya está)'); return; }
    const d = {
      id: scId().slice(0, 12), nombre: f.name, archivo: f, esPdf, rot: 0, paginas: [], paginasTotal: 1, mini: '', fuente: '',
      campos: { tipo: '', numero: '', fecha: '', proveedor: '', rut: '', detalle: '', proyecto: rd.cab.ultimoProyecto || '', valor: null },
      dudas: [], editado: [], estado: 'pendiente', error: '', texto: ''
    };
    rd.docs.push(d);
    rdEncolar(d);
  });
  if (rd.cab.enviada) rd.cab.enviada = null;     // con documentos nuevos, la rendición se puede volver a enviar
  rdGuardar();
  rdPintar();
  if (malos.length) avisar('No se agregó: ' + malos.join('; ') + '.');
}
// Otra boleta de la misma foto (observación de LC, 2026-11-23): una fila nueva justo debajo, con la misma imagen y lo que
// suele repetirse (tipo, fecha, proveedor, detalle, proyecto); el N° y el valor quedan por llenar. No se vuelve a leer.
function rdOtra(d) {
  if (rd.docs.length >= RD_MAX_DOCS) { avisar('Una rendición lleva hasta ' + RD_MAX_DOCS + ' documentos.'); return; }
  const c = d.campos;
  const n = {
    id: scId().slice(0, 12), nombre: d.nombre, archivo: d.archivo, esPdf: d.esPdf, rot: d.rot, paginas: d.paginas, paginasTotal: d.paginasTotal,
    mini: d.mini, fuente: d.fuente, texto: d.texto, error: '', estado: d.estado === 'error' ? 'error' : 'listo',
    campos: { tipo: c.tipo, numero: '', fecha: c.fecha, proveedor: c.proveedor, rut: c.rut, detalle: c.detalle, proyecto: c.proyecto, valor: null },
    dudas: ['numero', 'valor'], editado: ['tipo', 'fecha', 'proveedor', 'rut', 'detalle', 'proyecto']
  };
  if (n.estado === 'error') n.error = 'Otra boleta de la misma foto: llena sus datos.';
  // Sin el foco en la tabla, rdPintar la rehace entera y la fila nueva queda en su lugar (no al final)
  if (document.activeElement && $('#rdFilas').contains(document.activeElement)) document.activeElement.blur();
  rd.docs.splice(rd.docs.indexOf(d) + 1, 0, n);
  if (rd.cab.enviada) rd.cab.enviada = null;
  rd.confirmarEnvio = false;
  rdGuardar();
  rdPintar();
  const casilla = document.querySelector('#rdFilas tr[data-id="' + n.id + '"] [data-campo="numero"]');
  if (casilla) casilla.focus();
}
// «Están bien»: lo que quedó en naranjo se compara con la foto y se da por bueno sin tener que cambiarlo (observación de LC,
// 2026-11-23: antes había que cambiar el dato y volver a ponerlo)
function rdConfirmar(d) {
  if (document.activeElement && $('#rdFilas').contains(document.activeElement)) document.activeElement.blur();
  d.dudas = d.dudas.filter((c) => c === 'valor' ? !d.campos.valor : !texto(d.campos[c]));
  rd.confirmarEnvio = false;
  rdGuardar();
  rdPintarFila(d);
  rdPintarResumen();
}
function rdQuitar(d) {
  if (document.activeElement && $('#rdFilas').contains(document.activeElement)) document.activeElement.blur();
  rd.docs = rd.docs.filter((x) => x !== d);
  rdPeriodoAuto();
  rdGuardar();
  rdPintar();
}
function rdDb() {
  if (!rd.db) {
    rd.db = new Promise((listo, mal) => {
      const r = indexedDB.open('qpn-rendiciones', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('borrador');
      r.onsuccess = () => listo(r.result);
      r.onerror = () => mal(r.error);
    });
    rd.db.catch(() => { rd.db = null; });
  }
  return rd.db;
}
async function rdGuardarYa() {
  try {
    const db = await rdDb();
    const tx = db.transaction('borrador', 'readwrite');
    tx.objectStore('borrador').put({
      cab: rd.cab,
      docs: rd.docs.map((d) => ({
        id: d.id, nombre: d.nombre, archivo: d.archivo, esPdf: d.esPdf, rot: d.rot, paginas: d.paginas, paginasTotal: d.paginasTotal,
        mini: d.mini, fuente: d.fuente, campos: d.campos, dudas: d.dudas, editado: d.editado, error: d.error, texto: d.texto,
        estado: d.estado === 'leyendo' || d.estado === 'pendiente' ? 'pendiente' : d.estado
      }))
    }, 'actual');
    await new Promise((listo, mal) => { tx.oncomplete = listo; tx.onerror = () => mal(tx.error); tx.onabort = () => mal(tx.error); });
  } catch (e) { console.warn('La rendición no se pudo guardar en este navegador', e); }
}
let rdRelojGuardar = null;
function rdGuardar() {
  clearTimeout(rdRelojGuardar);
  rdRelojGuardar = setTimeout(rdGuardarYa, 400);
}
async function rdRecuperar() {
  rd.cab = rdCabNueva();
  try {
    const db = await rdDb();
    const v = await new Promise((listo, mal) => {
      const r = db.transaction('borrador').objectStore('borrador').get('actual');
      r.onsuccess = () => listo(r.result);
      r.onerror = () => mal(r.error);
    });
    if (v && v.cab) {
      rd.cab = Object.assign(rdCabNueva(), v.cab);
      rd.docs = (v.docs || []).filter((d) => d && d.archivo).map((d) => Object.assign({ paginas: [], editado: [], dudas: [], mini: '' }, d));
      rd.docs.filter((d) => d.estado === 'pendiente').forEach(rdEncolar);
    }
  } catch (e) { /* sin IndexedDB (ventana privada): la rendición vive solo en esta visita */ }
}
function rdNueva() {
  const sinTerminar = rd.docs.length && !rd.cab.enviada && !rd.cab.pdf;
  if (sinTerminar && Date.now() - rd.confirmarNueva > 5000) {
    rd.confirmarNueva = Date.now();
    $('#rdNueva').textContent = '¿Borrar la actual? Toca otra vez';
    setTimeout(() => { $('#rdNueva').textContent = 'Nueva rendición'; }, 5000);
    return;
  }
  rd.confirmarNueva = 0;
  $('#rdNueva').textContent = 'Nueva rendición';
  rd.docs = [];
  rd.cab = rdCabNueva();
  rd.confirmarEnvio = false;
  rdGuardar();
  rdPintarCab();
  rdPintar();
}
// El período sale solo de las fechas («Octubre - Noviembre 2026»), salvo que se haya escrito a mano
function rdPeriodoAuto() {
  if (rd.cab.periodoAMano) return;
  const f = rd.docs.map((d) => d.campos.fecha).filter((x) => /^\d{4}-\d{2}/.test(x || '')).sort();
  let p = '';
  if (f.length) {
    const [a1, m1] = f[0].split('-').map(Number);
    const [a2, m2] = f[f.length - 1].split('-').map(Number);
    p = a1 === a2 && m1 === m2 ? RD_NOMBRE_MES[m1 - 1] + ' ' + a1
      : a1 === a2 ? RD_NOMBRE_MES[m1 - 1] + ' - ' + RD_NOMBRE_MES[m2 - 1] + ' ' + a2
      : RD_NOMBRE_MES[m1 - 1] + ' ' + a1 + ' - ' + RD_NOMBRE_MES[m2 - 1] + ' ' + a2;
  }
  rd.cab.periodo = p;
  const c = $('#rdPeriodo');
  if (c && document.activeElement !== c) c.value = p;
}

// ---- Proyectos: las carpetas del Centro de Costos y los proyectos en ejecución sin carpeta (como «Subir») --------
function rdOpciones() {
  const pais = estado.pais === 'pe' ? 'PE' : 'CL';
  const lista = (rd.carpetas && Array.isArray(rd.carpetas[pais]) ? rd.carpetas[pais] : [])
    .filter((c) => c && texto(c.nombre)).map((c) => ({ carpeta: texto(c.nombre), req: texto(c.req) || null }));
  const conCarpeta = new Set(lista.map((c) => c.req).filter(Boolean));
  if (pais === 'CL') {
    (rc.tarjetas || []).forEach((t) => {
      if (t.etapa !== 'ejecucion' || t.antiguo || !t.req || conCarpeta.has(String(t.req))) return;
      lista.push({ carpeta: scLimpio(t.req + '. ' + (t.titulo || t.tag || 'Proyecto'), 120), req: String(t.req), titulo: t.titulo || '', nueva: true });
    });
  }
  return { pais, lista };
}
function rdProyectoDe(txt) {
  const n = norm(txt).trim();
  if (!n) return null;
  const { lista } = rdOpciones();
  return lista.find((o) => norm(o.carpeta) === n) || lista.find((o) => o.req && norm(o.req) === n) || null;
}
function rdAlMostrar() {
  if (!rd.recuperado) rd.recuperado = rdRecuperar().then(() => { rdPintarCab(); rdPintar(); });
  if (!rc.leyendo && (!rc.dir || !rc.leido || Date.now() - rc.leido > RC_RELEER_SEG * 1000)) rcCargar();   // al terminar llama a rdAlRecorrido
  else if (rc.dir) rdCargar();
  if (rd.cab) { rdPintarCab(); rdPintar(); }
}
function rdAlRecorrido() {
  if ($('#vistaRendir').hidden) return;
  if (rc.dir) rdCargar(); else if (rd.cab) rdPintar();
}
function rdCargar() {
  if (rd.leyendoCarpeta) return rd.leyendoCarpeta;
  const dir = rc.dir;
  if (!dir) return Promise.resolve();
  rd.leyendoCarpeta = (async () => {
    const pub = await rcJson(await rcSub(dir, 'publicado'), 'centro-costos-carpetas.json');
    rd.carpetas = pub && pub.datos && pub.datos.paises ? pub.datos.paises : null;
    const pubR = await rcJson(await rcSub(dir, 'publicado'), 'rendiciones.json');
    rd.envios = rdRegistro(pubR && pubR.datos && Array.isArray(pubR.datos.rendiciones) ? pubR.datos.rendiciones : [], await rdLeerEnvios(dir));
    rd.leidoCarpeta = Date.now();
  })().catch((e) => { console.error(e); }).then(() => {
    rd.leyendoCarpeta = null;
    if (rd.cab) rdPintar();
  });
  return rd.leyendoCarpeta;
}
// Las rendiciones enviadas: los documento-cc con «rendicion» del buzón y de lo procesado este mes y el anterior
async function rdLeerEnvios(dir) {
  const vistos = new Set();
  const grupos = new Map();
  const leer = async (carpeta, enCamino) => {
    if (!carpeta) return;
    try {
      for await (const [n, h] of carpeta.entries()) {
        if (h.kind !== 'file' || !SC_ARCHIVO_MSG.test(n)) continue;
        let m;
        try { m = JSON.parse(rcSinBom(await (await h.getFile()).text())); } catch (e) { continue; }
        if (!m || m.tipo !== 'documento-cc' || !m.rendicion || typeof m.rendicion !== 'object' || vistos.has(m.id)) continue;
        vistos.add(m.id);
        const r = m.rendicion;
        const k = texto(r.id) || texto(m.id);
        if (!grupos.has(k)) {
          grupos.set(k, {
            id: k, numero: texto(r.numero), deudor: texto(r.deudor), total: +r.total || 0, cantidad: +r.cantidad || 0,
            enviado: texto(m.origen && m.origen.enviado), usuario: texto(m.origen && m.origen.usuario), estados: [], carpetas: [], detalle: [], fechas: []
          });
        }
        const g = grupos.get(k);
        (Array.isArray(r.documentos) ? r.documentos : []).forEach((d) => { if (d && texto(d.fecha)) g.fechas.push(texto(d.fecha)); });
        const res = m.resultado || {};
        g.estados.push(enCamino ? 'camino' : res.estado === 'aplicado' ? 'aplicado' : 'rechazado');
        g.carpetas.push(texto(m.carpeta));
        if (!enCamino && res.estado !== 'aplicado' && Array.isArray(res.detalle) && res.detalle.length) g.detalle.push(texto(res.detalle[0]));
      }
    } catch (e) { /* sin permiso o a medio sincronizar */ }
  };
  const hoy = new Date();
  const mes = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
  // Lo procesado primero: si un mensaje aparece en los dos lados (OneDrive a medio mover), manda su resultado
  await leer(await rcSub(dir, 'procesado', mes(hoy)), false);
  await leer(await rcSub(dir, 'procesado', mes(new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1))), false);
  await leer(await rcSub(dir, 'buzon'), true);
  return [...grupos.values()].map((g) => Object.assign(g, {
    estado: g.estados.includes('rechazado') ? 'rechazado' : g.estados.includes('camino') ? 'camino' : 'aplicado'
  })).sort((a, b) => b.enviado.localeCompare(a.enviado));
}
// El registro de rendiciones (2026-11-18): lo publicado por el procesador (todas, con su correo) y encima lo que aún
// espera en el buzón o se rechazó (los mensajes de este mes y el anterior)
function rdRegistro(publicadas, mensajes) {
  const porId = new Map(mensajes.map((g) => [g.id, g]));
  const lista = publicadas.filter((r) => r && texto(r.id)).map((r) => {
    const docs = Array.isArray(r.documentos) ? r.documentos : [];
    const g = porId.get(texto(r.id));
    porId.delete(texto(r.id));
    return {
      id: texto(r.id), numero: texto(r.numero), deudor: texto(r.deudor), total: +r.total || 0, cantidad: +r.cantidad || 0,
      enviado: texto(r.enviado) || (g ? g.enviado : ''), usuario: texto(r.usuario), carpetas: docs.map((d) => texto(d.carpeta)),
      fechas: docs.map((d) => texto(d.fecha)).filter(Boolean), detalle: g ? g.detalle : [],
      correo: r.correo && texto(r.correo.fecha) ? r.correo : null,
      pdf: /^rendiciones\/[^/]+\.pdf$/.test(texto(r.pdf)) ? texto(r.pdf) : '',
      estado: r.correo && texto(r.correo.fecha) ? 'correo' : g && g.estado === 'camino' ? 'camino' : 'aplicado'
    };
  });
  return lista.concat([...porId.values()]).sort((a, b) => b.enviado.localeCompare(a.enviado)).slice(0, 60);
}
// Del documento más antiguo al más reciente (fechas dd-mm-aaaa), como en el correo
function rdRango(fechas) {
  const f = fechas.map((t) => { const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(t); return m ? m[3] + m[2] + m[1] : ''; }).filter(Boolean).sort();
  if (!f.length) return '';
  const v = (x) => x.slice(6) + '-' + x.slice(4, 6) + '-' + x.slice(0, 4);
  return f[0] === f[f.length - 1] ? v(f[0]) : v(f[0]) + ' al ' + v(f[f.length - 1]);
}

// ---- Lo que falta para enviar ---------------------------------------------------------------------------------
function rdFaltantes() {
  const salida = [];
  rd.docs.forEach((d) => {
    const f = [];
    if (!(d.campos.valor > 0)) f.push('valor');
    if (!texto(d.campos.numero)) f.push('numero');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(d.campos.fecha || '')) f.push('fecha');
    if (!rdProyectoDe(d.campos.proyecto)) f.push('proyecto');
    if (f.length) salida.push({ d, f });
  });
  return salida;
}
const RD_FALTA_TXT = { valor: 'el valor', numero: 'el N°', fecha: 'la fecha', proyecto: 'el proyecto' };

// ---- Enviar rendición: un documento-cc por proyecto, con los datos revisados en «rendicion»; el procesador la publica
//      en el registro (rendiciones.json) y envía el correo (correo_rendiciones.py) ------------------------------------
async function rdArchivoParaCC(d) {
  const m = d.nombre.match(/(\.[^.]+)$/);
  const ext = m ? m[1].toLowerCase() : '';
  if (RD_EXT_CC.test(ext)) return { datos: await d.archivo.arrayBuffer(), ext: ext === '.jpeg' ? '.jpg' : ext };
  // WebP, GIF…: el Centro de Costos no los abre; viaja la imagen que se ve en el PDF, en JPG
  const blob = await (await fetch(d.paginas[0])).blob();
  return { datos: await blob.arrayBuffer(), ext: '.jpg' };
}
async function rdEnviar() {
  if (mvNoSe()) return;      // solo lectura (js/resumen.js)
  if (rd.enviando || !rd.docs.length || !rc.dir || rd.cab.enviada) return;
  if (rd.docs.some((d) => d.estado === 'leyendo' || d.estado === 'pendiente')) return;
  const faltan = rdFaltantes();
  if (faltan.length) {
    faltan.forEach(({ d, f }) => { d.marcar = f; rdPintarFila(d); });
    avisar('Antes de enviar falta ' + rdFaltaTexto(faltan) + '.');
    return;
  }
  if (!rdConApellido(rd.cab.deudor)) {
    avisar('Antes de enviar falta el nombre y apellido de la persona: va en el correo.');
    $('#rdDeudor').focus();
    return;
  }
  const dudas = rd.docs.reduce((s, d) => s + d.dudas.length, 0);
  if (dudas && !rd.confirmarEnvio) {
    rd.confirmarEnvio = true;
    rdPintarResumen();
    return;
  }
  rd.enviando = true;
  rd.confirmarEnvio = false;
  rdPintarResumen();
  const grupos = new Map();
  rd.docs.forEach((d, i) => {
    const o = rdProyectoDe(d.campos.proyecto);
    if (!grupos.has(o.carpeta)) grupos.set(o.carpeta, { o, docs: [] });
    grupos.get(o.carpeta).docs.push({ d, n: i + 1 });
  });
  const cab = rd.cab;
  const total = rd.docs.reduce((s, d) => s + (d.campos.valor || 0), 0);
  const rid = scId().slice(0, 16);
  const pais = estado.pais === 'pe' ? 'PE' : 'CL';
  const enviados = [];
  // El PDF va siempre con la rendición: el correo lo lleva adjunto para la revisión. Sin PDF no se envía.
  let informe = null;
  try { informe = await rdGenerarPdf({ datos: true }); } catch (e) { console.error(e); }
  if (!informe || !informe.datos || !informe.datos.byteLength) {
    rd.enviando = false;
    rdPintar();
    avisar('No se pudo armar el PDF que va en el correo, así que la rendición no se envió. Revisa la conexión y vuelve a intentarlo.');
    return;
  }
  rd.enviando = true;
  rdPintarResumen();
  try {
    const buzon = await rc.dir.getDirectoryHandle('buzon', { create: true });
    const adjuntos = await buzon.getDirectoryHandle('adjuntos', { create: true });
    for (const [carpeta, g] of grupos) {
      const id = scId();
      const dir = await adjuntos.getDirectoryHandle(id, { create: true });
      const archivos = [], documentos = [], usados = new Set();
      for (const { d, n } of g.docs) {
        const { datos, ext } = await rdArchivoParaCC(d);
        let base = scLimpio(cab.numero + ' - ' + n + ' ' + (d.campos.tipo || 'Documento') + ' ' + (texto(d.campos.numero) || 'SN'), 140) || 'documento';
        while (usados.has((base + ext).toLowerCase())) base += '_';
        usados.add((base + ext).toLowerCase());
        const nombre = base + ext;
        const h = await dir.getFileHandle(nombre, { create: true });
        const w = await h.createWritable();
        await w.write(datos);
        await w.close();
        archivos.push({ nombre, bytes: datos.byteLength, sha256: await scSha(datos) });
        const doc = { archivo: nombre, n, tipo: d.campos.tipo || 'Otro', numero: texto(d.campos.numero), fecha: rdFechaCL(d.campos.fecha), detalle: texto(d.campos.detalle) || 'Otros', valor: Math.round(d.campos.valor) };
        if (texto(d.campos.proveedor)) doc.proveedor = texto(d.campos.proveedor);
        if (texto(d.campos.rut)) doc.rut = texto(d.campos.rut);
        documentos.push(doc);
      }
      const enviado = scAhora();
      const origen = { herramienta: 'portal', enviado };
      if (estado.usuario) origen.usuario = estado.usuario;
      const rendicion = { id: rid, numero: texto(cab.numero) || rid, tipo: cab.tipo, deudor: texto(cab.deudor), total, cantidad: rd.docs.length, documentos };
      if (!enviados.length) {
        // El PDF viaja con el primer mensaje, aparte de los documentos: no se copia a la carpeta del proyecto
        let nombrePdf = informe.nombre;
        while (usados.has(nombrePdf.toLowerCase())) nombrePdf = nombrePdf.replace(/\.pdf$/i, '_.pdf');
        const hp = await dir.getFileHandle(nombrePdf, { create: true });
        const wp = await hp.createWritable();
        await wp.write(informe.datos);
        await wp.close();
        rendicion.pdf = { nombre: nombrePdf, bytes: informe.datos.byteLength, sha256: await scSha(informe.datos) };
      }
      if (texto(cab.periodo)) rendicion.periodo = texto(cab.periodo);
      if (texto(cab.unidad)) rendicion.unidad = texto(cab.unidad);
      const msg = {
        esquema: 'quempin.intercambio/1', id, tipo: 'documento-cc', destino: 'centro-costos', origen, pais, carpeta, archivos,
        nota: 'Rendición ' + rendicion.numero + (rendicion.deudor ? ' de ' + rendicion.deudor : ''), rendicion
      };
      if (g.o.nueva) msg.nueva = true;
      if (g.o.req) msg.proyecto = g.o.titulo ? { req: g.o.req, titulo: g.o.titulo } : { req: g.o.req };
      const nombreMsg = enviado.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_documento-cc_' + id + '.json';
      const h = await buzon.getFileHandle(nombreMsg, { create: true });
      const w = await h.createWritable();
      await w.write(JSON.stringify(msg, null, 1));
      await w.close();
      enviados.push(carpeta);
      g.o.nueva = false;
    }
    cab.enviada = { fecha: scAhora(), id: rid, carpetas: enviados };
    rd.envios.unshift({ id: rid, numero: texto(cab.numero), deudor: texto(cab.deudor), total, cantidad: rd.docs.length, enviado: cab.enviada.fecha, usuario: estado.usuario || '', estados: [], carpetas: enviados, detalle: [], estado: 'camino',
      fechas: rd.docs.map((d) => /^\d{4}-\d{2}-\d{2}$/.test(d.campos.fecha || '') ? d.campos.fecha.split('-').reverse().join('-') : '').filter(Boolean) });
    avisar('Rendición enviada: queda en el registro y el correo sale en la próxima vuelta del procesador (unos minutos).');
  } catch (err) {
    console.error(err);
    avisar('No se pudo enviar' + (enviados.length ? ' todo (ya salió lo de ' + enviados.join(', ') + ')' : '') + ': ' +
      (err && err.name === 'NotAllowedError' ? 'falta el permiso para escribir en la carpeta del equipo.' : 'revisa que OneDrive esté funcionando y vuelve a intentarlo.'));
  } finally {
    rd.enviando = false;
    rdGuardar();
    rdPintar();
  }
}
function rdFaltaTexto(faltan) {
  const cuenta = {};
  faltan.forEach(({ f }) => f.forEach((c) => { cuenta[c] = (cuenta[c] || 0) + 1; }));
  return Object.keys(cuenta).map((c) => RD_FALTA_TXT[c] + ' en ' + pl(cuenta[c], 'documento', 'documentos')).join(', ');
}

// ---- El PDF: resumen con la cara de los informes QUEMPIN y una página por documento -----------------------------
async function rdLogo() {
  if (rd.logo !== undefined) return rd.logo;
  try {
    const res = await fetch('../marca/logo.png');
    if (!res.ok) throw new Error(String(res.status));
    const blob = await res.blob();
    const data = await new Promise((listo) => { const fr = new FileReader(); fr.onload = () => listo(fr.result); fr.readAsDataURL(blob); });
    const img = await rdCargarImagen(data);
    rd.logo = { data, w: img.naturalWidth, h: img.naturalHeight };
  } catch (e) { rd.logo = null; }
  return rd.logo;
}
// op.datos: no lo descarga; devuelve {nombre, datos} para enviarlo con la rendición (va adjunto en el correo)
async function rdGenerarPdf(op = {}) {
  if (rd.haciendoPdf || !rd.docs.length) return null;
  rd.haciendoPdf = true;
  rdPintarResumen();
  try {
    const { jsPDF } = await rdLib('jspdf');
    const logo = await rdLogo();
    const pdf = new jsPDF({ unit: 'mm', format: 'letter', compress: true });
    const W = 215.9, H = 279.4, M = 16;
    const NAR = [255, 81, 0], NEG = [0, 0, 0], GRIS = [84, 86, 90], GRIS_C = [152, 152, 154], LINEA = [214, 214, 214];
    const tinta = (c) => pdf.setTextColor(c[0], c[1], c[2]);
    const letra = (estilo, tam, c) => { pdf.setFont('helvetica', estilo); pdf.setFontSize(tam); tinta(c || NEG); };
    const corta = (s, ancho) => {
      s = String(s === null || s === undefined ? '' : s);
      if (pdf.getTextWidth(s) <= ancho) return s;
      while (s.length > 1 && pdf.getTextWidth(s + '...') > ancho) s = s.slice(0, -1);
      return s + '...';
    };
    const cab = rd.cab;
    const docs = rd.docs;
    const total = docs.reduce((s, d) => s + (d.campos.valor || 0), 0);
    const titulo = RD_TIPOS[cab.tipo] || RD_TIPOS.recuperacion;
    const emitido = rdFechaCL(rdHoy());
    const cabecera = (tit, sub, chico) => {
      const hL = chico ? 9 : 13;
      let x = M;
      if (logo) { const w = hL * logo.w / logo.h; pdf.addImage(logo.data, 'PNG', M, 12, w, hL); x = M + w + 5; }
      letra('bold', chico ? 12 : 17);
      pdf.text(tit, x, 12 + hL / 2 - (chico ? 0.6 : 1.2));
      letra('normal', chico ? 8 : 9, GRIS);
      pdf.text(corta(sub, W - M - x - (chico ? 45 : 0)), x, 12 + hL / 2 + (chico ? 3.6 : 4.6));
      const y = 12 + hL + 3;
      pdf.setDrawColor(NAR[0], NAR[1], NAR[2]);
      pdf.setLineWidth(chico ? 0.6 : 0.9);
      pdf.line(M, y, W - M, y);
      return y + (chico ? 5 : 7);
    };
    const subtitulo = [cab.periodo, cab.numero ? 'N° ' + cab.numero : '', 'emitida el ' + emitido].filter(Boolean).join(' · ');

    // Página 1: ficha, cifras, tabla, totales, distribución y firmas
    let y = cabecera(titulo, subtitulo, false);
    const ficha = [['Nombre del deudor', cab.deudor || '—'], ['Unidad presupuestaria', cab.unidad || '—'], ['N° documento', cab.numero || '—'], ['Período', cab.periodo || '—']];
    const vale = cab.tipo === 'vale';
    if (vale) ficha.push(['Monto del vale', cab.valeMonto ? rdPesos(cab.valeMonto) : '—'], ['Fecha del vale', rdFechaCL(cab.valeFecha) || '—']);
    const anchoCol = (W - 2 * M) / 2;
    ficha.forEach(([et, v], i) => {
      const x = M + (i % 2) * anchoCol;
      const yy = y + Math.floor(i / 2) * 11;
      letra('bold', 7, GRIS);
      pdf.text(et.toUpperCase(), x, yy);
      letra('normal', 10.5);
      pdf.text(corta(v, anchoCol - 6), x, yy + 5);
    });
    y += Math.ceil(ficha.length / 2) * 11 + 3;
    const saldo = vale && cab.valeMonto ? cab.valeMonto - total : null;
    const kpis = [['Total rendido', rdPesos(total)], ['Documentos', String(docs.length)],
      saldo === null ? ['Saldo a favor del deudor', rdPesos(total)] : saldo >= 0 ? ['Saldo a reintegrar', rdPesos(saldo)] : ['Saldo a favor del deudor', rdPesos(-saldo)]];
    const kw = (W - 2 * M - 8) / 3;
    kpis.forEach(([et, v], i) => {
      const x = M + i * (kw + 4);
      pdf.setDrawColor(GRIS_C[0], GRIS_C[1], GRIS_C[2]);
      pdf.setLineWidth(0.3);
      pdf.roundedRect(x, y, kw, 17, 2, 2);
      letra('bold', 15, NAR);
      pdf.text(v, x + 4, y + 8.5);
      letra('normal', 8, GRIS);
      pdf.text(et, x + 4, y + 13.5);
    });
    y += 25;
    const cols = [['#', 7, 'c'], ['Tipo', 22], ['N°', 24], ['Fecha', 18], ['Proveedor', 36], ['Detalle', 24], ['Proyecto', 31.9], ['Valor', 21, 'r']];
    const encabezado = () => {
      pdf.setFillColor(GRIS[0], GRIS[1], GRIS[2]);
      pdf.rect(M, y, W - 2 * M, 7, 'F');
      letra('bold', 7, [255, 255, 255]);
      let x = M;
      cols.forEach(([t, w, al]) => {
        const tx = al === 'r' ? x + w - 1.5 : al === 'c' ? x + w / 2 : x + 1.5;
        pdf.text(t.toUpperCase(), tx, y + 4.7, { align: al === 'r' ? 'right' : al === 'c' ? 'center' : 'left' });
        x += w;
      });
      y += 7;
    };
    const piePagina = H - 18;
    encabezado();
    docs.forEach((d, i) => {
      if (y + 6.5 > piePagina - 4) {
        pdf.addPage();
        y = cabecera(titulo, subtitulo + ' · continuación', true);
        encabezado();
      }
      const c = d.campos;
      const celdas = [String(i + 1), c.tipo, c.numero, rdFechaCL(c.fecha), c.proveedor, c.detalle, c.proyecto, c.valor ? rdPesos(c.valor) : '—'];
      letra('normal', 8);
      let x = M;
      cols.forEach(([, w, al], k) => {
        const v = corta(celdas[k] || '', w - 3);
        const tx = al === 'r' ? x + w - 1.5 : al === 'c' ? x + w / 2 : x + 1.5;
        pdf.text(v, tx, y + 4.4, { align: al === 'r' ? 'right' : al === 'c' ? 'center' : 'left' });
        x += w;
      });
      pdf.setDrawColor(LINEA[0], LINEA[1], LINEA[2]);
      pdf.setLineWidth(0.2);
      pdf.line(M, y + 6.5, W - M, y + 6.5);
      y += 6.5;
    });
    // Totales, a la derecha
    const filasTot = [['Total $', rdPesos(total), true]];
    if (saldo !== null) {
      filasTot.push(['Monto del vale $', rdPesos(cab.valeMonto), false]);
      filasTot.push(saldo >= 0 ? ['Saldo a reintegrar $', rdPesos(saldo), false] : ['Saldo a favor del deudor $', rdPesos(-saldo), false]);
    } else filasTot.push(['Saldo a favor del deudor $', rdPesos(total), false]);
    // Distribución por proyecto (pedido: a veces se juntan gastos de varios proyectos)
    const dist = new Map();
    docs.forEach((d) => {
      const k = texto(d.campos.proyecto) || 'Sin proyecto';
      const v = dist.get(k) || { n: 0, monto: 0 };
      v.n++;
      v.monto += d.campos.valor || 0;
      dist.set(k, v);
    });
    const alto = 4 + filasTot.length * 6 + 10 + dist.size * 6 + 44;
    if (y + alto > piePagina) { pdf.addPage(); y = cabecera(titulo, subtitulo + ' · continuación', true); }
    y += 4;
    filasTot.forEach(([et, v, fuerte]) => {
      letra(fuerte ? 'bold' : 'normal', fuerte ? 10 : 9, fuerte ? NEG : GRIS);
      pdf.text(et, W - M - 40, y + 4, { align: 'right' });
      letra('bold', fuerte ? 10 : 9);
      pdf.text(v, W - M - 1.5, y + 4, { align: 'right' });
      if (fuerte) { pdf.setDrawColor(NAR[0], NAR[1], NAR[2]); pdf.setLineWidth(0.5); pdf.line(W - M - 75, y + 6, W - M, y + 6); }
      y += 6;
    });
    y += 6;
    letra('bold', 9);
    pdf.text('Distribución por proyecto', M, y);
    y += 2;
    dist.forEach((v, k) => {
      letra('normal', 8.5);
      pdf.text(corta(k, 110), M + 1.5, y + 4.2);
      letra('normal', 8.5, GRIS);
      pdf.text(pl(v.n, 'documento', 'documentos'), M + 140, y + 4.2, { align: 'right' });
      letra('bold', 8.5);
      pdf.text(rdPesos(v.monto), W - M - 1.5, y + 4.2, { align: 'right' });
      pdf.setDrawColor(LINEA[0], LINEA[1], LINEA[2]);
      pdf.setLineWidth(0.2);
      pdf.line(M, y + 6, W - M, y + 6);
      y += 6;
    });
    // Firmas
    const yf = Math.max(y + 26, piePagina - 16);
    pdf.setDrawColor(NEG[0], NEG[1], NEG[2]);
    pdf.setLineWidth(0.3);
    [[M + 6, 'Firma Deudor'], [W - M - 76, 'Firma Director Proyecto']].forEach(([x, et]) => {
      pdf.line(x, yf, x + 70, yf);
      letra('bold', 8.5);
      pdf.text(et, x + 35, yf + 4.5, { align: 'center' });
    });

    // Una página por documento (y por cada página de un PDF)
    for (let k = 0; k < docs.length; k++) {
      const d = docs[k];
      const c = d.campos;
      const paginas = d.paginas.length ? d.paginas : [null];
      for (let j = 0; j < paginas.length; j++) {
        pdf.addPage();
        const tit = 'Documento ' + (k + 1) + ' de ' + docs.length + (paginas.length > 1 ? ' · página ' + (j + 1) + ' de ' + paginas.length : '');
        const sub = [(c.tipo || 'Documento') + (c.numero ? ' N° ' + c.numero : ''), rdFechaCL(c.fecha), c.detalle, c.proyecto].filter(Boolean).join(' · ');
        let yy = cabecera(tit, sub, true);
        letra('bold', 12);
        pdf.text(c.valor ? rdPesos(c.valor) : '', W - M, 12 + 9 / 2 - 0.6, { align: 'right' });
        const prov = [c.proveedor, c.rut ? 'RUT ' + c.rut : ''].filter(Boolean).join(' · ');
        if (prov) { letra('normal', 8.5, GRIS); pdf.text(corta(prov, W - 2 * M), M, yy); yy += 3; }
        yy += 2;
        const caja = { x: M, y: yy, w: W - 2 * M, h: piePagina - 4 - yy };
        if (paginas[j]) {
          const img = await rdCargarImagen(paginas[j]);
          const lienzo = rdLienzo(img, { max: 1700, rot: d.rot });
          const k2 = Math.min(caja.w / lienzo.width, caja.h / lienzo.height);
          const w = lienzo.width * k2, h = lienzo.height * k2;
          const x = caja.x + (caja.w - w) / 2;
          pdf.addImage(lienzo.toDataURL('image/jpeg', 0.8), 'JPEG', x, caja.y, w, h);
          pdf.setDrawColor(LINEA[0], LINEA[1], LINEA[2]);
          pdf.setLineWidth(0.2);
          pdf.rect(x, caja.y, w, h);
        } else {
          letra('normal', 10, GRIS);
          pdf.text('No se pudo mostrar «' + corta(d.nombre, 120) + '»: se adjunta aparte.', M, caja.y + 10);
        }
      }
    }
    // Pie de cada página
    const n = pdf.getNumberOfPages();
    for (let i = 1; i <= n; i++) {
      pdf.setPage(i);
      pdf.setDrawColor(LINEA[0], LINEA[1], LINEA[2]);
      pdf.setLineWidth(0.2);
      pdf.line(M, H - 13, W - M, H - 13);
      letra('normal', 7.5, GRIS);
      pdf.text('QUEMPIN SpA · ' + titulo + (cab.numero ? ' ' + cab.numero : ''), M, H - 9);
      pdf.text('Página ' + i + ' de ' + n, W - M, H - 9, { align: 'right' });
    }
    const nombre = scLimpio(titulo + ' ' + (cab.deudor || '') + ' - ' + (cab.periodo || emitido), 120) + '.pdf';
    if (op.datos) return { nombre, datos: pdf.output('arraybuffer') };
    pdf.save(nombre);
    cab.pdf = true;
    rdGuardar();
  } catch (e) {
    console.error(e);
    if (op.datos) throw e;
    avisar('No se pudo armar el PDF' + (/conexi/i.test(String(e && e.message)) ? ': hace falta internet la primera vez.' : '. Vuelve a intentarlo.'));
  } finally {
    rd.haciendoPdf = false;
    rdPintarResumen();
  }
}

// ---- Pintar -----------------------------------------------------------------------------------------------
function rdPintarCab() {
  const c = rd.cab;
  if (!c) return;
  document.querySelectorAll('.rd-tipo button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.tipo === c.tipo)));
  [['#rdDeudor', c.deudor], ['#rdPeriodo', c.periodo], ['#rdNumero', c.numero], ['#rdUnidad', c.unidad], ['#rdValeFecha', c.valeFecha],
    ['#rdValeMonto', c.valeMonto ? rdMiles(c.valeMonto) : '']].forEach(([s, v]) => {
    const e = $(s);
    if (document.activeElement !== e) e.value = v || '';
  });
  $('#rdValeMontoC').hidden = c.tipo !== 'vale';
  $('#rdValeFechaC').hidden = c.tipo !== 'vale';
  const ia = rdLectorIA();
  const b = $('#rdLector');
  b.dataset.ia = ia ? 'si' : 'no';
  b.textContent = ia ? 'Lectura con IA' : 'Lectura en este navegador';
  b.title = 'Cómo se leen los documentos';
}
function rdPintar() {
  if (!rd.cab) return;
  const dl = $('#rdProyectos');
  dl.textContent = '';
  rdOpciones().lista.forEach((o) => { const op = crear('option'); op.value = o.carpeta; if (o.nueva) op.label = o.carpeta + ' (carpeta nueva)'; dl.append(op); });
  $('#rdTodosC').hidden = rd.docs.length < 2;
  $('#rdTabla').hidden = !rd.docs.length;
  const tb = $('#rdFilas');
  const activo = document.activeElement;
  if (activo && tb.contains(activo)) {
    // Con el cursor en una casilla, solo se rehacen las filas que no la tienen (no se pierde lo que se escribe)
    rd.docs.forEach(rdPintarFila);
    [...tb.children].forEach((tr) => { if (!rd.docs.some((d) => d.id === tr.dataset.id)) tr.remove(); });
  } else {
    tb.textContent = '';
    rd.docs.forEach((d, i) => tb.append(rdFila(d, i)));
  }
  rdPintarResumen();
  rdPintarEnvios();
}
function rdPintarFila(d) {
  const tb = $('#rdFilas');
  const i = rd.docs.indexOf(d);
  if (i < 0) return;
  const viejo = tb.querySelector('tr[data-id="' + d.id + '"]');
  if (viejo && viejo.contains(document.activeElement)) {
    // Se repinta al salir de la fila; mientras tanto solo cambia el estado de la lectura
    d.repintar = true;
    rdPintarLectura(d);
    return;
  }
  const nuevo = rdFila(d, i);
  if (viejo) viejo.replaceWith(nuevo); else tb.append(nuevo);
}
function rdTextoLectura(d) {
  if (d.estado === 'pendiente') return ['leyendo', 'En espera…'];
  if (d.estado === 'leyendo') return ['leyendo', 'Leyendo…' + (d.progreso ? ' ' + Math.round(d.progreso * 100) + '%' : '')];
  if (d.estado === 'error') return ['bad', d.error || 'No se pudo leer'];
  if (d.dudas.length) return ['warn', pl(d.dudas.length, 'dato por revisar', 'datos por revisar')];
  return ['ok', d.fuente === 'pdf' ? 'Leído del PDF' : d.fuente === 'ia' ? 'Leído con IA' : 'Leído'];
}
// «Están bien» solo con datos en naranjo que ya tienen algo escrito: lo vacío hay que llenarlo
const rdPorConfirmar = (d) => d.estado === 'listo' && d.dudas.some((c) => c === 'valor' ? !!d.campos.valor : !!texto(d.campos[c]));
function rdPintarLectura(d) {
  const e = document.querySelector('#rdFilas tr[data-id="' + d.id + '"] .rd-lect');
  if (!e) return;
  const [nivel, txt] = rdTextoLectura(d);
  e.dataset.nivel = nivel;
  e.textContent = txt;
  const b = e.parentElement.querySelector('.rd-bien');
  if (b) b.hidden = !rdPorConfirmar(d);
}
// Las casillas de un documento (en la fila y en el diálogo): cada cambio se guarda y quita su marca naranja
function rdCasilla(d, campo) {
  const c = d.campos;
  let e;
  if (campo === 'tipo') {
    e = crear('select');
    const ops = RD_DOCS.includes(c.tipo) || !c.tipo ? RD_DOCS : RD_DOCS.concat(c.tipo);
    if (!c.tipo) { const o = crear('option', null, '—'); o.value = ''; e.append(o); }
    ops.forEach((t) => { const o = crear('option', null, t); o.value = t; e.append(o); });
    e.value = c.tipo || '';
  } else {
    e = crear('input');
    e.type = campo === 'fecha' ? 'date' : 'text';
    e.autocomplete = 'off';
    if (campo === 'valor') {
      e.inputMode = 'numeric';
      e.dataset.num = 'entero';
      e.maxLength = 14;
      e.value = c.valor ? String(Math.round(c.valor)) : '';   // sin formato: numeros.js le pone los puntos al prepararla
      e.placeholder = '$';
    } else e.value = c[campo] || '';
    if (campo === 'detalle') { e.setAttribute('list', 'rdDetalles'); e.maxLength = 40; }
    if (campo === 'proyecto') { e.setAttribute('list', 'rdProyectos'); e.placeholder = 'Elige el proyecto'; }
    if (campo === 'rut') { e.className = 'rd-rut'; e.placeholder = 'RUT'; e.maxLength = 14; }
    if (campo === 'numero') { e.maxLength = 30; e.placeholder = 'N°'; }
    if (campo === 'proveedor') e.maxLength = 70;
    if (campo === 'fecha') { e.min = '2000-01-01'; e.max = '2099-12-31'; }
  }
  e.dataset.campo = campo;
  const et = { tipo: 'Tipo de documento', numero: 'N° del documento', fecha: 'Fecha', proveedor: 'Proveedor', rut: 'RUT del proveedor', detalle: 'Detalle', proyecto: 'Proyecto', valor: 'Valor' }[campo];
  e.setAttribute('aria-label', et + ' del documento ' + (rd.docs.indexOf(d) + 1));
  if (d.dudas.includes(campo)) e.classList.add('duda');
  if (campo === 'proyecto' && c.proyecto && rd.carpetas && !rdProyectoDe(c.proyecto)) e.classList.add('mal');
  if (d.marcar && d.marcar.includes(campo)) e.classList.add('mal');
  const alCambiar = () => {
    let v = e.value;
    if (campo === 'valor') v = rdMonto(v);
    if (campo === 'proyecto') {
      const o = rdProyectoDe(v);
      if (o) { v = o.carpeta; e.value = o.carpeta; rd.cab.ultimoProyecto = o.carpeta; }
      e.classList.toggle('mal', !!texto(v) && !!rd.carpetas && !o);
    }
    d.campos[campo] = v;
    if (!d.editado.includes(campo)) d.editado.push(campo);
    d.dudas = d.dudas.filter((x) => x !== campo);
    if (d.marcar) d.marcar = d.marcar.filter((x) => x !== campo);
    e.classList.remove('duda');
    if (campo !== 'proyecto') e.classList.remove('mal');
    if (campo === 'fecha') rdPeriodoAuto();
    rd.confirmarEnvio = false;
    rdPintarLectura(d);
    rdPintarResumen();
    rdGuardar();
  };
  e.addEventListener(campo === 'tipo' || campo === 'fecha' || campo === 'proyecto' ? 'change' : 'input', alCambiar);
  if (campo === 'proyecto') e.addEventListener('blur', alCambiar);
  return e;
}
function rdFila(d, i) {
  const tr = crear('tr');
  tr.dataset.id = d.id;
  const td = (clase, et, ...hijos) => { const c = crear('td', clase); if (et) c.dataset.et = et; hijos.forEach((h) => c.append(h)); tr.append(c); return c; };
  td('rd-n', null, String(i + 1));
  const doc = crear('div', 'rd-doc');
  const mini = crear('button', 'rd-mini');
  mini.type = 'button';
  mini.title = 'Ver ' + d.nombre + ' en grande';
  mini.setAttribute('aria-label', 'Ver el documento ' + (i + 1) + ' en grande');
  if (d.mini) { const img = crear('img'); img.src = d.mini; img.alt = ''; mini.append(img); } else mini.append(icono('documento', 22));
  mini.addEventListener('click', () => rdAbrirDoc(d));
  const [nivel, txt] = rdTextoLectura(d);
  const lect = crear('span', 'rd-lect', txt);
  lect.dataset.nivel = nivel;
  const bien = crear('button', 'rd-bien', 'Están bien');
  bien.type = 'button';
  bien.title = 'Ya comparé los datos en naranjo con la foto: están bien';
  bien.setAttribute('aria-label', 'Los datos en naranjo del documento ' + (i + 1) + ' están bien');
  bien.hidden = !rdPorConfirmar(d);
  bien.addEventListener('click', () => rdConfirmar(d));
  doc.append(mini, lect, bien);
  td('rd-doc-td', null, doc);
  td(null, 'Tipo', rdCasilla(d, 'tipo'));
  td(null, 'N°', rdCasilla(d, 'numero'));
  td(null, 'Fecha', rdCasilla(d, 'fecha'));
  td('rd-prov', 'Proveedor', rdCasilla(d, 'proveedor'), rdCasilla(d, 'rut'));
  td(null, 'Detalle', rdCasilla(d, 'detalle'));
  td('rd-proy', 'Proyecto', rdCasilla(d, 'proyecto'));
  td('num', 'Valor', rdCasilla(d, 'valor'));
  const x = crear('button', 'rd-quitar');
  x.type = 'button';
  x.title = 'Quitar ' + d.nombre;
  x.setAttribute('aria-label', 'Quitar el documento ' + (i + 1));
  x.append(icono('cerrar', 16));
  x.addEventListener('click', () => rdQuitar(d));
  const otra = crear('button', 'rd-quitar rd-otra');
  otra.type = 'button';
  otra.title = 'Otra boleta de esta misma foto';
  otra.setAttribute('aria-label', 'Agregar otra boleta de la foto del documento ' + (i + 1));
  otra.append(icono('mas', 16));
  otra.addEventListener('click', () => rdOtra(d));
  td('rd-acc', null, x, otra);
  tr.addEventListener('focusout', () => {
    setTimeout(() => { if (d.repintar && !tr.contains(document.activeElement)) { d.repintar = false; rdPintarFila(d); } }, 0);
  });
  return tr;
}
function rdPintarResumen() {
  if (!rd.cab) return;
  const docs = rd.docs;
  const total = docs.reduce((s, d) => s + (d.campos.valor || 0), 0);
  $('#rdTotal').textContent = rdPesos(total);
  const saldo = $('#rdSaldo');
  saldo.textContent = '';
  const vale = rd.cab.tipo === 'vale' && rd.cab.valeMonto;
  saldo.hidden = !vale;
  if (vale) {
    const s = rd.cab.valeMonto - total;
    const fila = (et, v) => saldo.append(crear('dt', null, et), crear('dd', null, v));
    fila('Monto del vale', rdPesos(rd.cab.valeMonto));
    fila(s >= 0 ? 'Saldo a reintegrar' : 'Saldo a favor del deudor', rdPesos(Math.abs(s)));
  }
  const leyendo = docs.filter((d) => d.estado === 'leyendo' || d.estado === 'pendiente').length;
  const dudas = docs.reduce((s, d) => s + d.dudas.length, 0);
  const est = $('#rdEstado');
  est.textContent = '';
  if (!docs.length) est.textContent = 'Sube la primera boleta o factura.';
  else {
    est.append(pl(docs.length, 'documento', 'documentos') + ' · ');
    if (leyendo) est.append('leyendo ' + pl(leyendo, 'documento', 'documentos') + '…');
    else if (dudas) { est.append(crear('strong', null, pl(dudas, 'dato', 'datos') + ' en naranjo')); est.append(': compáralos con la foto (toca la miniatura).'); }
    else est.append('todo revisado.');
  }
  const bPdf = $('#rdPdf');
  bPdf.disabled = !docs.length || !!leyendo || rd.haciendoPdf;
  bPdf.classList.toggle('ocupado', rd.haciendoPdf);
  bPdf.textContent = rd.haciendoPdf ? 'Armando el PDF…' : 'Descargar PDF';
  const bEnv = $('#rdEnviar');
  const nota = $('#rdNotaEnviar');
  nota.classList.remove('mal');
  bEnv.disabled = !docs.length || !!leyendo || rd.enviando || !!rd.cab.enviada || !rc.dir;
  bEnv.classList.toggle('ocupado', rd.enviando);
  bEnv.textContent = rd.enviando ? 'Enviando…' : rd.cab.enviada ? 'Rendición enviada' : rd.confirmarEnvio ? 'Enviar igual, con ' + pl(dudas, 'dato', 'datos') + ' en naranjo' : 'Enviar rendición';
  if (rd.cab.enviada) {
    const f = new Date(rd.cab.enviada.fecha);
    nota.textContent = 'Enviada el ' + (isNaN(f) ? '' : f.toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })) + ' a ' + rd.cab.enviada.carpetas.join(', ') + '. Queda en el registro; el correo sale cuando el procesador la recibe (unos minutos).';
  } else if (!rc.dir) {
    nota.textContent = rc.leyendo ? 'Leyendo la carpeta del equipo…' : rc.sinDatos === 'navegador'
      ? 'Para enviar la rendición, abre el portal en Chrome o Edge de escritorio. El PDF sí se descarga aquí.'
      : 'Para enviar la rendición, conecta la biblioteca del equipo (Configuración y conexiones). El PDF sí se descarga aquí.';
  } else {
    const faltan = docs.length && !leyendo ? rdFaltantes() : [];
    if (faltan.length) { nota.textContent = 'Para enviar falta ' + rdFaltaTexto(faltan) + '.'; nota.classList.add('mal'); }
    else if (docs.length && !rdConApellido(rd.cab.deudor)) { nota.textContent = 'Para enviar falta el nombre y apellido de la persona.'; nota.classList.add('mal'); }
    else nota.textContent = docs.length ? 'Queda en el registro de rendiciones, cada documento llega a la carpeta de su proyecto y sale un correo automático con el total y el PDF adjunto.' : '';
  }
}
function rdPintarEnvios() {
  const ul = $('#rdEnvios');
  ul.textContent = '';
  if (!rc.dir) { ul.append(crear('li', 'sc-env-det', 'Se ven con la carpeta del equipo conectada.')); return; }
  if (!rd.envios.length) { ul.append(crear('li', 'sc-env-det', rd.leyendoCarpeta ? 'Leyendo…' : 'Todavía no hay rendiciones en el registro.')); return; }
  const NIVEL = { camino: ['warn', 'En camino'], aplicado: ['warn', 'Correo pendiente'], correo: ['ok', 'Correo enviado'], rechazado: ['bad', 'No se pudo'] };
  rd.envios.forEach((e) => {
    const li = crear('li');
    const cab = crear('div', 'sc-env-cab');
    const [nivel, txt] = NIVEL[e.estado];
    const pill = crear('span', 'sc-pill', txt);
    pill.dataset.nivel = nivel;
    cab.append(crear('span', 'sc-env-nom', [e.numero, e.deudor].filter(Boolean).join(' · ') || 'Rendición'), pill);
    const f = e.enviado ? new Date(e.enviado) : null;
    const cuando = f && !isNaN(f) ? f.toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
    const rango = rdRango(e.fechas || []);
    li.append(cab, crear('span', 'sc-env-det', [rdPesos(e.total), pl(e.cantidad, 'documento', 'documentos'), rango && 'gastos del ' + rango].filter(Boolean).join(' · ')));
    li.append(crear('span', 'sc-env-det', [...new Set(e.carpetas)].join(' · ')));
    const fc = e.correo ? new Date(e.correo.fecha) : null;
    li.append(crear('span', 'sc-env-det', ['Enviada ' + cuando + (e.usuario ? ' por ' + e.usuario : ''),
      fc && !isNaN(fc) ? 'correo ' + fc.toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : ''].filter(Boolean).join(' · ')));
    if (e.pdf) {
      const b = crear('button', 'cx-enlace rd-ver-pdf', 'Ver PDF');
      b.type = 'button';
      b.addEventListener('click', () => rdAbrirPdfRegistro(e.pdf, b));
      li.append(b);
    }
    if (e.estado === 'rechazado' && e.detalle.length) li.append(crear('span', 'sc-env-det mal', e.detalle[0]));
    ul.append(li);
  });
}

// El PDF de una rendición del registro (publicado/rendiciones/<N°>.pdf), el mismo que fue adjunto en el correo
async function rdAbrirPdfRegistro(ruta, boton) {
  const ventana = window.open('', '_blank');
  try {
    let d = await rcSub(rc.dir, 'publicado');
    const partes = ruta.split('/');
    for (const p of partes.slice(0, -1)) d = await d.getDirectoryHandle(p);
    const archivo = await (await d.getFileHandle(partes[partes.length - 1])).getFile();
    const url = URL.createObjectURL(archivo);
    if (ventana) ventana.location.href = url; else window.open(url, '_blank');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    if (ventana) ventana.close();
    boton.disabled = true;
    avisar('Ese PDF todavía no llega a este computador (OneDrive). Prueba en unos minutos.');
  }
}

// ---- Un documento en grande -------------------------------------------------------------------------------------
async function rdPintarFotos(d) {
  const caja = $('#rdDlgFotos');
  caja.textContent = '';
  if (!d.paginas.length) { caja.append(crear('p', 'rd-nota', d.estado === 'error' ? d.error : 'Preparando la imagen…')); return; }
  for (const p of d.paginas) {
    const img = crear('img');
    img.alt = 'Página de ' + d.nombre;
    try { img.src = rdLienzo(await rdCargarImagen(p), { max: 1600, rot: d.rot }).toDataURL('image/jpeg', 0.85); } catch (e) { img.src = p; }
    caja.append(img);
  }
}
function rdAbrirDoc(d) {
  rd.abierto = d;
  $('#dlgRdDocTit').textContent = 'Documento ' + (rd.docs.indexOf(d) + 1) + ' · ' + d.nombre;
  const campos = $('#rdDlgCampos');
  campos.textContent = '';
  [['tipo', 'Tipo'], ['numero', 'N°'], ['fecha', 'Fecha'], ['valor', 'Valor'], ['proveedor', 'Proveedor'], ['rut', 'RUT del proveedor'], ['detalle', 'Detalle'], ['proyecto', 'Proyecto']].forEach(([c, et]) => {
    const l = crear('label', null, et);
    const e = rdCasilla(d, c);
    e.classList.remove('rd-rut');
    l.append(e);
    campos.append(l);
  });
  $('#rdReleer').disabled = d.estado === 'leyendo' || d.estado === 'pendiente';
  rdPintarFotos(d);
  $('#dlgRdDoc').showModal();
}
function rdGirar(g) {
  const d = rd.abierto;
  if (!d) return;
  d.rot = ((d.rot || 0) + g + 360) % 360;
  rdPintarFotos(d);
  if (d.paginas.length) rdCargarImagen(d.paginas[0]).then((img) => { d.mini = rdLienzo(img, { max: 160, rot: d.rot }).toDataURL('image/jpeg', 0.7); rdGuardar(); });
}
function rdReleer() {
  const d = rd.abierto;
  if (!d || d.estado === 'leyendo' || d.estado === 'pendiente') return;
  d.editado = d.editado.filter((c) => c === 'proyecto');
  d.estado = 'pendiente';
  $('#dlgRdDoc').close();
  rdEncolar(d);
  rdPintarFila(d);
  rdPintarResumen();
}
// ---- El lector con IA (opcional) ---------------------------------------------------------------------------------
function rdAbrirLector() {
  const l = leer(RD_CLAVE_LECTOR, null) || {};
  $('#rdLectorUrl').value = texto(l.url);
  $('#rdLectorClave').value = texto(l.clave);
  $('#rdLectorNota').textContent = '';
  $('#dlgRdLector').showModal();
}
async function rdGuardarLector(ev) {
  ev.preventDefault();
  const url = texto($('#rdLectorUrl').value).replace(/\/+$/, '');
  const clave = texto($('#rdLectorClave').value);
  const nota = $('#rdLectorNota');
  if (!/^https:\/\/[^\s/]+/.test(url) || !clave) { nota.textContent = 'Escribe la dirección (https://…) y la clave.'; return; }
  nota.textContent = 'Probando el lector…';
  try {
    const res = await fetch(url, { headers: { 'x-clave': clave } });
    if (res.status === 401 || res.status === 403) throw new Error('La clave no es la del lector.');
    if (!res.ok) throw new Error('El lector respondió ' + res.status + '.');
  } catch (e) {
    nota.textContent = e && /clave|respondió/.test(e.message) ? e.message : 'No se pudo llegar al lector: revisa la dirección.';
    return;
  }
  guardar(RD_CLAVE_LECTOR, { url, clave });
  rd.avisoIA = false;
  $('#dlgRdLector').close();
  rdPintarCab();
  avisar('Listo: las fotos nuevas se leen con IA.');
}
