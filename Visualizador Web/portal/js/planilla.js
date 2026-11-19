/* Portal QUEMPIN — Requerimientos, antes Planilla de Ingreso (pq*).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

/* ---- Planilla de Ingreso (2026-10-29) --------------------------------------------------------------------------------
   Pedido del usuario: «que la planilla de proyectos sea replicada en el portal», que desde ahora los requerimientos se
   ingresen aquí y que el Excel de siempre quede de respaldo, «actualizándose mutuamente». Se ve lo que publica el Excel
   (publicado/requerimientos.json) con lo ingresado o cambiado aquí que todavía espera en el buzón encima (pqMezclar): un
   requerimiento nuevo es un «nuevo-requerimiento» y un cambio, un «editar-requerimiento», que Sistema Intercambio/
   planilla_escritura.py escribe en el Excel cada minuto; en esa misma vuelta republica lo que alguien cambió en el
   Excel. Si una casilla cambió en los dos lados, manda el cambio más reciente.
   Solo las columnas que el equipo llena de verdad: las que tenían 45 % o más de casillas vacías o ilegibles (visita,
   visitador, presupuesto, valores, entrega y el contador de plazo) siguen solo en el Excel. Eval. y Cliente también las
   tenían contadas en toda la Planilla, pero se llenan en casi toda fila reciente y el usuario las dejó (2026-10-30). */
// «Cerrado» (2026-11-09): adjudicado y ya entregado. Al elegirlo, el diálogo ofrece llevar su carpeta de Gestión de
// Proyectos a «0 Proyectos Entregados <año>» (pqVerMover); lo hace el procesador (cierre_entregados.py).
const PQ_ESTADOS = ['Evaluación', 'Ofertado', 'Adjudicado', 'Cerrado', 'No adjudicado', 'Descartado'];
const PQ_CANALES = ['Mercado Público', 'Postventa', 'Sitio Web', 'RRSS', 'Ferias', 'Otro'];
// Las mismas del esquema editar-requerimiento y de planilla_escritura.EDITABLES (tests/portal/ las compara)
const PQ_COLUMNAS = [
  { id: 'numero', et: 'N°', clase: 'c-n' },
  { id: 'estado', et: 'Estado', clase: 'c-estado' },
  { id: 'canal', et: 'Canal', clase: 'c-canal', tarjeta: 'Canal' },
  { id: 'captador', et: 'Capt.', clase: 'c-capt', tarjeta: 'Capt.', ayuda: 'Captador: quien recibió el requerimiento' },
  { id: 'evaluador', et: 'Eval.', clase: 'c-eval', tarjeta: 'Eval.', ayuda: 'Evaluador: quien lo evalúa y formula' },
  { id: 'titulo', et: 'Título', clase: 'c-titulo' },
  { id: 'cliente', et: 'Cliente', clase: 'c-cli', tarjeta: 'Cliente' },
  { id: 'ubicacion', et: 'Ubicación', clase: 'c-ubic', tarjeta: 'Ubicación' },
  { id: 'referencia', et: 'ID o referencia', clase: 'c-ref', tarjeta: 'ID' },
  { id: 'apertura', et: 'Apertura', clase: 'c-ap', tarjeta: 'Apertura' },
  { id: 'cierre', et: 'Cierre', clase: 'c-ci', tarjeta: 'Cierre' }
];
const PQ_CAMPOS = PQ_COLUMNAS.map((c) => c.id).filter((c) => c !== 'numero');
// Lo que el formulario envía: las columnas de la tabla y el presupuesto del mandante (2026-11-11, pedido del usuario). El
// presupuesto no es columna de la tabla; su casilla del Excel ya existe («Presupuesto (IVA Inc)») y los dos esquemas lo traen.
const PQ_ENVIAR = PQ_CAMPOS.concat(['presupuesto']);
// Con los montos que exporta el Formulador: no son columnas de aquí, pero salen en la lista de cambios
const PQ_NOMBRE = Object.assign(Object.fromEntries(PQ_COLUMNAS.map((c) => [c.id, c.et])),
  { presupuesto: 'Presupuesto', valorOfertado: 'Valor ofertado', valorAdjudicado: 'Valor adjudicado' });
const PQ_FECHAS = ['apertura', 'cierre'];
const PQ_DESTINO = 'planilla-requerimientos';
const PQ_TIPOS = ['nuevo-requerimiento', 'editar-requerimiento'];
const PQ_ARCHIVO = /_portal_(nuevo|editar)-requerimiento_[A-Za-z0-9_-]{6,64}\.json$/;
const PQ_PAGINA = 150;               // filas a la vista; el resto con «Mostrar más»
const PQ_ESPERA_MIN = 30;            // un cambio que espera más que esto: ¿está encendido el computador del procesador?
const pq = { q: '', estado: '', mostrar: PQ_PAGINA, cambios: [], leyendo: null, leido: 0, abierta: null, inicial: null,
  guardando: false, irA: null, verCambios: false, conForm: false };

