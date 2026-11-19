/* Portal QUEMPIN — Arranque: engancha los botones y abre la herramienta pedida. Va última.
   Script clásico, sin función que lo envuelva: lo de primer nivel es común a todos los js/ y se cargan
   en el orden de index.html. tests/portal/test_portal_archivos.py revisa que ningún nombre se repita
   ni tape uno del navegador (window.open, name, status...). */
'use strict';

// ---- Arranque ------------------------------------------------------------------------------------
infoPreparar(document);
try {
  const t = localStorage.getItem(LS.tema);
  if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t);
} catch (e) { /* nada */ }
pintarTema();
$('#btnTema').addEventListener('click', () => {
  const t = oscuroAhora() ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', t);
  try {
    localStorage.setItem(LS.tema, t);
    CLAVES_TEMA.forEach((k) => localStorage.setItem(k, t));
  } catch (e) { /* nada */ }
  pintarTema();
  estilarTodos();
});
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { pintarTema(); estilarTodos(); });
// Cada página nueva de una herramienta se arregla apenas existe, antes de que alcance a verse su
// cabecera; la fecha de los datos del tablero activo se lee cuando ya se abrió con la contraseña.
setInterval(estilarTodos, 100);
setInterval(pintarDato, 1000);

$('#pais').value = estado.pais;
$('#pais').addEventListener('change', () => {
  estado.pais = $('#pais').value === 'pe' ? 'pe' : 'cl';
  guardar(LS.pais, estado.pais);
  // Los tableros abiertos que existen en los dos países se cambian al elegido.
  estado.pestanas.forEach((p) => {
    const h = HERR.get(p.herr);
    if (h && h.peru) navegar(p, urlDe(h));
  });
  avisar(estado.pais === 'pe' ? 'Los tableros se abren con los datos de Perú.' : 'Los tableros se abren con los datos de Chile.');
});

construirMenu();
estado.proyectos = leerProyectos();
try { localStorage.removeItem(LS.proyecto); } catch (e) { /* nada */ }   // el del selector que ya no existe
estado.usuario = leerUsuario();
pintarUsuario();
mvPreparar();      // la franja del resumen de solo lectura (js/resumen.js)
$('#btnUsuario').addEventListener('click', () => { if ($('#popUsuario').hidden) abrirUsuario(); else cerrarUsuario(true); });
$('#sinUsuario').addEventListener('click', () => elegirUsuario(''));
$('#cerrarSesion').addEventListener('click', cerrarSesion);

