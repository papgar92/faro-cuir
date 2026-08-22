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
  // `slice(0, 10)` porque esto recibe las dos formas: `fecha_publicacion` es una fecha suelta
  // (`2014-11-06`) pero `generado_en` de un informe es un instante completo
  // (`2026-08-21T20:50:00Z`). Sin recortar, el dia salia como `21T20:50:00Z` y la pantalla
  // publicaba «el NaN ago 2026» — visto en el navegador el 2026-08-22, no por ningun test.
  const [anio, mes, dia] = iso.slice(0, 10).split("-");
  const indiceMes = Number(mes) - 1;
  const numeroDia = Number(dia);
  // Se comprueba que el dia sea un NUMERO, no solo que exista: esa era exactamente la grieta
  // por la que se colaba el NaN.
  if (!anio || !dia || Number.isNaN(numeroDia) || Number.isNaN(indiceMes) || !MESES[indiceMes]) {
    return iso;
  }
  return `${numeroDia} ${MESES[indiceMes]} ${anio}`;
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
