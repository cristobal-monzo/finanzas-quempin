/* ingreso.js — Lógica de la pestaña «Ingresar datos» del tablero de Análisis Financiero
 * (pedido del usuario, 2026-10-02): los valores manuales de la hoja «Proyectos» se
 * ingresan aquí y viajan al Excel como mensajes «datos-proyecto» por el buzón de la
 * carpeta de Intercambio. Quien los aplica es Análisis Financiero
 * (Sistema/presupuestos_formulador.py), con su regla de siempre: escribe una celda vacía
 * o una que todavía tiene lo que la persona vio aquí («reemplaza»); si no, el envío queda
 * pendiente. Este archivo nunca decide eso: solo arma el mensaje.
 *
 * build_visualizador.py lo inserta en el tablero. Lo que depende de los datos (qué campos
 * hay, de qué tipo, qué falta a cada proyecto) llega calculado en el snapshot
 * (DATA.ingreso); aquí solo vive lo que depende de lo que se teclea. Funciona también en
 * Node: tests/test_ingreso_js.py arma mensajes con él y los valida contra el catálogo y
 * contra las reglas de Python.
 *
 * Carpeta: misma API de acceso a archivos que el Formulador (Chrome y Edge de escritorio)
 * y el mismo registro en IndexedDB («qpn-intercambio»). Los dos tableros comparten origen
 * (cristobal-monzo.github.io), así que la carpeta que ya se conectó en el Formulador sirve
 * aquí sin elegirla de nuevo, y al revés.
 */
