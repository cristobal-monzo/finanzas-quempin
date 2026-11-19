/* Portal QUEMPIN — Recorrido de proyectos (rc*).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Recorrido de proyectos (2026-10-20) ----------------------------------------------------------
// Pedido del usuario: una herramienta nueva que deje muy claro el flujo de trabajo. Todos los proyectos
// del equipo en las seis etapas del recorrido (las mismas del Seguimiento del Formulador, js/flujo.js),
// cada uno con lo que sigue, quién lo tiene y un botón que abre la herramienta donde se hace. Se arma
// en el navegador con lo que publica la carpeta de intercambio, por la conexión de la biblioteca que
// ya usan el Formulador y «Configuración y conexiones»: la Planilla (requerimientos.json), el cruce de
// proyectos, el Análisis Financiero, Mercado Público, el repositorio de formulaciones y los borradores
// que esperan en Sistema QUEMPIN. Solo lee: nunca escribe en la carpeta. El usuario elegido marca lo
// suyo, y «Solo mis proyectos» deja solo eso.
const RC_ETAPAS = [
  { id: 'requerimiento', titulo: 'Requerimiento', corto: 'Requerimiento', herr: 'planilla' },
  { id: 'formulacion', titulo: 'Formulación', corto: 'Formulación', herr: 'formulador' },
  { id: 'cotizacion', titulo: 'Cotización', corto: 'Cotización', herr: 'cotizacion' },
  { id: 'oferta', titulo: 'Oferta y adjudicación', corto: 'Oferta', herr: 'proyectos' },
  { id: 'ejecucion', titulo: 'Ejecución', corto: 'Ejecución', herr: 'ejecucion' },
  { id: 'cierre', titulo: 'Cierre', corto: 'Cierre', herr: 'analisis' }
];
const RC_ANTES_DE_OFERTAR = ['requerimiento', 'formulacion', 'cotizacion'];
const RC_VIVOS = ['Evaluación', 'Ofertado', 'Adjudicado'];       // estados de la Planilla que siguen en curso
const RC_GANADOS = ['Adjudicado', 'Cerrado'];    // se adjudicó; «Cerrado» (2026-11-09): y ya se entregó
const RC_EN_FORMULACION = ['Borrador', 'En revisión'];
const RC_FUERA = ['Perdida', 'Descartada'];      // formulaciones que no siguen (Cerrada sí: va al «Cierre»)
const RC_DIAS_ANTIGUO = 60;          // lo que lleva más que esto sin moverse va plegado al pie de su etapa
const RC_DIAS_SIN_RESPUESTA = 45;    // una oferta sin respuesta hace más que esto: confirmar el resultado
const RC_RELEER_SEG = 60;            // al volver a la pestaña se relee si pasó más que esto
const LS_RC = 'quempin_portal_recorrido';   // { mios }: lo elegido en este navegador
const RC_MP = /^https:\/\/www\.mercadopublico\.cl\//;
const DIA = 86400000;
const MAXIMO = Number.MAX_SAFE_INTEGER;
const rc = {
  tarjetas: [], entregadas: [], datos: null, leido: 0, leyendo: null, carpetas: null, pulso: null, dir: null, vuelta: null,
  foco: null, q: '', mios: !!(leer(LS_RC, {}) || {}).mios
};

// Fechas de la Planilla y de las publicaciones: «2026-10-23», «2026-10-23T20:00», «15-10-2026 a las 11:00».
function rcFecha(v) {
  const s = texto(v);
  let m = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/.exec(s);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0));
  m = /\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b/.exec(s);
  return m ? new Date(+m[3], +m[2] - 1, +m[1]) : null;
}
const rcDia = (f) => new Date(f.getFullYear(), f.getMonth(), f.getDate()).getTime();
const rcDias = (f, hoy) => Math.round((rcDia(f) - rcDia(hoy)) / DIA);   // > 0: falta; < 0: ya pasó
const dos = (n) => String(n).padStart(2, '0');
const rcCorta = (f, hoy) => dos(f.getDate()) + '-' + dos(f.getMonth() + 1) + (f.getFullYear() === hoy.getFullYear() ? '' : '-' + String(f.getFullYear()).slice(2));
const pl = (n, uno, varios) => n + ' ' + (n === 1 ? uno : varios);
/* N° temporal «001t» (2026-11-09, pedido del usuario): de un proyecto de Gestión sin N° de la Planilla, para no
   asociarlo a un N° puntual. El procesador lo lee de tags-temporales.json del Intercambio. TAG: «001t - Nombre». */
const rcEsTemporal = (n) => /^\d{3,4}t$/.test(texto(n));
const rcNum = (v) => {
  const s = texto(v).replace(/\.0$/, '');
  if (/^\d{3,4}t$/i.test(s)) return s.toLowerCase();
  return /^\d{1,6}$/.test(s) && +s > 0 ? String(+s) : null;
};
function rcCierre(f, hoy) {
  const d = rcDias(f, hoy);
  if (d < 0) return { texto: 'Cerró el ' + rcCorta(f, hoy), nivel: '' };
  if (d <= 1) return { texto: d === 0 ? 'Cierra hoy' : 'Cierra mañana', nivel: 'bad' };
  return { texto: 'Cierra en ' + d + ' días', nivel: d <= 2 ? 'bad' : d <= 7 ? 'warn' : '' };
}
const rcNivel = (f, hoy) => (f ? rcCierre(f, hoy).nivel : '');
/* Quién lo tiene: las primeras iniciales del equipo entre las que se dan ([valor, de dónde]); si ninguna
   es del equipo de hoy, las primeras que haya (JB, SA, de antes). */
function rcResponsable(...pares) {
  const validas = pares.map(([v, de]) => [texto(v).toUpperCase(), de]).filter(([v]) => /^[A-Z]{2,3}$/.test(v));
  return validas.find(([v]) => USUARIOS.includes(v)) || validas[0] || ['', ''];
}
// Una carpeta del cruce («0 OFERTAS ADJUDICADAS/284. Nombre»), con las mismas reglas que carpetaDe.
function rcCarpeta(relativa, biblioteca) {
  const ruta = texto(relativa).split('/').map(texto).filter(Boolean);
  const valida = (n) => !!n && !n.startsWith('.') && !/[\\/:*?"<>|]/.test(n);
  return ruta.length && ruta.length <= 6 && ruta.every(valida) ? { nombre: ruta[ruta.length - 1], ruta, biblioteca } : null;
}
const rcSinNumero = (nombre) => texto(nombre).replace(/^\s*\d{1,4}\s*[.\-_)]\s*/, '');
/* Un título de la Planilla escrito todo en mayúsculas, legible en una tarjeta: cada palabra con mayúscula
   inicial, los artículos y preposiciones en minúscula y las siglas cortas (GLP, ACS, H2) como venían. */
const RC_MENORES = new Set(['a', 'al', 'de', 'del', 'el', 'la', 'las', 'los', 'en', 'y', 'e', 'o', 'u', 'con', 'por', 'para', 'sin', 'sobre', 'un', 'una']);
function rcLegible(v) {
  const s = texto(v);
  if (!s || /[a-záéíóúñü]/.test(s)) return s;
  return s.toLowerCase().split(/(\s+)/).map((w, i) => {
    if (/^\s+$/.test(w) || !w) return w;
    if (i > 0 && RC_MENORES.has(w)) return w;
    if (/\d/.test(w) || (w.length <= 3 && !RC_MENORES.has(w))) return w.toUpperCase();
    return w.replace(/\p{L}/u, (c) => c.toUpperCase());
  }).join('');
}
// Adónde lleva cada acción: una herramienta del portal (con su dirección) o QUEMPIN.exe.
const RC_IR = {
  req: (n) => ({ herr: 'formulador', url: HERR.get('formulador').ruta + '#/req/' + encodeURIComponent(n) }),
  ficha: (uid) => ({ herr: 'formulador', url: HERR.get('formulador').ruta + '#/p/' + encodeURIComponent(uid) + '/ficha' }),
  seguimiento: (uid) => ({ herr: 'proyectos', url: HERR.get('formulador').ruta + '#/p/' + encodeURIComponent(uid) + '/seguimiento' }),
  af: (tag) => ({ herr: 'analisis', url: HERR.get('analisis').ruta + '#proyecto=' + encodeURIComponent(tag) }),
  cc: (tag) => ({ herr: 'centro-costos', url: HERR.get('centro-costos').ruta + '#tag=' + encodeURIComponent(tag) }),
  // El resumen del proyecto en «Proyectos en ejecución» (una vista del portal: clave, la de su tarjeta)
  ejecucion: (clave) => ({ herr: 'ejecucion', ejecucion: clave }),
  // Su fila en la Planilla de Ingreso del portal, abierta para cambiarla (2026-10-29: antes era el Excel)
  planilla: (n) => ({ herr: 'planilla', planilla: n }),
  herr: (id) => ({ herr: id })
};

// ---- Lo que se sabe de cada proyecto → su etapa y lo que sigue (solo calcula) ---------------------
function rcBase(clave) {
  return { clave, req: null, tag: null, titulo: '', lugar: '', planilla: null, formulacion: null, af: null, lic: null, cierre: null,
    carpetas: {}, cotizaciones: [], chips: [], avisos: [], responsable: '', respDe: '', antiguo: false, orden: MAXIMO };
}
// Con ficha en el Análisis Financiero: en ejecución hasta el 100 % de avance, y después cerrado.
function rcEtapaAF(t, af, hoy) {
  const tag = texto(af.tag).toUpperCase();
  const avance = Math.max(0, Math.min(1, Number(af.avance) || 0));
  const fin = rcFecha(af.cierre);
  t.avance = avance;
  if (Number(af.avance) >= 1) {
    t.etapa = 'cierre';
    t.accion = { tipo: 'listo', corto: 'Ver su resultado', nivel: '', ir: RC_IR.af(tag),
      texto: 'Terminado. Lo gastado frente a lo presupuestado ya cuenta en su Nota del Análisis Financiero y en el sesgo real que usa el Formulador.' };
    t.chips.push(fin ? { texto: 'Terminó el ' + rcCorta(fin, hoy), nivel: 'ok' } : { texto: 'Sin fecha de término', nivel: '' });
    t.antiguo = !fin || rcDias(fin, hoy) < -RC_DIAS_ANTIGUO;
    t.orden = fin ? -fin.getTime() : MAXIMO;
    return;
  }
  t.etapa = 'ejecucion';
  const atrasado = !!fin && rcDias(fin, hoy) < 0;
  // Desde el 2026-10-28 el avance se registra en «Proyectos en ejecución», en el resumen del proyecto (también la fecha de
  // término, los días trabajados y lo que se piensa comprar); «Ingresar avance» sigue siendo la tabla de todos
  t.accion = atrasado
    ? { tipo: 'hacer', corto: 'Actualizar avance o término', nivel: 'warn', ir: RC_IR.ejecucion(t.clave),
        texto: 'Su término (' + rcCorta(fin, hoy) + ') ya pasó con ' + Math.round(avance * 100) + ' % de avance. Actualiza el avance o la fecha en su resumen de «Proyectos en ejecución».' }
    : { tipo: 'curso', corto: 'Registrar avance', nivel: '', ir: RC_IR.ejecucion(t.clave),
        texto: 'En ejecución. Registra el avance, la fecha de término y los días trabajados en su resumen de «Proyectos en ejecución», donde también se evalúan las compras con sus cotizaciones; las facturas llegan solas al Centro de Costos.'
          + ' Cuando termine, márcalo «Cerrada» en el Seguimiento del Formulador, deja su avance en 100 % o dalo por cerrado («Dar por cerrado», en su ficha o en «Estado de los proyectos»): sale de la Planificación semanal.' };
  if (fin) t.chips.push(atrasado ? { texto: 'Término vencido', nivel: 'warn' } : { texto: 'Termina el ' + rcCorta(fin, hoy), nivel: '' });
  t.orden = fin ? fin.getTime() : MAXIMO;
  if (af.venta && af.venta.cargada === false) t.avisos.push('Falta su monto de venta en el Análisis Financiero: sin él no entra completo a sus indicadores.');
}
/* Marcado «Cerrada» en el Formulador (2026-10-26): va al «Cierre» aunque el Análisis Financiero no tenga el 100 %, y
   sale de la Planificación semanal. Plegado, como los terminados, cuando lleva más de 60 días cerrado. */
