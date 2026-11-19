/* Portal QUEMPIN — Planificación semanal (pl*, planif).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Planificación semanal (2026-10-20) -----------------------------------------------------------
// Pedido del usuario: planificar cada semana según el personal y los proyectos activos. Cada día se asigna quién va
// a qué proyecto («el lunes, ES en Llay Llay y LC en Limache»), con 3 proyectos por persona en un día como máximo,
// y se ve por personal, por proyecto y en una vista general. Un proyecto activo sin nadie asignado en la semana de
// hoy es una alarma (en la vista, en la cabecera, en el menú y en el Inicio) hasta que se asigna o se marca que esa
// semana no se trabaja. Los proyectos activos son los que el Recorrido pone en Ejecución (rcArmar): las dos vistas
// cuentan lo mismo.
// Lo planificado vive en la carpeta de intercambio, en «publicado/planificacion/<AAAA-Www>/<dispositivo>.json».
// Cada navegador escribe solo su archivo, así OneDrive nunca tiene que juntar dos versiones del mismo, y la semana
// es la unión de todos: en cada casilla (una persona en un proyecto un día, una ausencia, una pausa, un vehículo)
// manda el cambio más reciente, también si fue quitar. Lo que no alcanzó a guardarse espera en este navegador y se
// reintenta.
// Vehículos (2026-10-25): a una persona en un proyecto un día se le asigna uno de los de la empresa (Quempineta o
// RAM, del registro), con un toque en la ventanita de la casilla; quienes van juntos llevan el mismo. Se ve en cada
// casilla, en el resumen de arriba, en «Vehículos en la semana» de la vista General, al compartir y al imprimir. Un
// vehículo con personas que no comparten proyecto ese día está en dos lugares a la vez: se avisa, sin impedirlo.
const PL_MAX = 3;                      // proyectos de una persona en un día
const PL_RELEER_SEG = 3;               // con la vista abierta, cada cuánto se miran los cambios del equipo
const PL_AJENO_SEG = 15;               // cuánto rato dice la línea de arriba quién acaba de cambiar algo
const PL_ATASCO_SEG = 60;              // leyendo o guardando más que esto, la carpeta no está respondiendo
const PL_REINTENTO_SEG = 30;           // tras un error al guardar, cada cuánto se reintenta solo
const PL_DIAS = [
  { nombre: 'Lunes', corto: 'Lun', letra: 'L' }, { nombre: 'Martes', corto: 'Mar', letra: 'M' },
  { nombre: 'Miércoles', corto: 'Mié', letra: 'X' }, { nombre: 'Jueves', corto: 'Jue', letra: 'J' },
  { nombre: 'Viernes', corto: 'Vie', letra: 'V' }, { nombre: 'Sábado', corto: 'Sáb', letra: 'S' }
];
const PL_MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const PL_AUSENCIAS = [
  { id: 'vacaciones', nombre: 'Vacaciones' }, { id: 'licencia', nombre: 'Licencia médica' },
  { id: 'permiso', nombre: 'Permiso' }, { id: 'otro', nombre: 'Otra ausencia' }
];
const PL_VISTAS = [
  { id: 'personal', nombre: 'Por personal', icono: 'persona' },   // la vista principal (pedido del usuario, 2026-11-12)
  { id: 'general', nombre: 'General', icono: 'cuadricula' },
  { id: 'proyecto', nombre: 'Por proyecto', icono: 'proyectos' }
];
const PL_COLORES = 10;                                       // --pl-c0 … --pl-c9
const LS_PL = 'quempin_portal_plan';                         // { vista, sabado, v }: lo elegido en este navegador
// v: 2 desde que «Por personal» es la vista principal (2026-11-12): una «General» guardada antes era la de entrada, no
// una elección, así que se abre en «Por personal» una vez; lo que se elija después se respeta
const PL_PREFS_V = 2;
const LS_PL_DISPOSITIVO = 'quempin_portal_dispositivo';      // el nombre del archivo de este navegador
const LS_PL_PENDIENTE = 'quempin_portal_plan_pendiente';     // lo que aún no llega a la carpeta
const PERSONAL = Array.isArray(REG.personal) && REG.personal.length ? REG.personal : USUARIOS;
const PL_VEHICULOS = (Array.isArray(REG.vehiculos) ? REG.vehiculos : []).filter((v) => v && /^[a-z0-9-]{1,24}$/.test(texto(v.id)) && texto(v.nombre));
const plVehiculo = (id) => PL_VEHICULOS.find((v) => v.id === id) || null;
const plLaVeh = (v) => (v.articulo || 'la') + ' ' + v.nombre;           // «la RAM»
const mayuscula = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const PL_TIPOS = ['asig', 'aus', 'pau', 'veh'];                          // las casillas de una semana
// pro: un proyecto escrito a mano en la planificación (2026-10-26), que no viene del Recorrido
const PL_CLAVE = /^(req:(\d{1,6}|\d{3,4}t)|tag:[A-Z0-9]{2,10}|otra:[a-z0-9-]{1,40}|pro:[a-z0-9-]{1,40})$/;
const PL_INSTANTE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/;
// Una persona escrita a mano (2026-10-26): «x-» y su nombre sin tildes («x-juan-perez»); el nombre va en la lista
const PL_PER_MANO = /^x-[a-z0-9-]{1,30}$/;
const plPerValida = (x) => PERSONAL.includes(x) || PL_PER_MANO.test(texto(x));
const PL_LISTA = 'lista';     // publicado/planificacion/lista/<dispositivo>.json: las personas y proyectos agregados a mano
const PL_CIERRES = 'cierres'; // publicado/planificacion/cierres/<dispositivo>.json: los proyectos dados por cerrados
const PL_CLAVE_CIERRE = /^(req:(\d{1,6}|\d{3,4}t)|tag:[A-Z0-9]{2,10})$/;
const PL_CERRADOS_MAX = 12;   // los cerrados más recientes que muestra «Estado de los proyectos», para reabrirlos
// «Juan Pérez» → «juan-perez»: la parte de la clave que sale del nombre
const plSlug = (txt, max) => norm(txt).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, max).replace(/-+$/, '');
const PL_SIN_CARPETA = {
  navegador: 'La planificación se guarda en la carpeta del equipo, y este navegador no puede abrir carpetas del computador.',
  conectar: 'La planificación lee los proyectos en ejecución y guarda lo asignado en la carpeta de intercambio. Conecta una vez la biblioteca «' + BIBLIOTECA_FORMULACION + '» en este navegador (la misma conexión del Formulador) y acepta «Ver archivos» y «Guardar cambios».'
};
const plPrefs = leer(LS_PL, {}) || {};
const planif = {
  vista: PL_VISTAS.some((v) => v.id === plPrefs.vista) && (plPrefs.v === PL_PREFS_V || plPrefs.vista !== 'general') ? plPrefs.vista : 'personal',
  sabado: plPrefs.sabado === true,
  ocultas: new Set(Array.isArray(plPrefs.ocultas) ? plPrefs.ocultas.filter((x) => typeof x === 'string').slice(0, 200) : []),   // quienes no se ven (2026-11-13)
  texto: plPrefs.texto === 'dia' ? 'dia' : 'persona',     // cómo se ordena el texto de Compartir
  lunes: null,              // el lunes de la semana a la vista
  semanas: new Map(),       // «2026-W43» → { id, lunes, archivos, mias, ef, leida }
  lista: null,              // las personas y proyectos agregados a mano: { archivos, mias, ef, leida } (plLista)
  cierres: null,            // los proyectos dados por cerrados: { archivos, mias, ef, leida } (plCierres)
  cerrar: null,             // en «Estado de los proyectos», la tarjeta que se está por cerrar (su formulario abierto)
  cerrando: false, proyAviso: null,
  dispositivo: '',
  reloj: 0,                 // el instante más nuevo que se vio o se escribió (ms)
  porGuardar: new Set(), guardando: false, otraVez: false, relojGuardar: null, guardado: 0, errorGuardar: null,
  deshacer: [],             // tandas de cambios para deshacer, la última al final
  recien: new Set(), relojRecien: null,   // las casillas (anclas) de la última tanda, que se iluminan
  recienAjeno: false, ajeno: null,        // esa tanda llegó de otro computador; quién y cuándo, para la línea de arriba
  pisado: null,             // lo tuyo que otro reemplazó (2026-11-10): { semana, items: [{ tipo, k, mio, suyo }] }
  repintar: false,                        // llegó algo con un arrastre a medias: se pinta al soltar
  leyendo: null, error: null, leyendoDesde: 0, guardandoDesde: 0, falloGuardar: 0,
  pop: null,                // la ventanita abierta: { tipo: persona | proyecto | nuevo, iso, ancla, … }
  diaMovil: null,           // el día que muestran las tablas en el teléfono
  foco: null,               // el proyecto que «Por proyecto» resalta al pintarse
  focoVeh: false,           // «Vehículos en la semana», que General muestra al pintarse (desde el resumen)
  alarmaAbierta: false,     // la lista de los proyectos sin asignar, desplegada bajo el resumen
  // Los paneles de abajo de General que están abiertos (plegados de entrada: 2026-10-28)
  paneles: new Set(Array.isArray(plPrefs.paneles) ? plPrefs.paneles.filter((x) => typeof x === 'string') : []),
  arrastre: null,           // lo que se está arrastrando: { tipo: proyecto | persona, clave?, per?, desde?: { per, iso, clave } }
  armado: null,             // lo elegido en el panel para ir tocando casillas: { tipo: proyecto, clave } o { tipo: persona, per }
  arrQ: '',                 // lo escrito en el buscador del panel de arrastre
  arrAbierto: false         // en lo angosto el panel va plegado hasta pedirlo (2026-10-29)
};
const plGuardarPrefs = () => guardar(LS_PL, { v: PL_PREFS_V, vista: planif.vista, sabado: planif.sabado, texto: planif.texto, paneles: [...planif.paneles], ocultas: [...planif.ocultas] });

// ---- Semanas: de lunes a sábado, con el número ISO 8601 (la semana es del año de su jueves) -------------------
const plMas = (f, n) => new Date(f.getFullYear(), f.getMonth(), f.getDate() + n);
const plISO = (f) => f.getFullYear() + '-' + dos(f.getMonth() + 1) + '-' + dos(f.getDate());
function plDesdeISO(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(texto(s));
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}
function plLunesDe(f) {
  const d = new Date(f.getFullYear(), f.getMonth(), f.getDate());
  return plMas(d, -((d.getDay() + 6) % 7));
}
function plSemanaId(lunes) {
  const jueves = plMas(lunes, 3);
  const primera = plLunesDe(new Date(jueves.getFullYear(), 0, 4));   // la semana 1 es la del 4 de enero
  return jueves.getFullYear() + '-W' + dos(1 + Math.round((rcDia(lunes) - rcDia(primera)) / (7 * DIA)));
}
function plLunesDeId(id) {
  const m = /^(\d{4})-W(\d{2})$/.exec(id || '');
  return m && +m[2] >= 1 && +m[2] <= 53 ? plMas(plLunesDe(new Date(+m[1], 0, 4)), 7 * (+m[2] - 1)) : null;
}
const plHoyId = () => plSemanaId(plLunesDe(new Date()));
const plNum = (s) => +s.id.slice(-2);
function plRango(lunes, n) {
  const fin = plMas(lunes, n - 1);
  return lunes.getMonth() === fin.getMonth() ? lunes.getDate() + ' al ' + fin.getDate() + ' de ' + PL_MESES[fin.getMonth()]
    : lunes.getDate() + ' de ' + PL_MESES[lunes.getMonth()] + ' al ' + fin.getDate() + ' de ' + PL_MESES[fin.getMonth()];
}
function plDiaDe(s, iso) {
  const i = Math.round((rcDia(plDesdeISO(iso)) - rcDia(s.lunes)) / DIA);
  const fecha = plMas(s.lunes, i);
  const hoy = plISO(new Date());
  return { i, iso, fecha, nombre: PL_DIAS[i].nombre, corto: PL_DIAS[i].corto, letra: PL_DIAS[i].letra, hoy: iso === hoy, pasado: iso < hoy };
}
// La clase de un día: hoy resaltado y los que ya pasaron, apagados (2026-10-29: se veían igual que los que vienen)
const plClaseDia = (d) => (d.hoy ? ' hoy' : d.pasado ? ' pasado' : '');
// Los días a la vista: de lunes a viernes, y el sábado si se pidió o si ya tiene algo.
function plDias(s) {
  const sabado = plISO(plMas(s.lunes, 5));
  const tiene = [...s.ef.asig.values()].some((e) => e.activa && e.dia === sabado) || [...s.ef.aus.values()].some((e) => e.motivo && e.dia === sabado);
  return PL_DIAS.slice(0, planif.sabado || tiene ? 6 : 5).map((x, i) => plDiaDe(s, plISO(plMas(s.lunes, i))));
}
const plElDia = (d) => 'el ' + d.nombre.toLowerCase() + ' ' + d.fecha.getDate();               // «el lunes 19»
const plFechaLarga = (d) => d.nombre + ' ' + d.fecha.getDate() + ' de ' + PL_MESES[d.fecha.getMonth()];
// «hoy a las 16:05», «ayer a las 9:30», «el 17-10 a las 11:00»
function plCuando(t) {
  const f = new Date(t);
  if (isNaN(f)) return '';
  const hoy = new Date();
  const d = rcDias(f, hoy);
  return (d === 0 ? 'hoy' : d === -1 ? 'ayer' : 'el ' + rcCorta(f, hoy)) + ' a las ' + f.getHours() + ':' + dos(f.getMinutes());
}
const plEsta = (s) => (s.id === plHoyId() ? 'esta semana' : 'la semana ' + plNum(s));

// ---- Lo de cada navegador y su reloj -------------------------------------------------------------------------
function plDispositivo() {
  if (planif.dispositivo) return planif.dispositivo;
  let id = null;
  try { id = localStorage.getItem(LS_PL_DISPOSITIVO); } catch (e) { id = null; }
  if (!/^[a-z0-9]{8,24}$/.test(id || '')) {
    id = Array.from(crypto.getRandomValues(new Uint8Array(10)), (b) => (b % 36).toString(36)).join('');
    try { localStorage.setItem(LS_PL_DISPOSITIVO, id); } catch (e) { /* solo esta visita: la próxima, otro archivo */ }
  }
  planif.dispositivo = id;
  return id;
}
// El instante de un cambio: el reloj de este computador, pero siempre después de lo último que se vio de otro. Si
// este reloj va atrasado, lo que se cambia aquí después de ver un cambio ajeno igual le gana.
function plAhora() {
  planif.reloj = Math.max(Date.now(), planif.reloj + 1);
  return new Date(planif.reloj).toISOString();
}

// ---- Uso del Portal (2026-11-09): cuántas veces se abre cada herramienta, anónimo ---------------------------
/* Para decidir qué mejorar con datos: por día y herramienta, en este navegador (sin usuario). Se cuenta en
   localStorage y se guarda en publicado/uso-portal/<dispositivo>.json como mucho cada 2 minutos; sin la carpeta
   conectada espera en este navegador. Lo suma Sistema Intercambio/uso_portal.py. Últimos 90 días. */
const LS_USO = 'quempin_portal_uso';
const USO_DIAS = 90;
const uso = { ultima: null, reloj: null, guardando: false };
const usoFecha = (t) => t.getFullYear() + '-' + dos(t.getMonth() + 1) + '-' + dos(t.getDate());
function usoLeer() {
  let d = null;
  try { d = JSON.parse(localStorage.getItem(LS_USO) || '{}'); } catch (e) { d = null; }
  return d && typeof d === 'object' && !Array.isArray(d) ? d : {};
}
function usoAnotar(herr) {
  if (!herr || herr === uso.ultima) return;     // volver a la misma pestaña sin pasar por otra no cuenta
  uso.ultima = herr;
  if (herr === 'inicio') return;
  const d = usoLeer();
  const hoy = usoFecha(new Date());
  d[hoy] = d[hoy] || {};
  d[hoy][herr] = (d[hoy][herr] | 0) + 1;
  const limite = usoFecha(new Date(Date.now() - USO_DIAS * 864e5));
  Object.keys(d).forEach((f) => { if (f < limite) delete d[f]; });
  try { localStorage.setItem(LS_USO, JSON.stringify(d)); } catch (e) { /* sin almacenamiento: no se cuenta */ }
  if (!uso.reloj) uso.reloj = setTimeout(usoGuardar, 120000);
}
function usoSobre() {
  const d = usoLeer();
  const dias = [];
  Object.keys(d).sort().forEach((f) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(f) || !d[f] || typeof d[f] !== 'object') return;
    Object.keys(d[f]).sort().forEach((h) => {
      const n = d[f][h] | 0;
      if (n > 0 && h) dias.push({ fecha: f, herramienta: String(h).slice(0, 64), aperturas: n });
    });
  });
  return { esquema: 'quempin.intercambio/1', herramienta: 'portal', generado: new Date().toISOString(),
    datos: { dispositivo: plDispositivo(), dias } };
}
async function usoGuardar() {
  uso.reloj = null;
  if (uso.guardando || !rc.dir || soloLectura()) return;       // sin la carpeta: queda en este navegador y se guarda la próxima vez
  uso.guardando = true;
  try {
    const sobre = usoSobre();
    await exigirEsquema(rc.dir, 'uso-portal', sobre);
    const carpeta = await (await rc.dir.getDirectoryHandle('publicado', { create: true })).getDirectoryHandle('uso-portal', { create: true });
    const w = await (await carpeta.getFileHandle(plDispositivo() + '.json', { create: true })).createWritable();
    await w.write(JSON.stringify(sobre, null, 1));
    await w.close();
  } catch (e) { console.warn('Uso del Portal: no se guardó', e); }
  uso.guardando = false;
}
// Al dejar la pestaña (otra ventana, cerrar) se guarda lo que esperaba, sin aguardar los 2 minutos.
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden' && uso.reloj) { clearTimeout(uso.reloj); usoGuardar(); }
});

// ---- Trabajar a la vez (2026-11-10): quién más está aquí, y lo tuyo que otro reemplazó ------------------------
/* Pedido del usuario: que en la Planificación semanal y en Proyectos en ejecución se pueda trabajar a la vez sin pisarse
   sin saberlo. Las dos vistas ya juntan lo de todos (en cada casilla o cosa manda el cambio más reciente); esto agrega:
   - Presencia: cada navegador deja en publicado/presencia/<dispositivo>.json (esquema presencia) qué semana o qué
     proyecto tiene a la vista, cada PRES_RENOVAR_SEG mientras la vista está abierta, y vacío al salir. Lo que no se
     renovó en PRES_VIGENCIA_SEG no cuenta (un computador que se apagó). Llega con OneDrive, como todo lo demás.
   - Pisado: si llega de otro un cambio que reemplaza uno tuyo hecho menos de PISADO_MIN minutos antes, con otro valor,
     una franja dice quién y qué, con «Volver a lo mío» (otro cambio, con su Deshacer) y «Dejar lo de …». */
const PRES_RENOVAR_SEG = 90;
const PRES_VIGENCIA_SEG = 300;
const PRES_LEER_SEG = 15;
const PISADO_MIN = 60;
const pres = { escrito: '|', escritoEn: 0, escribiendo: false, leidoEn: 0, leyendo: false, otros: [] };
// Lo que este navegador tiene a la vista: la semana de la Planificación o el proyecto de Proyectos en ejecución
function presAhora() {
  // Ingresando un requerimiento nuevo (2026-11-12): para que otro que ingresa a la vez sepa que pueden tomar el mismo N°
  if (document.visibilityState === 'visible' && $('#dlgPlanilla').open && pq.abierta && pq.abierta.nuevo) return { vista: 'planilla', donde: 'nuevo' };
  if (document.visibilityState === 'visible' && planif.lunes && !$('#vistaPlan').hidden) return { vista: 'planificacion', donde: plSemanaId(planif.lunes) };
  if (document.visibilityState === 'visible' && ej.clave && !$('#vistaEjecucion').hidden) return { vista: 'ejecucion', donde: ej.clave };
  return { vista: '', donde: '' };
}
function presVigilar() {
  if (!rc.dir) return;
  const a = presAhora();
  const clave = a.vista + '|' + a.donde;
  if (clave !== pres.escrito || (a.vista && Date.now() - pres.escritoEn > PRES_RENOVAR_SEG * 1000)) presEscribir(a);
  if (a.vista && Date.now() - pres.leidoEn > PRES_LEER_SEG * 1000) presLeer();
  else if (!a.vista && pres.otros.length) { pres.otros = []; presPintar(); }
}
async function presEscribir(a) {
  if (pres.escribiendo || soloLectura()) return;
  pres.escribiendo = true;
  const clave = a.vista + '|' + a.donde;
  try {
    const sobre = { esquema: 'quempin.intercambio/1', herramienta: 'portal', generado: new Date().toISOString(),
      datos: { dispositivo: plDispositivo(), por: /^[A-Z]{2,3}$/.test(estado.usuario || '') ? estado.usuario : '', vista: a.vista, donde: a.donde, t: new Date().toISOString() } };
    await exigirEsquema(rc.dir, 'presencia', sobre);
    const carpeta = await (await rc.dir.getDirectoryHandle('publicado', { create: true })).getDirectoryHandle('presencia', { create: true });
    const w = await (await carpeta.getFileHandle(plDispositivo() + '.json', { create: true })).createWritable();
    await w.write(JSON.stringify(sobre, null, 1));
    await w.close();
  } catch (e) { console.warn('Presencia: no se guardó', e); }      // se reintenta al renovar
  pres.escrito = clave;
  pres.escritoEn = Date.now();
  pres.escribiendo = false;
}
async function presLeer() {
  if (pres.leyendo) return;
  pres.leyendo = true;
  pres.leidoEn = Date.now();
  const otros = [];
  try {
    const carpeta = await (await rc.dir.getDirectoryHandle('publicado')).getDirectoryHandle('presencia');
    const mio = plDispositivo() + '.json';
    const limite = Date.now() - PRES_VIGENCIA_SEG * 1000, tope = Date.now() + PRES_VIGENCIA_SEG * 1000;
    for await (const [n, h] of carpeta.entries()) {
      if (h.kind !== 'file' || !/\.json$/i.test(n) || n === mio) continue;
      try {
        const f = await h.getFile();
        if (f.lastModified < limite) continue;          // no se tocó en todo ese rato: ya no está
        const sobre = JSON.parse(rcSinBom(await f.text()));
        const d = sobre && sobre.esquema === 'quempin.intercambio/1' && sobre.datos;
        const t = d ? Date.parse(d.t) : NaN;
        if (!(t > limite && t < tope) || !['planificacion', 'ejecucion', 'planilla'].includes(d.vista) || typeof d.donde !== 'string') continue;
        const por = /^[A-Z]{2,3}$/.test(texto(d.por)) ? d.por : '';
        if (por && por === estado.usuario) continue;    // la misma persona en otro computador
        otros.push({ por, vista: d.vista, donde: d.donde.slice(0, 40) });
      } catch (e) { /* a medio sincronizar */ }
    }
  } catch (e) { /* nadie ha dejado su presencia todavía */ }
  pres.otros = otros;
  pres.leyendo = false;
  presPintar();
}
// «LC también está en esta semana», «LC y NB también están en este proyecto»
function presTexto(vista, donde) {
  const ps = [...new Set(pres.otros.filter((o) => o.vista === vista && o.donde === donde).map((o) => o.por || 'Otro computador'))];
  if (!ps.length) return '';
  if (vista === 'planilla') return unir(ps) + (ps.length > 1 ? ' también están ingresando requerimientos' : ' también está ingresando un requerimiento');
  return unir(ps) + (ps.length > 1 ? ' también están ' : ' también está ') + (vista === 'planificacion' ? 'en esta semana' : 'en este proyecto');
}
function presPintar() {
  const nuevoAbierto = $('#dlgPlanilla').open && pq.abierta && pq.abierta.nuevo ? 'nuevo' : '';
  [['#plConmigo', 'planificacion', planif.lunes ? plSemanaId(planif.lunes) : ''], ['#ejConmigo', 'ejecucion', ej.clave || ''],
    ['#pqConmigo', 'planilla', nuevoAbierto]].forEach(([sel, vista, donde]) => {
    const el = $(sel);
    const t = donde ? presTexto(vista, donde) : '';
    el.hidden = !t;
    if (el.textContent !== t) el.textContent = t;
    el.title = t ? 'Lo que cambia cada uno llega al otro con OneDrive. Si los dos cambian lo mismo, queda lo último y esta vista avisa a quien le reemplazaron lo suyo.' : '';
  });
}
// La franja de lo tuyo que otro reemplazó: quién, qué (hasta 4 líneas) y los dos botones. Sin p, se esconde.
function pisPintar(caja, p, volver, dejar) {
  caja.textContent = '';
  caja.hidden = !p;
  if (!p) return;
  const txt = crear('div', 'pisado-txt');
  const n = p.lineas.length;
  txt.append(crear('strong', null, p.quien + ' cambió ' + (n === 1 ? 'algo' : n + ' cosas') + ' que tú acababas de cambiar'));
  const ul = crear('ul');
  p.lineas.slice(0, 4).forEach((l) => ul.append(crear('li', null, l)));
  if (n > 4) ul.append(crear('li', null, 'y ' + (n - 4) + ' más'));
  txt.append(ul);
  const b1 = crear('button', 'cx-enlace', 'Volver a lo mío');
  b1.type = 'button';
  b1.addEventListener('click', volver);
  const b2 = crear('button', 'cx-enlace', 'Dejar lo de ' + p.quien);
  b2.type = 'button';
  b2.addEventListener('click', dejar);
  caja.append(txt, b1, b2);
}
const pisQuien = (items) => unir([...new Set(items.map((x) => x.suyo.por || 'Otro computador'))]);
const sinMarca = (e) => { const x = Object.assign({}, e); delete x.t; delete x.por; delete x.de; return x; };
const pisReciente = (mio, suyo) => Date.parse(suyo.t) - Date.parse(mio.t) < PISADO_MIN * 60000;
// proyectos y personas: los nombres de lo usado en la semana (las personas, solo las escritas a mano)
const plVacia = () => ({ asig: new Map(), aus: new Map(), pau: new Map(), veh: new Map(), proyectos: {}, personas: {} });
const plKAsig = (e) => e.dia + '|' + e.persona + '|' + e.proyecto;      // también la del vehículo de esa asignación
const plKAus = (e) => e.dia + '|' + e.persona;
const plKPau = (e) => e.proyecto;
const plK = (tipo, e) => (tipo === 'asig' || tipo === 'veh' ? plKAsig(e) : tipo === 'aus' ? plKAus(e) : plKPau(e));
// Manda el cambio más reciente; con el mismo instante, el del dispositivo de nombre mayor (en todos los computadores el mismo).
const plGana = (a, b) => !a || b.t > a.t || (b.t === a.t && (b.de || '') > (a.de || ''));
function plPoner(mapa, k, e) { if (plGana(mapa.get(k), e)) mapa.set(k, e); }
function plSemana(id) {
  let s = planif.semanas.get(id);
  if (!s) {
    s = { id, lunes: plLunesDeId(id), archivos: new Map(), mias: plVacia(), ef: plVacia(), leida: 0 };
    planif.semanas.set(id, s);
  }
  return s;
}
/* Lo que trae un archivo de la semana, validado: la carpeta la puede editar cualquiera con acceso a la biblioteca, así
   que solo entra lo que tiene la forma acordada (días de esa semana, iniciales del personal, claves de proyecto). */
function plLeerArchivo(sobre, id, lunes) {
  const d = sobre && sobre.esquema === 'quempin.intercambio/1' && sobre.herramienta === 'planificacion' ? sobre.datos : null;
  if (!d || typeof d !== 'object' || d.semana !== id) return null;
  const de = texto(d.dispositivo).slice(0, 24);
  const primero = plISO(lunes), ultimo = plISO(plMas(lunes, 5));
  const tope = new Date(Date.now() + 365 * DIA).toISOString();    // un reloj muy adelantado no manda para siempre
  const instante = (x) => typeof x === 'string' && PL_INSTANTE.test(x) && x <= tope;
  const dia = (x) => typeof x === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(x) && x >= primero && x <= ultimo;
  const por = (x) => (/^[A-Z]{2,3}$/.test(texto(x)) ? texto(x) : '');
  const lista = (v) => (Array.isArray(v) ? v.slice(0, 3000) : []);
  const r = plVacia();
  lista(d.asignaciones).forEach((x) => {
    if (!x || !dia(x.dia) || !plPerValida(x.persona) || !PL_CLAVE.test(texto(x.proyecto)) || !instante(x.t)) return;
    plPoner(r.asig, plKAsig(x), { dia: x.dia, persona: x.persona, proyecto: x.proyecto, activa: x.activa === true, t: x.t, por: por(x.por), de });
  });
  lista(d.ausencias).forEach((x) => {
    if (!x || !dia(x.dia) || !plPerValida(x.persona) || !instante(x.t)) return;
    const motivo = PL_AUSENCIAS.some((a) => a.id === x.motivo) ? x.motivo : '';
    plPoner(r.aus, plKAus(x), { dia: x.dia, persona: x.persona, motivo, t: x.t, por: por(x.por), de });
  });
  lista(d.pausas).forEach((x) => {
    if (!x || !PL_CLAVE.test(texto(x.proyecto)) || !instante(x.t)) return;
    plPoner(r.pau, plKPau(x), { proyecto: x.proyecto, activa: x.activa === true, nota: texto(x.nota).slice(0, 120), t: x.t, por: por(x.por), de });
  });
  // Un vehículo que ya no está en el registro cuenta como quitado
  lista(d.vehiculos).forEach((x) => {
    if (!x || !dia(x.dia) || !plPerValida(x.persona) || !PL_CLAVE.test(texto(x.proyecto)) || !instante(x.t)) return;
    plPoner(r.veh, plKAsig(x), { dia: x.dia, persona: x.persona, proyecto: x.proyecto, vehiculo: plVehiculo(x.vehiculo) ? x.vehiculo : '', t: x.t, por: por(x.por), de });
  });
  if (d.proyectos && typeof d.proyectos === 'object' && !Array.isArray(d.proyectos)) {
    Object.keys(d.proyectos).slice(0, 500).forEach((k) => {
      const v = d.proyectos[k];
      if (!PL_CLAVE.test(k) || !v || typeof v !== 'object') return;
      r.proyectos[k] = { titulo: texto(v.titulo).slice(0, 120), lugar: texto(v.lugar).slice(0, 80), req: rcNum(v.req),
        tag: /^[A-Z0-9]{2,10}$/.test(texto(v.tag)) ? texto(v.tag) : null };
    });
  }
  if (d.personas && typeof d.personas === 'object' && !Array.isArray(d.personas)) {
    Object.keys(d.personas).slice(0, 200).forEach((k) => {
      const v = d.personas[k];
      const nombre = v && typeof v === 'object' ? plNombreLimpio(v.nombre) : '';
      if (PL_PER_MANO.test(k) && nombre) r.personas[k] = { nombre };
    });
  }
  r.generado = texto(sobre.generado);
  return r;
}
// La semana tal como la ve el equipo: todos los archivos y lo de este navegador, y en cada casilla lo más reciente.
function plRecalcular(s) {
  const ef = plVacia();
  const fuentes = [...s.archivos.values()].sort((a, b) => (a.generado || '').localeCompare(b.generado || '')).concat([s.mias]);
  fuentes.forEach((f) => {
    PL_TIPOS.forEach((tipo) => f[tipo].forEach((e, k) => plPoner(ef[tipo], k, e)));
    Object.assign(ef.proyectos, f.proyectos);      // los nombres: los del archivo más nuevo (y los de aquí) valen más
    Object.assign(ef.personas, f.personas);
  });
  s.ef = ef;
}
// Lo que este navegador escribió (su propio archivo, o lo que esperaba guardarse) vuelve a ser suyo.
function plAdoptar(s, r) {
  PL_TIPOS.forEach((tipo) => r[tipo].forEach((e, k) => plPoner(s.mias[tipo], k, e)));
  Object.keys(r.proyectos).forEach((k) => { if (!s.mias.proyectos[k]) s.mias.proyectos[k] = r.proyectos[k]; });
  Object.keys(r.personas).forEach((k) => { if (!s.mias.personas[k]) s.mias.personas[k] = r.personas[k]; });
}

/* ---- Las personas y proyectos agregados a mano (2026-10-26) ------------------------------------------------------
   Son temporales: valen solo para la semana en que se agregaron (2026-10-26: alguien de apoyo o una obra puntual no
   pasa a las semanas siguientes; «Copiar la semana anterior» los lleva junto con lo suyo). Van en
   publicado/planificacion/lista/<dispositivo>.json (esquema planificacion-lista), un archivo por navegador como las
   semanas, y en cada semana y persona o proyecto manda el cambio más reciente (quitarlo es 'activa': false; lo ya
   asignado se sigue viendo con su nombre). Uno guardado antes, sin 'semana', es de la semana en que se escribió. */
