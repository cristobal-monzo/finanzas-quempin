/* Portal QUEMPIN — Sin la carpeta del equipo: el resumen cifrado, solo para leer (mv*). 2026-11-18, fase C del plan
   del Portal (docs/plans/2026-11-18-mejoras-portal.md), maqueta M3: el mismo Inicio, con datos, en el teléfono.
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan en el orden de
   index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita ni tape uno del navegador.

   En el teléfono (y en Safari o Firefox) no hay showDirectoryPicker: el navegador no abre la carpeta de Intercambio.
   El procesador sube cada tanto a gh-pages un resumen de lo que el Portal lee de ella (Sistema Intercambio/
   resumen_movil.py): datos/indice.json (horas y huellas, sin cifrar) y datos/<parte>.json, cada uno cifrado con el
   candado de los tableros. Aquí se abre con la clave que el navegador ya recuerda (quempin_viz_clave, la de los
   tableros) y se arma una carpeta de mentira con la misma forma que la de verdad (mvCarpeta): rcCargar se la pasa a
   todas las vistas, que leen igual que en el computador. Escribir en ella falla (NotAllowedError); y antes de eso,
   cada cambio que una persona hace pasa por mvNoSe(), que lo frena con un aviso. */
'use strict';

const MV_DATOS = 'datos/';
const MV_VIEJO_MIN = 120;      // desde aquí la franja se pone ámbar: el procesador no corre o su computador está apagado
const MV_CLAVE = 'quempin_viz_clave';
const mv = { activo: false, indice: null, revisado: 0, falta: null, partes: new Map(), entrando: false };

// ---- La carpeta de mentira --------------------------------------------------------------------------------------
const mvError = (nombre, msg) => new DOMException(msg, nombre);
const MV_NO_ESCRIBE = 'Solo lectura: el resumen del teléfono no se escribe';
function mvArchivo(nombre, e) {
  const h = {
    kind: 'file', name: nombre,
    getFile: async () => new File([JSON.stringify(e.d)], nombre, { type: 'application/json', lastModified: e.m || 0 }),
    createWritable: async () => { throw mvError('NotAllowedError', MV_NO_ESCRIBE); },
    queryPermission: async () => 'granted', requestPermission: async () => 'granted',
    isSameEntry: async (o) => o === h
  };
  return h;
}
// nodo: Map nombre → { dir: Map } o { archivo: { m, d } }
function mvCarpeta(nombre, nodo) {
  const hijo = (n, x) => (x.dir ? mvCarpeta(n, x.dir) : mvArchivo(n, x.archivo));
  const h = {
    kind: 'directory', name: nombre,
    async getDirectoryHandle(n, op) {
      const x = nodo.get(n);
      if (x && x.dir) return hijo(n, x);
      throw mvError(op && op.create ? 'NotAllowedError' : 'NotFoundError', op && op.create ? MV_NO_ESCRIBE : n);
    },
    async getFileHandle(n, op) {
      const x = nodo.get(n);
      if (x && x.archivo) return hijo(n, x);
      throw mvError(op && op.create ? 'NotAllowedError' : 'NotFoundError', op && op.create ? MV_NO_ESCRIBE : n);
    },
    async removeEntry() { throw mvError('NotAllowedError', MV_NO_ESCRIBE); },
    async *entries() { for (const [n, x] of nodo) yield [n, hijo(n, x)]; },
    async *keys() { for (const n of nodo.keys()) yield n; },
    async *values() { for (const [n, x] of nodo) yield hijo(n, x); },
    queryPermission: async () => 'granted', requestPermission: async () => 'granted',
    isSameEntry: async (o) => o === h
  };
  h[Symbol.asyncIterator] = h.entries;
  return h;
}
// {"publicado/x.json": {m, d}} → el árbol de carpetas
function mvArbol(archivos) {
  const raiz = new Map();
  Object.keys(archivos).forEach((ruta) => {
    const partes = ruta.split('/');
    let nodo = raiz;
    partes.slice(0, -1).forEach((p) => {
      if (!nodo.has(p)) nodo.set(p, { dir: new Map() });
      nodo = nodo.get(p).dir;
    });
    nodo.set(partes[partes.length - 1], { archivo: archivos[ruta] });
  });
  return raiz;
}

