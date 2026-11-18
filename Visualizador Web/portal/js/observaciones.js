/* Portal QUEMPIN — Clic derecho, reportar errores y observaciones, errores sin aviso (ctx*, obs*, er*).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Clic derecho: el menú del portal (2026-10-30) ----------------------------------------------------------------------
// Vale en el portal y dentro de cada herramienta (enganchar). Shift + clic derecho deja el del navegador, igual que adentro
// de la ventana de reportar (corrector ortográfico, pegar). Si una herramienta tiene su propio menú y hace preventDefault, se
// respeta. Una de las opciones es reportar un error u observación: ver más abajo y docs/observaciones.md.
const CTX_SIN_TEXTO = /^(button|submit|reset|checkbox|radio|file|range|color|image|hidden)$/i;
const ctxElemento = (t) => (t && t.nodeType === 1 ? t : t && t.parentElement) || null;
function ctxCampo(el) {
  const c = el.closest('input, textarea, [contenteditable]:not([contenteditable="false"])');
  return !c || (c.tagName === 'INPUT' && CTX_SIN_TEXTO.test(c.type)) ? null : c;
}
const ctxEsValor = (c) => !!c && (c.tagName === 'INPUT' || c.tagName === 'TEXTAREA');
function ctxElegidoEnCampo(c) {
  try { return ctxEsValor(c) && c.selectionStart !== null ? c.value.slice(c.selectionStart, c.selectionEnd) : ''; } catch (e) { return ''; }
}
// Lo que hay en el punto del clic, tomado en ese momento: después el menú se lleva el foco.
function ctxLugar(e, p) {
  const el = ctxElemento(e.target);
  const doc = el.ownerDocument;
  const teclado = e.button !== 2 && !e.clientX && !e.clientY;     // la tecla de menú o Shift + F10
  const r = el.getBoundingClientRect();
  const x = Math.max(0, teclado ? r.left + Math.min(r.width / 2, 40) : e.clientX);
  const y = Math.max(0, teclado ? r.top + Math.min(r.height / 2, 20) : e.clientY);
  const m = p && p.marco ? p.marco.getBoundingClientRect() : { left: 0, top: 0 };
  const campo = ctxCampo(el);
  const foco = el.closest(OBS_ELEMENTO) || el;
  const rf = foco.getBoundingClientRect();
  return {
    p, doc, el, foco, teclado, x, y, xPortal: x + m.left, yPortal: y + m.top,
    rect: { x: rf.left, y: rf.top, ancho: rf.width, alto: rf.height },
    campo, enlace: el.closest('a[href]'),
    seleccion: (campo ? ctxElegidoEnCampo(campo) : String(doc.getSelection() || '')).trim(),
    desde: ctxEsValor(campo) ? campo.selectionStart : null, hasta: ctxEsValor(campo) ? campo.selectionEnd : null
  };
}
function ctxCopiar(txt, ok) {
  const mal = () => avisar('El navegador no dejó copiar. Usa Ctrl C.');
  try { navigator.clipboard.writeText(txt).then(() => { if (ok) avisar(ok); }, mal); } catch (e) { mal(); }
}
function ctxEnfocar(l) {
  const c = l.campo;
  try { l.doc.defaultView.focus(); } catch (e) { /* nada */ }
  c.focus();
  if (ctxEsValor(c) && l.desde !== null) { try { c.setSelectionRange(l.desde, l.hasta); } catch (e) { /* sin selección (number, date) */ } }
}
// insertText y delete dejan que el campo avise su cambio y que Ctrl Z lo deshaga, como si se hubiera tecleado.
function ctxPegarTexto(l, txt) {
  ctxEnfocar(l);
  if (l.doc.execCommand('insertText', false, txt) || !ctxEsValor(l.campo)) return;
  l.campo.setRangeText(txt, l.campo.selectionStart, l.campo.selectionEnd, 'end');
  l.campo.dispatchEvent(new Event('input', { bubbles: true }));
}
async function ctxPegar(l) {
  let txt = '';
  try { txt = await navigator.clipboard.readText(); } catch (e) {
    ctxEnfocar(l);
    avisar('El navegador no dejó pegar desde el menú. Usa Ctrl V.');
    return;
  }
  if (txt) ctxPegarTexto(l, txt);
}
function ctxCortar(l) {
  ctxCopiar(l.seleccion);
  ctxEnfocar(l);
  l.doc.execCommand('delete');
}
function ctxSeleccionarTodo(l) {
  ctxEnfocar(l);
  if (ctxEsValor(l.campo)) l.campo.select(); else l.doc.execCommand('selectAll');
}
function ctxRecargar(p) {
  if (p.familia !== estado.activa) activar(p.familia);
  const w = ventanaDe(p);
  if (!w) return;
  p.cargando = true;
  if (p.cargador) p.cargador.hidden = false;
  try { w.location.reload(); } catch (e) { p.marco.src = p.ultima || p.url; }
}
function ctxDireccion(p) {
  let href = p.ultima || p.url;
  try { const w = ventanaDe(p); if (w && w.location.href !== 'about:blank') href = w.location.href; } catch (e) { /* la pedida */ }
  return new URL(href, location.href).href;
}
const ctxAparte = (url) => { window.open(url, '_blank', 'noopener'); };
const ctxConMarco = (p) => !!p && !esVista(p);
// Las opciones, en grupos: primero lo que depende de dónde se hizo clic, después reportar y lo de siempre.
function ctxOpciones(l) {
  const grupos = [];
  const propio = [];
  const pest = !l.p && l.el.closest('.pestana[data-familia]');
  const lanzador = !l.p && !pest && l.el.closest('[data-herr]');
  const tab = pest && pestanaDe(pest.dataset.familia);
  if (tab) {
    if (ctxConMarco(tab)) {
      propio.push({ txt: 'Actualizar', ico: 'recargar', ir: () => ctxRecargar(tab) });
      propio.push({ txt: 'Abrir aparte', ico: 'fuera', ir: () => ctxAparte(ctxDireccion(tab)) });
    }
    propio.push({ txt: 'Cerrar esta pestaña', ico: 'cerrar', ir: () => cerrar(tab.familia) });
    if (estado.pestanas.length > 1) {
      propio.push({ txt: 'Cerrar las demás', ir: () => {
        estado.pestanas.filter((x) => x !== tab).forEach((x) => cerrar(x.familia));
        activar(tab.familia);
      } });
    }
  }
  if (lanzador) {
    const h = HERR.get(lanzador.dataset.herr);
    if (h) {
      propio.push({ txt: 'Abrir ' + h.nombre, ico: iconoDe(h), ir: () => abrir(h.id) });
      if (h.tipo === 'marco') propio.push({ txt: 'Abrir aparte', ico: 'fuera', ir: () => ctxAparte(new URL(urlDe(h), location.href).href) });
    }
  }
  if (l.campo) {
    const clave = l.campo.type === 'password';
    const editable = !l.campo.disabled && !l.campo.readOnly;
    if (l.seleccion && editable && !clave) propio.push({ txt: 'Cortar', ico: 'tijera', tecla: 'Ctrl X', ir: () => ctxCortar(l) });
    if (l.seleccion && !clave) propio.push({ txt: 'Copiar', ico: 'copiar', tecla: 'Ctrl C', ir: () => ctxCopiar(l.seleccion) });
    if (editable) propio.push({ txt: 'Pegar', ico: 'portapapeles', tecla: 'Ctrl V', ir: () => ctxPegar(l) });
    propio.push({ txt: 'Seleccionar todo', tecla: 'Ctrl A', ir: () => ctxSeleccionarTodo(l) });
  } else if (l.seleccion) {
    propio.push({ txt: 'Copiar', ico: 'copiar', tecla: 'Ctrl C', ir: () => ctxCopiar(l.seleccion) });
  }
  if (l.enlace && /^https?:/i.test(l.enlace.href)) {
    propio.push({ txt: 'Abrir el enlace en otra pestaña', ico: 'fuera', ir: () => ctxAparte(l.enlace.href) });
    propio.push({ txt: 'Copiar el enlace', ico: 'enlace', ir: () => ctxCopiar(l.enlace.href, 'Enlace copiado.') });
  }
  if (propio.length) grupos.push(propio);
  grupos.push([{ txt: 'Reportar un error u observación…', ico: 'nota', clase: 'ctx-reportar', ir: () => obsAbrir(l) }]);
  const comunes = [];
  const activa = pestanaDe(estado.activa);
  if (!tab && ctxConMarco(activa)) {
    comunes.push({ txt: 'Actualizar esta herramienta', ico: 'recargar', ir: () => ctxRecargar(activa) });
    comunes.push({ txt: 'Abrir aparte', ico: 'fuera', ir: () => ctxAparte(ctxDireccion(activa)) });
  }
  comunes.push({ txt: 'Copiar el enlace a esta pantalla', ico: 'enlace', ir: () => ctxCopiar(ctxConMarco(activa) ? ctxDireccion(activa) : location.href, 'Enlace copiado.') });
  comunes.push({ txt: 'Buscar', ico: 'lupa', tecla: 'Ctrl K', ir: enfocarBuscador });
  if (estado.activa !== 'observaciones') comunes.push({ txt: 'Ver las observaciones', ico: 'ayuda', ir: () => abrir('observaciones') });
  grupos.push(comunes);
  return grupos;
}
function ctxMostrar(l) {
  const menu = $('#menuCtx');
  const lista = $('#menuCtxLista');
  lista.textContent = '';
  ctxOpciones(l).forEach((grupo, i) => {
    if (i) { const sep = crear('div', 'ctx-sep'); sep.setAttribute('role', 'separator'); lista.append(sep); }
    grupo.forEach((op) => {
      const b = crear('button', 'ctx-item' + (op.clase ? ' ' + op.clase : ''));
      b.type = 'button';
      b.setAttribute('role', 'menuitem');
      const ico = crear('span', 'ctx-ico');
      if (op.ico) ico.append(icono(op.ico, 16));
      b.append(ico, crear('span', 'ctx-txt', op.txt));
      if (op.tecla) b.append(crear('kbd', null, op.tecla));
      b.addEventListener('click', () => { ctxCerrar(); op.ir(); });
      lista.append(b);
    });
  });
  menu.style.left = '0';
  menu.style.top = '0';
  if (!menu.open) menu.showModal();
  const r = menu.getBoundingClientRect();
  menu.style.left = Math.max(8, Math.min(l.xPortal, window.innerWidth - r.width - 8)) + 'px';
  menu.style.top = Math.max(8, Math.min(l.yPortal, window.innerHeight - r.height - 8)) + 'px';
  // Con el teclado parte en la primera opción; con el mouse, en ninguna: la primera flecha lleva a la primera.
  (l.teclado ? lista.querySelector('.ctx-item') : menu).focus();
}
function ctxCerrar() { const m = $('#menuCtx'); if (m.open) m.close(); }
function ctxDesdeEvento(e, p) {
  if (e.defaultPrevented || e.shiftKey) return;
  const el = ctxElemento(e.target);
  if (!el || el.closest('#dlgObs')) return;
  e.preventDefault();
  ctxMostrar(ctxLugar(e, p));
}
// Otro clic derecho con el menú abierto lo cierra y abre el de ese punto, como en el navegador.
function ctxOtroPunto(e) {
  ctxCerrar();
  const x = e.clientX, y = e.clientY;
  const el = document.elementFromPoint(x, y);
  if (!el) return;
  const p = el.tagName === 'IFRAME' ? estado.pestanas.find((t) => t.marco === el) : null;
  if (!p) { ctxMostrar(ctxLugar({ target: el, clientX: x, clientY: y, button: 2 }, null)); return; }
  let dentro = null;
  const m = el.getBoundingClientRect();
  try { dentro = el.contentDocument.elementFromPoint(x - m.left, y - m.top); } catch (err) { dentro = null; }
  if (dentro) ctxMostrar(ctxLugar({ target: dentro, clientX: x - m.left, clientY: y - m.top, button: 2 }, p));
}
function ctxTeclas(e) {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(e.key)) return;
  e.preventDefault();
  const items = Array.from($('#menuCtxLista').querySelectorAll('.ctx-item'));
  const i = items.indexOf(document.activeElement);
  const n = e.key === 'Home' ? 0 : e.key === 'End' ? items.length - 1 : e.key === 'ArrowDown' ? (i + 1) % items.length : (i <= 0 ? items.length : i) - 1;
  if (items[n]) items[n].focus();
}
document.addEventListener('contextmenu', (e) => {
  if ($('#menuCtx').open) {
    e.preventDefault();
    if (e.target === $('#menuCtx')) ctxOtroPunto(e);
    return;
  }
  ctxDesdeEvento(e, null);
});
$('#menuCtx').addEventListener('click', (e) => {
  // El clic no sigue hasta el documento, que cerraría la ventanita abierta de la Planificación.
  e.stopPropagation();
  if (e.target === $('#menuCtx')) ctxCerrar();
});
$('#menuCtx').addEventListener('keydown', ctxTeclas);
window.addEventListener('blur', ctxCerrar);