$('#btnMenu').addEventListener('click', () => { cerrarFlotantes(); mostrarMenu(!menuAbierto()); });
$('#velo').addEventListener('click', () => mostrarMenu(false));
MOVIL.addEventListener('change', () => { mostrarMenu(false); mostrarBuscadorMovil(false); });
$('#btnInicio').addEventListener('click', () => abrir('inicio'));
// Recorrido de proyectos
$('#rcActualizar').append(icono('recargar', 16));
$('#rcActualizar').addEventListener('click', () => {
  if (rc.sinDatos === 'permiso') { rcPedirPermiso(); return; }
  rcCargar();
  rcPintarFrescura();
});
$('#rcPedirVuelta').addEventListener('click', rcPedirVuelta);
$('#rcMios').addEventListener('change', (e) => {
  rc.mios = e.target.checked;
  guardar(LS_RC, { mios: rc.mios });
  rcPintar();
});
$('#rcElegir').addEventListener('click', abrirUsuario);
$('#rcBuscar').addEventListener('input', (e) => { rc.q = e.target.value; rcPintar(); });
$('#rcFoco').addEventListener('click', () => { rc.foco = null; rcPintar(); $('#rcBuscar').focus(); });
// Subir documentos
$('#scActualizar').append(icono('recargar', 16));
$('#scActualizar').addEventListener('click', () => {
  if (rc.sinDatos === 'permiso') { rcPedirPermiso(); return; }
  rcCargar();
  scPintar();
});
$('#scZonaIco').append(icono('subir', 26));
document.querySelectorAll('.sc-pais button').forEach((b) => b.addEventListener('click', () => { sc.pais = b.dataset.pais; scPintar(); }));
$('#scBuscar').addEventListener('input', (e) => { sc.q = e.target.value; scPintarProyecto(); });
$('#scBuscar').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  e.preventDefault();
  const primera = $('#scLista .sc-op');
  if (primera) primera.click();
});
$('#scCambiar').addEventListener('click', () => { sc.eleccion = null; scPintar(); $('#scBuscar').focus(); });
$('#scArchivo').addEventListener('change', (e) => { scAgregar(e.target.files); e.target.value = ''; });
const zona = $('#scZona');
['dragenter', 'dragover'].forEach((t) => zona.addEventListener(t, (e) => { e.preventDefault(); zona.classList.add('encima'); }));
['dragleave', 'dragend'].forEach((t) => zona.addEventListener(t, () => zona.classList.remove('encima')));
zona.addEventListener('drop', (e) => { e.preventDefault(); zona.classList.remove('encima'); scAgregar(e.dataTransfer && e.dataTransfer.files); });
$('#scForm').addEventListener('submit', scEnviar);
// Rendiciones
$('#rdZonaIco').append(icono('subir', 26));
RD_DETALLES.forEach((t) => { const o = crear('option'); o.value = t; $('#rdDetalles').append(o); });
Object.values(RD_NOMBRES).forEach((t) => { const o = crear('option'); o.value = t; $('#rdPersonas').append(o); });
$('#rdArchivo').addEventListener('change', (e) => { rdAgregar(e.target.files); e.target.value = ''; });
const rdZona = $('#rdZona');
['dragenter', 'dragover'].forEach((t) => rdZona.addEventListener(t, (e) => { e.preventDefault(); rdZona.classList.add('encima'); }));
['dragleave', 'dragend'].forEach((t) => rdZona.addEventListener(t, () => rdZona.classList.remove('encima')));
rdZona.addEventListener('drop', (e) => { e.preventDefault(); rdZona.classList.remove('encima'); rdAgregar(e.dataTransfer && e.dataTransfer.files); });
document.querySelectorAll('.rd-tipo button').forEach((b) => b.addEventListener('click', () => {
  if (!rd.cab) return;
  rd.cab.tipo = b.dataset.tipo;
  rdPintarCab();
  rdPintarResumen();
  rdGuardar();
}));
[['#rdDeudor', 'deudor'], ['#rdPeriodo', 'periodo'], ['#rdNumero', 'numero'], ['#rdUnidad', 'unidad'], ['#rdValeFecha', 'valeFecha']].forEach(([s, campo]) => {
  $(s).addEventListener('input', (e) => {
    if (!rd.cab) return;
    rd.cab[campo] = e.target.value;
    if (campo === 'periodo') { rd.cab.periodoAMano = !!e.target.value.trim(); if (!rd.cab.periodoAMano) rdPeriodoAuto(); }
    if (campo === 'deudor') guardar(RD_CLAVE_DEUDOR, e.target.value.trim());
    rdGuardar();
  });
});
$('#rdValeMonto').addEventListener('input', (e) => { if (!rd.cab) return; rd.cab.valeMonto = rdMonto(e.target.value); rdPintarResumen(); rdGuardar(); });
const rdAplicarTodos = () => {
  const o = rdProyectoDe($('#rdTodos').value);
  if (!o) { avisar(rd.carpetas ? 'Elige un proyecto de la lista.' : 'La lista de proyectos llega con la carpeta del equipo conectada.'); return; }
  rd.docs.forEach((d) => {
    d.campos.proyecto = o.carpeta;
    if (!d.editado.includes('proyecto')) d.editado.push('proyecto');
    if (d.marcar) d.marcar = d.marcar.filter((x) => x !== 'proyecto');
  });
  rd.cab.ultimoProyecto = o.carpeta;
  $('#rdTodos').value = '';
  rdGuardar();
  $('#rdTodosAplicar').focus();
  rdPintar();
};
$('#rdTodosAplicar').addEventListener('click', rdAplicarTodos);
$('#rdTodos').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); rdAplicarTodos(); } });
$('#rdPdf').addEventListener('click', rdGenerarPdf);
$('#rdEnviar').addEventListener('click', rdEnviar);
$('#rdNueva').addEventListener('click', rdNueva);
$('#rdLector').addEventListener('click', rdAbrirLector);
$('#rdGirarIzq').addEventListener('click', () => rdGirar(-90));
$('#rdGirarDer').addEventListener('click', () => rdGirar(90));
$('#rdReleer').addEventListener('click', rdReleer);
$('#dlgRdDoc').addEventListener('close', () => {
  const d = rd.abierto;
  rd.abierto = null;
  if (d && rd.docs.includes(d)) { rdPintarFila(d); rdPintarResumen(); }
});
$('#rdLectorForm').addEventListener('submit', rdGuardarLector);
$('#rdLectorX').addEventListener('click', () => $('#dlgRdLector').close());
$('#rdLectorQuitar').addEventListener('click', () => {
  try { localStorage.removeItem(RD_CLAVE_LECTOR); } catch (e) { /* nada */ }
  $('#dlgRdLector').close();
  rdPintarCab();
  avisar('Las fotos se leen en este navegador.');
});
// Planilla de Ingreso
$('#pqActualizar').append(icono('recargar', 16));
$('#pqActualizar').addEventListener('click', () => {
  if (rc.sinDatos === 'permiso') { rcPedirPermiso(); return; }
  rcCargar();
  pqPintar();
});
$('#pqNuevo').prepend(icono('mas', 16));
$('#pqNuevo').addEventListener('click', () => pqAbrir(null));
$('#pqExcel').href = HERR.get('planilla').url;
$('#pqExcel').append(icono('fuera', 14));
$('#pqBuscar').addEventListener('input', (e) => { pq.q = e.target.value; pq.mostrar = PQ_PAGINA; pqPintarTabla(); });
$('#pqBuscar').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  e.preventDefault();
  const filas = pqFiltradas();
  if (filas.length === 1) pqAbrir(filas[0]);
});
$('#pqMas').addEventListener('click', () => { pq.mostrar += PQ_PAGINA; pqPintarTabla(); });
$('#pqForm').addEventListener('submit', pqGuardar);
// Postventa: «ID o referencia» pasa a ser el proyecto original (su N° o su nombre, con sugerencias)
$('#pqCanal').addEventListener('change', () => {
  const pv = $('#pqCanal').value === 'Postventa';
  if (pv && !$('#pqOriginal').value) $('#pqOriginal').value = $('#pqReferencia').value === '-' ? '' : $('#pqReferencia').value;
  if (!pv && !$('#pqReferencia').value) $('#pqReferencia').value = $('#pqOriginal').value;
  pqVerOriginal();
});
$('#pqOriginal').addEventListener('change', () => { const v = pqOriginal($('#pqOriginal').value.trim()); if (v) $('#pqOriginal').value = v; });
$('#pqEstado').addEventListener('change', () => pqVerMover(false));
$('#pqX').addEventListener('click', () => $('#dlgPlanilla').close());
$('#pqCancelar').addEventListener('click', () => $('#dlgPlanilla').close());
$('#pqFormular').addEventListener('click', () => {
  const a = pq.abierta;
  $('#dlgPlanilla').close();
  if (a) rcIr(RC_IR.req(a.numero));
});
$('#dlgPlanilla').addEventListener('close', () => { pq.abierta = null; });
// Planificación semanal
plRecuperarPendiente();
$('#plAntes').append(icono('izquierda', 18));
$('#plDespues').append(icono('derecha', 18));
$('#plAntes').addEventListener('click', () => plIrSemana(-1));
$('#plDespues').addEventListener('click', () => plIrSemana(1));
$('#plHoy').addEventListener('click', () => plIrSemana(0));
PL_VISTAS.forEach((v) => {
  const b = crear('button', 'pl-vista');
  b.type = 'button';
  b.dataset.vista = v.id;
  b.append(icono(v.icono, 16), crear('span', null, v.nombre));
  b.addEventListener('click', () => plElegirVista(v.id));
  $('#plVistas').append(b);
});
$('#plSabado').addEventListener('change', (e) => { planif.sabado = e.target.checked; plGuardarPrefs(); plPintar(); });
[['#plAgregar', 'mas', 'Agregar', () => plAbrirAgregar(planif.vista === 'proyecto' ? 'proyecto' : 'persona')],
  ['#plProyectos', 'bandera', 'Estado de los proyectos', () => plAbrirProyectos()],
  ['#plCopiar', 'copiar', 'Copiar la semana anterior', plCopiarAnterior], ['#plCompartir', 'compartir', 'Compartir', plCompartir],
  ['#plImprimir', 'imprimir', 'Imprimir o PDF', plAbrirExportar]].forEach(([id, ico, txt, ir]) => {
  const b = $(id);
  b.append(icono(ico, 16), crear('span', null, txt));
  b.setAttribute('aria-label', txt);
  b.addEventListener('click', () => { plMasMenu(false); ir(); });
});
$('#vistaPlan').addEventListener('dragover', plArrSobre);
$('#vistaPlan').addEventListener('click', plQuitarToque, true);      // antes que la casilla: la ✕ no abre su ventanita
$('#vistaPlan').addEventListener('drop', plArrSoltar);
// Esc deja de poner lo elegido en el panel (si no hay una ventanita abierta, que se cierra primero)
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && planif.armado && !$('#vistaPlan').hidden && $('#plPop').hidden) { planif.armado = null; plPintar(); }
});
$('#plMas').append(crear('span', null, 'Más'), icono('flecha', 16));
$('#plMas').setAttribute('aria-label', 'Más acciones');
$('#plMas').addEventListener('click', () => plMasMenu($('#plMasLista').hidden));
document.addEventListener('pointerdown', (e) => { if (!$('#plMasLista').hidden && !e.target.closest('.pl-mas-menu:not(.pl-per-menu)')) plMasMenu(false); });
$('#plPersonas').addEventListener('click', () => plPersonasMenu($('#plPersonasLista').hidden));
document.addEventListener('pointerdown', (e) => { if (!$('#plPersonasLista').hidden && !e.target.closest('.pl-per-menu')) plPersonasMenu(false); });
$('#plPersonasLista').addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.stopPropagation(); plPersonasMenu(false); $('#plPersonas').focus(); } });
$('#plAgregarDura').addEventListener('click', (e) => {
  const b = e.target.closest('[data-fija]');
  if (!b) return;
  planif.agregarFija = b.dataset.fija === '1';
  plPintarAgregar();
  $('#plAgregarNombre').focus();
});
$('#plMasLista').addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.stopPropagation(); plMasMenu(false); $('#plMas').focus(); } });
$('#plActualizar').append(icono('recargar', 16));
$('#plActualizar').addEventListener('click', () => {
  if (rc.sinDatos === 'permiso') { rcPedirPermiso(); return; }
  rcCargar();
  plPintarFrescura();
});
$('#plReintentar').addEventListener('click', () => { planif.errorGuardar = null; plGuardar(); });
['#plPersonal', '#plProyecto'].forEach((id) => $(id).addEventListener('keydown', plTeclasTabla));
$('#plPopX').addEventListener('click', () => plCerrarPop(true));
$('#plPopListo').addEventListener('click', () => plCerrarPop(true));
$('#plPopSiguiente').addEventListener('click', (e) => plEnfocar(e.currentTarget.dataset.clave, true));
$('#plCopiarTexto').addEventListener('click', plCopiarTexto);
document.querySelectorAll('#plTextoModo .pl-vista').forEach((b) => b.addEventListener('click', () => {
  planif.texto = b.dataset.modo;
  plGuardarPrefs();
  plPintarTexto();
}));
['#plExpTabla', '#plExpHojas'].forEach((id) => $(id).addEventListener('change', plExpCuenta));
$('#plAgregarForm').addEventListener('submit', plConfirmarAgregar);
document.querySelectorAll('#plAgregarModo .pl-vista').forEach((b) => b.addEventListener('click', () => {
  planif.agregar = b.dataset.modo;
  plPintarAgregar();
  $('#plAgregarNombre').focus();
}));
['#plAgregarX', '#plAgregarCerrar'].forEach((id) => $(id).addEventListener('click', () => $('#dlgPlAgregar').close()));
$('#plAgregarNombre').addEventListener('input', () => { if ($('#plAgregarPista').classList.contains('error')) plPintarAgregar(); });
$('#plExpImprimir').addEventListener('click', plImprimir);
$('#plProyForm').addEventListener('submit', plConfirmarCierre);
['#plProyX', '#plProyCerrar'].forEach((id) => $(id).addEventListener('click', () => $('#dlgPlProyectos').close()));
$('#dlgPlProyectos').addEventListener('close', () => { planif.cerrar = null; planif.proyAviso = null; });
$('#vistaPlan').addEventListener('scroll', plColocarPop, { passive: true });
window.addEventListener('resize', plColocarPop);
// Lo que espera guardarse no espera al próximo cambio si la pestaña se esconde
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') { if (planif.porGuardar.size) plGuardar(); }
  else plVigilar();         // al volver a la pestaña, lo que llegó mientras tanto, sin esperar la vuelta
});
window.addEventListener('focus', plVigilar);
setInterval(plVigilar, 1000);
// Proyectos en ejecución
ejRecuperarPendiente();
$('#ejActualizar').append(icono('recargar', 16));
$('#ejActualizar').addEventListener('click', () => {
  if (rc.sinDatos === 'permiso') { rcPedirPermiso(); return; }
  rcCargar();
  ejPintarFrescura();
});
$('#ejReintentar').addEventListener('click', () => { ej.errorGuardar = null; ej.porGuardar = true; ejGuardar(); });
$('#ejMios').addEventListener('change', (e) => { ej.mios = e.target.checked; ejGuardarPrefs(); ejPintar(); });
$('#ejConDatos').addEventListener('change', (e) => { ej.conDatos = e.target.checked; ejGuardarPrefs(); ejPintar(); });
// Las pestañas: clic, o las flechas, Inicio y Fin (el foco va con la elegida)
document.querySelectorAll('#ejPestanas [role="tab"]').forEach((b) => {
  b.addEventListener('click', () => { ejElegirPestana(b.dataset.pestana); });
  b.addEventListener('keydown', (e) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    e.preventDefault();
    const otra = e.key === 'Home' ? 'ejecucion' : e.key === 'End' ? 'entregados' : b.dataset.pestana === 'ejecucion' ? 'entregados' : 'ejecucion';
    const x = $('#ejPestanas [data-pestana="' + otra + '"]');
    x.click();
    x.focus();
  });
});
$('#ejBuscar').addEventListener('input', (e) => { ej.q = e.target.value; ejPintar(); });
$('#ejBuscar').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  e.preventDefault();
  const primera = $('#ejTarjetas .ej-tarjeta');
  if (primera) primera.click();
});
// Lo escrito en los campos del resumen sobrevive a cada repintado (cambia algo del equipo, se marca una casilla)
['input', 'change'].forEach((tipo) => $('#ejProyecto').addEventListener(tipo, (e) => {
  const x = e.target;
  if (x && x.id && /^(INPUT|TEXTAREA|SELECT)$/.test(x.tagName) && x.type !== 'checkbox') ej.sucios.set(x.id, x.value);
}));
// El diálogo de un ítem con sus proveedores
$('#ejCostoForm').addEventListener('submit', ejGuardarCosto);
['#ejCostoX', '#ejCCancelar'].forEach((s) => $(s).addEventListener('click', () => { $('#dlgEjCosto').close(); ej.editando = null; }));
['#ejCDesc', '#ejCCant', '#ejCUnidad'].forEach((s) => $(s).addEventListener('input', ejPintarEvaluacion));
$('#ejCProvs').addEventListener('input', (e) => { if (ej.editando && e.target.matches('.ej-p-el')) ej.editando.auto = false; ejPintarEvaluacion(); });
$('#ejCProvs').addEventListener('click', (e) => { const b = e.target.closest('.ej-p-quitar'); if (b) ejQuitarProv(b.closest('.ej-prov-fila')); });
$('#ejCOtroProv').prepend(icono('mas', 15));
$('#ejCOtroProv').addEventListener('click', ejAgregarProv);
$('#ejCLinea').addEventListener('change', (ev) => ejAgregarLinea(ev.target.value));
$('#ejCEstado').addEventListener('change', () => { ejMostrarOC(); if ($('#ejCEstado').value === 'comprada') $('#ejCOC').focus(); });
$('#ejCBorrar').addEventListener('click', () => {
  const e = ej.editando, it = e && e.previo;
  if (!it || !rc.dir) return;
  $('#dlgEjCosto').close();
  ej.editando = null;
  ejBorrarItem(it, e.xs);
});
$('#dlgEjCosto').addEventListener('close', () => { ej.editando = null; });
// Pegar una cotización
$('#ejPegarForm').addEventListener('submit', ejAgregarPegadas);
['#ejPegarX', '#ejPCancelar'].forEach((s) => $(s).addEventListener('click', () => { $('#dlgEjPegar').close(); ej.pegadas = null; }));
$('#ejPegarTexto').addEventListener('input', ejPintarPrevia);
$('#ejPIva').addEventListener('change', () => { if (ej.pegadas) ej.pegadas.ivaTocado = true; ejPintarPrevia(); });
// La venta
$('#ejVentaForm').addEventListener('submit', (e) => ejGuardarVenta(e, false));
$('#ejNombreForm').addEventListener('submit', ejGuardarNombre);
['#ejNomX', '#ejNomCancelar'].forEach((s) => $(s).addEventListener('click', () => $('#dlgEjNombre').close()));
$('#ejCerrarForm').addEventListener('submit', ejGuardarCerrar);
['#ejCerX', '#ejCerCancelar'].forEach((s) => $(s).addEventListener('click', () => $('#dlgEjCerrar').close()));
$('#ejVQuitar').addEventListener('click', () => ejGuardarVenta(null, true));
['#ejVentaX', '#ejVCancelar'].forEach((s) => $(s).addEventListener('click', () => $('#dlgEjVenta').close()));
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden' && ej.porGuardar) ejGuardar(); });
setInterval(ejVigilar, 5000);
// Trabajar a la vez: la presencia de este navegador y la de los demás
setInterval(presVigilar, 3000);
document.addEventListener('visibilitychange', presVigilar);
// Al día sin F5: lo publicado de nuevo (el Portal y las herramientas abiertas) y los datos del Inicio y el Recorrido
adIniciar();
// La cotización del Cotizador Histórico, a un proyecto
$('#llForm').addEventListener('submit', llLlevar);
['#llX', '#llCancelar'].forEach((s) => $(s).addEventListener('click', () => $('#dlgLlevar').close()));
$('#dlgLlevar').addEventListener('close', () => { ll.datos = null; });
$('#llBuscar').addEventListener('input', (e) => { ll.q = e.target.value; llPintarLista(); llPintarPie(); });
$('#llBuscar').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  e.preventDefault();          // Enter elige el primero que coincide; llevarla es con el botón
  const primera = $('#llLista .ll-item');
  if (primera) primera.click();
});
// ---- «Qué buscamos» del tablero de Oportunidades (2026-11-16) ----------------------------------------
// El tablero no tiene la carpeta del equipo: manda los ajustes aquí y el Portal deja un «ajustes-oportunidades» en el
// buzón (lo aplica oportunidades.py en la próxima actualización del tablero). Contesta al tablero con el resultado.
async function opGuardarAjustes(m, ventana) {
  const responder = (r) => { try { ventana.postMessage(Object.assign({ tipo: 'quempin-ajustes-oportunidades-resultado', pedido: m.pedido }, r), location.origin); } catch (e) { /* se cerró */ } };
  if (!m.ajustes || typeof m.ajustes !== 'object' || Array.isArray(m.ajustes)) { responder({ ok: false, error: 'los ajustes no vienen bien armados.' }); return; }
  if (!rc.dir) await rcCargar();
  if (soloLectura()) { responder({ ok: false, error: 'en este navegador el Portal solo lee los datos: guárdalo desde un computador con la carpeta del equipo.' }); return; }
  if (!rc.dir) {
    responder({ ok: false, error: rc.sinDatos === 'navegador' ? 'este navegador no abre carpetas (usa Chrome o Edge de escritorio).'
      : 'el Portal no tiene abierta la carpeta del equipo. Ábrela en el Recorrido y vuelve a guardar.' });
    return;
  }
  const enviado = scAhora();
  const id = scId();
  const origen = { herramienta: 'portal', enviado };
  if (estado.usuario) origen.usuario = estado.usuario;
  const msg = { esquema: 'quempin.intercambio/1', id, tipo: 'ajustes-oportunidades', destino: 'oportunidades', origen, ajustes: m.ajustes };
  const nombre = enviado.slice(0, 19).replace(/[-:]/g, '').replace('T', '-') + '_portal_ajustes-oportunidades_' + id + '.json';
  try {
    const buzon = await rc.dir.getDirectoryHandle('buzon', { create: true });
    const w = await (await buzon.getFileHandle(nombre, { create: true })).createWritable();
    await w.write(JSON.stringify(msg, null, 2) + '\n');
    await w.close();
  } catch (err) {
    console.error(err);
    responder({ ok: false, error: 'no se pudo escribir en la carpeta del equipo: revisa que OneDrive esté funcionando.' });
    return;
  }
  responder({ ok: true, id, enviado });
  avisar('«Qué buscamos» guardado: vale para todo el equipo desde la próxima actualización de Oportunidades.');
}
// Llega del Cotizador abierto aquí dentro o del que abrió este Portal (ver el arranque): de otro lado, no se atiende
window.addEventListener('message', (e) => {
  const m = e.data;
  if (e.origin !== location.origin || !m || typeof m !== 'object'
    || !['quempin-cotizacion', 'quempin-nuevo-requerimiento', 'quempin-ajustes-oportunidades'].includes(m.tipo)) return;
  const deAqui = estado.pestanas.some((p) => ventanaDe(p) === e.source);
  if (m.tipo === 'quempin-ajustes-oportunidades') { if (deAqui) opGuardarAjustes(m, e.source); return; }
  if (m.tipo === 'quempin-nuevo-requerimiento') { if (deAqui) pqNuevoCon(m.datos); return; }
  if (!deAqui && !(window.opener && e.source === window.opener)) return;
  llAbrir(m.datos);
});
// Con muchas pestañas abiertas, la rueda del mouse las recorre de lado (no hay barra).
$('#pestanas').addEventListener('wheel', (e) => {
  const lista = $('#pestanas');
  if (lista.scrollWidth <= lista.clientWidth || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
  lista.scrollLeft += e.deltaY;
  e.preventDefault();
}, { passive: false });

const campo = $('#buscar');
campo.addEventListener('input', () => { elegido = campo.value.trim() ? 0 : -1; pintarResultados(); });
campo.addEventListener('focus', () => { if (campo.value.trim()) pintarResultados(); });
campo.addEventListener('blur', () => setTimeout(() => {
  if (document.activeElement !== campo) { $('#resultados').hidden = true; campo.setAttribute('aria-expanded', 'false'); }
}, 150));
campo.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    if (!resultados.length) return;
    e.preventDefault();
    elegido = (elegido + (e.key === 'ArrowDown' ? 1 : -1) + resultados.length) % resultados.length;
    pintarResultados();
    const b = document.getElementById('res-' + elegido);
    if (b) b.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') {
    if (resultados.length) { e.preventDefault(); irA(elegido >= 0 ? elegido : 0); }
  }
});
$('#btnBuscar').addEventListener('click', () => {
  if (portal.classList.contains('buscando')) mostrarBuscadorMovil(false); else enfocarBuscador();
});