const plNombreLimpio = (v) => texto(v).replace(/\s+/g, ' ').trim().slice(0, 60);
const plListaVacia = () => ({ personas: new Map(), proyectos: new Map() });
// Una persona del personal definitivo (2026-11-13, 'fija') es una sola para todas las semanas: «fija|x-juan-perez»
const plKLista = (e) => (e.fija ? 'fija' : e.semana) + '|' + (e.id || e.clave);
function plLista() {
  if (!planif.lista) planif.lista = { archivos: new Map(), mias: plListaVacia(), ef: plListaVacia(), leida: 0 };
  return planif.lista;
}
function plLeerListaArchivo(sobre) {
  const d = sobre && sobre.esquema === 'quempin.intercambio/1' && sobre.herramienta === 'planificacion' ? sobre.datos : null;
  if (!d || typeof d !== 'object') return null;
  const de = texto(d.dispositivo).slice(0, 24);
  const tope = new Date(Date.now() + 365 * DIA).toISOString();
  const instante = (x) => typeof x === 'string' && PL_INSTANTE.test(x) && x <= tope;
  const por = (x) => (/^[A-Z]{2,3}$/.test(texto(x)) ? texto(x) : '');
  const lista = (v) => (Array.isArray(v) ? v.slice(0, 2000) : []);
  const semana = (x) => (plLunesDeId(texto(x.semana)) ? x.semana : plSemanaId(plLunesDe(new Date(x.t))));
  const r = plListaVacia();
  lista(d.personas).forEach((x) => {
    const nombre = x ? plNombreLimpio(x.nombre) : '';
    if (!x || !PL_PER_MANO.test(texto(x.id)) || !nombre || !instante(x.t)) return;
    const e = { id: x.id, nombre, semana: semana(x), activa: x.activa === true, t: x.t, por: por(x.por), de };
    if (x.fija === true) e.fija = true;
    plPoner(r.personas, plKLista(e), e);
  });
  lista(d.proyectos).forEach((x) => {
    const titulo = x ? plNombreLimpio(x.titulo) : '';
    if (!x || !/^(req:(\d{1,6}|\d{3,4}t)|pro:[a-z0-9-]{1,40})$/.test(texto(x.clave)) || !titulo || !instante(x.t)) return;
    const e = { clave: x.clave, titulo, lugar: plNombreLimpio(x.lugar), semana: semana(x), activa: x.activa === true, t: x.t, por: por(x.por), de };
    plPoner(r.proyectos, plKLista(e), e);
  });
  r.generado = texto(sobre.generado);
  return r;
}
function plRecalcularLista() {
  const l = plLista();
  const ef = plListaVacia();
  [...l.archivos.values()].concat([l.mias]).forEach((f) => ['personas', 'proyectos'].forEach((k) => f[k].forEach((e, id) => plPoner(ef[k], id, e))));
  l.ef = ef;
}
function plAdoptarLista(r) {
  const l = plLista();
  ['personas', 'proyectos'].forEach((k) => r[k].forEach((e, id) => plPoner(l.mias[k], id, e)));
}
function plSobreLista() {
  const l = plLista();
  const sinDe = (e) => { const x = Object.assign({}, e); delete x.de; return x; };
  return {
    esquema: 'quempin.intercambio/1', herramienta: 'planificacion', tipo: 'planificacion-lista',
    generado: new Date().toISOString(), autor: estado.usuario || '',
    datos: { dispositivo: plDispositivo(), personas: [...l.mias.personas.values()].map(sinDe), proyectos: [...l.mias.proyectos.values()].map(sinDe) }
  };
}
// Lo más reciente de una persona o un proyecto agregado a mano, en cualquier semana: su nombre
function plManoUltimo(tipo, k) {
  let u = null;
  plLista().ef[tipo].forEach((e) => { if ((e.id || e.clave) === k && plGana(u, e)) u = e; });
  return u;
}
// El nombre de una persona: las iniciales del equipo tal cual; una escrita a mano, el de la lista o el de la semana
function plNom(per) {
  if (!PL_PER_MANO.test(per || '')) return per;
  const e = plManoUltimo('personas', per);
  if (e) return e.nombre;
  for (const s of planif.semanas.values()) if (s.ef.personas[per]) return s.ef.personas[per].nombre;
  return mayuscula(per.slice(2).replace(/-/g, ' '));
}
// Para las etiquetas chicas: «Juan Pérez» → «Juan P.»
function plNomCorto(per) {
  if (!PL_PER_MANO.test(per || '')) return per;
  const p = plNom(per).split(' ');
  return p.length > 1 ? p[0] + ' ' + p[1].charAt(0).toUpperCase() + '.' : p[0];
}
// El círculo de la fila: las iniciales («JP»)
const plIniciales = (per) => (PL_PER_MANO.test(per || '') ? plNom(per).split(' ').slice(0, 2).map((w) => w.charAt(0).toUpperCase()).join('') : per);
const plNoms = (xs) => unir(xs.map(plNom));
// Una persona escrita a mano vale en la semana s si es de esa semana o del personal definitivo desde antes (2026-11-13)
const plManoVale = (e, s) => e.activa && (e.fija ? e.semana <= s.id : e.semana === s.id);
// Las personas escritas a mano en la semana s, por nombre
const plManoActivas = (s) => [...new Set([...plLista().ef.personas.values()].filter((e) => plManoVale(e, s))
  .sort((a, b) => plComparar(a.nombre, b.nombre)).map((e) => e.id))];
// Su registro en la semana s: el definitivo primero, si no el de esa semana
const plManoDe = (s, id) => [plLista().ef.personas.get('fija|' + id), plLista().ef.personas.get(s.id + '|' + id)].find((e) => e && plManoVale(e, s)) || null;
// Los proyectos escritos a mano en la semana s
const plProyManoActivos = (s) => [...plLista().ef.proyectos.values()].filter((e) => e.activa && e.semana === s.id);

/* ---- Los proyectos dados por cerrados (2026-10-26) ----------------------------------------------------------------
   Pedido del usuario: un proyecto terminado y entregado que no pasó por el Formulador (solo «Adjudicado» en la
   Planilla de Ingreso, o con ficha en el Análisis Financiero sin el 100 %) no tenía cómo salir de la planificación.
   Darlo por cerrado lo lleva al «Cierre» del Recorrido (rcArmar → rcCerradoEnPlan) y así sale de los activos, en
   todas las semanas y para todo el equipo. Va en publicado/planificacion/cierres/<dispositivo>.json (esquema
   planificacion-cierres), un archivo por navegador como la lista; por cada clave (su N° y su TAG) manda el cambio
   más reciente, y reabrirlo es 'cerrado': false. */
function plCierres() {
  if (!planif.cierres) planif.cierres = { archivos: new Map(), mias: new Map(), ef: new Map(), leida: 0 };
  return planif.cierres;
}
function plLeerCierresArchivo(sobre) {
  const d = sobre && sobre.esquema === 'quempin.intercambio/1' && sobre.herramienta === 'planificacion' ? sobre.datos : null;
  if (!d || typeof d !== 'object') return null;
  const de = texto(d.dispositivo).slice(0, 24);
  const tope = new Date(Date.now() + 365 * DIA).toISOString();
  const instante = (x) => typeof x === 'string' && PL_INSTANTE.test(x) && x <= tope;
  const por = (x) => (/^[A-Z]{2,3}$/.test(texto(x)) ? texto(x) : '');
  const proyectos = new Map();
  (Array.isArray(d.proyectos) ? d.proyectos.slice(0, 2000) : []).forEach((x) => {
    if (!x || !PL_CLAVE_CIERRE.test(texto(x.clave)) || typeof x.cerrado !== 'boolean' || !instante(x.t)) return;
    plPoner(proyectos, x.clave, { clave: x.clave, titulo: plNombreLimpio(x.titulo), nota: plNota(x.nota), cerrado: x.cerrado, af: x.af === true,
      t: x.t, por: por(x.por), de });
  });
  return { proyectos, generado: texto(sobre.generado) };
}
const plNota = (v) => texto(v).replace(/\s+/g, ' ').trim().slice(0, 200);
function plRecalcularCierres() {
  const c = plCierres();
  const ef = new Map();
  [...c.archivos.values()].map((a) => a.proyectos).concat([c.mias]).forEach((m) => m.forEach((e, k) => plPoner(ef, k, e)));
  c.ef = ef;
}
function plAdoptarCierres(r) {
  const c = plCierres();
  r.proyectos.forEach((e, k) => plPoner(c.mias, k, e));
}
function plSobreCierres() {
  const sinDe = (e) => { const x = Object.assign({}, e); delete x.de; return x; };
  return {
    esquema: 'quempin.intercambio/1', herramienta: 'planificacion', tipo: 'planificacion-cierres',
    generado: new Date().toISOString(), autor: estado.usuario || '',
    datos: { dispositivo: plDispositivo(), proyectos: [...plCierres().mias.values()].map(sinDe) }
  };
}
// Lo lee el Recorrido junto con lo demás de la carpeta (rcLeer): devuelve lo vigente, clave → el último cambio
async function plLeerCierres(dir) {
  const c = plCierres();
  const carpeta = await plCarpeta(dir, PL_CIERRES, false);
  const vistos = new Set();
  if (carpeta) {
    for await (const [n, h] of carpeta.entries()) {
      if (h.kind !== 'file' || !/\.json$/i.test(n)) continue;
      vistos.add(n);
      let f;
      try { f = await h.getFile(); } catch (e) { continue; }
      const previo = c.archivos.get(n);
      if (previo && previo.lm === f.lastModified && previo.size === f.size) continue;
      let r = null;
      try { r = plLeerCierresArchivo(JSON.parse(rcSinBom(await f.text()))); } catch (e) { r = null; }   // a medio sincronizar
      if (!r) continue;
      r.lm = f.lastModified;
      r.size = f.size;
      c.archivos.set(n, r);
      r.proyectos.forEach((e) => { planif.reloj = Math.max(planif.reloj, Date.parse(e.t)); });
      if (n === plNombreArchivo()) plAdoptarCierres(r);
    }
  }
  c.archivos.forEach((x, n) => { if (!vistos.has(n)) c.archivos.delete(n); });
  c.leida = Date.now();
  plRecalcularCierres();
  return c.ef;
}
// Si alguien dio por cerrado o reabrió un proyecto: sale o vuelve a las listas, y eso lo arma el Recorrido.
async function plCierresCambiaron(dir) {
  const c = plCierres();
  if (!c.leida) return false;       // la primera lectura la hace el Recorrido
  const firma = () => [...c.archivos.values()].map((x) => x.lm + ':' + x.size).join();
  const antes = firma();
  await plLeerCierres(dir);
  return firma() !== antes;
}
async function plEscribirCierres(dir) {
  const c = plCierres();
  const carpeta = await plCarpeta(dir, PL_CIERRES, true);
  const nombre = plNombreArchivo();
  try {
    const f = await (await carpeta.getFileHandle(nombre)).getFile();
    const r = plLeerCierresArchivo(JSON.parse(rcSinBom(await f.text())));
    if (r) plAdoptarCierres(r);
  } catch (e) { /* todavía no existe */ }
  const sobre = plSobreCierres();
  await exigirEsquema(dir, 'planificacion-cierres', sobre);
  const h = await carpeta.getFileHandle(nombre, { create: true });
  const w = await h.createWritable();
  await w.write(JSON.stringify(sobre, null, 1));
  await w.close();
  const f = await h.getFile();
  const copia = plLeerCierresArchivo(sobre);
  copia.lm = f.lastModified;
  copia.size = f.size;
  c.archivos.set(nombre, copia);
  plRecalcularCierres();
}

// ---- Leer y guardar en la carpeta del equipo ---------------------------------------------------------------
const plNombreArchivo = () => plDispositivo() + '.json';
async function plCarpeta(dir, id, crear) {
  try {
    let d = await dir.getDirectoryHandle('publicado', { create: crear });
    d = await d.getDirectoryHandle('planificacion', { create: crear });
    return await d.getDirectoryHandle(id, { create: crear });
  } catch (e) {
    if (crear) throw e;
    return null;           // la semana aún no tiene nada
  }
}
// Lee una semana: solo los archivos que cambiaron desde la última vez. Devuelve si algo cambió.
async function plLeerSemana(dir, id) {
  const s = plSemana(id);
  const yaLeida = !!s.leida;
  const carpeta = await plCarpeta(dir, id, false);
  let cambio = !s.leida;
  const vistos = new Set();
  if (carpeta) {
    for await (const [n, h] of carpeta.entries()) {
      if (h.kind !== 'file' || !/\.json$/i.test(n)) continue;
      vistos.add(n);
      let f;
      try { f = await h.getFile(); } catch (e) { continue; }
      const previo = s.archivos.get(n);
      if (previo && previo.lm === f.lastModified && previo.size === f.size) continue;
      let r = null;
      try { r = plLeerArchivo(JSON.parse(rcSinBom(await f.text())), id, s.lunes); } catch (e) { r = null; }   // a medio sincronizar
      if (!r) continue;
      r.lm = f.lastModified;
      r.size = f.size;
      s.archivos.set(n, r);
      cambio = true;
      PL_TIPOS.forEach((tipo) => r[tipo].forEach((e) => { planif.reloj = Math.max(planif.reloj, Date.parse(e.t)); }));
      if (n === plNombreArchivo()) plAdoptar(s, r);
    }
  }
  s.archivos.forEach((x, n) => { if (!vistos.has(n)) { s.archivos.delete(n); cambio = true; } });
  s.leida = Date.now();
  if (cambio) {
    const antes = s.ef;
    plRecalcular(s);
    if (yaLeida) plNotarAjenos(s, antes);
  }
  return cambio;
}
/* Lo que acaba de llegar de otro computador: se ilumina y la línea de arriba dice quién fue. Lo de este navegador ya se
   vio al hacerlo, y una semana que recién se abre no cuenta: ahí todo sería nuevo. */
function plNotarAjenos(s, antes) {
  if (!planif.lunes || s.id !== plSemanaId(planif.lunes)) return;
  const yo = plDispositivo();
  const ajenos = [], pisados = [];
  PL_TIPOS.forEach((tipo) => s.ef[tipo].forEach((e, k) => {
    const a = antes[tipo].get(k);
    if (e.de === yo || (a && a.t === e.t)) return;
    ajenos.push(Object.assign({ tipo }, e));
    // Reemplaza algo que este navegador acababa de cambiar, con otro valor (2026-11-10)
    if (a && a.de === yo && plValor(tipo, a) !== plValor(tipo, e) && pisReciente(a, e)) pisados.push({ tipo, k, mio: a, suyo: e });
  }));
  if (!ajenos.length) return;
  const quien = [...new Set(ajenos.map((e) => e.por || 'Otro computador'))].join(', ');
  planif.ajeno = { quien, n: ajenos.length, cuando: Date.now() };
  plMarcarRecien(ajenos.filter((e) => e.tipo !== 'pau'), plModelo(s), true);
  if (!pisados.length) return;
  // Se suma a lo que ya avisaba en esa semana; de una misma casilla queda lo tuyo de antes del primer reemplazo
  const items = new Map((planif.pisado && planif.pisado.semana === s.id ? planif.pisado.items : []).map((x) => [x.tipo + '#' + x.k, x]));
  pisados.forEach((x) => { const v = items.get(x.tipo + '#' + x.k); items.set(x.tipo + '#' + x.k, v ? Object.assign({}, x, { mio: v.mio }) : x); });
  planif.pisado = { semana: s.id, items: [...items.values()] };
}
// Lo que cuenta de una casilla al comparar dos versiones
const plValor = (tipo, e) => (tipo === 'asig' ? String(e.activa) : tipo === 'aus' ? e.motivo : tipo === 'pau' ? e.activa + '|' + e.nota : e.vehiculo);
// Una línea de la franja: qué habías hecho y qué hizo el otro
function plPisadoTexto(s, m, x) {
  const { tipo, mio, suyo } = x;
  const per = mio.persona ? plNom(mio.persona) : '';
  const dia = mio.dia ? plElDia(plDiaDe(s, mio.dia)) : '';
  const proy = mio.proyecto ? m.titulo(m.canon(mio.proyecto)) : '';
  const quien = suyo.por || 'otro computador';
  if (tipo === 'asig') return mio.activa ? 'Asignaste a ' + per + ' ' + dia + ' en ' + proy + '; ' + quien + ' quitó esa asignación.'
    : 'Quitaste a ' + per + ' ' + dia + ' de ' + proy + '; ' + quien + ' volvió a poner esa asignación.';
  if (tipo === 'aus') {
    const nom = (id) => (PL_AUSENCIAS.find((a) => a.id === id) || { nombre: 'sin ausencia' }).nombre.toLowerCase();
    return per + ' ' + dia + ': pusiste «' + nom(mio.motivo) + '» y ' + quien + ' «' + nom(suyo.motivo) + '».';
  }
  if (tipo === 'pau') {
    if (mio.activa === suyo.activa) return proy + ': cambiaste la nota de «sin trabajo esta semana» y ' + quien + ' escribió otra.';
    return mio.activa ? 'Marcaste ' + proy + ' sin trabajo esta semana; ' + quien + ' lo desmarcó.' : 'Desmarcaste ' + proy + ' sin trabajo esta semana; ' + quien + ' lo volvió a marcar.';
  }
  const v = (id) => (plVehiculo(id) ? plLaVeh(plVehiculo(id)) : 'sin vehículo');
  return per + ' ' + dia + ' en ' + proy + ': pusiste ' + v(mio.vehiculo) + ' y ' + quien + ' ' + v(suyo.vehiculo) + '.';
}
function plPintarPisado() {
  const p = planif.pisado;
  if (!p || !planif.lunes || p.semana !== plSemanaId(planif.lunes)) { pisPintar($('#plPisado'), null); return; }
  const s = plSemana(p.semana);
  const m = plModelo(s);
  // El vehículo que se fue con una asignación no se cuenta aparte
  const asig = new Set(p.items.filter((x) => x.tipo === 'asig').map((x) => x.k));
  const lineas = p.items.filter((x) => !(x.tipo === 'veh' && asig.has(x.k))).map((x) => plPisadoTexto(s, m, x));
  pisPintar($('#plPisado'), { quien: pisQuien(p.items), lineas }, plVolverPisado, () => { planif.pisado = null; plPintarPisado(); });
}
// «Volver a lo mío»: lo tuyo vuelve como un cambio nuevo (le gana al del otro y le llega), en un paso de Deshacer
function plVolverPisado() {
  const p = planif.pisado;
  if (!p) return;
  planif.pisado = null;
  const s = plSemana(p.semana);
  const tanda = [];
  p.items.forEach(({ tipo, k, mio, suyo }) => {
    tanda.push({ tipo, e: sinMarca(suyo) });
    s.mias[tipo].set(k, Object.assign(sinMarca(mio), { t: plAhora(), por: estado.usuario || '', de: plDispositivo() }));
  });
  plRecalcular(s);
  planif.deshacer.push({ semana: s.id, tanda });
  if (planif.deshacer.length > 40) planif.deshacer.shift();
  plProgramarGuardado(s.id);
  plMarcarRecien(tanda.filter((x) => x.tipo !== 'pau').map((x) => x.e), plModelo(s));
  plPintar();
  plPintarAlarmaGlobal();
  avisar('Volvió lo tuyo; le llega a ' + pisQuien(p.items) + ' con OneDrive.', { texto: 'Deshacer', ir: plDeshacer });
}
// Lo mismo con la lista de lo agregado a mano
async function plLeerLista(dir) {
  const l = plLista();
  const carpeta = await plCarpeta(dir, PL_LISTA, false);
  let cambio = !l.leida;
  const vistos = new Set();
  if (carpeta) {
    for await (const [n, h] of carpeta.entries()) {
      if (h.kind !== 'file' || !/\.json$/i.test(n)) continue;
      vistos.add(n);
      let f;
      try { f = await h.getFile(); } catch (e) { continue; }
      const previo = l.archivos.get(n);
      if (previo && previo.lm === f.lastModified && previo.size === f.size) continue;
      let r = null;
      try { r = plLeerListaArchivo(JSON.parse(rcSinBom(await f.text()))); } catch (e) { r = null; }
      if (!r) continue;
      r.lm = f.lastModified;
      r.size = f.size;
      l.archivos.set(n, r);
      cambio = true;
      ['personas', 'proyectos'].forEach((k) => r[k].forEach((e) => { planif.reloj = Math.max(planif.reloj, Date.parse(e.t)); }));
      if (n === plNombreArchivo()) plAdoptarLista(r);
    }
  }
  l.archivos.forEach((x, n) => { if (!vistos.has(n)) { l.archivos.delete(n); cambio = true; } });
  l.leida = Date.now();
  if (cambio) plRecalcularLista();
  return cambio;
}
function plSobre(s) {
  const m = s.mias;
  const usados = new Set([...m.asig.values(), ...m.pau.values(), ...m.veh.values()].map((e) => e.proyecto));
  const proyectos = {};
  usados.forEach((k) => { const v = m.proyectos[k] || s.ef.proyectos[k]; if (v) proyectos[k] = v; });
  // El nombre de cada persona escrita a mano que aparece en el archivo: la semana se lee bien aunque la quiten de la lista
  const personas = {};
  [...m.asig.values(), ...m.aus.values(), ...m.veh.values()].forEach((e) => {
    if (PL_PER_MANO.test(e.persona) && !personas[e.persona]) personas[e.persona] = m.personas[e.persona] || s.ef.personas[e.persona] || { nombre: plNom(e.persona) };
  });
  const sinDe = (e) => { const x = Object.assign({}, e); delete x.de; return x; };   // el dispositivo ya va arriba
  return {
    esquema: 'quempin.intercambio/1', herramienta: 'planificacion', tipo: 'planificacion-semana',
    generado: new Date().toISOString(), autor: estado.usuario || '',
    datos: {
      semana: s.id, desde: plISO(s.lunes), dispositivo: plDispositivo(),
      asignaciones: [...m.asig.values()].map(sinDe), ausencias: [...m.aus.values()].map(sinDe), pausas: [...m.pau.values()].map(sinDe),
      vehiculos: [...m.veh.values()].map(sinDe), proyectos, personas
    }
  };
}
async function plEscribirLista(dir) {
  const l = plLista();
  const carpeta = await plCarpeta(dir, PL_LISTA, true);
  const nombre = plNombreArchivo();
  try {
    const f = await (await carpeta.getFileHandle(nombre)).getFile();
    const r = plLeerListaArchivo(JSON.parse(rcSinBom(await f.text())));
    if (r) plAdoptarLista(r);
  } catch (e) { /* todavía no existe */ }
  const sobre = plSobreLista();
  await exigirEsquema(dir, 'planificacion-lista', sobre);
  const h = await carpeta.getFileHandle(nombre, { create: true });
  const w = await h.createWritable();
  await w.write(JSON.stringify(sobre, null, 1));
  await w.close();
  const f = await h.getFile();
  const copia = plLeerListaArchivo(sobre);
  copia.lm = f.lastModified;
  copia.size = f.size;
  l.archivos.set(nombre, copia);
  plRecalcularLista();
}
async function plEscribirSemana(dir, id) {
  if (id === PL_LISTA) { await plEscribirLista(dir); return; }
  if (id === PL_CIERRES) { await plEscribirCierres(dir); return; }
  const s = plSemana(id);
  const carpeta = await plCarpeta(dir, id, true);
  const nombre = plNombreArchivo();
  // Otra pestaña de este mismo navegador pudo escribir el mismo archivo: lo suyo se suma antes de reemplazarlo.
  try {
    const f = await (await carpeta.getFileHandle(nombre)).getFile();
    const r = plLeerArchivo(JSON.parse(rcSinBom(await f.text())), id, s.lunes);
    if (r) plAdoptar(s, r);
  } catch (e) { /* todavía no existe */ }
  const sobre = plSobre(s);
  await exigirEsquema(dir, 'planificacion-semana', sobre);
  const h = await carpeta.getFileHandle(nombre, { create: true });
  const w = await h.createWritable();
  await w.write(JSON.stringify(sobre, null, 1));
  await w.close();
  const f = await h.getFile();
  const copia = plLeerArchivo(sobre, id, s.lunes);
  copia.lm = f.lastModified;
  copia.size = f.size;
  s.archivos.set(nombre, copia);
  plRecalcular(s);
}
// Lo que espera guardarse queda también en este navegador: si la página se cierra antes, se guarda la próxima vez.
function plGuardarPendiente() {
  const p = {};
  planif.porGuardar.forEach((id) => {
    if (id === PL_LISTA) { p[id] = plSobreLista().datos; return; }
    if (id === PL_CIERRES) { p[id] = plSobreCierres().datos; return; }
    const s = planif.semanas.get(id);
    if (s) p[id] = plSobre(s).datos;
  });
  try {
    if (Object.keys(p).length) localStorage.setItem(LS_PL_PENDIENTE, JSON.stringify(p));
    else localStorage.removeItem(LS_PL_PENDIENTE);
  } catch (e) { /* sin almacenamiento: solo en esta visita */ }
}
function plRecuperarPendiente() {
  let p = null;
  try { p = JSON.parse(localStorage.getItem(LS_PL_PENDIENTE) || 'null'); } catch (e) { p = null; }
  if (!p || typeof p !== 'object') return;
  Object.keys(p).forEach((id) => {
    if (id === PL_LISTA) {
      const r = plLeerListaArchivo({ esquema: 'quempin.intercambio/1', herramienta: 'planificacion', datos: p[id] });
      if (!r) return;
      plAdoptarLista(r);
      plRecalcularLista();
      planif.porGuardar.add(id);
      return;
    }
    if (id === PL_CIERRES) {
      const r = plLeerCierresArchivo({ esquema: 'quempin.intercambio/1', herramienta: 'planificacion', datos: p[id] });
      if (!r) return;
      plAdoptarCierres(r);
      plRecalcularCierres();
      planif.porGuardar.add(id);
      return;
    }
    const lunes = plLunesDeId(id);
    const r = lunes && plLeerArchivo({ esquema: 'quempin.intercambio/1', herramienta: 'planificacion', datos: p[id] }, id, lunes);
    if (!r) return;
    const s = plSemana(id);
    plAdoptar(s, r);
    plRecalcular(s);
    planif.porGuardar.add(id);
  });
}
function plProgramarGuardado(id) {
  planif.porGuardar.add(id);
  plGuardarPendiente();
  clearTimeout(planif.relojGuardar);
  planif.relojGuardar = setTimeout(plGuardar, 450);
  plPintarFrescura();
}
async function plGuardar() {
  if (soloLectura()) return;
  clearTimeout(planif.relojGuardar);
  if (planif.guardando) { planif.otraVez = true; return; }
  if (!planif.porGuardar.size) return;
  planif.guardando = true;
  planif.guardandoDesde = Date.now();
  plPintarFrescura();
  try {
    if (!rc.dir) throw new Error('La biblioteca del equipo no está conectada con permiso en este navegador.');
    /* Se saca de la lista antes de escribir: un cambio que llega mientras se escribe la vuelve a poner y se guarda en
       la vuelta siguiente (sacándola después, ese cambio quedaba fuera del archivo hasta el próximo, como marcar a
       alguien y tocar su vehículo enseguida). */
    for (const id of [...planif.porGuardar]) {
      planif.porGuardar.delete(id);
      try { await plEscribirSemana(rc.dir, id); } catch (e) { planif.porGuardar.add(id); throw e; }
    }
    planif.errorGuardar = null;
    planif.guardado = Date.now();
  } catch (e) {
    console.error(e);
    planif.errorGuardar = e;
    planif.falloGuardar = Date.now();
  }
  planif.guardando = false;
  plGuardarPendiente();
  plPintarFrescura();
  if (planif.otraVez) { planif.otraVez = false; plGuardar(); }
}

// ---- Los proyectos activos y lo que dice la semana -----------------------------------------------------------
// El lugar, legible («LLAY LLAY» → «Llay Llay») y solo si el nombre del proyecto no lo dice ya
function plLugar(titulo, lugar) {
  const l = rcLegible(lugar);
  return l && !norm(titulo).includes(norm(l)) ? l : '';
}
/* Los proyectos en ejecución del Recorrido y, después, los agregados a mano en la semana s (mano: true). Uno escrito
   con su N° que después entra en ejecución queda una sola vez, como el del Recorrido. */
function plActivos(s) {
  const vistos = new Set();
  const delRecorrido = rc.tarjetas.filter((t) => t.etapa === 'ejecucion' && !t.antiguo && (t.req || t.tag)).map((t) => ({
    clave: t.req ? 'req:' + t.req : 'tag:' + t.tag, req: t.req || null, tag: t.tag || null, titulo: t.titulo, lugar: plLugar(t.titulo, t.lugar), sitio: rcLegible(t.lugar),
    avance: typeof t.avance === 'number' ? t.avance : null, tarjeta: t.clave, activo: true, otra: false
  }));
  const aMano = plProyManoActivos(s).map((e) => {
    const req = e.clave.startsWith('req:') ? e.clave.slice(4) : null;
    const t = req ? rc.tarjetas.find((x) => x.req === req) : null;     // su tarjeta del Recorrido, aunque esté en otra etapa
    return { clave: e.clave, req, tag: (t && t.tag) || null, titulo: e.titulo, lugar: plLugar(e.titulo, e.lugar), sitio: e.lugar,
      avance: null, tarjeta: t ? t.clave : null, activo: true, otra: false, mano: true, cerrado: !!t && t.etapa === 'cierre' };
  }).filter((p) => !p.cerrado);       // cerrado (en el Formulador o con 100 % de avance): sale, como los del Recorrido
  return delRecorrido.concat(aMano).filter((p) => !vistos.has(p.clave) && vistos.add(p.clave)).sort(plPorTitulo);
}
const plComparar = (a, b) => a.localeCompare(b, 'es', { numeric: true, sensitivity: 'base' });
const plPorTitulo = (a, b) => plComparar(a.titulo, b.titulo);
// El equipo en su orden y, después, las personas escritas a mano por nombre
const plOrdenPersonas = (xs) => PERSONAL.filter((p) => xs.includes(p))
  .concat(xs.filter((p) => !PERSONAL.includes(p)).sort((a, b) => plComparar(plNom(a), plNom(b))));
// Un color por proyecto, el mismo en todas las vistas y semanas mientras no cambien los activos: sale de su clave y,
// si dos chocan, el segundo (en orden de clave) toma el siguiente libre. Con más de diez se repiten.
function plColores(claves) {
  const color = new Map(), usados = new Set();
  claves.slice().sort().forEach((c) => {
    let x = 0;
    for (let i = 0; i < c.length; i++) x = (x * 31 + c.charCodeAt(i)) >>> 0;
    let n = x % PL_COLORES;
    for (let k = 0; k < PL_COLORES && usados.has(n); k++) n = (n + 1) % PL_COLORES;
    usados.add(n);
    if (usados.size >= PL_COLORES) usados.clear();
    color.set(c, 'var(--pl-c' + n + ')');
  });
  return color;
}
/* Lo que dice la semana, unido con los proyectos activos de hoy. Una asignación hecha con el TAG de un proyecto que
   después recibió su N° (o al revés) sigue siendo del mismo proyecto: canon da la clave de hoy. */