(function (root) {
  'use strict';

  const ESQUEMA = 'quempin.intercambio/1';
  const MANIFIESTO = 'intercambio.json';
  const CARPETA_HERRAMIENTAS = '.Herramientas formulación';
  const BIBLIOTECA = 'Formulación de proyectos - Documentos';
  // El mismo almacén que js/intercambio.js del Formulador: no cambiar sin cambiar los dos.
  const DB = 'qpn-intercambio';
  const TIENDA = 'carpetas';
  const CLAVE = 'intercambio';
  const CLAVE_BIBLIOTECA = 'biblioteca';

  // ---- Lo que se teclea --------------------------------------------------------------------
  /* «$ 12.345.678» -> «12345678», «35,5» -> «35.5». Punto de miles y coma decimal (es-CL);
     un número con un solo punto y no en grupos de 3 («35.5») se lee como decimal. */
  function limpiarNumero(texto) {
    let s = String(texto).replace(/[\s$%]/g, '');
    if (s.indexOf(',') >= 0) s = s.replace(/\./g, '').replace(',', '.');
    else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, '');
    return s;
  }
  function fechaValida(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    if (!m) return false;
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return d.getUTCFullYear() === +m[1] && d.getUTCMonth() === +m[2] - 1 && d.getUTCDate() === +m[3];
  }
  /* Texto de un campo -> {valor} (null = vacío) o {error}. 'campo' es una entrada de
     DATA.ingreso.campos: {clave, tipo, positivo}. El avance se escribe en % (35) y viaja
     como fracción (0,35), igual que se guarda en el Excel. */
  function parsear(campo, texto) {
    const t = String(texto == null ? '' : texto).trim();
    if (t === '') return { valor: null };
    if (campo.tipo === 'fecha') {
      return fechaValida(t) ? { valor: t } : { error: 'Fecha no válida' };
    }
    const s = limpiarNumero(t);
    if (!/^-?\d+(\.\d+)?$/.test(s)) return { error: 'Escribe solo el número' };
    const n = Number(s);
    if (campo.tipo === 'fraccion') {
      if (n < 0 || n > 100) return { error: 'Debe estar entre 0 y 100 %' };
      return { valor: Math.round(n * 10) / 1000 };
    }
    if (campo.tipo === 'entero') {
      if (!Number.isInteger(n) || n < 1 || n > 999999) return { error: 'Número entero desde 1' };
      return { valor: n };
    }
    if (n < 0) return { error: 'No puede ser negativo' };
    if (campo.positivo && Math.round(n) <= 0) return { error: 'Debe ser mayor que 0' };
    return { valor: Math.round(n) };
  }
  /* Valor (del snapshot o de un envío) -> texto del campo. Un texto que no es número ni
     fecha (algo escrito a mano en el Excel) se muestra tal cual. */
  function mostrar(campo, valor, locale) {
    if (valor == null) return '';
    if (typeof valor !== 'number') return String(valor);
    const loc = locale || 'es-CL';
    if (campo.tipo === 'fraccion') return (Math.round(valor * 1000) / 10).toLocaleString(loc, { maximumFractionDigits: 1 });
    if (campo.tipo === 'entero') return String(valor);
    return Math.round(valor).toLocaleString(loc);
  }
  function normal(v) {
    if (v == null || (typeof v === 'string' && v.trim() === '')) return null;
    if (typeof v === 'string' && /^-?\d+(\.\d+)?$/.test(v.trim())) return Number(v.trim());
    return v;
  }
  /* ¿El mismo dato? Igual que _mismo_valor de Python: medio peso de tolerancia y una
     millonésima en el avance. */
  function iguales(campo, a, b) {
    a = normal(a); b = normal(b);
    if (a === null || b === null) return a === b;
    if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) < (campo.tipo === 'fraccion' ? 1e-6 : 0.5);
    return String(a) === String(b);
  }

  // ---- Mensajes ------------------------------------------------------------------------------
  function isoLocal(d) {
    const z = (n) => String(Math.abs(n)).padStart(2, '0');
    const off = -d.getTimezoneOffset();
    return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}` +
      `${off >= 0 ? '+' : '-'}${z(Math.trunc(off / 60))}:${z(off % 60)}`;
  }
  function nuevoId() {
    const c = root.crypto && root.crypto.getRandomValues ? root.crypto : null;
    const r = c ? c.getRandomValues(new Uint8Array(12)) : null;
    return r ? Array.from(r, (b) => b.toString(16).padStart(2, '0')).join('') : (Date.now().toString(36) + Math.random().toString(36).slice(2, 10));
  }
  /* El mismo nombre que da el Formulador y el Python (intercambio.nombre_mensaje): así el
     buzón queda en orden de envío y un archivo descargado se puede dejar ahí tal cual. */
  function nombreArchivo(m) {
    const t = String(m.origen.enviado).slice(0, 19).replace(/[-:]/g, '').replace('T', '-');
    return `${t}_${m.origen.herramienta}_${m.tipo}_${m.id}.json`;
  }
  /* Un mensaje por proyecto: si uno queda pendiente (alguien cambió el Excel), no frena a
     los demás. 'borrador': {tag: {valores: {clave: valor}, nuevo?: {nombre}}} con solo lo
     que cambió. 'visto(tag, clave)': lo que la persona tenía a la vista (el snapshot, o lo
     último que se envió desde este navegador si el tablero todavía no lo muestra). */
  function armarMensajes(ingreso, borrador, op) {
    op = op || {};
    const porTag = {};
    ingreso.proyectos.forEach((p) => { porTag[p.tag] = p; });
    const ahora = isoLocal(op.ahora || new Date());
    const visto = op.visto || ((tag, clave) => {
      const v = ((porTag[tag] || {}).valores || {})[clave];
      return v === undefined ? null : v;
    });
    const mensajes = [];
    Object.keys(borrador).forEach((tag) => {
      const b = borrador[tag];
      const valores = {}, reemplaza = {};
      ingreso.campos.forEach((c) => {
        if (!Object.prototype.hasOwnProperty.call(b.valores || {}, c.clave)) return;
        valores[c.clave] = b.valores[c.clave];
        reemplaza[c.clave] = b.nuevo ? null : visto(tag, c.clave);
      });
      if (!Object.keys(valores).length) return;
      mensajes.push({
        esquema: ESQUEMA,
        id: (op.nuevoId || nuevoId)(),
        tipo: ingreso.tipo,
        destino: ingreso.destino,
        origen: { herramienta: ingreso.herramienta, usuario: op.usuario || '', enviado: ahora },
        proyecto: b.nuevo ? { tag: tag, nombre: b.nuevo.nombre, crear: true } : { tag: tag },
        valores: valores,
        reemplaza: reemplaza,
        informativo: { nombre: b.nuevo ? b.nuevo.nombre : (porTag[tag] || {}).nombre || '', tablero: ingreso.generado }
      });
    });
    return mensajes;
  }
  /* TAG y nombre de un proyecto nuevo: mismo formato que el prefijo del N° Ref de Centro
     de Costos, y que no exista ya. */
  function validarNuevo(ingreso, tag, nombre, tagsYaAgregados) {
    const errores = [];
    if (!new RegExp(ingreso.patron_tag).test(tag)) errores.push('El TAG debe tener 2 a 10 letras mayúsculas o números (ej. UMAG).');
    else if (ingreso.tags.indexOf(tag) >= 0 || (tagsYaAgregados || []).indexOf(tag) >= 0) errores.push('Ya hay un proyecto con el TAG ' + tag + '.');
    if (!String(nombre || '').trim()) errores.push('Falta el nombre del proyecto.');
    return errores;
  }

  // ---- Carpeta de intercambio (solo navegador) ------------------------------------------------
  let carpeta = null, biblioteca = null, cargada = false;
  const disponible = () => typeof root.showDirectoryPicker === 'function';
  function idb(modo, fn) {
    return new Promise((resolve, reject) => {
      let req;
      try { req = root.indexedDB.open(DB, 1); } catch (e) { reject(e); return; }
      req.onupgradeneeded = () => req.result.createObjectStore(TIENDA);
      req.onerror = () => reject(req.error);
      req.onsuccess = () => {
        const db = req.result;
        const tx = db.transaction(TIENDA, modo);
        const r = fn(tx.objectStore(TIENDA));
        tx.oncomplete = () => { db.close(); resolve(r && r.result); };
        tx.onerror = () => { db.close(); reject(tx.error); };
      };
    });
  }
  async function cargar() {
    if (cargada) return carpeta;
    cargada = true;
    try { carpeta = (await idb('readonly', (s) => s.get(CLAVE))) || null; } catch (e) { carpeta = null; }
    try { biblioteca = carpeta ? (await idb('readonly', (s) => s.get(CLAVE_BIBLIOTECA))) || null : null; } catch (e) { biblioteca = null; }
    return carpeta;
  }
  async function recordar(h, bib) {
    carpeta = h; biblioteca = h ? bib || null : null; cargada = true;
    try { await idb('readwrite', (s) => (h ? s.put(h, CLAVE) : s.delete(CLAVE))); } catch (e) { /* solo esta sesión */ }
    try { await idb('readwrite', (s) => (biblioteca ? s.put(biblioteca, CLAVE_BIBLIOTECA) : s.delete(CLAVE_BIBLIOTECA))); } catch (e) { /* solo esta sesión */ }
  }
  async function leerJSON(dir, nombre) {
    try {
      const f = await (await dir.getFileHandle(nombre)).getFile();
      return JSON.parse((await f.text()).replace(/^﻿/, ''));
    } catch (e) { return null; }
  }
  const esManifiesto = (m) => !!(m && typeof m.esquema === 'string' && m.esquema.indexOf('quempin.intercambio/') === 0);
  const clave = (s) => String(s || '').normalize('NFC').toLowerCase();
  async function hijaComo(dir, nombre) {
    const k = clave(nombre);
    try { for await (const [n, h] of dir.entries()) if (h.kind === 'directory' && clave(n) === k) return h; } catch (e) { /* sin acceso */ }
    return null;
  }
  /* Se acepta elegir la carpeta Intercambio, la de herramientas o la biblioteca completa
     (como en el Formulador). A diferencia de él, nunca prepara una carpeta nueva: si no está
     el manifiesto, no es la carpeta. */
  async function resolverCarpeta(h) {
    if (esManifiesto(await leerJSON(h, MANIFIESTO))) return { carpeta: h, biblioteca: null };
    for (const ruta of [['Intercambio'], [CARPETA_HERRAMIENTAS, 'Intercambio']]) {
      let d = h;
      for (const n of ruta) d = d && await hijaComo(d, n);
      if (d && esManifiesto(await leerJSON(d, MANIFIESTO))) return { carpeta: d, biblioteca: ruta.length === 2 ? h : null };
    }
    return null;
  }
  async function permiso(h) {
    try { return await h.queryPermission({ mode: 'readwrite' }); } catch (e) { return 'prompt'; }
  }
  /* {disponible, conectada, permiso, nombre} -- no pide nada. */
  async function estadoCarpeta() {
    if (!disponible()) return { disponible: false, conectada: false };
    if (!(await cargar())) return { disponible: true, conectada: false };
    return { disponible: true, conectada: true, nombre: carpeta.name, permiso: await permiso(carpeta) };
  }
  /* Abre el selector (desde un clic). */
  async function conectar() {
    const h = await root.showDirectoryPicker({ id: 'quempin-intercambio', mode: 'readwrite' });
    const r = await resolverCarpeta(h);
    if (!r) throw new Error(`Ahí no está la carpeta de intercambio. Elige la biblioteca «${BIBLIOTECA}» de tu OneDrive.`);
    await recordar(r.carpeta, r.biblioteca);
    return estadoCarpeta();
  }
  /* Pide el permiso de la carpeta recordada (desde un clic). Si se recuerda la biblioteca,
     se pide para ella, que alcanza para la carpeta de adentro. */
  async function permitir() {
    if (!(await cargar())) return false;
    if ((await permiso(carpeta)) === 'granted') return true;
    const pedir = async (x) => { try { return (await x.requestPermission({ mode: 'readwrite' })) === 'granted'; } catch (e) { return false; } };
    if (biblioteca && (await permiso(biblioteca)) !== 'granted') await pedir(biblioteca);
    if ((await permiso(carpeta)) === 'granted') return true;
    return pedir(carpeta);
  }
  async function carpetaLista() {
    const h = disponible() ? await cargar() : null;
    return h && (await permiso(h)) === 'granted' && esManifiesto(await leerJSON(h, MANIFIESTO)) ? h : null;
  }
  async function enviar(m) {
    const h = await carpetaLista();
    if (!h) throw new Error('La carpeta de intercambio no está conectada.');
    const buzon = await h.getDirectoryHandle('buzon', { create: true });
    const fh = await buzon.getFileHandle(nombreArchivo(m), { create: true });
    const w = await fh.createWritable();
    await w.write(JSON.stringify(m, null, 2) + '\n');
    await w.close();
    return nombreArchivo(m);
  }
  /* Nombres de los archivos que siguen en el buzón (todavía no los atiende el Análisis
     Financiero). Se busca el id dentro del nombre, como hace el Formulador: el id puede
     llevar «_», así que no se puede recortar del nombre. */
  async function archivosEnBuzon() {
    const h = await carpetaLista();
    const salida = [];
    if (!h) return null;
    try {
      const buzon = await h.getDirectoryHandle('buzon');
      for await (const nombre of buzon.keys()) if (/\.json$/i.test(nombre)) salida.push(nombre);
    } catch (e) { /* sin buzón todavía */ }
    return salida;
  }
  /* Los resultados que publica el Análisis Financiero ({id: {estado, fecha, detalle, tag}}). */
  async function resultados() {
    const h = await carpetaLista();
    if (!h) return null;
    try {
      const pub = await h.getDirectoryHandle('publicado');
      const sobre = await leerJSON(pub, 'analisis-financiero.json');
      return (sobre && sobre.datos && sobre.datos.mensajes) || {};
    } catch (e) { return {}; }
  }
  /* El pulso del procesador del intercambio (publicado/estado.json): si no corre, lo que se
     envía queda en el buzón sin aplicarse. La lectura la hace pulso.js (Sistema Intercambio). */
  async function estadoProcesador() {
    const h = await carpetaLista();
    if (!h) return null;
    try {
      const pub = await h.getDirectoryHandle('publicado');
      const sobre = await leerJSON(pub, 'estado.json');
      return (sobre && sobre.datos) || null;
    } catch (e) { return null; }
  }
  function descargar(m) {
    const a = root.document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(m, null, 2) + '\n'], { type: 'application/json' }));
    a.download = nombreArchivo(m);
    root.document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  const api = {
    parsear, mostrar, iguales, armarMensajes, validarNuevo, nombreArchivo, isoLocal, nuevoId, fechaValida,
    carpeta: { disponible, estado: estadoCarpeta, conectar, permitir, enviar, archivosEnBuzon, resultados, estadoProcesador }, descargar
  };
  root.QIngreso = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
