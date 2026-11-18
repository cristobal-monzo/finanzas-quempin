/* Portal QUEMPIN — Tema claro u oscuro y lo que el Portal esconde de cada herramienta.
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Tema ----------------------------------------------------------------------------------------
function oscuroAhora() {
  const t = document.documentElement.getAttribute('data-theme');
  return t === 'dark' || (t !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);
}
function pintarTema() {
  const oscuro = oscuroAhora();
  const b = $('#btnTema');
  const txt = oscuro ? 'Modo claro' : 'Modo oscuro';
  b.textContent = '';
  b.append(icono(oscuro ? 'sol' : 'luna', 20));
  b.title = txt;
  b.setAttribute('aria-label', txt);
}
// Las claves de tema de cada herramienta: el botón del portal las deja iguales, así también
// quedan así cuando se abren aparte.
const CLAVES_TEMA = Array.from(new Set(REG.herramientas.map((h) => h.tema).filter(Boolean)));

// ---- Las herramientas dentro del portal ----------------------------------------------------------
// Dentro del portal cada herramienta no repite lo que el portal ya muestra: su logo y su nombre
// (están en la cabecera y en la pestaña), el menú hacia las demás herramientas y su botón de modo
// oscuro (el del portal vale para todas). Se marca <html data-en-portal="tablero|calculadora|
// formulador"> y se le agrega esta hoja; sus pestañas internas, sus datos y sus pies quedan iguales.
// Abiertas aparte, en su dirección de siempre, se ven como siempre. Los selectores los revisa
// tests/portal/ contra el código de cada herramienta.
const ESTILO_INCRUSTADO = [
  // Tableros y calculadoras: la cabecera entera (logo, título, país, tableros, modo oscuro). La
  // fecha de los datos pasa a la barra de pestañas del portal y el país, a su selector.
  // La Carta Gantt (2026-10-20) también: dentro de ella, «Todas las cartas» lleva a su lista.
  'html[data-en-portal="tablero"] .viz-header, html[data-en-portal="calculadora"] .viz-header, html[data-en-portal="gantt"] .viz-header { display: none !important; }',
  // El aire que dejaba la cabecera sobre el contenido del tablero
  'html[data-en-portal="tablero"] .viz-root { padding-top: 20px; }',
  // Formulador: queda su barra de secciones (Proyectos, el proyecto abierto, Guía) y Configuración,
  // en una barra clara y baja en vez del cromo negro.
  'html[data-en-portal="formulador"] .viz-header .viz-logo, html[data-en-portal="formulador"] .viz-header .viz-titleblock,' +
    ' html[data-en-portal="formulador"] #herrBtn, html[data-en-portal="formulador"] #themeToggle, html[data-en-portal="formulador"] #usuarioBtn { display: none !important; }',
  'html[data-en-portal="formulador"] .viz-header { display: flex; align-items: flex-end; gap: 8px; padding: 0 !important;' +
    ' margin-bottom: 18px; background: var(--surface-1); color: var(--text-primary); border-bottom: 1px solid var(--gridline); }',
  'html[data-en-portal="formulador"] .viz-header > .viz-modnav { order: 1; flex: 1 1 auto; min-width: 0; margin: 0; padding: 6px 0 0; border: 0; }',
  'html[data-en-portal="formulador"] .viz-header > .viz-container { order: 2; flex: 0 0 auto; max-width: none; margin: 0; padding: 4px 16px 6px 0; }',
  'html[data-en-portal="formulador"] .viz-modnav-tab { color: var(--text-secondary); }',
  'html[data-en-portal="formulador"] a.viz-modnav-tab:hover { color: var(--text-primary); background: var(--gridline); }',
  'html[data-en-portal="formulador"] .viz-modnav-tab.is-active { color: var(--text-primary); }',
  'html[data-en-portal="formulador"] .viz-header .viz-theme-toggle { color: var(--text-primary); background: transparent; border-color: var(--gridline); }',
  'html[data-en-portal="formulador"] .viz-header .viz-theme-toggle:hover { background: var(--gridline); }'
].join('\n');
function estilarMarco(p) {
  let doc = null;
  try { const w = ventanaDe(p); doc = w && w.document; } catch (e) { return; }
  const raiz = doc && doc.documentElement;
  if (!raiz || doc.URL === 'about:blank') return;
  // El mismo modo claro/oscuro que el portal (se repasa: la herramienta aplica el suyo al cargar)
  const tema = oscuroAhora() ? 'dark' : 'light';
  if (raiz.getAttribute('data-theme') !== tema) raiz.setAttribute('data-theme', tema);
  if (raiz.hasAttribute('data-en-portal')) return;
  let d = null;
  try { d = herramientaDeUrl(new URL(doc.URL)); } catch (e) { d = null; }
  const tipo = (d && d.h && d.h.incrustar) || '';
  raiz.setAttribute('data-en-portal', tipo);
  if (!tipo) return;
  const s = doc.createElement('style');
  s.id = 'portal-quempin-incrustado';
  s.textContent = ESTILO_INCRUSTADO;
  (doc.head || raiz).appendChild(s);
}
function estilarTodos() { estado.pestanas.forEach((p) => { if (p.marco) estilarMarco(p); }); }
