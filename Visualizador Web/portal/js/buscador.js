/* Portal QUEMPIN — Buscador (Ctrl K).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Buscador ------------------------------------------------------------------------------------
const GRUPO_NOMBRE = new Map(REG.grupos.map((g) => [g.id, g.nombre]));
let resultados = [];
let elegido = -1;
function indiceBusqueda() {
  const items = [];
  REG.herramientas.forEach((h) => {
    if (h.grupo === 'oculto' || h.tipo === 'inicio' || iniApagada(h)) return;
    const tipo = h.tipo === 'excel' || h.tipo === 'archivo' ? 'Excel' : h.tipo === 'programa' ? 'Programa' : h.grupo === 'calcular' ? 'Cálculo' : '';
    items.push({
      titulo: h.nombre, sub: GRUPO_NOMBRE.get(h.grupo) || 'Portal', tipo, calc: h.grupo === 'calcular',
      texto: norm([h.nombre, h.claves, h.desc, GRUPO_NOMBRE.get(h.grupo)].join(' ')),
      ir: () => abrir(h.id)
    });
    (h.pestanas || []).forEach((s) => items.push({
      titulo: h.nombre + ' › ' + s.nombre, sub: 'Calculadora', tipo: 'Cálculo', calc: true,
      texto: norm([s.nombre, h.nombre, h.claves].join(' ')),
      ir: () => abrir(h.id, { pestana: s.id })
    }));
  });
  // Los proyectos del Recorrido (si ya se leyó la carpeta del equipo): llevan a su detalle
  const porUid = new Map();
  rc.tarjetas.forEach((t) => {
    const it = {
      titulo: (rcEtiqueta(t) ? rcEtiqueta(t) + ' · ' : '') + t.titulo,
      sub: ['Recorrido', (RC_ETAPAS.find((e) => e.id === t.etapa) || {}).titulo, t.accion.corto, t.responsable && (rcMia(t) ? 'tuyo' : 'a cargo de ' + t.responsable)].filter(Boolean).join(' · '),
      tipo: 'Etapa', texto: t.buscar + ' recorrido etapa',
      ir: () => { abrir('recorrido'); rcVerDetalle(t.clave); },
      accesos: accesosDeTarjeta(t)
    };
    if (t.formulacion && t.formulacion.uid) porUid.set(String(t.formulacion.uid), it);
    items.push(it);
  });
  /* Los proyectos del Formulador de este navegador. Si el Recorrido ya tiene ese proyecto, va en su resultado (con lo
     que se busca de los dos), no repetido. */
  estado.proyectos.forEach((p) => {
    const txt = norm([p.codigo, p.titulo, p.cliente, p.req, p.req ? 'n' + p.req : '', p.tag, p.responsable, 'proyecto'].join(' '));
    const ya = porUid.get(String(p.uid));
    if (ya) { ya.texto += ' ' + txt; return; }
    const seguimiento = () => abrir('formulador', { url: baseDe(HERR.get('formulador')) + '#/p/' + encodeURIComponent(p.uid) + '/seguimiento' });
    items.push({
      titulo: nombreProyecto(p), sub: [esMio(p) ? 'Tu proyecto' : 'Proyecto', p.cliente, p.req ? 'N° ' + p.req : '', p.responsable && !esMio(p) ? 'a cargo de ' + p.responsable : ''].filter(Boolean).join(' · '), tipo: 'Proyecto',
      texto: txt, ir: seguimiento,
      accesos: [{ nombre: 'Formulador', ir: () => rcIr(RC_IR.ficha(p.uid)) }]
        .concat(RC_EN_FORMULACION.includes(texto(p.estado) || 'Borrador') ? [] : [{ nombre: 'Seguimiento', ir: seguimiento }])
    });
  });
  return items;
}
/* Los botones de un proyecto reconocido, según la etapa en que va (2026-11-12, pedido del usuario): su Formulador si
   tiene formulación (antes de ofertar, sin ella, por su N° para formularlo); su Seguimiento desde la oferta en adelante; «En ejecución» si está en obra o su carpeta sigue en
   Gestión de Proyectos. */