function rcCerrada(t, f, hoy) {
  const finAF = rcFecha(t.af && t.af.cierre);       // su término en el Análisis, si ya pasó; si no, el último cambio
  const fin = finAF && rcDias(finAF, hoy) <= 0 ? finAF : rcFecha(f.modificado) || finAF;
  const avance = t.af ? Math.max(0, Math.min(1, Number(t.af.avance) || 0)) : null;
  t.etapa = 'cierre';
  t.accion = { tipo: 'listo', corto: 'Cerrado', nivel: '', ir: t.af ? RC_IR.af(texto(t.af.tag).toUpperCase()) : RC_IR.seguimiento(f.uid),
    texto: 'Proyecto cerrado: su ejecución terminó y ya no aparece en la Planificación semanal.'
      + (t.af ? ' Su resultado está en el Análisis Financiero.' : '') };
  t.chips = [{ texto: 'Cerrado', nivel: 'ok' }].concat(t.chips.filter((c) => /^Terminó/.test(c.texto)));
  if (avance !== null && avance < 1) t.avisos.push('Está «Cerrada» en el Formulador, pero el Análisis Financiero tiene ' + Math.round(avance * 100) + ' % de avance: déjalo en 100 % en «Ingresar avance» para que su resultado cuente en el sesgo real.');
  t.antiguo = !!fin && rcDias(fin, hoy) < -RC_DIAS_ANTIGUO;
  t.orden = fin ? -fin.getTime() : MAXIMO;
}
/* «Cerrado» en la Planilla de Ingreso (2026-11-09): entregado. Lo pone el Portal o el procesador cuando su carpeta pasa a
   «0 Proyectos Entregados» (cierre_entregados.py). Va al «Cierre» aunque el Análisis Financiero no tenga el 100 %, como
   lo marcado «Cerrada» en el Formulador, y sale de la Planificación semanal. */
function rcCerradoPlanilla(t, hoy) {
  const fin = rcFecha(t.af && t.af.cierre);
  const avance = t.af ? Math.max(0, Math.min(1, Number(t.af.avance) || 0)) : null;
  t.etapa = 'cierre';
  t.accion = { tipo: 'listo', corto: 'Cerrado', nivel: '', ir: t.af ? RC_IR.af(texto(t.af.tag).toUpperCase()) : RC_IR.planilla(t.req),
    texto: 'Proyecto entregado: la Planilla de Ingreso lo dice «Cerrado» y ya no aparece en la Planificación semanal.'
      + (t.af ? ' Su resultado está en el Análisis Financiero.' : '') };
  t.chips = [{ texto: 'Cerrado', nivel: 'ok' }].concat(t.chips.filter((c) => /^Terminó/.test(c.texto)));
  if (avance !== null && avance < 1) t.avisos.push('Está «Cerrado» en la Planilla de Ingreso, pero el Análisis Financiero tiene ' + Math.round(avance * 100) + ' % de avance: déjalo en 100 % en «Ingresar avance» para que su resultado cuente en el sesgo real.');
  t.antiguo = !!fin && rcDias(fin, hoy) < -RC_DIAS_ANTIGUO;
  t.orden = fin ? -fin.getTime() : MAXIMO;
}
/* Dado por cerrado en la Planificación semanal (2026-10-26): un proyecto en ejecución que ya terminó y se entregó,
   aunque no haya pasado por el Formulador ni tenga el 100 % en el Análisis Financiero. Va al «Cierre» como los
   terminados; e es lo último que se guardó para su N° o su TAG (plCierres). */
const rcClavesCierre = (t) => [t.req ? 'req:' + t.req : '', t.tag ? 'tag:' + t.tag : ''].filter(Boolean);
function rcCierreDe(t, cierres) {
  let u = null;
  rcClavesCierre(t).forEach((k) => { const e = cierres.get(k); if (e && (!u || e.t > u.t)) u = e; });
  return u;
}
function rcCerradoEnPlan(t, e, hoy) {
  const fin = new Date(e.t);
  const avance = t.af ? Math.max(0, Math.min(1, Number(t.af.avance) || 0)) : null;
  t.etapa = 'cierre';
  t.cierrePlan = e;
  t.accion = { tipo: 'listo', corto: 'Cerrado', nivel: '', ir: t.af && t.tag ? RC_IR.af(t.tag) : t.formulacion ? RC_IR.seguimiento(t.formulacion.uid) : null,
    texto: 'Dado por cerrado en la Planificación semanal' + (e.por ? ' por ' + e.por : '') + ' el ' + rcCorta(fin, hoy) + (e.nota ? ': «' + e.nota + '»' : '')
      + '. Ya no aparece en la planificación; si sigue en obra, reábrelo.' };
  t.chips = [{ texto: 'Cerrado', nivel: 'ok' }];
  if (avance !== null && avance < 1) {
    t.avisos.push(e.af ? 'Se pidió dejar su avance en 100 % en el Análisis Financiero: llega en la próxima vuelta del procesador.'
      : 'El Análisis Financiero tiene ' + Math.round(avance * 100) + ' % de avance: déjalo en 100 % en «Ingresar avance» para que su resultado cuente en el sesgo real.');
  }
  t.antiguo = rcDias(fin, hoy) < -RC_DIAS_ANTIGUO;
  t.orden = -fin.getTime();
}
/* Las carpetas de proyecto de la raíz de «Gestión de Proyectos» (2026-11-03, pedido del usuario: todas deben verse en
   «Proyectos en ejecución», sin las complementarias, que el procesador ya deja fuera). Estar ahí dice que se adjudicó y
   está en obra: su proyecto va a Ejecución aunque la Planilla no lo diga (lo avisa), y no se pliega por antiguo. */
const RC_GESTION_PARECIDO = 0.75;    // una carpeta sin N° se une por el nombre solo con un proyecto que se le parezca así
function rcConGestion(t, carpeta) {
  t.gestion = carpeta;
  t.carpetas = Object.assign({}, t.carpetas, { ejecucion: [carpeta].concat((t.carpetas.ejecucion || []).filter((x) => x !== carpeta)) });
}
// Su carpeta está en Gestión y la Planilla no dice «Adjudicado»: falta marcarlo, o la carpeta lleva el N° de otro
function rcAvisoGestion(t) {
  const r = t.planilla;
  if (!r) return 'Su carpeta está en Gestión de Proyectos, pero el N° ' + t.req + ' no está en la Planilla de Ingreso: revisa el N° adelante del nombre de la carpeta o regístralo en la Planilla.';
  const pe = texto(r.estado);
  return 'Su carpeta está en Gestión de Proyectos, pero la Planilla de Ingreso ' + (pe ? 'dice «' + pe + '»' : 'no tiene estado') + ' para el N° ' + t.req
    + (texto(r.titulo) ? ' («' + rcLegible(r.titulo) + '»)' : '') + ': si se adjudicó, márcalo «Adjudicado»; si es otro proyecto, corrige el N° adelante del nombre de la carpeta.';
}
/* Una carpeta de Gestión sin N° adelante: el proyecto adjudicado (en ejecución o cerrado) que más se le parece por el
   nombre, si es uno solo y se parece bastante («Junji Región de Valparaíso» ↔ JUNJ «Junji's Valparaiso»; no «Maipu -
   Calderas CESFAMs» ↔ «Llay llay Caldera CESFAM»). Con las palabras de «Proyectos en ejecución» (ejPalabras), pero el
   mismo nombre o al menos dos palabras en común: un título de una palabra («Catedral», «En obra») no se une con todo. */
function rcParecido(a, b) {
  if (norm(a).trim() === norm(b).trim()) return 1;
  const x = ejPalabras(a), y = ejPalabras(b);
  let n = 0;
  x.forEach((w) => { if (y.has(w)) n++; });
  return n >= 2 ? n / Math.min(x.size, y.size) : 0;
}
function rcGestionDe(carpeta, tarjetas, fuera = (t) => t.gestion) {
  let mejor = null, puntaje = 0, empate = false;
  tarjetas.forEach((t) => {
    if (fuera(t) || !(t.req || t.tag) || (t.etapa !== 'ejecucion' && t.etapa !== 'cierre')) return;
    const nombres = [t.titulo, t.af && t.af.nombre, t.planilla && t.planilla.titulo, t.formulacion && t.formulacion.titulo].map(texto).filter(Boolean);
    const x = Math.max(0, ...nombres.map((n) => rcParecido(carpeta, n)));
    if (x > puntaje) { mejor = t; puntaje = x; empate = false; } else if (x > 0 && x === puntaje) empate = true;
  });
  return mejor && !empate && puntaje >= RC_GESTION_PARECIDO ? mejor : null;
}
// Una carpeta de Gestión sin N° y sin proyecto que se le parezca: va sola, en ejecución, y pide su N°.
function rcTarjetaGestion(carpeta) {
  const t = rcBase('gestion-' + carpeta);
  rcConGestion(t, carpeta);
  t.titulo = carpeta;
  t.etapa = 'ejecucion';
  t.accion = { tipo: 'hacer', corto: 'Ponerle su N°', nivel: 'warn', ir: RC_IR.herr('planilla'),
    texto: 'Está en Gestión de Proyectos, pero su carpeta no lleva adelante el N° de la Planilla de Ingreso («N°. Nombre») y no se encontró su ficha en el Análisis Financiero: sin el N° no se une con su oferta, su avance ni sus facturas. Búscalo en la Planilla de Ingreso y renombra la carpeta; si no tiene, regístralo ahí.' };
  t.chips.push({ texto: 'Sin N°', nivel: 'warn' });
  return t;
}
/* Las carpetas de «0 Proyectos Entregados <año>» (2026-11-09, pedido del usuario: los proyectos que ya se cerraron van en
   su propia pestaña de «Proyectos en ejecución»). Marca t.entregado = { carpeta, grupo } en el proyecto de cada una: por
   su N° o, sin N°, por el nombre (rcGestionDe, sin los que siguen en la raíz de Gestión: «Capredena» entregado no es
   «297. CAPREDENA» en obra). Las que no calzan con ninguno vuelven como tarjetas aparte (rcTarjetaEntregada), que solo
   ve esta pestaña: el Recorrido no las muestra. Corre después de rcArmar, con sus tarjetas. */
