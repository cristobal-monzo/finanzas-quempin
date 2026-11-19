/* Portal QUEMPIN — utilidades, estado, menú, pestañas y marcos, al día sin F5, usuario y diálogos.
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

const REG = JSON.parse(document.getElementById('portal-registro').textContent);
const HERR = new Map(REG.herramientas.map((h) => [h.id, h]));
const LS = {
  pestanas: 'quempin_portal_pestanas',
  proyecto: 'quempin_portal_proyecto',
  menu: 'quempin_portal_menu',
  pais: 'quempin_portal_pais',
  tema: 'quempin_hub_theme',         // el mismo del índice: claro u oscuro en los dos
  // El usuario (2026-10-16): la misma clave del Formulador (js/usuario.js), con las iniciales tal cual
  // (texto, no JSON), así elegirlo aquí o allá vale para los dos.
  usuario: 'quempin_usuario'
};
// Solo se leen: los escriben el Formulador (sus proyectos) y los tableros (la clave del candado).
const LS_FORMULADOR = 'qpn.formulacion.proyectos.v1';
const LS_CLAVE_TABLEROS = 'quempin_viz_clave';
// Las iniciales que el Formulador guardaba antes del selector de usuario (solo se leen, para
// adoptarlas la primera vez, igual que hace js/usuario.js)
const LS_FORMULADOR_ANTES = ['qpn.formulacion.iniciales', 'qpn.formulacion.config.v1'];
const USUARIOS = Array.isArray(REG.usuarios) ? REG.usuarios : [];
const MAX_MARCOS = 8;                  // herramientas cargadas a la vez; las demás se recargan al volver
const MOVIL = window.matchMedia('(max-width: 760px)');
const RUTA_PORTAL = rutaNormal(location.pathname);
const RUTA_INDICE = RUTA_PORTAL.replace(/[^/]+\/$/, '');   // /finanzas-quempin/

const $ = (s) => document.querySelector(s);
const portal = $('#portal');

// ---- Utilidades ------------------------------------------------------------------------------
function leer(clave, def) {
  try { const v = localStorage.getItem(clave); return v === null ? def : JSON.parse(v); } catch (e) { return def; }
}
function guardar(clave, valor) {
  try { localStorage.setItem(clave, JSON.stringify(valor)); } catch (e) { /* sin almacenamiento: solo esta visita */ }
}
const norm = (s) => String(s === null || s === undefined ? '' : s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const texto = (s) => String(s === null || s === undefined ? '' : s).trim();
function rutaNormal(pathname) {
  let p = pathname || '/';
  try { p = decodeURIComponent(p); } catch (e) { /* tal cual */ }
  p = p.replace(/index\.html$/, '');
  return p.endsWith('/') ? p : p + '/';
}
function crear(tag, clase, txt) {
  const e = document.createElement(tag);
  if (clase) e.className = clase;
  if (txt !== undefined && txt !== null) e.textContent = txt;
  return e;
}
const ICONOS = {
  inicio: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
  proyectos: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  bandera: '<path d="M5 21V4"/><path d="M5 4h11l-2 4 2 4H5"/>',
  portapapeles: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3h6v3H9z"/><path d="M9 12h6M9 16h4"/>',
  calculadora: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8"/><path d="M8.5 12h.01M12 12h.01M15.5 12h.01M8.5 16h.01M12 16h.01M15.5 16h.01" stroke-width="2.6"/>',
  documento: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>',
  barras: '<path d="M3 21h18"/><path d="M6 17v-6M11 17V5M16 17v-9"/>',
  billetera: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18"/><path d="M16 14h2"/>',
  ayuda: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .8-1 1.5v.7"/><path d="M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.6h.01" stroke-width="2.6"/>',
  // El mismo engranaje de «Configuración» del Formulador
  engranaje: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
  nube: '<path d="M7 18a4.5 4.5 0 0 1-.6-9 6 6 0 0 1 11.4 1.6A3.7 3.7 0 0 1 17.5 18z"/>',
  tabla: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9.5h18M3 15h18M9 4v16"/>',
  ventana: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 8.5h18"/><path d="M6 6.3h.01M8.5 6.3h.01" stroke-width="2.4"/>',
  persona: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  llave: '<circle cx="8" cy="15" r="4"/><path d="M11 12l9-9M16 7l3 3M14 9l2 2"/>',
  globo: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
  reloj: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  flecha: '<path d="M6 9l6 6 6-6"/>',
  fuera: '<path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  cerrar: '<path d="M6 6l12 12M18 6L6 18"/>',
  // Recorrido de proyectos: el camino de un proyecto, de un punto a otro
  ruta: '<circle cx="5.5" cy="6" r="2.5"/><circle cx="18.5" cy="18" r="2.5"/><path d="M8 6h7.5a3.5 3.5 0 0 1 0 7h-7a3.5 3.5 0 0 0 0 7H16"/>',
  derecha: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  recargar: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  alerta: '<path d="M12 3.5l9 16H3z"/><path d="M12 10v4.5M12 17.5h.01"/>',
  mas: '<path d="M12 5v14M5 12h14"/>',
  luna: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  sol: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  // Planificación semanal
  calendario: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/><path d="M7.5 14h.01M12 14h.01M16.5 14h.01M7.5 17.5h.01M12 17.5h.01" stroke-width="2.6"/>',
  cuadricula: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
  izquierda: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  copiar: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  compartir: '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="M8.2 10.8l7.6-4.4M8.2 13.2l7.6 4.4"/>',
  subir: '<path d="M12 15V4M7 9l5-5 5 5"/><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
  imprimir: '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
  // Una camioneta de lado: los vehículos de la empresa
  vehiculo: '<path d="M14 17V6.5a1 1 0 0 0-1-1H3.5a1 1 0 0 0-1 1V16a1 1 0 0 0 1 1H5"/><path d="M14 9.5h3.6l3.4 4.2V16a1 1 0 0 1-1 1h-.5"/><path d="M9 17h6.5"/><circle cx="7" cy="17" r="2"/><circle cx="17.5" cy="17" r="2"/>',
  // Proyectos en ejecución: un casco de obra
  casco: '<path d="M3.5 17.5h17"/><path d="M5.5 17.5V15a6.5 6.5 0 0 1 13 0v2.5"/><path d="M10 9V6.5a2 2 0 0 1 4 0V9"/>',
  basurero: '<path d="M4 7h16M9.5 7V4.5h5V7"/><path d="M6.5 7l1 13h9l1-13"/>',
  lapiz: '<path d="M4 20l1-4.5L15.5 5a2.1 2.1 0 0 1 3 3L8 18.5z"/><path d="M13.5 7l3 3"/>',
  // Clic derecho: una nota, un enlace, cortar y buscar
  nota: '<path d="M5 4h14a1 1 0 0 1 1 1v10l-5 5H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"/><path d="M15 20v-5h5"/><path d="M8 9h8M8 13h4"/>',
  enlace: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.7l1-1"/>',
  tijera: '<circle cx="6" cy="6.5" r="2.5"/><circle cx="6" cy="17.5" r="2.5"/><path d="M8.2 8l11.8 9M8.2 16L20 7"/>',
  lupa: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  // El estado de un proyecto en ejecución (2026-11-09): el color nunca va solo
  visto: '<path d="M5 12.5l4.5 4.5L19 7.5" stroke-width="3"/>',
  exclama: '<path d="M12 5.5v8.5" stroke-width="3"/><path d="M12 18.6h.01" stroke-width="3.6"/>',
  cruz: '<path d="M7 7l10 10M17 7L7 17" stroke-width="3"/>',
  guion: '<path d="M7 12h10" stroke-width="3"/>',
  // Las herramientas (2026-11-10, el Inicio «Tres áreas»): un dibujo propio cada una, el mismo en el Inicio y en su pestaña
  oportunidad: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/><path d="M11 8v6M8 11h6"/>',
  requerimiento: '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/>',
  formulario: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1"/><path d="M9 10h6M9 14h6M9 18h3"/>',
  seguimiento: '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h6a3 3 0 0 0 0-6h-4a3 3 0 0 1 0-6h6"/>',
  etiqueta: '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.5"/>',
  emitir: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M9 15h6M12 12v6"/>',
  gantt: '<path d="M4 4v16h16"/><path d="M7 8h6M10 12h7M8 16h5"/>',
  carro: '<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l3 12h11l2-8H6.5"/>',
  avance: '<path d="M4 20h16"/><path d="M7 16v-4M12 16V8M17 16v-7"/>',
  recibo: '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
  rendicion: '<path d="M5 3h11v8"/><path d="M5 3v18l2.5-1.5L10 21l2.5-1.5"/><path d="M8 8h5M8 12h3"/><circle cx="17" cy="17" r="4"/><path d="M15.5 17l1 1 2-2"/>',
  tendencia: '<path d="M3 20h18"/><path d="M5 16l5-5 4 3 6-7"/><path d="M15 7h5v5"/>',
  flujo: '<path d="M4 8h14l-3-3M20 16H6l3 3"/>',
  diametro: '<circle cx="12" cy="12" r="8"/><path d="M6 18L18 6"/>',
  h2: '<path d="M4 6v12M12 6v12M4 12h8"/><path d="M15 13.5a2.5 2.5 0 0 1 5 0c0 2-5 3-5 5h5"/>',
  llama: '<path d="M12 3c1 4 6 6 6 11a6 6 0 0 1-12 0c0-3 2-4 2-7 2 1 3 3 3 5 1-2 1-5 1-9z"/>',
  moleculas: '<circle cx="8" cy="15" r="4"/><circle cx="16" cy="9" r="3"/><circle cx="17" cy="18" r="2"/>'
};
function icono(nombre, tam) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 24 24');
  s.setAttribute('width', String(tam || 18));
  s.setAttribute('height', String(tam || 18));
  s.setAttribute('fill', 'none');
  s.setAttribute('stroke', 'currentColor');
  s.setAttribute('stroke-width', '1.9');
  s.setAttribute('stroke-linecap', 'round');
  s.setAttribute('stroke-linejoin', 'round');
  s.setAttribute('aria-hidden', 'true');
  s.innerHTML = ICONOS[nombre] || '';   // dibujos fijos de esta página, nunca datos
  return s;
}
let relojAviso = null;
// accion (opcional): { texto, ir } agrega un botón al aviso, que dura más para alcanzar a usarlo.
function avisar(msg, accion) {
  const a = $('#aviso');
  a.textContent = msg;
  if (accion) {
    const b = crear('button', null, accion.texto);
    b.type = 'button';
    b.addEventListener('click', () => { a.hidden = true; accion.ir(); });
    a.append(b);
  }
  a.hidden = false;
  clearTimeout(relojAviso);
  relojAviso = setTimeout(() => { a.hidden = true; }, accion ? 9000 : 4200);
}