// Un monto en pesos como número entero positivo; vacío, cero o ilegible, null. Acepta «12.500.000», «$ 12500000» y 12500000.
function pqMonto(v) {
  if (typeof v === 'number') return Number.isFinite(v) && v > 0 ? Math.round(v) : null;
  const d = texto(v).replace(/[^\d]/g, '');
  return d && Number(d) > 0 ? Number(d) : null;
}
// La Planilla del Excel con lo ingresado o cambiado en el portal que todavía espera en el buzón, en orden de envío.
// meta (por fila): los campos que el Excel todavía no tiene, si es nueva y, si su N° ya lo tiene otra fila, cuál.
function pqMezclar(excel, pedidos) {
  const meta = new WeakMap();
  const filas = (excel || []).filter((r) => r && Number.isInteger(r.numero)).map((r) => Object.assign({}, r));
  const porN = new Map();
  filas.forEach((r) => { if (!porN.has(r.numero)) porN.set(r.numero, r); });
  const marca = (r) => {
    if (!meta.has(r)) meta.set(r, { campos: new Set(), nuevo: false, choque: '', mensajes: [] });
    return meta.get(r);
  };
  const valor = (v) => (typeof v === 'string' && v.trim() ? v.trim() : null);
  (pedidos || []).slice().sort((a, b) => texto(a.origen && a.origen.enviado).localeCompare(texto(b.origen && b.origen.enviado))).forEach((m) => {
    const r = m.requerimiento;
    if (!r || !Number.isInteger(r.numero) || r.numero < 1) return;
    if (m.tipo === 'nuevo-requerimiento') {
      const ya = porN.get(r.numero);
      if (ya && norm(ya.titulo).trim() === norm(r.titulo).trim()) return;   // ya está en el Excel: se archiva en la vuelta
      const fila = { numero: r.numero };
      PQ_ENVIAR.forEach((c) => { fila[c] = c === 'presupuesto' ? pqMonto(r[c]) : valor(r[c]); });
      const mt = marca(fila);
      mt.nuevo = true;
      mt.choque = ya ? texto(ya.titulo) || 'otro requerimiento' : '';
      mt.mensajes.push(m);
      PQ_ENVIAR.forEach((c) => mt.campos.add(c));
      filas.push(fila);
      if (!ya) porN.set(r.numero, fila);
      return;
    }
    if (m.tipo !== 'editar-requerimiento' || !m.cambios || typeof m.cambios !== 'object') return;
    const fila = porN.get(r.numero);
    if (!fila) return;
    const mt = marca(fila);
    Object.keys(m.cambios).forEach((c) => {
      if (!PQ_ENVIAR.includes(c)) return;
      fila[c] = c === 'presupuesto' ? pqMonto(m.cambios[c]) : valor(m.cambios[c]);
      mt.campos.add(c);
    });
    mt.mensajes.push(m);
  });
  return { filas, meta };
}
// Después de enviar o retirar algo: todas las vistas (el Recorrido también) ven la Planilla nueva desde ya
function pqRemezclar() {
  if (!rc.datos) return;
  const m = pqMezclar(rc.datos.requerimientosExcel, rc.datos.planillaPedidos);
  rc.datos.requerimientos = m.filas;
  rc.datos.planillaMeta = m.meta;
  rc.tarjetas = rcArmar(rc.datos, new Date());
}
const pqMeta = (r) => (rc.datos && rc.datos.planillaMeta ? rc.datos.planillaMeta.get(r) : null) || null;
const pqFilas = () => ((rc.datos && rc.datos.requerimientos) || []).slice().sort((a, b) => b.numero - a.numero);
/* Los N° que ya tienen formulación en el Formulador (2026-11-03, pedido del usuario): la última versión de cada
   código, unida al N° como en el Recorrido (reqDe). Las perdidas o descartadas también cuentan, marcadas aparte. */
let pqFormCache = { de: null, mapa: new Map() };
function pqFormulaciones() {
  const lista = rc.datos && rc.datos.formulaciones;
  if (pqFormCache.de === lista) return pqFormCache.mapa;
  const porCodigo = new Map();
  (lista || []).forEach((x) => {
    const f = x.datos;
    if (!f || !f.uid || f.eliminado) return;
    const req = reqDe(f);
    if (!req) return;
    const ficha = { uid: String(f.uid), codigo: texto(f.codigo) || String(f.uid), version: parseInt(f.version, 10) || 1,
      estado: texto(f.estado) || 'Borrador', responsable: texto(f.responsable).toUpperCase(), modificado: texto(f.modificado), req };
    const previo = porCodigo.get(ficha.codigo);
    if (!previo || previo.version < ficha.version || (previo.version === ficha.version && previo.modificado < ficha.modificado)) porCodigo.set(ficha.codigo, ficha);
  });
  const mapa = new Map();
  porCodigo.forEach((f) => { const p = mapa.get(f.req); if (!p || p.modificado < f.modificado) mapa.set(f.req, f); });
  pqFormCache = { de: lista, mapa };
  return mapa;
}
const pqForm = (r) => pqFormulaciones().get(String(r.numero)) || null;
const pqBuscable = (r) => norm(['n' + r.numero, r.numero, r.titulo, r.cliente, r.ubicacion, r.referencia, r.captador, r.evaluador, r.canal, r.estado].join(' '));
function pqFiltradas() {
  const q = norm(pq.q).trim().split(/\s+/).filter(Boolean);
  return pqFilas().filter((r) => (!pq.estado || texto(r.estado) === pq.estado) && (!pq.conForm || pqForm(r)) && q.every((x) => pqBuscable(r).includes(x)));
}
/* El N° de un requerimiento nuevo: el siguiente al mayor que ya se usa en la Planilla, en lo que espera en el buzón, en
   las carpetas de proyecto y en las formulaciones (como el Formulador). Si dos personas lo toman a la vez, el Excel le
   da al segundo el siguiente libre (numeroLibre) y el resultado lo dice. */
function pqSiguienteN() {
  const d = rc.datos || {};
  let max = 0;
  const ver = (v) => { const n = Number(v); if (Number.isInteger(n) && n > max && n < 100000) max = n; };
  (d.requerimientosExcel || []).forEach((r) => ver(r.numero));
  (d.planillaPedidos || []).forEach((m) => { if (m.tipo === 'nuevo-requerimiento') ver(m.requerimiento.numero); });
  (d.cruce || []).forEach((p) => ver(p && p.req));
  (d.formulaciones || []).forEach((f) => { const v = f.datos.vinculos && f.datos.vinculos.requerimiento; if (v) ver(v.numero); });
  return max + 1;
}
// Minutos desde el cambio más antiguo que todavía no llega al Excel, o null
function pqEsperaMin() {
  const t = ((rc.datos && rc.datos.planillaPedidos) || []).map((m) => new Date(texto(m.origen && m.origen.enviado))).filter((d) => !isNaN(d));
  return t.length ? Math.max(0, Math.round((Date.now() - Math.min(...t)) / 60000)) : null;
}
const pqHace = (min) => (min < 1 ? 'un momento' : min < 60 ? min + ' min' : min < 48 * 60 ? Math.round(min / 60) + ' h' : Math.round(min / 1440) + ' días');
const pqCuando = (f) => f.toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
// «2026-10-21T11:20» → «21-10-2026 11:20»; lo que no es fecha (algunas filas antiguas dicen «-»), tal cual
function pqFecha(v) {
  const s = texto(v);
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}:\d{2}))?/.exec(s);
  return m ? m[3] + '-' + m[2] + '-' + m[1] + (m[4] && m[4] !== '00:00' ? ' ' + m[4] : '') : s;
}

