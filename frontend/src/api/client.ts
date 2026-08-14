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
  /**
   * Qué eje disparó (7.3). `referencial` significa que esta norma **modifica una norma
   * vigilada**, diga lo que diga su texto: es el caso silencioso, y merece verse.
   */
  prefiltro_ejes: EjePrefiltro[] | null;
  /** Términos directos distintos. Es la magnitud que separa `relevante` de `sospecha`. */
  prefiltro_directos: number | null;
  /**
   * Prueba de archivo del texto íntegro. `null` mientras la fase 2 no lo haya descargado —
   * que no es lo mismo que "no existe", y la interfaz no debe pintarlo igual.
   */
  texto_archivado: TextoArchivadoApi | null;
}

/**
 * La huella de lo que se archivó. Espejo de `TextoArchivado` (CLAUDE.md 6.5).
 *
 * Se enseña en la interfaz, no solo se guarda: el proyecto afirma «el día X esta norma decía
 * esto», y esa afirmación no vale nada si quien la lee no puede comprobarla. Con el hash y la
 * fecha delante, cualquiera descarga el texto de la fuente y contrasta.
 */
export interface TextoArchivadoApi {
  sha256: string;
  sello_tiempo: string;
  url_original: string;
}

/**
 * Los CUATRO estados de 7.2. `sospecha` faltaba aquí hasta el 2026-08-09 y el tipo declaraba
 * imposible un valor que el backend lleva emitiendo desde la tarea 0.b — hoy hay 23 normas en
 * ese estado sobre datos reales.
 *
 * No es un valor más de la lista. `relevante` y `sospecha` **entran las dos en la cola del
 * extractor**: la diferencia entre ellas es de orden en la cola, no de cobertura. Cualquier
 * comparación `=== "relevante"` para decidir si una norma "pasa" pierde las sospechas en
 * silencio, que es exactamente el falso negativo que el proyecto no se puede permitir. Usa
 * `entraEnLaCola`.
 */
export type EstadoPrefiltro = "pendiente" | "sospecha" | "relevante" | "descartada";

export type EjePrefiltro = "lexico" | "referencial";

/**
 * Si una norma acaba pasando por el extractor. Espejo de la propiedad
 * `EstadoPrefiltro.entra_en_la_cola_del_extractor` del backend, que existe por el mismo
 * motivo: para que la cola no se escriba nunca como `=== "relevante"`.
 */
export function entraEnLaCola(estado: EstadoPrefiltro): boolean {
  return estado === "relevante" || estado === "sospecha";
}

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

// --- Alertas emitidas: lo aprobado, y solo lo aprobado ----------------------------------
//
// Espejo de `backend/app/schemas/alerta.py`. Que exista una fila aquí significa que **una
// persona la aprobó** (regla de oro 4): el endpoint lee de `alerta`, no de `deteccion`.
//
// Cada alerta viaja con lo que hace falta para no tener que creérsela: la regla que la produjo
// con su versión, los fragmentos recortados del texto archivado con sus offsets, y el `sha256`
// del documento con el enlace a la fuente oficial.

export interface NormaVigiladaAfectadaApi {
  identificador: string;
  titulo: string;
  /** `estatal` o el código ISO 3166-2:ES de la comunidad. Sale de la watchlist, no de la fuente. */
  ambito: string;
}

export interface AlertaApi {
  id: number;
  emitida_en: string;
  /** Fecha del boletín, no de cuándo lo procesamos: la cronología es de lo que pasó. */
  fecha_publicacion: string;
  clasificacion: "avance" | "retroceso" | "neutro" | "indeterminado";
  /** Declaradas por la regla y **sin calibrar**. Ordenan; no son una medición. */
  severidad: number;
  confianza: number;
  regla_aplicada: string | null;
  version_reglas: string | null;
  version_texto_plano: string | null;
  normas_vigiladas: NormaVigiladaAfectadaApi[];
  spans: SpanEvidenciaApi[];
  norma: {
    id: number;
    identificador_oficial: string;
    titulo: string;
    organo_emisor: string | null;
    url_texto: string | null;
  };
  texto_archivado: TextoArchivadoApi | null;
}

export interface ListarAlertasParams {
  clasificacion?: AlertaApi["clasificacion"];
  limite?: number;
  desplazamiento?: number;
}

export function listarAlertas(
  params: ListarAlertasParams = {},
  signal?: AbortSignal,
): Promise<AlertaApi[]> {
  const query = new URLSearchParams();
  if (params.clasificacion) query.set("clasificacion", params.clasificacion);
  if (params.limite !== undefined) query.set("limite", String(params.limite));
  if (params.desplazamiento !== undefined) {
    query.set("desplazamiento", String(params.desplazamiento));
  }
  const sufijo = query.size > 0 ? `?${query}` : "";
  return pedir<AlertaApi[]>(`/api/alertas${sufijo}`, signal);
}