function rcEntregadas(d, tarjetas) {
  const porReq = new Map();
  tarjetas.forEach((t) => { if (t.req && !porReq.has(t.req)) porReq.set(t.req, t); });
  const porNum = new Map();
  d.requerimientos.forEach((r) => { const n = rcNum(r && r.numero); if (n) porNum.set(n, r); });
  const sueltas = [];
  (d.entregados || []).forEach((g) => {
    const carpeta = texto(g && g.carpeta), grupo = texto(g && g.grupo);
    if (!carpeta) return;
    const n = rcNum(g.req);
    let t = n ? porReq.get(n) : rcGestionDe(carpeta, tarjetas, (x) => x.gestion || x.entregado);
    if (!t) {
      t = rcTarjetaEntregada(carpeta, grupo, n, n ? porNum.get(n) || null : null);
      sueltas.push(t);
      if (n) porReq.set(n, t);
    }
    if (t.entregado) {
      t.avisos.push('Tiene otra carpeta en los entregados («' + grupo + '/' + carpeta + '»): deja una sola.');
      return;
    }
    t.entregado = { carpeta, grupo };
    const ruta = grupo ? grupo + '/' + carpeta : carpeta;
    if (!(t.carpetas.ejecucion || []).includes(ruta) && !t.gestion) t.carpetas = Object.assign({}, t.carpetas, { ejecucion: [ruta].concat(t.carpetas.ejecucion || []) });
    if (t.gestion) t.avisos.push('Tiene carpeta en la raíz de Gestión de Proyectos y otra en «' + grupo + '»: si ya se entregó, deja solo la de los entregados; si sigue en obra, quita la otra.');
    else if (!n && t.req) t.avisos.push('Su carpeta en «' + grupo + '» («' + carpeta + '») no lleva su N° adelante y se reconoció por el nombre: renómbrala «' + t.req + '. ' + carpeta + '».');
  });
  sueltas.forEach((t) => {
    t.buscar = norm([t.req ? 'n' + t.req + ' n° ' + t.req : '', t.titulo, t.lugar, t.entregado && t.entregado.grupo, t.planilla && t.planilla.titulo].join(' '));
  });
  return sueltas;
}
// Una carpeta entregada que no calza con ningún proyecto del Recorrido: se ve en «Entregados» con su carpeta y su N°, si lo lleva
function rcTarjetaEntregada(carpeta, grupo, n, r) {
  const t = rcBase('entregado-' + (n || carpeta));
  t.req = n;
  t.planilla = r;
  t.titulo = rcSinNumero(carpeta);
  t.lugar = texto(r && r.ubicacion);
  t.etapa = 'cierre';
  const anio = /\b(\d{4})\b/.exec(grupo);
  t.orden = anio ? -Number(anio[1]) : MAXIMO;
  if (!n) t.chips.push({ texto: 'Sin N°', nivel: '' });
  return t;
}
// Un requerimiento de la Planilla, con lo que cuelga de él en las demás herramientas.
function rcTarjetaReq(n, x, hoy) {
  const { r, c, f, af, lic, g } = x;
  const t = rcBase('req-' + n);
  const pe = r ? texto(r.estado) : '';
  const fe = f ? f.estado : '';
  t.req = n;
  t.planilla = r; t.formulacion = f; t.af = af; t.lic = lic;
  t.carpetas = (c && c.carpetas && typeof c.carpetas === 'object') ? c.carpetas : {};
  t.fichaAjena = (c && Array.isArray(c.fichaAjena)) ? c.fichaAjena.map((x) => texto(x).toUpperCase()) : [];
  if (g) rcConGestion(t, g);
  t.cotizaciones = c && Array.isArray(c.cotizaciones) ? c.cotizaciones : [];
  t.tag = texto((af && af.tag) || (c && c.tag)).toUpperCase() || null;
  const carpeta = (t.carpetas.oferta || t.carpetas.ejecucion || [])[0];
  // El apodo del Análisis Financiero manda («Caldera Valdivia»); el N° va aparte, como siempre
  t.titulo = texto(af && af.apodo) || rcSinNumero(texto(carpeta).split('/').pop()) || (f && f.titulo) || rcLegible(r && r.titulo) || texto(af && af.nombre) || 'Requerimiento ' + n;
  t.lugar = texto(r && r.ubicacion) || texto(af && af.cliente);
  [t.responsable, t.respDe] = rcResponsable([f && f.responsable, 'responsable de la formulación'],
    [r && r.evaluador, 'evaluador en la Planilla'], [r && r.captador, 'captador en la Planilla']);
  const cierre = rcFecha(r && r.cierre) || rcFecha(lic && lic.fechaCierre);
  t.cierre = cierre;
  const dondeMarca = f ? RC_IR.seguimiento(f.uid) : RC_IR.planilla(n);

  if (af) {
    rcEtapaAF(t, af, hoy);
    if (fe === 'Cerrada') rcCerrada(t, f, hoy);
    else if (pe === 'Cerrado') rcCerradoPlanilla(t, hoy);
    else if (t.etapa === 'cierre' && fe === 'Adjudicada') t.avisos.push('Tiene 100 % de avance: márcalo «Cerrada» en el Seguimiento del Formulador para que quede descrito como terminado.');
    if (pe && !RC_GANADOS.includes(pe)) t.avisos.push('La Planilla de Ingreso dice «' + pe + '», pero el proyecto ya tiene ficha en el Análisis Financiero: corresponde «Adjudicado».');
    return t;
  }
  if (fe === 'Cerrada') {
    rcCerrada(t, f, hoy);
    if (pe && !RC_GANADOS.includes(pe)) t.avisos.push('Falta avisar «Adjudicado» a la Planilla de Ingreso.');
    return t;
  }
  if (pe === 'Cerrado') {
    rcCerradoPlanilla(t, hoy);
    return t;
  }
  if (pe === 'Adjudicado' || fe === 'Adjudicada' || t.gestion) {
    t.etapa = 'ejecucion';
    t.accion = f
      ? { tipo: 'hacer', corto: 'Pasar a ejecución', nivel: 'warn', ir: RC_IR.seguimiento(f.uid),
          texto: 'Adjudicado. Pásalo a ejecución desde el Seguimiento del Formulador: sus costos y su venta llegan al Análisis Financiero en un solo envío.' }
      : { tipo: 'hacer', corto: 'Crear su ficha en el Análisis', nivel: 'warn', ir: RC_IR.herr('ingresar'),
          texto: 'Adjudicado y sin ficha en el Análisis Financiero. Créala en «Ingresar avance» con su TAG y este N°, para seguir su avance y sus costos.' };
    if (fe === 'Adjudicada' && pe && !RC_GANADOS.includes(pe)) t.avisos.push('Falta avisar «Adjudicado» a la Planilla de Ingreso.');
    else if (t.gestion && !RC_GANADOS.includes(pe) && !rcEsTemporal(n)) t.avisos.push(rcAvisoGestion(t));
    const ref = cierre || rcFecha(r && r.apertura);
    t.antiguo = !!ref && rcDias(ref, hoy) < -RC_DIAS_ANTIGUO;
    t.orden = ref ? -ref.getTime() : MAXIMO;
    return t;
  }
  if (fe === 'Perdida' || fe === 'Descartada') {
    // El Formulador ya la cerró y la Planilla sigue diciendo que está viva: solo falta cambiarla en su fila
    const debe = fe === 'Perdida' ? 'No adjudicado' : 'Descartado';
    t.etapa = 'oferta';
    t.accion = { tipo: 'hacer', corto: 'Avisar en Requerimientos', nivel: 'warn', ir: RC_IR.planilla(n),
      texto: 'En el Formulador quedó «' + fe + '». Falta que la Planilla de Ingreso diga «' + debe + '»: cámbialo en su fila de Requerimientos.' };
    t.orden = cierre ? rcDias(cierre, hoy) : MAXIMO;      // como las demás ofertas: la más antigua arriba
    return t;
  }
  const enviada = pe === 'Ofertado' || fe === 'Enviada';
  if (enviada || t.cotizaciones.length) {
    t.etapa = 'oferta';
    const res = lic ? texto(lic.resultado) : '';
    const resuelta = ['ganada', 'otro', 'desierta', 'revocada'].includes(res);
    const desde = cierre || rcFecha(r && r.apertura);
    const dias = desde ? -rcDias(desde, hoy) : null;          // días desde que se entregó la oferta
    if (!enviada) {
      const folio = t.cotizaciones.map((x) => texto(x.folio)).filter(Boolean)[0];
      t.accion = { tipo: 'hacer', corto: 'Marcar como Enviada', nivel: rcNivel(cierre, hoy) || 'warn', ir: dondeMarca,
        texto: 'La cotización' + (folio ? ' ' + folio : '') + ' ya está emitida. Envíala al cliente y márcala como Enviada: el valor ofertado se avisa a la Planilla de Ingreso.' };
      if (cierre && rcDias(cierre, hoy) >= 0) t.chips.push(rcCierre(cierre, hoy));
    } else if (res === 'ganada') {
      t.accion = { tipo: 'hacer', corto: 'Marcar como Adjudicada', nivel: 'warn', ir: dondeMarca,
        texto: 'Mercado Público ya la adjudicó a QUEMPIN. Márcala Adjudicada' + (f ? ' en el Seguimiento del Formulador' : ' en Requerimientos') + ' y pásala a ejecución.' };
      t.chips.push({ texto: 'Ganada en Mercado Público', nivel: 'ok' });
    } else if (resuelta) {
      const que = { otro: 'la adjudicó a otro proveedor', desierta: 'la declaró desierta', revocada: 'la revocó' }[res];
      t.accion = { tipo: 'hacer', corto: 'Marcar «No adjudicado»', nivel: 'warn', ir: dondeMarca,
        texto: 'Mercado Público ' + que + '. Márcala «No adjudicado» en Requerimientos' + (f ? ', o como Perdida en el Seguimiento del Formulador, que se lo avisa' : '') + '.' };
      t.chips.push({ texto: { otro: 'Adjudicada a otro', desierta: 'Desierta', revocada: 'Revocada' }[res], nivel: '' });
    } else if (fe === 'Enviada' && pe !== 'Ofertado') {
      t.accion = { tipo: 'hacer', corto: 'Avisar en Requerimientos', nivel: 'warn', ir: RC_IR.planilla(n),
        texto: 'La oferta se envió. Falta que la Planilla de Ingreso diga «Ofertado»: cámbialo en su fila de Requerimientos (el valor ofertado va en el Excel).' };
    } else if (dias !== null && dias > RC_DIAS_SIN_RESPUESTA) {
      t.accion = { tipo: 'hacer', corto: 'Confirmar el resultado', nivel: '', ir: dondeMarca,
        texto: 'Lleva ' + dias + ' días sin respuesta. Confirma con el cliente o en Mercado Público si se adjudicó, y déjalo en Requerimientos.' };
    } else {
      t.accion = { tipo: 'espera', corto: 'Esperando respuesta', nivel: '', ir: f ? RC_IR.seguimiento(f.uid) : null,
        texto: 'Oferta enviada, esperando la respuesta del cliente' + (res === 'en-evaluacion' ? ' (en Mercado Público está en evaluación)' : '') + '. Cuando llegue, márcala Adjudicada o Perdida.' };
    }
    if (enviada && dias !== null && dias >= 0) {
      const como = cierre ? 'Ofertada' : 'Ingresó';      // sin cierre, se cuenta desde la apertura
      t.chips.push({ texto: dias === 0 ? como + ' hoy' : como + ' hace ' + pl(dias, 'día', 'días'), nivel: '' });
    }
    const adjudica = rcFecha(lic && lic.fechaAdjudicacion);
    if (enviada && !resuelta && adjudica && rcDias(adjudica, hoy) >= 0) t.chips.push({ texto: 'Adjudica ~' + rcCorta(adjudica, hoy), nivel: '' });
    if (pe === 'Ofertado' && RC_EN_FORMULACION.includes(fe)) t.avisos.push('La formulación sigue como «' + fe + '»: márcala Enviada en el Seguimiento para que su recorrido quede al día.');
    t.orden = dias !== null ? -dias : MAXIMO;
    return t;
  }
  // Antes de ofertar: lo manda el cierre de la licitación
  const vencida = !!cierre && rcDias(cierre, hoy) < 0;
  const nivel = vencida ? '' : rcNivel(cierre, hoy);
  if (cierre) t.chips.push(rcCierre(cierre, hoy));
  const visita = rcFecha(r && r.visita);
  if (visita && rcDias(visita, hoy) >= 0) {
    const d = rcDias(visita, hoy);
    t.chips.push({ texto: 'Visita ' + (d === 0 ? 'hoy' : d === 1 ? 'mañana' : 'el ' + rcCorta(visita, hoy)), nivel: d <= 2 ? 'warn' : '' });
  }
  t.orden = cierre ? cierre.getTime() : MAXIMO;
  if (x.borrador) {
    t.etapa = 'cotizacion';
    t.accion = { tipo: 'hacer', corto: 'Emitir en Sistema QUEMPIN', nivel, ir: RC_IR.herr('cotizacion'),
      texto: 'La cotización espera en Sistema QUEMPIN, en «Borradores del Formulador»: revísala y emítela con su folio.' };
  } else if (f) {
    const resumen = f.resumen || {};
    const errores = Number(resumen.errores) || 0;
    const avisos = Number(resumen.alertas) || 0;
    if (!errores && Number(resumen.precioNeto) > 0) {
      t.etapa = 'cotizacion';
      t.accion = { tipo: 'hacer', corto: 'Preparar la cotización', nivel, ir: RC_IR.seguimiento(f.uid),
        texto: 'La formulación ya tiene precio' + (avisos ? ' (con ' + pl(avisos, 'aviso', 'avisos') + ' por revisar)' : '') + '. Prepara la cotización desde el Seguimiento: llega a Sistema QUEMPIN para emitirse con su folio.' };
    } else {
      t.etapa = 'formulacion';
      t.accion = { tipo: 'hacer', corto: errores ? 'Corregir la formulación' : 'Seguir formulando', nivel, ir: RC_IR.req(n),
        texto: errores ? 'La formulación tiene ' + pl(errores, 'error', 'errores') + ': corrígelos en el Formulador antes de cotizar.'
          : 'La formulación está en curso: completa costos, utilidad y precio en el Formulador.' };
    }
  } else {
    t.etapa = 'requerimiento';
    t.accion = vencida
      ? { tipo: 'hacer', corto: 'Actualizar Requerimientos', nivel: '', ir: RC_IR.planilla(n),
          texto: 'Cerró el ' + rcCorta(cierre, hoy) + ' sin formulación. Si no se ofertó, márcalo «Descartado» en Requerimientos; si se ofertó, «Ofertado».' }
      : { tipo: 'hacer', corto: 'Formular', nivel, ir: RC_IR.req(n),
          texto: 'Decide si se oferta. Para ofertar, crea su formulación en el Formulador: queda unida a este N° y a su carpeta.' };
    t.antiguo = vencida && rcDias(cierre, hoy) < -RC_DIAS_ANTIGUO;
    if ((t.carpetas.oferta || []).length) t.chips.push({ texto: 'Carpeta creada', nivel: '' });
  }
  if (vencida && t.etapa !== 'requerimiento') t.avisos.push('Su cierre ya pasó (' + rcCorta(cierre, hoy) + '): si la oferta se entregó, márcala Enviada.');
  return t;
}
// Un presupuesto del Formulador sin N° de requerimiento: no se une con nada hasta que lo tenga.
function rcTarjetaSinReq(f, hoy) {
  const t = rcBase('f-' + f.uid);
  const mod = rcFecha(f.modificado);
  t.formulacion = f;
  t.titulo = f.titulo || 'Presupuesto sin nombre';
  t.lugar = f.cliente;
  t.etapa = 'requerimiento';
  t.accion = { tipo: 'hacer', corto: 'Escribir el N° de requerimiento', nivel: 'warn', ir: RC_IR.ficha(f.uid),
    texto: 'Este presupuesto (' + f.codigo + ') no tiene el N° de la Planilla de Ingreso: sin él no se une con su cotización, el Análisis Financiero ni el Flujo de Caja. Escríbelo en su Ficha.' };
  t.chips.push({ texto: 'Sin N°', nivel: 'warn' });
  t.antiguo = !!mod && rcDias(mod, hoy) < -RC_DIAS_ANTIGUO;
  t.orden = mod ? -mod.getTime() : MAXIMO;
  [t.responsable, t.respDe] = rcResponsable([f.responsable, 'responsable de la formulación']);
  return t;
}
// Un proyecto del Análisis Financiero sin N° de requerimiento (los de antes del 2026-10).
function rcTarjetaAF(af, hoy) {
  const t = rcBase('tag-' + texto(af.tag).toUpperCase());
  t.tag = texto(af.tag).toUpperCase();
  t.af = af;
  t.titulo = texto(af.apodo) || texto(af.nombre) || t.tag;
  t.lugar = texto(af.cliente);
  rcEtapaAF(t, af, hoy);
  t.avisos.push('No tiene N° de requerimiento: escríbelo en «Ingresar avance» para unirlo con su oferta y su Planilla.');
  if (t.etapa === 'ejecucion') t.chips.unshift({ texto: 'Sin N°', nivel: 'warn' });
  return t;
}
/* Todo el recorrido a partir de lo publicado. d: { requerimientos, cruce, af, licitaciones, formulaciones,
   borradores, cierres } tal como vienen de la carpeta (rcLeer). Devuelve las tarjetas, sin pintar. */
