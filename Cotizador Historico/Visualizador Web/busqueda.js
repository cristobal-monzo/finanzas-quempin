/*
 * busqueda.js -- el lado navegador del buscador del Cotizador Historico.
 *
 * ESTE ARCHIVO ES UNO SOLO PARA CHILE Y PERU. Los dos build_visualizador.py
 * lo inyectan en su template reemplazando el placeholder __CH_BUSQUEDA_JS__.
 * No copiar su contenido dentro de un template.html: la taxonomia vivio
 * duplicada en los dos templates hasta 2026-09-08 y termino divergiendo sin
 * que nadie se enterara (Peru nunca recibio una categoria nueva).
 *
 * QUE HACE Y QUE NO
 *
 * Implementa SOLO el lado de la CONSULTA: normalizar lo que el usuario
 * escribe, detectar la medida que pidio y puntuar. Todo lo demas viene ya
 * resuelto desde Python dentro del snapshot:
 *
 *   DATA.busqueda   -- sinonimos, palabras vacias, pesos, alias de medida y
 *                      umbrales (Sistema/catalogo_busqueda.py)
 *   item._bt        -- los terminos indexados del item, por campo
 *   item._bm        -- todas las medidas que menciona el item
 *
 * Es decir: no hay una segunda lista de sinonimos ni una segunda gramatica
 * de medidas en JavaScript. Hay un lector de tablas.
 *
 * La paridad con el motor de Python se verifica en
 * Sistema/tests/test_paridad_busqueda_js.py, que corre las mismas consultas
 * por los dos motores y compara el orden resultante.
 */
