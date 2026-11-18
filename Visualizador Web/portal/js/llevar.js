/* Portal QUEMPIN — Llevar la cotización del Cotizador Histórico a un proyecto (ll*).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- La cotización del Cotizador Histórico, a un proyecto (2026-10-29) -----------------------------------------------
/* Pedido del usuario: que el carrito del Cotizador Histórico exporte sus costos a un proyecto específico en formulación o
   en ejecución. El carrito manda sus líneas (mensaje 'quempin-cotizacion', desde su marco aquí dentro o, abierto suelto,
   desde la pestaña que abrió este Portal) y aquí se elige el proyecto: los que el Recorrido pone en Ejecución y los que
   tienen formulación antes de ofertar, en la moneda de la cotización.
   - En ejecución, cada línea queda como gasto por decidir y simulado en «Proyectos en ejecución» (ejPoner: se deshace con
     el aviso), con el proveedor de la compra y la hoja del Cotizador con que se compara. No llega al Centro de Costos.
   - En formulación, el Formulador abre el proyecto en esa tabla de costos con su «Pegar desde Excel» y las filas ya
     pegadas (mensaje 'quempin-pegar-costos'): ahí se elige la partida y se agregan.
   La cotización no se guarda en el navegador (el carrito no se guarda, a propósito): vive en ll.datos mientras se elige. */
const LL_CATS = EJ_CATS.filter((c) => c.k !== 'Mano de Obra');
const LL_LISTA = { Materiales: 'materiales', Equipos: 'equipos', Otros: 'otros' };      // sus tablas en el Formulador
/* La categoría del Análisis Financiero de cada categoría del Centro de Costos, para proponer la de la cotización: la tabla
   MAPEO_CATEGORIA_BUCKET de analisis_financiero.py (tests/portal/ vigila que no se separen); lo demás va a «Otros». */
const LL_BUCKET = {
  materiales: 'Materiales', consumibles: 'Materiales', ferreteria: 'Materiales', 'reposicion de material': 'Materiales',
  'equipos-herramientas': 'Equipos', herramientas: 'Equipos', arriendo: 'Equipos'
};
const LL_ESPERA_FORMULADOR = 180000;     // lo que se espera al Formulador: su contraseña, la carpeta del equipo
const ll = { datos: null, clave: null, propuesto: false, cat: 'Materiales', q: '' };

// Lo que manda el carrito, validado: viene de otra página, así que solo entra lo que tiene la forma acordada
function llLeer(d) {
  if (!d || typeof d !== 'object' || d.v !== 1 || !Array.isArray(d.filas) || !['CLP', 'PEN'].includes(d.moneda)) return null;
  const num = (v, max) => (typeof v === 'number' && isFinite(v) && v >= 0 && v < max ? v : null);
  const filas = [];
  d.filas.slice(0, 500).forEach((f) => {
    if (!f || typeof f !== 'object') return;
    const descripcion = ejTxt(f.descripcion, 200), cantidad = num(f.cantidad, 1e7), costo = num(f.costoUnitario, 1e12);
    if (!descripcion || !(cantidad > 0) || costo === null) return;
    filas.push({
      descripcion, cantidad, costo, unidad: ejTxt(f.unidad, 12) || 'Un.', proveedor: ejTxt(f.proveedor, 120),
      ref: texto(f.ref).length <= 80 ? ejTxt(f.ref, 80) : '', categoria: ejTxt(f.categoria, 60),
      compra: /^\d{4}-\d{2}-\d{2}$/.test(texto(f.compra)) ? texto(f.compra) : '', nRef: ejTxt(f.nRef, 40)
    });
  });
  return filas.length ? { moneda: d.moneda, uf: num(d.uf, 1e7) || null, ufFecha: ejTxt(d.ufFecha, 30).split(' ')[0], filas } : null;
}
const llMonto = (n, moneda) => (moneda === 'PEN' ? 'S/ ' + n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : ejPesos(n));
const llTotal = (d) => d.filas.reduce((a, f) => a + f.cantidad * f.costo, 0);
const llDia = (iso) => iso.split('-').reverse().join('-');
// La categoría con más plata entre las de sus compras; sin ninguna dicha, Materiales
function llCategoria(d) {
  const por = new Map();
  d.filas.forEach((f) => {
    if (!f.categoria) return;
    const c = LL_BUCKET[norm(f.categoria).trim()] || 'Otros';
    por.set(c, (por.get(c) || 0) + f.cantidad * f.costo);
  });
  return [...por.entries()].sort((a, b) => b[1] - a[1]).map((x) => x[0])[0] || 'Materiales';
}
// Los que pueden recibirla. «Proyectos en ejecución» lleva sus cuentas en pesos, y el Formulador no convierte monedas.
function llDestinos(moneda) {
  // Los de Gestión que ya terminaron o no tienen N° ni TAG se ven en «Proyectos en ejecución», pero no reciben compras
  const ejec = moneda === 'CLP' ? ejTarjetas('ejecucion').filter((t) => t.etapa === 'ejecucion' && ejClave(t)).sort(ejOrden) : [];
  const form = rc.tarjetas.filter((t) => t.formulacion && RC_ANTES_DE_OFERTAR.includes(t.etapa) && !t.antiguo
    && ejMoneda(ejFormulacion(t)) === moneda).sort((a, b) => (rcMia(b) - rcMia(a)) || rcOrden(a, b));
  return { ejec, form };
}
const llElegida = () => {
  if (!ll.datos || !ll.clave) return null;
  const d = llDestinos(ll.datos.moneda);
  return d.ejec.concat(d.form).find((t) => t.clave === ll.clave) || null;
};
const llNombre = (t) => (t.req ? 'N° ' + t.req : t.tag || (t.formulacion ? t.formulacion.codigo : t.titulo));
// El único proyecto que puede recibirla, si hay uno solo
function llPropuesto(dest) {
  const todos = dest.ejec.concat(dest.form);
  return todos.length === 1 ? todos[0].clave : null;
}

