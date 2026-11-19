/* Portal QUEMPIN — Inicio: las herramientas por área y la semana (ini*).
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Inicio: las herramientas por área (2026-11-10) -------------------------------------------------
/* Pedido del usuario: el saludo y las herramientas de cada área del trabajo como botones con su ícono, sin cifras ni
   gráficos. De la carpeta del equipo depende la semana de la Planificación (iniPintarSemana); por eso el Inicio sigue
   pidiendo la lectura del Recorrido. La alarma de los sin asignar ya no va en su botón (pedido del 2026-11-18). */
const ini = { cuadro: 0 };
const iniVisible = () => !$('#vistaInicio').hidden;
// El nombre de cada botón: el corto, salvo donde cabe uno más claro. Los de una palabra larga llevan guiones suaves
// entre sílabas: con poco ancho (1024 px) se cortan ahí y no en cualquier letra. Los de dos palabras se cortan en el
// espacio (con guiones suaves, el navegador cortaría «Análisis Finan-ciero»).
const INI_NOMBRE = { analisis: 'Análisis Financiero', 'subir-cc': 'Subir docs.' };
const INI_SILABAS = new Map(['Opor-tu-ni-da-des', 'Re-que-ri-mien-tos', 'For-mu-la-dor', 'Se-gui-mien-to', 'Co-ti-za-dor',
  'Pla-ni-fi-ca-ción', 'Diá-me-tro', 'Hi-dró-ge-no'].map((w) => [w.replace(/-/g, ''), w.replace(/-/g, '­')]));
const iniNombre = (h) => { const n = INI_NOMBRE[h.id] || h.corto || h.nombre; return INI_SILABAS.get(n) || n; };

// Una herramienta como botón: su ícono, su nombre y ↗ si se abre fuera del portal
function iniBoton(h) {
  const b = crear('button', 'ini-item');
  b.type = 'button';
  b.dataset.herr = h.id;
  const ico = crear('span', 'ini-ico');
  ico.append(icono(iconoDe(h), 24));
  b.append(ico, crear('span', 'ini-nom', iniNombre(h)));
  b.title = h.nombre + (h.desc ? ': ' + h.desc : h.breve ? ': ' + h.breve : '');
  if (h.tipo !== 'marco' && h.tipo !== 'vista') {
    // Se abre fuera del portal: Excel o Sistema QUEMPIN
    const f = crear('span', 'ini-fuera');
    f.append(icono('fuera', 12));
    b.append(f, crear('span', 'sr', h.tipo === 'programa' ? ' (abre Sistema QUEMPIN)' : ' (abre Excel)'));
  }
  b.addEventListener('click', () => abrir(h.id));
  return b;
}
/* El teléfono (2026-11-18): en un navegador que no abre la carpeta del equipo (el teléfono, Safari, Firefox) no se
   muestran, ni en el Inicio ni en el menú ni en el buscador, las que solo sirven con ella para escribir y las que abren
   Sistema QUEMPIN (pedido del usuario: lo que no se puede hacer aquí, ni siquiera como opción). Las calculadoras, los
   tableros y lo que se lee del resumen (js/resumen.js) siguen. Devuelve por qué no va, o ''. */
const INI_SOLO_CARPETA = new Set(['subir-cc', 'rendiciones']);
function iniApagada(h) {
  if (typeof window.showDirectoryPicker === 'function') return '';
  if (h.tipo === 'programa') return h.nombre + ': abre Sistema QUEMPIN, que está en los computadores de la oficina.';
  if (INI_SOLO_CARPETA.has(h.id)) return h.nombre + ': necesita un computador con Chrome o Edge y la carpeta del equipo conectada.';
  return '';
}
function pintarInicio() {
  if (!ini.semAbrir) {
    ini.semAbrir = true;
    $('#iniSemAbrir').addEventListener('click', () => abrir('planificacion'));
  }
  document.querySelectorAll('#iniAreas .ini-area').forEach((sec) => {
    const ul = sec.querySelector('.ini-tiles');
    if (ul.childElementCount) return;      // no depende de datos: se arma una vez
    REG.herramientas.filter((h) => h.grupo === sec.dataset.grupo && !iniApagada(h)).forEach((h) => {
      const li = crear('li');
      li.append(iniBoton(h));
      ul.append(li);
    });
  });
  // Las que ya tienen su pestaña abierta llevan un punto: volver a elegirlas va a esa pestaña.
  const abiertas = new Set(estado.pestanas.map((p) => p.herr));
  document.querySelectorAll('#iniAreas .ini-item').forEach((b) => {
    const si = abiertas.has(b.dataset.herr);
    b.classList.toggle('abierta', si);
    let s = b.querySelector('.sr.abierta-sr');
    if (si && !s) { s = crear('span', 'sr abierta-sr', ' (ya abierta)'); b.append(s); }
    if (!si && s) s.remove();
  });
  estado.proyectos = leerProyectos();      // el Formulador pudo cambiarlos mientras tanto (los usa el buscador)
  plPintarAlarmaGlobal();    // la alarma va en el menú
  iniPintarDatos();
  if (!rc.leyendo && (!rc.intentado || (rc.leido && Date.now() - rc.leido > 5 * RC_RELEER_SEG * 1000))) {
    rc.intentado = true;
    rcCargar();
  }
}
// Lo que cambia con los datos o el usuario, una vez por cuadro aunque lo pidan varias lecturas seguidas. Con el Inicio
// escondido no se pinta: se pinta al volver a él.
function pintarInicioRecorrido() {
  if (ini.cuadro) return;
  ini.cuadro = requestAnimationFrame(() => { ini.cuadro = 0; iniPintarDatos(); });
}
function iniPintarDatos() {
  if (!iniVisible()) return;
  iniPintarSaludo();
  iniPintarSemana();
}
/* La semana de hoy de la Planificación (2026-11-18, maqueta V4): un día por columna con sus proyectos, los de más gente
   primero y hasta tres, y cuántas personas tienen algo. Tocar un día abre la Planificación con ese día en grande.
   Sin carpeta o sin leerla todavía, la franja no se muestra. */