// ---- La explicación en un ícono (2026-11-05) ----------------------------------------------------
/* Lo que antes era un párrafo bajo un título va en un ⓘ: se abre al pasar el mouse (y se cierra al salir) o al tocarlo
   (queda abierto hasta tocar fuera o Esc). El texto sigue en la página, escondido, como descripción del botón para los
   lectores de pantalla. contenido: un texto, un nodo o una lista de los dos. */
let infoN = 0;
function info(contenido, etiqueta) {
  const w = crear('span', 'info lista');
  const b = crear('button', 'info-i');
  b.type = 'button';
  b.setAttribute('aria-label', etiqueta || 'Qué es esto');
  b.setAttribute('aria-expanded', 'false');
  b.append(icono('info', 18));
  const t = crear('span', 'info-txt');
  t.hidden = true;
  t.id = 'infoTxt' + (++infoN);
  [].concat(contenido).forEach((x) => { if (x !== null && x !== undefined && x !== '') t.append(typeof x === 'string' ? document.createTextNode(x) : x); });
  b.setAttribute('aria-describedby', t.id);
  w.append(b, t);
  return w;
}
// Una línea corta con su ⓘ: lo que pasa en pocas palabras, y el detalle a un toque
function lineaInfo(clase, corto, largo, etiqueta) {
  const p = crear('p', 'linea-info' + (clase ? ' ' + clase : ''));
  p.append(crear('span', null, corto), info(largo, etiqueta));
  return p;
}
// Los ⓘ escritos en el HTML: <span class="info" data-etiqueta="…">el texto</span>
function infoPreparar(raiz) {
  raiz.querySelectorAll('.info:not(.lista)').forEach((w) => w.replaceWith(info([...w.childNodes], w.dataset.etiqueta)));
}
const infoPop = crear('div', 'info-pop');
infoPop.id = 'infoPop';
infoPop.setAttribute('popover', 'manual');
infoPop.setAttribute('role', 'tooltip');
let infoDe = null, infoFijo = false, infoReloj = null;
function infoAbrir(b, fijo) {
  clearTimeout(infoReloj);
  infoFijo = fijo;
  if (infoDe === b && infoPop.matches(':popover-open')) return;
  infoCerrar();
  const t = document.getElementById(b.getAttribute('aria-describedby'));
  if (!t || typeof infoPop.showPopover !== 'function') return;
  infoFijo = fijo;
  // Junto a su botón, para que un toque dentro del globo cuente como dentro del menú o diálogo donde está
  b.parentNode.append(infoPop);
  infoPop.replaceChildren(...[...t.childNodes].map((n) => n.cloneNode(true)));
  infoPop.showPopover();
  infoDe = b;
  b.setAttribute('aria-expanded', 'true');
  infoPoner();
}
function infoCerrar() {
  clearTimeout(infoReloj);
  if (infoDe) infoDe.setAttribute('aria-expanded', 'false');
  infoDe = null;
  infoFijo = false;
  if (infoPop.matches(':popover-open')) infoPop.hidePopover();
}
function infoPoner() {
  if (!infoDe || !infoDe.isConnected) { infoCerrar(); return; }
  const r = infoDe.getBoundingClientRect(), w = infoPop.offsetWidth, h = infoPop.offsetHeight, m = 8;
  const x = Math.max(m, Math.min(r.left - 10, innerWidth - w - m));
  let y = r.bottom + 6;
  if (y + h > innerHeight - m && r.top - 6 - h >= m) y = r.top - 6 - h;
  infoPop.style.left = Math.round(x) + 'px';
  infoPop.style.top = Math.round(y) + 'px';
}
document.addEventListener('click', (e) => {
  const b = e.target.closest && e.target.closest('.info-i');
  if (b) {
    // Solo abre el globo: no cuenta como clic en la tarjeta, la etiqueta o el resumen donde está
    e.preventDefault();
    e.stopPropagation();
    if (infoDe === b && infoFijo) infoCerrar(); else infoAbrir(b, true);
    return;
  }
  if (infoPop.contains(e.target)) { e.preventDefault(); e.stopPropagation(); return; }
  if (infoDe) infoCerrar();
}, true);
document.addEventListener('pointerover', (e) => {
  if (e.pointerType !== 'mouse') return;
  const b = e.target.closest && e.target.closest('.info-i');
  if (b) { if (!(infoFijo && infoDe === b)) { clearTimeout(infoReloj); infoReloj = setTimeout(() => infoAbrir(b, infoFijo && infoDe === b), 150); } return; }
  if (infoPop.contains(e.target)) { clearTimeout(infoReloj); return; }
  if (infoDe && !infoFijo) { clearTimeout(infoReloj); infoReloj = setTimeout(infoCerrar, 200); }
  else clearTimeout(infoReloj);
});
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || !infoDe) return;
  const b = infoDe;
  infoCerrar();
  b.focus();
  e.preventDefault();
  e.stopPropagation();
}, true);
addEventListener('scroll', () => { if (infoDe) infoPoner(); }, true);
addEventListener('resize', () => { if (infoDe) infoPoner(); });
// Si la vista se repinta con el globo abierto (llegan datos del equipo), sigue abierto junto al ⓘ que reemplazó al suyo:
// el que tiene la misma etiqueta, si hay uno solo a la vista; si no, se cierra.
setInterval(() => {
  if (!infoDe || infoDe.isConnected) return;
  const et = infoDe.getAttribute('aria-label'), fijo = infoFijo;
  const otros = [...document.querySelectorAll('.info-i')].filter((x) => x.getAttribute('aria-label') === et && x.getClientRects().length);
  infoCerrar();
  if (otros.length === 1) infoAbrir(otros[0], fijo);
}, 300);