// ---- Reportar un error u observación (2026-10-30) ---------------------------------------------------------------------
// Queda como mensaje «observacion» en el buzón, con su lugar exacto y las imágenes en «buzon/adjuntos/<id>/»; nadie lo aplica
// solo: lo revisa una persona con /Observaciones_Portal (Sistema Intercambio/observaciones.py), y su respuesta se ve en la
// vista «Errores y observaciones». Flujo de Caja lleva sinCaptura en el registro: su resultado no debe quedar en esta carpeta,
// que ve toda la biblioteca, así que de ahí no sale imagen ni lo que muestra la pantalla.
const OBS_ELEMENTO = 'button, a, label, summary, th, td, li, h1, h2, h3, h4, h5, input, select, textarea, [role="button"], [role="tab"], [role="menuitem"], [data-herr]';
const OBS_TITULOS = 'h1, h2, h3, h4, legend, caption, summary';
const OBS_PESTANAS = '[role="tab"][aria-selected="true"], [role="tab"].is-active, .viz-tab-btn.is-active, .viz-tab-btn.active, .viz-modnav-tab.is-active';
const OBS_ARCHIVO = /_observacion_([A-Za-z0-9_-]{6,64})\.json$/;
const OBS_TIPOS_IMAGEN = { 'image/png': 'png', 'image/jpeg': 'jpg' };
const OBS_IMAGENES_MAX = 3;
const OBS_IMAGEN_BYTES = 10 * 1024 * 1024;
const OBS_NODOS_MAX = 60000;
const OBS_CAPTURA_MS = 8000;
const OBS_ANCHO_MAX = 1920;
const OBS_MESES = 3;
const OBS_CLASES = {
  error: { txt: 'Algo no funciona', ico: 'alerta' },
  dato: { txt: 'Un dato está mal', ico: 'tabla' },
  mejora: { txt: 'Se podría mejorar', ico: 'lapiz' }
};
const OBS_ESTADOS = {
  pendiente: ['warn', 'Por revisar'], aplicado: ['ok', 'Resuelta'], 'sin-cambios': ['', 'Sin cambios'],
  reemplazado: ['', 'Repetida'], rechazado: ['', 'No se aplicará'], descartado: ['', 'Descartada']
};
const obs = {
  lugar: null, herr: null, sinCaptura: false, donde: null, entorno: null, captura: null, fotoEnCurso: null, imagenes: [],
  acceso: null, dir: null, enviando: false, aviso: null,
  lista: [], leyendo: null, leido: 0, soloMias: false
};
const obsCorto = (s, max) => { const t = texto(s).replace(/\s+/g, ' '); return t.length > max ? t.slice(0, max - 1) + '…' : t; };

