/* Portal QUEMPIN — Configuración y conexiones: la carpeta del equipo y lo que necesita cada herramienta.
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Configuración y conexiones ------------------------------------------------------------------
// Qué carpetas, programas y permisos necesita cada herramienta, dónde están (bloque «portal-conexiones»)
// y lo que este navegador puede revisar solo: si conecta carpetas, si la biblioteca del equipo está
// conectada (la misma conexión del Formulador: IndexedDB «qpn-intercambio», que se comparte porque es
// el mismo sitio), el pulso del procesador y si ya tiene la contraseña.
// «Preparar este computador» (2026-10-19, pedido del usuario: que la sincronización sea más sencilla en cada
// PC, con cada cosa que se conecta arriba y un botón claro para hacerlo): un paso por cosa, en orden. La
// biblioteca se conecta aquí mismo y queda guardada donde la guarda el Formulador (misma base, mismas claves),
// así vale para él y para «Ingresar avance». Lo que el navegador no puede revisar (OneDrive, QUEMPIN.exe) lo
// marca la persona, y esa marca queda solo en este navegador.
const CX = JSON.parse(document.getElementById('portal-conexiones').textContent);
const CX_POR_ID = new Map(CX.elementos.map((e) => [e.id, e]).concat([[CX.procesador.id, CX.procesador]]));
const ICONO_TIPO = { 'Cuenta': 'persona', 'Biblioteca de SharePoint': 'nube', 'Carpeta': 'proyectos', 'Carpeta de SharePoint': 'proyectos',
  'Excel': 'tabla', 'Programa': 'ventana', 'En el navegador': 'globo' };
// tarjeta: la de abajo que explica el paso. delEquipo: no es de este computador y no cuenta en el avance.
const ESTADOS = [
  { id: 'navegador', nombre: 'Usar Chrome o Edge de escritorio', tarjeta: 'navegador' },
  { id: 'onedrive', nombre: 'Tener las bibliotecas del equipo en OneDrive', tarjeta: 'cuenta' },
  { id: 'biblioteca', nombre: 'Conectar la biblioteca «Formulación de proyectos»', tarjeta: 'biblioteca' },
  { id: 'contrasena', nombre: 'Escribir la contraseña del equipo', tarjeta: 'contrasena' },
  { id: 'usuario', nombre: 'Elegir tu usuario' },
  { id: 'sistema', nombre: 'Abrir QUEMPIN.exe una vez', tarjeta: 'sistema' },
  { id: 'procesador', nombre: 'Procesador del intercambio (del equipo)', tarjeta: 'procesador', delEquipo: true }
];
const LS_CX_MARCAS = 'quempin_portal_conexiones';   // { onedrive: fecha, sistema: fecha }: lo marcado a mano
const BIBLIOTECA_FORMULACION = 'Formulación de proyectos - Documentos';
const PLANILLA = 'Planilla de Ingreso de Requerimientos.xlsx';
const marcas = () => { const m = leer(LS_CX_MARCAS, {}); return m && typeof m === 'object' ? m : {}; };
function marcar(id, si) {
  const m = marcas();
  if (si) m[id] = new Date().toISOString(); else delete m[id];
  guardar(LS_CX_MARCAS, m);
  pintarEstadoConexiones();
}
const REDUCIR = window.matchMedia('(prefers-reduced-motion: reduce)');
const unir = (xs) => (xs.length < 2 ? xs.join('') : xs.slice(0, -1).join(', ') + ' y ' + xs[xs.length - 1]);

// Lo que necesita una herramienta: lo que la nombra, o lo de la dueña de su pestaña (Seguimiento, Ingresar avance).
function necesidades(h) {
  const de = (id) => CX.elementos.filter((e) => e.usan.includes(id)).map((e) => e.id);
  const propias = de(h.id);
  return propias.length || !h.alias ? propias : de(h.familia);
}
function irATarjeta(id) {
  const t = document.getElementById('cx-' + id);
  if (!t) return;
  t.scrollIntoView({ block: 'start', behavior: REDUCIR.matches ? 'auto' : 'smooth' });
  t.classList.add('resaltada');
  setTimeout(() => t.classList.remove('resaltada'), 1800);
}
function chipElemento(id) {
  const e = CX_POR_ID.get(id);
  const b = crear('button', 'cx-chip', e.corto || e.nombre);
  b.type = 'button';
  b.title = 'Ver dónde está: ' + e.nombre;
  b.addEventListener('click', () => irATarjeta(id));
  return b;
}
// En «Lo usan»: una herramienta abre su pestaña; el procesador, que no está en el portal, lleva a su tarjeta.
function chipUsa(id) {
  if (!HERR.has(id)) return chipElemento(id);
  const h = HERR.get(id);
  const b = crear('button', 'cx-chip herr', h.nombre);
  b.type = 'button';
  b.title = 'Abrir ' + h.nombre;
  b.addEventListener('click', () => abrir(id));
  return b;
}
function pildora(estadoId) {
  const p = crear('span', 'cx-pildora');
  p.dataset.estado = estadoId;
  p.append(crear('span', 'cx-punto'), crear('span', null, 'Revisando…'));
  return p;
}
function cabeceraTarjeta(e, tipo, ico) {
  const cab = crear('header', 'cx-tar-cab');
  const i = crear('span', 'ico');
  i.append(icono(ico, 20));
  const tit = crear('div', 'cx-tar-tit');
  const h3 = crear('h3', null, e.nombre);
  h3.id = 'cxt-' + e.id;
  tit.append(crear('span', 'cx-tipo', tipo), h3);
  cab.append(i, tit);
  if (e.estado) cab.append(pildora(e.estado));
  return cab;
}
function parrafoFalta(texto) {
  const p = crear('p', 'cx-falta');
  p.append(crear('strong', null, 'Si falta: '), document.createTextNode(texto));
  return p;
}
function tarjeta(e) {
  const t = crear('article', 'cx-tarjeta');
  t.id = 'cx-' + e.id;
  t.setAttribute('aria-labelledby', 'cxt-' + e.id);
  t.append(cabeceraTarjeta(e, e.tipo, e.icono || ICONO_TIPO[e.tipo] || 'documento'), crear('p', 'cx-para', e.para));
  if (e.ruta) {
    const r = crear('div', 'cx-ruta');
    r.append(crear('span', 'cx-ruta-et', e.en === 'SharePoint' ? 'En SharePoint' : 'En tu computador'));
    const ol = crear('ol', 'cx-migas');
    ol.setAttribute('aria-label', 'Ruta, carpeta por carpeta');
    e.ruta.forEach((x) => ol.append(crear('li', null, x)));
    r.append(ol);
    t.append(r);
  }
  if (e.web || e.abrir) {
    const acc = crear('div', 'cx-acc');
    if (e.web) {
      const a = crear('a', 'cx-enlace');
      a.href = encodeURI(e.web);
      a.target = '_blank';
      a.rel = 'noopener';
      a.append(crear('span', null, 'Abrir en SharePoint'), icono('fuera', 14));
      acc.append(a);
    }
    if (e.abrir) {
      const b = crear('button', 'cx-enlace');
      b.type = 'button';
      b.append(crear('span', null, 'Abrir en Excel para la web'), icono('fuera', 14));
      b.addEventListener('click', () => abrirExcel(HERR.get(e.abrir)));
      acc.append(b);
    }
    t.append(acc);
  }
  if (e.pasos && e.pasos.length) {
    t.append(crear('h4', null, 'Cómo dejarlo listo'));
    const ol = crear('ol', 'cx-pasos');
    e.pasos.forEach((x) => ol.append(crear('li', null, x)));
    t.append(ol);
  }
  const u = crear('div', 'cx-usan');
  u.append(crear('span', 'cx-usan-et', 'Lo usan'));
  e.usan.forEach((id) => u.append(chipUsa(id)));
  t.append(u);
  if (e.falta) t.append(parrafoFalta(e.falta));
  return t;
}
function tarjetaProcesador() {
  const e = CX.procesador;
  const t = crear('section', 'cx-tarjeta cx-procesador');
  t.id = 'cx-' + e.id;
  t.setAttribute('aria-labelledby', 'cxt-' + e.id);
  t.append(cabeceraTarjeta(Object.assign({ estado: 'procesador' }, e), 'Lo que corre solo', 'reloj'), crear('p', 'cx-para', e.para));
  const tabla = crear('table', 'cx-tabla cx-tareas');
  const cab = crear('tr');
  ['Tarea programada', 'Cuándo', 'Qué hace'].forEach((x) => { const th = crear('th', null, x); th.scope = 'col'; cab.append(th); });
  const thead = crear('thead');
  thead.append(cab);
  const tbody = crear('tbody');
  e.tareas.forEach((x) => {
    const tr = crear('tr');
    const th = crear('th', null, x.nombre);
    th.scope = 'row';
    tr.append(th, crear('td', null, x.cuando), crear('td', null, x.hace));
    tbody.append(tr);
  });
  tabla.append(thead, tbody);
  t.append(tabla, parrafoFalta(e.falta));
  return t;
}
let cxArmada = false;
function armarConexiones() {
  if (cxArmada) return;
  cxArmada = true;
  let n = 0;
  ESTADOS.forEach((s) => {
    const li = crear('li');
    li.dataset.estado = s.id;
    const num = crear('span', 'cx-num', s.delEquipo ? '·' : String(++n));
    num.dataset.n = num.textContent;
    num.setAttribute('aria-hidden', 'true');
    const txt = crear('div', 'cx-est-txt');
    let nom;
    if (s.tarjeta) {
      nom = crear('button', 'cx-est-nom', s.nombre);
      nom.type = 'button';
      nom.title = 'Ver dónde está y cómo dejarlo listo';
      nom.addEventListener('click', () => irATarjeta(s.tarjeta));
    } else {
      nom = crear('span', 'cx-est-nom', s.nombre);
    }
    txt.append(nom, crear('span', 'cx-est-det', 'Revisando…'));
    li.append(num, txt, crear('div', 'cx-est-acc'));
    $('#cxEstado').append(li);
  });
  // Una fila por herramienta (o por varias que necesitan lo mismo); las calculadoras no necesitan nada.
  const filas = [];
  REG.herramientas.forEach((h) => {
    // Las de cada grupo (sin la ayuda) y, de las de arriba, las que necesitan algo (el Recorrido)
    if (h.grupo === 'arriba' ? !necesidades(h).length : !GRUPO_NOMBRE.has(h.grupo) || h.grupo === 'ayuda') return;
    const nec = necesidades(h);
    const clave = h.grupo + '|' + nec.join(',');
    const f = filas.find((x) => x.clave === clave);
    if (f) f.nombres.push(h.nombre); else filas.push({ clave, grupo: h.grupo, nombres: [h.nombre], nec });
  });
  filas.forEach((f) => {
    const tr = crear('tr');
    const th = crear('th', null, f.grupo === 'calcular' && f.nombres.length > 1 ? GRUPO_NOMBRE.get(f.grupo) + ' (todas)' : unir(f.nombres));
    th.scope = 'row';
    const td = crear('td');
    if (f.nec.length) {
      const c = crear('div', 'cx-chips');
      f.nec.forEach((id) => c.append(chipElemento(id)));
      td.append(c);
    } else {
      td.append(crear('span', 'cx-nada', 'Nada: funciona sola, sin contraseña.'));
    }
    tr.append(th, td);
    $('#cxNecesita tbody').append(tr);
  });
  const cont = $('#cxTarjetas');
  CX.elementos.forEach((e) => cont.append(tarjeta(e)));
  cont.after(tarjetaProcesador());
}

// La biblioteca que conectó el Formulador en este navegador (js/intercambio.js): solo se lee.
function leerCarpetas() {
  return new Promise((listo) => {
    let req;
    try { req = indexedDB.open('qpn-intercambio'); } catch (e) { listo({}); return; }
    // No existe todavía: se deja sin crear (al cancelarla el navegador no la guarda) para que el Formulador la arme a su modo.
    req.onupgradeneeded = () => { try { req.transaction.abort(); } catch (e) { /* nada */ } };
    req.onerror = (e) => { if (e && e.preventDefault) e.preventDefault(); listo({}); };
    req.onsuccess = () => {
      const db = req.result;
      try {
        const tx = db.transaction('carpetas', 'readonly');
        const tienda = tx.objectStore('carpetas');
        const a = tienda.get('intercambio');
        const b = tienda.get('biblioteca');
        tx.oncomplete = () => { db.close(); listo({ intercambio: a.result || null, biblioteca: b.result || null }); };
        tx.onerror = () => { db.close(); listo({}); };
      } catch (e) { db.close(); listo({}); }
    };
  });
}
async function permisoDe(h) {
  try { return await h.queryPermission({ mode: 'readwrite' }); } catch (e) { return 'prompt'; }
}
const nombreClave = (s) => String(s || '').normalize('NFC').toLowerCase();
async function hijaComo(dir, nombre) {
  try {
    for await (const [n, h] of dir.entries()) if (h.kind === 'directory' && nombreClave(n) === nombreClave(nombre)) return h;
  } catch (e) { /* sin permiso */ }
  return null;
}
// La carpeta de intercambio, si ya hay permiso (con el de la biblioteca alcanza, como en el Formulador).
async function intercambioLegible(c) {
  if (c.intercambio && (await permisoDe(c.intercambio)) === 'granted') return c.intercambio;
  if (c.biblioteca && (await permisoDe(c.biblioteca)) === 'granted') {
    const herramientas = await hijaComo(c.biblioteca, '.Herramientas formulación');
    return herramientas ? hijaComo(herramientas, 'Intercambio') : null;
  }
  return null;
}
async function leerPulso(dir) {
  try {
    const pub = await dir.getDirectoryHandle('publicado');
    const f = await (await pub.getFileHandle('estado.json')).getFile();
    const sobre = JSON.parse((await f.text()).replace(/^﻿/, ''));
    return sobre && sobre.datos ? sobre.datos : null;
  } catch (e) { return null; }
}
// La misma lectura del pulso que el Formulador y «Ingresar datos» (su js/pulso.js, en este mismo sitio):
// iguales umbrales de horario hábil y los mismos textos. Si no carga, se dice solo la hora de la última vuelta.
let pulsoCargado = null;
function cargarPulso() {
  if (window.QPulso) return Promise.resolve();
  if (!pulsoCargado) {
    pulsoCargado = new Promise((listo) => {
      const s = document.createElement('script');
      s.src = HERR.get('formulador').ruta + 'js/pulso.js';
      s.onload = () => listo();
      s.onerror = () => listo();
      document.head.append(s);
    });
  }
  return pulsoCargado;
}
// ---- Lo que el Portal publica cumple su esquema (2026-11-06) ------------------------------------------
// Antes de escribir su archivo de la Planificación o de Proyectos en ejecución, se valida contra el catálogo de la
// carpeta (esquemas.json, que deja el procesador) con el mismo validador de Python (esquemas.js, que el Formulador
// publica en su js/). Lo que no cumple no se escribe: el cambio queda pendiente y la vista dice que no se guardó.
// Sin el validador o sin el catálogo (o con uno anterior a esa publicación) se escribe como antes.
let esquemasCargados = null;
function cargarEsquemas() {
  if (window.QEsquemas) return Promise.resolve();
  if (!esquemasCargados) {
    esquemasCargados = new Promise((listo) => {
      const s = document.createElement('script');
      s.src = HERR.get('formulador').ruta + 'js/esquemas.js';
      s.onload = () => listo();
      s.onerror = () => listo();
      document.head.append(s);
    });
  }
  return esquemasCargados;
}
// El catálogo se vuelve a leer solo cuando cambia el archivo (su fecha o su tamaño).
const catalogoCarpeta = { dir: null, paquete: null, marca: '' };
async function catalogoDeLaCarpeta(dir) {
  let f = null;
  try { f = await (await dir.getFileHandle('esquemas.json')).getFile(); } catch (e) { f = null; }
  const marca = f ? f.lastModified + ':' + f.size : '';
  if (catalogoCarpeta.dir === dir && catalogoCarpeta.marca === marca) return catalogoCarpeta.paquete;
  let p = null;
  try { p = f ? JSON.parse(rcSinBom(await f.text())) : null; } catch (e) { p = null; }
  Object.assign(catalogoCarpeta, { dir, paquete: p && p.publicaciones && p.sobrePublicacion ? p : null, marca });
  return catalogoCarpeta.paquete;
}
async function exigirEsquema(dir, nombre, sobre) {
  await cargarEsquemas();
  const paquete = await catalogoDeLaCarpeta(dir);
  if (!window.QEsquemas || !paquete || !paquete.publicaciones[nombre]) return;
  // Se valida lo que queda en el archivo: JSON quita lo undefined (como intercambio.publicar en Python)
  const errores = window.QEsquemas.validarPublicacion(nombre, JSON.parse(JSON.stringify(sobre)), paquete);
  if (errores.length) throw new Error('No se guardó: el archivo no cumple su esquema (' + nombre + ': ' + errores.slice(0, 3).join('; ') + ').');
}
function lecturaPulso(est) {
  let l = null;
  try { l = window.QPulso ? window.QPulso.lectura(est) : null; } catch (e) { l = null; }
  if (l) return l;
  const t = est && est.procesador ? new Date(est.procesador.ultimaCorrida) : null;
  if (!t || isNaN(t)) return null;
  const min = Math.max(0, Math.round((Date.now() - t) / 60000));
  const cuando = t.toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  return { nivel: min <= 150 ? 'ok' : 'warn', minutos: min, detenido: false, texto: 'La última vuelta del procesador fue el ' + cuando + '.' };
}
// ---- Conectar la biblioteca desde el portal --------------------------------------------------------
// Lo mismo que el Formulador › Configuración › Conectar carpeta (js/intercambio.js): se elige la biblioteca
// completa (o, si no, la carpeta de intercambio) y se guarda en su base. A diferencia del Formulador, aquí
// nunca se crea una carpeta de intercambio nueva: si no está, se dice qué elegir.
const esManifiesto = (m) => !!(m && typeof m.esquema === 'string' && m.esquema.indexOf('quempin.intercambio/') === 0);
async function tieneManifiesto(dir) {
  try {
    const f = await (await dir.getFileHandle('intercambio.json')).getFile();
    return esManifiesto(JSON.parse((await f.text()).replace(/^﻿/, '')));
  } catch (e) { return false; }
}
async function resolverBiblioteca(h) {
  if (await tieneManifiesto(h)) return { intercambio: h, biblioteca: null };
  const herramientas = await hijaComo(h, '.Herramientas formulación');
  const desdeBib = herramientas && await hijaComo(herramientas, 'Intercambio');
  if (desdeBib && await tieneManifiesto(desdeBib)) return { intercambio: desdeBib, biblioteca: h };
  const desdeHerr = await hijaComo(h, 'Intercambio');
  if (desdeHerr && await tieneManifiesto(desdeHerr)) return { intercambio: desdeHerr, biblioteca: null };
  return null;
}
function guardarCarpetas(c) {
  return new Promise((listo, mal) => {
    let req;
    try { req = indexedDB.open('qpn-intercambio', 1); } catch (e) { mal(e); return; }
    req.onupgradeneeded = () => req.result.createObjectStore('carpetas');   // la misma forma que la arma el Formulador
    req.onerror = () => mal(req.error);
    req.onsuccess = () => {
      const db = req.result;
      const tx = db.transaction('carpetas', 'readwrite');
      const t = tx.objectStore('carpetas');
      t.put(c.intercambio, 'intercambio');
      if (c.biblioteca) t.put(c.biblioteca, 'biblioteca'); else t.delete('biblioteca');
      tx.oncomplete = () => { db.close(); listo(); };
      tx.onerror = () => { db.close(); mal(tx.error); };
    };
  });
}
// Las herramientas que ya estaban abiertas leyeron su conexión al cargar: se avisa para recargarlas.
function abiertasConCarpeta() {
  return estado.pestanas.filter((p) => p.marco && (p.familia === 'formulador' || p.herr === 'ingresar'));
}
// Desde el clic y sin esperas antes: el navegador solo abre el selector si viene de uno.
async function conectarBiblioteca() {
  let h;
  try {
    h = await window.showDirectoryPicker({ id: 'quempin-intercambio', mode: 'readwrite' });
  } catch (e) {
    if (e && e.name !== 'AbortError') avisar('No se pudo abrir el selector de carpetas: ' + (e.message || e));
    return;
  }
  const c = await resolverBiblioteca(h);
  if (!c) {
    avisar('«' + h.name + '» no es la biblioteca. Elige la carpeta «' + BIBLIOTECA_FORMULACION + '» completa, dentro de «OneDrive - QUEMPIN SPA».');
    return;
  }
  try { await guardarCarpetas(c); } catch (e) { avisar('No se pudo guardar la conexión en este navegador: ' + (e.message || e)); return; }
  await pintarEstadoConexiones();
  const abiertas = abiertasConCarpeta();
  const msg = c.biblioteca ? 'Biblioteca conectada: el Formulador e «Ingresar avance» ya la usan en este navegador.'
    : 'Quedó conectada solo la carpeta de intercambio. Para el Excel de cada oferta, conecta la biblioteca completa.';
  avisar(msg, abiertas.length ? { texto: 'Recargar las herramientas abiertas', ir: () => abiertas.forEach((p) => {
    const w = ventanaDe(p);
    if (w) { try { w.location.reload(); } catch (e) { /* nada */ } }
  }) } : undefined);
}
async function archivoEn(dir, nombre) {
  try {
    for await (const [n, h] of dir.entries()) if (h.kind === 'file' && nombreClave(n) === nombreClave(nombre)) return true;
  } catch (e) { /* sin permiso */ }
  return false;
}
function copiarDireccion() {
  const url = location.href.split('#')[0];
  const ok = () => avisar('Dirección copiada: pégala en Chrome o Edge.');
  try { navigator.clipboard.writeText(url).then(ok, () => avisar('Copia esta dirección: ' + url)); } catch (e) { avisar('Copia esta dirección: ' + url); }
}
function probarSistema() {
  abrirEnlace('quempin://historial');
  avisar('Abriendo Sistema QUEMPIN… Si el navegador pregunta, marca «Permitir siempre» y elige «Abrir».',
    { texto: 'Sí, se abrió', ir: () => marcar('sistema', true) });
}