function plModelo(s) {
  const activos = plActivos(s);
  const porReq = new Map(), porTag = new Map();
  activos.forEach((p) => { if (p.req) porReq.set(p.req, p); if (p.tag) porTag.set(p.tag, p); });
  const canon = (k) => {
    const p = k.startsWith('req:') ? porReq.get(k.slice(4)) : k.startsWith('tag:') ? porTag.get(k.slice(4)) : null;
    return p ? p.clave : k;
  };
  const proyectos = new Map(activos.map((p) => [p.clave, p]));
  const deLaSemana = (c, k) => {      // un proyecto que ya no está activo, o una otra actividad, con su nombre guardado
    if (proyectos.has(c)) return;
    const sn = s.ef.proyectos[k] || s.ef.proyectos[c] || plManoUltimo('proyectos', c) || {};
    const otra = c.startsWith('otra:');
    proyectos.set(c, { clave: c, req: sn.req || (c.startsWith('req:') ? c.slice(4) : null), tag: sn.tag || (c.startsWith('tag:') ? c.slice(4) : null),
      titulo: sn.titulo || (otra ? 'Otra actividad' : c.startsWith('req:') ? 'N° ' + c.slice(4) : c.slice(4)), lugar: sn.lugar || '', activo: false, otra, tarjeta: null });
  };
  const porPersona = new Map(), porProyecto = new Map(), dias = new Map();
  const sumar = (mapa, k, v) => { const l = mapa.get(k) || []; if (!l.includes(v)) l.push(v); mapa.set(k, l); };
  s.ef.asig.forEach((e) => {
    if (!e.activa) return;
    const c = canon(e.proyecto);
    deLaSemana(c, e.proyecto);
    sumar(porPersona, e.dia + '|' + e.persona, c);
    sumar(porProyecto, e.dia + '|' + c, e.persona);
    sumar(dias, c, e.dia);
  });
  const ausencias = new Map();
  s.ef.aus.forEach((e) => { if (e.motivo) ausencias.set(e.dia + '|' + e.persona, e); });
  /* Las filas de personas: el equipo, las escritas a mano en esta semana y las que se quitaron pero tienen algo en
     ella (así no se pierde lo asignado) */
  const enLaSemana = new Set();
  s.ef.asig.forEach((e) => { if (e.activa) enLaSemana.add(e.persona); });
  ausencias.forEach((e) => enLaSemana.add(e.persona));
  // Las que se ocultaron en «Personal» (2026-11-13) no tienen fila, salvo que tengan algo esa semana: nada asignado se pierde
  const personas = plOrdenPersonas([...new Set(PERSONAL.concat(plManoActivas(s)).filter((p) => !planif.ocultas.has(p)).concat([...enLaSemana]))]);
  const pausas = new Map();
  s.ef.pau.forEach((e) => { if (e.activa) pausas.set(canon(e.proyecto), e); });
  const colores = plColores([...proyectos.keys()]);
  const titulo = (c) => { const p = proyectos.get(c); const sn = s.ef.proyectos[c]; return (p && p.titulo) || (sn && sn.titulo) || (c.startsWith('otra:') ? 'Otra actividad' : c.slice(4)); };
  /* El vehículo de cada asignación (una persona en un proyecto un día): manda el cambio más reciente entre las claves
     del mismo proyecto (su TAG y su N°), y cuenta solo mientras la persona siga en ese proyecto ese día. */
  const vehMas = new Map();
  s.ef.veh.forEach((e) => { const k = e.dia + '|' + e.persona + '|' + canon(e.proyecto); if (plGana(vehMas.get(k), e)) vehMas.set(k, e); });
  const vehiculos = new Map();       // «dia|persona|clave» → el id del vehículo
  const porVeh = new Map();          // «dia|vehículo» → Map(clave → personas)
  vehMas.forEach((e, k) => {
    const c = canon(e.proyecto);
    if (!e.vehiculo || !(porPersona.get(e.dia + '|' + e.persona) || []).includes(c)) return;
    vehiculos.set(k, e.vehiculo);
    const l = porVeh.get(e.dia + '|' + e.vehiculo) || new Map();
    l.set(c, (l.get(c) || []).concat(e.persona));
    porVeh.set(e.dia + '|' + e.vehiculo, l);
  });
  // Cada vehículo, cada día, en grupos de los que viajan juntos (comparten algún proyecto en él): dos grupos son el
  // mismo vehículo en dos lugares a la vez. Los proyectos y los grupos, por nombre.
  const usoVeh = new Map();          // «dia|vehículo» → [[{ clave, personas }], …]
  porVeh.forEach((l, kv) => {
    const grupos = [];
    [...l.keys()].sort((a, b) => plComparar(titulo(a), titulo(b))).forEach((clave) => {
      const personas = l.get(clave);
      const juntos = grupos.filter((g) => g.some((x) => x.personas.some((p) => personas.includes(p))));
      juntos.forEach((g) => grupos.splice(grupos.indexOf(g), 1));
      grupos.push([].concat(...juntos, [{ clave, personas: plOrdenPersonas(personas) }]));
    });
    grupos.forEach((g) => g.sort((a, b) => plComparar(titulo(a.clave), titulo(b.clave))));
    usoVeh.set(kv, grupos.sort((a, b) => plComparar(titulo(a[0].clave), titulo(b[0].clave))));
  });
  return {
    activos, proyectos, canon, porPersona, porProyecto, dias, ausencias, pausas, titulo, personas,
    color: (c) => (c.startsWith('otra:') ? 'var(--baseline)' : colores.get(c) || 'var(--baseline)'),
    ordenar: (claves) => claves.slice().sort((a, b) => plComparar(titulo(a), titulo(b))),
    vehiculo: (dia, per, c) => vehiculos.get(dia + '|' + per + '|' + c) || '',
    usoVeh: (dia, id) => usoVeh.get(dia + '|' + id) || [],
    // Los grupos que llevan ese vehículo ese día a otra parte: ni van a ese proyecto ni llevan a esa persona
    vehOtros: (dia, id, per, c) => (usoVeh.get(dia + '|' + id) || []).filter((g) => !g.some((x) => x.clave === c || x.personas.includes(per))),
    // La alarma: un proyecto activo sin nadie ningún día de la semana, salvo que esa semana no se trabaje en él
    sinAsignar: activos.filter((p) => !dias.has(p.clave) && !pausas.has(p.clave))
  };
}

// ---- Cambiar la semana --------------------------------------------------------------------------------------
// El nombre del proyecto va en el archivo junto a lo asignado: la semana se sigue leyendo bien cuando el proyecto terminó.
function plNombrar(s, m, clave) {
  const p = m.proyectos.get(clave) || {};
  const sn = s.ef.proyectos[clave] || {};
  s.mias.proyectos[clave] = { titulo: p.titulo || sn.titulo || m.titulo(clave), lugar: p.lugar || sn.lugar || '', req: p.req || sn.req || null, tag: p.tag || sn.tag || null };
}
/* Cada cambio: { tipo: 'asig', dia, persona, clave, activa }, { tipo: 'aus', dia, persona, motivo }, { tipo: 'pau',
   clave, activa, nota } o { tipo: 'veh', dia, persona, clave, vehiculo } ('' lo quita), con la clave de hoy del
   proyecto. Queda como lo de este navegador, con su instante; se guarda en la carpeta y se puede deshacer (Ctrl Z o
   el aviso). Devuelve si algo cambió. */
function plCambiar(s, cambios, mensaje) {
  if (mvNoSe()) return;
  const m = plModelo(s);
  const tanda = [];
  const poner = (tipo, e, antes) => {
    tanda.push({ tipo, e: Object.assign({}, e, antes) });
    s.mias[tipo].set(plK(tipo, e), Object.assign({}, e, { t: plAhora(), por: estado.usuario || '', de: plDispositivo() }));
    // Lo que vuelves a cambiar sale de la franja de lo reemplazado: «Volver a lo mío» ya no lo tocaría
    if (planif.pisado && planif.pisado.semana === s.id) {
      planif.pisado.items = planif.pisado.items.filter((x) => !(x.tipo === tipo && x.k === plK(tipo, e)));
      if (!planif.pisado.items.length) planif.pisado = null;
    }
    plRecalcular(s);
  };
  // El vehículo de una casilla tal como va quedando la tanda, también si ya no está asignada: el cambio más reciente
  // entre las claves del mismo proyecto
  const vehDe = (dia, per, clave) => {
    let u = null;
    s.ef.veh.forEach((e) => { if (e.dia === dia && e.persona === per && m.canon(e.proyecto) === clave && plGana(u, e)) u = e; });
    return u ? u.vehiculo : '';
  };
  // Una asignación que se pone o se quita queda sin vehículo (uno que quedó de antes no vuelve a aparecer)
  const sinVeh = (dia, per, clave) => {
    const v = vehDe(dia, per, clave);
    if (v) poner('veh', { dia, persona: per, proyecto: clave, vehiculo: '' }, { vehiculo: v });
  };
  cambios.forEach((c) => {
    // El nombre de una persona escrita a mano va en el archivo de la semana junto a lo suyo
    if (c.persona && PL_PER_MANO.test(c.persona)) s.mias.personas[c.persona] = { nombre: plNom(c.persona) };
    if (c.tipo === 'asig') {
      const iguales = [...s.ef.asig.values()].filter((e) => e.activa && e.dia === c.dia && e.persona === c.persona && m.canon(e.proyecto) === c.clave);
      if (c.activa && !iguales.length) {
        plNombrar(s, m, c.clave);
        poner('asig', { dia: c.dia, persona: c.persona, proyecto: c.clave, activa: true }, { activa: false });
        sinVeh(c.dia, c.persona, c.clave);
      } else if (!c.activa && iguales.length) {
        iguales.forEach((x) => poner('asig', { dia: x.dia, persona: x.persona, proyecto: x.proyecto, activa: false }, { activa: true }));
        sinVeh(c.dia, c.persona, c.clave);
      }
    } else if (c.tipo === 'veh') {
      const antes = vehDe(c.dia, c.persona, c.clave);
      if (antes !== c.vehiculo) poner('veh', { dia: c.dia, persona: c.persona, proyecto: c.clave, vehiculo: c.vehiculo }, { vehiculo: antes });
    } else if (c.tipo === 'aus') {
      const previo = s.ef.aus.get(c.dia + '|' + c.persona);
      const antes = previo ? previo.motivo : '';
      if (antes !== c.motivo) poner('aus', { dia: c.dia, persona: c.persona, motivo: c.motivo }, { motivo: antes });
    } else if (c.tipo === 'pau') {
      const iguales = [...s.ef.pau.values()].filter((e) => e.activa && m.canon(e.proyecto) === c.clave);
      if (c.activa && !iguales.length) {
        plNombrar(s, m, c.clave);
        poner('pau', { proyecto: c.clave, activa: true, nota: texto(c.nota).slice(0, 120) }, { activa: false, nota: '' });
      } else if (!c.activa) {
        iguales.forEach((x) => poner('pau', { proyecto: x.proyecto, activa: false, nota: '' }, { activa: true, nota: x.nota }));
      }
    }
  });
  if (!tanda.length) { plPintar(); return false; }
  planif.deshacer.push({ semana: s.id, tanda });
  if (planif.deshacer.length > 40) planif.deshacer.shift();
  plProgramarGuardado(s.id);
  plMarcarRecien(tanda.filter((x) => x.tipo !== 'pau').map((x) => x.e), m);
  plPintar();
  plPintarAlarmaGlobal();
  if (mensaje) avisar(typeof mensaje === 'function' ? mensaje() : mensaje, { texto: 'Deshacer', ir: plDeshacer });
  return true;
}
// Las casillas de la última tanda se iluminan un momento al repintarse: se ve qué llenó «Toda la semana» o varios días.
function plMarcarRecien(es, m, ajeno) {
  planif.recien = new Set(es.flatMap((e) => ['p|' + e.persona + '|' + e.dia].concat(e.proyecto ? ['j|' + m.canon(e.proyecto) + '|' + e.dia] : [])));
  planif.recienAjeno = !!ajeno;
  clearTimeout(planif.relojRecien);
  planif.relojRecien = setTimeout(() => { planif.recien = new Set(); }, ajeno ? 6000 : 1800);
}
function plDeshacer() {
  const u = planif.deshacer.pop();
  if (!u) { avisar('No hay cambios de la planificación para deshacer.'); return; }
  if (u.cierres) { plDeshacerCierre(u); return; }
  // Agregar o quitar una persona o un proyecto escrito a mano (también los que «Copiar la semana anterior» trajo)
  (u.listas || []).forEach(({ tipo, e }) => plPonerLista(tipo, e));
  if (u.listas) plRecalcularLista();
  if (!u.tanda) {
    plPintar();
    plPintarAlarmaGlobal();
    avisar('Se deshizo el último cambio.');
    return;
  }
  const s = plSemana(u.semana);
  u.tanda.slice().reverse().forEach(({ tipo, e }) => {
    s.mias[tipo].set(plK(tipo, e), Object.assign({}, e, { t: plAhora(), por: estado.usuario || '', de: plDispositivo() }));
  });
  plRecalcular(s);
  plProgramarGuardado(s.id);
  plMarcarRecien(u.tanda.filter((x) => x.tipo !== 'pau').map((x) => x.e), plModelo(s));
  plPintar();
  plPintarAlarmaGlobal();
  avisar('Se deshizo el último cambio' + (planif.lunes && s.id !== plSemanaId(planif.lunes) ? ', de la semana ' + plNum(s) : '') + '.');
}
const plSemanaVista = () => plSemana(plSemanaId(planif.lunes || plLunesDe(new Date())));
/* Unos días de la semana, para los avisos: «el lunes 19», «el lunes y el jueves», «de lunes a viernes» (tres o más
   seguidos), «el lunes, el miércoles y el viernes». */
function plDiasTexto(s, isos) {
  const ds = [...new Set(isos)].map((iso) => plDiaDe(s, iso)).sort((a, b) => a.i - b.i);
  if (ds.length === 1) return plElDia(ds[0]);
  if (ds.length >= 3 && ds[ds.length - 1].i - ds[0].i === ds.length - 1) return 'de ' + ds[0].nombre.toLowerCase() + ' a ' + ds[ds.length - 1].nombre.toLowerCase();
  return unir(ds.map((d) => 'el ' + d.nombre.toLowerCase()));
}
/* Asignar (si) o quitar a una persona en un proyecto, uno o varios días, en una sola tanda: un aviso y un «Deshacer».
   Se salta lo que no se puede (una ausencia, o el máximo de 3) y el aviso lo dice. Con un solo día bloqueado, el aviso
   explica qué hacer. Asignar le quita al proyecto la marca «sin trabajo esta semana». Devuelve si algo cambió. */
function plAsignarDias(s, per, clave, isos, si) {
  const m = plModelo(s);
  const cambios = [], no = [];
  isos.forEach((iso) => {
    const k = iso + '|' + per;
    const suyos = m.porPersona.get(k) || [];
    const ya = suyos.includes(clave);
    if (!si) { if (ya) cambios.push({ tipo: 'asig', dia: iso, persona: per, clave, activa: false }); return; }
    const aus = m.ausencias.get(k);
    if (ya) return;
    if (aus) no.push({ iso, por: plAusencia(aus.motivo).nombre.toLowerCase() });
    else if (suyos.length >= PL_MAX) no.push({ iso, por: 'ya tiene ' + PL_MAX + ' proyectos' });
    else cambios.push({ tipo: 'asig', dia: iso, persona: per, clave, activa: true });
  });
  const dias = cambios.map((c) => c.dia);        // el aviso dice solo los días que cambian
  const t = m.titulo(clave);
  if (!cambios.length) {
    if (no.length === 1 && isos.length === 1) {
      const d = plDiaDe(s, no[0].iso);
      avisar(m.ausencias.has(no[0].iso + '|' + per) ? plNom(per) + ' está ausente ' + plElDia(d) + ': quita la ausencia para asignarle un proyecto.'
        : plNom(per) + ' ya tiene ' + PL_MAX + ' proyectos ' + plElDia(d) + ', el máximo: quita uno para agregar otro.');
    } else if (no.length) avisar('No se puede asignar a ' + plNom(per) + ' en ' + t + ': ' + unir(no.map((x) => plElDia(plDiaDe(s, x.iso)) + ' (' + x.por + ')')) + '.');
    plPintar();
    return false;
  }
  let extra = '';
  if (si && m.pausas.has(clave)) { cambios.push({ tipo: 'pau', clave, activa: false }); extra = ' Ya no está «sin trabajo esta semana».'; }
  const salvo = no.length ? ', salvo ' + unir(no.map((x) => plElDia(plDiaDe(s, x.iso)) + ' (' + x.por + ')')) : '';
  return plCambiar(s, cambios, si ? plNom(per) + ' va a ' + t + ' ' + plDiasTexto(s, dias) + salvo + '.' + extra
    : plNom(per) + ' ya no va a ' + t + ' ' + plDiasTexto(s, dias) + '.');
}
/* El vehículo de una persona en un proyecto, los días elegidos en que va ('' lo quita), en una sola tanda. Si ese
   vehículo ya va con otros a otro lugar alguno de esos días, el aviso lo dice (no se impide: pueden ir pasando). */
function plVehiculoDias(s, per, clave, isos, id) {
  const m = plModelo(s);
  const dias = isos.filter((iso) => (m.porPersona.get(iso + '|' + per) || []).includes(clave) && m.vehiculo(iso, per, clave) !== id);
  if (!dias.length) return false;
  const v = plVehiculo(id);
  const antes = [...new Set(dias.map((iso) => m.vehiculo(iso, per, clave)).filter(Boolean))].map(plVehiculo).filter(Boolean);
  const t = m.titulo(clave);
  return plCambiar(s, dias.map((iso) => ({ tipo: 'veh', dia: iso, persona: per, clave, vehiculo: id })), () => {
    const cuando = plDiasTexto(s, dias);
    if (!v) return plNom(per) + ' ya no lleva ' + unir(antes.map(plLaVeh)) + ' a ' + t + ' ' + cuando + '.';
    const mm = plModelo(s);
    const choques = dias.map((iso) => ({ iso, otros: mm.vehOtros(iso, id, per, clave) })).filter((x) => x.otros.length);
    const donde = [...new Set(choques.flatMap((x) => x.otros.flat().map((y) => mm.titulo(y.clave) + ' (' + plNoms(y.personas) + ')')))];
    return plNom(per) + ' va en ' + plLaVeh(v) + ' a ' + t + ' ' + cuando + '.'
      + (choques.length ? ' Ojo: ' + plDiasTexto(s, choques.map((x) => x.iso)) + ' ' + plLaVeh(v) + ' también va a ' + unir(donde) + '.' : '');
  });
}
/* Un vehículo ('' lo quita) a quienes van a un proyecto un día, en una tanda (arrastrado desde el panel, 2026-11-12).
   pares: [{ per, clave }]. Uno solo es como elegirlo en la ventanita; varios (la casilla de un proyecto), todos juntos. */
function plVehiculoPoner(s, id, iso, pares) {
  if (pares.length === 1) return plVehiculoDias(s, pares[0].per, pares[0].clave, [iso], id);
  const m = plModelo(s);
  const cambia = pares.filter((p) => m.vehiculo(iso, p.per, p.clave) !== id);
  if (!cambia.length) return false;
  const v = plVehiculo(id);
  const pers = cambia.map((p) => p.per);
  const claves = [...new Set(cambia.map((p) => p.clave))];
  const t = unir(claves.map((c) => m.titulo(c)));
  const dia = plElDia(plDiaDe(s, iso));
  return plCambiar(s, cambia.map((p) => ({ tipo: 'veh', dia: iso, persona: p.per, clave: p.clave, vehiculo: id })), () => {
    if (!v) return plNoms(pers) + (pers.length > 1 ? ' ya no llevan' : ' ya no lleva') + ' vehículo a ' + t + ' ' + dia + '.';
    const mm = plModelo(s);
    const otros = mm.vehOtros(iso, id, pers[0], claves[0]);
    const donde = [...new Set(otros.flat().map((y) => mm.titulo(y.clave) + ' (' + plNoms(y.personas) + ')'))];
    return plNoms(pers) + (pers.length > 1 ? ' van' : ' va') + ' en ' + plLaVeh(v) + ' a ' + t + ' ' + dia + '.'
      + (donde.length ? ' Ojo: ese día ' + plLaVeh(v) + ' también va a ' + unir(donde) + '.' : '');
  });
}
/* Cambiar a una persona de un proyecto a otro, los días en que estaba, en un paso: se quita y se pone en la misma
   tanda, así también sirve con el día completo (3 proyectos). Si ese día ya iba al otro, solo se quita del primero.
   El vehículo que llevaba se va con ella al otro proyecto, salvo que allá ya lleve uno. */
function plCambiarPor(s, per, de, a, isos) {
  const m = plModelo(s);
  const suyos = (iso) => m.porPersona.get(iso + '|' + per) || [];
  const dias = isos.filter((iso) => suyos(iso).includes(de));
  if (!dias.length || dias.every((iso) => suyos(iso).includes(a))) { avisar(plNom(per) + ' ya va a ' + m.titulo(a) + ' esos días.'); return false; }
  const cambios = dias.flatMap((iso) => {
    const ya = suyos(iso).includes(a);
    const v = m.vehiculo(iso, per, de);
    return [{ tipo: 'asig', dia: iso, persona: per, clave: de, activa: false }]
      .concat(ya ? [] : [{ tipo: 'asig', dia: iso, persona: per, clave: a, activa: true }])
      .concat(v && !(ya && m.vehiculo(iso, per, a)) ? [{ tipo: 'veh', dia: iso, persona: per, clave: a, vehiculo: v }] : []);
  });
  if (m.pausas.has(a)) cambios.push({ tipo: 'pau', clave: a, activa: false });
  return plCambiar(s, cambios, plNom(per) + ' cambia de ' + m.titulo(de) + ' a ' + m.titulo(a) + ' ' + plDiasTexto(s, dias) + '.');
}
/* Lo mismo desde el proyecto: en vez de una persona va otra, los días en que iba la primera (si la otra ya iba, solo
   se quita la primera). Se saltan los días en que la otra está ausente o tiene 3 proyectos: ahí sigue la primera, y
   el aviso lo dice. El vehículo de la primera pasa a la otra, si ella no lleva uno a ese proyecto. */
function plReemplazar(s, clave, de, a, isos) {
  const m = plModelo(s);
  const dias = [], no = [], cambios = [];
  let pone = 0;
  isos.forEach((iso) => {
    const van = m.porProyecto.get(iso + '|' + clave) || [];
    if (!van.includes(de)) return;
    const aus = m.ausencias.get(iso + '|' + a);
    const dia = plElDia(plDiaDe(s, iso));
    if (van.includes(a)) cambios.push({ tipo: 'asig', dia: iso, persona: de, clave, activa: false });
    else if (aus) { no.push({ dia, por: plAusencia(aus.motivo).nombre.toLowerCase() }); return; }
    else if ((m.porPersona.get(iso + '|' + a) || []).length >= PL_MAX) { no.push({ dia, por: 'ya tiene ' + PL_MAX + ' proyectos' }); return; }
    else { pone++; cambios.push({ tipo: 'asig', dia: iso, persona: de, clave, activa: false }, { tipo: 'asig', dia: iso, persona: a, clave, activa: true }); }
    const v = m.vehiculo(iso, de, clave);
    if (v && !m.vehiculo(iso, a, clave)) cambios.push({ tipo: 'veh', dia: iso, persona: a, clave, vehiculo: v });
    dias.push(iso);
  });
  const t = m.titulo(clave);
  if (!pone) { avisar(no.length ? plNom(a) + ' no puede ir a ' + t + ': ' + unir(no.map((x) => x.dia + ' (' + x.por + ')')) + '.' : plNom(a) + ' ya va a ' + t + ' esos días.'); return false; }
  return plCambiar(s, cambios, plNom(a) + ' va a ' + t + ' en vez de ' + plNom(de) + ' ' + plDiasTexto(s, dias)
    + (no.length ? '; ' + plNom(de) + ' sigue ' + unir(no.map((x) => x.dia + ' (' + plNom(a) + ': ' + x.por + ')')) : '') + '.');
}
// Una ausencia (vacaciones, licencia, permiso…) deja a la persona sin proyectos esos días; motivo '' la quita.
function plAusentarDias(s, isos, per, motivo) {
  const m = plModelo(s);
  const cambios = [], quitados = new Set();
  isos.forEach((iso) => {
    cambios.push({ tipo: 'aus', dia: iso, persona: per, motivo });
    if (motivo) (m.porPersona.get(iso + '|' + per) || []).forEach((c) => { quitados.add(c); cambios.push({ tipo: 'asig', dia: iso, persona: per, clave: c, activa: false }); });
  });
  return plCambiar(s, cambios, motivo
    ? plNom(per) + ' queda ausente ' + plDiasTexto(s, isos) + ' (' + plAusencia(motivo).nombre.toLowerCase() + ')' + (quitados.size ? '; se quitó de ' + unir([...quitados].map(m.titulo)) : '') + '.'
    : plNom(per) + ' ya no está ausente ' + plDiasTexto(s, isos) + '.');
}
// «Sin trabajo esta semana»: el proyecto sigue activo, pero esa semana no se trabaja en él y no cuenta como alarma.
function plPausar(s, clave, si) {
  const m = plModelo(s);
  plCambiar(s, [{ tipo: 'pau', clave, activa: si }], si ? m.titulo(clave) + ' queda sin trabajo ' + plEsta(s) + ': ya no cuenta como alarma.'
    : m.titulo(clave) + ' vuelve a planificarse ' + plEsta(s) + '.');
}
// Otra actividad (oficina, visita técnica, bodega): una clave propia con su nombre, que cuenta como un proyecto más del día.
function plClaveOtra(s, txt) {
  const nombre = texto(txt).replace(/\s+/g, ' ').slice(0, 60);
  const base = norm(nombre).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40).replace(/-+$/, '');
  if (!base) return null;
  const clave = 'otra:' + base;
  if (!s.ef.proyectos[clave]) {
    s.mias.proyectos[clave] = { titulo: nombre.charAt(0).toUpperCase() + nombre.slice(1), lugar: '', req: null, tag: null };
    plRecalcular(s);
  }
  return clave;
}
function plOtra(s, isos, per, txt) {
  const c = plClaveOtra(s, txt);
  if (!c) { avisar('Escribe qué actividad es: oficina, visita técnica, bodega…'); return; }
  plAsignarDias(s, per, c, isos, true);
}
/* Agregar a mano (2026-10-26): una persona por su nombre (alguien de apoyo, un contratista) o un proyecto que no está en
   ejecución en el Recorrido. Es temporal: queda solo en la semana a la vista; quitarlo no borra lo ya asignado.
   tipo: 'personas' | 'proyectos'; e: la persona { id, nombre, semana, activa } o el proyecto { clave, titulo, lugar,
   semana, activa }. plPonerLista lo deja como de este navegador y devuelve cómo deshacerlo (falta plRecalcularLista). */
function plPonerLista(tipo, e) {
  const l = plLista();
  const previo = l.ef[tipo].get(plKLista(e));
  const sinMeta = (x) => { const y = Object.assign({}, x); delete y.t; delete y.por; delete y.de; return y; };
  l.mias[tipo].set(plKLista(e), Object.assign({}, e, { t: plAhora(), por: estado.usuario || '', de: plDispositivo() }));
  plProgramarGuardado(PL_LISTA);
  return { tipo, e: previo ? sinMeta(previo) : Object.assign({}, e, { activa: false }) };
}
// Un cambio de la lista con su aviso; se puede deshacer desde el aviso o con Ctrl Z
function plCambiarLista(tipo, e, mensaje) {
  if (mvNoSe()) return;
  const antes = plPonerLista(tipo, e);
  plRecalcularLista();
  planif.deshacer.push({ listas: [antes] });
  if (planif.deshacer.length > 40) planif.deshacer.shift();
  plPintar();
  plPintarAlarmaGlobal();
  avisar(mensaje, { texto: 'Deshacer', ir: plDeshacer });
}
// «juan pérez» → «Juan Pérez»: cada palabra escrita toda en minúsculas parte con mayúscula
const plCapital = (txt) => txt.split(' ').map((w) => (w === w.toLowerCase() ? mayuscula(w) : w)).join(' ');
// fija: al personal definitivo, desde la semana a la vista en adelante (2026-11-13); si no, solo en esa semana
function plAgregarPersona(txt, aviso = avisar, fija = false) {
  const s = plSemanaVista();
  const nombre = plCapital(plNombreLimpio(txt));
  const delEquipo = PERSONAL.find((p) => p === nombre.toUpperCase());
  if (delEquipo) { aviso(delEquipo + ' ya está en la planificación.'); return null; }
  const slug = plSlug(nombre, 30);
  if (!slug) { aviso('Escribe el nombre de la persona.'); return null; }
  const id = 'x-' + slug;
  const yaFija = plLista().ef.personas.get('fija|' + id);
  planif.ocultas.delete(id);
  if (fija) {
    if (yaFija && plManoVale(yaFija, s)) { aviso(plNom(id) + ' ya está en el personal definitivo.'); return id; }
    plGuardarPrefs();
    plCambiarLista('personas', { id, nombre, semana: s.id, fija: true, activa: true },
      nombre + ' queda en el personal desde ' + plEsta(s) + ', también en las semanas siguientes.');
    return id;
  }
  plGuardarPrefs();
  if (plManoActivas(s).includes(id)) { aviso(plNom(id) + ' ya está en ' + plEsta(s) + '.'); return id; }
  plCambiarLista('personas', { id, nombre, semana: s.id, activa: true },
    nombre + ' queda solo en ' + plEsta(s) + ': toca su fila en «Por personal» para asignarle proyectos.');
  return id;
}
// Un N° de requerimiento de la Planilla de Ingreso: su nombre, el de su tarjeta del Recorrido o el de la Planilla
function plNombreReq(n) {
  const t = rc.tarjetas.find((x) => x.req === n);
  if (t) return t.titulo;
  const r = rc.datos && rc.datos.requerimientos.find((x) => rcNum(x && x.numero) === n);
  return r ? rcLegible(r.titulo) || 'Requerimiento ' + n : null;
}
/* Con su N° de la Planilla adelante («281. H2 Green», «N° 281») queda unido a ese requerimiento: si después entra en
   ejecución en el Recorrido, es el mismo proyecto. Si no, una clave propia sale de su nombre. Devuelve la clave. */
function plAgregarProyecto(txt, lugarTxt, aviso = avisar) {
  const s = plSemanaVista();
  let titulo = plNombreLimpio(txt);
  const lugar = plNombreLimpio(lugarTxt);
  if (!titulo) { aviso('Escribe el nombre del proyecto.'); return null; }
  const n = /^(?:n\s*°?\s*)?(\d{1,6})(?=$|[\s.\-–:])[\s.\-–:]*(.*)$/i.exec(titulo);
  const req = n && rcNum(n[1]);
  let clave;
  if (req && plNombreReq(req)) {
    clave = 'req:' + req;
    titulo = plNombreLimpio(n[2]) || plNombreReq(req);
  } else {
    const slug = plSlug(titulo, 40);
    if (!slug) { aviso('Escribe el nombre del proyecto.'); return null; }
    clave = 'pro:' + slug;
  }
  titulo = mayuscula(titulo);
  const ya = plActivos(s).find((p) => p.clave === clave || (!req && norm(p.titulo) === norm(titulo)));
  if (ya) { aviso(ya.titulo + (ya.mano ? ' ya está en ' + plEsta(s) + '.' : ' ya está en la planificación.')); return ya.clave; }
  plCambiarLista('proyectos', { clave, titulo, lugar, semana: s.id, activa: true },
    titulo + ' queda solo en ' + plEsta(s) + ', como un proyecto activo más.');
  return clave;
}
function plQuitarPersona(id) {
  const s = plSemanaVista();
  const e = plManoDe(s, id);
  if (!e) return;
  if (e.fija) {
    plCambiarLista('personas', { id, nombre: e.nombre, semana: e.semana, fija: true, activa: false },
      e.nombre + ' ya no está en el personal definitivo. Lo que tenía asignado se sigue viendo.');
    return;
  }
  plCambiarLista('personas', { id, nombre: e.nombre, semana: s.id, activa: false }, e.nombre + ' ya no está en ' + plEsta(s) + '. Lo que tenía asignado se sigue viendo.');
}
function plQuitarProyecto(clave) {
  const s = plSemanaVista();
  const e = plLista().ef.proyectos.get(s.id + '|' + clave);
  if (!e || !e.activa) return;
  plCambiarLista('proyectos', { clave, titulo: e.titulo, lugar: e.lugar, semana: s.id, activa: false },
    e.titulo + ' ya no está en ' + plEsta(s) + '. Lo asignado se sigue viendo.');
}
/* Copia lo de la semana anterior, día por día, sin borrar nada de esta: lo que ya no se puede (un proyecto que terminó,
   una ausencia o un día con 3 proyectos) se salta y se cuenta. Cada asignación copiada lleva su vehículo, y las
   personas y proyectos agregados a mano que van en ella pasan también a esta semana (son temporales: solo así siguen). */
async function plCopiarAnterior() {
  if (!rc.dir || mvNoSe()) return;
  const s = plSemanaVista();
  const antes = plSemana(plSemanaId(plMas(s.lunes, -7)));
  try { await plLeerSemana(rc.dir, antes.id); } catch (e) { avisar('No se pudo leer la semana anterior: ' + (e.message || e)); return; }
  const ma = plModelo(antes), m = plModelo(s);
  const cambios = [], cuenta = new Map();
  let total = 0, saltados = 0, copiadas = 0, vehiculos = 0;
  [...ma.porPersona.keys()].sort().forEach((k) => {
    const [diaAntes, per] = k.split('|');
    const iso = plISO(plMas(plDesdeISO(diaAntes), 7));
    const kk = iso + '|' + per;
    ma.porPersona.get(k).forEach((c) => {
      total++;
      const suyos = m.porPersona.get(kk) || [];
      if (suyos.includes(c)) return;
      const p = ma.proyectos.get(c);
      const n = cuenta.has(kk) ? cuenta.get(kk) : suyos.length;
      if (!(p && (p.activo || p.otra)) || m.ausencias.has(kk) || n >= PL_MAX) { saltados++; return; }
      cuenta.set(kk, n + 1);
      if (p.otra && !s.ef.proyectos[c]) s.mias.proyectos[c] = antes.ef.proyectos[c] || { titulo: p.titulo, lugar: '', req: null, tag: null };
      cambios.push({ tipo: 'asig', dia: iso, persona: per, clave: c, activa: true });
      copiadas++;
      const v = ma.vehiculo(diaAntes, per, c);
      if (v) { vehiculos++; cambios.push({ tipo: 'veh', dia: iso, persona: per, clave: c, vehiculo: v }); }
    });
  });
  const n = plNum(antes);
  if (!total) { avisar('La semana ' + n + ' no tiene asignaciones para copiar.'); return; }
  if (!cambios.length) { avisar('Lo de la semana ' + n + ' ya está en esta' + (saltados ? ', salvo ' + pl(saltados, 'asignación que no se puede copiar', 'asignaciones que no se pueden copiar') : '') + '.'); return; }
  // Lo agregado a mano que va en lo copiado (en la semana anterior, aunque después lo quitaran) pasa a esta
  const listas = [];
  const llevar = (tipo, k) => {
    const e = plLista().ef[tipo].get(antes.id + '|' + k), ya = plLista().ef[tipo].get(s.id + '|' + k);
    if (!e || (ya && ya.activa)) return;
    const x = Object.assign({}, e, { semana: s.id, activa: true });
    delete x.t; delete x.por; delete x.de;
    listas.push(plPonerLista(tipo, x));
  };
  const copiado = cambios.filter((c) => c.tipo === 'asig');
  new Set(copiado.map((c) => c.persona)).forEach((per) => { if (PL_PER_MANO.test(per)) llevar('personas', per); });
  new Set(copiado.map((c) => c.clave)).forEach((c) => { if (ma.proyectos.get(c).mano) llevar('proyectos', c); });
  if (listas.length) plRecalcularLista();
  plRecalcular(s);
  const hecho = plCambiar(s, cambios, (copiadas === 1 ? 'Se copió 1 asignación' : 'Se copiaron ' + copiadas + ' asignaciones') + ' de la semana ' + n
    + (vehiculos ? ' (' + (vehiculos === copiadas ? (copiadas === 1 ? 'con su vehículo' : 'con sus vehículos') : pl(vehiculos, 'con vehículo', 'con vehículo')) + ')' : '')
    + (saltados ? '; ' + saltados + ' no (proyecto terminado, ausencia o día con 3 proyectos)' : '') + '.');
  if (hecho && listas.length) planif.deshacer[planif.deshacer.length - 1].listas = listas;     // un Deshacer quita también eso
}

