/* numeros.js — cajas de números de las herramientas QUEMPIN (pedido del usuario, 2026-11-10).

   Original: Finanzas QUEMPIN «Visualizador Web/numeros.js» (los tableros la llevan incrustada, como candado.js).
   Copias idénticas: Formulador «js/numeros.js» y Calculadora Técnica «assets/numeros.js». Un test compara las copias:
   cámbialas juntas.

   - Al entrar a una caja numérica (clic, toque o Tab) se selecciona todo: lo que se escribe reemplaza al 0 que había.
   - Mientras se escribe aparece el punto de miles (1.234.567); la coma es la decimal (12,5), como en Chile.
   - Un punto tecleado se lee como en el resto de QUEMPIN: «1.500» y «1.500.000» son miles, «2.5» es decimal.

   Qué cajas toma:
   - <input type="number">: pasa a ser de texto, porque el navegador no muestra puntos en una numérica. Su .value y
     .valueAsNumber siguen dando el número sin formato («1234.5»): el código de cada herramienta no cambia.
   - <input data-num>: caja de texto cuya herramienta ya lee el formato chileno; se formatea y .value da lo que se ve.
     Tokens: «entero» (sin decimales), «canonico» (.value da el número sin formato, como las type="number").
   - <script src="…/numeros.js" data-canonico="selector">: esas cajas se tratan como data-num="canonico".
   - Una caja con inputmode numeric/decimal y sin data-num (un N° de OC, un año): solo se selecciona todo, sin puntos.
*/
(function () {
  'use strict';
  if (typeof window === 'undefined' || window.QuempinNumeros) return;

  var VALOR = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  var crudo = function (el) { return VALOR.get.call(el); };
  var poner = function (el, t) { VALOR.set.call(el, t); };
  var guion = document.currentScript;
  var selectorCanonico = (guion && guion.getAttribute('data-canonico')) || '';
  var CANONICO = /^-?\d+(\.\d+)?(e[+-]?\d+)?$/i;

  /* Texto (tecleado o pegado) -> número sin formato («1234.5»), o null si no es un número.
     Con coma: los puntos son de miles. Sin coma: puntos en grupos de 3 («1.500») son de miles y un punto
     suelto («2.5») es decimal, igual que ejNumero del Portal, limpiarNumero de AF y parsear_cantidad_decimal
     de Sistema QUEMPIN. Si están los dos, el último es el decimal («1,234.56» pegado de un sistema en inglés). */
  function canonico(texto) {
    var s = String(texto == null ? '' : texto).replace(/[^\d.,-]/g, '');
    var neg = s.charAt(0) === '-';
    s = s.replace(/-/g, '');
    if (!/\d/.test(s)) return null;
    var coma = s.lastIndexOf(','), punto = s.lastIndexOf('.');
    if (coma >= 0 && punto > coma) s = s.replace(/,/g, '');
    else if (coma >= 0) s = s.replace(/\./g, '').replace(/,(?=.*,)/g, '').replace(',', '.');
    else if (/^\d{1,3}(\.\d{3})+$/.test(s) || s.split('.').length > 2) s = s.replace(/\./g, '');
    if (s.charAt(0) === '.') s = '0' + s;
    s = s.replace(/\.$/, '').replace(/^0+(?=\d)/, '');
    if (!/^\d+(\.\d+)?$/.test(s)) return null;
    return (neg && /[1-9]/.test(s) ? '-' : '') + s;
  }

  var agrupar = function (ent) { return ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.'); };

  /* Número sin formato (texto o number) -> como se ve: «1.234,5». */
  function mostrar(c) {
    if (c === null || c === undefined || c === '') return '';
    var s = String(c);
    if (/e/i.test(s)) {
      var n = Number(s);
      if (!isFinite(n)) return '';
      s = Math.abs(n) < 1e21 ? n.toFixed(20).replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '') : String(n);
    }
    var neg = s.charAt(0) === '-';
    if (neg) s = s.slice(1);
    var p = s.split('.');
    return (neg ? '-' : '') + agrupar(p[0] || '0') + (p.length > 1 && p[1] !== '' ? ',' + p[1] : '');
  }

  /* ---- Configuración de cada caja ---------------------------------------------------------------- */
  function decimalesDe(paso) {
    if (!paso || paso === 'any') return -1;   // -1 = sin límite
    var n = Number(paso);
    if (!isFinite(n) || n <= 0) return -1;
    if (Number.isInteger(n)) return 0;
    var m = /\.(\d+)$/.exec(String(paso));
    return m ? m[1].length : -1;
  }
  function tokens(el) { return ' ' + (el.getAttribute('data-num') || '') + ' '; }
  function esCanonicaPorSelector(el) {
    try { return !!selectorCanonico && el.matches(selectorCanonico); } catch (e) { return false; }
  }
  function formateable(el) {
    return !!el && el.tagName === 'INPUT' && !el.readOnly &&
      (el.type === 'number' || el.hasAttribute('data-num') || esCanonicaPorSelector(el) || !!el._qn);
  }
  function soloSeleccion(el) {
    return !!el && el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'tel' || el.type === '') &&
      /^(numeric|decimal)$/.test(el.getAttribute('inputmode') || '');
  }

  /* Deja la caja lista: la de tipo number pasa a texto con su número formateado y un .value sin formato. */
  function preparar(el) {
    if (el._qn || !formateable(el)) return el._qn || null;
    var numero = el.type === 'number';
    var t = tokens(el);
    var cfg = {
      canonico: numero || / canonico /.test(t) || esCanonicaPorSelector(el),
      decimales: / entero /.test(t) ? 0 : decimalesDe(el.getAttribute('step')),
      negativos: !(el.hasAttribute('min') && Number(el.getAttribute('min')) >= 0),
      punto: false
    };
    var inicial = crudo(el);
    el._qn = cfg;
    if (numero) {
      el.type = 'text';
      if (!el.hasAttribute('inputmode')) el.setAttribute('inputmode', cfg.decimales === 0 ? 'numeric' : 'decimal');
    }
    el.setAttribute('autocomplete', 'off');
    el.classList.add('qnum');
    if (cfg.canonico) {
      Object.defineProperty(el, 'value', {
        configurable: true,
        get: function () { return valorDe(el); },
        set: function (v) { ponerValor(el, v); }
      });
      Object.defineProperty(el, 'valueAsNumber', {
        configurable: true,
        get: function () { var v = valorDe(el); return v === '' ? NaN : Number(v); },
        set: function (n) { ponerValor(el, isFinite(n) ? n : ''); }
      });
    }
    ponerValor(el, inicial);
    return cfg;
  }

  /* Lo que la herramienta lee: sin formato en las canónicas (o el texto tal cual si no es un número, para que
     su validación lo marque), lo que se ve en las demás. */
  function valorDe(el) {
    var t = crudo(el);
    if (!el._qn || !el._qn.canonico) return t;
    if (t.trim() === '') return '';
    var c = canonico(t);
    return c === null ? t : c;
  }
  function ponerValor(el, v) {
    var t = v === null || v === undefined ? '' : String(v);
    if (el._qn) el._qn.punto = false;
    if (t.trim() === '') { poner(el, ''); return; }
    var c = typeof v === 'number' || CANONICO.test(t.trim()) ? t.trim() : canonico(t);
    poner(el, c === null ? t : mostrar(c));
  }

  /* ---- Mientras se escribe -------------------------------------------------------------------------- */
  /* Reescribe la caja con sus puntos de miles sin mover el cursor de entre las cifras. */
  function formatearEnVivo(el) {
    var cfg = el._qn, t = crudo(el);
    var pos = el.selectionStart == null ? t.length : el.selectionStart;
    var neg = cfg.negativos && /^\s*-/.test(t);
    var ent = '', dec = '', coma = false, antes = 0;
    for (var i = 0; i < t.length; i++) {
      var ch = t.charAt(i), cuenta = false;
      if (ch >= '0' && ch <= '9') { if (coma) dec += ch; else ent += ch; cuenta = true; }
      else if (ch === ',' && !coma && cfg.decimales !== 0) { coma = true; cuenta = true; }
      if (cuenta && i < pos) antes++;
    }
    // Ceros a la izquierda: «05» -> «5» (el cursor retrocede los que estaban antes de él)
    var ceros = /^0+(?=\d)/.exec(ent);
    if (ceros) { ent = ent.slice(ceros[0].length); antes = Math.max(0, antes - ceros[0].length); }
    if (coma && ent === '') { ent = '0'; if (antes > 0) antes++; }
    if (cfg.decimales > 0 && dec.length > cfg.decimales) dec = dec.slice(0, cfg.decimales);
    var nuevo = (neg ? '-' : '') + agrupar(ent) + (coma ? ',' + dec : '');
    if (nuevo === t) return;
    var p = neg ? 1 : 0, vistas = 0;
    while (p < nuevo.length && vistas < antes) {
      var c2 = nuevo.charAt(p);
      if ((c2 >= '0' && c2 <= '9') || c2 === ',') vistas++;
      p++;
    }
    poner(el, nuevo);
    try { el.setSelectionRange(p, p); } catch (e) { /* caja oculta */ }
  }

  document.addEventListener('beforeinput', function (e) {
    var el = e.target, cfg = el && el._qn;
    if (!cfg || cfg.punto || cfg.decimales === 0 || !e.data || e.data.indexOf('.') < 0) return;
    // Un punto tecleado en una caja con decimales: ¿miles o decimal? Se decide al salir (o al pegar), con
    // la regla de canonico(). Mientras tanto la caja queda como se escribe, sin los puntos que puso esta caja.
    if (crudo(el).indexOf(',') < 0 && /^insert(Text|CompositionText)?$/.test(e.inputType || 'insertText')) cfg.punto = 'nuevo';
  }, true);

  document.addEventListener('input', function (e) {
    var el = e.target, cfg = el && el._qn;
    if (!cfg || e.isComposing) return;
    var tipo = e.inputType || '';
    if (/^insertFrom(Paste|Drop)/.test(tipo)) {
      var c = canonico(crudo(el));
      cfg.punto = false;
      if (c !== null) {
        if (cfg.decimales === 0 && c.indexOf('.') >= 0) c = String(Math.round(Number(c)));
        poner(el, mostrar(c));
        try { el.setSelectionRange(crudo(el).length, crudo(el).length); } catch (err) { /* caja oculta */ }
      }
      return;
    }
    if (cfg.punto === 'nuevo') {
      // Quita los puntos de miles que había puesto la caja; deja solo el que se tecleó (junto al cursor).
      var t = crudo(el), pos = el.selectionStart == null ? t.length : el.selectionStart;
      var limpio = '', nuevoPos = pos;
      for (var i = 0; i < t.length; i++) {
        if (t.charAt(i) === '.' && i !== pos - 1) { if (i < pos) nuevoPos--; continue; }
        limpio += t.charAt(i);
      }
      cfg.punto = true;
      if (limpio !== t) { poner(el, limpio); try { el.setSelectionRange(nuevoPos, nuevoPos); } catch (err) { /* */ } }
      return;
    }
    if (cfg.punto) return;
    formatearEnVivo(el);
  }, true);

  // Al salir: el formato definitivo («1.500» tecleado = mil quinientos; «2.5» = dos coma cinco)
  document.addEventListener('focusout', function (e) {
    var el = e.target, cfg = el && el._qn;
    if (el) el._qnPuntero = false;
    if (!cfg) return;
    var t = crudo(el);
    if (t.trim() === '') { cfg.punto = false; return; }
    var c = canonico(t);
    if (c !== null && cfg.decimales === 0 && c.indexOf('.') >= 0) c = String(Math.round(Number(c)));
    cfg.punto = false;
    if (c !== null && mostrar(c) !== t) poner(el, mostrar(c));
  }, true);

  // ↑ y ↓ suben y bajan un paso, como en las cajas numéricas del navegador
  document.addEventListener('keydown', function (e) {
    var el = e.target, cfg = el && el._qn;
    if (el && el._qnPuntero) el._qnPuntero = false;
    if (!cfg || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') || e.altKey || e.ctrlKey || e.metaKey || e.defaultPrevented) return;
    var c = canonico(crudo(el));
    var paso = Number(el.getAttribute('step'));
    if (!isFinite(paso) || paso <= 0) paso = 1;
    var n = (c === null ? 0 : Number(c)) + (e.key === 'ArrowUp' ? paso : -paso);
    var min = el.getAttribute('min'), max = el.getAttribute('max');
    if (min !== null && min !== '' && n < Number(min)) n = Number(min);
    if (max !== null && max !== '' && n > Number(max)) n = Number(max);
    n = Math.round(n * 1e9) / 1e9;
    e.preventDefault();
    cfg.punto = false;
    poner(el, mostrar(String(n)));
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }, true);

  /* ---- Seleccionar todo al entrar ------------------------------------------------------------------- */
  function seleccionar(el) { try { el.select(); } catch (e) { /* caja oculta */ } }
  document.addEventListener('pointerdown', function (e) {
    var el = e.target;
    if (el && el.tagName === 'INPUT' && document.activeElement !== el && (formateable(el) || soloSeleccion(el))) el._qnPuntero = true;
  }, true);
  document.addEventListener('focusin', function (e) {
    var el = e.target;
    if (!el || el.tagName !== 'INPUT') return;
    if (!formateable(el) && !soloSeleccion(el)) return;
    preparar(el);
    seleccionar(el);
    // Con el mouse, el clic pone el cursor después del foco: se vuelve a seleccionar al soltar. Solo con el
    // mouse: si una herramienta devuelve el foco y repone el cursor mientras se escribe, no se le pisa.
    if (el._qnPuntero) setTimeout(function () { if (el._qnPuntero && document.activeElement === el) seleccionar(el); }, 0);
  }, true);
  document.addEventListener('mouseup', function (e) {
    var el = e.target;
    if (!el || !el._qnPuntero) return;
    el._qnPuntero = false;
    if (document.activeElement === el) { e.preventDefault(); seleccionar(el); }
  }, true);
  document.addEventListener('touchend', function (e) {
    var el = e.target;
    if (el && el._qnPuntero) setTimeout(function () { el._qnPuntero = false; if (document.activeElement === el) seleccionar(el); }, 0);
  }, true);

  /* ---- Cajas que aparecen después (las herramientas dibujan con innerHTML) -------------------------- */
  function prepararEn(raiz) {
    if (!raiz || !raiz.querySelectorAll) return;
    if (raiz.tagName === 'INPUT') { preparar(raiz); return; }
    var sel = 'input[type="number"], input[data-num]' + (selectorCanonico ? ', ' + selectorCanonico : '');
    var lista;
    try { lista = raiz.querySelectorAll(sel); } catch (e) { lista = raiz.querySelectorAll('input[type="number"], input[data-num]'); }
    for (var i = 0; i < lista.length; i++) preparar(lista[i]);
  }
  function iniciar() {
    prepararEn(document);
    new MutationObserver(function (cambios) {
      for (var i = 0; i < cambios.length; i++) {
        var nodos = cambios[i].addedNodes;
        for (var j = 0; j < nodos.length; j++) if (nodos[j].nodeType === 1) prepararEn(nodos[j]);
      }
    }).observe(document.documentElement, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();

  window.QuempinNumeros = { canonico: canonico, mostrar: mostrar, preparar: preparar };
})();