document.addEventListener('keydown', teclas);
document.addEventListener('click', (e) => {
  const popU = $('#popUsuario');
  if (!popU.hidden && !usuarioRecien && !popU.contains(e.target) && !$('#btnUsuario').contains(e.target)) cerrarUsuario(false);
  // La ventanita de la Planificación: tocar fuera la cierra (otra casilla abre la suya). Se mira el camino del clic, no
  // su destino: al cambiar algo la ventanita se repinta y el botón tocado ya no está en ella.
  const popP = $('#plPop');
  if (!popP.hidden && !plPopRecien) {
    const camino = e.composedPath();
    if (!camino.includes(popP) && !camino.includes($('#aviso'))) plCerrarPop(false);
  }
});

$('#btnRecargar').addEventListener('click', () => {
  const p = pestanaDe(estado.activa);
  if (p) ctxRecargar(p);
});
$('#btnAparte').addEventListener('click', () => {
  const p = pestanaDe(estado.activa);
  if (p) $('#btnAparte').href = ctxDireccion(p);
});

window.addEventListener('storage', (e) => {
  if (e.key === LS_FORMULADOR) refrescarProyectos();
  // El usuario elegido en el Formulador (aquí dentro o en otra pestaña) también vale aquí
  if (e.key === LS.usuario || e.key === null) {
    estado.usuario = leerUsuario();
    pintarUsuario();
    rcAlCambiarUsuario();
  }
  // La contraseña o el usuario recién escritos en una herramienta marcan su paso en «Preparar este computador»
  if ((e.key === LS_CLAVE_TABLEROS || e.key === LS.usuario || e.key === null) && cxArmada && !$('#vistaConexiones').hidden) pintarEstadoConexiones();
  // Si en una herramienta se acaba de escribir la contraseña, las que esperaban con el candado se abren.
  // Si en otra pestaña se cerró la sesión, esta también se cierra (salvo que tenga algo sin guardar).
  if (e.key === LS_CLAVE_TABLEROS && !e.newValue && e.oldValue) {
    if (!adPortalOcupado()) location.reload();
    else avisar('Se cerró la sesión en este equipo. Guarda lo que tienes abierto y recarga la página.');
  }
  if (e.key === LS_CLAVE_TABLEROS && e.newValue) {
    estado.pestanas.forEach((p) => {
      const w = ventanaDe(p);
      if (w && bloqueada(w)) { try { w.location.reload(); } catch (err) { /* nada */ } }
    });
  }
});

