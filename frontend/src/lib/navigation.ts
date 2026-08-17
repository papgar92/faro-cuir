export type Screen = "mapa" | "alertas" | "archivo" | "ficha" | "revision";

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
 * **Alertas salió de aquí el 2026-08-14**: con el gate humano implementado (ADR 0017) la tabla
 * `alerta` tiene filas y la pantalla las lee de `GET /api/alertas`.
 *
 * El Mapa sigue: necesita agregar por comunidad, y hoy hay una sola alerta emitida. Pintar un
 * mapa de España con un dato sería peor que el mock, porque parecería una medición.
 */
// Vacío desde el 2026-08-17: el Mapa fue la última pantalla con datos inventados. Se deja el
// conjunto —y no se borra el mecanismo— porque el aviso de maqueta es de las cosas que hay que
// poder volver a encender en cuanto alguien enseñe algo que no venga de la base de datos.
export const PANTALLAS_CON_MOCK: ReadonlySet<Screen> = new Set<Screen>();

/**
 * Pantallas que exigen sesión de revisión (ADR 0017). Hoy solo el panel del gate humano.
 *
 * El conjunto existe para que "esta pantalla es privada" se lea de un sitio y no de un `if`
 * repartido: no es un control de seguridad —el control está en el backend, que devuelve 401 y
 * no sirve nada— sino lo que evita que la interfaz prometa una pantalla que no va a poder
 * pintar.
 */
export const PANTALLAS_CON_SESION: ReadonlySet<Screen> = new Set<Screen>(["revision"]);
