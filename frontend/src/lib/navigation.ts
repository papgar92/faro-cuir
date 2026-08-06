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