// ---- Leer, mostrar y vigilar ---------------------------------------------------------------------------------
// Al abrir la vista: los proyectos activos (lo que leyó el Recorrido) y la semana a la vista.
function plAlMostrar() {
  if (!planif.lunes) planif.lunes = plLunesDe(new Date());
  if (!rc.leyendo && (!rc.leido || Date.now() - rc.leido > RC_RELEER_SEG * 1000)) rcCargar();   // al terminar llama a plAlRecorrido
  else if (rc.dir) plCargar();
  plPintar();
}
// El Recorrido terminó de leer la carpeta: lo planificado de la semana de hoy (la alarma) y de la que está a la vista.
function plAlRecorrido() {
  if (rc.dir) { plCargar(true); return; }
  plPintarAlarmaGlobal();
  if (!$('#vistaPlan').hidden) plPintar();
}
function plCargar(siempre) {
  if (planif.leyendo) return planif.leyendo;
  const dir = rc.dir;
  if (!dir) return Promise.resolve();
  if (!planif.lunes) planif.lunes = plLunesDe(new Date());
  const ids = Array.from(new Set([plHoyId(), plSemanaId(planif.lunes)]));
  let cierres = false;
  planif.leyendoDesde = Date.now();
  planif.leyendo = (async () => {
    let cambio = await plLeerLista(dir);      // primero lo agregado a mano: los nombres y los proyectos de la semana
    for (const id of ids) cambio = (await plLeerSemana(dir, id)) || cambio;
    cierres = await plCierresCambiaron(dir);
    planif.error = null;
    return cambio;
  })().catch((e) => { console.error(e); planif.error = e; return true; }).then((cambio) => {
    planif.leyendo = null;
    // Lo que esperaba, ahora que se lee la carpeta. Tras un error, sin insistir en cada vuelta: el aviso parpadearía.
    const reintentar = !planif.errorGuardar || Date.now() - planif.falloGuardar > PL_REINTENTO_SEG * 1000;
    if (planif.porGuardar.size && !planif.guardando && !planif.error && reintentar) plGuardar();
    if (cierres && !rc.leyendo) rcCargar();
    if (cambio || siempre) {
      plRepintarLlegado();
      plPintarAlarmaGlobal();
      if (!$('#vistaEjecucion').hidden) ejPintar();      // el equipo de la semana y los días por traer
    } else if (!$('#vistaPlan').hidden) plPintarFrescura();
    // Se cambió de semana mientras se leía: falta la nueva
    if (planif.lunes && !plSemana(plSemanaId(planif.lunes)).leida && !planif.error && rc.dir) plCargar(true);
  });
  return planif.leyendo;
}
/* Lo que llega del equipo no interrumpe a quien está trabajando: con algo a medio arrastrar se espera a que lo suelte
   (repintar borraría lo que lleva en la mano), y el foco sigue en la casilla o en el buscador donde estaba. */
function plRepintarLlegado() {
  if ($('#vistaPlan').hidden) return;
  if (planif.arrastre) { planif.repintar = true; return; }
  const a = document.activeElement;
  const dentro = a && $('#vistaPlan').contains(a) && !$('#plPop').contains(a);
  const ancla = dentro ? a.dataset.ancla : null;
  const buscador = dentro && a.classList.contains('pl-arr-buscar');
  const cursor = buscador ? a.selectionStart : 0;
  plPintar();
  if (ancla) { const b = plAncla(ancla); if (b) b.focus({ preventScroll: true }); }
  else if (buscador) {
    const b = $('#vistaPlan .pl-arr-buscar');
    if (b) { b.focus({ preventScroll: true }); b.setSelectionRange(cursor, cursor); }
  }
}
// Con la vista abierta, los cambios del equipo: cada PL_RELEER_SEG segundos, y solo se relee lo que cambió.
function plVigilar() {
  if ($('#vistaPlan').hidden || document.visibilityState !== 'visible') return;
  plPintarFrescura();
  if (!rc.dir || planif.leyendo || planif.guardando) return;
  const s = planif.lunes && planif.semanas.get(plSemanaId(planif.lunes));
  if (!s || Date.now() - s.leida > PL_RELEER_SEG * 1000) plCargar();
}
function plIrSemana(paso) {
  planif.lunes = paso === 0 ? plLunesDe(new Date()) : plMas(planif.lunes || plLunesDe(new Date()), 7 * paso);
  planif.diaMovil = null;
  plCerrarPop(false);
  plPintar();
  if (rc.dir) plCargar(true);
}
function plElegirVista(id) {
  planif.vista = id;
  planif.armado = null;
  planif.arrQ = '';
  plGuardarPrefs();
  plCerrarPop(false);
  plPintar();
}
// «Más»: lo que se usa de vez en cuando con la semana (copiar, compartir, imprimir, el estado, el sábado)
function plMasMenu(abrir) {
  if (abrir) plPersonasMenu(false);
  $('#plMasLista').hidden = !abrir;
  $('#plMas').setAttribute('aria-expanded', abrir ? 'true' : 'false');
  if (abrir) { plCerrarPop(false); const b = $('#plMasLista button:not(:disabled)'); if (b) b.focus(); }
}
/* «Personal» (2026-11-13, pedido del usuario): una casilla por persona para elegir quiénes se ven, y agregar personal
   definitivo o temporal. Ocultar es de este navegador (prefs.ocultas); quien tiene algo en la semana sigue con su fila,
   así nada asignado desaparece de la vista. */
function plPersonasMenu(abrir) {
  const lista = $('#plPersonasLista');
  if (!lista || lista.hidden === !abrir) return;
  if (abrir) { plMasMenu(false); plCerrarPop(false); plPintarPersonasMenu(); }
  lista.hidden = !abrir;
  $('#plPersonas').setAttribute('aria-expanded', abrir ? 'true' : 'false');
  if (abrir) { const c = lista.querySelector('input'); if (c) c.focus(); }
}
// Todos los que pueden tener fila esa semana: el equipo y lo agregado a mano (definitivo y de esa semana)
const plTodasPersonas = (s) => plOrdenPersonas([...new Set(PERSONAL.concat(plManoActivas(s)))]);
function plPintarPersonasMenu() {
  const lista = $('#plPersonasLista');
  const s = plSemanaVista();
  const m = plModelo(s);
  const dias = plDias(s);
  const todas = plTodasPersonas(s);
  const tiene = (per) => dias.some((d) => (m.porPersona.get(d.iso + '|' + per) || []).length || m.ausencias.has(d.iso + '|' + per));
  const act = document.activeElement;
  const enfocada = act && lista.contains(act) ? (act.dataset.per ? '[data-per="' + CSS.escape(act.dataset.per) + '"]' : act.id ? '#' + act.id : '') : '';
  lista.textContent = '';
  const n = todas.filter((p) => !planif.ocultas.has(p)).length;
  const cab = crear('div', 'pl-per-cab');
  cab.append(crear('b', null, 'Quiénes se ven'), crear('span', 'pl-per-cuenta', n + ' de ' + todas.length));
  const todos = crear('button', 'cx-enlace pl-per-todos', n === todas.length ? 'Ninguno' : 'Todos');
  todos.type = 'button';
  todos.id = 'plPersonasTodos';
  todos.addEventListener('click', () => {
    if (n === todas.length) todas.forEach((p) => planif.ocultas.add(p)); else todas.forEach((p) => planif.ocultas.delete(p));
    plAlCambiarOcultas();
  });
  cab.append(todos);
  const items = crear('div', 'pl-per-items');
  todas.forEach((per) => {
    const mano = PL_PER_MANO.test(per);
    const l = crear('label', 'pl-mas-op pl-per-op');
    const c = crear('input');
    c.type = 'checkbox';
    c.dataset.per = per;
    c.checked = !planif.ocultas.has(per);
    c.addEventListener('change', () => {
      if (c.checked) planif.ocultas.delete(per); else planif.ocultas.add(per);
      plAlCambiarOcultas();
    });
    const tx = crear('span', 'pl-per-txt');
    tx.append(crear('span', null, per === estado.usuario ? per + ' · tú' : plNom(per)));
    const de = mano ? plManoDe(s, per) : null;
    const sub = [de ? (de.fija ? 'Definitivo' : 'Solo esta semana') : '', !c.checked && tiene(per) ? 'Tiene algo esta semana: sigue a la vista' : ''].filter(Boolean).join(' · ');
    if (sub) tx.append(crear('small', null, sub));
    l.append(c, tx);
    items.append(l);
  });
  const acc = crear('div', 'pl-per-acc');
  [['1', 'Agregar personal definitivo', 'En todas las semanas', 'Se suma al equipo desde la semana a la vista, en todas las semanas'],
    ['0', 'Agregar personal temporal', 'Solo esta semana', 'De apoyo o un contratista: solo para la semana a la vista']].forEach(([f, txt, sub, titulo]) => {
    const b = crear('button', 'pl-mas-op');
    b.type = 'button';
    b.dataset.agregarFija = f;
    b.title = titulo;
    b.disabled = !rc.dir;
    const tx = crear('span', 'pl-per-txt');
    tx.append(crear('span', null, txt), crear('small', null, sub));
    b.append(icono('mas', 16), tx);
    b.addEventListener('click', () => plAbrirAgregar('persona', f === '1'));
    acc.append(b);
  });
  lista.append(cab, items, acc);
  const x = enfocada && lista.querySelector(enfocada);
  if (x) x.focus();
}
function plAlCambiarOcultas() {
  plGuardarPrefs();
  plPintar();
}
// El botón dice cuántos se ven cuando falta alguien («Personal · 6 de 8»); con la lista abierta, la repinta
function plPintarBotonPersonas(s) {
  const b = $('#plPersonas');
  const todas = plTodasPersonas(s);
  const n = todas.filter((p) => !planif.ocultas.has(p)).length;
  b.textContent = '';
  b.append(icono('persona', 16), crear('span', null, 'Personal'));
  if (n < todas.length) b.append(crear('span', 'pl-per-n', n + ' de ' + todas.length));
  b.append(icono('flecha', 16));
  b.setAttribute('aria-label', 'Personal: ' + n + ' de ' + todas.length + ' a la vista');
  b.classList.toggle('filtrado', n < todas.length);
  if (!$('#plPersonasLista').hidden) plPintarPersonasMenu();
}
// Desde la alarma: «Por proyecto», con ese proyecto a la vista y, con abrir, su ventanita en hoy (o en el primer día)
function plEnfocar(clave, abrir) {
  planif.foco = clave;
  planif.focoAbrir = !!abrir;
  plElegirVista('proyecto');
}

// ---- La alarma, fuera de la vista --------------------------------------------------------------------------

// Los proyectos activos sin nadie en la semana de hoy, o null si todavía no se sabe (sin carpeta, o sin leer).
function plSinAsignarHoy() {
  if (!rc.leido || !rc.dir) return null;
  const s = planif.semanas.get(plHoyId());
  return s && s.leida ? plModelo(s).sinAsignar : null;
}
function plPintarAlarmaGlobal() {
  const l = plSinAsignarHoy() || [];
  const n = l.length;
  const que = n === 1 ? 'Un proyecto activo sin nadie asignado esta semana' : n + ' proyectos activos sin nadie asignado esta semana';
  // Junto al nombre de la herramienta, en el menú. En el Inicio ya no (pedido del usuario, 2026-11-18).
  document.querySelectorAll('.menu-item[data-herr="planificacion"]').forEach((el) => {
    let s = el.querySelector('.pl-alerta-n');
    if (!n) { if (s) s.remove(); return; }
    if (!s) { s = crear('span', 'pl-alerta-n'); el.append(s); }
    s.textContent = String(n);
    s.title = que;
  });
  pintarInicioRecorrido();     // el aviso del Inicio
}

// ---- Pintar ---------------------------------------------------------------------------------------------
const plAusencia = (id) => PL_AUSENCIAS.find((a) => a.id === id) || PL_AUSENCIAS[PL_AUSENCIAS.length - 1];
// Una persona: sus iniciales; una escrita a mano, su nombre corto («Juan P.») y entero al pasar encima
function plPersona(per, boton) {
  const mano = PL_PER_MANO.test(per);
  const e = crear(boton ? 'button' : 'span', 'pl-per' + (per === estado.usuario ? ' tuya' : '') + (mano ? ' mano' : ''), plNomCorto(per));
  if (boton) e.type = 'button';
  if (mano) e.title = plNom(per);
  return e;
}
function plChipEstado(txt, nivel) {
  const c = crear('span', 'rc-chip', txt);
  if (nivel) c.dataset.nivel = nivel;
  return c;
}
function plPintar() {
  const hay = rc.leido > 0;
  $('#plLeyendo').hidden = hay || !!rc.sinDatos;
  $('#plContenido').hidden = !hay;
  $('#plVacio').hidden = hay || !rc.sinDatos;
  plPintarFrescura();
  if (!hay) {
    plCerrarPop(false);
    if (rc.sinDatos) pintarSinCarpeta($('#plVacio'), rc.sinDatos, PL_SIN_CARPETA);
    return;
  }
  if (!planif.lunes) planif.lunes = plLunesDe(new Date());
  const s = plSemanaVista();
  const m = plModelo(s);
  const dias = plDias(s);
  if (planif.diaMovil === null || planif.diaMovil >= dias.length) planif.diaMovil = Math.max(0, dias.findIndex((d) => d.hoy));
  plPintarBarra(s, dias);
  plPintarBotonPersonas(s);
  plPintarPisado();
  presPintar();
  const leida = s.leida > 0;
  const estadoSemana = $('#plEstadoSemana');
  estadoSemana.hidden = leida && !planif.error;
  estadoSemana.textContent = planif.error ? 'No se pudo leer lo planificado en la carpeta del equipo: ' + (planif.error.message || planif.error) + '. Vuelve a intentarlo con ↻.'
    : 'Leyendo la semana ' + plNum(s) + '…';
  $('#plAlarma').hidden = true;
  $('#plSemanaVacia').hidden = true;
  $('#plResumen').hidden = !leida;
  $('#plDiasMovil').hidden = !leida;
  PL_VISTAS.forEach((v) => { $('#pl' + v.id.charAt(0).toUpperCase() + v.id.slice(1)).hidden = !leida || planif.vista !== v.id; });
  if (!leida) { plCerrarPop(false); return; }
  plPintarAlarma(s, m);
  plPintarResumen(s, m, dias);
  plPintarVacia(s);
  plPintarDiasMovil(dias);
  if (planif.vista === 'general') plPintarGeneral(s, m, dias);
  else if (planif.vista === 'personal') plPintarPersonal(s, m, dias);
  else plPintarProyecto(s, m, dias);
  if (planif.pop) plPintarPop(false);
}
function plPintarFrescura() {
  const txt = $('#plFrescura'), punto = $('#plPunto');
  $('#plReintentar').hidden = !planif.errorGuardar;
  if (planif.errorGuardar) {
    txt.textContent = 'No se pudo guardar en la carpeta del equipo';
    txt.title = 'Lo cambiado espera en este navegador y se vuelve a intentar solo, con el próximo cambio o con «Reintentar». ' + (planif.errorGuardar.message || '');
    punto.className = 'cx-punto bad';
    return;
  }
  const tope = Date.now() - PL_ATASCO_SEG * 1000;
  if ((planif.leyendo && planif.leyendoDesde < tope) || (planif.guardando && planif.guardandoDesde < tope)) {
    txt.textContent = 'La carpeta del equipo no responde: recarga la página (F5)';
    txt.title = 'Lleva más de un minuto sin terminar de leer o guardar, así que esta vista no está recibiendo los cambios del equipo.';
    punto.className = 'cx-punto bad';
    return;
  }
  if (planif.guardando || planif.porGuardar.size) { txt.textContent = 'Guardando en la carpeta del equipo…'; txt.title = ''; punto.className = 'cx-punto warn'; return; }
  if (!rc.leido) { txt.textContent = rc.leyendo ? 'Leyendo la carpeta del equipo…' : 'Sin datos de la carpeta del equipo'; txt.title = ''; punto.className = 'cx-punto'; return; }
  const s = planif.lunes ? planif.semanas.get(plSemanaId(planif.lunes)) : null;
  let u = null;
  if (s) PL_TIPOS.forEach((tipo) => s.ef[tipo].forEach((e) => { if (!u || e.t > u.t) u = e; }));
  const aj = planif.ajeno && Date.now() - planif.ajeno.cuando < PL_AJENO_SEG * 1000 ? planif.ajeno : null;
  const linea = aj ? aj.quien + ' acaba de cambiar ' + pl(aj.n, 'casilla', 'casillas')
    : Date.now() - planif.guardado < 8000 ? 'Guardado · OneDrive lo lleva al equipo'
    : u ? 'Último cambio: ' + (u.por || 'sin usuario') + ', ' + plCuando(u.t) : 'Sin cambios esta semana';
  if (txt.textContent !== linea) txt.textContent = linea;    // el lector de pantalla anuncia cada cambio de esta línea
  txt.title = 'Lo que cambias queda guardado en este computador y OneDrive lo lleva a la carpeta del equipo: cuánto tarda depende de OneDrive de cada computador. Esta vista revisa lo que llega cada ' + PL_RELEER_SEG + ' segundos.';
  punto.className = 'cx-punto ok';
}
function plPintarBarra(s, dias) {
  const actual = s.id === plHoyId();
  const anio = plMas(s.lunes, 3).getFullYear();     // el año de la semana es el de su jueves
  $('#plSemanaN').textContent = 'Semana ' + plNum(s) + (anio !== new Date().getFullYear() ? ' de ' + anio : '');
  $('#plSemanaRango').textContent = (actual ? 'Esta semana · ' : '') + plRango(s.lunes, dias.length);
  $('#plHoy').disabled = actual;
  document.querySelectorAll('#plVistas .pl-vista').forEach((b) => b.setAttribute('aria-pressed', b.dataset.vista === planif.vista ? 'true' : 'false'));
  const sab = $('#plSabado');
  sab.checked = dias.length === 6;
  sab.disabled = dias.length === 6 && !planif.sabado;        // el sábado ya tiene algo: queda a la vista
  sab.parentElement.title = sab.disabled ? 'El sábado tiene asignaciones o ausencias: queda a la vista' : 'Mostrar también el sábado';
  $('#plCopiar').disabled = !rc.dir;
  $('#plAgregar').disabled = !rc.dir;
}
function plPintarAlarma(s, m) {
  const caja = $('#plAlarma');
  const l = m.sinAsignar;
  caja.textContent = '';
  if (!l.length) planif.alarmaAbierta = false;
  caja.hidden = !planif.alarmaAbierta;      // plegada: la despliega la cifra «sin asignar» del resumen
  if (!l.length) return;
  const actual = s.id === plHoyId();
  const futura = s.lunes > new Date();
  caja.dataset.nivel = actual ? 'bad' : futura ? 'warn' : '';
  const ico = crear('span', 'ico');
  ico.append(icono('alerta', 20));
  const txt = crear('div', 'pl-alarma-txt');
  const cuando = actual ? 'esta semana' : futura ? 'en la semana ' + plNum(s) : 'en la semana ' + plNum(s) + ', que ya pasó';
  txt.append(crear('span', 'pl-alarma-tit', (l.length === 1 ? 'Un proyecto activo' : l.length + ' proyectos activos') + ' sin nadie asignado ' + cuando));
  const ul = crear('ul', 'pl-alarma-lista');
  l.forEach((p) => {
    const li = crear('li');
    const b = crear('button', 'pl-alarma-p');
    b.type = 'button';
    b.style.setProperty('--pc', m.color(p.clave));
    b.append(crear('span', 'pl-dot'), crear('span', null, p.titulo));
    b.title = 'Asignar a alguien en ' + p.titulo;
    b.addEventListener('click', () => plEnfocar(p.clave, true));
    li.append(b);
    ul.append(li);
  });
  txt.append(ul, crear('span', 'pl-alarma-pista', 'Toca uno para asignar a alguien al menos un día o, si esa semana no se trabaja en él, marcarlo «Sin trabajo esta semana».'));
  caja.append(ico, txt);
}
/* Las cifras de la semana, en una línea discreta (2026-10-28: antes eran cinco tarjetas y la alarma, una caja roja);
   cada una abre la vista donde se ve, el detalle va al pasar encima. «Sin asignar» despliega la lista de esos
   proyectos, y la de los vehículos lleva a «Vehículos en la semana». */
function plPintarResumen(s, m, dias) {
  const cont = $('#plResumen');
  cont.textContent = '';
  let asignados = 0, ausentes = 0;
  dias.forEach((d) => m.personas.forEach((per) => {
    const k = d.iso + '|' + per;
    if (m.ausencias.has(k)) ausentes++;
    else if ((m.porPersona.get(k) || []).length) asignados++;
  }));
  const disponibles = m.personas.length * dias.length - ausentes;
  const pausados = m.activos.filter((p) => m.pausas.has(p.clave) && !m.dias.has(p.clave)).length;
  const actual = s.id === plHoyId();
  const cifras = [
    { n: m.activos.length, et: m.activos.length === 1 ? 'proyecto activo' : 'proyectos activos', vista: 'proyecto',
      sub: m.activos.some((p) => p.mano) ? 'Con ' + pl(m.activos.filter((p) => p.mano).length, 'agregado', 'agregados') + ' a mano' : 'En ejecución, según el Recorrido' },
    { n: m.sinAsignar.length, et: 'sin asignar', sub: pausados ? 'Y ' + pausados + ' sin trabajo ' + plEsta(s) : 'Sin nadie ningún día de la semana',
      alarma: m.sinAsignar.length > 0, vista: 'proyecto', nivel: m.sinAsignar.length ? (actual ? 'bad' : 'warn') : '' },
    // Una sola cifra para el equipo (2026-10-29): «22 días asignados» y «23 días libres» se leían como días del calendario
    { n: asignados, et: 'de ' + pl(disponibles, 'jornada', 'jornadas') + ' con proyecto', vista: 'personal',
      sub: 'Cada persona cada día es una jornada: ' + pl(disponibles - asignados, 'libre', 'libres') + ' (sin proyecto)'
        + (ausentes ? ' y, aparte, ' + pl(ausentes, 'de ausencia', 'de ausencia') : '') }
  ];
  if (PL_VEHICULOS.length) {
    // Cuántos se usan y cuántos días cada uno; si uno va a dos lugares a la vez, eso primero
    const usos = PL_VEHICULOS.map((v) => ({ v, dias: dias.filter((d) => m.usoVeh(d.iso, v.id).length) }));
    const choques = usos.flatMap((u) => u.dias.filter((d) => m.usoVeh(d.iso, u.v.id).length > 1).map((d) => ({ v: u.v, d, n: m.usoVeh(d.iso, u.v.id).length })));
    const enUso = usos.filter((u) => u.dias.length).length;
    const detalle = usos.map((u) => u.v.nombre + ' ' + (u.dias.length ? pl(u.dias.length, 'día', 'días') : 'libre')).join(' · ');
    cifras.push({ n: enUso, et: enUso === 1 ? 'vehículo en uso' : 'vehículos en uso', vista: 'general', veh: true, nivel: choques.length ? 'warn' : '',
      sub: choques.length ? mayuscula(plLaVeh(choques[0].v)) + ' en ' + choques[0].n + ' lugares ' + plElDia(choques[0].d) + (choques.length > 1 ? ' y ' + (choques.length - 1) + ' más' : '') : detalle,
      titulo: (choques.length ? choques.map((x) => mayuscula(plLaVeh(x.v)) + ' va a ' + x.n + ' lugares a la vez ' + plElDia(x.d)).join('. ') + '. ' : detalle + '. ')
        + 'Ver dónde va cada vehículo, en la vista General' });
  }
  cifras.forEach((k) => {
    const b = crear('button', 'rc-kpi' + (k.veh ? ' pl-kpi-veh' : '') + (k.alarma ? ' pl-kpi-alarma' : ''));
    b.type = 'button';
    if (k.nivel) b.dataset.nivel = k.nivel;
    if (k.veh) b.append(icono('vehiculo', 15));
    else if (k.alarma) b.append(icono('alerta', 15));
    b.append(crear('span', 'rc-kpi-n', String(k.n)), crear('span', 'rc-kpi-et', k.et), crear('span', 'rc-kpi-sub', k.sub));
    if (k.alarma) {
      b.append(icono('flecha', 14));
      b.setAttribute('aria-expanded', planif.alarmaAbierta ? 'true' : 'false');
      b.setAttribute('aria-controls', 'plAlarma');
      b.title = k.sub + '. Toca para ver cuáles son';
      b.addEventListener('click', () => { planif.alarmaAbierta = !planif.alarmaAbierta; plPintarAlarma(s, m); b.setAttribute('aria-expanded', planif.alarmaAbierta ? 'true' : 'false'); });
    } else {
      b.title = (k.titulo || k.sub + '. Ver ' + PL_VISTAS.find((v) => v.id === k.vista).nombre.toLowerCase());
      b.addEventListener('click', () => { planif.focoVeh = !!k.veh; plElegirVista(k.vista); });
    }
    cont.append(b);
  });
}
// Esta semana o una que viene, sin nada todavía: lo primero suele ser copiar la anterior, que estaba escondido en «Más»
function plPintarVacia(s) {
  const caja = $('#plSemanaVacia');
  caja.textContent = '';
  const vacia = ![...s.ef.asig.values()].some((e) => e.activa) && ![...s.ef.aus.values()].some((e) => e.motivo);
  caja.hidden = !(vacia && rc.dir && s.lunes >= plLunesDe(new Date()));
  if (caja.hidden) return;
  const b = crear('button', 'btn-pri pl-vacia-copiar', 'Copiar la semana ' + plNum({ id: plSemanaId(plMas(s.lunes, -7)) }));
  b.type = 'button';
  b.title = 'Agrega lo de la semana anterior, día por día; después se cambia lo que haga falta';
  b.addEventListener('click', plCopiarAnterior);
  caja.append(crear('p', null, 'Semana ' + plNum(s) + ' sin planificar'), b);
}
function plPintarDiasMovil(dias) {
  const cont = $('#plDiasMovil');
  cont.textContent = '';
  dias.forEach((d) => {
    const b = crear('button', 'pl-dia-tab' + plClaseDia(d));
    b.type = 'button';
    b.setAttribute('aria-pressed', d.i === planif.diaMovil ? 'true' : 'false');
    b.setAttribute('aria-label', plFechaLarga(d) + (d.hoy ? ' (hoy)' : ''));
    b.append(crear('span', null, d.corto), crear('b', null, String(d.fecha.getDate())));
    b.addEventListener('click', () => { planif.diaMovil = d.i; plPintar(); });
    cont.append(b);
  });
}
function plCabecera(t, primera, dias) {
  const thead = crear('thead'), tr = crear('tr');
  const th0 = crear('th', 'pl-th-nom', primera);
  th0.scope = 'col';
  tr.append(th0);
  dias.forEach((d) => {
    const th = crear('th', plClaseDia(d).trim() || null);
    th.scope = 'col';
    th.dataset.dia = String(d.i);
    th.title = plFechaLarga(d) + (d.hoy ? ' (hoy)' : '');
    const c = crear('span', 'pl-th-txt');
    c.append(crear('span', null, d.corto), crear('b', null, String(d.fecha.getDate())));
    if (d.hoy) c.append(crear('span', 'pl-hoy-pill', 'Hoy'));
    th.append(c);
    tr.append(th);
  });
  thead.append(tr);
  t.append(thead);
}
function plCelda(ancla, d) {
  const td = crear('td', plClaseDia(d).trim() || null);
  td.dataset.dia = String(d.i);
  const b = crear('button', 'pl-celda' + (planif.recien.has(ancla) ? ' recien' + (planif.recienAjeno ? ' ajeno' : '') : ''));
  b.type = 'button';
  b.dataset.ancla = ancla;
  td.append(b);
  return [td, b];
}
// En las tablas, las flechas van de casilla en casilla (Inicio y Fin: el primer y el último día), sin recorrerlas con
// Tab; Enter abre la ventanita. En el teléfono solo se recorren las casillas a la vista (las del día elegido).
function plTeclasTabla(e) {
  const c = e.target.closest && e.target.closest('.pl-celda');
  if (c && (e.key === 'Delete' || e.key === 'Backspace') && !e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
    e.preventDefault();
    plQuitarCasilla(c);
    return;
  }
  const paso = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0], Home: [0, -99], End: [0, 99] }[e.key];
  if (!c || !paso || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  e.preventDefault();
  const visibles = (tr) => [...tr.querySelectorAll('.pl-celda')].filter((x) => x.getClientRects().length);
  const filas = [...c.closest('tbody').rows].filter((tr) => visibles(tr).length);
  const f = Math.max(0, Math.min(filas.length - 1, filas.indexOf(c.closest('tr')) + paso[0]));
  const fila = visibles(filas[f]);
  const destino = fila[Math.max(0, Math.min(fila.length - 1, visibles(c.closest('tr')).indexOf(c) + paso[1]))];
  if (destino) destino.focus();
}
// «Asignar» en una casilla vacía; con algo ya asignado, un «+» que aparece en la esquina (txt null)
function plAgregar(b, txt) {
  const mas = crear('span', 'pl-mas' + (txt ? '' : ' flota'));
  mas.setAttribute('aria-hidden', 'true');
  mas.append(icono('mas', 13));
  if (txt) mas.append(crear('span', null, txt));
  b.append(mas);
}
// Un proyecto de una persona un día (d) y, si lo lleva, el vehículo con que va
function plChip(m, c, veh, d) {
  const p = m.proyectos.get(c) || {};
  const v = plVehiculo(veh);
  const s = crear('span', 'pl-chip' + (p.otra ? ' otra' : p.activo === false ? ' inactivo' : ''));
  s.style.setProperty('--pc', m.color(c));
  s.append(crear('span', 't', m.titulo(c)));
  if (v) s.append(plVeh(v.id, null, plChoque(m, d, v.id)));
  s.title = m.titulo(c) + (p.lugar ? ' · ' + p.lugar : '') + (p.otra ? ' (otra actividad)' : p.activo === false ? ' (ya no está en ejecución)' : '')
    + (v ? ', en ' + plLaVeh(v) : '');
  return s;
}
/* Quitar con un toque (2026-11-06, observación del equipo: «acceso rápido para eliminar asignaciones»): una ✕ en un
   proyecto de una persona un día (o en una persona de un proyecto). Va dentro del botón de la casilla, así que no es
   un botón: la toma plQuitarToque antes que la casilla. Con el teclado, Supr en la casilla (plQuitarCasilla). Sin la
   carpeta conectada no se puede guardar, y no se pone. */
function plQuitarX(el, per, d, clave, m) {
  if (!rc.dir) return el;
  const x = crear('span', 'pl-quitar');
  Object.assign(x.dataset, { per, iso: d.iso, clave });
  x.title = 'Quitar: ' + plNom(per) + ' ya no va a ' + m.titulo(clave) + ' ' + plElDia(d);
  x.setAttribute('aria-hidden', 'true');
  x.append(icono('cerrar', 12));
  const t = el.querySelector(':scope > .t');       // en un proyecto, junto a su nombre, arriba a la derecha
  if (t) t.after(x); else el.append(x);
  return el;
}
function plQuitarToque(e) {
  const x = e.target.closest && e.target.closest('#vistaPlan .pl-quitar');
  if (!x) return;
  e.preventDefault();
  e.stopPropagation();                          // la casilla no abre su ventanita
  plCerrarPop(false);
  plAsignarDias(plSemanaVista(), x.dataset.per, x.dataset.clave, [x.dataset.iso], false);
}
/* Supr en una casilla: quita lo que tiene ese día (los proyectos de la persona, o las personas del proyecto), en un
   paso que se deshace. La casilla sigue con el foco. */