function rcArmar(d, hoy) {
  const porNum = new Map();
  d.requerimientos.forEach((r) => { const n = rcNum(r && r.numero); if (n) porNum.set(n, r); });
  const cruce = new Map(), lic = new Map(), afPorReq = new Map(), afPorTag = new Map();
  d.cruce.forEach((c) => { const n = rcNum(c && c.req); if (n) cruce.set(n, c); });
  d.licitaciones.forEach((l) => { const n = rcNum(l && l.req); if (n) lic.set(n, l); });
  /* Una ficha que el procesador marcó como de otro proyecto (fichaAjena: cada uno tiene su carpeta en el Centro de
     Costos, mismo_proyecto.py) no se une con el N° aunque lo lleve (2026-11-03, pedido del usuario: la ficha UMAG,
     «UMAG Linea de H2», llevaba el N° 280 y el 280 mostraba sus costos). */
  const ajena = (n, p) => { const c = cruce.get(n); return !!(c && Array.isArray(c.fichaAjena) && c.fichaAjena.map((x) => texto(x).toUpperCase()).includes(texto(p.tag).toUpperCase())); };
  d.af.forEach((p) => {
    if (!p || !texto(p.tag)) return;
    afPorTag.set(texto(p.tag).toUpperCase(), p);

    const n = rcNum(p.req);
    if (n && !ajena(n, p)) afPorReq.set(n, p);
  });
  cruce.forEach((c, n) => {      // el TAG que declaró otra herramienta (el Formulador, Sistema QUEMPIN)
    const p = afPorTag.get(texto(c.tag).toUpperCase());
    if (p && !afPorReq.has(n) && !rcNum(p.req) && !ajena(n, p)) afPorReq.set(n, p);
  });
  // Formulaciones del repositorio: la última versión de cada código manda, como en el Formulador.
  const porCodigo = new Map();
  d.formulaciones.forEach((x) => {
    const f = x.datos;
    if (!f || !f.uid || f.eliminado) return;
    const ficha = { uid: String(f.uid), codigo: texto(f.codigo) || String(f.uid), version: parseInt(f.version, 10) || 1,
      titulo: texto(f.titulo), cliente: texto(f.cliente), estado: texto(f.estado) || 'Borrador',
      responsable: texto(f.responsable).toUpperCase(), modificado: texto(f.modificado), req: reqDe(f), resumen: x.resumen || {} };
    const previo = porCodigo.get(ficha.codigo);
    if (!previo) { porCodigo.set(ficha.codigo, ficha); return; }
    const manda = previo.version > ficha.version || (previo.version === ficha.version && previo.modificado >= ficha.modificado) ? previo : ficha;
    manda.req = manda.req || previo.req || ficha.req;
    porCodigo.set(ficha.codigo, manda);
  });
  const formPorReq = new Map();
  const sinReq = [];
  porCodigo.forEach((f) => {
    if (!f.req) { if (!RC_FUERA.includes(f.estado) && f.estado !== 'Cerrada') sinReq.push(f); return; }
    const previo = formPorReq.get(f.req);
    if (!previo || previo.modificado < f.modificado) formPorReq.set(f.req, f);
  });
  const borradores = new Set();
  d.borradores.forEach((m) => { const n = rcNum(m.proyecto && m.proyecto.req); if (n) borradores.add(n); });
  // Entra lo que sigue vivo en la Planilla, lo que tiene formulación (si la Planilla no lo cerró) y lo
  // que tiene ficha en el Análisis Financiero.
  const nums = new Set();
  porNum.forEach((r, n) => { if (RC_VIVOS.includes(texto(r.estado))) nums.add(n); });
  formPorReq.forEach((f, n) => {
    const r = porNum.get(n);
    if ((!r || RC_VIVOS.includes(texto(r.estado))) && !RC_FUERA.includes(f.estado)) nums.add(n);
  });
  afPorReq.forEach((p, n) => nums.add(n));
  // ... y lo que tiene carpeta en la raíz de Gestión de Proyectos (2026-11-03), aunque nada más lo nombre
  const gesPorReq = new Map(), gesSinNum = [], gesNombreTemp = new Map();
  (d.gestion || []).forEach((g) => {
    const carpeta = texto(g && g.carpeta);
    const n = rcNum(g && g.req);
    if (!carpeta) return;
    if (n && rcEsTemporal(n)) gesNombreTemp.set(n, texto(g.tag).replace(/^\S+\s+-\s+/, '') || carpeta);
    if (!n) gesSinNum.push(carpeta);
    else if (!gesPorReq.has(n)) gesPorReq.set(n, carpeta);
  });
  gesPorReq.forEach((g, n) => nums.add(n));
  const tarjetas = [];
  nums.forEach((n) => tarjetas.push(rcTarjetaReq(n, { r: porNum.get(n) || null, c: cruce.get(n) || null, f: formPorReq.get(n) || null,
    af: afPorReq.get(n) || null, lic: lic.get(n) || null, borrador: borradores.has(n), g: gesPorReq.get(n) || null }, hoy)));
  tarjetas.forEach((t) => { if (t.req && gesNombreTemp.has(t.req)) t.titulo = gesNombreTemp.get(t.req); });
  sinReq.forEach((f) => tarjetas.push(rcTarjetaSinReq(f, hoy)));
  const unidos = new Set(afPorReq.values());
  afPorTag.forEach((p) => { if (!unidos.has(p)) tarjetas.push(rcTarjetaAF(p, hoy)); });
  const cierres = d.cierres || new Map();
  tarjetas.forEach((t) => {
    const e = t.etapa === 'ejecucion' ? rcCierreDe(t, cierres) : null;
    if (e && e.cerrado) rcCerradoEnPlan(t, e, hoy);
  });
  // Las carpetas de Gestión sin N°: con el proyecto que se les parece o, si no, solas
  gesSinNum.forEach((carpeta) => {
    const t = rcGestionDe(carpeta, tarjetas);
    if (!t) { tarjetas.push(rcTarjetaGestion(carpeta)); return; }
    rcConGestion(t, carpeta);
    t.avisos.push('Su carpeta en Gestión de Proyectos («' + carpeta + '») no lleva su N° adelante y se reconoció por el nombre: '
      + (t.req ? 'renómbrala «' + t.req + '. ' + carpeta + '»' : 'ponle adelante su N° de la Planilla de Ingreso («N°. Nombre»)') + ' para que las herramientas la unan sin adivinar.');
  });
  tarjetas.forEach((t) => {
    if (!t.gestion) return;
    if (t.etapa === 'ejecucion') t.antiguo = false;
    else t.avisos.push('Ya terminó, pero su carpeta sigue en la raíz de Gestión de Proyectos: si se entregó, muévela a «0 Proyectos Entregados» de su año; si sigue en obra, corrige su avance o reábrelo.');
  });
  // El avance pedido al Análisis Financiero que todavía espera al procesador (2026-10-28, «Proyectos en ejecución»): se ve
  // desde ya, sin cambiar la etapa, que sigue saliendo del Análisis Financiero
  const pedidos = new Map();
  (d.datosProyecto || []).forEach((m) => {
    const tag = texto(m.proyecto && m.proyecto.tag).toUpperCase();
    const v = m.valores && m.valores['% Avance'];
    const cuando = texto(m.origen && m.origen.enviado);
    if (tag && typeof v === 'number' && isFinite(v) && (!pedidos.has(tag) || pedidos.get(tag).enviado < cuando)) pedidos.set(tag, { valor: Math.max(0, Math.min(1, v)), enviado: cuando });
  });
  tarjetas.forEach((t) => {
    const p = t.af && t.tag ? pedidos.get(t.tag) : null;
    if (!p || t.etapa !== 'ejecucion') return;
    t.avancePedido = p;
    t.chips.push({ texto: 'Avance ' + Math.round(p.valor * 100) + ' % por aplicar', nivel: '' });
  });
  // El nombre pedido (2026-11-09: solo el apodo, desde el lápiz del Seguimiento o del Formulador) se ve desde ya
  const nombres = new Map();
  (d.datosProyecto || []).forEach((m) => {
    const tag = texto(m.proyecto && m.proyecto.tag).toUpperCase();
    const cuando = texto(m.origen && m.origen.enviado);
    if (tag && m.valores && 'Apodo' in m.valores && (!nombres.has(tag) || nombres.get(tag).enviado < cuando)) nombres.set(tag, { valor: texto(m.valores.Apodo), enviado: cuando });
  });
  tarjetas.forEach((t) => {
    const p = t.af && t.tag ? nombres.get(t.tag) : null;
    if (p) t.titulo = p.valor || texto(t.af.nombre) || t.titulo;
  });
  tarjetas.forEach((t) => {
    t.buscar = norm([t.req ? 'n' + t.req + ' n° ' + t.req : '', t.tag, t.titulo, t.lugar, t.responsable, t.planilla && t.planilla.titulo,
      t.planilla && t.planilla.referencia, t.formulacion && t.formulacion.codigo, t.lic && t.lic.comprador, t.af && t.af.nombre].join(' '));
  });
  return tarjetas;
}