// ---- Leer: lo ingresado y cambiado desde el portal (lo que espera y lo que dijo el Excel) ----------------------------
function pqAlMostrar() {
  if (!rc.leyendo && (!rc.dir || !rc.leido || Date.now() - rc.leido > RC_RELEER_SEG * 1000)) rcCargar();   // al terminar llama a pqAlRecorrido
  else if (rc.dir) pqCargar();
  pqPintar();
}
function pqAlRecorrido() {
  if ($('#vistaPlanilla').hidden) return;
  if (rc.dir) pqCargar(); else pqPintar();
}
function pqCargar() {
  if (pq.leyendo) return pq.leyendo;
  const dir = rc.dir;
  if (!dir) return Promise.resolve();
  pq.leyendo = pqLeerCambios(dir).then((c) => { pq.cambios = c; pq.leido = Date.now(); }).catch((e) => console.error(e))
    .then(() => { pq.leyendo = null; pqPintar(); });
  pqPintar();
  return pq.leyendo;
}
// Del portal, este mes y el anterior: lo que espera en el buzón y lo que ya atendió el Excel (procesado), lo último primero
async function pqLeerCambios(dir) {
  const salida = [];
  const leer = async (carpeta, enCamino) => {
    if (!carpeta) return;
    try {
      for await (const [n, h] of carpeta.entries()) {
        if (h.kind !== 'file' || !PQ_ARCHIVO.test(n)) continue;
        let m;
        try { m = JSON.parse(rcSinBom(await (await h.getFile()).text())); } catch (e) { continue; }
        if (!m || !PQ_TIPOS.includes(m.tipo) || !m.requerimiento || typeof m.requerimiento !== 'object') continue;
        const r = m.resultado || {};
        salida.push({
          id: texto(m.id), tipo: m.tipo, enviado: texto(m.origen && m.origen.enviado), usuario: texto(m.origen && m.origen.usuario),
          numero: Number.isInteger(r.requerimiento) ? r.requerimiento : m.requerimiento.numero, titulo: texto(m.requerimiento.titulo),
          campos: m.cambios && typeof m.cambios === 'object' ? Object.keys(m.cambios) : [],
          estado: enCamino ? 'camino' : texto(r.estado), detalle: Array.isArray(r.detalle) ? r.detalle.map(texto) : []
        });
      }
    } catch (e) { /* sin permiso o a medio sincronizar */ }
  };
  const hoy = new Date();
  const mes = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
  await leer(await rcSub(dir, 'buzon'), true);
  await leer(await rcSub(dir, 'procesado', mes(hoy)), false);
  await leer(await rcSub(dir, 'procesado', mes(new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1))), false);
  const vistos = new Set();
  return salida.sort((a, b) => b.enviado.localeCompare(a.enviado)).filter((e) => !vistos.has(e.id) && vistos.add(e.id)).slice(0, 20);
}

// ---- Enviar y retirar ---------------------------------------------------------------------------------------------
// Deja el pedido en el buzón con el nombre de siempre (intercambio.nombre_mensaje) y lo suma a la Planilla desde ya.
async function pqEnviar(tipo, cuerpo) {
  if (soloLectura()) throw new Error('Solo lectura: en este navegador no se cambian los datos.');
  const enviado = scAhora();
  const id = scId();
  const origen = { herramienta: 'portal', enviado };
  if (estado.usuario) origen.usuario = estado.usuario;
  const msg = Object.assign({ esquema: 'quempin.intercambio/1', id, tipo, destino: PQ_DESTINO, origen }, cuerpo);
  const nombre = enviado.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_' + tipo + '_' + id + '.json';
  const buzon = await rc.dir.getDirectoryHandle('buzon', { create: true });
  const w = await (await buzon.getFileHandle(nombre, { create: true })).createWritable();
  await w.write(JSON.stringify(msg, null, 2) + '\n');
  await w.close();
  rc.datos.planillaPedidos = (rc.datos.planillaPedidos || []).concat([msg]);
  pq.cambios.unshift({ id, tipo, enviado, usuario: estado.usuario || '', numero: msg.requerimiento.numero, titulo: texto(msg.requerimiento.titulo),
    campos: msg.cambios ? Object.keys(msg.cambios) : [], estado: 'camino', detalle: [] });
  pqRemezclar();
  return msg;
}
// Un mensaje del buzón para la Planilla (nuevo o editar requerimiento)
function pqEsPedido(m) {
  return !!m && m.destino === PQ_DESTINO && PQ_TIPOS.includes(m.tipo) && !!m.requerimiento && typeof m.requerimiento === 'object';
}
// Antes de guardar uno nuevo: lo que hay ahora en el buzón y en la Planilla publicada (otro pudo ingresar mientras tanto)
async function pqReleer() {
  if (!rc.dir || !rc.datos) return;
  const [buzon, req] = await Promise.all([rcSub(rc.dir, 'buzon').then(rcJsonDe),
    rcSub(rc.dir, 'publicado').then((p) => (p ? rcJson(p, 'requerimientos.json') : null))]);
  rc.datos.planillaPedidos = buzon.filter(pqEsPedido);
  if (req && req.datos && Array.isArray(req.datos.requerimientos)) rc.datos.requerimientosExcel = req.datos.requerimientos;
  pqRemezclar();
}
// Retira del buzón lo que todavía no llega al Excel (lo busca por su id, como ejRetirarAF)
async function pqRetirar(c) {
  if (mvNoSe()) return;
  try {
    const buzon = await rc.dir.getDirectoryHandle('buzon');
    let nombre = null;
    for await (const n of buzon.keys()) if (n.indexOf(c.id) >= 0 && /\.json$/i.test(n)) { nombre = n; break; }
    if (!nombre) { avisar('Ya pasó al Excel: no se puede retirar. Si hace falta, cámbialo de nuevo.'); pqCargar(); return; }
    await buzon.removeEntry(nombre);
  } catch (err) {
    console.error(err);
    avisar('No se pudo retirar: revisa que OneDrive esté funcionando y vuelve a intentarlo.');
    return;
  }
  rc.datos.planillaPedidos = (rc.datos.planillaPedidos || []).filter((m) => m.id !== c.id);
  pq.cambios = pq.cambios.filter((x) => x.id !== c.id);
  pqRemezclar();
  pqPintar();
  avisar(c.tipo === 'nuevo-requerimiento' ? 'Se retiró el N° ' + c.numero + ': no llega al Excel.' : 'Se retiró el cambio: el Excel queda como estaba.');
}

