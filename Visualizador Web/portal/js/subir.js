/* Portal QUEMPIN — Subir documentos al Centro de Costos (sc*).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Subir documentos al Centro de Costos (2026-10-23) --------------------------------------------------------
// Los archivos se escriben en la carpeta de intercambio («buzon/adjuntos/<id>/») y después el mensaje «documento-cc»;
// el procesador los copia a «Facturas y Boletas/<país>/<carpeta>/» del Centro de Costos (Sistema Intercambio/
// documentos_cc.py), donde /Registro_Centro_de_Costos los encuentra como cualquier documento pendiente.
const SC_EXT = /\.(pdf|png|jpe?g|heic)$/i;
const SC_MAX = 25 * 1024 * 1024;
const SC_PROHIBIDO = /[\\/:*?"<>|]/g;
const SC_ARCHIVO_MSG = /_documento-cc_([A-Za-z0-9_-]{6,64})\.json$/;
const sc = {
  pais: estado.pais === 'pe' ? 'PE' : 'CL', carpetas: null, eleccion: null, archivos: [], q: '',
  enviando: false, envios: [], leyendo: null, leido: 0, propuesto: false
};
const scTam = (b) => (b < 1024 * 1024 ? Math.max(1, Math.round(b / 1024)) + ' KB' : (b / 1024 / 1024).toFixed(1).replace('.', ',') + ' MB');
// Un nombre que sirve como archivo o carpeta en Windows y en SharePoint
const scLimpio = (s, max) => String(s || '').normalize('NFC').replace(SC_PROHIBIDO, '-').replace(/\s+/g, ' ').replace(/^[.\s]+/, '').trim().slice(0, max);
function scAhora() {
  const d = new Date();
  const z = -d.getTimezoneOffset();
  const p = (n) => String(Math.floor(Math.abs(n))).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + 'T' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' +
    p(d.getSeconds()) + (z >= 0 ? '+' : '-') + p(z / 60) + ':' + p(z % 60);
}
function scId() {
  const b = new Uint8Array(12);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
}
async function scSha(datos) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', datos)), (x) => x.toString(16).padStart(2, '0')).join('');
}

// ---- Leer: las carpetas del Centro de Costos y los envíos recientes ----------------------------------------------
function scAlMostrar() {
  if (!rc.leyendo && (!rc.dir || !rc.leido || Date.now() - rc.leido > RC_RELEER_SEG * 1000)) rcCargar();   // al terminar llama a scAlRecorrido
  else if (rc.dir) scCargar();
  scPintar();
}
function scAlRecorrido() {
  if ($('#vistaSubir').hidden) return;
  if (rc.dir) scCargar(); else scPintar();
}
function scCargar() {
  if (sc.leyendo) return sc.leyendo;
  const dir = rc.dir;
  if (!dir) return Promise.resolve();
  sc.leyendo = (async () => {
    const pub = await rcJson(await rcSub(dir, 'publicado'), 'centro-costos-carpetas.json');
    sc.carpetas = pub && pub.datos && pub.datos.paises ? pub.datos.paises : null;
    sc.envios = await scLeerEnvios(dir);
    sc.leido = Date.now();
  })().catch((e) => { console.error(e); }).then(() => {
    sc.leyendo = null;
    scPintar();
  });
  return sc.leyendo;
}
async function scLeerEnvios(dir) {
  const salida = [];
  const leer = async (carpeta, enCamino) => {
    if (!carpeta) return;
    try {
      for await (const [n, h] of carpeta.entries()) {
        if (h.kind !== 'file' || !SC_ARCHIVO_MSG.test(n)) continue;
        let m;
        try { m = JSON.parse(rcSinBom(await (await h.getFile()).text())); } catch (e) { continue; }
        if (!m || m.tipo !== 'documento-cc' || !Array.isArray(m.archivos)) continue;
        const r = m.resultado || {};
        salida.push({
          id: texto(m.id), enviado: texto(m.origen && m.origen.enviado), usuario: texto(m.origen && m.origen.usuario),
          carpeta: texto(m.carpeta), pais: texto(m.pais), n: m.archivos.length,
          estado: enCamino ? 'camino' : r.estado === 'aplicado' ? 'aplicado' : 'rechazado',
          detalle: Array.isArray(r.detalle) ? r.detalle.map(texto) : [],
          repetidos: Array.isArray(r.archivos) ? r.archivos.filter((a) => a && a.repetido).length : 0
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
  return salida.sort((a, b) => b.enviado.localeCompare(a.enviado)).filter((e) => !vistos.has(e.id) && vistos.add(e.id)).slice(0, 15);
}

// ---- Las opciones de proyecto: las carpetas que existen, y los proyectos en ejecución que todavía no tienen ---------
function scOpciones() {
  const carpetas = (sc.carpetas && Array.isArray(sc.carpetas[sc.pais]) ? sc.carpetas[sc.pais] : [])
    .filter((c) => c && texto(c.nombre)).map((c) => ({ carpeta: texto(c.nombre), req: texto(c.req) || null, documentos: +c.documentos || 0 }));
  const conCarpeta = new Set(carpetas.map((c) => c.req).filter(Boolean));
  const nuevas = [];
  if (sc.pais === 'CL') {
    (rc.tarjetas || []).forEach((t) => {
      if (t.etapa !== 'ejecucion' || t.antiguo || !t.req || conCarpeta.has(String(t.req))) return;
      const nombre = scLimpio(t.req + '. ' + (t.titulo || t.tag || 'Proyecto'), 120);
      nuevas.push({ carpeta: nombre, req: String(t.req), titulo: t.titulo || '', nueva: true });
    });
  }
  return { carpetas, nuevas };
}
function scElegir(op) {
  sc.eleccion = Object.assign({ pais: sc.pais }, op);
  sc.q = '';
  $('#scBuscar').value = '';
  scPintar();
  $('#scCambiar').focus();
}

// ---- Los archivos ------------------------------------------------------------------------------------------
function scAgregar(lista) {
  const malos = [];
  Array.from(lista || []).forEach((f) => {
    if (!SC_EXT.test(f.name)) { malos.push(f.name + ' (no es PDF ni imagen)'); return; }
    if (!f.size) { malos.push(f.name + ' (está vacío)'); return; }
    if (f.size > SC_MAX) { malos.push(f.name + ' (más de 25 MB)'); return; }
    if (sc.archivos.some((a) => a.file.name === f.name && a.file.size === f.size && a.file.lastModified === f.lastModified)) return;
    sc.archivos.push({ file: f });
  });
  scNombrar();
  scPintar();
  if (malos.length) avisar('No se agregó: ' + malos.join('; ') + '.');
}
// El nombre con que viaja cada archivo: limpio y sin repetirse dentro del envío.
function scNombrar() {
  const usados = new Set();
  sc.archivos.forEach((a) => {
    const m = a.file.name.match(/^(.*?)(\.[^.]+)$/);
    const base = scLimpio(m ? m[1] : a.file.name, 120) || 'documento';
    const ext = m ? m[2] : '.pdf';
    let nombre = base + ext;
    for (let n = 2; usados.has(nombre.toLowerCase()); n++) nombre = base + ' (' + n + ')' + ext;
    usados.add(nombre.toLowerCase());
    a.nombre = nombre;
  });
}

// ---- Enviar -------------------------------------------------------------------------------------------------
async function scEnviar(ev) {
  if (ev) ev.preventDefault();
  const e = sc.eleccion;
  if (sc.enviando || !e || !sc.archivos.length || !rc.dir) return;
  sc.enviando = true;
  scPintarEnviar();
  const id = scId();
  try {
    const buzon = await rc.dir.getDirectoryHandle('buzon', { create: true });
    const adjuntos = await (await buzon.getDirectoryHandle('adjuntos', { create: true })).getDirectoryHandle(id, { create: true });
    const archivos = [];
    for (const a of sc.archivos) {
      const datos = await a.file.arrayBuffer();
      const h = await adjuntos.getFileHandle(a.nombre, { create: true });
      const w = await h.createWritable();
      await w.write(datos);
      await w.close();
      archivos.push({ nombre: a.nombre, bytes: datos.byteLength, sha256: await scSha(datos) });
    }
    // El mensaje va al final: el procesador no lo ve hasta que los archivos están escritos.
    const enviado = scAhora();
    const origen = { herramienta: 'portal', enviado };
    if (estado.usuario) origen.usuario = estado.usuario;
    const msg = { esquema: 'quempin.intercambio/1', id, tipo: 'documento-cc', destino: 'centro-costos', origen, pais: e.pais, carpeta: e.carpeta, archivos };
    if (e.nueva) msg.nueva = true;
    if (e.req) msg.proyecto = e.titulo ? { req: e.req, titulo: e.titulo } : { req: e.req };
    const nota = $('#scNota').value.trim();
    if (nota) msg.nota = nota;
    const nombre = enviado.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_documento-cc_' + id + '.json';
    const h = await buzon.getFileHandle(nombre, { create: true });
    const w = await h.createWritable();
    await w.write(JSON.stringify(msg, null, 1));
    await w.close();
    sc.envios.unshift({ id, enviado, usuario: estado.usuario || '', carpeta: e.carpeta, pais: e.pais, n: archivos.length, estado: 'camino', detalle: [], repetidos: 0 });
    avisar(pl(archivos.length, 'documento enviado', 'documentos enviados') + ' a «' + e.carpeta + '». Llegan al Centro de Costos en la próxima vuelta del procesador.');
    sc.archivos = [];
    $('#scNota').value = '';
    if (e.nueva) e.nueva = false;      // la próxima vez la carpeta ya existe (o viene en camino)
  } catch (err) {
    console.error(err);
    avisar('No se pudo subir: ' + (err && err.name === 'NotAllowedError' ? 'falta el permiso para escribir en la carpeta del equipo.' : 'revisa que OneDrive esté funcionando y vuelve a intentarlo.'));
  } finally {
    sc.enviando = false;
    scPintar();
  }
}

// ---- Pintar -----------------------------------------------------------------------------------------------
function scPintar() {
  const hay = !!rc.dir;
  $('#scLeyendo').hidden = hay || !rc.leyendo;
  $('#scContenido').hidden = !hay;
  $('#scVacio').hidden = hay || !!rc.leyendo || !rc.sinDatos;
  if (!hay && !rc.leyendo && rc.sinDatos) {
    pintarSinCarpeta($('#scVacio'), rc.sinDatos, {
      navegador: 'Los documentos viajan por la carpeta del equipo, y este navegador no puede abrir carpetas del computador.',
      conectar: 'Los documentos viajan por la carpeta de intercambio. Conecta una vez la biblioteca «' + BIBLIOTECA_FORMULACION + '» en este navegador (la misma conexión del Formulador) y acepta «Ver y editar archivos».'
    });
  }
  scPintarFrescura();
  if (!hay) return;
  scPintarProyecto();
  scPintarArchivos();
  scPintarEnviar();
  scPintarEnvios();
}
function scPintarFrescura() {
  const txt = $('#scFrescura');
  const punto = $('#scPunto');
  if (rc.leyendo || sc.leyendo) { txt.textContent = 'Leyendo la carpeta del equipo…'; return; }
  const l = rc.pulso;
  if (!rc.dir || !l) { txt.textContent = rc.dir ? 'Carpeta del equipo conectada' : 'Sin la carpeta del equipo'; punto.className = 'cx-punto'; return; }
  const min = l.minutos;
  const hace = min === null ? '' : min < 1 ? 'hace un momento' : min < 60 ? 'hace ' + min + ' min' : min < 48 * 60 ? 'hace ' + Math.round(min / 60) + ' h' : 'hace ' + Math.round(min / 1440) + ' días';
  txt.textContent = l.detenido ? 'Procesador detenido desde ' + hace : 'Última vuelta del procesador ' + hace;
  txt.title = l.texto + ' El procesador deja los documentos en el Centro de Costos cada 5 minutos.';
  punto.className = 'cx-punto ' + l.nivel;
}
function scPintarProyecto() {
  const e = sc.eleccion;
  $('#scElegido').hidden = !e;
  $('#scElegir').hidden = !!e;
  if (e) {
    $('#scElegidoNom').textContent = e.carpeta;
    $('#scElegidoMeta').textContent = (e.pais === 'PE' ? 'Perú' : 'Chile') + ' · ' +
      (e.nueva ? 'carpeta nueva: el procesador la crea en Facturas y Boletas' : pl(e.documentos || 0, 'documento', 'documentos') + ' en la carpeta');
    return;
  }
  document.querySelectorAll('.sc-pais button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.pais === sc.pais)));
  const lista = $('#scLista');
  lista.textContent = '';
  const { carpetas, nuevas } = scOpciones();
  const q = norm(sc.q).trim().split(/\s+/).filter(Boolean);
  const pasa = (o) => q.every((x) => norm(o.carpeta).includes(x));
  const op = (o, meta, clase) => {
    const b = crear('button', 'sc-op' + (clase ? ' ' + clase : ''));
    b.type = 'button';
    b.setAttribute('role', 'option');
    b.append(crear('span', null, o.carpeta), crear('span', 'sc-op-meta', meta));
    b.addEventListener('click', () => scElegir(o));
    lista.append(b);
  };
  const c1 = carpetas.filter(pasa);
  const c2 = nuevas.filter(pasa);
  c1.forEach((o) => op(o, pl(o.documentos, 'documento', 'documentos')));
  if (c2.length) {
    lista.append(crear('div', 'sc-grupo', 'En ejecución, sin carpeta todavía'));
    c2.forEach((o) => op(o, 'carpeta nueva', 'nueva'));
  }
  const libre = scLimpio(sc.q, 120);
  const existe = libre && carpetas.concat(nuevas).some((o) => norm(o.carpeta) === norm(libre));
  if (libre && !existe) op({ carpeta: libre, req: (libre.match(/^(\d{1,4})\s*[.\-_)]/) || [])[1] || null, nueva: true }, '+ crear carpeta', 'nueva');
  if (!lista.children.length) lista.append(crear('div', 'sc-grupo', q.length ? 'Ninguna carpeta coincide' : 'Escribe el nombre de la carpeta'));
  const nota = $('#scNotaLista');
  nota.hidden = !!sc.carpetas;
  nota.textContent = 'La lista de carpetas del Centro de Costos llega con la próxima vuelta del procesador. Mientras, puedes escribir el nombre exacto de la carpeta.';
}
function scPintarArchivos() {
  const ul = $('#scArchivos');
  ul.textContent = '';
  sc.archivos.forEach((a, i) => {
    const li = crear('li');
    const x = crear('button', 'sc-quitar');
    x.type = 'button';
    x.title = 'Quitar ' + a.nombre;
    x.setAttribute('aria-label', 'Quitar ' + a.nombre);
    x.append(icono('cerrar', 16));
    x.addEventListener('click', () => { sc.archivos.splice(i, 1); scNombrar(); scPintar(); });
    const nom = crear('span', 'sc-arch-nom', a.nombre);
    nom.title = a.nombre;
    li.append(icono('documento', 18), nom, crear('span', 'sc-arch-tam', scTam(a.file.size)), x);
    ul.append(li);
  });
}
function scPintarEnviar() {
  const b = $('#scEnviar');
  const n = sc.archivos.length;
  b.disabled = sc.enviando || !sc.eleccion || !n;
  b.classList.toggle('enviando', sc.enviando);
  b.textContent = sc.enviando ? 'Subiendo…' : n ? 'Subir ' + pl(n, 'documento', 'documentos') : 'Subir documentos';
  const total = sc.archivos.reduce((s, a) => s + a.file.size, 0);
  $('#scResumen').textContent = !sc.eleccion ? 'Elige primero el proyecto.' : !n ? 'Agrega uno o más documentos.'
    : pl(n, 'documento', 'documentos') + ' (' + scTam(total) + ') para «' + sc.eleccion.carpeta + '».';
}
function scPintarEnvios() {
  const ul = $('#scEnvios');
  ul.textContent = '';
  if (!sc.envios.length) { ul.append(crear('li', 'sc-env-det', sc.leyendo ? 'Leyendo…' : 'Todavía no hay envíos desde el portal.')); return; }
  const NIVEL = { camino: ['warn', 'En camino'], aplicado: ['ok', 'En el Centro de Costos'], rechazado: ['bad', 'No se pudo'] };
  sc.envios.forEach((e) => {
    const li = crear('li');
    const cab = crear('div', 'sc-env-cab');
    const [nivel, txt] = NIVEL[e.estado];
    const pill = crear('span', 'sc-pill', txt);
    pill.dataset.nivel = nivel;
    cab.append(crear('span', 'sc-env-nom', e.carpeta), pill);
    const fecha = e.enviado ? new Date(e.enviado) : null;
    const cuando = fecha && !isNaN(fecha) ? fecha.toLocaleString('es-CL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
    li.append(cab, crear('span', 'sc-env-det', [pl(e.n, 'documento', 'documentos'), e.usuario, cuando, e.pais === 'PE' ? 'Perú' : ''].filter(Boolean).join(' · ')));
    if (e.estado === 'rechazado' && e.detalle.length) li.append(crear('span', 'sc-env-det mal', e.detalle[0]));
    if (e.estado === 'aplicado' && e.repetidos) li.append(crear('span', 'sc-env-det', pl(e.repetidos, 'ya estaba', 'ya estaban') + ' en la carpeta: no se duplicó.'));
    ul.append(li);
  });
}