// ---- Leer la carpeta del equipo -------------------------------------------------------------------
// Si este navegador puede cambiar algo en la carpeta: con el resumen del teléfono (js/resumen.js) se lee, pero no.
// Un control que cambia algo se habilita con esto, no con rc.dir; en solo lectura, portal.css lo esconde.
const rcEscribe = () => !!rc.dir && !soloLectura();
const rcSinBom = (s) => String(s).replace(/^﻿/, '');
async function rcSub(dir, ...camino) {
  try { let d = dir; for (const n of camino) d = await d.getDirectoryHandle(n); return d; } catch (e) { return null; }
}
async function rcJson(dir, archivo) {
  try { return JSON.parse(rcSinBom(await (await (await dir.getFileHandle(archivo)).getFile()).text())); } catch (e) { return null; }
}
// Todos los .json de una carpeta; uno a medio sincronizar se salta.
async function rcJsonDe(dir) {
  const salida = [];
  if (!dir) return salida;
  try {
    for await (const [n, h] of dir.entries()) {
      if (h.kind !== 'file' || !/\.json$/i.test(n)) continue;
      try { salida.push(JSON.parse(rcSinBom(await (await h.getFile()).text()))); } catch (e) { /* se salta */ }
    }
  } catch (e) { /* sin permiso */ }
  return salida;
}
async function rcLeer(dir) {
  const pub = await rcSub(dir, 'publicado');
  const leerPub = (n) => (pub ? rcJson(pub, n + '.json') : Promise.resolve(null));
  const [req, cruce, af, lic, est, repo, buzon, cierres] = await Promise.all([
    leerPub('requerimientos'), leerPub('proyectos'), leerPub('analisis-financiero'), leerPub('licitaciones'), leerPub('estado'),
    rcSub(dir, 'publicado', 'formulador').then(rcJsonDe), rcSub(dir, 'buzon').then(rcJsonDe),
    plLeerCierres(dir).catch((e) => { console.error(e); return plCierres().ef; })
  ]);
  const lista = (s, k) => (s && s.datos && Array.isArray(s.datos[k]) ? s.datos[k] : []);
  // La Planilla de Ingreso es la del Excel con lo ingresado o cambiado en el portal que todavía espera en el buzón (pqMezclar)
  const planillaPedidos = buzon.filter(pqEsPedido);
  const planilla = pqMezclar(lista(req, 'requerimientos'), planillaPedidos);
  return {
    requerimientos: planilla.filas, requerimientosExcel: lista(req, 'requerimientos'), planillaPedidos, planillaMeta: planilla.meta,
    planillaInfo: req && req.datos ? { actualizado: texto(req.datos.actualizado), generado: texto(req.generado),
      avisos: Array.isArray(req.datos.avisos) ? req.datos.avisos.map(texto).filter(Boolean) : [] } : null,
    cruce: lista(cruce, 'proyectos'), af: lista(af, 'proyectos'),
    gestion: lista(cruce, 'gestion'),      // las carpetas de proyecto de la raíz de Gestión de Proyectos (2026-11-03)
    entregados: lista(cruce, 'entregados'),    // ... y las de sus «0 Proyectos Entregados <año>» (2026-11-09)
    // Si el procesador ya publica esas listas: sin ellas, «Proyectos en ejecución» sigue con lo que el Recorrido pone en Ejecución
    hayGestion: !!(cruce && cruce.datos && Array.isArray(cruce.datos.gestion)),
    hayEntregados: !!(cruce && cruce.datos && Array.isArray(cruce.datos.entregados)),
    licitaciones: lista(lic, 'licitaciones'),
    formulaciones: repo.filter((x) => x && x.datos && typeof x.datos === 'object'),
    borradores: buzon.filter((m) => m && m.tipo === 'borrador-cotizacion' && m.destino === 'sistema-quempin'),
    // Lo pedido al Análisis Financiero que todavía espera (el avance, la mano de obra real…), y lo que dijo de cada pedido
    datosProyecto: buzon.filter((m) => m && m.tipo === 'datos-proyecto' && m.destino === 'analisis-financiero' && m.proyecto && m.valores && typeof m.valores === 'object'),
    afMensajes: af && af.datos && af.datos.mensajes && typeof af.datos.mensajes === 'object' ? af.datos.mensajes : {},
    cierres,
    pedidosVuelta: buzon.filter((m) => m && m.tipo === RC_VUELTA_TIPO && m.destino === RC_VUELTA_DESTINO),
    estado: est && est.datos ? est.datos : null,
    falta: [!req && 'la Planilla de Ingreso', !af && 'el Análisis Financiero'].filter(Boolean)
  };
}
// Lee la carpeta si este navegador ya tiene la biblioteca conectada y con permiso; si no, dice qué falta.
function rcCargar() {
  if (rc.leyendo) return rc.leyendo;
  rc.leyendo = (async () => {
    // Sin la carpeta (el teléfono, o un computador que no la conectó), el resumen cifrado de solo lectura (js/resumen.js)
    let dir = null;
    if (typeof window.showDirectoryPicker !== 'function') {
      dir = await mvAbrir('navegador');
      if (!dir) { rcSinDatos('navegador'); return; }
    } else {
      const c = await leerCarpetas();
      rc.carpetas = c;
      if (!c.intercambio) {
        dir = await mvAbrir('conectar');
        if (!dir) { rcSinDatos('conectar'); return; }
      } else {
        dir = await intercambioLegible(c);
        if (!dir) { mvSoltar(); rcSinDatos('permiso'); return; }
        mvSoltar();
      }
    }
    const datos = await rcLeer(dir);
    await cargarPulso();
    rc.datos = datos;
    leerApodos(datos.af);
    rc.pulso = lecturaPulso(datos.estado);
    rc.tarjetas = rcArmar(datos, new Date());
    rc.entregadas = rcEntregadas(datos, rc.tarjetas);
    rc.leido = Date.now();
    rc.sinDatos = null;
    rc.dir = dir;      // la Planificación semanal lee y guarda en la misma carpeta
  })().catch((e) => { console.error(e); rcSinDatos('error'); }).then(() => {
    rc.leyendo = null;
    rcVueltaAlLeer();
    if (!$('#vistaRecorrido').hidden) rcPintar();
    pintarInicioRecorrido();
    plAlRecorrido();
    scAlRecorrido();
    rdAlRecorrido();
    ejAlRecorrido();
    pqAlRecorrido();
    llAlRecorrido();
    obsAlRecorrido();
  });
  return rc.leyendo;
}
function rcAlMostrar() {
  if (!rc.leido || Date.now() - rc.leido > RC_RELEER_SEG * 1000) rcCargar();
  rcPintar();
}
function rcSinDatos(por) {
  rc.sinDatos = por;
  rc.tarjetas = [];
  rc.leido = 0;
  rc.dir = null;
}
// Desde el clic y sin esperas antes: el navegador solo pide permiso si viene de uno.
function rcPedirPermiso() {
  const h = rc.carpetas && (rc.carpetas.biblioteca || rc.carpetas.intercambio);
  if (!h) { rcCargar(); return; }
  h.requestPermission({ mode: 'readwrite' }).catch(() => null).then(() => rcCargar());
}