// ---- Estado ------------------------------------------------------------------------------------
const estado = {
  pestanas: [],               // { familia, herr, url (la pedida), ultima (la que muestra), marco, cargador, cargando, usado }
  activa: 'inicio',           // familia activa, o 'inicio'
  pais: leer(LS.pais, 'cl') === 'pe' ? 'pe' : 'cl',
  // abierto: el único grupo desplegado del menú (así cabe sin barra de desplazamiento)
  menu: Object.assign({ abierto: 'ofertar' }, leer(LS.menu, {}) || {}),
  proyectos: [],
  usuario: ''                 // las iniciales de quien trabaja (leerUsuario), o ''
};
delete estado.menu.cerrados;  // de versiones anteriores del portal
delete estado.menu.oculto;
delete estado.menu.modo;      // la franja de íconos (hasta el 2026-10-16)
const familiaDe = (h) => (h && (h.familia || h.id)) || null;
// Las vistas propias del portal (Configuración y conexiones) van en su pestaña, sin marco.
const VISTAS = REG.herramientas.filter((h) => h.tipo === 'vista');
const esVista = (p) => !!p && (HERR.get(p.herr) || {}).tipo === 'vista';

// ---- Proyectos del Formulador (los de este navegador; solo lectura) ------------------------
function reqDe(p) {
  const r = p && p.vinculos && p.vinculos.requerimiento;
  const n = r && typeof r === 'object' ? r.numero : r;
  if (n !== undefined && n !== null && /^\d{1,6}$/.test(String(n))) return String(n);
  return p && /^\d{1,6}$/.test(String(p.codigo || '')) ? String(p.codigo) : null;
}
const tagDe = (p) => texto(((p && p.vinculos && p.vinculos.analisisFinanciero) || {}).tag).toUpperCase() || null;
/* La carpeta del proyecto: { nombre, ruta, biblioteca } o null. Es la de la oferta (vinculos.carpetaOferta del
   Formulador, ruta dentro de «Formulación de proyectos») o, cuando ya se adjudicó y se copió a Gestión de
   Proyectos (v.gestion, 2026-10-19), esa copia, donde sigue la ejecución. */
