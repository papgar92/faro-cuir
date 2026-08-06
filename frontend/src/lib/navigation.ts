export type Screen = "mapa" | "alertas" | "archivo" | "ficha";

/**
 * Qué norma tiene que pintar la Ficha. Hacen falta los dos ids: la API expone las normas
 * anidadas dentro de su documento (`GET /api/documentos/{id}`), así que el documento es la
 * petición y la norma es la fila dentro de la respuesta.
 */
export interface SeleccionNorma {
  documentoId: number;
  normaId: number;
}

/**
 * Pantallas que todavía sirven datos inventados, para que el aviso de la interfaz se derive
 * de un único sitio y no de un booleano copiado en cada componente.
 *
 * El Mapa y las Alertas dependen de `deteccion` y `alerta`, vacías hasta que exista el
 * pipeline (CLAUDE.md sección 7). En cuanto una de las dos lea de la API, se quita de aquí.
 */
export const PANTALLAS_CON_MOCK: ReadonlySet<Screen> = new Set<Screen>(["mapa", "alertas"]);