// ---- El diálogo: un requerimiento nuevo o los datos de uno ---------------------------------------------------------
// Las opciones de la Planilla; un valor que el Excel tiene fuera de la lista (o vacío, en una fila que ya existe) también,
// para que se vea tal cual y no cuente como cambio si no se toca
function pqOpciones(sel, lista, valor, vacio) {
  sel.textContent = '';
  const v = texto(valor);
  const ops = (v && !lista.includes(v) ? [v].concat(lista) : lista).map((x) => [x, x]);
  if (!v && vacio) ops.unshift(['', '(vacío)']);
  ops.forEach(([x, et]) => { const o = crear('option', null, et); o.value = x; sel.append(o); });
  sel.value = v || (vacio ? '' : lista[0]);
}
function pqPonerFecha(pre, v) {
  const m = /^(\d{4}-\d{2}-\d{2})(?:T(\d{2}:\d{2}))?/.exec(texto(v));
  $('#pq' + pre + 'F').value = m ? m[1] : '';
  $('#pq' + pre + 'H').value = m && m[2] && m[2] !== '00:00' ? m[2] : '';
}
function pqLeerForm() {
  const t = (id) => $('#' + id).value.replace(/\s+/g, ' ').trim() || null;
  const fecha = (pre) => { const f = $('#pq' + pre + 'F').value, h = $('#pq' + pre + 'H').value; return f ? (h ? f + 'T' + h.slice(0, 5) : f) : null; };
  const capt = t('pqCaptador'), ev = t('pqEvaluador');
  return { estado: $('#pqEstado').value || null, canal: $('#pqCanal').value || null, captador: capt ? capt.toUpperCase() : null,
    evaluador: ev ? ev.toUpperCase() : null, titulo: t('pqTitulo'), cliente: t('pqCliente'), ubicacion: t('pqUbicacion'),
    // Una postventa guarda su proyecto original en «ID o referencia», como «164. Talca» (2026-11-06)
    referencia: $('#pqCanal').value === 'Postventa' ? pqOriginal(t('pqOriginal')) : t('pqReferencia'), apertura: fecha('Ap'), cierre: fecha('Ci'),
    presupuesto: pqMonto($('#pqPresupuesto').value) };
}
/* El proyecto original de una postventa, por su N° o por su nombre: «303» o «quemador» → «303. Quemador Osorno».
   Lo que no calza con un solo requerimiento queda tal como se escribió. */
function pqOriginal(txt) {
  if (!txt) return null;
  // Ya escrito como «N°. nombre» (o copiado de las sugerencias): se respeta tal cual
  if (/^\s*\d{1,6}\s*\.\s*\S/.test(txt)) return txt;
  const filas = pqFilas().filter((r) => rcNum(r.numero) && texto(r.titulo));
  const nombre = (r) => (rcNum(r.numero) + '. ' + (apodoDe(r.numero) || rcLegible(r.titulo))).slice(0, 80);
  const m = /^\s*(?:n[°º.]?\s*)?0*(\d{1,6})\s*$/i.exec(txt);
  if (m) { const r = filas.find((x) => rcNum(x.numero) === rcNum(m[1])); return r ? nombre(r) : txt; }
  const q = norm(txt);
  const hallas = filas.filter((r) => norm([r.titulo, apodoDe(r.numero)].join(' ')).includes(q));
  return hallas.length === 1 ? nombre(hallas[0]) : txt;
}
function pqVerOriginal() {
  const pv = $('#pqCanal').value === 'Postventa';
  $('#pqOriginalCampo').hidden = !pv;
  $('#pqReferenciaCampo').hidden = pv;
}
/* «Cerrado» y su carpeta (2026-11-09, pedido del usuario: al cambiar un proyecto a «Cerrado», una opción para mover su
   carpeta a la de entregados). La carpeta es la de su N° en la raíz de Gestión de Proyectos (proyectos.json, «gestion»);
   si hay dos con el mismo N°, ninguna: eso lo decide una persona. El procesador la mueve (mensaje mover-carpeta,
   cierre_entregados.py) cuando la Planilla ya dice «Cerrado», y nunca pisa otra con el mismo nombre. */