function carpetaDe(p) {
  const v = p && p.vinculos && p.vinculos.carpetaOferta;
  const ruta = v && Array.isArray(v.ruta) ? v.ruta.map(texto) : [];
  const valida = (n) => !!n && !n.startsWith('.') && !/[\\/:*?"<>|]/.test(n);
  if (!ruta.length || ruta.length > 6 || !ruta.every(valida)) return null;
  const nombre = texto(v.nombre) || ruta[ruta.length - 1];
  if (v.gestion && typeof v.gestion === 'object' && valida(nombre)) return { nombre, ruta: [nombre], biblioteca: 'gestion' };
  return { nombre, ruta, biblioteca: 'formulacion' };
}
function leerProyectos() {
  let datos = null;
  try { datos = JSON.parse(localStorage.getItem(LS_FORMULADOR) || 'null'); } catch (e) { datos = null; }
  const todos = datos && Array.isArray(datos.proyectos) ? datos.proyectos : [];
  const porCodigo = new Map();
  todos.forEach((p) => {
    if (!p || typeof p !== 'object' || !p.uid || p.eliminado) return;
    const codigo = texto(p.codigo) || String(p.uid);
    const version = parseInt(p.version, 10) || 1;
    const modificado = texto(p.modificado);
    const previo = porCodigo.get(codigo);
    if (previo && (previo.version > version || (previo.version === version && previo.modificado >= modificado))) return;
    porCodigo.set(codigo, {
      uid: String(p.uid), codigo, version, modificado,
      titulo: texto(p.titulo), cliente: texto(p.cliente), estado: texto(p.estado),
      req: reqDe(p), tag: tagDe(p), responsable: texto(p.responsable), carpeta: carpetaDe(p)
    });
  });
  return Array.from(porCodigo.values()).sort((a, b) => b.modificado.localeCompare(a.modificado));
}
/* Apodo de cada proyecto (columna «Apodo» del Análisis Financiero, 2026-11-05): «270 - Caldera Valdivia». Se llena al
   leer la carpeta de intercambio (rcArmar); mientras no llega, el nombre de siempre. */
const APODOS = { porReq: new Map(), porTag: new Map() };
function leerApodos(fichas) {
  APODOS.porReq.clear(); APODOS.porTag.clear();
  (fichas || []).forEach((p) => {
    if (!p || !texto(p.tag) || !texto(p.apodo)) return;
    APODOS.porTag.set(texto(p.tag).toUpperCase(), texto(p.apodo));
    if (rcNum(p.req)) APODOS.porReq.set(rcNum(p.req), texto(p.apodo));
  });
}
const apodoDe = (req, tag) => APODOS.porReq.get(rcNum(req)) || APODOS.porTag.get(texto(tag).toUpperCase()) || '';
const nombreProyecto = (p) => {
  const a = apodoDe(p.req, p.tag);
  return a ? (rcNum(p.req) || texto(p.tag).toUpperCase()) + ' - ' + a : p.codigo + (p.titulo ? ' · ' + p.titulo : '');
};

// ---- Usuario (2026-10-16): quién trabaja, con las iniciales del equipo ---------------------------
const usuarioValido = (v) => { const s = texto(v).toUpperCase(); return USUARIOS.includes(s) ? s : ''; };
/* Las iniciales elegidas, o ''. Sin elección guardada, las que el Formulador tenía de antes, si son del
   equipo (quedan guardadas en la clave común, como hace el Formulador). */
function leerUsuario() {
  let v = null;
  try { v = localStorage.getItem(LS.usuario); } catch (e) { v = null; }
  if (v !== null) return usuarioValido(v);
  let previa = '';
  try {
    previa = usuarioValido(localStorage.getItem(LS_FORMULADOR_ANTES[0])) ||
      usuarioValido((JSON.parse(localStorage.getItem(LS_FORMULADOR_ANTES[1]) || 'null') || {}).responsable);
  } catch (e) { previa = ''; }
  if (previa) { try { localStorage.setItem(LS.usuario, previa); } catch (e) { /* solo esta visita */ } }
  return previa;
}
const esMio = (p) => !!estado.usuario && texto(p.responsable).toUpperCase() === estado.usuario;

// ---- Direcciones -------------------------------------------------------------------------------
// Cada ruta del sitio → su herramienta (la más larga primero). Los alias comparten la ruta de otra.
const RUTAS = [];
REG.herramientas.forEach((h) => {
  if (h.tipo !== 'marco' || h.alias) return;
  RUTAS.push({ prefijo: rutaNormal(h.ruta), h, pais: 'cl' });
  if (h.peru) RUTAS.push({ prefijo: rutaNormal(h.peru), h, pais: 'pe' });
});
RUTAS.sort((a, b) => b.prefijo.length - a.prefijo.length);
function herramientaDeUrl(u) {
  if (!u || u.origin !== location.origin) return null;
  const p = rutaNormal(u.pathname);
  // El índice «Herramientas QUEMPIN» de antes (la carpeta de arriba del portal) lo reemplaza el Inicio.
  if (p === RUTA_PORTAL || p.startsWith(RUTA_PORTAL) || p === RUTA_INDICE) return { portal: true };
  for (const r of RUTAS) {
    if (r.h.exacta ? p === r.prefijo : p.startsWith(r.prefijo)) return { h: r.h, pais: r.pais };
  }
  return null;
}
const baseDe = (h) => (estado.pais === 'pe' && h.peru ? h.peru : h.ruta);
/* Sin selector de proyecto (quitado el 2026-11-06, pedido del usuario: «no aporta»): el Formulador, su Seguimiento y
   la Carta Gantt abren en su lista; los tableros, en su vista general. */
function hashProyecto(h) {
  return ['formulador', 'seguimiento', 'gantt'].includes(h.proyecto) ? '#/' : '';
}
function urlDe(h, sub) {
  const hp = hashProyecto(h);
  return baseDe(h) + (hp || (sub ? '#' + encodeURIComponent(sub) : ''));
}

// ---- Menú ----------------------------------------------------------------------------------------
function itemMenu(h) {
  const b = crear('button', 'menu-item');
  b.type = 'button';
  b.dataset.herr = h.id;
  if (h.icono) { const i = crear('span', 'ico'); i.append(icono(h.icono)); b.append(i); }
  b.append(crear('span', 'nom', h.nombre));
  if (h.tipo === 'excel' || h.tipo === 'archivo') b.append(crear('span', 'tipo', 'Excel'));
  if (h.tipo === 'programa') b.append(crear('span', 'tipo', 'Programa'));
  b.addEventListener('click', () => abrir(h.id));
  return b;
}
// Un solo grupo desplegado a la vez: al abrir uno se cierra el anterior.
function pintarGrupos() {
  REG.grupos.forEach((g) => {
    const abierto = estado.menu.abierto === g.id;
    $('#grupo-' + g.id).setAttribute('aria-expanded', abierto ? 'true' : 'false');
    $('#items-' + g.id).hidden = !abierto;
  });
}
function construirMenu() {
  const lista = $('#menuLista');
  lista.textContent = '';
  const arriba = crear('div', 'menu-arriba');
  REG.herramientas.filter((h) => h.grupo === 'arriba').forEach((h) => arriba.append(itemMenu(h)));
  lista.append(arriba, crear('div', 'menu-sep'));
  REG.grupos.forEach((g) => {
    const sec = crear('section');
    const cab = crear('button', 'grupo-cab');
    cab.type = 'button';
    cab.id = 'grupo-' + g.id;
    cab.setAttribute('aria-controls', 'items-' + g.id);
    const i = crear('span', 'ico'); i.append(icono(g.icono));
    const f = crear('span', 'flecha'); f.append(icono('flecha', 14));
    cab.append(i, crear('span', 'nom', g.nombre), f);
    const ul = crear('ul', 'grupo-items');
    ul.id = 'items-' + g.id;
    REG.herramientas.filter((h) => h.grupo === g.id).forEach((h) => { const li = crear('li'); li.append(itemMenu(h)); ul.append(li); });
    cab.addEventListener('click', () => {
      estado.menu.abierto = estado.menu.abierto === g.id ? null : g.id;
      guardar(LS.menu, estado.menu);
      pintarGrupos();
    });
    sec.append(cab, ul);
    lista.append(sec);
  });
  pintarGrupos();
}
const herrActual = () => (estado.activa === 'inicio' ? 'inicio' : ((pestanaDe(estado.activa) || {}).herr || ''));
let marcada = null;   // la herramienta que se marcó la última vez
function marcarMenu() {
  const actual = herrActual();
  document.querySelectorAll('.menu-item').forEach((b) => {
    if (b.dataset.herr === actual) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  // Al cambiar de herramienta se despliega su grupo (si la persona abrió otro a mano, se respeta hasta el próximo cambio).
  const h = HERR.get(actual);
  if (actual !== marcada && h && GRUPO_NOMBRE.has(h.grupo) && estado.menu.abierto !== h.grupo) {
    estado.menu.abierto = h.grupo;
    guardar(LS.menu, estado.menu);
    pintarGrupos();
  }
  marcada = actual;
}
// El menú se despliega encima de la herramienta solo al tocar ☰ (en el computador y en el teléfono).
const menuAbierto = () => portal.classList.contains('menu-abierto');
function mostrarMenu(si, devolverFoco) {
  if (si === menuAbierto()) return;
  portal.classList.toggle('menu-abierto', si);
  $('#velo').hidden = !si;
  $('#btnMenu').setAttribute('aria-expanded', si ? 'true' : 'false');
  if (si) {
    // El foco va a la herramienta abierta (o a la primera), para seguir con el teclado
    const actual = document.querySelector('#menu .menu-item[aria-current="page"]');
    (actual && actual.getClientRects().length ? actual : $('#menu .menu-item')).focus({ preventScroll: true });
  } else if (devolverFoco) {
    $('#btnMenu').focus();
  }
}

// ---- Pestañas y marcos -------------------------------------------------------------------------
const pestanaDe = (familia) => estado.pestanas.find((p) => p.familia === familia) || null;
function ventanaDe(p) {
  try { return p && p.marco && p.marco.contentWindow ? p.marco.contentWindow : null; } catch (e) { return null; }
}
// El nombre corto va en la pestaña; el completo, en su title.
function etiqueta(p, completa) {
  const h = HERR.get(p.herr);
  return h ? (completa ? h.nombre : h.corto || h.nombre) : p.herr;
}
function pintarPestanas() {
  const cont = $('#pestanas');
  cont.textContent = '';
  const filas = [{ familia: 'inicio', inicio: true }].concat(estado.pestanas);
  filas.forEach((p) => {
    const activa = p.familia === estado.activa;
    const w = crear('div', 'pestana' + (activa ? ' activa' : '') + (p.inicio ? ' solo' : ''));
    w.dataset.familia = p.familia;
    const ir = crear('button', 'ir');
    // Inicio va como una casita; cada herramienta, con el ícono de su grupo y su nombre corto
    const i = crear('span', 'ico');
    i.append(icono(p.inicio ? 'inicio' : iconoDe(HERR.get(p.herr)), p.inicio ? 17 : 15));
    ir.append(i, p.inicio ? crear('span', 'sr', 'Inicio') : crear('span', 'txt', etiqueta(p)));
    ir.type = 'button';
    ir.setAttribute('role', 'tab');
    ir.setAttribute('aria-selected', activa ? 'true' : 'false');
    ir.setAttribute('aria-controls', p.inicio ? 'vistaInicio' : esVista(p) ? HERR.get(p.herr).vista : 'marco-' + p.familia);
    ir.title = p.inicio ? 'Inicio' : etiqueta(p, true);
    ir.addEventListener('click', () => activar(p.familia));
    w.setAttribute('role', 'presentation');
    w.append(ir);
    if (!p.inicio) {
      // Una lista de pestañas solo puede tener pestañas (ARIA): la ✕ es para el ratón y con el teclado se
      // cierra con Supr sobre la pestaña (o con «Cerrar esta pestaña» del clic derecho).
      ir.setAttribute('aria-keyshortcuts', 'Delete');
      ir.addEventListener('keydown', (e) => { if (e.key === 'Delete') { e.preventDefault(); cerrar(p.familia); } });
      const x = crear('button', 'x');
      x.type = 'button';
      x.tabIndex = -1;
      x.setAttribute('aria-hidden', 'true');
      x.title = 'Cerrar (Supr)';
      x.append(icono('cerrar', 13));
      x.addEventListener('click', () => cerrar(p.familia));
      w.append(x);
    }
    cont.append(w);
    if (activa) requestAnimationFrame(() => w.scrollIntoView({ block: 'nearest', inline: 'nearest' }));
  });
  const p = pestanaDe(estado.activa);
  const h = p && HERR.get(p.herr);
  $('#btnRecargar').hidden = !p || esVista(p);
  $('#btnAparte').hidden = !p || esVista(p);
  $('#pais').hidden = !(h && h.peru);    // solo en los tableros que existen en Chile y en Perú
  pintarDato();
}
const iconoDe = (h) => (h && (h.icono || (REG.grupos.find((g) => g.id === h.grupo) || {}).icono)) || 'documento';
// La fecha de los datos del tablero activo, que el tablero mostraba en su cabecera (oculta dentro del portal)
function pintarDato() {
  const p = pestanaDe(estado.activa);
  let txt = '';
  try {
    const w = ventanaDe(p);
    const e = w && w.document.getElementById('vizGenerated');
    txt = e ? texto(e.textContent).replace(/\s+/g, ' ') : '';
  } catch (err) { txt = ''; }
  if (!/\d/.test(txt)) txt = '';          // «Datos actualizados al —» mientras no se abre con la contraseña
  const el = $('#datoMarco');
  if (el.textContent !== txt) { el.textContent = txt; el.title = txt; }
  el.hidden = !txt;
}
function guardarPestanas() {
  guardar(LS.pestanas, {
    activa: estado.activa,
    pestanas: estado.pestanas.map((p) => ({ familia: p.familia, herr: p.herr, url: p.ultima || p.url }))
  });
}
function crearMarco(p) {
  liberarMarcos(p);
  const h = HERR.get(p.herr);
  const f = document.createElement('iframe');
  f.className = 'marco';
  f.id = 'marco-' + p.familia;
  f.title = h ? h.nombre : 'Herramienta';
  // El Formulador y el Cotizador copian y pegan con el portapapeles.
  f.setAttribute('allow', 'clipboard-read; clipboard-write; fullscreen');
  f.src = p.url;
  f.addEventListener('load', () => alCargar(p, f));
  const c = crear('div', 'cargando', 'Abriendo ' + (h ? h.nombre : 'la herramienta') + '…');
  c.setAttribute('role', 'status');
  p.marco = f; p.cargador = c; p.cargando = true;
  $('#escenario').append(f, c);
}
// Con más de MAX_MARCOS cargados se descarga la que lleva más tiempo sin usarse (su pestaña queda).
function liberarMarcos(nueva) {
  const cargadas = estado.pestanas.filter((p) => p.marco && p !== nueva);
  if (cargadas.length < MAX_MARCOS) return;
  cargadas.filter((p) => p.familia !== estado.activa).sort((a, b) => a.usado - b.usado).slice(0, cargadas.length - MAX_MARCOS + 1)
    .forEach(descargar);
}
function descargar(p) {
  if (!p.marco) return;
  const f = p.marco, c = p.cargador;
  p.marco = null; p.cargador = null; p.cargando = false;
  if (c) c.remove();
  // Navegar a una página vacía antes de quitarlo deja que la herramienta guarde lo pendiente (pagehide).
  try { f.contentWindow.location.replace('about:blank'); } catch (e) { /* nada */ }
  f.classList.add('oculto');
  setTimeout(() => f.remove(), 600);
}
function activar(familia) {
  if (familia !== 'inicio' && !pestanaDe(familia)) familia = 'inicio';
  estado.activa = familia;
  $('#vistaInicio').hidden = familia !== 'inicio';
  VISTAS.forEach((h) => { $('#' + h.vista).hidden = familia !== h.id; });
  let actual = null;
  estado.pestanas.forEach((p) => {
    const es = p.familia === familia;
    if (es) {
      actual = p;
      p.usado = Date.now();
      if (!p.marco && !esVista(p)) crearMarco(p);
    }
    if (p.marco) p.marco.classList.toggle('oculto', !es);
    if (p.cargador) p.cargador.hidden = !es || !p.cargando;
  });
  pintarPestanas();
  marcarMenu();
  usoAnotar(actual ? actual.herr : 'inicio');
  try { history.replaceState(null, '', '#/' + (actual ? actual.herr : '')); } catch (e) { /* nada */ }
  if (familia === 'inicio') pintarInicio();
  if (familia === 'conexiones') pintarConexiones();
  if (familia === 'recorrido') rcAlMostrar();
  if (familia === 'planificacion') plAlMostrar(); else plCerrarPop(false);
  if (familia === 'subir-cc') scAlMostrar();
  if (familia === 'rendiciones') rdAlMostrar();
  if (familia === 'ejecucion') ejAlMostrar();
  if (familia === 'planilla') pqAlMostrar();
  if (familia === 'observaciones') obsAlMostrar();
  guardarPestanas();
}
function cerrar(familia) {
  const i = estado.pestanas.findIndex((p) => p.familia === familia);
  if (i < 0) return;
  const [p] = estado.pestanas.splice(i, 1);
  descargar(p);
  if (estado.activa === familia) {
    const vecina = estado.pestanas[i] || estado.pestanas[i - 1];
    activar(vecina ? vecina.familia : 'inicio');
  } else {
    pintarPestanas();
    guardarPestanas();
  }
}
function navegar(p, url) {
  p.url = url;
  p.ultima = url;
  const w = ventanaDe(p);
  if (!w) { if (p.marco) p.marco.src = url; return; }
  const destino = new URL(url, location.href);
  let actual = null;
  try { actual = new URL(w.location.href); } catch (e) { actual = null; }
  if (actual && actual.origin === destino.origin && actual.pathname === destino.pathname && actual.search === destino.search) {
    // Misma página: solo cambia el #, y la herramienta lo atiende sin recargarse
    // (rutas del Formulador, #tag= del Centro de Costos, #proyecto= del Análisis, pestañas de una calculadora).
    if (actual.hash !== destino.hash) w.location.hash = destino.hash;
    return;
  }
  p.cargando = true;
  if (p.cargador) p.cargador.hidden = p.familia !== estado.activa;
  w.location.href = destino.href;
}
// Clic en un botón de la herramienta cuando ya se pueda (tras la contraseña y su arranque).
function clicCuandoEste(p, selector) {
  const marco = p.marco;
  const hasta = Date.now() + 30000;
  (function intentar() {
    if (!p.marco || p.marco !== marco) return;
    const w = ventanaDe(p);
    let b = null;
    try { b = w && w.document && w.document.readyState !== 'loading' ? w.document.querySelector(selector) : null; } catch (e) { b = null; }
    if (b && !b.hidden && b.getClientRects().length && !bloqueada(w)) { b.click(); return; }
    if (Date.now() < hasta) setTimeout(intentar, 250);
  })();
}
function bloqueada(w) {
  try {
    const g = w.document.getElementById('pwGate');
    return !!(g && !g.hidden && g.getClientRects().length);
  } catch (e) { return false; }
}

// ---- Abrir una herramienta ---------------------------------------------------------------------
// Un Excel de SharePoint, en otra pestaña del navegador (también el de respaldo de la Planilla de Ingreso, que es una vista)
function abrirExcel(h) {
  window.open(h.url, '_blank', 'noopener');
  avisar(h.nombre + (h.tipo === 'vista' ? ' (el Excel de respaldo)' : '') + ' se abrió en otra pestaña del navegador.');
}
function abrir(id, op) {
  op = op || {};
  const h = HERR.get(id);
  if (!h) return;
  cerrarFlotantes();
  mostrarMenu(false);
  if (h.tipo === 'inicio') { activar('inicio'); return; }
  if (h.tipo === 'excel') { usoAnotar(h.id); abrirExcel(h); return; }
  if (h.tipo === 'programa') { usoAnotar(h.id); abrirPrograma(h); return; }
  if (h.tipo === 'archivo') { mostrarInfo(h); return; }
  if (h.tipo === 'ayuda') { $('#dlgAyuda').showModal(); return; }
  if (h.tipo === 'vista') {
    if (!pestanaDe(h.id)) estado.pestanas.push({ familia: h.id, herr: h.id, url: '', ultima: '', marco: null, cargador: null, cargando: false, usado: 0 });
    activar(h.id);
    return;
  }
  const familia = familiaDe(h);
  const url = op.url || urlDe(h, op.pestana);
  let p = pestanaDe(familia);
  const nueva = !p;
  const antes = p ? p.herr : null;
  if (nueva) {
    p = { familia, herr: id, url, ultima: url, marco: null, cargador: null, cargando: false, usado: 0 };
    estado.pestanas.push(p);
  } else {
    p.herr = id;
    // Ya abierta: se queda donde la persona la dejó, salvo que se pida otra cosa (otra vista de la
    // misma página, una pestaña de calculadora, el proyecto recién elegido o el otro país).
    const camino = (u) => new URL(u, location.href).pathname;
    if (op.url || op.pestana || antes !== id || (h.proyecto && url !== p.url) || camino(url) !== camino(p.url)) navegar(p, url);
  }
  activar(familia);
  // «Ingresar datos» y «Análisis Financiero» son la misma página: la pestaña del tablero dice cuál.
  if (h.pestanaTablero && !op.url && (nueva ? h.alias : antes !== id || h.alias)) {
    clicCuandoEste(p, '.viz-tab-btn[data-tab="' + h.pestanaTablero + '"]');
  }
}

// ---- Lo que pasa dentro de cada herramienta ----------------------------------------------------
function alCargar(p, f) {
  if (p.marco !== f) return;
  p.cargando = false;
  if (p.cargador) p.cargador.hidden = true;
  const w = ventanaDe(p);
  let u = null;
  try { u = w ? new URL(w.location.href) : null; } catch (e) { u = null; }   // otro sitio: no se puede mirar
  if (!u || u.href === 'about:blank') return;
  p.ultima = u.pathname + u.search + u.hash;
  const d = herramientaDeUrl(u);
  if (d && d.portal) { cerrar(p.familia); activar('inicio'); return; }
  if (d && d.h && familiaDe(d.h) !== p.familia && !pestanaDe(familiaDe(d.h))) {
    // La herramienta se fue a otra por su cuenta (el selector de calculadora, un menú propio): la pestaña la sigue.
    const eraActiva = estado.activa === p.familia;
    p.familia = familiaDe(d.h);
    p.herr = d.h.id;
    f.id = 'marco-' + p.familia;
    if (eraActiva) estado.activa = p.familia;
  } else if (d && d.h && familiaDe(d.h) === p.familia && d.h.ruta !== (HERR.get(p.herr) || {}).ruta) {
    // Otra página de la misma familia (de Hidrógeno a Otros gases): la pestaña muestra cuál es.
    p.herr = d.h.id;
  }
  estilarMarco(p);
  const hp = HERR.get(p.herr);
  if (d && d.h && d.h.peru && hp && hp.peru && d.pais !== estado.pais) {
    // Se cambió de país desde el selector del propio tablero: el portal lo recuerda para los próximos.
    estado.pais = d.pais;
    $('#pais').value = d.pais;
    guardar(LS.pais, d.pais);
  }
  f.title = (HERR.get(p.herr) || {}).nombre || f.title;
  enganchar(p, w);
  adAlCargar(p, w);
  if (p.familia === estado.activa) {
    try { history.replaceState(null, '', '#/' + p.herr); } catch (e) { /* nada */ }
  }
  pintarPestanas();
  marcarMenu();
  guardarPestanas();
}
// Destino de un enlace hecho en una herramienta: null si se queda en ella (o es de otro sitio).
function destinoDeEnlace(href, w, p) {
  if (!href || typeof href !== 'string') return null;     // window.open('') de los reportes PDF del Análisis
  let u;
  try { u = new URL(href, w.location.href); } catch (e) { return null; }
  if (!/^https?:$/.test(u.protocol)) return null;
  const d = herramientaDeUrl(u);
  if (!d) return null;
  if (d.portal) return { id: 'inicio' };
  if (familiaDe(d.h) === p.familia) return null;
  return { id: d.h.id, url: u.pathname + u.search + u.hash };
}
function enganchar(p, w) {
  let doc = null;
  try { doc = w.document; } catch (e) { return; }
  if (!doc || doc.__portalQuempin) return;
  doc.__portalQuempin = true;
  doc.addEventListener('click', (e) => {
    cerrarFlotantes();
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
    if (!a || a.hasAttribute('download')) return;
    const destino = destinoDeEnlace(a.href, w, p);
    if (!destino) return;
    e.preventDefault();
    e.stopPropagation();
    abrir(destino.id, destino.url ? { url: destino.url } : {});
  }, true);
  doc.addEventListener('keydown', teclas, true);
  doc.addEventListener('contextmenu', (e) => ctxDesdeEvento(e, p));
  // Sus errores de JavaScript llegan solos a «Errores y observaciones» (2026-11-18, sección «Errores sin aviso»).
  // Los de antes de engancharse (mientras carga) no se ven.
  const alError = (e) => { try { erTomar(window.__qpnErrores.leer(e), p.herr, w); } catch (z) { /* nunca otro error */ } };
  w.addEventListener('error', alError);
  w.addEventListener('unhandledrejection', alError);
  // Lo que muestra (la ruta del Formulador, el proyecto de un tablero) se recuerda para la próxima visita.
  w.addEventListener('hashchange', () => {
    try { p.ultima = w.location.pathname + w.location.search + w.location.hash; } catch (e) { return; }
    guardarPestanas();
  });
  // Las herramientas que abren otra con window.open (el Formulador al pasar a ejecución) también quedan aquí.
  try {
    const original = w.open;
    w.open = function (url) {
      const destino = destinoDeEnlace(url, w, p);
      if (destino) { abrir(destino.id, destino.url ? { url: destino.url } : {}); return null; }
      return original.apply(w, arguments);
    };
  } catch (e) { /* nada */ }
}

function refrescarProyectos() {
  estado.proyectos = leerProyectos();
  if (estado.activa === 'inicio') pintarInicio();
  pintarPestanas();
}

// ---- Al día sin F5 (2026-11-18) -------------------------------------------------------------------------------------
/* Pedido del usuario: que el equipo vea lo nuevo sin apretar F5. Cada AD_REVISAR_SEG, y al volver a la pestaña, el
   Portal pregunta al sitio si cambió su propia página o la de una herramienta abierta (la página y sus scripts y hojas
   de estilo del mismo sitio). GitHub Pages cambia el ETag de todos los archivos en cada publicación, así que un ETag
   distinto solo hace bajar el archivo, y lo que decide es su contenido (SHA-256). Sin ETag (el sitio de las pruebas) se
   compara siempre el contenido.
   Lo nuevo se carga solo cuando no se pierde nada: una herramienta escondida o la ventana en otra pestaña, al tiro; lo
   que está a la vista, después de AD_QUIETO_SEG sin tocarlo. Nunca con un diálogo abierto, un campo con el foco o algo
   del Portal por guardar. Mientras espera, un aviso con «Actualizar».
   Los datos del equipo ya llegan solos en Planificación, Ejecución y Requerimientos; el Inicio y el Recorrido se
   releen cada AD_DATOS_SEG mientras se miran. */
const AD_REVISAR_SEG = 300;
const AD_QUIETO_SEG = 600;
const AD_DATOS_SEG = 120;
const ad = { portal: null, toque: Date.now(), revisando: false, revisado: 0, avisado: new Set() };
const adTocar = () => { ad.toque = Date.now(); };
['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart', 'input'].forEach((t) =>
  document.addEventListener(t, adTocar, { capture: true, passive: true }));
async function adHash(texto) {
  const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(texto));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, '0')).join('');
}
const adMarca = (r) => r.headers.get('etag') || r.headers.get('last-modified') || '';
// La huella de cómo está cada archivo ahora. modo 'force-cache' para la base (la copia que se acaba de cargar).
async function adLeer(url, modo, antes) {
  const r = await fetch(url, { cache: modo, credentials: 'same-origin' });
  if (!r.ok) throw new Error(url + ': ' + r.status);
  const marca = adMarca(r);
  if (antes && marca && marca === antes.marca) { try { r.body && r.body.cancel(); } catch (e) { /* nada */ } return antes; }
  return { marca, hash: await adHash(await r.text()), lm: r.headers.get('last-modified') || '' };
}
// Los archivos de una página que valen: ella misma y sus scripts y hojas de estilo del mismo sitio.
function adArchivos(doc, url) {
  const urls = new Set([url.split('#')[0]]);
  try {
    doc.querySelectorAll('script[src], link[rel="stylesheet"][href]').forEach((el) => {
      const u = new URL(el.src || el.href, doc.baseURI);
      if (u.origin === location.origin) urls.add(u.href.split('#')[0]);
    });
  } catch (e) { /* nada */ }
  return [...urls];
}
// La base de una página: cómo estaba cada archivo al cargarla. Si el servidor ya tiene otra publicación que la cargada
// (Last-Modified distinto al de la página), queda como «nueva» de entrada.
async function adBase(doc, url) {
  const base = { archivos: new Map(), nueva: false };
  for (const u of adArchivos(doc, url)) {
    try { base.archivos.set(u, await adLeer(u, 'force-cache')); } catch (e) { /* no se vigila ese */ }
  }
  const pag = base.archivos.get(url.split('#')[0]);
  const cargada = Date.parse(doc.lastModified), servida = pag && pag.lm ? Date.parse(pag.lm) : NaN;
  if (!isNaN(cargada) && !isNaN(servida) && Math.abs(servida - cargada) > 2000 && servida > cargada) base.nueva = true;
  return base;
}
async function adCambio(base) {
  if (!base) return false;
  if (base.nueva) return true;
  for (const [u, antes] of base.archivos) {
    let ahora;
    try { ahora = await adLeer(u, 'no-cache', antes); } catch (e) { continue; }
    if (ahora.hash !== antes.hash) { base.nueva = true; return true; }
    base.archivos.set(u, ahora);    // otra publicación, el mismo contenido: la próxima vez basta el ETag
  }
  return false;
}
// Algo que se perdería al recargar: un diálogo abierto, un campo con el foco, lo del Portal por guardar.
function adOcupado(doc) {
  try {
    if ([...doc.querySelectorAll('dialog[open], [role="dialog"]')].some((d) => d.getClientRects().length)) return true;
    const a = doc.activeElement;
    if (a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))) return true;
  } catch (e) { return true; }
  return false;
}
function adPortalOcupado() {
  if (adOcupado(document)) return true;
  if (planif.porGuardar.size || planif.guardando || ej.porGuardar || ej.guardando) return true;
  try { if (localStorage.getItem(LS_PL_PENDIENTE) || localStorage.getItem(LS_EJ_PENDIENTE)) return true; } catch (e) { /* nada */ }
  return false;
}
const adQuieto = () => document.visibilityState === 'hidden' || Date.now() - ad.toque > AD_QUIETO_SEG * 1000;
function adAvisar(clave, msg, ir) {
  if (ad.avisado.has(clave) || document.visibilityState !== 'visible') return;
  ad.avisado.add(clave);
  avisar(msg, { texto: 'Actualizar', ir });
}
function adRecargarMarco(p) {
  const w = ventanaDe(p);
  if (!w) return;
  ad.avisado.delete('marco:' + p.familia);
  p.ad = null;
  p.cargando = true;
  if (p.cargador) p.cargador.hidden = p.familia !== estado.activa;
  try { w.location.reload(); } catch (e) { p.marco.src = p.ultima || p.url; }
}
// Al cargar una herramienta (alCargar), su base.
function adAlCargar(p, w) {
  p.ad = null;
  let doc = null, url = '';
  try { doc = w.document; url = w.location.href; } catch (e) { return; }
  if (!doc || !/^https?:/.test(url)) return;
  ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart', 'input'].forEach((t) =>
    doc.addEventListener(t, () => { adTocar(); p.adToque = Date.now(); }, { capture: true, passive: true }));
  p.adToque = Date.now();
  const marco = p.marco;
  adBase(doc, url).then((b) => { if (p.marco === marco) p.ad = b; });
}
async function adRevisar() {
  if (ad.revisando || !navigator.onLine) return;
  ad.revisando = true;
  ad.revisado = Date.now();
  try {
    if (!ad.portal) ad.portal = await adBase(document, location.href);
    else if (await adCambio(ad.portal)) {
      if (adQuieto() && !adPortalOcupado()) { location.reload(); return; }
      adAvisar('portal', 'Hay una versión nueva del Portal.', () => { if (!adPortalOcupado() || confirm('Hay algo sin guardar o abierto. ¿Actualizar igual?')) location.reload(); });
    }
    for (const p of estado.pestanas.slice()) {
      if (!p.ad || !p.marco) continue;
      const marco = p.marco;
      if (!(await adCambio(p.ad)) || p.marco !== marco) continue;
      const w = ventanaDe(p);
      let doc = null;
      try { doc = w && w.document; } catch (e) { doc = null; }
      if (!doc) continue;
      const aLaVista = p.familia === estado.activa && document.visibilityState === 'visible';
      const quieta = !aLaVista || Date.now() - Math.max(p.adToque || 0, ad.toque) > AD_QUIETO_SEG * 1000;
      if (quieta && !adOcupado(doc)) adRecargarMarco(p);
      else if (aLaVista) adAvisar('marco:' + p.familia, 'Hay una versión nueva de «' + etiqueta(p, true) + '».', () => adRecargarMarco(p));
    }
  } finally { ad.revisando = false; }
}
// Los datos del equipo en el Inicio y el Recorrido, mientras se miran
function adDatos() {
  if (document.visibilityState !== 'visible' || rc.leyendo || !rc.dir || !rc.leido) return;
  if (estado.activa !== 'inicio' && estado.activa !== 'recorrido') return;
  if (document.querySelector('dialog[open]')) return;
  if (Date.now() - rc.leido > AD_DATOS_SEG * 1000) rcCargar();
}
function adIniciar() {
  adRevisar();
  setInterval(() => { if (Date.now() - ad.revisado >= AD_REVISAR_SEG * 1000) adRevisar(); }, 30000);
  setInterval(adDatos, 30000);
  document.addEventListener('visibilitychange', () => {
    // Al irse a otra pestaña, lo que ya se sabe nuevo se carga sin que se note; al volver, se pregunta si pasó más de un minuto.
    if (document.visibilityState === 'hidden') {
      if (ad.portal && ad.portal.nueva) { setTimeout(() => { if (document.visibilityState === 'hidden' && !adPortalOcupado()) location.reload(); }, 3000); }
      return;
    }
    if (Date.now() - ad.revisado > 60000) adRevisar();
  });
}