function plQuitarCasilla(c) {
  if (!rc.dir || !c.dataset.ancla) return false;
  const [k, x, iso] = c.dataset.ancla.split('|');
  const s = plSemanaVista(), m = plModelo(s), d = plDiaDe(s, iso);
  const pares = k === 'p' ? (m.porPersona.get(iso + '|' + x) || []).map((clave) => ({ per: x, clave }))
    : (m.porProyecto.get(iso + '|' + x) || []).map((per) => ({ per, clave: x }));
  if (!pares.length) return false;
  const pers = pares.map((p) => p.per);
  const hecho = plCambiar(s, pares.map((p) => ({ tipo: 'asig', dia: iso, persona: p.per, clave: p.clave, activa: false })),
    (k === 'p' ? plNom(x) + ' ya no va a ' + unir(pares.map((p) => m.titulo(p.clave)))
      : plNoms(pers) + (pers.length > 1 ? ' ya no van a ' : ' ya no va a ') + m.titulo(x)) + ' ' + plElDia(d) + '.');
  const otra = document.querySelector('#vistaPlan .pl-celda[data-ancla="' + CSS.escape(c.dataset.ancla) + '"]');
  if (otra) otra.focus();
  return hecho;
}
// Un vehículo, con su ícono («RAM»); con quiénes lo llevan si no son todos los de la casilla («RAM · ES LC»); en
// naranjo si ese día va a dos lugares a la vez (choque: lo que dice su título)
function plVeh(id, quienes, choque) {
  const v = plVehiculo(id);
  const e = crear('span', 'pl-veh' + (choque ? ' choque' : ''));
  e.append(icono('vehiculo', 14), crear('span', 'n', v ? v.nombre : id));
  if (quienes && quienes.length) e.append(crear('span', 'q', quienes.map(plNomCorto).join(' ')));
  if (choque) e.title = choque;
  return e;
}
// «La RAM va a 2 lugares a la vez el martes 20: Adjudicada sin ficha (NB) y En obra (ES)», o '' si va a uno solo
function plChoque(m, d, id) {
  const g = m.usoVeh(d.iso, id);
  return g.length < 2 ? '' : mayuscula(plLaVeh(plVehiculo(id))) + ' va a ' + g.length + ' lugares a la vez ' + plElDia(d) + ': '
    + unir(g.flat().map((x) => m.titulo(x.clave) + ' (' + plNoms(x.personas) + ')')) + '. Revisa si van juntos';
}
// Los vehículos de quienes van a un proyecto un día (d): uno solo si van todos en él; si no, cada uno con quiénes lo llevan
function plVehs(m, d, clave, van) {
  const w = crear('span', 'pl-vehs');
  PL_VEHICULOS.forEach((v) => {
    const con = van.filter((per) => m.vehiculo(d.iso, per, clave) === v.id);
    if (con.length) w.append(plVeh(v.id, con.length === van.length ? null : con, plChoque(m, d, v.id)));
  });
  return w.childElementCount ? w : null;
}
// Lo mismo en palabras, para leer en voz alta: «, en la RAM» o «, ES en la RAM y LC en la Quempineta»
function plVehsTexto(m, iso, clave, van) {
  const partes = PL_VEHICULOS.map((v) => {
    const con = van.filter((per) => m.vehiculo(iso, per, clave) === v.id);
    return con.length ? (con.length === van.length ? '' : plNoms(con) + ' ') + 'en ' + plLaVeh(v) : '';
  }).filter(Boolean);
  return partes.length ? ', ' + unir(partes) : '';
}
// Por personal: una fila por persona, sus proyectos de cada día (hasta 3) y sus ausencias.
function plPintarPersonal(s, m, dias) {
  const cont = $('#plPersonal');
  cont.textContent = '';
  const t = crear('table', 'pl-tabla pl-t-personal');
  t.dataset.foco = String(planif.diaMovil);
  plCabecera(t, 'Personal', dias);
  const tb = crear('tbody');
  m.personas.forEach((per) => {
    const tr = crear('tr');
    tr.dataset.persona = per;
    if (per === estado.usuario) tr.classList.add('tuya');
    const proyectos = new Set();
    let con = 0, aus = 0;
    const celdas = dias.map((d) => {
      const k = d.iso + '|' + per;
      const lista = m.ordenar(m.porPersona.get(k) || []);
      const a = m.ausencias.get(k);
      const [td, b] = plCelda('p|' + per + '|' + d.iso, d);
      if (a) { aus++; b.classList.add('ausente'); b.append(crear('span', 'pl-aus', plAusencia(a.motivo).nombre)); }
      else if (lista.length) con++;
      lista.forEach((c) => {
        proyectos.add(c);
        const chip = plChip(m, c, m.vehiculo(d.iso, per, c), d);
        plArrastrable(chip, { tipo: 'proyecto', clave: c, desde: { per, iso: d.iso, clave: c } }, m.titulo(c));
        b.append(plQuitarX(chip, per, d, c, m));
      });
      if (lista.length > PL_MAX) { b.classList.add('exceso'); b.append(crear('span', 'pl-lleno', lista.length + ' de ' + PL_MAX + ': quita ' + (lista.length - PL_MAX))); }
      else if (lista.length === PL_MAX) b.append(crear('span', 'pl-lleno', 'Completo'));
      else if (!a) plAgregar(b, lista.length ? null : 'Asignar');
      b.setAttribute('aria-label', plNom(per) + ', ' + plFechaLarga(d) + ': ' + (a ? plAusencia(a.motivo).nombre.toLowerCase()
        : lista.length ? lista.map((c) => m.titulo(c) + plVehsTexto(m, d.iso, c, [per])).join('; ') : 'sin proyecto') + '. Cambiar');
      if (lista.length && rc.dir) b.setAttribute('aria-keyshortcuts', 'Delete');      // Supr la deja sin proyectos
      b.addEventListener('click', (e) => plColocar(plDestino(e.target) || { per, iso: d.iso }) || plAbrirPersona(per, d.iso));
      return td;
    });
    const th = crear('th');
    th.scope = 'row';
    const q = crear('div', 'pl-quien');
    const tx = crear('span', 'pl-quien-txt');
    const mano = PL_PER_MANO.test(per);
    const enLista = !mano || plManoActivas(s).includes(per);
    // Una persona escrita a mano se ve por su círculo punteado; si ya la quitaron de la lista, lo dice
    // Lo de la semana va bajo el nombre (2026-10-28: antes, en una columna «Semana» al final)
    tx.append(crear('b', null, per === estado.usuario ? per + ' · tú' : plNom(per)),
      crear('span', null, !enLista ? 'Fuera de la lista' : aus === dias.length ? 'Ausente' : proyectos.size ? con + ' de ' + pl(dias.length - aus, 'día', 'días') + ' · ' + pl(proyectos.size, 'proyecto', 'proyectos') : 'Sin proyectos'));
    q.append(crear('span', 'pl-avatar' + (mano ? ' mano' : ''), plIniciales(per)), tx);
    if (mano) th.title = plNom(per) + (enLista ? ((plManoDe(s, per) || {}).fija ? ': personal definitivo agregado en la planificación' : ': agregada a mano solo en esta semana') :': ya no está en la lista de la planificación');
    th.append(q);
    tr.append(th, ...celdas);
    tb.append(tr);
  });
  t.append(tb);
  const tabla = crear('div', 'pl-con-tabla');
  tabla.append(t, plBotonAgregar('persona', 'Agregar persona', 'Alguien que no está en la lista: escribe su nombre y queda solo en esta semana'));
  cont.append(plConArrastre(tabla, plPanelArrastre(s, m, dias, 'proyecto')));
}
// Al pie de «Por personal» y «Por proyecto»: agregar a mano lo que no está en la lista
function plBotonAgregar(modo, txt, titulo) {
  const b = crear('button', 'rc-nueva pl-agregar-pie');
  b.type = 'button';
  b.dataset.agregar = modo;
  b.title = titulo;
  b.disabled = !rc.dir;
  b.append(icono('mas', 14), crear('span', null, txt));
  b.addEventListener('click', () => plAbrirAgregar(modo));
  return b;
}
// Por proyecto: una fila por proyecto activo (primero los que nadie tiene), quiénes van cada día, y lo demás de la semana.
function plPintarProyecto(s, m, dias) {
  const cont = $('#plProyecto');
  cont.textContent = '';
  const t = crear('table', 'pl-tabla pl-t-proyecto');
  t.dataset.foco = String(planif.diaMovil);
  plCabecera(t, 'Proyecto', dias);
  const tb = crear('tbody');
  const sin = new Set(m.sinAsignar.map((p) => p.clave));
  const grupo = (p) => (sin.has(p.clave) ? 0 : m.pausas.has(p.clave) && !m.dias.has(p.clave) ? 2 : 1);
  const sep = (txt, n) => {
    const tr = crear('tr', 'pl-sep');
    const th = crear('th', null, txt);
    if (n) th.append(crear('span', 'pl-sep-n', String(n)));
    th.colSpan = dias.length + 1;
    th.scope = 'rowgroup';
    tr.append(th);
    tb.append(tr);
  };
  // Cada grupo con su título (2026-10-29): la raya roja de las primeras filas y el orden no se explicaban solos
  const activos = m.activos.slice().sort((a, b) => grupo(a) - grupo(b) || plPorTitulo(a, b));
  const titulos = ['Sin nadie asignado ' + plEsta(s), 'Con alguien asignado', 'Sin trabajo ' + plEsta(s)];
  const hay = new Set(activos.map(grupo));
  let ultimo = -1;
  activos.forEach((p) => {
    const g = grupo(p);
    if (g !== ultimo && hay.size > 1) sep(titulos[g], activos.filter((x) => grupo(x) === g).length);
    ultimo = g;
    tb.append(plFilaProyecto(s, m, dias, p, sin.has(p.clave)));
  });
  const otros = [...m.dias.keys()].map((c) => m.proyectos.get(c)).filter((p) => p && !p.activo).sort(plPorTitulo);
  if (otros.length) {
    sep('También en la semana: otras actividades y proyectos que ya no están en ejecución');
    otros.forEach((p) => tb.append(plFilaProyecto(s, m, dias, p, false)));
  }
  if (!m.activos.length && !otros.length) {
    const tr = crear('tr', 'pl-nada');
    const td = crear('td', null, 'No hay proyectos en ejecución en el Recorrido. Cuando un proyecto se adjudica o tiene su ficha en el Análisis Financiero, aparece aquí; uno que no está, agrégalo abajo.');
    td.colSpan = dias.length + 1;
    tr.append(td);
    tb.append(tr);
  }
  t.append(tb);
  const pie = crear('div', 'pl-pie');
  const est = crear('button', 'rc-nueva pl-agregar-pie');
  est.type = 'button';
  est.dataset.estado = 'proyectos';
  est.title = 'De dónde sale cada proyecto, cómo va, y dar por cerrado uno que ya terminó';
  est.append(icono('bandera', 14), crear('span', null, 'Estado de los proyectos'));
  est.addEventListener('click', () => plAbrirProyectos());
  pie.append(plBotonAgregar('proyecto', 'Agregar proyecto', 'Un proyecto que no está en ejecución en el Recorrido: escribe su nombre y queda solo en esta semana'), est);
  const tabla = crear('div', 'pl-con-tabla');
  tabla.append(t, pie);
  cont.append(plConArrastre(tabla, plPanelArrastre(s, m, dias, 'persona')));
  if (planif.foco) {
    const f = cont.querySelector('tr[data-clave="' + CSS.escape(planif.foco) + '"]');
    const abrir = planif.focoAbrir;
    planif.foco = null;
    planif.focoAbrir = false;
    if (f) {
      f.scrollIntoView({ block: 'center', behavior: REDUCIR.matches ? 'auto' : 'smooth' });
      f.classList.add('resaltada');
      setTimeout(() => f.classList.remove('resaltada'), 1800);
      const celdas = [...f.querySelectorAll('.pl-celda')].filter((x) => x.getClientRects().length);
      const c = celdas.find((x) => x.closest('td.hoy')) || celdas[0];
      if (c) {
        c.focus({ preventScroll: true });
        if (abrir) plAbrirProyecto(f.dataset.clave, dias[+c.closest('td').dataset.dia].iso, null, true);
      }
    }
  }
}
function plFilaProyecto(s, m, dias, p, alarma) {
  const tr = crear('tr');
  tr.dataset.clave = p.clave;
  const pausa = m.pausas.get(p.clave);
  const diasCon = m.dias.get(p.clave) || [];
  const personas = new Set();
  dias.forEach((d) => (m.porProyecto.get(d.iso + '|' + p.clave) || []).forEach((x) => personas.add(x)));
  if (alarma) tr.classList.add('alarma');
  if (pausa && !diasCon.length) tr.classList.add('pausa');
  const th = crear('th');
  th.scope = 'row';
  const b = crear(p.tarjeta ? 'button' : 'div', 'pl-proy');
  if (p.tarjeta) {
    b.type = 'button';
    b.title = 'Ver su recorrido, sus datos y sus enlaces';
    b.addEventListener('click', () => rcVerDetalle(p.tarjeta));
  }
  const dot = crear('span', 'pl-dot');
  dot.style.setProperty('--pc', m.color(p.clave));
  const tx = crear('span', 'pl-proy-txt');
  tx.append(crear('span', 't', p.titulo));
  const sub = p.otra ? 'Otra actividad' : [p.req ? 'N° ' + p.req : '', p.tag && p.tag !== p.titulo ? p.tag : '', p.lugar, p.mano ? 'agregado a mano' : '',
    p.activo === false ? 'ya no está en ejecución' : ''].filter(Boolean).join(' · ');
  if (sub) tx.append(crear('span', 's', sub));
  b.append(dot, tx);
  th.append(b);
  const est = crear('div', 'pl-proy-estado');
  // Cómo va según el Recorrido (su avance, o lo que le falta), con el detalle al pasar encima (2026-10-26)
  const como = p.activo && !p.mano ? plEstadoDe(plTarjeta(p.tarjeta)) : null;
  if (como) { const c = plChipEstado(como.texto, como.nivel); c.title = como.titulo; c.classList.add('pl-avance'); est.append(c); }
  // Sin asignar ya lo dicen la raya roja de la fila y el panel del costado (2026-10-28: una etiqueta menos)
  if (alarma) th.title = 'Sin nadie asignado ' + plEsta(s);
  else if (pausa && !diasCon.length) est.append(plChipEstado('Sin trabajo ' + plEsta(s) + (pausa.nota ? ': ' + pausa.nota : ''), ''));
  else if (diasCon.length) est.append(plChipEstado(pl(diasCon.length, 'día', 'días') + ' · ' + pl(personas.size, 'persona', 'personas'), 'ok'));
  if (p.activo && !diasCon.length) {
    const a = crear('button', 'pl-pausar', pausa ? 'Volver a planificar' : 'Sin trabajo esta semana');
    a.type = 'button';
    a.title = pausa ? 'Que vuelva a contar como alarma si nadie lo tiene en la semana' : 'Esta semana no se trabaja en este proyecto: deja de contar como alarma';
    a.addEventListener('click', () => plPausar(s, p.clave, !pausa));
    est.append(a);
  }
  if (est.childElementCount) th.append(est);
  tr.append(th);
  dias.forEach((d) => {
    const [td, c] = plCelda('j|' + p.clave + '|' + d.iso, d);
    const van = plOrdenPersonas(m.porProyecto.get(d.iso + '|' + p.clave) || []);
    if (van.length) {
      const w = crear('span', 'pl-pers');
      van.forEach((x) => w.append(plQuitarX(plArrastrable(plPersona(x), { tipo: 'persona', per: x, desde: { per: x, iso: d.iso, clave: p.clave } }, plNom(x)), x, d, p.clave, m)));
      c.append(w);
      if (rc.dir) c.setAttribute('aria-keyshortcuts', 'Delete');      // Supr quita a todos de ese día
    }
    const vs = van.length ? plVehs(m, d, p.clave, van) : null;
    if (vs) c.append(vs);
    plAgregar(c, van.length ? null : 'Asignar');
    c.setAttribute('aria-label', p.titulo + ', ' + plFechaLarga(d) + ': ' + (van.length ? plNoms(van) + plVehsTexto(m, d.iso, p.clave, van) : 'nadie') + '. Cambiar');
    c.addEventListener('click', (e) => plColocar(plDestino(e.target) || { clave: p.clave, iso: d.iso }) || plAbrirProyecto(p.clave, d.iso));
    tr.append(td);
  });
  return tr;
}
// General: un tablero por día con cada proyecto y quiénes van, quiénes quedan sin proyecto y quiénes faltan; abajo, lo que
// cubre cada proyecto en la semana y la carga de cada persona.
/* General (2026-11-16, el usuario eligió «Hoy con la semana al lado» entre 6 maquetas y 5 variantes): el día elegido en
   grande y, al lado, la semana en una línea por día con los avisos. Abre en hoy (en otra semana, el lunes) y tocar un
   día lo muestra en grande. El día elegido es el mismo que muestran las tablas en el teléfono (planif.diaMovil). */
function plPintarGeneral(s, m, dias) {
  const cont = $('#plGeneral');
  cont.textContent = '';
  const d = dias[planif.diaMovil] || dias[0];
  const w = crear('div', 'pl-hoy-sem');
  w.append(plDiaGrande(m, d), plSemanaLado(s, m, dias, d));
  cont.append(w, plPaneles(s, m, dias));
  // Desde la cifra de los vehículos en el resumen: su panel, a la vista y resaltado un momento
  const veh = planif.focoVeh && $('#plVehiculos');
  planif.focoVeh = false;
  if (veh) {
    veh.open = true;
    veh.scrollIntoView({ block: 'center', behavior: REDUCIR.matches ? 'auto' : 'smooth' });
    veh.classList.add('resaltada');
    setTimeout(() => veh.classList.remove('resaltada'), 1800);
  }
}
// Un día en grande: sus proyectos con quiénes van y en qué vehículo, quién queda sin proyecto o ausente, y «Asignar»
function plDiaGrande(m, d) {
  const col = crear('section', 'pl-dia pl-dia-grande' + plClaseDia(d));
  col.dataset.dia = String(d.i);
  col.setAttribute('aria-label', plFechaLarga(d));
  const cab = crear('header', 'pl-dia-cab');
  const h3 = crear('h3');
  h3.append(crear('span', null, d.nombre), crear('b', null, String(d.fecha.getDate())));
  cab.append(h3);
  if (d.hoy) cab.append(crear('span', 'pl-hoy-pill', 'Hoy'));
  const enObra = m.personas.filter((per) => (m.porPersona.get(d.iso + '|' + per) || []).length);
  cab.append(crear('span', 'pl-dia-n', enObra.length ? pl(enObra.length, 'persona', 'personas') : 'Nadie asignado'));
  col.append(cab);
  const claves = m.ordenar([...new Set(m.personas.flatMap((per) => m.porPersona.get(d.iso + '|' + per) || []))]);
  if (claves.length) {
    const ul = crear('ul', 'pl-bloques');
    claves.forEach((c) => {
      const p = m.proyectos.get(c) || {};
      const li = crear('li');
      const b = crear('button', 'pl-bloque' + (p.otra ? ' otra' : '') + (planif.recien.has('j|' + c + '|' + d.iso) ? ' recien' + (planif.recienAjeno ? ' ajeno' : '') : ''));
      b.type = 'button';
      b.dataset.ancla = 'j|' + c + '|' + d.iso;
      b.style.setProperty('--pc', m.color(c));
      b.append(crear('span', 't', m.titulo(c)));
      if (p.lugar) b.append(crear('span', 's', p.lugar));
      const van = plOrdenPersonas(m.porProyecto.get(d.iso + '|' + c) || []);
      const w = crear('span', 'pl-pers');
      van.forEach((x) => w.append(plQuitarX(plArrastrable(plPersona(x), { tipo: 'persona', per: x, desde: { per: x, iso: d.iso, clave: c } }, plNom(x)), x, d, c, m)));
      b.append(w);
      const vs = plVehs(m, d, c, van);
      if (vs) b.append(vs);
      b.setAttribute('aria-label', m.titulo(c) + ', ' + plFechaLarga(d) + ': ' + plNoms(van) + plVehsTexto(m, d.iso, c, van) + '. Cambiar quiénes van');
      b.addEventListener('click', () => plAbrirProyecto(c, d.iso));
      li.append(b);
      ul.append(li);
    });
    col.append(ul);
  }
  // Sin nadie, la cabecera del día ya dice «Nadie asignado» (2026-11-05: sin repetirlo abajo)
  const libres = m.personas.filter((per) => !m.ausencias.has(d.iso + '|' + per) && !(m.porPersona.get(d.iso + '|' + per) || []).length);
  const ausentes = m.personas.filter((per) => m.ausencias.has(d.iso + '|' + per));
  [[libres, 'Sin proyecto', 'libre'], [ausentes, 'Ausentes', 'aus']].forEach(([lista, et, clase]) => {
    if (!lista.length) return;
    const f = crear('div', 'pl-libres');
    f.append(crear('span', 'et', et));
    lista.forEach((per) => {
      const b = plPersona(per, true);
      b.classList.add(clase);
      b.dataset.ancla = 'p|' + per + '|' + d.iso;
      const a = m.ausencias.get(d.iso + '|' + per);
      b.title = a ? plNom(per) + ': ' + plAusencia(a.motivo).nombre.toLowerCase() + ' ' + plElDia(d) : plNom(per) + ' no tiene proyecto ' + plElDia(d) + ': asignarle uno';
      b.setAttribute('aria-label', b.title);
      // Sin proyecto: se arrastra a un proyecto de ese día (o de otro)
      if (!a) { b.title += ', o arrástralo a un proyecto'; plArrastrable(b, { tipo: 'persona', per }, plNom(per)); }
      b.addEventListener('click', () => plAbrirPersona(per, d.iso));
      f.append(b);
    });
    col.append(f);
  });
  const nuevo = crear('button', 'rc-nueva pl-nuevo');
  nuevo.type = 'button';
  nuevo.dataset.ancla = 'n|' + d.iso;
  nuevo.append(icono('mas', 14), crear('span', null, 'Asignar'));
  nuevo.title = 'Asignar un proyecto ' + plElDia(d);
  nuevo.addEventListener('click', () => plAbrirNuevo(d.iso));
  col.append(nuevo);
  return col;
}
/* La semana al lado: una línea por día (cuántas personas tienen algo y una barra con el color de cada proyecto, ancha
   según cuántos van) que lo muestra en grande, y abajo los avisos: proyectos sin nadie, un vehículo en dos lugares y
   las ausencias. */
function plSemanaLado(s, m, dias, sel) {
  const lado = crear('aside', 'pl-sem-lado');
  lado.setAttribute('aria-label', 'La semana');
  lado.append(crear('h3', null, 'La semana'));
  const lista = crear('div', 'pl-sem-dias');
  lista.setAttribute('role', 'group');
  lista.setAttribute('aria-label', 'Día que se ve en grande');
  const elegir = (i) => {
    planif.diaMovil = i;
    plPintar();
    const x = $('#plGeneral .pl-sem-dia[data-dia="' + i + '"]');
    if (x) x.focus({ preventScroll: true });
  };
  const choques = [];
  dias.forEach((d) => {
    const claves = m.ordenar([...new Set(m.personas.flatMap((per) => m.porPersona.get(d.iso + '|' + per) || []))]);
    const van = m.personas.filter((per) => (m.porPersona.get(d.iso + '|' + per) || []).length);
    const dosLugares = PL_VEHICULOS.filter((v) => m.usoVeh(d.iso, v.id).length > 1);
    dosLugares.forEach((v) => choques.push({ d, v, n: m.usoVeh(d.iso, v.id).length }));
    const b = crear('button', 'pl-sem-dia' + plClaseDia(d));
    b.type = 'button';
    b.dataset.dia = String(d.i);
    b.setAttribute('aria-pressed', d.i === sel.i ? 'true' : 'false');
    const et = crear('span', 'pl-sem-et');
    et.append(crear('span', null, d.corto), crear('b', null, String(d.fecha.getDate())));
    const barra = crear('span', 'pl-sem-barra' + (claves.length ? '' : ' vacia'));
    claves.forEach((c) => {
      const i = crear('i');
      i.style.setProperty('--pc', m.color(c));
      i.style.flexGrow = String((m.porProyecto.get(d.iso + '|' + c) || []).length || 1);
      barra.append(i);
    });
    const alerta = crear('span', 'pl-sem-alerta');
    if (dosLugares.length) alerta.append(icono('vehiculo', 14));
    b.append(et, barra, crear('span', 'pl-sem-n', String(van.length)), alerta);
    b.title = plFechaLarga(d) + (d.hoy ? ' (hoy)' : '') + ': '
      + (van.length ? pl(van.length, 'persona', 'personas') + ' en ' + pl(claves.length, 'proyecto', 'proyectos') + ' (' + claves.map(m.titulo).join(', ') + ')' : 'nadie asignado')
      + dosLugares.map((v) => '. ' + mayuscula(plLaVeh(v)) + ' en ' + m.usoVeh(d.iso, v.id).length + ' lugares a la vez').join('')
      + (d.i === sel.i ? '' : '. Verlo en grande');
    b.setAttribute('aria-label', b.title);
    b.addEventListener('click', () => elegir(d.i));
    lista.append(b);
  });
  lado.append(lista);
  const avisos = crear('ul', 'pl-sem-avisos');
  const aviso = (texto, nivel, ico, accion, titulo) => {
    const li = crear('li');
    const x = crear(accion ? 'button' : 'span', 'pl-sem-aviso');
    if (accion) { x.type = 'button'; x.addEventListener('click', accion); }
    if (nivel) x.dataset.nivel = nivel;
    if (ico) x.append(icono(ico, 14));
    x.append(crear('span', null, texto));
    if (titulo) x.title = titulo;
    li.append(x);
    avisos.append(li);
  };
  if (m.sinAsignar.length) {
    aviso(pl(m.sinAsignar.length, 'proyecto', 'proyectos') + ' sin nadie ' + plEsta(s), s.id === plHoyId() ? 'bad' : 'warn', 'alerta', () => {
      const k = $('#plResumen .pl-kpi-alarma');
      if (k && !planif.alarmaAbierta) k.click();
      const caja = $('#plAlarma');
      if (caja && !caja.hidden) caja.scrollIntoView({ block: 'nearest', behavior: REDUCIR.matches ? 'auto' : 'smooth' });
    }, 'Ver cuáles son: ' + m.sinAsignar.map((p) => p.titulo).join(', '));
  }
  choques.forEach((c) => aviso(c.d.corto + ' ' + c.d.fecha.getDate() + ': ' + c.v.nombre + ' en ' + c.n + ' lugares', 'warn', 'vehiculo',
    () => elegir(c.d.i), mayuscula(plLaVeh(c.v)) + ' va a ' + c.n + ' lugares a la vez ' + plElDia(c.d) + '. Ver ese día en grande'));
  // Las ausencias, una línea por persona: «MP: vacaciones, 5 días»
  m.personas.forEach((per) => {
    const motivos = new Map();
    dias.forEach((d) => { const a = m.ausencias.get(d.iso + '|' + per); if (a) motivos.set(a.motivo, (motivos.get(a.motivo) || 0) + 1); });
    motivos.forEach((n, motivo) => aviso(plNomCorto(per) + ': ' + plAusencia(motivo).nombre.toLowerCase() + ', ' + pl(n, 'día', 'días'), '', null, null));
  });
  if (avisos.childElementCount) lado.append(avisos);
  return lado;
}
/* Un panel de abajo de General, plegado con una línea de lo que dice (2026-10-28: los tres abiertos eran demasiado);
   abierto o cerrado queda recordado en este navegador. */
function plPlegable(id, titulo, resumen) {
  const det = crear('details', 'pl-panel');
  det.dataset.panel = id;
  det.open = planif.paneles.has(id);
  const sum = crear('summary');
  sum.append(crear('h2', null, titulo), crear('span', 'pl-panel-res', resumen), icono('flecha', 16));
  det.append(sum);
  det.addEventListener('toggle', () => {
    if (det.open === planif.paneles.has(id)) return;
    if (det.open) planif.paneles.add(id); else planif.paneles.delete(id);
    plGuardarPrefs();
  });
  return det;
}
function plPaneles(s, m, dias) {
  const w = crear('div', 'pl-paneles');
  const tabla = (primera, ultimas) => {
    const t = crear('table', 'pl-cob');
    const thead = crear('thead'), tr = crear('tr');
    const th = crear('th', null, primera);
    th.scope = 'col';
    tr.append(th);
    dias.forEach((d) => { const x = crear('th', 'd', d.letra); x.scope = 'col'; x.title = plFechaLarga(d); tr.append(x); });
    ultimas.forEach(([txt, clase]) => { const x = crear('th', clase, txt); x.scope = 'col'; tr.append(x); });
    thead.append(tr);
    t.append(thead);
    return t;
  };
  // Lo que cubre cada proyecto activo
  const sin = new Set(m.sinAsignar.map((p) => p.clave));
  const conAlguien = m.activos.filter((p) => m.dias.has(p.clave)).length;
  const a = plPlegable('proyectos', 'Proyectos activos en la semana',
    pl(conAlguien, 'con alguien', 'con alguien') + (sin.size ? ' · ' + sin.size + ' sin asignar' : ''));
  const ta = tabla('Proyecto', [['Quiénes', 'q'], ['Días', 'n']]);
  const tba = crear('tbody');
  m.activos.slice().sort((x, y) => (sin.has(y.clave) - sin.has(x.clave)) || plPorTitulo(x, y)).forEach((p) => {
    const tr = crear('tr');
    const th = crear('th');
    th.scope = 'row';
    const b = crear('button', 'pl-cob-nom');
    b.type = 'button';
    b.style.setProperty('--pc', m.color(p.clave));
    b.append(crear('span', 'pl-dot'), crear('span', null, p.titulo));
    b.title = 'Ver ' + p.titulo + ' en «Por proyecto»';
    b.addEventListener('click', () => plEnfocar(p.clave));
    th.append(b);
    tr.append(th);
    const quienes = new Set();
    dias.forEach((d) => {
      const van = plOrdenPersonas(m.porProyecto.get(d.iso + '|' + p.clave) || []);
      van.forEach((x) => quienes.add(x));
      const td = crear('td', 'd');
      const q = crear('span', 'pl-cuadro' + (van.length ? ' si' : ''));
      q.style.setProperty('--pc', m.color(p.clave));
      q.title = plFechaLarga(d) + ': ' + (van.length ? plNoms(van) : 'nadie');
      td.append(q);
      tr.append(td);
    });
    const tq = crear('td', 'q');
    const wq = crear('span', 'pl-pers');
    plOrdenPersonas([...quienes]).forEach((x) => wq.append(plPersona(x)));
    tq.append(wq);
    const n = (m.dias.get(p.clave) || []).length;
    const tn = crear('td', 'n');
    tn.append(sin.has(p.clave) ? plChipEstado('Sin asignar', s.id === plHoyId() ? 'bad' : 'warn')
      : m.pausas.has(p.clave) && !n ? plChipEstado('Sin trabajo', '') : document.createTextNode(pl(n, 'día', 'días')));
    tr.append(tq, tn);
    tba.append(tr);
  });
  if (!m.activos.length) {
    const tr = crear('tr');
    const td = crear('td', null, 'No hay proyectos en ejecución en el Recorrido.');
    td.colSpan = dias.length + 3;
    tr.append(td);
    tba.append(tr);
  }
  ta.append(tba);
  a.append(ta);
  // La carga de cada persona: cuántos proyectos tiene cada día (hasta 3)
  const conProy = m.personas.filter((per) => dias.some((d) => (m.porPersona.get(d.iso + '|' + per) || []).length)).length;
  const b = plPlegable('personal', 'Personal en la semana', conProy + ' de ' + pl(m.personas.length, 'persona', 'personas') + ' con proyecto');
  const tb = tabla('Persona', [['Días', 'n']]);
  const tbb = crear('tbody');
  m.personas.forEach((per) => {
    const tr = crear('tr');
    const th = crear('th');
    th.scope = 'row';
    th.append(plPersona(per));
    tr.append(th);
    let con = 0, aus = 0;
    dias.forEach((d) => {
      const k = d.iso + '|' + per;
      const lista = m.porPersona.get(k) || [];
      const au = m.ausencias.get(k);
      if (au) aus++; else if (lista.length) con++;
      const td = crear('td', 'd');
      const q = crear('button', 'pl-cuadro ' + (au ? 'aus' : lista.length ? 'n' + Math.min(lista.length, 4) : ''), au || !lista.length ? '' : String(lista.length));
      q.type = 'button';
      q.dataset.ancla = 'q|' + per + '|' + d.iso;
      q.title = plNom(per) + ', ' + plFechaLarga(d) + ': ' + (au ? plAusencia(au.motivo).nombre.toLowerCase() : lista.length ? m.ordenar(lista).map(m.titulo).join(', ') : 'sin proyecto');
      q.setAttribute('aria-label', q.title + '. Cambiar');
      q.addEventListener('click', () => plAbrirPersona(per, d.iso, 'q|' + per + '|' + d.iso));
      td.append(q);
      tr.append(td);
    });
    tr.append(crear('td', 'n', con + ' de ' + (dias.length - aus)));
    tbb.append(tr);
  });
  tb.append(tbb);
  b.append(tb);
  w.append(a, b);
  if (PL_VEHICULOS.length) w.append(plPanelVehiculos(m, dias));
  return w;
}
/* Dónde va cada vehículo cada día y con quiénes (tocar uno abre ese proyecto ese día, donde se cambia); «Libre» si
   nadie lo lleva, y en naranjo si va a dos lugares a la vez: personas que no comparten proyecto ese día. */
