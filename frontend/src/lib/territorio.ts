/**
 * Del código ISO 3166-2:ES al nombre visible.
 *
 * La tabla no se escribe a mano: se deriva de la geometría del mapa, que ya tiene los
 * diecinueve códigos con su nombre y se genera desde el TopoJSON del IGN. Mantener dos listas
 * de comunidades es cómo se consigue que «Euskadi» en la interfaz y «País Vasco» en los datos
 * dejen de cruzar sin que nada falle — el fallo silencioso que `ccaa_codigo` existe para
 * evitar en el backend (ADR 0014).
 */

import { CCAA_PATHS } from "../components/MapaCCAA/ccaa-paths";

const NOMBRES: ReadonlyMap<string, string> = new Map(
  CCAA_PATHS.map((entidad) => [entidad.code, entidad.name]),
);

/**
 * `MD` → `Comunidad de Madrid`. `estatal` → `todo el Estado`.
 *
 * Un código que no se reconoce se devuelve tal cual en vez de traducirse a «desconocido»:
 * enseñar el código deja rastro de qué llegó, y «desconocido» lo borra.
 */
export function nombreTerritorio(codigo: string): string {
  if (codigo === "estatal") return "todo el Estado";
  if (codigo === "") return "territorio sin determinar";
  return NOMBRES.get(codigo) ?? codigo;
}