// ---- Pedir una vuelta al procesador ---------------------------------------------------------------
// ↻ solo vuelve a leer la carpeta; «Datos del procesador hace X» cambia cuando el procesador corre, y corre en su
// computador. «Actualizar datos» deja un pedido en el buzón y una tarea de ese computador lo toma (procesar.py
// --si-hay-pedido). Lo pendiente es lo que hay en el buzón, no algo de este navegador: sigue al recargar y también
// se ve el pedido de un colega.
const RC_VUELTA_TIPO = 'pedir-vuelta';
const RC_VUELTA_DESTINO = 'procesador';
const RC_VUELTA_ARCHIVO = /_pedir-vuelta_.*\.json$/i;
const RC_VUELTA_REVISAR_SEG = 10;
const RC_VUELTA_TARDA_MIN = 15;      // desde aquí dice que no responde: lo normal son unos 5 min
// estado.json dice si en el computador del procesador está la tarea que atiende el pedido al momento (2026-11-06:
// el botón se publicó antes que la tarea y prometía 5 minutos). Sin ella, el pedido espera la vuelta de cada 5 minutos,
// y así se dice; «no responde» recién pasadas 2 horas y media, como el pulso.
const RC_VUELTA_SIN_TAREA_TARDA_MIN = 150;
const rcSinTareaDePedidos = () => !!(rc.datos && rc.datos.estado && rc.datos.estado.pedidos && rc.datos.estado.pedidos.tarea === false);
const rcCorrida = (est) => (est && est.procesador && est.procesador.ultimaCorrida) || '';
// Hecha cuando el pedido salió del buzón y el pulso dice que corrió: OneDrive trae esos dos cambios por separado, y
// con uno solo lo que se ve todavía es lo de antes.
const rcVueltaHecha = (hayPedido, corrida) => !hayPedido && !!corrida && (corrida !== rc.vuelta.corrida || Date.parse(corrida) >= rc.vuelta.desde);
function rcVueltaEsperar(desde, corrida) {
  if (!rc.vuelta) rc.vuelta = { desde, corrida, reloj: setInterval(rcVueltaRevisar, RC_VUELTA_REVISAR_SEG * 1000) };
}
function rcVueltaAlLeer() {
  if (!rc.leido || !rc.datos) return;
  const corrida = rcCorrida(rc.datos.estado);
  const pedidos = rc.datos.pedidosVuelta;
  if (pedidos.length) {
    rcVueltaEsperar(Math.min(...pedidos.map((m) => Date.parse(m.origen && m.origen.enviado) || Date.now())), corrida);
  } else if (rc.vuelta && rcVueltaHecha(false, corrida)) {
    clearInterval(rc.vuelta.reloj);
    rc.vuelta = null;
    avisar('Datos del procesador actualizados.');
  }
}
// Mira solo los nombres del buzón y el pulso; la carpeta entera se relee cuando ya se hizo.
async function rcVueltaRevisar() {
  if (!rc.vuelta || !rc.dir || rc.leyendo || document.hidden) return;
  let hayPedido = false;
  const buzon = await rcSub(rc.dir, 'buzon');
  try {
    if (buzon) for await (const n of buzon.keys()) if (RC_VUELTA_ARCHIVO.test(n)) { hayPedido = true; break; }
  } catch (e) { return; }
  const pub = await rcSub(rc.dir, 'publicado');
  const est = pub ? await rcJson(pub, 'estado.json') : null;
  if (rc.vuelta && rcVueltaHecha(hayPedido, rcCorrida(est && est.datos))) rcCargar();
  else rcPintarFrescura();
}
async function rcPedirVuelta() {
  if (mvNoSe()) return;
  if (rc.vuelta || !rc.dir) return;
  const enviado = scAhora();
  const id = scId();
  const origen = { herramienta: 'portal', enviado };
  if (estado.usuario) origen.usuario = estado.usuario;
  const msg = { esquema: 'quempin.intercambio/1', id, tipo: RC_VUELTA_TIPO, destino: RC_VUELTA_DESTINO, origen };
  const nombre = enviado.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_' + RC_VUELTA_TIPO + '_' + id + '.json';
  try {
    const buzon = await rc.dir.getDirectoryHandle('buzon', { create: true });
    const w = await (await buzon.getFileHandle(nombre, { create: true })).createWritable();
    await w.write(JSON.stringify(msg, null, 2) + '\n');
    await w.close();
  } catch (err) {
    console.error(err);
    avisar('No se pudo pedir la actualización: revisa que OneDrive esté funcionando y vuelve a intentarlo.');
    return;
  }
  rcVueltaEsperar(Date.now(), rcCorrida(rc.datos && rc.datos.estado));
  rcPintarFrescura();
}

// ---- Filtros, resumen y orden ---------------------------------------------------------------------
const rcMia = (t) => !!estado.usuario && t.responsable === estado.usuario;
const RC_FOCOS = {
  accion: { es: (t) => t.accion.tipo === 'hacer' && !t.antiguo && (!estado.usuario || rcMia(t)) },
  cierran: { es: (t) => RC_ANTES_DE_OFERTAR.includes(t.etapa) && !!t.cierre && rcDias(t.cierre, new Date()) >= 0 && rcDias(t.cierre, new Date()) <= 7 },
  esperan: { es: (t) => t.accion.tipo === 'espera' },
  ejecucion: { es: (t) => t.etapa === 'ejecucion' && !t.antiguo }
};
function rcAlcance() {
  const q = norm(rc.q).trim().split(/\s+/).filter(Boolean);
  const mios = rc.mios && !!estado.usuario;
  return rc.tarjetas.filter((t) => (!mios || rcMia(t)) && q.every((x) => t.buscar.includes(x)));
}
const RC_PESO = { hacer: 2, curso: 3, espera: 4, listo: 5 };
const rcPeso = (t) => (t.accion.nivel === 'bad' ? 0 : t.accion.nivel === 'warn' ? 1 : RC_PESO[t.accion.tipo] || 6);
const rcOrden = (a, b) => rcPeso(a) - rcPeso(b) || a.orden - b.orden || (+(b.req || 0)) - (+(a.req || 0));
const rcEtapaN = (t) => RC_ETAPAS.findIndex((e) => e.id === t.etapa);