// ---- Dónde estaba la persona ---------------------------------------------------------------------------------------
function obsSelector(el) {
  const partes = [];
  for (let n = el, i = 0; n && n.nodeType === 1 && n.tagName !== 'HTML' && i < 6; n = n.parentElement, i++) {
    if (n.id && /^[A-Za-z][\w-]*$/.test(n.id)) { partes.unshift('#' + n.id); break; }
    let s = n.tagName.toLowerCase();
    const clases = Array.from(n.classList).filter((c) => /^[A-Za-z_][\w-]*$/.test(c)).slice(0, 2);
    if (clases.length) s += '.' + clases.join('.');
    const hermanos = n.parentElement ? Array.from(n.parentElement.children).filter((x) => x.tagName === n.tagName) : [];
    if (hermanos.length > 1) s += ':nth-of-type(' + (hermanos.indexOf(n) + 1) + ')';
    partes.unshift(s);
  }
  return partes.join(' > ');
}
// El título más cercano: el del propio elemento o el último antes de él, subiendo por sus contenedores.
function obsSeccion(el) {
  for (let n = el; n && n.tagName !== 'BODY' && n.tagName !== 'HTML'; n = n.parentElement) {
    let vistos = 0;
    for (let s = n; s && vistos < 40; s = s.previousElementSibling, vistos++) {
      if (s.matches(OBS_TITULOS)) return obsCorto(s.textContent, 120);
      if (s !== n) {
        const dentro = s.querySelectorAll(OBS_TITULOS);
        if (dentro.length) return obsCorto(dentro[dentro.length - 1].textContent, 120);
      }
    }
  }
  return '';
}
function obsElemento(foco, sinDatos) {
  const salida = { selector: obsSelector(foco), etiqueta: foco.tagName.toLowerCase() };
  const atributos = {};
  ['id', 'name', 'role', 'type'].forEach((a) => { if (foco.getAttribute(a)) atributos[a] = obsCorto(foco.getAttribute(a), 80); });
  if (!sinDatos) {
    Array.from(foco.attributes).filter((a) => a.name.startsWith('data-')).slice(0, 6).forEach((a) => { atributos[a.name] = obsCorto(a.value, 80); });
    const clave = foco.tagName === 'INPUT' && foco.type === 'password';
    const valor = /^(INPUT|TEXTAREA|SELECT)$/.test(foco.tagName) ? foco.value : foco.innerText || foco.textContent;
    if (!clave && texto(valor)) salida.texto = obsCorto(valor, 200);
    const titulo = foco.getAttribute('title') || foco.getAttribute('aria-label');
    if (titulo) salida.titulo = obsCorto(titulo, 200);
  }
  if (Object.keys(atributos).length) salida.atributos = atributos;
  return salida;
}
function obsPestanasInternas(doc) {
  const vistas = [];
  doc.querySelectorAll(OBS_PESTANAS).forEach((t) => {
    const txt = obsCorto(t.textContent, 60);
    if (txt && !t.closest('#pestanas') && t.getClientRects().length && !vistas.includes(txt)) vistas.push(txt);
  });
  return vistas.slice(0, 4);
}
function obsNavegador() {
  const m = navigator.userAgent.match(/(Edg|Firefox|Chrome|Version)\/(\d+)/);
  return m ? (m[1] === 'Version' ? 'Safari' : m[1] === 'Edg' ? 'Edge' : m[1]) + '/' + m[2] : '';
}
// La herramienta de un clic: la pestaña o el botón que se tocó, la del marco, o la pestaña activa.
function obsHerrDe(l) {
  if (l.p) return l.p.herr;
  const pest = l.el.closest('.pestana[data-familia]');
  const tab = pest && pestanaDe(pest.dataset.familia);
  if (tab) return tab.herr;
  const lanzador = l.el.closest('[data-herr]');
  if (lanzador && HERR.has(lanzador.dataset.herr)) return lanzador.dataset.herr;
  const activa = pestanaDe(estado.activa);
  return activa ? activa.herr : 'inicio';
}
function obsDonde() {
  const l = obs.lugar;
  const h = HERR.get(obs.herr);
  const donde = { herramienta: obs.herr || 'portal', nombre: h ? h.nombre : 'El portal en general' };
  if (h && h.peru) donde.pais = estado.pais === 'pe' ? 'PE' : 'CL';
  if (!l) { donde.ruta = [donde.nombre]; return donde; }
  const activa = pestanaDe(estado.activa);
  try { donde.direccion = l.p ? l.doc.defaultView.location.href : ctxConMarco(activa) ? ctxDireccion(activa) : location.href; } catch (e) { donde.direccion = location.href; }
  donde.ruta = [donde.nombre].concat(obsPestanasInternas(l.doc));
  const seccion = obsSeccion(l.foco);
  if (seccion) donde.seccion = seccion;
  const dlg = l.el.closest('dialog[open], [role="dialog"]');
  const tit = dlg && dlg.querySelector('h1, h2, h3');
  if (tit) donde.dialogo = obsCorto(tit.textContent, 120);
  donde.elemento = obsElemento(l.foco, obs.sinCaptura);
  if (l.seleccion && !obs.sinCaptura && !(l.campo && l.campo.type === 'password')) donde.seleccion = obsCorto(l.seleccion, 500);
  donde.posicion = { x: Math.round(l.x), y: Math.round(l.y) };
  return donde;
}
function obsEntorno() {
  const l = obs.lugar;
  const versiones = { portal: document.lastModified };
  // El sello que publicar.py le pone al Portal al publicarlo (2026-11-06): rama, commit y fecha del código que se vio
  const sello = document.querySelector('meta[name="quempin-version"]');
  if (sello && sello.content) versiones.codigo = sello.content;
  if (l && l.p) {
    versiones.herramienta = l.doc.lastModified;
    const d = l.doc.getElementById('vizGenerated');
    if (d && /\d/.test(d.textContent)) versiones.datos = obsCorto(d.textContent, 80);
  }
  const w = (l && l.doc.defaultView) || window;
  return {
    ventana: { ancho: w.innerWidth, alto: w.innerHeight }, tema: oscuroAhora() ? 'oscuro' : 'claro',
    navegador: obsNavegador(), movil: MOVIL.matches, versiones
  };
}