(function (global) {
  'use strict';

  // ---------- normalizacion (espejo de taxonomia.normalizar/singular) ----------

  function sinTildes(s) {
    return String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  }

  function normalizar(s) {
    var t = sinTildes(s).toLowerCase().replace(/[^a-z0-9ñ]+/g, ' ');
    return t.replace(/\s+/g, ' ').trim();
  }

  // taxonomia.singular: no intenta deducir el singular real (el espanol no lo
  // permite sin lexico), lleva las dos formas a la misma raiz.
  function singular(p) {
    if (p.length <= 3) return p;
    if (p.slice(-3) === 'ces') p = p.slice(0, -3) + 'z';
    else if (p.slice(-1) === 's') p = p.slice(0, -1);
    if (p.length > 3 && p.slice(-1) === 'e') p = p.slice(0, -1);
    return p;
  }

  var COMILLAS = /[“”″′′]/g;

  function unificarComillas(s) {
    return String(s == null ? '' : s).replace(COMILLAS, '"').replace(/''/g, '"');
  }

  // Espejo de busqueda.normalizar_alias: deja pasar " / . - porque son parte
  // de la medida, y manda todo lo demas a espacio.
  function normalizarAlias(texto) {
    var t = sinTildes(unificarComillas(texto).toLowerCase());
    t = t.replace(/[^a-z0-9"/.\- ]+/g, ' ');
    return t.replace(/\s+/g, ' ').trim();
  }

  // ---------- distancia de edicion acotada ----------

  function maxErrores(largo, tabla) {
    for (var i = 0; i < tabla.length; i++) {
      if (largo >= tabla[i][0] && largo <= tabla[i][1]) return tabla[i][2];
    }
    return 0;
  }

  function distanciaAcotada(a, b, maximo) {
    if (a === b) return 0;
    var la = a.length, lb = b.length;
    if (Math.abs(la - lb) > maximo) return maximo + 1;
    var anterior = new Array(lb + 1), actual = new Array(lb + 1), j;
    for (j = 0; j <= lb; j++) anterior[j] = j;
    for (var i = 1; i <= la; i++) {
      actual[0] = i;
      var mejorFila = i, ca = a.charAt(i - 1);
      for (j = 1; j <= lb; j++) {
        var costo = ca === b.charAt(j - 1) ? 0 : 1;
        actual[j] = Math.min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + costo);
        if (actual[j] < mejorFila) mejorFila = actual[j];
      }
      if (mejorFila > maximo) return maximo + 1;
      var tmp = anterior; anterior = actual; actual = tmp;
    }
    return anterior[lb];
  }

  // ---------- el buscador ----------

  function crearBuscador(items, cfg) {
    var vacias = {};
    (cfg.vacias || []).forEach(function (v) { vacias[v] = true; });
    var sinonimos = cfg.sinonimos || {};
    var alias = cfg.alias_medida || {};
    var pesos = cfg.pesos_campo || {};
    var campos = cfg.campos || Object.keys(pesos);
    var pesoCampoMax = 0;
    campos.forEach(function (c) { if (pesos[c] > pesoCampoMax) pesoCampoMax = pesos[c]; });
    var maxPalabrasAlias = cfg.max_palabras_alias || 3;
    var n = items.length;

    function raiz(palabra) {
      var r = singular(normalizar(palabra));
      return Object.prototype.hasOwnProperty.call(sinonimos, r) ? sinonimos[r] : r;
    }

    function terminos(texto) {
      var vistos = [], partes = normalizar(texto).split(' ');
      for (var i = 0; i < partes.length; i++) {
        if (!partes[i] || vacias[partes[i]]) continue;
        var r = raiz(partes[i]);
        if (r && vistos.indexOf(r) === -1) vistos.push(r);
      }
      return vistos;
    }

    var ES_CODIGO = /^(?=.*\d)[a-z0-9]{4,}$/;

    // Un numero suelto en una CONSULTA es casi siempre el calibre: "valvula
    // bola 2" es una valvula de dos pulgadas, no dos valvulas. Las tres
    // guardas y sus constantes son las mismas que usa Python (vienen en
    // cfg.entero_suelto, no escritas aqui).
    var ENTERO = cfg.entero_suelto || { alias: {}, max_pulgadas: 24, angulos: [], cuantificadores: [] };
    function enteroSueltoComoPulgada(palabras) {
      for (var i = 0; i < palabras.length; i++) {
        if (!/^\d{1,2}$/.test(palabras[i])) continue;
        var valor = parseInt(palabras[i], 10);
        if (valor < 1 || valor > ENTERO.max_pulgadas) continue;
        if (ENTERO.angulos.indexOf(valor) !== -1) continue;
        if (i && ENTERO.cuantificadores.indexOf(palabras[i - 1]) !== -1) continue;
        return Object.prototype.hasOwnProperty.call(ENTERO.alias, palabras[i])
          ? ENTERO.alias[palabras[i]] : null;
      }
      return null;
    }

    function parsearConsulta(texto) {
      var medidas = {};
      var palabras = normalizarAlias(texto).split(' ').filter(Boolean);
      var usadas = {}, i = 0;
      while (i < palabras.length) {
        var avance = 1, tope = Math.min(maxPalabrasAlias, palabras.length - i);
        for (var largo = tope; largo >= 1; largo--) {
          var clave = palabras.slice(i, i + largo).join(' ');
          if (Object.prototype.hasOwnProperty.call(alias, clave)) {
            medidas[alias[clave]] = true;
            for (var k = i; k < i + largo; k++) usadas[k] = true;
            avance = largo;
            break;
          }
        }
        i += avance;
      }
      if (!Object.keys(medidas).length) {
        var suelto = enteroSueltoComoPulgada(palabras);
        if (suelto) medidas[suelto] = true;
      }
      var resto = palabras.filter(function (_p, idx) { return !usadas[idx]; }).join(' ');
      var terms = terminos(resto).filter(function (t) { return !/^\d+$/.test(t); });
      // Un codigo se escribe con separadores pero se indexa pegado. Palabra
      // por palabra, nunca la consulta entera (ver la nota en busqueda.py).
      palabras.forEach(function (palabra) {
        var pegado = palabra.replace(/[^a-z0-9]/g, '');
        if (ES_CODIGO.test(pegado) && terms.indexOf(pegado) === -1) terms.push(pegado);
      });
      return { terminos: terms, medidas: Object.keys(medidas) };
    }

    // ---------- indice invertido ----------

    var post = {}, df = {}, largo = {}, medidasItem = new Array(n);
    campos.forEach(function (c) { post[c] = {}; largo[c] = new Array(n); });

    for (var idx = 0; idx < n; idx++) {
      var bt = items[idx]._bt || {};
      var delItem = {};
      for (var ci = 0; ci < campos.length; ci++) {
        var campo = campos[ci], texto = bt[campo];
        if (!texto) { largo[campo][idx] = 0; continue; }
        var tks = texto.split(' ');
        largo[campo][idx] = tks.length;
        for (var ti = 0; ti < tks.length; ti++) {
          var termino = tks[ti];
          if (!post[campo][termino]) post[campo][termino] = [];
          post[campo][termino].push(idx);
          delItem[termino] = true;
        }
      }
      for (var t in delItem) df[t] = (df[t] || 0) + 1;
      medidasItem[idx] = items[idx]._bm || [];
    }
    var vocabOrdenado = Object.keys(df).sort();
    var vocabPorLargo = {};
    vocabOrdenado.forEach(function (t) {
      (vocabPorLargo[t.length] = vocabPorLargo[t.length] || []).push(t);
    });

    var cacheExpansion = {};

    function expandir(termino) {
      if (cacheExpansion[termino]) return cacheExpansion[termino];
      var exp = {}, exacto = Object.prototype.hasOwnProperty.call(df, termino);
      if (exacto) exp[termino] = cfg.calidad.exacta;
      if (termino.length >= 3) {
        // Prefijo: "valv" encuentra "valvula".
        var i = buscarInsercion(vocabOrdenado, termino);
        while (i < vocabOrdenado.length && vocabOrdenado[i].indexOf(termino) === 0) {
          if (exp[vocabOrdenado[i]] === undefined) exp[vocabOrdenado[i]] = cfg.calidad.prefijo;
          i++;
        }
      }
      // La expansion difusa solo corre si el termino NO existe tal cual: si
      // existe ya esta bien escrito, y buscarle vecinos cuesta casi toda la
      // latencia de la consulta ademas de traer ruido.
      if (!exacto) {
        var tope = maxErrores(termino.length, cfg.max_errores);
        for (var L = termino.length - tope; L <= termino.length + tope; L++) {
          var bucket = vocabPorLargo[L] || [];
          for (var b = 0; b < bucket.length; b++) {
            if (distanciaAcotada(termino, bucket[b], tope) <= tope &&
                exp[bucket[b]] === undefined) {
              exp[bucket[b]] = cfg.calidad.difusa;
            }
          }
        }
      }
      cacheExpansion[termino] = exp;
      return exp;
    }

    function buscarInsercion(arr, valor) {
      var lo = 0, hi = arr.length;
      while (lo < hi) {
        var mid = (lo + hi) >> 1;
        if (arr[mid] < valor) lo = mid + 1; else hi = mid;
      }
      return lo;
    }

    function idf(expansion) {
      var maxDf = 0;
      for (var t in expansion) if ((df[t] || 0) > maxDf) maxDf = df[t];
      return Math.log(1 + n / (1 + maxDf));
    }

    function normaLargo(nPalabras) {
      return 1 / (1 + cfg.factor_norma_largo * Math.max(0, nPalabras - 1));
    }

    var ETIQUETA = {
      cod: 'código', nom: 'nombre', hoja: 'producto', mat: 'material',
      mar: 'marca', cat: 'categoría', desc: 'descripción',
      prov: 'proveedor', proy: 'proyecto', medida: 'medida'
    };

    function buscar(texto, opciones) {
      opciones = opciones || {};
      var parsed = parsearConsulta(texto);
      var terms = parsed.terminos;
      var medidasPedidas = opciones.aplicarMedida === false ? [] : parsed.medidas;
      if (!terms.length && !medidasPedidas.length) {
        return { resultados: [], sugerencias: [], terminos: [], desconocidos: [], medidas: [] };
      }

      var expansiones = {}, pesosTermino = {}, pesoTotal = 0, desconocidos = [];
      terms.forEach(function (t) {
        var exp = expandir(t);
        expansiones[t] = exp;
        if (!Object.keys(exp).length) desconocidos.push(t);
        pesosTermino[t] = idf(exp);
        pesoTotal += pesosTermino[t];
      });
      if (!pesoTotal) pesoTotal = 1;

      var mejorPorItem = {};
      terms.forEach(function (t) {
        var exp = expansiones[t];
        for (var terminoIdx in exp) {
          var calidad = exp[terminoIdx];
          for (var ci = 0; ci < campos.length; ci++) {
            var campo = campos[ci];
            var ids = post[campo][terminoIdx];
            if (!ids) continue;
            var peso = pesos[campo] * calidad, largos = largo[campo];
            for (var k = 0; k < ids.length; k++) {
              var idx = ids[k];
              var valor = peso * normaLargo(largos[idx] || 1);
              var actual = mejorPorItem[idx] || (mejorPorItem[idx] = {});
              if (!actual[t] || valor > actual[t].valor) {
                actual[t] = { valor: valor, campo: campo, coincidencia: terminoIdx, calidad: calidad };
              }
            }
          }
        }
      });

      var candidatos = Object.keys(mejorPorItem);
      if (medidasPedidas.length && !terms.length) {
        for (var i2 = 0; i2 < n; i2++) {
          if (compartenMedida(medidasItem[i2], medidasPedidas) && !mejorPorItem[i2]) candidatos.push(String(i2));
        }
      }

      var puntuados = [];
      for (var c = 0; c < candidatos.length; c++) {
        var id = parseInt(candidatos[c], 10);
        var item = items[id];
        if (opciones.filtro && !opciones.filtro(item)) continue;
        var calzados = mejorPorItem[id] || {};

        var bruto = 0, cubierto = 0;
        for (var t2 in calzados) {
          bruto += calzados[t2].valor * pesosTermino[t2];
          cubierto += pesosTermino[t2];
        }
        var cobertura = cubierto / pesoTotal;
        var relevancia = bruto / (pesoTotal * pesoCampoMax);
        relevancia *= cfg.piso_cobertura + (1 - cfg.piso_cobertura) * cobertura * cobertura;

        var medidaOk = null;
        if (medidasPedidas.length) {
          if (compartenMedida(medidasItem[id], medidasPedidas)) {
            relevancia *= cfg.medida.exacta; medidaOk = true;
          } else if (medidasItem[id] && medidasItem[id].length) {
            relevancia *= cfg.medida.distinta; medidaOk = false;
          } else {
            relevancia *= cfg.medida.ausente;
          }
        }
        if (relevancia <= 0) continue;
        puntuados.push({
          idx: id, item: item, score: relevancia, cobertura: cobertura, medidaOk: medidaOk,
          motivos: motivosDe(calzados, medidasItem[id], medidasPedidas)
        });
      }

      puntuados.sort(function (a, b) {
        if (b.score !== a.score) return b.score - a.score;
        var na = String(a.item.nombre_item || ''), nb = String(b.item.nombre_item || '');
        return na < nb ? -1 : na > nb ? 1 : 0;
      });
      if (!puntuados.length) {
        return { resultados: [], sugerencias: [], terminos: terms, desconocidos: desconocidos, medidas: medidasPedidas };
      }

      var corte = Math.max(cfg.umbral_absoluto, puntuados[0].score * cfg.fraccion_del_mejor);
      var resultados = [], descartados = [];
      puntuados.forEach(function (p) { (p.score >= corte ? resultados : descartados).push(p); });

      return {
        resultados: resultados,
        sugerencias: sugerenciasDe(descartados),
        terminos: terms,
        desconocidos: desconocidos,
        medidas: medidasPedidas
      };
    }

    function compartenMedida(medidas, pedidas) {
      if (!medidas || !medidas.length) return false;
      for (var i = 0; i < pedidas.length; i++) {
        if (medidas.indexOf(pedidas[i]) !== -1) return true;
      }
      return false;
    }

    function motivosDe(calzados, medidasDelItem, medidasPedidas) {
      var motivos = Object.keys(calzados).map(function (t) {
        return {
          campo: calzados[t].campo, etiqueta: ETIQUETA[calzados[t].campo] || calzados[t].campo,
          termino: t, coincidencia: calzados[t].coincidencia,
          calidad: calzados[t].calidad, valor: calzados[t].valor
        };
      }).sort(function (a, b) { return b.valor - a.valor; });
      if (medidasPedidas.length && compartenMedida(medidasDelItem, medidasPedidas)) {
        var comunes = medidasPedidas.filter(function (m) { return medidasDelItem.indexOf(m) !== -1; }).sort();
        motivos.unshift({
          campo: 'medida', etiqueta: 'medida', termino: comunes[0],
          coincidencia: comunes[0], calidad: cfg.calidad.exacta, valor: Infinity
        });
      }
      return motivos;
    }

    function sugerenciasDe(descartados) {
      var salida = [];
      for (var i = 0; i < descartados.length && salida.length < cfg.max_sugerencias; i++) {
        var d = descartados[i];
        if (d.score < cfg.umbral_sugerencia || d.cobertura < cfg.min_cobertura_sugerencia) continue;
        var etiqueta = d.item.hoja || d.item.nombre_item;
        if (etiqueta && salida.indexOf(etiqueta) === -1) salida.push(etiqueta);
      }
      return salida;
    }

    // ---------- resaltado ----------
    // Resalta las PALABRAS que calzaron, no el string literal de la consulta.
    // El resaltado anterior buscaba la consulta completa como substring, asi
    // que en "valvula de bola 2" no marcaba absolutamente nada.
    function resaltar(texto, consulta, escapar) {
      var crudo = String(texto == null ? '' : texto);
      if (!consulta) return escapar(crudo);
      var parsed = parsearConsulta(consulta);
      var buscadas = {};
      parsed.terminos.forEach(function (t) {
        var exp = expandir(t);
        for (var e in exp) buscadas[e] = true;
      });
      var medidasNorm = {};
      parsed.medidas.forEach(function (m) { medidasNorm[normalizarAlias(m)] = true; });

      var salida = '', ultimo = 0;
      var re = /[\p{L}\p{N}][\p{L}\p{N}.,/'"“”-]*/gu;
      var m;
      while ((m = re.exec(crudo)) !== null) {
        var palabra = m[0];
        var marcar = Object.prototype.hasOwnProperty.call(buscadas, raiz(palabra)) ||
                     Object.prototype.hasOwnProperty.call(medidasNorm, normalizarAlias(palabra)) ||
                     Object.prototype.hasOwnProperty.call(
                       buscadas, palabra.replace(/[^a-zA-Z0-9]/g, '').toLowerCase());
        if (!marcar) continue;
        salida += escapar(crudo.slice(ultimo, m.index)) + '<mark>' + escapar(palabra) + '</mark>';
        ultimo = m.index + palabra.length;
      }
      return salida + escapar(crudo.slice(ultimo));
    }

    return {
      buscar: buscar,
      resaltar: resaltar,
      parsearConsulta: parsearConsulta,
      terminos: terminos,
      raiz: raiz,
      normalizar: normalizar,
      normalizarAlias: normalizarAlias
    };
  }

  global.CHBusqueda = { crear: crearBuscador, normalizar: normalizar, singular: singular,
                        normalizarAlias: normalizarAlias };
})(typeof globalThis !== 'undefined' ? globalThis : this);