function plPanelVehiculos(m, dias) {
  const choques = dias.filter((d) => PL_VEHICULOS.some((v) => m.usoVeh(d.iso, v.id).length > 1)).length;
  const sec = plPlegable('vehiculos', 'Vehículos en la semana', choques ? pl(choques, 'día', 'días') + ' con un vehículo en dos lugares'
    : PL_VEHICULOS.map((v) => { const n = dias.filter((d) => m.usoVeh(d.iso, v.id).length).length; return v.nombre + ' ' + (n ? pl(n, 'día', 'días') : 'libre'); }).join(' · '));
  sec.classList.add('pl-panel-veh');
  sec.id = 'plVehiculos';
  if (choques) sec.dataset.nivel = 'warn';
  const t = crear('table', 'pl-cob pl-vehs-t');
  const thead = crear('thead'), tr = crear('tr');
  const th0 = crear('th', 'dia', 'Día');
  th0.scope = 'col';
  tr.append(th0);
  PL_VEHICULOS.forEach((v) => {
    const th = crear('th');
    th.scope = 'col';
    const e = crear('span', 'pl-veh-th');
    e.append(icono('vehiculo', 16), crear('span', null, v.nombre));
    th.append(e);
    tr.append(th);
  });
  thead.append(tr);
  const tb = crear('tbody');
  dias.forEach((d) => {
    const fila = crear('tr', d.hoy ? 'hoy' : null);
    fila.dataset.iso = d.iso;          // no data-dia: en las tablas es el número del día que esconde el teléfono
    const th = crear('th', 'dia');
    th.scope = 'row';
    th.title = plFechaLarga(d) + (d.hoy ? ' (hoy)' : '');
    th.append(crear('span', null, d.corto), crear('b', null, String(d.fecha.getDate())));
    fila.append(th);
    PL_VEHICULOS.forEach((v) => {
      const td = crear('td');
      td.dataset.veh = v.id;
      const grupos = m.usoVeh(d.iso, v.id);
      if (!grupos.length) td.append(crear('span', 'pl-veh-libre', 'Libre'));
      grupos.forEach((g) => g.forEach((x) => {
        const b = crear('button', 'pl-veh-uso');
        b.type = 'button';
        b.dataset.ancla = 'v|' + v.id + '|' + x.clave + '|' + d.iso;
        b.style.setProperty('--pc', m.color(x.clave));
        b.append(crear('span', 'pl-dot'), crear('span', 't', m.titulo(x.clave)), crear('span', 'quien', x.personas.map(plNomCorto).join(' ')));
        b.title = mayuscula(plLaVeh(v)) + ' ' + plElDia(d) + ': ' + m.titulo(x.clave) + ', con ' + plNoms(x.personas) + '. Toca para cambiarlo';
        b.setAttribute('aria-label', b.title);
        b.addEventListener('click', () => plAbrirProyecto(x.clave, d.iso, b.dataset.ancla));
        td.append(b);
      }));
      if (grupos.length > 1) {
        td.dataset.nivel = 'warn';
        const n = crear('span', 'pl-veh-choque', 'En ' + grupos.length + ' lugares a la vez');
        n.title = 'Van en ' + plLaVeh(v) + ' personas que ' + plElDia(d) + ' no comparten proyecto: revisa si van juntas o si alguien cambia de vehículo';
        td.append(n);
      }
      fila.append(td);
    });
    tb.append(fila);
  });
  const tf = crear('tfoot'), pie = crear('tr');
  const thf = crear('th', 'dia', 'Semana');
  thf.scope = 'row';
  pie.append(thf);
  PL_VEHICULOS.forEach((v) => {
    const n = dias.filter((d) => m.usoVeh(d.iso, v.id).length).length;
    pie.append(crear('td', 'n', n ? n + ' de ' + pl(dias.length, 'día', 'días') : 'Sin uso'));
  });
  tf.append(pie);
  t.append(thead, tb, tf);
  sec.append(t);
  return sec;
}

// ---- Arrastrar a las casillas (2026-10-28) --------------------------------------------------------------------
/* Junto a «Por personal», los proyectos activos; junto a «Por proyecto», las personas. Se arrastran a la casilla de un
   día, o se tocan y después se van tocando casillas (así también con el dedo). Lo ya asignado en una casilla también
   se arrastra: a otra casilla se mueve y, con Ctrl, se copia. En General se arrastran las personas a un proyecto de un
   día. Tocar la casilla y elegir en la ventanita sigue igual. Lo arrastrado: { tipo: 'proyecto', clave } o { tipo:
   'persona', per }, con desde: { per, iso, clave } si sale de una casilla. */
function plConArrastre(tabla, panel) {
  const w = crear('div', 'pl-con-arr' + (planif.armado ? ' pl-colocando' : ''));
  w.append(tabla, panel);
  return w;
}
function plArrastrable(el, x, nombre) {
  if (soloLectura()) return el;
  el.draggable = true;
  el.classList.add('pl-arrastrable');
  if (x.desde) el.title = (el.title || nombre) + ' · Arrástralo a otra casilla para moverlo (con Ctrl, se copia)';
  if (x.desde) el.dataset.asig = x.desde.per + '|' + x.desde.iso + '|' + x.desde.clave;     // donde se suelta un vehículo
  el.addEventListener('dragstart', (e) => {
    e.stopPropagation();
    planif.arrastre = Object.assign({}, x, { m: plModelo(plSemanaVista()) });     // el modelo, una vez: dragover llega muy seguido
    plCerrarPop(false);
    e.dataTransfer.effectAllowed = x.desde ? 'copyMove' : 'copy';
    e.dataTransfer.setData('text/plain', nombre);
    $('#vistaPlan').classList.add('pl-arrastrando');
    requestAnimationFrame(() => el.classList.add('pl-origen'));
  });
  el.addEventListener('dragend', plArrFin);
  return el;
}
// La casilla (o el proyecto de un día, en General) que tiene el puntero: { el, iso, per } o { el, iso, clave }
function plDestino(t) {
  const b = t && t.closest ? t.closest('#vistaPlan [data-ancla]') : null;
  const [k, x, iso] = b ? b.dataset.ancla.split('|') : [];
  const d = k === 'p' ? { el: b, per: x, iso } : k === 'j' ? { el: b, clave: x, iso } : null;
  // Un proyecto de una persona (o una persona de un proyecto) dentro de la casilla: ahí va un vehículo
  const ch = d && t.closest('[data-asig]');
  if (ch && b.contains(ch)) { const [per, , clave] = ch.dataset.asig.split('|'); d.asig = { per, clave }; d.chip = ch; }
  return d;
}
/* Vehículos (2026-11-12, observación del equipo: «los vehículos deberían poder arrastrarse»): la Quempineta y la RAM
   van arriba del panel. Se sueltan (o se toca uno y después) sobre un proyecto ya asignado: un proyecto de una
   persona, una persona de un proyecto, la casilla de una persona con un solo proyecto ese día, o la de un proyecto
   (todos los que van ese día). Lo arrastrado: { tipo: 'vehiculo', id }. El objetivo: { veh, iso, pares: [{ per, clave }] }. */
function plObjetivoVeh(x, d, m) {
  let pares = [];
  if (d.asig) pares = [d.asig];
  else if (d.per) { const l = m.porPersona.get(d.iso + '|' + d.per) || []; if (l.length === 1) pares = [{ per: d.per, clave: l[0] }]; }
  else if (d.clave) pares = (m.porProyecto.get(d.iso + '|' + d.clave) || []).map((per) => ({ per, clave: d.clave }));
  return { veh: x.id, iso: d.iso, pares, el: d.chip || d.el, varios: !!d.per && !d.asig && (m.porPersona.get(d.iso + '|' + d.per) || []).length > 1 };
}
// Lo arrastrado (o elegido en el panel) en ese destino: la asignación que quedaría, o null si no encaja ahí
function plObjetivo(x, d, m) {
  if (!x || !d) return null;
  if (x.tipo === 'vehiculo') return plObjetivoVeh(x, d, m || x.m || plModelo(plSemanaVista()));
  if (x.tipo === 'proyecto' && d.per) return { per: d.per, iso: d.iso, clave: x.clave };
  if (x.tipo === 'persona' && d.clave) return { per: x.per, iso: d.iso, clave: d.clave };
  return null;
}
// Por qué no se puede soltar ahí, en corto para la casilla ('' si se puede; 'mismo' si es de donde salió)
function plPorQueNo(m, x, a, copiar) {
  if (a.veh) return a.varios ? 'Suéltalo en un proyecto' : !a.pares.length ? 'Sin proyecto'
    : a.pares.every((p) => m.vehiculo(a.iso, p.per, p.clave) === a.veh) ? 'Ya va' : '';
  const d = x.desde;
  if (d && d.per === a.per && d.iso === a.iso && d.clave === a.clave) return 'mismo';
  const suyos = m.porPersona.get(a.iso + '|' + a.per) || [];
  if (m.ausencias.has(a.iso + '|' + a.per)) return 'Ausente';
  if (suyos.includes(a.clave)) return 'Ya está';
  const libera = d && !copiar && d.per === a.per && d.iso === a.iso ? 1 : 0;   // cambiar de proyecto el mismo día deja su lugar
  if (suyos.length - libera >= PL_MAX) return 'Ya tiene ' + PL_MAX;
  return '';
}
let plArrMarcada = null;
function plArrMarcar(el, no) {
  if (plArrMarcada && plArrMarcada !== el) { plArrMarcada.classList.remove('pl-soltar-si', 'pl-soltar-no'); delete plArrMarcada.dataset.no; }
  plArrMarcada = el;
  if (!el) return;
  el.classList.toggle('pl-soltar-si', !no);
  el.classList.toggle('pl-soltar-no', !!no);
  if (no) el.dataset.no = no; else delete el.dataset.no;
}
function plArrSobre(e) {
  const x = planif.arrastre;
  if (!x) return;
  const d = plDestino(e.target);
  const a = plObjetivo(x, d);
  const copiar = e.ctrlKey || e.metaKey;
  const no = a ? plPorQueNo(x.m, x, a, copiar) : '';
  const el = a && a.el ? a.el : d && d.el;
  if (!a || no) { plArrMarcar(a && no !== 'mismo' ? el : null, no); return; }     // sin preventDefault no se suelta
  e.preventDefault();
  e.dataTransfer.dropEffect = x.desde && !copiar ? 'move' : 'copy';
  plArrMarcar(el, '');
}
function plArrSoltar(e) {
  const x = planif.arrastre;
  if (!x) return;
  e.preventDefault();
  const a = plObjetivo(x, plDestino(e.target));
  const copiar = e.ctrlKey || e.metaKey;
  plArrFin();
  if (a && a.veh) { if (!plPorQueNo(plModelo(plSemanaVista()), x, a)) plVehiculoPoner(plSemanaVista(), a.veh, a.iso, a.pares); }
  else if (a) plSoltar(x, a, copiar);
}
function plArrFin() {
  planif.arrastre = null;
  plArrMarcar(null);
  $('#vistaPlan').classList.remove('pl-arrastrando');
  document.querySelectorAll('#vistaPlan .pl-origen').forEach((el) => el.classList.remove('pl-origen'));
  if (planif.repintar) { planif.repintar = false; plPintar(); }      // lo que llegó del equipo mientras se arrastraba
}
/* Soltar: lo del panel (o copiado con Ctrl) se asigna como en la ventanita; lo que sale de una casilla se mueve en una
   sola tanda (un aviso, un Deshacer). El vehículo sigue a la persona si se queda en el mismo día. */
function plSoltar(x, a, copiar) {
  const s = plSemanaVista();
  if (!x.desde || copiar) return plAsignarDias(s, a.per, a.clave, [a.iso], true);
  const m = plModelo(s);
  if (plPorQueNo(m, x, a, false)) return false;
  const d = x.desde;
  const cambios = [{ tipo: 'asig', dia: d.iso, persona: d.per, clave: d.clave, activa: false }, { tipo: 'asig', dia: a.iso, persona: a.per, clave: a.clave, activa: true }];
  const v = d.per === a.per && d.iso === a.iso ? m.vehiculo(d.iso, d.per, d.clave) : '';
  if (v) cambios.push({ tipo: 'veh', dia: a.iso, persona: a.per, clave: a.clave, vehiculo: v });
  if (m.pausas.has(a.clave)) cambios.push({ tipo: 'pau', clave: a.clave, activa: false });
  const dd = plElDia(plDiaDe(s, d.iso)), da = plElDia(plDiaDe(s, a.iso));
  const msg = d.per === a.per && d.clave === a.clave ? plNom(a.per) + ' va a ' + m.titulo(a.clave) + ' ' + da + ' en vez ' + dd.replace(/^el /, 'del ') + '.'
    : d.per === a.per ? plNom(a.per) + ' cambia de ' + m.titulo(d.clave) + ' a ' + m.titulo(a.clave) + ' ' + da + (d.iso === a.iso ? '' : ' (estaba ' + dd + ')') + '.'
    : plNom(a.per) + ' va a ' + m.titulo(a.clave) + ' ' + da + ' en vez de ' + plNom(d.per)
      + (d.iso === a.iso && d.clave === a.clave ? '' : ', que ya no va a ' + m.titulo(d.clave) + ' ' + dd) + '.';
  return plCambiar(s, cambios, msg);
}
// Con algo elegido en el panel, tocar una casilla lo pone ahí (o lo quita, si ya estaba). Devuelve si lo hizo.
function plColocar(d) {
  const a = plObjetivo(planif.armado, d);
  if (!a) return false;
  const s = plSemanaVista();
  if (a.veh) {
    // Tocar donde ya va lo quita; donde no se puede, lo dice (y no abre la ventanita)
    const m = plModelo(s);
    if (!a.pares.length || a.varios) { avisar(a.varios ? 'Ese día tiene más de un proyecto: toca el proyecto donde va ' + plLaVeh(plVehiculo(a.veh)) + '.' : 'Ahí no hay nadie asignado: primero asigna el proyecto.'); return true; }
    const ya = a.pares.every((p) => m.vehiculo(a.iso, p.per, p.clave) === a.veh);
    plVehiculoPoner(s, ya ? '' : a.veh, a.iso, a.pares);
    return true;
  }
  const ya = (plModelo(s).porPersona.get(a.iso + '|' + a.per) || []).includes(a.clave);
  plAsignarDias(s, a.per, a.clave, [a.iso], !ya);
  return true;
}
// El panel: los proyectos activos (primero los sin asignar) o las personas, para arrastrar o elegir
function plPanelArrastre(s, m, dias, tipo) {
  const proy = tipo === 'proyecto';
  const aside = crear('aside', 'pl-arr');
  aside.dataset.tipo = tipo;
  aside.setAttribute('aria-label', proy ? 'Proyectos activos para poner en las casillas' : 'Personal para poner en las casillas');
  const elegido = planif.armado && (planif.armado.tipo === tipo || planif.armado.tipo === 'vehiculo') ? planif.armado : null;
  const vehElegido = elegido && elegido.tipo === 'vehiculo' ? plVehiculo(elegido.id) : null;
  // En lo angosto va arriba de la tabla: plegado en una línea hasta pedirlo, así la semana se ve de entrada (2026-10-29)
  const abierto = planif.arrAbierto || !!elegido;
  aside.classList.toggle('abierto', abierto);
  const cab = crear('div', 'pl-arr-cab');
  const tog = crear('button', 'cx-enlace pl-arr-abrir');
  tog.type = 'button';
  tog.setAttribute('aria-expanded', abierto ? 'true' : 'false');
  tog.append(crear('span', null, abierto ? 'Ocultar' : 'Asignar tocando'), icono('flecha', 14));
  tog.title = abierto ? 'Ocultar la lista' : (proy ? 'Elegir un proyecto' : 'Elegir a alguien') + ' y después tocar las casillas donde va';
  tog.addEventListener('click', () => { planif.arrAbierto = !abierto; if (abierto) planif.armado = null; plPintar(); });
  cab.append(crear('h2', null, proy ? 'Proyectos activos' : 'Personal'), tog);
  aside.append(cab);
  if (elegido) {
    const bar = crear('div', 'pl-arr-colocando');
    bar.setAttribute('role', 'status');
    const p = crear('p');
    if (vehElegido) p.append('Toca los proyectos donde va ', crear('b', null, plLaVeh(vehElegido)), '. Otra vez en el mismo, lo quita.');
    else p.append('Toca las casillas donde va ', crear('b', null, proy ? m.titulo(elegido.clave) : plNom(elegido.per)), '. Otra vez en la misma casilla, lo quita.');
    const listo = crear('button', 'cx-boton pl-arr-listo', 'Listo');
    listo.type = 'button';
    listo.addEventListener('click', () => { planif.armado = null; plPintar(); });
    bar.append(p, listo);
    aside.append(bar);
  } else {
    aside.append(crear('p', 'pl-arr-pista-corta', (proy ? 'Toca un proyecto' : 'Toca a alguien') + ' y después las casillas donde va.'));
  }
  // Los vehículos, arriba: se sueltan sobre un proyecto ya asignado (plObjetivoVeh)
  if (PL_VEHICULOS.length) {
    const fila = crear('div', 'pl-arr-vehs');
    fila.setAttribute('role', 'group');
    fila.setAttribute('aria-label', 'Vehículos');
    PL_VEHICULOS.forEach((v) => {
      const x = { tipo: 'vehiculo', id: v.id };
      const sel = !!vehElegido && vehElegido.id === v.id;
      const b = crear('button', 'pl-arr-veh');
      b.type = 'button';
      b.dataset.vehiculo = v.id;
      b.setAttribute('aria-pressed', sel ? 'true' : 'false');
      b.append(icono('vehiculo', 16), crear('span', null, v.nombre));
      b.title = v.nombre + (sel ? '. Tocar otra vez deja de ponerlo' : '. Arrástralo a un proyecto ya asignado, o tócalo y después toca los proyectos');
      plArrastrable(b, x, v.nombre);
      b.addEventListener('click', () => { planif.armado = sel ? null : x; plPintar(); });
      fila.append(b);
    });
    aside.append(fila);
  }
  // Los grupos: [título, nivel, [{ x, nombre, meta, marca }]]
  let grupos;
  if (proy) {
    const sin = new Set(m.sinAsignar.map((p) => p.clave));
    const item = (p) => ({ x: { tipo, clave: p.clave }, nombre: p.titulo, meta: [p.req ? 'N° ' + p.req : '', p.lugar].filter(Boolean).join(' · '),
      marca: m.dias.has(p.clave) ? pl(m.dias.get(p.clave).length, 'día', 'días') : '' });
    const orden = m.activos.slice().sort(plPorTitulo);
    grupos = [['Sin asignar', s.id === plHoyId() ? 'bad' : 'warn', orden.filter((p) => sin.has(p.clave)).map(item)],
      ['Con alguien esta semana', '', orden.filter((p) => m.dias.has(p.clave)).map(item)],
      ['Sin trabajo esta semana', '', orden.filter((p) => !sin.has(p.clave) && !m.dias.has(p.clave)).map(item)]];
  } else {
    grupos = [['', '', m.personas.map((per) => {
      const aus = dias.filter((d) => m.ausencias.has(d.iso + '|' + per)).length;
      const con = dias.filter((d) => (m.porPersona.get(d.iso + '|' + per) || []).length).length;
      return { x: { tipo, per }, nombre: plNom(per), meta: aus === dias.length ? 'Ausente' : con + ' de ' + pl(dias.length - aus, 'día', 'días') };
    })]];
  }
  const total = grupos.reduce((n, g) => n + g[2].length, 0);
  const lista = crear('div', 'pl-arr-lista');
  const pintarLista = () => {
    lista.textContent = '';
    const q = norm(planif.arrQ);
    grupos.forEach(([titulo, nivel, items]) => {
      const vis = items.filter((it) => !q || norm(it.nombre + ' ' + (it.meta || '')).includes(q));
      if (!vis.length) return;
      if (titulo) {
        const h = crear('h3', 'pl-arr-grupo', titulo + ' · ' + vis.length);
        if (nivel) h.dataset.nivel = nivel;
        lista.append(h);
      }
      vis.forEach((it) => {
        const sel = !!elegido && !vehElegido && (proy ? elegido.clave === it.x.clave : elegido.per === it.x.per);
        const b = crear('button', 'pl-arr-item');
        b.type = 'button';
        b.setAttribute('aria-pressed', sel ? 'true' : 'false');
        if (proy) { b.dataset.clave = it.x.clave; b.style.setProperty('--pc', m.color(it.x.clave)); b.append(crear('span', 'pl-dot')); }
        else {
          b.dataset.persona = it.x.per;
          b.append(crear('span', 'pl-avatar' + (PL_PER_MANO.test(it.x.per) ? ' mano' : '') + (it.x.per === estado.usuario ? ' tuya' : ''), plIniciales(it.x.per)));
        }
        const tx = crear('span', 'pl-arr-txt');
        tx.append(crear('span', 't', it.nombre));
        if (it.meta) tx.append(crear('span', 's', it.meta));
        b.append(tx);
        if (it.marca) b.append(crear('span', 'pl-arr-marca', it.marca));
        b.title = it.nombre + (it.meta ? ' · ' + it.meta : '') + (sel ? '. Tocar otra vez deja de ponerlo' : '. Arrástralo a una casilla, o tócalo y después toca las casillas');
        plArrastrable(b, it.x, it.nombre);
        b.addEventListener('click', () => { planif.armado = sel ? null : it.x; plPintar(); });
        lista.append(b);
      });
    });
    if (!lista.childElementCount) lista.append(crear('p', 'pl-arr-pista', total ? 'Nada con «' + planif.arrQ + '».' : proy ? 'No hay proyectos en ejecución en el Recorrido.' : 'No hay personas en la lista.'));
  };
  if (total > 12) {
    const bus = crear('input', 'pl-arr-buscar');
    bus.type = 'search';
    bus.placeholder = proy ? 'Buscar proyecto' : 'Buscar persona';
    bus.setAttribute('aria-label', bus.placeholder);
    bus.autocomplete = 'off';
    bus.value = planif.arrQ;
    bus.addEventListener('input', () => { planif.arrQ = bus.value; pintarLista(); });
    aside.append(bus);
  }
  pintarLista();
  aside.append(lista);
  return aside;
}

// ---- La ventanita de una casilla ------------------------------------------------------------------------
let plPopRecien = false;     // el clic que la abrió no la cierra al llegar al documento
const plAncla = (k) => (k ? document.querySelector('#vistaPlan [data-ancla="' + CSS.escape(k) + '"]') : null);
function plAbrir(pop) {
  if (mvNoSe()) return;      // solo lectura (js/resumen.js): la ventanita es para cambiar la casilla
  // Tocar otra vez la casilla de la ventanita abierta la cierra
  if (planif.pop && planif.pop.ancla === pop.ancla && !$('#plPop').hidden) { plCerrarPop(false); return; }
  cerrarUsuario(false);
  planif.pop = pop;
  plPopRecien = true;
  setTimeout(() => { plPopRecien = false; }, 0);
  $('#plPop').hidden = false;
  plPintarPop(true);
}
// dias: los días elegidos en la franja «Qué días» (al abrir, el de la casilla); cambiar: «Cambiar» a medio elegir
const plAbrirPersona = (per, iso, ancla) => plAbrir({ tipo: 'persona', per, iso, dias: [iso], ancla: ancla || 'p|' + per + '|' + iso, q: '' });
const plAbrirProyecto = (clave, iso, ancla, alarma) => plAbrir({ tipo: 'proyecto', clave, iso, dias: [iso], ancla: ancla || 'j|' + clave + '|' + iso, alarma: !!alarma, q: '' });
const plAbrirNuevo = (iso) => plAbrir({ tipo: 'nuevo', iso, dias: [iso], ancla: 'n|' + iso, q: '' });
function plCerrarPop(devolverFoco) {
  const pop = $('#plPop');
  const ancla = planif.pop && planif.pop.ancla;
  planif.pop = null;
  if (pop.hidden) return;
  pop.hidden = true;
  if (devolverFoco) { const a = plAncla(ancla); if (a) a.focus(); }
}
function plColocarPop() {
  const pop = $('#plPop');
  if (pop.hidden || !planif.pop) return;
  if (MOVIL.matches) { pop.style.left = ''; pop.style.top = ''; return; }   // en el teléfono sube desde abajo (CSS)
  const a = plAncla(planif.pop.ancla);
  if (!a) return;
  const r = a.getBoundingClientRect();
  const w = pop.offsetWidth, h = pop.offsetHeight;
  let y = r.bottom + 6;
  if (y + h > innerHeight - 12) y = r.top - 6 - h >= 12 ? r.top - 6 - h : innerHeight - 12 - h;
  pop.style.left = Math.max(12, Math.min(r.left, innerWidth - 12 - w)) + 'px';
  pop.style.top = Math.max(12, y) + 'px';
}
function plPintarPop(primera) {
  const pop = $('#plPop');
  const x = planif.pop;
  if (!x || pop.hidden) return;
  const s = plSemanaVista();
  const d = plDiaDe(s, x.iso);
  if (!s.leida || d.i < 0 || d.i > 5) { plCerrarPop(false); return; }
  const m = plModelo(s);
  /* Los días elegidos, entre los que están a la vista. El día de la casilla sigue en la franja aunque su columna se
     esconda con la ventanita abierta (el sábado al quitarle lo último): si no, lo marcado caería en otro día. */
  const visibles = plDias(s);
  if (!visibles.some((y) => y.iso === x.iso)) visibles.push(d);
  x.dias = visibles.map((y) => y.iso).filter((iso) => x.dias.includes(iso));
  if (!x.dias.length) x.dias = [x.iso];
  const ds = x.dias.map((iso) => plDiaDe(s, iso));
  const cuerpo = $('#plPopCuerpo');
  const a = document.activeElement;
  const enfocado = a && pop.contains(a) ? a.dataset.op : null;
  const scroll = cuerpo.scrollTop;
  cuerpo.textContent = '';
  $('#plPopSiguiente').hidden = true;
  plPopDias(s, m, visibles, x);
  if (x.tipo === 'persona') plPopPersona(s, m, ds, x, cuerpo);
  else if (x.tipo === 'proyecto') plPopProyecto(s, m, ds, x, cuerpo);
  else plPopNuevo(s, m, ds, x, cuerpo);
  cuerpo.scrollTop = primera ? 0 : scroll;
  plColocarPop();
  const volver = enfocado && pop.querySelector('[data-op="' + CSS.escape(enfocado) + '"]');
  if (volver && !volver.disabled) volver.focus({ preventScroll: true });
  else if (primera || enfocado) {
    // En el computador, el buscador (se escribe y filtra); en el teléfono, nada que abra el teclado
    const f = cuerpo.querySelector(MOVIL.matches ? 'input[type="checkbox"]:not([disabled]), button:not([disabled])' : 'input:not([disabled]), button:not([disabled])');
    if (f) f.focus({ preventScroll: true });
  }
}
/* La franja «Qué días»: lo que se marca en la ventanita vale para todos los días elegidos, en un solo paso (un aviso y
   un «Deshacer»). Cada día dice en su título cómo está ese día: ausente, completo, cuántos van. */
function plPopDias(s, m, visibles, x) {
  const cont = $('#plPopDias');
  cont.textContent = '';
  cont.hidden = false;
  const elegir = (isos) => { x.dias = isos; x.cambiar = null; plPintarPop(false); };
  const iguales = (isos) => isos.length === x.dias.length && isos.every((iso) => x.dias.includes(iso));
  const cab = crear('div', 'pl-dias-cab');
  cab.append(crear('span', 'pl-dias-tit', 'Qué días'));
  const rapido = (op, txt, isos, titulo) => {
    if (!isos.length) return;
    const b = crear('button', 'pl-dias-r', txt);
    b.type = 'button';
    b.dataset.op = op;
    b.title = titulo;
    b.setAttribute('aria-pressed', iguales(isos) ? 'true' : 'false');
    b.addEventListener('click', () => elegir(isos));
    cab.append(b);
  };
  const todos = visibles.map((d) => d.iso);
  rapido('d|todos', 'Toda la semana', todos, 'Elegir todos los días a la vista');
  if (x.tipo === 'persona') {
    rapido('d|libres', 'Días libres', todos.filter((iso) => !m.ausencias.has(iso + '|' + x.per) && !(m.porPersona.get(iso + '|' + x.per) || []).length),
      'Los días en que ' + plNom(x.per) + ' no tiene proyectos ni ausencia');
  } else if (x.tipo === 'proyecto') {
    rapido('d|libres', 'Días sin nadie', todos.filter((iso) => !(m.porProyecto.get(iso + '|' + x.clave) || []).length), 'Los días en que nadie va a este proyecto');
  }
  const casilla = plDiaDe(s, x.iso);
  if (!iguales([x.iso])) rapido('d|solo', 'Solo ' + casilla.corto.toLowerCase() + ' ' + casilla.fecha.getDate(), [x.iso], 'Volver al día de la casilla: ' + plFechaLarga(casilla));
  const fila = crear('div', 'pl-dias-fila');
  visibles.forEach((d) => {
    const si = x.dias.includes(d.iso);
    const b = crear('button', 'pl-dia-op' + plClaseDia(d));
    b.type = 'button';
    b.dataset.op = 'd|' + d.iso;
    b.setAttribute('aria-pressed', si ? 'true' : 'false');
    b.append(crear('span', null, d.corto), crear('b', null, String(d.fecha.getDate())));
    let como = '';
    if (x.tipo === 'persona') {
      const au = m.ausencias.get(d.iso + '|' + x.per);
      const n = (m.porPersona.get(d.iso + '|' + x.per) || []).length;
      como = au ? 'ausente (' + plAusencia(au.motivo).nombre.toLowerCase() + ')' : n >= PL_MAX ? 'completo, con ' + PL_MAX + ' proyectos' : n ? pl(n, 'proyecto', 'proyectos') : 'sin proyecto';
      if (au || n >= PL_MAX) b.classList.add('bloq');
    } else if (x.tipo === 'proyecto') {
      const n = (m.porProyecto.get(d.iso + '|' + x.clave) || []).length;
      como = n ? pl(n, 'persona', 'personas') : 'nadie';
    }
    b.setAttribute('aria-label', plFechaLarga(d) + (d.hoy ? ' (hoy)' : '') + (como ? ', ' + como : ''));
    b.title = plFechaLarga(d) + (d.hoy ? ' (hoy)' : '') + (como ? ': ' + como : '') + (!si ? '. Toca para sumarlo' : x.dias.length > 1 ? '. Toca para sacarlo' : '');
    b.addEventListener('click', () => { if (!si || x.dias.length > 1) elegir(si ? x.dias.filter((iso) => iso !== d.iso) : x.dias.concat(d.iso)); });
    fila.append(b);
  });
  cont.append(cab, fila);
}
const plCortos = (ds) => ds.map((d) => d.corto.toLowerCase() + ' ' + d.fecha.getDate()).join(', ');     // «lun 19, mié 21»
/* Un buscador sobre la lista de la ventanita (con muchas opciones); lo escrito sigue al repintar. Enter elige la primera
   opción a la vista: la marca y cierra la ventanita, o entra en ella. */
function plBuscador(x, cuerpo, cont, placeholder) {
  const inp = crear('input', 'pl-buscar');
  inp.type = 'search';
  inp.autocomplete = 'off';
  inp.placeholder = placeholder;
  inp.setAttribute('aria-label', placeholder + '. Enter elige el primero');
  inp.dataset.op = 'buscar';
  inp.value = x.q || '';
  const filtrar = () => {
    x.q = inp.value;
    const q = norm(inp.value).trim().split(/\s+/).filter(Boolean);
    cont.querySelectorAll('li[data-buscar]').forEach((li) => { li.hidden = !q.every((y) => li.dataset.buscar.includes(y)); });
    cont.querySelectorAll('.pl-grupo').forEach((g) => { g.hidden = !g.querySelector('li[data-buscar]:not([hidden])'); });
  };
  inp.addEventListener('input', filtrar);
  inp.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || !norm(inp.value).trim()) return;
    e.preventDefault();
    const li = cont.querySelector('li[data-buscar]:not([hidden])');
    const c = li && li.querySelector('input[type="checkbox"], button.pl-op');
    if (!c || c.disabled) return;
    if (c.type !== 'checkbox') { c.click(); return; }
    if (!c.checked) c.click();
    plCerrarPop(true);
  });
  cuerpo.append(inp);
  return filtrar;
}
// Una opción de la lista: su casilla, su marca (color o iniciales), su nombre y, al lado, «Cambiar» si ya está elegida;
// debajo, con qué vehículo va
function plOpcion(ul, buscar, casilla, marca, titulo, sub, extra, debajo) {
  const li = crear('li');
  li.dataset.buscar = buscar;
  const lab = crear('label', 'pl-op' + (casilla.disabled ? ' no' : ''));
  const tx = crear('span', 'pl-op-txt');
  tx.append(crear('span', 't', titulo));
  if (sub) tx.append(typeof sub === 'string' ? crear('span', 's', sub) : sub);
  lab.append(casilla, marca, tx);
  li.append(lab);
  if (extra) li.append(extra);
  if (debajo) { li.classList.add('con-debajo'); li.append(debajo); }
  ul.append(li);
}
/* Con qué vehículo va una persona a un proyecto, los días elegidos en que va: un toque asigna uno y, si ya era el suyo,
   lo quita. Con varios días queda a medias si lo lleva solo algunos (tocarlo lo pone en todos). Un punto naranjo dice
   que ese vehículo ya va con otros a otra parte alguno de esos días (se puede igual: pueden ir pasando). */