const INI_SEM_MAX = 3;
function iniPintarSemana() {
  const sec = $('#iniSemana');
  const s = rc.leido && rc.dir ? planif.semanas.get(plHoyId()) : null;
  sec.hidden = !(s && s.leida);
  if (sec.hidden) return;
  const m = plModelo(s);
  const ul = $('#iniSemDias');
  ul.textContent = '';
  plDias(s).forEach((d) => {
    const claves = [...new Set(m.personas.flatMap((per) => m.porPersona.get(d.iso + '|' + per) || []))];
    const cuantos = (c) => (m.porProyecto.get(d.iso + '|' + c) || []).length;
    const orden = m.ordenar(claves).sort((a, b) => cuantos(b) - cuantos(a));
    const van = m.personas.filter((per) => (m.porPersona.get(d.iso + '|' + per) || []).length).length;
    const b = crear('button', 'ini-sem-dia' + (d.hoy ? ' hoy' : ''));
    b.type = 'button';
    b.dataset.dia = String(d.i);
    const et = crear('span', 'ini-sem-et');
    et.append(crear('span', null, d.corto + ' ' + d.fecha.getDate()));
    if (van) et.append(crear('span', 'ini-sem-n', van + ' pers.'));
    b.append(et);
    orden.slice(0, INI_SEM_MAX).forEach((c, k) => {
      const f = crear('span', 'ini-sem-pr p' + (k + 1));
      const i = crear('i');
      i.style.setProperty('--pc', m.color(c));
      f.append(i, crear('span', null, m.titulo(c)), crear('b', null, String(cuantos(c))));
      b.append(f);
    });
    // «+N más»: uno contando tres proyectos y otro contando dos, para las pantallas bajas (el CSS muestra uno)
    [3, 2].forEach((n) => { if (orden.length > n) b.append(crear('span', 'ini-sem-mas m' + n, '+' + (orden.length - n) + ' más')); });
    if (!orden.length) b.append(crear('span', 'ini-sem-nadie', 'Nadie asignado'));
    b.title = plFechaLarga(d) + (d.hoy ? ' (hoy)' : '') + ': '
      + (van ? pl(van, 'persona', 'personas') + ' en ' + pl(orden.length, 'proyecto', 'proyectos') + ' ('
        + orden.map((c) => m.titulo(c) + ', ' + cuantos(c)).join('; ') + ')' : 'nadie asignado') + '. Verlo en la Planificación';
    b.setAttribute('aria-label', b.title);
    b.addEventListener('click', () => iniAbrirDia(d.i));
    const li = crear('li');
    li.append(b);
    ul.append(li);
  });
}
// La Planificación en la semana de hoy, en General con ese día en grande (las otras vistas no muestran un día solo)
function iniAbrirDia(i) {
  planif.lunes = plLunesDe(new Date());
  planif.diaMovil = i;
  abrir('planificacion');
  if (planif.vista !== 'general') plElegirVista('general');
}
// El saludo; sin usuario, se elige aquí mismo con un clic (también está arriba, en la cabecera)
function iniPintarSaludo() {
  const hoy = new Date();
  const h = hoy.getHours();
  const t = $('#tituloInicio');
  t.textContent = h < 12 ? 'Buenos días' : h < 20 ? 'Buenas tardes' : 'Buenas noches';
  if (estado.usuario) t.append(', ', crear('b', null, estado.usuario));
  t.title = hoy.toLocaleDateString('es-CL', { weekday: 'long', day: 'numeric', month: 'long' }) + ' · semana ' + (+plHoyId().slice(-2));
  const q = $('#iniQuien');
  q.hidden = !!estado.usuario;
  if (!estado.usuario && !q.querySelector('button')) {
    USUARIOS.forEach((u) => {
      const b = crear('button', null, u);
      b.type = 'button';
      b.dataset.usuario = u;
      b.title = 'Trabajar como ' + u;
      b.addEventListener('click', () => elegirUsuario(u));
      q.append(b);
    });
  }
}

// «Solo mis proyectos» se recuerda aunque no haya usuario: vuelve a valer al elegir uno.
function rcAlCambiarUsuario() {
  if (!$('#vistaRecorrido').hidden) rcPintar();
  iniPintarDatos();      // al momento: es lo que la persona acaba de cambiar
  if (!$('#vistaPlan').hidden) plPintar();     // la Planificación semanal también marca lo suyo
  if (!$('#vistaEjecucion').hidden) ejPintar();
  if (!$('#vistaObservaciones').hidden) obsPintar();
}