// Pestañas de la visita anterior: vuelven sin cargar (solo la activa se abre).
const previas = leer(LS.pestanas, null);
if (previas && Array.isArray(previas.pestanas)) {
  previas.pestanas.forEach((x) => {
    const h = x && HERR.get(x.herr);
    if (!h || (h.tipo !== 'marco' && h.tipo !== 'vista') || familiaDe(h) !== x.familia || pestanaDe(x.familia)) return;
    const url = h.tipo === 'vista' ? '' : typeof x.url === 'string' && x.url.startsWith('/') ? x.url : urlDe(h);
    estado.pestanas.push({ familia: x.familia, herr: h.id, url, ultima: url, marco: null, cargador: null, cargando: false, usado: 0 });
  });
}
// El Cotizador abierto suelto abre …/portal/#/llevar-cotizacion para llevar su cotización a un proyecto: se le avisa
// que el Portal está listo y él la manda como mensaje (la dirección no la lleva: así no queda en el historial)
if (/^#\/?llevar-cotizacion\b/.test(location.hash)) {
  try { history.replaceState(null, '', '#/'); } catch (e) { /* nada */ }
  if (window.opener) { try { window.opener.postMessage({ tipo: 'quempin-portal-listo' }, location.origin); } catch (e) { /* se cerró */ } }
}
// Una dirección como …/portal/#/centro-costos abre esa herramienta.
let pedida = null;
try { pedida = HERR.get(decodeURIComponent(location.hash.replace(/^#\/?/, '').split(/[/?]/)[0] || '')); } catch (e) { pedida = null; }
// …/portal/#/planilla?nuevo=<JSON>: «Ingresar en Requerimientos» del Formulador abierto fuera del portal
const nuevoPedido = /^#\/?planilla\?nuevo=(.*)$/.exec(location.hash);
if (nuevoPedido) {
  let datos = null;
  try { datos = JSON.parse(decodeURIComponent(nuevoPedido[1])); } catch (e) { datos = null; }
  try { history.replaceState(null, '', '#/planilla'); } catch (e) { /* nada */ }
  if (datos) { pqNuevoCon(datos); pedida = null; }
}
if (nuevoPedido && !pedida) { /* ya abierta por pqNuevoCon */ }
else if (pedida && (pedida.tipo === 'marco' || pedida.tipo === 'vista')) {
  // Si la pestaña de la visita anterior mostraba otra herramienta de la misma página (Análisis
  // Financiero e Ingresar avance), se abre la pedida: antes quedaba la
  // anterior con el nombre de la pedida (…/portal/#/ingresar mostraba el Resumen, 2026-10-25).
  const ya = pestanaDe(familiaDe(pedida));
  if (ya && ya.herr === pedida.id) activar(ya.familia); else abrir(pedida.id);
} else {
  activar(previas && pestanaDe(previas.activa) ? previas.activa : 'inicio');
}
// La alarma de la Planificación se ve desde cualquier herramienta: se lee la carpeta del equipo aunque el portal no abra
// en el Inicio (sin pedir permisos: si falta algo, no aparece).
if (!rc.intentado) { rc.intentado = true; rcCargar(); }