// ---- Usuario elegido (2026-10-16) ---------------------------------------------------------------
// Una vez por navegador. Lo usa el Formulador (responsable de lo que se crea, autor en el Control de
// Documentos, «Mis proyectos») y aquí el selector de proyectos, que muestra primero los suyos.
function pintarUsuario() {
  const u = estado.usuario;
  const b = $('#btnUsuario');
  $('#usuarioActual').textContent = u || '¿Quién eres?';
  b.classList.toggle('sin', !u);
  b.setAttribute('aria-label', u ? 'Usuario: ' + u + '. Cambiar' : 'Elegir tu usuario');
  b.title = u ? 'Trabajas como ' + u + ': lo que formules o registres queda a tu nombre' : 'Elige tus iniciales: lo que formules o registres queda a tu nombre';
}
let usuarioRecien = false;
function abrirUsuario() {
  cerrarFlotantes();
  usuarioRecien = true;
  setTimeout(() => { usuarioRecien = false; }, 0);
  const ul = $('#listaUsuarios');
  ul.textContent = '';
  USUARIOS.forEach((ini) => {
    const li = crear('li');
    const b = crear('button', 'usr-op', ini);
    b.type = 'button';
    b.dataset.usuario = ini;
    b.setAttribute('role', 'option');
    b.setAttribute('aria-selected', ini === estado.usuario ? 'true' : 'false');
    const n = estado.proyectos.filter((p) => texto(p.responsable).toUpperCase() === ini).length;
    b.title = ini + (n ? ' · ' + n + (n === 1 ? ' proyecto a su cargo' : ' proyectos a su cargo') : '');
    b.addEventListener('click', () => elegirUsuario(ini));
    li.append(b);
    ul.append(li);
  });
  $('#sinUsuario').setAttribute('aria-selected', estado.usuario ? 'false' : 'true');
  $('#popUsuario').hidden = false;
  $('#btnUsuario').setAttribute('aria-expanded', 'true');
  const actual = ul.querySelector('[aria-selected="true"]') || ul.querySelector('.usr-op');
  if (actual) actual.focus();
}
function cerrarUsuario(devolverFoco) {
  const pop = $('#popUsuario');
  if (pop.hidden) return;
  pop.hidden = true;
  $('#btnUsuario').setAttribute('aria-expanded', 'false');
  if (devolverFoco) $('#btnUsuario').focus();
}
function elegirUsuario(ini) {
  const nuevo = usuarioValido(ini);
  const cambia = nuevo !== estado.usuario;
  estado.usuario = nuevo;
  // Las iniciales tal cual (no JSON): así las lee el Formulador. Las herramientas abiertas aquí dentro
  // se enteran solas (evento storage del mismo sitio).
  try { localStorage.setItem(LS.usuario, nuevo); } catch (e) { /* solo esta visita */ }
  cerrarUsuario(false);
  pintarUsuario();
  rcAlCambiarUsuario();
  if (cxArmada && !$('#vistaConexiones').hidden) pintarEstadoConexiones();
  if (cambia) avisar(nuevo ? 'Trabajas como ' + nuevo + ': lo que formules o registres queda a tu nombre.' : 'Sin usuario: lo que hagas no queda a nombre de nadie.');
}