// ---- Pintar ---------------------------------------------------------------------------------------
function rcPintar() {
  const hay = rc.leido > 0;
  $('#rcLeyendo').hidden = hay || !!rc.sinDatos;
  $('#rcContenido').hidden = !hay;
  $('#rcVacio').hidden = hay || !rc.sinDatos;
  rcPintarFrescura();
  if (!hay) { if (rc.sinDatos) rcPintarVacio(rc.sinDatos); return; }
  rcPintarFiltros();
  const alcance = rcAlcance();
  rcPintarResumen(alcance);
  rcPintarTablero(alcance);
}
function rcPintarFrescura() {
  const txt = $('#rcFrescura');
  const punto = $('#rcPunto');
  const boton = $('#rcPedirVuelta');
  const sinTarea = rcSinTareaDePedidos();
  boton.hidden = !rc.leido;
  boton.disabled = !!rc.vuelta;
  boton.textContent = rc.vuelta ? 'Actualizando…' : 'Actualizar datos';
  boton.title = sinTarea
    ? 'Le pide al procesador una vuelta. En su computador falta la tarea que la da al momento: se atiende en la próxima vuelta (cada 5 minutos).'
    : 'Le pide al procesador una vuelta ahora, sin esperar la de cada 5 minutos. Tarda unos 5 min.';
  if (rc.leyendo) { txt.textContent = rc.leido ? 'Actualizando…' : 'Leyendo la carpeta del equipo…'; return; }
  if (!rc.leido) { txt.textContent = 'Sin datos de la carpeta del equipo'; punto.className = 'cx-punto'; txt.title = ''; return; }
  const l = rc.pulso;
  const haceTexto = (m) => (m < 1 ? 'hace un momento' : m < 60 ? 'hace ' + m + ' min' : m < 48 * 60 ? 'hace ' + Math.round(m / 60) + ' h' : 'hace ' + Math.round(m / 1440) + ' días');
  if (rc.vuelta) {
    const pedida = Math.max(0, Math.round((Date.now() - rc.vuelta.desde) / 60000));
    const tarda = pedida >= (sinTarea ? RC_VUELTA_SIN_TAREA_TARDA_MIN : RC_VUELTA_TARDA_MIN);
    txt.textContent = 'Actualización pedida ' + haceTexto(pedida) +
      (tarda ? ': el procesador aún no responde' : sinTarea ? ': se atiende en la próxima vuelta (cada 5 minutos)' : ': tarda unos 5 min');
    txt.title = tarda
      ? 'El pedido sigue en el buzón y se atiende apenas se pueda. El computador del procesador puede estar apagado, o su OneDrive atrasado.'
      : sinTarea
        ? 'En el computador del procesador falta la tarea que atiende estos pedidos al momento: el pedido espera la vuelta de cada 5 minutos. Avisa a quien administra las herramientas QUEMPIN.'
        : 'El computador del procesador toma el pedido y da una vuelta completa; lo demás es lo que OneDrive demora en llevar y traer los archivos.';
    punto.className = 'cx-punto ' + (tarda ? 'warn' : (l ? l.nivel : ''));
    return;
  }
  const min = l ? l.minutos : null;
  const hace = min === null ? '' : haceTexto(min);
  txt.textContent = l ? (l.detenido ? 'Procesador detenido: datos de ' + hace : 'Datos del procesador ' + hace) : 'Leído de la carpeta del equipo';
  txt.title = (l ? l.texto + ' ' : '') + 'Las formulaciones del equipo se leen al momento; la Planilla, el Análisis y Mercado Público, de la última vuelta del procesador.';
  punto.className = 'cx-punto ' + (l ? l.nivel : '');
}
function rcPintarVacio(por) {
  pintarSinCarpeta($('#rcVacio'), por, {
    navegador: 'El recorrido se arma con los datos de la carpeta del equipo, y este navegador no puede abrir carpetas del computador.',
    conectar: 'El recorrido lee lo que publican las herramientas en la carpeta de intercambio. Conecta una vez la biblioteca «' + BIBLIOTECA_FORMULACION + '» en este navegador (la misma conexión del Formulador) y acepta «Ver archivos».'
  });
}
// Sin la carpeta del equipo (el Recorrido y la Planificación semanal): qué falta y su botón. que: lo que dice cada
// vista de sí misma sin navegador que abra carpetas, o sin la biblioteca conectada.
function pintarSinCarpeta(v, por, que) {
  v.textContent = '';
  const ico = crear('span', 'ico');
  ico.append(icono(por === 'error' ? 'alerta' : 'nube', 26));
  const acc = crear('div', 'cx-acc');
  const boton = (txt, ir, pri) => {
    const b = crear('button', pri ? 'cx-boton' : 'cx-enlace', txt);
    b.type = 'button';
    b.addEventListener('click', ir);
    acc.append(b);
  };
  let tit, p;
  if (por === 'navegador') {
    tit = 'Ábrelo en Chrome o Edge de escritorio';
    p = que.navegador;
    boton('Copiar la dirección del portal', copiarDireccion, true);
  } else if (por === 'conectar') {
    tit = 'Conecta la biblioteca del equipo';
    p = que.conectar;
    boton('Conectar biblioteca', () => conectarBiblioteca().then(() => rcCargar()), true);
    boton('Ver Configuración y conexiones', () => abrir('conexiones'));
  } else if (por === 'permiso') {
    tit = 'Falta el permiso de esta sesión';
    p = 'La biblioteca está conectada, pero el navegador pide permiso otra vez para leerla.';
    boton('Dar permiso', rcPedirPermiso, true);
  } else {
    tit = 'No se pudo leer la carpeta del equipo';
    p = 'Puede que OneDrive esté sincronizando. Vuelve a intentarlo en un momento; si sigue, revisa Configuración y conexiones.';
    boton('Volver a intentar', () => rcCargar(), true);
    boton('Ver Configuración y conexiones', () => abrir('conexiones'));
  }
  v.append(ico, crear('h2', null, tit), crear('p', null, p), acc);
}
function rcPintarFiltros() {
  const u = estado.usuario;
  const caja = $('#rcMios');
  caja.disabled = !u;
  caja.checked = rc.mios && !!u;
  const t = $('#rcMiosTxt');
  t.textContent = 'Solo mis proyectos';
  if (u) { const b = crear('b', null, u); t.append(' ', b); }
  $('#rcElegir').hidden = !!u;
  const foco = $('#rcFoco');
  foco.hidden = !rc.foco;
  if (rc.foco) {
    foco.textContent = '';
    foco.append(crear('span', null, 'Mostrando: ' + rcFocoNombre(rc.foco)), icono('cerrar', 14));
    foco.setAttribute('aria-label', 'Quitar el filtro «' + rcFocoNombre(rc.foco) + '»');
  }
}
// Las cuatro cifras de arriba; cada una es también un filtro del tablero.
const rcKpis = () => [
  { id: 'accion', et: estado.usuario ? 'Te esperan' : 'Requieren acción', sub: estado.usuario ? 'Tuyos, con algo por hacer' : 'Elige tu usuario para ver los tuyos', alerta: 'warn' },
  { id: 'cierran', et: 'Cierran esta semana', sub: 'Por ofertar, vencen en 7 días o menos', alerta: 'bad' },
  { id: 'esperan', et: 'Esperan respuesta', sub: 'Ofertas enviadas, sin resultado aún', alerta: '' },
  { id: 'ejecucion', et: 'En ejecución', sub: 'Obras en curso en el Análisis Financiero', alerta: '' }
];
const rcFocoNombre = (id) => (rcKpis().find((k) => k.id === id) || {}).et || '';
function rcCifras(alcance) {
  return Object.fromEntries(Object.entries(RC_FOCOS).map(([id, f]) => [id, alcance.filter(f.es).length]));
}
function rcPintarResumen(alcance) {
  const n = rcCifras(alcance);
  const cont = $('#rcResumen');
  cont.textContent = '';
  rcKpis().forEach((k) => {
    const b = crear('button', 'rc-kpi');
    b.type = 'button';
    b.dataset.foco = k.id;
    if (k.alerta && n[k.id]) b.dataset.nivel = k.alerta;
    b.setAttribute('aria-pressed', rc.foco === k.id ? 'true' : 'false');
    b.append(crear('span', 'rc-kpi-n', String(n[k.id])), crear('span', 'rc-kpi-et', k.et), crear('span', 'rc-kpi-sub', k.sub));
    // La explicación de cada cifra, al pasar el mouse (2026-11-05: ya no va escrita debajo)
    b.title = rc.foco === k.id ? 'Mostrar todo otra vez' : k.sub + '. Toca para ver solo esos.';
    b.addEventListener('click', () => {
      rc.foco = rc.foco === k.id ? null : k.id;
      rcPintar();
      const otra = document.querySelector('.rc-kpi[data-foco="' + k.id + '"]');   // se repintó: el foco sigue en ella
      if (otra) otra.focus();
    });
    cont.append(b);
  });
}
function rcPintarTablero(alcance) {
  const foco = rc.foco ? RC_FOCOS[rc.foco] : null;
  const tab = $('#rcTablero');
  tab.textContent = '';
  let vistas = 0;
  const anchos = [];
  RC_ETAPAS.forEach((e, i) => {
    const todas = alcance.filter((t) => t.etapa === e.id && (!foco || foco.es(t))).sort(rcOrden);
    const actuales = todas.filter((t) => !t.antiguo);
    const antiguas = todas.filter((t) => t.antiguo);
    vistas += todas.length;
    const col = crear('section', 'rc-col');
    col.dataset.etapa = e.id;
    col.setAttribute('aria-labelledby', 'rc-et-' + e.id);
    const cab = crear('header', 'rc-col-cab');
    const tit = crear('div', 'rc-col-tit');
    const h2 = crear('h2', null, e.titulo);
    h2.id = 'rc-et-' + e.id;
    const cuenta = crear('span', 'rc-col-n', String(actuales.length));
    cuenta.title = pl(actuales.length, 'proyecto', 'proyectos') + (antiguas.length ? ' (y ' + antiguas.length + ' de antes, plegados)' : '');
    h2.title = e.titulo;
    tit.append(crear('span', 'rc-num', String(i + 1)), h2, cuenta);
    if (!todas.length) col.classList.add('vacia');
    anchos.push(todas.length ? 'minmax(0, 1fr)' : 'minmax(0, 0.6fr)');
    // Abajo del nombre: la herramienta donde se hace la etapa (la abre) y cuántos proyectos hay en ella
    const h = HERR.get(e.herr);
    const donde = crear('button', 'rc-donde');
    donde.type = 'button';
    donde.append(crear('span', null, h.nombre));
    if (h.tipo !== 'marco') donde.append(icono('fuera', 12));
    donde.title = 'Abrir ' + h.nombre + ': ' + (h.desc || '');
    donde.addEventListener('click', () => abrir(h.id));
    const pie = crear('div', 'rc-col-pie');
    pie.append(donde);
    cab.append(tit, pie);
    col.append(cab);
    if (e.id === 'requerimiento' && !rc.foco && !rc.q) {
      const nueva = crear('button', 'rc-nueva');
      nueva.type = 'button';
      nueva.append(icono('mas', 14), crear('span', null, 'Ver Oportunidades'));
      nueva.title = 'Licitaciones y compras ágiles de Mercado Público que calzan con QUEMPIN';
      nueva.addEventListener('click', () => abrir('oportunidades'));
      col.append(nueva);
    }
    const ul = crear('ul', 'rc-lista');
    actuales.forEach((t) => { const li = crear('li'); li.append(rcTarjetaEl(t)); ul.append(li); });
    col.append(ul);
    if (!actuales.length && !antiguas.length) col.append(crear('p', 'rc-vacia', rc.foco || rc.q || (rc.mios && estado.usuario) ? 'Nada con este filtro' : 'Nada en esta etapa'));
    if (antiguas.length) {
      const det = crear('details', 'rc-antiguos');
      det.append(crear('summary', null, (actuales.length ? '' : 'Nada reciente · ') + pl(antiguas.length, 'de antes', 'de antes') + ' (más de ' + RC_DIAS_ANTIGUO + ' días)'));
      const ul2 = crear('ul', 'rc-lista');
      antiguas.forEach((t) => { const li = crear('li'); li.append(rcTarjetaEl(t)); ul2.append(li); });
      det.append(ul2);
      col.append(det);
    }
    tab.append(col);
  });
  tab.style.setProperty('--rc-cols', anchos.join(' '));
  const de = rc.mios && estado.usuario ? 'tuyos' : 'del equipo';
  $('#rcCuenta').textContent = pl(vistas, 'proyecto ', 'proyectos ') + de;
}
function rcEtiqueta(t) {
  return t.req ? 'N° ' + t.req : t.tag ? t.tag : t.formulacion ? t.formulacion.codigo : '';
}
// conEtapa: fuera del tablero (en el Inicio) la tarjeta dice además en qué etapa va.
function rcTarjetaEl(t, conEtapa) {
  const art = crear('article', 'rc-tarjeta');
  art.dataset.clave = t.clave;
  art.dataset.etapa = t.etapa;
  art.dataset.tipo = t.accion.tipo;
  if (t.accion.nivel) art.dataset.nivel = t.accion.nivel;
  const mia = rcMia(t);
  if (mia) art.classList.add('tuya');
  const det = crear('button', 'rc-abrir');
  det.type = 'button';
  det.title = 'Ver su recorrido, sus datos y sus enlaces';
  const f1 = crear('span', 'rc-fila1');
  f1.append(crear('span', 'rc-n', rcEtiqueta(t)));
  if (t.req && t.tag) f1.append(crear('span', 'rc-tag', t.tag));
  const r = crear('span', 'rc-resp' + (t.responsable ? '' : ' nadie'), t.responsable || '—');
  r.title = t.responsable ? (mia ? 'Tuyo' : 'A cargo de ' + t.responsable) + ' (' + t.respDe + ')' : 'Sin responsable';
  f1.append(r);
  if (conEtapa) {
    const i = rcEtapaN(t);
    const et = crear('span', 'rc-etapa');
    const segs = crear('span', 'rc-segs');
    segs.setAttribute('aria-hidden', 'true');
    RC_ETAPAS.forEach((e, k) => segs.append(crear('span', k < i ? 'hecha' : k === i ? 'aqui' : null)));
    et.append(segs, crear('span', null, RC_ETAPAS[i].corto));
    et.title = 'Etapa ' + (i + 1) + ' de 6: ' + RC_ETAPAS[i].titulo;
    f1.append(et);
  }
  det.append(f1, crear('span', 'rc-tit', t.titulo));
  if (t.lugar) det.append(crear('span', 'rc-sub', t.lugar));
  if (t.etapa === 'ejecucion' && typeof t.avance === 'number') {
    const av = crear('span', 'rc-avance');
    const barra = crear('span', 'rc-barra');
    const lleno = crear('span');
    lleno.style.width = Math.round(t.avance * 100) + '%';
    barra.append(lleno);
    av.append(barra, crear('span', null, Math.round(t.avance * 100) + ' %'));
    av.title = 'Avance registrado en el Análisis Financiero';
    det.append(av);
  }
  const chips = t.chips.slice();
  if (t.avisos.length) chips.push({ texto: pl(t.avisos.length, 'dato por revisar', 'datos por revisar'), nivel: 'warn' });
  if (chips.length) {
    const c = crear('span', 'rc-chips');
    chips.forEach((x) => { const s = crear('span', 'rc-chip', x.texto); if (x.nivel) s.dataset.nivel = x.nivel; c.append(s); });
    det.append(c);
  }
  det.addEventListener('click', () => rcVerDetalle(t.clave));
  art.append(det);
  const a = t.accion;
  if (a.ir && a.tipo !== 'espera') {
    const b = crear('button', 'rc-accion');
    b.type = 'button';
    b.dataset.accion = a.corto;
    b.append(crear('span', null, a.corto), icono('derecha', 15));
    b.title = a.texto;
    b.addEventListener('click', () => rcIr(a.ir));
    art.append(b);
  } else {
    const s = crear('div', 'rc-espera');
    s.append(icono('reloj', 15), crear('span', null, a.corto));
    s.title = a.texto;
    art.append(s);
  }
  return art;
}
/* «Facturas del proyecto» (2026-10-29): la carpeta del proyecto en el Centro de Costos, en SharePoint. La
   dirección la publica el procesador (carpetas_proyecto.py); solo se abre si es del sitio de QUEMPIN. */