function plVehOps(s, m, per, clave, isos, op) {
  const fila = crear('div', 'pl-op-veh');
  fila.setAttribute('role', 'group');
  fila.setAttribute('aria-label', 'Vehículo de ' + plNom(per) + ' en ' + m.titulo(clave));
  const et = crear('span', 'et');
  et.append(icono('vehiculo', 16), crear('span', null, 'Vehículo'));
  fila.append(et);
  const cuando = plDiasTexto(s, isos);
  PL_VEHICULOS.forEach((v) => {
    const con = isos.filter((iso) => m.vehiculo(iso, per, clave) === v.id);
    const todos = con.length === isos.length;
    const otros = isos.map((iso) => ({ iso, g: m.vehOtros(iso, v.id, per, clave) })).filter((x) => x.g.length);
    const b = crear('button', 'pl-veh-op' + (otros.length ? ' ocupado' : ''));
    b.type = 'button';
    b.dataset.op = op + '|' + v.id;
    b.setAttribute('aria-pressed', todos ? 'true' : con.length ? 'mixed' : 'false');
    b.append(crear('span', null, v.nombre));
    // Ocupado en otra parte: dice quién lo lleva (2026-10-29: antes era solo un punto naranjo, sin explicación)
    const quien = [...new Set(otros.flatMap((x) => x.g.flat().flatMap((y) => y.personas)))];
    if (quien.length) b.append(crear('span', 'pl-veh-op-q', (v.articulo === 'el' ? 'lo' : 'la') + (quien.length > 1 ? ' llevan ' : ' lleva ') + quien.map(plNomCorto).join(', ')));
    const ojo = otros.length ? '. Ojo: ' + plDiasTexto(s, otros.map((x) => x.iso)) + ' ' + plLaVeh(v) + ' también va a '
      + unir([...new Set(otros.flatMap((x) => x.g.flat().map((y) => m.titulo(y.clave) + ' (' + plNoms(y.personas) + ')')))]) : '';
    b.title = (todos ? 'Quitar ' + plLaVeh(v) + ' a ' + plNom(per) + ' ' + cuando : plNom(per) + ' va en ' + plLaVeh(v) + ' ' + cuando) + ojo;
    b.setAttribute('aria-label', v.nombre + (otros.length ? ', que ya va a otra parte' : ''));     // elegido o a medias: aria-pressed
    b.addEventListener('click', () => plVehiculoDias(s, per, clave, isos, todos ? '' : v.id));
    fila.append(b);
  });
  return fila;
}
// Una opción que lleva a otra parte (el proyecto que se elige, a quién se pasa): su marca, su nombre y una flecha
function plBotonLista(ul, op, buscar, marca, titulo, sub, ir) {
  const li = crear('li');
  li.dataset.buscar = buscar;
  const b = crear('button', 'pl-op');
  b.type = 'button';
  b.dataset.op = op;
  const tx = crear('span', 'pl-op-txt');
  tx.append(crear('span', 't', titulo));
  if (sub) tx.append(sub);
  const f = crear('span', 'pl-flecha');
  f.append(icono('derecha', 15));
  b.append(marca, tx, f);
  b.addEventListener('click', ir);
  li.append(b);
  ul.append(li);
  return b;
}
// La línea de abajo de una opción, con un aviso en rojo al comienzo si hace falta («Sin nadie esta semana»)
function plSub(partes, alerta) {
  const txt = partes.filter(Boolean).join(' · ');
  if (!txt && !alerta) return null;
  const e = crear('span', 's');
  if (alerta) e.append(crear('b', 'pl-op-alerta', alerta), txt ? ' · ' : '');
  e.append(txt);
  return e;
}
function plCasilla(op, si, no, alCambiar) {
  const cb = crear('input');
  cb.type = 'checkbox';
  cb.checked = si;
  cb.disabled = no;
  cb.dataset.op = op;
  cb.addEventListener('change', () => alCambiar(cb.checked));
  return cb;
}
function plBotonOp(op, txt, titulo, ir) {
  const b = crear('button', 'pl-op-btn', txt);
  b.type = 'button';
  b.dataset.op = op;
  b.title = titulo;
  b.addEventListener('click', ir);
  return b;
}
function plVolver(txt, ir) {
  const b = crear('button', 'cx-enlace pl-pop-volver', '‹ ' + txt);
  b.type = 'button';
  b.dataset.op = 'volver';
  b.addEventListener('click', ir);
  return b;
}
// Un campo para escribir algo que no está en la lista (otra actividad, otra persona, otro proyecto) y su botón
function plFormTexto(titulo, placeholder, etiqueta, boton, op, ir) {
  const sec = crear('div', 'pl-pop-sec');
  sec.append(crear('h4', null, titulo));
  const f = crear('form', 'pl-otra');
  const inp = crear('input');
  inp.type = 'text';
  inp.maxLength = 60;
  inp.placeholder = placeholder;
  inp.setAttribute('aria-label', etiqueta);
  inp.dataset.op = op;
  const ok = crear('button', 'cx-enlace', boton);
  ok.type = 'submit';
  f.append(inp, ok);
  f.addEventListener('submit', (e) => { e.preventDefault(); ir(inp.value); });
  sec.append(f);
  return sec;
}
const plFormOtra = (etiqueta, boton, ir) => plFormTexto('Otra actividad', 'Oficina, visita técnica, bodega…', etiqueta, boton, 'otra', ir);
// Un proyecto que no está en la lista, escrito: queda en la planificación de la semana a la vista (plAgregarProyecto)
const plFormProyecto = (etiqueta, boton, ir) => plFormTexto('Proyecto que no está en la lista', 'Nombre, o su N° de la Planilla', etiqueta, boton, 'proyecto-nuevo', ir);
/* Una persona, uno o varios días: sus proyectos (hasta 3 por día), otra actividad y una ausencia. Con varios días, una
   casilla a medias es un proyecto que tiene solo algunos de ellos: marcarla lo completa. */
function plPopPersona(s, m, ds, x, cuerpo) {
  const uno = ds.length === 1 ? ds[0] : null;
  const suyosDe = (d) => m.porPersona.get(d.iso + '|' + x.per) || [];
  const ausDe = (d) => m.ausencias.get(d.iso + '|' + x.per);
  const cuando = plDiasTexto(s, x.dias);
  if (x.cambiar && !ds.some((d) => suyosDe(d).includes(x.cambiar))) x.cambiar = null;
  const aus = uno && ausDe(uno);
  $('#plPopTit').textContent = plNom(x.per) + ' · ' + (uno ? plFechaLarga(uno) : pl(ds.length, 'día', 'días'));
  $('#plPopSub').textContent = uno ? (aus ? plAusencia(aus.motivo).nombre : suyosDe(uno).length + ' de ' + PL_MAX + ' proyectos este día') : 'Lo que marques vale ' + cuando;
  // Los proyectos activos, y lo que ya tiene esos días o se usó en la semana (otras actividades, proyectos que terminaron)
  const ops = m.activos.slice();
  m.ordenar([...new Set(ds.flatMap(suyosDe))].concat([...m.dias.keys()].filter((c) => c.startsWith('otra:')))).forEach((c) => {
    if (!ops.some((p) => p.clave === c) && m.proyectos.has(c)) ops.push(m.proyectos.get(c));
  });
  if (x.cambiar) { plPopCambiarProyecto(s, m, ds, x, cuerpo, ops); return; }
  const libres = ds.filter((d) => !ausDe(d) && suyosDe(d).length < PL_MAX);      // los días en que se le puede agregar algo
  if (aus) cuerpo.append(crear('p', 'pl-pop-nota tinte', plNom(x.per) + ' está ausente este día (' + plAusencia(aus.motivo).nombre.toLowerCase() + '). Quita la ausencia para asignarle proyectos.'));
  else if (uno && !libres.length) cuerpo.append(crear('p', 'pl-pop-nota tinte', plNom(x.per) + ' ya tiene ' + PL_MAX + ' proyectos ' + plElDia(uno) + ', el máximo. Quita uno o usa «Cambiar».'));
  else if (!uno && libres.length < ds.length) {
    const no = ds.filter((d) => !libres.includes(d)).map((d) => plElDia(d) + ' (' + (ausDe(d) ? plAusencia(ausDe(d).motivo).nombre.toLowerCase() : 'ya tiene ' + PL_MAX + ' proyectos') + ')');
    cuerpo.append(crear('p', 'pl-pop-nota tinte', (!libres.length ? 'No se le puede agregar nada: ' : no.length === 1 ? 'Al agregar se salta ' : 'Al agregar se saltan ') + unir(no) + '.'));
  }
  const ul = crear('ul', 'pl-ops');
  ul.setAttribute('aria-label', 'Proyectos de ' + plNom(x.per) + ' ' + cuando);
  const filtrar = ops.length > 7 ? plBuscador(x, cuerpo, ul, 'Buscar proyecto') : null;
  const sin = new Set(m.sinAsignar.map((p) => p.clave));
  ops.forEach((p) => {
    // Marcada si ya va todos los días en que se le puede agregar algo (una ausencia o 3 proyectos no la dejan a medias)
    const con = ds.filter((d) => suyosDe(d).includes(p.clave));
    const faltan = libres.filter((d) => !con.includes(d));
    const cb = plCasilla('c|' + p.clave, con.length > 0 && !faltan.length, !con.length && !libres.length, (v) => plAsignarDias(s, x.per, p.clave, x.dias, v));
    cb.indeterminate = con.length > 0 && faltan.length > 0;
    const dot = crear('span', 'pl-dot');
    dot.style.setProperty('--pc', m.color(p.clave));
    const otros = uno ? plOrdenPersonas((m.porProyecto.get(uno.iso + '|' + p.clave) || []).filter((q) => q !== x.per)) : [];
    const sub = plSub([p.otra ? 'Otra actividad' : p.lugar, otros.length ? 'con ' + plNoms(otros) : '', con.length && con.length < ds.length ? 'va ' + plCortos(con) : ''],
      sin.has(p.clave) ? 'Sin nadie ' + plEsta(s) : '');
    plOpcion(ul, norm([p.titulo, p.lugar, p.tag, p.req].join(' ')), cb, dot, p.titulo, sub,
      con.length && ops.length > 1 ? plBotonOp('k|' + p.clave, 'Cambiar', 'Pasar a ' + plNom(x.per) + ' de ' + p.titulo + ' a otro proyecto ' + plDiasTexto(s, con.map((d) => d.iso)),
        () => { x.cambiar = p.clave; x.q = ''; plPintarPop(true); }) : null,
      con.length && PL_VEHICULOS.length ? plVehOps(s, m, x.per, p.clave, con.map((d) => d.iso), 'v|' + p.clave) : null);
  });
  if (ops.length) cuerpo.append(ul);
  else cuerpo.append(crear('p', 'pl-pop-nota', 'No hay proyectos en ejecución en el Recorrido. Puedes anotar otra actividad.'));
  if (filtrar) filtrar();
  if (libres.length) {
    cuerpo.append(plFormProyecto('Proyecto que no está en la lista, para ' + plNom(x.per) + ' ' + cuando, 'Agregar', (txt) => {
      const c = plAgregarProyecto(txt);
      if (c) plAsignarDias(s, x.per, c, x.dias, true);
    }));
    cuerpo.append(plFormOtra('Otra actividad de ' + plNom(x.per) + ' ' + cuando, 'Agregar', (txt) => plOtra(s, x.dias, x.per, txt)));
  }
  const sec = crear('div', 'pl-pop-sec');
  sec.append(crear('h4', null, 'Ausencia'));
  const fila = crear('div', 'pl-aus-ops');
  const conAus = ds.filter(ausDe);
  const conProy = ds.some((d) => suyosDe(d).length);
  PL_AUSENCIAS.forEach((a) => {
    const b = crear('button', 'pl-aus-op', a.nombre);
    b.type = 'button';
    b.dataset.op = 'a|' + a.id;
    const es = conAus.length === ds.length && ds.every((d) => ausDe(d).motivo === a.id);
    b.setAttribute('aria-pressed', es ? 'true' : 'false');
    b.title = es ? 'Quitar la ausencia' : plNom(x.per) + ' no está disponible ' + cuando + (conProy ? ': se quita de sus proyectos ' + (uno ? 'de ese día' : 'de esos días') : '');
    b.addEventListener('click', () => plAusentarDias(s, x.dias, x.per, es ? '' : a.id));
    fila.append(b);
  });
  // Con varios días, si la ausencia es solo en algunos o con motivos distintos, un botón para quitarla
  if (conAus.length && !fila.querySelector('[aria-pressed="true"]')) {
    const b = crear('button', 'pl-aus-op', 'Quitar ausencia');
    b.type = 'button';
    b.dataset.op = 'a|';
    b.title = 'Quitar la ausencia ' + plDiasTexto(s, conAus.map((d) => d.iso));
    b.addEventListener('click', () => plAusentarDias(s, conAus.map((d) => d.iso), x.per, ''));
    fila.append(b);
  }
  sec.append(fila);
  cuerpo.append(sec);
}
// «Cambiar» desde la persona: deja un proyecto y pasa a otro, los días elegidos en que lo tenía, en un paso
function plPopCambiarProyecto(s, m, ds, x, cuerpo, ops) {
  const de = x.cambiar;
  const con = ds.filter((d) => (m.porPersona.get(d.iso + '|' + x.per) || []).includes(de)).map((d) => d.iso);
  cuerpo.append(plVolver('Volver', () => { x.cambiar = null; plPintarPop(true); }));
  cuerpo.append(crear('p', 'pl-pop-nota', 'Pasar a ' + plNom(x.per) + ' de ' + m.titulo(de) + ' a otro proyecto ' + plDiasTexto(s, con) + '. ¿A cuál?'));
  const lista = ops.filter((p) => p.clave !== de);
  const ul = crear('ul', 'pl-ops');
  ul.setAttribute('aria-label', 'Proyecto al que pasa ' + plNom(x.per));
  const filtrar = lista.length > 7 ? plBuscador(x, cuerpo, ul, 'Buscar proyecto') : null;
  lista.forEach((p) => {
    const ya = con.filter((iso) => (m.porPersona.get(iso + '|' + x.per) || []).includes(p.clave));
    const dot = crear('span', 'pl-dot');
    dot.style.setProperty('--pc', m.color(p.clave));
    const b = plBotonLista(ul, 'x|' + p.clave, norm([p.titulo, p.lugar, p.tag, p.req].join(' ')), dot, p.titulo,
      plSub([p.otra ? 'Otra actividad' : p.lugar, !ya.length ? '' : ya.length === con.length ? 'ya va ' + (con.length === 1 ? 'ese día' : 'esos días')
        : 'ya va ' + plCortos(ya.map((iso) => plDiaDe(s, iso)))]), () => {
        x.cambiar = null;
        if (!plCambiarPor(s, x.per, de, p.clave, con)) { x.cambiar = de; plPintarPop(false); return; }
        const c = $('#plPop [data-op="' + CSS.escape('c|' + p.clave) + '"]');
        if (c) c.focus({ preventScroll: true });
      });
    b.disabled = ya.length === con.length;
  });
  cuerpo.append(ul);
  if (filtrar) filtrar();
}
/* Un proyecto, uno o varios días: quiénes van (cada persona con lo demás que tiene), «Cambiar» a una por otra y, si
   nadie va en la semana, «Sin trabajo». Desde la alarma, el pie lleva al siguiente proyecto sin nadie. */
function plPopProyecto(s, m, ds, x, cuerpo) {
  const uno = ds.length === 1 ? ds[0] : null;
  const p = m.proyectos.get(x.clave) || { clave: x.clave, titulo: m.titulo(x.clave), lugar: '' };
  const vanDe = (d) => m.porProyecto.get(d.iso + '|' + x.clave) || [];
  const cuando = plDiasTexto(s, x.dias);
  if (x.cambiar && !ds.some((d) => vanDe(d).includes(x.cambiar))) x.cambiar = null;
  $('#plPopTit').textContent = p.titulo;
  $('#plPopSub').textContent = uno ? plFechaLarga(uno) + ' · ' + (vanDe(uno).length ? pl(vanDe(uno).length, 'persona', 'personas') : 'nadie asignado') : 'Lo que marques vale ' + cuando;
  /* El que sigue en la lista de la alarma, dando la vuelta: así se recorren todos aunque se deje alguno pendiente.
     Si este ya salió de la lista (se asignó), sigue el que quedó en su lugar (x.idx). */
  const l = m.sinAsignar;
  const i = l.findIndex((q) => q.clave === x.clave);
  if (i >= 0) x.idx = i;
  const desde = i >= 0 ? i + 1 : Math.min(x.idx || 0, l.length);
  const sig = l.slice(desde).concat(l.slice(0, desde)).find((q) => q.clave !== x.clave);
  if (x.alarma && sig) {
    const b = $('#plPopSiguiente');
    b.hidden = false;
    b.dataset.clave = sig.clave;
    b.textContent = 'Siguiente sin nadie: ' + sig.titulo + ' ›';
  }
  if (x.volver) cuerpo.append(plVolver('Otro proyecto', () => { planif.pop = { tipo: 'nuevo', iso: x.iso, dias: x.dias, ancla: x.ancla, q: '' }; plPintarPop(true); }));
  // Si nadie va en la semana, arriba la otra salida: «sin trabajo esta semana» (deja de contar como alarma)
  const pausa = m.pausas.has(x.clave);
  if ((p.activo || pausa) && !(m.dias.get(x.clave) || []).length) {
    const fila = crear('div', 'pl-pop-pausa');
    fila.append(crear('span', null, pausa ? 'No cuenta como alarma. Si asignas a alguien, vuelve a planificarse.' : 'Nadie va en toda la semana.'));
    const b = crear('button', 'pl-aus-op', 'Sin trabajo ' + plEsta(s));
    b.type = 'button';
    b.dataset.op = 'pausa';
    b.setAttribute('aria-pressed', pausa ? 'true' : 'false');
    b.title = pausa ? 'Que vuelva a contar como alarma si nadie va en la semana' : 'No se trabaja en este proyecto ' + plEsta(s) + ': deja de contar como alarma';
    b.addEventListener('click', () => plPausar(s, x.clave, !pausa));
    fila.append(b);
    cuerpo.append(fila);
  }
  if (x.cambiar) { plPopCambiarPersona(s, m, ds, x, cuerpo); return; }
  const ul = crear('ul', 'pl-ops');
  ul.setAttribute('aria-label', 'Quiénes van a ' + p.titulo + ' ' + cuando);
  m.personas.forEach((per) => {
    const suyosDe = (d) => m.porPersona.get(d.iso + '|' + per) || [];
    const con = ds.filter((d) => vanDe(d).includes(per));
    const ausentes = ds.filter((d) => m.ausencias.has(d.iso + '|' + per));
    const llenos = ds.filter((d) => !con.includes(d) && !m.ausencias.has(d.iso + '|' + per) && suyosDe(d).length >= PL_MAX);
    // Marcada si va todos los días en que puede ir (una ausencia o 3 proyectos no la dejan a medias)
    const faltan = ds.filter((d) => !con.includes(d) && !ausentes.includes(d) && !llenos.includes(d));
    const cb = plCasilla('c|' + per, con.length > 0 && !faltan.length, !con.length && !faltan.length, (v) => plAsignarDias(s, per, x.clave, x.dias, v));
    cb.indeterminate = con.length > 0 && faltan.length > 0;
    let sub;
    if (uno) {
      const aus = m.ausencias.get(uno.iso + '|' + per);
      const otros = m.ordenar(suyosDe(uno).filter((c) => c !== x.clave)).map(m.titulo);
      sub = aus ? plAusencia(aus.motivo).nombre : llenos.length ? 'Completo: ya tiene ' + PL_MAX + ' proyectos ese día'
        : otros.length ? 'También en ' + unir(otros) : 'Sin otro proyecto ese día';
    } else {
      const partes = [con.length && con.length < ds.length ? 'va ' + plCortos(con) : '', ausentes.length ? 'ausente ' + plCortos(ausentes) : '', llenos.length ? 'completo ' + plCortos(llenos) : ''].filter(Boolean);
      sub = partes.length ? partes.join(' · ') : con.length ? 'Va todos esos días' : 'Puede ir esos días';
      sub = sub.charAt(0).toUpperCase() + sub.slice(1);
    }
    plOpcion(ul, norm(per + ' ' + plNom(per)), cb, plPersona(per), per === estado.usuario ? per + ' · tú' : plNom(per), sub,
      con.length ? plBotonOp('k|' + per, 'Cambiar', 'Que vaya otra persona en vez de ' + plNom(per) + ' ' + plDiasTexto(s, con.map((d) => d.iso)),
        () => { x.cambiar = per; plPintarPop(true); }) : null,
      con.length && PL_VEHICULOS.length ? plVehOps(s, m, per, x.clave, con.map((d) => d.iso), 'v|' + per) : null);
  });
  cuerpo.append(ul);
  // Alguien que no está en la lista: se escribe su nombre, queda en la planificación y va a este proyecto esos días
  cuerpo.append(plFormTexto('Otra persona', 'Nombre y apellido', 'Otra persona que va a ' + p.titulo + ' ' + cuando, 'Agregar', 'persona-nueva', (txt) => {
    const per = plAgregarPersona(txt);
    if (per) plAsignarDias(s, per, x.clave, x.dias, true);
  }));
}
// «Cambiar» desde el proyecto: otra persona va en vez de esta, los días elegidos en que iba
function plPopCambiarPersona(s, m, ds, x, cuerpo) {
  const de = x.cambiar;
  const vanDe = (iso) => m.porProyecto.get(iso + '|' + x.clave) || [];
  const con = ds.filter((d) => vanDe(d.iso).includes(de)).map((d) => d.iso);
  cuerpo.append(plVolver('Volver', () => { x.cambiar = null; plPintarPop(true); }));
  cuerpo.append(crear('p', 'pl-pop-nota', '¿Quién va a ' + m.titulo(x.clave) + ' en vez de ' + plNom(de) + ' ' + plDiasTexto(s, con) + '?'));
  const ul = crear('ul', 'pl-ops');
  ul.setAttribute('aria-label', 'Quién va en vez de ' + de);
  m.personas.filter((per) => per !== de).forEach((per) => {
    const ya = con.filter((iso) => vanDe(iso).includes(per));
    const aus = con.filter((iso) => !ya.includes(iso) && m.ausencias.has(iso + '|' + per));
    const puede = con.filter((iso) => !ya.includes(iso) && !aus.includes(iso) && (m.porPersona.get(iso + '|' + per) || []).length < PL_MAX);
    const llenos = con.filter((iso) => !ya.includes(iso) && !aus.includes(iso) && !puede.includes(iso));
    // Cada motivo con sus días («ya va lun 19 · ausente mar 20»); si es uno solo para todos, «ese día» o «esos días»
    const cuando = (isos) => (isos.length < con.length ? ' ' + plCortos(isos.map((iso) => plDiaDe(s, iso))) : con.length === 1 ? ' ese día' : ' esos días');
    const partes = [puede.length && puede.length < con.length ? 'puede' + cuando(puede) : '', ya.length ? 'ya va' + cuando(ya) : '',
      aus.length ? 'ausente' + cuando(aus) : '', llenos.length ? 'completo' + cuando(llenos) : ''].filter(Boolean).join(' · ');
    const sub = partes.charAt(0).toUpperCase() + partes.slice(1);
    const b = plBotonLista(ul, 'x|' + per, norm(per + ' ' + plNom(per)), plPersona(per), per === estado.usuario ? per + ' · tú' : plNom(per), plSub([sub]), () => {
      x.cambiar = null;
      if (!plReemplazar(s, x.clave, de, per, con)) { x.cambiar = de; plPintarPop(false); return; }
      const c = $('#plPop [data-op="' + CSS.escape('c|' + per) + '"]');
      if (c) c.focus({ preventScroll: true });
    });
    b.disabled = !puede.length;
  });
  cuerpo.append(ul);
}
// «Asignar» en un día del tablero general: primero el proyecto (arriba, los que no tienen a nadie), después quiénes van
function plPopNuevo(s, m, ds, x, cuerpo) {
  const uno = ds.length === 1 ? ds[0] : null;
  const cuando = plDiasTexto(s, x.dias);
  $('#plPopTit').textContent = 'Asignar ' + cuando;
  $('#plPopSub').textContent = 'Elige el proyecto; después, quiénes van';
  const vanDe = (p) => plOrdenPersonas([...new Set(ds.flatMap((d) => m.porProyecto.get(d.iso + '|' + p.clave) || []))]);
  const sin = new Set(m.sinAsignar.map((p) => p.clave));
  const ir = (clave) => { planif.pop = { tipo: 'proyecto', clave, iso: x.iso, dias: x.dias, ancla: x.ancla, volver: true, q: '' }; plPintarPop(true); };
  const grupos = [['Sin nadie ' + (uno ? 'ese día' : 'esos días'), m.activos.filter((p) => !vanDe(p).length)],
    ['Ya tienen a alguien', m.activos.filter((p) => vanDe(p).length)]].filter(([, l]) => l.length);
  const cont = crear('div', 'pl-grupos');
  const filtrar = m.activos.length > 7 ? plBuscador(x, cuerpo, cont, 'Buscar proyecto') : null;
  grupos.forEach(([tit, lista]) => {
    const g = crear('div', 'pl-grupo');
    const ul = crear('ul', 'pl-ops');
    ul.setAttribute('aria-label', tit);
    lista.forEach((p) => {
      const dot = crear('span', 'pl-dot');
      dot.style.setProperty('--pc', m.color(p.clave));
      const van = vanDe(p);
      plBotonLista(ul, 'n|' + p.clave, norm([p.titulo, p.lugar, p.tag, p.req].join(' ')), dot, p.titulo,
        plSub([p.lugar, van.length ? 'van ' + plNoms(van) : ''], sin.has(p.clave) ? 'Sin nadie ' + plEsta(s) : ''), () => ir(p.clave));
    });
    g.append(crear('h4', null, tit), ul);
    cont.append(g);
  });
  if (grupos.length) cuerpo.append(cont);
  else cuerpo.append(crear('p', 'pl-pop-nota', 'No hay proyectos en ejecución en el Recorrido.'));
  if (filtrar) filtrar();
  cuerpo.append(plFormProyecto('Proyecto ' + cuando + ' que no está en la lista', 'Seguir', (txt) => {
    const c = plAgregarProyecto(txt);
    if (c) ir(c);
  }));
  cuerpo.append(plFormOtra('Otra actividad ' + cuando, 'Seguir', (txt) => {
    const c = plClaveOtra(s, txt);
    if (!c) { avisar('Escribe qué actividad es: oficina, visita técnica, bodega…'); return; }
    ir(c);
  }));
}

// ---- Compartir y exportar --------------------------------------------------------------------------------
// Lo de una persona un día, para el papel y el texto: su ausencia y sus proyectos, cada uno con el lugar, con quién va y
// en qué vehículo.
function plDiaDePersona(m, d, per) {
  const a = m.ausencias.get(d.iso + '|' + per);
  const proyectos = m.ordenar(m.porPersona.get(d.iso + '|' + per) || []).map((c) => {
    const p = m.proyectos.get(c) || {};
    return { clave: c, titulo: m.titulo(c), lugar: p.lugar || '', sitio: p.sitio || p.lugar || '', req: p.req || null, otra: !!p.otra,
      con: plOrdenPersonas((m.porProyecto.get(d.iso + '|' + c) || []).filter((x) => x !== per)), vehiculo: plVehiculo(m.vehiculo(d.iso, per, c)) };
  });
  return { ausencia: a ? plAusencia(a.motivo).nombre : '', proyectos };
}
// Quiénes van a un proyecto un día, con su vehículo: «ES, LC (RAM)» si van todos en el mismo; si no, cada uno el suyo
function plQuienesConVeh(m, iso, c) {
  const van = plOrdenPersonas(m.porProyecto.get(iso + '|' + c) || []);
  const vs = van.map((per) => plVehiculo(m.vehiculo(iso, per, c)));
  if (vs.length && vs[0] && vs.every((v) => v === vs[0])) return van.map(plNom).join(', ') + ' (' + vs[0].nombre + ')';
  return van.map((per, i) => plNom(per) + (vs[i] ? ' (' + vs[i].nombre + ')' : '')).join(', ');
}
/* La semana como texto para WhatsApp (*negrita*). Por persona: cada uno, día por día, sus proyectos con el lugar, con
   quién va y en qué vehículo («• Lun 19: Chimenea Talcahuano, con MP y EV, en la RAM»). Por día: cada día, sus
   proyectos con quiénes van (y su vehículo), y quiénes faltan. */
function plTexto(s, m, dias, modo) {
  const l = ['*Planificación semana ' + plNum(s) + ' · ' + plRango(s.lunes, dias.length) + '*'];
  if (modo === 'dia') {
    dias.forEach((d) => {
      l.push('', '*' + d.nombre + ' ' + d.fecha.getDate() + '*');
      const claves = m.ordenar([...new Set(m.personas.flatMap((per) => m.porPersona.get(d.iso + '|' + per) || []))]);
      claves.forEach((c) => l.push('• ' + m.titulo(c) + ': ' + plQuienesConVeh(m, d.iso, c)));
      const aus = m.personas.filter((per) => m.ausencias.has(d.iso + '|' + per));
      if (aus.length) l.push('• Ausentes: ' + aus.map((per) => plNom(per) + ' (' + plAusencia(m.ausencias.get(d.iso + '|' + per).motivo).nombre.toLowerCase() + ')').join(', '));
      if (!claves.length && !aus.length) l.push('Sin asignaciones');
    });
  } else {
    m.personas.forEach((per) => {
      l.push('', '*' + plNom(per) + '*');
      // Sin nada en toda la semana: una línea, no una de «sin proyecto» por día (2026-10-29)
      const xs = dias.map((d) => plDiaDePersona(m, d, per));
      if (xs.every((x) => !x.ausencia && !x.proyectos.length)) { l.push('• Sin proyectos ' + plEsta(s)); return; }
      dias.forEach((d, i) => {
        const x = xs[i];
        const que = x.proyectos.map((p) => p.titulo + (p.lugar ? ' (' + p.lugar + ')' : '') + (p.con.length ? ', con ' + plNoms(p.con) : '')
          + (p.vehiculo ? ', en ' + plLaVeh(p.vehiculo) : ''));
        if (x.ausencia) que.unshift(x.ausencia);
        l.push('• ' + d.corto + ' ' + d.fecha.getDate() + ': ' + (que.length ? que.join('; ') : 'sin proyecto'));
      });
    });
  }
  if (m.sinAsignar.length) l.push('', '⚠ Sin nadie asignado: ' + m.sinAsignar.map((p) => p.titulo).join(', '));
  return l.join('\n');
}
function plPintarTexto() {
  const s = plSemanaVista();
  $('#plTextoArea').value = plTexto(s, plModelo(s), plDias(s), planif.texto);
  document.querySelectorAll('#plTextoModo .pl-vista').forEach((b) => b.setAttribute('aria-pressed', b.dataset.modo === planif.texto ? 'true' : 'false'));
}
function plCompartir() {
  const s = plSemanaVista();
  if (!s.leida) return;
  plCerrarPop(false);
  plPintarTexto();
  $('#dlgPlTexto').showModal();
}
function plCopiarTexto() {
  const area = $('#plTextoArea');
  const mal = () => { area.focus(); area.select(); avisar('Selecciona el texto y cópialo con Ctrl C.'); };
  try {
    navigator.clipboard.writeText(area.value).then(() => { $('#dlgPlTexto').close(); avisar('Copiado: pégalo en WhatsApp o en un correo.'); }, mal);
  } catch (e) { mal(); }
}
// Exportar: qué va al papel. Las hojas son de quienes tienen algo esa semana; las demás se pueden sumar.
function plAbrirExportar() {
  const s = plSemanaVista();
  if (!s.leida) return;
  plCerrarPop(false);
  const m = plModelo(s), dias = plDias(s);
  $('#plExpSemana').textContent = 'Semana ' + plNum(s) + ' · ' + plRango(s.lunes, dias.length) + ' de ' + plMas(s.lunes, dias.length - 1).getFullYear()
    + '. Sale igual desde cualquier vista.';
  const cont = $('#plExpPers');
  cont.textContent = '';
  m.personas.forEach((per) => {
    const tiene = dias.some((d) => m.ausencias.has(d.iso + '|' + per) || (m.porPersona.get(d.iso + '|' + per) || []).length);
    const lab = crear('label', 'pl-exp-per' + (tiene ? '' : ' nada'));
    const cb = crear('input');
    cb.type = 'checkbox';
    cb.value = per;
    cb.checked = tiene;
    cb.addEventListener('change', plExpCuenta);
    lab.title = tiene ? 'La hoja de ' + plNom(per) : plNom(per) + ' no tiene nada asignado esta semana';
    lab.append(cb, crear('span', null, plNom(per)));
    cont.append(lab);
  });
  plExpCuenta();
  $('#dlgPlExportar').showModal();
}
const plExpPersonas = () => ($('#plExpHojas').checked ? [...document.querySelectorAll('#plExpPers input:checked')].map((x) => x.value) : []);
function plExpCuenta() {
  const tabla = $('#plExpTabla').checked, n = plExpPersonas().length;
  $('#plExpQuienes').disabled = !$('#plExpHojas').checked;
  $('#plExpImprimir').disabled = !tabla && !n;
  $('#plExpCuenta').textContent = !tabla && !n ? 'Elige qué imprimir.'
    : (!tabla && n > 1 ? 'Salen ' : 'Sale ') + unir([tabla ? 'la tabla de la semana' : '', n ? pl(n, 'hoja de persona', 'hojas de personas') : ''].filter(Boolean)) + '.';
}
// «el 23 de octubre de 2026 a las 10:25»: en el papel, «hoy» deja de servir al día siguiente
const plFechaHora = (f) => 'el ' + f.getDate() + ' de ' + PL_MESES[f.getMonth()] + ' de ' + f.getFullYear() + ' a las ' + f.getHours() + ':' + dos(f.getMinutes());
/* La semana en papel, pensada para quien la recibe y no la pantalla impresa: sin cortar nombres, sin marcas de quien
   imprime («tú», «Hoy») y legible en blanco y negro (el color de cada proyecto solo acompaña). La tabla de la semana
   (cada persona en una fila y, cada día, sus proyectos con el N° y el lugar) va en hojas horizontales; cada persona
   elegida, en su hoja vertical: día por día, sus proyectos, el lugar y con quién va. */