// ---- La imagen de la pantalla, sin librerías ----------------------------------------------------------------------------
// La página se copia a un <svg><foreignObject>, se dibuja en un canvas y sale un PNG. Una imagen SVG no carga nada de afuera,
// así que las hojas de estilo y las imágenes van incrustadas en la copia. Lo que no alcanza (fuentes web, fondos con url(),
// lo sticky) queda parecido: sirve para ver dónde estaba la persona, no para imprimir.
function obsImagenADatos(o, doc, cache) {
  const r = o.getBoundingClientRect();
  if (!o.complete || !o.naturalWidth || !r.width) return null;
  const ancho = Math.min(o.naturalWidth, Math.ceil(r.width * 2));
  const clave = (o.currentSrc || o.src) + '|' + ancho;
  if (cache.has(clave)) return cache.get(clave);
  const k = doc.createElement('canvas');
  k.width = ancho;
  k.height = Math.max(1, Math.round(o.naturalHeight * ancho / o.naturalWidth));
  k.getContext('2d').drawImage(o, 0, 0, k.width, k.height);
  const url = k.toDataURL();
  cache.set(clave, url);
  return url;
}
// La copia se hace en el acto, antes de abrir la ventana de reportar; serializarla y dibujarla pueden esperar.
function obsCopiarPagina(doc) {
  const raiz = doc.documentElement;
  const orig = raiz.querySelectorAll('*');
  if (orig.length > OBS_NODOS_MAX) throw new Error('página demasiado grande (' + orig.length + ' elementos)');
  const w = doc.defaultView;
  const clon = raiz.cloneNode(true);
  const copia = clon.querySelectorAll('*');
  const fuera = [];
  const cache = new Map();
  for (let i = 0; i < orig.length; i++) {
    const o = orig[i], c = copia[i], tag = o.tagName;
    if (/^(SCRIPT|NOSCRIPT|IFRAME|VIDEO|AUDIO|OBJECT|EMBED|TEMPLATE)$/.test(tag)) { fuera.push(c); continue; }
    if (tag === 'LINK') {
      if (!/stylesheet/i.test(o.rel)) { fuera.push(c); continue; }
      let css = '';
      try { css = Array.from(o.sheet.cssRules, (r) => r.cssText).join('\n'); } catch (e) { /* de otro sitio */ }
      const s = doc.createElement('style');
      s.textContent = css;
      c.replaceWith(s);
      continue;
    }
    if (tag === 'IMG') {
      let url = null;
      try { url = obsImagenADatos(o, doc, cache); } catch (e) { url = null; }
      c.removeAttribute('srcset');
      if (url) c.setAttribute('src', url); else c.removeAttribute('src');
    } else if (tag === 'CANVAS') {
      try {
        const r = o.getBoundingClientRect();
        const im = doc.createElement('img');
        im.src = o.toDataURL();
        if (o.id) im.id = o.id;
        if (o.className) im.className = o.className;
        im.style.cssText = (o.getAttribute('style') || '') + ';width:' + r.width + 'px;height:' + r.height + 'px';
        c.replaceWith(im);
      } catch (e) { /* dibujó algo de otro sitio: queda vacío */ }
      continue;
    } else if (tag === 'INPUT') {
      // Una clave nunca sale de su campo, y lo oculto no se ve.
      if (o.type === 'password' || o.type === 'hidden' || o.type === 'file') c.removeAttribute('value');
      else if (o.type === 'checkbox' || o.type === 'radio') { if (o.checked) c.setAttribute('checked', ''); else c.removeAttribute('checked'); }
      else c.setAttribute('value', o.value);
    } else if (tag === 'TEXTAREA') {
      c.textContent = o.value;
    } else if (tag === 'SELECT') {
      Array.from(c.options).forEach((op, n) => {
        if (o.options[n] && o.options[n].selected) op.setAttribute('selected', ''); else op.removeAttribute('selected');
      });
    }
    if (o.scrollTop || o.scrollLeft) {
      Array.from(c.children).forEach((h) => { h.style.translate = (-o.scrollLeft) + 'px ' + (-o.scrollTop) + 'px'; });
    }
  }
  fuera.forEach((c) => c.remove());
  // Un comentario con «--» dejaría la copia sin poder leerse como XML.
  const comentarios = doc.createTreeWalker(clon, 128);
  const sobran = [];
  while (comentarios.nextNode()) sobran.push(comentarios.currentNode);
  sobran.forEach((c) => c.remove());
  // La página desplazada: con position y no con transform, que movería también lo fijo.
  const cuerpo = clon.querySelector('body');
  if (cuerpo && (w.scrollX || w.scrollY)) {
    cuerpo.style.position = 'relative';
    cuerpo.style.top = (-w.scrollY) + 'px';
    cuerpo.style.left = (-w.scrollX) + 'px';
  }
  const extra = doc.createElement('style');
  extra.textContent = '*,*::before,*::after{animation:none!important;transition:none!important}' +
    'dialog[open]{position:fixed;inset:0;margin:auto;z-index:99999}';
  clon.appendChild(extra);
  const fondo = (e) => { const f = e ? w.getComputedStyle(e).backgroundColor : ''; return f && f !== 'rgba(0, 0, 0, 0)' && f !== 'transparent' ? f : ''; };
  // Lo de <html> va también en la raíz del svg: ahí es donde :root[data-theme] encuentra el modo.
  const atributos = Array.from(raiz.attributes).filter((a) => /^[A-Za-z_:][-\w:.]*$/.test(a.name) && a.name !== 'xmlns')
    .map((a) => a.name + '="' + a.value.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;') + '"').join(' ');
  return { clon, atributos, ancho: w.innerWidth, alto: w.innerHeight, fondo: fondo(doc.body) || fondo(raiz) || '#ffffff' };
}
async function obsDibujable(pagina) {
  const xml = new XMLSerializer().serializeToString(pagina.clon).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, '');
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" ' + pagina.atributos + ' width="' + pagina.ancho + '" height="' + pagina.alto + '">' +
    '<foreignObject x="0" y="0" width="100%" height="100%">' + xml + '</foreignObject></svg>';
  const img = new Image();
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  await img.decode();
  return img;
}
const obsBlob = (canvas, tipo, calidad) => new Promise((listo) => canvas.toBlob(listo, tipo, calidad));
async function obsRevelar(capas, marca) {
  const base = capas[0].pagina;
  const esc = Math.min(Math.max(window.devicePixelRatio || 1, 1), 2, OBS_ANCHO_MAX / base.ancho);
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(base.ancho * esc);
  canvas.height = Math.round(base.alto * esc);
  const g = canvas.getContext('2d');
  for (const capa of capas) {
    const img = await obsDibujable(capa.pagina);
    g.fillStyle = capa.pagina.fondo;
    g.fillRect(capa.x * esc, capa.y * esc, capa.pagina.ancho * esc, capa.pagina.alto * esc);
    g.drawImage(img, capa.x * esc, capa.y * esc, capa.pagina.ancho * esc, capa.pagina.alto * esc);
  }
  g.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--brand-orange').trim() || '#ff5100';
  const r = marca.rect;
  if (r.ancho * r.alto < base.ancho * base.alto * 0.5) {
    g.lineWidth = 2 * esc;
    g.setLineDash([6 * esc, 4 * esc]);
    g.strokeRect((r.x - 2) * esc, (r.y - 2) * esc, (r.ancho + 4) * esc, (r.alto + 4) * esc);
    g.setLineDash([]);
  }
  g.lineWidth = 4 * esc;
  g.beginPath();
  g.arc(marca.x * esc, marca.y * esc, 16 * esc, 0, Math.PI * 2);
  g.stroke();
  let blob = await obsBlob(canvas, 'image/png');
  if (blob && blob.size > 2.5 * 1024 * 1024) blob = await obsBlob(canvas, 'image/jpeg', 0.85);
  return blob;
}
// Se copia lo que se ve: la herramienta del clic o, si fue en el portal, el portal con la herramienta activa en su marco.
function obsSacarFoto(l) {
  const capas = [];
  try {
    if (l.p) {
      capas.push({ pagina: obsCopiarPagina(l.doc), x: 0, y: 0 });
    } else {
      capas.push({ pagina: obsCopiarPagina(document), x: 0, y: 0 });
      const activa = pestanaDe(estado.activa);
      if (ctxConMarco(activa) && activa.marco && !activa.cargando) {
        try {
          const m = activa.marco.getBoundingClientRect();
          capas.push({ pagina: obsCopiarPagina(activa.marco.contentDocument), x: m.left, y: m.top });
        } catch (e) { /* queda el portal, con el hueco del marco */ }
      }
    }
  } catch (e) {
    console.warn('Sin imagen de la pantalla:', e);
    obs.captura = { falla: true };
    return;
  }
  const esta = { enCurso: true };
  obs.captura = esta;
  const tiempo = new Promise((_, no) => setTimeout(() => no(new Error('tardó demasiado')), OBS_CAPTURA_MS));
  const marca = { x: l.x, y: l.y, rect: l.rect };
  const enCurso = new Promise((listo) => setTimeout(listo, 30))      // deja pintar la ventana primero
    .then(() => Promise.race([obsRevelar(capas, marca), tiempo]))
    .then((blob) => {
      if (obs.captura !== esta) return;
      if (!blob) throw new Error('sin imagen');
      obs.captura = { blob, url: URL.createObjectURL(blob) };
    })
    .catch((e) => {
      console.warn('Sin imagen de la pantalla:', e);
      if (obs.captura === esta) obs.captura = { falla: true };
    })
    .then(() => {
      if (obs.fotoEnCurso === enCurso) obs.fotoEnCurso = null;
      if ($('#dlgObs').open) obsPintarFotos();
    });
  obs.fotoEnCurso = enCurso;
}
function obsQuitarCaptura() {
  if (obs.captura && obs.captura.url) URL.revokeObjectURL(obs.captura.url);
  obs.captura = null;
}