function accesosDeTarjeta(t) {
  const out = [];
  const uid = t.formulacion && t.formulacion.uid;
  const i = RC_ETAPAS.findIndex((e) => e.id === t.etapa);
  const desdeOferta = i >= RC_ETAPAS.findIndex((e) => e.id === 'oferta');
  if (uid) out.push({ nombre: 'Formulador', ir: () => rcIr(RC_IR.ficha(uid)) });
  else if (t.req && !desdeOferta) out.push({ nombre: 'Formulador', ir: () => rcIr(RC_IR.req(t.req)) });   // para formularlo
  if (uid && desdeOferta) out.push({ nombre: 'Seguimiento', ir: () => rcIr(RC_IR.seguimiento(uid)) });
  if (t.etapa === 'ejecucion' || t.gestion || t.entregado) out.push({ nombre: 'En ejecución', ir: () => rcIr(RC_IR.ejecucion(t.clave)) });
  return out;
}
function buscar(q) {
  const t = norm(q).trim().split(/\s+/).filter(Boolean);
  if (!t.length) return [];
  return indiceBusqueda()
    .filter((it) => t.every((x) => it.texto.includes(x)))
    .map((it) => ({ it, peso: norm(it.titulo).startsWith(t[0]) ? 0 : norm(it.titulo).includes(t[0]) ? 1 : 2 }))
    .sort((a, b) => a.peso - b.peso)
    .slice(0, 10)
    .map((x) => x.it);
}
function pintarResultados() {
  const q = $('#buscar').value;
  const caja = $('#resultados');
  caja.textContent = '';
  if (!q.trim()) { caja.hidden = true; $('#buscar').setAttribute('aria-expanded', 'false'); $('#buscar').removeAttribute('aria-activedescendant'); return; }
  resultados = buscar(q);
  if (elegido >= resultados.length) elegido = resultados.length - 1;
  resultados.forEach((r, i) => {
    const b = crear('button', 'res');
    b.type = 'button';
    b.id = 'res-' + i;
    b.tabIndex = -1;
    b.setAttribute('role', 'option');
    b.setAttribute('aria-selected', i === elegido ? 'true' : 'false');
    const t = crear('span', 'res-txt');
    t.append(crear('span', 'res-tit', r.titulo), crear('span', 'res-sub', r.sub));
    b.append(t);
    if (r.tipo) b.append(crear('span', 'chip' + (r.calc ? ' es-calc' : ''), r.tipo));
    b.addEventListener('mousedown', (e) => e.preventDefault());   // el campo no pierde el foco antes del clic
    b.addEventListener('click', () => irA(i));
    if (!r.accesos || !r.accesos.length) { caja.append(b); return; }
    // Un proyecto reconocido: la fila lleva además sus botones (no van dentro del botón: no se anidan)
    const fila = crear('div', 'res-fila');
    fila.setAttribute('role', 'presentation');
    const acc = crear('div', 'res-acc');
    acc.setAttribute('aria-hidden', 'true');   // atajos del ratón (fuera del Tab): un listbox solo lleva opciones
    r.accesos.forEach((a) => {
      const x = crear('button', 'res-ir', a.nombre);
      x.type = 'button';
      x.tabIndex = -1;
      x.title = 'Abrir ' + (a.nombre === 'En ejecución' ? 'su página en Proyectos en ejecución' : 'su ' + a.nombre);
      x.addEventListener('mousedown', (e) => e.preventDefault());
      x.addEventListener('click', () => { cerrarBusqueda(); a.ir(); });
      acc.append(x);
    });
    fila.append(b, acc);
    caja.append(fila);
  });
  if (!resultados.length) caja.append(crear('p', 'res-vacio', 'Nada calza con «' + q.trim() + '».'));
  caja.hidden = false;
  $('#buscar').setAttribute('aria-expanded', 'true');
  if (elegido >= 0) $('#buscar').setAttribute('aria-activedescendant', 'res-' + elegido);
  else $('#buscar').removeAttribute('aria-activedescendant');
}
function irA(i) {
  const r = resultados[i];
  if (!r) return;
  cerrarBusqueda();
  r.ir();
}
function cerrarBusqueda() {
  $('#buscar').value = '';
  elegido = -1;
  pintarResultados();
  if (MOVIL.matches) mostrarBuscadorMovil(false);
}
function mostrarBuscadorMovil(si) {
  portal.classList.toggle('buscando', si);
  $('#btnBuscar').setAttribute('aria-expanded', si ? 'true' : 'false');
}
function enfocarBuscador() {
  if (MOVIL.matches) mostrarBuscadorMovil(true);
  window.focus();
  $('#buscar').focus();
  $('#buscar').select();
}

function cerrarFlotantes() {
  cerrarUsuario(false);
  plCerrarPop(false);
  if (!$('#resultados').hidden && document.activeElement !== $('#buscar')) cerrarBusqueda();
}
// Atajos de teclado, también con el foco dentro de una herramienta.
function teclas(e) {
  if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === 'k' || e.key === 'K')) {
    e.preventDefault();
    enfocarBuscador();
    return;
  }
  // Ctrl Z en la Planificación semanal deshace el último cambio (fuera de un campo de texto)
  if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === 'z' || e.key === 'Z') && !$('#vistaPlan').hidden &&
      !(e.target && e.target.closest && e.target.closest('input[type="text"], input[type="search"], textarea')) && !document.querySelector('dialog[open]')) {
    e.preventDefault();
    plDeshacer();
    return;
  }
  // Lo mismo en «Proyectos en ejecución»
  if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && (e.key === 'z' || e.key === 'Z') && !$('#vistaEjecucion').hidden &&
      !(e.target && e.target.closest && e.target.closest('input[type="text"], input[type="search"], input[type="number"], input[type="date"], textarea')) && !document.querySelector('dialog[open]')) {
    e.preventDefault();
    ejDeshacer();
    return;
  }
  if (e.key === 'Escape') {
    if ($('#menuCtx').open || $('#dlgObs').open) return;     // lo cierra el navegador: son modales
    // En la ventanita, Escape primero sale de «Cambiar»; después la cierra
    if (!$('#plPop').hidden) {
      e.preventDefault();
      if (planif.pop && planif.pop.cambiar) { planif.pop.cambiar = null; plPintarPop(true); } else plCerrarPop(true);
      return;
    }
    if (!$('#popUsuario').hidden) { e.preventDefault(); cerrarUsuario(true); return; }
    if (menuAbierto()) { e.preventDefault(); mostrarMenu(false, true); return; }
    if (!$('#resultados').hidden || portal.classList.contains('buscando')) { e.preventDefault(); cerrarBusqueda(); }
  }
}