const PQ_ENTREGADOS = '0 Proyectos Entregados';
function pqCarpetaGestion(n) {
  const hay = ((rc.datos && rc.datos.gestion) || []).filter((g) => texto(g && g.carpeta) && rcNum(g.req) === rcNum(n));
  return hay.length === 1 ? texto(hay[0].carpeta) : null;
}
// Se muestra al elegir «Cerrado» en una fila que ya existe. Marcada si recién se cierra; sin marcar si ya estaba cerrado
// (abrir la fila para cambiar otra cosa no debe mover nada).
function pqVerMover(alAbrir) {
  const a = pq.abierta;
  const campo = $('#pqMoverCampo');
  const caja = $('#pqMover');
  const visible = !!a && !a.nuevo && $('#pqEstado').value === 'Cerrado';
  const aparece = campo.hidden;
  campo.hidden = !visible;
  if (!visible) return;
  const carpeta = pqCarpetaGestion(a.numero);
  caja.disabled = !carpeta;
  // Lo que la persona ya marcó o desmarcó se respeta mientras siga en «Cerrado»
  if (alAbrir === true || aparece || !carpeta) caja.checked = !!carpeta && texto(a.fila && a.fila.estado) !== 'Cerrado';
  $('#pqMoverTxt').textContent = carpeta ? 'Mover su carpeta a «' + PQ_ENTREGADOS + ' ' + new Date().getFullYear() + '»'
    : 'Sin carpeta con el N° ' + a.numero + ' en Gestión de Proyectos';
  $('#pqMoverDe').textContent = carpeta ? 'Gestión de Proyectos › ' + carpeta : 'Si ya está en «' + PQ_ENTREGADOS + '», no hay nada que mover.';
}
async function pqEnviarMover(numero, titulo) {
  if (mvNoSe()) return;
  const enviado = scAhora();
  const id = scId();
  const origen = { herramienta: 'portal', enviado };
  if (estado.usuario) origen.usuario = estado.usuario;
  const requerimiento = { numero };
  if (titulo) requerimiento.titulo = titulo;
  const msg = { esquema: 'quempin.intercambio/1', id, tipo: 'mover-carpeta', destino: 'carpetas-proyecto', origen, requerimiento, estado: 'Cerrado' };
  const nombre = enviado.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_mover-carpeta_' + id + '.json';
  const buzon = await rc.dir.getDirectoryHandle('buzon', { create: true });
  const w = await (await buzon.getFileHandle(nombre, { create: true })).createWritable();
  await w.write(JSON.stringify(msg, null, 2) + '\n');
  await w.close();
  return msg;
}
// Sugerencias al escribir: el equipo y los captadores de la Planilla; las ubicaciones, de la más usada a la menos
function pqListas() {
  const filas = pqFilas();
  const contar = (campo) => {
    const n = new Map();
    filas.forEach((r) => { const v = texto(r[campo]); if (v) n.set(v, (n.get(v) || 0) + 1); });
    return [...n.entries()].sort((a, b) => b[1] - a[1]).map(([v]) => v);
  };
  const llenar = (dl, valores) => { dl.textContent = ''; valores.slice(0, 200).forEach((v) => { const o = crear('option'); o.value = v; dl.append(o); }); };
  llenar($('#pqUsuarios'), [...new Set(USUARIOS.concat(contar('captador'), contar('evaluador')))]);
  llenar($('#pqLugares'), contar('ubicacion'));
  llenar($('#pqClientes'), contar('cliente'));
  // Para el proyecto original de una postventa: primero los adjudicados, del más nuevo al más antiguo
  const orden = (r) => (/^(adjudicad|cerrad)/i.test(texto(r.estado)) ? 0 : 1);
  llenar($('#pqProyectos'), filas.filter((r) => rcNum(r.numero) && texto(r.titulo))
    .sort((a, b) => orden(a) - orden(b) || rcNum(b.numero) - rcNum(a.numero))
    .map((r) => (rcNum(r.numero) + '. ' + (apodoDe(r.numero) || rcLegible(r.titulo))).slice(0, 80)));
}
function pqAbrir(fila, pre) {
  if (!fila && mvNoSe()) return;      // un requerimiento nuevo; uno que ya está se puede mirar
  if (!rc.dir || !rc.datos) return;
  const nuevo = !fila;
  const n = nuevo ? pqSiguienteN() : fila.numero;
  const mt = fila ? pqMeta(fila) : null;
  pq.abierta = { nuevo, numero: n, fila };
  // pre: lo que trae el Formulador («Ingresar en Requerimientos», pqNuevoCon)
  const v = fila || Object.assign({ estado: 'Evaluación', canal: 'Mercado Público', captador: estado.usuario || null, apertura: plISO(new Date()) }, pre || {});
  $('#dlgPqTit').textContent = nuevo ? 'Nuevo requerimiento · N° ' + n : 'Requerimiento N° ' + n;
  pqOpciones($('#pqEstado'), PQ_ESTADOS, v.estado, !nuevo);
  pqOpciones($('#pqCanal'), PQ_CANALES, v.canal, !nuevo);
  $('#pqTitulo').value = texto(v.titulo);
  $('#pqCaptador').value = texto(v.captador);
  $('#pqEvaluador').value = texto(v.evaluador);
  $('#pqCliente').value = texto(v.cliente);
  $('#pqUbicacion').value = texto(v.ubicacion);
  $('#pqReferencia').value = texto(v.referencia);
  $('#pqPresupuesto').value = pqMonto(v.presupuesto) ? pqMonto(v.presupuesto).toLocaleString('es-CL') : '';
  $('#pqOriginal').value = texto(v.canal) === 'Postventa' ? texto(v.referencia) : '';
  pqVerOriginal();
  pqVerMover(true);
  pqPonerFecha('Ap', v.apertura);
  pqPonerFecha('Ci', v.cierre);
  pqListas();
  const pista = $('#pqPista');
  pista.classList.remove('error');
  // Nuevo: el título ya dice su N°; el resto de la explicación va en el ⓘ del pie (2026-11-05)
  pista.textContent = nuevo ? ''
    : mt && mt.choque ? 'El N° ' + n + ' ya es «' + mt.choque + '» en el Excel: al pasar, este requerimiento queda con el siguiente N° libre.'
      : mt && mt.nuevo ? 'Recién agregado: todavía no llega al Excel.'
        : mt && mt.campos.size ? 'Lo marcado con un punto naranjo en la tabla (' + [...mt.campos].map((c) => PQ_NOMBRE[c]).join(', ') + ') todavía no llega al Excel.' : '';
  $('#pqNota').replaceChildren(info(nuevo
    ? 'Queda con el N° ' + n + ', el siguiente libre. El equipo lo ve al instante aquí y pasa al Excel en un par de minutos. Los valores ofertado y adjudicado los exporta el Formulador; el Excel está protegido.'
    : 'Lo que cambies aquí lo ve el equipo al instante y pasa al Excel en un par de minutos. El Excel está protegido: los cambios se hacen aquí.', 'Qué pasa al guardar'));
  $('#pqGuardar').textContent = nuevo ? 'Agregar a Requerimientos' : 'Guardar cambios';
  $('#pqGuardar').disabled = false;
  $('#pqFormular').hidden = nuevo;
  pq.inicial = pqLeerForm();
  const dlg = $('#dlgPlanilla');
  if (!dlg.open) dlg.showModal();
  (nuevo ? $('#pqTitulo') : $('#pqEstado')).focus();
}
function pqError(msg, campo) {
  const p = $('#pqPista');
  p.textContent = msg;
  p.classList.add('error');
  if (campo) campo.focus();
}
async function pqGuardar(ev) {
  if (mvNoSe()) { if (ev) ev.preventDefault(); return; }
  if (ev) ev.preventDefault();
  const a = pq.abierta;
  if (!a || pq.guardando || !rc.dir) return;
  const f = pqLeerForm();
  if (!f.titulo) { pqError('Falta el título: una descripción breve del requerimiento.', $('#pqTitulo')); return; }
  for (const [pre, campo, nombre] of [['Ap', 'apertura', 'apertura'], ['Ci', 'cierre', 'cierre']]) {
    if (!f[campo] && $('#pq' + pre + 'H').value) { pqError('Falta la fecha de ' + nombre + ' de esa hora.', $('#pq' + pre + 'F')); return; }
  }
  // El N° de un requerimiento nuevo se vuelve a calcular al guardar (2026-11-12), con lo que llegó mientras se escribía:
  // un formulario abierto un buen rato no debe proponer un N° que otro ya tomó
  let nAntes = null;
  if (a.nuevo) {
    pq.guardando = true;
    try { await pqReleer(); } catch (e) { console.warn('Requerimientos: no se releyó antes de guardar', e); }
    pq.guardando = false;
    const n = pqSiguienteN();
    if (n > a.numero) { nAntes = a.numero; a.numero = n; }
  }
  let cuerpo, cambios = null;
  const mover = !a.nuevo && !$('#pqMoverCampo').hidden && $('#pqMover').checked && !$('#pqMover').disabled ? pqCarpetaGestion(a.numero) : null;
  if (a.nuevo) {
    const req = { numero: a.numero };
    PQ_ENVIAR.forEach((c) => { if (f[c] !== null) req[c] = f[c]; });
    cuerpo = { requerimiento: req, fuente: { herramienta: 'portal' }, numeroLibre: true };
  } else {
    cambios = {};
    const reemplaza = {};
    PQ_ENVIAR.forEach((c) => {
      if (f[c] === pq.inicial[c]) return;
      if (c === 'presupuesto' && f[c] === null) return;   // el esquema no deja vaciarlo desde aquí: se vacía en el Excel
      cambios[c] = f[c];
      reemplaza[c] = a.fila[c] === null || a.fila[c] === undefined || a.fila[c] === '' ? null : String(a.fila[c]);
    });
    if (!Object.keys(cambios).length && !mover) { $('#dlgPlanilla').close(); avisar('No cambiaste nada: el N° ' + a.numero + ' queda como estaba.'); return; }
    const req = { numero: a.numero };
    if (texto(a.fila.titulo)) req.titulo = texto(a.fila.titulo);
    cuerpo = Object.keys(cambios).length ? { requerimiento: req, cambios, reemplaza } : null;
  }
  pq.guardando = true;
  $('#pqGuardar').disabled = true;
  try {
    if (cuerpo) await pqEnviar(a.nuevo ? 'nuevo-requerimiento' : 'editar-requerimiento', cuerpo);
    if (mover) await pqEnviarMover(a.numero, texto(a.fila.titulo));
  } catch (err) {
    console.error(err);
    pqError(err && err.name === 'NotAllowedError' ? 'Falta el permiso para escribir en la carpeta del equipo: usa «Volver a leer» arriba y acepta «Ver y editar archivos».'
      : 'No se pudo guardar: revisa que OneDrive esté funcionando y vuelve a intentarlo.');
    return;
  } finally {
    pq.guardando = false;
    $('#pqGuardar').disabled = false;
  }
  $('#dlgPlanilla').close();
  const fila = (rc.datos.requerimientos || []).find((r) => r.numero === a.numero && (!a.nuevo || pqMeta(r)));
  if (fila && pq.estado && texto(fila.estado) !== pq.estado) pq.estado = '';
  if (fila && pq.q && !pqBuscable(fila).includes(norm(pq.q).trim())) { pq.q = ''; $('#pqBuscar').value = ''; }
  pqPintar();
  pqResaltar(a.numero);
  // La carpeta la mueve el procesador: se le pide una vuelta para que no espere la de cada 5 minutos
  if (mover) rcPedirVuelta().catch((err) => console.error(err));
  const carpeta = mover ? ' Su carpeta pasa a «' + PQ_ENTREGADOS + '» ' + (rcSinTareaDePedidos() ? 'en la próxima vuelta del procesador.' : 'en unos minutos.') : '';
  avisar(a.nuevo ? (nAntes ? 'El N° ' + nAntes + ' lo tomó otro requerimiento mientras escribías: ' : '') + 'N° ' + a.numero + ' agregado a Requerimientos. Pasa al Excel en un par de minutos.'
    : !cuerpo ? 'N° ' + a.numero + ':' + carpeta
      : 'N° ' + a.numero + ': ' + Object.keys(cambios).map((c) => PQ_NOMBRE[c]).join(', ') + ' cambiado. Pasa al Excel en un par de minutos.' + carpeta);
}
function pqResaltar(n) {
  const tr = document.querySelector('#pqFilas tr[data-n="' + n + '"]');
  if (!tr) return;
  tr.scrollIntoView({ block: 'center', behavior: REDUCIR.matches ? 'auto' : 'smooth' });
  tr.classList.add('resaltada');
  setTimeout(() => tr.classList.remove('resaltada'), 2400);
}
// Desde el Recorrido: la vista con la fila de ese N° abierta (cuando la carpeta ya está leída)
function pqIrA(n) {
  pq.irA = Number(n);
  abrir('planilla');
  pqAbrirPendiente();
}
/* «Ingresar en Requerimientos» del Formulador (2026-11-12, fase 1 del plan contra choques de N°: solo el Portal da N°).
   Llega como mensaje (el Formulador dentro del portal) o en la dirección (…/portal/#/planilla?nuevo=<JSON>): abre
   «Nuevo requerimiento» con lo que trae, y el N° lo pone el portal como siempre. Solo campos conocidos, como texto. */
