/* pulso.js — Cuán al día está la carpeta de intercambio, leído de
 * publicado/estado.json (lo escribe el procesador en cada vuelta).
 *
 * Por qué existe (2026-10-08): la tarea del procesador estuvo deshabilitada
 * del 05-10 al 08-10 y nadie se enteró. Los envíos al Análisis Financiero
 * esperaron hasta 28 horas, y la única señal era un punto ámbar en la
 * configuración del Formulador. Ahora, si el procesador lleva más de
 * DETENIDO_HORAS_HABILES horas de horario hábil sin correr (dos vueltas
 * perdidas), las herramientas lo dicen con un aviso rojo. Las horas fuera del
 * horario no cuentan: con el computador apagado de noche o el fin de semana
 * el procesador espera, y eso no es una falla.
 *
 * Lo usan el Formulador (copia textual en js/pulso.js) y la pestaña «Ingresar
 * datos» del tablero de Análisis Financiero (su build lo inserta). Si cambias
 * este archivo, vuelve a copiarlo al Formulador (un test compara las dos).
 */
(function (root) {
  'use strict';

  // Horario hábil del equipo, en la hora local del navegador: lunes (1) a
  // viernes (5), de 08:30 a 19:00.
  const HORARIO = { dias: [1, 2, 3, 4, 5], desde: 8.5, hasta: 19 };
  // El procesador corre cada 2 horas (decisión del usuario, 2026-10-02): en
  // verde hasta 2 h y media, para no marcar «atrasado» entre dos corridas.
  const VERDE_HASTA_MIN = 150;
  const DETENIDO_HORAS_HABILES = 4;

  /* Minutos de horario hábil entre dos fechas (Date). */
  function minutosHabiles(desde, hasta, horario) {
    const h = horario || HORARIO;
    if (!(desde instanceof Date) || !(hasta instanceof Date) || !(hasta > desde)) return 0;
    let total = 0;
    const dia = new Date(desde.getFullYear(), desde.getMonth(), desde.getDate());
    for (let i = 0; dia <= hasta && i < 800; i++, dia.setDate(dia.getDate() + 1)) {
      if (h.dias.indexOf(dia.getDay()) < 0) continue;
      const ini = new Date(dia.getFullYear(), dia.getMonth(), dia.getDate(), 0, Math.round(h.desde * 60));
      const fin = new Date(dia.getFullYear(), dia.getMonth(), dia.getDate(), 0, Math.round(h.hasta * 60));
      const a = Math.max(ini.getTime(), desde.getTime());
      const b = Math.min(fin.getTime(), hasta.getTime());
      if (b > a) total += (b - a) / 60000;
    }
    return Math.round(total);
  }

  function haceCuanto(min) {
    if (min < 1) return 'hace menos de un minuto';
    if (min < 60) return `hace ${min} min`;
    if (min < 48 * 60) return `hace ${Math.round(min / 60)} h`;
    return `hace ${Math.round(min / 1440)} días`;
  }

  /* { nivel: 'ok'|'warn'|'bad', detenido, texto, minutos, minutosHabiles }, o
     null si no hay estado. 'ahora' se puede fijar (pruebas). */
  function lectura(estado, ahora) {
    const ultima = estado && estado.procesador && estado.procesador.ultimaCorrida;
    const t = ultima ? new Date(ultima) : null;
    if (!t || isNaN(t)) return null;
    const ya = ahora || new Date();
    const min = Math.max(0, Math.round((ya - t) / 60000));
    const habiles = minutosHabiles(t, ya);
    const pasos = estado.procesador.pasos || {};
    const fallas = Object.keys(pasos).filter((k) => pasos[k] && pasos[k].ok === false);
    const detenido = habiles > DETENIDO_HORAS_HABILES * 60;
    const nivel = detenido ? 'bad' : fallas.length ? 'warn' : min <= VERDE_HASTA_MIN ? 'ok' : 'warn';
    const texto = detenido
      ? `El procesador del intercambio no corre desde ${haceCuanto(min)}: lo que se envíe a las demás herramientas queda esperando hasta que vuelva a correr. Avisa a quien administra las herramientas QUEMPIN.`
      : `Las demás herramientas revisaron la carpeta ${haceCuanto(min)}` + (fallas.length ? ` (con problemas en: ${fallas.join(', ')})` : '') + '.';
    return { nivel, detenido, texto, minutos: min, minutosHabiles: habiles };
  }

  root.QPulso = { lectura, minutosHabiles, HORARIO, VERDE_HASTA_MIN, DETENIDO_HORAS_HABILES };
})(typeof window !== 'undefined' ? window : globalThis);