// ---- La ventana de reportar -------------------------------------------------------------------------------------------
function obsLineaDonde() {
  const d = obs.donde;
  if (!d) return '';
  const partes = (d.ruta || []).slice();
  if (d.dialogo) partes.push(d.dialogo);
  else if (d.seccion && !partes.includes(d.seccion)) partes.push(d.seccion);
  const e = d.elemento;
  const que = e && (e.texto || e.titulo);
  return partes.join(' › ') + (que ? ' · «' + obsCorto(que, 60) + '»' : '');
}
function obsLlenarHerramientas() {
  const s = $('#obsHerr');
  if (s.options.length) return;
  const op = (v, t) => { const o = crear('option', null, t); o.value = v; s.append(o); };
  op('portal', 'El portal en general');
  REG.herramientas.filter((h) => h.tipo !== 'inicio' && !h.alias && h.id !== 'observaciones').forEach((h) => op(h.id, h.nombre));
}
function obsLlenarQuien() {
  const s = $('#obsQuien');
  if (!s.options.length) {
    const o = crear('option', null, 'Sin indicar');
    o.value = '';
    s.append(o);
    PERSONAL.forEach((p) => { const x = crear('option', null, p); x.value = p; s.append(x); });
  }
  s.value = estado.usuario || '';
}
// Una herramienta sin captura lo es también si es la que se ve detrás, aunque el clic haya sido en el portal.
function obsSinCaptura() {
  const activa = pestanaDe(estado.activa);
  const de = (id) => !!(HERR.get(id) || {}).sinCaptura;
  return de(obs.herr) || (!!obs.lugar && !!activa && de(activa.herr));
}
// Se abre con un clic derecho (l), o desde un botón: entonces se pregunta de qué herramienta se trata.
function obsAbrir(l) {
  const dlg = $('#dlgObs');
  if (dlg.open) return;
  obs.lugar = l || null;
  obsQuitarCaptura();
  obs.aviso = null;
  obs.acceso = null;
  if (l) {
    obs.herr = obsHerrDe(l);
  } else {
    obsLlenarHerramientas();
    const activa = pestanaDe(estado.activa);
    $('#obsHerr').value = activa && activa.herr !== 'observaciones' ? activa.herr : 'portal';
    obs.herr = $('#obsHerr').value;
  }
  obs.sinCaptura = obsSinCaptura();
  // Se fija ahora: mientras se escribe, la herramienta de atrás puede recargarse.
  obs.donde = l ? obsDonde() : null;
  obs.entorno = obsEntorno();
  $('#obsHerrCampo').hidden = !!l;
  if (l && !obs.sinCaptura && typeof window.showDirectoryPicker === 'function') obsSacarFoto(l);
  obsLlenarQuien();
  obsPintarLugar();
  obsPintarFotos();
  obsPintarAcceso();
  dlg.showModal();
  if (!window.matchMedia('(pointer: coarse)').matches) $('#obsNota').focus();
  obsPreparar();
}
function obsPintarLugar() {
  const linea = obsLineaDonde();
  $('#obsDonde').textContent = linea;
  $('#obsDonde').hidden = !linea;
  $('#obsSinCaptura').hidden = !obs.sinCaptura;
  $('#obsZonaImagen').hidden = obs.sinCaptura || typeof window.showDirectoryPicker !== 'function';
  if (obs.sinCaptura) {
    obs.imagenes.forEach((i) => URL.revokeObjectURL(i.url));
    obs.imagenes = [];
    obsQuitarCaptura();
  }
}
function obsTarjetaFoto(url, pie, quitar) {
  const f = crear('figure', 'obs-foto');
  const b = crear('button', 'obs-foto-ver');
  b.type = 'button';
  b.title = 'Ver más grande';
  b.setAttribute('aria-label', 'Ver más grande: ' + pie);
  const im = crear('img');
  im.src = url;
  im.alt = pie;
  b.append(im);
  b.addEventListener('click', () => f.classList.toggle('grande'));
  const x = crear('button', 'obs-foto-x');
  x.type = 'button';
  x.title = 'Quitar';
  x.setAttribute('aria-label', 'Quitar ' + pie);
  x.append(icono('cerrar', 14));
  x.addEventListener('click', () => { quitar(); obsPintarFotos(); });
  f.append(b, x, crear('figcaption', null, pie));
  return f;
}
function obsPintarFotos() {
  const cont = $('#obsFotos');
  cont.textContent = '';
  const c = obs.captura;
  if (c && c.enCurso) cont.append(crear('div', 'obs-foto obs-foto-nota', 'Sacando la imagen de la pantalla…'));
  if (c && c.url) cont.append(obsTarjetaFoto(c.url, 'Imagen de la pantalla', obsQuitarCaptura));
  obs.imagenes.forEach((i, n) => {
    cont.append(obsTarjetaFoto(i.url, i.file.name || 'Imagen pegada', () => { URL.revokeObjectURL(i.url); obs.imagenes.splice(n, 1); }));
  });
  $('#obsAgregar').hidden = obs.imagenes.length >= OBS_IMAGENES_MAX;
  $('#obsSinFoto').hidden = !(c && c.falla);
}
function obsAgregarImagenes(lista) {
  if (obs.sinCaptura) return;
  const malas = [];
  Array.from(lista || []).forEach((f) => {
    if (!OBS_TIPOS_IMAGEN[f.type]) { malas.push((f.name || 'la imagen') + ' (solo PNG o JPG)'); return; }
    if (!f.size || f.size > OBS_IMAGEN_BYTES) { malas.push((f.name || 'la imagen') + ' (hasta 10 MB)'); return; }
    if (obs.imagenes.length >= OBS_IMAGENES_MAX) { malas.push((f.name || 'la imagen') + ' (hasta ' + OBS_IMAGENES_MAX + ')'); return; }
    obs.imagenes.push({ file: f, url: URL.createObjectURL(f) });
  });
  obs.aviso = malas.length ? 'No se agregó: ' + malas.join('; ') + '.' : null;
  obsPintarFotos();
  obsPintarAcceso();
}
// Qué se puede hacer desde este navegador: enviar, pedir permiso al enviar, conectar la biblioteca o, sin carpetas, copiar el reporte.
async function obsPreparar() {
  if (typeof window.showDirectoryPicker !== 'function') { obs.acceso = 'navegador'; obs.dir = null; obsPintarAcceso(); return; }
  let c = {};
  try { c = await leerCarpetas(); } catch (e) { c = {}; }
  rc.carpetas = c;
  if (!c.intercambio) { obs.acceso = 'conectar'; obs.dir = null; obsPintarAcceso(); return; }
  obs.dir = await intercambioLegible(c);
  obs.acceso = obs.dir ? 'listo' : 'permiso';
  obsPintarAcceso();
}
function obsPintarAcceso() {
  const a = obs.acceso;
  const info = $('#obsAcceso');
  const enviar = $('#obsEnviar');
  $('#obsConectar').hidden = a !== 'conectar';
  $('#obsCompartir').hidden = !(a === 'navegador' && typeof navigator.share === 'function');
  let txt = obs.aviso || '';
  if (!txt && a === 'conectar') txt = 'Para enviarla, conecta una vez la biblioteca «' + BIBLIOTECA_FORMULACION + '» en este navegador: es la carpeta por donde viaja.';
  if (!txt && a === 'permiso') txt = 'Al enviar, el navegador pedirá permiso para escribir en la carpeta del equipo: elige «Ver y editar archivos».';
  if (!txt && a === 'navegador') txt = 'Este navegador no puede escribir en la carpeta del equipo. Copia el reporte y mándaselo a quien mantiene el portal, o envíalo desde Chrome o Edge de escritorio.';
  info.textContent = txt;
  info.hidden = !txt;
  info.classList.toggle('mal', !!obs.aviso);
  enviar.disabled = obs.enviando || !a || a === 'conectar';
  enviar.textContent = obs.enviando ? 'Enviando…' : a === 'navegador' ? 'Copiar el reporte' : 'Enviar';
}
function obsLimpiar() {
  $('#obsNota').value = '';
  $('#obsBloquea').checked = false;
  document.querySelector('input[name="obsClase"]').checked = true;
  obs.imagenes.forEach((i) => URL.revokeObjectURL(i.url));
  obs.imagenes = [];
  obsQuitarCaptura();
  obs.aviso = null;
}
const obsClaseElegida = () => document.querySelector('input[name="obsClase"]:checked').value;
function obsMensaje(id, enviado, adjuntos) {
  const origen = { herramienta: 'portal', enviado };
  const quien = $('#obsQuien').value;
  if (quien) origen.usuario = quien;
  const msg = {
    esquema: 'quempin.intercambio/1', id, tipo: 'observacion', destino: 'mejora-continua', origen,
    clase: obsClaseElegida(), nota: $('#obsNota').value.trim(), donde: obs.donde || obsDonde(), entorno: obs.entorno
  };
  if ($('#obsBloquea').checked) msg.bloquea = true;
  if (adjuntos.length) msg.adjuntos = adjuntos;
  return msg;
}
function obsTextoReporte() {
  const m = obsMensaje('', scAhora(), []);
  const d = m.donde;
  return ['Observación para el Portal QUEMPIN', OBS_CLASES[m.clase].txt + (m.bloquea ? ' · me impide seguir trabajando' : ''), m.nota, '',
    'Dónde: ' + (d.ruta || [d.nombre]).join(' › '), d.seccion ? 'Sección: ' + d.seccion : '', d.dialogo ? 'Ventana: ' + d.dialogo : '',
    d.elemento && d.elemento.texto ? 'Elemento: ' + d.elemento.texto : '', d.direccion ? 'Dirección: ' + d.direccion : '',
    m.origen.usuario ? 'Quién: ' + m.origen.usuario : '', 'Cuándo: ' + m.origen.enviado].filter((x, i) => x || i === 3).join('\n');
}
function obsCopiarReporte() {
  const mal = () => { obs.aviso = 'El navegador no dejó copiar. Selecciona el texto de la nota y cópialo.'; obsPintarAcceso(); };
  try {
    navigator.clipboard.writeText(obsTextoReporte()).then(() => {
      $('#dlgObs').close();
      obsLimpiar();
      avisar('Reporte copiado: pégalo en un mensaje a quien mantiene el portal.');
    }, mal);
  } catch (e) { mal(); }
}
async function obsArchivosFinales() {
  if (obs.fotoEnCurso) await obs.fotoEnCurso;
  const archivos = [];
  if (obs.captura && obs.captura.blob) {
    const b = obs.captura.blob;
    archivos.push({ nombre: 'captura.' + (OBS_TIPOS_IMAGEN[b.type] || 'png'), blob: b, origen: 'captura' });
  }
  obs.imagenes.forEach((i, n) => archivos.push({ nombre: 'imagen-' + (n + 1) + '.' + OBS_TIPOS_IMAGEN[i.file.type], blob: i.file, origen: 'pegada' }));
  return archivos;
}
// Las imágenes primero y el mensaje al final: nadie lo ve antes de que estén escritas.
async function obsEnviar(ev) {
  if (ev) ev.preventDefault();
  if (obs.enviando) return;
  if ($('#obsNota').value.trim().length < 3) {
    obs.aviso = 'Cuenta en pocas palabras qué pasó o qué se podría mejorar.';
    obsPintarAcceso();
    $('#obsNota').focus();
    return;
  }
  if (obs.acceso === 'navegador') { obsCopiarReporte(); return; }
  if (obs.acceso === 'conectar') return;
  obs.aviso = null;
  obs.enviando = true;
  obsPintarAcceso();
  try {
    if (obs.acceso !== 'listo') {
      const h = rc.carpetas && (rc.carpetas.biblioteca || rc.carpetas.intercambio);
      if (h) await h.requestPermission({ mode: 'readwrite' });   // sin esperas antes: el navegador solo pregunta si viene del clic
      obs.dir = await intercambioLegible(rc.carpetas || {});
      if (!obs.dir) throw Object.assign(new Error('sin permiso'), { name: 'NotAllowedError' });
      obs.acceso = 'listo';
    }
    const id = scId();
    const buzon = await obs.dir.getDirectoryHandle('buzon', { create: true });
    const archivos = await obsArchivosFinales();
    const adjuntos = [];
    if (archivos.length) {
      const carpeta = await (await buzon.getDirectoryHandle('adjuntos', { create: true })).getDirectoryHandle(id, { create: true });
      for (const a of archivos) {
        const datos = await a.blob.arrayBuffer();
        const h = await carpeta.getFileHandle(a.nombre, { create: true });
        const w = await h.createWritable();
        await w.write(datos);
        await w.close();
        adjuntos.push({ nombre: a.nombre, bytes: datos.byteLength, sha256: await scSha(datos), origen: a.origen });
      }
    }
    const enviado = scAhora();
    const msg = obsMensaje(id, enviado, adjuntos);
    const nombre = enviado.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_observacion_' + id + '.json';
    const h = await buzon.getFileHandle(nombre, { create: true });
    const w = await h.createWritable();
    await w.write(JSON.stringify(msg, null, 1));
    await w.close();
    obs.lista.unshift(obsFicha(msg, nombre, true));
    $('#dlgObs').close();
    obsLimpiar();
    avisar('Gracias: tu observación quedó registrada y se revisará.', { texto: 'Ver las observaciones', ir: () => abrir('observaciones') });
    if (!$('#vistaObservaciones').hidden) obsPintar();
  } catch (err) {
    console.error(err);
    const permiso = !!err && err.name === 'NotAllowedError';
    obs.aviso = 'No se pudo enviar: ' + (permiso ? 'falta el permiso para escribir en la carpeta del equipo.' : 'revisa que OneDrive esté funcionando y vuelve a intentarlo. Lo que escribiste sigue aquí.');
    if (permiso) obs.acceso = 'permiso';
  } finally {
    obs.enviando = false;
    if ($('#dlgObs').open) obsPintarAcceso();
  }
}
$('#obsForm').addEventListener('submit', obsEnviar);
$('#obsNota').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); obsEnviar(); }
});
$('#obsNota').addEventListener('input', () => { if (obs.aviso) { obs.aviso = null; obsPintarAcceso(); } });
// Cerrar con ✕ o Escape guarda lo escrito hasta la próxima vez; Cancelar lo borra.
$('#obsX').addEventListener('click', () => $('#dlgObs').close());
$('#obsCancelar').addEventListener('click', () => { $('#dlgObs').close(); obsLimpiar(); });
$('#dlgObs').addEventListener('click', (e) => e.stopPropagation());
$('#obsConectar').addEventListener('click', async () => { await conectarBiblioteca(); await obsPreparar(); rcCargar(); });
$('#obsCompartir').addEventListener('click', () => {
  navigator.share({ title: 'Observación para el Portal QUEMPIN', text: obsTextoReporte() }).then(() => { $('#dlgObs').close(); obsLimpiar(); }, () => { /* no la compartió */ });
});
$('#obsHerr').addEventListener('change', () => {
  obs.herr = $('#obsHerr').value;
  obs.sinCaptura = obsSinCaptura();
  obsPintarLugar();
  obsPintarFotos();
});
$('#obsArchivo').addEventListener('change', (e) => { obsAgregarImagenes(e.target.files); e.target.value = ''; });
$('#dlgObs').addEventListener('paste', (e) => {
  const imagenes = Array.from((e.clipboardData && e.clipboardData.files) || []).filter((f) => f.type.startsWith('image/'));
  if (!imagenes.length || obs.sinCaptura) return;
  e.preventDefault();
  obsAgregarImagenes(imagenes);
});
$('#dlgObs').addEventListener('dragover', (e) => { if (!obs.sinCaptura) e.preventDefault(); });
$('#dlgObs').addEventListener('drop', (e) => {
  if (obs.sinCaptura || !e.dataTransfer || !e.dataTransfer.files.length) return;
  e.preventDefault();
  obsAgregarImagenes(e.dataTransfer.files);
});
Object.entries(OBS_CLASES).forEach(([id, c], i) => {
  const l = crear('label', 'obs-clase');
  const r = crear('input');
  r.type = 'radio';
  r.name = 'obsClase';
  r.value = id;
  r.checked = !i;
  l.append(r, icono(c.ico, 17), crear('span', null, c.txt));
  $('#obsClases').append(l);
});
$('#obsAgregarIco').append(icono('mas', 18));