function plDocumento(s, m, dias, tabla, personas) {
  const doc = $('#plDoc');
  doc.textContent = '';
  const semana = 'Planificación semanal · Semana ' + plNum(s) + ' · ' + plRango(s.lunes, dias.length) + ' de ' + plMas(s.lunes, dias.length - 1).getFullYear();
  const impreso = 'Impreso ' + plFechaHora(new Date()) + (estado.usuario ? ' por ' + estado.usuario : '');
  const cabecera = (titulo, lineas) => {
    const h = crear('header', 'pl-doc-cab');
    const t = crear('div');
    t.append(crear('p', 'pl-doc-sem', semana), crear('h1', null, titulo));
    const d = crear('p', 'pl-doc-imp');
    lineas.forEach((x, i) => { if (i) d.append(crear('br')); d.append(document.createTextNode(x)); });
    h.append(t, d);
    return h;
  };
  const proyecto = (p) => {
    const e = crear('div', 'pl-doc-p' + (p.otra ? ' otra' : ''));
    e.style.setProperty('--pc', m.color(p.clave));
    e.append(crear('b', null, p.titulo));
    const sub = [p.otra ? 'Otra actividad' : p.req ? 'N° ' + p.req : '', p.lugar].filter(Boolean).join(' · ');
    if (sub) e.append(crear('span', null, sub));
    if (p.vehiculo) e.append(crear('span', 'pl-doc-veh', 'Vehículo: ' + p.vehiculo.nombre));
    return e;
  };
  // ¿Alguien va en vehículo esta semana? Entonces las hojas llevan su columna
  const conVeh = PL_VEHICULOS.some((v) => dias.some((d) => m.usoVeh(d.iso, v.id).length));
  if (tabla) {
    const sec = crear('section', 'pl-doc-tabla');
    sec.append(cabecera('Quién va a qué proyecto', [impreso]));
    const t = crear('table', 'pl-doc-t');
    const thead = crear('thead'), tr = crear('tr');
    const th0 = crear('th', 'pl-doc-per', 'Persona');
    th0.scope = 'col';
    tr.append(th0);
    dias.forEach((d) => { const th = crear('th', null, d.nombre + ' ' + d.fecha.getDate()); th.scope = 'col'; tr.append(th); });
    thead.append(tr);
    const tb = crear('tbody');
    m.personas.forEach((per) => {
      const fila = crear('tr');
      const th = crear('th', 'pl-doc-per', plNom(per));
      th.scope = 'row';
      fila.append(th);
      dias.forEach((d) => {
        const x = plDiaDePersona(m, d, per);
        const td = crear('td');
        if (x.ausencia) td.append(crear('p', 'pl-doc-aus', 'Ausente: ' + x.ausencia.toLowerCase()));
        x.proyectos.forEach((p) => td.append(proyecto(p)));
        if (!x.ausencia && !x.proyectos.length) td.append(crear('p', 'pl-doc-libre', 'Sin proyecto'));
        if (x.proyectos.length > PL_MAX) td.append(crear('p', 'pl-doc-exceso', x.proyectos.length + ' proyectos: el máximo es ' + PL_MAX));
        fila.append(td);
      });
      tb.append(fila);
    });
    t.append(thead, tb);
    sec.append(t);
    const notas = crear('ul', 'pl-doc-notas');
    const nota = (et, lista) => { if (!lista.length) return; const li = crear('li'); li.append(crear('b', null, et + ': '), document.createTextNode(lista.join(', ') + '.')); notas.append(li); };
    nota('Proyectos activos sin nadie esta semana', m.sinAsignar.map((p) => p.titulo));
    nota('Sin trabajo esta semana', m.activos.filter((p) => m.pausas.has(p.clave) && !m.dias.has(p.clave)).map((p) => p.titulo));
    // Dónde va cada vehículo: «Quempineta: lun 19, En obra (ES y LC); mié 21, Limache (MP).», y si un día va a dos
    // lugares, también lo dice
    PL_VEHICULOS.forEach((v) => {
      const usos = dias.filter((d) => m.usoVeh(d.iso, v.id).length).map((d) => {
        const g = m.usoVeh(d.iso, v.id);
        return d.corto.toLowerCase() + ' ' + d.fecha.getDate() + ', ' + unir(g.flat().map((x) => m.titulo(x.clave) + ' (' + plNoms(x.personas) + ')'))
          + (g.length > 1 ? ' — en ' + g.length + ' lugares a la vez' : '');
      });
      if (!usos.length) return;
      const li = crear('li');
      li.append(crear('b', null, v.nombre + ': '), document.createTextNode(usos.join('; ') + '.'));
      notas.append(li);
    });
    if (notas.childElementCount) sec.append(notas);
    doc.append(sec);
  }
  personas.forEach((per) => {
    const sec = crear('section', 'pl-doc-hoja');
    const semanaDe = dias.map((d) => plDiaDePersona(m, d, per));
    const conProyecto = semanaDe.filter((x) => x.proyectos.length).length;
    const ausente = semanaDe.filter((x) => x.ausencia && !x.proyectos.length).length;
    const proyectos = new Set(semanaDe.flatMap((x) => x.proyectos.map((p) => p.clave)));
    const disponibles = dias.length - ausente;
    sec.append(cabecera(plNom(per), [!disponibles ? 'Ausente toda la semana'
      : conProyecto + ' de ' + pl(disponibles, 'día', 'días') + ' con proyecto · ' + pl(proyectos.size, 'proyecto', 'proyectos'), impreso]));
    const t = crear('table', 'pl-doc-dias');
    const cols = crear('colgroup');
    (conVeh ? ['14%', '33%', '18%', '21%', '14%'] : ['17%', '39%', '20%', '24%']).forEach((w) => { const c = crear('col'); c.style.width = w; cols.append(c); });
    const thead = crear('thead'), tr = crear('tr');
    ['Día', 'Proyecto', 'Lugar', 'Con quién va'].concat(conVeh ? ['Vehículo'] : []).forEach((x) => { const th = crear('th', null, x); th.scope = 'col'; tr.append(th); });
    thead.append(tr);
    t.append(cols, thead);
    dias.forEach((d, i) => {
      const x = semanaDe[i];
      const tb = crear('tbody');      // un día por grupo: no se parte entre dos hojas
      const filas = [];
      if (x.ausencia) {
        const f = crear('tr', 'aus');
        const td = crear('td', null, 'Ausente: ' + x.ausencia.toLowerCase());
        td.colSpan = conVeh ? 4 : 3;
        f.append(td);
        filas.push(f);
      }
      x.proyectos.forEach((p) => {
        const f = crear('tr');
        const tp = crear('td');
        tp.append(proyecto(Object.assign({}, p, { lugar: '', vehiculo: null })));
        f.append(tp, crear('td', null, p.sitio || '—'), crear('td', null, p.con.length ? plNoms(p.con) : 'Nadie más'));
        if (conVeh) f.append(crear('td', p.vehiculo ? 'veh' : null, p.vehiculo ? p.vehiculo.nombre : '—'));
        filas.push(f);
      });
      if (!filas.length) {
        const f = crear('tr', 'libre');
        const td = crear('td', null, 'Sin proyecto asignado');
        td.colSpan = conVeh ? 4 : 3;
        f.append(td);
        filas.push(f);
      }
      const th = crear('th', null, d.nombre + ' ' + d.fecha.getDate());
      th.scope = 'rowgroup';
      th.rowSpan = filas.length;
      filas[0].prepend(th);
      tb.append(...filas);
      t.append(tb);
    });
    sec.append(t);
    doc.append(sec);
  });
}
/* Imprime lo elegido. El título de la página pasa a ser el de la semana mientras tanto: es el nombre que el navegador
   propone al guardar en PDF («Planificación semana 43 (19 al 23 de octubre)»). */
function plImprimir() {
  const s = plSemanaVista();
  const tabla = $('#plExpTabla').checked, personas = plExpPersonas();
  if (!s.leida || (!tabla && !personas.length)) return;
  $('#dlgPlExportar').close();
  const dias = plDias(s);
  plDocumento(s, plModelo(s), dias, tabla, personas);
  const titulo = document.title;
  document.title = 'Planificación semana ' + plNum(s) + ' (' + plRango(s.lunes, dias.length) + ')';
  document.body.classList.add('pl-imprimiendo');
  const fin = () => {
    document.body.classList.remove('pl-imprimiendo');
    document.title = titulo;
    $('#plDoc').textContent = '';
    window.removeEventListener('afterprint', fin);
  };
  window.addEventListener('afterprint', fin);
  window.print();
}

// ---- Agregar a mano: el diálogo (2026-10-26) --------------------------------------------------------------------
// modo: 'persona' o 'proyecto'. Abajo, lo agregado a mano que sigue en la planificación, cada uno con «Quitar».
// fija (2026-11-13): una persona del personal definitivo; si no, temporal (solo la semana a la vista)
function plAbrirAgregar(modo, fija = false) {
  if (!rc.dir) return;
  plCerrarPop(false);
  plPersonasMenu(false);
  planif.agregar = modo === 'proyecto' ? 'proyecto' : 'persona';
  planif.agregarFija = !!fija;
  $('#plAgregarNombre').value = '';
  $('#plAgregarLugar').value = '';
  plPintarAgregar();
  $('#dlgPlAgregar').showModal();
  $('#plAgregarNombre').focus();
}
function plPintarAgregar(error) {
  const proy = planif.agregar === 'proyecto';
  document.querySelectorAll('#plAgregarModo .pl-vista').forEach((b) => b.setAttribute('aria-pressed', b.dataset.modo === planif.agregar ? 'true' : 'false'));
  const fija = !proy && planif.agregarFija;
  $('#plAgregarDura').hidden = proy;
  document.querySelectorAll('#plAgregarDura .pl-vista').forEach((b) => b.setAttribute('aria-pressed', (b.dataset.fija === '1') === fija ? 'true' : 'false'));
  $('#dlgPlAgregarTit').textContent = proy ? 'Agregar a la planificación' : fija ? 'Agregar personal definitivo' : 'Agregar personal temporal';
  const pista = $('#plAgregarPista');
  pista.classList.toggle('error', !!error);
  const s = plSemanaVista();
  const esta = plEsta(s);
  pista.textContent = error || (proy
    ? 'Un proyecto que no está en ejecución en el Recorrido. Queda solo en ' + esta + ' como un proyecto activo más: no pasa a las siguientes. Si tiene N° en la Planilla de Ingreso, escríbelo adelante («281. H2 Green»): cuando entre en ejecución será el mismo.'
    : fija ? 'Queda en el personal desde ' + esta + ' en adelante, en todas las semanas.'
    : 'De apoyo o un contratista: queda solo en ' + esta + ' y no pasa a las siguientes.');
  $('#plAgregarEt').textContent = proy ? 'Nombre del proyecto' : 'Nombre y apellido';
  $('#plAgregarNombre').placeholder = proy ? 'Galpón Quilicura, o 281. H2 Green' : 'Juan Pérez';
  $('#plAgregarLugarCampo').hidden = !proy;
  $('#plAgregarOk').textContent = proy ? 'Agregar proyecto' : fija ? 'Agregar al personal' : 'Agregar persona';
  const cont = $('#plAgregados');
  cont.textContent = '';
  const fila = (e) => (proy ? { k: e.clave, nom: e.titulo, sub: [e.clave.startsWith('req:') ? 'N° ' + e.clave.slice(4) : '', e.lugar].filter(Boolean).join(' · ') }
    : { k: e.id, nom: e.nombre, sub: e.fija && e.activa ? 'Personal definitivo' : '' });
  const lista = proy ? plProyManoActivos(s).sort(plPorTitulo).map(fila) : plManoActivas(s).map((id) => fila(plManoDe(s, id)));
  /* Los de semanas anteriores que no están en esta, lo más reciente primero: vuelven con un toque (alguien de apoyo que
     sigue otra semana). Hasta 6. */
  const enEsta = new Set(lista.map((x) => x.k));
  const antes = new Map();
  [...plLista().ef[proy ? 'proyectos' : 'personas'].values()]
    .filter((e) => e.activa && e.semana < s.id && !enEsta.has(e.id || e.clave) && !(proy && plActivos(s).some((p) => p.clave === e.clave)))
    .sort((a, b) => b.semana.localeCompare(a.semana) || b.t.localeCompare(a.t))
    .forEach((e) => { if (!antes.has(e.id || e.clave)) antes.set(e.id || e.clave, e); });
  const previos = [...antes.values()].slice(0, 6);
  cont.hidden = !lista.length && !previos.length;
  const bloque = (titulo, filas, boton, accion) => {
    cont.append(crear('h3', null, titulo));
    const ul = crear('ul');
    filas.forEach((x) => {
      const li = crear('li');
      const tx = crear('span', 'pl-agr-txt');
      tx.append(crear('b', null, x.nom));
      if (x.sub) tx.append(crear('span', null, x.sub));
      const b = crear('button', 'cx-enlace', boton);
      b.type = 'button';
      b.dataset.k = x.k;
      b.dataset.accion = boton === 'Quitar' ? 'quitar' : 'sumar';
      b.title = x.titulo;
      b.addEventListener('click', () => {
        accion(x);
        plPintarAgregar();
        $('#plAgregarNombre').focus();
      });
      li.append(tx, b);
      ul.append(li);
    });
    cont.append(ul);
  };
  if (lista.length) {
    bloque((proy ? 'Proyectos agregados a mano en ' : 'Personas agregadas a mano en ') + esta,
      lista.map((x) => Object.assign(x, { titulo: 'Sacar a ' + x.nom + (x.sub ? ' del personal definitivo' : ' de ' + esta) + '. Lo ya asignado se sigue viendo' })), 'Quitar',
      (x) => { if (proy) plQuitarProyecto(x.k); else plQuitarPersona(x.k); });
  }
  if (previos.length) {
    bloque('De semanas anteriores',
      previos.map((e) => Object.assign(fila(e), { sub: [fila(e).sub, 'semana ' + +e.semana.slice(-2)].filter(Boolean).join(' · '), titulo: 'Sumar a ' + (e.titulo || e.nombre) + ' a ' + esta })),
      'Sumar a esta', (x) => {
        const e = antes.get(x.k);
        if (proy) plCambiarLista('proyectos', { clave: e.clave, titulo: e.titulo, lugar: e.lugar, semana: s.id, activa: true }, e.titulo + ' queda solo en ' + esta + ', como un proyecto activo más.');
        else plCambiarLista('personas', { id: e.id, nombre: e.nombre, semana: s.id, activa: true }, e.nombre + ' queda solo en ' + esta + ': toca su fila en «Por personal» para asignarle proyectos.');
      });
  }
}
// Con el diálogo abierto, el aviso de abajo no se ve: un problema se dice en el diálogo y no se cierra
function plConfirmarAgregar(e) {
  e.preventDefault();
  let problema = '';
  const aviso = (txt) => { problema = txt; };
  const nombre = $('#plAgregarNombre').value;
  const k = planif.agregar === 'proyecto' ? plAgregarProyecto(nombre, $('#plAgregarLugar').value, aviso) : plAgregarPersona(nombre, aviso, planif.agregarFija);
  if (problema) { plPintarAgregar(problema); $('#plAgregarNombre').focus(); return; }
  $('#dlgPlAgregar').close();
  if (planif.agregar === 'proyecto') { plEnfocar(k); return; }
  plElegirVista('personal');
  const tr = document.querySelector('#plPersonal tr[data-persona="' + CSS.escape(k) + '"]');
  if (tr) {
    tr.scrollIntoView({ block: 'center', behavior: REDUCIR.matches ? 'auto' : 'smooth' });
    tr.classList.add('resaltada');
    setTimeout(() => tr.classList.remove('resaltada'), 1800);
  }
}

/* ---- Estado de los proyectos y darlos por cerrados (2026-10-26) ---------------------------------------------------
   Pedido del usuario: ver en la planificación el estado de cada proyecto y dar por cerrado uno que ya terminó y se
   entregó, aunque no haya pasado por el Formulador. Cerrarlo vale para su N° y su TAG (plCierres); si tiene ficha
   en el Análisis Financiero sin el 100 %, se puede pedir ahí el 100 % de avance (un «datos-proyecto» al buzón, como
   «Ingresar avance»). Se deshace como lo demás: si ese mensaje todavía no se procesa, se borra del buzón. */
const plTarjeta = (clave) => (clave && rc.tarjetas.find((t) => t.clave === clave)) || null;
const plAvanceAF = (t) => (t && t.af ? Math.max(0, Math.min(1, Number(t.af.avance) || 0)) : null);
// Cómo va un proyecto en ejecución, en una etiqueta: su avance o lo que le falta. El detalle, al pasar encima.
function plEstadoDe(t) {
  if (!t || t.etapa !== 'ejecucion') return null;
  if (t.af) {
    // El avance pedido desde «Proyectos en ejecución» ya cuenta aquí, mientras espera al procesador
    const pct = t.avancePedido ? Math.round(t.avancePedido.valor * 100) + ' % de avance (por aplicar)' : Math.round(plAvanceAF(t) * 100) + ' % de avance';
    const vencido = t.chips.some((c) => c.texto === 'Término vencido');
    return { texto: vencido ? 'Término vencido · ' + pct : pct, nivel: vencido ? 'warn' : '', titulo: t.accion.texto };
  }
  return { texto: t.formulacion ? 'Falta pasarlo a ejecución' : 'Sin ficha en el Análisis Financiero', nivel: 'warn', titulo: t.accion.texto };
}
// De dónde sale: lo que dicen de él la Planilla de Ingreso, el Formulador y el Análisis Financiero
function plFuentes(t) {
  const r = t.planilla, f = t.formulacion, af = t.af;
  const fin = af && rcFecha(af.cierre);
  return [r ? 'Planilla «' + texto(r.estado) + '»' : t.req ? 'N° ' + t.req + ' sin fila en la Planilla' : 'Sin N° en la Planilla',
    f ? 'Formulador «' + f.estado + '»' : 'sin formulación',
    af ? 'Análisis Financiero ' + Math.round(plAvanceAF(t) * 100) + ' %' + (fin ? ', término ' + rcCorta(fin, new Date()) : '') : 'sin ficha en el Análisis Financiero'
  ].join(' · ');
}
// Después de cerrar o reabrir: el Recorrido se rearma con lo nuevo y se repinta todo lo que lo muestra
function plAlCambiarCierres() {
  if (rc.datos) {
    rc.datos.cierres = plCierres().ef;
    rc.tarjetas = rcArmar(rc.datos, new Date());
  }
  if (!$('#vistaRecorrido').hidden) rcPintar();
  pintarInicioRecorrido();
  plPintar();
  plPintarAlarmaGlobal();
  if ($('#dlgPlProyectos').open) plPintarProyectos();
  if (!$('#vistaEjecucion').hidden) ejPintar();
}
// Cierra (o reabre) la tarjeta en todas sus claves; devuelve lo que había, para deshacer
function plPonerCierres(t, cerrado, nota, af) {
  if (mvNoSe()) return [];
  const c = plCierres();
  const antes = rcClavesCierre(t).map((k) => {
    const previo = c.ef.get(k);
    const x = previo ? Object.assign({}, previo) : { clave: k, titulo: t.titulo, nota: '', cerrado: false, af: false };
    delete x.t; delete x.por; delete x.de;
    c.mias.set(k, { clave: k, titulo: plNombreLimpio(t.titulo), nota: cerrado ? plNota(nota) : '', cerrado, af: cerrado && !!af,
      t: plAhora(), por: estado.usuario || '', de: plDispositivo() });
    return x;
  });
  plRecalcularCierres();
  plProgramarGuardado(PL_CIERRES);
  return antes;
}
function plRecordar(u) {
  planif.deshacer.push(u);
  if (planif.deshacer.length > 40) planif.deshacer.shift();
}
// El aviso: abajo y, con «Estado de los proyectos» abierto (tapa el de abajo), también arriba en el diálogo
function plAvisarCierre(txt, conDeshacer) {
  planif.proyAviso = { texto: txt, deshacer: !!conDeshacer };
  if ($('#dlgPlProyectos').open) plPintarProyectos();
  avisar(txt, conDeshacer ? { texto: 'Deshacer', ir: plDeshacer } : undefined);
}
/* El 100 % de avance al Análisis Financiero, como lo manda «Ingresar avance»: solo si la celda tiene lo que se vio (o, si
   ya espera otro avance pedido desde «Proyectos en ejecución», el de ese pedido: el Análisis los aplica en orden). */
async function plPedirAvanceCompleto(t) {
  const visto = t.af.avance === null || t.af.avance === undefined || t.af.avance === '' || !isFinite(Number(t.af.avance)) ? null : Number(t.af.avance);
  return ejEnviarAF(t, { '% Avance': 1 }, { '% Avance': ejVisto(t.tag, '% Avance', visto) }, 'Dado por cerrado en la Planificación semanal del Portal');
}
async function plDarPorCerrado(t, nota, conAF) {
  if (!rc.dir || t.etapa !== 'ejecucion' || !rcClavesCierre(t).length) return false;
  const pedirAF = conAF && !!t.af && !!t.tag && plAvanceAF(t) < 1;
  let buzon = null;
  if (pedirAF) {
    try { buzon = await plPedirAvanceCompleto(t); } catch (e) {
      console.error(e);
      plAvisarCierre('No se pudo pedir el 100 % al Análisis Financiero (' + (e && e.name === 'NotAllowedError' ? 'falta el permiso para escribir en la carpeta del equipo' : 'revisa que OneDrive esté funcionando') + '): ' + t.titulo + ' sigue abierto.');
      return false;
    }
  }
  plRecordar({ cierres: plPonerCierres(t, true, nota, !!buzon), buzon, titulo: t.titulo });
  planif.cerrar = null;
  plAlCambiarCierres();
  plAvisarCierre(t.titulo + ' queda cerrado: pasa al «Cierre» del Recorrido y sale de la planificación.'
    + (buzon ? ' El 100 % de avance llega al Análisis Financiero en la próxima vuelta del procesador.' : ''), true);
  return true;
}
function plReabrir(t) {
  if (!rc.dir || !t.cierrePlan) return;
  plRecordar({ cierres: plPonerCierres(t, false), buzon: null, titulo: t.titulo });
  plAlCambiarCierres();
  const u = plTarjeta(t.clave);
  plAvisarCierre(u && u.etapa === 'ejecucion' ? t.titulo + ' vuelve a ejecución: aparece otra vez en la planificación.'
    : t.titulo + ' ya no está cerrado en la planificación, pero sigue en el «Cierre»: ' + (u && plAvanceAF(u) === 1
      ? 'el Análisis Financiero tiene 100 % de avance (bájalo en «Ingresar avance» si sigue en obra).' : 'otra herramienta lo da por terminado.'), true);
}
async function plDeshacerCierre(u) {
  if (mvNoSe()) return;
  const c = plCierres();
  u.cierres.forEach((e) => c.mias.set(e.clave, Object.assign({}, e, { t: plAhora(), por: estado.usuario || '', de: plDispositivo() })));
  plRecalcularCierres();
  plProgramarGuardado(PL_CIERRES);
  plAlCambiarCierres();
  let extra = '';
  if (u.buzon) {
    try {
      await (await rc.dir.getDirectoryHandle('buzon')).removeEntry(u.buzon);
      extra = ' El pedido del 100 % al Análisis Financiero se retiró.';
      // Ya no espera: el Recorrido y «Proyectos en ejecución» dejan de mostrarlo como pedido
      if (rc.datos) { rc.datos.datosProyecto = (rc.datos.datosProyecto || []).filter((m) => u.buzon.indexOf(m.id) < 0); plAlCambiarCierres(); }
    } catch (e) { extra = ' El 100 % de avance ya llegó al Análisis Financiero: cámbialo en «Ingresar avance».'; }
  }
  plAvisarCierre('Se deshizo el último cambio de ' + u.titulo + '.' + extra, false);
}

function plAbrirProyectos(clave) {
  plCerrarPop(false);
  planif.cerrar = clave || null;
  planif.proyAviso = null;
  plPintarProyectos();
  const d = $('#dlgPlProyectos');
  if (!d.open) d.showModal();
  const li = clave && d.querySelector('li[data-tarjeta="' + CSS.escape(clave) + '"]');
  if (li) {
    li.scrollIntoView({ block: 'nearest' });
    const nota = li.querySelector('#plCerrarNota');
    if (nota) nota.focus();
  }
}
function plPintarProyectos() {
  const s = plSemanaVista();
  const activos = rc.leido ? plActivos(s) : [];
  const m = s.leida ? plModelo(s) : null;
  const delRc = activos.filter((p) => !p.mano);
  const aMano = activos.filter((p) => p.mano);
  const cerrados = rc.tarjetas.filter((t) => t.cierrePlan).sort((a, b) => b.cierrePlan.t.localeCompare(a.cierrePlan.t)).slice(0, PL_CERRADOS_MAX);
  if (planif.cerrar && !delRc.some((p) => p.tarjeta === planif.cerrar)) planif.cerrar = null;
  $('#plProyPista').textContent = rc.leido
    ? 'Uno que ya terminó y se entregó, dalo por cerrado: sale de la planificación para todo el equipo y pasa al «Cierre» del Recorrido. Los demás salen solos al llegar al 100 % de avance o quedar «Cerrada» en el Formulador.'
    : 'Leyendo la carpeta del equipo…';
  const av = $('#plProyAviso');
  av.textContent = '';
  av.hidden = !planif.proyAviso;
  if (planif.proyAviso) {
    av.append(crear('span', null, planif.proyAviso.texto));
    if (planif.proyAviso.deshacer) {
      const b = crear('button', 'cx-enlace', 'Deshacer');
      b.type = 'button';
      b.addEventListener('click', () => {
        planif.proyAviso = null;
        plDeshacer();
        if ($('#dlgPlProyectos').open) plPintarProyectos();
      });
      av.append(b);
    }
  }
  const cont = $('#plProyLista');
  cont.textContent = '';
  const lista = (titulo) => { cont.append(crear('h3', null, titulo)); const ul = crear('ul'); cont.append(ul); return ul; };
  const boton = (txt, accion, titulo, ir) => {
    const b = crear('button', 'cx-enlace', txt);
    b.type = 'button';
    b.dataset.accion = accion;
    b.title = titulo;
    b.addEventListener('click', ir);
    return b;
  };
  const fila = (li, titulo, sub, extra, chips, botones) => {
    const f = crear('div', 'pl-proys-fila');
    const tx = crear('div', 'pl-proys-txt');
    tx.append(crear('b', null, titulo));
    if (sub) tx.append(crear('span', null, sub));
    if (extra) tx.append(crear('span', 'pl-proys-fuentes', extra));
    if (chips.length) {
      const w = crear('div', 'pl-proys-chips');
      chips.forEach((c) => { const x = plChipEstado(c.texto, c.nivel); if (c.titulo) x.title = c.titulo; w.append(x); });
      tx.append(w);
    }
    const acc = crear('div', 'pl-proys-acc');
    botones.forEach((b) => acc.append(b));
    f.append(tx, acc);
    li.append(f);
  };
  const ul = lista(delRc.length ? 'En ejecución · ' + delRc.length : 'En ejecución');
  if (!delRc.length) ul.append(crear('li', 'pl-proys-vacio', rc.leido ? 'No hay proyectos en ejecución en el Recorrido.' : 'Leyendo…'));
  delRc.forEach((p) => {
    const t = plTarjeta(p.tarjeta);
    if (!t) return;
    const li = crear('li');
    li.dataset.tarjeta = t.clave;
    li.dataset.clave = p.clave;
    const chips = [plEstadoDe(t)].filter(Boolean);
    if (m) {
      const n = (m.dias.get(p.clave) || []).length;
      chips.push(n ? { texto: (s.id === plHoyId() ? 'Esta semana: ' : 'Semana ' + plNum(s) + ': ') + pl(n, 'día', 'días'), nivel: 'ok' }
        : { texto: 'Nadie ' + plEsta(s), nivel: '' });
    }
    const abierto = planif.cerrar === t.clave;
    const cerrarB = boton('Dar por cerrado', 'cerrar', 'Ya terminó y se entregó: pasa al «Cierre» del Recorrido y sale de la planificación', () => {
      planif.cerrar = abierto ? null : t.clave;
      plPintarProyectos();
      const nota = $('#plCerrarNota');
      if (nota) nota.focus();
    });
    cerrarB.disabled = !rc.dir;
    cerrarB.setAttribute('aria-expanded', abierto ? 'true' : 'false');
    fila(li, p.titulo, [p.req ? 'N° ' + p.req : '', p.tag && p.tag !== p.titulo ? p.tag : '', p.lugar].filter(Boolean).join(' · '), plFuentes(t), chips,
      [boton('Ver recorrido', 'ver', 'Sus etapas, sus datos y sus enlaces', () => rcVerDetalle(t.clave)), cerrarB]);
    if (abierto) li.append(plFormCerrar(t));
    ul.append(li);
  });
  if (aMano.length) {
    const um = lista('Agregados a mano en ' + plEsta(s));
    aMano.forEach((p) => {
      const li = crear('li');
      li.dataset.clave = p.clave;
      const b = boton('Quitar de ' + plEsta(s), 'quitar', 'Son temporales: dejan de estar en ' + plEsta(s) + ' y lo ya asignado se sigue viendo', () => {
        plQuitarProyecto(p.clave);
        plAvisarCierre(p.titulo + ' ya no está en ' + plEsta(s) + '. Lo asignado se sigue viendo.', true);
      });
      b.disabled = !rc.dir;
      fila(li, p.titulo, [p.req ? 'N° ' + p.req : '', p.lugar].filter(Boolean).join(' · '), 'Agregado a mano: vale solo para ' + plEsta(s), [], [b]);
      um.append(li);
    });
  }
  if (cerrados.length) {
    const uc = lista('Cerrados en la planificación');
    cerrados.forEach((t) => {
      const e = t.cierrePlan;
      const li = crear('li');
      li.dataset.tarjeta = t.clave;
      const b = boton('Reabrir', 'reabrir', 'Sigue en obra: vuelve a ejecución y a la planificación', () => plReabrir(t));
      b.disabled = !rc.dir;
      fila(li, t.titulo, [t.req ? 'N° ' + t.req : '', t.tag && t.tag !== t.titulo ? t.tag : ''].filter(Boolean).join(' · '),
        'Cerrado' + (e.por ? ' por ' + e.por : '') + ' ' + plCuando(e.t) + (e.nota ? ': «' + e.nota + '»' : ''), [], [b]);
      uc.append(li);
    });
  }
}
// El formulario de una tarjeta que se va a cerrar: una nota y, si corresponde, el 100 % en el Análisis Financiero
function plFormCerrar(t) {
  const w = crear('div', 'pl-cerrar');
  w.append(crear('p', 'pl-cerrar-txt', 'Pasa al «Cierre» del Recorrido y deja de aparecer en la planificación, también en las semanas que vienen. Lo ya asignado se sigue viendo con su nombre, y se puede reabrir.'));
  const campo = crear('label', 'pl-campo');
  const et = crear('span', null, 'Nota ');
  et.append(crear('i', null, '(opcional)'));
  const nota = crear('input');
  nota.id = 'plCerrarNota';
  nota.type = 'text';
  nota.maxLength = 200;
  nota.autocomplete = 'off';
  nota.placeholder = 'Entregado el 20-10, con acta de recepción';
  campo.append(et, nota);
  w.append(campo);
  const avance = plAvanceAF(t);
  if (t.af && t.tag && avance < 1) {
    const l = crear('label', 'pl-cerrar-af');
    const cb = crear('input');
    cb.type = 'checkbox';
    cb.id = 'plCerrarAF';
    cb.checked = true;
    l.append(cb, crear('span', null, 'Dejar también su avance en 100 % en el Análisis Financiero (hoy tiene ' + Math.round(avance * 100) + ' %). Llega en la próxima vuelta del procesador.'));
    w.append(l);
  }
  const acc = crear('div', 'pl-cerrar-acc');
  const no = crear('button', 'cx-enlace', 'Cancelar');
  no.type = 'button';
  no.addEventListener('click', () => { planif.cerrar = null; plPintarProyectos(); });
  const si = crear('button', 'btn-pri', 'Dar por cerrado');
  si.type = 'submit';
  si.id = 'plCerrarOk';
  acc.append(no, si);
  w.append(acc);
  return w;
}
async function plConfirmarCierre(e) {
  if (e) e.preventDefault();
  const t = plTarjeta(planif.cerrar);
  if (!t || planif.cerrando) return;
  const cb = $('#plCerrarAF');
  planif.cerrando = true;
  const ok = $('#plCerrarOk');
  if (ok) ok.disabled = true;
  try { await plDarPorCerrado(t, $('#plCerrarNota') ? $('#plCerrarNota').value : '', !!(cb && cb.checked)); }
  finally { planif.cerrando = false; if (ok && ok.isConnected) ok.disabled = false; }
}