const PQ_PRELLENO = ['titulo', 'cliente', 'ubicacion', 'referencia', 'canal', 'estado', 'evaluador', 'cierre', 'presupuesto'];
function pqNuevoCon(datos) {
  if (!datos || typeof datos !== 'object') return;
  const v = {};
  PQ_PRELLENO.forEach((k) => {
    const x = datos[k];
    if (k === 'presupuesto') { if (typeof x === 'number' && x > 0) v[k] = x; return; }
    if (typeof x === 'string' && x.trim()) v[k] = x.trim().slice(0, 250);
  });
  if (v.canal && !PQ_CANALES.includes(v.canal)) delete v.canal;
  if (v.estado && !PQ_ESTADOS.includes(v.estado)) delete v.estado;
  if (v.cierre && !/^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$/.test(v.cierre)) delete v.cierre;
  pq.nuevoCon = v;
  abrir('planilla');
  pqAbrirPendiente();
}
function pqAbrirPendiente() {
  if (pq.nuevoCon && rc.datos && rc.dir && !$('#vistaPlanilla').hidden && !$('#dlgPlanilla').open) {
    const v = pq.nuevoCon;
    pq.nuevoCon = null;
    pqAbrir(null, v);
    return;
  }
  if (!pq.irA || !rc.datos || $('#vistaPlanilla').hidden) return;
  const n = pq.irA;
  pq.irA = null;
  const r = (rc.datos.requerimientos || []).find((x) => x.numero === n);
  if (!r) return;
  pq.q = '';
  $('#pqBuscar').value = '';
  pq.estado = '';
  pqPintarEstados();
  pqPintarTabla();
  pqResaltar(n);
  pqAbrir(r);
}