// ---- La vista: lo reportado y qué pasó con cada cosa --------------------------------------------------------------------
function obsFicha(m, archivo, pendiente) {
  const r = m.resultado || {};
  const d = m.donde && typeof m.donde === 'object' ? m.donde : {};
  return {
    id: texto(m.id), archivo, enviado: texto(m.origen && m.origen.enviado), usuario: texto(m.origen && m.origen.usuario),
    clase: texto(m.clase), nota: texto(m.nota), bloquea: !!m.bloquea,
    lugar: (Array.isArray(d.ruta) && d.ruta.length ? d.ruta.map(texto) : [texto(d.nombre) || texto(d.herramienta)]).filter(Boolean).join(' › '),
    n: Array.isArray(m.adjuntos) ? m.adjuntos.length : 0,
    estado: pendiente ? 'pendiente' : texto(r.estado), detalle: Array.isArray(r.detalle) ? r.detalle.map(texto).filter(Boolean) : [],
    automatico: m.automatico === true, firma: texto(m.tecnico && m.tecnico.firma) || texto(m.id),
    tecnico: m.tecnico && typeof m.tecnico === 'object'
      ? [texto(m.tecnico.archivo) && erCamino(texto(m.tecnico.archivo)), m.tecnico.linea].filter((x) => x !== '' && x != null).join(':') : ''
  };
}
async function obsLeer(dir) {
  const fichas = new Map();
  const leer = async (carpeta, pendiente) => {
    if (!carpeta) return;
    try {
      for await (const [n, h] of carpeta.entries()) {
        if (h.kind !== 'file' || !OBS_ARCHIVO.test(n)) continue;
        let m;
        try { m = JSON.parse(rcSinBom(await (await h.getFile()).text())); } catch (e) { continue; }
        if (!m || m.tipo !== 'observacion') continue;
        fichas.set(texto(m.id), obsFicha(m, n, pendiente));     // el mismo id en procesado manda: se lee después
      }
    } catch (e) { /* sin permiso o a medio sincronizar */ }
  };
  await leer(await rcSub(dir, 'buzon'), true);
  const hoy = new Date();
  for (let i = OBS_MESES - 1; i >= 0; i--) {
    const f = new Date(hoy.getFullYear(), hoy.getMonth() - i, 1);
    await leer(await rcSub(dir, 'procesado', f.getFullYear() + '-' + String(f.getMonth() + 1).padStart(2, '0')), false);
  }
  return Array.from(fichas.values());
}
function obsAlMostrar() {
  if (!rc.leyendo && (!rc.dir || !rc.leido || Date.now() - rc.leido > RC_RELEER_SEG * 1000)) rcCargar();   // al terminar llama a obsAlRecorrido
  else if (rc.dir) obsCargar();
  obsPintar();
}
function obsAlRecorrido() {
  if ($('#vistaObservaciones').hidden) return;
  if (rc.dir) obsCargar(); else obsPintar();
}
function obsCargar() {
  if (obs.leyendo) return obs.leyendo;
  const dir = rc.dir;
  if (!dir) return Promise.resolve();
  obs.leyendo = obsLeer(dir).then((lista) => { obs.lista = lista; obs.leido = Date.now(); }).catch((e) => { console.error(e); }).then(() => {
    obs.leyendo = null;
    obsPintar();
  });
  return obs.leyendo;
}
function obsPintar() {
  const hay = !!rc.dir;
  $('#obsLeyendo').hidden = hay || !rc.leyendo;
  $('#obsContenido').hidden = !hay;
  $('#obsVacio').hidden = hay || !!rc.leyendo || !rc.sinDatos;
  if (!hay && !rc.leyendo && rc.sinDatos) {
    pintarSinCarpeta($('#obsVacio'), rc.sinDatos, {
      navegador: 'Las observaciones viajan por la carpeta del equipo, y este navegador no puede abrir carpetas del computador. Igual puedes reportar: «Reportar», arriba, deja el reporte listo para copiarlo y mandarlo por mensaje.',
      conectar: 'Las observaciones viajan por la carpeta de intercambio. Conecta una vez la biblioteca «' + BIBLIOTECA_FORMULACION + '» en este navegador (la misma conexión del Formulador) y acepta «Ver y editar archivos».'
    });
  }
  if (!hay) return;
  const mias = !!estado.usuario && obs.soloMias;
  $('#obsMiasQuien').textContent = estado.usuario;
  $('#obsMiasQuien').hidden = !estado.usuario;
  $('#obsMias').disabled = !estado.usuario;
  $('#obsMias').checked = mias;
  const orden = (a, b) => (a.estado === 'pendiente' ? 0 : 1) - (b.estado === 'pendiente' ? 0 : 1) || b.enviado.localeCompare(a.enviado);
  const todas = obs.lista.filter((o) => !mias || o.usuario === estado.usuario);
  const lista = todas.filter((o) => !o.automatico).sort(orden);
  obsPintarAutomaticos(todas.filter((o) => o.automatico));
  const por = lista.filter((o) => o.estado === 'pendiente').length;
  $('#obsCuenta').textContent = lista.length ? por + ' por revisar de ' + pl(lista.length, 'observación', 'observaciones') : '';
  const ul = $('#obsLista');
  ul.textContent = '';
  if (!lista.length) {
    ul.append(crear('li', 'obs-fila obs-fila-vacia', obs.leyendo ? 'Leyendo…' : mias ? 'Todavía no has reportado nada.' : 'Todavía no hay observaciones. Con clic derecho, en cualquier pantalla, puedes reportar un error o una idea.'));
    return;
  }
  lista.forEach((o) => ul.append(obsFila(o)));
}
// Los errores que el Portal envió solo (2026-11-18): una fila por firma, con cuántas veces y cuántas personas.
function obsPintarAutomaticos(autos) {
  const grupos = new Map();
  autos.forEach((o) => {
    const g = grupos.get(o.firma);
    const pend = o.estado === 'pendiente';
    if (!g) { grupos.set(o.firma, { o, veces: 1, personas: new Set(o.usuario ? [o.usuario] : []), pend }); return; }
    g.veces++;
    if (o.usuario) g.personas.add(o.usuario);
    g.pend = g.pend || pend;
    if (o.enviado > g.o.enviado) g.o = o;
  });
  const filas = Array.from(grupos.values()).map((g) => Object.assign({}, g.o, {
    estado: g.pend ? 'pendiente' : g.o.estado, veces: g.veces, personas: g.personas.size
  })).sort((a, b) => (a.estado === 'pendiente' ? 0 : 1) - (b.estado === 'pendiente' ? 0 : 1) || b.enviado.localeCompare(a.enviado));
  $('#obsAuto').hidden = !filas.length;
  const por = filas.filter((o) => o.estado === 'pendiente').length;
  $('#obsAutoResumen').textContent = 'Errores detectados solos: ' + pl(filas.length, 'error', 'errores') + (por ? ', ' + por + ' por revisar' : '');
  const ul = $('#obsAutoLista');
  ul.textContent = '';
  filas.forEach((o) => ul.append(obsFila(o)));
}
function obsFila(o) {
  const li = crear('li', 'obs-fila');
  const cab = crear('div', 'obs-fila-cab');
  const [nivel, txt] = Object.hasOwn(OBS_ESTADOS, o.estado) ? OBS_ESTADOS[o.estado] : ['', o.estado || 'Revisada'];
  const pill = crear('span', 'sc-pill', txt);
  if (nivel) pill.dataset.nivel = nivel;
  cab.append(pill);
  if (Object.hasOwn(OBS_CLASES, o.clase)) cab.append(crear('span', 'obs-fila-clase', OBS_CLASES[o.clase].txt));
  if (o.bloquea && o.estado === 'pendiente') cab.append(crear('span', 'obs-fila-bloquea', 'Impide trabajar'));
  li.append(cab, crear('p', 'obs-fila-nota', o.nota));
  const fecha = o.enviado ? new Date(o.enviado) : null;
  const cuando = fecha && !isNaN(fecha) ? fecha.toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
  if (o.automatico && o.tecnico) li.append(crear('p', 'obs-fila-tec', o.tecnico));
  const veces = o.veces > 1 ? 'visto ' + o.veces + ' veces' + (o.personas > 1 ? ' por ' + o.personas + ' personas' : '') : '';
  li.append(crear('span', 'sc-env-det', [o.lugar, veces || o.usuario, cuando, o.n ? pl(o.n, 'imagen', 'imágenes') : ''].filter(Boolean).join(' · ')));
  if (o.detalle.length) {
    const res = crear('p', 'obs-fila-res');
    res.append(crear('strong', null, 'Respuesta: '), o.detalle.join(' '));
    li.append(res);
  }
  if (!o.automatico && o.estado === 'pendiente' && estado.usuario && o.usuario === estado.usuario) {
    const b = crear('button', 'cx-enlace obs-retirar', 'Retirar');
    b.type = 'button';
    b.addEventListener('click', () => obsRetirar(o, b));
    li.append(b);
  }
  return li;
}
// El mensaje se borra primero, para que nunca quede uno esperando imágenes que ya no van a llegar.
async function obsRetirar(o, b) {
  if (b.dataset.seguro !== 'si') {
    b.dataset.seguro = 'si';
    b.textContent = '¿Retirarla? Toca otra vez';
    setTimeout(() => { if (b.isConnected) { b.dataset.seguro = ''; b.textContent = 'Retirar'; } }, 5000);
    return;
  }
  b.disabled = true;
  try {
    const buzon = await rc.dir.getDirectoryHandle('buzon');
    await buzon.removeEntry(o.archivo);
    const delArchivo = OBS_ARCHIVO.exec(o.archivo)[1];
    try { await (await buzon.getDirectoryHandle('adjuntos')).removeEntry(delArchivo, { recursive: true }); } catch (e) { /* no llevaba imágenes */ }
    obs.lista = obs.lista.filter((x) => x.id !== o.id);
    avisar('Se retiró tu observación.');
  } catch (err) {
    console.error(err);
    avisar('No se pudo retirar: ' + (err && err.name === 'NotAllowedError' ? 'falta el permiso para escribir en la carpeta del equipo.' : 'revisa que OneDrive esté funcionando y vuelve a intentarlo.'));
    b.disabled = false;
  }
  obsPintar();
}
$('#obsActualizar').append(icono('recargar', 16));
$('#obsActualizar').addEventListener('click', () => {
  if (rc.sinDatos === 'permiso') { rcPedirPermiso(); return; }
  rcCargar();
});
$('#obsMias').addEventListener('change', (e) => { obs.soloMias = e.target.checked; obsPintar(); });
$('#obsNueva').addEventListener('click', () => obsAbrir(null));