// --- Panel de revisión: el gate humano (ADR 0017) ---------------------------------------
//
// La única parte de la API que escribe, y la única con sesión. Espejo de
// `backend/app/schemas/revision.py`.
//
// La sesión viaja en una cookie `HttpOnly`, así que **este código no ve el token y no puede
// verlo**: eso es lo que se quiere. No hay nada que guardar en `localStorage` ni que meter en
// una cabecera `Authorization`; el navegador manda la cookie sola porque las rutas son del
// mismo origen. Saber si hay sesión se pregunta al backend (`comprobarSesion`), no se deduce
// de una variable del cliente.

/** Un fragmento del texto archivado sobre el que se aplicó la regla (7.5 y 7.6). */
export interface SpanEvidenciaApi {
  inicio: number;
  fin: number;
  fragmento: string;
}

export interface ItemRevisionApi {
  id: number;
  estado: "pendiente" | "aprobada" | "descartada";
  creada_en: string;
  resuelta_en: string | null;
  nota_revision: string | null;

  deteccion_id: number;
  clasificacion: "avance" | "retroceso" | "neutro" | "indeterminado";
  origen: "derivado_diff" | "heuristica";
  regla_aplicada: string | null;
  /**
   * Declaradas por cada regla y **sin calibrar** contra ningún corpus. Sirven para ordenar la
   * cola, no para citarlas como dato; la interfaz tiene que decirlo donde se pintan.
   */
  severidad: number;
  confianza: number;
  version_reglas: string | null;
  version_texto_plano: string | null;
  normas_vigiladas: string[];
  spans: SpanEvidenciaApi[];

  /**
   * Que el extractor pasara por esta norma. El panel **no** publica lo que dijo el modelo
   * (reglas de oro 3 y 10): quien revisa decide sobre el texto archivado y la evidencia que
   * el catálogo recortó de él.
   */
  tiene_extraccion: boolean;
  punteros_corroborados: number;
  punteros_sin_corroborar: number;

  norma: {
    id: number;
    identificador_oficial: string;
    titulo: string;
    organo_emisor: string | null;
    url_texto: string | null;
    prefiltro_estado: EstadoPrefiltro;
    prefiltro_ejes: EjePrefiltro[] | null;
  };
  texto_archivado: TextoArchivadoApi | null;
}

/**
 * Cabecera propia en todo lo que escribe. Es el segundo control anti-CSRF del ADR 0017: no se
 * puede enviar entre orígenes sin un *preflight* de CORS, y este proyecto no activa CORS.
 */
const CABECERA_PANEL = "X-Faro-Panel";

async function escribir<T>(ruta: string, metodo: "POST" | "DELETE", cuerpo?: unknown): Promise<T> {
  const respuesta = await fetch(ruta, {
    method: metodo,
    // Explícito aunque sea el valor por defecto: es lo que hace que la cookie de sesión viaje,
    // y un cambio a `omit` rompería el panel de una forma difícil de diagnosticar.
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      [CABECERA_PANEL]: "1",
      ...(cuerpo === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });

  if (!respuesta.ok) {
    throw new ApiError(respuesta.status, `La API respondió ${respuesta.status} en ${ruta}`);
  }
  if (respuesta.status === 204) return undefined as T;
  return (await respuesta.json()) as T;
}

export function abrirSesionPanel(password: string): Promise<{ caduca_en: string }> {
  return escribir<{ caduca_en: string }>("/api/revision/sesion", "POST", { password });
}

export function cerrarSesionPanel(): Promise<void> {
  return escribir<void>("/api/revision/sesion", "DELETE");
}

/** 204 si la sesión vale, 401 si no. Lo que se consulta al entrar en el panel. */
export async function comprobarSesionPanel(signal?: AbortSignal): Promise<boolean> {
  const respuesta = await fetch("/api/revision/sesion", {
    signal,
    credentials: "same-origin",
  });
  if (respuesta.status === 204) return true;
  if (respuesta.status === 401) return false;
  throw new ApiError(respuesta.status, "La API respondió un estado inesperado al comprobar sesión");
}

export function listarColaRevision(
  estado: ItemRevisionApi["estado"] = "pendiente",
  signal?: AbortSignal,
): Promise<ItemRevisionApi[]> {
  return pedir<ItemRevisionApi[]>(`/api/revision/cola?estado=${estado}`, signal);
}

export function resolverRevision(
  id: number,
  accion: "aprobar" | "descartar",
  nota: string,
): Promise<ItemRevisionApi> {
  return escribir<ItemRevisionApi>(`/api/revision/cola/${id}/${accion}`, "POST", {
    nota: nota.trim() === "" ? null : nota.trim(),
  });
}