// ---- Pintar -------------------------------------------------------------------------------------------------------
function pqPintar() {
  const hay = !!rc.dir && !!rc.datos;
  $('#pqLeyendo').hidden = hay || !rc.leyendo;
  $('#pqContenido').hidden = !hay;
  $('#pqVacio').hidden = hay || !!rc.leyendo || !rc.sinDatos;
  if (!hay && !rc.leyendo && rc.sinDatos) {
    pintarSinCarpeta($('#pqVacio'), rc.sinDatos, {
      navegador: 'Requerimientos se lee y se escribe en la carpeta del equipo, y este navegador no puede abrir carpetas del computador. El Excel de respaldo sí se abre en cualquier navegador.',
      conectar: 'Requerimientos se lee y se escribe en la carpeta de intercambio. Conecta una vez la biblioteca «' + BIBLIOTECA_FORMULACION + '» en este navegador (la misma conexión del Formulador) y acepta «Ver y editar archivos».'
    });
    // Sin carpeta (un teléfono, otro computador), el Excel sigue a mano: antes del 2026-10-29 era lo único que abría
    const acc = $('#pqVacio .cx-acc');
    const a = crear('a', 'cx-enlace');
    a.href = HERR.get('planilla').url;
    a.target = '_blank';
    a.rel = 'noopener';
    a.append(crear('span', null, 'Abrir el Excel de respaldo'), icono('fuera', 14));
    acc.append(a);
  }
  pqPintarFrescura();
  if (!hay) return;
  pqPintarEstados();
  pqPintarSinc();
  pqPintarTabla();
  pqAbrirPendiente();
}
function pqPintarFrescura() {
  const txt = $('#pqFrescura');
  const punto = $('#pqPunto');
  if (rc.leyendo) { txt.textContent = rc.leido ? 'Actualizando…' : 'Leyendo la carpeta del equipo…'; return; }
  const info = rc.datos && rc.datos.planillaInfo;
  const f = info ? new Date(info.actualizado) : null;
  if (!rc.dir || !f || isNaN(f)) { txt.textContent = rc.dir ? 'Requerimientos leídos de la carpeta del equipo' : 'Sin la carpeta del equipo'; punto.className = 'cx-punto'; txt.title = ''; return; }
  txt.textContent = 'Excel guardado el ' + pqCuando(f);
  txt.title = 'Requerimientos es la Planilla del Excel más lo ingresado o cambiado aquí que todavía no llega a él. Cada minuto el computador del procesador pasa al Excel lo del portal y trae aquí lo que se cambió en el Excel.';
  const espera = pqEsperaMin();
  punto.className = 'cx-punto ' + (espera !== null && espera > PQ_ESPERA_MIN ? 'warn' : 'ok');
}
function pqPintarSinc() {
  const caja = $('#pqSinc');
  const cuerpo = $('#pqSincCuerpo');
  cuerpo.textContent = '';
  const n = (rc.datos.planillaPedidos || []).length;
  const espera = pqEsperaMin();
  const p = crear('p', 'pq-sinc-txt');
  caja.dataset.nivel = '';
  if (!rc.datos.planillaInfo) {
    caja.dataset.nivel = 'warn';
    p.textContent = 'La Planilla del Excel todavía no está publicada en la carpeta del equipo: se ve solo lo ingresado en el portal.';
  } else if (n) {
    const tarde = espera !== null && espera > PQ_ESPERA_MIN;
    if (tarde) caja.dataset.nivel = 'warn';
    p.append(crear('b', null, pl(n, 'cambio espera', 'cambios esperan') + ' pasar al Excel'));
    if (tarde) p.append(document.createTextNode(' desde hace ' + pqHace(espera) + ': ¿está encendido el computador del procesador? Aquí ya se ven, con un punto naranjo.'));
    else p.append(' ', info('Aquí ya se ven (con un punto naranjo) y el Excel los recibe en un par de minutos.', 'Cuándo llegan al Excel'));
  } else {
    // Lo normal, en dos palabras; cómo funciona, en el ⓘ (2026-11-05)
    p.append(crear('b', null, 'Al día con el Excel'), ' ',
      info('Lo de aquí pasa al Excel en un par de minutos, y lo del Excel llega aquí igual. El Excel queda de respaldo en SharePoint.', 'Cómo se sincroniza con el Excel'));
  }
  cuerpo.append(p);
  // Lo del portal que no quedó en el Excel esta semana: rechazado, o la casilla cambió después en el Excel
  const semana = Date.now() - 7 * 86400000;
  const malos = pq.cambios.filter((c) => (c.estado === 'rechazado' || c.estado === 'reemplazado') && new Date(c.enviado) > semana);
  if (malos.length) {
    const ul = crear('ul', 'pq-avisos');
    malos.slice(0, 3).forEach((c) => ul.append(crear('li', null, 'N° ' + c.numero + (c.titulo ? ' «' + c.titulo + '»' : '') + ': '
      + (c.estado === 'rechazado' ? 'no se pudo pasar al Excel. ' : 'quedó lo del Excel, que se cambió después. ') + (c.detalle[0] || ''))));
    cuerpo.append(ul);
  }
  // Lo que está en el Excel y aquí no se ve: un N° repetido o una fila sin N° (lo dice requerimientos.leer_planilla)
  const fuera = (rc.datos.planillaInfo && rc.datos.planillaInfo.avisos) || [];
  if (fuera.length) {
    const d = crear('details', 'pq-fuera');
    d.append(crear('summary', null, pl(fuera.length, 'fila del Excel no se ve aquí', 'filas del Excel no se ven aquí') + ': les falta un N° propio'));
    const lista = crear('ul', 'pq-cambios');
    fuera.forEach((a) => lista.append(crear('li', 'sc-env-det', a)));
    d.append(lista, crear('p', 'sc-env-det', 'Se arregla en el Excel, dándole a cada fila su N° (no se decide solo porque ese N° puede estar ya en una carpeta).'));
    cuerpo.append(d);
  }
  if (!pq.cambios.length) return;
  const det = crear('details');
  det.open = pq.verCambios;
  det.addEventListener('toggle', () => { pq.verCambios = det.open; });
  det.append(crear('summary', null, 'Lo ingresado y cambiado desde el portal (' + pq.cambios.length + ')'));
  const ul = crear('ul', 'pq-cambios');
  const NIVEL = { camino: ['warn', 'Por pasar al Excel'], aplicado: ['ok', 'En el Excel'], 'sin-cambios': ['ok', 'Ya estaba en el Excel'],
    reemplazado: ['warn', 'Quedó lo del Excel'], rechazado: ['bad', 'No se pudo'] };
  pq.cambios.forEach((c) => {
    const li = crear('li');
    const cab = crear('div', 'sc-env-cab');
    const [nivel, txt] = NIVEL[c.estado] || ['', c.estado];
    const pill = crear('span', 'sc-pill', txt);
    pill.dataset.nivel = nivel;
    const que = c.tipo === 'nuevo-requerimiento' ? 'nuevo' : c.campos.map((x) => PQ_NOMBRE[x] || x).join(', ');
    cab.append(crear('span', 'sc-env-nom', 'N° ' + c.numero + (c.titulo ? ' · ' + c.titulo : '') + ' · ' + que), pill);
    const f = new Date(c.enviado);
    li.append(cab, crear('span', 'sc-env-det', [c.usuario, isNaN(f) ? '' : pqCuando(f)].filter(Boolean).join(' · ')));
    // Lo que agrega el Excel a su resultado (el N° que tomó, quién mandó en una casilla)
    c.detalle.slice(c.estado === 'aplicado' ? 1 : 0).forEach((d) => li.append(crear('span', 'sc-env-det' + (c.estado === 'rechazado' ? ' mal' : ''), d)));
    if (c.estado === 'camino') {
      const b = crear('button', 'cx-enlace pq-retirar', 'Retirar');
      b.type = 'button';
      b.title = 'Que no llegue al Excel';
      b.addEventListener('click', () => pqRetirar(c));
      li.append(b);
    }
    ul.append(li);
  });
  det.append(ul);
  cuerpo.append(det);
}
function pqPintarEstados() {
  const caja = $('#pqEstados');
  caja.textContent = '';
  const filas = pqFilas();
  const cuenta = (e) => filas.filter((r) => texto(r.estado) === e).length;
  [['', 'Todos', filas.length]].concat(PQ_ESTADOS.map((e) => [e, e === 'Evaluación' ? 'En evaluación' : e, cuenta(e)])).forEach(([id, nombre, n]) => {
    const b = crear('button', 'pl-vista');
    b.type = 'button';
    b.dataset.estado = id;
    b.setAttribute('aria-pressed', String(pq.estado === id));
    b.append(document.createTextNode(nombre + ' '), crear('b', null, String(n)));
    b.addEventListener('click', () => { pq.estado = id; pq.mostrar = PQ_PAGINA; pqPintarEstados(); pqPintarTabla(); });
    caja.append(b);
  });
  const nf = filas.filter(pqForm).length;
  const b = crear('button', 'pl-vista pq-con-form');
  b.type = 'button';
  b.title = 'Solo los requerimientos que ya tienen una formulación en el Formulador';
  b.setAttribute('aria-pressed', String(pq.conForm));
  b.append(document.createTextNode('Con formulación '), crear('b', null, String(nf)));
  b.addEventListener('click', () => { pq.conForm = !pq.conForm; pq.mostrar = PQ_PAGINA; pqPintarEstados(); pqPintarTabla(); });
  caja.append(b);
}
function pqPintarTabla() {
  const cab = $('#pqCabeza');
  if (!cab.childElementCount) {
    PQ_COLUMNAS.forEach((c) => {
      const th = crear('th', c.clase, c.et);
      th.scope = 'col';
      if (c.ayuda) th.title = c.ayuda;
      cab.append(th);
    });
  }
  const todas = pqFilas().length;
  const filas = pqFiltradas();
  const tb = $('#pqFilas');
  tb.textContent = '';
  const hoy = new Date();
  filas.slice(0, pq.mostrar).forEach((r) => tb.append(pqFila(r, hoy)));
  $('#pqCuenta').textContent = filas.length === todas ? pl(todas, 'requerimiento', 'requerimientos') : filas.length + ' de ' + todas;
  const nada = $('#pqNada');
  nada.hidden = filas.length > 0;
  nada.textContent = !todas ? 'Todavía no hay requerimientos.' : 'Ningún requerimiento calza' + (pq.q.trim() ? ' con «' + pq.q.trim() + '»' : '')
    + (pq.estado ? ' en «' + pq.estado + '»' : '') + '.';
  const resto = filas.length - pq.mostrar;
  const mas = $('#pqMas');
  mas.hidden = resto <= 0;
  mas.textContent = resto > PQ_PAGINA ? 'Mostrar ' + PQ_PAGINA + ' más (quedan ' + resto + ')' : 'Mostrar ' + pl(resto, 'requerimiento más', 'requerimientos más');
}
function pqFila(r, hoy) {
  const mt = pqMeta(r);
  const tr = crear('tr');
  tr.dataset.n = String(r.numero);
  if (mt && mt.nuevo) tr.classList.add('pq-nueva');
  PQ_COLUMNAS.forEach((c) => {
    const td = crear('td', c.clase);
    const v = texto(r[c.id]);
    if (c.tarjeta) td.dataset.et = c.tarjeta;
    if (c.id === 'numero') {
      td.textContent = String(r.numero);
      if (mt && mt.nuevo) td.append(crear('span', 'pq-nuevo-tag', 'nuevo'));
    } else if (c.id === 'estado') {
      if (v) { const p = crear('span', 'pq-est', v); p.dataset.estado = v; td.append(p); }
    } else if (c.id === 'titulo') {
      const b = crear('button', 'pq-abrir', v || '(sin título)');
      b.type = 'button';
      b.title = v ? 'Abrir el N° ' + r.numero + ': ' + v : 'Abrir el N° ' + r.numero;
      b.addEventListener('click', () => pqAbrir(r));
      td.append(b);
      const fo = pqForm(r);
      if (fo) {
        const fuera = RC_FUERA.includes(fo.estado);
        const a = crear('button', 'pq-form' + (fuera ? ' fuera' : ''), 'Formulado · ' + fo.estado);
        a.type = 'button';
        a.title = 'Formulación ' + fo.codigo + ' v' + fo.version + (fo.responsable ? ' (' + fo.responsable + ')' : '') + ': abrirla en el Formulador';
        a.addEventListener('click', () => rcIr(RC_IR.ficha(fo.uid)));
        td.append(a);
      } else if (!(mt && mt.choque) && ['Evaluación', 'Ofertado', 'Adjudicado'].includes(texto(r.estado))) {
        // Sin formulación: pasa directo al Formulador con el diálogo de nuevo proyecto de este N° (2026-11-11), también
        // recién ingresado (el Formulador lo toma del buzón con N° provisorio). Con choque no: ese N° va a cambiar.
        const f = crear('button', 'pq-form', 'Formular →');
        f.type = 'button';
        f.title = 'Crear la formulación del N° ' + r.numero + ' en el Formulador';
        f.addEventListener('click', () => rcIr({ herr: 'formulador', url: HERR.get('formulador').ruta + '#/req/' + encodeURIComponent(r.numero) + '/crear' }));
        td.append(f);
      }
      if (mt && mt.choque) td.append(crear('span', 'pq-choque', 'El N° ' + r.numero + ' ya es «' + mt.choque + '»: al pasar al Excel queda con el siguiente libre.'));
    } else if (PQ_FECHAS.includes(c.id)) {
      td.textContent = pqFecha(v);
      if (c.id === 'cierre' && texto(r.estado) === 'Evaluación') {
        const f = rcFecha(v);
        const d = f ? rcDias(f, hoy) : null;
        if (d !== null && d >= 0 && d <= 14) td.append(crear('span', 'pq-quedan' + (d <= 3 ? ' pronto' : ''), d === 0 ? 'cierra hoy' : d === 1 ? 'cierra mañana' : 'faltan ' + d + ' días'));
      }
    } else {
      td.textContent = v;
      if (v) td.title = v;
    }
    if (!v && c.id !== 'numero') td.classList.add('vacia');
    if (mt && !mt.nuevo && mt.campos.has(c.id)) {
      const punto = crear('span', 'pq-punto');
      punto.title = 'Cambiado en el portal: todavía no llega al Excel';
      punto.setAttribute('role', 'img');
      punto.setAttribute('aria-label', 'cambiado en el portal, todavía no llega al Excel');
      td.classList.remove('vacia');
      td.append(punto);
    }
    tr.append(td);
  });
  tr.addEventListener('click', (e) => { if (!e.target.closest('button, a')) pqAbrir(r); });
  return tr;
}
// Mientras se mira, lo del equipo y lo del Excel llegan solos (cada 2 minutos, y nunca con el diálogo abierto)
setInterval(() => {
  if ($('#vistaPlanilla').hidden || document.visibilityState !== 'visible' || rc.leyendo || !rc.dir || $('#dlgPlanilla').open) return;
  if (Date.now() - rc.leido > 120000) rcCargar();
}, 30000);