// ---- Errores sin aviso (2026-11-18) -----------------------------------------------------------------------------------
/* Plan docs/plans/2026-11-18-mejoras-portal.md, fase A: un error de JavaScript en el PC de un colega no le llegaba a
   nadie. Ahora el Portal (y cada herramienta que abre, ver enganchar) lo envía solo como «observacion» con
   automatico: true y su detalle técnico, sin imagen. Frenos: la misma firma (herramienta, mensaje, archivo, línea) una
   vez al día por navegador, y a lo más ER_POR_SESION por visita. Sin permiso de escritura en la carpeta (no se pide:
   no hay un clic), espera en quempin_portal_errores_pendiente y sale en la próxima ocasión. En una herramienta
   sinCaptura (Flujo de Caja) no va la pila ni la ruta interna (#…). */
const ER_POR_SESION = 5;
const ER_PENDIENTES_MAX = 20;
const ER_PILA_MAX = 4000;
const ER_VISTOS = 'quempin_portal_errores_vistos';
const ER_PENDIENTE = 'quempin_portal_errores_pendiente';
// Ruido conocido: el aviso inofensivo de ResizeObserver y «Script error.» (de otro sitio: no trae nada que sirva)
const ER_IGNORAR = /ResizeObserver loop|^(Uncaught )?Script error\.?$/i;
const ER_EXTENSION = /^(chrome|moz|safari(-web)?|ms-browser)-extension:/i;
const er = { tomados: 0, enviando: false };
function erLeer(clave, porDefecto) {
  try { const v = JSON.parse(localStorage.getItem(clave)); return v == null ? porDefecto : v; } catch (e) { return porDefecto; }
}
function erGuardar(clave, v) {
  try { localStorage.setItem(clave, JSON.stringify(v)); } catch (e) { /* sin almacenamiento: se pierde, no molesta */ }
}
const erSinRutaInterna = (u) => String(u || '').split(/[?#]/)[0];
function erCamino(u) { try { return new URL(u).pathname; } catch (e) { return erSinRutaInterna(u); } }
const erEntero = (n) => (Number.isInteger(n) && n >= 0 ? n : null);
// La herramienta de un error del propio Portal: la vista que se ve, si es del Portal; si no, el Portal en general.
function erHerrDelPortal() {
  const a = pestanaDe(estado.activa);
  if (!a) return estado.activa === 'inicio' ? 'inicio' : 'portal';
  return ctxConMarco(a) ? 'portal' : a.herr;
}
// Lo que se guarda y se envía; null si es ruido.
function erArmar(r, herr, w) {
  const mensaje = obsCorto(r && r.mensaje, 300);
  if (!mensaje || ER_IGNORAR.test(mensaje) || ER_EXTENSION.test(r.archivo || '')) return null;
  const h = HERR.get(herr);
  const sinDatos = !!(h && h.sinCaptura);
  const archivo = erSinRutaInterna(r.archivo).slice(0, 300);
  const linea = erEntero(r.linea);
  const firma = [herr || 'portal', mensaje, erCamino(archivo), linea == null ? '' : linea].join('|').slice(0, 200);
  const tecnico = { tipo: r.tipo === 'promesa' ? 'promesa' : 'error', mensaje, firma };
  if (archivo) tecnico.archivo = archivo;
  if (linea != null) tecnico.linea = linea;
  if (erEntero(r.columna) != null) tecnico.columna = r.columna;
  if (!sinDatos && r.pila) tecnico.pila = String(r.pila).slice(0, ER_PILA_MAX);
  const nombre = h ? h.nombre : 'El portal en general';
  const donde = { herramienta: herr || 'portal', nombre, ruta: [nombre] };
  if (h && h.peru) donde.pais = estado.pais === 'pe' ? 'PE' : 'CL';
  const versiones = {};
  const sello = document.querySelector('meta[name="quempin-version"]');
  if (sello && sello.content) versiones.codigo = sello.content;
  try {
    donde.direccion = (sinDatos ? erSinRutaInterna(w.location.href) : w.location.href).slice(0, 500);
    if (w !== window) versiones.herramienta = w.document.lastModified;
  } catch (e) { /* el marco ya no está */ }
  let ventana = null;
  try { ventana = { ancho: w.innerWidth, alto: w.innerHeight }; } catch (e) { ventana = null; }
  const entorno = { navegador: obsNavegador(), movil: MOVIL.matches, versiones };
  if (ventana) entorno.ventana = ventana;
  return { firma, cuando: scAhora(), usuario: estado.usuario || '', donde, entorno, tecnico };
}
function erTomar(r, herr, w) {
  let m = null;
  try { m = erArmar(r, herr, w || window); } catch (e) { m = null; }
  if (!m || er.tomados >= ER_POR_SESION) return;
  const hoy = m.cuando.slice(0, 10);
  const vistos = erLeer(ER_VISTOS, {});
  if (vistos[m.firma] === hoy) return;
  er.tomados++;
  Object.keys(vistos).forEach((k) => { if (vistos[k] !== hoy) delete vistos[k]; });
  vistos[m.firma] = hoy;
  erGuardar(ER_VISTOS, vistos);
  const cola = erLeer(ER_PENDIENTE, []);
  const lista = Array.isArray(cola) ? cola : [];
  lista.push(m);
  erGuardar(ER_PENDIENTE, lista.slice(-ER_PENDIENTES_MAX));
  erEnviar();
}
function erMensaje(m, id) {
  const origen = { herramienta: 'portal', enviado: m.cuando };
  if (m.usuario) origen.usuario = m.usuario;
  return {
    esquema: 'quempin.intercambio/1', id, tipo: 'observacion', destino: 'mejora-continua', origen, clase: 'error',
    automatico: true, nota: obsCorto('Error automático: ' + m.tecnico.mensaje, 320), donde: m.donde, entorno: m.entorno,
    tecnico: m.tecnico
  };
}
// Envía lo que espera, del más antiguo al más nuevo. Sin permiso ya dado, no hace nada: no se pide sin un clic.
async function erEnviar() {
  if (er.enviando) return;
  const leida = erLeer(ER_PENDIENTE, []);
  const cola = (Array.isArray(leida) ? leida : []).filter((m) => m && m.tecnico && typeof m.cuando === 'string' && m.donde);
  if (cola.length !== (Array.isArray(leida) ? leida.length : -1)) erGuardar(ER_PENDIENTE, cola);   // lo ilegible se bota
  if (!cola.length) return;
  er.enviando = true;
  let completo = false;
  try {
    const dir = await intercambioLegible(await leerCarpetas());
    if (!dir) return;
    const buzon = await dir.getDirectoryHandle('buzon', { create: true });
    for (const m of cola) {
      const id = scId();
      const nombre = m.cuando.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_observacion_' + id + '.json';
      const w = await (await buzon.getFileHandle(nombre, { create: true })).createWritable();
      await w.write(JSON.stringify(erMensaje(m, id), null, 1));
      await w.close();
      // Se saca de la cola apenas se escribe: lo que llegó mientras tanto se queda
      const quedan = erLeer(ER_PENDIENTE, []);
      erGuardar(ER_PENDIENTE, (Array.isArray(quedan) ? quedan : []).filter((x) => !(x && x.firma === m.firma && x.cuando === m.cuando)));
    }
    completo = true;
  } catch (e) {
    console.warn('No se pudo enviar un error automático; queda para la próxima.', e);
  } finally {
    er.enviando = false;
  }
  // Lo que llegó mientras se enviaba sale ahora (solo si esta pasada funcionó: si no, espera otra ocasión)
  if (completo && (erLeer(ER_PENDIENTE, []) || []).length) setTimeout(erEnviar, 0);
}
(function erEnganchar() {
  const q = window.__qpnErrores;
  if (!q) return;
  // Lo anotado antes de este punto (el arranque de ahora o uno que se cayó en una visita anterior)
  const antes = erLeer(q.CLAVE, []);
  try { localStorage.removeItem(q.CLAVE); } catch (e) { /* nada */ }
  q.oir = (r) => erTomar(r, erHerrDelPortal(), window);
  (Array.isArray(antes) ? antes : []).forEach((r) => erTomar(r, 'portal', window));
  setTimeout(erEnviar, 5000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) erEnviar(); });
})();
