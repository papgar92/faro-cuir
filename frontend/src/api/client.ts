/**
 * Cliente tipado de la API real de Faro Cuir.
 *
 * Convive con `mocks.ts` a propósito: las pantallas siguen leyendo de los mocks hasta que
 * se migren una a una. Introducir el cliente sin tocar las pantallas hace que este paso no
 * pueda romper la demo, y deja el trabajo de migración reducido a cambiar de import.
 *
 * Los tipos son un espejo a mano de `backend/app/schemas/documento.py`. No se generan del
 * OpenAPI: son dos ficheros pequeños y estables, y la generación automática añadiría una
 * herramienta y un paso de build para ahorrar treinta líneas. Si la API crece mucho, se
 * revisa esta decisión.
 *
 * Las rutas son relativas (`/api/...`), nunca absolutas con host. En desarrollo las reenvía
 * el proxy de Vite al backend del puerto 8000; en producción frontend y API irán tras el
 * mismo origen. Así no hace falta CORS permisivo en ningún momento.
 */

/** Una norma dentro de un documento. Espejo de `NormaResumen`. */
export interface NormaApi {
  id: number;
  identificador_oficial: string;
  titulo: string;
  organo_emisor: string | null;
  /**
   * `rango` y `ambito` son null mientras el extractor no haya procesado la norma. Es
   * información, no un hueco: distingue "todavía no analizado" de "analizado y sin ámbito
   * claro", y la interfaz no debería pintar los dos casos igual.
   */
  rango: string | null;
  ambito: string | null;
  /** URL al texto íntegro en la fuente oficial. Es lo que debe usar el enlace de la Ficha. */
  url_texto: string | null;

  /**
   * Etapa 1 del pipeline (ADR 0007). `pendiente` significa que nadie la ha mirado todavía,
   * que no es lo mismo que `descartada`. La interfaz no debe pintar los dos casos igual.
   */
  prefiltro_estado: EstadoPrefiltro;
  /**
   * Términos del vocabulario que hicieron pasar la norma. `null` mientras está pendiente;
   * lista vacía cuando se evaluó y no coincidió nada.
   */
  prefiltro_terminos: string[] | null;
}

export type EstadoPrefiltro = "pendiente" | "relevante" | "descartada";

/** Un documento ingerido. Espejo de `DocumentoResumen`. */
export interface DocumentoApi {
  id: number;
  identificador_oficial: string;
  /** ISO 8601 (`YYYY-MM-DD`). */
  fecha_publicacion: string;
  url_original: string;
  /**
   * Huella del contenido archivado y momento en que se ingirió. Se exponen a propósito
   * (CLAUDE.md 6.5) para que cualquiera pueda verificar que lo archivado es lo publicado.
   */
  sha256: string;
  sello_tiempo: string;
  estado_pipeline: string;
}

export interface DocumentoDetalleApi extends DocumentoApi {
  normas: NormaApi[];
}

/** Error de la API con su código HTTP, para que quien llame pueda distinguir un 404. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function pedir<T>(ruta: string, signal?: AbortSignal): Promise<T> {
  const respuesta = await fetch(ruta, {
    signal,
    headers: { Accept: "application/json" },
  });

  if (!respuesta.ok) {
    throw new ApiError(
      respuesta.status,
      `La API respondió ${respuesta.status} en ${ruta}`,
    );
  }

  return (await respuesta.json()) as T;
}

export interface ListarDocumentosParams {
  /** Filtra por fecha de publicación, en formato `YYYY-MM-DD`. */
  fecha?: string;
  /** El backend impone un tope de 100; pedir más devuelve 422. */
  limite?: number;
  desplazamiento?: number;
}

export function listarDocumentos(
  params: ListarDocumentosParams = {},
  signal?: AbortSignal,
): Promise<DocumentoApi[]> {
  const query = new URLSearchParams();
  if (params.fecha) query.set("fecha", params.fecha);
  if (params.limite !== undefined) query.set("limite", String(params.limite));
  if (params.desplazamiento !== undefined) {
    query.set("desplazamiento", String(params.desplazamiento));
  }

  const sufijo = query.size > 0 ? `?${query}` : "";
  return pedir<DocumentoApi[]>(`/api/documentos${sufijo}`, signal);
}

export function obtenerDocumento(
  id: number,
  signal?: AbortSignal,
): Promise<DocumentoDetalleApi> {
  return pedir<DocumentoDetalleApi>(`/api/documentos/${id}`, signal);
}

// --- Cobertura de fuentes (ADR 0014) ---------------------------------------------------
//
// Espejo de `backend/app/schemas/cobertura.py`. Es el único endpoint de la API que publica
// un hueco en vez de un dato: cuántos boletines oficiales existen frente a cuántos se están
// leyendo de verdad. `conocidas` y `vigiladas` van siempre juntas a propósito — un solo
// número dejaría leer "8 fuentes" como si fueran ocho fuentes vigiladas.

export type AmbitoTerritorial = "estatal" | "autonomico" | "provincial" | "local";

export interface CoberturaNivelApi {
  ambito: AmbitoTerritorial;
  conocidas: number;
  vigiladas: number;
}

export interface CoberturaCcaaApi {
  ccaa_codigo: string;
  ccaa: string;
  niveles: CoberturaNivelApi[];
  conocidas: number;
  vigiladas: number;
}

export interface CoberturaApi {
  conocidas: number;
  vigiladas: number;
  por_ccaa: CoberturaCcaaApi[];
}

export function obtenerCobertura(signal?: AbortSignal): Promise<CoberturaApi> {
  return pedir<CoberturaApi>("/api/cobertura", signal);
}
