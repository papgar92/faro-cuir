export type Screen = "mapa" | "alertas" | "hallazgos" | "archivo" | "revision";

/**
 * Qué norma está abierta en el Archivo. Hacen falta los dos ids: la API expone las normas
 * anidadas dentro de su documento (`GET /api/documentos/{id}`), así que el documento es la
 * petición y la norma es la fila dentro de la respuesta.
 *
 * **`ficha` dejó de ser una pantalla el 2026-09-05.** Era una entrada de menú que, pulsada en
 * frío, solo servía para mandarte a otra entrada de menú; y al abrirse volvía a pedir el mismo
 * documento de 160 KB que el Archivo acababa de descargar. Ahora la ficha es el panel derecho
 * del Archivo y esta selección viaja **también en la URL**, que es lo que faltaba: para un
 * archivo que se ofrece como verificable, «mira esta norma y su huella» tiene que ser un enlace.
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

/**
 * La pantalla y la comunidad, en la barra de direcciones.
 *
 * ## Por qué hacía falta
 *
 * Hasta ahora **ninguna pantalla tenía URL**: todo el estado vivía en `useState`, así que
 * `localhost:5174` llevaba siempre al mapa y no había forma de enlazar nada. Para un observatorio
 * eso no es un detalle de comodidad — «mándame el enlace de Andalucía» o «mira esta alerta» es la
 * acción de compartir principal, y es la que convierte una consulta en una cita. Las
 * organizaciones de referencia (ILGA con `/country/spain/`) lo tienen resuelto desde siempre.
 *
 * ## Por qué no hay router
 *
 * Porque no hace falta: son seis pantallas y un parámetro. `URLSearchParams` más
 * `history.replaceState` lo resuelven en veinte líneas, sin dependencia nueva y sin servidor que
 * tenga que saber de rutas. Meter `react-router` para esto sería añadir una capa que hay que
 * auditar (sección 3: nada de dependencias que no ganen su sitio).
 *
 * `replaceState` y no `pushState`: la selección de comunidad cambia al pasar el ratón, y empujar
 * una entrada de historial por cada hover dejaría el botón «atrás» inservible.
 */
export interface EstadoUrl {
  screen: Screen;
  ccaa?: string;
  /** El documento abierto en el Archivo, y la norma abierta dentro de él. */
  doc?: number;
  norma?: number;
}

const PANTALLAS: ReadonlySet<string> = new Set<string>([
  "mapa",
  "alertas",
  "hallazgos",
  "archivo",
  "revision",
]);

/**
 * Un id de la URL, o `undefined`.
 *
 * Solo entero positivo: la cadena va a un `GET /api/documentos/{id}`, así que lo que no sea un
 * id se descarta aquí y no se compone con nada. Es el mismo criterio de 6.10 aplicado a la
 * barra de direcciones — un valor que viene de fuera no acciona nada sin validarse.
 */
function idDeUrl(valor: string | null): number | undefined {
  if (valor === null || !/^\d{1,9}$/.test(valor)) return undefined;
  const numero = Number(valor);
  return numero > 0 ? numero : undefined;
}

/** Lee la URL al arrancar. Cualquier valor que no reconozca cae al mapa, sin fallar. */
export function leerUrl(busqueda: string): EstadoUrl {
  const params = new URLSearchParams(busqueda);
  const pantalla = params.get("pantalla") ?? "";
  const ccaa = params.get("ccaa") ?? undefined;
  return {
    screen: PANTALLAS.has(pantalla) ? (pantalla as Screen) : "mapa",
    // El código de comunidad se valida en destino contra la geometría del mapa, no aquí: este
    // módulo no sabe qué territorios existen y no debe empezar a saberlo.
    ccaa: ccaa || undefined,
    doc: idDeUrl(params.get("doc")),
    norma: idDeUrl(params.get("norma")),
  };
}

/** Escribe la URL sin tocar el historial. */
export function escribirUrl(estado: EstadoUrl): void {
  const params = new URLSearchParams();
  // El mapa es la pantalla por defecto, así que no se escribe: `?pantalla=mapa` en la barra de
  // direcciones es ruido que no dice nada.
  if (estado.screen !== "mapa") params.set("pantalla", estado.screen);
  if (estado.ccaa) params.set("ccaa", estado.ccaa);
  if (estado.doc !== undefined) params.set("doc", String(estado.doc));
  // Sin documento, una norma suelta no identifica nada: la API pide el documento y busca la
  // norma dentro. Se omite en vez de escribir un enlace que no se puede resolver.
  if (estado.doc !== undefined && estado.norma !== undefined) {
    params.set("norma", String(estado.norma));
  }
  const cadena = params.toString();
  window.history.replaceState(null, "", cadena ? `?${cadena}` : window.location.pathname);
}
