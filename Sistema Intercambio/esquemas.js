/* esquemas.js — Gemelo de esquemas.py para el navegador y Node.
 *
 * Mismo algoritmo y mismos textos de error que esquemas.py (los clava
 * tests/test_esquemas.py, que corre los dos sobre los mismos ejemplos). Los
 * esquemas no viajan dentro de este archivo: el procesador del intercambio
 * los deja en la carpeta como esquemas.json (esquemas.paquete()), así una
 * herramienta web valida con el catálogo vigente sin copiarlo.
 *
 * Copias: el Formulador lleva una copia textual en js/esquemas.js. Si cambias
 * este archivo, vuelve a copiarlo allá (un test compara las dos).
 */
(function (root) {
  'use strict';

  const RAIZ_RUTA = '(raíz)';
  const NOMBRE_TIPO = {
    string: 'texto', number: 'número', integer: 'número entero', boolean: 'verdadero o falso',
    array: 'lista', object: 'objeto', null: 'vacío'
  };

  const esNumero = (v) => typeof v === 'number' && Number.isFinite(v);
  const esObjeto = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

  function esTipo(v, tipo) {
    switch (tipo) {
      case 'null': return v === null;
      case 'boolean': return typeof v === 'boolean';
      case 'integer': return esNumero(v) && Number.isInteger(v);
      case 'number': return esNumero(v);
      case 'string': return typeof v === 'string';
      case 'array': return Array.isArray(v);
      case 'object': return esObjeto(v);
      default: return false;
    }
  }

  function fmt(valor) {
    if (esNumero(valor) && Number.isInteger(valor)) return String(valor);
    if (typeof valor === 'string') return "'" + valor + "'";
    return JSON.stringify(valor);
  }

  const hija = (ruta, clave) => (typeof clave === 'number'
    ? ruta + '[' + clave + ']'
    : (ruta === RAIZ_RUTA ? clave : ruta + '.' + clave));

  const largo = (s) => Array.from(s).length;   // puntos de código, como len() de Python

  function validar(valor, esquema, ruta) {
    const errores = [];
    validarEn(valor, esquema, ruta || RAIZ_RUTA, errores);
    return errores;
  }

  function validarEn(v, s, ruta, errores) {
    if (s.anyOf) {
      if (!s.anyOf.some((rama) => validar(v, rama, ruta).length === 0)) {
        errores.push(ruta + ': no cumple ninguna de las formas permitidas');
      }
      return;
    }
    if (s.type !== undefined) {
      const tipos = Array.isArray(s.type) ? s.type : [s.type];
      if (!tipos.some((t) => esTipo(v, t))) {
        errores.push(ruta + ': debe ser ' + tipos.map((t) => NOMBRE_TIPO[t] || t).join(' o '));
        return;
      }
    }
    if (Object.prototype.hasOwnProperty.call(s, 'const') && v !== s.const) {
      errores.push(ruta + ': debe ser ' + fmt(s.const));
      return;
    }
    if (s.enum && !s.enum.some((op) => op === v)) {
      errores.push(ruta + ': valor no permitido (se acepta: ' + s.enum.map(fmt).join(', ') + ')');
      return;
    }
    if (typeof v === 'string') {
      if (s.minLength !== undefined && largo(v) < s.minLength) {
        errores.push(ruta + ': debe tener al menos ' + s.minLength + ' caracter(es)');
      }
      if (s.pattern !== undefined && !new RegExp(s.pattern).test(v)) {
        errores.push(ruta + ': no tiene el formato esperado');
      }
    }
    if (esNumero(v)) {
      if (s.minimum !== undefined && v < s.minimum) errores.push(ruta + ': debe ser mayor o igual a ' + fmt(s.minimum));
      if (s.exclusiveMinimum !== undefined && v <= s.exclusiveMinimum) errores.push(ruta + ': debe ser mayor que ' + fmt(s.exclusiveMinimum));
      if (s.maximum !== undefined && v > s.maximum) errores.push(ruta + ': debe ser menor o igual a ' + fmt(s.maximum));
    }
    if (Array.isArray(v)) {
      if (s.minItems !== undefined && v.length < s.minItems) {
        errores.push(ruta + ': debe tener al menos ' + s.minItems + ' elemento(s)');
      }
      if (esObjeto(s.items)) v.forEach((x, i) => validarEn(x, s.items, hija(ruta, i), errores));
    }
    if (esObjeto(v)) {
      (s.required || []).forEach((campo) => {
        if (!Object.prototype.hasOwnProperty.call(v, campo)) errores.push(ruta + ": falta '" + campo + "'");
      });
      const props = s.properties || {};
      Object.keys(props).forEach((clave) => {
        if (Object.prototype.hasOwnProperty.call(v, clave)) validarEn(v[clave], props[clave], hija(ruta, clave), errores);
      });
      const adicionales = s.additionalProperties === undefined ? true : s.additionalProperties;
      if (adicionales !== true) {
        Object.keys(v).forEach((clave) => {
          if (Object.prototype.hasOwnProperty.call(props, clave)) return;
          if (adicionales === false) errores.push(ruta + ": campo no permitido '" + clave + "'");
          else if (esObjeto(adicionales)) validarEn(v[clave], adicionales, hija(ruta, clave), errores);
        });
      }
    }
  }

  /* paquete = esquemas.json de la carpeta: {sobreMensaje, sobrePublicacion, mensajes, publicaciones}. */
  function validarMensaje(mensaje, paquete) {
    const errores = validar(mensaje, paquete.sobreMensaje);
    const esquema = errores.length ? null : (paquete.mensajes || {})[mensaje.tipo];
    if (!esquema) return errores;
    if (esquema.destino && mensaje.destino !== esquema.destino) {
      errores.push("destino: el tipo '" + mensaje.tipo + "' va a '" + esquema.destino + "', no a '" + mensaje.destino + "'");
    }
    return errores.concat(validar(mensaje, esquema));
  }

  function validarPublicacion(nombre, sobre, paquete) {
    const esquema = (paquete.publicaciones || {})[nombre];
    if (!esquema) return ["publicación desconocida: '" + nombre + "'"];
    if (nombre === 'formulador-proyecto') return validar(sobre, esquema);
    const errores = validar(sobre, paquete.sobrePublicacion);
    return errores.length ? errores : validar(sobre.datos, esquema, 'datos');
  }

  const api = { validar, validarMensaje, validarPublicacion };
  root.QEsquemas = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