// ---- Sistema QUEMPIN (QUEMPIN.exe) ---------------------------------------------------------------
// El navegador no ejecuta programas, pero sí abre direcciones de un protocolo que Windows conoce:
// QUEMPIN.exe se anota como dueño de quempin:// cada vez que se abre (Sistema QUEMPIN 1.3.8,
// app/protocolo.py) y abre la sección que dice la dirección. Si ya está abierto, se trae al frente.
function abrirEnlace(url) {
  const a = crear('a');
  a.href = url;
  a.hidden = true;
  document.body.append(a);
  a.click();
  a.remove();
}
function abrirPrograma(h) {
  abrirEnlace(h.enlace);
  avisar('Abriendo Sistema QUEMPIN…', { texto: '¿No se abrió?', ir: () => mostrarInfo(h) });
}

// ---- Carpeta del proyecto (2026-10-19) -------------------------------------------------------------
// Pedido del usuario: abrir la carpeta del proyecto en el Explorador de archivos del computador. QUEMPIN.exe
// 1.3.10 atiende quempin://carpeta/<biblioteca>/<ruta> sin abrir su ventana y, si la carpeta se movió (a
// Adjudicadas), la busca por su nombre en las dos bibliotecas (Sistema QUEMPIN app/carpetas.py).
const NOMBRE_BIBLIOTECA = { formulacion: 'Formulación de proyectos', gestion: 'Gestión de Proyectos' };
const enlaceCarpeta = (c) => 'quempin://carpeta/' + c.biblioteca + '/' + c.ruta.map(encodeURIComponent).join('/');
function infoCarpeta(c) {
  $('#dlgInfoTit').textContent = 'Si la carpeta no se abrió';
  $('#dlgInfoTxt').textContent = 'El botón le pide a QUEMPIN.exe que abra la carpeta en el Explorador de archivos de este computador. Necesita la versión 1.3.10 o más nueva, abierta una vez desde su carpeta, y la biblioteca sincronizada en OneDrive. Si el navegador pregunta, marca «Permitir siempre» y elige «Abrir». La carpeta es:';
  $('#dlgInfoDonde').textContent = [NOMBRE_BIBLIOTECA[c.biblioteca]].concat(c.ruta).join(' › ');
  $('#dlgInfoDonde').hidden = false;
  $('#dlgInfoDesc').textContent = 'Si la movieron de lugar, el programa la busca por su nombre en Formulación de proyectos y en Gestión de Proyectos.';
  $('#dlgInfo').showModal();
}

// ---- Diálogos ------------------------------------------------------------------------------------
function mostrarInfo(h) {
  $('#dlgInfoTit').textContent = h.tipo === 'programa' ? 'Si Sistema QUEMPIN no se abrió' : h.nombre;
  if (h.tipo === 'programa') {
    $('#dlgInfoTxt').textContent = 'El botón abre QUEMPIN.exe en ' + h.accion + '. Para que funcione en este computador, abre el programa una vez desde su carpeta (o su acceso directo), versión 1.3.8 o más nueva. Si el navegador pregunta, marca «Permitir siempre» y elige «Abrir».';
    $('#dlgInfoDonde').textContent = 'Cotizaciones y OC - Documentos › QUEMPIN.exe';
    $('#dlgInfoDonde').hidden = false;
  } else {
    $('#dlgInfoTxt').textContent = 'Es un Excel compartido del equipo. Está en:';
    $('#dlgInfoDonde').textContent = h.donde || '';
    $('#dlgInfoDonde').hidden = !h.donde;
  }
  $('#dlgInfoDesc').textContent = h.desc || '';
  $('#dlgInfo').showModal();
}
