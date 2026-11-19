/* Portal QUEMPIN — Proyectos en ejecución (ej*).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

/* ---- Proyectos en ejecución (2026-10-28) ---------------------------------------------------------------------------
   Pedido del usuario: una herramienta con el resumen de cada proyecto en ejecución, que abra su carpeta de «Gestión de
   Proyectos», donde se agreguen costos potenciales (no los definitivos: esos los registra el Centro de Costos) desde
   cotizaciones reales, para evaluar si una compra conviene y ver al tiro cómo terminaría el proyecto si se hace; donde se
   fije el avance (y llegue a las demás herramientas), y con otras herramientas útiles.
   Los proyectos son los que el Recorrido pone en Ejecución (rcArmar): el Recorrido, la Planificación y esta vista cuentan
   lo mismo. De cada uno:
     - La venta: la escrita aquí y, si no, el precio neto de su formulación, su cotización emitida o el valor adjudicado
       de la Planilla sin IVA (el monto del Análisis Financiero no viaja por la carpeta).
     - Por categoría: lo presupuestado (los proyectados del Análisis Financiero o, si no, los costos de su formulación),
       lo gastado (los reales del Análisis, que vienen del Centro de Costos), lo comprometido (las OC de Sistema QUEMPIN que
       el Centro de Costos todavía no trae, más lo comprado cuya OC aún no aparece) y lo simulado (las cotizaciones
       marcadas en «Simular»). El costo estimado al cierre es gastado + comprometido + simulado o, si es menos, lo
       presupuestado: lo que todavía no se compra se estima con el presupuesto. El margen sale de la venta.
     - Cada cotización se evalúa contra la línea del presupuesto que reemplaza, lo que QUEMPIN pagó por lo mismo (los
       precios de referencia del Cotizador Histórico, con su buscador), las otras cotizaciones para lo mismo, lo que queda
       en su categoría y el margen.
     - El avance se pide al Análisis Financiero con un «datos-proyecto» al buzón, como «Ingresar avance»: de ahí lo leen
       el Recorrido, la Planificación semanal y el Formulador, y mientras espera al procesador el portal ya lo muestra.
   Lo anotado aquí (cotizaciones, la venta corregida, notas y pendientes) va en «publicado/ejecucion/<dispositivo>.json»,
   un archivo por navegador como la Planificación (esquema ejecucion-proyectos): lo vigente es la unión de todos y en cada
   cosa manda el cambio más reciente, también si es borrarla. Las reglas de cálculo del Formulador (js/calc.js), su
   lector de filas pegadas (js/pegar.js) y el buscador del Cotizador (js/busqueda.js) se cargan de su sitio, como
   js/pulso.js: sin ellos la vista funciona igual, sin la comparación por línea, el pegado ni la referencia histórica. */
const EJ_CATS = [
  { k: 'Materiales', nombre: 'Materiales', calc: 'materiales', total: 'mat', historico: true },
  { k: 'Equipos', nombre: 'Equipos', calc: 'equipos', total: 'eq', historico: true },
  { k: 'Mano de Obra', nombre: 'Mano de obra', calc: 'manoObra', total: 'mo', historico: false },
  { k: 'Otros', nombre: 'Otros', calc: 'otros', total: 'otros', historico: false }
];
const EJ_CAT = new Map(EJ_CATS.map((c) => [c.k, c]));
const EJ_ESTADOS = [
  { id: 'evaluar', nombre: 'Por decidir' }, { id: 'aprobada', nombre: 'Aprobada' },
  { id: 'comprada', nombre: 'Comprada' }, { id: 'descartada', nombre: 'Descartada' }
];
const EJ_FILTROS = [
  { id: 'vigentes', nombre: 'Por decidir y aprobadas', es: (it) => it.estado === 'evaluar' || it.estado === 'aprobada' },
  { id: 'compradas', nombre: 'Compradas', es: (it) => it.estado === 'comprada' },
  { id: 'descartadas', nombre: 'Descartadas', es: (it) => it.estado === 'descartada' },
  { id: 'todas', nombre: 'Todas', es: () => true }
];
const EJ_TIPOS = ['costo', 'nota', 'pendiente', 'venta', 'dia', 'tarifas', 'asociacion', 'presupuesto'];
const EJ_DESTINO = /^(i:[a-z0-9-]{6,40}|l:[A-Za-z0-9_-]{1,40})$/;      // un ítem (su grupo o id) o una línea del presupuesto
const EJ_IVA = 0.19;                                    // Chile: el Análisis Financiero y el Centro de Costos van sin IVA
const EJ_MARGEN = { objetivo: 30, minimo: 20 };         // los de un proyecto nuevo del Formulador (js/store.js)
// Lo que cuesta un día-hombre según su nivel, si el proyecto no tiene formulación ni tarifas propias (las del Formulador)
const EJ_TARIFAS = { n1: 45000, n2: 60000, n3: 75000 };
const EJ_NIVELES = [{ n: 1, nombre: 'Nivel 1' }, { n: 2, nombre: 'Nivel 2' }, { n: 3, nombre: 'Nivel 3' }];
const EJ_JORNADAS = [{ j: 1, nombre: 'Día completo' }, { j: 0.5, nombre: 'Medio día' }];
// Una cotización contra la línea que reemplaza: hasta 3 % más cara está bien, hasta 15 % se revisa, más no conviene.
// Contra lo que QUEMPIN ha pagado: hasta 15 % sobre el promedio está bien; sobre el máximo, no conviene.
const EJ_TOLERANCIA = { linea: 0.03, lineaMala: 0.15, historico: 0.15 };
// Una cotización puede cubrir varias líneas del presupuesto (2026-11-10, pedido del usuario); lo anotado antes trae solo «linea»
const EJ_MAX_LINEAS = 30;
const ejLineasDe = (it) => (Array.isArray(it.lineas) && it.lineas.length ? it.lineas : it.linea ? [it.linea] : []);
const EJ_GASTO_SOBRE_AVANCE = 0.15;                     // gastado el 60 % del presupuesto con 40 % de avance: se avisa
const EJ_RELEER_SEG = 10;                               // 2026-11-10: antes 30; para trabajar a la vez
const EJ_CLAVE = /^(req:(\d{1,6}|\d{3,4}t)|tag:[A-Z0-9]{2,10})$/;
const EJ_ID = /^[a-z0-9-]{6,40}$/;
const EJ_UNIDADES = ['Un.', 'kg', 'm', 'm2', 'm3', 'gl', 'km', 'día', 'hr', 'lt', 'noche'];   // las del Formulador
const EJ_LIBS = { calc: ['js/calc.js', 'QCalc'], pegar: ['js/pegar.js', 'QPegar'], busqueda: ['js/busqueda.js', 'CHBusqueda'] };
const LS_EJ = 'quempin_portal_ejecucion';                 // { proyecto, mios, filtro, pestana, conDatos }: lo elegido en este navegador
const LS_EJ_PENDIENTE = 'quempin_portal_ejecucion_pendiente';   // lo que aún no llega a la carpeta
const ejPrefs = leer(LS_EJ, {}) || {};
const ej = {
  clave: typeof ejPrefs.proyecto === 'string' ? ejPrefs.proyecto : null,   // la tarjeta del Recorrido a la vista; null: la lista
  mios: ejPrefs.mios === true, q: '',
  pestana: ejPrefs.pestana === 'entregados' ? 'entregados' : 'ejecucion',   // En ejecución (raíz de Gestión) o Entregados
  conDatos: ejPrefs.conDatos === true,     // solo los proyectos con algo anotado en su resumen
  filtro: EJ_FILTROS.some((f) => f.id === ejPrefs.filtro) ? ejPrefs.filtro : 'vigentes',
  datos: { archivos: new Map(), mias: new Map(), ef: new Map(), leida: 0 },
  gantt: { porUid: new Map(), porReq: new Map() }, ganttLeido: 0,
  leyendo: null, error: null,
  porGuardar: false, guardando: false, otraVez: false, relojGuardar: null, guardado: 0, errorGuardar: null,
  deshacer: [], recien: new Set(), relojRecien: null,
  ajeno: null, pisado: null,  // 2026-11-10: lo que llegó de otro (quién, cuántas, cuándo) y lo tuyo que reemplazó ([{ id, mio, suyo }])
  libs: new Map(), precios: null, preciosLm: 0, buscador: null, parecidas: new Map(), calc: new Map(),
  docs: null,               // las facturas del Centro de Costos: { porTag: Map(TAG → documentos), actualizado, lm, size }
  docsFiltro: 'todas', docsQ: '', todosDocs: false, asociando: null,
  modelo: null,             // el resumen pintado
  editando: null,           // el diálogo de un ítem: { xs, grupo, ref, cat, proyecto, simular, oc, lineaTocada, previo, quitadas, auto }
  pegadas: null,            // lo que lee el diálogo de pegar
  diasForm: null,           // el calendario de días trabajados: { clave, mes, jornada, personas, nombres, dias (los marcados) }
  diasAbiertos: null,
  sucios: new Map(),        // lo escrito en los campos del resumen, que sobrevive a cada repintado (id → valor)
  tarifasAbiertas: false, todosDias: false, todasNotas: false, enviando: false,
  salud: null,              // el estado elegido en la leyenda del Mapa de salud (ok, warn, bad, sin); null: todos
  espera: null,             // lo que espera el equipo elegido en la lista (decidir, facturas, pendientes); null: todo
  // 2026-11-12, pedido del usuario: la página nueva del proyecto, con la anterior a un clic por si no se adopta bien
  idxPlegado: ejPrefs.idxPlegado === true   // el índice de la izquierda, solo con íconos
};
const ejGuardarPrefs = () => guardar(LS_EJ, { proyecto: ej.clave, mios: ej.mios, filtro: ej.filtro, pestana: ej.pestana, conDatos: ej.conDatos, idxPlegado: ej.idxPlegado });

// ---- Utilidades ---------------------------------------------------------------------------------------------------
const ejPesos = (n) => (n < -0.5 ? '−$' : '$') + Math.round(Math.abs(n)).toLocaleString('es-CL');
// Para lo que no cabe entero: «$1,2 M», «$850 mil»
const ejPct = (x) => (x === null || x === undefined || !isFinite(x) ? '—' : Math.round(x * 100) + ' %');
const ejPuntos = (x) => { const n = Math.round(Math.abs(x) * 100); return n === 1 ? '1 punto' : n + ' puntos'; };
const ejCantidad = (n) => (Math.round(n * 100) / 100).toLocaleString('es-CL');
// «$180.000», «1.234,56», «12,5»: como en Chile (el mismo lector del Formulador, js/pegar.js, cuando está)
function ejNumero(t) {
  if (typeof t === 'number') return isFinite(t) ? t : null;
  if (window.QPegar) return window.QPegar.numero(t);
  let s = texto(t).replace(/[$\s]/g, '');
  if (!s || !/^[\d.,]+$/.test(s)) return null;
  if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  else if (/^\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, '');
  const n = Number(s);
  return isFinite(n) ? n : null;
}
function ejNuevoId(pre) {
  return pre + Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => (b % 36).toString(36)).join('');
}
const ejTxt = (v, max) => texto(v).replace(/\s+/g, ' ').slice(0, max);
const ejFechaCorta = (iso) => { const f = plDesdeISO(iso); return f ? rcCorta(f, new Date()) : ''; };
// Las palabras que dicen algo de una descripción, para comparar dos sin tildes, plurales ni palabras vacías
const EJ_VACIAS = new Set(['de', 'del', 'la', 'el', 'los', 'las', 'en', 'y', 'con', 'para', 'por', 'a', 'un', 'una', 'al', 'o', 'e']);
const ejPalabras = (s) => new Set(norm(s).replace(/[^a-z0-9ñ]+/g, ' ').split(' ').filter((w) => w.length > 1 && !EJ_VACIAS.has(w))
  .map((w) => (w.length > 4 && w.endsWith('s') ? w.slice(0, -1) : w)));
function ejParecido(a, b) {
  const x = ejPalabras(a), y = ejPalabras(b);
  if (!x.size || !y.size) return 0;
  let n = 0;
  x.forEach((w) => { if (y.has(w)) n++; });
  return n / Math.min(x.size, y.size);
}

// ---- Lo del Formulador que se carga de su sitio -------------------------------------------------------------------
function ejLib(nombre) {
  const [ruta, global] = EJ_LIBS[nombre];
  if (window[global]) return Promise.resolve(window[global]);
  if (!ej.libs.has(nombre)) {
    ej.libs.set(nombre, new Promise((listo) => {
      const s = document.createElement('script');
      s.src = HERR.get('formulador').ruta + ruta;
      s.onload = () => listo(window[global] || null);
      s.onerror = () => listo(null);
      document.head.append(s);
    }));
  }
  return ej.libs.get(nombre);
}

// ---- Lo anotado por el equipo: un archivo por navegador en publicado/ejecucion ------------------------------------
/* Una cosa del archivo, validada: la carpeta la puede editar cualquiera con acceso a la biblioteca, así que solo entra lo
   que tiene la forma acordada. Borrar es dejar «borrado»: así gana también en los demás navegadores. */
function ejValidar(x, tope) {
  if (!x || typeof x !== 'object' || !EJ_ID.test(texto(x.id)) || !EJ_CLAVE.test(texto(x.proyecto)) || !EJ_TIPOS.includes(x.tipo)) return null;
  if (typeof x.t !== 'string' || !PL_INSTANTE.test(x.t) || x.t > tope) return null;
  const e = { id: x.id, proyecto: x.proyecto, tipo: x.tipo, t: x.t, por: /^[A-Z]{2,3}$/.test(texto(x.por)) ? texto(x.por) : '' };
  e.creado = typeof x.creado === 'string' && PL_INSTANTE.test(x.creado) && x.creado <= tope ? x.creado : x.t;
  if (x.borrado === true) { e.borrado = true; return e; }
  const monto = (v) => (typeof v === 'number' && isFinite(v) && v >= 0 && v < 1e13 ? v : null);
  if (x.tipo === 'costo') {
    const descripcion = ejTxt(x.descripcion, 200);
    const cantidad = monto(x.cantidad), precio = monto(x.precio);
    if (!descripcion || !EJ_CAT.has(x.categoria) || cantidad === null || precio === null) return null;
    const lineas = [...new Set((Array.isArray(x.lineas) && x.lineas.length ? x.lineas : [x.linea]).map(texto).filter((u) => /^[A-Za-z0-9_-]{1,40}$/.test(u)))].slice(0, EJ_MAX_LINEAS);
    return Object.assign(e, {
      descripcion, categoria: x.categoria, cantidad, precio, unidad: ejTxt(x.unidad, 12),
      proveedor: ejTxt(x.proveedor, 120), cotizacion: ejTxt(x.cotizacion, 60),
      fecha: /^\d{4}-\d{2}-\d{2}$/.test(texto(x.fecha)) ? x.fecha : '',
      estado: EJ_ESTADOS.some((s) => s.id === x.estado) ? x.estado : 'evaluar',
      simular: x.simular !== false, grupo: EJ_ID.test(texto(x.grupo)) ? x.grupo : '', elegida: x.elegida === true,
      oc: /^\d{1,12}$/.test(texto(x.oc)) ? texto(x.oc) : '',
      // Las líneas del presupuesto que reemplaza (antes una sola, «linea», que se sigue leyendo y escribiendo con la primera)
      lineas, linea: lineas[0] || '',
      ref: ejTxt(x.ref, 80), nota: ejTxt(x.nota, 300)
    });
  }
  if (x.tipo === 'nota') {
    const t = texto(x.texto).slice(0, 1000).trim();
    return t ? Object.assign(e, { texto: t }) : null;
  }
  if (x.tipo === 'pendiente') {
    const t = ejTxt(x.texto, 200);
    return t ? Object.assign(e, { texto: t, listo: x.listo === true, responsable: /^[A-Z]{2,3}$/.test(texto(x.responsable)) ? texto(x.responsable) : '' }) : null;
  }
  // Un día trabajado por una persona (del equipo o escrita a mano, «x-juan-perez» con su nombre), con su jornada y su nivel
  if (x.tipo === 'dia') {
    const j = Number(x.jornada);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(texto(x.fecha)) || !plPerValida(x.persona) || !(j > 0 && j <= 2) || ![1, 2, 3].includes(x.nivel)) return null;
    return Object.assign(e, { fecha: x.fecha, persona: x.persona, nombre: PL_PER_MANO.test(x.persona) ? ejTxt(x.nombre, 60) : '', jornada: j, nivel: x.nivel,
      origen: x.origen === 'planificacion' ? 'planificacion' : '', nota: ejTxt(x.nota, 200) });
  }
  // Lo que cuesta un día-hombre de cada nivel en este proyecto (si no, las tarifas de su formulación)
  if (x.tipo === 'tarifas') {
    const ns = ['n1', 'n2', 'n3'].map((k) => monto(x[k]));
    if (ns.some((n) => !(n > 0))) return null;
    return Object.assign(e, { n1: ns[0], n2: ns[1], n3: ns[2] });
  }
  // A qué gastos proyectados o cotizados corresponde una factura del Centro de Costos (2026-11-06); vacía: a ninguno
  if (x.tipo === 'asociacion') {
    if (!/^[A-Z0-9]+-\d+$/.test(texto(x.ref)) || !Array.isArray(x.destinos)) return null;
    return Object.assign(e, { ref: texto(x.ref), destinos: [...new Set(x.destinos.filter((d) => typeof d === 'string' && EJ_DESTINO.test(d)))].slice(0, 50) });
  }
  // Un presupuesto actualizado (2026-11-13): lo que cambia respecto del de su formulación, por línea (su uid), sus costos
  // nuevos, el % de gastos generales e imprevistos (null: el de la formulación), la venta (null: la de la formulación) y si
  // se usa en «Cómo va el proyecto»
  if (x.tipo === 'presupuesto') {
    const cambios = (Array.isArray(x.cambios) ? x.cambios : []).slice(0, 3000).filter((c) => c && EJ_PR_UID.test(texto(c.uid))).map((c) => {
      const r = { uid: texto(c.uid) };
      if (monto(c.cantidad) !== null) r.cantidad = c.cantidad;
      if (monto(c.unitario) !== null) r.unitario = c.unitario;
      if (c.quitado === true) r.quitado = true;
      return r;
    });
    const nuevos = (Array.isArray(x.nuevos) ? x.nuevos : []).slice(0, 500)
      .filter((n) => n && EJ_ID.test(texto(n.id)) && EJ_CAT.has(n.categoria) && monto(n.cantidad) !== null && monto(n.unitario) !== null)
      .map((n) => ({ id: n.id, descripcion: ejTxt(n.descripcion, 200), categoria: n.categoria, partida: ejTxt(n.partida, 40), unidad: ejTxt(n.unidad, 12), cantidad: n.cantidad, unitario: n.unitario }));
    const gg = typeof x.gg === 'number' && isFinite(x.gg) && x.gg >= 0 && x.gg <= 100 ? x.gg : null;
    return Object.assign(e, { nombre: ejTxt(x.nombre, 60) || 'Presupuesto actualizado', cambios, nuevos, gg, venta: monto(x.venta) > 0 ? x.venta : null, seguimiento: x.seguimiento === true });
  }
  // La venta neta escrita aquí; null vuelve a la que se calcula
  if (x.monto !== null && !(monto(x.monto) > 0)) return null;
  return Object.assign(e, { monto: x.monto, nota: ejTxt(x.nota, 200) });
}
function ejLeerArchivo(sobre) {
  const d = sobre && sobre.esquema === 'quempin.intercambio/1' && sobre.herramienta === 'ejecucion' ? sobre.datos : null;
  if (!d || typeof d !== 'object' || !Array.isArray(d.items)) return null;
  const de = texto(d.dispositivo).slice(0, 24);
  const tope = new Date(Date.now() + 365 * DIA).toISOString();    // un reloj muy adelantado no manda para siempre
  const items = new Map();
  d.items.slice(0, 5000).forEach((x) => {
    const e = ejValidar(x, tope);
    if (e) { e.de = de; plPoner(items, e.id, e); }
  });
  return { items, generado: texto(sobre.generado) };
}
function ejRecalcular() {
  const d = ej.datos;
  const ef = new Map();
  [...d.archivos.values()].map((a) => a.items).concat([d.mias]).forEach((m) => m.forEach((e, k) => plPoner(ef, k, e)));
  d.ef = ef;
}
function ejAdoptar(r) { r.items.forEach((e, k) => plPoner(ej.datos.mias, k, e)); }
function ejSobre() {
  const sinDe = (e) => { const x = Object.assign({}, e); delete x.de; return x; };   // el dispositivo ya va arriba
  return {
    esquema: 'quempin.intercambio/1', herramienta: 'ejecucion', tipo: 'ejecucion-proyectos',
    generado: new Date().toISOString(), autor: estado.usuario || '',
    datos: { dispositivo: plDispositivo(), items: [...ej.datos.mias.values()].map(sinDe) }
  };
}
const ejNombreArchivo = () => plDispositivo() + '.json';
async function ejCarpeta(dir, crear) {
  try { return await (await dir.getDirectoryHandle('publicado', { create: crear })).getDirectoryHandle('ejecucion', { create: crear }); }
  catch (e) { if (crear) throw e; return null; }     // todavía nadie anotó nada
}
// Lee los archivos del equipo: solo los que cambiaron desde la última vez. Devuelve si algo cambió.
async function ejLeer(dir) {
  const d = ej.datos;
  const yaLeida = !!d.leida;
  const carpeta = await ejCarpeta(dir, false);
  let cambio = !d.leida;
  const vistos = new Set();
  if (carpeta) {
    for await (const [n, h] of carpeta.entries()) {
      if (h.kind !== 'file' || !/\.json$/i.test(n)) continue;
      vistos.add(n);
      let f;
      try { f = await h.getFile(); } catch (e) { continue; }
      const previo = d.archivos.get(n);
      if (previo && previo.lm === f.lastModified && previo.size === f.size) continue;
      let r = null;
      try { r = ejLeerArchivo(JSON.parse(rcSinBom(await f.text()))); } catch (e) { r = null; }   // a medio sincronizar
      if (!r) continue;
      r.lm = f.lastModified;
      r.size = f.size;
      d.archivos.set(n, r);
      cambio = true;
      r.items.forEach((e) => { planif.reloj = Math.max(planif.reloj, Date.parse(e.t)); });
      if (n === ejNombreArchivo()) ejAdoptar(r);
    }
  }
  d.archivos.forEach((x, n) => { if (!vistos.has(n)) { d.archivos.delete(n); cambio = true; } });
  d.leida = Date.now();
  if (cambio) {
    const antes = d.ef;
    ejRecalcular();
    if (yaLeida) ejNotarAjenos(antes);
  }
  return cambio;
}
/* Lo que acaba de llegar de otro computador (2026-11-10, como en la Planificación): se ilumina, la línea de arriba dice
   quién fue y, si reemplaza algo que este navegador acababa de cambiar, la franja de lo reemplazado lo dice. */
function ejNotarAjenos(antes) {
  const yo = plDispositivo();
  const ajenos = [], pisados = [];
  ej.datos.ef.forEach((e, id) => {
    const a = antes.get(id);
    if (e.de === yo || (a && a.t === e.t)) return;
    ajenos.push(e);
    if (a && a.de === yo && ejValor(a) !== ejValor(e) && pisReciente(a, e)) pisados.push({ id, mio: a, suyo: e });
  });
  if (!ajenos.length) return;
  ej.ajeno = { quien: unir([...new Set(ajenos.map((e) => e.por || 'Otro computador'))]), n: ajenos.length, cuando: Date.now() };
  ajenos.forEach((e) => ej.recien.add(e.id));
  clearTimeout(ej.relojRecien);
  ej.relojRecien = setTimeout(() => {
    ej.recien.clear();
    document.querySelectorAll('#ejProyecto .recien').forEach((x) => x.classList.remove('recien'));
  }, 6000);
  if (!pisados.length) return;
  const items = new Map((ej.pisado || []).map((x) => [x.id, x]));
  pisados.forEach((x) => { const v = items.get(x.id); items.set(x.id, v ? Object.assign({}, x, { mio: v.mio }) : x); });
  ej.pisado = [...items.values()];
}
// Lo que cuenta de una cosa al comparar dos versiones: lo validado, sin quién ni cuándo
function ejValor(e) {
  const v = ejValidar(e, '9999') || e;
  return JSON.stringify(Object.keys(v).filter((k) => !['t', 'por', 'de', 'creado'].includes(k)).sort().map((k) => [k, v[k]]));
}
function ejPisadoTexto({ mio, suyo }) {
  const e = mio.borrado ? suyo : mio;
  const que = e.tipo === 'costo' ? 'la cotización «' + (e.descripcion || '') + '»' : e.tipo === 'nota' ? 'una nota'
    : e.tipo === 'pendiente' ? 'el pendiente «' + (e.texto || '') + '»' : e.tipo === 'dia' ? 'el día ' + (e.fecha || '') + ' de ' + plNom(e.persona)
    : e.tipo === 'tarifas' ? 'las tarifas' : e.tipo === 'asociacion' ? 'la factura ' + (e.ref || '') : 'la venta corregida';
  const donde = mio.proyecto.startsWith('req:') ? 'N° ' + mio.proyecto.slice(4) : mio.proyecto.slice(4);
  const quien = suyo.por || 'Otro computador';
  return quien + (suyo.borrado ? ' borró ' : mio.borrado ? ' volvió a poner lo que borraste: ' : ' cambió ') + que + ' (' + donde + ').';
}
function ejPintarPisado() {
  const p = ej.pisado && ej.pisado.length ? ej.pisado : null;
  pisPintar($('#ejPisado'), p && { quien: pisQuien(p), lineas: p.map(ejPisadoTexto) }, ejVolverPisado, () => { ej.pisado = null; ejPintarPisado(); });
}
// «Volver a lo mío»: lo tuyo vuelve como un cambio nuevo, con su Deshacer
function ejVolverPisado() {
  const p = ej.pisado;
  if (!p) return;
  ej.pisado = null;
  ejPoner(p.map((x) => sinMarca(x.mio)), 'Volvió lo tuyo; le llega a ' + pisQuien(p) + ' con OneDrive.');
}
async function ejEscribir(dir) {
  const d = ej.datos;
  const carpeta = await ejCarpeta(dir, true);
  const nombre = ejNombreArchivo();
  // Otra pestaña de este mismo navegador pudo escribir el mismo archivo: lo suyo se suma antes de reemplazarlo.
  try {
    const f = await (await carpeta.getFileHandle(nombre)).getFile();
    const r = ejLeerArchivo(JSON.parse(rcSinBom(await f.text())));
    if (r) ejAdoptar(r);
  } catch (e) { /* todavía no existe */ }
  const sobre = ejSobre();
  await exigirEsquema(dir, 'ejecucion-proyectos', sobre);
  const h = await carpeta.getFileHandle(nombre, { create: true });
  const w = await h.createWritable();
  await w.write(JSON.stringify(sobre, null, 1));
  await w.close();
  const f = await h.getFile();
  const copia = ejLeerArchivo(sobre);
  copia.lm = f.lastModified;
  copia.size = f.size;
  d.archivos.set(nombre, copia);
  ejRecalcular();
}
// Lo que espera guardarse queda también en este navegador: si la página se cierra antes, se guarda la próxima vez.
function ejGuardarPendiente() {
  try {
    if (ej.porGuardar) localStorage.setItem(LS_EJ_PENDIENTE, JSON.stringify(ejSobre().datos));
    else localStorage.removeItem(LS_EJ_PENDIENTE);
  } catch (e) { /* sin almacenamiento: solo en esta visita */ }
}
function ejRecuperarPendiente() {
  let p = null;
  try { p = JSON.parse(localStorage.getItem(LS_EJ_PENDIENTE) || 'null'); } catch (e) { p = null; }
  const r = p && typeof p === 'object' ? ejLeerArchivo({ esquema: 'quempin.intercambio/1', herramienta: 'ejecucion', datos: p }) : null;
  if (!r) return;
  ejAdoptar(r);
  ejRecalcular();
  ej.porGuardar = true;
}
function ejProgramarGuardado() {
  ej.porGuardar = true;
  ejGuardarPendiente();
  clearTimeout(ej.relojGuardar);
  ej.relojGuardar = setTimeout(ejGuardar, 450);
  ejPintarFrescura();
}
async function ejGuardar() {
  if (soloLectura()) return;
  clearTimeout(ej.relojGuardar);
  if (ej.guardando) { ej.otraVez = true; return; }
  if (!ej.porGuardar) return;
  ej.guardando = true;
  ejPintarFrescura();
  try {
    if (!rc.dir) throw new Error('La biblioteca del equipo no está conectada con permiso en este navegador.');
    // Se marca guardado antes de escribir: un cambio que llega mientras se escribe lo vuelve a marcar y se guarda después
    ej.porGuardar = false;
    try { await ejEscribir(rc.dir); } catch (e) { ej.porGuardar = true; throw e; }
    ej.errorGuardar = null;
    ej.guardado = Date.now();
  } catch (e) {
    console.error(e);
    ej.errorGuardar = e;
  }
  ej.guardando = false;
  ejGuardarPendiente();
  ejPintarFrescura();
  if (ej.otraVez) { ej.otraVez = false; ejGuardar(); }
}
/* Cada cambio: las cosas nuevas o cambiadas, enteras. Quedan como lo de este navegador con su instante, se guardan en la
   carpeta y se pueden deshacer (el aviso o Ctrl Z). */
function ejPoner(cambios, mensaje) {
  if (mvNoSe()) return;
  const antes = cambios.map((e) => {
    const a = ej.datos.ef.get(e.id);
    return a ? Object.assign({}, a) : { id: e.id, proyecto: e.proyecto, tipo: e.tipo, creado: e.creado, nuevo: true };
  });
  cambios.forEach((e) => {
    const x = Object.assign({}, e, { t: plAhora(), por: estado.usuario || '', de: plDispositivo() });
    if (!x.creado) x.creado = x.t;
    ej.datos.mias.set(x.id, x);
    ej.recien.add(x.id);
  });
  // Lo que vuelves a cambiar sale de la franja de lo reemplazado
  if (ej.pisado) { ej.pisado = ej.pisado.filter((x) => !cambios.some((c) => c.id === x.id)); if (!ej.pisado.length) ej.pisado = null; }
  ejRecalcular();
  ej.deshacer.push(antes);
  if (ej.deshacer.length > 40) ej.deshacer.shift();
  ejProgramarGuardado();
  clearTimeout(ej.relojRecien);
  ej.relojRecien = setTimeout(() => {
    ej.recien.clear();
    document.querySelectorAll('#ejProyecto .recien').forEach((x) => x.classList.remove('recien'));
  }, 1600);
  ejPintar();
  if (mensaje) avisar(mensaje, { texto: 'Deshacer', ir: ejDeshacer });
}
function ejDeshacer() {
  const antes = ej.deshacer.pop();
  if (!antes) { avisar('No hay cambios que deshacer en esta vista.'); return; }
  antes.forEach((a) => {
    const x = a.nuevo ? { id: a.id, proyecto: a.proyecto, tipo: a.tipo, creado: a.creado, borrado: true } : Object.assign({}, a);
    delete x.nuevo;
    Object.assign(x, { t: plAhora(), por: estado.usuario || '', de: plDispositivo() });
    if (!x.creado) x.creado = x.t;
    ej.datos.mias.set(x.id, x);
  });
  ejRecalcular();
  ejProgramarGuardado();
  ejPintar();
  avisar('Se deshizo el último cambio.');
}

// ---- Lo demás que se lee de la carpeta: las cartas Gantt y los precios de referencia ---------------------------------
// Las cartas Gantt (publicado/gantt/<uid>.json, herramienta del Formulador) traen su resumen: avance, inicio y término
async function ejLeerGantt(dir) {
  const porUid = new Map(), porReq = new Map();
  for (const s of await rcJsonDe(await rcSub(dir, 'publicado', 'gantt'))) {
    const d = s && s.tipo === 'carta-gantt' && s.datos;
    if (!d || d.eliminado || !s.resumen || typeof s.resumen !== 'object') continue;
    const p = d.proyecto && typeof d.proyecto === 'object' ? d.proyecto : {};
    const x = { uid: texto(d.uid), resumen: s.resumen, modificado: texto(d.modificado) };
    if (p.uid) porUid.set(String(p.uid), x);
    const n = rcNum(p.req);
    if (n && (!porReq.has(n) || porReq.get(n).modificado < x.modificado)) porReq.set(n, x);
  }
  ej.gantt = { porUid, porReq };
  ej.ganttLeido = Date.now();
}
/* Los precios de referencia del Cotizador Histórico (publicado/precios-referencia.json, ~1 MB): se leen recién cuando hay
   algo que comparar, y otra vez solo si el archivo cambió. El buscador es el del Cotizador (js/busqueda.js). */
async function ejPrecios() {
  if (!rc.dir) return null;
  const B = await ejLib('busqueda');
  try {
    const f = await (await (await rc.dir.getDirectoryHandle('publicado')).getFileHandle('precios-referencia.json')).getFile();
    if (ej.precios && ej.preciosLm === f.lastModified) return ej.precios;
    const d = (JSON.parse(rcSinBom(await f.text())) || {}).datos;
    if (!d || !Array.isArray(d.hojas)) return ej.precios;
    ej.precios = d;
    ej.preciosLm = f.lastModified;
    ej.parecidas.clear();
    ej.buscador = B ? B.crear(d.hojas, d.busqueda || {}) : null;
    return d;
  } catch (e) { return ej.precios; }
}
/* Las facturas del Centro de Costos de cada proyecto (2026-11-06): publicado/documentos-proyecto.json, que el procesador
   arma desde el snapshot del tablero del Centro de Costos (esquema documentos-proyecto). Se relee solo si cambió. Cada
   documento va con su TAG (el prefijo del N° Ref.) y cada ítem con la categoría del Análisis Financiero. */
const EJ_DOC_CATS = new Set(['Materiales', 'Equipos', 'Otros']);
async function ejLeerDocumentos(dir) {
  let f;
  try { f = await (await (await dir.getDirectoryHandle('publicado')).getFileHandle('documentos-proyecto.json')).getFile(); }
  catch (e) { const habia = !!ej.docs; ej.docs = null; return habia; }   // el procesador todavía no lo publica
  if (ej.docs && ej.docs.lm === f.lastModified && ej.docs.size === f.size) return false;
  let d = null;
  try { d = (JSON.parse(rcSinBom(await f.text())) || {}).datos; } catch (e) { return false; }   // a medio sincronizar
  if (!d || !Array.isArray(d.documentos)) return false;
  const porTag = new Map();
  const num = (v) => (typeof v === 'number' && isFinite(v) ? v : 0);
  d.documentos.forEach((x) => {
    if (!x || !/^[A-Z0-9]+-\d+$/.test(texto(x.ref)) || !/^[A-Z0-9]{2,10}$/.test(texto(x.tag))) return;
    const enlace = /^https:\/\/quempinspa2020\.sharepoint\.com\//.test(texto(x.enlace)) ? texto(x.enlace) : '';
    const items = (Array.isArray(x.items) ? x.items : []).filter((i) => i && typeof i === 'object').map((i) => ({
      nombre: ejTxt(i.nombre, 160), cantidad: num(i.cantidad), unitario: num(i.unitario), neto: num(i.neto),
      categoria: EJ_DOC_CATS.has(i.categoria) ? i.categoria : 'Otros' }));
    const doc = { ref: texto(x.ref), tag: texto(x.tag), fecha: /^\d{4}-\d{2}-\d{2}$/.test(texto(x.fecha)) ? x.fecha : '', tipo: ejTxt(x.tipo, 40),
      numero: ejTxt(x.numero, 40), proveedor: ejTxt(x.proveedor, 120), resumen: ejTxt(x.resumen, 300), neto: num(x.neto),
      categoria: EJ_DOC_CATS.has(x.categoria) ? x.categoria : 'Otros', estado: ejTxt(x.estado, 40), pendiente: x.pendiente === true, enlace, items };
    if (!porTag.has(doc.tag)) porTag.set(doc.tag, []);
    porTag.get(doc.tag).push(doc);
  });
  porTag.forEach((xs) => xs.sort((a, b) => b.fecha.localeCompare(a.fecha) || b.ref.localeCompare(a.ref)));
  ej.docs = { porTag, actualizado: texto(d.actualizado), lm: f.lastModified, size: f.size };
  return true;
}
/* Las hojas del Cotizador parecidas a lo que se compra; «bien»: cubre al menos la mitad de lo pedido y no es de otra
   medida. Con ella se compara sola, y la evaluación dice cuál es: si no es lo mismo, se elige otra o ninguna. */
function ejParecidas(desc) {
  if (!ej.buscador || !texto(desc)) return [];
  const k = norm(desc).trim();
  if (!ej.parecidas.has(k)) {
    let r = [];
    try { r = (ej.buscador.buscar(desc).resultados || []).slice(0, 5); } catch (e) { r = []; }
    ej.parecidas.set(k, r.filter((x) => x.item && x.item.precio).map((x) => ({ hoja: x.item, bien: x.cobertura >= 0.5 && x.medidaOk !== false })));
  }
  return ej.parecidas.get(k);
}
// La hoja con que se compara una cotización: la elegida, «-» ninguna, o la más parecida si calza bien
function ejReferencia(it) {
  const c = EJ_CAT.get(it.categoria);
  if (!c || !c.historico || it.ref === '-' || !ej.precios) return null;
  const ps = ejParecidas(it.descripcion);
  if (it.ref) return (ps.find((x) => x.hoja.clave === it.ref) || {}).hoja || ej.precios.hojas.find((h) => h.clave === it.ref) || null;
  return ps[0] && ps[0].bien ? ps[0].hoja : null;
}

// ---- Cada proyecto: de dónde sale cada cifra (solo calcula) ----------------------------------------------------------
/* Los de esta vista, en dos pestañas (2026-11-09, pedido del usuario: «solo deben aparecer proyectos que se encuentren
   dentro de la carpeta de Gestión de Proyectos»; los cerrados, en otra pestaña con los de la carpeta de entregados):
   - «En ejecución»: los que tienen carpeta en la raíz de Gestión de Proyectos (t.gestion), también si ya terminaron (lo
     avisa) o si su carpeta no lleva N° (se ve, pero sin N° ni TAG no se le anota nada). Mientras el procesador no publique
     esas carpetas (rc.datos.hayGestion), los que el Recorrido pone en Ejecución, como antes.
   - «Entregados»: los que tienen carpeta en «0 Proyectos Entregados <año>» (t.entregado) y no en la raíz.
   Lo que no tiene carpeta en ninguna de las dos no sale aquí; el Recorrido lo sigue abriendo con su clave (ejPintar). */
const ejHayGestion = () => !!(rc.datos && rc.datos.hayGestion);
const ejTodas = () => rc.tarjetas.concat(rc.entregadas || []);
const ejTarjetas = (pestana = ej.pestana) => (pestana === 'entregados'
  ? ejTodas().filter((t) => t.entregado && !t.gestion)
  : rc.tarjetas.filter((t) => t.gestion || (!ejHayGestion() && t.etapa === 'ejecucion' && (t.req || t.tag))));
// Sus claves: su N° y su TAG. Lo anotado con el TAG sigue siendo del proyecto cuando recibe su N° (o al revés).
const ejClaves = (t) => [t.req ? 'req:' + t.req : '', t.tag ? 'tag:' + t.tag : ''].filter(Boolean);
const ejClave = (t) => ejClaves(t)[0];
function ejDe(t, tipo) {
  const ks = new Set(ejClaves(t));
  return [...ej.datos.ef.values()].filter((e) => e.tipo === tipo && !e.borrado && ks.has(e.proyecto));
}
// Las claves con algo anotado en su resumen (una cotización, un día, una nota, una venta, una factura asociada…): el
// filtro «Solo con datos anotados» (2026-11-09). Una vez por repintado de la lista.
function ejConDatosSet() {
  const s = new Set();
  ej.datos.ef.forEach((e) => { if (e && !e.borrado && e.proyecto) s.add(e.proyecto); });
  return s;
}
// Su formulación completa, del repositorio del equipo (la misma que eligió el Recorrido)
function ejFormulacion(t) {
  const f = t.formulacion;
  const x = f && rc.datos ? rc.datos.formulaciones.find((s) => s.datos && String(s.datos.uid) === f.uid) : null;
  return x ? { datos: x.datos, resumen: x.resumen && typeof x.resumen === 'object' ? x.resumen : {} } : null;
}
const ejMoneda = (form) => texto(form && form.datos.parametros && form.datos.parametros.moneda) || 'CLP';
// El cálculo de la formulación con las reglas del Formulador (js/calc.js), una vez por versión
function ejCalculo(form) {
  if (!form || !window.QCalc) return null;
  const k = form.datos.uid + '|' + texto(form.datos.modificado);
  if (!ej.calc.has(k)) {
    let r = null;
    try { r = window.QCalc.computeProject(form.datos); } catch (e) { r = null; }
    ej.calc.set(k, r);
  }
  return ej.calc.get(k);
}
/* Las líneas del presupuesto de la formulación (materiales, equipos, mano de obra y otros), para elegir la que reemplaza
   una cotización: su cantidad total, su costo unitario y su total, como los calcula el Formulador. */
function ejLineas(form, calc) {
  if (!calc || ejMoneda(form) !== 'CLP') return [];
  const out = [];
  EJ_CATS.forEach((c) => {
    const crudos = new Map((Array.isArray(form.datos[c.calc]) ? form.datos[c.calc] : []).map((it) => [it.uid, it]));
    ((calc.lines && calc.lines[c.calc]) || []).forEach((l) => {
      if (!(l.subtotal > 0) || !/^[A-Za-z0-9_-]{1,40}$/.test(String(l.uid))) return;
      const it = crudos.get(l.uid) || {};
      const mo = c.calc === 'manoObra';
      out.push({ uid: String(l.uid), cat: c.k, code: l.code, descripcion: texto(l.descripcion) || l.code, partida: texto(l.partidaCode),
        unidad: mo ? 'día-hombre' : texto(it.unidad), cantidad: mo ? l.dh : (Number(l.qtyPartida) || 0) * (Number(it.cantidad) || 0),
        unitario: mo ? null : Number(it.costoUnitario) || 0, subtotal: l.subtotal });
    });
  });
  return out;
}
// La línea más parecida a lo que se compra, de su categoría (o null)
function ejLineaSugerida(desc, cat, lineas) {
  let mejor = null, p = 0;
  lineas.forEach((l) => { if (l.cat !== cat) return; const x = ejParecido(desc, l.descripcion); if (x > p) { p = x; mejor = l; } });
  return p >= 0.6 ? mejor : null;
}
/* La venta neta: la escrita aquí y, si no, el precio neto de su formulación, su cotización emitida o el valor adjudicado
   de la Planilla (que lleva IVA). */
function ejVenta(t, form, calc) {
  const v = ejDe(t, 'venta').sort((a, b) => (a.t < b.t ? 1 : -1))[0];
  if (v && v.monto) return { monto: v.monto, fuente: 'Escrita aquí' + (v.por ? ' por ' + v.por : '') + ', ' + plCuando(v.t) + (v.nota ? ': «' + v.nota + '»' : ''), manual: v };
  if (form && ejMoneda(form) === 'CLP') {
    const pn = calc ? calc.totals.precioNeto : Number(form.resumen.precioNeto);
    if (pn > 0) return { monto: pn, fuente: 'Precio neto de su formulación ' + t.formulacion.codigo + (t.formulacion.version > 1 ? ' v' + t.formulacion.version : '') };
  }
  const cot = (t.cotizaciones || []).filter((c) => texto(c.moneda || 'CLP') === 'CLP' && Number(c.neto) > 0)
    .sort((a, b) => String(b.fecha).localeCompare(String(a.fecha)))[0];
  if (cot) return { monto: Number(cot.neto), fuente: 'Neto de su cotización ' + texto(cot.folio) };
  const adj = t.planilla ? Number(t.planilla.valorAdjudicado) : 0;
  if (adj > 0) return { monto: Math.round(adj / (1 + EJ_IVA)), fuente: 'Valor adjudicado de la Planilla de Ingreso, sin IVA' };
  return null;
}
// Lo presupuestado por categoría: los proyectados del Análisis Financiero o, si no tiene, los costos de su formulación
function ejPresupuesto(t, form, calc) {
  const p = t.af && t.af.proyectados;
  const por = (f) => Object.fromEntries(EJ_CATS.map((c) => [c.k, Math.max(0, Number(f(c)) || 0)]));
  if (p && typeof p === 'object' && EJ_CATS.some((c) => typeof p[c.k] === 'number')) return { por: por((c) => p[c.k]), fuente: 'Presupuesto del Análisis Financiero' };
  if (form && ejMoneda(form) === 'CLP') {
    const de = 'Costos de su formulación ' + t.formulacion.codigo;
    if (calc) return { por: por((c) => calc.totals[c.total]), fuente: de };
    const af = form.resumen.costosAF;
    if (af && typeof af === 'object' && EJ_CATS.some((c) => typeof af[c.k] === 'number')) return { por: por((c) => af[c.k]), fuente: de };
  }
  return null;
}
/* Sus órdenes de compra (Sistema QUEMPIN, por el cruce de proyectos): en el gasto (el Centro de Costos ya la trajo o la
   reemplazó su factura), comprometida (todavía no está ahí: se suma), por confirmar (el procesador no lo sabe) o en otra
   moneda (no se suma). Una OC cuenta en la categoría de la compra que la lleva; si no, en Materiales, como en el Centro
   de Costos. */
function ejOCs(t, costos) {
  const c = t.req && rc.datos ? rc.datos.cruce.find((x) => rcNum(x && x.req) === t.req) : null;
  const compras = new Map(costos.filter((it) => it.oc).map((it) => [it.oc, it]));
  return (c && Array.isArray(c.ordenes) ? c.ordenes : []).filter((o) => o && texto(o.folio)).map((o) => {
    const folio = texto(o.folio);
    const it = compras.get(folio) || null;
    const moneda = texto(o.moneda) || 'CLP';
    const estado = moneda !== 'CLP' ? 'moneda' : o.enCentroCostos === true ? 'gasto' : o.enCentroCostos === false ? 'comprometida' : 'confirmar';
    return { folio, fecha: texto(o.fecha), proveedor: texto(o.contraparte), referencia: texto(o.referencia), neto: Number(o.neto) || 0,
      moneda, estado, cat: it ? it.categoria : 'Materiales', compra: it };
  }).sort((a, b) => b.fecha.localeCompare(a.fecha) || b.folio.localeCompare(a.folio));
}
/* Cómo cuenta una cotización en el costo estimado: 'q' simulada (por decidir o aprobada, marcada en «Simular»), 'c'
   comprometida (comprada con una OC que todavía no aparece en Sistema QUEMPIN) o '' (descartada, o comprada: ya la
   cuenta su OC o, sin OC, su factura cuando llegue al Centro de Costos). */
function ejCuentaComo(it, folios) {
  if (it.estado === 'descartada') return '';
  if (it.estado === 'comprada') return it.oc && !folios.has(it.oc) ? 'c' : '';
  return it.simular ? 'q' : '';
}
// Las otras cotizaciones para lo mismo (el grupo lleva el id de la primera, que lo tiene recién al guardar la segunda)
const ejHermanas = (it, costos) => (it.grupo ? costos.filter((x) => x.id !== it.id && (x.grupo === it.grupo || x.id === it.grupo)) : []);
/* Un ítem con varios proveedores son sus cotizaciones, con el mismo grupo. La que se ve en su fila y puede contar: la
   comprada o aprobada; si no, la elegida en el menú Proveedor, la que se simula o, si no, la más barata. */
function ejElegida(xs) {
  const ultima = (f) => xs.filter(f).sort((a, b) => (a.t < b.t ? 1 : -1))[0];
  return ultima((x) => x.estado === 'comprada') || ultima((x) => x.estado === 'aprobada') || ultima((x) => x.elegida)
    || ultima((x) => x.simular && x.estado === 'evaluar') || xs.find((x) => x.estado !== 'descartada' && x.precio > 0) || xs[0];
}
const ejItems = (costos) => ejBloques(costos).map((xs) => ({ xs, it: ejElegida(xs) }));
// Lo que les pasa a los demás proveedores de un ítem según su estado: aprobarlo, comprarlo o descartarlo los deja descartados
const ejEstadoOtra = (est) => (est === 'evaluar' ? 'evaluar' : 'descartada');

/* La mano de obra de los días trabajados (pedido del usuario, 2026-10-28: «indicar días en que se ha trabajado para
   estimar los costos reales asociados a mano de obra», sin que sea la única forma de ingresarla). Cada persona y día es
   una cosa del archivo, con su jornada (día completo o medio) y su nivel; su costo, el de la tarifa de ese nivel. */
const ejSlugClave = (k) => k.replace(':', '-').toLowerCase();
const ejIdDia = (t, fecha, per) => ('dia-' + ejSlugClave(ejClave(t)) + '-' + fecha.replace(/-/g, '') + '-' + per.toLowerCase()).slice(0, 40);
const ejNomPer = (d) => (PL_PER_MANO.test(d.persona) ? d.nombre || plNom(d.persona) : d.persona);
// Uno por persona y día (si se anotó con el TAG y con el N°, manda el más reciente), del más nuevo al más antiguo
function ejDias(t) {
  const por = new Map();
  ejDe(t, 'dia').forEach((d) => { const k = d.fecha + '|' + d.persona; if (plGana(por.get(k), d)) por.set(k, d); });
  return [...por.values()].sort((a, b) => b.fecha.localeCompare(a.fecha) || plComparar(ejNomPer(a), ejNomPer(b)));
}
// El nivel con que se anotó por última vez a esa persona, en cualquier proyecto (2 la primera vez)
function ejNivelDe(per) {
  let u = null;
  ej.datos.ef.forEach((e) => { if (e.tipo === 'dia' && !e.borrado && e.persona === per && (!u || e.t > u.t)) u = e; });
  return u ? u.nivel : 2;
}
// Lo que cuesta un día-hombre de cada nivel: las tarifas de este proyecto, las de su formulación o las del Formulador
function ejTarifas(t, form) {
  const x = ejDe(t, 'tarifas').sort((a, b) => (a.t < b.t ? 1 : -1))[0];
  if (x) return { n1: x.n1, n2: x.n2, n3: x.n3, fuente: 'propias de este proyecto', propias: x };
  const p = form && form.datos.parametros;
  if (p && ejMoneda(form) === 'CLP' && ['tarifaN1', 'tarifaN2', 'tarifaN3'].every((k) => Number(p[k]) > 0)) {
    return { n1: Number(p.tarifaN1), n2: Number(p.tarifaN2), n3: Number(p.tarifaN3), fuente: 'las de su formulación' };
  }
  return Object.assign({ fuente: 'las del Formulador' }, EJ_TARIFAS);
}
function ejManoObra(t, form, calc) {
  const tarifas = ejTarifas(t, form);
  const dias = ejDias(t);
  let dh = 0, costo = 0;
  dias.forEach((d) => { dh += d.jornada; costo += d.jornada * tarifas['n' + d.nivel]; });
  return { dias, dh, costo, tarifas, dhP: calc && calc.totals.dh > 0 ? calc.totals.dh : null, moP: calc ? calc.totals.mo : null };
}
/* Las facturas del Centro de Costos de un proyecto (2026-11-06): las de su TAG o su N° (el TAG es el N° de la Planilla
   desde el 2026-11-05; los antiguos, siglas). null: el procesador todavía no las publica. */
function ejDocumentosDe(t) {
  if (!ej.docs) return null;
  const tags = [...new Set([t.tag, t.req].map((x) => texto(x).toUpperCase()).filter(Boolean))];
  return tags.flatMap((k) => ej.docs.porTag.get(k) || []);
}
// Lo de cada documento por categoría del Análisis Financiero: sus ítems o, sin detalle, el documento entero
function ejDocPorCat(d) {
  const por = { Materiales: 0, Equipos: 0, Otros: 0 };
  if (d.items.length) d.items.forEach((i) => { por[i.categoria] += i.neto; }); else por[d.categoria] += d.neto;
  return por;
}
// A qué gastos corresponde cada factura (N° Ref. → destinos), la anotación más reciente de cada una
function ejAsociaciones(t) {
  const por = new Map();
  ejDe(t, 'asociacion').forEach((a) => { if (!por.has(a.ref) || por.get(a.ref).t < a.t) por.set(a.ref, a); });
  return por;
}
const ejKeyItem = (it) => 'i:' + (it.grupo || it.id);
/* Lo facturado de cada gasto: el neto de cada factura asociada se reparte entre sus destinos según lo cotizado o
   presupuestado de cada uno (iguales si ninguno tiene monto). Los destinos que ya no existen no se cuentan. */
function ejFacturado(docs, asoc, items, lineas) {
  const peso = new Map();
  items.forEach(({ it }) => peso.set(ejKeyItem(it), Math.max(0, it.cantidad * it.precio)));
  lineas.forEach((l) => peso.set('l:' + l.uid, Math.max(0, l.subtotal)));
  const fact = new Map();      // destino → { monto, refs }
  (docs || []).forEach((d) => {
    const a = asoc.get(d.ref);
    const ds = a ? a.destinos.filter((x) => peso.has(x)) : [];
    if (!ds.length) return;
    const total = ds.reduce((s, x) => s + peso.get(x), 0);
    ds.forEach((x) => {
      const f = fact.get(x) || { monto: 0, refs: [] };
      f.monto += d.neto * (total > 0 ? peso.get(x) / total : 1 / ds.length);
      f.refs.push(d.ref);
      fact.set(x, f);
    });
  });
  return fact;
}
function ejModelo(t) {
  const form = ejFormulacion(t);
  const calc = ejCalculo(form);
  // Se simula un proveedor por ítem, aunque dos navegadores hayan elegido a la vez (en cada id manda el cambio más reciente)
  const costos = ejItems(ejDe(t, 'costo')).flatMap(({ xs, it }) => xs.map((x) => (x !== it && x.simular ? Object.assign({}, x, { simular: false }) : x)));
  const docs = ejDocumentosDe(t);
  const asoc = ejAsociaciones(t);
  const lineas = ejLineas(form, calc);
  const facturado = ejFacturado(docs, asoc, ejItems(costos), lineas);
  // Lo gastado de materiales, equipos y otros: sus facturas del Centro de Costos, si hay; si no, los reales del Análisis
  const gastoCC = docs && docs.length ? docs.reduce((a, d) => { const p = ejDocPorCat(d); Object.keys(p).forEach((k) => { a[k] += p[k]; }); return a; }, { Materiales: 0, Equipos: 0, Otros: 0 }) : null;
  const ocs = ejOCs(t, costos);
  const par = (form && form.datos.parametros) || {};
  // El presupuesto completo y sus versiones actualizadas (2026-11-13); la que se usa en «Cómo va el proyecto» cambia lo
  // presupuestado de cada categoría en lo que ella lo cambia, y su venta reemplaza a la calculada (no a la escrita aquí)
  const prVersiones = ejPrVersiones(t);
  const prBase = ejPrBase(calc, lineas);
  const prSeg = ejPrSeguimiento(prVersiones, prBase);
  let pres = ejPresupuesto(t, form, calc);
  if (pres && prSeg) pres = { por: Object.fromEntries(EJ_CATS.map((c) => [c.k, Math.max(0, pres.por[c.k] + prSeg.delta[c.k])])), fuente: pres.fuente + ' · con «' + prSeg.v.nombre + '»' };
  let venta = ejVenta(t, form, calc);
  if (prSeg && prSeg.v.venta && !(venta && venta.manual)) venta = { monto: prSeg.v.venta, fuente: 'Venta del presupuesto «' + prSeg.v.nombre + '»' };
  const reales = (t.af && t.af.reales) || {};
  const mo = ejManoObra(t, form, calc);
  // La mano de obra real: la de los días anotados aquí y, si no hay ninguno, la «Mano de Obra Real» del Análisis Financiero
  const moAF = reales['Mano de Obra'] === null || reales['Mano de Obra'] === undefined || !isFinite(Number(reales['Mano de Obra'])) ? null : Math.max(0, Number(reales['Mano de Obra']));
  mo.af = moAF;
  mo.fuente = mo.dias.length ? 'dias' : moAF !== null ? 'af' : '';
  const m = {
    t, form, calc, costos, ocs, folios: new Set(ocs.map((o) => o.folio)), pres, venta, lineas, mo, prVersiones, prBase, prSeg,
    docs, asoc, facturado, gastoFuente: gastoCC ? 'cc' : 'af',
    margenes: { objetivo: (Number(par.margenObjetivo) || EJ_MARGEN.objetivo) / 100, minimo: (Number(par.margenMinimo) || EJ_MARGEN.minimo) / 100 },
    metaDH: Number(par.metaUtilidadDH) > 0 ? Number(par.metaUtilidadDH) : 0,
    base: EJ_CATS.map((c) => ({ k: c.k, nombre: c.nombre, P: pres ? pres.por[c.k] : null,
      G: c.k === 'Mano de Obra' ? (mo.dias.length ? mo.costo : Math.max(0, Number(reales[c.k]) || 0)) : gastoCC ? gastoCC[c.k] : Math.max(0, Number(reales[c.k]) || 0),
      Coc: ocs.filter((o) => o.estado === 'comprometida' && o.cat === c.k).reduce((a, o) => a + o.neto, 0) }))
  };
  Object.assign(m, ejCuentas(m));
  m.avance = ejAvanceDe(t);
  return m;
}
/* Los indicadores de la obra, presupuestados (los de su formulación: js/calc.js) y estimados hoy, que se recalculan con
   cada gasto, cotización simulada y día trabajado. Los días-hombre al cierre son los presupuestados o, si ya se pasaron,
   los trabajados (como el costo: lo que falta se estima con el presupuesto); sin presupuesto, los trabajados divididos
   por el avance. */
function ejIndicadores(m) {
  const k = m.calc && m.calc.kpis ? m.calc.kpis : null;
  const V = m.venta ? m.venta.monto : null;
  const mo = m.mo;
  const av = m.avance.valor;
  const moCat = m.cats.find((c) => c.k === 'Mano de Obra');
  const dhCierre = mo.dhP ? Math.max(mo.dhP, mo.dh) : av !== null && av >= 0.1 && mo.dh > 0 ? mo.dh / av : null;
  const util = V !== null ? V - m.tot.EAC : null;
  const uDH = util !== null && dhCierre ? util / dhCierre : null;
  const costoDH = mo.dh > 0 ? mo.costo / mo.dh : null;
  const filas = [
    { id: 'dh', nombre: 'Días-hombre', fmt: ejCantidad, pres: mo.dhP, hoy: mo.dh || null,
      desc: 'Los trabajados (anotados aquí) frente a los presupuestados en la formulación.',
      nota: mo.dhP && mo.dh ? ejPct(mo.dh / mo.dhP) + ' de lo presupuestado' + (av !== null ? ', con ' + ejPct(av) + ' de avance' : '') : '',
      nivel: mo.dhP && av !== null && mo.dh / mo.dhP - av > EJ_GASTO_SOBRE_AVANCE ? 'warn' : '' },
    { id: 'costoDH', nombre: 'Costo por día-hombre', fmt: ejPesos, pres: k ? k.costoMODH : null, hoy: costoDH,
      desc: 'Lo que cuesta en promedio un día de trabajo: la mano de obra dividida por los días-hombre.',
      nivel: k && k.costoMODH && costoDH !== null && costoDH > k.costoMODH * 1.1 ? 'warn' : '' },
    { id: 'utilDH', nombre: 'Utilidad por día-hombre', fmt: ejPesos, pres: k ? k.rentDH : null, hoy: uDH,
      desc: 'Lo que deja cada día de trabajo: la venta menos el costo estimado al cierre, dividida por los días-hombre estimados al cierre.' + (m.metaDH ? ' Meta: ' + ejPesos(m.metaDH) + '.' : ''),
      nivel: uDH === null ? '' : uDH < 0 ? 'bad' : m.metaDH ? (uDH >= m.metaDH ? 'ok' : uDH >= m.metaDH * 0.8 ? 'warn' : 'bad') : k && k.rentDH > 0 ? (uDH >= k.rentDH * 0.9 ? 'ok' : 'warn') : '' },
    { id: 'ventaDH', nombre: 'Venta por día-hombre', fmt: ejPesos, pres: k ? k.ventaDH : null, hoy: V !== null && dhCierre ? V / dhCierre : null,
      desc: 'La venta dividida por los días-hombre estimados al cierre.', nivel: '' },
    { id: 'incMO', nombre: 'Incidencia de la mano de obra', fmt: ejPct, pres: k ? k.incidenciaMO : null, hoy: V ? moCat.EAC / V : null,
      desc: 'La mano de obra estimada al cierre como parte de la venta.', nivel: '' },
    { id: 'margen', nombre: 'Margen', fmt: ejPct, pres: m.margenP, hoy: m.margen,
      desc: 'La venta menos el costo estimado al cierre, como parte de la venta.', nivel: ejNivelMargen(m.margen, m) }
  ];
  return { filas, dhCierre };
}
/* El costo estimado al cierre: por categoría, lo gastado + comprometido + simulado o, si es menos, lo presupuestado. op:
   { quitar: Set de ids } no cuenta esas cotizaciones y { agregar: cotización } la cuenta como simulada: así se evalúa una
   sin tocarla. EAC0: sin nada simulado. */
function ejCuentas(m, op) {
  op = op || {};
  const cats = m.base.map((b) => Object.assign({}, b, { C: b.Coc, Q: 0 }));
  const por = new Map(cats.map((c) => [c.k, c]));
  m.costos.forEach((it) => {
    if (op.quitar && op.quitar.has(it.id)) return;
    const como = ejCuentaComo(it, m.folios);
    // Lo ya facturado de un ítem está en lo gastado: se simula o compromete solo lo que falta facturar (2026-11-06)
    const f = m.facturado ? m.facturado.get(ejKeyItem(it)) : null;
    const monto = Math.max(0, it.cantidad * it.precio - (f ? f.monto : 0));
    if (como === 'q') por.get(it.categoria).Q += monto;
    else if (como === 'c') por.get(it.categoria).C += monto;
  });
  if (op.agregar && por.has(op.agregar.categoria)) por.get(op.agregar.categoria).Q += op.agregar.cantidad * op.agregar.precio;
  const tot = { P: 0, G: 0, C: 0, Q: 0, EAC: 0, EAC0: 0 };
  cats.forEach((c) => {
    const usado = c.G + c.C + c.Q;
    c.usado = usado;
    c.EAC = c.P !== null ? Math.max(c.P, usado) : usado;
    c.EAC0 = c.P !== null ? Math.max(c.P, c.G + c.C) : c.G + c.C;
    c.queda = c.P !== null ? c.P - usado : null;
    ['P', 'G', 'C', 'Q', 'EAC', 'EAC0'].forEach((k) => { tot[k] += c[k] || 0; });
  });
  tot.usado = tot.G + tot.C + tot.Q;
  tot.queda = m.pres ? tot.P - tot.usado : null;
  const V = m.venta ? m.venta.monto : null;
  // Sin presupuesto ni nada anotado no hay margen que estimar (sería la venta entera); sin presupuesto, es «con lo anotado»
  const margen = (costo, base) => (V && (m.pres || base > 0) ? (V - costo) / V : null);
  return { cats, tot, margen: margen(tot.EAC, tot.usado), margen0: margen(tot.EAC0, tot.G + tot.C), margenP: m.pres ? margen(tot.P, 1) : null };
}
// El semáforo del margen, contra la meta y el mínimo de su formulación; sin presupuesto no lo lleva (le falta lo por venir)
const ejNivelMargen = (mg, m) => (mg === null || !m.pres ? '' : mg >= m.margenes.objetivo ? 'ok' : mg >= m.margenes.minimo ? 'warn' : 'bad');
/* La evaluación de una cotización (la guardada o la que se está escribiendo): cada comparación con su nivel, y la peor
   como veredicto. Que sea la más barata entre las de lo mismo informa, pero no la hace conveniente. dialogo: { otras, ids },
   lo escrito en el diálogo en vez de lo guardado. */
function ejEvaluar(it, m, dialogo) {
  const puntos = [];
  const total = it.cantidad * it.precio;
  const ls = ejLineasDe(it).map((u) => m.lineas.find((x) => x.uid === u)).filter(Boolean);
  const l = ls.length === 1 ? ls[0] : null;
  const subLineas = ls.reduce((a, x) => a + x.subtotal, 0);
  if (ls.length > 1 && subLineas > 0) {
    // Varias líneas: el total de la cotización contra lo que suman en el presupuesto
    const dif = total / subLineas - 1;
    puntos.push({ tipo: 'linea', nivel: dif <= EJ_TOLERANCIA.linea ? 'ok' : dif <= EJ_TOLERANCIA.lineaMala ? 'warn' : 'bad',
      texto: 'Presupuestado ' + ejPesos(subLineas) + ' en total en ' + ls.length + ' líneas (' + ls.map((x) => x.code).join(', ') + '): '
        + (Math.abs(dif) < 0.005 ? 'lo mismo.' : dif < 0 ? 'esta es ' + Math.round(-dif * 100) + ' % más barata.' : 'esta es ' + Math.round(dif * 100) + ' % más cara.') });
  }
  if (l) {
    const mismaUnidad = l.unitario > 0 && (!it.unidad || !l.unidad || norm(it.unidad) === norm(l.unidad));
    const dif = mismaUnidad ? it.precio / l.unitario - 1 : total / l.subtotal - 1;
    puntos.push({ tipo: 'linea', nivel: dif <= EJ_TOLERANCIA.linea ? 'ok' : dif <= EJ_TOLERANCIA.lineaMala ? 'warn' : 'bad',
      texto: 'Presupuestado ' + (mismaUnidad ? ejPesos(l.unitario) + ' c/u' : ejPesos(l.subtotal) + ' en total') + ' en ' + l.code + (l.partida ? ' (' + l.partida + ')' : '')
        + ' «' + l.descripcion + '»: ' + (Math.abs(dif) < 0.005 ? 'lo mismo.' : dif < 0 ? 'esta es ' + Math.round(-dif * 100) + ' % más barata.' : 'esta es ' + Math.round(dif * 100) + ' % más cara.') });
  }
  const h = ejReferencia(it);
  if (h && h.precio && h.precio.promedio > 0 && it.precio > 0) {
    const p = h.precio;
    const dif = it.precio / p.promedio - 1;
    const ultima = h.ultimaCompra ? ejFechaCorta(texto(h.ultimaCompra).slice(0, 10)) : '';
    puntos.push({ tipo: 'historico', nivel: it.precio > p.maximo ? 'bad' : dif > EJ_TOLERANCIA.historico ? 'warn' : 'ok',
      texto: 'QUEMPIN ha pagado «' + texto(h.nombre) + '» a ' + ejPesos(p.promedio) + ' en promedio, sin IVA y al valor de hoy (entre ' + ejPesos(p.minimo) + ' y ' + ejPesos(p.maximo)
        + ', ' + pl(Number(h.n) || 0, 'compra', 'compras') + (ultima ? '; la última, ' + ejPesos(p.ultimo) + ' el ' + ultima : '') + '): '
        + (it.precio > p.maximo ? 'esta cotización está sobre el máximo.' : Math.abs(dif) < 0.005 ? 'igual al promedio.' : dif < 0 ? Math.round(-dif * 100) + ' % bajo el promedio.' : Math.round(dif * 100) + ' % sobre el promedio.') });
  }
  const hermanas = ejHermanas(it, m.costos);
  const otras = (dialogo ? dialogo.otras : hermanas.filter((x) => x.estado !== 'descartada')).filter((x) => x.precio > 0);
  if (otras.length && total > 0) {
    const mejor = otras.reduce((a, x) => (x.cantidad * x.precio < a.cantidad * a.precio ? x : a));
    const tm = mejor.cantidad * mejor.precio;
    puntos.push(total <= tm
      ? { tipo: 'otras', nivel: 'ok', texto: 'La más conveniente de las ' + (otras.length + 1) + ' cotizaciones para esto.' }
      : { tipo: 'otras', nivel: 'warn', texto: Math.round((total / tm - 1) * 100) + ' % más cara que la de ' + (mejor.proveedor || 'otro proveedor') + ' (' + ejPesos(tm) + ').' });
  }
  // Se simula un proveedor a la vez: se evalúa como si este reemplazara a los otros del ítem
  const quitar = new Set([it.id].concat(hermanas.map((x) => x.id), dialogo ? dialogo.ids : []));
  const con = ejCuentas(m, { quitar, agregar: it });
  const sin = ejCuentas(m, { quitar });
  const c = con.cats.find((x) => x.k === it.categoria);
  const cat = EJ_CAT.get(it.categoria).nombre.toLowerCase();
  if (c && c.P !== null && total > 0) {
    const usado = sin.cats.find((x) => x.k === it.categoria).usado;
    puntos.push(c.queda >= -0.5
      ? { tipo: 'queda', nivel: 'ok', texto: 'Cabe en ' + cat + ': quedarían ' + ejPesos(c.queda) + ' de ' + ejPesos(c.P) + ' presupuestados.' }
      : { tipo: 'queda', nivel: 'bad', texto: 'Con esta compra, ' + cat + ' se pasa del presupuesto en ' + ejPesos(-c.queda) + ': ya van ' + ejPesos(usado) + ' de ' + ejPesos(c.P)
          + (l ? ', y su línea ' + l.code + ' estaba presupuestada en ' + ejPesos(l.subtotal)
            : ls.length > 1 ? ', y sus líneas ' + ls.map((x) => x.code).join(', ') + ' estaban presupuestadas en ' + ejPesos(subLineas) : '') + '.' });
  }
  if (con.margen !== null && total > 0) {
    const baja = sin.margen !== null ? sin.margen - con.margen : 0;
    const metas = ' (la meta es ' + ejPct(m.margenes.objetivo) + ' y el mínimo ' + ejPct(m.margenes.minimo) + ')';
    if (!m.pres) {
      // Sin presupuesto el margen sale solo de lo anotado: bajo el mínimo ya no conviene; sobre él, no se sabe
      puntos.push({ tipo: 'margen', nivel: con.margen < m.margenes.minimo ? 'bad' : 'ok',
        texto: 'Sin presupuesto, con lo anotado el margen queda en ' + ejPct(con.margen) + metas + ': falta lo que todavía no se anota.' });
    } else {
      puntos.push(baja <= 0.0005
        ? { tipo: 'margen', nivel: 'ok', texto: 'No cambia el margen estimado (' + ejPct(con.margen) + '): cabe en lo presupuestado.' }
        : { tipo: 'margen', nivel: ejNivelMargen(con.margen, m), texto: 'Con esta compra el margen estimado baja ' + ejPuntos(baja) + ', a ' + ejPct(con.margen) + metas + '.' });
    }
  }
  // Más barata que su línea del presupuesto: si igual no cabe, es por lo que ya se gastó en la categoría, no por esta
  // compra; se revisa, pero no es «No conviene»
  if (puntos.some((p) => p.tipo === 'linea' && p.nivel === 'ok')) {
    puntos.forEach((p) => { if ((p.tipo === 'queda' || p.tipo === 'margen') && p.nivel === 'bad') p.nivel = 'warn'; });
  }
  const peso = { ok: 1, warn: 2, bad: 3 };
  const cuentan = puntos.filter((p) => p.tipo !== 'otras' || p.nivel !== 'ok');
  const nivel = cuentan.length ? cuentan.reduce((a, p) => (peso[p.nivel] > peso[a] ? p.nivel : a), 'ok') : '';
  const corto = !puntos.length ? 'Sin referencias' : { ok: 'Conveniente', warn: 'Revisar', bad: 'No conviene' }[nivel] || 'Sin referencias';
  return { nivel, corto, puntos, total, con, sin, hoja: h, linea: ls[0] || null, lineas: ls };
}

// ---- El avance: el del Análisis Financiero, lo pedido que espera en el buzón y el de su Carta Gantt -------------------
// Lo pedido al Análisis Financiero que todavía espera en el buzón (de cualquier navegador o herramienta), por TAG
function ejPedidosAF(tag) {
  return ((rc.datos && rc.datos.datosProyecto) || []).filter((m) => m && m.proyecto && texto(m.proyecto.tag).toUpperCase() === tag && m.valores && typeof m.valores === 'object')
    .sort((a, b) => String(a.origen && a.origen.enviado).localeCompare(String(b.origen && b.origen.enviado)));
}
/* Lo que «reemplaza» un pedido nuevo: el valor que se vio en el Análisis o, si ya espera otro pedido de ese campo, el de
   ese pedido. El Análisis aplica los de un TAG en orden: así el nuevo vale después del anterior. */
function ejVisto(tag, campo, valorAF) {
  const previos = tag ? ejPedidosAF(tag).filter((m) => campo in m.valores) : [];
  return previos.length ? previos[previos.length - 1].valores[campo] : valorAF;
}
function ejAvanceDe(t) {
  const crudo = t.af ? t.af.avance : null;
  const af = crudo === null || crudo === undefined || crudo === '' || !isFinite(Number(crudo)) ? null : Math.max(0, Math.min(1, Number(crudo)));
  const pedidos = t.af && t.tag ? ejPedidosAF(t.tag).filter((m) => typeof m.valores['% Avance'] === 'number') : [];
  const pedido = pedidos[pedidos.length - 1] || null;
  // Lo que dijo el Análisis Financiero de ese pedido si lo dejó esperando (una celda que ya no tenía lo que se vio)
  const msj = pedido && rc.datos && rc.datos.afMensajes ? rc.datos.afMensajes[pedido.id] || null : null;
  const pedidosFin = t.af && t.tag ? ejPedidosAF(t.tag).filter((m) => 'Fecha de cierre' in m.valores) : [];
  const finPedido = pedidosFin.length ? pedidosFin[pedidosFin.length - 1].valores['Fecha de cierre'] : undefined;
  const fin = rcFecha(finPedido !== undefined ? finPedido : t.af ? t.af.cierre : null);
  return { af, pedido, msj, valor: pedido ? Math.max(0, Math.min(1, pedido.valores['% Avance'])) : af, fin, finPedido: finPedido !== undefined };
}
// La Carta Gantt del proyecto: la de su formulación o, si no, la de su N°
function ejGanttDe(t) {
  return (t.formulacion && ej.gantt.porUid.get(t.formulacion.uid)) || (t.req && ej.gantt.porReq.get(t.req)) || null;
}
/* Pide valores al Análisis Financiero con un «datos-proyecto» al buzón, como «Ingresar avance» y «Dar por cerrado»:
   cada valor se escribe solo si la celda todavía tiene lo que se vio («reemplaza»). Devuelve el nombre del archivo. */
async function ejEnviarAF(t, valores, reemplaza, motivo) {
  if (soloLectura()) throw new Error('Solo lectura: en este navegador no se cambian los datos.');
  const enviado = scAhora();
  const id = scId();
  const origen = { herramienta: 'portal', enviado };
  if (estado.usuario) origen.usuario = estado.usuario;
  const msg = { esquema: 'quempin.intercambio/1', id, tipo: 'datos-proyecto', destino: 'analisis-financiero', origen,
    proyecto: { tag: t.tag }, valores, reemplaza, informativo: { nombre: texto(t.af && t.af.nombre) || t.titulo, motivo } };
  const nombre = enviado.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_datos-proyecto_' + id + '.json';
  const buzon = await rc.dir.getDirectoryHandle('buzon', { create: true });
  const h = await buzon.getFileHandle(nombre, { create: true });
  const w = await h.createWritable();
  await w.write(JSON.stringify(msg, null, 2) + '\n');
  await w.close();
  // Las demás vistas del portal lo muestran desde ya: el Recorrido y la Planificación ven el avance pedido
  if (rc.datos) {
    rc.datos.datosProyecto = (rc.datos.datosProyecto || []).concat([msg]);
    rc.tarjetas = rcArmar(rc.datos, new Date());
  }
  return nombre;
}
// Retira del buzón un pedido que todavía no se aplica (lo busca por su id, como el Formulador: js/intercambio.js enBuzon)
async function ejRetirarAF(msg) {
  if (soloLectura()) throw new Error('Solo lectura: en este navegador no se cambian los datos.');
  const buzon = await rc.dir.getDirectoryHandle('buzon');
  let nombre = null;
  for await (const n of buzon.keys()) if (n.indexOf(msg.id) >= 0 && /\.json$/i.test(n)) { nombre = n; break; }
  if (!nombre) return false;
  await buzon.removeEntry(nombre);
  if (rc.datos) {
    rc.datos.datosProyecto = (rc.datos.datosProyecto || []).filter((m) => m.id !== msg.id);
    rc.tarjetas = rcArmar(rc.datos, new Date());
  }
  return true;
}

// ---- Leer y pintar ---------------------------------------------------------------------------------------------------
function ejAlMostrar() {
  if (!rc.leyendo && (!rc.leido || Date.now() - rc.leido > RC_RELEER_SEG * 1000)) rcCargar();   // al terminar llama a ejAlRecorrido
  else if (rc.dir) ejCargar();
  ejPintar();
  // Las reglas de cálculo del Formulador: con ellas, la comparación por línea del presupuesto
  if (!window.QCalc) ejLib('calc').then((x) => { if (x && !$('#vistaEjecucion').hidden) ejPintar(); });
}
// El Recorrido terminó de leer la carpeta: lo anotado por el equipo y las cartas Gantt
function ejAlRecorrido() {
  if (rc.dir) { ejCargar(true); return; }
  if (!$('#vistaEjecucion').hidden) ejPintar();
}
function ejCargar(todo) {
  if (ej.leyendo) return ej.leyendo;
  const dir = rc.dir;
  if (!dir) return Promise.resolve();
  ej.leyendo = (async () => {
    let cambio = await ejLeer(dir);
    if (todo || !ej.ganttLeido) { await ejLeerGantt(dir); cambio = true; }
    if (await ejLeerDocumentos(dir)) cambio = true;
    ej.error = null;
    return cambio;
  })().catch((e) => { console.error(e); ej.error = e; return true; }).then((cambio) => {
    ej.leyendo = null;
    if (ej.porGuardar && !ej.guardando && !ej.error) ejGuardar();    // lo que esperaba, ahora que se lee la carpeta
    if (cambio && !$('#vistaEjecucion').hidden) ejPintar(); else ejPintarFrescura();
    pintarInicioRecorrido();
  });
  return ej.leyendo;
}
// Con la vista abierta, los cambios del equipo: cada EJ_RELEER_SEG segundos, y solo se relee lo que cambió.
function ejVigilar() {
  if ($('#vistaEjecucion').hidden || document.visibilityState !== 'visible') return;
  ejPintarFrescura();
  if (!rc.dir || ej.leyendo || ej.guardando || document.querySelector('dialog[open]')) return;
  if (Date.now() - ej.datos.leida > EJ_RELEER_SEG * 1000) ejCargar();
}
function ejPintarVacio(por) {
  pintarSinCarpeta($('#ejVacio'), por, {
    navegador: 'Los proyectos en ejecución se arman con los datos de la carpeta del equipo, y este navegador no puede abrir carpetas del computador.',
    conectar: 'Esta vista lee los proyectos en ejecución y guarda las cotizaciones en la carpeta de intercambio. Conecta una vez la biblioteca «' + BIBLIOTECA_FORMULACION + '» en este navegador (la misma conexión del Formulador) y acepta «Ver archivos» y «Guardar cambios».'
  });
}
function ejPintarFrescura() {
  const txt = $('#ejFrescura'), punto = $('#ejPunto');
  $('#ejReintentar').hidden = !ej.errorGuardar;
  if (ej.errorGuardar) {
    txt.textContent = 'No se pudo guardar en la carpeta del equipo';
    txt.title = 'Lo cambiado espera en este navegador y se vuelve a intentar con el próximo cambio o con «Reintentar». ' + (ej.errorGuardar.message || '');
    punto.className = 'cx-punto bad';
    return;
  }
  if (ej.guardando || ej.porGuardar) { txt.textContent = 'Guardando en la carpeta del equipo…'; txt.title = ''; punto.className = 'cx-punto warn'; return; }
  if (!rc.leido) { txt.textContent = rc.leyendo ? 'Leyendo la carpeta del equipo…' : 'Sin datos de la carpeta del equipo'; txt.title = ''; punto.className = 'cx-punto'; return; }
  const l = rc.pulso;
  const aj = ej.ajeno && Date.now() - ej.ajeno.cuando < PL_AJENO_SEG * 1000 ? ej.ajeno : null;
  const linea = soloLectura() ? 'Resumen ' + mvHora() + ', solo para leer' : aj ? aj.quien + ' acaba de cambiar ' + pl(aj.n, 'cosa', 'cosas')
    : Date.now() - ej.guardado < 8000 ? 'Guardado · OneDrive lo lleva al equipo' : l && l.detenido ? 'El procesador está detenido' : 'Al día con la carpeta del equipo';
  if (txt.textContent !== linea) txt.textContent = linea;
  txt.title = 'Las cotizaciones, la venta corregida, las notas y los pendientes se guardan en la carpeta de intercambio (publicado › ejecucion), así todo el equipo ve lo mismo; esta vista revisa cada '
    + EJ_RELEER_SEG + ' segundos lo que cambian los demás. El avance llega al Análisis Financiero con la próxima vuelta del procesador.' + (l ? ' ' + l.texto : '');
  punto.className = 'cx-punto ' + (l && l.nivel !== 'ok' ? l.nivel : 'ok');
}
function ejPintar() {
  const hay = rc.leido > 0;
  $('#ejLeyendo').hidden = hay || !!rc.sinDatos;
  $('#ejVacio').hidden = hay || !rc.sinDatos;
  ejPintarFrescura();
  ejPintarPisado();
  presPintar();
  if (!hay) {
    $('#ejLista').hidden = true;
    $('#ejProyecto').hidden = true;
    if (rc.sinDatos) ejPintarVacio(rc.sinDatos);
    return;
  }
  // El elegido se sigue mostrando aunque haya salido de ejecución (lo recién dado por cerrado), mientras exista
  const t = ej.clave ? ejTodas().find((x) => x.clave === ej.clave) || null : null;
  $('#ejLista').hidden = !!t;
  $('#ejProyecto').hidden = !t;
  if (t) ejPintarProyecto(t); else ejPintarLista();
}
function ejElegir(clave) {
  if (clave !== ej.clave) { ej.sucios.clear(); ej.tarifasAbiertas = false; ej.todosDias = false; ej.todasNotas = false; }
  ej.clave = clave;
  ejGuardarPrefs();
  ejPintar();
  $('#vistaEjecucion').scrollTop = 0;
  const h = $('#ejProyecto h2');
  if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
}
function ejVolver() {
  const antes = ej.clave;
  ej.sucios.clear();
  ej.clave = null;
  ejGuardarPrefs();
  ejPintar();
  const b = antes && document.querySelector('#ejLista .ej-tarjeta[data-clave="' + CSS.escape(antes) + '"]');
  if (b) b.focus();
}
// Desde otra parte del portal (el Recorrido): esta vista con ese proyecto a la vista
function ejAbrirProyecto(clave) {
  if ((clave || null) !== ej.clave) ej.sucios.clear();
  ej.clave = clave || null;
  // Al volver a la lista, la pestaña donde está (2026-11-09)
  const t = ej.clave ? ejTodas().find((x) => x.clave === ej.clave) : null;
  if (t && (t.gestion || t.entregado)) ej.pestana = t.gestion ? 'ejecucion' : 'entregados';
  ejGuardarPrefs();
  abrir('ejecucion');
  $('#vistaEjecucion').scrollTop = 0;
}
// ---- La lista -------------------------------------------------------------------------------------------------------
// Lo tuyo primero; lo que ya terminó y sigue en Gestión de Proyectos, al final
const ejOrden = (a, b) => (rcMia(b) - rcMia(a)) || ((a.etapa !== 'ejecucion') - (b.etapa !== 'ejecucion')) || a.orden - b.orden || plComparar(a.titulo, b.titulo);
// La lista vacía: por qué
function ejNadaEn(entregados, sinFiltro) {
  if (ej.conDatos && sinFiltro) return 'Ningún proyecto de esta pestaña tiene datos anotados en su resumen. Quita «Solo con datos anotados» para ver los ' + sinFiltro + '.';
  if (entregados) return rc.datos && !rc.datos.hayEntregados
    ? 'Las carpetas de «0 Proyectos Entregados» llegan con la próxima vuelta del procesador.'
    : 'No hay carpetas de proyecto en «0 Proyectos Entregados» de Gestión de Proyectos.';
  return ejHayGestion() ? 'No hay carpetas de proyecto en la raíz de Gestión de Proyectos.'
    : 'No hay proyectos en ejecución: entran aquí cuando se adjudican y cuando su carpeta está en Gestión de Proyectos.';
}
// Cambiar de pestaña
function ejElegirPestana(id) {
  if (id === ej.pestana) return;
  ej.pestana = id;
  ej.salud = null;
  ej.espera = null;
  ejGuardarPrefs();
  ejPintarLista();
}
function ejPintarLista() {
  const u = estado.usuario;
  const mios = $('#ejMios');
  mios.checked = ej.mios && !!u;
  mios.disabled = !u;
  $('#ejMiosTxt').textContent = u ? 'Solo mis proyectos' : 'Solo mis proyectos (elige tu usuario)';
  const q = norm(ej.q).trim().split(/\s+/).filter(Boolean);
  const entregados = ej.pestana === 'entregados';
  // Solo con datos anotados: con algo guardado con su N° o su TAG
  const anotadas = ejConDatosSet();
  const conDatos = (t) => ejClaves(t).some((k) => anotadas.has(k));
  const listas = { ejecucion: ejTarjetas('ejecucion'), entregados: ejTarjetas('entregados') };
  document.querySelectorAll('#ejPestanas [data-pestana]').forEach((b) => {
    const id = b.dataset.pestana, n = listas[id].filter((t) => !ej.conDatos || conDatos(t)).length;
    b.setAttribute('aria-selected', String(id === ej.pestana));
    b.tabIndex = id === ej.pestana ? 0 : -1;
    b.querySelector('b').textContent = String(n);
    if (id === ej.pestana) $('#ejListaCuerpo').setAttribute('aria-labelledby', b.id);
  });
  $('#ejConDatos').checked = ej.conDatos;
  const todas = listas[ej.pestana].filter((t) => !ej.conDatos || conDatos(t));
  // Cada proyecto se calcula una vez por repintado: lo usan el mapa y las tarjetas
  const modelos = new Map(todas.map((t) => [t.clave, ejModelo(t)]));
  const saludes = new Map(todas.map((t) => [t.clave, ejSalud(t, modelos.get(t.clave))]));
  const buscadas = todas.filter((t) => (!ej.mios || !u || rcMia(t)) && q.every((x) => t.buscar.includes(x)));
  const esperas = new Map(todas.map((t) => [t.clave, ejEspera(t, modelos.get(t.clave))]));
  const alcance = buscadas.filter((t) => (!ej.salud || saludes.get(t.clave).nivel === ej.salud) && (!ej.espera || esperas.get(t.clave)[ej.espera] > 0));
  const plegada = (t) => !entregados && t.antiguo && !t.gestion;      // lo de Gestión y lo entregado nunca va plegado
  const vivas = alcance.filter((t) => !plegada(t)).sort(ejOrden);
  const viejas = alcance.filter(plegada).sort(ejOrden);
  // El mapa muestra lo buscado (sin el filtro de estado, que se elige en él mismo) y no lo plegado por antiguo
  const mapa = $('#ejMapa');
  const enMapa = buscadas.filter((t) => !plegada(t));
  mapa.hidden = !todas.length;
  mapa.textContent = '';
  if (todas.length) mapa.append(...ejMapaEl(enMapa, modelos, saludes));
  ejEsperaEl(enMapa, esperas);
  const caja = $('#ejTarjetas');
  caja.textContent = '';
  vivas.forEach((t) => caja.append(ejTarjetaEl(t, modelos.get(t.clave), saludes.get(t.clave))));
  if (!vivas.length) {
    caja.append(crear('p', 'ej-nada', !todas.length ? ejNadaEn(entregados, listas[ej.pestana].length)
      : alcance.length ? 'Los proyectos que calzan llevan más de 60 días sin moverse: están abajo.' : ej.salud ? 'Ningún proyecto «' + EJ_SALUD[ej.salud].nombre + '» calza con lo buscado.' : 'Ningún proyecto en ejecución calza con lo buscado.'));
  }
  $('#ejAntiguos').hidden = !viejas.length;
  $('#ejAntiguosTxt').textContent = pl(viejas.length, 'proyecto lleva', 'proyectos llevan') + ' más de 60 días sin moverse';
  const v = $('#ejTarjetasAntiguas');
  v.textContent = '';
  viejas.forEach((t) => v.append(ejTarjetaEl(t, modelos.get(t.clave), saludes.get(t.clave))));
  $('#ejCuenta').textContent = pl(vivas.length + viejas.length, 'proyecto', 'proyectos') + (alcance.length < todas.length ? ' de ' + todas.length : '');
}
/* ---- El estado de cada proyecto y el Mapa de salud (2026-11-09) ----------------------------------------------------
   Pedido del usuario: una herramienta que aporte al seguimiento del estado de cada proyecto y una pestaña mucho más
   visual. El estado junta lo que antes era solo la raya de color de la tarjeta: el margen contra la meta y el mínimo de
   su formulación, lo gastado y comprometido contra el avance (EJ_GASTO_SOBRE_AVANCE; el doble, en riesgo), si se pasa
   del presupuesto y los avisos del Recorrido. Sin presupuesto o sin avance no se puede ubicar en el mapa: «Sin datos». */
const EJ_SALUD = {
  bad: { nombre: 'En riesgo', icono: 'cruz' }, warn: { nombre: 'Atención', icono: 'exclama' },
  ok: { nombre: 'En línea', icono: 'visto' }, sin: { nombre: 'Sin datos', icono: 'guion' }
};
function ejSalud(t, m) {
  if (!ejClave(t)) return { nivel: 'sin', motivos: ['Su carpeta no lleva el N° de la Planilla de Ingreso'] };
  let nivel = 'ok';
  const motivos = [];
  const marcar = (n, txt) => { motivos.push(txt); if (n === 'bad' || nivel === 'ok') nivel = n; };
  const nm = ejNivelMargen(m.margen, m);
  if (nm === 'bad') marcar('bad', 'Margen estimado ' + ejPct(m.margen) + ': bajo el mínimo de ' + ejPct(m.margenes.minimo));
  else if (nm === 'warn') marcar('warn', 'Margen estimado ' + ejPct(m.margen) + ': bajo la meta de ' + ejPct(m.margenes.objetivo));
  const gs = ejGastoSobreAvance(m);
  if (gs) marcar(gs.gasto - gs.avance > 2 * EJ_GASTO_SOBRE_AVANCE ? 'bad' : 'warn', 'Lleva ' + ejPct(gs.gasto) + ' del presupuesto con ' + ejPct(gs.avance) + ' de avance');
  if (m.pres && m.tot.EAC > m.tot.P + 0.5) marcar('warn', 'Terminaría ' + ejPesos(m.tot.EAC - m.tot.P) + ' sobre el presupuesto');
  t.chips.filter((c) => c.nivel === 'warn' || c.nivel === 'bad').forEach((c) => marcar(c.nivel, c.texto));
  if (nivel === 'ok' && (!m.pres || m.avance.valor === null)) {
    return { nivel: 'sin', motivos: [!m.pres && m.avance.valor === null ? 'Sin presupuesto ni avance' : !m.pres ? 'Sin presupuesto' : 'Sin avance'] };
  }
  if (nivel === 'ok') motivos.push('Gasta de acuerdo con lo que avanza' + (m.margen !== null ? ' y el margen está en la meta' : ''));
  return { nivel, motivos };
}
// Lo que espera cada proyecto (lo mismo que su tarjeta y su «Por hacer»): compras por decidir, facturas sin asociar, pendientes
const EJ_ESPERA = [
  { id: 'decidir', ico: 'billetera', uno: 'compra por decidir', varios: 'compras por decidir' },
  { id: 'facturas', ico: 'documento', uno: 'factura sin asociar', varios: 'facturas sin asociar' },
  { id: 'pendientes', ico: 'portapapeles', uno: 'pendiente', varios: 'pendientes' }
];
function ejEspera(t, m) {
  if (!ejClave(t)) return { decidir: 0, facturas: 0, pendientes: 0 };
  return {
    decidir: ejItems(m.costos).filter((x) => x.it.estado === 'evaluar').length,
    facturas: (m.docs || []).filter((d) => !m.asoc.get(d.ref)).length,
    pendientes: ejDe(t, 'pendiente').filter((x) => !x.listo).length
  };
}
function ejPinEl(nivel, tam) {
  const p = crear('span', 'ej-pin');
  p.dataset.nivel = nivel;
  p.append(icono(EJ_SALUD[nivel].icono, tam || 12));
  return p;
}
// Dónde va cada proyecto: avance (0 a 1) y lo gastado y comprometido sobre el presupuesto. Sin uno de los dos, null.
const ejPosMapa = (m) => (m.pres && m.tot.P > 0 && m.avance.valor !== null ? { x: m.avance.valor, y: (m.tot.G + m.tot.C) / m.tot.P } : null);
function ejMapaEl(tarjetas, modelos, saludes) {
  const NS = 'http://www.w3.org/2000/svg';
  const sv = (tag, at, txt) => { const e = document.createElementNS(NS, tag); Object.entries(at || {}).forEach(([k, v]) => e.setAttribute(k, String(v))); if (txt !== undefined) e.textContent = txt; return e; };
  const cab = crear('div', 'ej-mapa-cab');
  const h = crear('h2', null, 'Mapa de salud');
  h.id = 'ejMapaTit';
  h.append(info('Cada punto es un proyecto: a la derecha, más avance; arriba, más gastado y comprometido en OC del presupuesto. Sobre la diagonal '
      + 'gasta más de lo que avanza: hasta ' + ejPct(EJ_GASTO_SOBRE_AVANCE) + ' de diferencia está bien (franja amarilla), más es «Atención» y el doble, «En riesgo». '
      + 'El estado también mira el margen estimado contra la meta y el mínimo de su formulación y los avisos del Recorrido. Los que no tienen presupuesto o avance no se pueden ubicar y quedan abajo, en «Sin datos».', 'Cómo leer el Mapa de salud'));
  cab.append(h, crear('small', null, 'Avance contra lo gastado del presupuesto · en naranjo, los tuyos · toca un punto para abrirlo'));
  // El gráfico: 0 a 100 % de avance; arriba, al menos 120 % del presupuesto (lo que se pasa cabe a la vista)
  const pos = tarjetas.map((t) => ({ t, m: modelos.get(t.clave), s: saludes.get(t.clave), p: ejPosMapa(modelos.get(t.clave)) }));
  const ubicados = pos.filter((x) => x.p);
  // Se dibuja al ancho que tiene (la letra queda de su tamaño): el de la lista menos la columna de los estados
  const ancho = (ejMapaAncho = $('#ejLista').clientWidth || 960) - 34;
  const W = Math.max(300, ancho > 720 ? ancho - 260 : ancho), H = ancho > 720 ? 250 : 220, L = 58, R = 22, T = 10, B = 38, P = 12;   // P: margen interior, un punto en 0 no tapa los ejes
  const yMax = Math.max(1.2, Math.ceil((Math.max(0, ...ubicados.map((x) => x.p.y)) + 0.1) * 5) / 5);
  const X = (v) => L + P + (W - L - R - P) * Math.max(0, Math.min(1, v));
  const Y = (v) => T + (H - T - B - P) * (1 - Math.max(0, Math.min(yMax, v)) / yMax);
  const svg = sv('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'group', 'aria-label': 'Mapa de salud: ' + pl(ubicados.length, 'proyecto ubicado', 'proyectos ubicados') + ' según su avance y lo gastado del presupuesto' });
  // Zonas: la de tolerancia (amarilla) y la de gastar más de lo que avanza (roja), sobre la diagonal
  const tol = EJ_GASTO_SOBRE_AVANCE;
  svg.append(sv('polygon', { class: 'zona-mala', points: [[0, tol], [1, 1 + tol], [1, yMax], [0, yMax]].map(([a, b]) => X(a) + ',' + Y(b)).join(' ') }));
  svg.append(sv('polygon', { class: 'zona-ojo', points: [[0, 0], [1, 1], [1, 1 + tol], [0, tol]].map(([a, b]) => X(a) + ',' + Y(b)).join(' ') }));
  for (let i = 0; i <= 4; i++) {
    const v = i / 4;
    svg.append(sv('line', { class: 'reja', x1: X(v), x2: X(v), y1: T, y2: H - B }), sv('text', { class: 'eje-txt', x: X(v), y: H - B + 15, 'text-anchor': 'middle' }, Math.round(v * 100) + ' %'));
  }
  for (let v = 0; v <= yMax + 1e-9; v += yMax > 1.6 ? 0.5 : 0.25) {
    svg.append(sv('line', { class: 'reja', x1: L, x2: W - R, y1: Y(v), y2: Y(v) }), sv('text', { class: 'eje-txt', x: L - 6, y: Y(v) + 4, 'text-anchor': 'end' }, Math.round(v * 100) + ' %'));
  }
  svg.append(sv('line', { class: 'eje', x1: L, x2: W - R, y1: H - B, y2: H - B }), sv('line', { class: 'eje', x1: L, x2: L, y1: T, y2: H - B }));
  svg.append(sv('line', { class: 'diagonal', x1: X(0), y1: Y(0), x2: X(1), y2: Y(1) }));
  svg.append(sv('text', { class: 'zona-txt', x: X(0.03), y: Y(Math.min(yMax, 1.08)), 'text-anchor': 'start' }, 'Gasta más de lo que avanza'));
  svg.append(sv('text', { class: 'zona-txt', x: X(0.97), y: Y(0.12), 'text-anchor': 'end' }, 'Avanza más de lo que gasta'));
  svg.append(sv('text', { class: 'eje-tit', x: (L + W - R) / 2, y: H - 3, 'text-anchor': 'middle' }, 'Avance →'));
  const yTit = sv('text', { class: 'eje-tit', x: 12, y: (T + H - B) / 2, 'text-anchor': 'middle', transform: 'rotate(-90 12 ' + (T + H - B) / 2 + ')' }, 'Gastado →');
  svg.append(yTit);
  const graf = crear('div', 'ej-mapa-graf');
  const tip = crear('div', 'ej-mapa-tip');
  tip.hidden = true;
  tip.setAttribute('role', 'status');
  const mostrar = (x, g) => {
    tip.textContent = '';
    tip.append(crear('b', null, (rcEtiqueta(x.t) ? rcEtiqueta(x.t) + ' · ' : '') + x.t.titulo),
      document.createTextNode(EJ_SALUD[x.s.nivel].nombre + ': ' + x.s.motivos.join(' · ')),
      crear('br'), document.createTextNode('Avance ' + ejPct(x.p.x) + ' · gastado y comprometido ' + ejPct(x.p.y) + ' del presupuesto'));
    const r = graf.getBoundingClientRect(), c = g.querySelector('.marca').getBoundingClientRect();
    tip.style.left = Math.min(r.width - 130, Math.max(130, c.left + c.width / 2 - r.left)) + 'px';
    tip.style.top = (c.top - r.top) + 'px';
    tip.hidden = false;
    const card = document.querySelector('#ejLista .ej-tarjeta[data-clave="' + CSS.escape(x.t.clave) + '"]');
    if (card) card.classList.add('resalta');
  };
  const ocultar = () => { tip.hidden = true; document.querySelectorAll('#ejLista .ej-tarjeta.resalta').forEach((c) => c.classList.remove('resalta')); };
  // Los en riesgo, encima de los demás
  const orden = { sin: 0, ok: 1, warn: 2, bad: 3 };
  const ocupadas = [];
  const lugarEtq = (cx, cy, largo) => {
    const op = [[cx + 12, cy + 4, 'start'], [cx - 12, cy + 4, 'end'], [cx, cy - 12, 'middle'], [cx, cy + 20, 'middle']];
    const caja = ([x, y, a]) => { const x0 = a === 'start' ? x : a === 'end' ? x - largo : x - largo / 2; return [x0, y - 11, x0 + largo, y + 2]; };
    const libre = (c) => c[0] >= L - 4 && c[2] <= W && ocupadas.every((o) => c[2] < o[0] || c[0] > o[2] || c[3] < o[1] || c[1] > o[3]);
    const elegida = op.find((o) => libre(caja(o))) || op[cx > W - 70 ? 1 : 0];
    ocupadas.push(caja(elegida));
    return elegida;
  };
  ubicados.forEach((x) => ocupadas.push([X(x.p.x) - 9, Y(x.p.y) - 9, X(x.p.x) + 9, Y(x.p.y) + 9]));
  ubicados.slice().sort((a, b) => orden[a.s.nivel] - orden[b.s.nivel]).forEach((x) => {
    const cx = X(x.p.x), cy = Y(x.p.y);
    const g = sv('g', { class: 'punto' + (rcMia(x.t) ? ' tuya' : ''), tabindex: 0, role: 'button', 'data-clave': x.t.clave, 'data-nivel': x.s.nivel,
      'aria-label': (rcEtiqueta(x.t) || '') + ' ' + x.t.titulo + ': ' + EJ_SALUD[x.s.nivel].nombre + ', avance ' + ejPct(x.p.x) + ', gastado ' + ejPct(x.p.y) + ' del presupuesto' });
    g.append(sv('circle', { class: 'area', cx, cy, r: 16 }), sv('circle', { class: 'marca', cx, cy, r: 7.5 }));
    const etq = x.t.req ? x.t.req : x.t.tag || '';
    if (etq) {
      ocupadas.splice(ocupadas.findIndex((o) => o[0] === cx - 9 && o[1] === cy - 9), 1);   // su propio punto no le estorba
      const [ex, ey, ea] = lugarEtq(cx, cy, String(etq).length * 7.5 + 2);
      ocupadas.push([cx - 9, cy - 9, cx + 9, cy + 9]);
      g.append(sv('text', { class: 'etq', x: ex, y: ey, 'text-anchor': ea }, etq));
    }
    g.addEventListener('pointerenter', () => mostrar(x, g));
    g.addEventListener('pointerleave', ocultar);
    g.addEventListener('focus', () => mostrar(x, g));
    g.addEventListener('blur', ocultar);
    g.addEventListener('click', () => { ocultar(); ejElegir(x.t.clave); });
    g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ocultar(); ejElegir(x.t.clave); } });
    svg.append(g);
  });
  graf.append(svg, tip);
  // Al lado: cuántos hay en cada estado, que además filtran las tarjetas
  const lado = crear('div', 'ej-mapa-lado');
  lado.setAttribute('role', 'group');
  lado.setAttribute('aria-label', 'Filtrar por estado');
  ['bad', 'warn', 'ok', 'sin'].forEach((n) => {
    const cuenta = pos.filter((x) => x.s.nivel === n).length;
    const b = crear('button', 'ej-estado-fil');
    b.type = 'button';
    b.dataset.nivel = n;
    b.dataset.cuenta = String(cuenta);
    b.setAttribute('aria-pressed', String(ej.salud === n));
    b.append(ejPinEl(n), crear('span', null, EJ_SALUD[n].nombre), crear('b', null, String(cuenta)));
    b.title = ej.salud === n ? 'Mostrar todos los proyectos' : 'Mostrar solo los proyectos «' + EJ_SALUD[n].nombre + '»';
    b.addEventListener('click', () => { ej.salud = ej.salud === n ? null : n; ejPintarLista(); const x = $('#ejMapa .ej-estado-fil[data-nivel="' + n + '"]'); if (x) x.focus(); });
    lado.append(b);
  });
  const sin = pos.filter((x) => !x.p);
  if (sin.length) {
    const p = crear('p', 'ej-mapa-nota');
    p.append(document.createTextNode('Fuera del mapa, sin presupuesto o avance: '));
    sin.forEach((x, i) => {
      const b = crear('button', null, rcEtiqueta(x.t) || x.t.titulo);
      b.type = 'button';
      b.title = x.t.titulo + ': ' + x.s.motivos.join(' · ');
      b.addEventListener('click', () => ejElegir(x.t.clave));
      p.append(b, document.createTextNode(i < sin.length - 1 ? ', ' : '.'));
    });
    lado.append(p);
  }
  return [cab, graf, lado];
}
// Al cambiar el ancho de la ventana, el mapa se vuelve a dibujar a su medida
let ejMapaAncho = 0, ejRelojMapa = 0;
window.addEventListener('resize', () => {
  clearTimeout(ejRelojMapa);
  ejRelojMapa = setTimeout(() => {
    if (!$('#vistaEjecucion').hidden && !$('#ejLista').hidden && Math.abs($('#ejLista').clientWidth - ejMapaAncho) > 30) ejPintarLista();
  }, 200);
});
/* Lo que espera el equipo (2026-11-09, vuelta 11 del loop de UX): sobre las tarjetas, cuántas compras hay por decidir,
   facturas sin asociar y pendientes en todos los proyectos a la vista, y en cuántos; tocar uno deja solo esos proyectos. */
function ejEsperaEl(tarjetas, esperas) {
  const caja = $('#ejEspera');
  caja.textContent = '';
  const filas = EJ_ESPERA.map((e) => {
    const con = tarjetas.filter((t) => esperas.get(t.clave)[e.id] > 0);
    return { e, n: con.reduce((a, t) => a + esperas.get(t.clave)[e.id], 0), proyectos: con.length };
  });
  if (ej.espera && !filas.some((f) => f.e.id === ej.espera && f.n)) ej.espera = null;
  const hay = filas.filter((f) => f.n);
  caja.hidden = !hay.length;
  if (!hay.length) return;
  caja.append(crear('span', 'ej-espera-tit', 'Espera al equipo'));
  hay.forEach(({ e, n, proyectos }) => {
    const b = crear('button', 'ej-espera-op');
    b.type = 'button';
    b.dataset.espera = e.id;
    b.setAttribute('aria-pressed', String(ej.espera === e.id));
    b.append(icono(e.ico, 15), crear('b', null, String(n)), crear('span', null, (n === 1 ? e.uno : e.varios) + ' en ' + pl(proyectos, 'proyecto', 'proyectos')));
    b.title = ej.espera === e.id ? 'Mostrar todos los proyectos' : 'Mostrar solo los proyectos con ' + e.varios;
    b.addEventListener('click', () => { ej.espera = ej.espera === e.id ? null : e.id; ejPintarLista(); const x = $('#ejEspera [data-espera="' + e.id + '"]'); if (x) x.focus(); });
    caja.append(b);
  });
}
function ejTarjetaEl(t, m, salud) {
  m = m || ejModelo(t);
  salud = salud || ejSalud(t, m);
  const b = crear('button', 'ej-tarjeta' + (rcMia(t) ? ' tuya' : ''));
  b.type = 'button';
  b.dataset.clave = t.clave;
  b.dataset.salud = salud.nivel;
  const cab = crear('span', 'ej-t-cab');
  if (rcEtiqueta(t)) cab.append(crear('span', 'ej-n', rcEtiqueta(t)));
  cab.append(crear('span', 'ej-t-tit', t.titulo));
  b.append(cab);
  /* La tarjeta más visual (2026-11-09, vuelta 2 del loop de UX): el avance en un anillo, el presupuesto en una barra con
     la raya del avance (si lo gastado pasa la raya, gasta más de lo que avanza) y abajo lo que falta hacer, con números. */
  // Bajo el título: dónde y su TAG; a la derecha, su estado (con palabra) y quién lo lleva
  const meta = crear('span', 'ej-t-meta');
  meta.append(crear('span', 'ej-t-sub', [rcLegible(t.lugar), t.req && t.tag ? 'TAG ' + t.tag : ''].filter(Boolean).join(' · ')));
  const est = crear('span', 'ej-salud');
  est.append(ejPinEl(salud.nivel), document.createTextNode(EJ_SALUD[salud.nivel].nombre));
  est.title = salud.motivos.join(' · ');
  meta.append(est);
  if (t.responsable) { const r = crear('span', 'ej-resp', t.responsable); r.title = (rcMia(t) ? 'Tuyo' : 'A cargo de ' + t.responsable) + ' (' + t.respDe + ')'; meta.append(r); }
  b.append(meta);
  const cuerpo = crear('span', 'ej-t-cuerpo');
  const av = m.avance;
  cuerpo.append(ejAnilloEl(av.valor, av.pedido ? 'pedido' : ''));
  const datos = crear('span', 'ej-t-datos');
  if (!ejClave(t)) datos.append(crear('span', 'ej-t-fila', 'Su carpeta no lleva el N° de la Planilla de Ingreso'));
  else {
    // El presupuesto: gastado y comprometido contra lo presupuestado, con la raya del avance
    const fp = crear('span', 'ej-t-pres');
    const leer = crear('span', 'ej-t-pres-txt');
    if (m.pres && m.tot.P > 0) {
      const med = crear('span', 'ej-t-barra');
      [['', m.tot.G], ['c', m.tot.C]].forEach(([k, v]) => {
        if (!(v > 0)) return;
        const x = crear('span', 'ej-seg' + (k ? ' ' + k : ''));
        x.style.width = Math.min(100, 100 * v / m.tot.P) + '%';
        med.append(x);
      });
      if (av.valor !== null) { const r = crear('i', 'ej-raya-avance'); r.style.left = Math.round(av.valor * 100) + '%'; med.append(r); }
      leer.append(crear('span', null, 'Gastado '), crear('b', null, ejPesos(m.tot.G)), crear('span', null, ' de ' + ejPesos(m.tot.P)));
      fp.append(leer, med);
      fp.title = ejPct(m.tot.G / m.tot.P) + ' del presupuesto gastado' + (m.tot.C > 0.5 ? ', ' + ejPesos(m.tot.C) + ' comprometidos en OC' : '')
        + (av.valor !== null ? '; la raya naranja es el avance (' + ejPct(av.valor) + ')' : '');
    } else if (m.tot.G > 0.5) {
      leer.append(crear('span', null, 'Gastado '), crear('b', null, ejPesos(m.tot.G)), crear('span', null, ' · sin presupuesto'));
      fp.append(leer);
    } else fp.append(crear('span', 'ej-t-pres-txt', 'Sin presupuesto ni gastos registrados'));
    datos.append(fp);
    const nivel = ejNivelMargen(m.margen, m);
    if (m.margen !== null) {
      const s = crear('span', 'ej-semaforo' + (nivel ? '' : ' sin'), (m.pres ? 'Margen estimado ' : 'Margen con lo anotado ') + ejPct(m.margen));
      if (nivel) s.dataset.nivel = nivel;
      if (!m.pres) s.title = 'Sin presupuesto: solo con lo gastado, comprometido y proyectado que está anotado';
      datos.append(s);
    } else if (!m.venta) datos.append(crear('span', 'ej-t-fila', 'Sin venta'));
  }
  cuerpo.append(datos);
  b.append(cuerpo);
  // Lo que falta hacer en el proyecto: cada cosa con su número (lo mismo que dice su resumen)
  if (ejClave(t)) {
    const es = ejEspera(t, m);
    const tareas = EJ_ESPERA.map((e) => [es[e.id], e.ico, pl(es[e.id], e.uno, e.varios)]).filter(([n]) => n > 0);
    if (tareas.length) {
      const ul = crear('span', 'ej-t-tareas');
      tareas.forEach(([, ico, txt]) => { const x = crear('span', 'ej-t-tarea'); x.append(icono(ico, 14), crear('span', null, txt)); ul.append(x); });
      b.append(ul);
    }
  }
  if (t.chips.length) {
    const ch = crear('span', 'rc-chips');
    t.chips.slice(0, 3).forEach((c) => { const x = crear('span', 'rc-chip', c.texto); if (c.nivel) x.dataset.nivel = c.nivel; ch.append(x); });
    b.append(ch);
  }
  b.dataset.nivel = salud.nivel === 'bad' || salud.nivel === 'warn' ? salud.nivel : '';
  b.addEventListener('click', () => ejElegir(t.clave));
  return b;
}
// El avance en un anillo (2026-11-09): el número adentro; sin dato, el anillo vacío con un guion
function ejAnilloEl(valor, extra) {
  const NS = 'http://www.w3.org/2000/svg';
  const caja = crear('span', 'ej-anillo' + (extra ? ' ' + extra : ''));
  caja.setAttribute('role', 'img');
  caja.setAttribute('aria-label', valor === null ? 'Avance sin dato' : 'Avance ' + ejPct(valor) + (extra === 'pedido' ? ', pedido al Análisis Financiero' : ''));
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 44 44');
  svg.setAttribute('aria-hidden', 'true');
  const c = (cl, d) => {
    const e = document.createElementNS(NS, 'circle');
    e.setAttribute('class', cl); e.setAttribute('cx', '22'); e.setAttribute('cy', '22'); e.setAttribute('r', '18');
    if (d !== undefined) { e.setAttribute('pathLength', '100'); e.setAttribute('stroke-dasharray', d + ' 100'); }
    return e;
  };
  svg.append(c('pista'));
  if (valor > 0) svg.append(c('arco', Math.min(100, Math.round(valor * 100))));
  caja.append(svg, crear('b', null, valor === null ? '—' : ejPct(valor)), crear('small', null, 'avance'));
  if (extra === 'pedido') caja.title = 'Pedido al Análisis Financiero: llega con la próxima vuelta del procesador';
  return caja;
}
// Lo gastado y comprometido frente al avance: con 40 % de avance y 60 % del presupuesto gastado, se avisa
function ejGastoSobreAvance(m) {
  const av = m.avance.valor;
  if (!m.pres || !(m.tot.P > 0) || av === null) return null;
  const gasto = (m.tot.G + m.tot.C) / m.tot.P;
  return gasto - av > EJ_GASTO_SOBRE_AVANCE ? { gasto, avance: av } : null;
}

// ---- El resumen de un proyecto ------------------------------------------------------------------------------------
// ayuda (2026-11-05): lo que antes era el párrafo de explicación del panel, en un ⓘ junto a su título
function ejPanel(titulo, extra, ayuda) {
  const s = crear('section', 'ej-panel');
  const cab = crear('div', 'ej-panel-cab');
  const h = crear('h3', null, titulo);
  if (extra) h.append(crear('small', null, extra));
  if (ayuda) h.append(info(ayuda, 'Cómo funciona: ' + titulo.toLowerCase()));
  cab.append(h);
  s.append(cab);
  return { s, cab };
}
function ejBoton(txt, clase, ir, ico) {
  const b = crear('button', clase || 'cx-enlace');
  b.type = 'button';
  if (ico) b.append(icono(ico, 16));
  b.append(crear('span', null, txt));
  b.addEventListener('click', ir);
  return b;
}
function ejPintarProyecto(t) {
  const raiz = $('#ejProyecto');
  const vista = $('#vistaEjecucion');
  const desplazado = vista.scrollTop;
  // El foco sigue donde estaba después de repintar (una casilla de «Simular», un botón)
  const a = document.activeElement;
  const foco = a && raiz.contains(a) && a.dataset ? a.dataset.foco : null;
  const m = ejModelo(t);
  ej.modelo = m;
  if (!ej.diasForm || ej.diasForm.clave !== t.clave) ej.diasForm = { clave: t.clave, mes: plISO(new Date()).slice(0, 7), jornada: 1, personas: new Set(), nombres: {}, dias: new Set(), abierto: null };
  raiz.textContent = '';
  // Una carpeta de Gestión sin N° ni TAG (2026-11-03): se ve, pero no hay a qué anotarle compras, días ni avance
  const sinClave = !ejClave(t);
  raiz.classList.add('ej-v2');
  raiz.classList.toggle('ej-plegado', ej.idxPlegado);
  ejPintarV2(t, m, raiz, sinClave);
  ejRestaurar(raiz, vista, desplazado, foco, t, m);
}
// Después de pintar (las dos vistas): lo escrito, el desplazamiento, el foco y los precios de referencia
function ejRestaurar(raiz, vista, desplazado, foco, t, m) {
  // Lo que se estaba escribiendo (una nota, un pendiente, el avance) sigue escrito después de repintar
  ej.sucios.forEach((v, id) => { const x = raiz.querySelector('#' + CSS.escape(id)); if (x && x.value !== v) x.value = v; });
  vista.scrollTop = desplazado;
  if (foco) { const x = raiz.querySelector('[data-foco="' + CSS.escape(foco) + '"]'); if (x) x.focus({ preventScroll: true }); }
  // Los precios de referencia se leen cuando hay materiales o equipos que comparar; las líneas del presupuesto, con las
  // reglas del Formulador
  if (!ej.precios && m.costos.some((x) => EJ_CAT.get(x.categoria).historico)) {
    ejPrecios().then((d) => { if (d && !vista.hidden && ej.clave === t.clave && !document.querySelector('dialog[open]')) ejPintar(); });
  }
}
/* La página nueva del proyecto (2026-11-12, pedido del usuario: «dale mayor relevancia al espacio general y no tanta a
   la barra de navegación lateral»; «la sección de cosas por hacer no es tan importante»). Las mismas partes de siempre,
   ordenadas así: a la izquierda un índice angosto que se pliega a íconos (los accesos de ejSaltosEl); arriba «Todos los
   proyectos» y «Por hacer» como un botón chico que despliega la lista; la cabecera sin tarjeta; un resumen grande (el
   anillo del avance, una sola barra con lo gastado, comprometido, simulado y lo que falta según el presupuesto, con la
   raya del avance, y el margen en un medidor con el mínimo y la meta) y debajo las partes. «Todos los proyectos» va
   primero en el índice (2026-11-12, pedido del usuario); la página anterior se eliminó (queda la etiqueta de git
   portal-ejecucion-proyecto-v1). */
function ejPintarV2(t, m, raiz, sinClave) {
  const cuerpo = crear('div', 'ej-v2-cuerpo');
  const arriba = crear('div', 'ej-v2-arriba');
  const idx = crear('section', 'ej-v2-idx');
  idx.setAttribute('aria-label', 'Índice del proyecto');
  const volver = ejBoton('Todos los proyectos', 'ej-volver', ejVolver, 'izquierda');
  volver.title = 'Volver a la lista de todos los proyectos';
  idx.append(volver);
  cuerpo.append(arriba, ejCabEl(m));
  if (t.avisos.length) {
    const ul = crear('ul', 'rc-avisos');
    t.avisos.forEach((x) => { const li = crear('li'); li.append(icono('alerta', 16), crear('span', null, x)); ul.append(li); });
    cuerpo.append(ul);
  }
  if (sinClave) {
    cuerpo.append(ejSinClaveEl(t));
    raiz.append(idx, cuerpo);
    return;
  }
  arriba.append(ejPorHacerEl(m));
  const plegar = crear('button', 'ej-idx-plegar');
  plegar.type = 'button';
  plegar.append(icono(ej.idxPlegado ? 'derecha' : 'izquierda', 14), crear('span', null, ej.idxPlegado ? 'Mostrar' : 'Plegar'));
  plegar.title = ej.idxPlegado ? 'Mostrar los nombres del índice' : 'Dejar el índice solo con íconos';
  plegar.setAttribute('aria-expanded', String(!ej.idxPlegado));
  plegar.addEventListener('click', () => { ej.idxPlegado = !ej.idxPlegado; ejGuardarPrefs(); ejPintar(); });
  idx.append(plegar, ejSaltosEl(m, true));
  cuerpo.append(ejResumenEl(m));
  const dos = crear('div', 'ej-dos');
  dos.append(ejPresupuestoEl(m), ejAvanceEl(m));
  const mo = crear('div', 'ej-dos');
  mo.append(ejManoObraEl(m), ejIndicadoresEl(m));
  cuerpo.append(dos, ejDocumentosEl(m), ejComprasEl(m), mo);
  const tres = crear('div', 'ej-tres');
  tres.append(ejOCsEl(m), ejEquipoEl(m), ejNotasEl(m));
  tres.id = 'ejSecMas';
  cuerpo.append(tres);
  raiz.append(idx, cuerpo);
}
// El resumen grande de arriba: avance, dinero y margen; debajo, la venta, el cierre, lo comprometido y la mano de obra
function ejResumenEl(m) {
  const s = crear('section', 'ej-panel ej-v2-resumen');
  s.id = 'ejSecResumen';
  s.setAttribute('aria-label', 'Resumen del proyecto');
  const tot = m.tot, av = m.avance;
  const hero = crear('div', 'ej-v2-hero');
  // El avance
  const c1 = crear('div', 'ej-v2-av');
  c1.append(ejAnilloEl(av.valor, av.pedido ? 'pedido' : ''),
    crear('span', 'ej-v2-av-sub', av.pedido ? 'Pedido: llega con la próxima vuelta del procesador' : av.fin ? 'Término ' + rcCorta(av.fin, new Date()) : 'Sin fecha de término'));
  if (rc.dir && m.t.af && m.t.tag) c1.append(ejBoton('Registrar avance', 'cx-enlace', () => ejIrA('ejSecAvance')));
  // El dinero en una barra
  const c2 = crear('div', 'ej-v2-dinero');
  const cab = crear('div', 'ej-v2-dinero-cab');
  const g = crear('div');
  g.append(crear('span', 'ej-v2-et', 'Gastado a la fecha'), crear('b', 'ej-v2-grande', ejPesos(tot.G)));
  const p = crear('div', 'ej-v2-der');
  p.append(crear('span', 'ej-v2-et', 'Presupuesto'), crear('b', 'ej-v2-medio', m.pres && tot.P > 0 ? ejPesos(tot.P) : 'Sin presupuesto'));
  cab.append(g, p);
  c2.append(cab);
  if (m.pres && tot.P > 0) {
    const esc = Math.max(tot.P, tot.EAC);
    const resto = Math.max(0, tot.EAC - tot.G - tot.C - tot.Q);
    const segs = [['g', tot.G, 'Gastado'], ['c', tot.C, 'Comprometido en OC'], ['q', tot.Q, 'Simulado'], ['r', resto, 'Por gastar según el presupuesto']];
    const bar = crear('div', 'ej-v2-barra');
    bar.setAttribute('role', 'img');
    bar.setAttribute('aria-label', segs.filter(([, v]) => v > 0.5).map(([, v, n]) => n + ' ' + ejPesos(v)).join(', ') + '; presupuesto ' + ejPesos(tot.P)
      + (av.valor !== null ? '; avance ' + ejPct(av.valor) : ''));
    segs.forEach(([k, v, n]) => {
      if (!(v > 0.5)) return;
      const x = crear('span', 'ej-v2-seg ' + k);
      x.style.width = (100 * v / esc) + '%';
      x.title = n + ' ' + ejPesos(v);
      bar.append(x);
    });
    if (tot.EAC > tot.P + 0.5) { const x = crear('i', 'ej-v2-tope'); x.style.left = (100 * tot.P / esc) + '%'; x.title = 'Presupuesto ' + ejPesos(tot.P); bar.append(x); }
    if (av.valor !== null) {
      const pos = 100 * Math.min(1, av.valor) * tot.P / esc;
      const r = crear('i', 'ej-v2-raya' + (pos > 75 ? ' izq' : ''));
      r.style.left = pos + '%';
      r.append(crear('span', null, 'Avance ' + ejPct(av.valor)));
      bar.append(r);
    }
    c2.append(bar);
    const ley = crear('div', 'ej-v2-ley');
    segs.forEach(([k, v, n]) => {
      if (!(v > 0.5) && k !== 'g') return;
      const x = crear('span');
      x.append(crear('i', 'ej-v2-seg ' + k), document.createTextNode(n + ' '), crear('b', null, ejPesos(v)));
      if (k === 'g') x.append(document.createTextNode(' (' + ejPct(tot.G / tot.P) + ')'));
      ley.append(x);
    });
    c2.append(ley);
    if (av.valor !== null) {
      const gs = ejGastoSobreAvance(m);
      const msg = crear('p', 'ej-v2-msg', gs ? 'Gasta más de lo que avanza: lleva ' + ejPct(gs.gasto) + ' del presupuesto con ' + ejPct(gs.avance) + ' de avance'
        : 'Gasta de acuerdo con lo que avanza');
      msg.dataset.nivel = gs ? 'warn' : 'ok';
      msg.prepend(icono(gs ? 'exclama' : 'visto', 14));
      c2.append(msg);
    }
  } else c2.append(crear('p', 'ej-v2-nota', tot.G > 0.5 ? 'Sin presupuesto con que compararlo: lo gastado sale de las facturas y la mano de obra anotada.' : 'Sin presupuesto ni gastos registrados.'));
  // El margen
  const c3 = crear('div', 'ej-v2-margen');
  c3.append(crear('span', 'ej-v2-et', m.pres ? 'Margen estimado' : 'Margen con lo anotado'), ejMedidorMargenEl(m));
  hero.append(c1, c2, c3);
  // Las cifras de abajo: las KPI de siempre (la venta con «Corregir», el cierre) y lo comprometido y la mano de obra
  const kpis = ejKpisEl(m);
  const stat = (et, v, sub) => { const k = crear('div', 'ej-stat'); k.append(crear('span', 'ej-kpi-et', et), crear('span', 'ej-kpi-v', v), crear('span', 'ej-kpi-sub', sub)); return k; };
  kpis.append(stat('Comprometido en OC', ejPesos(tot.C), tot.C > 0.5 ? 'Órdenes de compra aún sin factura' : 'Sin OC pendientes de factura'),
    stat('Mano de obra real', ejPesos(m.mo.costo || 0), m.mo.dh ? ejCantidad(m.mo.dh) + ' días-hombre anotados' : 'Sin días anotados'));
  s.append(hero, kpis);
  return s;
}
// El margen en un medidor de media vuelta, con las marcas del mínimo y la meta
function ejMedidorMargenEl(m) {
  const mg = m.margen, min = m.margenes.minimo, meta = m.margenes.objetivo;
  const tope = Math.max(0.4, (meta || 0) + 0.15, (mg || 0) + 0.05);
  const ang = (v) => Math.PI * (1 - Math.min(Math.max(v, 0), tope) / tope);
  const pt = (v, r) => [(110 + r * Math.cos(ang(v))).toFixed(1), (112 - r * Math.sin(ang(v))).toFixed(1)];
  const nivel = ejNivelMargen(mg, m);
  const caja = crear('div', 'ej-v2-medidor');
  if (nivel) caja.dataset.nivel = nivel;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 -16 220 140');
  svg.setAttribute('aria-hidden', 'true');
  const el = (tag, at, txt) => {
    const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(at).forEach(([k, v]) => e.setAttribute(k, v));
    if (txt) e.textContent = txt;
    svg.append(e);
  };
  el('path', { class: 'pista', d: 'M22 112 A88 88 0 0 1 198 112' });
  if (mg !== null && mg > 0) { const [x, y] = pt(mg, 88); el('path', { class: 'arco', d: 'M22 112 A88 88 0 0 1 ' + x + ' ' + y }); }
  [[min, 'mín'], [meta, 'meta']].forEach(([v, et]) => {
    if (v === null || v === undefined) return;
    const [a, b] = pt(v, 74), [c, d] = pt(v, 102), [tx, ty] = pt(v, 116);
    el('line', { class: 'marca', x1: a, y1: b, x2: c, y2: d });
    el('text', { class: 'marca-t', x: tx, y: ty, 'text-anchor': 'middle' }, et);
  });
  caja.setAttribute('role', 'img');
  caja.setAttribute('aria-label', mg === null ? 'Margen sin calcular' : 'Margen ' + ejPct(mg) + ', mínimo ' + ejPct(min) + ', meta ' + ejPct(meta));
  caja.append(svg, crear('b', null, mg === null ? '—' : ejPct(mg)),
    crear('small', null, mg === null ? (!m.venta ? 'Falta la venta para calcularlo' : 'Sin presupuesto ni gastos anotados') : 'Mínimo ' + ejPct(min) + ' · meta ' + ejPct(meta)));
  return caja;
}
/* Por hacer (2026-11-09, vuelta 3 del loop de UX): lo que el proyecto está esperando de alguien, primero y con su botón,
   que lo hace ahí mismo o lleva a la parte donde se hace. Sigue el camino de la información: las facturas del Centro de
   Costos se asocian a sus gastos, las compras se deciden, los días de la Planificación se traen y lo anotado se lleva al
   Análisis Financiero, que lo reparte al Recorrido, la Planificación y el Formulador. Sin nada pendiente, «Todo al día». */
function ejIrA(id, despues) {
  const x = document.getElementById(id);
  if (!x) return;
  x.scrollIntoView({ behavior: 'smooth', block: 'start' });
  x.classList.remove('ej-destello');
  void x.offsetWidth;
  x.classList.add('ej-destello');
  if (despues) setTimeout(despues, 350);
}
function ejTareas(m) {
  const t = m.t, mo = m.mo, av = m.avance;
  const out = [];
  const docs = m.docs || [];
  const sin = docs.filter((d) => !m.asoc.get(d.ref));
  if (sin.length) {
    out.push({ id: 'facturas', ico: 'documento', nivel: 'warn', txt: pl(sin.length, 'factura sin asociar', 'facturas sin asociar'),
      det: ejPesos(sin.reduce((a, d) => a + (Number(d.neto) || 0), 0)) + ' del Centro de Costos sin decir a qué gasto corresponden', boton: 'Asociar',
      ir: () => { ej.docsFiltro = 'sin'; ejPintar(); ejIrA('ejSecFacturas'); } });
  }
  const decidir = ejItems(m.costos).filter((x) => x.it.estado === 'evaluar');
  if (decidir.length) {
    out.push({ id: 'decidir', ico: 'billetera', nivel: 'warn', txt: pl(decidir.length, 'compra por decidir', 'compras por decidir'),
      det: 'Apruébala, cómprala o descártala en los gastos proyectados', boton: 'Decidir',
      ir: () => { ej.filtro = 'vigentes'; ejGuardarPrefs(); ejPintar(); ejIrA('ejSecGastos'); } });
  }
  const porTraer = rc.dir ? ejPorTraer(m, ejSemanasAtras(2)) : [];
  if (porTraer.length) {
    out.push({ id: 'traer', ico: 'calendario', nivel: '', txt: pl(porTraer.length, 'día-hombre', 'días-hombre') + ' de la Planificación',
      det: 'Asignados en la Planificación semanal y sin anotar como trabajados', boton: 'Traerlos', hace: true, ir: () => ejTraerPlanificacion(m) });
  }
  if (t.af && t.tag && mo.dias.length && Math.round(mo.costo) !== Math.round(mo.af || 0)
    && !ejPedidosAF(t.tag).some((x) => 'Mano de Obra Real' in x.valores)) {
    out.push({ id: 'llevar-mo', ico: 'derecha', nivel: '', txt: 'Mano de obra real: ' + ejPesos(mo.costo),
      det: 'El Análisis Financiero tiene ' + (mo.af !== null ? ejPesos(mo.af) : 'nada') + '; llévale lo de los días anotados', boton: 'Llevarla', hace: true,
      ir: () => ejLlevarManoObra(m) });
  }
  if (t.af && t.tag) {
    const g = ejGanttDe(t);
    if (av.valor === 1 && t.etapa === 'ejecucion' && rcClavesCierre(t).length) {
      out.push({ id: 'cerrar', ico: 'bandera', nivel: 'ok', txt: 'Avance 100 %', det: 'Si ya terminó, dalo por cerrado: pasa al Cierre del Recorrido', boton: 'Dar por cerrado', ir: () => plAbrirProyectos(t.clave) });
    } else if (g && g.resumen && g.resumen.avance > 0 && Math.round(g.resumen.avance) !== Math.round((av.valor || 0) * 100) && !av.pedido) {
      out.push({ id: 'gantt', ico: 'barras', nivel: '', txt: 'La Carta Gantt dice ' + Math.round(g.resumen.avance) + ' %',
        det: 'El Análisis Financiero tiene ' + (av.valor === null ? 'sin avance' : ejPct(av.valor)), boton: 'Revisar el avance', ir: () => ejIrA('ejSecAvance') });
    }
    if (!av.fin) {
      out.push({ id: 'fin', ico: 'reloj', nivel: '', txt: 'Sin fecha de término', det: 'Sin ella no se sabe si va atrasado', boton: 'Fijarla',
        ir: () => ejIrA('ejSecAvance', () => { const f = $('#ejAvFin'); if (f) f.focus(); }) });
    }
  } else {
    out.push({ id: 'ficha', ico: 'alerta', nivel: 'warn', txt: 'Sin ficha en el Análisis Financiero', det: 'Sin ella no se puede fijar su avance ni su fecha de término',
      boton: 'Ver cómo', ir: () => ejIrA('ejSecAvance') });
  }
  const pend = ejDe(t, 'pendiente').filter((x) => !x.listo);
  if (pend.length) {
    out.push({ id: 'pendientes', ico: 'portapapeles', nivel: '', txt: pl(pend.length, 'pendiente', 'pendientes') + ' del equipo',
      det: pend.slice(0, 2).map((x) => x.texto).join(' · '), boton: 'Ver', ir: () => ejIrA('ejSecMas') });
  }
  return out;
}
function ejPorHacerEl(m) {
  const tareas = ejTareas(m);
  // 2026-11-10, pedido del usuario: lo pendiente en un desplegable, no siempre a la vista (se recuerda abierto o cerrado)
  const s = crear('details', 'ej-porhacer');
  s.open = !!ej.porHacerAbierto;
  s.addEventListener('toggle', () => { ej.porHacerAbierto = s.open; });
  const sum = crear('summary');
  const h = crear('h2', null, tareas.length ? 'Por hacer' : 'Todo al día');
  h.id = 'ejPorHacerTit';
  if (tareas.length) h.append(crear('small', null, String(tareas.length)));
  sum.append(h);
  if (tareas.length) sum.append(crear('span', 'ej-porhacer-res', tareas.map((x) => x.txt).join(' · ')));
  s.append(sum);
  if (!tareas.length) {
    s.classList.add('al-dia');
    const p = crear('p');
    p.append(ejPinEl('ok'), document.createTextNode(' Las facturas están asociadas, no hay compras por decidir y lo anotado ya llegó al Análisis Financiero.'));
    s.append(p);
    return s;
  }
  const ul = crear('ul');
  tareas.forEach((x) => {
    const li = crear('li', 'ej-tarea');
    li.dataset.tarea = x.id;
    if (x.nivel) li.dataset.nivel = x.nivel;
    const ico = crear('span', 'ej-tarea-ico');
    ico.append(icono(x.ico, 18));
    const txt = crear('span', 'ej-tarea-txt');
    txt.append(crear('b', null, x.txt));
    if (x.det) txt.append(crear('small', null, x.det));
    const b = crear('button', x.hace ? 'cx-boton' : 'cx-enlace', x.boton);
    b.type = 'button';
    b.dataset.foco = 'tarea-' + x.id;
    if (x.hace) b.disabled = !rc.dir || ej.enviando;
    b.addEventListener('click', x.ir);
    li.append(ico, txt, b);
    ul.append(li);
  });
  s.append(ul);
  return s;
}
// Saltar a cada parte del resumen (2026-11-06): la página es larga; una fila de accesos con lo que hay en cada una
function ejSaltosEl(m, v2) {
  const nav = crear('nav', 'ej-saltos');
  nav.setAttribute('aria-label', 'Partes del resumen');
  const docs = m.docs || [];
  const sinAsoc = docs.filter((d) => !m.asoc.get(d.ref)).length;
  const decidir = ejItems(m.costos).filter((x) => x.it.estado === 'evaluar').length;
  // En la página nueva (v2), un índice vertical con íconos: lo que espera se ve como un número naranjo
  const partes = v2
    ? [['ejSecResumen', 'Resumen', '', 'inicio'], ['ejSecComoVa', 'Presupuesto', '', 'barras'], ['ejSecAvance', 'Avance', '', 'avance'],
      ['ejSecFacturas', 'Facturas', sinAsoc ? String(sinAsoc) : '', 'recibo', sinAsoc ? pl(sinAsoc, 'factura sin asociar', 'facturas sin asociar') : ''],
      ['ejSecGastos', 'Gastos proyectados', decidir ? String(decidir) : '', 'billetera', decidir ? pl(decidir, 'compra por decidir', 'compras por decidir') : ''],
      ['ejSecMO', 'Mano de obra', '', 'persona'], ['ejSecMas', 'OC, equipo y notas', '', 'nota']]
    : [['ejSecComoVa', 'Cómo va', ''], ['ejSecAvance', 'Avance', m.avance.valor === null ? '' : ejPct(m.avance.valor)], ['ejSecFacturas', 'Facturas', docs.length ? String(docs.length) + (sinAsoc ? ' · ' + sinAsoc + ' sin asociar' : '') : ''],
      ['ejSecGastos', 'Gastos proyectados', decidir ? decidir + ' por decidir' : ''], ['ejSecMO', 'Mano de obra', m.mo.dh ? ejCantidad(m.mo.dh) + ' DH' : ''],
      ['ejSecMas', 'OC, equipo y notas', '']];
  partes.forEach(([id, txt, extra, ico, dice]) => {
    const b = crear('button', 'ej-salto');
    b.type = 'button';
    if (ico) b.append(icono(ico, 16));
    b.append(crear('span', null, txt));
    if (extra) { const x = crear('small', v2 ? 'ej-hay' : null, extra); if (dice) x.title = dice; b.append(x); }
    if (v2) b.title = txt + (dice ? ': ' + dice : '');
    b.dataset.sec = id;
    b.addEventListener('click', () => ejIrA(id));
    nav.append(b);
  });
  requestAnimationFrame(ejMarcarSalto);
  return nav;
}
/* La parte a la vista se marca en los accesos (2026-11-09, vuelta 5): así se sabe dónde se está en una página larga */
function ejMarcarSalto() {
  const nav = document.querySelector('#ejProyecto .ej-saltos');
  if (!nav || $('#ejProyecto').hidden) return;
  // El índice de la página nueva va al costado: la parte a la vista es la que pasó bajo el borde de arriba de la vista
  const v2 = !!nav.closest('.ej-v2-idx') && getComputedStyle(nav).flexDirection === 'column';
  const borde = v2 ? $('#vistaEjecucion').getBoundingClientRect().top + 140 : nav.getBoundingClientRect().bottom + 24;
  let activa = null, arriba = -Infinity;
  // La última parte que ya pasó bajo los accesos; dos lado a lado (Cómo va y Avance) cuentan como la primera
  nav.querySelectorAll('.ej-salto').forEach((b) => {
    const x = document.getElementById(b.dataset.sec);
    const top = x ? x.getBoundingClientRect().top : Infinity;
    if (top <= borde && top > arriba + 4) { activa = b; arriba = top; }
  });
  const v = $('#vistaEjecucion');
  if (v.scrollTop < 8) activa = v2 ? nav.querySelector('.ej-salto') : null;   // arriba de todo: ninguna (en la nueva, el resumen)
  else if (v.scrollTop + v.clientHeight >= v.scrollHeight - 4) activa = nav.querySelector('.ej-salto:last-child');   // al fondo, la última
  nav.querySelectorAll('.ej-salto').forEach((b) => { if (b === activa) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
}
let ejRelojSalto = 0;
const ejVigilarSaltos = () => {
  const v = document.getElementById('vistaEjecucion');
  if (v) v.addEventListener('scroll', () => { cancelAnimationFrame(ejRelojSalto); ejRelojSalto = requestAnimationFrame(ejMarcarSalto); }, { passive: true });
};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ejVigilarSaltos); else ejVigilarSaltos();
function ejSinClaveEl(t) {
  const { s } = ejPanel('Le falta su N° de requerimiento');
  s.classList.add('ej-sin-clave');
  const p = crear('p', 'ej-linea');
  const carpeta = t.gestion || (t.entregado && t.entregado.carpeta) || t.titulo;
  p.append(crear('span', null, 'Su carpeta «' + carpeta + '» no lleva adelante el N° de la Planilla de Ingreso. '),
    info('Tampoco se encontró su ficha en el Análisis Financiero. Sin ese N° no se une con su oferta, su avance ni sus facturas, y no se le pueden anotar compras, días trabajados ni avance. '
      + 'Búscalo en Requerimientos y renombra la carpeta «N°. ' + carpeta + '»; si no tiene, regístralo ahí. Con la próxima vuelta del procesador aparece aquí con todo lo suyo.', 'Cómo se arregla'));
  s.append(p, ejBoton('Buscarlo en Requerimientos', 'cx-enlace', () => abrir('planilla')));
  return s;
}
function ejCabEl(m) {
  const t = m.t;
  /* La cabecera (2026-11-09, vuelta 4 del loop de UX): una tarjeta con la raya del color de su estado; a la izquierda
     quién es (N°, nombre, dónde, quién lo lleva, su formulación y sus avisos en una línea) y a la derecha su estado con
     el motivo principal; abajo, sus accesos. */
  const salud = ejSalud(t, m);
  const cab = crear('header', 'ej-cab');
  cab.dataset.salud = salud.nivel;
  const fila = crear('div', 'ej-cab-fila');
  const quien = crear('div', 'ej-cab-quien');
  const h = crear('h2');
  if (rcEtiqueta(t)) h.append(crear('span', 'ej-n', rcEtiqueta(t)));
  h.append(crear('span', null, t.titulo));
  // Cambiar el nombre que se ve (2026-11-09, pedido del usuario): solo el apodo del Análisis Financiero
  if (rc.dir && t.af && t.tag) {
    const lapiz = crear('button', 'ej-renombrar', '✎');
    lapiz.type = 'button';
    lapiz.title = 'Cambiar el nombre';
    lapiz.setAttribute('aria-label', 'Cambiar el nombre del proyecto');
    lapiz.addEventListener('click', () => ejAbrirNombre(m));
    h.append(lapiz);
  }
  quien.append(h);
  const sub = crear('p', 'ej-sub');
  sub.append(document.createTextNode([rcLegible(t.lugar), t.responsable ? (rcMia(t) ? 'Tuyo' : 'A cargo de ' + t.responsable) : 'Sin responsable',
    t.req && t.tag ? 'TAG ' + t.tag : '', t.formulacion ? 'Formulación ' + t.formulacion.codigo + ' «' + t.formulacion.estado + '»' : 'Sin formulación'].filter(Boolean).join(' · ')));
  const chips = t.etapa === 'ejecucion' ? t.chips.slice() : [{ texto: 'Ya no está en ejecución: ' + (RC_ETAPAS.find((e) => e.id === t.etapa) || {}).titulo, nivel: 'ok' }];
  if (chips.length) {
    const ch = crear('span', 'rc-chips');
    chips.forEach((c) => { const x = crear('span', 'rc-chip', c.texto); if (c.nivel) x.dataset.nivel = c.nivel; ch.append(x); });
    sub.append(ch);
  }
  quien.append(sub);
  const est = crear('div', 'ej-cab-estado');
  est.dataset.nivel = salud.nivel;
  const estTxt = crear('span', 'ej-cab-estado-txt');
  estTxt.append(crear('b', null, EJ_SALUD[salud.nivel].nombre), crear('small', null, salud.motivos[0] || ''));
  est.append(ejPinEl(salud.nivel, 16), estTxt);
  est.title = salud.motivos.join(' · ');
  fila.append(quien, est);
  cab.append(fila);
  // Abrir: su carpeta de Gestión de Proyectos (QUEMPIN.exe) y las herramientas donde tiene algo. Desde
  // 2026-10-28 la carpeta de Gestión trae «Formulación» (la copia de la oferta) y, desde el 2026-10-29, el
  // acceso directo web «Facturas del proyecto» a su carpeta del Centro de Costos en SharePoint, que el
  // botón de aquí abre directo (también en el teléfono).
  const acc = crear('div', 'cx-acc');
  const gestion = rcCarpeta((t.carpetas.ejecucion || [])[0], 'gestion');
  const oferta = rcCarpeta((t.carpetas.oferta || [])[0], 'formulacion');
  const facturas = rcFacturasWeb(t);
  const carpeta = (c, txt, pri) => {
    const b = ejBoton(txt, pri ? 'cx-boton' : 'cx-enlace', () => {
      abrirEnlace(enlaceCarpeta(c));
      avisar('Abriendo «' + c.nombre + '» en el Explorador de archivos…', { texto: '¿No se abrió?', ir: () => infoCarpeta(c) });
    }, 'proyectos');
    b.title = [NOMBRE_BIBLIOTECA[c.biblioteca]].concat(c.ruta).join(' › ');
    b.dataset.foco = 'carpeta-' + c.biblioteca;
    acc.append(b);
    return b;
  };
  /* Los accesos (2026-11-06, pedido del usuario): primero la carpeta del proyecto en el Explorador de archivos (la de
     Gestión de Proyectos o, si todavía no pasa ahí, la de su oferta), después «Facturas del proyecto». Sin el Centro de
     Costos, el Análisis Financiero ni la Carta Gantt: lo que importa de ellos ya está en este resumen. */
  const proyecto = gestion || oferta;
  if (!MOVIL.matches && proyecto) carpeta(proyecto, 'Carpeta del proyecto', true);
  if (facturas) {
    const b = ejBoton('Facturas del proyecto', proyecto && !MOVIL.matches ? 'cx-enlace' : 'cx-boton', () => window.open(facturas, '_blank', 'noopener'), 'documento');
    b.dataset.foco = 'carpeta-facturas';
    b.title = 'Su carpeta del Centro de Costos en SharePoint: las facturas que ya tiene, y lo que subas ahí entra al Centro de Costos.';
    acc.append(b);
  }
  if (!MOVIL.matches && oferta && !gestion) {
    // QUEMPIN.exe 1.3.15 pregunta antes, arma la carpeta en Gestión y deja el original en Adjudicadas
    const b = ejBoton('Pasar a Gestión de Proyectos', 'cx-enlace', () => {
      abrirEnlace('quempin://trasladar/formulacion/' + oferta.ruta.map(encodeURIComponent).join('/'));
      avisar('Pasando «' + oferta.nombre + '» a Gestión de Proyectos: confirma en la ventana de QUEMPIN.exe.', { texto: '¿No se abrió?', ir: () => infoCarpeta(oferta) });
    }, 'derecha');
    b.dataset.foco = 'trasladar';
    acc.append(b);
  }
  const ir = (txt, x, ico) => acc.append(ejBoton(txt, 'cx-enlace', () => rcIr(x), ico));
  if (t.formulacion) ir('Seguimiento', RC_IR.seguimiento(t.formulacion.uid), 'ruta');
  ir('Subir documentos', { herr: 'subir-cc' }, 'subir');
  // «Cerrado» aquí mismo (2026-11-10, pedido del usuario), o solo llevar su carpeta si ya lo está
  const cierre = ejCierreDe(t);
  if (cierre) {
    const b = ejBoton(cierre.yaCerrado ? 'Llevar su carpeta a entregados' : 'Marcar «Cerrado»', 'cx-enlace', () => ejAbrirCerrar(m), 'bandera');
    b.dataset.foco = 'marcar-cerrado';
    acc.append(b);
  }
  cab.append(acc);
  if (!gestion && !MOVIL.matches) {
    cab.append(oferta ? lineaInfo('ej-pista', 'Sin carpeta en Gestión de Proyectos', '«Pasar a Gestión de Proyectos» la crea con «Formulación» (la copia de la oferta) y deja el original en 0 OFERTAS ADJUDICADAS; lo hace QUEMPIN.exe 1.3.16 o más nuevo, que pregunta antes. Después el procesador le agrega «Facturas del proyecto», el acceso directo a su carpeta del Centro de Costos.', 'Cómo se crea')
      : lineaInfo('ej-pista', 'Sin carpeta de oferta ni de Gestión', 'No se encontró su carpeta en Formulación de proyectos ni en Gestión de Proyectos: el procesador las reconoce por el N° adelante («' + (t.req || 'N°') + '. Nombre»).', 'Por qué'));
  } else if (gestion && !facturas && ejClave(t) && !MOVIL.matches) {
    cab.append(lineaInfo('ej-pista', 'Sin carpeta en el Centro de Costos', 'Todavía no tiene carpeta con su N° en el Centro de Costos («' + (t.req || 'N°') + '. Nombre» en Facturas y Boletas): el procesador la crea al adjudicarse el proyecto y entonces agrega «Facturas del proyecto» a su carpeta de Gestión.', 'Cuándo se crea'));
  }
  return cab;
}
/* Un gráfico chico bajo la cifra (2026-11-09, vuelta 5): segmentos [clase, fracción], marcas [fracción, título] y la raya
   del avance; la escala es 0 a 1 (las fracciones ya vienen sobre el máximo). */
function ejMini(segs, marcas, raya, titulo) {
  const b = crear('span', 'ej-mini');
  b.setAttribute('aria-hidden', 'true');
  if (titulo) b.title = titulo;
  segs.forEach(([cl, f]) => { if (!(f > 0)) return; const x = crear('span', 'ej-mini-seg' + (cl ? ' ' + cl : '')); x.style.width = Math.min(100, f * 100) + '%'; b.append(x); });
  (marcas || []).forEach(([f, tt]) => { const x = crear('i', 'ej-mini-marca'); x.style.left = Math.min(100, Math.max(0, f * 100)) + '%'; x.title = tt; b.append(x); });
  if (raya !== null && raya !== undefined) { const r = crear('i', 'ej-raya-avance'); r.style.left = Math.round(Math.min(1, raya) * 100) + '%'; b.append(r); }
  return b;
}
function ejKpi(et, valor, sub, nivel, graf) {
  const k = crear('div', 'ej-kpi');
  if (nivel) k.dataset.nivel = nivel;
  k.append(crear('span', 'ej-kpi-et', et), crear('span', 'ej-kpi-v', valor));
  if (graf) k.append(graf);
  if (sub) { const s = crear('span', 'ej-kpi-sub'); (Array.isArray(sub) ? sub : [sub]).forEach((x) => s.append(typeof x === 'string' ? document.createTextNode(x) : x)); k.append(s); }
  return k;
}
function ejKpisEl(m) {
  const box = crear('div', 'ej-kpis');
  box.setAttribute('role', 'group');
  box.setAttribute('aria-label', 'El proyecto en cifras, con las compras simuladas');
  const v = m.venta;
  const kv = ejKpi('Venta neta', v ? ejPesos(v.monto) : 'Sin venta', v ? v.fuente : 'Escríbela para ver el margen estimado.');
  const corregir = crear('button', 'cx-desmarcar', v ? 'Corregir' : 'Escribir la venta');
  corregir.type = 'button';
  corregir.dataset.foco = 'venta';
  corregir.disabled = !rc.dir;
  corregir.addEventListener('click', () => ejAbrirVenta(m));
  kv.append(corregir);
  box.append(kv);
  const tot = m.tot;
  // Lo gastado hasta hoy (2026-11-06, pedido del usuario): facturas del Centro de Costos y mano de obra
  const subG = [];
  if (m.pres && tot.P > 0) subG.push(crear('b', null, ejPct(tot.G / tot.P)), ' del presupuesto');
  else subG.push('Sin presupuesto con que compararlo');
  if (tot.C > 0.5) subG.push(' · ' + ejPesos(tot.C) + ' comprometidos en OC');
  const avv = m.avance.valor;
  box.append(ejKpi('Gastado a la fecha', ejPesos(tot.G), subG, '', m.pres && tot.P > 0
    ? ejMini([['', tot.G / tot.P], ['c', tot.C / tot.P]], [], avv, 'Gastado y comprometido contra el presupuesto; la raya naranja es el avance') : null));
  const sub = [];
  if (m.pres) {
    sub.push('Presupuesto ' + ejPesos(tot.P));
    if (tot.EAC > tot.P + 0.5) sub.push(' · se pasa en ', crear('b', null, ejPesos(tot.EAC - tot.P)));
  } else sub.push('Sin presupuesto: lo gastado, comprometido y simulado');
  if (tot.Q > 0) sub.push(' · ' + ejPesos(tot.Q) + ' simulados');
  const escC = Math.max(tot.P || 0, tot.EAC) || 1;
  box.append(ejKpi('Costo estimado al cierre', ejPesos(tot.EAC), sub, m.pres && tot.EAC > tot.P + 0.5 ? 'warn' : '', m.pres && tot.P > 0
    ? ejMini([['', Math.min(tot.EAC, tot.P) / escC], ['pasa', Math.max(0, tot.EAC - tot.P) / escC]], [[tot.P / escC, 'Presupuesto ' + ejPesos(tot.P)]], null, 'Al cierre contra el presupuesto (la marca)') : null));
  const subM = [];
  if (m.margenP !== null) subM.push('Presupuestado ' + ejPct(m.margenP));
  else subM.push('Sin presupuesto: solo con lo anotado');
  subM.push(' · meta ' + ejPct(m.margenes.objetivo));
  if (m.margen !== null && m.margen0 !== null && Math.abs(m.margen0 - m.margen) > 0.0005) subM.push(' · ', crear('b', null, (m.margen < m.margen0 ? '−' : '+') + ejPuntos(m.margen0 - m.margen)), ' por lo simulado');
  const sinMargen = !m.venta ? 'Falta la venta para calcularlo.' : 'Sin presupuesto ni gastos anotados: anota lo que se espera gastar para estimarlo.';
  const escM = Math.max(0.5, (m.margenes.objetivo || 0) + 0.15, (m.margen || 0) + 0.05);
  const nivM = ejNivelMargen(m.margen, m);
  box.append(ejKpi(m.pres ? 'Margen estimado' : 'Margen con lo anotado', m.margen === null ? '—' : ejPct(m.margen), m.margen === null ? sinMargen : subM,
    nivM === 'ok' ? '' : nivM, m.margen === null ? null : ejMini([[nivM ? 'n-' + nivM : '', Math.max(0, m.margen) / escM]],
      [[m.margenes.minimo / escM, 'Mínimo ' + ejPct(m.margenes.minimo)], [m.margenes.objetivo / escM, 'Meta ' + ejPct(m.margenes.objetivo)]], null, 'El margen contra el mínimo y la meta (las marcas)')));
  const av = m.avance;
  const gs = ejGastoSobreAvance(m);
  const subA = gs ? ['Va gastado más de lo que avanza: ', crear('b', null, ejPct((tot.G + tot.C) / tot.P)), ' del presupuesto'] : av.fin ? 'Término ' + rcCorta(av.fin, new Date()) : 'Sin fecha de término';
  box.append(ejKpi('Avance', av.valor === null ? 'Sin dato' : ejPct(av.valor), av.pedido ? 'Pedido: llega con la próxima vuelta del procesador' : subA, gs ? 'warn' : '',
    av.valor === null ? null : ejMini([[av.pedido ? 'pedido' : 'av', av.valor]], [], null, 'Avance del proyecto')));
  return box;
}
/* Cómo va el proyecto (2026-11-06, pedido del usuario: «más clara y que muestre además lo que se lleva gastado»): una
   tabla por categoría con lo presupuestado, lo gastado hasta hoy, lo comprometido en OC, lo simulado, lo estimado al
   cierre y cuánto queda (o cuánto se pasa); bajo cada nombre, la barra de lo usado contra lo presupuestado (la raya). */
function ejPresupuestoEl(m) {
  const fuenteG = m.gastoFuente === 'cc' ? 'las facturas del Centro de Costos' : 'los costos reales del Análisis Financiero';
  const { s, cab } = ejPanel('Cómo va el proyecto', m.pres ? m.pres.fuente : 'sin presupuesto',
    'Gastado: ' + fuenteG + (m.mo.fuente === 'dias' ? ' y, en mano de obra, los días trabajados anotados aquí' : '') + '. Comprometido: las órdenes de compra que el Centro de Costos todavía no trae. '
    + 'Simulado: lo marcado en «Simular» en los gastos proyectados, menos lo ya facturado. '
    + (m.pres ? 'Al cierre: lo presupuestado o, si se pasa, lo gastado más lo comprometido y lo simulado (lo que todavía no se compra se estima con el presupuesto).'
      : 'Sin presupuesto, el cierre es lo gastado más lo comprometido y lo simulado.'));
  s.id = 'ejSecComoVa';
  // El presupuesto completo, en una ventana grande (2026-11-13): solo un acceso aquí, para los casos puntuales
  if (m.prBase) {
    const n = m.prVersiones.length;
    const b = ejBoton(n ? 'Presupuesto · ' + pl(n, 'actualizado', 'actualizados') : 'Ver el presupuesto', 'cx-enlace ej-pr-abrir', ejPrAbrir, 'tabla');
    b.dataset.foco = 'ver-presupuesto';
    b.title = 'El presupuesto de su formulación con todos sus costos, y versiones actualizadas para evaluar cambios';
    cab.append(b);
  }
  const tot = m.tot;
  // Lo gastado hasta hoy, en grande, con lo que se lleva del presupuesto y del avance
  const res = crear('div', 'ej-gastado');
  const g = crear('div', 'ej-gastado-num');
  g.append(crear('span', null, 'Gastado a la fecha'), crear('b', null, ejPesos(tot.G)));
  res.append(g);
  if (m.pres && tot.P > 0) {
    const p = crear('div', 'ej-gastado-barra');
    const med = crear('div', 'ej-medidor');
    const b = crear('span');
    b.style.width = Math.min(100, Math.round(100 * tot.G / tot.P)) + '%';
    med.append(b);
    if (m.avance.valor !== null) {
      const raya = crear('i', 'ej-raya-avance');
      raya.style.left = Math.round(m.avance.valor * 100) + '%';
      raya.title = 'Avance ' + ejPct(m.avance.valor);
      med.append(raya);
    }
    p.append(med, crear('span', null, ejPct(tot.G / tot.P) + ' del presupuesto' + (m.avance.valor !== null ? ' · avance ' + ejPct(m.avance.valor) : '')));
    res.append(p);
  }
  s.append(res);
  const filas = m.cats.filter((c) => (c.P || 0) > 0 || c.usado > 0);
  if (!filas.length) { s.append(crear('p', 'ej-nada', 'Todavía no tiene presupuesto ni gasto registrado.')); return s; }
  const escala = Math.max(1, ...m.cats.map((c) => Math.max(c.P || 0, c.usado)));
  const tabla = crear('table', 'ej-como');
  const cols = [['Categoría', ''], ['Presupuestado', 'ej-num'], ['Gastado', 'ej-num'], ['Comprometido', 'ej-num'], ['Simulado', 'ej-num'], ['Al cierre', 'ej-num'], [m.pres ? 'Queda' : '', 'ej-num']];
  const thead = crear('thead');
  const trh = crear('tr');
  cols.forEach(([x, c]) => { const th = crear('th', c, x); th.scope = 'col'; trh.append(th); });
  thead.append(trh);
  const tbody = crear('tbody');
  const celda = (v, et, clase) => { const td = crear('td', 'ej-num' + (clase ? ' ' + clase : ''), v); td.dataset.et = et; return td; };
  const monto = (v) => (v > 0.5 || v < -0.5 ? ejPesos(v) : '—');
  filas.forEach((c) => {
    const tr = crear('tr', 'ej-cat');
    tr.dataset.cat = c.k;
    tr.setAttribute('aria-label', c.nombre);
    const th = crear('th');
    th.scope = 'row';
    th.append(crear('b', null, c.nombre));
    // La barra: gastado, comprometido y simulado contra lo presupuestado (la raya), todas en la misma escala
    const pista = crear('div', 'ej-pista-barra');
    const segs = crear('div', 'ej-segs');
    [['', c.G, 'Gastado'], ['c', c.C, 'Comprometido'], ['q', c.Q, 'Simulado']].forEach(([k, v, et]) => {
      if (!(v > 0)) return;
      const x = crear('span', 'ej-seg' + (k ? ' ' + k : ''));
      x.style.width = (100 * v / escala) + '%';
      x.title = et + ' en ' + c.nombre.toLowerCase() + ': ' + ejPesos(v);
      segs.append(x);
    });
    pista.append(segs);
    if (c.P !== null) {
      const tope = crear('span', 'ej-tope');
      tope.style.left = (100 * c.P / escala) + '%';
      tope.title = 'Presupuestado en ' + c.nombre.toLowerCase() + ': ' + ejPesos(c.P);
      pista.append(tope);
    }
    th.append(pista);
    const q = c.queda;
    tr.append(th, celda(c.P !== null ? ejPesos(c.P) : '—', 'Presupuestado'), celda(monto(c.G), 'Gastado', 'fuerte'), celda(monto(c.C), 'Comprometido'),
      celda(monto(c.Q), 'Simulado'), celda(ejPesos(c.EAC), 'Al cierre'),
      celda(q === null ? '' : q >= -0.5 ? ejPesos(q) : 'se pasa ' + ejPesos(-q), m.pres ? (q !== null && q < -0.5 ? 'Se pasa' : 'Queda') : '', q !== null && q < -0.5 ? 'bad' : ''));
    tbody.append(tr);
  });
  const tfoot = crear('tfoot');
  const trf = crear('tr');
  const thf = crear('th', null, 'Total');
  thf.scope = 'row';
  const qt = tot.queda;
  trf.append(thf, celda(m.pres ? ejPesos(tot.P) : '—', 'Presupuestado'), celda(ejPesos(tot.G), 'Gastado', 'fuerte'), celda(monto(tot.C), 'Comprometido'),
    celda(monto(tot.Q), 'Simulado'), celda(ejPesos(tot.EAC), 'Al cierre'),
    celda(qt === null ? '' : qt >= -0.5 ? ejPesos(qt) : 'se pasa ' + ejPesos(-qt), m.pres ? (qt !== null && qt < -0.5 ? 'Se pasa' : 'Queda') : '', qt !== null && qt < -0.5 ? 'bad' : ''));
  tfoot.append(trf);
  tabla.append(thead, tbody, tfoot);
  s.append(tabla);
  const ley = crear('ul', 'ej-leyenda');
  [['', 'Gastado'], ['c', 'Comprometido'], ['q', 'Simulado'], ['t', 'Presupuestado']].forEach(([k, txt]) => {
    if (k === 't' && !m.pres) return;
    const li = crear('li');
    li.append(crear('i', k), document.createTextNode(txt));
    ley.append(li);
  });
  s.append(ley);
  const sin = m.cats.filter((c) => !((c.P || 0) > 0 || c.usado > 0)).map((c) => c.nombre.toLowerCase());
  if (sin.length) s.append(crear('p', 'ej-pista', 'Sin presupuesto ni gasto en ' + unir(sin) + '.'));
  return s;
}
// El avance: el del Análisis Financiero (o el que se pidió), el de su Carta Gantt, a qué ritmo va el gasto, y cambiarlo
function ejAvanceEl(m) {
  const t = m.t;
  const av = m.avance;
  const { s } = ejPanel('Avance', '', t.af && t.tag ? 'Lo que guardas llega al Análisis Financiero con la próxima vuelta del procesador, y de ahí al Recorrido, la Planificación semanal y el Formulador. Solo se escribe si allá sigue el valor que ves aquí.' : '');
  s.id = 'ejSecAvance';
  const num = crear('div', 'ej-av-num');
  const cambio = crear('em', 'ej-av-cambio');
  cambio.id = 'ejAvCambio';
  cambio.setAttribute('aria-live', 'polite');
  num.append(crear('b', null, av.valor === null ? 'Sin dato' : ejPct(av.valor)), cambio,
    crear('span', null, av.pedido ? 'pedido ' + plCuando(texto(av.pedido.origen && av.pedido.origen.enviado)) + (av.pedido.origen && av.pedido.origen.usuario ? ' por ' + av.pedido.origen.usuario : '')
      : t.af ? 'en el Análisis Financiero' : 'sin ficha en el Análisis Financiero'));
  s.append(num);
  const med = crear('div', 'ej-medidor ej-av-medidor');
  med.setAttribute('role', 'progressbar');
  med.setAttribute('aria-valuemin', '0');
  med.setAttribute('aria-valuemax', '100');
  med.setAttribute('aria-valuenow', String(Math.round((av.valor || 0) * 100)));
  med.setAttribute('aria-label', 'Avance del proyecto');
  const b = crear('span');
  b.style.width = Math.round((av.valor || 0) * 100) + '%';
  const previa = crear('i', 'ej-av-previa');
  previa.id = 'ejAvPrevia';
  previa.hidden = true;
  med.append(b, previa);
  s.append(med);
  if (av.pedido) {
    const p = crear('p', 'ej-linea tinte');
    const antes = av.af === null ? 'sin avance' : ejPct(av.af);
    p.append(crear('span', null, av.msj && av.msj.estado === 'pendiente' ? 'El Análisis Financiero dejó esperando el pedido (' + [].concat(av.msj.detalle || []).join(' ') + ').'
      : 'Pedido al Análisis Financiero: hoy tiene ' + antes + '. Llega con la próxima vuelta del procesador (cada 5 minutos).'));
    const r = crear('button', 'cx-desmarcar', 'Retirar el pedido');
    r.type = 'button';
    r.dataset.foco = 'retirar';
    r.addEventListener('click', () => ejRetirarAvance(m, av.pedido));
    p.append(r);
    s.append(p);
  }
  const hoy = new Date();
  if (av.fin) {
    const d = rcDias(av.fin, hoy);
    const p = crear('p', 'ej-linea');
    p.append(document.createTextNode('Término: '), crear('b', null, rcCorta(av.fin, hoy)), document.createTextNode(d < 0 ? ' · venció hace ' + pl(-d, 'día', 'días') : d === 0 ? ' · hoy' : ' · en ' + pl(d, 'día', 'días')));
    s.append(p);
  }
  const g = ejGanttDe(t);
  if (g && g.resumen && typeof g.resumen.avance === 'number') {
    const p = crear('p', 'ej-linea');
    const fin = rcFecha(g.resumen.termino);
    p.append(document.createTextNode('Carta Gantt: '), crear('b', null, Math.round(g.resumen.avance) + ' %'),
      document.createTextNode(' de avance (' + pl(Number(g.resumen.tareas) || 0, 'tarea', 'tareas') + (fin ? ', termina el ' + rcCorta(fin, hoy) : '') + ')'));
    if (t.af && t.tag && rc.dir && g.resumen.avance > 0 && Math.round(g.resumen.avance) !== Math.round((av.valor || 0) * 100)) {
      const u = crear('button', 'cx-desmarcar', 'Usar ' + Math.round(g.resumen.avance) + ' %');
      u.type = 'button';
      u.addEventListener('click', () => {
        const r = $('#ejAvRango'), n = $('#ejAvNum');
        if (!r || !n) return;
        r.value = n.value = String(Math.round(g.resumen.avance));
        ej.sucios.set('ejAvRango', r.value);
        ej.sucios.set('ejAvNum', n.value);
        n.dispatchEvent(new Event('input', { bubbles: true }));
        n.focus();
      });
      p.append(u);
    }
    s.append(p);
  }
  // A este ritmo: si el gasto siguiera como va, cuánto costaría (y el margen); solo con avance suficiente para decir algo
  const gasto = m.tot.G + m.tot.C;
  if (av.valor !== null && av.valor >= 0.1 && av.valor < 1 && gasto > 0 && m.pres) {
    const final = gasto / av.valor;
    const p = crear('p', 'ej-linea' + (final > m.tot.P * 1.05 ? ' tinte' : ''));
    p.append(document.createTextNode('A este ritmo de gasto, el costo final sería '), crear('b', null, '~' + ejPesos(final)),
      document.createTextNode(m.venta ? ' (margen ' + ejPct((m.venta.monto - final) / m.venta.monto) + ')' : ''), document.createTextNode(final > m.tot.P * 1.05 ? ': sobre lo presupuestado.' : '.'));
    p.title = 'Lo gastado y comprometido (' + ejPesos(gasto) + ') dividido por el avance (' + ejPct(av.valor) + ').';
    s.append(p);
  }
  if (t.af && t.tag) s.append(ejAvanceForm(m));
  else s.append(...ejSinFicha(m));
  return s;
}
/* Cambiar el avance (2026-11-09, vuelta 6 del loop de UX): botones rápidos (+5, +10, +25, terminado), la barra muestra
   en naranjo lo que se va a guardar y el botón dice qué guarda; sin cambios, no se puede apretar. Lo escrito sobrevive al
   repintado (ej.sucios). */
function ejAvanceForm(m) {
  const t = m.t, av = m.avance;
  const f = crear('form', 'ej-av-form');
  f.noValidate = true;
  const pct = Math.round((av.valor || 0) * 100);
  const finActual = av.fin ? plISO(av.fin) : '';
  const inicial = (id, v) => (ej.sucios.has(id) ? ej.sucios.get(id) : v);
  const rapidos = crear('div', 'ej-av-rapidos');
  rapidos.setAttribute('role', 'group');
  rapidos.setAttribute('aria-label', 'Cambiar el avance rápido');
  const rLab = crear('label', 'pl-campo ej-av-rango');
  rLab.append(crear('span', null, 'Nuevo avance'));
  const r = crear('input');
  r.type = 'range'; r.min = '0'; r.max = '100'; r.step = '5'; r.id = 'ejAvRango';
  r.value = String(inicial('ejAvRango', pct));
  rLab.append(r);
  const nLab = crear('label', 'pl-campo ej-av-pct');
  nLab.append(crear('span', null, '%'));
  const n = crear('input');
  n.type = 'number'; n.min = '0'; n.max = '100'; n.step = '1'; n.id = 'ejAvNum'; n.inputMode = 'numeric';
  n.value = String(inicial('ejAvNum', pct));
  nLab.append(n);
  const fLab = crear('label', 'pl-campo ej-av-fecha');
  fLab.append(crear('span', null, 'Fecha de término'));
  const fe = crear('input');
  fe.type = 'date'; fe.id = 'ejAvFin';
  fe.value = inicial('ejAvFin', finActual);
  fLab.append(fe);
  const enviar = crear('button', 'cx-boton');
  enviar.type = 'submit';
  enviar.dataset.foco = 'enviar-avance';
  const poner = (v) => {
    v = Math.max(0, Math.min(100, Math.round(v)));
    r.value = n.value = String(v);
    ej.sucios.set('ejAvRango', r.value);
    ej.sucios.set('ejAvNum', n.value);
    actualizar();
  };
  [['+5', 5], ['+10', 10], ['+25', 25]].forEach(([txt, d]) => {
    const b = crear('button', 'ej-av-chip', txt);
    b.type = 'button';
    b.title = 'Sumar ' + d + ' puntos al avance';
    b.addEventListener('click', () => poner((Number(n.value) || 0) + d));
    rapidos.append(b);
  });
  const fin = crear('button', 'ej-av-chip', 'Terminado 100 %');
  fin.type = 'button';
  fin.addEventListener('click', () => poner(100));
  rapidos.append(fin);
  const deshacer = crear('button', 'ej-av-chip suave', 'Como estaba');
  deshacer.type = 'button';
  deshacer.addEventListener('click', () => {
    ['ejAvRango', 'ejAvNum', 'ejAvFin'].forEach((id) => ej.sucios.delete(id));
    fe.value = finActual;
    poner(pct);
    ['ejAvRango', 'ejAvNum'].forEach((id) => ej.sucios.delete(id));
  });
  rapidos.append(deshacer);
  // Lo que se va a guardar, en la barra del panel (el naranjo) y en el botón
  function actualizar() {
    const v = Math.max(0, Math.min(100, Math.round(Number(n.value) || 0)));
    const cambiaAv = v !== pct || av.valor === null;
    const cambiaFin = /^\d{4}-\d{2}-\d{2}$/.test(fe.value) && fe.value !== finActual;
    const prev = document.getElementById('ejAvPrevia');
    if (prev) {
      prev.style.left = Math.min(v, pct) + '%';
      prev.style.width = Math.abs(v - pct) + '%';
      prev.hidden = !cambiaAv || v === pct;
      prev.classList.toggle('baja', v < pct);
    }
    const cambio = document.getElementById('ejAvCambio');
    if (cambio) cambio.textContent = cambiaAv && v !== pct ? '→ ' + v + ' %' : '';
    enviar.textContent = cambiaAv && cambiaFin ? 'Guardar ' + v + ' % y la fecha en el Análisis Financiero'
      : cambiaAv ? 'Guardar ' + v + ' % en el Análisis Financiero' : cambiaFin ? 'Guardar la fecha en el Análisis Financiero' : 'Sin cambios que guardar';
    enviar.disabled = !rc.dir || ej.enviando || !(cambiaAv || cambiaFin);
    deshacer.hidden = !(cambiaAv && v !== pct) && !cambiaFin;
  }
  r.addEventListener('input', () => { n.value = r.value; ej.sucios.set('ejAvNum', n.value); actualizar(); });
  n.addEventListener('input', () => { r.value = n.value; ej.sucios.set('ejAvRango', r.value); actualizar(); });
  fe.addEventListener('input', actualizar);
  fe.addEventListener('change', actualizar);
  f.append(rapidos, rLab, nLab, fLab, enviar);
  f.addEventListener('submit', (e) => { e.preventDefault(); ejEnviarAvance(m, Number(n.value), fe.value); });
  if (av.valor === 1 && t.etapa === 'ejecucion' && rcClavesCierre(t).length) {
    const cerrar = ejBoton('Ya terminó: dar por cerrado', 'cx-enlace ej-av-fecha', () => plAbrirProyectos(t.clave));
    cerrar.title = 'Pasa al «Cierre» del Recorrido y sale de la Planificación semanal';
    f.append(cerrar);
  }
  requestAnimationFrame(actualizar);
  actualizar();
  return f;
}
// Sin ficha en el Análisis Financiero: unirlo con una ficha sin N° que se le parezca, o crear la suya en «Ingresar avance»
function ejSinFicha(m) {
  const t = m.t;
  const out = [];
  // Sin las fichas que el procesador sabe que son otro proyecto (su propia carpeta en el Centro de Costos)
  const sueltas = ((rc.datos && rc.datos.af) || []).filter((p) => p && texto(p.tag) && !rcNum(p.req) && !(Number(p.avance) >= 1)
    && !(t.fichaAjena || []).includes(texto(p.tag).toUpperCase()));
  // La carpeta del Centro de Costos lleva el mismo nombre que su ficha («317. Quimetal -Flujómetros» ↔ «Quimetal -Flujómetros»)
  const nombres = [].concat(t.carpetas.facturas || [], t.carpetas.ejecucion || [], t.carpetas.oferta || []).map((x) => rcSinNumero(texto(x).split('/').pop())).concat([t.titulo]);
  let mejor = null, puntaje = 0;
  sueltas.forEach((p) => {
    const n = norm(p.nombre).trim();
    const x = Math.max(...nombres.map((y) => (norm(y).trim() === n && n ? 1 : ejParecido(y, p.nombre))));
    if (x > puntaje) { puntaje = x; mejor = p; }
  });
  if (mejor && puntaje >= 0.5 && t.req) {
    const pedido = ejPedidosAF(texto(mejor.tag).toUpperCase()).find((x) => 'N° Requerimiento' in x.valores);
    const p = crear('p', 'ej-linea tinte');
    p.append(document.createTextNode(pedido ? 'Se pidió unirlo con la ficha ' : '¿Es la ficha '), crear('b', null, texto(mejor.tag) + ' «' + texto(mejor.nombre) + '»'),
      document.createTextNode(pedido ? ' del Análisis Financiero: llega con la próxima vuelta del procesador.' : ' del Análisis Financiero? No tiene N° de requerimiento.'));
    out.push(p);
    if (!pedido) {
      const b = ejBoton('Unirla con el N° ' + t.req, 'cx-boton', () => ejUnirFicha(m, mejor));
      b.disabled = !rc.dir || ej.enviando;
      b.dataset.foco = 'unir';
      out.push(b);
    }
    return out;
  }
  const fila = crear('div', 'cx-acc');
  fila.append(ejBoton('Crear su ficha en «Ingresar avance»', 'cx-enlace', () => abrir('ingresar')),
    info('Para fijar su avance, sus fechas y su venta en el Análisis Financiero, crea su ficha en «Ingresar avance» con su TAG (el mismo prefijo de sus facturas en el Centro de Costos) y su N°.', 'Para qué sirve la ficha'));
  out.push(fila);
  return out;
}

// ---- El presupuesto completo y sus versiones actualizadas (2026-11-13) ----------------------------------------------
/* Pedido del usuario (2026-11-12/13): ver dentro del proyecto el presupuesto original con el desglose completo de sus
   costos y poder modificarlo para evaluar condiciones e indicadores al agregar o quitar costos, sin perder el original:
   «que se pueda generar un presupuesto actualizado». Como «una pestaña emergente grande», porque con muchos ítems ocupa
   demasiado, y como algo puntual: no se aplica en todos los proyectos. Maqueta aprobada (v2, con buscador, orden y la
   forma de la pestaña de costos del Formulador) en docs/plans/2026-11-12-presupuesto-actualizado-maqueta.html.
   - El original son las líneas de su formulación (ejLineas, con las reglas del Formulador): no se modifica. Sus
     indicadores son los del Formulador (costo total = costo directo + gastos generales e imprevistos; margen = utilidad
     / venta; incidencia de la mano de obra = mano de obra / venta).
   - Un presupuesto actualizado es una cosa del archivo (tipo 'presupuesto') con lo que cambia respecto del original:
     cantidad, costo unitario o quitado por línea (por su uid), los costos nuevos, el % de gastos generales e imprevistos y
     la venta. Si la formulación cambia después, los cambios se aplican sobre la versión nueva.
   - «Usar en «Cómo va el proyecto»» (uno a la vez): lo presupuestado de cada categoría pasa a ser el de siempre más lo
     que esa versión cambia en ella, y su venta (si la tiene) reemplaza a la calculada, no a la escrita aquí. */
const EJ_PR_SW = { Materiales: 'mat', Equipos: 'eq', 'Mano de Obra': 'mo', Otros: 'otros' };
const EJ_PR_PRE = { Materiales: 'M', Equipos: 'E', 'Mano de Obra': 'MO', Otros: 'O' };
const EJ_PR_ORDENES = [['', 'Como se ingresaron'], ['mayor', 'Mayor a menor costo'], ['menor', 'Menor a mayor costo'],
  ['pu-mayor', 'Mayor a menor costo unitario'], ['pu-menor', 'Menor a mayor costo unitario'], ['az', 'Alfabético (A → Z)'], ['dif', 'Mayor diferencia con el original']];
const EJ_PR_UID = /^[A-Za-z0-9_-]{1,40}$/;
// Las versiones actualizadas del proyecto, de la más antigua a la más nueva
const ejPrVersiones = (t) => ejDe(t, 'presupuesto').sort((a, b) => (a.creado < b.creado ? -1 : a.creado > b.creado ? 1 : a.id < b.id ? -1 : 1));
// El original: cada línea con cantidad × costo unitario = su subtotal; la mano de obra en días-hombre
function ejPrBase(calc, lineas) {
  if (!calc || !lineas.length) return null;
  const T = calc.totals;
  const items = lineas.map((l) => {
    const mo = l.cat === 'Mano de Obra';
    const conCant = l.cantidad > 0;
    const q = conCant ? l.cantidad : 1;
    return { id: l.uid, code: l.code, d: l.descripcion, cat: l.cat, partida: l.partida || '',
      unidad: mo ? (conCant ? 'DH' : 'gl') : (l.unidad || 'Un.'), q0: q, p0: l.subtotal / q, q, p: l.subtotal / q, quitado: false };
  });
  const partidas = (calc.partidas || []).concat(calc.base ? [calc.base] : []).map((p) => ({ code: p.code, nombre: texto(p.descripcion) || p.code }));
  return { items, partidas, gg0: T.cd > 0 ? (T.gg + T.imp) / T.cd * 100 : 0, venta0: T.precioNeto };
}
// Las líneas con los cambios de una versión, y sus costos nuevos al final
function ejPrAplicar(base, v) {
  const ch = new Map((v ? v.cambios : []).map((c) => [c.uid, c]));
  const items = base.items.map((b) => {
    const c = ch.get(b.id) || {};
    return Object.assign({}, b, { q: typeof c.cantidad === 'number' ? c.cantidad : b.q0, p: typeof c.unitario === 'number' ? c.unitario : b.p0, quitado: c.quitado === true });
  });
  (v ? v.nuevos : []).forEach((n) => items.push({ id: n.id, code: '', d: n.descripcion, cat: n.categoria, partida: n.partida, unidad: n.unidad || 'Un.',
    q0: null, p0: null, q: n.cantidad, p: n.unitario, quitado: false, nuevo: true }));
  return items;
}
const ejPrSub = (i) => (i.quitado ? 0 : i.q * i.p);
const ejPrSub0 = (i) => (i.nuevo ? 0 : i.q0 * i.p0);
// Cuánto cambió una línea: 'nue' nueva, 'qui' quitada, 'cam' otra cantidad o costo unitario, '' igual
const ejPrEstado = (i) => (i.nuevo ? 'nue' : i.quitado ? 'qui' : Math.abs(i.q - i.q0) > 1e-9 || Math.abs(i.p - i.p0) > 1e-6 ? 'cam' : '');
// Los indicadores de un presupuesto, con las reglas del Formulador (js/calc.js: kpis)
function ejPrCuentas(items, gg, V) {
  const cat = Object.fromEntries(EJ_CATS.map((c) => [c.k, 0]));
  let dh = 0;
  items.forEach((i) => { if (i.quitado) return; cat[i.cat] += i.q * i.p; if (i.cat === 'Mano de Obra' && i.unidad === 'DH') dh += i.q; });
  const cd = EJ_CATS.reduce((a, c) => a + cat[c.k], 0);
  const ggm = cd * gg / 100;
  const costo = cd + ggm;
  const util = V > 0 ? V - costo : null;
  return { cat, cd, ggm, costo, venta: V > 0 ? V : null, util, margen: util !== null ? util / V : null, dh,
    uDH: util !== null && dh > 0 ? util / dh : null, inc: V > 0 ? cat['Mano de Obra'] / V : null };
}
// La versión que se usa en «Cómo va el proyecto»: cuánto cambia cada categoría y su venta
function ejPrSeguimiento(versiones, base) {
  const v = base ? versiones.filter((x) => x.seguimiento).sort((a, b) => (a.t < b.t ? 1 : -1))[0] : null;
  if (!v) return null;
  const items = ejPrAplicar(base, v);
  const delta = Object.fromEntries(EJ_CATS.map((c) => [c.k, 0]));
  items.forEach((i) => { delta[i.cat] += ejPrSub(i) - ejPrSub0(i); });
  return { v, delta };
}
// Una versión como cosa del archivo: solo lo que cambia respecto del original
function ejPrCosa(t, b, base) {
  const cambios = b.items.filter((i) => !i.nuevo && ejPrEstado(i)).map((i) => {
    const c = { uid: i.id };
    if (i.quitado) c.quitado = true;
    if (Math.abs(i.q - i.q0) > 1e-9) c.cantidad = i.q;
    if (Math.abs(i.p - i.p0) > 1e-6) c.unitario = i.p;
    return c;
  });
  const nuevos = b.items.filter((i) => i.nuevo).map((i) => ({ id: i.id, descripcion: i.d, categoria: i.cat, partida: i.partida, unidad: i.unidad, cantidad: i.q, unitario: i.p }));
  return { id: b.id, proyecto: ejClave(t), tipo: 'presupuesto', nombre: ejTxt(b.nombre, 60) || 'Presupuesto actualizado', cambios, nuevos,
    gg: Math.abs(b.gg - base.gg0) > 1e-9 ? b.gg : null, venta: b.venta, seguimiento: b.seguimiento, creado: b.creado || undefined };
}
/* La ventana del presupuesto (#dlgEjPres, se arma en JS): arriba las versiones y los indicadores; debajo las subpestañas
   por categoría como la pestaña de costos del Formulador, con buscador, «Ordenar» y «Mostrar» (la partida); al final el
   cierre (costo directo, gastos generales e imprevistos, costo total, venta y utilidad). En una versión actualizada se
   cambian la cantidad y el costo unitario de cada línea, se quita una línea (✕, vuelve con ↺) o se agrega un costo; nada
   se guarda hasta «Guardar». ej.pr: { clave, tab, q, orden, mostrar, solo, b (la versión a la vista; null: el original),
   guardado (cómo estaba al abrirla, para saber si hay cambios) }. */
function ejPrCtx() {
  const m = ej.modelo;
  const pr = ej.pr;
  if (!m || !pr || m.t.clave !== pr.clave || !m.prBase) return null;
  return { m, t: m.t, base: m.prBase, vs: m.prVersiones };
}
function ejPrSucio() {
  const pr = ej.pr;
  if (!pr || !pr.b) return false;
  const c = ejPrCtx();
  return !c || !pr.b.guardada || JSON.stringify(ejPrCosa(c.t, pr.b, c.base)) !== pr.guardado;
}
const ejPrSalir = () => !ejPrSucio() || confirm('Hay cambios sin guardar en «' + ej.pr.b.nombre + '». ¿Dejarlos igual?');
const ejPrVenta = (c) => (ej.pr.b && ej.pr.b.venta > 0 ? ej.pr.b.venta : c.base.venta0);
function ejPrDlg() {
  let d = $('#dlgEjPres');
  if (d) return d;
  d = crear('dialog');
  d.id = 'dlgEjPres';
  d.setAttribute('aria-labelledby', 'ejPrTit');
  const f = crear('form', 'dlg');
  f.noValidate = true;
  // Enter en una caja la deja escrita (su «change»), no cierra nada
  f.addEventListener('submit', (e) => { e.preventDefault(); const a = document.activeElement; if (a && a.matches('input')) a.blur(); });
  const h = crear('h2');
  h.id = 'ejPrTit';
  const x = crear('button', 'dlg-x');
  x.type = 'button';
  x.setAttribute('aria-label', 'Cerrar');
  x.append(icono('cerrar', 18));
  x.addEventListener('click', () => { if (ejPrSalir()) d.close(); });
  const cuerpo = crear('div', 'ej-pr');
  cuerpo.id = 'ejPrCuerpo';
  const acc = crear('div', 'dlg-acc ej-pr-acc');
  acc.id = 'ejPrAcc';
  f.append(h, x, cuerpo, acc);
  d.append(f);
  document.body.append(d);
  d.addEventListener('cancel', (e) => { if (!ejPrSalir()) e.preventDefault(); });
  d.addEventListener('close', () => { ej.pr = null; });
  return d;
}
function ejPrAbrir() {
  const m = ej.modelo;
  if (!m || !m.prBase) return;
  const d = ejPrDlg();
  ej.pr = { clave: m.t.clave, tab: 'todo', q: '', orden: '', mostrar: '', solo: false, b: null, guardado: '' };
  // Abre la que se usa en el seguimiento o, si no, la más nueva; sin versiones, el original
  const vs = m.prVersiones;
  const seg = vs.find((v) => v.seguimiento);
  ejPrElegir(seg ? seg.id : vs.length ? vs[vs.length - 1].id : 'o');
  d.showModal();
  const f = d.querySelector('.dlg');
  if (f) f.scrollTop = 0;
}
function ejPrElegir(id) {
  const c = ejPrCtx();
  if (!c) return;
  const pr = ej.pr;
  const v = id === 'o' ? null : c.vs.find((x) => x.id === id);
  if (!v) { pr.b = null; pr.guardado = ''; }
  else {
    pr.b = { id: v.id, nombre: v.nombre, items: ejPrAplicar(c.base, v), gg: v.gg !== null ? v.gg : c.base.gg0, venta: v.venta, seguimiento: v.seguimiento, creado: v.creado, guardada: true };
    pr.guardado = JSON.stringify(ejPrCosa(c.t, pr.b, c.base));
  }
  pr.solo = false;
  ejPrPintar();
}
// Una versión nueva, copia del original o de otra versión (sin guardar hasta «Guardar»)
function ejPrNueva(desde) {
  const c = ejPrCtx();
  if (!c) return;
  if (!rc.dir) { avisar('Conecta la carpeta de Intercambio para guardar un presupuesto actualizado.'); return; }
  if (!ejPrSalir()) return;
  const v = desde === 'o' ? null : c.vs.find((x) => x.id === desde) || null;
  const items = ejPrAplicar(c.base, v).map((i) => (i.nuevo ? Object.assign({}, i, { id: ejNuevoId('prn-') }) : i));
  const usados = new Set(c.vs.map((x) => x.nombre));
  let n = c.vs.length + 1;
  while (usados.has('Actualizado ' + n)) n++;
  ej.pr.b = { id: ejNuevoId('pr-'), nombre: 'Actualizado ' + n, items, gg: v && v.gg !== null ? v.gg : c.base.gg0, venta: v ? v.venta : null, seguimiento: false, creado: '', guardada: false };
  ej.pr.guardado = '';
  ej.pr.solo = false;
  ejPrPintar();
}
function ejPrPintar() {
  const c = ejPrCtx();
  if (!c) return;
  const t = c.t;
  $('#ejPrTit').textContent = 'Presupuesto · ' + (rcEtiqueta(t) ? rcEtiqueta(t) + ' ' : '') + t.titulo;
  const d = $('#dlgEjPres');
  const f = d.querySelector('.dlg');
  const desplazado = f.scrollTop;
  const a = document.activeElement;
  const foco = a && d.contains(a) && a.dataset ? a.dataset.foco : null;
  const cuerpo = $('#ejPrCuerpo');
  cuerpo.textContent = '';
  const tabla = crear('div', 'ej-pr-tabla');
  tabla.id = 'ejPrTabla';
  const cierre = crear('div', 'ej-pr-cierre');
  cierre.id = 'ejPrCierre';
  cuerpo.append(ejPrVersionesEl(c), ejPrKpisEl(c), ejPrTabsEl(c), ejPrBarraEl(c), tabla, cierre);
  ejPrPintarTabla();
  ejPrCierreEl(c, cierre);
  ejPrAccEl(c);
  f.scrollTop = desplazado;
  if (foco) { const x = d.querySelector('[data-foco="' + CSS.escape(foco) + '"]'); if (x) x.focus({ preventScroll: true }); }
}
function ejPrVersionesEl(c) {
  const pr = ej.pr;
  const w = crear('div', 'ej-pr-vers');
  const actual = pr.b ? pr.b.id : 'o';
  const chip = (id, nombre, sub, seg) => {
    const b = crear('button', 'ej-pr-ver' + (id === actual ? ' on' : ''));
    b.type = 'button';
    b.setAttribute('aria-pressed', String(id === actual));
    b.dataset.foco = 'pr-ver-' + id;
    const n = crear('b', null, nombre);
    if (seg) n.append(crear('span', 'ej-pr-seg', 'en uso'));
    b.append(n, crear('span', null, sub));
    b.addEventListener('click', () => { if (id !== actual && ejPrSalir()) ejPrElegir(id); });
    return b;
  };
  const f = c.t.formulacion;
  const o = chip('o', 'Original', 'Formulación ' + f.codigo + (f.version > 1 ? ' v' + f.version : ''), false);
  o.querySelector('b').prepend(icono('llave', 14));
  o.title = 'El presupuesto de su formulación, tal como se vendió. No se modifica.';
  w.append(o);
  c.vs.forEach((v) => {
    const b = chip(v.id, v.nombre, (v.por ? v.por + ', ' : '') + plCuando(v.t), v.seguimiento);
    if (v.seguimiento) b.title = '«Cómo va el proyecto» usa este presupuesto';
    w.append(b);
  });
  if (pr.b && !pr.b.guardada) w.append(chip(pr.b.id, pr.b.nombre, 'sin guardar', false));
  // Otra versión: del original o copia de una de las actualizadas
  if (rc.dir) {
    if (!c.vs.length && !pr.b) {
      const b = ejBoton('Crear un presupuesto actualizado', 'cx-enlace', () => ejPrNueva('o'), 'mas');
      b.dataset.foco = 'pr-nueva';
      w.append(b);
    } else {
      const s = crear('select', 'ej-pr-nueva');
      s.setAttribute('aria-label', 'Nuevo presupuesto actualizado');
      s.dataset.foco = 'pr-nueva';
      const op = (v, txt) => { const x = crear('option', null, txt); x.value = v; return x; };
      s.append(op('', '+ Nuevo actualizado…'), op('o', 'Copia del original'));
      c.vs.forEach((v) => s.append(op(v.id, 'Copia de «' + v.nombre + '»')));
      s.addEventListener('change', () => { const v = s.value; s.value = ''; if (v) ejPrNueva(v); });
      w.append(s);
    }
  }
  if (pr.b) {
    const l = crear('label', 'ej-pr-nombre');
    const x = crear('input');
    x.type = 'text'; x.maxLength = 60; x.value = pr.b.nombre; x.autocomplete = 'off';
    x.dataset.foco = 'pr-nombre';
    x.addEventListener('change', () => { pr.b.nombre = ejTxt(x.value, 60) || pr.b.nombre; ejPrPintar(); });
    l.append(crear('span', null, 'Nombre'), x);
    w.append(l);
  }
  return w;
}
// Los indicadores arriba, como en la maqueta aprobada: en una versión actualizada, con el original y la diferencia
function ejPrKpisEl(c) {
  const pr = ej.pr;
  const m = c.m;
  const o = ejPrCuentas(c.base.items, c.base.gg0, c.base.venta0);
  const a = pr.b ? ejPrCuentas(pr.b.items, pr.b.gg, ejPrVenta(c)) : o;
  const w = crear('div', 'ej-pr-kpis');
  const pesos = (x) => (x === null ? '—' : ejPesos(x));
  const dh = (x) => (x ? ejCantidad(x) + ' DH' : '—');
  const tile = (nombre, k, fmt, mejor, ayuda, extra) => {
    const d = crear('div', 'ej-pr-kpi');
    d.dataset.k = k;
    const et = crear('span', 'ej-pr-k', nombre);
    if (ayuda) et.append(info(ayuda, 'Qué es: ' + nombre.toLowerCase()));
    d.append(et, crear('b', 'ej-num', fmt(a[k])));
    if (extra) d.append(extra);
    if (pr.b) {
      const s = crear('span', 'ej-pr-o', 'Original ' + fmt(o[k]));
      const df = a[k] !== null && o[k] !== null ? a[k] - o[k] : 0;
      const casi = fmt === ejPct ? Math.abs(df) < 0.0005 : Math.abs(df) < 0.5;
      if (!casi) {
        const ch = crear('span', 'ej-pr-d', (df > 0 ? '▲ ' : '▼ ') + (fmt === ejPct ? ejPuntos(df) : fmt(Math.abs(df))));
        ch.dataset.nivel = mejor === 0 ? '' : (df > 0) === (mejor > 0) ? 'ok' : 'bad';
        s.append(ch);
      }
      d.append(s);
    }
    return d;
  };
  // El margen con su barra, el mínimo y la meta de su formulación
  let barra = null;
  if (a.margen !== null) {
    barra = crear('span', 'ej-pr-mg');
    const r = crear('i');
    r.style.width = Math.max(0, Math.min(100, a.margen / 0.5 * 100)) + '%';
    r.dataset.nivel = a.margen >= m.margenes.objetivo ? 'ok' : a.margen >= m.margenes.minimo ? 'warn' : 'bad';
    barra.append(r);
    [m.margenes.minimo, m.margenes.objetivo].forEach((x) => { const u = crear('u'); u.style.left = Math.min(100, x / 0.5 * 100) + '%'; barra.append(u); });
    barra.title = 'Mínimo ' + ejPct(m.margenes.minimo) + ' · meta ' + ejPct(m.margenes.objetivo);
  }
  w.append(tile('Costo total', 'costo', pesos, -1, 'Costo directo más gastos generales e imprevistos.'),
    tile('Margen', 'margen', ejPct, 1, 'La venta menos el costo total, como parte de la venta. Mínimo ' + ejPct(m.margenes.minimo) + ', meta ' + ejPct(m.margenes.objetivo) + '.', barra),
    tile('Utilidad', 'util', pesos, 1, ''),
    tile('Días-hombre', 'dh', dh, 0, ''),
    tile('Utilidad por día-hombre', 'uDH', pesos, 1, 'La utilidad dividida por los días-hombre de la mano de obra.'),
    tile('Incidencia de la mano de obra', 'inc', ejPct, 0, 'La mano de obra como parte de la venta.'));
  return w;
}
const ejPrItems = () => (ej.pr.b ? ej.pr.b.items : ejPrCtx().base.items);
function ejPrTabsEl(c) {
  const pr = ej.pr;
  const items = ejPrItems();
  const w = crear('div', 'ej-pr-tabs');
  w.setAttribute('role', 'tablist');
  w.setAttribute('aria-label', 'Tipo de costo');
  const tab = (k, sw, nombre, xs) => {
    const b = crear('button', 'ej-pr-tab' + (pr.tab === k ? ' on' : ''));
    b.type = 'button';
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(pr.tab === k));
    b.dataset.foco = 'pr-tab-' + k;
    const n = xs ? xs.filter((i) => !i.quitado).length : (c.base.partidas.length || '');
    const cam = pr.b && xs ? xs.filter((i) => ejPrEstado(i)).length : 0;
    const cnt = crear('span', 'ej-pr-cnt' + (cam ? ' cam' : ''), String(cam || n));
    if (cam) cnt.title = pl(cam, 'cambio', 'cambios');
    b.append(crear('i', 'ej-pr-sw ' + sw), crear('b', null, nombre), cnt);
    if (xs) {
      const v = xs.reduce((s, i) => s + ejPrSub(i), 0);
      const v0 = xs.reduce((s, i) => s + ejPrSub0(i), 0);
      const val = crear('span', 'ej-num', ejPesos(v));
      if (pr.b && Math.abs(v - v0) >= 0.5) val.append(crear('em', v > v0 ? 'pos' : 'neg', ' (' + (v > v0 ? '+' : '−') + ejPesos(Math.abs(v - v0)) + ')'));
      b.append(val);
    } else b.append(crear('span', null, 'El costo de cada partida'));
    b.addEventListener('click', () => { pr.tab = k; ejPrPintar(); });
    return b;
  };
  w.append(tab('todo', 'todo', 'Todos los costos', items));
  EJ_CATS.forEach((cat) => w.append(tab(cat.k, EJ_PR_SW[cat.k], cat.nombre, items.filter((i) => i.cat === cat.k))));
  w.append(tab('part', 'part', 'Por partida', null));
  return w;
}
function ejPrBarraEl(c) {
  const pr = ej.pr;
  const w = crear('div', 'ej-pr-barra');
  const izq = crear('div', 'ej-pr-izq');
  if (!pr.b) {
    const l = crear('span', 'ej-pr-lock');
    l.append(icono('llave', 14), document.createTextNode('No se modifica'));
    izq.append(l);
  } else if (pr.tab !== 'part') {
    const b = ejBoton('Agregar costo', 'cx-boton', ejPrAgregar, 'mas');
    b.dataset.foco = 'pr-agregar';
    const l = crear('label', 'ej-pr-solo');
    const cb = crear('input');
    cb.type = 'checkbox'; cb.checked = pr.solo; cb.dataset.foco = 'pr-solo';
    cb.addEventListener('change', () => { pr.solo = cb.checked; ejPrPintarTabla(); });
    l.append(cb, document.createTextNode('Solo lo que cambió'));
    izq.append(b, l);
  }
  const der = crear('div', 'ej-pr-der');
  const q = crear('input', 'ej-pr-q' + (pr.q ? ' is-set' : ''));
  q.type = 'search'; q.placeholder = 'Buscar'; q.autocomplete = 'off'; q.value = pr.q; q.dataset.foco = 'pr-q';
  q.setAttribute('aria-label', 'Buscar por descripción, ID o partida');
  q.addEventListener('input', () => { pr.q = q.value; q.classList.toggle('is-set', !!pr.q); ejPrPintarTabla(); });
  der.append(q);
  const sel = (et, id, ops, v, al) => {
    const l = crear('label', 'ej-pr-filtro');
    const s = crear('select', v ? 'is-set' : '');
    s.dataset.foco = 'pr-' + id;
    ops.forEach(([val, txt]) => { const o = crear('option', null, txt); o.value = val; o.selected = val === v; s.append(o); });
    s.addEventListener('change', () => al(s.value));
    l.append(crear('span', null, et), s);
    return l;
  };
  if (pr.tab !== 'part') {
    der.append(sel('Ordenar', 'orden', EJ_PR_ORDENES.filter((o) => pr.b || o[0] !== 'dif'), pr.orden, (v) => { pr.orden = v; ejPrPintar(); }));
    if (c.base.partidas.length > 1) {
      der.append(sel('Mostrar', 'mostrar', [['', 'Todas las partidas']].concat(c.base.partidas.map((p) => [p.code, p.code + ' · ' + p.nombre])), pr.mostrar, (v) => { pr.mostrar = v; ejPrPintar(); }));
    }
  }
  w.append(izq, der);
  return w;
}
const ejPrPartidaDe = (c, code) => (c.base.partidas.find((p) => p.code === code) || {}).nombre || '';
const ejPrEnPartida = (i, code) => !code || i.partida === code || i.partida.split('+').includes(code);
function ejPrVisibles(c) {
  const pr = ej.pr;
  const q = norm(pr.q.trim());
  let xs = ejPrItems().filter((i) => (pr.tab === 'todo' || i.cat === pr.tab) && ejPrEnPartida(i, pr.mostrar));
  if (q) xs = xs.filter((i) => norm([i.code, i.d, i.partida, ejPrPartidaDe(c, i.partida)].join(' ')).includes(q));
  if (pr.solo && pr.b) xs = xs.filter((i) => ejPrEstado(i));
  const o = pr.orden;
  const ord = (f) => { xs = xs.slice().sort(f); };
  if (o === 'mayor') ord((a, b) => ejPrSub(b) - ejPrSub(a));
  else if (o === 'menor') ord((a, b) => ejPrSub(a) - ejPrSub(b));
  else if (o === 'pu-mayor') ord((a, b) => b.p - a.p);
  else if (o === 'pu-menor') ord((a, b) => a.p - b.p);
  else if (o === 'az') ord((a, b) => (!a.d - !b.d) || a.d.localeCompare(b.d, 'es', { sensitivity: 'base', numeric: true }));
  else if (o === 'dif') ord((a, b) => Math.abs(ejPrSub(b) - ejPrSub0(b)) - Math.abs(ejPrSub(a) - ejPrSub0(a)));
  return xs;
}
const ejPrDif = (d) => { const s = crear('span', d > 0.5 ? 'pos' : d < -0.5 ? 'neg' : null, Math.abs(d) >= 0.5 ? (d > 0 ? '+' : '−') + ejPesos(Math.abs(d)) : ''); return s; };
function ejPrTh(txt, k, num) {
  const pr = ej.pr;
  const th = crear('th', num ? 'ej-num' : null, txt);
  th.scope = 'col';
  if (!k) return th;
  const pares = { sub: ['mayor', 'menor'], pu: ['pu-mayor', 'pu-menor'], az: ['az'], dif: ['dif'] }[k];
  const on = pares.includes(pr.orden);
  th.classList.add('ej-pr-ord');
  if (on) th.classList.add('on');
  th.tabIndex = 0;
  th.dataset.foco = 'pr-th-' + k;
  th.setAttribute('aria-sort', on ? (pr.orden === 'menor' || pr.orden === 'pu-menor' ? 'ascending' : 'descending') : 'none');
  th.append(crear('span', 'ej-pr-flecha', on ? (pr.orden === 'menor' || pr.orden === 'pu-menor' ? '▲' : '▼') : '↕'));
  const ir = () => {
    pr.orden = k === 'sub' ? (pr.orden === 'mayor' ? 'menor' : 'mayor') : k === 'pu' ? (pr.orden === 'pu-mayor' ? 'pu-menor' : 'pu-mayor') : pr.orden === pares[0] ? '' : pares[0];
    ejPrPintar();
  };
  th.addEventListener('click', ir);
  th.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ir(); } });
  return th;
}
function ejPrPintarTabla() {
  const c = ejPrCtx();
  if (!c) return;
  const pr = ej.pr;
  const w = $('#ejPrTabla');
  w.textContent = '';
  if (pr.tab === 'part') { ejPrPartidasEl(c, w); return; }
  const ed = !!pr.b;
  const xs = ejPrVisibles(c);
  const tabla = crear('table', 'ej-pr-t');
  const trh = crear('tr');
  trh.append(ejPrTh('ID'), ejPrTh('Descripción', 'az'), ejPrTh('Partida'), ejPrTh('Cantidad', null, true), ejPrTh('Unidad'), ejPrTh('Costo unitario', 'pu', true));
  if (ed) trh.append(ejPrTh('Original', null, true), ejPrTh('Subtotal', 'sub', true), ejPrTh('Diferencia', 'dif', true), crear('th'));
  else trh.append(ejPrTh('Subtotal', 'sub', true));
  const thead = crear('thead');
  thead.append(trh);
  const tbody = crear('tbody');
  const celda = (et, clase, hijo) => { const td = crear('td', clase || null); td.dataset.et = et; if (hijo !== undefined && hijo !== null) td.append(hijo); return td; };
  const caja = (i, f) => {
    const x = crear('input', 'ej-pr-in');
    x.type = 'text'; x.inputMode = 'decimal'; x.autocomplete = 'off';
    x.setAttribute('data-num', '');
    // Sin formato: numeros.js le pone los puntos al prepararla («800.000» antes de eso lo leería como 800,000)
    x.value = String(Math.round(i[f] * 100) / 100);
    x.dataset.foco = 'pr-' + f + '-' + i.id;
    x.setAttribute('aria-label', (f === 'q' ? 'Cantidad de ' : 'Costo unitario de ') + (i.d || 'el costo nuevo'));
    const orig = f === 'q' ? i.q0 : i.p0;
    if (!i.nuevo && Math.abs(i[f] - orig) > 1e-6) { x.classList.add('mod'); x.title = 'Original: ' + (f === 'p' ? ejPesos(orig) : ejCantidad(orig)); }
    x.addEventListener('change', () => {
      const n = ejNumero(x.value);
      if (n === null || n < 0) { x.value = ejCantidad(i[f]); return; }
      i[f] = n;
      ejPrPintar();
    });
    return x;
  };
  xs.forEach((i) => {
    const e = ed ? ejPrEstado(i) : '';
    const tr = crear('tr', e ? 'ej-pr-' + e : null);
    const id = crear('td', 'ej-pr-code');
    id.append(crear('i', 'ej-pr-sw ' + EJ_PR_SW[i.cat]), document.createTextNode(i.code || EJ_PR_PRE[i.cat] + '+'));
    id.title = EJ_CAT.get(i.cat).nombre;
    // Descripción, categoría y partida: escritas solo en un costo nuevo
    let dsc, par;
    if (ed && i.nuevo) {
      dsc = crear('span', 'ej-pr-nuevo-dsc');
      const x = crear('input', 'ej-pr-in ej-pr-dsc');
      x.type = 'text'; x.maxLength = 200; x.value = i.d; x.placeholder = 'Descripción'; x.autocomplete = 'off';
      x.dataset.foco = 'pr-d-' + i.id;
      x.setAttribute('aria-label', 'Descripción del costo nuevo');
      x.addEventListener('change', () => { i.d = ejTxt(x.value, 200); ejPrPintar(); });
      const s = crear('select', 'ej-pr-sel');
      s.dataset.foco = 'pr-c-' + i.id;
      s.setAttribute('aria-label', 'Categoría del costo nuevo');
      EJ_CATS.forEach((cat) => { const o = crear('option', null, cat.nombre); o.value = cat.k; o.selected = cat.k === i.cat; s.append(o); });
      s.addEventListener('change', () => { i.cat = s.value; ejPrPintar(); });
      dsc.append(x, s, crear('span', 'ej-pr-tag n', 'nuevo'));
      par = crear('select', 'ej-pr-sel');
      par.dataset.foco = 'pr-p-' + i.id;
      par.setAttribute('aria-label', 'Partida del costo nuevo');
      c.base.partidas.forEach((p) => { const o = crear('option', null, p.code + ' · ' + p.nombre); o.value = p.code; o.selected = p.code === i.partida; par.append(o); });
      par.addEventListener('change', () => { i.partida = par.value; ejPrPintar(); });
    } else {
      dsc = crear('span', null, i.d);
      if (e === 'qui') dsc.append(crear('span', 'ej-pr-tag q', 'quitado'));
      par = crear('span', 'ej-pr-partida');
      if (i.partida) par.append(crear('span', 'ej-pr-pcode', i.partida.includes('+') ? '÷' + i.partida.split('+').length : i.partida), crear('span', 'ej-pr-ptxt', i.partida.includes('+') ? i.partida : ejPrPartidaDe(c, i.partida)));
    }
    const tdD = celda('Descripción', 'ej-pr-desc', dsc);
    tr.append(id, tdD, celda('Partida', null, par));
    const editable = ed && !i.quitado;
    tr.append(celda('Cantidad', 'ej-num', editable ? caja(i, 'q') : document.createTextNode(ejCantidad(i.q))), celda('Unidad', null, document.createTextNode(i.unidad)),
      celda('Costo unitario', 'ej-num', editable ? caja(i, 'p') : document.createTextNode(ejPesos(i.p))));
    if (ed) {
      const b = crear('button', 'ej-pr-x');
      b.type = 'button';
      b.dataset.foco = 'pr-x-' + i.id;
      if (i.quitado) {
        b.textContent = '↺'; b.title = 'Volver a incluir'; b.setAttribute('aria-label', 'Volver a incluir ' + i.d);
        b.addEventListener('click', () => { i.quitado = false; ejPrPintar(); });
      } else {
        b.append(icono('cerrar', 14)); b.title = i.nuevo ? 'Eliminar' : 'Quitar'; b.setAttribute('aria-label', (i.nuevo ? 'Eliminar ' : 'Quitar ') + (i.d || 'el costo nuevo'));
        b.addEventListener('click', () => {
          if (i.nuevo) pr.b.items.splice(pr.b.items.indexOf(i), 1); else i.quitado = true;
          ejPrPintar();
        });
      }
      tr.append(celda('Original', 'ej-num ej-pr-mu', document.createTextNode(i.nuevo ? '—' : ejPesos(ejPrSub0(i)))),
        celda('Subtotal', 'ej-num ej-pr-sub', document.createTextNode(ejPesos(ejPrSub(i)))), celda('Diferencia', 'ej-num', ejPrDif(ejPrSub(i) - ejPrSub0(i))), celda('', 'ej-pr-acc-fila', b));
    } else tr.append(celda('Subtotal', 'ej-num ej-pr-sub', document.createTextNode(ejPesos(ejPrSub(i)))));
    tbody.append(tr);
  });
  if (!xs.length) {
    const tr = crear('tr', 'ej-pr-vacio');
    const td = crear('td', null, pr.q || pr.mostrar || pr.solo ? 'No hay costos con este filtro.' : 'Sin costos de este tipo.');
    td.colSpan = ed ? 10 : 7;
    tr.append(td);
    tbody.append(tr);
  }
  // El total de lo que se ve; con filtro dice cuántas filas suma, como el Formulador
  const todos = ejPrItems().filter((i) => pr.tab === 'todo' || i.cat === pr.tab);
  const sum = xs.reduce((s, i) => s + ejPrSub(i), 0);
  const sum0 = xs.reduce((s, i) => s + ejPrSub0(i), 0);
  const tfoot = crear('tfoot');
  const trf = crear('tr');
  const et = crear('td', null, 'Total ' + (pr.tab === 'todo' ? 'costo directo' : EJ_CAT.get(pr.tab).nombre.toLowerCase()) + (xs.length !== todos.length ? ' filtrado · ' + xs.length + ' de ' + todos.length : ''));
  et.colSpan = 6;
  trf.append(et);
  if (ed) trf.append(celda('Original', 'ej-num ej-pr-mu', document.createTextNode(ejPesos(sum0))), celda('Subtotal', 'ej-num', document.createTextNode(ejPesos(sum))), celda('Diferencia', 'ej-num', ejPrDif(sum - sum0)), crear('td'));
  else trf.append(celda('Subtotal', 'ej-num', document.createTextNode(ejPesos(sum))));
  tfoot.append(trf);
  tabla.append(thead, tbody, tfoot);
  w.append(tabla);
}
// Por partida: sus cuatro categorías y su costo directo (un costo repartido entre varias va en partes iguales)
function ejPrPartidasEl(c, w) {
  const pr = ej.pr;
  const ed = !!pr.b;
  const q = norm(pr.q.trim());
  const items = ejPrItems();
  const reparto = (i, code, f) => { const ps = i.partida.split('+'); return ps.includes(code) ? f(i) / ps.length : 0; };
  const tabla = crear('table', 'ej-pr-t');
  const trh = crear('tr');
  trh.append(ejPrTh('ID'), ejPrTh('Partida'));
  EJ_CATS.forEach((cat) => { const th = ejPrTh(cat.nombre, null, true); th.prepend(crear('i', 'ej-pr-sw ' + EJ_PR_SW[cat.k])); trh.append(th); });
  if (ed) trh.append(ejPrTh('Original', null, true), ejPrTh('Costo directo', null, true), ejPrTh('Diferencia', null, true));
  else trh.append(ejPrTh('Costo directo', null, true));
  const thead = crear('thead');
  thead.append(trh);
  const tbody = crear('tbody');
  const td = (txt, clase, et) => { const x = crear('td', clase || 'ej-num', txt); if (et) x.dataset.et = et; return x; };
  c.base.partidas.filter((p) => !q || norm(p.code + ' ' + p.nombre).includes(q)).forEach((p) => {
    const tr = crear('tr', 'ej-pr-clic');
    tr.tabIndex = 0;
    tr.title = 'Ver los costos de ' + p.code;
    const cd = items.reduce((s, i) => s + reparto(i, p.code, ejPrSub), 0);
    const cd0 = items.reduce((s, i) => s + reparto(i, p.code, ejPrSub0), 0);
    const nom = crear('td', 'ej-pr-desc', p.nombre);
    const cam = ed ? items.filter((i) => ejPrEnPartida(i, p.code) && ejPrEstado(i)).length : 0;
    if (cam) nom.append(crear('span', 'ej-pr-cnt cam', String(cam)));
    tr.append(td(p.code, 'ej-pr-code'), nom);
    EJ_CATS.forEach((cat) => tr.append(td(ejPesos(items.filter((i) => i.cat === cat.k).reduce((s, i) => s + reparto(i, p.code, ejPrSub), 0)), null, cat.nombre)));
    if (ed) { tr.append(td(ejPesos(cd0), 'ej-num ej-pr-mu', 'Original'), td(ejPesos(cd), 'ej-num ej-pr-sub', 'Costo directo')); const x = td('', 'ej-num', 'Diferencia'); x.append(ejPrDif(cd - cd0)); tr.append(x); }
    else tr.append(td(ejPesos(cd), 'ej-num ej-pr-sub', 'Costo directo'));
    const ir = () => { pr.mostrar = p.code; pr.tab = 'todo'; pr.q = ''; ejPrPintar(); };
    tr.addEventListener('click', ir);
    tr.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); ir(); } });
    tbody.append(tr);
  });
  tabla.append(thead, tbody);
  w.append(tabla);
}
function ejPrAgregar() {
  const c = ejPrCtx();
  const pr = ej.pr;
  if (!c || !pr.b) return;
  const cat = pr.tab !== 'todo' && pr.tab !== 'part' ? pr.tab : 'Materiales';
  const id = ejNuevoId('prn-');
  pr.b.items.push({ id, code: '', d: '', cat, partida: pr.mostrar || (c.base.partidas[0] || {}).code || '', unidad: cat === 'Mano de Obra' ? 'DH' : 'Un.',
    q0: null, p0: null, q: 1, p: 0, quitado: false, nuevo: true });
  pr.orden = ''; pr.q = ''; pr.solo = false;
  ejPrPintar();
  const x = $('#dlgEjPres').querySelector('[data-foco="pr-d-' + id + '"]');
  if (x) { x.focus(); x.scrollIntoView({ block: 'nearest' }); }
}
// El cierre: costo directo, gastos generales e imprevistos (su % se cambia), costo total, venta (se cambia) y utilidad
function ejPrCierreEl(c, w) {
  const pr = ej.pr;
  const ed = !!pr.b;
  const o = ejPrCuentas(c.base.items, c.base.gg0, c.base.venta0);
  const a = ed ? ejPrCuentas(pr.b.items, pr.b.gg, ejPrVenta(c)) : o;
  const tabla = crear('table', 'ej-pr-t ej-pr-cierre-t');
  if (ed) {
    const trh = crear('tr');
    trh.append(crear('th'), ejPrTh('Original', null, true), ejPrTh('Actualizado', null, true), ejPrTh('Diferencia', null, true));
    const th = crear('thead');
    th.append(trh);
    tabla.append(th);
  }
  const tbody = crear('tbody');
  const fila = (et, k, cls, campo, bueno) => {
    const tr = crear('tr', cls || null);
    const e = crear('td');
    e.append(et);
    tr.append(e);
    if (ed) {
      tr.append(crear('td', 'ej-num ej-pr-mu', o[k] === null ? '—' : ejPesos(o[k])));
      const v = crear('td', 'ej-num');
      v.append(campo || document.createTextNode(a[k] === null ? '—' : ejPesos(a[k])));
      const d = crear('td', 'ej-num');
      if (a[k] !== null && o[k] !== null) { const s = ejPrDif(a[k] - o[k]); if (bueno && s.className) s.className = s.className === 'pos' ? 'neg' : 'pos'; d.append(s); }
      tr.append(v, d);
    } else tr.append(crear('td', 'ej-num', a[k] === null ? '—' : ejPesos(a[k])));
    tbody.append(tr);
  };
  const caja = (valor, foco, etiqueta, al) => {
    const x = crear('input', 'ej-pr-in');
    x.type = 'text'; x.inputMode = 'decimal'; x.autocomplete = 'off';
    x.setAttribute('data-num', '');
    x.value = String(Math.round(valor * 100) / 100);
    x.dataset.foco = foco;
    x.setAttribute('aria-label', etiqueta);
    x.addEventListener('change', () => { const n = ejNumero(x.value); if (n === null || n < 0) { x.value = ejCantidad(valor); return; } al(n); ejPrPintar(); });
    return x;
  };
  const gg = ed ? pr.b.gg : c.base.gg0;
  const etGG = crear('span', 'ej-pr-gg');
  etGG.append(document.createTextNode('Gastos generales e imprevistos · '));
  if (ed) {
    const x = caja(Math.round(gg * 100) / 100, 'pr-gg', 'Porcentaje de gastos generales e imprevistos', (n) => { pr.b.gg = Math.min(100, n); });
    if (Math.abs(gg - c.base.gg0) > 1e-9) x.classList.add('mod');
    etGG.append(x, document.createTextNode(' %'));
  } else etGG.append(document.createTextNode((Math.round(gg * 100) / 100).toLocaleString('es-CL') + ' %'));
  fila(document.createTextNode('Costo directo'), 'cd');
  fila(etGG, 'ggm');
  fila(document.createTextNode('Costo total'), 'costo', 'ej-pr-tot');
  // La venta: la de su formulación; en una versión se cambia (un adicional, un descuento) o se toma la de la página
  const etV = crear('span', 'ej-pr-gg');
  etV.append(document.createTextNode('Venta neta'), info('En el original, el precio neto de su formulación. En un presupuesto actualizado se puede cambiar, por ejemplo por un adicional aprobado o un descuento.', 'Qué venta es'));
  let campoV = null;
  if (ed) {
    campoV = caja(ejPrVenta(c), 'pr-venta', 'Venta neta del presupuesto actualizado', (n) => { pr.b.venta = n > 0 && Math.abs(n - c.base.venta0) >= 0.5 ? n : null; });
    if (pr.b.venta) campoV.classList.add('mod');
    const vp = c.m.venta ? c.m.venta.monto : null;
    if (vp && Math.abs(vp - ejPrVenta(c)) >= 0.5) {
      const b = crear('button', 'ej-pr-usar', 'Usar la de la página: ' + ejPesos(vp));
      b.type = 'button';
      b.title = c.m.venta.fuente;
      b.dataset.foco = 'pr-venta-pagina';
      b.addEventListener('click', () => { pr.b.venta = Math.abs(vp - c.base.venta0) >= 0.5 ? vp : null; ejPrPintar(); });
      etV.append(b);
    }
  }
  fila(etV, 'venta', null, campoV, true);
  fila(document.createTextNode('Utilidad · margen ' + ejPct(a.margen)), 'util', null, null, true);
  tabla.append(tbody);
  w.append(tabla);
}
// Abajo, fijo: usarlo en «Cómo va el proyecto», si hay cambios sin guardar, eliminar, descartar y guardar
function ejPrAccEl(c) {
  const pr = ej.pr;
  const acc = $('#ejPrAcc');
  acc.textContent = '';
  if (!pr.b) {
    acc.append(crear('span', 'ej-pr-estado', 'El presupuesto de su formulación, tal como se vendió.'));
    const b = crear('button', 'cx-enlace', 'Cerrar');
    b.type = 'button';
    b.addEventListener('click', () => $('#dlgEjPres').close());
    acc.append(b);
    return;
  }
  const l = crear('label', 'ej-pr-usa');
  const cb = crear('input');
  cb.type = 'checkbox'; cb.checked = pr.b.seguimiento; cb.dataset.foco = 'pr-seg';
  cb.addEventListener('change', () => { pr.b.seguimiento = cb.checked; ejPrPintar(); });
  l.append(cb, document.createTextNode('Usar en «Cómo va el proyecto»'), info('Si lo marcas, lo presupuestado de cada categoría y la venta de la página salen de este presupuesto actualizado; si no, del original. Solo uno a la vez.', 'Qué cambia'));
  const sucio = ejPrSucio();
  const n = pr.b.items.filter((i) => ejPrEstado(i)).length + (Math.abs(pr.b.gg - c.base.gg0) > 1e-9 ? 1 : 0) + (pr.b.venta ? 1 : 0);
  const est = crear('span', 'ej-pr-estado');
  est.append(crear('b', null, pl(n, 'cambio', 'cambios')), document.createTextNode(' respecto del original · ' + (sucio ? 'sin guardar' : 'guardado')));
  if (sucio) est.classList.add('sucio');
  acc.append(l, est);
  if (pr.b.guardada) {
    const del = crear('button', 'cx-enlace ej-borrar', 'Eliminar');
    del.type = 'button';
    del.addEventListener('click', ejPrEliminar);
    acc.append(del);
  }
  const des = crear('button', 'cx-enlace', 'Descartar');
  des.type = 'button';
  des.disabled = !sucio;
  des.addEventListener('click', () => { if (pr.b.guardada) ejPrElegir(pr.b.id); else ejPrElegir(c.vs.length ? c.vs[c.vs.length - 1].id : 'o'); });
  const ok = crear('button', 'btn-pri', 'Guardar');
  ok.type = 'button';
  ok.disabled = !sucio;
  ok.addEventListener('click', ejPrGuardar);
  acc.append(des, ok);
}
function ejPrGuardar() {
  const c = ejPrCtx();
  const pr = ej.pr;
  if (!c || !pr.b) return;
  if (!rc.dir) { avisar('Conecta la carpeta de Intercambio para guardar el presupuesto.'); return; }
  const sin = pr.b.items.find((i) => i.nuevo && !texto(i.d).trim());
  if (sin) {
    avisar('Escribe la descripción del costo nuevo antes de guardar.');
    pr.tab = 'todo'; pr.q = ''; pr.solo = false; pr.mostrar = '';
    ejPrPintar();
    const x = $('#dlgEjPres').querySelector('[data-foco="pr-d-' + sin.id + '"]');
    if (x) x.focus();
    return;
  }
  const cosa = ejPrCosa(c.t, pr.b, c.base);
  const cambios = [cosa];
  // Uno a la vez en «Cómo va el proyecto»
  if (cosa.seguimiento) c.vs.filter((v) => v.id !== cosa.id && v.seguimiento).forEach((v) => cambios.push(ejPrCosa(c.t, { id: v.id, nombre: v.nombre, items: ejPrAplicar(c.base, v), gg: v.gg !== null ? v.gg : c.base.gg0, venta: v.venta, seguimiento: false, creado: v.creado }, c.base)));
  pr.b.guardada = true;
  ejPoner(cambios, '«' + cosa.nombre + '» guardado. El original sigue igual.');
  const c2 = ejPrCtx();
  if (!c2) return;
  const v = c2.vs.find((x) => x.id === cosa.id);
  if (v) pr.b.creado = v.creado;
  pr.guardado = JSON.stringify(ejPrCosa(c2.t, pr.b, c2.base));
  ejPrPintar();
}
function ejPrEliminar() {
  const c = ejPrCtx();
  const pr = ej.pr;
  if (!c || !pr.b || !pr.b.guardada) return;
  if (!confirm('¿Eliminar «' + pr.b.nombre + '»? El original no cambia.')) return;
  const v = c.vs.find((x) => x.id === pr.b.id);
  if (!v) return;
  ejPoner([{ id: v.id, proyecto: v.proyecto, tipo: 'presupuesto', creado: v.creado, borrado: true }], 'Se eliminó «' + v.nombre + '».');
  ejPrElegir('o');
}
// ---- Las compras y cotizaciones ------------------------------------------------------------------------------------
/* En bloques: una compra sola, o las cotizaciones para lo mismo (su grupo) juntas, de la más barata a la más cara. Los
   bloques, del más nuevo al más antiguo (por cuándo se anotaron: cambiar uno no lo mueve de lugar). */
function ejBloques(costos) {
  const por = new Map();
  costos.forEach((it) => { const k = it.grupo || it.id; if (!por.has(k)) por.set(k, []); por.get(k).push(it); });
  return [...por.values()].map((xs) => xs.sort((a, b) => a.cantidad * a.precio - b.cantidad * b.precio || a.creado.localeCompare(b.creado)))
    .sort((a, b) => Math.min(...b.map((x) => Date.parse(x.creado))) - Math.min(...a.map((x) => Date.parse(x.creado))));
}
function ejComprasEl(m) {
  const items = ejItems(m.costos);
  const { s } = ejPanel('Gastos proyectados y cotizaciones', items.length ? pl(items.length, 'anotado', 'anotados') : '',
    'Anota cada ítem que se espera comprar, con la cotización de uno o varios proveedores: en la columna Proveedor se comparan y se elige uno. Se contrasta con lo presupuestado y con lo que QUEMPIN ha pagado, y lo marcado en «Simular» cambia al tiro el costo estimado, el margen y los indicadores. No es un costo real: al Centro de Costos solo llegan las facturas y las órdenes de compra.');
  s.classList.add('ej-compras');
  s.id = 'ejSecGastos';
  const barra = crear('div', 'ej-barra-compras');
  const agregar = ejBoton('Agregar gasto o cotización', 'cx-boton', () => ejAbrirCosto(null), 'mas');
  agregar.disabled = !rc.dir;
  agregar.dataset.foco = 'agregar';
  const pegar = ejBoton('Pegar una cotización', 'cx-enlace', ejAbrirPegar, 'copiar');
  pegar.disabled = !rc.dir;
  pegar.dataset.foco = 'pegar';
  barra.append(agregar, pegar);
  const filtros = crear('div', 'ej-filtros');
  filtros.setAttribute('role', 'group');
  filtros.setAttribute('aria-label', 'Qué compras mostrar');
  EJ_FILTROS.forEach((f) => {
    const n = items.filter((x) => f.es(x.it)).length;
    if (f.id !== 'vigentes' && f.id !== 'todas' && !n) return;
    const b = crear('button', 'ej-filtro', f.nombre + ' (' + n + ')');
    b.type = 'button';
    b.dataset.foco = 'filtro-' + f.id;
    b.setAttribute('aria-pressed', ej.filtro === f.id ? 'true' : 'false');
    b.addEventListener('click', () => { ej.filtro = f.id; ejGuardarPrefs(); ejPintar(); });
    filtros.append(b);
  });
  if (m.costos.length) barra.append(filtros);
  s.append(barra);
  // Vuelta 8 del loop de UX (2026-11-09): las compras por estado en una barra, con cuánto suma cada uno; tocar uno filtra
  const vivos = items.filter((x) => x.it.estado !== 'descartada');
  if (vivos.length) {
    const montoDe = (x) => (Number(x.it.cantidad) || 0) * (Number(x.it.precio) || 0);
    const grupos = [['evaluar', 'Por decidir', 'vigentes'], ['aprobada', 'Aprobadas', 'vigentes'], ['comprada', 'Compradas', 'compradas']]
      .map(([id, nombre, filtro]) => { const xs = vivos.filter((x) => x.it.estado === id); return { id, nombre, filtro, n: xs.length, monto: xs.reduce((a, x) => a + montoDe(x), 0) }; });
    const total = grupos.reduce((a, g) => a + g.monto, 0) || 1;
    const emb = crear('div', 'ej-embudo');
    const barraE = crear('div', 'ej-embudo-barra');
    barraE.setAttribute('aria-hidden', 'true');
    const ley = crear('div', 'ej-embudo-ley');
    grupos.forEach((g) => {
      if (g.n) { const x = crear('span', 'ej-embudo-seg'); x.dataset.estado = g.id; x.style.flexGrow = String(Math.max(g.monto / total, 0.04)); x.title = g.nombre + ': ' + ejPesos(g.monto); barraE.append(x); }
      const b = crear('button', 'ej-embudo-et');
      b.type = 'button';
      b.dataset.estado = g.id;
      b.disabled = !g.n;
      b.append(crear('i'), crear('span', null, g.nombre), crear('b', null, g.n ? ejPesos(g.monto) : '—'), crear('small', null, g.n ? '(' + g.n + ')' : ''));
      b.title = g.n ? 'Mostrar ' + g.nombre.toLowerCase() : 'No hay ' + g.nombre.toLowerCase();
      b.addEventListener('click', () => { ej.filtro = g.filtro; ejGuardarPrefs(); ejPintar(); });
      ley.append(b);
    });
    emb.append(barraE, ley);
    s.append(emb);
  }
  // Lo simulado, en una línea: cuánto suma y cómo mueve el margen
  const simuladas = m.costos.filter((it) => ejCuentaComo(it, m.folios) === 'q');
  const porDecidir = m.costos.filter((it) => it.estado === 'evaluar');
  if (m.costos.length) {
    const p = crear('p', 'ej-sim');
    if (simuladas.length) {
      p.append(document.createTextNode('Simulando ' + pl(simuladas.length, 'gasto', 'gastos') + ' por '), crear('b', null, ejPesos(m.tot.Q)), document.createTextNode(': '));
      if (Math.abs(m.tot.EAC - m.tot.EAC0) < 0.5) {
        p.append(document.createTextNode('cabe en lo presupuestado, así que el costo estimado al cierre no cambia' + (m.margen !== null ? ' y el margen sigue en ' + ejPct(m.margen) : '') + '.'));
      } else if (m.margen !== null && m.margen0 !== null) {
        p.append(document.createTextNode('el margen estimado pasa de ' + ejPct(m.margen0) + ' a '), crear('b', null, ejPct(m.margen)),
          document.createTextNode(' (el costo estimado sube ' + ejPesos(m.tot.EAC - m.tot.EAC0) + ').'));
      } else p.append(document.createTextNode('el costo estimado pasa de ' + ejPesos(m.tot.EAC0) + ' a '), crear('b', null, ejPesos(m.tot.EAC)), document.createTextNode('.'));
    } else p.append(document.createTextNode('Nada simulado.'));
    if (porDecidir.length) {
      const todas = crear('button', 'cx-desmarcar', 'Simular todas las por decidir');
      todas.type = 'button';
      todas.dataset.foco = 'sim-todas';
      todas.disabled = !rc.dir;
      todas.addEventListener('click', () => ejSimularTodas(m, true));
      p.append(todas);
    }
    if (simuladas.length) {
      const ninguna = crear('button', 'cx-desmarcar', 'No simular ninguna');
      ninguna.type = 'button';
      ninguna.dataset.foco = 'sim-ninguna';
      ninguna.disabled = !rc.dir;
      ninguna.addEventListener('click', () => ejSimularTodas(m, false));
      p.append(ninguna);
    }
    s.append(p);
  }
  const filtro = EJ_FILTROS.find((f) => f.id === ej.filtro) || EJ_FILTROS[0];
  const visibles = items.filter((x) => filtro.es(x.it));
  if (!m.costos.length) {
    s.append(crear('p', 'ej-nada', 'Sin gastos ni cotizaciones todavía.'));
    return s;
  }
  if (!visibles.length) { s.append(crear('p', 'ej-nada', 'Nada en «' + filtro.nombre + '».')); return s; }
  const tabla = crear('table', 'ej-tabla');
  const thead = crear('thead');
  const trh = crear('tr');
  [['Simular', ''], ['Qué se compra', ''], ['Proveedor', ''], ['Cantidad', 'ej-num'], ['Precio unit.', 'ej-num'], ['Total', 'ej-num'], ['Evaluación', ''], ['Estado', ''], ['', '']].forEach(([x, c]) => {
    const th = crear('th', c, x);
    th.scope = 'col';
    trh.append(th);
  });
  trh.lastChild.append(crear('span', 'sr', 'Acciones'));
  thead.append(trh);
  const tbody = crear('tbody');
  visibles.forEach((x) => tbody.append(ejFilaEl(x.it, x.xs, m)));
  const tfoot = crear('tfoot');
  const trf = crear('tr');
  const t1 = crear('td', null, 'Lo simulado suma');
  t1.colSpan = 5;
  const t2 = crear('td', 'ej-num', ejPesos(m.tot.Q));
  const t3 = crear('td');
  t3.colSpan = 3;
  if (m.tot.C - m.base.reduce((a, b) => a + b.Coc, 0) > 0.5) t3.textContent = 'y lo comprado sin OC a la vista, ' + ejPesos(m.tot.C - m.base.reduce((a, b) => a + b.Coc, 0)) + ' comprometidos';
  trf.append(t1, t2, t3);
  tfoot.append(trf);
  tabla.append(thead, tbody, tfoot);
  s.append(tabla);
  return s;
}
// Una fila por ítem, con los datos de su proveedor elegido. clave: no cambia al elegir otro, para que el foco siga ahí.
function ejFilaEl(it, xs, m) {
  const como = ejCuentaComo(it, m.folios);
  const ev = ejEvaluar(it, m);
  const fuera = it.estado === 'descartada' || (it.estado === 'comprada' && !como);
  const clave = it.grupo || it.id;
  const tr = crear('tr', [fuera ? 'fuera' : '', xs.some((x) => ej.recien.has(x.id)) ? 'recien' : ''].filter(Boolean).join(' '));
  tr.dataset.id = it.id;
  tr.dataset.item = clave;
  // Simular
  const tdS = crear('td', 'ej-c-sim');
  const cb = crear('input');
  cb.type = 'checkbox';
  cb.checked = como !== '';
  cb.disabled = !rc.dir || it.estado === 'comprada' || it.estado === 'descartada';
  cb.dataset.foco = 'sim-' + clave;
  cb.setAttribute('aria-label', 'Simular la compra de ' + it.descripcion);
  cb.title = it.estado === 'comprada' ? (como ? 'Comprada: cuenta como comprometida hasta que su OC ' + it.oc + ' aparezca en Sistema QUEMPIN' : 'Comprada: la cuenta su orden de compra o, sin OC, su factura en el Centro de Costos')
    : it.estado === 'descartada' ? 'Descartada: no cuenta' : 'Contarla en el costo estimado y el margen de arriba';
  cb.addEventListener('change', () => ejSimularItem(it, cb.checked));
  tdS.append(cb);
  // Qué se compra: abre el ítem con sus proveedores
  const tdQ = crear('td', 'ej-c-que');
  const q = crear('button', 'ej-c-desc');
  q.type = 'button';
  q.dataset.foco = 'abrir-' + clave;
  q.append(crear('b', null, it.descripcion));
  q.append(crear('span', null, [EJ_CAT.get(it.categoria).nombre, it.cotizacion ? 'cot. ' + it.cotizacion : '', it.fecha ? ejFechaCorta(it.fecha) : '',
    it.estado === 'comprada' && it.oc ? 'OC ' + it.oc : ''].filter(Boolean).join(' · ')));
  if (it.nota) q.append(crear('span', null, it.nota));
  const fx = ejFacturadoEl(it, m);
  if (fx) q.append(fx);
  q.title = 'Ver o cambiar este ítem y sus proveedores';
  q.addEventListener('click', () => ejAbrirCosto(it));
  tdQ.append(q);
  // Una OC de Sistema QUEMPIN que parece ser esta compra, con cualquiera de sus proveedores (mismo proveedor y monto): marcarla comprada con un toque
  const conOC = it.estado === 'aprobada' || it.estado === 'evaluar' ? [it].concat(xs.filter((x) => x !== it)).map((x) => ({ x, oc: ejOCParecida(x, m) })).find((c) => c.oc) : null;
  if (conOC) {
    const sug = crear('div', 'ej-sugerida');
    sug.append(document.createTextNode('¿Es la OC ' + conOC.oc.folio + ' (' + ejPesos(conOC.oc.neto) + ')' + (conOC.x !== it && conOC.x.proveedor ? ', de ' + conOC.x.proveedor : '') + '? '));
    const b = crear('button', null, 'Marcar comprada');
    b.type = 'button';
    b.addEventListener('click', () => ejCambiarEstado(Object.assign({}, conOC.x, { oc: conOC.oc.folio }), 'comprada', m));
    sug.append(b);
    tdQ.append(sug);
  }
  // Proveedor: cada cotización con su valor
  const tdPr = crear('td', 'ej-c-prov');
  tdPr.append(ejMenuProveedor(it, xs, clave));
  if (xs.length > 1) tdPr.append(crear('small', 'ej-prov-nota', ejNotaProveedor(it, xs)));
  const tdC = crear('td', 'ej-c-cant ej-num', ejCantidad(it.cantidad) + (it.unidad ? ' ' + it.unidad : ''));
  const tdP = crear('td', 'ej-c-pu ej-num', ejPesos(it.precio));
  const tdT = crear('td', 'ej-c-tot ej-num', ejPesos(ev.total));
  tdT.dataset.detalle = ejCantidad(it.cantidad) + (it.unidad ? ' ' + it.unidad : '') + ' × ' + ejPesos(it.precio);
  // Evaluación: el veredicto; el detalle, en el ítem
  const tdE = crear('td', 'ej-c-eval');
  const chip = crear('button', 'ej-eval-chip', ev.corto);
  chip.type = 'button';
  if (ev.nivel) chip.dataset.nivel = ev.nivel;
  chip.title = ev.puntos.length ? ev.puntos.map((p) => '• ' + p.texto).join('\n') : 'Sin presupuesto, precio histórico ni venta con que compararla.';
  chip.setAttribute('aria-label', 'Evaluación: ' + ev.corto + '. Ver el detalle');
  chip.addEventListener('click', () => ejAbrirCosto(it));
  tdE.append(chip);
  // Estado
  const tdEs = crear('td', 'ej-c-est');
  const sel = crear('select', 'ej-estado');
  sel.setAttribute('aria-label', 'Estado de ' + it.descripcion);
  sel.dataset.foco = 'estado-' + clave;
  sel.disabled = !rc.dir;
  EJ_ESTADOS.forEach((e) => { const o = crear('option', null, e.nombre); o.value = e.id; o.selected = e.id === it.estado; sel.append(o); });
  sel.addEventListener('change', () => { const est = sel.value; sel.value = it.estado; ejCambiarEstado(it, est, m); });
  tdEs.append(sel);
  // Eliminar el ítem
  const tdA = crear('td', 'ej-c-acc');
  const acc = crear('div', 'ej-acc');
  const borrar = crear('button', 'ej-ico');
  borrar.type = 'button';
  borrar.append(icono('basurero', 16));
  borrar.title = xs.length > 1 ? 'Eliminar este ítem, con sus ' + xs.length + ' proveedores' : 'Eliminar este ítem';
  borrar.setAttribute('aria-label', 'Eliminar ' + it.descripcion);
  borrar.disabled = !rc.dir;
  borrar.addEventListener('click', () => ejBorrarItem(it, xs));
  acc.append(borrar);
  tdA.append(acc);
  tr.append(tdS, tdQ, tdPr, tdC, tdP, tdT, tdE, tdEs, tdA);
  return tr;
}
// El menú de la columna Proveedor: cada cotización del ítem con su valor, de la más barata a la más cara, y agregar otra
function ejMenuProveedor(it, xs, clave) {
  const sel = crear('select', 'ej-prov');
  sel.setAttribute('aria-label', 'Proveedor de ' + it.descripcion);
  sel.dataset.foco = 'prov-' + clave;
  sel.disabled = !rc.dir || it.estado === 'comprada';
  xs.forEach((x) => { const o = crear('option', null, (x.proveedor || 'Sin proveedor') + ' · ' + ejPesos(x.precio)); o.value = x.id; sel.append(o); });
  const otro = crear('option', null, '+ Agregar otro proveedor…');
  otro.value = '';
  sel.append(otro);
  sel.value = it.id;
  sel.title = it.estado === 'comprada' ? 'Ya comprada: para elegir otro proveedor, cambia primero su estado' : xs.map((x) => (x.proveedor || 'Sin proveedor') + ': ' + ejPesos(x.precio)).join('\n');
  sel.addEventListener('change', () => {
    const id = sel.value;
    sel.value = it.id;
    if (id) ejElegirProveedor(it, xs.find((x) => x.id === id)); else ejAbrirCosto(it, { otro: true });
  });
  return sel;
}
// Bajo el menú: cuántos proveedores hay y, si el elegido no es el más barato, cuánto se ahorraría con el que lo es
function ejNotaProveedor(it, xs) {
  const n = pl(xs.length, 'proveedor', 'proveedores');
  const mejor = xs.find((x) => x.precio > 0);
  if (!mejor || !(it.precio > 0)) return n;
  const dif = it.cantidad * it.precio - mejor.cantidad * mejor.precio;
  return n + ' · ' + (dif < 0.5 ? 'el más barato' : (mejor.proveedor || 'Otro') + ', ' + ejPesos(dif) + ' menos');
}
function ejBorrarItem(it, xs) {
  ejPoner(xs.map((x) => ({ id: x.id, proyecto: x.proyecto, tipo: 'costo', creado: x.creado, borrado: true })), 'Se eliminó «' + it.descripcion + '».');
}
// Una OC del proyecto sin compra anotada, del mismo proveedor (o sin decirlo) y con el mismo neto (±2 %, como el Centro de Costos)
function ejOCParecida(it, m) {
  const total = it.cantidad * it.precio;
  if (!(total > 0)) return null;
  const ligadas = new Set(m.costos.map((x) => x.oc).filter(Boolean));
  return m.ocs.find((o) => !ligadas.has(o.folio) && o.moneda === 'CLP' && Math.abs(o.neto - total) <= 0.02 * total
    && (!it.proveedor || !o.proveedor || ejParecido(it.proveedor, o.proveedor) >= 0.5)) || null;
}
// Marcar o no «Simular»: entre los proveedores de un ítem, uno a la vez, y ese queda como el elegido
function ejSimularItem(it, si) {
  const otras = ej.modelo ? ejHermanas(it, ej.modelo.costos) : [];
  const cambios = [Object.assign({}, it, { simular: si }, otras.length ? { elegida: true } : null)];
  otras.filter((x) => x.elegida || (si && x.simular && (x.estado === 'evaluar' || x.estado === 'aprobada'))).forEach((x) => cambios.push(Object.assign({}, x, { simular: false, elegida: false })));
  ejPoner(cambios);
}
// Elegir otro proveedor en el menú: toma el estado y el «Simular» del que estaba, que sigue en el menú como alternativa
function ejElegirProveedor(it, nueva) {
  if (!nueva || nueva.id === it.id) return;
  ejPoner([Object.assign({}, nueva, { estado: it.estado, simular: it.simular, elegida: true }),
    Object.assign({}, it, { estado: ejEstadoOtra(it.estado), simular: false, elegida: false })],
    '«' + it.descripcion + '»: se elige ' + (nueva.proveedor || 'la cotización sin proveedor') + ', ' + ejPesos(nueva.precio) + ' c/u.');
}
// Todas las por decidir a la vez; de cada ítem con varios proveedores, el elegido o, si no, el más barato
function ejSimularTodas(m, si) {
  const cambios = [];
  const vistos = new Set();
  m.costos.filter((it) => it.estado === 'evaluar' || it.estado === 'aprobada').forEach((it) => {
    if (!si) { if (it.simular) cambios.push(Object.assign({}, it, { simular: false })); return; }
    if (it.estado !== 'evaluar' || vistos.has(it.grupo || it.id)) return;
    const rivales = [it].concat(ejHermanas(it, m.costos)).filter((x) => x.estado === 'evaluar' || x.estado === 'aprobada');
    vistos.add(it.grupo || it.id);
    if (rivales.some((x) => x.estado === 'aprobada')) return;      // ya se eligió una: queda esa
    const mejor = rivales.find((x) => x.elegida) || rivales.reduce((a, x) => (x.cantidad * x.precio < a.cantidad * a.precio ? x : a));
    rivales.forEach((x) => { if (x.simular !== (x === mejor)) cambios.push(Object.assign({}, x, { simular: x === mejor })); });
  });
  if (!cambios.length) return;
  ejPoner(cambios, si ? 'Se simulan las compras por decidir (de cada ítem con varios proveedores, el elegido o el más barato).' : 'Nada simulado.');
}
/* Cambiar el estado de un ítem, en su proveedor elegido: aprobarlo, comprarlo o descartarlo deja descartados a los demás, y
   volver a «por decidir» los trae de vuelta. Comprar pide el N° de su orden de compra (con ella el Centro de Costos la trae
   como costo). */
function ejCambiarEstado(it, est, m) {
  if (est === it.estado) return;
  if (est === 'comprada' && !it.oc) { ejAbrirCosto(it, { estado: 'comprada' }); return; }
  const hermanas = m ? ejHermanas(it, m.costos) : [];
  const cambios = [Object.assign({}, it, { estado: est, simular: est === 'aprobada' ? true : est === 'evaluar' ? it.simular : false }, hermanas.length ? { elegida: true } : null)];
  let msg = '«' + it.descripcion + '»: ' + EJ_ESTADOS.find((e) => e.id === est).nombre.toLowerCase() + (est === 'comprada' ? ' con la OC ' + it.oc : '') + '.';
  const otras = hermanas.filter((x) => x.estado !== 'comprada' && (x.estado !== ejEstadoOtra(est) || x.elegida));
  otras.forEach((x) => cambios.push(Object.assign({}, x, { estado: ejEstadoOtra(est), simular: false, elegida: false })));
  if (est !== 'evaluar' && otras.length) msg += otras.length === 1 ? ' El otro proveedor queda descartado.' : ' Los otros ' + otras.length + ' proveedores quedan descartados.';
  ejPoner(cambios, msg);
}

// ---- Las facturas del Centro de Costos y a qué gastos corresponden (2026-11-06) ------------------------------------
/* Pedido del usuario: ver en cada proyecto los costos registrados en el Centro de Costos y asociar cada factura a uno o
   varios de sus gastos proyectados y cotizados. Una asociación es una cosa del archivo por factura (tipo 'asociacion',
   su N° Ref. y sus destinos: los ítems, 'i:<grupo o id>', y las líneas del presupuesto de su formulación, 'l:<uid>').
   Lo facturado de un ítem ya está en lo gastado: de él se simula o compromete solo lo que falta facturar. */
const EJ_DOCS_FILTROS = [
  { id: 'todas', nombre: 'Todas', es: () => true },
  { id: 'sin', nombre: 'Sin asociar', es: (d, a) => !a },
  { id: 'con', nombre: 'Asociadas', es: (d, a) => !!a }
];
const EJ_DOCS_MAX = 12;
const ejIdAsoc = (t, ref) => ('as-' + ejSlugClave(ejClave(t)) + '-' + ref.toLowerCase()).slice(0, 40);
// Los destinos que se pueden elegir: los ítems (no descartados) y las líneas del presupuesto de su formulación
function ejDestinos(m) {
  const out = [];
  ejItems(m.costos).forEach(({ it, xs }) => {
    if (xs.every((x) => x.estado === 'descartada')) return;
    out.push({ k: ejKeyItem(it), tipo: 'item', nombre: it.descripcion, it, xs, monto: it.cantidad * it.precio, cat: it.categoria,
      sub: [EJ_CAT.get(it.categoria).nombre, it.proveedor, (EJ_ESTADOS.find((e) => e.id === it.estado) || {}).nombre].filter(Boolean).join(' · ') });
  });
  m.lineas.filter((l) => l.cat !== 'Mano de Obra').forEach((l) => out.push({ k: 'l:' + l.uid, tipo: 'linea', nombre: l.descripcion, l, monto: l.subtotal, cat: l.cat,
    sub: [l.code, l.partida, EJ_CAT.get(l.cat).nombre].filter(Boolean).join(' · ') }));
  return out;
}
// Los destinos de una factura que todavía existen (un ítem borrado ya no cuenta)
function ejDestinosDe(m, ref, todos) {
  const a = m.asoc.get(ref);
  if (!a || !a.destinos.length) return [];
  const por = new Map((todos || ejDestinos(m)).map((d) => [d.k, d]));
  return a.destinos.map((k) => por.get(k)).filter(Boolean);
}
const ejDocNombre = (d) => [d.tipo || 'Documento', d.numero ? 'N° ' + d.numero : ''].filter(Boolean).join(' ');
function ejDocumentosEl(m) {
  const docs = m.docs;
  const total = docs ? docs.reduce((a, d) => a + d.neto, 0) : 0;
  const { s, cab } = ejPanel('Facturas del Centro de Costos', docs && docs.length ? pl(docs.length, 'documento', 'documentos') + ' · ' + ejPesos(total) : '',
    'Las facturas, boletas, notas de crédito y órdenes de compra registradas en el Centro de Costos con su TAG, sin IVA. Asocia cada una a los gastos proyectados o cotizados y a las líneas del presupuesto a que corresponde: '
    + 'así se ve cuánto se lleva facturado de cada uno y lo que ya se facturó deja de simularse. Si una factura es de varios gastos, su monto se reparte según lo cotizado o presupuestado de cada uno.'
    + (ej.docs && ej.docs.actualizado ? ' Centro de Costos al ' + ej.docs.actualizado + '.' : ''));
  s.id = 'ejSecFacturas';
  s.classList.add('ej-facturas');
  const fw = rcFacturasWeb(m.t);
  if (fw) { const b = ejBoton('Abrir la carpeta', 'cx-enlace', () => window.open(fw, '_blank', 'noopener'), 'fuera'); b.title = 'Su carpeta del Centro de Costos en SharePoint'; cab.append(b); }
  if (docs === null) { s.append(lineaInfo('ej-nada', 'Las facturas todavía no llegan a la carpeta del equipo.', 'Las publica el procesador desde el Centro de Costos en su próxima vuelta (cada 5 minutos). Mientras, lo gastado sale del Análisis Financiero.', 'Cuándo llegan')); return s; }
  if (!docs.length) { s.append(crear('p', 'ej-nada', 'Sin documentos registrados con su TAG en el Centro de Costos.')); return s; }
  const todos = ejDestinos(m);
  const asociada = (d) => ejDestinosDe(m, d.ref, todos).length > 0 || !!(m.asoc.get(d.ref) && !m.asoc.get(d.ref).destinos.length);
  // Vuelta 8 del loop de UX (2026-11-09): cuánto de lo facturado ya dice a qué gasto corresponde, en una barra
  const asoc = docs.filter(asociada);
  const montoA = asoc.reduce((a, d) => a + Math.max(0, d.neto), 0), montoT = docs.reduce((a, d) => a + Math.max(0, d.neto), 0) || 1;
  const prog = crear('div', 'ej-prog');
  const pt = crear('div', 'ej-prog-txt');
  pt.append(crear('b', null, asoc.length === docs.length ? 'Todas asociadas' : pl(asoc.length, 'asociada', 'asociadas') + ' de ' + docs.length),
    crear('span', null, ejPesos(montoA) + ' de ' + ejPesos(montoT)));
  prog.append(pt, ejMini([['', montoA / montoT], ['falta', (montoT - montoA) / montoT]], [], null, 'Lo facturado que ya está asociado (oscuro) y lo que falta (rayado)'));
  s.append(prog);
  // Filtros y búsqueda (la búsqueda solo esconde filas: no repinta, para no perder lo escrito)
  const barra = crear('div', 'ej-barra-compras');
  const filtros = crear('div', 'ej-filtros');
  filtros.setAttribute('role', 'group');
  filtros.setAttribute('aria-label', 'Qué facturas mostrar');
  EJ_DOCS_FILTROS.forEach((f) => {
    const n = docs.filter((d) => f.es(d, asociada(d))).length;
    const b = crear('button', 'ej-filtro', f.nombre + ' (' + n + ')');
    b.type = 'button';
    b.dataset.foco = 'docs-' + f.id;
    b.setAttribute('aria-pressed', ej.docsFiltro === f.id ? 'true' : 'false');
    b.addEventListener('click', () => { ej.docsFiltro = f.id; ejPintar(); });
    filtros.append(b);
  });
  const bus = crear('input', 'ej-docs-buscar');
  bus.type = 'search'; bus.id = 'ejDocBuscar'; bus.autocomplete = 'off'; bus.placeholder = 'Buscar proveedor, ítem o N° Ref.';
  bus.setAttribute('aria-label', 'Buscar entre las facturas del proyecto');
  bus.value = ej.docsQ;
  barra.append(bus, filtros);
  s.append(barra);
  const filtro = EJ_DOCS_FILTROS.find((f) => f.id === ej.docsFiltro) || EJ_DOCS_FILTROS[0];
  const visibles = docs.filter((d) => filtro.es(d, asociada(d)));
  const tabla = crear('table', 'ej-tabla ej-docs');
  const thead = crear('thead');
  const trh = crear('tr');
  [['Fecha', ''], ['Documento', ''], ['Proveedor y detalle', ''], ['Neto', 'ej-num'], ['Corresponde a', '']].forEach(([x, c]) => { const th = crear('th', c, x); th.scope = 'col'; trh.append(th); });
  thead.append(trh);
  const tbody = crear('tbody');
  const max = ej.todosDocs || ej.docsQ ? visibles.length : EJ_DOCS_MAX;
  visibles.forEach((d, i) => {
    const tr = crear('tr', ej.recien.has(ejIdAsoc(m.t, d.ref)) ? 'recien' : '');
    tr.dataset.ref = d.ref;
    tr.dataset.buscar = norm([d.ref, d.tipo, d.numero, d.proveedor, d.resumen].concat(d.items.map((x) => x.nombre)).join(' '));
    if (i >= max) tr.dataset.extra = '1';
    tr.hidden = i >= max;
    const tdF = crear('td', 'ej-d-fecha', d.fecha ? ejFechaCorta(d.fecha) : '—');
    const tdD = crear('td', 'ej-d-doc');
    const nom = crear('span', 'ej-d-nom');
    if (d.enlace) {
      const a = crear('a', 'ej-d-ref');
      a.href = d.enlace; a.target = '_blank'; a.rel = 'noopener';
      a.append(document.createTextNode(d.ref), icono('fuera', 12));
      a.title = 'Abrir el documento en SharePoint';
      nom.append(a);
    } else nom.append(crear('span', 'ej-d-ref', d.ref));
    tdD.append(nom, crear('small', null, ejDocNombre(d)));
    if (d.pendiente) { const c = crear('span', 'rc-chip', 'Por revisar'); c.dataset.nivel = 'warn'; c.title = 'El Centro de Costos lo marcó en rojo: algún dato está por revisar'; tdD.append(c); }
    const tdP = crear('td', 'ej-d-prov');
    tdP.append(crear('b', null, d.proveedor || 'Sin proveedor'));
    const det = d.resumen || d.items.map((x) => x.nombre).filter(Boolean).join(', ');
    if (det) { const sp = crear('span', null, det); sp.title = d.items.map((x) => '• ' + x.nombre + ': ' + ejPesos(x.neto) + ' (' + x.categoria + ')').join('\n') || det; tdP.append(sp); }
    const tdN = crear('td', 'ej-num ej-d-neto', ejPesos(d.neto));
    tdN.dataset.et = 'Neto';
    const tdA = crear('td', 'ej-d-asoc');
    const ds = ejDestinosDe(m, d.ref, todos);
    const a = m.asoc.get(d.ref);
    if (ds.length) {
      const ch = crear('div', 'ej-d-chips');
      ds.forEach((x) => { const c = crear('span', 'ej-d-chip' + (x.tipo === 'linea' ? ' linea' : ''), x.nombre); c.title = (x.tipo === 'linea' ? 'Línea del presupuesto: ' : 'Gasto proyectado: ') + x.sub; ch.append(c); });
      tdA.append(ch);
    } else if (a && !a.destinos.length) tdA.append(crear('span', 'ej-d-ninguno', 'A ningún gasto anotado'));
    // Sin asociar, un botón que se ve (vuelta 8); ya asociada, el enlace discreto para cambiarla
    const b = crear('button', ds.length || (a && !a.destinos.length) ? 'cx-desmarcar' : 'ej-asociar', ds.length || (a && !a.destinos.length) ? 'Cambiar' : 'Asociar');
    b.type = 'button';
    b.disabled = !rc.dir;
    b.dataset.foco = 'asociar-' + d.ref;
    b.setAttribute('aria-label', (ds.length ? 'Cambiar a qué gastos corresponde ' : 'Asociar a sus gastos ') + d.ref);
    b.addEventListener('click', () => ejAbrirAsociar(d));
    tdA.append(b);
    tr.append(tdF, tdD, tdP, tdN, tdA);
    tbody.append(tr);
  });
  tabla.append(thead, tbody);
  if (!visibles.length) s.append(crear('p', 'ej-nada', 'Nada en «' + filtro.nombre + '».'));
  else s.append(tabla);
  const nada = crear('p', 'ej-nada ej-docs-nada', 'Ninguna factura calza con lo buscado.');
  nada.hidden = true;
  s.append(nada);
  const mas = crear('button', 'cx-desmarcar ej-docs-mas', ej.todosDocs ? 'Ver menos' : 'Ver las ' + visibles.length + ' facturas');
  mas.type = 'button';
  mas.hidden = visibles.length <= EJ_DOCS_MAX || !!ej.docsQ;
  mas.addEventListener('click', () => { ej.todosDocs = !ej.todosDocs; ejPintar(); });
  s.append(mas);
  const filtrar = () => {
    const q = norm(bus.value).trim().split(/\s+/).filter(Boolean);
    ej.docsQ = bus.value;
    let n = 0;
    tbody.querySelectorAll('tr').forEach((tr) => {
      const calza = q.every((x) => tr.dataset.buscar.includes(x));
      tr.hidden = !calza || (!q.length && !ej.todosDocs && tr.dataset.extra === '1');
      if (calza) n++;
    });
    nada.hidden = !visibles.length || n > 0;
    mas.hidden = visibles.length <= EJ_DOCS_MAX || q.length > 0;
  };
  bus.addEventListener('input', filtrar);
  if (ej.docsQ) filtrar();
  // Lo que falta asociar ya lo dice la barra de arriba (vuelta 8); sin gastos ni presupuesto, a qué asociarlas
  if (!todos.length) {
    s.append(lineaInfo('ej-pista', 'Sin gastos proyectados ni presupuesto a que asociarlas.', 'Anota los gastos en «Gastos proyectados y cotizaciones» o formula el proyecto en el Formulador: sus líneas del presupuesto también se pueden elegir.', 'Cómo'));
  }
  return s;
}

// El diálogo: a qué gastos corresponde una factura (se arma una vez)
function ejDlgAsociar() {
  let d = $('#dlgEjAsociar');
  if (d) return d;
  d = crear('dialog');
  d.id = 'dlgEjAsociar';
  d.setAttribute('aria-labelledby', 'ejAsTit');
  const f = crear('form', 'dlg');
  f.noValidate = true;
  const h = crear('h2', null, '¿A qué gastos corresponde?');
  h.id = 'ejAsTit';
  const x = crear('button', 'dlg-x');
  x.type = 'button';
  x.setAttribute('aria-label', 'Cerrar');
  x.append(icono('cerrar', 18));
  x.addEventListener('click', () => d.close());
  const res = crear('div', 'ej-as-doc');
  res.id = 'ejAsDoc';
  const bus = crear('input', 'ej-docs-buscar');
  bus.type = 'search'; bus.id = 'ejAsBuscar'; bus.autocomplete = 'off'; bus.placeholder = 'Buscar un gasto o una línea del presupuesto';
  bus.setAttribute('aria-label', 'Buscar un gasto o una línea del presupuesto');
  const lista = crear('div', 'ej-as-lista');
  lista.id = 'ejAsLista';
  const comprar = crear('label', 'ej-as-comprar');
  comprar.id = 'ejAsComprarCampo';
  const cb = crear('input');
  cb.type = 'checkbox'; cb.id = 'ejAsComprar'; cb.checked = true;
  comprar.append(cb, document.createTextNode('Marcar como comprados los gastos elegidos que siguen por decidir o aprobados'));
  const pista = crear('p', 'ej-dlg-pista');
  pista.id = 'ejAsPista';
  const acc = crear('div', 'dlg-acc');
  const ninguno = crear('button', 'cx-enlace ej-borrar', 'No es de ningún gasto anotado');
  ninguno.type = 'button'; ninguno.id = 'ejAsNinguno';
  const cancelar = crear('button', 'cx-enlace', 'Cancelar');
  cancelar.type = 'button';
  cancelar.addEventListener('click', () => d.close());
  const ok = crear('button', 'btn-pri', 'Guardar');
  ok.type = 'submit'; ok.id = 'ejAsGuardar';
  acc.append(ninguno, cancelar, ok);
  f.append(h, x, res, bus, lista, comprar, pista, acc);
  d.append(f);
  document.body.append(d);
  bus.addEventListener('input', () => {
    const q = norm(bus.value).trim().split(/\s+/).filter(Boolean);
    lista.querySelectorAll('.ej-as-op').forEach((l) => { l.hidden = !q.every((w) => l.dataset.buscar.includes(w)); });
  });
  lista.addEventListener('change', ejAsPintarPista);
  f.addEventListener('submit', (e) => { e.preventDefault(); ejGuardarAsociacion(false); });
  ninguno.addEventListener('click', () => ejGuardarAsociacion(true));
  d.addEventListener('close', () => { ej.asociando = null; });
  return d;
}
function ejAbrirAsociar(doc) {
  const m = ej.modelo;
  if (!m || !rc.dir) return;
  const d = ejDlgAsociar();
  const todos = ejDestinos(m);
  const a = m.asoc.get(doc.ref);
  const elegidos = new Set(a ? a.destinos : []);
  ej.asociando = { ref: doc.ref, clave: m.t.clave, previo: a || null };
  // La factura: quién, cuánto y su detalle
  const res = $('#ejAsDoc');
  res.textContent = '';
  const c = crear('div', 'ej-as-cab');
  c.append(crear('b', null, (doc.proveedor || 'Sin proveedor')), crear('b', 'ej-num', ejPesos(doc.neto)));
  res.append(c, crear('span', 'ej-pista', [doc.ref, ejDocNombre(doc), doc.fecha ? ejFechaCorta(doc.fecha) : ''].filter(Boolean).join(' · ')));
  if (doc.items.length) {
    const ul = crear('ul', 'ej-as-items');
    doc.items.slice(0, 8).forEach((i) => { const li = crear('li'); li.append(crear('span', null, i.nombre || 'Ítem'), crear('span', 'ej-num', ejPesos(i.neto))); ul.append(li); });
    if (doc.items.length > 8) ul.append(crear('li', 'ej-pista', 'y ' + pl(doc.items.length - 8, 'ítem más', 'ítems más')));
    res.append(ul);
  }
  // Las opciones: primero lo que se le parece (por lo que dice la factura y su proveedor), después el resto
  const textoDoc = [doc.resumen].concat(doc.items.map((i) => i.nombre)).join(' ');
  const puntaje = (x) => {
    let p = ejParecido(textoDoc, x.nombre);
    if (x.tipo === 'item' && doc.proveedor && x.xs.some((y) => y.proveedor && ejParecido(y.proveedor, doc.proveedor) >= 0.75)) p += 0.6;   // el mismo proveedor, no una palabra suelta en común
    const cats = new Set(doc.items.length ? doc.items.map((i) => i.categoria) : [doc.categoria]);
    if (cats.has(x.cat)) p += 0.1;
    return p;
  };
  const ops = todos.map((x) => ({ x, p: puntaje(x) })).sort((u, v) => (elegidos.has(v.x.k) - elegidos.has(u.x.k)) || v.p - u.p);
  const lista = $('#ejAsLista');
  lista.textContent = '';
  const grupo = (titulo, xs) => {
    if (!xs.length) return;
    lista.append(crear('h3', 'ej-sec', titulo));
    xs.forEach(({ x, p }) => {
      const l = crear('label', 'ej-as-op');
      l.dataset.buscar = norm(x.nombre + ' ' + x.sub);
      const cb = crear('input');
      cb.type = 'checkbox'; cb.value = x.k; cb.checked = elegidos.has(x.k);
      const txt = crear('span', 'ej-as-txt');
      const n = crear('b', null, x.nombre);
      if (p >= 0.6 && !elegidos.has(x.k)) n.append(crear('span', 'ej-as-parece', 'Parece'));
      const f = m.facturado.get(x.k);
      const ya = f ? f.refs.filter((r) => r !== doc.ref) : [];
      txt.append(n, crear('span', null, x.sub + (ya.length ? ' · ya facturado ' + ejPesos(f.monto * (ya.length / f.refs.length)) + ' en ' + pl(ya.length, 'documento', 'documentos') : '')));
      l.append(cb, txt, crear('span', 'ej-num ej-as-monto', ejPesos(x.monto)));
      lista.append(l);
    });
  };
  grupo('Gastos proyectados y cotizados', ops.filter((o) => o.x.tipo === 'item'));
  grupo('Presupuesto de su formulación' + (m.t.formulacion ? ' ' + m.t.formulacion.codigo : ''), ops.filter((o) => o.x.tipo === 'linea'));
  if (!todos.length) lista.append(crear('p', 'ej-nada', 'Este proyecto todavía no tiene gastos proyectados ni presupuesto con líneas. Anótalos en «Gastos proyectados y cotizaciones».'));
  $('#ejAsBuscar').value = '';
  $('#ejAsBuscar').hidden = todos.length < 8;
  $('#ejAsNinguno').hidden = !todos.length;
  $('#ejAsComprar').checked = true;
  ejAsPintarPista();
  d.showModal();
  const primero = lista.querySelector('input');
  if (primero) primero.focus();
}
// Bajo la lista: cómo se reparte la factura entre lo elegido, y si hay algo por marcar comprado
function ejAsPintarPista() {
  const m = ej.modelo;
  const as = ej.asociando;
  if (!m || !as) return;
  const doc = (m.docs || []).find((x) => x.ref === as.ref);
  const ks = [...document.querySelectorAll('#ejAsLista input:checked')].map((x) => x.value);
  const por = new Map(ejDestinos(m).map((x) => [x.k, x]));
  const xs = ks.map((k) => por.get(k)).filter(Boolean);
  const porComprar = xs.filter((x) => x.tipo === 'item' && (x.it.estado === 'evaluar' || x.it.estado === 'aprobada'));
  $('#ejAsComprarCampo').hidden = !porComprar.length;
  const p = $('#ejAsPista');
  p.classList.remove('error');
  if (!doc || xs.length < 2) { p.textContent = ''; return; }
  const total = xs.reduce((a, x) => a + Math.max(0, x.monto), 0);
  p.textContent = 'Se reparte según lo cotizado o presupuestado de cada uno: ' + xs.map((x) => x.nombre + ' ' + ejPesos(doc.neto * (total > 0 ? Math.max(0, x.monto) / total : 1 / xs.length))).join(' · ') + '.';
}
function ejGuardarAsociacion(ninguno) {
  const m = ej.modelo;
  const as = ej.asociando;
  if (!m || !as || !rc.dir || m.t.clave !== as.clave) return;
  const ks = ninguno ? [] : [...document.querySelectorAll('#ejAsLista input:checked')].map((x) => x.value);
  if (!ninguno && !ks.length && !as.previo) { const p = $('#ejAsPista'); p.textContent = 'Elige al menos un gasto, o «No es de ningún gasto anotado».'; p.classList.add('error'); return; }
  const comprar = !ninguno && $('#ejAsComprar').checked;
  $('#dlgEjAsociar').close();
  const t = m.t;
  const cambios = [{ id: ejIdAsoc(t, as.ref), proyecto: ejClave(t), tipo: 'asociacion', ref: as.ref, destinos: ks, creado: as.previo ? as.previo.creado : undefined }];
  let comprados = 0;
  if (comprar) {
    const por = new Map(ejDestinos(m).map((x) => [x.k, x]));
    ks.map((k) => por.get(k)).filter((x) => x && x.tipo === 'item' && (x.it.estado === 'evaluar' || x.it.estado === 'aprobada')).forEach((x) => {
      comprados++;
      const otras = ejHermanas(x.it, m.costos);
      cambios.push(Object.assign({}, x.it, { estado: 'comprada', simular: false }, otras.length ? { elegida: true } : null));
      otras.filter((y) => y.estado !== 'comprada' && y.estado !== 'descartada').forEach((y) => cambios.push(Object.assign({}, y, { estado: 'descartada', simular: false, elegida: false })));
    });
  }
  const msg = ninguno ? as.ref + ': no corresponde a ningún gasto anotado.' : !ks.length ? as.ref + ': sin asociar.'
    : as.ref + ' asociada a ' + pl(ks.length, 'gasto', 'gastos') + (comprados ? '; ' + pl(comprados, 'queda comprado', 'quedan comprados') : '') + ': lo facturado ya no se simula.';
  ejPoner(cambios, msg);
}
// En la fila de un gasto: cuánto lleva facturado y en cuántos documentos
function ejFacturadoEl(it, m) {
  const f = m.facturado.get(ejKeyItem(it));
  if (!f || !f.refs.length) return null;
  const total = it.cantidad * it.precio;
  const el = crear('span', 'ej-facturado');
  el.append(document.createTextNode('Facturado ' + ejPesos(f.monto) + (total > 0 ? ' de ' + ejPesos(total) : '')));
  if (total > 0 && f.monto > total * 1.02) { el.classList.add('sobre'); el.append(document.createTextNode(' · ' + ejPesos(f.monto - total) + ' más de lo cotizado')); }
  el.title = 'En ' + f.refs.join(', ');
  return el;
}

// ---- Órdenes de compra, equipo de la semana, pendientes y notas ----------------------------------------------------
const EJ_OC = {
  gasto: { texto: 'En el gasto', nivel: 'ok', titulo: 'El Centro de Costos ya la trajo (o ya llegó su factura): está en lo gastado.' },
  comprometida: { texto: 'Comprometida', nivel: 'warn', titulo: 'Emitida y todavía no en el Centro de Costos: se suma al costo estimado como comprometida.' },
  confirmar: { texto: 'Por confirmar', nivel: '', titulo: 'El procesador todavía no dice si el Centro de Costos la trajo: no se suma, para no contarla dos veces.' },
  moneda: { texto: 'En otra moneda', nivel: '', titulo: 'No se suma: el costo estimado va en pesos.' }
};
function ejOCsEl(m) {
  const { s, cab } = ejPanel('Órdenes de compra', m.ocs.length ? String(m.ocs.length) : '');
  const nueva = ejBoton('Nueva', 'cx-enlace', () => abrirPrograma(HERR.get('orden-compra')), 'mas');
  nueva.title = 'Emitir una orden de compra en Sistema QUEMPIN (QUEMPIN.exe)';
  if (!MOVIL.matches) cab.append(nueva);
  if (!m.t.req) { s.append(crear('p', 'ej-nada', 'Sin N° de requerimiento no se unen sus órdenes de compra: Sistema QUEMPIN las anota con el N°.')); return s; }
  if (!m.ocs.length) { s.append(crear('p', 'ej-nada', 'Ninguna orden de compra de Sistema QUEMPIN con su N°.')); return s; }
  const ul = crear('ul', 'ej-lista ej-ocs');
  m.ocs.forEach((o) => {
    const li = crear('li');
    li.dataset.folio = o.folio;
    const txt = crear('span', 'ej-li-txt');
    txt.append(crear('b', null, 'OC ' + o.folio + (o.proveedor ? ' · ' + o.proveedor : '')),
      crear('span', null, [o.fecha ? ejFechaCorta(o.fecha) : '', o.referencia, o.compra ? 'compra «' + o.compra.descripcion + '»' : ''].filter(Boolean).join(' · ')));
    const der = crear('span', 'ej-li-der');
    const e = EJ_OC[o.estado];
    const chip = crear('span', 'rc-chip', e.texto);
    if (e.nivel) chip.dataset.nivel = e.nivel;
    chip.title = e.titulo;
    der.append(crear('b', null, o.moneda === 'CLP' ? ejPesos(o.neto) : o.neto.toLocaleString('es-CL') + ' ' + o.moneda), chip);
    li.append(txt, der);
    ul.append(li);
  });
  s.append(ul);
  const sum = m.ocs.filter((o) => o.estado === 'comprometida').reduce((a, o) => a + o.neto, 0);
  if (sum > 0) s.append(lineaInfo('ej-pista', ejPesos(sum) + ' comprometidos sin factura', 'Órdenes que el Centro de Costos todavía no trae: se suman al costo estimado.', 'Qué es lo comprometido'));
  return s;
}
// Quién va al proyecto esta semana, día por día, y en qué vehículo (de la Planificación semanal)
function ejEquipoEl(m) {
  const t = m.t;
  const { s, cab } = ejPanel('Equipo esta semana', '');
  const clave = ejClave(t);
  const planificar = ejBoton('Planificar', 'cx-enlace', () => { abrir('planificacion'); planif.lunes = plLunesDe(new Date()); plEnfocar(clave, false); }, 'calendario');
  cab.append(planificar);
  const sem = plSemana(plHoyId());
  if (!sem.leida) { s.append(crear('p', 'ej-nada', 'Leyendo la planificación de esta semana…')); return s; }
  const mod = plModelo(sem);
  const c = mod.canon(clave);
  /* La semana en una tira (2026-11-09, vuelta 10 del loop de UX): lunes a sábado, quién va cada día (sus iniciales) y en
     qué vehículo, con hoy marcado; abajo, quiénes van en la semana. */
  const caja = crear('div', 'ej-equipo');
  const ol = crear('ol', 'ej-semana');
  let alguien = false;
  const todos = new Set();
  plDias(sem).forEach((d) => {
    const per = plOrdenPersonas(mod.porProyecto.get(d.iso + '|' + c) || []);
    const li = crear('li', (d.hoy ? 'hoy' : '') + (per.length ? '' : ' vacio'));
    li.append(crear('span', 'ej-sem-dia', d.corto + ' ' + d.fecha.getDate()));
    const chips = crear('span', 'ej-sem-pers');
    per.forEach((x) => { todos.add(x); const ch = crear('span', 'ej-sem-per' + (x === estado.usuario ? ' tuya' : ''), PL_PER_MANO.test(x) ? plNom(x).slice(0, 3) : x); ch.title = plNom(x); chips.append(ch); });
    li.append(chips);
    const vehs = [...new Set(per.map((x) => mod.vehiculo(d.iso, x, c)).filter(Boolean))].map((v) => (plVehiculo(v) || { nombre: v }).nombre);
    if (vehs.length) { const v = crear('span', 'ej-sem-veh'); v.append(icono('vehiculo', 13), crear('span', null, unir(vehs))); li.append(v); }
    li.setAttribute('aria-label', d.corto + ' ' + d.fecha.getDate() + ': ' + (per.length ? plNoms(per) + (vehs.length ? ', en ' + unir(vehs) : '') : 'nadie'));
    if (per.length) alguien = true;
    ol.append(li);
  });
  caja.append(ol);
  if (alguien) caja.append(crear('p', 'ej-eq-res', 'Esta semana: ' + plNoms(plOrdenPersonas([...todos]))));
  const ul = caja;
  const pausa = mod.pausas.get(c);
  if (alguien) s.append(ul);
  else if (pausa || (t.etapa === 'ejecucion' && !t.antiguo)) s.append(crear('p', 'ej-nada', pausa ? 'Esta semana no se trabaja en él.' : 'Nadie asignado esta semana.'));
  else s.append(lineaInfo('ej-nada', 'Nadie asignado esta semana.', 'No aparece en la Planificación porque no está en ejecución o lleva más de 60 días sin moverse.', 'Por qué'));
  return s;
}
function ejNotasEl(m) {
  const t = m.t;
  const { s } = ejPanel('Pendientes y notas', '');
  // Pendientes: lo que falta hacer, con quién lo hace
  const pend = ejDe(t, 'pendiente').sort((a, b) => (a.listo - b.listo) || a.creado.localeCompare(b.creado));
  const f = crear('form', 'ej-nuevo');
  f.noValidate = true;
  const i = crear('input');
  i.type = 'text'; i.maxLength = 200; i.autocomplete = 'off'; i.id = 'ejPendTexto';
  i.placeholder = 'Algo por hacer: pedir la certificación SEC…';
  i.setAttribute('aria-label', 'Pendiente nuevo');
  const r = crear('select');
  r.id = 'ejPendResp';
  r.setAttribute('aria-label', 'Quién lo hace');
  [''].concat(PERSONAL).forEach((p) => { const o = crear('option', null, p || 'Quién'); o.value = p; o.selected = p === estado.usuario; r.append(o); });
  const ok = crear('button', 'cx-enlace', 'Agregar');
  ok.type = 'submit';
  ok.disabled = !rc.dir;
  f.append(i, r, ok);
  f.addEventListener('submit', (e) => {
    e.preventDefault();
    const txt = ejTxt(i.value, 200);
    if (!txt) { i.focus(); return; }
    ej.sucios.delete('ejPendTexto');
    ejPoner([{ id: ejNuevoId('p'), proyecto: ejClave(t), tipo: 'pendiente', texto: txt, responsable: r.value, listo: false }]);
    const x = $('#ejPendTexto');
    if (x) x.focus();
  });
  s.append(crear('h4', 'ej-sec', 'Pendientes'), f);
  if (pend.length) {
    const ul = crear('ul', 'ej-lista');
    pend.forEach((p) => {
      const li = crear('li', 'ej-pend' + (p.listo ? ' listo' : '') + (ej.recien.has(p.id) ? ' recien' : ''));
      const cb = crear('input');
      cb.type = 'checkbox';
      cb.checked = p.listo;
      cb.disabled = !rc.dir;
      cb.dataset.foco = 'pend-' + p.id;
      cb.setAttribute('aria-label', (p.listo ? 'Hecho: ' : 'Marcar hecho: ') + p.texto);
      cb.addEventListener('change', () => ejPoner([Object.assign({}, p, { listo: cb.checked })]));
      const txt = crear('span', 'ej-li-txt');
      txt.append(crear('b', null, p.texto), crear('span', null, [p.responsable ? 'Lo hace ' + p.responsable : '', (p.listo ? 'hecho ' : 'anotado ') + plCuando(p.listo ? p.t : p.creado) + (p.por ? ' por ' + p.por : '')].filter(Boolean).join(' · ')));
      const borrar = crear('button', 'ej-ico');
      borrar.type = 'button';
      borrar.append(icono('cerrar', 14));
      borrar.title = 'Quitar este pendiente';
      borrar.setAttribute('aria-label', 'Quitar el pendiente ' + p.texto);
      borrar.disabled = !rc.dir;
      borrar.addEventListener('click', () => ejPoner([{ id: p.id, proyecto: p.proyecto, tipo: 'pendiente', creado: p.creado, borrado: true }], 'Se quitó el pendiente.'));
      li.append(cb, txt, borrar);
      ul.append(li);
    });
    s.append(ul);
  }
  // Notas: lo que pasó en el proyecto, con fecha y quién lo anotó
  const notas = ejDe(t, 'nota').sort((a, b) => b.creado.localeCompare(a.creado));
  const fn = crear('form', 'ej-nuevo');
  fn.noValidate = true;
  const ta = crear('textarea');
  ta.rows = 2; ta.maxLength = 1000; ta.id = 'ejNotaTexto';
  ta.placeholder = 'Una nota: lo conversado con el cliente, un cambio en terreno…';
  ta.setAttribute('aria-label', 'Nota nueva');
  const okn = crear('button', 'cx-enlace', 'Anotar');
  okn.type = 'submit';
  okn.disabled = !rc.dir;
  fn.append(ta, okn);
  fn.addEventListener('submit', (e) => {
    e.preventDefault();
    const txt = texto(ta.value).slice(0, 1000);
    if (!txt) { ta.focus(); return; }
    ej.sucios.delete('ejNotaTexto');
    ejPoner([{ id: ejNuevoId('n'), proyecto: ejClave(t), tipo: 'nota', texto: txt }], 'Nota anotada.');
  });
  s.append(crear('h4', 'ej-sec', 'Notas'), fn);
  if (notas.length) {
    const ul = crear('ul', 'ej-lista');
    const max = ej.todasNotas ? notas.length : 5;
    notas.slice(0, max).forEach((n) => {
      const li = crear('li', ej.recien.has(n.id) ? 'recien' : '');
      const txt = crear('span', 'ej-li-txt');
      const b = crear('b', null, n.texto);
      b.style.whiteSpace = 'pre-wrap';
      b.style.fontWeight = '400';
      txt.append(b, crear('span', null, (n.por || 'Sin usuario') + ', ' + plCuando(n.creado)));
      const borrar = crear('button', 'ej-ico');
      borrar.type = 'button';
      borrar.append(icono('cerrar', 14));
      borrar.title = 'Borrar esta nota';
      borrar.setAttribute('aria-label', 'Borrar la nota');
      borrar.disabled = !rc.dir;
      borrar.addEventListener('click', () => ejPoner([{ id: n.id, proyecto: n.proyecto, tipo: 'nota', creado: n.creado, borrado: true }], 'Se borró la nota.'));
      li.append(txt, borrar);
      ul.append(li);
    });
    s.append(ul);
    if (notas.length > 5) {
      const mas = crear('button', 'cx-desmarcar', ej.todasNotas ? 'Ver menos' : 'Ver las ' + notas.length + ' notas');
      mas.type = 'button';
      mas.addEventListener('click', () => { ej.todasNotas = !ej.todasNotas; ejPintar(); });
      s.append(mas);
    }
  }
  return s;
}

// ---- Mano de obra: los días trabajados ----------------------------------------------------------------------------
// Las asignaciones de la Planificación semanal de este proyecto, hasta hoy, que todavía no están anotadas como trabajadas
function ejPorTraer(m, semanas) {
  const t = m.t;
  const hoy = plISO(new Date());
  const ya = new Set(m.mo.dias.map((d) => d.fecha + '|' + d.persona));
  const out = [];
  semanas.forEach((id) => {
    const s = plSemana(id);
    if (!s.leida) return;
    const mod = plModelo(s);
    const c = mod.canon(ejClave(t));
    for (let i = 0; i < 6; i++) {
      const iso = plISO(plMas(s.lunes, i));
      if (iso > hoy) break;
      (mod.porProyecto.get(iso + '|' + c) || []).forEach((per) => { if (!ya.has(iso + '|' + per)) out.push({ fecha: iso, persona: per }); });
    }
  });
  return out;
}
const ejSemanasAtras = (n) => Array.from({ length: n }, (x, k) => plSemanaId(plMas(plLunesDe(new Date()), -7 * k)));
/* La mano de obra en un calendario del mes (2026-11-06, pedido del usuario: «un cuadro tipo calendario con el mes actual
   mediante el cual se puedan ir seleccionando los días en que se ha trabajado, con 1/2 día o 1 día entero, para
   distribuir los días de trabajo en una sola acción»). Se marcan los días (un toque o, con el mouse, arrastrando), se
   eligen quiénes y la jornada, y «Anotar» deja un día trabajado por persona y día, de una vez. Cada casilla muestra lo
   ya anotado ese día. Lo marcado vive en ej.diasForm.dias y no repinta la página al marcar. */
const EJ_MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const ejMesDe = (iso) => iso.slice(0, 7);
function ejMesMas(mes, n) {
  const [a, m] = mes.split('-').map(Number);
  const d = new Date(a, m - 1 + n, 1);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
}
const ejNombreMes = (mes) => { const [a, m] = mes.split('-').map(Number); return EJ_MESES[m - 1].replace(/^./, (c) => c.toUpperCase()) + ' ' + a; };
const ejIniciales = (d) => (PL_PER_MANO.test(d.persona) ? (ejNomPer(d).split(/\s+/).map((w) => w[0] || '').join('').slice(0, 2).toUpperCase() || '·') : d.persona);
// Lo trabajado, en gráfico: días-hombre contra los presupuestados (con la raya de lo esperable al avance) y por persona
function ejMoResumenEl(m) {
  const mo = m.mo, av = m.avance.valor;
  const caja = crear('div', 'ej-mo-res');
  if (!mo.dias.length) {
    caja.append(crear('p', 'ej-pista', mo.dhP ? 'Todavía no hay días trabajados anotados: el presupuesto considera ' + pl(mo.dhP, 'día-hombre', 'días-hombre') + '.' : 'Todavía no hay días trabajados anotados.'));
    return caja;
  }
  const tot = crear('div', 'ej-mo-tot');
  const num = crear('div', 'ej-mo-num');
  num.append(crear('b', null, ejCantidad(mo.dh) + ' DH'), crear('span', null, (mo.dhP ? 'de ' + ejCantidad(mo.dhP) + ' presupuestados · ' : '') + ejPesos(mo.costo)));
  tot.append(num);
  if (mo.dhP) {
    const esc = Math.max(mo.dhP, mo.dh);
    tot.append(ejMini([[mo.dh > mo.dhP ? 'pasa' : 'av', Math.min(mo.dh, mo.dhP) / esc], ['pasa', Math.max(0, mo.dh - mo.dhP) / esc]],
      [[mo.dhP / esc, 'Presupuestados: ' + ejCantidad(mo.dhP) + ' DH']], av, 'Días-hombre trabajados contra los presupuestados (la marca); la raya naranja es el avance'));
    if (av !== null && av > 0) {
      const esperado = mo.dhP * av;
      tot.append(crear('small', 'ej-mo-ritmo', mo.dh > esperado * 1.15 ? 'Va con más días de los que su avance (' + ejPct(av) + ') supone: ~' + ejCantidad(Math.round(esperado)) + ' DH'
        : mo.dh < esperado * 0.85 ? 'Va con menos días de los que su avance (' + ejPct(av) + ') supone: ~' + ejCantidad(Math.round(esperado)) + ' DH' : 'Acorde con su avance (' + ejPct(av) + ')'));
    }
  }
  caja.append(tot);
  // Por persona: sus días-hombre y su costo, de más a menos
  const por = new Map();
  mo.dias.forEach((d) => {
    const x = por.get(d.persona) || { dh: 0, nombre: PL_PER_MANO.test(d.persona) ? d.nombre || plNom(d.persona) : d.persona };
    x.dh += Number(d.jornada) || 0;
    por.set(d.persona, x);
  });
  const filas = [...por.entries()].sort((a, b) => b[1].dh - a[1].dh);
  const max = Math.max(...filas.map(([, x]) => x.dh), 1);
  const ul = crear('ul', 'ej-mo-pers');
  ul.setAttribute('aria-label', 'Días-hombre por persona');
  filas.forEach(([per, x]) => {
    const li = crear('li');
    const barra = crear('span', 'ej-mo-barra');
    const b = crear('span');
    b.style.width = (100 * x.dh / max) + '%';
    barra.append(b);
    li.append(crear('b', 'ej-mo-quien', x.nombre), barra, crear('span', 'ej-mo-dh', ejCantidad(x.dh) + ' DH · ' + ejPesos(x.dh * mo.tarifas['n' + ejNivelDe(per)])));
    ul.append(li);
  });
  caja.append(ul);
  return caja;
}
function ejManoObraEl(m) {
  const t = m.t, mo = m.mo, f = ej.diasForm;
  const { s } = ejPanel('Mano de obra: días trabajados', mo.dh ? ejCantidad(mo.dh) + ' días-hombre · ' + ejPesos(mo.costo) : '',
    'Marca en el calendario los días trabajados (un toque, o arrastrando con el mouse), elige quiénes y si fue día completo o medio día, y «Anotar» los deja todos de una vez. '
    + 'Su costo se estima con la tarifa del nivel de cada uno y pasa a ser la mano de obra real de este resumen y de sus indicadores. También se puede escribir directo en «Ingresar avance»; desde aquí se lleva al Análisis Financiero con un toque.');
  s.id = 'ejSecMO';
  const hoy = plISO(new Date());
  const porDia = new Map();
  mo.dias.forEach((d) => { if (!porDia.has(d.fecha)) porDia.set(d.fecha, []); porDia.get(d.fecha).push(d); });
  const box = crear('div', 'ej-cal-caja');
  // Quiénes y la jornada
  const quienes = crear('div', 'pl-exp-pers ej-quienes');
  quienes.setAttribute('role', 'group');
  quienes.setAttribute('aria-label', 'Quiénes trabajaron');
  const manos = [...new Set(mo.dias.filter((d) => PL_PER_MANO.test(d.persona)).map((d) => d.persona).concat(Object.keys(f.nombres)))];
  PERSONAL.concat(manos).forEach((per) => {
    const l = crear('label', 'pl-exp-per' + (estado.usuario === per ? ' tuya' : ''));
    const cb = crear('input');
    cb.type = 'checkbox';
    cb.checked = f.personas.has(per);
    cb.dataset.foco = 'quien-' + per;
    cb.dataset.per = per;
    cb.addEventListener('change', () => { if (cb.checked) f.personas.add(per); else f.personas.delete(per); pintar(); });
    const nombre = PL_PER_MANO.test(per) ? f.nombres[per] || (mo.dias.find((d) => d.persona === per) || {}).nombre || plNom(per) : per;
    l.append(cb, document.createTextNode(nombre));
    l.title = nombre + ': nivel ' + ejNivelDe(per) + ' (' + ejPesos(mo.tarifas['n' + ejNivelDe(per)]) + ' por día)';
    quienes.append(l);
  });
  const otra = crear('div', 'ej-nuevo ej-cal-otra');
  const oi = crear('input');
  oi.type = 'text'; oi.id = 'ejDiaOtra'; oi.maxLength = 60; oi.autocomplete = 'off';
  oi.placeholder = 'Otra persona: su nombre';
  oi.setAttribute('aria-label', 'Otra persona que trabajó (su nombre)');
  const ob = crear('button', 'cx-enlace', 'Sumar');
  ob.type = 'button';
  ob.addEventListener('click', () => {
    const nombre = plNombreLimpio(oi.value);
    const slug = plSlug(nombre, 30);
    if (!slug) { oi.focus(); return; }
    const id = 'x-' + slug;
    f.nombres[id] = nombre;
    f.personas.add(id);
    ej.sucios.delete('ejDiaOtra');
    ejPintar();
  });
  otra.append(oi, ob);
  const jor = crear('div', 'pl-vistas ej-jornada');
  jor.setAttribute('role', 'radiogroup');
  jor.setAttribute('aria-label', 'Jornada');
  EJ_JORNADAS.forEach((x) => {
    const b = crear('button', 'pl-vista', x.j === 1 ? '1 día' : '½ día');
    b.type = 'button';
    b.title = x.nombre;
    b.dataset.jornada = String(x.j);
    b.dataset.foco = 'jornada-' + x.j;
    b.setAttribute('role', 'radio');
    b.addEventListener('click', () => { f.jornada = x.j; pintar(); });
    jor.append(b);
  });
  const arriba = crear('div', 'ej-cal-arriba');
  const jl = crear('div', 'ej-cal-jornada');
  jl.append(crear('span', 'ej-et', 'Jornada'), jor);
  arriba.append(quienes, jl);
  box.append(arriba, otra);
  // El mes: navegar, la grilla y lo anotado en cada día
  const nav = crear('div', 'ej-cal-nav');
  const antes = crear('button', 'ej-ico');
  antes.type = 'button';
  antes.append(icono('izquierda', 16));
  antes.setAttribute('aria-label', 'Mes anterior');
  antes.dataset.foco = 'mes-antes';
  antes.addEventListener('click', () => { f.mes = ejMesMas(f.mes, -1); ejPintar(); });
  const despues = crear('button', 'ej-ico');
  despues.type = 'button';
  despues.append(icono('derecha', 16));
  despues.setAttribute('aria-label', 'Mes siguiente');
  despues.dataset.foco = 'mes-despues';
  despues.disabled = f.mes >= ejMesDe(hoy);
  despues.addEventListener('click', () => { f.mes = ejMesMas(f.mes, 1); ejPintar(); });
  const delMes = mo.dias.filter((d) => ejMesDe(d.fecha) === f.mes);
  const tit = crear('div', 'ej-cal-tit');
  tit.append(crear('b', null, ejNombreMes(f.mes)), crear('span', null, delMes.length
    ? ejCantidad(delMes.reduce((a, d) => a + d.jornada, 0)) + ' DH · ' + ejPesos(delMes.reduce((a, d) => a + d.jornada * mo.tarifas['n' + d.nivel], 0)) : 'Nada anotado'));
  nav.append(antes, tit, despues);
  box.append(nav);
  const grilla = crear('div', 'ej-cal');
  grilla.setAttribute('role', 'group');   // grid exige filas; son botones sueltos
  grilla.setAttribute('aria-label', 'Días de ' + ejNombreMes(f.mes) + ': marca los trabajados');
  ['L', 'M', 'M', 'J', 'V', 'S', 'D'].forEach((x, i) => { const c = crear('span', 'ej-cal-sem' + (i > 4 ? ' finde' : ''), x); c.setAttribute('aria-hidden', 'true'); grilla.append(c); });
  const [ano, mes] = f.mes.split('-').map(Number);
  const primero = new Date(ano, mes - 1, 1);
  const enMes = new Date(ano, mes, 0).getDate();
  for (let i = 0; i < (primero.getDay() + 6) % 7; i++) grilla.append(crear('span', 'ej-cal-vacio'));
  const celdas = [];
  for (let n = 1; n <= enMes; n++) {
    const iso = f.mes + '-' + String(n).padStart(2, '0');
    const fecha = new Date(ano, mes - 1, n);
    const ds = porDia.get(iso) || [];
    const b = crear('button', 'ej-cal-dia' + ((fecha.getDay() + 6) % 7 > 4 ? ' finde' : '') + (iso === hoy ? ' hoy' : '') + (ds.length ? ' con' : '') + (ds.some((d) => ej.recien.has(d.id)) ? ' recien' : ''));
    b.type = 'button';
    b.dataset.iso = iso;
    b.dataset.foco = 'dia-' + iso;
    b.disabled = iso > hoy || !rc.dir;
    b.append(crear('span', 'ej-cal-n', String(n)));
    if (ds.length) {
      const marcas = crear('span', 'ej-cal-marcas');
      const ord = plOrdenPersonas([...new Set(ds.map((d) => d.persona))]).map((p) => ds.find((d) => d.persona === p));
      ord.slice(0, 3).forEach((d) => marcas.append(crear('span', 'ej-cal-per' + (d.jornada < 1 ? ' medio' : ''), ejIniciales(d) + (d.jornada < 1 ? '½' : ''))));
      if (ord.length > 3) marcas.append(crear('span', 'ej-cal-per mas', '+' + (ord.length - 3)));
      b.append(marcas);
    }
    const dh = ds.reduce((a, d) => a + d.jornada, 0);
    b.setAttribute('aria-label', n + ' de ' + EJ_MESES[mes - 1] + (ds.length ? ': ' + ejCantidad(dh) + ' días-hombre, ' + unir(ds.map((d) => ejNomPer(d) + (d.jornada < 1 ? ' medio día' : ''))) : ': nada anotado'));
    b.title = ds.length ? ds.map((d) => ejNomPer(d) + ': ' + (d.jornada === 1 ? 'día completo' : 'medio día') + ', nivel ' + d.nivel).join('\n') : '';
    celdas.push(b);
    grilla.append(b);
  }
  box.append(grilla);
  // Marcar días: un toque cambia uno; con el mouse, arrastrar marca (o desmarca) todos los que toca
  let arrastre = null;
  const marcar = (b, si) => { if (!b || b.disabled) return; if (si) f.dias.add(b.dataset.iso); else f.dias.delete(b.dataset.iso); b.setAttribute('aria-pressed', si ? 'true' : 'false'); };
  grilla.addEventListener('pointerdown', (e) => {
    const b = e.target.closest('.ej-cal-dia');
    if (!b || b.disabled || e.button > 0) return;
    e.preventDefault();
    arrastre = { si: !f.dias.has(b.dataset.iso), raton: e.pointerType !== 'touch' };
    marcar(b, arrastre.si);
    pintar();
  });
  grilla.addEventListener('pointermove', (e) => {
    if (!arrastre || !arrastre.raton) return;
    const x = document.elementFromPoint(e.clientX, e.clientY);
    const b = x && x.closest ? x.closest('.ej-cal-dia') : null;
    if (b && grilla.contains(b) && f.dias.has(b.dataset.iso) !== arrastre.si) { marcar(b, arrastre.si); pintar(); }
  });
  const soltar = () => { arrastre = null; };
  grilla.addEventListener('pointerup', soltar);
  grilla.addEventListener('pointercancel', soltar);
  grilla.addEventListener('pointerleave', soltar);
  grilla.addEventListener('click', (e) => {      // con el teclado (Enter o Espacio), sin puntero
    const b = e.target.closest('.ej-cal-dia');
    if (!b || e.detail !== 0) return;
    marcar(b, !f.dias.has(b.dataset.iso));
    pintar();
  });
  // Atajos y acciones
  const atajos = crear('div', 'ej-cal-atajos');
  const habiles = crear('button', 'cx-desmarcar', 'Lunes a viernes');
  habiles.type = 'button';
  habiles.title = 'Marcar los días hábiles de este mes, hasta hoy';
  habiles.dataset.foco = 'habiles';
  habiles.addEventListener('click', () => { celdas.forEach((b) => { if (!b.classList.contains('finde')) marcar(b, true); }); pintar(); });
  const limpiar = crear('button', 'cx-desmarcar', 'Desmarcar');
  limpiar.type = 'button';
  limpiar.dataset.foco = 'desmarcar';
  limpiar.addEventListener('click', () => { celdas.forEach((b) => marcar(b, false)); f.dias.clear(); pintar(); });
  atajos.append(habiles, limpiar);
  const acc = crear('div', 'ej-cal-acc');
  const resumen = crear('p', 'ej-cal-resumen');
  resumen.setAttribute('aria-live', 'polite');
  const ok = crear('button', 'cx-boton', 'Anotar');
  ok.type = 'button';
  ok.id = 'ejDiasAnotar';
  ok.dataset.foco = 'anotar-dias';
  ok.addEventListener('click', () => ejAnotarDias(m));
  const quitar = crear('button', 'cx-enlace', 'Quitar lo anotado');
  quitar.type = 'button';
  quitar.id = 'ejDiasQuitar';
  quitar.dataset.foco = 'quitar-dias';
  quitar.addEventListener('click', () => ejQuitarDias(m));
  acc.append(resumen, quitar, ok);
  box.append(atajos, acc);
  // Lo que dicen los botones según lo marcado (sin repintar la página)
  const pintar = () => {
    celdas.forEach((b) => b.setAttribute('aria-pressed', f.dias.has(b.dataset.iso) ? 'true' : 'false'));
    jor.querySelectorAll('.pl-vista').forEach((b) => { const si = Number(b.dataset.jornada) === f.jornada; b.setAttribute('aria-checked', si ? 'true' : 'false'); b.classList.toggle('activa', si); });
    quienes.querySelectorAll('input').forEach((cb) => { cb.checked = f.personas.has(cb.dataset.per); });
    const nd = f.dias.size;
    const np = f.personas.size;
    const borrables = ejDiasPorQuitar(m);
    ok.disabled = !rc.dir || !nd || !np;
    quitar.disabled = !rc.dir || !borrables.length;
    quitar.textContent = borrables.length ? 'Quitar ' + pl(borrables.length, 'día anotado', 'días anotados') : 'Quitar lo anotado';
    if (!nd) { resumen.textContent = 'Marca los días trabajados en el calendario.'; ok.textContent = 'Anotar'; return; }
    if (!np) { resumen.textContent = pl(nd, 'día marcado', 'días marcados') + ': elige quiénes trabajaron.'; ok.textContent = 'Anotar'; return; }
    const dh = nd * np * f.jornada;
    const costo = [...f.personas].reduce((a, per) => a + nd * f.jornada * mo.tarifas['n' + ejNivelDe(per)], 0);
    resumen.textContent = pl(nd, 'día', 'días') + ' × ' + pl(np, 'persona', 'personas') + (f.jornada < 1 ? ', medio día' : '') + ' = ' + ejCantidad(dh) + ' DH · ' + ejPesos(costo);
    ok.textContent = 'Anotar ' + ejCantidad(dh) + ' DH';
  };
  pintar();
  /* Vuelta 7 del loop de UX (2026-11-09): arriba, lo trabajado en gráfico (días-hombre contra lo presupuestado y por
     persona); el calendario se abre con «Anotar días trabajados» (abierto de entrada si todavía no hay nada anotado). */
  if (f.abierto === null || f.abierto === undefined) f.abierto = !mo.dias.length;
  s.append(ejMoResumenEl(m));
  const abrir = crear('button', (f.abierto ? 'cx-enlace' : 'cx-boton') + ' ej-cal-abrir');
  abrir.type = 'button';
  abrir.setAttribute('aria-expanded', String(f.abierto));
  abrir.setAttribute('aria-controls', 'ejCalCaja');
  abrir.dataset.foco = 'cal-abrir';
  abrir.append(icono(f.abierto ? 'cerrar' : 'calendario', 16), crear('span', null, f.abierto ? 'Ocultar el calendario' : 'Anotar días trabajados'));
  abrir.addEventListener('click', () => { f.abierto = !f.abierto; ejPintar(); });
  s.append(abrir);
  box.id = 'ejCalCaja';
  box.hidden = !f.abierto;
  s.append(box);
  // Lo que la Planificación ya tiene de este proyecto, hasta hoy
  const porTraer = ejPorTraer(m, ejSemanasAtras(2));
  if (porTraer.length && rc.dir) {
    const p = crear('p', 'ej-linea tinte');
    p.append(document.createTextNode(pl(porTraer.length, 'día-hombre', 'días-hombre') + ' de la Planificación semanal sin anotar aquí.'));
    p.title = 'Lo asignado a este proyecto en la Planificación semanal, hasta hoy, que todavía no está entre los días trabajados';
    const b = crear('button', 'cx-desmarcar', 'Traerlos');
    b.type = 'button';
    b.dataset.foco = 'traer';
    b.addEventListener('click', () => ejTraerPlanificacion(m));
    p.append(b);
    s.append(p);
  }
  // Las tarifas, y el nivel de cada persona en este proyecto
  const tar = mo.tarifas;
  const pt = crear('p', 'ej-linea');
  pt.append(document.createTextNode('Tarifas por día-hombre (' + tar.fuente + '): '), crear('b', null, EJ_NIVELES.map((x) => 'N' + x.n + ' ' + ejPesos(tar['n' + x.n])).join(' · ')));
  const ct = crear('button', 'cx-desmarcar', ej.tarifasAbiertas ? 'Cerrar' : 'Cambiar');
  ct.type = 'button';
  ct.disabled = !rc.dir;
  ct.dataset.foco = 'tarifas';
  ct.addEventListener('click', () => { ej.tarifasAbiertas = !ej.tarifasAbiertas; ejPintar(); });
  pt.append(ct);
  s.append(pt);
  if (ej.tarifasAbiertas) s.append(ejTarifasForm(m));
  const personas = [...new Set(mo.dias.map((d) => d.persona))];
  if (personas.length) {
    const niv = crear('div', 'ej-niveles');
    niv.append(crear('span', 'ej-pista', 'Nivel de cada uno aquí:'));
    plOrdenPersonas(personas).forEach((per) => {
      const d = mo.dias.find((x) => x.persona === per);
      const l = crear('label', 'ej-nivel');
      l.append(crear('span', null, ejNomPer(d)));
      const sel = crear('select');
      sel.setAttribute('aria-label', 'Nivel de ' + ejNomPer(d) + ' en este proyecto');
      sel.dataset.foco = 'nivel-' + per;
      sel.disabled = !rc.dir;
      EJ_NIVELES.forEach((x) => { const o = crear('option', null, 'N' + x.n); o.value = String(x.n); o.selected = x.n === d.nivel; sel.append(o); });
      sel.addEventListener('change', () => ejCambiarNivel(m, per, Number(sel.value)));
      l.append(sel);
      niv.append(l);
    });
    s.append(niv);
  }
  // Los días anotados, del más nuevo al más antiguo, plegados (el calendario ya los muestra)
  if (mo.dias.length) {
    const fechas = [...porDia.keys()];
    const det = crear('details', 'ej-dias-det');
    det.open = ej.diasAbiertos === t.clave;
    det.addEventListener('toggle', () => { ej.diasAbiertos = det.open ? t.clave : null; });
    det.append(crear('summary', null, 'Ver la lista de días anotados (' + pl(fechas.length, 'fecha', 'fechas') + ')'));
    const max = ej.todosDias ? fechas.length : 8;
    const ul = crear('ul', 'ej-lista ej-dias');
    fechas.slice(0, max).forEach((fecha) => {
      const ds = porDia.get(fecha);
      const li = crear('li', ds.some((d) => ej.recien.has(d.id)) ? 'recien' : '');
      const dia = plDesdeISO(fecha);
      li.append(crear('span', 'ej-dia' + (fecha === hoy ? ' hoy' : ''), PL_DIAS[(dia.getDay() + 6) % 7] ? PL_DIAS[(dia.getDay() + 6) % 7].corto + ' ' + rcCorta(dia, new Date()) : rcCorta(dia, new Date())));
      const txt = crear('span', 'ej-li-txt ej-dia-per');
      ds.forEach((d) => {
        const chip = crear('span', 'ej-per');
        chip.append(document.createTextNode(ejNomPer(d) + (d.jornada !== 1 ? ' ½' : '')));
        chip.title = ejNomPer(d) + ': ' + (d.jornada === 1 ? 'día completo' : d.jornada + ' de jornada') + ', nivel ' + d.nivel + ' (' + ejPesos(d.jornada * tar['n' + d.nivel]) + ')' + (d.origen === 'planificacion' ? ', traído de la Planificación' : '') + (d.por ? ', anotado por ' + d.por : '');
        const x = crear('button', 'ej-per-x');
        x.type = 'button';
        x.append(icono('cerrar', 12));
        x.setAttribute('aria-label', 'Quitar el día de ' + ejNomPer(d) + ' del ' + rcCorta(dia, new Date()));
        x.disabled = !rc.dir;
        x.addEventListener('click', () => ejPoner([{ id: d.id, proyecto: d.proyecto, tipo: 'dia', creado: d.creado, borrado: true }], 'Se quitó el día de ' + ejNomPer(d) + '.'));
        chip.append(x);
        txt.append(chip);
      });
      const der = crear('span', 'ej-li-der');
      der.append(crear('b', null, ejPesos(ds.reduce((a, d) => a + d.jornada * tar['n' + d.nivel], 0))));
      li.append(txt, der);
      ul.append(li);
    });
    det.append(ul);
    if (fechas.length > 8) {
      const mas = crear('button', 'cx-desmarcar', ej.todosDias ? 'Ver menos' : 'Ver los ' + fechas.length + ' días');
      mas.type = 'button';
      mas.addEventListener('click', () => { ej.todosDias = !ej.todosDias; ej.diasAbiertos = t.clave; ejPintar(); });
      det.append(mas);
    }
    s.append(det);
  }
  // Con el Análisis Financiero: su «Mano de Obra Real», y llevarle la de los días
  const pedidos = t.af && t.tag ? ejPedidosAF(t.tag).filter((x) => 'Mano de Obra Real' in x.valores) : [];
  const pedido = pedidos[pedidos.length - 1] || null;
  const tot = crear('div', 'ej-total');
  tot.append(crear('span', null, mo.dias.length ? 'Mano de obra real estimada' : 'Mano de obra real'),
    crear('b', null, mo.dias.length ? ejPesos(mo.costo) + ' (' + pl(mo.dh, 'día-hombre', 'días-hombre') + ')' : mo.af !== null ? ejPesos(mo.af) + ' del Análisis Financiero' : 'Sin dato'));
  s.append(tot);
  if (t.af && t.tag) {
    const p = crear('p', 'ej-linea');
    if (pedido) p.append(document.createTextNode('Pedido al Análisis Financiero: ' + ejPesos(pedido.valores['Mano de Obra Real']) + ', llega con la próxima vuelta del procesador.'));
    else {
      p.append(document.createTextNode('En el Análisis Financiero: ' + (mo.af !== null ? ejPesos(mo.af) : 'sin mano de obra real') + '.'));
      if (mo.dias.length && Math.round(mo.costo) !== Math.round(mo.af || 0)) {
        const b = crear('button', 'cx-desmarcar', 'Llevarle ' + ejPesos(mo.costo));
        b.type = 'button';
        b.disabled = !rc.dir || ej.enviando;
        b.dataset.foco = 'llevar-mo';
        b.addEventListener('click', () => ejLlevarManoObra(m));
        p.append(b);
      }
    }
    s.append(p);
  }
  return s;
}
// Lo anotado que «Quitar» borraría: en los días marcados, de las personas elegidas (o de todas, si no se elige a nadie)
function ejDiasPorQuitar(m) {
  const f = ej.diasForm;
  return m.mo.dias.filter((d) => f.dias.has(d.fecha) && (!f.personas.size || f.personas.has(d.persona)));
}
function ejTarifasForm(m) {
  const tar = m.mo.tarifas;
  const f = crear('form', 'ej-tarifas');
  f.noValidate = true;
  EJ_NIVELES.forEach((x) => {
    const l = crear('label', 'pl-campo');
    l.append(crear('span', null, 'Nivel ' + x.n));
    const i = crear('input');
    i.type = 'text'; i.inputMode = 'numeric'; i.id = 'ejTarifa' + x.n; i.autocomplete = 'off';
    i.value = ejCantidad(tar['n' + x.n]);
    l.append(i);
    f.append(l);
  });
  const acc = crear('div', 'cx-acc');
  const ok = crear('button', 'cx-boton', 'Guardar tarifas');
  ok.type = 'submit';
  acc.append(ok);
  if (tar.propias) acc.append(ejBoton(m.form ? 'Volver a las de su formulación' : 'Volver a las del Formulador', 'cx-enlace', () => {
    ej.tarifasAbiertas = false;
    ejPoner([{ id: tar.propias.id, proyecto: tar.propias.proyecto, tipo: 'tarifas', creado: tar.propias.creado, borrado: true }],
      'Las tarifas vuelven a ser ' + (m.form ? 'las de su formulación' : 'las del Formulador') + ': la mano de obra se recalculó.');
  }));
  f.append(acc);
  f.addEventListener('submit', (e) => {
    e.preventDefault();
    const ns = EJ_NIVELES.map((x) => ejNumero($('#ejTarifa' + x.n).value));
    if (ns.some((n) => !(n > 0))) { avisar('Cada tarifa es lo que cuesta un día de trabajo de ese nivel: un número mayor que cero.'); return; }
    ej.tarifasAbiertas = false;
    ['ejTarifa1', 'ejTarifa2', 'ejTarifa3'].forEach((id) => ej.sucios.delete(id));
    const clave = ejClave(m.t);
    ejPoner([{ id: 'tarifas-' + ejSlugClave(clave), proyecto: clave, tipo: 'tarifas', n1: ns[0], n2: ns[1], n3: ns[2], creado: tar.propias ? tar.propias.creado : undefined }],
      'Tarifas de este proyecto guardadas: la mano de obra y sus indicadores se recalcularon.');
  });
  return f;
}
// Anotar de una vez: cada día marcado (hasta hoy) por cada persona elegida, con la jornada elegida (un día ya anotado cambia)
function ejAnotarDias(m) {
  const t = m.t, f = ej.diasForm;
  if (!rc.dir) return;
  const hoy = plISO(new Date());
  const dias = [...f.dias].filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x) && x <= hoy).sort();
  if (!dias.length) { avisar('Marca en el calendario los días trabajados: hoy o anteriores.'); return; }
  if (!f.personas.size) { avisar('Elige quiénes trabajaron esos días.'); return; }
  const clave = ejClave(t);
  const cambios = [];
  dias.forEach((fecha) => f.personas.forEach((per) => {
    const id = ejIdDia(t, fecha, per);
    const previo = ej.datos.ef.get(id);
    const vivo = previo && !previo.borrado ? previo : null;
    cambios.push({ id, proyecto: clave, tipo: 'dia', fecha, persona: per, nombre: PL_PER_MANO.test(per) ? f.nombres[per] || (vivo && vivo.nombre) || plNom(per) : '',
      jornada: f.jornada, nivel: vivo ? vivo.nivel : ejNivelDe(per), origen: vivo ? vivo.origen : '', nota: vivo ? vivo.nota : '', creado: previo ? previo.creado : undefined });
  }));
  const n = cambios.reduce((a, d) => a + d.jornada, 0);
  f.dias.clear();
  ejPoner(cambios, 'Se anotó ' + (n === 1 ? '1 día-hombre' : ejCantidad(n) + ' días-hombre') + ' en ' + pl(dias.length, 'día', 'días') + ': la mano de obra real y los indicadores se recalcularon.');
}
function ejQuitarDias(m) {
  const xs = ejDiasPorQuitar(m);
  if (!xs.length || !rc.dir) return;
  ej.diasForm.dias.clear();
  ejPoner(xs.map((d) => ({ id: d.id, proyecto: d.proyecto, tipo: 'dia', creado: d.creado, borrado: true })),
    'Se quitaron ' + pl(xs.length, 'día anotado', 'días anotados') + ' (' + ejCantidad(xs.reduce((a, d) => a + d.jornada, 0)) + ' DH).');
}
// Trae de la Planificación semanal las asignaciones de este proyecto de las últimas 4 semanas, hasta hoy, que faltan aquí
async function ejTraerPlanificacion(m) {
  if (!rc.dir) return;
  const semanas = ejSemanasAtras(4);
  for (const id of semanas) {
    if (!plSemana(id).leida) { try { await plLeerSemana(rc.dir, id); } catch (e) { console.error(e); } }
  }
  const mm = ej.modelo && ej.modelo.t.clave === m.t.clave ? ej.modelo : m;
  const t = mm.t, clave = ejClave(t);
  const nuevos = ejPorTraer(mm, semanas).map((x) => {
    const id = ejIdDia(t, x.fecha, x.persona);
    const previo = ej.datos.ef.get(id);
    return { id, proyecto: clave, tipo: 'dia', fecha: x.fecha, persona: x.persona, nombre: PL_PER_MANO.test(x.persona) ? plNom(x.persona) : '',
      jornada: 1, nivel: ejNivelDe(x.persona), origen: 'planificacion', nota: '', creado: previo ? previo.creado : undefined };
  });
  if (!nuevos.length) { avisar('La Planificación no tiene días de este proyecto, hasta hoy, que falten aquí.'); ejPintar(); return; }
  ejPoner(nuevos, 'Se trajeron ' + pl(nuevos.length, 'día-hombre', 'días-hombre') + ' de la Planificación semanal (las últimas 4 semanas, hasta hoy), con día completo: corrige lo que no fue así.');
}
function ejCambiarNivel(m, per, nivel) {
  const cambios = m.mo.dias.filter((d) => d.persona === per && d.nivel !== nivel).map((d) => Object.assign({}, d, { nivel }));
  if (!cambios.length) return;
  ejPoner(cambios, ejNomPer(cambios[0]) + ' queda en el nivel ' + nivel + ' en este proyecto (' + pl(cambios.length, 'día', 'días') + '): la mano de obra se recalculó.');
}
async function ejLlevarManoObra(m) {
  if (mvNoSe()) return;
  const t = m.t;
  if (!rc.dir || !t.af || !t.tag || ej.enviando) return;
  ej.enviando = true;
  const valor = Math.round(m.mo.costo);
  try {
    await ejEnviarAF(t, { 'Mano de Obra Real': valor }, { 'Mano de Obra Real': ejVisto(t.tag, 'Mano de Obra Real', m.mo.af) }, 'Mano de obra de los días trabajados, desde Proyectos en ejecución del Portal');
    avisar('Se pidió dejar ' + ejPesos(valor) + ' como mano de obra real en el Análisis Financiero: llega con la próxima vuelta del procesador.');
  } catch (e) {
    console.error(e);
    avisar('No se pudo dejar el pedido en la carpeta del equipo (' + (e && e.name === 'NotAllowedError' ? 'falta el permiso para escribir' : 'revisa que OneDrive esté funcionando') + ').');
  }
  ej.enviando = false;
  ejPintar();
}

// ---- Indicadores ---------------------------------------------------------------------------------------------------
function ejIndicadoresEl(m) {
  const { filas, dhCierre } = ejIndicadores(m);
  const { s } = ejPanel('Indicadores', 'presupuestados y estimados hoy', 'Se recalculan con cada gasto o cotización simulada y cada día trabajado. '
    + (dhCierre ? 'Los días-hombre al cierre se estiman en ' + ejCantidad(dhCierre) + (m.mo.dhP ? ' (los presupuestados o, si ya se pasaron, los trabajados).' : ' (los trabajados divididos por el avance).') : 'Sin días-hombre presupuestados ni trabajados, los indicadores por día-hombre quedan sin dato.')
    + (m.calc ? '' : ' Lo presupuestado sale de su formulación' + (m.form ? ', con las reglas del Formulador (no se pudieron cargar).' : ': este proyecto no tiene.')));
  const tabla = crear('table', 'ej-ind');
  const thead = crear('thead');
  const trh = crear('tr');
  ['Indicador', 'Presupuestado', 'Estimado hoy'].forEach((x, i) => { const th = crear('th', i ? 'ej-num' : null, x); th.scope = 'col'; trh.append(th); });
  thead.append(trh);
  const tbody = crear('tbody');
  filas.forEach((r) => {
    const tr = crear('tr');
    tr.dataset.ind = r.id;
    const th = crear('th');
    th.scope = 'row';
    th.append(crear('span', null, r.nombre));
    if (r.nota) th.append(crear('small', null, r.nota));
    th.title = r.desc;
    const p = crear('td', 'ej-num', r.pres === null || r.pres === undefined || !isFinite(r.pres) ? '—' : r.fmt(r.pres));
    p.dataset.et = 'Presupuestado';
    const h = crear('td', 'ej-num');
    h.dataset.et = 'Estimado hoy';
    const v = crear('span', 'ej-semaforo', r.hoy === null || r.hoy === undefined || !isFinite(r.hoy) ? '—' : r.fmt(r.hoy));
    if (r.nivel) v.dataset.nivel = r.nivel; else v.classList.add('sin');
    h.append(v);
    tr.append(th, p, h);
    tbody.append(tr);
  });
  tabla.append(thead, tbody);
  s.append(tabla);
  return s;
}

// ---- El diálogo de un ítem con sus proveedores -------------------------------------------------------------------
function ejElegirCat(k) {
  if (!ej.editando) return;
  ej.editando.cat = EJ_CAT.has(k) ? k : 'Materiales';
  document.querySelectorAll('#ejCCat .pl-vista').forEach((b) => b.setAttribute('aria-checked', b.dataset.cat === ej.editando.cat ? 'true' : 'false'));
  document.querySelectorAll('#ejCCat .pl-vista').forEach((b) => b.setAttribute('aria-pressed', b.dataset.cat === ej.editando.cat ? 'true' : 'false'));
  if (ej.modelo) {
    // Las líneas de otra categoría ya no corresponden (las que el modelo aún no conoce se dejan)
    const ms = ej.modelo.lineas;
    ej.editando.lineas = ej.editando.lineas.filter((u) => { const l = ms.find((x) => x.uid === u); return !l || l.cat === ej.editando.cat; });
    ejOpcionesLinea(ej.modelo);
  }
}
const ejNombreLinea = (l) => l.code + (l.partida ? ' (' + l.partida + ')' : '') + ' · ' + l.descripcion;
/* Las líneas del presupuesto que reemplaza el ítem, una bajo otra con su ✕, y el menú con las que quedan de su categoría
   para agregar otra (ej.editando.lineas) */
function ejOpcionesLinea(m) {
  const e = ej.editando;
  const sel = $('#ejCLinea'), caja = $('#ejCLineas');
  const cat = e.cat;
  const lineas = m.lineas.filter((l) => l.cat === cat);
  const elegidas = e.lineas.map((u) => lineas.find((l) => l.uid === u)).filter(Boolean);
  $('#ejCLineaCampo').hidden = !m.lineas.length;
  caja.textContent = '';
  caja.hidden = !elegidas.length;
  elegidas.forEach((l) => {
    const c = crear('div', 'ej-lin');
    c.setAttribute('role', 'listitem');
    const t = crear('span', 'ej-lin-txt', ejNombreLinea(l) + ' ');
    t.append(crear('small', null, ejPesos(l.subtotal)));
    const x = crear('button', 'ej-ico');
    x.type = 'button';
    x.append(icono('cerrar', 16));
    x.title = 'Quitar ' + l.code;
    x.setAttribute('aria-label', 'Quitar la línea ' + ejNombreLinea(l));
    x.addEventListener('click', () => ejQuitarLinea(l.uid));
    c.append(t, x);
    caja.append(c);
  });
  if (elegidas.length > 1) caja.append(crear('span', 'ej-lin-suma', 'Suman ' + ejPesos(elegidas.reduce((a, l) => a + l.subtotal, 0)) + ' presupuestados.'));
  sel.textContent = '';
  const libres = lineas.filter((l) => !e.lineas.includes(l.uid));
  const o0 = crear('option', null, !lineas.length ? 'Su formulación no tiene ' + EJ_CAT.get(cat).nombre.toLowerCase()
    : !elegidas.length ? 'Ninguna: no estaba en el presupuesto'
    : libres.length && e.lineas.length < EJ_MAX_LINEAS ? '+ Agregar otra línea del presupuesto…' : 'No quedan más líneas de ' + EJ_CAT.get(cat).nombre.toLowerCase());
  o0.value = '';
  sel.append(o0);
  if (e.lineas.length < EJ_MAX_LINEAS) {
    libres.forEach((l) => {
      const o = crear('option', null, ejNombreLinea(l) + ' · ' + ejPesos(l.subtotal));
      o.value = l.uid;
      sel.append(o);
    });
  }
  sel.value = '';
}
function ejAgregarLinea(u) {
  const e = ej.editando;
  if (!e || !u || !ej.modelo) return;
  e.lineaTocada = true;
  if (!e.lineas.includes(u) && e.lineas.length < EJ_MAX_LINEAS) e.lineas.push(u);
  ejOpcionesLinea(ej.modelo);
  ejPintarEvaluacion();
  $('#ejCLinea').focus();
}
function ejQuitarLinea(u) {
  const e = ej.editando;
  if (!e || !ej.modelo) return;
  e.lineaTocada = true;
  e.lineas = e.lineas.filter((x) => x !== u);
  ejOpcionesLinea(ej.modelo);
  ejPintarEvaluacion();
  $('#ejCLinea').focus();
}
function ejMostrarOC() { $('#ejCOCCampo').hidden = $('#ejCEstado').value !== 'comprada'; }
function ejDatalists(m) {
  const llenar = (id, valores) => {
    const d = $(id);
    d.textContent = '';
    valores.forEach(([v, et]) => { const o = crear('option'); o.value = v; if (et) o.label = et; d.append(o); });
  };
  llenar('#ejUnidades', EJ_UNIDADES.map((u) => [u]));
  const provs = new Set();
  ej.datos.ef.forEach((e) => { if (e.tipo === 'costo' && !e.borrado && e.proveedor) provs.add(e.proveedor); });
  m.ocs.forEach((o) => { if (o.proveedor) provs.add(o.proveedor); });
  llenar('#ejProveedores', [...provs].sort((a, b) => plComparar(a, b)).slice(0, 200).map((p) => [p]));
  const ligadas = new Set(m.costos.map((x) => x.oc).filter(Boolean));
  llenar('#ejOCs', m.ocs.filter((o) => !ligadas.has(o.folio) || (ej.editando && ej.editando.oc === o.folio)).map((o) => [o.folio, [o.proveedor, ejPesos(o.neto)].filter(Boolean).join(' · ')]));
}
// Un proveedor en el diálogo: quién, a cuánto y los datos de su cotización. x: la guardada, o nada para uno nuevo.
function ejFilaProv(x) {
  const f = crear('div', 'ej-prov-fila');
  f.dataset.id = x ? x.id : '';
  const cab = crear('div', 'ej-prov-cab');
  const el = crear('label', 'ej-prov-el');
  const r = crear('input', 'ej-p-el');
  r.type = 'radio';
  r.name = 'ejCElegido';
  el.append(r, crear('span'));
  const quitar = crear('button', 'ej-ico ej-p-quitar');
  quitar.type = 'button';
  quitar.append(icono('cerrar', 16));
  quitar.title = 'Quitar este proveedor';
  quitar.setAttribute('aria-label', 'Quitar este proveedor');
  cab.append(el, crear('span', 'ej-prov-dif'), quitar);
  const campo = (clase, et, opcional, atributos, valor) => {
    const l = crear('label', 'pl-campo ' + clase);
    const s = crear('span', null, et);
    if (opcional) s.append(' ', crear('i', null, '(opcional)'));
    const i = crear('input');
    Object.entries(atributos).forEach(([k, v]) => i.setAttribute(k, v));
    i.value = valor;
    l.append(s, i);
    return l;
  };
  const iva = crear('label', 'rc-mios ej-iva ej-p-iva');
  const cb = crear('input');
  cb.type = 'checkbox';
  iva.append(cb, crear('span', null, 'Incluye IVA'));
  f.append(cab,
    campo('ej-p-prov', 'Proveedor', false, { type: 'text', maxlength: 120, autocomplete: 'off', list: 'ejProveedores' }, x ? x.proveedor : ''),
    campo('ej-p-precio', 'Precio unitario', false, { type: 'text', inputmode: 'decimal', autocomplete: 'off', placeholder: '$ sin IVA' }, x ? ejCantidad(x.precio) : ''),
    iva,
    campo('ej-p-cot', 'N° de cotización', false, { type: 'text', maxlength: 60, autocomplete: 'off' }, x ? x.cotizacion : ''),
    campo('ej-p-fecha', 'Fecha', false, { type: 'date' }, x ? x.fecha : plISO(new Date())),
    campo('ej-p-nota', 'Nota', true, { type: 'text', maxlength: 300, autocomplete: 'off', placeholder: 'Ej.: plazo 10 días, incluye despacho' }, x ? x.nota : ''));
  return f;
}
function ejAgregarProv() {
  if (!ej.editando) return;
  const f = ejFilaProv(null);
  $('#ejCProvs').append(f);
  ejPintarEvaluacion();
  f.querySelector('.ej-p-prov input').focus();
}
function ejQuitarProv(f) {
  const e = ej.editando;
  if (!e) return;
  const x = e.xs.find((y) => y.id === f.dataset.id);
  if (x) e.quitadas.push(x);
  f.remove();
  ejPintarEvaluacion();
  $('#ejCOtroProv').focus();
}
/* it: el ítem que se cambia, en su proveedor elegido (o null para uno nuevo). op.otro: se abre para agregarle un proveedor;
   op.estado: el estado que se pidió en la tabla (comprada: aquí se escribe su OC). */
function ejAbrirCosto(it, op) {
  op = op || {};
  const m = ej.modelo;
  if (!m || (!it && !rc.dir)) return;
  const xs = it ? ejItems(m.costos).map((x) => x.xs).find((ys) => ys.some((y) => y.id === it.id)) || [it] : [];
  ej.editando = { xs, grupo: it ? it.grupo : '', ref: it ? it.ref : '', simular: it ? it.simular : true, proyecto: it ? it.proyecto : ejClave(m.t), cat: 'Materiales',
    oc: it ? it.oc : '', lineaTocada: !!it, lineas: it ? ejLineasDe(it).slice() : [], previo: it || null, quitadas: [], auto: !it };
  $('#dlgEjCostoTit').textContent = it ? it.descripcion : 'Agregar un gasto o cotización';
  const pista = $('#ejCostoPista');
  pista.className = 'ej-dlg-pista';
  pista.textContent = op.otro ? 'Escribe la cotización del otro proveedor: se compara con las demás y en la tabla se elige una.'
    : it ? '' : 'Una cotización que llegó o un gasto que se espera hacer, con uno o varios proveedores para compararlos. El elegido queda por decidir y simulado: arriba cambian al tiro el costo estimado, el margen y los indicadores.';
  const cats = $('#ejCCat');
  cats.textContent = '';
  EJ_CATS.forEach((c) => {
    const b = crear('button', 'pl-vista', c.nombre);
    b.type = 'button';
    b.dataset.cat = c.k;
    b.setAttribute('role', 'radio');
    b.addEventListener('click', () => { ejElegirCat(c.k); ejPintarEvaluacion(); });
    cats.append(b);
  });
  $('#ejCDesc').value = it ? it.descripcion : '';
  ejElegirCat(it ? it.categoria : 'Materiales');
  $('#ejCCant').value = it ? ejCantidad(it.cantidad) : '1';
  $('#ejCUnidad').value = it ? it.unidad : 'Un.';
  const provs = $('#ejCProvs');
  provs.textContent = '';
  (xs.length ? xs : [null]).forEach((x) => {
    const f = ejFilaProv(x);
    f.querySelector('.ej-p-el').checked = !x || x.id === it.id;
    provs.append(f);
  });
  const est = $('#ejCEstado');
  est.textContent = '';
  EJ_ESTADOS.forEach((e) => { const o = crear('option', null, e.nombre); o.value = e.id; est.append(o); });
  est.value = op.estado || (it ? it.estado : 'evaluar');
  $('#ejCOC').value = it ? it.oc : '';
  ejMostrarOC();
  ejDatalists(m);
  $('#ejCBorrar').hidden = !it;
  $('#ejCBorrar').disabled = !rc.dir;
  $('#ejCOtroProv').disabled = !rc.dir;
  $('#ejCGuardar').disabled = !rc.dir;
  ejPintarEvaluacion();
  $('#dlgEjCosto').showModal();
  if (op.otro) ejAgregarProv();
  else (op.estado === 'comprada' ? $('#ejCOC') : it ? provs.querySelector('.ej-p-el:checked').closest('.ej-prov-fila').querySelector('.ej-p-precio input') : $('#ejCDesc')).focus();
  if (!ej.precios) ejPrecios().then(() => { if ($('#dlgEjCosto').open) ejPintarEvaluacion(); });
  if (!window.QCalc && m.form) {
    ejLib('calc').then((x) => {
      if (!x || !$('#dlgEjCosto').open || !ej.modelo) return;
      ej.modelo = ejModelo(ej.modelo.t);
      ejOpcionesLinea(ej.modelo);
      ejPintarEvaluacion();
    });
  }
}
// Lo común a todos los proveedores del ítem en el diálogo
function ejLeerItem() {
  const e = ej.editando;
  const cantidad = ejNumero($('#ejCCant').value);
  return { proyecto: e.proyecto, tipo: 'costo', descripcion: ejTxt($('#ejCDesc').value, 200), categoria: e.cat, linea: e.lineas[0] || '', lineas: e.lineas.slice(),
    cantidad: cantidad === null ? NaN : cantidad, unidad: ejTxt($('#ejCUnidad').value, 12), ref: e.ref || '' };
}
// Los proveedores escritos en el diálogo (el precio, sin IVA). vacia: nada escrito, no cuenta.
function ejLeerProvs() {
  return [...document.querySelectorAll('#ejCProvs .ej-prov-fila')].map((el) => {
    const v = (c) => el.querySelector(c + ' input').value;
    const precio = texto(v('.ej-p-precio')) ? ejNumero(v('.ej-p-precio')) : null;
    const fecha = v('.ej-p-fecha');
    const f = { el, id: el.dataset.id, elegida: el.querySelector('.ej-p-el').checked, proveedor: ejTxt(v('.ej-p-prov'), 120), cotizacion: ejTxt(v('.ej-p-cot'), 60),
      fecha: /^\d{4}-\d{2}-\d{2}$/.test(fecha) ? fecha : '', nota: ejTxt(v('.ej-p-nota'), 300),
      precio: precio === null ? NaN : el.querySelector('.ej-p-iva input').checked ? Math.round(precio / (1 + EJ_IVA) * 100) / 100 : precio };
    f.vacia = !f.proveedor && !f.cotizacion && !f.nota && !texto(v('.ej-p-precio'));
    return f;
  });
}
const ejDatosProv = (f) => ({ proveedor: f.proveedor, cotizacion: f.cotizacion, fecha: f.fecha, nota: f.nota, precio: f.precio });
/* Cada proveedor frente al más barato, y cuál está elegido: en un ítem nuevo, el más barato mientras no se elija otro a mano.
   Devuelve lo escrito. */
function ejPintarProvs(cantidad) {
  const filas = ejLeerProvs();
  const conPrecio = filas.filter((f) => f.precio > 0);
  const min = conPrecio.length ? Math.min(...conPrecio.map((f) => f.precio)) : 0;
  const marcar = (elegida) => filas.forEach((f) => { f.elegida = f === elegida; f.el.querySelector('.ej-p-el').checked = f.elegida; });
  if (ej.editando.auto && conPrecio.length) marcar(conPrecio.find((f) => f.precio === min));
  else if (!filas.some((f) => f.elegida)) marcar(filas[0]);
  $('#ejCProvs').classList.toggle('uno', filas.length < 2);
  filas.forEach((f) => {
    f.el.classList.toggle('elegida', f.elegida && filas.length > 1);
    f.el.querySelector('.ej-prov-el span').textContent = f.elegida ? 'Elegido' : 'Elegir';
    f.el.querySelector('.ej-prov-dif').textContent = conPrecio.length < 2 || !(f.precio > 0) ? ''
      : f.precio === min ? 'El más barato' : ejPesos((f.precio - min) * (cantidad > 0 ? cantidad : 1)) + ' más (' + Math.round((f.precio / min - 1) * 100) + ' %)';
  });
  return filas;
}
// La evaluación del proveedor elegido mientras se escribe: el veredicto, cada comparación y con qué compra del Cotizador se compara
function ejPintarEvaluacion() {
  const box = $('#ejCEval');
  const m = ej.modelo, e = ej.editando;
  const enRefs = document.activeElement && box.contains(document.activeElement);
  box.textContent = '';
  if (!m || !e) return;
  const item = ejLeerItem();
  // Uno nuevo: la línea del presupuesto más parecida, mientras no se elija otra a mano
  if (!e.lineaTocada && item.descripcion) {
    const l = ejLineaSugerida(item.descripcion, item.categoria, m.lineas);
    const nuevas = l ? [l.uid] : [];
    if (nuevas.join() !== e.lineas.join()) { e.lineas = nuevas; ejOpcionesLinea(m); }
    item.lineas = nuevas.slice();
    item.linea = nuevas[0] || '';
  }
  const vivas = ejPintarProvs(item.cantidad).filter((f) => !f.vacia);
  const el = vivas.find((f) => f.elegida) || vivas[0];
  if (!item.descripcion || !el || !(el.precio > 0) || !(item.cantidad > 0)) {
    box.append(crear('p', 'ej-pista', 'Escribe qué se compra, la cantidad y el precio para ver si conviene.'));
    return;
  }
  const d = Object.assign({}, item, ejDatosProv(el), { id: el.id || 'nueva', grupo: e.grupo });
  const ev = ejEvaluar(d, m, { otras: vivas.filter((f) => f !== el).map((f) => ({ proveedor: f.proveedor, precio: f.precio, cantidad: item.cantidad })), ids: e.xs.map((x) => x.id) });
  const h = crear('h3');
  const chip = crear('span', 'ej-eval-chip', ev.corto);
  if (ev.nivel) chip.dataset.nivel = ev.nivel;
  h.append(chip, document.createTextNode('Total ' + ejPesos(ev.total) + ' sin IVA' + (vivas.length > 1 && el.proveedor ? ' · ' + el.proveedor : '')));
  box.append(h);
  if (ev.puntos.length) {
    const ul = crear('ul');
    ev.puntos.forEach((p) => { const li = crear('li', null, p.texto); li.dataset.nivel = p.nivel; ul.append(li); });
    box.append(ul);
  } else box.append(crear('p', 'ej-pista', 'Sin presupuesto, precio histórico ni venta con que compararla todavía.'));
  if (d.linea && !e.lineaTocada) box.append(crear('p', 'ej-pista', 'Se compara con la línea más parecida del presupuesto: si no es esa, quítala o agrega otras arriba.'));
  if (EJ_CAT.get(d.categoria).historico) {
    if (!ej.precios) { if (rc.dir) box.append(crear('p', 'ej-pista', 'Buscando lo que QUEMPIN ha pagado por algo parecido…')); return; }
    const ps = ejParecidas(d.descripcion);
    if (!ps.length) { box.append(crear('p', 'ej-pista', 'El Cotizador Histórico no tiene compras parecidas.')); return; }
    box.append(crear('p', 'ej-pista', ev.hoja && !e.ref ? 'Se compara con la compra más parecida del Cotizador Histórico; si no es lo mismo, elige otra o «Con ninguna»:'
      : 'Comparar con lo que QUEMPIN ha pagado por:'));
    const refs = crear('div', 'ej-refs');
    const elegida = ev.hoja ? ev.hoja.clave : '-';
    ps.forEach((x) => {
      const b = crear('button', 'ej-ref', texto(x.hoja.nombre) + ' · ' + ejPesos(x.hoja.precio.promedio));
      b.type = 'button';
      b.setAttribute('aria-pressed', x.hoja.clave === elegida ? 'true' : 'false');
      b.title = [texto(x.hoja.categoria), pl(Number(x.hoja.n) || 0, 'compra', 'compras')].filter(Boolean).join(' · ');
      b.addEventListener('click', () => { ej.editando.ref = x.hoja.clave; ejPintarEvaluacion(); });
      refs.append(b);
    });
    const no = crear('button', 'ej-ref', 'Con ninguna');
    no.type = 'button';
    no.setAttribute('aria-pressed', elegida === '-' ? 'true' : 'false');
    no.addEventListener('click', () => { ej.editando.ref = '-'; ejPintarEvaluacion(); });
    refs.append(no);
    box.append(refs);
    if (enRefs) { const x = refs.querySelector('[aria-pressed="true"]'); if (x) x.focus(); }
  }
}
function ejGuardarCosto(ev) {
  ev.preventDefault();
  const m = ej.modelo, e = ej.editando;
  if (!m || !e || !rc.dir) return;
  const item = ejLeerItem();
  const filas = ejLeerProvs();
  const vivas = filas.filter((f) => !f.vacia);
  const pista = $('#ejCostoPista');
  const error = (msg, campo) => { pista.textContent = msg; pista.className = 'ej-dlg-pista error'; campo.focus(); };
  const campoPrecio = (f) => f.el.querySelector('.ej-p-precio input');
  if (!item.descripcion) { error('Escribe qué se compra.', $('#ejCDesc')); return; }
  if (!(item.cantidad > 0)) { error('La cantidad tiene que ser mayor que cero.', $('#ejCCant')); return; }
  if (!vivas.length) { error('Escribe el precio unitario, por ejemplo 125.000.', campoPrecio(filas[0])); return; }
  const mala = vivas.find((f) => !(f.precio >= 0));
  if (mala) { error('Escribe el precio unitario' + (mala.proveedor ? ' de ' + mala.proveedor : '') + ', por ejemplo 125.000.', campoPrecio(mala)); return; }
  const nuevo = !e.xs.length;
  const previo = e.previo;
  const estado = $('#ejCEstado').value;
  const oc = estado === 'comprada' ? texto($('#ejCOC').value).replace(/\D/g, '').slice(0, 12) : '';     // la OC dice que se compró
  let simular = e.simular;
  if (estado === 'descartada' || estado === 'comprada') simular = false;
  else if (estado === 'aprobada' && (!previo || previo.estado !== 'aprobada')) simular = true;
  const el = vivas.find((f) => f.elegida) || vivas[0];
  vivas.forEach((f) => { if (!f.id) f.id = ejNuevoId('c'); });
  const grupo = e.grupo || (vivas.length > 1 ? vivas[0].id : '');          // varios: en el grupo del primero
  const cambios = vivas.map((f) => {
    const antes = e.xs.find((x) => x.id === f.id);
    const d = Object.assign({}, item, ejDatosProv(f), { id: f.id, grupo, oc: f === el ? oc : '', estado: f === el ? estado : ejEstadoOtra(estado),
      simular: f === el && simular, elegida: f === el && vivas.length > 1 });
    if (antes) d.creado = antes.creado;
    return d;
  });
  // Los proveedores que se quitaron o se dejaron en blanco
  e.quitadas.concat(filas.filter((f) => f.vacia && f.id).map((f) => e.xs.find((x) => x.id === f.id)).filter(Boolean))
    .forEach((x) => cambios.push({ id: x.id, proyecto: x.proyecto, tipo: 'costo', creado: x.creado, borrado: true }));
  $('#dlgEjCosto').close();
  ej.editando = null;
  ejPoner(cambios, nuevo ? '«' + item.descripcion + '» anotada' + (vivas.length > 1 ? ' con ' + vivas.length + ' proveedores' : '') + (simular ? ' y simulada: arriba se ve cómo cambia el proyecto.' : '.') : 'Se guardó «' + item.descripcion + '».');
}

// ---- Pegar una cotización completa ----------------------------------------------------------------------------------
async function ejAbrirPegar() {
  const m = ej.modelo;
  if (!m || !rc.dir) return;
  const P = await ejLib('pegar');
  if (!P) { avisar('No se pudo cargar el lector de filas del Formulador: revisa la conexión a internet y vuelve a intentarlo.'); return; }
  ej.pegadas = { cat: 'Materiales', ivaTocado: false, filas: [] };
  $('#ejPegarTexto').value = '';
  $('#ejPProv').value = '';
  $('#ejPCot').value = '';
  $('#ejPFecha').value = plISO(new Date());
  $('#ejPIva').checked = false;
  const cats = $('#ejPCat');
  cats.textContent = '';
  EJ_CATS.forEach((c) => {
    const b = crear('button', 'pl-vista', c.nombre);
    b.type = 'button';
    b.dataset.cat = c.k;
    b.setAttribute('role', 'radio');
    b.addEventListener('click', () => { ej.pegadas.cat = c.k; ejPintarPrevia(); });
    cats.append(b);
  });
  ejDatalists(m);
  ejPintarPrevia();
  $('#dlgEjPegar').showModal();
  $('#ejPegarTexto').focus();
}
function ejPintarPrevia() {
  const p = ej.pegadas;
  if (!p) return;
  document.querySelectorAll('#ejPCat .pl-vista').forEach((b) => {
    b.setAttribute('aria-pressed', b.dataset.cat === p.cat ? 'true' : 'false');
    b.setAttribute('aria-checked', b.dataset.cat === p.cat ? 'true' : 'false');
  });
  const txt = $('#ejPegarTexto').value;
  const r = window.QPegar && texto(txt) ? window.QPegar.interpretar(txt) : { filas: [], omitidas: 0, conIva: null };
  if (!p.ivaTocado && r.conIva !== null) $('#ejPIva').checked = r.conIva;
  p.filas = r.filas;
  const iva = $('#ejPIva').checked;
  const box = $('#ejPPrevia');
  const ok = $('#ejPAgregar');
  box.textContent = '';
  ok.textContent = 'Agregar';
  ok.disabled = true;
  if (!texto(txt)) return;
  if (!r.filas.length) { box.append(crear('p', null, 'No se reconoció ninguna fila: cada una necesita una descripción y su precio.')); return; }
  const tabla = crear('table');
  const thead = crear('thead');
  const trh = crear('tr');
  ['Descripción', 'Cantidad', 'Precio unit.', 'Total'].forEach((x, i) => { const th = crear('th', i ? 'ej-num' : null, x); th.scope = 'col'; trh.append(th); });
  thead.append(trh);
  const tbody = crear('tbody');
  let total = 0;
  r.filas.forEach((f) => {
    const pu = iva ? f.costoUnitario / (1 + EJ_IVA) : f.costoUnitario;
    total += pu * f.cantidad;
    const tr = crear('tr');
    tr.append(crear('td', null, f.descripcion), crear('td', 'ej-num', ejCantidad(f.cantidad) + (f.unidad ? ' ' + f.unidad : '')), crear('td', 'ej-num', ejPesos(pu)), crear('td', 'ej-num', ejPesos(pu * f.cantidad)));
    tbody.append(tr);
  });
  tabla.append(thead, tbody);
  box.append(tabla, crear('p', null, pl(r.filas.length, 'fila', 'filas') + ' por ' + ejPesos(total) + ' sin IVA' + (r.omitidas ? ' · ' + pl(r.omitidas, 'línea omitida', 'líneas omitidas') + ' (totales o sin precio)' : '') + '.'));
  ok.textContent = 'Agregar ' + pl(r.filas.length, 'fila', 'filas');
  ok.disabled = !rc.dir;
}
function ejAgregarPegadas(e) {
  e.preventDefault();
  const m = ej.modelo, p = ej.pegadas;
  if (!m || !p || !p.filas.length || !rc.dir) return;
  const iva = $('#ejPIva').checked;
  const prov = ejTxt($('#ejPProv').value, 120), cot = ejTxt($('#ejPCot').value, 60), fecha = $('#ejPFecha').value;
  const clave = ejClave(m.t);
  const items = p.filas.map((f) => ({
    id: ejNuevoId('c'), proyecto: clave, tipo: 'costo', descripcion: ejTxt(f.descripcion, 200), categoria: p.cat,
    cantidad: f.cantidad > 0 ? f.cantidad : 1, unidad: ejTxt(f.unidad, 12) || 'Un.',
    precio: iva ? Math.round(f.costoUnitario / (1 + EJ_IVA) * 100) / 100 : f.costoUnitario,
    proveedor: prov, cotizacion: cot, fecha: /^\d{4}-\d{2}-\d{2}$/.test(fecha) ? fecha : '', estado: 'evaluar', simular: true, grupo: '', oc: '',
    linea: (ejLineaSugerida(f.descripcion, p.cat, m.lineas) || {}).uid || '', ref: '', nota: ''
  }));
  $('#dlgEjPegar').close();
  ej.pegadas = null;
  ejPoner(items, 'Se agregaron ' + pl(items.length, 'gasto por decidir', 'gastos por decidir') + (prov ? ' de ' + prov : '') + ', simulados: arriba se ve cómo cambia el proyecto.');
}

// ---- La venta, el avance y la ficha del Análisis Financiero -----------------------------------------------------------
function ejAbrirVenta(m) {
  if (!rc.dir) return;
  const v = m.venta;
  $('#ejVentaPista').textContent = v ? 'Hoy: ' + ejPesos(v.monto) + ' (' + v.fuente + '). Corrígela si cambió: un adicional aprobado, un descuento.'
    : 'No hay venta en su formulación, una cotización emitida ni la Planilla de Ingreso. Escríbela para ver el margen estimado.';
  $('#ejVMonto').value = v ? ejCantidad(Math.round(v.monto)) : '';
  $('#ejVNota').value = v && v.manual ? v.manual.nota : '';
  $('#ejVQuitar').hidden = !(v && v.manual);
  $('#dlgEjVenta').showModal();
  $('#ejVMonto').focus();
  $('#ejVMonto').select();
}
function ejGuardarVenta(e, quitar) {
  if (e) e.preventDefault();
  const m = ej.modelo;
  if (!m || !rc.dir) return;
  const monto = quitar ? null : ejNumero($('#ejVMonto').value);
  if (!quitar && !(monto > 0)) { $('#ejVentaPista').textContent = 'Escribe la venta neta, sin IVA (por ejemplo 12.500.000).'; $('#ejVMonto').focus(); return; }
  $('#dlgEjVenta').close();
  const clave = ejClave(m.t);
  const previa = m.venta && m.venta.manual;
  ejPoner([{ id: 'venta-' + ejSlugClave(clave), proyecto: clave, tipo: 'venta', monto, nota: quitar ? '' : ejTxt($('#ejVNota').value, 200), creado: previa ? previa.creado : undefined }],
    quitar ? 'La venta vuelve a ser la calculada.' : 'Venta corregida a ' + ejPesos(monto) + ': el margen y los indicadores se recalcularon.');
}
async function ejEnviarAvance(m, pct, fin) {
  if (mvNoSe()) return;
  const t = m.t;
  if (!rc.dir || !t.af || !t.tag || ej.enviando) return;
  const v = Math.round(Number(pct));
  if (!isFinite(v) || v < 0 || v > 100) { avisar('El avance va de 0 a 100 %.'); return; }
  const valores = {}, reemplaza = {};
  const actual = m.avance.valor;
  if (actual === null || Math.round(actual * 100) !== v) {
    valores['% Avance'] = v / 100;
    reemplaza['% Avance'] = ejVisto(t.tag, '% Avance', m.avance.af);
  }
  const finIso = /^\d{4}-\d{2}-\d{2}$/.test(texto(fin)) ? fin : '';
  if (finIso && finIso !== (m.avance.fin ? plISO(m.avance.fin) : '')) {
    valores['Fecha de cierre'] = finIso;
    reemplaza['Fecha de cierre'] = ejVisto(t.tag, 'Fecha de cierre', t.af.cierre ? texto(t.af.cierre).slice(0, 10) : null);
  }
  if (!Object.keys(valores).length) { avisar('El Análisis Financiero ya tiene ese avance y esa fecha.'); return; }
  ej.enviando = true;
  try {
    await ejEnviarAF(t, valores, reemplaza, 'Proyectos en ejecución del Portal');
    ['ejAvRango', 'ejAvNum', 'ejAvFin'].forEach((id) => ej.sucios.delete(id));
    avisar(('% Avance' in valores ? 'Avance ' + v + ' %' : 'Fecha de término') + ' pedido al Análisis Financiero: llega con la próxima vuelta del procesador. El Recorrido y la Planificación ya lo muestran.');
  } catch (e) {
    console.error(e);
    avisar('No se pudo dejar el pedido en la carpeta del equipo (' + (e && e.name === 'NotAllowedError' ? 'falta el permiso para escribir' : 'revisa que OneDrive esté funcionando') + ').');
  }
  ej.enviando = false;
  ejPintar();
  pintarInicioRecorrido();
  plPintarAlarmaGlobal();
}
async function ejRetirarAvance(m, msg) {
  if (!rc.dir) return;
  try {
    const ok = await ejRetirarAF(msg);
    avisar(ok ? 'Se retiró el pedido: el avance queda como está en el Análisis Financiero.' : 'Ese pedido ya no está en el buzón: el Análisis Financiero ya lo atendió.');
  } catch (e) {
    console.error(e);
    avisar('No se pudo retirar el pedido (revisa que OneDrive esté funcionando).');
  }
  ejPintar();
}
// ---- El nombre que se ve (2026-11-09): el apodo del Análisis Financiero, con un «datos-proyecto» -----------------------
function ejAbrirNombre(m) {
  if (!rc.dir || !m.t.af) return;
  $('#ejNomPista').textContent = 'Nombre en el Análisis Financiero: «' + (texto(m.t.af.nombre) || m.t.tag) + '». Si lo dejas vacío, se ve ese.';
  $('#ejNomTexto').value = m.t.titulo || '';
  $('#dlgEjNombre').showModal();
  $('#ejNomTexto').focus();
  $('#ejNomTexto').select();
}
async function ejGuardarNombre(e) {
  if (e) e.preventDefault();
  if (mvNoSe()) return;
  const m = ej.modelo;
  if (!m || !rc.dir || !m.t.af || !m.t.tag || ej.enviando) return;
  const t = m.t;
  const nuevo = texto($('#ejNomTexto').value).replace(/\s+/g, ' ').slice(0, 60);
  $('#dlgEjNombre').close();
  if (nuevo === texto(t.titulo)) return;
  ej.enviando = true;
  try {
    await ejEnviarAF(t, { Apodo: nuevo || null }, { Apodo: ejVisto(t.tag, 'Apodo', texto(t.af.apodo) || null) }, 'Cambiar el nombre, desde Proyectos en ejecución del Portal');
    avisar('Nombre pedido: «' + (nuevo || texto(t.af.nombre)) + '». Aquí ya se ve; en los tableros llega con la próxima vuelta del procesador.');
  } catch (err) {
    console.error(err);
    avisar('No se pudo dejar el pedido en la carpeta del equipo (' + (err && err.name === 'NotAllowedError' ? 'falta el permiso para escribir' : 'revisa que OneDrive esté funcionando') + ').');
  }
  ej.enviando = false;
  ejPintar();
  pintarInicioRecorrido();
}
/* ---- «Cerrado» desde Proyectos en ejecución (2026-11-10) -------------------------------------------------------------
   Pedido del usuario: que aquí también se pueda cambiar el estado a «Cerrado». Es el mismo cambio que hace Requerimientos
   (un editar-requerimiento al buzón, pqEnviar) y la misma opción de llevar su carpeta de Gestión de Proyectos a
   «0 Proyectos Entregados <año>» (pqEnviarMover). Si la Planilla ya dice «Cerrado» y su carpeta sigue en la raíz de
   Gestión, el botón solo ofrece moverla. Sin N° de requerimiento o sin fila en la Planilla, no se ofrece. */
function ejCierreDe(t) {
  if (!rc.dir || !t || !t.req || !t.planilla) return null;
  const yaCerrado = texto(t.planilla.estado) === 'Cerrado';
  const carpeta = pqCarpetaGestion(t.req);
  if (yaCerrado && !carpeta) return null;
  return { yaCerrado, carpeta, antes: texto(t.planilla.estado) || null };
}
function ejAbrirCerrar(m) {
  const c = ejCierreDe(m.t);
  if (!c) return;
  ej.cerrar = { clave: m.t.clave, yaCerrado: c.yaCerrado };
  $('#dlgEjCerrarTit').textContent = c.yaCerrado ? 'Llevar su carpeta a entregados' : 'Marcar «Cerrado» · N° ' + m.t.req;
  $('#ejCerPista').textContent = c.yaCerrado ? 'Requerimientos ya lo dice «Cerrado».'
    : 'En Requerimientos pasa de «' + (c.antes || 'sin estado') + '» a «Cerrado»: ya se entregó.';
  const caja = $('#ejCerMover');
  caja.disabled = !c.carpeta || c.yaCerrado;
  caja.checked = !!c.carpeta;
  $('#ejCerMoverTxt').textContent = c.carpeta ? 'Mover su carpeta a «' + PQ_ENTREGADOS + ' ' + new Date().getFullYear() + '»'
    : 'Sin carpeta con el N° ' + m.t.req + ' en Gestión de Proyectos';
  $('#ejCerMoverDe').textContent = c.carpeta ? 'Gestión de Proyectos › ' + c.carpeta : 'Si ya está en «' + PQ_ENTREGADOS + '», no hay nada que mover.';
  $('#ejCerGuardar').textContent = c.yaCerrado ? 'Mover la carpeta' : 'Marcar «Cerrado»';
  $('#ejCerGuardar').disabled = false;
  $('#dlgEjCerrar').showModal();
  $('#ejCerGuardar').focus();
}
async function ejGuardarCerrar(e) {
  if (e) e.preventDefault();
  if (mvNoSe()) return;
  const m = ej.modelo;
  if (!m || !ej.cerrar || m.t.clave !== ej.cerrar.clave || ej.enviando) return;
  const t = m.t;
  const c = ejCierreDe(t);
  if (!c) { $('#dlgEjCerrar').close(); return; }
  const mover = $('#ejCerMover').checked && c.carpeta ? c.carpeta : null;
  const titulo = texto(t.planilla.titulo);
  const numero = t.planilla.numero;               // el de la Planilla, entero (t.req viene como texto)
  ej.enviando = true;
  $('#ejCerGuardar').disabled = true;
  try {
    if (!c.yaCerrado) {
      const req = { numero };
      if (titulo) req.titulo = titulo;
      await pqEnviar('editar-requerimiento', { requerimiento: req, cambios: { estado: 'Cerrado' }, reemplaza: { estado: c.antes } });
    }
    if (mover) await pqEnviarMover(numero, titulo);
  } catch (err) {
    console.error(err);
    ej.enviando = false;
    $('#ejCerGuardar').disabled = false;
    $('#ejCerPista').textContent = err && err.name === 'NotAllowedError'
      ? 'Falta el permiso para escribir en la carpeta del equipo: usa «Volver a leer» y acepta «Ver y editar archivos».'
      : 'No se pudo guardar: revisa que OneDrive esté funcionando y vuelve a intentarlo.';
    return;
  }
  ej.enviando = false;
  $('#dlgEjCerrar').close();
  if (mover) rcPedirVuelta().catch((err) => console.error(err));
  const carpeta = mover ? ' Su carpeta pasa a «' + PQ_ENTREGADOS + '» ' + (rcSinTareaDePedidos() ? 'en la próxima vuelta del procesador.' : 'en unos minutos.') : '';
  avisar(c.yaCerrado ? 'N° ' + t.req + ':' + carpeta : 'N° ' + t.req + ' marcado «Cerrado». Pasa al Excel en un par de minutos.' + carpeta);
  ejPintar();
  pintarInicioRecorrido();
}
async function ejUnirFicha(m, af) {
  if (mvNoSe()) return;
  const t = m.t;
  if (!rc.dir || !t.req || ej.enviando) return;
  ej.enviando = true;
  const tag = texto(af.tag).toUpperCase();
  try {
    await ejEnviarAF({ tag, af, titulo: texto(af.nombre) }, { 'N° Requerimiento': Number(t.req) }, { 'N° Requerimiento': null }, 'Unir la ficha con su N° de requerimiento, desde Proyectos en ejecución del Portal');
    avisar('Se pidió unir la ficha ' + tag + ' con el N° ' + t.req + ': llega con la próxima vuelta del procesador, y entonces aquí se ven su avance y sus costos.');
  } catch (e) {
    console.error(e);
    avisar('No se pudo dejar el pedido en la carpeta del equipo (' + (e && e.name === 'NotAllowedError' ? 'falta el permiso para escribir' : 'revisa que OneDrive esté funcionando') + ').');
  }
  ej.enviando = false;
  ejPintar();
}