// ---- Bajar y abrir el resumen -----------------------------------------------------------------------------------
function mvClave() {
  let b64 = null;
  try { b64 = localStorage.getItem(MV_CLAVE); } catch (e) { /* sin almacenamiento */ }
  if (!b64) return null;
  try { return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)); } catch (e) { return null; }
}
const mvPuedeAbrir = () => !!(window.crypto && crypto.subtle && typeof DecompressionStream === 'function' && window.QuempinCandado);
async function mvBajar(ruta, cache) {
  const r = await fetch(MV_DATOS + ruta, { cache });
  if (!r.ok) { const e = new Error('No está ' + ruta + ' (' + r.status + ')'); e.falta = r.status === 404 ? 'sin-resumen' : 'red'; throw e; }
  return r.json();
}
// Una parte ya abierta no se vuelve a descifrar mientras no cambie su huella
async function mvParte(nombre, huella, clave) {
  const ya = mv.partes.get(nombre);
  if (ya && ya.huella === huella) return ya.archivos;
  const sobre = await mvBajar(nombre + '.json?v=' + encodeURIComponent(huella), 'default');
  let plano;
  try { plano = await QuempinCandado.descifrarBytes(clave, sobre); } catch (e) { const x = new Error('La clave no abre el resumen'); x.falta = 'clave'; throw x; }
  const archivos = (JSON.parse(new TextDecoder('utf-8').decode(plano)) || {}).archivos || {};
  mv.partes.set(nombre, { huella, archivos });
  return archivos;
}
/* La carpeta de mentira, o null con mv.falta: 'sin-resumen' (no hay o no se pudo bajar), 'clave' (el navegador no
   recuerda la contraseña o ya no abre) o 'navegador' (no puede descifrar). */
async function mvCargar() {
  if (!mvPuedeAbrir()) { mv.falta = 'navegador'; return null; }
  try {
    mv.indice = await mvBajar('indice.json', 'no-cache');
    mv.revisado = Date.parse(mv.indice.revisado) || 0;
    const clave = mvClave();
    if (!clave) { mv.falta = 'clave'; return null; }
    const archivos = {};
    for (const [nombre, huella] of Object.entries(mv.indice.partes || {})) Object.assign(archivos, await mvParte(nombre, huella, clave));
    mv.falta = null;
    return mvCarpeta('Intercambio', mvArbol(archivos));
  } catch (e) {
    mv.falta = e.falta || 'sin-resumen';
    if (!e.falta) console.warn('Resumen del teléfono:', e);
    return null;
  }
}
/* Lo que rcCargar usa cuando no hay carpeta: el resumen, si este navegador puede abrirlo. Sin showDirectoryPicker se
   intenta siempre; en Chrome o Edge sin la carpeta conectada, solo si el navegador ya recuerda la contraseña (si no,
   se ve lo de siempre: «conecta la carpeta»). */
async function mvAbrir(por) {
  if (por !== 'navegador' && !mvClave()) { mv.activo = false; mvPintar(); return null; }
  const dir = await mvCargar();
  mv.activo = !!dir;
  mvPintar();
  return dir;
}
function mvSoltar() {
  if (!mv.activo && !mv.falta) return;
  mv.activo = false;
  mv.falta = null;
  mvPintar();
}
const soloLectura = () => mv.activo;
// Cada cambio pasa por aquí: con el resumen, no se hace y se dice por qué. Devuelve true si se frenó.
function mvNoSe() {
  if (!mv.activo) return false;
  avisar('Solo lectura: aquí se ven los datos de la carpeta del equipo, pero no se cambian. Para cambiarlos, usa el Portal en un computador con la carpeta conectada.');
  return true;
}

/* Un diálogo con los datos de algo (un requerimiento, un gasto) se abre igual para mirarlo; en solo lectura sus campos
   quedan sin poder tocarse y portal.css esconde lo que guarda o borra (dialog.solo-ver). Se llama justo antes de abrirlo. */