function llAbrir(datos) {
  const d = llLeer(datos);
  if (!d) { avisar('La cotización llegó vacía o incompleta: vuelve a usar «Llevar a un proyecto…» en el Cotizador.'); return; }
  Object.assign(ll, { datos: d, clave: null, propuesto: false, cat: llCategoria(d), q: '' });
  $('#llBuscar').value = '';
  if (!rc.leyendo && (!rc.leido || Date.now() - rc.leido > RC_RELEER_SEG * 1000)) rcCargar();   // al terminar, llAlRecorrido
  llPintar();
  const dlg = $('#dlgLlevar');
  if (!dlg.open) dlg.showModal();
  (rc.leido ? $('#llBuscar') : $('#llX')).focus();
}
function llAlRecorrido() { if ($('#dlgLlevar').open) llPintar(); }
function llPintar() {
  const d = ll.datos;
  if (!d) return;
  const n = d.filas.length;
  $('#llResumen').textContent = pl(n, 'línea', 'líneas') + ' por ' + llMonto(llTotal(d), d.moneda) + ' sin IVA, '
    + (d.moneda === 'PEN' ? 'en soles.' : 'con lo que QUEMPIN pagó actualizado por UF' + (d.ufFecha ? ' (la del ' + d.ufFecha + ').' : '.'));
  $('#llLineasSum').textContent = n === 1 ? 'Ver la línea' : 'Ver las ' + n + ' líneas';
  const tb = $('#llLineas');
  tb.textContent = '';
  d.filas.forEach((f) => {
    const tr = crear('tr');
    tr.append(crear('td', null, f.descripcion), crear('td', 'ej-num', ejCantidad(f.cantidad) + ' ' + f.unidad),
      crear('td', 'ej-num', llMonto(f.costo, d.moneda)), crear('td', 'ej-num', llMonto(f.costo * f.cantidad, d.moneda)));
    tb.append(tr);
  });
  const cats = $('#llCat');
  cats.textContent = '';
  LL_CATS.forEach((c) => {
    const b = crear('button', 'pl-vista', c.nombre);
    b.type = 'button';
    b.dataset.cat = c.k;
    b.setAttribute('role', 'radio');
    b.addEventListener('click', () => { ll.cat = c.k; llPintarCat(); llPintarPie(); });
    cats.append(b);
  });
  llPintarCat();
  llPintarLista();
  llPintarPie();
}
function llPintarCat() {
  document.querySelectorAll('#llCat .pl-vista').forEach((b) => {
    const si = b.dataset.cat === ll.cat ? 'true' : 'false';
    b.setAttribute('aria-pressed', si);
    b.setAttribute('aria-checked', si);
  });
}
function llPintarLista() {
  const d = ll.datos, box = $('#llLista'), vacio = $('#llVacio');
  box.textContent = '';
  const hay = rc.leido > 0;
  box.hidden = !hay;
  $('#llBuscarCampo').hidden = !hay;
  vacio.hidden = hay;
  if (!hay) {
    if (rc.sinDatos) {
      pintarSinCarpeta(vacio, rc.sinDatos, {
        navegador: 'Los proyectos del equipo se leen de su carpeta, y este navegador no puede abrir carpetas del computador.',
        conectar: 'Los proyectos del equipo y sus costos están en la carpeta de intercambio. Conecta una vez la biblioteca «' + BIBLIOTECA_FORMULACION + '» en este navegador (la misma conexión del Formulador) y acepta «Ver archivos» y «Guardar cambios».'
      });
    } else {
      vacio.textContent = '';
      vacio.append(crear('p', null, 'Leyendo los proyectos de la carpeta del equipo…'));
    }
    return;
  }
  const dest = llDestinos(d.moneda);
  if (!ll.propuesto) { ll.clave = llPropuesto(dest); ll.propuesto = true; }
  const q = norm(ll.q).trim().split(/\s+/).filter(Boolean);
  const fila = (t, enEjecucion) => {
    const b = crear('button', 'pop-item ll-item');
    b.type = 'button';
    b.dataset.clave = t.clave;
    b.setAttribute('aria-pressed', t.clave === ll.clave ? 'true' : 'false');
    b.append(crear('span', 't', llNombre(t) + ' · ' + t.titulo));
    const f = t.formulacion;
    const sub = enEjecucion
      ? [t.af ? 'Avance ' + Math.round((t.avance || 0) * 100) + ' %' : 'Sin ficha en el Análisis Financiero', t.lugar, t.responsable]
      : [t.req || t.tag ? f.codigo + (f.version > 1 ? ' v' + f.version : '') : '', f.estado, t.lugar, t.responsable];   // sin N°, el código ya es su nombre
    b.append(crear('span', 's', sub.filter(Boolean).join(' · ')));
    b.addEventListener('click', () => {
      ll.clave = t.clave;
      box.querySelectorAll('.ll-item').forEach((x) => x.setAttribute('aria-pressed', x === b ? 'true' : 'false'));
      llPintarPie();
    });
    return b;
  };
  const grupo = (titulo, nota, lista, sinNinguno, enEjecucion) => {
    const sec = crear('section', 'll-grupo');
    sec.append(crear('h3', 'pop-grupo', titulo), crear('p', 'll-nota', nota));
    const vistos = lista.filter((t) => q.every((x) => t.buscar.includes(x)));
    vistos.forEach((t) => sec.append(fila(t, enEjecucion)));
    if (!vistos.length) sec.append(crear('p', 'll-nada', lista.length ? 'Ninguno coincide con la búsqueda.' : sinNinguno));
    box.append(sec);
  };
  grupo('En ejecución', 'Quedan como gastos por decidir, simulados: se ve cómo terminaría el proyecto. No llegan al Centro de Costos.', dest.ejec,
    d.moneda === 'CLP' ? 'No hay proyectos en ejecución.' : 'Los proyectos en ejecución llevan sus cuentas en pesos chilenos, y esta cotización está en soles.', true);
  grupo('En formulación', 'Van a sus costos en el Formulador: ahí eliges la partida y las agregas.', dest.form,
    'No hay proyectos con formulación en ' + (d.moneda === 'PEN' ? 'soles' : 'pesos') + ' antes de ofertar.', false);
}
function llPintarPie() {
  const t = llElegida(), b = $('#llLlevar'), pista = $('#llPista');
  b.disabled = !t || !rc.dir;
  b.textContent = t ? 'Llevar a ' + llNombre(t) : 'Llevar';
  const cat = ((EJ_CAT.get(ll.cat) || {}).nombre || ll.cat).toLowerCase();
  pista.textContent = !t ? (rc.leido ? 'Elige el proyecto.' : '')
    : t.etapa === 'ejecucion' ? 'Quedan en ' + cat + ' de ' + llNombre(t) + ', en «Proyectos en ejecución», por decidir y simuladas. Ahí se aprueban, se descartan o se marcan compradas.'
      : 'Se abre ' + t.formulacion.codigo + ' en el Formulador, en ' + cat + ', con las filas listas para agregar: eliges la partida y confirmas.';
}
async function llLlevar(e) {
  e.preventDefault();
  const d = ll.datos, t = llElegida(), cat = ll.cat;
  if (!d || !t || !rc.dir) return;
  $('#dlgLlevar').close();
  if (t.etapa === 'ejecucion') await llAEjecucion(t, cat, d); else llAFormulacion(t, cat, d);
}
async function llAEjecucion(t, cat, d) {
  // Lo anotado en este navegador se lee antes (el resumen se pinta con todo), y las reglas del Formulador, para proponer
  // la línea del presupuesto que reemplaza cada una
  if (!ej.datos.leida) await ejCargar(true);
  await ejLib('calc');
  const form = ejFormulacion(t);
  const lineas = ejLineas(form, ejCalculo(form));
  const proyecto = ejClave(t), hoy = plISO(new Date());
  const items = d.filas.map((f) => ({
    id: ejNuevoId('c'), proyecto, tipo: 'costo', descripcion: f.descripcion, categoria: cat, cantidad: f.cantidad, unidad: f.unidad,
    precio: f.costo, proveedor: f.proveedor, cotizacion: '', fecha: hoy, estado: 'evaluar', simular: true, grupo: '', oc: '',
    linea: (ejLineaSugerida(f.descripcion, cat, lineas) || {}).uid || '', ref: f.ref,
    nota: ejTxt('Del Cotizador Histórico: lo pagado' + (f.compra ? ' el ' + llDia(f.compra) : '') + (f.nRef ? ' (N° Ref. ' + f.nRef + ')' : '')
      + (d.uf ? ', actualizado por UF' : '') + '.', 300)
  }));
  ejAbrirProyecto(t.clave);
  ejPoner(items, pl(items.length, 'gasto', 'gastos') + ' del Cotizador Histórico en ' + llNombre(t) + ', por decidir y simulados: arriba se ve cómo cambia el proyecto.');
}
function llAFormulacion(t, cat, d) {
  const h = HERR.get('formulador');
  const lista = LL_LISTA[cat], uid = t.formulacion.uid;
  abrir('formulador', { url: h.ruta + '#/p/' + encodeURIComponent(uid) + '/' + lista });
  const p = pestanaDe(familiaDe(h));
  if (!p) return;
  // Las filas como las copia «Copiar para el Formulador» del carrito: las lee el mismo «Pegar desde Excel»
  const filas = d.filas.map((f) => [f.descripcion.replace(/[\t\r\n]+/g, ' '), f.unidad, f.cantidad, f.costo].join('\t'));
  llEntregar(p, {
    tipo: 'quempin-pegar-costos', proyecto: uid, lista,
    texto: ['Descripción\tUnidad\tCantidad\tCosto unitario neto'].concat(filas).join('\n'),
    origen: 'Costos del Cotizador Histórico' + (d.moneda === 'PEN' ? ', en soles.' : ': lo que QUEMPIN pagó, actualizado por UF' + (d.ufFecha ? ' (la del ' + d.ufFecha + ').' : '.'))
  });
  avisar('Se abre ' + t.formulacion.codigo + ' en el Formulador: elige la partida y agrega las filas.');
}
// El Formulador recibe las filas cuando ya muestra ese proyecto en esa tabla (tras su contraseña y la carpeta del equipo)
function llEntregar(p, msg) {
  const marco = p.marco;
  const hasta = Date.now() + LL_ESPERA_FORMULADOR;
  (function intentar() {
    if (!p.marco || p.marco !== marco) return;         // se cerró su pestaña
    const w = ventanaDe(p);
    let listo = false;
    try {
      listo = !!w && w.document.readyState !== 'loading' && !bloqueada(w) && !w.document.querySelector('dialog[open]')
        && w.location.hash.startsWith('#/p/' + encodeURIComponent(msg.proyecto) + '/' + msg.lista)
        && !!w.document.querySelector('[data-act="pegar-filas"][data-list="' + msg.lista + '"]');
    } catch (e) { listo = false; }
    if (listo) { w.postMessage(msg, location.origin); return; }
    if (Date.now() < hasta) setTimeout(intentar, 300);
    else avisar('El Formulador no alcanzó a abrir el proyecto. Cuando lo muestre, vuelve a usar «Llevar a un proyecto…» en el Cotizador.');
  })();
}
