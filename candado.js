/* Candado de los tableros (2026-10-05) -- par de Visualizador Web/candado.py,
   que cada build_visualizador.py inserta en su tablero (el original, no una copia).

   Los datos llegan cifrados (AES-256-GCM, clave derivada de la contraseña con
   PBKDF2-SHA256): solo la contraseña correcta los abre, porque en la página no
   hay ninguna contraseña contra la cual comparar. La clave derivada se recuerda
   en este navegador (localStorage, la misma para los 7 tableros), así que la
   contraseña se escribe una vez; si cambia, la clave recordada deja de abrir
   los datos y el candado vuelve a pedirla. */
var QuempinCandado = (function () {
  var RECORDADA = 'quempin_viz_clave';

  // Igual que normalizar() de candado.py: sin mayúsculas, tildes ni espacios en los extremos.
  function normalizar(s) {
    return String(s == null ? '' : s).toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim();
  }
  function bytes(b64) {
    var bin = atob(b64);
    var out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function aB64(arr) {
    var bin = '';
    for (var i = 0; i < arr.length; i++) bin += String.fromCharCode(arr[i]);
    return btoa(bin);
  }

  function derivar(contrasena, sobre) {
    var sutil = crypto.subtle;
    return sutil.importKey('raw', new TextEncoder().encode(normalizar(contrasena)), 'PBKDF2', false, ['deriveBits'])
      .then(function (base) {
        return sutil.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: bytes(sobre.sal), iterations: sobre.it }, base, 256);
      })
      .then(function (bits) { return new Uint8Array(bits); });
  }
  // Sobre versión 2 (2026-10-08): los datos van comprimidos con gzip antes de
  // cifrar ("comp": "gzip"); el navegador los descomprime con DecompressionStream.
  // Los sobres versión 1 (sin "comp") se siguen abriendo igual.
  function puedeAbrir(sobre) {
    return sobre.comp !== 'gzip' || typeof DecompressionStream === 'function';
  }
  function descomprimir(buffer) {
    var flujo = new Blob([buffer]).stream().pipeThrough(new DecompressionStream('gzip'));
    return new Response(flujo).arrayBuffer();
  }
  // Con una clave equivocada AES-GCM rechaza la promesa (no devuelve basura).
  function descifrarBytes(clave, sobre) {
    return crypto.subtle.importKey('raw', clave, 'AES-GCM', false, ['decrypt'])
      .then(function (k) { return crypto.subtle.decrypt({ name: 'AES-GCM', iv: bytes(sobre.iv) }, k, bytes(sobre.datos)); })
      .then(function (plano) { return sobre.comp === 'gzip' ? descomprimir(plano) : plano; });
  }
  function descifrar(clave, sobre) {
    return descifrarBytes(clave, sobre)
      .then(function (plano) { return JSON.parse(new TextDecoder('utf-8').decode(plano)); });
  }

  // La clave con que se abrió este tablero: con ella se abren después los
  // archivos cifrados que se bajan al usarlos (los reportes PDF del AF).
  var claveAbierta = null;
  // Baja un archivo cifrado (ruta relativa al tablero, ej. reportes/<huella>.json)
  // y devuelve sus bytes ya descifrados (ArrayBuffer).
  function abrirArchivo(ruta) {
    if (!claveAbierta) return Promise.reject(new Error('El tablero todavía no está abierto.'));
    return fetch(ruta, { cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('No se encontró el archivo (' + r.status + ').');
        return r.json();
      })
      .then(function (sobre) { return descifrarBytes(claveAbierta, sobre); });
  }

  // Engancha el formulario de contraseña de la plantilla (#pwGate, #pwForm,
  // #pwInput, #pwError) y llama alAbrir(DATA) cuando los datos se abren.
  // idSobre es el <script type="text/plain"> con el sobre cifrado.
  function abrir(idSobre, alAbrir) {
    var sobre = JSON.parse(document.getElementById(idSobre).textContent);
    var gate = document.getElementById('pwGate');
    var form = document.getElementById('pwForm');
    var input = document.getElementById('pwInput');
    var error = document.getElementById('pwError');
    var boton = form.querySelector('button');

    function mostrar(DATA, clave) {
      claveAbierta = clave;
      try { localStorage.setItem(RECORDADA, aB64(clave)); } catch (e) {}
      gate.style.display = 'none';
      document.getElementById('vizRoot').style.display = '';
      alAbrir(DATA);
    }
    function pedir() {
      gate.style.visibility = '';
      input.focus();
    }

    // Marca de la barrera anterior: ya no abre nada.
    try { localStorage.removeItem('quempin_viz_unlocked'); } catch (e) {}

    // Antes de pedir la contraseña: si el navegador no puede abrir el sobre, que
    // no parezca una contraseña incorrecta.
    if (!window.crypto || !crypto.subtle || !puedeAbrir(sobre)) {
      error.textContent = 'Este navegador no puede abrir los datos cifrados. Actualízalo, o usa Chrome, Edge o Safari al día.';
      boton.disabled = true;
      return;
    }

    form.addEventListener('submit', function (evt) {
      evt.preventDefault();
      boton.disabled = true;
      error.textContent = 'Abriendo…';
      var clave;
      derivar(input.value, sobre)
        .then(function (c) { clave = c; return descifrar(c, sobre); })
        // Con dos argumentos: un error al dibujar el tablero no se confunde con una contraseña incorrecta.
        .then(function (DATA) { error.textContent = ''; mostrar(DATA, clave); }, function () {
          error.textContent = 'Contraseña incorrecta. Intenta de nuevo.';
          boton.disabled = false;
          input.value = '';
          input.focus();
        });
    });

    var recordada = null;
    try { recordada = localStorage.getItem(RECORDADA); } catch (e) {}
    if (!recordada) { pedir(); return; }
    // Con una clave recordada el formulario no se alcanza a ver mientras se descifra.
    gate.style.visibility = 'hidden';
    var clave;
    try { clave = bytes(recordada); } catch (e) { clave = new Uint8Array(0); }
    descifrar(clave, sobre).then(function (DATA) { mostrar(DATA, clave); }, function () {
      try { localStorage.removeItem(RECORDADA); } catch (e) {}
      pedir();
    });
  }

  return { abrir: abrir, derivar: derivar, descifrar: descifrar, descifrarBytes: descifrarBytes, abrirArchivo: abrirArchivo };
})();