function mvSoloVer(dlg) {
  const si = soloLectura();
  dlg.classList.toggle('solo-ver', si);
  dlg.querySelectorAll('input, select, textarea').forEach((e) => {
    if (si && !e.disabled) { e.disabled = true; e.dataset.mvApagado = '1'; }
    else if (!si && e.dataset.mvApagado) { e.disabled = false; delete e.dataset.mvApagado; }
    // El texto de ayuda de un campo vacío («Comuna de los trabajos») parecería un dato: se ve «—»
    if (!('placeholder' in e)) return;
    if (si && e.dataset.mvAyuda === undefined) { e.dataset.mvAyuda = e.placeholder || ''; e.placeholder = '—'; }
    else if (!si && e.dataset.mvAyuda !== undefined) { e.placeholder = e.dataset.mvAyuda; delete e.dataset.mvAyuda; }
  });
}

// ---- La franja «Solo lectura · datos de las HH:MM» ---------------------------------------------------------------
function mvHora() {
  const d = new Date(mv.revisado);
  const hh = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  const hoy = new Date();
  if (d.toDateString() === hoy.toDateString()) return 'de las ' + hh;
  return 'del ' + d.toLocaleDateString('es-CL', { weekday: 'short', day: 'numeric', month: 'short' }) + ', ' + hh;
}
function mvPintar() {
  const f = $('#mvFranja');
  const clave = mv.falta === 'clave' && !!mv.indice;
  f.hidden = !mv.activo && !clave;
  document.documentElement.classList.toggle('solo-lectura', mv.activo);
  if (f.hidden) return;
  const min = (Date.now() - mv.revisado) / 60000;
  const viejo = mv.activo && min > MV_VIEJO_MIN;
  f.classList.toggle('viejo', viejo);
  $('#mvTexto').textContent = mv.activo
    ? 'Solo lectura · datos ' + mvHora() + (viejo ? ' (hace ' + (min < 48 * 60 ? Math.round(min / 60) + ' h' : Math.round(min / 1440) + ' días') + ')' : '')
    : 'Escribe la contraseña del equipo para ver los datos';
  $('#mvFranja').title = mv.activo
    ? 'En este navegador no se abre la carpeta del equipo: se ve un resumen que el computador del procesador sube cada media hora. '
      + (viejo ? 'Tiene más de 2 horas: ese computador puede estar apagado o sin conexión.' : 'Aquí no se cambia nada.')
    : 'La misma contraseña de los tableros: se escribe una vez en este navegador.';
  $('#mvEntrar').hidden = !clave;
}
// La contraseña: se deriva la clave como en los tableros (misma sal), se prueba con la parte más chica y se recuerda
async function mvEntrar(ev) {
  ev.preventDefault();
  if (mv.entrando || !mv.indice) return;
  const campo = $('#mvContrasena');
  const boton = $('#mvEntrar button');
  mv.entrando = true;
  boton.disabled = true;
  try {
    const partes = Object.entries(mv.indice.partes || {});
    const [nombre] = partes.find(([n]) => n === 'estado') || partes[0];
    const sobre = await mvBajar(nombre + '.json?v=' + encodeURIComponent(mv.indice.partes[nombre]), 'default');
    const clave = await QuempinCandado.derivar(campo.value, sobre);
    await QuempinCandado.descifrarBytes(clave, sobre);
    try { localStorage.setItem(MV_CLAVE, btoa(String.fromCharCode(...clave))); } catch (e) { /* sin almacenamiento */ }
    campo.value = '';
    mv.falta = null;
    rcCargar();
  } catch (e) {
    avisar('Contraseña incorrecta. Intenta de nuevo.');
    campo.select();
  }
  mv.entrando = false;
  boton.disabled = false;
}
function mvPreparar() {
  $('#mvEntrar').addEventListener('submit', mvEntrar);
  // La hora envejece sola: «hace 3 h» sin esperar otra lectura
  setInterval(() => { if (mv.activo) mvPintar(); }, 60000);
}