let carpetasVistas = {};
async function revisarConexiones() {
  const r = {};
  const m = marcas();
  const puede = typeof window.showDirectoryPicker === 'function';
  r.navegador = puede
    ? { nivel: 'ok', corto: 'Compatible', texto: 'Este navegador puede conectar carpetas.' }
    : { nivel: 'bad', corto: 'No compatible', texto: 'Este navegador no puede conectar carpetas: abre el portal en Chrome o Edge de escritorio.',
        acciones: [{ texto: 'Copiar la dirección del portal', ir: copiarDireccion, pri: true }] };
  let clave = null;
  try { clave = localStorage.getItem(LS_CLAVE_TABLEROS); } catch (e) { clave = null; }
  r.contrasena = clave
    ? { nivel: 'ok', corto: 'Guardada', texto: 'Guardada en este navegador: abre todos los tableros y el Formulador.' }
    : { nivel: 'warn', corto: 'Falta', texto: 'Se escribe una vez, en el candado de cualquier herramienta. Pídela a quien administra las herramientas.',
        acciones: [{ texto: 'Escribir la contraseña', ir: () => abrir('formulador'), pri: true }] };
  r.usuario = estado.usuario
    ? { nivel: 'ok', corto: estado.usuario, texto: 'Trabajas como ' + estado.usuario + ': lo que formules queda a tu nombre.',
        acciones: [{ texto: 'Cambiar', ir: abrirUsuario }] }
    : { nivel: 'warn', corto: 'Falta', texto: 'Tus iniciales, para quedar como responsable de lo que formules.',
        acciones: [{ texto: 'Elegir mi usuario', ir: abrirUsuario, pri: true }] };
  const c = puede ? await leerCarpetas() : {};
  carpetasVistas = c;
  const conectar = (texto, pri) => ({ texto, ir: conectarBiblioteca, pri });
  let dir = null;
  if (!puede) {
    r.biblioteca = { nivel: 'bad', corto: 'No se puede', texto: 'Se conecta en Chrome o Edge de escritorio.' };
  } else if (!c.intercambio) {
    r.biblioteca = { nivel: 'bad', corto: 'Sin conectar', texto: 'Sin conectar en este navegador. Elige la carpeta «' + BIBLIOTECA_FORMULACION + '» completa, dentro de «OneDrive - QUEMPIN SPA», y acepta «Ver archivos» y «Guardar cambios».',
      acciones: [conectar('Conectar biblioteca', true)] };
  } else {
    dir = await intercambioLegible(c);
    const nombre = (c.biblioteca || c.intercambio).name;
    if (!dir) r.biblioteca = { nivel: 'warn', corto: 'Falta permiso', texto: 'Conectada («' + nombre + '»), pero el navegador pide permiso otra vez en esta sesión.', acciones: [{ texto: 'Dar permiso', ir: darPermiso, pri: true }] };
    else if (!c.biblioteca) r.biblioteca = { nivel: 'warn', corto: 'Incompleta', texto: 'Está conectada solo «' + c.intercambio.name + '». Para el Excel de cada oferta, conecta la biblioteca completa.', acciones: [conectar('Conectar la biblioteca completa', true)] };
    else r.biblioteca = { nivel: 'ok', corto: 'Conectada', texto: 'Conectada: «' + nombre + '».', acciones: [conectar('Cambiar', false)] };
    if (dir) {
      r.biblioteca.dentro = [
        { texto: 'Carpeta de intercambio', si: await tieneManifiesto(dir) },
        { texto: 'Planilla de Ingreso', si: c.biblioteca && (await permisoDe(c.biblioteca)) === 'granted' ? await archivoEn(c.biblioteca, PLANILLA) : null }
      ];
    }
  }
  // Lo que el navegador no ve: se marca a mano. Con la biblioteca conectada, «Formulación» ya está en el PC.
  const bibOk = r.biblioteca.nivel === 'ok';
  const sharepoint = (id, texto) => ({ texto, href: encodeURI(CX_POR_ID.get(id).web) });
  r.onedrive = m.onedrive
    ? { nivel: 'ok', corto: 'Listo', texto: 'Marcado como listo: «Formulación de proyectos» y «Cotizaciones y OC» están en OneDrive, una junto a la otra.', marcado: 'onedrive' }
    : { nivel: bibOk ? 'warn' : 'bad', corto: 'Revisar',
        texto: (bibOk ? '«Formulación de proyectos» ya está en este computador. ' : 'Inicia OneDrive con tu cuenta @quempin.cl. ') +
          'En cada biblioteca, en SharePoint, elige «Agregar acceso directo a Mis archivos», y espera que OneDrive las sincronice.',
        acciones: [sharepoint('biblioteca', 'Formulación de proyectos'), sharepoint('cotizaciones', 'Cotizaciones y OC'),
          { texto: 'Ya están las dos', ir: () => marcar('onedrive', true), pri: true }] };
  r.sistema = m.sistema
    ? { nivel: 'ok', corto: 'Listo', texto: 'Marcado como listo: el portal abre QUEMPIN.exe y la carpeta de cada proyecto.', marcado: 'sistema',
        acciones: [{ texto: 'Probar', ir: probarSistema }] }
    : { nivel: 'warn', corto: 'Revisar', texto: 'En el Explorador, abre «Cotizaciones y OC - Documentos › QUEMPIN.exe» con doble clic (1.3.10 o más nueva) y completa tu perfil. Luego pruébalo desde aquí.',
        acciones: [{ texto: 'Cómo hacerlo', ir: () => irATarjeta('sistema') }, { texto: 'Probar QUEMPIN.exe', ir: probarSistema, pri: true }] };
  if (dir) {
    await cargarPulso();
    const l = lecturaPulso(await leerPulso(dir));
    r.procesador = l
      ? { nivel: l.nivel, corto: l.nivel === 'ok' ? 'Al día' : l.detenido ? 'Detenido' : 'Revisar', texto: l.texto }
      : { nivel: 'warn', corto: 'Sin pulso', texto: 'La carpeta no tiene el pulso del procesador (publicado › estado.json).' };
  } else {
    r.procesador = { nivel: '', corto: 'Sin ver', texto: 'Se ve aquí cuando la biblioteca está conectada y con permiso.' };
  }
  return r;
}
// Desde el clic y sin esperas antes: el navegador solo pide permiso si viene de uno.
function darPermiso() {
  const h = carpetasVistas.biblioteca || carpetasVistas.intercambio;
  if (!h) return;
  h.requestPermission({ mode: 'readwrite' }).catch(() => null).then(pintarEstadoConexiones);
}
let revisando = null;
function pintarEstadoConexiones() {
  if (revisando) return revisando;
  revisando = revisarConexiones().then((r) => {
    // Solo el primer paso pendiente lleva el botón destacado: el que toca hacer ahora.
    const siguiente = ESTADOS.find((s) => !s.delEquipo && r[s.id] && r[s.id].nivel !== 'ok');
    ESTADOS.forEach((s) => {
      const x = r[s.id];
      const li = document.querySelector('#cxEstado li[data-estado="' + s.id + '"]');
      if (!li || !x) return;
      li.dataset.nivel = x.nivel || 'nada';
      li.classList.toggle('cx-sigue', s === siguiente);
      const num = li.querySelector('.cx-num');
      num.textContent = x.nivel === 'ok' ? '✓' : num.dataset.n;
      li.querySelector('.cx-est-det').textContent = x.texto;
      const txt = li.querySelector('.cx-est-txt');
      const viejo = txt.querySelector('.cx-est-dentro');
      if (viejo) viejo.remove();
      if (x.dentro) {
        const d = crear('div', 'cx-est-dentro');
        x.dentro.forEach((y) => {
          const s = crear('span', y.si === true ? 'si' : y.si === false ? 'no' : null, y.texto + (y.si === false ? ': no está' : ''));
          d.append(s);
        });
        txt.append(d);
      }
      const acc = li.querySelector('.cx-est-acc');
      acc.textContent = '';
      (x.acciones || []).forEach((a) => {
        let b;
        if (a.href) {
          b = crear('a', 'cx-enlace');
          b.href = a.href;
          b.target = '_blank';
          b.rel = 'noopener';
          b.append(crear('span', null, a.texto), icono('fuera', 14));
        } else {
          b = crear('button', a.pri && s === siguiente ? 'cx-boton' : 'cx-enlace', a.texto);
          b.type = 'button';
          b.addEventListener('click', a.ir);
        }
        acc.append(b);
      });
      if (x.marcado) {
        const d = crear('button', 'cx-desmarcar', 'Desmarcar');
        d.type = 'button';
        d.title = 'Volver a marcarlo como pendiente';
        d.addEventListener('click', () => marcar(x.marcado, false));
        acc.append(d);
      }
    });
    const pasos = ESTADOS.filter((s) => !s.delEquipo);
    const listos = pasos.filter((s) => r[s.id] && r[s.id].nivel === 'ok').length;
    $('#cxAvanceTxt').textContent = listos === pasos.length ? 'Este computador está listo' : listos + ' de ' + pasos.length + ' pasos listos';
    $('#cxBarra').style.width = Math.round(100 * listos / pasos.length) + '%';
    document.querySelectorAll('.cx-pildora').forEach((p) => {
      const x = r[p.dataset.estado];
      if (!x) return;
      p.querySelector('.cx-punto').className = 'cx-punto ' + (x.nivel || '');
      p.lastChild.textContent = x.corto;
      p.title = x.texto;
    });
  }).catch((e) => console.error(e)).then(() => { revisando = null; });
  return revisando;
}
function pintarConexiones() {
  armarConexiones();
  pintarEstadoConexiones();
}
