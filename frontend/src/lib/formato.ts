/** Formateo de los valores que llegan de la API. Nada de esto añade información: solo la presenta. */

const MESES = [
  "ene",
  "feb",
  "mar",
  "abr",
  "may",
  "jun",
  "jul",
  "ago",
  "sep",
  "oct",
  "nov",
  "dic",
];

/**
 * `2024-12-19` → `19 dic 2024`.
 *
 * Se parte la cadena a mano en vez de usar `new Date(iso)`: con una fecha sin hora, el
 * constructor la interpreta como medianoche **UTC** y al formatearla en local puede retroceder
 * un día. Aquí no hay zona horaria que aplicar — la fecha de publicación de un boletín es un
 * día del calendario, no un instante.
 */
export function formatearFecha(iso: string): string {
  const [anio, mes, dia] = iso.split("-");
  const indiceMes = Number(mes) - 1;
  if (!anio || !dia || Number.isNaN(indiceMes) || !MESES[indiceMes]) return iso;
  return `${Number(dia)} ${MESES[indiceMes]} ${anio}`;
}

/**
 * El sello de tiempo sí es un instante, y se muestra en UTC a propósito: es un dato de
 * verificación (CLAUDE.md 6.5), y quien compare nuestro archivo con el suyo necesita leer el
 * mismo valor esté donde esté, no uno traducido a su zona.
 */
export function formatearSelloTiempo(iso: string): string {
  const momento = new Date(iso);
  if (Number.isNaN(momento.getTime())) return iso;
  return `${momento.toISOString().slice(0, 19).replace("T", " ")}Z`;
}

/** Primeros y últimos caracteres del hash, para listados donde no cabe entero. */
export function acortarHash(sha256: string): string {
  if (sha256.length <= 20) return sha256;
  return `${sha256.slice(0, 10)}…${sha256.slice(-6)}`;
}