const RC_SHAREPOINT = 'https://quempinspa2020.sharepoint.com/';
const rcFacturasWeb = (t) => {
  const u = texto(((t.carpetas || {}).facturasWeb || [])[0]);
  return u.startsWith(RC_SHAREPOINT) ? u : null;
};
function rcIr(ir) {
  if (!ir) return;
  const dlg = $('#dlgRecorrido');
  if (dlg.open) dlg.close();
  if (ir.enlace) { abrirEnlace(ir.enlace); return; }
  if (ir.web) { window.open(ir.web, '_blank', 'noopener'); return; }
  if (ir.ejecucion) { ejAbrirProyecto(ir.ejecucion); return; }
  if (ir.planilla) { pqIrA(ir.planilla); return; }
  abrir(ir.herr, ir.url ? { url: ir.url } : {});
}

// ---- El detalle de un proyecto ---------------------------------------------------------------------
function rcPasos(t) {
  const i = RC_ETAPAS.findIndex((e) => e.id === t.etapa);
  return RC_ETAPAS.map((e, k) => {
    let est = k < i ? 'hecha' : k > i ? 'pendiente' : t.accion.tipo === 'espera' ? 'espera' : t.accion.tipo === 'listo' ? 'hecha' : 'actual';
    // Lo que se saltó sin dejar registro aquí (una obra de antes sin formulación ni cotización en las herramientas)
    if (k < i && ((e.id === 'formulacion' && !t.formulacion) || (e.id === 'cotizacion' && !t.cotizaciones.length) || (e.id === 'requerimiento' && !t.req))) est = 'omitida';
    return { e, n: k + 1, est };
  });
}
const RC_EST_TXT = { hecha: 'hecha', omitida: 'sin registro en las herramientas', actual: 'aquí está', espera: 'aquí está, esperando', pendiente: 'por venir' };
function rcVerDetalle(clave) {
  const t = rc.tarjetas.find((x) => x.clave === clave);
  if (!t) return;
  const cuerpo = $('#dlgRcCuerpo');
  cuerpo.textContent = '';
  $('#dlgRcTit').textContent = (rcEtiqueta(t) ? rcEtiqueta(t) + ' · ' : '') + t.titulo;
  const sub = [t.responsable ? (rcMia(t) ? 'Tuyo' : 'A cargo de ' + t.responsable) + ' (' + t.respDe + ')' : 'Sin responsable', t.lugar].filter(Boolean).join(' · ');
  cuerpo.append(crear('p', 'rc-det-sub', sub));
  const ol = crear('ol', 'rc-pasos');
  ol.setAttribute('aria-label', 'Las seis etapas del recorrido');
  rcPasos(t).forEach((p) => {
    const li = crear('li', 'rc-paso');
    li.dataset.est = p.est;
    const c = crear('span', 'p', p.est === 'hecha' ? '✓' : p.est === 'omitida' ? '–' : String(p.n));
    c.setAttribute('aria-hidden', 'true');
    li.append(c, crear('span', 'et', p.e.corto), crear('span', 'sr', ': ' + RC_EST_TXT[p.est]));
    li.title = p.e.titulo + ': ' + RC_EST_TXT[p.est];
    ol.append(li);
  });
  const etapa = RC_ETAPAS.find((e) => e.id === t.etapa);
  cuerpo.append(ol);
  const a = t.accion;
  const sigue = crear('section', 'rc-sigue');
  sigue.dataset.tipo = a.tipo;
  // La etapa ya se ve en los seis pasos de arriba (2026-11-05: sin repetirla aquí)
  sigue.append(crear('h3', null, a.tipo === 'espera' ? 'En espera' : a.tipo === 'listo' ? 'Terminado' : 'Qué sigue'),
    crear('p', null, a.texto));
  if (a.ir && !(soloLectura() && a.tipo === 'hacer')) {      // en solo lectura, lo que hay que hacer se lee, sin el botón
    const acc = crear('div', 'cx-acc');
    const b = crear('button', a.tipo === 'hacer' ? 'cx-boton' : 'cx-enlace', a.tipo === 'espera' ? 'Ver su seguimiento' : a.corto);
    b.type = 'button';
    b.addEventListener('click', () => rcIr(a.ir));
    acc.append(b);
    sigue.append(acc);
  }
  cuerpo.append(sigue);
  if (t.avisos.length) {
    const ul = crear('ul', 'rc-avisos');
    t.avisos.forEach((x) => { const li = crear('li'); li.append(icono('alerta', 16), crear('span', null, x)); ul.append(li); });
    cuerpo.append(ul);
  }
  const dl = crear('dl', 'rc-datos');
  const hoy = new Date();
  const fecha = (v) => { const f = rcFecha(v); return f ? rcCorta(f, hoy) : texto(v); };
  const dato = (et, val) => { if (texto(val)) dl.append(crear('dt', null, et), crear('dd', null, texto(val))); };
  const r = t.planilla;
  if (r) {
    dato('Planilla de Ingreso', [r.estado, r.canal].filter((x) => texto(x)).join(' · '));
    dato('Licitación', [r.titulo, r.referencia].filter((x) => texto(x)).join(' · '));
    dato('Evaluador · captador', [r.evaluador || '—', r.captador || '—'].join(' · '));
    dato('Apertura · cierre', [r.apertura ? fecha(r.apertura) : '—', r.cierre ? fecha(r.cierre) : '—'].join(' · '));
    const fv = rcFecha(r.visita);
    dato('Visita a terreno', fv ? rcCorta(fv, hoy) + (fv.getHours() || fv.getMinutes() ? ' a las ' + dos(fv.getHours()) + ':' + dos(fv.getMinutes()) : '') : r.visita);
  }
  if (t.lic) dato('Mercado Público', [t.lic.estado, t.lic.comprador].filter((x) => texto(x)).join(' · '));
  const f = t.formulacion;
  if (f) dato('Formulación', [f.codigo, f.estado, f.responsable && 'a cargo de ' + f.responsable, f.modificado && 'modificada el ' + fecha(f.modificado)].filter(Boolean).join(' · '));
  if (t.cotizaciones.length) dato('Cotizaciones', t.cotizaciones.map((x) => texto(x.folio) + (x.fecha ? ' (' + fecha(x.fecha) + ')' : '')).join(', '));
  if (t.af) dato('Análisis Financiero', [t.tag, Math.round((Number(t.af.avance) || 0) * 100) + ' % de avance', t.af.cierre && 'término ' + fecha(t.af.cierre)].filter(Boolean).join(' · '));
  if (dl.childElementCount) cuerpo.append(crear('h3', 'rc-det-h', 'Sus datos'), dl);
  // Sus enlaces: cada herramienta donde tiene algo, y sus carpetas en el Explorador
  const enl = crear('div', 'cx-acc');
  const enlace = (txt, ir, fuera) => {
    const b = crear('button', 'cx-enlace');
    b.type = 'button';
    b.append(crear('span', null, txt));
    if (fuera) b.append(icono('fuera', 14));
    b.addEventListener('click', () => rcIr(ir));
    enl.append(b);
  };
  if (t.etapa === 'ejecucion' || t.gestion || t.entregado) enlace('Su resumen en ejecución', RC_IR.ejecucion(t.clave));
  if (t.req) enlace('Formulador', RC_IR.req(t.req));
  else if (f) enlace('Formulador', RC_IR.ficha(f.uid));
  if (f) enlace('Seguimiento', RC_IR.seguimiento(f.uid));
  if (t.tag && t.af) { enlace('Análisis Financiero', RC_IR.af(t.tag)); enlace('Centro de Costos', RC_IR.cc(t.tag)); }
  if (t.lic && RC_MP.test(texto(t.lic.url))) enlace('Ficha en Mercado Público', { web: texto(t.lic.url) }, true);
  [['oferta', 'formulacion', 'Carpeta de la oferta'], ['ejecucion', 'gestion', 'Carpeta de ejecución']].forEach(([k, bib, txt]) => {
    const c = rcCarpeta((t.carpetas[k] || [])[0], bib);
    if (c && !MOVIL.matches) enlace(txt, { enlace: enlaceCarpeta(c) }, true);
  });
  if (rcFacturasWeb(t)) enlace('Facturas del proyecto', { web: rcFacturasWeb(t) }, true);
  if (enl.childElementCount) cuerpo.append(crear('h3', 'rc-det-h', 'Abrir'), enl);
  // En ejecución: darlo por cerrado si ya terminó; cerrado en la Planificación: reabrirlo (2026-10-26)
  if ((t.etapa === 'ejecucion' || t.cierrePlan) && rcClavesCierre(t).length) {
    const acc = crear('div', 'cx-acc');
    const b = crear('button', 'cx-enlace', t.cierrePlan ? 'Reabrir: sigue en obra' : 'Dar por cerrado');
    b.type = 'button';
    b.dataset.op = t.cierrePlan ? 'reabrir' : 'cerrar';
    b.disabled = !rcEscribe();
    b.title = t.cierrePlan ? 'Vuelve a ejecución y a la Planificación semanal' : 'Ya terminó y se entregó: pasa al «Cierre» y sale de la Planificación semanal';
    b.addEventListener('click', () => {
      if (t.cierrePlan) { plReabrir(t); rcVerDetalle(t.clave); return; }
      $('#dlgRecorrido').close();
      plAbrirProyectos(t.clave);
    });
    acc.append(b);
    cuerpo.append(crear('h3', 'rc-det-h', t.cierrePlan ? 'Cerrado en la planificación' : '¿Ya terminó?'), acc);
  }
  if (!$('#dlgRecorrido').open) $('#dlgRecorrido').showModal();
}
